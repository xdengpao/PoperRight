"""
风控 API 端点测试

覆盖：
- POST /risk/check — 委托风控校验（短路求值）
- POST/GET /risk/stop-config — 止损止盈配置 Redis 读写
- GET /risk/position-warnings — 持仓预警
- GET /risk/strategy-health — 策略健康状态
- CRUD /blacklist, /whitelist — 黑白名单
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.risk import (
    RiskCheckResponse,
    StopConfigRequest,
    StopConfigResponse,
    PositionWarningItem,
    StockListItemOut,
    StockListPageResponse,
    StrategyHealthResponse,
)
from app.core.database import get_pg_session, get_ts_session
from app.core.redis_client import get_redis
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = "00000000-0000-0000-0000-000000000001"


def _mock_pg_session_with_data(
    blacklist_hit: bool = False,
    positions: list | None = None,
    board: str | None = None,
    sector_symbols: list | None = None,
):
    """Build a mock PG session that responds to sequential queries."""
    call_idx = 0
    results_queue: list = []

    # 1. blacklist check
    bl_mock = MagicMock()
    bl_mock.scalar_one_or_none.return_value = "HIT" if blacklist_hit else None
    results_queue.append(bl_mock)

    # 2. positions query
    if positions is not None:
        pos_mock = MagicMock()
        pos_mock.scalars.return_value.all.return_value = positions
        results_queue.append(pos_mock)

        # 3. board query
        board_mock = MagicMock()
        board_mock.scalar_one_or_none.return_value = board
        results_queue.append(board_mock)

        # 4. sector symbols query
        if sector_symbols is not None:
            sec_mock = MagicMock()
            sec_mock.scalars.return_value.all.return_value = sector_symbols
            results_queue.append(sec_mock)

    async def mock_execute(stmt):
        nonlocal call_idx
        if call_idx < len(results_queue):
            r = results_queue[call_idx]
            call_idx += 1
            return r
        # fallback
        m = MagicMock()
        m.scalar_one_or_none.return_value = None
        m.scalars.return_value.all.return_value = []
        return m

    session = AsyncMock()
    session.execute = mock_execute
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _mock_ts_session_no_kline():
    """TS session that returns no kline data."""
    async def mock_execute(stmt):
        m = MagicMock()
        m.first.return_value = None
        m.scalars.return_value.all.return_value = []
        m.all.return_value = []
        return m

    session = AsyncMock()
    session.execute = mock_execute
    return session


def _mock_redis(stored_data: dict | None = None):
    """Build a mock Redis client."""
    store: dict[str, str] = {}
    if stored_data:
        for k, v in stored_data.items():
            store[k] = json.dumps(v) if isinstance(v, dict) else v

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ex=None):
        store[key] = value

    redis = AsyncMock()
    redis.get = mock_get
    redis.set = mock_set
    return redis


class _FakePosition:
    """Fake Position ORM object."""
    def __init__(self, symbol: str, quantity: int, cost_price: float, user_id: str = _USER_ID):
        self.symbol = symbol
        self.quantity = quantity
        self.cost_price = Decimal(str(cost_price))
        self.user_id = user_id



# ---------------------------------------------------------------------------
# POST /risk/check — 委托风控校验
# ---------------------------------------------------------------------------


class TestRiskCheck:
    @pytest.mark.asyncio
    async def test_blacklist_hit_returns_failed(self):
        """黑名单命中 → passed=False, 短路不继续。"""
        pg = _mock_pg_session_with_data(blacklist_hit=True)
        ts = _mock_ts_session_no_kline()

        async def pg_dep():
            yield pg

        async def ts_dep():
            yield ts

        app.dependency_overrides[get_pg_session] = pg_dep
        app.dependency_overrides[get_ts_session] = ts_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/risk/check",
                    json={"symbol": "000001.SZ", "direction": "BUY", "quantity": 100},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is False
        assert "黑名单" in data["reason"]

    @pytest.mark.asyncio
    async def test_all_checks_pass(self):
        """无黑名单、无异常涨幅、仓位正常 → passed=True。"""
        pg = _mock_pg_session_with_data(blacklist_hit=False, positions=[], board=None)
        ts = _mock_ts_session_no_kline()

        async def pg_dep():
            yield pg

        async def ts_dep():
            yield ts

        app.dependency_overrides[get_pg_session] = pg_dep
        app.dependency_overrides[get_ts_session] = ts_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/risk/check",
                    json={"symbol": "600000.SH", "direction": "BUY", "quantity": 100},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True
        assert data["reason"] is None

    @pytest.mark.asyncio
    async def test_risk_check_response_model(self):
        """验证 RiskCheckResponse 模型字段。"""
        r = RiskCheckResponse(passed=False, reason="test reason")
        assert r.passed is False
        assert r.reason == "test reason"

        r2 = RiskCheckResponse(passed=True)
        assert r2.reason is None


# ---------------------------------------------------------------------------
# POST/GET /risk/stop-config — 止损止盈配置
# ---------------------------------------------------------------------------


class TestStopConfig:
    @pytest.mark.asyncio
    async def test_save_and_get_config(self):
        """保存配置后读取应返回相同值。"""
        redis = _mock_redis()

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # POST save
                resp = await client.post(
                    "/api/v1/risk/stop-config",
                    json={"fixed_stop_loss": 10.0, "trailing_stop": 3.0, "trend_stop_ma": 60},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["fixed_stop_loss"] == 10.0
                assert data["trailing_stop"] == 3.0
                assert data["trend_stop_ma"] == 60

                # GET read back
                resp2 = await client.get("/api/v1/risk/stop-config")
                assert resp2.status_code == 200
                data2 = resp2.json()
                assert data2["fixed_stop_loss"] == 10.0
                assert data2["trailing_stop"] == 3.0
                assert data2["trend_stop_ma"] == 60
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_config_defaults(self):
        """Redis 无数据时返回默认值。"""
        redis = _mock_redis()

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/stop-config")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["fixed_stop_loss"] == 8.0
        assert data["trailing_stop"] == 5.0
        assert data["trend_stop_ma"] == 20

    @pytest.mark.asyncio
    async def test_stop_config_models(self):
        """验证 StopConfigRequest/Response 模型。"""
        req = StopConfigRequest(fixed_stop_loss=5.0, trailing_stop=3.0, trend_stop_ma=10)
        assert req.fixed_stop_loss == 5.0

        resp = StopConfigResponse(fixed_stop_loss=8.0, trailing_stop=5.0, trend_stop_ma=20)
        assert resp.trend_stop_ma == 20


# ---------------------------------------------------------------------------
# GET /risk/position-warnings — 持仓预警
# ---------------------------------------------------------------------------


class TestPositionWarnings:
    @pytest.mark.asyncio
    async def test_no_positions_returns_empty(self):
        """无持仓时返回空列表。"""
        pg = AsyncMock()
        pos_result = MagicMock()
        pos_result.scalars.return_value.all.return_value = []
        pg.execute = AsyncMock(return_value=pos_result)

        ts = _mock_ts_session_no_kline()
        redis = _mock_redis()

        async def pg_dep():
            yield pg

        async def ts_dep():
            yield ts

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_pg_session] = pg_dep
        app.dependency_overrides[get_ts_session] = ts_dep
        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/position-warnings")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_position_warning_item_model(self):
        """验证 PositionWarningItem 模型字段。"""
        item = PositionWarningItem(
            symbol="000001.SZ",
            type="单股仓位超限",
            level="danger",
            current_value="20.00%",
            threshold="15.00%",
            time="2024-01-01T00:00:00",
        )
        assert item.level == "danger"
        assert item.symbol == "000001.SZ"


# ---------------------------------------------------------------------------
# GET /risk/strategy-health — 策略健康状态
# ---------------------------------------------------------------------------


class TestStrategyHealth:
    @pytest.mark.asyncio
    async def test_no_strategy_id_returns_defaults(self):
        """无 strategy_id 时返回默认健康状态。"""
        pg = AsyncMock()

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/risk/strategy-health")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_healthy"] is True
        assert data["win_rate"] == 0.0
        assert data["max_drawdown"] == 0.0
        assert data["warnings"] == []

    @pytest.mark.asyncio
    async def test_strategy_no_backtest_returns_defaults(self):
        """有 strategy_id 但无回测记录时返回默认值。"""
        pg = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        pg.execute = AsyncMock(return_value=result_mock)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/risk/strategy-health",
                    params={"strategy_id": "00000000-0000-0000-0000-000000000099"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_healthy"] is True
        assert data["strategy_id"] == "00000000-0000-0000-0000-000000000099"

    @pytest.mark.asyncio
    async def test_unhealthy_strategy(self):
        """胜率低 + 回撤高 → 不健康 + 预警信息。"""
        fake_run = MagicMock()
        fake_run.result = {"win_rate": 0.3, "max_drawdown": 0.25}

        pg = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_run
        pg.execute = AsyncMock(return_value=result_mock)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/risk/strategy-health",
                    params={"strategy_id": "00000000-0000-0000-0000-000000000099"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_healthy"] is False
        assert len(data["warnings"]) == 2
        assert any("胜率" in w for w in data["warnings"])
        assert any("回撤" in w for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_healthy_strategy(self):
        """胜率高 + 回撤低 → 健康。"""
        fake_run = MagicMock()
        fake_run.result = {"win_rate": 0.65, "max_drawdown": 0.08}

        pg = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_run
        pg.execute = AsyncMock(return_value=result_mock)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/risk/strategy-health",
                    params={"strategy_id": "00000000-0000-0000-0000-000000000099"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_healthy"] is True
        assert data["warnings"] == []
        assert data["win_rate"] == 0.65

    @pytest.mark.asyncio
    async def test_strategy_health_response_model(self):
        """验证 StrategyHealthResponse 模型。"""
        r = StrategyHealthResponse()
        assert r.is_healthy is True
        assert r.strategy_id is None
        assert r.warnings == []


# ---------------------------------------------------------------------------
# CRUD /blacklist, /whitelist — 黑白名单
# ---------------------------------------------------------------------------


def _mock_pg_for_list(items=None, total=0, exists=False):
    """Build a mock PG session for blacklist/whitelist CRUD."""
    call_idx = 0

    async def mock_execute(stmt):
        nonlocal call_idx
        call_idx += 1
        m = MagicMock()
        # Heuristic: first call is often count or existence check
        m.scalar.return_value = total
        m.scalar_one_or_none.return_value = "EXISTS" if exists else None
        m.scalars.return_value.all.return_value = items or []
        return m

    session = AsyncMock()
    session.execute = mock_execute
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestBlacklistCRUD:
    @pytest.mark.asyncio
    async def test_list_blacklist_empty(self):
        """空黑名单返回 total=0, items=[]。"""
        pg = _mock_pg_for_list(items=[], total=0)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/blacklist")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_add_blacklist_duplicate_409(self):
        """重复添加返回 409。"""
        pg = _mock_pg_for_list(exists=True)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/blacklist",
                    json={"symbol": "000001.SZ", "reason": "test"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_blacklist_not_found_404(self):
        """删除不存在的记录返回 404。"""
        pg = _mock_pg_for_list(exists=False)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.delete("/api/v1/blacklist/999999.SZ")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404


class TestWhitelistCRUD:
    @pytest.mark.asyncio
    async def test_list_whitelist_empty(self):
        """空白名单返回 total=0, items=[]。"""
        pg = _mock_pg_for_list(items=[], total=0)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/whitelist")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_add_whitelist_duplicate_409(self):
        """重复添加白名单返回 409。"""
        pg = _mock_pg_for_list(exists=True)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/whitelist",
                    json={"symbol": "600000.SH"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_whitelist_not_found_404(self):
        """删除不存在的白名单记录返回 404。"""
        pg = _mock_pg_for_list(exists=False)

        async def pg_dep():
            yield pg

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.delete("/api/v1/whitelist/999999.SZ")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pydantic model unit tests
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_stock_list_page_response(self):
        r = StockListPageResponse(total=1, items=[
            StockListItemOut(symbol="000001.SZ", reason="test", created_at="2024-01-01")
        ])
        assert r.total == 1
        assert len(r.items) == 1

    def test_stock_list_item_out(self):
        item = StockListItemOut(symbol="600000.SH", reason=None, created_at="2024-06-01")
        assert item.reason is None
