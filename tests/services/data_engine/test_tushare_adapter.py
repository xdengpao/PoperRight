"""
TushareAdapter 单元测试

通过 mock httpx 响应验证：
- 配置驱动初始化（不硬编码凭证）
- _call_api() HTTP POST + Token 认证
- fetch_kline / fetch_fundamentals / fetch_money_flow / fetch_market_overview 数据转换
- health_check 连通性检查
- 错误处理（HTTP 错误、网络错误、API 业务错误）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.data_engine.tushare_adapter import TushareAdapter, TushareAPIError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter() -> TushareAdapter:
    """创建使用显式配置的 TushareAdapter 实例。"""
    return TushareAdapter(api_token="test-token-123", api_url="http://mock-tushare.local")


_MOCK_REQUEST = httpx.Request("POST", "http://mock-tushare.local")


def _make_tushare_response(fields: list[str], items: list[list], code: int = 0, msg: str = "") -> dict:
    """构造 Tushare 标准响应体。"""
    return {
        "code": code,
        "msg": msg,
        "data": {"fields": fields, "items": items},
    }


def _mock_httpx_response(status_code: int, body: dict) -> httpx.Response:
    """构造带 request 的 httpx.Response（raise_for_status 需要）。"""
    return httpx.Response(status_code, json=body, request=_MOCK_REQUEST)


# ---------------------------------------------------------------------------
# 初始化与配置
# ---------------------------------------------------------------------------

class TestInit:
    def test_explicit_config(self) -> None:
        adapter = TushareAdapter(api_token="my-token", api_url="http://my-api.com/")
        assert adapter._api_token == "my-token"
        assert adapter._api_url == "http://my-api.com"  # trailing slash stripped

    def test_defaults_from_settings(self) -> None:
        with patch("app.services.data_engine.tushare_adapter.settings") as mock_settings:
            mock_settings.tushare_api_token = "settings-token"
            mock_settings.tushare_api_url = "http://settings-api.com"
            adapter = TushareAdapter()
            assert adapter._api_token == "settings-token"
            assert adapter._api_url == "http://settings-api.com"

    def test_no_hardcoded_credentials(self) -> None:
        """确保代码中不硬编码凭证——传入空字符串时使用 settings 值。"""
        with patch("app.services.data_engine.tushare_adapter.settings") as mock_settings:
            mock_settings.tushare_api_token = "from-env"
            mock_settings.tushare_api_url = "http://from-env.com"
            adapter = TushareAdapter(api_token=None, api_url=None)
            assert adapter._api_token == "from-env"


# ---------------------------------------------------------------------------
# _call_api
# ---------------------------------------------------------------------------

class TestCallApi:
    @pytest.mark.asyncio
    async def test_successful_call(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response(["ts_code"], [["000001.SZ"]])
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            data = await adapter._call_api("daily", ts_code="000001.SZ")
            assert data["fields"] == ["ts_code"]
            assert data["items"] == [["000001.SZ"]]

    @pytest.mark.asyncio
    async def test_api_error_code(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response([], [], code=-2001, msg="权限不足")
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(TushareAPIError, match="权限不足"):
                await adapter._call_api("daily")

    @pytest.mark.asyncio
    async def test_http_error(self, adapter: TushareAdapter) -> None:
        mock_resp = httpx.Response(500, request=httpx.Request("POST", "http://mock"))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(TushareAPIError, match="HTTP 500"):
                await adapter._call_api("daily")

    @pytest.mark.asyncio
    async def test_network_error(self, adapter: TushareAdapter) -> None:
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(TushareAPIError, match="网络错误"):
                await adapter._call_api("daily")

    @pytest.mark.asyncio
    async def test_date_params_converted(self, adapter: TushareAdapter) -> None:
        """验证 date 类型参数自动转为 YYYYMMDD 字符串。"""
        resp_body = _make_tushare_response([], [])
        mock_resp = _mock_httpx_response(200, resp_body)
        captured_payload = {}

        async def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=capture_post):
            await adapter._call_api("daily", trade_date=date(2024, 1, 15))
            assert captured_payload["params"]["trade_date"] == "20240115"

    @pytest.mark.asyncio
    async def test_token_in_payload(self, adapter: TushareAdapter) -> None:
        """验证 token 包含在请求体中。"""
        resp_body = _make_tushare_response([], [])
        mock_resp = _mock_httpx_response(200, resp_body)
        captured_payload = {}

        async def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=capture_post):
            await adapter._call_api("daily")
            assert captured_payload["token"] == "test-token-123"
            assert captured_payload["api_name"] == "daily"


# ---------------------------------------------------------------------------
# fetch_kline
# ---------------------------------------------------------------------------

class TestFetchKline:
    @pytest.mark.asyncio
    async def test_returns_kline_bars(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response(
            ["trade_date", "ts_code", "open", "high", "low", "close", "vol", "amount"],
            [
                ["20240115", "000001.SZ", 10.5, 11.0, 10.2, 10.8, 500000, 5400000],
                ["20240116", "000001.SZ", 10.8, 11.2, 10.6, 11.1, 600000, 6600000],
            ],
        )
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
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
        assert bars[0].freq == "D"

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response([], [])
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 1), date(2024, 1, 1))

        assert bars == []

    @pytest.mark.asyncio
    async def test_sorted_ascending(self, adapter: TushareAdapter) -> None:
        """Tushare 返回降序数据，验证转换后为升序。"""
        resp_body = _make_tushare_response(
            ["trade_date", "ts_code", "open", "high", "low", "close", "vol", "amount"],
            [
                ["20240116", "000001.SZ", 10.8, 11.2, 10.6, 11.1, 600000, 6600000],
                ["20240115", "000001.SZ", 10.5, 11.0, 10.2, 10.8, 500000, 5400000],
            ],
        )
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            bars = await adapter.fetch_kline("000001.SZ", "D", date(2024, 1, 15), date(2024, 1, 16))

        assert bars[0].time.day == 15
        assert bars[1].time.day == 16


# ---------------------------------------------------------------------------
# fetch_fundamentals
# ---------------------------------------------------------------------------

class TestFetchFundamentals:
    @pytest.mark.asyncio
    async def test_returns_fundamentals(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response(
            ["ts_code", "pe_ttm", "pb", "roe_dt", "netprofit_yoy", "or_yoy"],
            [["000001.SZ", 8.5, 1.2, 12.3, 15.6, 10.2]],
        )
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await adapter.fetch_fundamentals("000001.SZ")

        assert result.symbol == "000001.SZ"
        assert result.pe_ttm == Decimal("8.5")
        assert result.pb == Decimal("1.2")
        assert result.roe == Decimal("12.3")
        assert result.net_profit_yoy == Decimal("15.6")
        assert result.revenue_yoy == Decimal("10.2")
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response([], [])
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await adapter.fetch_fundamentals("000001.SZ")

        assert result.symbol == "000001.SZ"
        assert result.pe_ttm is None


# ---------------------------------------------------------------------------
# fetch_money_flow
# ---------------------------------------------------------------------------

class TestFetchMoneyFlow:
    @pytest.mark.asyncio
    async def test_returns_money_flow(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response(
            ["ts_code", "trade_date", "net_mf_amount", "buy_elg_amount", "sell_elg_amount", "net_lg_amount"],
            [["000001.SZ", "20240115", 5000.0, 12000.0, 7000.0, 3000.0]],
        )
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result.symbol == "000001.SZ"
        assert result.trade_date == date(2024, 1, 15)
        assert result.main_net_inflow == Decimal("5000.0")
        assert result.main_inflow == Decimal("12000.0")
        assert result.main_outflow == Decimal("7000.0")
        assert result.large_order_net == Decimal("3000.0")

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response([], [])
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await adapter.fetch_money_flow("000001.SZ", date(2024, 1, 15))

        assert result.symbol == "000001.SZ"
        assert result.main_net_inflow is None


# ---------------------------------------------------------------------------
# fetch_market_overview
# ---------------------------------------------------------------------------

class TestFetchMarketOverview:
    @pytest.mark.asyncio
    async def test_returns_overview(self, adapter: TushareAdapter) -> None:
        """验证多个指数数据聚合为 MarketOverview。"""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            payload = kwargs.get("json", {})
            ts_code = payload.get("params", {}).get("ts_code", "")

            index_data = {
                "000001.SH": (3100.5, 0.85),
                "399001.SZ": (10200.3, 1.2),
                "399006.SZ": (2050.8, -0.5),
                "000688.SH": (980.2, 0.3),
            }

            close_val, pct_val = index_data.get(ts_code, (0, 0))
            resp_body = _make_tushare_response(
                ["ts_code", "trade_date", "close", "pct_chg"],
                [[ts_code, "20240115", close_val, pct_val]],
            )
            call_count += 1
            return _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
            result = await adapter.fetch_market_overview(date(2024, 1, 15))

        assert result.trade_date == date(2024, 1, 15)
        assert result.sh_index == Decimal("3100.5")
        assert result.sh_change_pct == Decimal("0.85")
        assert result.sz_index == Decimal("10200.3")
        assert result.cyb_index == Decimal("2050.8")
        assert result.kcb_index == Decimal("980.2")
        assert call_count == 4  # 4 个指数各调用一次


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response(["exchange", "is_open"], [["SSE", 1]])
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy_on_error(self, adapter: TushareAdapter) -> None:
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_unhealthy_on_api_error(self, adapter: TushareAdapter) -> None:
        resp_body = _make_tushare_response([], [], code=-1, msg="token error")
        mock_resp = _mock_httpx_response(200, resp_body)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            assert await adapter.health_check() is False
