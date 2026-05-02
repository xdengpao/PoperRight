#!/usr/bin/env python
"""按交易日精确修复 K 线日级 16:00 UTC 重复数据。

该脚本用于处理同一交易日同时存在：

- 规范行：`trade_date 00:00:00 UTC`
- 旧脏行：`trade_date - 8 hours`，即前一日 `16:00:00 UTC`

与旧的宽范围扫描不同，本脚本逐个交易日只命中两个精确时间点，
避免在大表上执行 `extract(hour)` 导致长时间扫描。
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Sequence

from sqlalchemy import text

from app.core.database import AsyncSessionTS


DATE_FREQS = {"1d", "1w", "1M"}


@dataclass(frozen=True)
class DayStats:
    trade_date: date
    candidate_rows: int
    conflict_rows: int
    movable_rows: int
    diff_rows: int
    merged_rows: int = 0
    moved_rows: int = 0
    deleted_rows: int = 0


def parse_date(value: str) -> date:
    raw = value.strip()
    if len(raw) == 8 and raw.isdigit():
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    return date.fromisoformat(raw)


def iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def validate_freqs(freqs: Sequence[str] | None) -> list[str]:
    values = list(freqs or []) or ["1d"]
    invalid = [freq for freq in values if freq not in DATE_FREQS]
    if invalid:
        raise ValueError(f"仅支持日/周/月级频率 {sorted(DATE_FREQS)}，不支持: {invalid}")
    return values


def _time_pair(trade_day: date) -> tuple[datetime, datetime]:
    target_time = datetime.combine(trade_day, time.min, tzinfo=timezone.utc)
    source_time = target_time - timedelta(hours=8)
    return source_time, target_time


def _freq_clause(freqs: Sequence[str]) -> tuple[str, dict[str, str]]:
    params = {f"freq_{idx}": freq for idx, freq in enumerate(freqs)}
    placeholders = ", ".join(f":freq_{idx}" for idx in range(len(freqs)))
    return placeholders, params


async def _set_statement_timeout(session, milliseconds: int) -> None:
    await session.execute(text(f"SET statement_timeout = {int(milliseconds)}"))
    await session.execute(text("SET TIME ZONE 'UTC'"))


async def _inspect_day(
    session,
    trade_day: date,
    freqs: Sequence[str],
    *,
    include_diff: bool = False,
) -> DayStats:
    source_time, target_time = _time_pair(trade_day)
    placeholders, freq_params = _freq_clause(freqs)
    params = {
        "source_time": source_time,
        "target_time": target_time,
        **freq_params,
    }

    candidate_rows = await session.scalar(text(f"""
        SELECT COUNT(*)
        FROM kline src
        WHERE src.time = :source_time
          AND src.freq IN ({placeholders})
    """), params)
    candidate_count = int(candidate_rows or 0)
    if candidate_count == 0:
        return DayStats(
            trade_date=trade_day,
            candidate_rows=0,
            conflict_rows=0,
            movable_rows=0,
            diff_rows=0,
        )

    conflict_rows = await session.scalar(text(f"""
        SELECT COUNT(*)
        FROM kline src
        WHERE src.time = :source_time
          AND src.freq IN ({placeholders})
          AND EXISTS (
            SELECT 1
            FROM kline dst
            WHERE dst.time = :target_time
              AND dst.symbol = src.symbol
              AND dst.freq = src.freq
              AND dst.adj_type = src.adj_type
          )
    """), params)
    conflict_count = int(conflict_rows or 0)

    diff_count = 0
    if include_diff and conflict_count:
        diff_rows = await session.scalar(text(f"""
            SELECT COUNT(*)
            FROM kline src
            JOIN kline dst
              ON dst.time = :target_time
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
            WHERE src.time = :source_time
              AND src.freq IN ({placeholders})
              AND (
                (src.open IS NOT NULL AND dst.open IS NOT NULL AND src.open IS DISTINCT FROM dst.open)
                OR (src.high IS NOT NULL AND dst.high IS NOT NULL AND src.high IS DISTINCT FROM dst.high)
                OR (src.low IS NOT NULL AND dst.low IS NOT NULL AND src.low IS DISTINCT FROM dst.low)
                OR (src.close IS NOT NULL AND dst.close IS NOT NULL AND src.close IS DISTINCT FROM dst.close)
                OR (src.volume IS NOT NULL AND dst.volume IS NOT NULL AND src.volume IS DISTINCT FROM dst.volume)
                OR (src.amount IS NOT NULL AND dst.amount IS NOT NULL AND src.amount IS DISTINCT FROM dst.amount)
              )
        """), params)
        diff_count = int(diff_rows or 0)

    return DayStats(
        trade_date=trade_day,
        candidate_rows=candidate_count,
        conflict_rows=conflict_count,
        movable_rows=candidate_count - conflict_count,
        diff_rows=diff_count,
    )


async def _ensure_backup_table(session, table_name: str) -> None:
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            LIKE kline INCLUDING DEFAULTS,
            target_time timestamptz,
            backup_created_at timestamptz DEFAULT now()
        )
    """))


