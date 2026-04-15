"""
本地K线数据导入 单元测试

覆盖：
- 配置项读取和默认值（需求 7）
- 目录不存在时的错误处理（需求 1.3）
- ZIP 文件损坏时的跳过行为（需求 2.4）
- CSV 行格式不合法时的跳过行为（需求 2.5）
- API 端点 202/409 响应（需求 10.3, 10.4）
- 并发任务保护（需求 6.4）
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.local_kline_import import LocalKlineImportService


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_zip_bytes(csv_content: str, inner_name: str = "data.csv") -> bytes:
    """构造内存 ZIP 文件的字节内容。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(inner_name, csv_content)
    return buf.getvalue()


def _make_corrupt_zip_bytes() -> bytes:
    """构造损坏的 ZIP 文件字节。"""
    return b"PK\x03\x04this-is-not-a-valid-zip-file"


# ---------------------------------------------------------------------------
# 需求 7：配置项读取和默认值
# ---------------------------------------------------------------------------


class TestConfig:
    def test_default_local_kline_data_dir(self):
        """Settings 默认 local_kline_data_dir 为 /Users/poper/AData。"""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            timescale_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.local_kline_data_dir == "/Users/poper/AData"

    def test_env_override_local_kline_data_dir(self, monkeypatch):
        """环境变量 LOCAL_KLINE_DATA_DIR 可覆盖默认值。"""
        from app.core.config import Settings

        monkeypatch.setenv("LOCAL_KLINE_DATA_DIR", "/tmp/custom_data")
        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            timescale_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.local_kline_data_dir == "/tmp/custom_data"


# ---------------------------------------------------------------------------
# 需求 1.3：目录不存在时的错误处理
# ---------------------------------------------------------------------------


class TestDirectoryNotExists:
    def test_scan_nonexistent_dir_returns_empty(self):
        """扫描不存在的目录返回空列表。"""
        svc = LocalKlineImportService()
        result = svc.scan_zip_files("/nonexistent/path/that/does/not/exist")
        assert result == []

    def test_scan_nonexistent_subdir_returns_empty(self, tmp_path):
        """扫描存在的根目录但不存在的子目录返回空列表。"""
        svc = LocalKlineImportService()
        result = svc.scan_zip_files(str(tmp_path), sub_dir="no_such_subdir")
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_nonexistent_dir_returns_failed(self):
        """execute 对不存在的目录返回 status=failed。"""
        svc = LocalKlineImportService()
        with patch.object(svc, "update_progress", new_callable=AsyncMock):
            with patch(
                "app.services.data_engine.local_kline_import.settings"
            ) as mock_settings:
                mock_settings.local_kline_data_dir = "/nonexistent/dir/xyz"
                result = await svc.execute()

        assert result["status"] == "failed"
        assert "目录不存在" in result["error"]
        assert result["total_files"] == 0


# ---------------------------------------------------------------------------
# 需求 2.4：ZIP 文件损坏时的跳过行为
# ---------------------------------------------------------------------------


class TestCorruptZip:
    def test_corrupt_zip_returns_empty(self, tmp_path):
        """损坏的 ZIP 文件解析返回空列表，不抛异常。"""
        svc = LocalKlineImportService()
        # 创建符合路径推断规则的目录结构
        symbol_dir = tmp_path / "000001"
        symbol_dir.mkdir()
        corrupt_file = symbol_dir / "1m.zip"
        corrupt_file.write_bytes(_make_corrupt_zip_bytes())

        bars, parsed, skipped = svc.extract_and_parse_zip(corrupt_file)
        assert bars == []
        assert parsed == 0
        assert skipped == 0

    def test_corrupt_zip_does_not_raise(self, tmp_path):
        """损坏的 ZIP 文件不会导致异常传播。"""
        svc = LocalKlineImportService()
        symbol_dir = tmp_path / "600519"
        symbol_dir.mkdir()
        bad_file = symbol_dir / "5m.zip"
        bad_file.write_bytes(b"not a zip at all")

        # 不应抛出异常
        bars, parsed, skipped = svc.extract_and_parse_zip(bad_file)
        assert bars == []


# ---------------------------------------------------------------------------
# 需求 2.5：CSV 行格式不合法时的跳过行为
# ---------------------------------------------------------------------------


