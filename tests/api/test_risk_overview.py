"""
大盘风控状态实时计算端点单元测试

测试 GET /risk/overview 端点。
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.risk import RiskOverviewResponse
from app.core.database import get_ts_session
from app.main import app


def _make_kline_rows(closes: list[float]) -> list[Decimal]:
    """构造 DB 查询返回的收盘价列表（DESC 顺序，模拟 ORM scalars）。"""
    return [Decimal(str(c)) for c in reversed(closes)]


def _build_mock_session(sh_rows: list[Decimal], cyb_rows: list[Decimal]) -> AsyncMock:
    """构建模拟 TimescaleDB session，根据 SQL 中的 symbol 返回对应数据。"""
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        # 第一次调用查询上证，第二次查询创业板
        rows = sh_rows if call_count == 0 else cyb_rows
        call_count += 1
        # scalars().all() 是同步调用链
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = rows
        result = MagicMock()
        result.scalars.return_value = scalars_obj
        return result

    session = AsyncMock()
    session.execute = mock_execute
    return session


class TestRiskOverview:
    @pytest.mark.asyncio
    async def test_normal_market(self):
        """两个指数均在 MA20/MA60 之上 → NORMAL, threshold=80。"""
        sh_closes = [3000.0 + i * 10 for i in range(60)]
        cyb_closes = [2000.0 + i * 8 for i in range(60)]

        mock_session = _build_mock_session(
            _make_kline_rows(sh_closes), _make_kline_rows(cyb_closes)
        )

        async def override_dep():
            yield mock_session

        app.dependency_overrides[get_ts_session] = override_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["market_risk_level"] == "NORMAL"
        assert data["sh_above_ma20"] is True
        assert data["sh_above_ma60"] is True
        assert data["cyb_above_ma20"] is True
        assert data["cyb_above_ma60"] is True
        assert data["current_threshold"] == 80.0
        assert data["data_insufficient"] is False

    @pytest.mark.asyncio
    async def test_caution_market(self):
        """上证跌破 MA20 但在 MA60 之上 → CAUTION, threshold=90。"""
        sh_closes = [3000.0 + i * 10 for i in range(40)] + [3390.0 - i * 5 for i in range(20)]
        cyb_closes = [2000.0 + i * 8 for i in range(60)]

        mock_session = _build_mock_session(
            _make_kline_rows(sh_closes), _make_kline_rows(cyb_closes)
        )

        async def override_dep():
            yield mock_session

        app.dependency_overrides[get_ts_session] = override_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["market_risk_level"] == "CAUTION"
        assert data["current_threshold"] == 90.0
        assert data["sh_above_ma20"] is False
        assert data["data_insufficient"] is False

    @pytest.mark.asyncio
    async def test_empty_data_returns_insufficient(self):
        """无 K 线数据时返回 NORMAL + data_insufficient=True。"""
        mock_session = _build_mock_session([], [])

        async def override_dep():
            yield mock_session

        app.dependency_overrides[get_ts_session] = override_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["market_risk_level"] == "NORMAL"
        assert data["data_insufficient"] is True
        assert data["current_threshold"] == 80.0

    @pytest.mark.asyncio
    async def test_db_exception_returns_insufficient(self):
        """数据库查询异常时返回 NORMAL + data_insufficient=True。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        async def override_dep():
            yield mock_session

        app.dependency_overrides[get_ts_session] = override_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["market_risk_level"] == "NORMAL"
        assert data["data_insufficient"] is True

    @pytest.mark.asyncio
    async def test_response_model_fields(self):
        """验证 RiskOverviewResponse 模型字段完整性。"""
        resp = RiskOverviewResponse(
            market_risk_level="DANGER",
            sh_above_ma20=False,
            sh_above_ma60=False,
            cyb_above_ma20=True,
            cyb_above_ma60=False,
            current_threshold=90.0,
            data_insufficient=False,
        )
        assert resp.market_risk_level == "DANGER"
        assert resp.sh_above_ma20 is False
        assert resp.cyb_above_ma60 is False
        assert resp.current_threshold == 90.0

    @pytest.mark.asyncio
    async def test_data_insufficient_default_false(self):
        """data_insufficient 默认值为 False。"""
        resp = RiskOverviewResponse(
            market_risk_level="NORMAL",
            sh_above_ma20=True,
            sh_above_ma60=True,
            cyb_above_ma20=True,
            cyb_above_ma60=True,
            current_threshold=80.0,
        )
        assert resp.data_insufficient is False
