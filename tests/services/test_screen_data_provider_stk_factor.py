"""ScreenDataProvider stk_factor 最近可用日期回退测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.tushare_import import StkFactor
from app.services.screener.screen_data_provider import ScreenDataProvider


def _make_stk_factor(ts_code: str = "000001.SZ", trade_date: str = "20240610") -> StkFactor:
    row = StkFactor()
    row.ts_code = ts_code
    row.trade_date = trade_date
    row.kdj_k = 70.0
    row.kdj_d = 60.0
    row.kdj_j = 90.0
    row.cci = 120.0
    row.wr = 20.0
    row.trix = 1.5
    row.bias = 3.0
    return row


@pytest.mark.asyncio
async def test_stk_factor_target_date_hit_uses_target_date():
    provider = ScreenDataProvider(pg_session=MagicMock())
    provider._query_stk_factor = AsyncMock(return_value=[_make_stk_factor()])
    provider._resolve_latest_stk_factor_date = AsyncMock(return_value="20240609")

    stocks_data = {"000001.SZ": {}}
    await provider._enrich_stk_factor_factors(stocks_data, date(2024, 6, 10))

    assert stocks_data["000001.SZ"]["kdj_k"] == 70.0
    assert stocks_data["000001.SZ"]["trix"] is True
    provider._query_stk_factor.assert_awaited_once()
    provider._resolve_latest_stk_factor_date.assert_not_awaited()


@pytest.mark.asyncio
async def test_stk_factor_falls_back_to_latest_available_date():
    provider = ScreenDataProvider(pg_session=MagicMock())
    provider._query_stk_factor = AsyncMock(
        side_effect=[[], [_make_stk_factor(trade_date="20240607")]]
    )
    provider._resolve_latest_stk_factor_date = AsyncMock(return_value="20240607")

    stocks_data = {"000001.SZ": {}, "000002.SZ": {}}
    await provider._enrich_stk_factor_factors(stocks_data, date(2024, 6, 10))

    assert stocks_data["000001.SZ"]["cci"] == 120.0
    assert stocks_data["000002.SZ"]["cci"] is None
    assert provider._query_stk_factor.await_count == 2
    provider._resolve_latest_stk_factor_date.assert_awaited_once()


@pytest.mark.asyncio
async def test_stk_factor_no_recent_date_degrades_to_none():
    provider = ScreenDataProvider(pg_session=MagicMock())
    provider._query_stk_factor = AsyncMock(return_value=[])
    provider._resolve_latest_stk_factor_date = AsyncMock(return_value=None)

    stocks_data = {"000001.SZ": {}}
    await provider._enrich_stk_factor_factors(stocks_data, date(2024, 6, 10))

    assert stocks_data["000001.SZ"]["kdj_k"] is None
    assert stocks_data["000001.SZ"]["trix"] is None
    provider._query_stk_factor.assert_awaited_once()
