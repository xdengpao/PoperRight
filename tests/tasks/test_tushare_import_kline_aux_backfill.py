"""Tushare 导入后置 kline 辅助字段回填 hook 测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.services.data_engine.tushare_registry import get_entry
from app.tasks import tushare_import


@dataclass
class _Stats:
    source_table: str
    start_date: str | None
    end_date: str | None
    source_rows: int
    matched_rows: int
    updated_rows: int
    skipped_rows: int
    retry_count: int = 0
    failed_batches: int = 0


@pytest.mark.asyncio
async def test_daily_basic_post_write_hook_records_backfill_stats():
    entry = get_entry("daily_basic")
    assert entry is not None
    token = tushare_import._BACKFILL_HOOK_INFO.set([])
    try:
        service = AsyncMock()
        service.backfill_daily_basic_rows.return_value = _Stats(
            "daily_basic", "2024-06-10", "2024-06-10", 1, 1, 1, 0
        )
        with patch(
            "app.services.data_engine.kline_aux_field_backfill.KlineAuxFieldBackfillService",
            return_value=service,
        ):
            await tushare_import._run_post_write_hooks(
                [{"symbol": "000001.SZ", "trade_date": "20240610"}],
                entry,
            )

        merged = tushare_import._merge_backfill_hook_info(None)
        assert merged is not None
        assert merged["kline_aux_backfill"][0]["source_table"] == "daily_basic"
        assert merged["kline_aux_backfill"][0]["updated_rows"] == 1
        assert merged["kline_aux_backfill_summary"]["items"] == 1
        assert merged["kline_aux_backfill_summary"]["updated_rows"] == 1
        assert merged["kline_aux_backfill_summary"]["errors"] == 0
        service.backfill_daily_basic_rows.assert_awaited_once()
    finally:
        tushare_import._BACKFILL_HOOK_INFO.reset(token)


@pytest.mark.asyncio
async def test_stk_limit_post_write_hook_records_error_without_raise():
    entry = get_entry("stk_limit")
    assert entry is not None
    token = tushare_import._BACKFILL_HOOK_INFO.set([])
    try:
        service = AsyncMock()
        service.backfill_stk_limit_rows.side_effect = RuntimeError("ts unavailable")
        with patch(
            "app.services.data_engine.kline_aux_field_backfill.KlineAuxFieldBackfillService",
            return_value=service,
        ):
            await tushare_import._run_post_write_hooks(
                [{"ts_code": "000001.SZ", "trade_date": "20240610"}],
                entry,
            )

        merged = tushare_import._merge_backfill_hook_info({})
        assert merged is not None
        assert merged["backfill_error"] == "ts unavailable"
        assert merged["kline_aux_backfill"][0]["source_table"] == "stk_limit"
        assert merged["kline_aux_backfill"][0]["start_date"] == "2024-06-10"
        assert merged["kline_aux_backfill"][0]["end_date"] == "2024-06-10"
        assert merged["kline_aux_backfill"][0]["source_rows"] == 1
        assert merged["kline_aux_backfill"][0]["failed_batches"] == 1
        assert merged["kline_aux_backfill_summary"]["errors"] == 1
        assert merged["kline_aux_backfill_summary"]["failed_batches"] == 1
        service.backfill_stk_limit_rows.assert_awaited_once()
    finally:
        tushare_import._BACKFILL_HOOK_INFO.reset(token)


@pytest.mark.asyncio
async def test_post_write_hook_compacts_long_sql_error():
    entry = get_entry("daily_basic")
    assert entry is not None
    token = tushare_import._BACKFILL_HOOK_INFO.set([])
    try:
        service = AsyncMock()
        service.backfill_daily_basic_rows.side_effect = RuntimeError(
            "boom\n[SQL: SELECT * FROM kline WHERE very_long_condition]\n[parameters: ...]"
        )
        with patch(
            "app.services.data_engine.kline_aux_field_backfill.KlineAuxFieldBackfillService",
            return_value=service,
        ):
            await tushare_import._run_post_write_hooks(
                [{"ts_code": "000001.SZ", "trade_date": "20240610"}],
                entry,
            )

        merged = tushare_import._merge_backfill_hook_info({})
        assert merged is not None
        error = merged["kline_aux_backfill"][0]["backfill_error"]
        assert error == "boom"
        assert "[SQL:" not in error
        assert merged["kline_aux_backfill_summary"]["errors"] == 1
    finally:
        tushare_import._BACKFILL_HOOK_INFO.reset(token)


def test_merge_backfill_hook_info_adds_summary_totals():
    token = tushare_import._BACKFILL_HOOK_INFO.set(
        [
            {
                "source_table": "daily_basic",
                "start_date": "2024-06-10",
                "end_date": "2024-06-10",
                "source_rows": 2,
                "matched_rows": 2,
                "updated_rows": 1,
                "skipped_rows": 0,
                "retry_count": 1,
            },
            {
                "source_table": "stk_limit",
                "start_date": "2024-06-11",
                "end_date": "2024-06-11",
                "source_rows": 3,
                "matched_rows": 1,
                "updated_rows": 1,
                "skipped_rows": 2,
                "failed_batches": 1,
                "backfill_error": "DeadlockDetectedError: deadlock detected",
            },
        ]
    )
    try:
        merged = tushare_import._merge_backfill_hook_info({"batch_mode": "by_trade_date"})
    finally:
        tushare_import._BACKFILL_HOOK_INFO.reset(token)

    assert merged is not None
    summary = merged["kline_aux_backfill_summary"]
    assert summary["items"] == 2
    assert summary["errors"] == 1
    assert summary["source_rows"] == 5
    assert summary["matched_rows"] == 3
    assert summary["updated_rows"] == 2
    assert summary["skipped_rows"] == 2
    assert summary["retry_count"] == 1
    assert summary["failed_batches"] == 1
    assert summary["start_date"] == "2024-06-10"
    assert summary["end_date"] == "2024-06-11"
