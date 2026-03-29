"""
数据源故障转移集成测试

测试 DataSourceRouter 在不同数据源状态下的全链路行为：
1. Tushare 正常 → 直接返回数据 → 不调用 AkShare（20.11.1）
2. Tushare 失败 → 自动切换 AkShare → 返回数据（20.11.2）
3. Tushare 和 AkShare 均失败 → 抛出异常 → 推送告警（20.11.3）

对应需求：1.1, 1.9, 1.10
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.core.schemas import KlineBar
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.data_source_router import DataSourceRouter
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData


# ---------------------------------------------------------------------------
# 共用 fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_SYMBOL = "000001.SZ"
SAMPLE_FREQ = "D"
SAMPLE_START = date(2024, 1, 1)
SAMPLE_END = date(2024, 1, 31)
SAMPLE_TRADE_DATE = date(2024, 1, 15)


def _make_kline_bars() -> list[KlineBar]:
    """构造有效的 KlineBar 列表。"""
    return [
        KlineBar(
            time=datetime(2024, 1, 15, 0, 0),
            symbol=SAMPLE_SYMBOL,
            freq=SAMPLE_FREQ,
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.80"),
            close=Decimal("10.30"),
            volume=100000,
            amount=Decimal("1030000"),
            turnover=Decimal("3.5"),
            vol_ratio=Decimal("1.2"),
        ),
    ]


def _make_fundamentals() -> FundamentalsData:
    """构造有效的 FundamentalsData。"""
    return FundamentalsData(
        symbol=SAMPLE_SYMBOL,
        name="平安银行",
        pe_ttm=Decimal("8.5"),
        pb=Decimal("0.9"),
        roe=Decimal("12.5"),
        updated_at=datetime.utcnow(),
    )


def _make_money_flow() -> MoneyFlowData:
    """构造有效的 MoneyFlowData。"""
    return MoneyFlowData(
        symbol=SAMPLE_SYMBOL,
        trade_date=SAMPLE_TRADE_DATE,
        main_net_inflow=Decimal("5000000"),
        main_inflow=Decimal("20000000"),
        main_outflow=Decimal("15000000"),
        updated_at=datetime.utcnow(),
    )


def _make_market_overview() -> MarketOverview:
    """构造有效的 MarketOverview。"""
    return MarketOverview(
        trade_date=SAMPLE_TRADE_DATE,
        sh_index=Decimal("3100.50"),
        sh_change_pct=Decimal("0.35"),
        sz_index=Decimal("10200.80"),
        sz_change_pct=Decimal("0.42"),
        updated_at=datetime.utcnow(),
    )


def _build_router(
    tushare_mock: AsyncMock,
    akshare_mock: AsyncMock,
) -> DataSourceRouter:
    """用 mock 适配器构建 DataSourceRouter。"""
    return DataSourceRouter(tushare=tushare_mock, akshare=akshare_mock)


# ---------------------------------------------------------------------------
# 20.11.1 Tushare 正常 → 直接返回数据 → 不调用 AkShare
# ---------------------------------------------------------------------------


class TestTushareSuccessNoFallback:
    """
    验证主数据源（Tushare）正常时：
    - 直接返回 Tushare 数据
    - AkShare 不被调用

    **Validates: Requirements 1.1, 1.9**
    """

    @pytest.mark.asyncio
    async def test_fetch_kline_tushare_success_no_akshare_call(self):
        """Tushare fetch_kline 成功 → 返回数据 → AkShare.fetch_kline 未被调用。"""
        expected = _make_kline_bars()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_kline.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_kline(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )

        assert result == expected
        tushare.fetch_kline.assert_awaited_once_with(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )
        akshare.fetch_kline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_tushare_success_no_akshare_call(self):
        """Tushare fetch_fundamentals 成功 → 返回数据 → AkShare.fetch_fundamentals 未被调用。"""
        expected = _make_fundamentals()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_fundamentals.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_fundamentals(SAMPLE_SYMBOL)

        assert result == expected
        assert result.symbol == SAMPLE_SYMBOL
        assert result.pe_ttm == Decimal("8.5")
        tushare.fetch_fundamentals.assert_awaited_once_with(SAMPLE_SYMBOL)
        akshare.fetch_fundamentals.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_money_flow_tushare_success_no_akshare_call(self):
        """Tushare fetch_money_flow 成功 → 返回数据 → AkShare.fetch_money_flow 未被调用。"""
        expected = _make_money_flow()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_money_flow.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)

        assert result == expected
        assert result.main_net_inflow == Decimal("5000000")
        tushare.fetch_money_flow.assert_awaited_once_with(
            SAMPLE_SYMBOL, SAMPLE_TRADE_DATE,
        )
        akshare.fetch_money_flow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_market_overview_tushare_success_no_akshare_call(self):
        """Tushare fetch_market_overview 成功 → 返回数据 → AkShare.fetch_market_overview 未被调用。"""
        expected = _make_market_overview()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_market_overview.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_market_overview(SAMPLE_TRADE_DATE)

        assert result == expected
        assert result.sh_index == Decimal("3100.50")
        tushare.fetch_market_overview.assert_awaited_once_with(SAMPLE_TRADE_DATE)
        akshare.fetch_market_overview.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_four_methods_tushare_only(self):
        """全部四种数据方法均走 Tushare，AkShare 完全未被调用。"""
        tushare = AsyncMock()
        akshare = AsyncMock()

        tushare.fetch_kline.return_value = _make_kline_bars()
        tushare.fetch_fundamentals.return_value = _make_fundamentals()
        tushare.fetch_money_flow.return_value = _make_money_flow()
        tushare.fetch_market_overview.return_value = _make_market_overview()

        router = _build_router(tushare, akshare)

        # 依次调用四种方法
        kline = await router.fetch_kline(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )
        fundamentals = await router.fetch_fundamentals(SAMPLE_SYMBOL)
        money_flow = await router.fetch_money_flow(
            SAMPLE_SYMBOL, SAMPLE_TRADE_DATE,
        )
        overview = await router.fetch_market_overview(SAMPLE_TRADE_DATE)

        # 验证返回数据有效
        assert len(kline) == 1
        assert fundamentals.symbol == SAMPLE_SYMBOL
        assert money_flow.trade_date == SAMPLE_TRADE_DATE
        assert overview.sh_index is not None

        # 验证 AkShare 的所有方法均未被调用
        akshare.fetch_kline.assert_not_awaited()
        akshare.fetch_fundamentals.assert_not_awaited()
        akshare.fetch_money_flow.assert_not_awaited()
        akshare.fetch_market_overview.assert_not_awaited()


# ---------------------------------------------------------------------------
# 20.11.2 Tushare 失败 → 自动切换 AkShare → 返回数据
# ---------------------------------------------------------------------------


class TestTushareFallbackToAkShare:
    """
    验证主数据源（Tushare）失败时：
    - Tushare 被调用（尝试过）
    - 自动切换至 AkShare（备用数据源）
    - 返回 AkShare 的数据

    **Validates: Requirements 1.9**
    """

    # -- fetch_kline fallback ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_kline_tushare_fails_akshare_returns_data(self):
        """Tushare fetch_kline 抛出异常 → AkShare 返回数据 → 结果等于 AkShare 数据。"""
        expected = _make_kline_bars()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_kline.side_effect = RuntimeError("Tushare API error")
        akshare.fetch_kline.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_kline(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )

        assert result == expected
        tushare.fetch_kline.assert_awaited_once()
        akshare.fetch_kline.assert_awaited_once_with(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )

    # -- fetch_fundamentals fallback --------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_tushare_fails_akshare_returns_data(self):
        """Tushare fetch_fundamentals 抛出异常 → AkShare 返回数据。"""
        expected = _make_fundamentals()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_fundamentals.side_effect = ConnectionError("connection refused")
        akshare.fetch_fundamentals.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_fundamentals(SAMPLE_SYMBOL)

        assert result == expected
        assert result.symbol == SAMPLE_SYMBOL
        tushare.fetch_fundamentals.assert_awaited_once()
        akshare.fetch_fundamentals.assert_awaited_once_with(SAMPLE_SYMBOL)

    # -- fetch_money_flow fallback ----------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_money_flow_tushare_fails_akshare_returns_data(self):
        """Tushare fetch_money_flow 抛出异常 → AkShare 返回数据。"""
        expected = _make_money_flow()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_money_flow.side_effect = TimeoutError("request timed out")
        akshare.fetch_money_flow.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)

        assert result == expected
        assert result.main_net_inflow == Decimal("5000000")
        tushare.fetch_money_flow.assert_awaited_once()
        akshare.fetch_money_flow.assert_awaited_once_with(
            SAMPLE_SYMBOL, SAMPLE_TRADE_DATE,
        )

    # -- fetch_market_overview fallback -----------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_market_overview_tushare_fails_akshare_returns_data(self):
        """Tushare fetch_market_overview 抛出异常 → AkShare 返回数据。"""
        expected = _make_market_overview()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_market_overview.side_effect = RuntimeError("server error")
        akshare.fetch_market_overview.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_market_overview(SAMPLE_TRADE_DATE)

        assert result == expected
        assert result.sh_index == Decimal("3100.50")
        tushare.fetch_market_overview.assert_awaited_once()
        akshare.fetch_market_overview.assert_awaited_once_with(SAMPLE_TRADE_DATE)

    # -- all four methods fallback in sequence ----------------------------------

    @pytest.mark.asyncio
    async def test_all_four_methods_fallback_to_akshare(self):
        """全部四种数据方法 Tushare 均失败 → 全部走 AkShare 返回正确数据。"""
        tushare = AsyncMock()
        akshare = AsyncMock()

        # Tushare 全部失败
        tushare.fetch_kline.side_effect = RuntimeError("fail")
        tushare.fetch_fundamentals.side_effect = RuntimeError("fail")
        tushare.fetch_money_flow.side_effect = RuntimeError("fail")
        tushare.fetch_market_overview.side_effect = RuntimeError("fail")

        # AkShare 全部返回有效数据
        expected_kline = _make_kline_bars()
        expected_fundamentals = _make_fundamentals()
        expected_money_flow = _make_money_flow()
        expected_overview = _make_market_overview()

        akshare.fetch_kline.return_value = expected_kline
        akshare.fetch_fundamentals.return_value = expected_fundamentals
        akshare.fetch_money_flow.return_value = expected_money_flow
        akshare.fetch_market_overview.return_value = expected_overview

        router = _build_router(tushare, akshare)

        kline = await router.fetch_kline(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )
        fundamentals = await router.fetch_fundamentals(SAMPLE_SYMBOL)
        money_flow = await router.fetch_money_flow(
            SAMPLE_SYMBOL, SAMPLE_TRADE_DATE,
        )
        overview = await router.fetch_market_overview(SAMPLE_TRADE_DATE)

        # 验证返回值匹配 AkShare 数据
        assert kline == expected_kline
        assert fundamentals == expected_fundamentals
        assert money_flow == expected_money_flow
        assert overview == expected_overview

        # 验证 Tushare 被尝试调用
        tushare.fetch_kline.assert_awaited_once()
        tushare.fetch_fundamentals.assert_awaited_once()
        tushare.fetch_money_flow.assert_awaited_once()
        tushare.fetch_market_overview.assert_awaited_once()

        # 验证 AkShare 被调用（fallback 触发）
        akshare.fetch_kline.assert_awaited_once()
        akshare.fetch_fundamentals.assert_awaited_once()
        akshare.fetch_money_flow.assert_awaited_once()
        akshare.fetch_market_overview.assert_awaited_once()

    # -- different exception types trigger fallback -----------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc_class,exc_msg",
        [
            (ConnectionError, "connection refused"),
            (TimeoutError, "request timed out"),
            (RuntimeError, "internal server error"),
        ],
        ids=["ConnectionError", "TimeoutError", "RuntimeError"],
    )
    async def test_various_exception_types_trigger_fallback(
        self, exc_class: type, exc_msg: str,
    ):
        """不同异常类型（ConnectionError/TimeoutError/RuntimeError）均触发 fallback。"""
        expected = _make_kline_bars()

        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_kline.side_effect = exc_class(exc_msg)
        akshare.fetch_kline.return_value = expected

        router = _build_router(tushare, akshare)
        result = await router.fetch_kline(
            SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
        )

        assert result == expected
        tushare.fetch_kline.assert_awaited_once()
        akshare.fetch_kline.assert_awaited_once()


# ---------------------------------------------------------------------------
# 20.11.3 Tushare 和 AkShare 均失败 → 抛出异常 → 推送告警
# ---------------------------------------------------------------------------


class TestBothSourcesFail:
    """
    验证双数据源均不可用时：
    - 抛出 DataSourceUnavailableError
    - 推送 DANGER 级别告警（alert_service 已配置时）
    - 无 alert_service 时仍正常抛出异常（不崩溃）

    **Validates: Requirements 1.10**
    """

    # -- fetch_kline both fail -------------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_kline_both_fail_raises_error(self):
        """Tushare 和 AkShare fetch_kline 均失败 → 抛出 DataSourceUnavailableError。"""
        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_kline.side_effect = RuntimeError("Tushare down")
        akshare.fetch_kline.side_effect = ConnectionError("AkShare down")

        router = _build_router(tushare, akshare)

        with pytest.raises(DataSourceUnavailableError, match="fetch_kline"):
            await router.fetch_kline(
                SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
            )

        tushare.fetch_kline.assert_awaited_once()
        akshare.fetch_kline.assert_awaited_once()

    # -- fetch_fundamentals both fail ------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_both_fail_raises_error(self):
        """Tushare 和 AkShare fetch_fundamentals 均失败 → 抛出 DataSourceUnavailableError。"""
        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_fundamentals.side_effect = TimeoutError("Tushare timeout")
        akshare.fetch_fundamentals.side_effect = RuntimeError("AkShare error")

        router = _build_router(tushare, akshare)

        with pytest.raises(DataSourceUnavailableError, match="fetch_fundamentals"):
            await router.fetch_fundamentals(SAMPLE_SYMBOL)

    # -- fetch_money_flow both fail --------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_money_flow_both_fail_raises_error(self):
        """Tushare 和 AkShare fetch_money_flow 均失败 → 抛出 DataSourceUnavailableError。"""
        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_money_flow.side_effect = ConnectionError("Tushare refused")
        akshare.fetch_money_flow.side_effect = TimeoutError("AkShare timeout")

        router = _build_router(tushare, akshare)

        with pytest.raises(DataSourceUnavailableError, match="fetch_money_flow"):
            await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)

    # -- fetch_market_overview both fail ---------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_market_overview_both_fail_raises_error(self):
        """Tushare 和 AkShare fetch_market_overview 均失败 → 抛出 DataSourceUnavailableError。"""
        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_market_overview.side_effect = RuntimeError("Tushare 500")
        akshare.fetch_market_overview.side_effect = RuntimeError("AkShare 500")

        router = _build_router(tushare, akshare)

        with pytest.raises(DataSourceUnavailableError, match="fetch_market_overview"):
            await router.fetch_market_overview(SAMPLE_TRADE_DATE)

    # -- all four methods both fail --------------------------------------------

    @pytest.mark.asyncio
    async def test_all_four_methods_both_fail(self):
        """全部四种数据方法 Tushare 和 AkShare 均失败 → 每次均抛出 DataSourceUnavailableError。"""
        tushare = AsyncMock()
        akshare = AsyncMock()

        tushare.fetch_kline.side_effect = RuntimeError("fail")
        tushare.fetch_fundamentals.side_effect = RuntimeError("fail")
        tushare.fetch_money_flow.side_effect = RuntimeError("fail")
        tushare.fetch_market_overview.side_effect = RuntimeError("fail")

        akshare.fetch_kline.side_effect = RuntimeError("fail")
        akshare.fetch_fundamentals.side_effect = RuntimeError("fail")
        akshare.fetch_money_flow.side_effect = RuntimeError("fail")
        akshare.fetch_market_overview.side_effect = RuntimeError("fail")

        router = _build_router(tushare, akshare)

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_kline(
                SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
            )
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_fundamentals(SAMPLE_SYMBOL)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_market_overview(SAMPLE_TRADE_DATE)

    # -- alert_service.push_alert called with correct params -------------------

    @pytest.mark.asyncio
    async def test_alert_service_push_alert_called_on_both_fail(self):
        """双源失败时 alert_service.push_alert 被调用，参数包含 user_id='system' 和 AlertType.SYSTEM。"""
        from app.core.schemas import AlertType

        tushare = AsyncMock()
        akshare = AsyncMock()
        alert_service = AsyncMock()

        tushare.fetch_kline.side_effect = RuntimeError("Tushare down")
        akshare.fetch_kline.side_effect = RuntimeError("AkShare down")

        router = DataSourceRouter(
            tushare=tushare, akshare=akshare, alert_service=alert_service,
        )

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_kline(
                SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
            )

        alert_service.push_alert.assert_awaited_once()
        call_kwargs = alert_service.push_alert.call_args
        assert call_kwargs.kwargs["user_id"] == "system" or call_kwargs.args[0] == "system"

        # 提取 alert 参数（可能是 kwarg 或 positional）
        alert_arg = call_kwargs.kwargs.get("alert") or call_kwargs.args[1]
        assert alert_arg.alert_type == AlertType.SYSTEM
        assert alert_arg.user_id == "system"
        assert "fetch_kline" in alert_arg.message

    @pytest.mark.asyncio
    async def test_alert_service_called_for_each_method(self):
        """每种数据方法双源失败时都会触发 alert_service.push_alert。"""
        from app.core.schemas import AlertType

        tushare = AsyncMock()
        akshare = AsyncMock()
        alert_service = AsyncMock()

        # 所有方法均失败
        for method in ("fetch_kline", "fetch_fundamentals", "fetch_money_flow", "fetch_market_overview"):
            getattr(tushare, method).side_effect = RuntimeError("fail")
            getattr(akshare, method).side_effect = RuntimeError("fail")

        router = DataSourceRouter(
            tushare=tushare, akshare=akshare, alert_service=alert_service,
        )

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_kline(SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_fundamentals(SAMPLE_SYMBOL)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_market_overview(SAMPLE_TRADE_DATE)

        assert alert_service.push_alert.await_count == 4

        # 验证每次调用的 alert 都是 SYSTEM 类型
        for call in alert_service.push_alert.call_args_list:
            alert_arg = call.kwargs.get("alert") or call.args[1]
            assert alert_arg.alert_type == AlertType.SYSTEM

    # -- without alert_service: still raises error gracefully ------------------

    @pytest.mark.asyncio
    async def test_no_alert_service_still_raises_error(self):
        """未配置 alert_service 时，双源失败仍正常抛出 DataSourceUnavailableError（不崩溃）。"""
        tushare = AsyncMock()
        akshare = AsyncMock()
        tushare.fetch_kline.side_effect = RuntimeError("Tushare down")
        akshare.fetch_kline.side_effect = RuntimeError("AkShare down")

        # alert_service=None（默认）
        router = DataSourceRouter(tushare=tushare, akshare=akshare, alert_service=None)

        with pytest.raises(DataSourceUnavailableError, match="fetch_kline"):
            await router.fetch_kline(
                SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END,
            )

    @pytest.mark.asyncio
    async def test_no_alert_service_all_methods_raise(self):
        """未配置 alert_service 时，全部四种方法双源失败均正常抛出异常。"""
        tushare = AsyncMock()
        akshare = AsyncMock()

        for method in ("fetch_kline", "fetch_fundamentals", "fetch_money_flow", "fetch_market_overview"):
            getattr(tushare, method).side_effect = RuntimeError("fail")
            getattr(akshare, method).side_effect = RuntimeError("fail")

        router = DataSourceRouter(tushare=tushare, akshare=akshare)

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_kline(SAMPLE_SYMBOL, SAMPLE_FREQ, SAMPLE_START, SAMPLE_END)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_fundamentals(SAMPLE_SYMBOL)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_money_flow(SAMPLE_SYMBOL, SAMPLE_TRADE_DATE)
        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_market_overview(SAMPLE_TRADE_DATE)
