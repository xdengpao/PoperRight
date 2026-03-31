"""
风控 API 集成测试

- 28.11.1: 止损配置 round-trip 集成测试
- 28.11.2: 黑名单 CRUD 全链路集成测试
- 28.11.3: 持仓预警全链路集成测试
- 28.11.4: 黑名单联动委托风控集成测试

Validates: Requirements 28.3, 28.5, 28.6, 28.8, 28.9, 28.11, 28.14
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


def _mock_redis():
    """In-memory Redis mock."""
    store: dict[str, str] = {}

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
        self.user_id = _USER_ID


# ---------------------------------------------------------------------------
# 28.11.1 — 止损配置 round-trip 集成测试
# ---------------------------------------------------------------------------


class TestStopConfigRoundTrip:
    @pytest.mark.asyncio
    async def test_save_then_read_consistency(self):
        """保存止损配置 → 读取配置 → 验证一致性。"""
        redis = _mock_redis()

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # Step 1: Save config
                save_resp = await client.post(
                    "/api/v1/risk/stop-config",
                    json={
                        "fixed_stop_loss": 12.0,
                        "trailing_stop": 4.0,
                        "trend_stop_ma": 60,
                    },
                )
                assert save_resp.status_code == 200
                saved = save_resp.json()

                # Step 2: Read config
                read_resp = await client.get("/api/v1/risk/stop-config")
                assert read_resp.status_code == 200
                loaded = read_resp.json()

                # Step 3: Verify consistency
                assert loaded["fixed_stop_loss"] == saved["fixed_stop_loss"] == 12.0
                assert loaded["trailing_stop"] == saved["trailing_stop"] == 4.0
                assert loaded["trend_stop_ma"] == saved["trend_stop_ma"] == 60

                # Step 4: Overwrite and verify again
                save_resp2 = await client.post(
                    "/api/v1/risk/stop-config",
                    json={
                        "fixed_stop_loss": 5.0,
                        "trailing_stop": 3.0,
                        "trend_stop_ma": 20,
                    },
                )
                assert save_resp2.status_code == 200

                read_resp2 = await client.get("/api/v1/risk/stop-config")
                assert read_resp2.status_code == 200
                loaded2 = read_resp2.json()
                assert loaded2["fixed_stop_loss"] == 5.0
                assert loaded2["trailing_stop"] == 3.0
                assert loaded2["trend_stop_ma"] == 20
        finally:
            app.dependency_overrides.clear()



# ---------------------------------------------------------------------------
# 28.11.2 — 黑名单 CRUD 全链路集成测试
# ---------------------------------------------------------------------------


class TestBlacklistCRUDChain:
    @pytest.mark.asyncio
    async def test_add_query_remove_verify(self):
        """添加黑名单 → 查询黑名单 → 移除黑名单 → 验证已移除。"""
        store: list[_FakeStockListEntry] = []
        symbol = "000001.SZ"

        async def mock_pg_execute(stmt):
            m = MagicMock()
            stmt_str = str(stmt)

            if "DELETE" in stmt_str or "delete" in stmt_str:
                store[:] = [e for e in store if not (e.symbol == symbol and e.list_type == "BLACK")]
                m.scalar_one_or_none.return_value = None
            elif "count" in stmt_str.lower() or "COUNT" in stmt_str:
                count = sum(1 for e in store if e.list_type == "BLACK")
                m.scalar.return_value = count
                m.scalars.return_value.all.return_value = []
            else:
                matching = [e for e in store if e.symbol == symbol and e.list_type == "BLACK"]
                m.scalar_one_or_none.return_value = matching[0] if matching else None
                items = [e for e in store if e.list_type == "BLACK"]
                m.scalar.return_value = len(items)
                m.scalars.return_value.all.return_value = items
            return m

        def mock_add(entry):
            store.append(_FakeStockListEntry(entry.symbol, entry.list_type, entry.reason))
            entry.created_at = datetime.now()

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute
        pg_session.add = mock_add
        pg_session.flush = AsyncMock()

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # Step 1: Add to blacklist
                resp1 = await client.post(
                    "/api/v1/blacklist",
                    json={"symbol": symbol, "reason": "integration test"},
                )
                assert resp1.status_code == 201

                # Step 2: Query blacklist — should contain symbol
                resp2 = await client.get("/api/v1/blacklist")
                assert resp2.status_code == 200
                data2 = resp2.json()
                assert any(item["symbol"] == symbol for item in data2["items"])

                # Step 3: Remove from blacklist
                resp3 = await client.delete(f"/api/v1/blacklist/{symbol}")
                assert resp3.status_code == 200

                # Step 4: Query again — should NOT contain symbol
                resp4 = await client.get("/api/v1/blacklist")
                assert resp4.status_code == 200
                data4 = resp4.json()
                assert not any(item["symbol"] == symbol for item in data4["items"])
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 28.11.3 — 持仓预警全链路集成测试
# ---------------------------------------------------------------------------


class TestPositionWarningsChain:
    @pytest.mark.asyncio
    async def test_create_positions_write_kline_query_warnings(self):
        """创建持仓 → 写入 K 线数据 → 查询持仓预警 → 验证预警内容。"""
        # Position: cost=100, current=80 → 20% loss triggers fixed stop loss (default 8%)
        positions = [_FakePosition("600000.SH", 1000, 100.0)]
        current_price = 80.0

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                # Positions query
                m.scalars.return_value.all.return_value = positions
            else:
                # Board / sector queries
                m.scalar_one_or_none.return_value = None
                m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        # TS session: kline data with current_price=80
        async def mock_ts_execute(stmt):
            m = MagicMock()
            rows = [(current_price, 100.0, 500000, 100.0)] * 60
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

        # Should have at least one warning (fixed stop loss)
        assert len(warnings) > 0

        # Verify warning content
        stop_loss_warnings = [w for w in warnings if "止损" in w["type"]]
        assert len(stop_loss_warnings) > 0

        for w in warnings:
            assert w["symbol"] == "600000.SH"
            assert w["type"] != ""
            assert w["level"] in ("danger", "warning", "info")
            assert w["current_value"] != ""
            assert w["threshold"] != ""
            assert w["time"] != ""


# ---------------------------------------------------------------------------
# 28.11.4 — 黑名单联动委托风控集成测试
# ---------------------------------------------------------------------------


class TestBlacklistLinkedToRiskCheck:
    @pytest.mark.asyncio
    async def test_add_blacklist_then_risk_check_blocked(self):
        """添加黑名单 → 委托风控校验 → 验证黑名单命中。"""
        store: list[_FakeStockListEntry] = []
        symbol = "000001.SZ"

        async def mock_pg_execute(stmt):
            m = MagicMock()
            stmt_str = str(stmt)

            # Check if this is a blacklist existence check (used by both add and risk check)
            matching = [e for e in store if e.symbol == symbol and e.list_type == "BLACK"]

            if "count" in stmt_str.lower() or "COUNT" in stmt_str:
                m.scalar.return_value = len(store)
                m.scalars.return_value.all.return_value = []
            else:
                m.scalar_one_or_none.return_value = matching[0] if matching else None
                m.scalars.return_value.all.return_value = store
                m.scalar.return_value = len(store)
            return m

        def mock_add(entry):
            store.append(_FakeStockListEntry(entry.symbol, entry.list_type, entry.reason))
            entry.created_at = datetime.now()

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute
        pg_session.add = mock_add
        pg_session.flush = AsyncMock()

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
                # Step 1: Add to blacklist
                resp1 = await client.post(
                    "/api/v1/blacklist",
                    json={"symbol": symbol, "reason": "integration test"},
                )
                assert resp1.status_code == 201

                # Step 2: Risk check — should be blocked by blacklist
                resp2 = await client.post(
                    "/api/v1/risk/check",
                    json={"symbol": symbol, "direction": "BUY", "quantity": 100},
                )
                assert resp2.status_code == 200
                data = resp2.json()
                assert data["passed"] is False
                assert "黑名单" in data["reason"]
        finally:
            app.dependency_overrides.clear()
