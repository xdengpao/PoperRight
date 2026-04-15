"""
K线 API adj_type 参数单元测试

验证 GET /api/v1/data/kline/{symbol} 端点的前复权功能：
- adj_type=0 返回原始K线数据
- adj_type=1 返回前复权K线数据
- 不传 adj_type 默认返回原始K线数据
- 响应中包含 adj_type 字段

Requirements: 4.1, 4.2, 4.3
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.adjustment_factor import AdjustmentFactor
from app.models.kline import KlineBar


# ---------------------------------------------------------------------------
# Mock helpers (reuse patterns from test_kline_minute_freq.py)
# ---------------------------------------------------------------------------


def _make_kline_orm(
    symbol: str = "600000",
    dt: datetime = datetime(2024, 6, 10, 0, 0),
    open_: Decimal = Decimal("10.00"),
    high: Decimal = Decimal("11.00"),
    low: Decimal = Decimal("9.50"),
    close: Decimal = Decimal("10.50"),
) -> MagicMock:
    """Create a mock Kline ORM object returned by TimescaleDB query."""
    orm = MagicMock()
    orm.time = dt
    orm.symbol = symbol
    orm.freq = "1d"
    orm.open = open_
    orm.high = high
    orm.low = low
    orm.close = close
    orm.volume = 100000
    orm.amount = Decimal("1050000")
    orm.turnover = Decimal("0.80")
    orm.vol_ratio = Decimal("1.20")
    orm.limit_up = None
    orm.limit_down = None
    orm.adj_type = 0
    return orm


def _make_mock_ts_session(rows=None):
    """Mock AsyncSessionTS context manager returning given rows."""
    if rows is None:
        rows = []

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=result_mock)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=ctx)


def _make_mock_pg_session(stock_name: str = ""):
    """Mock AsyncSessionPG for stock name lookup."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = stock_name or None

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=result_mock)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=ctx)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_ORM = _make_kline_orm()

# Adjustment factor: daily_factor=1.5, latest_factor=2.0 → ratio=0.75
_SAMPLE_FACTORS = [
    AdjustmentFactor(
        symbol="600000",
        trade_date=date(2024, 6, 10),
        adj_type=1,
        adj_factor=Decimal("1.50000000"),
    ),
]
_SAMPLE_LATEST = Decimal("2.00000000")

# Expected adjusted prices: raw * (1.5 / 2.0) = raw * 0.75
# open=10.00*0.75=7.50, high=11.00*0.75=8.25, low=9.50*0.75=7.13 (rounded), close=10.50*0.75=7.88 (rounded)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKlineAdjType:
    """K线 API adj_type 参数测试。"""

    @pytest.mark.asyncio
    async def test_adj_type_0_returns_raw_data(self):
        """adj_type=0 时返回原始K线数据，不调用前复权逻辑。"""
        mock_ts = _make_mock_ts_session(rows=[_make_kline_orm()])
        mock_pg = _make_mock_pg_session()
        mock_adj_query = AsyncMock(return_value=_SAMPLE_FACTORS)
        mock_adj_latest = AsyncMock(return_value=_SAMPLE_LATEST)

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_by_symbol",
                mock_adj_query,
            ),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_latest_factor",
                mock_adj_latest,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={
                        "freq": "1d",
                        "start": "2024-06-10",
                        "end": "2024-06-10",
                        "adj_type": 0,
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bars"]) == 1
        # Raw prices should be unchanged
        assert data["bars"][0]["open"] == "10.00"
        assert data["bars"][0]["high"] == "11.00"
        assert data["bars"][0]["low"] == "9.50"
        assert data["bars"][0]["close"] == "10.50"
        # adj_type=0 should NOT trigger forward adjustment queries
        mock_adj_query.assert_not_called()
        mock_adj_latest.assert_not_called()

    @pytest.mark.asyncio
    async def test_adj_type_1_returns_forward_adjusted_data(self):
        """adj_type=1 时返回前复权K线数据。"""
        mock_ts = _make_mock_ts_session(rows=[_make_kline_orm()])
        mock_pg = _make_mock_pg_session()
        mock_adj_query = AsyncMock(return_value=_SAMPLE_FACTORS)
        mock_adj_latest = AsyncMock(return_value=_SAMPLE_LATEST)

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_by_symbol",
                mock_adj_query,
            ),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_latest_factor",
                mock_adj_latest,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={
                        "freq": "1d",
                        "start": "2024-06-10",
                        "end": "2024-06-10",
                        "adj_type": 1,
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bars"]) == 1

        # ratio = 1.5 / 2.0 = 0.75
        # adjusted: open=7.50, high=8.25, low=7.13, close=7.88
        bar = data["bars"][0]
        assert bar["open"] == "7.50"
        assert bar["high"] == "8.25"
        assert bar["low"] == "7.13"
        assert bar["close"] == "7.88"

        # Forward adjustment repos should have been called
        mock_adj_query.assert_called_once()
        mock_adj_latest.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_no_adj_type_returns_raw_data(self):
        """不传 adj_type 参数时默认返回原始K线数据（adj_type=0）。"""
        mock_ts = _make_mock_ts_session(rows=[_make_kline_orm()])
        mock_pg = _make_mock_pg_session()
        mock_adj_query = AsyncMock(return_value=_SAMPLE_FACTORS)
        mock_adj_latest = AsyncMock(return_value=_SAMPLE_LATEST)

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_by_symbol",
                mock_adj_query,
            ),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_latest_factor",
                mock_adj_latest,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={
                        "freq": "1d",
                        "start": "2024-06-10",
                        "end": "2024-06-10",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bars"]) == 1
        # Raw prices unchanged (default adj_type=0)
        assert data["bars"][0]["open"] == "10.00"
        assert data["bars"][0]["close"] == "10.50"
        assert data["adj_type"] == 0
        # No forward adjustment should be triggered
        mock_adj_query.assert_not_called()
        mock_adj_latest.assert_not_called()

    @pytest.mark.asyncio
    async def test_response_includes_adj_type_field(self):
        """响应中包含 adj_type 字段，标识返回数据的复权类型。"""
        mock_ts = _make_mock_ts_session(rows=[_make_kline_orm()])
        mock_pg = _make_mock_pg_session()
        mock_adj_query = AsyncMock(return_value=_SAMPLE_FACTORS)
        mock_adj_latest = AsyncMock(return_value=_SAMPLE_LATEST)

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_by_symbol",
                mock_adj_query,
            ),
            patch(
                "app.services.data_engine.adj_factor_repository.AdjFactorRepository.query_latest_factor",
                mock_adj_latest,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # Test adj_type=0
                resp0 = await client.get(
                    "/api/v1/data/kline/600000",
                    params={
                        "freq": "1d",
                        "start": "2024-06-10",
                        "end": "2024-06-10",
                        "adj_type": 0,
                    },
                )
                # Test adj_type=1
                resp1 = await client.get(
                    "/api/v1/data/kline/600000",
                    params={
                        "freq": "1d",
                        "start": "2024-06-10",
                        "end": "2024-06-10",
                        "adj_type": 1,
                    },
                )

        assert resp0.status_code == 200
        assert resp0.json()["adj_type"] == 0

        assert resp1.status_code == 200
        assert resp1.json()["adj_type"] == 1
