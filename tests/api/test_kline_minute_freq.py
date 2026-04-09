"""
分钟级K线频率回退逻辑单元测试

验证 GET /api/v1/data/kline/{symbol} 端点：
- 分钟级 freq（1m/5m/15m/30m/60m）本地无数据时返回空 bars，不调用 DataSourceRouter
- 日级 freq（1d）本地无数据时回退到 DataSourceRouter

需求: 5.2, 5.5
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.kline import KlineBar


def _make_mock_session(rows=None):
    """Create a mock async session that returns the given rows from execute().

    The mock replicates the pattern:
        async with AsyncSessionTS() as session:
            result = await session.execute(...)
            rows = result.scalars().all()
    """
    if rows is None:
        rows = []

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=result_mock)

    # Support `async with AsyncSessionXX() as session:`
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory


def _make_mock_pg_session(stock_name: str = ""):
    """Create a mock PG session for stock name lookup."""
    scalar_result = stock_name or None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = scalar_result

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=result_mock)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory


class TestMinuteFreqNoFallback:
    """分钟级 freq 本地无数据时不调用 DataSourceRouter。"""

    @pytest.mark.asyncio
    async def test_5m_no_local_data_returns_empty_bars(self):
        """5m freq 本地无数据 → 返回空 bars，不调用 DataSourceRouter。"""
        mock_ts = _make_mock_session(rows=[])
        mock_pg = _make_mock_pg_session()
        mock_fetch_kline = AsyncMock(return_value=[])

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.data_source_router.DataSourceRouter.fetch_kline",
                mock_fetch_kline,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={"freq": "5m", "start": "2024-01-15", "end": "2024-01-15"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["bars"] == []
        assert data["freq"] == "5m"
        mock_fetch_kline.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("freq", ["1m", "5m", "15m", "30m", "60m"])
    async def test_all_minute_freqs_skip_fallback(self, freq: str):
        """所有分钟级 freq 本地无数据时均不调用 DataSourceRouter。"""
        mock_ts = _make_mock_session(rows=[])
        mock_pg = _make_mock_pg_session()
        mock_fetch_kline = AsyncMock(return_value=[])

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.data_source_router.DataSourceRouter.fetch_kline",
                mock_fetch_kline,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={"freq": freq, "start": "2024-01-15", "end": "2024-01-15"},
                )

        assert resp.status_code == 200
        assert resp.json()["bars"] == []
        mock_fetch_kline.assert_not_called()


class TestDailyFreqFallback:
    """日级 freq 本地无数据时回退到 DataSourceRouter。"""

    @pytest.mark.asyncio
    async def test_1d_no_local_data_calls_datasource_router(self):
        """1d freq 本地无数据 → 回退调用 DataSourceRouter.fetch_kline。"""
        mock_ts = _make_mock_session(rows=[])
        mock_pg = _make_mock_pg_session()

        sample_bar = KlineBar(
            time=datetime(2024, 1, 15, 0, 0),
            symbol="600000",
            freq="1d",
            open=Decimal("10.50"),
            high=Decimal("10.80"),
            low=Decimal("10.40"),
            close=Decimal("10.70"),
            volume=500000,
            amount=Decimal("5300000"),
            turnover=Decimal("0.50"),
            vol_ratio=Decimal("1.10"),
        )
        mock_fetch_kline = AsyncMock(return_value=[sample_bar])

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.data_source_router.DataSourceRouter.fetch_kline",
                mock_fetch_kline,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={"freq": "1d", "start": "2024-01-15", "end": "2024-01-15"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bars"]) == 1
        assert data["bars"][0]["close"] == "10.70"
        mock_fetch_kline.assert_called_once()

    @pytest.mark.asyncio
    async def test_1d_with_local_data_skips_fallback(self):
        """1d freq 本地有数据 → 不调用 DataSourceRouter。"""
        # Create a mock Kline ORM object
        kline_orm = MagicMock()
        kline_orm.time = datetime(2024, 1, 15, 0, 0)
        kline_orm.symbol = "600000"
        kline_orm.freq = "1d"
        kline_orm.open = Decimal("10.50")
        kline_orm.high = Decimal("10.80")
        kline_orm.low = Decimal("10.40")
        kline_orm.close = Decimal("10.70")
        kline_orm.volume = 500000
        kline_orm.amount = Decimal("5300000")
        kline_orm.turnover = Decimal("0.50")
        kline_orm.vol_ratio = Decimal("1.10")
        kline_orm.limit_up = None
        kline_orm.limit_down = None
        kline_orm.adj_type = 0

        mock_ts = _make_mock_session(rows=[kline_orm])
        mock_pg = _make_mock_pg_session()
        mock_fetch_kline = AsyncMock(return_value=[])

        with (
            patch("app.core.database.AsyncSessionTS", mock_ts),
            patch("app.core.database.AsyncSessionPG", mock_pg),
            patch(
                "app.services.data_engine.data_source_router.DataSourceRouter.fetch_kline",
                mock_fetch_kline,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/kline/600000",
                    params={"freq": "1d", "start": "2024-01-15", "end": "2024-01-15"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bars"]) == 1
        mock_fetch_kline.assert_not_called()
