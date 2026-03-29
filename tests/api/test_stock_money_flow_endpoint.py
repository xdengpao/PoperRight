"""
个股资金流向数据端点单元测试

测试 GET /data/stock/{symbol}/money-flow 端点。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.money_flow_adapter import MoneyFlowData


def _make_flow(symbol: str, trade_date: date, main_net: float = 5000000.0) -> MoneyFlowData:
    """创建测试用 MoneyFlowData。"""
    return MoneyFlowData(
        symbol=symbol,
        trade_date=trade_date,
        main_net_inflow=Decimal(str(main_net)),
        north_net_inflow=Decimal("2000000"),
        large_order_ratio=Decimal("35.5"),
        large_order_net=Decimal("3000000"),
        updated_at=datetime(2024, 6, 1, 12, 0, 0),
        raw={"name": "贵州茅台"},
    )


class TestGetStockMoneyFlow:
    @pytest.mark.asyncio
    async def test_success_default_days(self):
        """正常返回资金流向数据，默认 20 天。"""
        today = date.today()
        call_count = 0

        async def mock_fetch(symbol: str, td: date) -> MoneyFlowData:
            nonlocal call_count
            call_count += 1
            return _make_flow(symbol, td, main_net=call_count * 1000000.0)

        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            side_effect=mock_fetch,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/money-flow")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "600519.SH"
        assert data["name"] == "贵州茅台"
        assert data["days"] == 20
        assert len(data["records"]) == 20
        # records 按日期升序
        dates = [r["trade_date"] for r in data["records"]]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_custom_days_parameter(self):
        """自定义 days=5 参数。"""
        async def mock_fetch(symbol: str, td: date) -> MoneyFlowData:
            return _make_flow(symbol, td)

        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            side_effect=mock_fetch,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/money-flow?days=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 5
        assert len(data["records"]) == 5

    @pytest.mark.asyncio
    async def test_days_validation_too_low(self):
        """days < 1 → 422 验证错误。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/data/stock/600519.SH/money-flow?days=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_days_validation_too_high(self):
        """days > 60 → 422 验证错误。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/data/stock/600519.SH/money-flow?days=61")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        """股票不存在或无数据 → HTTP 404。"""
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/999999.SH/money-flow")

        assert resp.status_code == 404
        assert "未找到该股票的资金流向数据" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_datasource_unavailable_returns_503(self):
        """DataSourceUnavailableError → HTTP 503。"""
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            side_effect=DataSourceUnavailableError("所有数据源均不可用"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/money-flow")

        assert resp.status_code == 503
        assert "数据源暂时不可用，请稍后重试" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_records_ascending_order(self):
        """records 按日期升序排列。"""
        async def mock_fetch(symbol: str, td: date) -> MoneyFlowData:
            return _make_flow(symbol, td)

        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            side_effect=mock_fetch,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/money-flow?days=10")

        assert resp.status_code == 200
        dates = [r["trade_date"] for r in resp.json()["records"]]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_field_mapping(self):
        """字段映射正确：元→万元转换。"""
        flow = MoneyFlowData(
            symbol="600519.SH",
            trade_date=date(2024, 6, 3),  # Monday
            main_net_inflow=Decimal("50000000"),   # 5000万元 → 5000万
            north_net_inflow=Decimal("20000000"),  # 2000万元 → 2000万
            large_order_ratio=Decimal("35.5"),
            large_order_net=Decimal("30000000"),   # 3000万元 → 3000万
        )

        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            return_value=flow,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/money-flow?days=1")

        assert resp.status_code == 200
        rec = resp.json()["records"][0]
        assert rec["main_net_inflow"] == 5000.0      # 50000000 / 10000
        assert rec["north_net_inflow"] == 2000.0      # 20000000 / 10000
        assert rec["large_order_ratio"] == 35.5
        assert rec["super_large_inflow"] == 3000.0    # 30000000 / 10000
