"""
AkShareAdapter 单元测试

通过 mock akshare SDK 调用验证：
- 配置驱动初始化（不硬编码凭证）
- asyncio.to_thread() 异步包装同步 SDK 调用
- fetch_kline / fetch_fundamentals / fetch_money_flow / fetch_market_overview 数据转换
- health_check 连通性检查
- 错误处理（SDK 异常、akshare 未安装）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.services.data_engine.akshare_adapter import (
    AkShareAdapter,
    AkShareAPIError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter() -> AkShareAdapter:
    """创建使用显式超时配置的 AkShareAdapter 实例。"""
    return AkShareAdapter(timeout=15.0)


def _make_kline_df(rows: list[dict]) -> pd.DataFrame:
    """构造 AkShare K 线 DataFrame（中文列名）。"""
    return pd.DataFrame(rows)


def _make_fundamentals_df(rows: list[dict]) -> pd.DataFrame:
    """构造 AkShare 财务数据 DataFrame。"""
    return pd.DataFrame(rows)


def _make_money_flow_df(rows: list[dict]) -> pd.DataFrame:
    """构造 AkShare 资金流向 DataFrame。"""
    return pd.DataFrame(rows)


def _make_index_df(rows: list[dict]) -> pd.DataFrame:
    """构造 AkShare 指数 DataFrame。"""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 初始化与配置
# ---------------------------------------------------------------------------

class TestInit:
    def test_explicit_timeout(self) -> None:
        adapter = AkShareAdapter(timeout=20.0)
        assert adapter._timeout == 20.0

    def test_defaults_from_settings(self) -> None:
        with patch("app.services.data_engine.akshare_adapter.settings") as mock_settings:
            mock_settings.akshare_request_timeout = 45.0
            adapter = AkShareAdapter()
            assert adapter._timeout == 45.0

    def test_no_hardcoded_timeout(self) -> None:
        """确保代码中不硬编码超时——传入 None 时使用 settings 值。"""
        with patch("app.services.data_engine.akshare_adapter.settings") as mock_settings:
            mock_settings.akshare_request_timeout = 60.0
            adapter = AkShareAdapter(timeout=None)
            assert adapter._timeout == 60.0


# ---------------------------------------------------------------------------
# fetch_kline
# ---------------------------------------------------------------------------

class TestFetchKline:
    @pytest.mark.asyncio
    async def test_returns_kline_bars(self, adapter: AkShareAdapter) -> None:
        mock_df = _make_kline_df([
            {"日期": "2024-01-15", "开盘": 10.5, "最高": 11.0, "最低": 10.2, "收盘": 10.8, "成交量": 500000, "成交额": 5400000, "换手率": 3.5},
            {"日期": "2024-01-16", "开盘": 10.8, "最高": 11.2, "最低": 10.6, "收盘": 11.1, "成交量": 600000, "成交额": 6600000, "换手率": 4.2},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 15), date(2024, 1, 16))

        assert len(bars) == 2
        # 验证升序排列
        assert bars[0].time < bars[1].time
        # 验证字段转换
        assert bars[0].symbol == "000001.SZ"
        assert bars[0].open == Decimal("10.5")
        assert bars[0].high == Decimal("11.0")
        assert bars[0].low == Decimal("10.2")
        assert bars[0].close == Decimal("10.8")
        assert bars[0].volume == 500000
        assert bars[0].amount == Decimal("5400000")
        assert bars[0].turnover == Decimal("3.5")
        assert bars[0].freq == "D"

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: AkShareAdapter) -> None:
        mock_df = pd.DataFrame()

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 1))

        assert bars == []

    @pytest.mark.asyncio
    async def test_none_response(self, adapter: AkShareAdapter) -> None:
        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=None):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 1))

        assert bars == []

    @pytest.mark.asyncio
    async def test_strips_symbol_suffix(self, adapter: AkShareAdapter) -> None:
        """验证 symbol 后缀（.SZ/.SH）被正确去除后传给 akshare。"""
        mock_df = pd.DataFrame()
        captured_kwargs: dict = {}

        async def capture_to_thread(func, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_df

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", side_effect=capture_to_thread):
            await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 1))

        assert captured_kwargs.get("symbol") == "000001"

    @pytest.mark.asyncio
    async def test_sdk_error_raises_akshare_api_error(self, adapter: AkShareAdapter) -> None:
        with patch(
            "app.services.data_engine.akshare_adapter.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=Exception("Connection timeout"),
        ):
            with pytest.raises(AkShareAPIError, match="K线数据获取失败"):
                await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 1))

    @pytest.mark.asyncio
    async def test_sorted_ascending(self, adapter: AkShareAdapter) -> None:
        """验证返回数据按时间升序排列。"""
        mock_df = _make_kline_df([
            {"日期": "2024-01-16", "开盘": 10.8, "最高": 11.2, "最低": 10.6, "收盘": 11.1, "成交量": 600000, "成交额": 6600000, "换手率": 4.2},
            {"日期": "2024-01-15", "开盘": 10.5, "最高": 11.0, "最低": 10.2, "收盘": 10.8, "成交量": 500000, "成交额": 5400000, "换手率": 3.5},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 15), date(2024, 1, 16))

        assert bars[0].time.day == 15
        assert bars[1].time.day == 16


# ---------------------------------------------------------------------------
# fetch_fundamentals
# ---------------------------------------------------------------------------

class TestFetchFundamentals:
    @pytest.mark.asyncio
    async def test_returns_fundamentals(self, adapter: AkShareAdapter) -> None:
        mock_df = _make_fundamentals_df([
            {"净资产收益率(%)": 12.3, "净利润同比增长率(%)": 15.6, "主营业务收入同比增长率(%)": 10.2},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_fundamentals("000001.SZ")

        assert result.symbol == "000001.SZ"
        assert result.roe == Decimal("12.3")
        assert result.net_profit_yoy == Decimal("15.6")
        assert result.revenue_yoy == Decimal("10.2")
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: AkShareAdapter) -> None:
        mock_df = pd.DataFrame()

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_fundamentals("000001.SZ")

        assert result.symbol == "000001.SZ"
        assert result.roe is None

    @pytest.mark.asyncio
    async def test_sdk_error_raises(self, adapter: AkShareAdapter) -> None:
        with patch(
            "app.services.data_engine.akshare_adapter.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            with pytest.raises(AkShareAPIError, match="财务数据获取失败"):
                await adapter.fetch_fundamentals("000001.SZ")


# ---------------------------------------------------------------------------
# fetch_money_flow
# ---------------------------------------------------------------------------

class TestFetchMoneyFlow:
    @pytest.mark.asyncio
    async def test_returns_money_flow(self, adapter: AkShareAdapter) -> None:
        mock_df = _make_money_flow_df([
            {"日期": "2024-01-15", "主力净流入-净额": 5000.0, "主力净流入-净占比": 12.5, "超大单净流入-净额": 3000.0},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result.symbol == "000001.SZ"
        assert result.trade_date == date(2024, 1, 15)
        assert result.main_net_inflow == Decimal("5000.0")
        assert result.large_order_net == Decimal("3000.0")

    @pytest.mark.asyncio
    async def test_matches_target_date(self, adapter: AkShareAdapter) -> None:
        """验证优先匹配指定日期的数据行。"""
        mock_df = _make_money_flow_df([
            {"日期": "2024-01-14", "主力净流入-净额": 1000.0, "主力净流入-净占比": 5.0, "超大单净流入-净额": 500.0},
            {"日期": "2024-01-15", "主力净流入-净额": 5000.0, "主力净流入-净占比": 12.5, "超大单净流入-净额": 3000.0},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result.main_net_inflow == Decimal("5000.0")

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: AkShareAdapter) -> None:
        mock_df = pd.DataFrame()

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result.symbol == "000001.SZ"
        assert result.main_net_inflow is None

    @pytest.mark.asyncio
    async def test_sdk_error_raises(self, adapter: AkShareAdapter) -> None:
        with patch(
            "app.services.data_engine.akshare_adapter.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            with pytest.raises(AkShareAPIError, match="资金流向获取失败"):
                await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))


# ---------------------------------------------------------------------------
# fetch_market_overview
# ---------------------------------------------------------------------------

class TestFetchMarketOverview:
    @pytest.mark.asyncio
    async def test_returns_overview(self, adapter: AkShareAdapter) -> None:
        mock_df = _make_index_df([
            {"date": "2024-01-14", "close": 3050.0, "change": 0.5},
            {"date": "2024-01-15", "close": 3100.5, "change": 0.85},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_market_overview(date(2024, 1, 15))

        assert result.trade_date == date(2024, 1, 15)
        assert result.sh_index == Decimal("3100.5")
        assert result.sh_change_pct == Decimal("0.85")

    @pytest.mark.asyncio
    async def test_fallback_to_last_row(self, adapter: AkShareAdapter) -> None:
        """未匹配到指定日期时取最后一行。"""
        mock_df = _make_index_df([
            {"date": "2024-01-10", "close": 3000.0, "change": -0.2},
            {"date": "2024-01-11", "close": 3020.0, "change": 0.3},
        ])

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            result = await adapter.fetch_market_overview(date(2024, 1, 15))

        assert result.sh_index == Decimal("3020.0")

    @pytest.mark.asyncio
    async def test_sdk_error_raises(self, adapter: AkShareAdapter) -> None:
        with patch(
            "app.services.data_engine.akshare_adapter.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=Exception("Timeout"),
        ):
            with pytest.raises(AkShareAPIError, match="大盘数据获取失败"):
                await adapter.fetch_market_overview(date(2024, 1, 15))


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self, adapter: AkShareAdapter) -> None:
        mock_df = pd.DataFrame({"代码": ["000001"]})

        with patch("app.services.data_engine.akshare_adapter.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_df):
            assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy_on_error(self, adapter: AkShareAdapter) -> None:
        with patch(
            "app.services.data_engine.akshare_adapter.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_unhealthy_when_akshare_not_installed(self) -> None:
        """akshare 未安装时 health_check 返回 False。"""
        with patch("app.services.data_engine.akshare_adapter.ak", None):
            adapter = AkShareAdapter(timeout=10.0)
            assert await adapter.health_check() is False


# ---------------------------------------------------------------------------
# akshare 未安装
# ---------------------------------------------------------------------------

class TestAkShareNotInstalled:
    @pytest.mark.asyncio
    async def test_fetch_kline_raises_when_not_installed(self) -> None:
        with patch("app.services.data_engine.akshare_adapter.ak", None):
            adapter = AkShareAdapter(timeout=10.0)
            with pytest.raises(AkShareAPIError, match="akshare 未安装"):
                await adapter.fetch_kline("000001", "D", date(2024, 1, 1), date(2024, 1, 1))

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_raises_when_not_installed(self) -> None:
        with patch("app.services.data_engine.akshare_adapter.ak", None):
            adapter = AkShareAdapter(timeout=10.0)
            with pytest.raises(AkShareAPIError, match="akshare 未安装"):
                await adapter.fetch_fundamentals("000001")

    @pytest.mark.asyncio
    async def test_fetch_money_flow_raises_when_not_installed(self) -> None:
        with patch("app.services.data_engine.akshare_adapter.ak", None):
            adapter = AkShareAdapter(timeout=10.0)
            with pytest.raises(AkShareAPIError, match="akshare 未安装"):
                await adapter.fetch_money_flow("000001", date(2024, 1, 1))

    @pytest.mark.asyncio
    async def test_fetch_market_overview_raises_when_not_installed(self) -> None:
        with patch("app.services.data_engine.akshare_adapter.ak", None):
            adapter = AkShareAdapter(timeout=10.0)
            with pytest.raises(AkShareAPIError, match="akshare 未安装"):
                await adapter.fetch_market_overview(date(2024, 1, 1))


# ---------------------------------------------------------------------------
# BaseDataSourceAdapter 接口一致性
# ---------------------------------------------------------------------------

class TestInterfaceCompliance:
    def test_inherits_base_adapter(self) -> None:
        """验证 AkShareAdapter 继承 BaseDataSourceAdapter。"""
        from app.services.data_engine.base_adapter import BaseDataSourceAdapter
        assert issubclass(AkShareAdapter, BaseDataSourceAdapter)

    def test_has_all_required_methods(self) -> None:
        """验证 AkShareAdapter 实现了所有抽象方法。"""
        adapter = AkShareAdapter(timeout=10.0)
        assert hasattr(adapter, "fetch_kline")
        assert hasattr(adapter, "fetch_fundamentals")
        assert hasattr(adapter, "fetch_money_flow")
        assert hasattr(adapter, "fetch_market_overview")
        assert hasattr(adapter, "health_check")
