"""
选股执行全链路集成测试

26.4.1: 创建策略 → mock 预设股票因子数据 → 执行选股 → 验证返回真实结果

Validates: Requirements 27.9, 27.10
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.screen import _strategies
from app.main import app

VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


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


# Pre-built stock factor data with realistic values that will pass screening.
# ma_trend >= 80 ensures trend score is high enough; closes/highs/lows/volumes
# sequences are needed by the strategy engine evaluation.
MOCK_STOCKS_DATA = {
    "000001": {
        "close": 15.50,
        "open": 15.20,
        "high": 15.80,
        "low": 15.10,
        "volume": 850000,
        "amount": 13175000.0,
        "turnover": 5.2,
        "vol_ratio": 1.8,
        "closes": [14.0, 14.3, 14.6, 14.9, 15.2, 15.50],
        "highs": [14.2, 14.5, 14.8, 15.1, 15.4, 15.80],
        "lows": [13.8, 14.1, 14.4, 14.7, 15.0, 15.10],
        "volumes": [700000, 720000, 750000, 780000, 800000, 850000],
        "amounts": [9800000, 10296000, 10950000, 11622000, 12160000, 13175000],
        "turnovers": [4.0, 4.2, 4.5, 4.8, 5.0, 5.2],
        "pe_ttm": 12.5,
        "pb": 1.8,
        "roe": 15.0,
        "market_cap": 3500.0,
        "ma_trend": 85,
    },
    "600036": {
        "close": 42.30,
        "open": 41.80,
        "high": 42.60,
        "low": 41.50,
        "volume": 1200000,
        "amount": 50760000.0,
        "turnover": 3.8,
        "vol_ratio": 2.1,
        "closes": [40.0, 40.5, 41.0, 41.5, 42.0, 42.30],
        "highs": [40.3, 40.8, 41.3, 41.8, 42.3, 42.60],
        "lows": [39.7, 40.2, 40.7, 41.2, 41.7, 41.50],
        "volumes": [1000000, 1050000, 1080000, 1100000, 1150000, 1200000],
        "amounts": [40000000, 42525000, 44280000, 45650000, 48300000, 50760000],
        "turnovers": [3.0, 3.2, 3.3, 3.5, 3.6, 3.8],
        "pe_ttm": 8.2,
        "pb": 0.9,
        "roe": 18.0,
        "market_cap": 12000.0,
        "ma_trend": 92,
    },
}


@pytest.mark.anyio
async def test_create_strategy_run_screen_full_chain(client: AsyncClient):
    """
    Full chain: create strategy with enabled_modules → mock ScreenDataProvider
    → POST /screen/run → verify non-empty items with all required fields.

    Validates: Requirements 27.9, 27.10
    """
    # Step 1: Create strategy with enabled_modules
    create_resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "integration-test-strategy",
            "config": {
                "factors": [
                    {"factor_name": "ma_trend", "operator": ">=", "threshold": 80.0, "params": {}},
                ],
                "logic": "AND",
            },
            "enabled_modules": ["factor_editor", "ma_trend"],
        },
    )
    assert create_resp.status_code == 201
    strategy = create_resp.json()
    strategy_id = strategy["id"]
    assert strategy["name"] == "integration-test-strategy"
    assert sorted(strategy["enabled_modules"]) == ["factor_editor", "ma_trend"]

    # Step 2: Mock ScreenDataProvider to return pre-built factor data
    load_mock = AsyncMock(return_value=MOCK_STOCKS_DATA)

    with patch("app.api.v1.screen.AsyncSessionPG") as mock_pg, \
         patch("app.api.v1.screen.AsyncSessionTS") as mock_ts, \
         patch("app.api.v1.screen.ScreenDataProvider") as mock_provider_cls:

        mock_pg_inst = MagicMock()
        mock_pg.return_value.__aenter__ = AsyncMock(return_value=mock_pg_inst)
        mock_pg.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_ts_inst = MagicMock()
        mock_ts.return_value.__aenter__ = AsyncMock(return_value=mock_ts_inst)
        mock_ts.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_provider = MagicMock()
        mock_provider.load_screen_data = load_mock
        mock_provider_cls.return_value = mock_provider

        # Step 3: Execute screening
        run_resp = await client.post(
            "/api/v1/screen/run",
            json={"strategy_id": strategy_id, "screen_type": "EOD"},
        )

    # Step 4: Verify ScreenDataProvider was called (local DB driven, req 27.10)
    load_mock.assert_called_once()

    assert run_resp.status_code == 200
    body = run_resp.json()

    # Top-level fields
    assert body["strategy_id"] == strategy_id
    assert body["screen_type"] == "EOD"
    assert body["is_complete"] is True
    assert "screen_time" in body

    # Items must be non-empty (we provided data that passes screening)
    items = body["items"]
    assert len(items) > 0, "Expected non-empty screening results"

    # Verify every item has all required fields with valid values
    for item in items:
        assert item["symbol"] and isinstance(item["symbol"], str)

        ref_price = Decimal(str(item["ref_buy_price"]))
        assert ref_price > 0

        assert isinstance(item["trend_score"], (int, float))
        assert 0 <= item["trend_score"] <= 100

        assert item["risk_level"] in VALID_RISK_LEVELS

        assert isinstance(item["signals"], list)


@pytest.mark.anyio
async def test_nonexistent_strategy_id_returns_404(client: AsyncClient):
    """
    POST /screen/run with a strategy_id that does not exist in _strategies
    must return HTTP 404 with detail "策略不存在".

    Validates: Requirement 27.11
    """
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/screen/run",
        json={"strategy_id": fake_id, "screen_type": "EOD"},
    )
    assert resp.status_code == 404
    assert "策略不存在" in resp.json()["detail"]


@pytest.mark.anyio
async def test_empty_database_returns_empty_results(client: AsyncClient):
    """
    When ScreenDataProvider.load_screen_data returns an empty dict (no market
    data in local DB), POST /screen/run must return HTTP 200 with items=[]
    and is_complete=true.

    Validates: Requirement 27.12
    """
    # Step 1: Create a valid strategy
    create_resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "empty-db-test-strategy",
            "config": {
                "factors": [
                    {"factor_name": "ma_trend", "operator": ">=", "threshold": 80.0},
                ],
                "logic": "AND",
            },
            "enabled_modules": ["factor_editor"],
        },
    )
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]

    # Step 2: Mock ScreenDataProvider to return empty dict (no data)
    empty_mock = AsyncMock(return_value={})

    with patch("app.api.v1.screen.AsyncSessionPG") as mock_pg, \
         patch("app.api.v1.screen.AsyncSessionTS") as mock_ts, \
         patch("app.api.v1.screen.ScreenDataProvider") as mock_provider_cls:

        mock_pg_inst = MagicMock()
        mock_pg.return_value.__aenter__ = AsyncMock(return_value=mock_pg_inst)
        mock_pg.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_ts_inst = MagicMock()
        mock_ts.return_value.__aenter__ = AsyncMock(return_value=mock_ts_inst)
        mock_ts.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_provider = MagicMock()
        mock_provider.load_screen_data = empty_mock
        mock_provider_cls.return_value = mock_provider

        # Step 3: Execute screening
        run_resp = await client.post(
            "/api/v1/screen/run",
            json={"strategy_id": strategy_id, "screen_type": "EOD"},
        )

    # Step 4: Verify empty result set
    empty_mock.assert_called_once()
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["items"] == []
    assert body["is_complete"] is True
    assert body["strategy_id"] == strategy_id