class TestInvalidCsvRows:
    def test_insufficient_fields_skipped(self):
        """字段不足的 CSV 行被跳过。"""
        svc = LocalKlineImportService()
        csv_text = "2024-01-15 09:30:00,10.5,11.0\n"  # 只有 3 个字段
        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m")
        assert bars == []
        assert skipped == 1

    def test_invalid_number_skipped(self):
        """数值字段非法的 CSV 行被跳过。"""
        svc = LocalKlineImportService()
        csv_text = "2024-01-15 09:30:00,abc,11.0,10.0,10.5,1000,50000\n"
        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m")
        assert bars == []
        assert skipped == 1

    def test_valid_rows_parsed_invalid_skipped(self):
        """混合有效和无效行时，有效行被解析，无效行被跳过。"""
        svc = LocalKlineImportService()
        csv_text = (
            "2024-01-15 09:30:00,10.0,11.0,9.5,10.5,1000,50000\n"
            "bad,row,only\n"
            "2024-01-15 09:31:00,10.1,11.1,9.6,10.6,2000,60000\n"
        )
        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m")
        assert len(bars) == 2
        assert skipped == 1

    def test_header_row_skipped(self):
        """表头行被自动跳过。"""
        svc = LocalKlineImportService()
        csv_text = (
            "time,open,high,low,close,volume,amount\n"
            "2024-01-15 09:30:00,10.0,11.0,9.5,10.5,1000,50000\n"
        )
        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m")
        assert len(bars) == 1
        assert skipped == 0

    def test_invalid_datetime_skipped(self):
        """无法解析的时间字段导致该行被跳过。"""
        svc = LocalKlineImportService()
        csv_text = "not-a-date,10.0,11.0,9.5,10.5,1000,50000\n"
        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m")
        assert bars == []
        assert skipped == 1

    def test_empty_csv_returns_empty(self):
        """空 CSV 内容返回空列表。"""
        svc = LocalKlineImportService()
        bars, skipped = svc.parse_csv_content("", "000001", "1m")
        assert bars == []
        assert skipped == 0


# ---------------------------------------------------------------------------
# 需求 10.3, 10.4：API 端点 202/409 响应
# ---------------------------------------------------------------------------


class TestLocalKlineImportAPI:
    @pytest.mark.asyncio
    async def test_post_returns_202_on_success(self):
        """成功触发导入任务返回 HTTP 202 和 task_id。"""
        mock_task_result = MagicMock()
        mock_task_result.id = "test-task-id-123"

        with patch(
            "app.services.data_engine.local_kline_import.LocalKlineImportService.is_running",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "app.tasks.data_sync.import_local_kline.delay",
            return_value=mock_task_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/import/local-kline",
                    json={"freqs": ["1m", "5m"], "force": False},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"] == "test-task-id-123"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_post_returns_409_when_running(self):
        """已有导入任务运行中时返回 HTTP 409。"""
        with patch(
            "app.services.data_engine.local_kline_import.LocalKlineImportService.is_running",
            new_callable=AsyncMock,
            return_value=True,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/import/local-kline",
                    json={},
                )

        assert resp.status_code == 409
        assert "已有导入任务正在运行" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_status_returns_idle_when_no_data(self):
        """Redis 无数据时返回 idle 默认状态。"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.aclose = AsyncMock()

        with patch(
            "app.core.redis_client.get_redis_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/import/local-kline/status"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["total_files"] == 0

    @pytest.mark.asyncio
    async def test_get_status_returns_running_progress(self):
        """返回正在运行的导入进度。"""
        import time

        progress = json.dumps({
            "status": "running",
            "total_files": 50,
            "processed_files": 20,
            "success_files": 18,
            "failed_files": 2,
            "total_parsed": 10000,
            "total_inserted": 9500,
            "total_skipped": 500,
            "elapsed_seconds": 45.3,
            "failed_details": [{"path": "bad.zip", "error": "损坏"}],
            "heartbeat": time.time(),  # 活跃心跳，非僵尸任务
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[progress, None])
        mock_client.aclose = AsyncMock()

        with patch(
            "app.core.redis_client.get_redis_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/import/local-kline/status"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["total_files"] == 50
        assert data["processed_files"] == 20
        assert data["failed_files"] == 2


# ---------------------------------------------------------------------------
# 需求 6.4：并发任务保护
# ---------------------------------------------------------------------------


class TestConcurrencyProtection:
    @pytest.mark.asyncio
    async def test_is_running_returns_true_when_running(self):
        """Redis 中 status=running 且心跳活跃时 is_running 返回 True。"""
        import time

        svc = LocalKlineImportService()
        progress = json.dumps({"status": "running", "heartbeat": time.time()})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=progress)
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ):
            assert await svc.is_running() is True

    @pytest.mark.asyncio
    async def test_is_running_returns_false_when_completed(self):
        """Redis 中 status=completed 时 is_running 返回 False。"""
        svc = LocalKlineImportService()
        progress = json.dumps({"status": "completed"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=progress)
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ):
            assert await svc.is_running() is False

    @pytest.mark.asyncio
    async def test_is_running_returns_false_when_no_data(self):
        """Redis 无进度数据时 is_running 返回 False。"""
        svc = LocalKlineImportService()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ):
            assert await svc.is_running() is False

    @pytest.mark.asyncio
    async def test_api_rejects_concurrent_import(self):
        """连续两次 POST 请求，第二次应返回 409。"""
        mock_task_result = MagicMock()
        mock_task_result.id = "task-1"

        # 第一次调用 is_running=False，第二次 is_running=True
        call_count = 0

        async def is_running_side_effect(self_arg=None):
            nonlocal call_count
            call_count += 1
            return call_count > 1

        with patch(
            "app.services.data_engine.local_kline_import.LocalKlineImportService.is_running",
            new_callable=AsyncMock,
            side_effect=is_running_side_effect,
        ), patch(
            "app.tasks.data_sync.import_local_kline.delay",
            return_value=mock_task_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp1 = await client.post(
                    "/api/v1/data/import/local-kline", json={}
                )
                resp2 = await client.post(
                    "/api/v1/data/import/local-kline", json={}
                )

        assert resp1.status_code == 202
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# 需求 7.2：市场分类过滤
# ---------------------------------------------------------------------------


class TestMarketCategoryFiltering:
    """市场分类过滤测试（需求 7.2）"""

    def _create_market_structure(self, tmp_path: Path) -> None:
        """在 tmp_path 下创建三个市场的四级目录结构并放入 dummy ZIP。"""
        for market_dir_name in (
            "A股_分时数据_沪深",
            "A股_分时数据_京市",
            "A股_分时数据_指数",
        ):
            month_dir = tmp_path / market_dir_name / "1分钟_按月归档" / "2026-01"
            month_dir.mkdir(parents=True)
            zip_path = month_dir / "20260102_1min.zip"
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("dummy.csv", "placeholder")
            zip_path.write_bytes(buf.getvalue())

    def test_scan_market_zip_files_filters_by_market(self, tmp_path):
        """指定 markets=["hushen"] 时仅返回沪深目录下的文件。"""
        self._create_market_structure(tmp_path)
        svc = LocalKlineImportService()

        results = svc.scan_market_zip_files(
            str(tmp_path), markets=["hushen"],
        )

        assert len(results) == 1
        zip_path, market, freq = results[0]
        assert market == "hushen"
        assert "A股_分时数据_沪深" in str(zip_path)

    def test_scan_market_zip_files_all_markets_when_none(self, tmp_path):
        """markets=None 时返回所有三个市场的文件。"""
        self._create_market_structure(tmp_path)
        svc = LocalKlineImportService()

        results = svc.scan_market_zip_files(
            str(tmp_path), markets=None,
        )

        returned_markets = {r[1] for r in results}
        assert returned_markets == {"hushen", "jingshi", "zhishu"}
        assert len(results) == 3

    def test_infer_market_from_path(self, tmp_path):
        """infer_market_from_path 从路径部分正确识别市场分类。"""
        svc = LocalKlineImportService()

        hushen_path = tmp_path / "A股_分时数据_沪深" / "1分钟_按月归档" / "2026-01" / "20260102_1min.zip"
        assert svc.infer_market_from_path(hushen_path) == "hushen"

        jingshi_path = tmp_path / "A股_分时数据_京市" / "5分钟_按月归档" / "2026-01" / "20260102_5min.zip"
        assert svc.infer_market_from_path(jingshi_path) == "jingshi"

        zhishu_path = tmp_path / "A股_分时数据_指数" / "15分钟_按月归档" / "2026-01" / "20260102_15min.zip"
        assert svc.infer_market_from_path(zhishu_path) == "zhishu"

        unknown_path = tmp_path / "unknown_dir" / "data.zip"
        assert svc.infer_market_from_path(unknown_path) is None


# ---------------------------------------------------------------------------
# 需求 9.2：月份范围过滤
# ---------------------------------------------------------------------------


class TestMonthRangeFiltering:
    """月份范围过滤测试（需求 9.2）"""

    def _create_months_structure(self, tmp_path: Path, months: list[str]) -> None:
        """在 tmp_path 下创建沪深市场指定月份的目录结构。"""
        for month in months:
            month_dir = tmp_path / "A股_分时数据_沪深" / "1分钟_按月归档" / month
            month_dir.mkdir(parents=True)
            zip_path = month_dir / f"{month.replace('-', '')}01_1min.zip"
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("dummy.csv", "placeholder")
            zip_path.write_bytes(buf.getvalue())

    def test_scan_market_zip_files_filters_by_month_range(self, tmp_path):
        """start_date/end_date 过滤后仅返回范围内的月份。"""
        self._create_months_structure(tmp_path, ["2025-06", "2026-01", "2026-06"])
        svc = LocalKlineImportService()

        results = svc.scan_market_zip_files(
            str(tmp_path),
            markets=["hushen"],
            start_date="2025-09",
            end_date="2026-03",
        )

        assert len(results) == 1
        zip_path, market, freq = results[0]
        assert "2026-01" in str(zip_path)

    def test_scan_market_zip_files_no_month_filter(self, tmp_path):
        """不指定月份范围时返回所有月份的文件。"""
        self._create_months_structure(tmp_path, ["2025-06", "2026-01", "2026-06"])
        svc = LocalKlineImportService()

        results = svc.scan_market_zip_files(
            str(tmp_path),
            markets=["hushen"],
        )

        assert len(results) == 3


# ---------------------------------------------------------------------------
# 需求 10.3：复权因子导入
# ---------------------------------------------------------------------------


class TestAdjFactorImport:
    """复权因子导入测试（需求 10.3, 10.4）"""

    def test_infer_symbol_from_adj_csv_name_sz(self):
        """000001.SZ.csv → 000001"""
        svc = LocalKlineImportService()
        assert svc.infer_symbol_from_adj_csv_name("000001.SZ.csv") == "000001"

    def test_infer_symbol_from_adj_csv_name_sh(self):
        """600000.SH.csv → 600000"""
        svc = LocalKlineImportService()
        assert svc.infer_symbol_from_adj_csv_name("600000.SH.csv") == "600000"

    def test_infer_symbol_from_adj_csv_name_invalid(self):
        """非法文件名返回 None。"""
        svc = LocalKlineImportService()
        assert svc.infer_symbol_from_adj_csv_name("invalid_name.csv") is None
        assert svc.infer_symbol_from_adj_csv_name("abc.SZ.csv") is None

    def test_parse_adj_factor_zip(self, tmp_path):
        """解析复权因子 ZIP，验证返回正确的因子数据。"""
        svc = LocalKlineImportService()

        csv_content = (
            "股票代码,交易日期,复权因子\n"
            "000001,20240115,1.2345\n"
            "000001,20240116,1.2400\n"
        )

        zip_path = tmp_path / "复权因子_前复权.zip"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("000001.SZ.csv", csv_content)
        zip_path.write_bytes(buf.getvalue())

        factors, parsed, skipped = svc.parse_adj_factor_zip(zip_path, adj_type=1)

        assert parsed == 2
        assert skipped == 0
        assert len(factors) == 2

        f0 = factors[0]
        assert f0["symbol"] == "000001"
        assert f0["trade_date"] == date(2024, 1, 15)
        assert f0["adj_factor"] == Decimal("1.2345")
        assert f0["adj_type"] == 1

        f1 = factors[1]
        assert f1["trade_date"] == date(2024, 1, 16)
        assert f1["adj_factor"] == Decimal("1.2400")


# ---------------------------------------------------------------------------
# 需求 4.2：指数数据（无成交量列）解析
# ---------------------------------------------------------------------------


class TestIndexDataParsing:
    """指数数据解析测试（需求 4.2, 4.3）"""

    def test_parse_csv_content_index_no_volume(self):
        """指数 CSV 无成交量列时，所有 bar 的 volume 应为 0。"""
        svc = LocalKlineImportService()

        csv_text = (
            "时间,代码,名称,开盘价,收盘价,最高价,最低价,成交额,涨幅,振幅\n"
            "2026/04/01 09:30,000001,上证指数,3200.00,3210.00,3215.00,3195.00,50000000,0.31,0.63\n"
            "2026/04/01 09:31,000001,上证指数,3210.00,3205.00,3212.00,3200.00,48000000,0.16,0.37\n"
        )

        bars, skipped = svc.parse_csv_content(csv_text, "000001", "1m", market="zhishu")

        assert len(bars) == 2
        assert skipped == 0
        for bar in bars:
            assert bar.volume == 0

    def test_infer_symbol_from_csv_name_zhishu(self):
        """指数市场 CSV 文件名 000001.csv → 000001（无前缀）。"""
        svc = LocalKlineImportService()
        result = svc.infer_symbol_from_csv_name("000001.csv", market="zhishu")
        assert result == "000001"
