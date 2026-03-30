"""Tests for strategy CRUD endpoints — enabled_modules handling (需求 27.4, 27.6)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.screen import _strategies
from app.main import app


@pytest.fixture(autouse=True)
def _clear_strategies():
    """Reset in-memory store before each test."""
    _strategies.clear()
    yield
    _strategies.clear()


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
    payload = {
        "name": "test-strategy",
        "config": {"factors": [], "logic": "AND"},
        "enabled_modules": ["ma_trend", "breakout"],
    }
    resp = await client.post("/api/v1/strategies", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["enabled_modules"] == ["ma_trend", "breakout"]


@pytest.mark.anyio
async def test_create_strategy_default_enabled_modules(client: AsyncClient):
    """When enabled_modules is omitted, it defaults to empty list."""
    payload = {"name": "no-modules", "config": {"factors": [], "logic": "AND"}}
    resp = await client.post("/api/v1/strategies", json=payload)
    assert resp.status_code == 201
    assert resp.json()["enabled_modules"] == []


# ---------------------------------------------------------------------------
# PUT /strategies/{id} — enabled_modules updated only when provided
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_strategy_sets_enabled_modules(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "s1", "config": {"factors": [], "logic": "AND"}, "enabled_modules": ["ma_trend"]},
    )
    sid = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/strategies/{sid}", json={"enabled_modules": ["breakout", "volume_price"]})
    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == ["breakout", "volume_price"]


@pytest.mark.anyio
async def test_update_strategy_without_enabled_modules_keeps_existing(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/strategies",
        json={"name": "s2", "config": {"factors": [], "logic": "AND"}, "enabled_modules": ["indicator_params"]},
    )
    sid = create_resp.json()["id"]

    # Update only name — enabled_modules should remain unchanged
    resp = await client.put(f"/api/v1/strategies/{sid}", json={"name": "renamed"})
    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == ["indicator_params"]


# ---------------------------------------------------------------------------
# GET /strategies and GET /strategies/{id} — default for legacy strategies
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_strategy_defaults_enabled_modules_for_legacy(client: AsyncClient):
    """Old strategies without enabled_modules should return []."""
    legacy_id = "00000000-0000-0000-0000-000000000001"
    _strategies[legacy_id] = {
        "id": legacy_id,
        "name": "legacy",
        "config": {},
        "is_active": False,
        "created_at": "2024-01-01T00:00:00",
    }
    resp = await client.get(f"/api/v1/strategies/{legacy_id}")
    assert resp.status_code == 200
    assert resp.json()["enabled_modules"] == []


@pytest.mark.anyio
async def test_list_strategies_defaults_enabled_modules_for_legacy(client: AsyncClient):
    _strategies["old-1"] = {
        "id": "old-1",
        "name": "old",
        "config": {},
        "is_active": False,
        "created_at": "2024-01-01T00:00:00",
    }
    resp = await client.get("/api/v1/strategies")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["enabled_modules"] == []
