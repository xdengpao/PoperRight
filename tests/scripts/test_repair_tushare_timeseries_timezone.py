"""Tushare 时序时区历史修复脚本测试。"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "repair_tushare_timeseries_timezone.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "repair_tushare_timeseries_timezone",
    _SCRIPT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
repair = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = repair
_SPEC.loader.exec_module(repair)


def test_parse_repair_date_accepts_two_formats():
    assert repair.parse_repair_date("20260429") == date(2026, 4, 29)
    assert repair.parse_repair_date("2026-04-29") == date(2026, 4, 29)


def test_split_date_batches_uses_closed_range():
    batches = repair.split_date_batches(date(2026, 4, 1), date(2026, 4, 6), 2)
    assert batches == [
        repair.RepairBatch(date(2026, 4, 1), date(2026, 4, 2)),
        repair.RepairBatch(date(2026, 4, 3), date(2026, 4, 4)),
        repair.RepairBatch(date(2026, 4, 5), date(2026, 4, 6)),
    ]


def test_validate_freqs_rejects_intraday_frequency():
    with pytest.raises(ValueError):
        repair.validate_freqs(["1d", "5m"])


def test_dry_run_sql_uses_table_specific_hour_expression():
    kline_sql = repair.build_dry_run_sql("kline", ["1d"])["summary"]
    sector_sql = repair.build_dry_run_sql("sector_kline", ["1d"])["summary"]

    assert "at time zone 'UTC'" in kline_sql
    assert "extract(hour from src.time)" in sector_sql
    assert "at time zone 'UTC'" not in sector_sql
    assert kline_sql.index("FROM kline src") < kline_sql.index("LEFT JOIN")
    assert kline_sql.index("LEFT JOIN") < kline_sql.rindex("WHERE src.freq")
    assert sector_sql.index("FROM sector_kline src") < sector_sql.index("LEFT JOIN")
    assert sector_sql.index("LEFT JOIN") < sector_sql.rindex("WHERE src.freq")


def test_execute_sql_preserves_target_values_with_coalesce_order():
    sql = repair.build_execute_sql("kline", ["1d"])
    assert "open = COALESCE(dst.open, src.open)" in sql
    assert "turnover = COALESCE(dst.turnover, src.turnover)" in sql
    assert "DELETE FROM kline" in sql
    assert "UPDATE kline k" in sql


def test_move_only_sql_keeps_not_exists_guard():
    sql = repair.build_move_only_sql("kline", ["1d"])
    assert "UPDATE kline src" in sql
    assert "NOT EXISTS" in sql
    assert "dst.time = src.time + interval '8 hours'" in sql


def test_local_duplicate_sql_uses_shanghai_trade_date_for_kline():
    sql = repair.build_local_duplicate_sql("kline", ["1d"])
    sample_sql = repair.build_local_duplicate_samples_sql("kline", ["1d"])

    assert "date(src.time at time zone 'Asia/Shanghai')" in sql
    assert "date(src.time at time zone 'Asia/Shanghai')" in sample_sql
    assert "HAVING COUNT(*) > 1" in sample_sql


def test_ohlcv_diff_dry_run_sql_is_read_only():
    sqls = repair.build_ohlcv_diff_sql("kline", ["1d"])
    joined = f"{sqls['summary']}\n{sqls['samples']}".upper()

    assert "IS DISTINCT FROM" in joined
    assert "UPDATE " not in joined
    assert "DELETE " not in joined


def test_target_distribution_sql_groups_by_target_date():
    sql = repair.build_target_distribution_sql("kline", ["1d"])

    assert "src.time + interval '8 hours'" in sql
    assert "target_date" in sql
    assert "GROUP BY 1" in sql


def test_delete_conflicts_only_sql_keeps_target_join_guard():
    sql = repair.build_delete_conflicts_only_sql("kline", ["1d"])

    assert "DELETE FROM kline src" in sql
    assert "USING kline dst" in sql
    assert "dst.time = src.time + interval '8 hours'" in sql
    assert "dst.symbol = src.symbol" in sql


def test_fill_needed_sql_checks_target_null_source_non_null():
    sql = repair.build_fill_needed_sql("kline", ["1d"])

    assert "need_fill_rows" in sql
    assert "dst.turnover IS NULL AND src.turnover IS NOT NULL" in sql
    assert "dst.limit_down IS NULL AND src.limit_down IS NOT NULL" in sql


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self) -> None:
        self.sql_texts: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt, _params=None):
        sql_text = str(stmt)
        self.sql_texts.append(sql_text)
        if "SELECT\n              COUNT(*) AS candidate_rows" in sql_text:
            return _FakeResult([
                {"candidate_rows": 1, "conflict_rows": 0, "movable_rows": 1}
            ])
        if "target_distribution" in sql_text or "AS target_date" in sql_text:
            return _FakeResult([])
        if "duplicate_groups" in sql_text:
            return _FakeResult([
                {"duplicate_groups": 0, "duplicate_extra_rows": 0}
            ])
        if "AS local_trade_date" in sql_text and "HAVING COUNT(*) > 1" in sql_text:
            return _FakeResult([])
        if "AS diff_rows" in sql_text:
            return _FakeResult([
                {"diff_rows": 0}
            ])
        if "ohlcv_diff_sample" in sql_text or "src_open" in sql_text:
            return _FakeResult([])
        return _FakeResult([])


@pytest.mark.asyncio
async def test_async_main_dry_run_does_not_execute_update_or_delete():
    fake = _FakeSession()
    with patch.object(repair, "AsyncSessionTS", return_value=fake):
        code = await repair.async_main(
            [
                "--table", "kline",
                "--start-date", "20260429",
                "--end-date", "20260429",
                "--dry-run",
            ]
        )

    assert code == 0
    joined_sql = "\n".join(fake.sql_texts).upper()
    assert "UPDATE " not in joined_sql
    assert "DELETE " not in joined_sql
