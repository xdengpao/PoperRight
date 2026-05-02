"""KlineAuxFieldBackfillService 单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.kline_aux_field_backfill import (
    KlineAuxFieldBackfillService,
)


def _make_ts_session(matched: int = 1, updated: int = 1) -> MagicMock:
    result = MagicMock()
    result.first.return_value = SimpleNamespace(
        matched_rows=matched,
        updated_rows=updated,
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_result(matched: int = 1, updated: int = 1) -> MagicMock:
    result = MagicMock()
    result.first.return_value = SimpleNamespace(
        matched_rows=matched,
        updated_rows=updated,
    )
    return result


@pytest.mark.asyncio
async def test_backfill_daily_basic_rows_updates_turnover_and_vol_ratio():
    ts_session = _make_ts_session(matched=2, updated=2)
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    stats = await service.backfill_daily_basic_rows(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240610",
                "turnover_rate": 5.5,
                "volume_ratio": 1.2,
            },
            {
                "symbol": "600000.SH",
                "trade_date": "2024-06-10",
                "turnover_rate": 3.2,
                "volume_ratio": 0.9,
            },
        ]
    )

    assert stats.source_table == "daily_basic"
    assert stats.source_rows == 2
    assert stats.matched_rows == 2
    assert stats.updated_rows == 2
    assert stats.retry_count == 0
    assert ts_session.execute.await_count == 2
    lock_sql = str(ts_session.execute.await_args_list[0].args[0])
    assert "pg_advisory_xact_lock" in lock_sql
    ts_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_backfill_stk_limit_rows_updates_limit_prices():
    ts_session = _make_ts_session(matched=1, updated=1)
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    stats = await service.backfill_stk_limit_rows(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240610",
                "up_limit": 11.0,
                "down_limit": 9.0,
            }
        ]
    )

    assert stats.source_table == "stk_limit"
    assert stats.matched_rows == 1
    assert stats.updated_rows == 1
    assert ts_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_none_values_are_skipped_without_update():
    ts_session = _make_ts_session()
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    stats = await service.backfill_daily_basic_rows(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240610",
                "turnover_rate": None,
                "volume_ratio": None,
            }
        ]
    )

    assert stats.source_rows == 1
    assert stats.matched_rows == 0
    assert stats.updated_rows == 0
    assert stats.skipped_rows == 1
    ts_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_idempotent_repeat_can_match_without_update():
    ts_session = _make_ts_session(matched=1, updated=0)
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    stats = await service.backfill_stk_limit_rows(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240610",
                "up_limit": 11.0,
                "down_limit": 9.0,
            }
        ]
    )

    assert stats.matched_rows == 1
    assert stats.updated_rows == 0
    assert stats.skipped_rows == 0


@pytest.mark.asyncio
async def test_transient_error_retries_batch_and_records_retry_count():
    ts_session = MagicMock()
    ts_session.execute = AsyncMock(
        side_effect=[
            _make_result(),
            RuntimeError("deadlock detected"),
            _make_result(),
            _make_result(matched=1, updated=1),
        ]
    )
    ts_session.commit = AsyncMock()
    ts_session.rollback = AsyncMock()
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    with patch(
        "app.services.data_engine.kline_aux_field_backfill.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock:
        stats = await service.backfill_stk_limit_rows(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20240610",
                    "up_limit": 11.0,
                    "down_limit": 9.0,
                }
            ]
        )

    assert stats.matched_rows == 1
    assert stats.updated_rows == 1
    assert stats.retry_count == 1
    assert ts_session.execute.await_count == 4
    ts_session.rollback.assert_awaited_once()
    ts_session.commit.assert_awaited_once()
    sleep_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_transient_error_raises_without_retry():
    ts_session = MagicMock()
    ts_session.execute = AsyncMock(
        side_effect=[
            _make_result(),
            RuntimeError("permission denied for table kline"),
        ]
    )
    ts_session.commit = AsyncMock()
    ts_session.rollback = AsyncMock()
    service = KlineAuxFieldBackfillService(ts_session=ts_session)

    with pytest.raises(RuntimeError, match="permission denied"):
        await service.backfill_daily_basic_rows(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20240610",
                    "turnover_rate": 5.5,
                    "volume_ratio": 1.2,
                }
            ]
        )

    assert ts_session.execute.await_count == 2
    ts_session.rollback.assert_awaited_once()
    ts_session.commit.assert_not_awaited()
