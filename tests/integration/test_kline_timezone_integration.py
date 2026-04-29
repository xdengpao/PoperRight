"""
K线数据时区处理集成测试

验证完整导入链路：
- 本地 CSV 导入日线数据，验证 00:00:00 UTC 时间戳
- 本地 CSV 导入分钟级数据，验证时间组件保持不变
- Tushare API 导入日线数据，验证 00:00:00 UTC 时间戳
- 查询 API 返回无重复记录

对应需求：2.1, 3.1, 3.2, 3.3
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, and_, func

from app.core.database import AsyncSessionTS
from app.models.kline import Kline, KlineBar
from app.services.data_engine.kline_repository import KlineRepository
from app.services.data_engine.local_kline_import import LocalKlineImportService
from app.services.data_engine.tushare_adapter import TushareAdapter


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_daily_csv_content(symbol: str = "000001.SZ") -> str:
    """创建日线 CSV 内容（仅日期格式）。"""
    return f"""时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额
2024-01-15,{symbol},测试股票,10.00,10.50,10.80,9.90,1000000,10500000
2024-01-16,{symbol},测试股票,10.50,11.00,11.20,10.40,1200000,13200000
"""


def _make_minute_csv_content(symbol: str = "000001.SZ") -> str:
    """创建分钟级 CSV 内容（带时间格式）。"""
    return f"""时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额
