"""
DataSourceRouter 单元测试

测试三种核心场景：
1. 主数据源（Tushare）成功 → 直接返回，不调用 AkShare
2. 主数据源失败 → 自动切换 AkShare → 返回数据
3. 两个数据源均失败 → 记录 error 日志 + 推送 DANGER 告警 + 抛出 DataSourceUnavailableError
"""

from __future__ import annotations

import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.schemas import AlertType
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.data_source_router import DataSourceRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tushare():
    adapter = AsyncMock()
    adapter.fetch_kline = AsyncMock()
    adapter.fetch_fundamentals = AsyncMock()
    adapter.fetch_money_flow = AsyncMock()
    adapter.fetch_market_overview = AsyncMock()
    return adapter


@pytest.fixture
def mock_akshare():
    adapter = AsyncMock()
    adapter.fetch_kline = AsyncMock()
    adapter.fetch_fundamentals = AsyncMock()
    adapter.fetch_money_flow = AsyncMock()
    adapter.fetch_market_overview = AsyncMock()
    return adapter


@pytest.fixture
def mock_alert_service():
    svc = AsyncMock()
    svc.push_alert = AsyncMock()
    return svc


@pytest.fixture
def router(mock_tushare, mock_akshare, mock_alert_service):
    return DataSourceRouter(
        tushare=mock_tushare,
        akshare=mock_akshare,
        alert_service=mock_alert_service,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Primary (Tushare) succeeds
# ---------------------------------------------------------------------------


class TestPrimarySuccess:
    """主数据源成功时直接返回数据，不调用备用数据源。"""

    @pytest.mark.asyncio
    async def test_fetch_kline_primary_success(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_kline.return_value = ["bar1", "bar2"]

        result = await router.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31))

        assert result == ["bar1", "bar2"]
        mock_tushare.fetch_kline.assert_awaited_once_with(
            "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
        )
        mock_akshare.fetch_kline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_primary_success(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_fundamentals.return_value = {"pe_ttm": 15.0}

        result = await router.fetch_fundamentals("000001.SZ")

        assert result == {"pe_ttm": 15.0}
        mock_tushare.fetch_fundamentals.assert_awaited_once_with("000001.SZ")
        mock_akshare.fetch_fundamentals.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_money_flow_primary_success(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_money_flow.return_value = {"main_net": 1000}

        result = await router.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result == {"main_net": 1000}
        mock_tushare.fetch_money_flow.assert_awaited_once_with("000001.SZ", date(2024, 1, 15))
        mock_akshare.fetch_money_flow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_market_overview_primary_success(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_market_overview.return_value = {"sh_index": 3000}

        result = await router.fetch_market_overview(date(2024, 1, 15))

        assert result == {"sh_index": 3000}
        mock_tushare.fetch_market_overview.assert_awaited_once_with(date(2024, 1, 15))
        mock_akshare.fetch_market_overview.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 2: Primary fails, fallback (AkShare) succeeds
# ---------------------------------------------------------------------------


class TestFallbackSuccess:
    """主数据源失败时自动切换备用数据源。"""

    @pytest.mark.asyncio
    async def test_fetch_kline_fallback(self, router, mock_tushare, mock_akshare, caplog):
        mock_tushare.fetch_kline.side_effect = RuntimeError("Tushare timeout")
        mock_akshare.fetch_kline.return_value = ["fallback_bar"]

        with caplog.at_level(logging.WARNING):
            result = await router.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31))

        assert result == ["fallback_bar"]
        mock_tushare.fetch_kline.assert_awaited_once()
        mock_akshare.fetch_kline.assert_awaited_once_with(
            "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert "Tushare 数据源调用失败" in caplog.text
        assert "切换至 AkShare" in caplog.text

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_fallback(self, router, mock_tushare, mock_akshare, caplog):
        mock_tushare.fetch_fundamentals.side_effect = ConnectionError("connection refused")
        mock_akshare.fetch_fundamentals.return_value = {"roe": 12.5}

        with caplog.at_level(logging.WARNING):
            result = await router.fetch_fundamentals("600519.SH")

        assert result == {"roe": 12.5}
        assert "Tushare 数据源调用失败" in caplog.text

    @pytest.mark.asyncio
    async def test_fetch_money_flow_fallback(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_money_flow.side_effect = Exception("API error")
        mock_akshare.fetch_money_flow.return_value = {"main_net": 500}

        result = await router.fetch_money_flow("000001.SZ", date(2024, 6, 1))

        assert result == {"main_net": 500}

    @pytest.mark.asyncio
    async def test_fetch_market_overview_fallback(self, router, mock_tushare, mock_akshare):
        mock_tushare.fetch_market_overview.side_effect = TimeoutError("slow")
        mock_akshare.fetch_market_overview.return_value = {"sh_index": 2900}

        result = await router.fetch_market_overview(date(2024, 6, 1))

        assert result == {"sh_index": 2900}


# ---------------------------------------------------------------------------
# Scenario 3: Both sources fail
# ---------------------------------------------------------------------------


class TestBothFail:
    """两个数据源均失败时抛出异常并推送告警。"""

    @pytest.mark.asyncio
    async def test_both_fail_raises_error(self, router, mock_tushare, mock_akshare, caplog):
        mock_tushare.fetch_kline.side_effect = RuntimeError("Tushare down")
        mock_akshare.fetch_kline.side_effect = RuntimeError("AkShare down")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(DataSourceUnavailableError) as exc_info:
                await router.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31))

        assert "fetch_kline" in str(exc_info.value)
        assert "Tushare 和 AkShare 均不可用" in caplog.text

    @pytest.mark.asyncio
    async def test_both_fail_pushes_danger_alert(
        self, router, mock_tushare, mock_akshare, mock_alert_service
    ):
        mock_tushare.fetch_fundamentals.side_effect = RuntimeError("err1")
        mock_akshare.fetch_fundamentals.side_effect = RuntimeError("err2")

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_fundamentals("000001.SZ")

        mock_alert_service.push_alert.assert_awaited_once()
        call_kwargs = mock_alert_service.push_alert.call_args
        assert call_kwargs.kwargs["user_id"] == "system"
        alert = call_kwargs.kwargs["alert"]
        assert alert.alert_type == AlertType.SYSTEM
        assert "DANGER" in alert.title or "数据源异常" in alert.title
        assert "fetch_fundamentals" in alert.message

    @pytest.mark.asyncio
    async def test_both_fail_no_alert_service(self, mock_tushare, mock_akshare):
        """alert_service 为 None 时不推送告警，仍抛出异常。"""
        router = DataSourceRouter(
            tushare=mock_tushare, akshare=mock_akshare, alert_service=None
        )
        mock_tushare.fetch_money_flow.side_effect = RuntimeError("err1")
        mock_akshare.fetch_money_flow.side_effect = RuntimeError("err2")

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_money_flow("000001.SZ", date(2024, 1, 1))

    @pytest.mark.asyncio
    async def test_both_fail_alert_push_failure_still_raises(
        self, router, mock_tushare, mock_akshare, mock_alert_service, caplog
    ):
        """告警推送本身失败时，仍然抛出 DataSourceUnavailableError。"""
        mock_tushare.fetch_market_overview.side_effect = RuntimeError("err1")
        mock_akshare.fetch_market_overview.side_effect = RuntimeError("err2")
        mock_alert_service.push_alert.side_effect = RuntimeError("alert push failed")

        with caplog.at_level(logging.WARNING):
            with pytest.raises(DataSourceUnavailableError):
                await router.fetch_market_overview(date(2024, 1, 1))

        assert "推送数据源异常告警失败" in caplog.text


# ---------------------------------------------------------------------------
# fetch_with_fallback direct usage
# ---------------------------------------------------------------------------


class TestFetchWithFallback:
    """直接测试 fetch_with_fallback 核心方法。"""

    @pytest.mark.asyncio
    async def test_generic_method_routing(self, router, mock_tushare):
        mock_tushare.fetch_kline.return_value = "data"

        result = await router.fetch_with_fallback(
            "fetch_kline", "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
        )

        assert result == "data"

    @pytest.mark.asyncio
    async def test_kwargs_passed_through(self, mock_tushare, mock_akshare):
        """验证 kwargs 正确传递。"""
        router = DataSourceRouter(tushare=mock_tushare, akshare=mock_akshare)
        mock_tushare.fetch_kline.return_value = "ok"

        await router.fetch_with_fallback("fetch_kline", symbol="000001.SZ", freq="D")

        mock_tushare.fetch_kline.assert_awaited_once_with(symbol="000001.SZ", freq="D")


# ---------------------------------------------------------------------------
# fetch_with_fallback_info: returns (data, source_name, is_fallback)
# ---------------------------------------------------------------------------


class TestFetchWithFallbackInfo:
    """测试 fetch_with_fallback_info() 返回三元组 (data, data_source_name, is_fallback)。"""

    @pytest.mark.asyncio
    async def test_primary_success_returns_tushare_info(self, router, mock_tushare, mock_akshare):
        """主数据源成功时返回 (data, "Tushare", False)。"""
        mock_tushare.fetch_kline.return_value = ["bar1", "bar2"]

        data, source, is_fallback = await router.fetch_with_fallback_info(
            "fetch_kline", "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
        )

        assert data == ["bar1", "bar2"]
        assert source == "Tushare"
        assert is_fallback is False
        mock_akshare.fetch_kline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_success_returns_akshare_info(self, router, mock_tushare, mock_akshare):
        """主数据源失败、备用成功时返回 (data, "AkShare", True)。"""
        mock_tushare.fetch_fundamentals.side_effect = RuntimeError("Tushare down")
        mock_akshare.fetch_fundamentals.return_value = {"roe": 10.0}

        data, source, is_fallback = await router.fetch_with_fallback_info(
            "fetch_fundamentals", "600519.SH"
        )

        assert data == {"roe": 10.0}
        assert source == "AkShare"
        assert is_fallback is True

    @pytest.mark.asyncio
    async def test_both_fail_raises_error(self, router, mock_tushare, mock_akshare, caplog):
        """两者均失败时抛出 DataSourceUnavailableError。"""
        mock_tushare.fetch_money_flow.side_effect = RuntimeError("err1")
        mock_akshare.fetch_money_flow.side_effect = RuntimeError("err2")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(DataSourceUnavailableError) as exc_info:
                await router.fetch_with_fallback_info(
                    "fetch_money_flow", "000001.SZ", date(2024, 6, 1)
                )

        assert "fetch_money_flow" in str(exc_info.value)
        assert "Tushare 和 AkShare 均不可用" in caplog.text

    @pytest.mark.asyncio
    async def test_both_fail_pushes_alert(
        self, router, mock_tushare, mock_akshare, mock_alert_service
    ):
        """两者均失败时推送告警。"""
        mock_tushare.fetch_kline.side_effect = RuntimeError("err1")
        mock_akshare.fetch_kline.side_effect = RuntimeError("err2")

        with pytest.raises(DataSourceUnavailableError):
            await router.fetch_with_fallback_info(
                "fetch_kline", "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
            )

        mock_alert_service.push_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kwargs_passed_through(self, router, mock_tushare):
        """验证 kwargs 正确传递到主数据源。"""
        mock_tushare.fetch_kline.return_value = "ok"

        data, source, is_fallback = await router.fetch_with_fallback_info(
            "fetch_kline", symbol="000001.SZ", freq="D"
        )

        assert data == "ok"
        assert source == "Tushare"
        assert is_fallback is False
        mock_tushare.fetch_kline.assert_awaited_once_with(symbol="000001.SZ", freq="D")

    @pytest.mark.asyncio
    async def test_original_fetch_with_fallback_unchanged(self, router, mock_tushare):
        """原 fetch_with_fallback() 仍只返回数据（向后兼容）。"""
        mock_tushare.fetch_kline.return_value = ["bar1"]

        result = await router.fetch_with_fallback(
            "fetch_kline", "000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 31)
        )

        # fetch_with_fallback returns plain data, not a tuple
        assert result == ["bar1"]
        assert not isinstance(result, tuple)