async def _backup_day(session, table_name: str, trade_day: date, freqs: Sequence[str]) -> int:
    source_time, target_time = _time_pair(trade_day)
    placeholders, freq_params = _freq_clause(freqs)
    result = await session.execute(text(f"""
        INSERT INTO {table_name}
        SELECT src.*, :target_time AS target_time, now() AS backup_created_at
        FROM kline src
        WHERE src.time = :source_time
          AND src.freq IN ({placeholders})
    """), {
        "source_time": source_time,
        "target_time": target_time,
        **freq_params,
    })
    return int(result.rowcount or 0)


async def _repair_day(
    session,
    trade_day: date,
    freqs: Sequence[str],
    *,
    include_diff: bool = False,
) -> DayStats:
    before = await _inspect_day(session, trade_day, freqs, include_diff=include_diff)
    if before.candidate_rows == 0:
        return before

    source_time, target_time = _time_pair(trade_day)
    placeholders, freq_params = _freq_clause(freqs)
    params = {
        "source_time": source_time,
        "target_time": target_time,
        **freq_params,
    }

    await session.execute(text("DROP TABLE IF EXISTS tmp_kline_trade_date_candidates"))
    await session.execute(text("""
        CREATE TEMP TABLE tmp_kline_trade_date_candidates (
            symbol varchar(12) NOT NULL,
            freq varchar(5) NOT NULL,
            adj_type smallint NOT NULL,
            has_conflict boolean NOT NULL
        ) ON COMMIT DROP
    """))
    await session.execute(text(f"""
        INSERT INTO tmp_kline_trade_date_candidates (symbol, freq, adj_type, has_conflict)
        SELECT
          src.symbol,
          src.freq,
          src.adj_type,
          EXISTS (
            SELECT 1
            FROM kline dst
            WHERE dst.time = :target_time
              AND dst.symbol = src.symbol
              AND dst.freq = src.freq
              AND dst.adj_type = src.adj_type
          ) AS has_conflict
        FROM kline src
        WHERE src.time = :source_time
          AND src.freq IN ({placeholders})
    """), params)

    merge_result = await session.execute(text("""
        UPDATE kline dst
        SET
          open = COALESCE(dst.open, src.open),
          high = COALESCE(dst.high, src.high),
          low = COALESCE(dst.low, src.low),
          close = COALESCE(dst.close, src.close),
          volume = COALESCE(dst.volume, src.volume),
          amount = COALESCE(dst.amount, src.amount),
          turnover = COALESCE(dst.turnover, src.turnover),
          vol_ratio = COALESCE(dst.vol_ratio, src.vol_ratio),
          limit_up = COALESCE(dst.limit_up, src.limit_up),
          limit_down = COALESCE(dst.limit_down, src.limit_down)
        FROM tmp_kline_trade_date_candidates c
        JOIN kline src
          ON src.time = :source_time
         AND src.symbol = c.symbol
         AND src.freq = c.freq
         AND src.adj_type = c.adj_type
        WHERE c.has_conflict
          AND dst.time = :target_time
          AND dst.symbol = c.symbol
          AND dst.freq = c.freq
          AND dst.adj_type = c.adj_type
          AND (
            (dst.open IS NULL AND src.open IS NOT NULL)
            OR (dst.high IS NULL AND src.high IS NOT NULL)
            OR (dst.low IS NULL AND src.low IS NOT NULL)
            OR (dst.close IS NULL AND src.close IS NOT NULL)
            OR (dst.volume IS NULL AND src.volume IS NOT NULL)
            OR (dst.amount IS NULL AND src.amount IS NOT NULL)
            OR (dst.turnover IS NULL AND src.turnover IS NOT NULL)
            OR (dst.vol_ratio IS NULL AND src.vol_ratio IS NOT NULL)
            OR (dst.limit_up IS NULL AND src.limit_up IS NOT NULL)
            OR (dst.limit_down IS NULL AND src.limit_down IS NOT NULL)
          )
    """), params)

    delete_result = await session.execute(text("""
        DELETE FROM kline src
        USING tmp_kline_trade_date_candidates c
        WHERE c.has_conflict
          AND src.time = :source_time
          AND src.symbol = c.symbol
          AND src.freq = c.freq
          AND src.adj_type = c.adj_type
    """), params)

    move_insert_result = await session.execute(text("""
        INSERT INTO kline (
          time, symbol, freq, open, high, low, close, volume, amount,
          turnover, vol_ratio, limit_up, limit_down, adj_type
        )
        SELECT
          :target_time,
          src.symbol,
          src.freq,
          src.open,
          src.high,
          src.low,
          src.close,
          src.volume,
          src.amount,
          src.turnover,
          src.vol_ratio,
          src.limit_up,
          src.limit_down,
          src.adj_type
        FROM kline src
        JOIN tmp_kline_trade_date_candidates c
          ON src.time = :source_time
         AND src.symbol = c.symbol
         AND src.freq = c.freq
         AND src.adj_type = c.adj_type
        WHERE NOT c.has_conflict
        ON CONFLICT (time, symbol, freq, adj_type) DO NOTHING
    """), params)

    await session.execute(text("""
        DELETE FROM kline src
        USING tmp_kline_trade_date_candidates c
        WHERE NOT c.has_conflict
          AND src.time = :source_time
          AND src.symbol = c.symbol
          AND src.freq = c.freq
          AND src.adj_type = c.adj_type
          AND EXISTS (
            SELECT 1
            FROM kline dst
            WHERE dst.time = :target_time
              AND dst.symbol = src.symbol
              AND dst.freq = src.freq
              AND dst.adj_type = src.adj_type
          )
    """), params)

    return DayStats(
        trade_date=trade_day,
        candidate_rows=before.candidate_rows,
        conflict_rows=before.conflict_rows,
        movable_rows=before.movable_rows,
        diff_rows=before.diff_rows,
        merged_rows=int(merge_result.rowcount or 0),
        moved_rows=int(move_insert_result.rowcount or 0),
        deleted_rows=int(delete_result.rowcount or 0),
    )