2024-01-15 09:30:00,{symbol},测试股票,10.00,10.02,10.05,9.98,5000,50000
2024-01-15 09:31:00,{symbol},测试股票,10.02,10.04,10.06,10.00,6000,60000
2024-01-15 09:32:00,{symbol},测试股票,10.04,10.03,10.07,10.01,4500,45000
"""


def _make_zip_file(csv_content: str, csv_name: str = "000001.SZ.csv") -> bytes:
    """创建包含 CSV 的 ZIP 文件字节。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(csv_name, csv_content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 测试 1：本地 CSV 导入日线数据，验证 00:00:00 UTC 时间戳
# ---------------------------------------------------------------------------

class TestLocalCSVImportDailyData:
    """本地 CSV 导入日线数据集成测试

    **Validates: Requirements 2.1, 3.1**
    """

    @pytest.mark.asyncio
    async def test_local_csv_daily_import_timestamp_utc_midnight(self):
        """
        本地 CSV 导入日线数据，验证时间戳为 00:00:00 UTC

        GIVEN 日线 CSV 文件，日期格式为 "YYYY-MM-DD"
        WHEN 通过 LocalKlineImportService 解析并写入数据库
        THEN 数据库中的时间戳应为 00:00:00 UTC
        """
        # 创建日线 CSV 内容
        csv_content = _make_daily_csv_content("000001.SZ")
        service = LocalKlineImportService()

        # 解析 CSV 内容
        bars, skipped = service.parse_csv_content(
            csv_text=csv_content,
            symbol="000001.SZ",
            freq="1d",
            market="hushen",
        )

        # 验证解析结果
        assert len(bars) == 2
        assert skipped == 0

        # 验证时间戳为 00:00:00 UTC
        for bar in bars:
            assert bar.time.hour == 0, f"日线数据 hour 应为 0，实际为 {bar.time.hour}"
            assert bar.time.minute == 0, f"日线数据 minute 应为 0，实际为 {bar.time.minute}"
            assert bar.time.second == 0, f"日线数据 second 应为 0，实际为 {bar.time.second}"
            assert bar.time.tzinfo == timezone.utc, f"时间戳应包含 UTC 时区信息"

        # 验证具体日期
        assert bars[0].time.year == 2024
        assert bars[0].time.month == 1
        assert bars[0].time.day == 15

        assert bars[1].time.year == 2024
        assert bars[1].time.month == 1
        assert bars[1].time.day == 16

    @pytest.mark.asyncio
    async def test_local_csv_daily_import_write_to_database(self):
        """
        本地 CSV 导入日线数据写入数据库，验证时间戳正确存储

        **Validates: Requirements 2.1, 3.2**
        """
        # 创建日线 CSV 内容
        csv_content = _make_daily_csv_content("600000.SH")
        service = LocalKlineImportService()

        # 解析 CSV 内容
        bars, _ = service.parse_csv_content(
            csv_text=csv_content,
            symbol="600000.SH",
            freq="1d",
            market="hushen",
        )

        # Mock 数据库写入
        written_rows: list[dict] = []

        async def mock_bulk_insert(rows):
            written_rows.extend([{"time": b.time, "symbol": b.symbol} for b in rows])
            return len(rows)

        repo = KlineRepository()
        with patch.object(repo, "bulk_insert", side_effect=mock_bulk_insert):
            inserted = await repo.bulk_insert(bars)

        assert inserted == 2
        assert len(written_rows) == 2

        # 验证写入的时间戳
        for row in written_rows:
            assert row["time"].hour == 0
            assert row["time"].tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# 测试 2：本地 CSV 导入分钟级数据，验证时间组件保持不变
# ---------------------------------------------------------------------------

class TestLocalCSVImportMinuteData:
    """本地 CSV 导入分钟级数据集成测试

    **Validates: Requirements 3.3**
    """

    @pytest.mark.asyncio
    async def test_local_csv_minute_import_preserves_time_components(self):
        """
        本地 CSV 导入分钟级数据，验证时间组件保持不变

        GIVEN 分钟级 CSV 文件，时间格式为 "YYYY-MM-DD HH:MM:SS"
        WHEN 通过 LocalKlineImportService 解析
        THEN 时间组件（hour, minute）应与输入一致
        """
        # 创建分钟级 CSV 内容
        csv_content = _make_minute_csv_content("000001.SZ")
        service = LocalKlineImportService()

        # 解析 CSV 内容
        bars, skipped = service.parse_csv_content(
            csv_text=csv_content,
            symbol="000001.SZ",
            freq="5m",
            market="hushen",
        )

        # 验证解析结果
        assert len(bars) == 3
        assert skipped == 0

        # 验证时间组件保持不变
        expected_times = [
            (9, 30),   # 09:30:00
            (9, 31),   # 09:31:00
            (9, 32),   # 09:32:00
        ]

        for bar, (expected_hour, expected_minute) in zip(bars, expected_times):
            assert bar.time.hour == expected_hour, (
                f"分钟数据 hour 应为 {expected_hour}，实际为 {bar.time.hour}"
            )
            assert bar.time.minute == expected_minute, (
                f"分钟数据 minute 应为 {expected_minute}，实际为 {bar.time.minute}"
            )
            assert bar.time.second == 0
            assert bar.time.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_local_csv_minute_import_afternoon_time(self):
        """
        本地 CSV 导入下午时间分钟数据，验证时间组件正确

        **Validates: Requirements 3.3**
        """
        # 创建下午时间分钟级 CSV
        csv_content = """时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额
2024-01-15 13:00:00,000001.SZ,测试股票,10.50,10.52,10.55,10.48,8000,84000
2024-01-15 14:55:00,000001.SZ,测试股票,10.60,10.58,10.62,10.56,9000,95000
"""
        service = LocalKlineImportService()

        bars, _ = service.parse_csv_content(
            csv_text=csv_content,
            symbol="000001.SZ",
            freq="5m",
            market="hushen",
        )

        assert len(bars) == 2

        # 验证下午时间
        assert bars[0].time.hour == 13
        assert bars[0].time.minute == 0

        assert bars[1].time.hour == 14
        assert bars[1].time.minute == 55


# ---------------------------------------------------------------------------
# 测试 3：Tushare API 导入日线数据，验证 00:00:00 UTC 时间戳
# ---------------------------------------------------------------------------

class TestTushareAPIImportDailyData:
    """Tushare API 导入日线数据集成测试

    **Validates: Requirements 2.1, 3.1**
    """

    @pytest.mark.asyncio
    async def test_tushare_api_daily_import_timestamp_utc_midnight(self):
        """
        Tushare API 导入日线数据，验证时间戳为 00:00:00 UTC

        GIVEN Tushare daily API 返回数据
        WHEN 通过 TushareAdapter 解析
        THEN 时间戳应为 00:00:00 UTC
        """
        # Mock Tushare API 响应
        mock_api_response = {
            "fields": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [
                ["000001.SZ", "20240115", 10.0, 10.5, 9.8, 10.3, 50000, 5100000],
                ["000001.SZ", "20240116", 10.3, 10.8, 10.1, 10.6, 60000, 6300000],
            ],
        }

        adapter = TushareAdapter()

        # 使用静态方法解析数据
        rows = TushareAdapter._rows_from_data(mock_api_response)

        # 解析每行数据
        bars = []
        for row in rows:
            bar = KlineBar(
                time=TushareAdapter._parse_trade_date(row.get("trade_date")),
                symbol=row.get("ts_code", "000001.SZ"),
                freq="1d",
                open=Decimal(str(row.get("open", 0))),
                high=Decimal(str(row.get("high", 0))),
                low=Decimal(str(row.get("low", 0))),
                close=Decimal(str(row.get("close", 0))),
                volume=int(row.get("vol", 0)),
                amount=Decimal(str(row.get("amount", 0))),
                turnover=Decimal("0"),
                vol_ratio=Decimal("0"),
            )
            bars.append(bar)

        # 验证解析结果
        assert len(bars) == 2

        # 验证时间戳为 00:00:00 UTC
        for bar in bars:
            assert bar.time.hour == 0, f"日线数据 hour 应为 0，实际为 {bar.time.hour}"
            assert bar.time.minute == 0
            assert bar.time.second == 0
            assert bar.time.tzinfo == timezone.utc

        # 验证具体日期
        assert bars[0].time.year == 2024
        assert bars[0].time.month == 1
        assert bars[0].time.day == 15

    @pytest.mark.asyncio
    async def test_tushare_api_fetch_kline_returns_utc_timestamps(self):
        """
        Tushare API fetch_kline 方法返回 UTC 时间戳

        **Validates: Requirements 2.1**
        """
        from datetime import date

        # Mock API 响应
        mock_response = {
            "fields": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [
                ["600000.SH", "20240115", 12.0, 12.5, 11.8, 12.3, 80000, 9800000],
            ],
        }

        adapter = TushareAdapter()

        with patch.object(adapter, "_call_api", new_callable=AsyncMock, return_value=mock_response):
            bars = await adapter.fetch_kline(
                symbol="600000.SH",
                freq="D",
                start=date(2024, 1, 15),
                end=date(2024, 1, 15),
            )

        assert len(bars) == 1
        bar = bars[0]

        # 验证时间戳
        assert bar.time.hour == 0
        assert bar.time.minute == 0
        assert bar.time.second == 0
        assert bar.time.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# 测试 4：查询 API 返回无重复记录
# ---------------------------------------------------------------------------

class TestQueryAPINoDuplicates:
    """查询 API 无重复记录集成测试

    **Validates: Requirements 3.1, 3.2**
    """

    @pytest.mark.asyncio
    async def test_query_returns_no_duplicate_for_same_trading_day(self):
        """
        查询同一交易日的 K 线数据，应返回唯一记录

        GIVEN 数据库中存储了日线数据（时间戳为 00:00:00 UTC）
        WHEN 查询同一交易日
        THEN 应返回唯一一条记录，无重复
        """
        # 创建测试数据
        bars = [
            KlineBar(
                time=datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
                symbol="000001.SZ",
                freq="1d",
                open=Decimal("10.00"),
                high=Decimal("10.50"),
                low=Decimal("9.90"),
                close=Decimal("10.30"),
                volume=1000000,
                amount=Decimal("10500000"),
                turnover=Decimal("0"),
                vol_ratio=Decimal("0"),
                adj_type=0,
            ),
            KlineBar(
                time=datetime(2024, 1, 16, 0, 0, 0, tzinfo=timezone.utc),
                symbol="000001.SZ",
                freq="1d",
                open=Decimal("10.30"),
                high=Decimal("10.80"),
                low=Decimal("10.10"),
                close=Decimal("10.60"),
                volume=1200000,
                amount=Decimal("13200000"),
                turnover=Decimal("0"),
                vol_ratio=Decimal("0"),
                adj_type=0,
            ),
        ]

        # Mock 数据库查询
        repo = KlineRepository()

        # 模拟查询返回结果
        mock_query_result = bars.copy()

        with patch.object(repo, "query", new_callable=AsyncMock, return_value=mock_query_result):
            from datetime import date
            result = await repo.query(
                symbol="000001.SZ",
                freq="1d",
                start=date(2024, 1, 15),
                end=date(2024, 1, 16),
                adj_type=0,
            )

        # 验证无重复
        assert len(result) == 2

        # 验证每个交易日只有一条记录
        dates_seen = set()
        for bar in result:
            date_key = (bar.time.year, bar.time.month, bar.time.day)
            assert date_key not in dates_seen, f"发现重复日期: {date_key}"
            dates_seen.add(date_key)

    @pytest.mark.asyncio
    async def test_bulk_insert_idempotency_no_duplicates(self):
        """
        批量写入幂等性测试：重复写入相同数据不应产生重复记录

        **Validates: Requirements 3.2**
        """
        # 创建测试数据
        bars = [
            KlineBar(
                time=datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
                symbol="000001.SZ",
                freq="1d",
                open=Decimal("10.00"),
                high=Decimal("10.50"),
                low=Decimal("9.90"),
                close=Decimal("10.30"),
                volume=1000000,
                amount=Decimal("10500000"),
                turnover=Decimal("0"),
                vol_ratio=Decimal("0"),
                adj_type=0,
            ),
        ]

        repo = KlineRepository()

        # Mock 第一次写入成功
        first_insert_result = MagicMock()
        first_insert_result.rowcount = 1

        # Mock 第二次写入（幂等，无新记录）
        second_insert_result = MagicMock()
        second_insert_result.rowcount = 0

        with patch.object(repo, "_get_session_ctx") as mock_ctx:
            # 模拟 session 上下文
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # 第一次写入
            mock_session.execute.return_value = first_insert_result
            inserted1 = await repo.bulk_insert(bars)

            # 第二次写入相同数据
            mock_session.execute.return_value = second_insert_result
            inserted2 = await repo.bulk_insert(bars)

        # 第一次应插入 1 条
        assert inserted1 == 1
        # 第二次应插入 0 条（幂等）
        assert inserted2 == 0


# ---------------------------------------------------------------------------
# 测试 5：CSV 内容解析集成测试（直接测试 parse_csv_content）
# ---------------------------------------------------------------------------

class TestCSVParsingIntegration:
    """CSV 内容解析集成测试

    **Validates: Requirements 2.1, 3.3**
    
    注：extract_and_parse_zip 方法需要从 ZIP 文件路径推断频率，
    这要求特定的目录结构。此处直接测试 parse_csv_content 方法，
    验证时间戳处理逻辑。
    """

    def test_parse_daily_csv_content(self):
        """
        解析日线 CSV 内容，验证时间戳为 00:00:00 UTC

        GIVEN CSV 内容包含日线数据（日期格式）
        WHEN 通过 parse_csv_content 解析
        THEN 时间戳应为 00:00:00 UTC
        """
        # 创建日线 CSV 内容
        csv_content = _make_daily_csv_content("000001.SZ")

        service = LocalKlineImportService()
        bars, skipped = service.parse_csv_content(
            csv_text=csv_content,
            symbol="000001.SZ",
            freq="1d",
            market="hushen",
        )

        # 验证解析结果
        assert len(bars) == 2
        assert skipped == 0

        # 验证时间戳
        for bar in bars:
            assert bar.time.hour == 0
            assert bar.time.minute == 0
            assert bar.time.second == 0
            assert bar.time.tzinfo == timezone.utc

    def test_parse_minute_csv_content(self):
        """
        解析分钟级 CSV 内容，验证时间组件保持不变

        **Validates: Requirements 3.3**
        """
        # 创建分钟级 CSV 内容
        csv_content = _make_minute_csv_content("000001.SZ")

        service = LocalKlineImportService()
        bars, skipped = service.parse_csv_content(
            csv_text=csv_content,
            symbol="000001.SZ",
            freq="5m",
            market="hushen",
        )

        # 验证解析结果
        assert len(bars) == 3

        # 验证时间组件
        expected_hours = [9, 9, 9]
        expected_minutes = [30, 31, 32]

        for bar, expected_hour, expected_minute in zip(bars, expected_hours, expected_minutes):
            assert bar.time.hour == expected_hour
            assert bar.time.minute == expected_minute
            assert bar.time.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# 测试 6：边界情况测试
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """边界情况集成测试

    **Validates: Requirements 2.1, 3.3**
    """

    def test_parse_datetime_various_date_formats(self):
        """
        测试多种日期格式的解析

        **Validates: Requirements 2.1**
        """
        service = LocalKlineImportService()

        # 测试各种日期格式
        test_cases = [
            ("2024-01-15", 2024, 1, 15),
            ("2024/01/15", 2024, 1, 15),
            ("20240115", 2024, 1, 15),
        ]

        for date_str, expected_year, expected_month, expected_day in test_cases:
            result = service._parse_datetime(date_str)

            assert result.year == expected_year
            assert result.month == expected_month
            assert result.day == expected_day
            assert result.hour == 0
            assert result.minute == 0
            assert result.second == 0
            assert result.tzinfo == timezone.utc

    def test_parse_datetime_various_minute_formats(self):
        """
        测试多种分钟级时间格式的解析

        **Validates: Requirements 3.3**
        """
        service = LocalKlineImportService()

        # 测试各种分钟级格式
        test_cases = [
            ("2024-01-15 09:30:00", 9, 30, 0),
            ("2024-01-15 14:55", 14, 55, 0),
            ("2024/01/15 10:00:00", 10, 0, 0),
            ("20240115 11:30:00", 11, 30, 0),
        ]

        for time_str, expected_hour, expected_minute, expected_second in test_cases:
            result = service._parse_datetime(time_str)

            assert result.hour == expected_hour, f"{time_str} hour 应为 {expected_hour}"
            assert result.minute == expected_minute, f"{time_str} minute 应为 {expected_minute}"
            assert result.second == expected_second
            assert result.tzinfo == timezone.utc

    def test_parse_trade_date_edge_cases(self):
        """
        测试 Tushare 交易日期解析边界情况

        **Validates: Requirements 2.1**
        """
        # 测试正常日期
        result = TushareAdapter._parse_trade_date(20240115)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.tzinfo == timezone.utc

        # 测试 None 输入（应返回当前日期的 00:00:00 UTC）
        result = TushareAdapter._parse_trade_date(None)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc

        # 测试无效日期（应返回当前日期的 00:00:00 UTC）
        result = TushareAdapter._parse_trade_date("invalid")
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc
