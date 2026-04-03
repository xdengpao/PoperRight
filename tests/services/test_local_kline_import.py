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
        """Redis 中 status=running 时 is_running 返回 True。"""
        svc = LocalKlineImportService()
        progress = json.dumps({"status": "running"})

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
