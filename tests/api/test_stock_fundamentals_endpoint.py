"""
个股基本面数据端点单元测试

测试 GET /data/stock/{symbol}/fundamentals 端点。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.fundamental_adapter import FundamentalsData


@pytest.fixture
def sample_fundamentals() -> FundamentalsData:
    return FundamentalsData(
        symbol="600519.SH",
        name="贵州茅台",
        pe_ttm=Decimal("30.5"),
        pb=Decimal("8.2"),
        roe=Decimal("25.3"),
        market_cap=Decimal("2100000000000"),
        revenue_yoy=Decimal("15.8"),
        net_profit_yoy=Decimal("12.3"),
        updated_at=datetime(2024, 6, 1, 12, 0, 0),
        raw={"report_period": "2024Q1"},
    )


class TestGetStockFundamentals:
    @pytest.mark.asyncio
    async def test_success(self, sample_fundamentals: FundamentalsData):
        """正常返回基本面数据，字段映射正确。"""
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_fundamentals",
            new_callable=AsyncMock,
            return_value=sample_fundamentals,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/fundamentals")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "600519.SH"
        assert data["name"] == "贵州茅台"
        assert data["pe_ttm"] == 30.5
        assert data["pb"] == 8.2
        assert data["roe"] == 25.3
        assert data["market_cap"] == 2100000000000.0
        assert data["revenue_growth"] == 15.8
        assert data["net_profit_growth"] == 12.3
        assert data["report_period"] == "2024Q1"
        assert data["updated_at"] == "2024-06-01T12:00:00"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        """股票不存在或无数据时返回 HTTP 404。"""
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_fundamentals",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/999999.SH/fundamentals")

        assert resp.status_code == 404
        assert "未找到该股票的基本面数据" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_datasource_unavailable_returns_503(self):
        """DataSourceUnavailableError → HTTP 503。"""
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_fundamentals",
            new_callable=AsyncMock,
            side_effect=DataSourceUnavailableError("所有数据源均不可用"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/600519.SH/fundamentals")

        assert resp.status_code == 503
        assert "数据源暂时不可用，请稍后重试" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_nullable_fields(self):
        """可选字段为 None 时正常返回 null。"""
        data = FundamentalsData(symbol="000001.SZ")
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_fundamentals",
            new_callable=AsyncMock,
            return_value=data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/stock/000001.SZ/fundamentals")

        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "000001.SZ"
        assert body["name"] is None
        assert body["pe_ttm"] is None
        assert body["revenue_growth"] is None
        assert body["net_profit_growth"] is None
        assert body["report_period"] is None
        assert body["updated_at"] is None
