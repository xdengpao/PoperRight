"""daily_basic 按交易日导入写入策略测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.data_engine.tushare_registry import get_entry
from app.tasks.tushare_import import WriteContext, _write_rows_with_policy


def _daily_basic_rows():
    return [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260427",
            "pe_ttm": 8.0,
            "pb": 1.0,
            "total_mv": 1000000.0,
            "turnover_rate": 3.2,
            "volume_ratio": 1.4,
        }
    ]


@pytest.mark.asyncio
async def test_daily_basic_history_date_skips_primary_write_but_runs_hook():
    entry = get_entry("daily_basic")
    assert entry is not None

    with patch(
        "app.tasks.tushare_import._write_to_postgresql",
        new=AsyncMock(),
    ) as write_pg, patch(
        "app.tasks.tushare_import._run_post_write_hooks",
        new=AsyncMock(),
    ) as hooks:
        stats = await _write_rows_with_policy(
            _daily_basic_rows(),
            entry,
            WriteContext(
                batch_mode="by_trade_date",
                current_trade_date="20260427",
                latest_market_trade_date="20260429",
            ),
        )

    write_pg.assert_not_awaited()
    hooks.assert_awaited_once()
    assert stats["api_rows"] == 1
    assert stats["primary_written_rows"] == 0


@pytest.mark.asyncio
async def test_daily_basic_latest_market_date_writes_primary_and_hook():
    entry = get_entry("daily_basic")
    assert entry is not None

    with patch(
        "app.tasks.tushare_import._write_to_postgresql",
        new=AsyncMock(),
    ) as write_pg, patch(
        "app.tasks.tushare_import._run_post_write_hooks",
        new=AsyncMock(),
    ) as hooks:
        stats = await _write_rows_with_policy(
            _daily_basic_rows(),
            entry,
            WriteContext(
                batch_mode="by_trade_date",
                current_trade_date="20260429",
                latest_market_trade_date="20260429",
            ),
        )

    write_pg.assert_awaited_once()
    assert write_pg.await_args.kwargs["run_post_hooks"] is True
    hooks.assert_not_awaited()
    assert stats["primary_written_rows"] == 1


@pytest.mark.asyncio
async def test_daily_basic_explicit_snapshot_update_writes_old_date():
    entry = get_entry("daily_basic")
    assert entry is not None

    with patch(
        "app.tasks.tushare_import._write_to_postgresql",
        new=AsyncMock(),
    ) as write_pg:
        stats = await _write_rows_with_policy(
            _daily_basic_rows(),
            entry,
            WriteContext(
                batch_mode="by_trade_date",
                current_trade_date="20240131",
                latest_market_trade_date="20260429",
                update_current_snapshot=True,
            ),
        )

    write_pg.assert_awaited_once()
    assert stats["primary_written_rows"] == 1


@pytest.mark.asyncio
async def test_stk_limit_always_writes_primary():
    entry = get_entry("stk_limit")
    assert entry is not None

    with patch(
        "app.tasks.tushare_import._write_to_postgresql",
        new=AsyncMock(),
    ) as write_pg:
        stats = await _write_rows_with_policy(
            [{"ts_code": "000001.SZ", "trade_date": "20260427", "up_limit": 11.0}],
            entry,
            WriteContext(batch_mode="by_trade_date", current_trade_date="20260427"),
        )

    write_pg.assert_awaited_once()
    assert stats["api_rows"] == 1
    assert stats["primary_written_rows"] == 1
