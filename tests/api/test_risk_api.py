"""
风控 API 单元测试

覆盖：
- GET  /risk/overview — 大盘风控状态
- POST /risk/check — 委托风控校验
- POST/GET /risk/stop-config — 止损止盈配置
- GET  /risk/position-warnings — 持仓预警
- CRUD /blacklist, /whitelist — 黑白名单
- GET  /risk/strategy-health — 策略健康状态

Validates: Requirements 28.1–28.16
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_pg_session, get_ts_session
from app.core.redis_client import get_redis
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = "00000000-0000-0000-0000-000000000001"


def _mock_redis(stored_data: dict | None = None):
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
    def __init__(self, symbol: str, quantity: int, cost_price: float, user_id: str = _USER_ID):
        self.symbol = symbol
        self.quantity = quantity
        self.cost_price = Decimal(str(cost_price))
        self.user_id = user_id


class _FakeStockListEntry:
    def __init__(self, symbol: str, list_type: str, reason: str | None = None):
        self.symbol = symbol
        self.list_type = list_type
        self.reason = reason
        self.created_at = datetime.now()


# ---------------------------------------------------------------------------
# 28.10.1 — GET /risk/overview 单元测试
# ---------------------------------------------------------------------------


class TestRiskOverview:
    @pytest.mark.asyncio
    async def test_normal_data_returns_correct_risk_level(self):
        """正常数据返回正确风险等级。"""
        # Build ascending close prices → NORMAL
        sh_closes = [100.0 + i * 0.5 for i in range(60)]
        cyb_closes = [50.0 + i * 0.3 for i in range(60)]

        call_idx = 0

        async def mock_ts_execute(stmt):
            nonlocal call_idx
            m = MagicMock()
            if call_idx == 0:
                m.scalars.return_value.all.return_value = list(reversed(sh_closes))
            else:
                m.scalars.return_value.all.return_value = list(reversed(cyb_closes))
            call_idx += 1
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        async def ts_dep():
            yield ts_session

        app.dependency_overrides[get_ts_session] = ts_dep
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
        assert data["current_threshold"] == 80.0
        assert data["data_insufficient"] is False

    @pytest.mark.asyncio
    async def test_data_insufficient_returns_normal_default(self):
        """数据不足时返回 NORMAL + data_insufficient=true。"""
        async def mock_ts_execute(stmt):
            m = MagicMock()
            m.scalars.return_value.all.return_value = []
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        async def ts_dep():
            yield ts_session

        app.dependency_overrides[get_ts_session] = ts_dep
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



# ---------------------------------------------------------------------------
# 28.10.2 — POST /risk/check 单元测试
# ---------------------------------------------------------------------------


class TestRiskCheck:
    @pytest.mark.asyncio
    async def test_blacklist_hit_returns_failed(self):
        """黑名单命中返回 passed=false。"""
        async def mock_pg_execute(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = "HIT"
            m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def mock_ts_execute(stmt):
            m = MagicMock()
            m.first.return_value = None
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        async def pg_dep():
            yield pg_session

        async def ts_dep():
            yield ts_session

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
    async def test_daily_gain_over_9pct_returns_failed(self):
        """涨幅超 9% 返回 passed=false。"""
        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                m.scalar_one_or_none.return_value = None  # not blacklisted
            else:
                m.scalars.return_value.all.return_value = []
                m.scalar_one_or_none.return_value = None
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def mock_ts_execute(stmt):
            m = MagicMock()
            # open=10, close=11 → 10% gain
            m.first.return_value = (10.0, 11.0)
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        async def pg_dep():
            yield pg_session

        async def ts_dep():
            yield ts_session

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
        assert "9%" in data["reason"]

    @pytest.mark.asyncio
    async def test_all_checks_pass(self):
        """所有检查通过返回 passed=true。"""
        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            m.scalar_one_or_none.return_value = None
            m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def mock_ts_execute(stmt):
            m = MagicMock()
            m.first.return_value = None  # no kline data
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        async def pg_dep():
            yield pg_session

        async def ts_dep():
            yield ts_session

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


# ---------------------------------------------------------------------------
# 28.10.3 — POST/GET /risk/stop-config 单元测试
# ---------------------------------------------------------------------------


class TestStopConfig:
    @pytest.mark.asyncio
    async def test_save_config_success(self):
        """保存配置成功。"""
        redis = _mock_redis()

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/risk/stop-config",
                    json={"fixed_stop_loss": 10.0, "trailing_stop": 3.0, "trend_stop_ma": 60},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["fixed_stop_loss"] == 10.0
        assert data["trailing_stop"] == 3.0
        assert data["trend_stop_ma"] == 60

    @pytest.mark.asyncio
    async def test_redis_no_data_returns_defaults(self):
        """Redis 无数据返回默认值。"""
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



# ---------------------------------------------------------------------------
# 28.10.4 — GET /risk/position-warnings 单元测试
# ---------------------------------------------------------------------------


class TestPositionWarnings:
    @pytest.mark.asyncio
    async def test_no_positions_returns_empty(self):
        """无持仓返回空列表。"""
        pg = AsyncMock()
        pos_result = MagicMock()
        pos_result.scalars.return_value.all.return_value = []
        pg.execute = AsyncMock(return_value=pos_result)

        ts = AsyncMock()
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
    async def test_fixed_stop_loss_trigger_warning(self):
        """触发固定止损预警。"""
        # Position: cost=100, current=85 → loss 15% > default 8%
        positions = [_FakePosition("000001.SZ", 1000, 100.0)]
        current_price = 85.0

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                m.scalars.return_value.all.return_value = positions
            else:
                m.scalar_one_or_none.return_value = None
                m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        # TS session: return kline data with current_price=85
        async def mock_ts_execute(stmt):
            m = MagicMock()
            rows = [(current_price, 100.0, 500000, current_price)] * 60
            m.all.return_value = rows
            return m

        ts_session = AsyncMock()
        ts_session.execute = mock_ts_execute

        redis = _mock_redis()

        async def pg_dep():
            yield pg_session

        async def ts_dep():
            yield ts_session

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
        warnings = resp.json()
        # Should have at least a fixed stop loss warning
        stop_loss_warnings = [w for w in warnings if "止损" in w["type"]]
        assert len(stop_loss_warnings) > 0
        for w in stop_loss_warnings:
            assert w["symbol"] == "000001.SZ"
            assert w["level"] in ("danger", "warning")


# ---------------------------------------------------------------------------
# 28.10.5 — 黑白名单 CRUD 单元测试
# ---------------------------------------------------------------------------


class TestBlacklistWhitelistCRUD:
    @pytest.mark.asyncio
    async def test_add_success_returns_201(self):
        """添加成功返回 201。"""
        async def mock_pg_execute(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = None  # not exists
            m.scalar.return_value = 0
            m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute
        pg_session.add = MagicMock()
        pg_session.flush = AsyncMock()

        async def pg_dep():
            yield pg_session

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

        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_duplicate_add_returns_409(self):
        """重复添加返回 409。"""
        async def mock_pg_execute(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = "EXISTS"
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

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
    async def test_pagination_returns_correct_total_and_items(self):
        """分页查询返回正确 total 和 items。"""
        entries = [
            _FakeStockListEntry("000001.SZ", "BLACK", "reason1"),
            _FakeStockListEntry("000002.SZ", "BLACK", "reason2"),
            _FakeStockListEntry("000003.SZ", "BLACK", "reason3"),
        ]

        call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal call_idx
            call_idx += 1
            m = MagicMock()
            if call_idx == 1:
                # Count query
                m.scalar.return_value = 3
            else:
                # Data query
                m.scalars.return_value.all.return_value = entries[:2]  # page_size=2
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/blacklist",
                    params={"page": 1, "page_size": 2},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_remove_success(self):
        """移除成功。"""
        async def mock_pg_execute(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = "EXISTS"
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.delete("/api/v1/blacklist/000001.SZ")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True


# ---------------------------------------------------------------------------
# 28.10.6 — GET /risk/strategy-health 单元测试
# ---------------------------------------------------------------------------


class TestStrategyHealth:
    @pytest.mark.asyncio
    async def test_no_strategy_id_returns_defaults(self):
        """无 strategy_id 返回默认值。"""
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
    async def test_unhealthy_strategy_returns_warnings(self):
        """策略不健康时返回 warnings。"""
        fake_run = MagicMock()
        fake_run.result = {"win_rate": 0.3, "max_drawdown": 0.25}

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_run

        pg = AsyncMock()
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
