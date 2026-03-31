"""
选股执行全链路集成测试

26.4.1: 创建策略 → mock 预设股票因子数据 → 执行选股 → 验证返回真实结果

Validates: Requirements 27.9, 27.10
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_pg_session
from app.main import app

VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}

_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class _FakeStrategy:
    """Fake StrategyTemplate ORM object for mocking DB queries."""
    def __init__(self, sid, name, config, enabled_modules=None, is_active=False, is_builtin=False):
        self.id = UUID(sid) if isinstance(sid, str) else sid
        self.user_id = _USER_ID
        self.name = name
        self.config = config
        self.is_active = is_active
        self.is_builtin = is_builtin
        self.enabled_modules = enabled_modules or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


# Pre-built stock factor data with realistic values that will pass screening.
MOCK_STOCKS_DATA = {
    "000001": {
        "close": 15.50, "open": 15.20, "high": 15.80, "low": 15.10,
        "volume": 850000, "amount": 13175000.0, "turnover": 5.2, "vol_ratio": 1.8,
        "closes": [14.0, 14.3, 14.6, 14.9, 15.2, 15.50],
        "highs": [14.2, 14.5, 14.8, 15.1, 15.4, 15.80],
        "lows": [13.8, 14.1, 14.4, 14.7, 15.0, 15.10],
        "volumes": [700000, 720000, 750000, 780000, 800000, 850000],
        "amounts": [9800000, 10296000, 10950000, 11622000, 12160000, 13175000],
        "turnovers": [4.0, 4.2, 4.5, 4.8, 5.0, 5.2],
        "pe_ttm": 12.5, "pb": 1.8, "roe": 15.0, "market_cap": 3500.0,
        "ma_trend": 85,
    },
    "600036": {
        "close": 42.30, "open": 41.80, "high": 42.60, "low": 41.50,
        "volume": 1200000, "amount": 50760000.0, "turnover": 3.8, "vol_ratio": 2.1,
        "closes": [40.0, 40.5, 41.0, 41.5, 42.0, 42.30],
        "highs": [40.3, 40.8, 41.3, 41.8, 42.3, 42.60],
        "lows": [39.7, 40.2, 40.7, 41.2, 41.7, 41.50],
        "volumes": [1000000, 1050000, 1080000, 1100000, 1150000, 1200000],
        "amounts": [40000000, 42525000, 44280000, 45650000, 48300000, 50760000],
        "turnovers": [3.0, 3.2, 3.3, 3.5, 3.6, 3.8],
        "pe_ttm": 8.2, "pb": 0.9, "roe": 18.0, "market_cap": 12000.0,
        "ma_trend": 92,
    },
}


def _build_pg_session_with_store():
    """Build a mock PG session with an in-memory strategy store."""
    store: dict[str, _FakeStrategy] = {}

    async def mock_execute(stmt):
        m = MagicMock()
        stmt_str = str(stmt)

        if "UPDATE" in stmt_str:
            return m

        # Return all strategies for list queries
        m.scalars.return_value.all.return_value = list(store.values())

        # For single-item lookups, try to find by ID
        # The mock is simplistic — returns first item or None
        if store:
            m.scalar_one_or_none.return_value = list(store.values())[0]
        else:
            m.scalar_one_or_none.return_value = None
        return m

    def mock_add(entry):
        entry.id = entry.id or uuid4()
        entry.created_at = entry.created_at or datetime.now()
        entry.updated_at = entry.updated_at or datetime.now()
        entry.enabled_modules = entry.enabled_modules or []
        entry.is_builtin = getattr(entry, "is_builtin", False)
        store[str(entry.id)] = entry

    session = AsyncMock()
    session.execute = mock_execute
    session.add = mock_add
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session._store = store
    return session


@pytest.mark.anyio
async def test_create_strategy_run_screen_full_chain(client: AsyncClient):
    """
    Full chain: create strategy → mock ScreenDataProvider → POST /screen/run
    → verify non-empty items with all required fields.
    """
    pg = _build_pg_session_with_store()

    async def pg_dep():
        yield pg

    app.dependency_overrides[get_pg_session] = pg_dep
    try:
        # Step 1: Create strategy
        create_resp = await client.post(
            "/api/v1/strategies",
            json={
                "name": "integration-test-strategy",
                "config": {
                    "factors": [{"factor_name": "ma_trend", "operator": ">=", "threshold": 80.0, "params": {}}],
                    "logic": "AND",
                },
                "enabled_modules": ["factor_editor", "ma_trend"],
            },
        )
        assert create_resp.status_code == 201
        strategy = create_resp.json()
        strategy_id = strategy["id"]

        # Step 2: Mock ScreenDataProvider and AsyncSessionPG/TS for run_screen
        load_mock = AsyncMock(return_value=MOCK_STOCKS_DATA)

        # For run_screen, we need to mock the direct AsyncSessionPG() usage
        # AND ensure the strategy lookup works via the same mock
        with patch("app.api.v1.screen.AsyncSessionPG") as mock_pg_cls, \
             patch("app.api.v1.screen.AsyncSessionTS") as mock_ts_cls, \
             patch("app.api.v1.screen.ScreenDataProvider") as mock_provider_cls, \
             patch("app.api.v1.screen.cache_set", new_callable=AsyncMock) as mock_cache:

            # Mock the strategy lookup in run_screen (uses AsyncSessionPG directly)
            fake_strategy = list(pg._store.values())[0]
            mock_pg_session = AsyncMock()
            mock_pg_result = MagicMock()
            mock_pg_result.scalar_one_or_none.return_value = fake_strategy
            mock_pg_session.execute = AsyncMock(return_value=mock_pg_result)

            mock_pg_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pg_session)
            mock_pg_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_ts_inst = MagicMock()
            mock_ts_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ts_inst)
            mock_ts_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_provider = MagicMock()
            mock_provider.load_screen_data = load_mock
            mock_provider_cls.return_value = mock_provider

            run_resp = await client.post(
                "/api/v1/screen/run",
                json={"strategy_id": strategy_id, "screen_type": "EOD"},
            )

        load_mock.assert_called_once()
        assert run_resp.status_code == 200
        body = run_resp.json()
        assert body["strategy_id"] == strategy_id
        assert body["screen_type"] == "EOD"
        assert body["is_complete"] is True
        items = body["items"]
        assert len(items) > 0

        for item in items:
            assert item["symbol"] and isinstance(item["symbol"], str)
            assert Decimal(str(item["ref_buy_price"])) > 0
            assert 0 <= item["trend_score"] <= 100
            assert item["risk_level"] in VALID_RISK_LEVELS
            assert isinstance(item["signals"], list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_nonexistent_strategy_id_returns_404(client: AsyncClient):
    """POST /screen/run with nonexistent strategy_id → HTTP 404."""
    import uuid

    fake_id = str(uuid.uuid4())

    # Mock AsyncSessionPG for run_screen's direct usage
    with patch("app.api.v1.screen.AsyncSessionPG") as mock_pg_cls:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_pg_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_pg_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.post(
            "/api/v1/screen/run",
            json={"strategy_id": fake_id, "screen_type": "EOD"},
        )

    assert resp.status_code == 404
    assert "策略不存在" in resp.json()["detail"]


@pytest.mark.anyio
async def test_empty_database_returns_empty_results(client: AsyncClient):
    """When no market data, POST /screen/run returns items=[] and is_complete=true."""
    fake = _FakeStrategy(
        sid=str(uuid4()), name="empty-db-test",
        config={"factors": [{"factor_name": "ma_trend", "operator": ">=", "threshold": 80.0}], "logic": "AND"},
        enabled_modules=["factor_editor"],
    )

    empty_mock = AsyncMock(return_value={})

    with patch("app.api.v1.screen.AsyncSessionPG") as mock_pg_cls, \
         patch("app.api.v1.screen.AsyncSessionTS") as mock_ts_cls, \
         patch("app.api.v1.screen.ScreenDataProvider") as mock_provider_cls:

        # Strategy lookup
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_pg_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_pg_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_ts_inst = MagicMock()
        mock_ts_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ts_inst)
        mock_ts_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_provider = MagicMock()
        mock_provider.load_screen_data = empty_mock
        mock_provider_cls.return_value = mock_provider

        run_resp = await client.post(
            "/api/v1/screen/run",
            json={"strategy_id": str(fake.id), "screen_type": "EOD"},
        )

    empty_mock.assert_called_once()
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["items"] == []
    assert body["is_complete"] is True
