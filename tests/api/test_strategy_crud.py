"""Tests for strategy CRUD endpoints — enabled_modules handling (需求 27.4, 27.6).

Migrated from in-memory _strategies dict to PostgreSQL-backed CRUD.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_pg_session
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class _FakeStrategy:
    """Fake StrategyTemplate ORM object."""
    def __init__(self, name, config=None, is_active=False, enabled_modules=None,
                 is_builtin=False, sid=None):
        self.id = sid or uuid4()
        self.user_id = _USER_ID
        self.name = name
        self.config = config or {}
        self.is_active = is_active
        self.is_builtin = is_builtin
        self.enabled_modules = enabled_modules or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


def _build_pg_session(strategies: list[_FakeStrategy] | None = None):
    """Build a mock PG session backed by an in-memory list."""
    store = list(strategies or [])

    async def mock_execute(stmt):
        m = MagicMock()
        stmt_str = str(stmt)

        # Detect query type
        if "DELETE" in stmt_str or "delete" in stmt_str:
            m.scalar_one_or_none.return_value = None
            return m

        if "UPDATE" in stmt_str:
            m.scalar_one_or_none.return_value = None
            return m

        # SELECT queries
        m.scalars.return_value.all.return_value = store
        if store:
            m.scalar_one_or_none.return_value = store[0]
        else:
            m.scalar_one_or_none.return_value = None
        return m

    def mock_add(entry):
        entry.id = entry.id or uuid4()
        entry.created_at = entry.created_at or datetime.now()
        entry.updated_at = entry.updated_at or datetime.now()
        entry.enabled_modules = entry.enabled_modules or []
        entry.is_builtin = getattr(entry, "is_builtin", False)
        store.append(entry)

    session = AsyncMock()
    session.execute = mock_execute
    session.add = mock_add
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session._store = store
    return session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


# ---------------------------------------------------------------------------
# POST /strategies — enabled_modules stored on create
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_strategy_stores_enabled_modules(client: AsyncClient):
    pg = _build_pg_session()

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        payload = {
            "name": "test-strategy",
            "config": {"factors": [], "logic": "AND"},
            "enabled_modules": ["ma_trend", "breakout"],
        }
        resp = await client.post("/api/v1/strategies", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["enabled_modules"] == ["ma_trend", "breakout"]


@pytest.mark.anyio
async def test_create_strategy_default_enabled_modules(client: AsyncClient):
    """When enabled_modules is omitted, it defaults to empty list."""
    pg = _build_pg_session()

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        payload = {"name": "no-modules", "config": {"factors": [], "logic": "AND"}}
        resp = await client.post("/api/v1/strategies", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    assert resp.json()["enabled_modules"] == []


# ---------------------------------------------------------------------------
# PUT /strategies/{id} — enabled_modules updated only when provided
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_strategy_sets_enabled_modules(client: AsyncClient):
    fake = _FakeStrategy("s1", config={"factors": [], "logic": "AND"},
                         enabled_modules=["ma_trend"])
    pg = _build_pg_session([fake])

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        resp = await client.put(
            f"/api/v1/strategies/{fake.id}",
            json={"enabled_modules": ["breakout", "volume_price"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == ["breakout", "volume_price"]


@pytest.mark.anyio
async def test_update_strategy_without_enabled_modules_keeps_existing(client: AsyncClient):
    fake = _FakeStrategy("s2", config={"factors": [], "logic": "AND"},
                         enabled_modules=["indicator_params"])
    pg = _build_pg_session([fake])

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        resp = await client.put(
            f"/api/v1/strategies/{fake.id}",
            json={"name": "renamed"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == ["indicator_params"]


# ---------------------------------------------------------------------------
# GET /strategies and GET /strategies/{id} — default for legacy strategies
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_strategy_defaults_enabled_modules_for_legacy(client: AsyncClient):
    """Old strategies without enabled_modules should return []."""
    legacy = _FakeStrategy("legacy", config={}, enabled_modules=[],
                           sid=UUID("00000000-0000-0000-0000-000000000099"))
    pg = _build_pg_session([legacy])

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        resp = await client.get(f"/api/v1/strategies/{legacy.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == []


@pytest.mark.anyio
async def test_list_strategies_defaults_enabled_modules_for_legacy(client: AsyncClient):
    legacy = _FakeStrategy("old", config={}, enabled_modules=[])
    pg = _build_pg_session([legacy])

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        resp = await client.get("/api/v1/strategies")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["enabled_modules"] == []
