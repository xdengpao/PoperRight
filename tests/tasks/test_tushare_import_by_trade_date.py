"""Tushare 按交易日全市场导入执行器测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_adapter import TushareAPIError
from app.services.data_engine.tushare_registry import get_entry
from app.tasks import tushare_import


def _data(ts_code: str = "000001.SZ") -> dict:
    return {
        "fields": ["ts_code", "trade_date", "close"],
        "items": [[ts_code, "20260427", 10.0]],
    }


@pytest.mark.asyncio
async def test_process_batched_by_trade_date_calls_api_once_per_trade_date():
    entry = get_entry("stk_factor_pro")
    assert entry is not None
    adapter = MagicMock()
    write = AsyncMock(return_value={"api_rows": 1, "primary_written_rows": 1})

    with patch(
        "app.tasks.tushare_import._resolve_trade_dates",
        new=AsyncMock(return_value=(["20260427", "20260428", "20260429"], True)),
    ), patch(
        "app.tasks.tushare_import._resolve_latest_market_trade_date",
        new=AsyncMock(return_value=("20260429", True)),
    ), patch(
        "app.tasks.tushare_import._call_api_with_retry",
        new=AsyncMock(return_value=_data()),
    ) as call_api, patch(
        "app.tasks.tushare_import._write_rows_with_policy",
        new=write,
    ), patch(
        "app.tasks.tushare_import._update_progress",
        new=AsyncMock(),
    ), patch(
        "app.tasks.tushare_import._check_stop_signal",
        new=AsyncMock(return_value=False),
    ), patch(
        "asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await tushare_import._process_batched_by_trade_date(
            entry, adapter, {"start_date": "20260427", "end_date": "20260429"},
            "task-1", 1, 0,
        )

    assert call_api.await_count == 3
    seen_trade_dates = [call.args[2]["trade_date"] for call in call_api.await_args_list]
    assert seen_trade_dates == ["20260427", "20260428", "20260429"]
    assert all("start_date" not in call.args[2] for call in call_api.await_args_list)
    assert all("end_date" not in call.args[2] for call in call_api.await_args_list)
    assert write.await_count == 3
    assert result["record_count"] == 3
    assert result["batch_stats"]["planned_trade_dates"] == 3
    assert result["batch_stats"]["api_rows"] == 3
    assert result["batch_stats"]["primary_written_rows"] == 3


@pytest.mark.asyncio
async def test_process_batched_by_trade_date_tracks_empty_and_failed_dates():
    entry = get_entry("stk_limit")
    assert entry is not None
    adapter = MagicMock()
    responses = [
        {"fields": ["ts_code", "trade_date"], "items": []},
        TushareAPIError("boom", api_name="stk_limit"),
        _data("000002.SZ"),
    ]

    async def fake_call(*args, **kwargs):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with patch(
        "app.tasks.tushare_import._resolve_trade_dates",
        new=AsyncMock(return_value=(["20260427", "20260428", "20260429"], True)),
    ), patch(
        "app.tasks.tushare_import._resolve_latest_market_trade_date",
        new=AsyncMock(return_value=("20260429", True)),
    ), patch(
        "app.tasks.tushare_import._call_api_with_retry",
        new=AsyncMock(side_effect=fake_call),
    ), patch(
        "app.tasks.tushare_import._write_rows_with_policy",
        new=AsyncMock(return_value={"api_rows": 1, "primary_written_rows": 1}),
    ), patch(
        "app.tasks.tushare_import._update_progress",
        new=AsyncMock(),
    ), patch(
        "app.tasks.tushare_import._check_stop_signal",
        new=AsyncMock(return_value=False),
    ), patch(
        "asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await tushare_import._process_batched_by_trade_date(
            entry, adapter, {"start_date": "20260427", "end_date": "20260429"},
            "task-1", 1, 0,
        )

    stats = result["batch_stats"]
    assert stats["empty_trade_dates"] == 1
    assert stats["failed_trade_dates"] == 1
    assert stats["failed_dates"] == ["20260428"]
    assert stats["api_rows"] == 1