async def run(args: argparse.Namespace) -> int:
    freqs = validate_freqs(args.freq)
    if args.start_date > args.end_date:
        raise ValueError("start-date 不能晚于 end-date")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_table = args.backup_table or (
        f"duplicate_backup_kline_exact_{args.start_date:%Y%m%d}_{args.end_date:%Y%m%d}_{stamp}"
    )

    totals = {
        "candidate_rows": 0,
        "conflict_rows": 0,
        "movable_rows": 0,
        "diff_rows": 0,
        "merged_rows": 0,
        "moved_rows": 0,
        "deleted_rows": 0,
        "backup_rows": 0,
    }
    touched_days = 0

    async with AsyncSessionTS() as session:
        await _set_statement_timeout(session, args.statement_timeout_ms)
        if args.execute:
            await _ensure_backup_table(session, backup_table)
            await session.commit()
            print(f"备份表: {backup_table}")

        for trade_day in iter_dates(args.start_date, args.end_date):
            if args.execute:
                before = await _inspect_day(session, trade_day, freqs, include_diff=args.with_diff)
                if before.candidate_rows:
                    backup_rows = await _backup_day(session, backup_table, trade_day, freqs)
                    stats = await _repair_day(
                        session,
                        trade_day,
                        freqs,
                        include_diff=args.with_diff,
                    )
                    await session.commit()
                    totals["backup_rows"] += backup_rows
                else:
                    stats = before
            else:
                stats = await _inspect_day(session, trade_day, freqs, include_diff=args.with_diff)

            for key in (
                "candidate_rows",
                "conflict_rows",
                "movable_rows",
                "diff_rows",
                "merged_rows",
                "moved_rows",
                "deleted_rows",
            ):
                totals[key] += getattr(stats, key)

            if stats.candidate_rows or stats.conflict_rows or stats.moved_rows or stats.deleted_rows:
                touched_days += 1
                print(
                    f"{trade_day}: candidates={stats.candidate_rows}, "
                    f"conflicts={stats.conflict_rows}, movable={stats.movable_rows}, "
                    f"diffs={stats.diff_rows}, merged={stats.merged_rows}, "
                    f"moved={stats.moved_rows}, deleted={stats.deleted_rows}"
                )

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(
        f"[{mode}] days={touched_days}, candidates={totals['candidate_rows']}, "
        f"conflicts={totals['conflict_rows']}, movable={totals['movable_rows']}, "
        f"diffs={totals['diff_rows']}, merged={totals['merged_rows']}, "
        f"moved={totals['moved_rows']}, deleted={totals['deleted_rows']}, "
        f"backup={totals['backup_rows']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, type=parse_date)
    parser.add_argument("--end-date", required=True, type=parse_date)
    parser.add_argument("--freq", action="append", help="可重复传入，默认 1d")
    parser.add_argument("--execute", action="store_true", help="实际写库；默认 dry-run")
    parser.add_argument("--backup-table", help="自定义备份表名，仅 execute 使用")
    parser.add_argument("--statement-timeout-ms", type=int, default=15000)
    parser.add_argument("--with-diff", action="store_true", help="额外统计 OHLCV 差异，较慢")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
