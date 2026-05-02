#!/usr/bin/env python
"""修复 Tushare 时序行情日级时间戳 16:00 偏移。

默认 dry-run，仅输出候选、冲突、可移动行数和样例；传入 --execute 才写库。
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import text

from app.core.database import AsyncSessionTS


DATE_FREQS = {"1d", "1w", "1M"}


@dataclass(frozen=True)
class RepairBatch:
    start_date: date
    end_date: date


def parse_repair_date(value: str) -> date:
    """解析 YYYYMMDD 或 YYYY-MM-DD 日期。"""
    raw = value.strip()
    if len(raw) == 8 and raw.isdigit():
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    if len(raw) == 10 and "-" in raw:
        return date.fromisoformat(raw)
    raise argparse.ArgumentTypeError(f"无效日期: {value}，应为 YYYYMMDD 或 YYYY-MM-DD")


def split_date_batches(start_date: date, end_date: date, batch_days: int) -> list[RepairBatch]:
    """将闭区间日期拆成小批次。"""
    if start_date > end_date:
        raise ValueError("start-date 不能晚于 end-date")
    if batch_days <= 0:
        raise ValueError("batch-days 必须大于 0")

    batches: list[RepairBatch] = []
    current = start_date
    while current <= end_date:
        batch_end = min(current + timedelta(days=batch_days - 1), end_date)
        batches.append(RepairBatch(current, batch_end))
        current = batch_end + timedelta(days=1)
    return batches


def validate_freqs(freqs: Sequence[str] | None) -> list[str]:
    """仅允许日/周/月级频率参与历史偏移修复。"""
    values = list(freqs or []) or ["1d"]
    invalid = [freq for freq in values if freq not in DATE_FREQS]
    if invalid:
        raise ValueError(f"历史偏移修复仅支持 {sorted(DATE_FREQS)}，不支持: {invalid}")
    return values


def _freq_clause(freqs: Sequence[str]) -> tuple[str, dict[str, str]]:
    params = {f"freq_{idx}": freq for idx, freq in enumerate(freqs)}
    placeholders = ", ".join(f":freq_{idx}" for idx in range(len(freqs)))
    return placeholders, params


def _base_params(batch: RepairBatch, freqs: Sequence[str]) -> dict[str, object]:
    _, freq_params = _freq_clause(freqs)
    return {
        "start_date": batch.start_date,
        "end_next": batch.end_date + timedelta(days=1),
        **freq_params,
    }


def build_dry_run_sql(table: str, freqs: Sequence[str]) -> dict[str, str]:
    """构建 dry-run 查询 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        from_clause = "FROM kline src"
        join = """
            LEFT JOIN kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
        """
        where_clause = f"""
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
        """
        conflict_predicate = "dst.symbol IS NOT NULL"
        sample_cols = (
            "src.time AS stored_time, src.time + interval '8 hours' AS target_time, "
            "src.symbol, src.freq, src.adj_type"
        )
    elif table == "sector_kline":
        from_clause = "FROM sector_kline src"
        join = """
            LEFT JOIN sector_kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.sector_code = src.sector_code
             AND dst.data_source = src.data_source
             AND dst.freq = src.freq
        """
        where_clause = f"""
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
        """
        conflict_predicate = "dst.sector_code IS NOT NULL"
        sample_cols = (
            "src.time AS stored_time, src.time + interval '8 hours' AS target_time, "
            "src.sector_code, src.data_source, src.freq"
        )
    else:
        raise ValueError(f"不支持的表: {table}")

    return {
        "summary": f"""
            SELECT
              COUNT(*) AS candidate_rows,
              COUNT(*) FILTER (WHERE {conflict_predicate}) AS conflict_rows,
              COUNT(*) FILTER (WHERE NOT ({conflict_predicate})) AS movable_rows
            {from_clause}
            {join}
            {where_clause}
        """,
        "samples": f"""
            SELECT {sample_cols},
                   CASE WHEN {conflict_predicate} THEN true ELSE false END AS has_conflict
            {from_clause}
            {join}
            {where_clause}
            ORDER BY src.time DESC
            LIMIT 10
        """,
    }


def build_target_distribution_sql(table: str, freqs: Sequence[str]) -> str:
    """构建按目标交易日统计 16:00 UTC 候选分布的 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            SELECT
              date((src.time + interval '8 hours') at time zone 'UTC') AS target_date,
              COUNT(*) AS candidate_rows,
              COUNT(*) FILTER (WHERE dst.symbol IS NOT NULL) AS conflict_rows,
              COUNT(*) FILTER (WHERE dst.symbol IS NULL) AS movable_rows
            FROM kline src
            LEFT JOIN kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
            GROUP BY 1
            ORDER BY 1
        """
    if table == "sector_kline":
        return f"""
            SELECT
              date(src.time + interval '8 hours') AS target_date,
              COUNT(*) AS candidate_rows,
              COUNT(*) FILTER (WHERE dst.sector_code IS NOT NULL) AS conflict_rows,
              COUNT(*) FILTER (WHERE dst.sector_code IS NULL) AS movable_rows
            FROM sector_kline src
            LEFT JOIN sector_kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.sector_code = src.sector_code
             AND dst.data_source = src.data_source
             AND dst.freq = src.freq
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
            GROUP BY 1
            ORDER BY 1
        """
    raise ValueError(f"不支持的表: {table}")


def build_local_duplicate_sql(table: str, freqs: Sequence[str]) -> str:
    """构建同一本地交易日重复记录统计 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            SELECT
              COUNT(*) AS duplicate_groups,
              COALESCE(SUM(rows - 1), 0) AS duplicate_extra_rows
            FROM (
              SELECT
                src.symbol,
                src.freq,
                src.adj_type,
                date(src.time at time zone 'Asia/Shanghai') AS local_trade_date,
                COUNT(*) AS rows
              FROM kline src
              WHERE src.freq IN ({placeholders})
                AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
                AND src.time < CAST(:end_next AS timestamp)
              GROUP BY src.symbol, src.freq, src.adj_type,
                       date(src.time at time zone 'Asia/Shanghai')
              HAVING COUNT(*) > 1
            ) dup
        """
    if table == "sector_kline":
        return f"""
            SELECT
              COUNT(*) AS duplicate_groups,
              COALESCE(SUM(rows - 1), 0) AS duplicate_extra_rows
            FROM (
              SELECT
                src.sector_code,
                src.data_source,
                src.freq,
                date(src.time) AS local_trade_date,
                COUNT(*) AS rows
              FROM sector_kline src
              WHERE src.freq IN ({placeholders})
                AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
                AND src.time < CAST(:end_next AS timestamp)
              GROUP BY src.sector_code, src.data_source, src.freq, date(src.time)
              HAVING COUNT(*) > 1
            ) dup
        """
    raise ValueError(f"不支持的表: {table}")


def build_local_duplicate_samples_sql(table: str, freqs: Sequence[str]) -> str:
    """构建同一本地交易日重复记录样例 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            SELECT
              src.symbol,
              src.freq,
              src.adj_type,
              date(src.time at time zone 'Asia/Shanghai') AS local_trade_date,
              COUNT(*) AS rows,
              MIN(src.time) AS min_time,
              MAX(src.time) AS max_time
            FROM kline src
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp)
            GROUP BY src.symbol, src.freq, src.adj_type,
                     date(src.time at time zone 'Asia/Shanghai')
            HAVING COUNT(*) > 1
            ORDER BY local_trade_date DESC, src.symbol
            LIMIT 10
        """
    if table == "sector_kline":
        return f"""
            SELECT
              src.sector_code,
              src.data_source,
              src.freq,
              date(src.time) AS local_trade_date,
              COUNT(*) AS rows,
              MIN(src.time) AS min_time,
              MAX(src.time) AS max_time
            FROM sector_kline src
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp)
            GROUP BY src.sector_code, src.data_source, src.freq, date(src.time)
            HAVING COUNT(*) > 1
            ORDER BY local_trade_date DESC, src.sector_code
            LIMIT 10
        """
    raise ValueError(f"不支持的表: {table}")


def build_ohlcv_diff_sql(table: str, freqs: Sequence[str]) -> dict[str, str]:
    """构建冲突记录 OHLCV 差异诊断 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        base = f"""
            FROM kline src
            JOIN kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
              AND (
                (src.open IS NOT NULL AND dst.open IS NOT NULL AND src.open IS DISTINCT FROM dst.open)
                OR (src.high IS NOT NULL AND dst.high IS NOT NULL AND src.high IS DISTINCT FROM dst.high)
                OR (src.low IS NOT NULL AND dst.low IS NOT NULL AND src.low IS DISTINCT FROM dst.low)
                OR (src.close IS NOT NULL AND dst.close IS NOT NULL AND src.close IS DISTINCT FROM dst.close)
                OR (src.volume IS NOT NULL AND dst.volume IS NOT NULL AND src.volume IS DISTINCT FROM dst.volume)
                OR (src.amount IS NOT NULL AND dst.amount IS NOT NULL AND src.amount IS DISTINCT FROM dst.amount)
              )
        """
        return {
            "summary": f"SELECT COUNT(*) AS diff_rows {base}",
            "samples": f"""
                SELECT
                  src.time AS stored_time,
                  dst.time AS target_time,
                  src.symbol,
                  src.freq,
                  src.adj_type,
                  src.open AS src_open,
                  dst.open AS dst_open,
                  src.close AS src_close,
                  dst.close AS dst_close,
                  src.volume AS src_volume,
                  dst.volume AS dst_volume
                {base}
                ORDER BY src.time DESC, src.symbol
                LIMIT 10
            """,
        }
    if table == "sector_kline":
        base = f"""
            FROM sector_kline src
            JOIN sector_kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.sector_code = src.sector_code
             AND dst.data_source = src.data_source
             AND dst.freq = src.freq
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
              AND (
                (src.open IS NOT NULL AND dst.open IS NOT NULL AND src.open IS DISTINCT FROM dst.open)
                OR (src.high IS NOT NULL AND dst.high IS NOT NULL AND src.high IS DISTINCT FROM dst.high)
                OR (src.low IS NOT NULL AND dst.low IS NOT NULL AND src.low IS DISTINCT FROM dst.low)
                OR (src.close IS NOT NULL AND dst.close IS NOT NULL AND src.close IS DISTINCT FROM dst.close)
                OR (src.volume IS NOT NULL AND dst.volume IS NOT NULL AND src.volume IS DISTINCT FROM dst.volume)
                OR (src.amount IS NOT NULL AND dst.amount IS NOT NULL AND src.amount IS DISTINCT FROM dst.amount)
              )
        """
        return {
            "summary": f"SELECT COUNT(*) AS diff_rows {base}",
            "samples": f"""
                SELECT
                  src.time AS stored_time,
                  dst.time AS target_time,
                  src.sector_code,
                  src.data_source,
                  src.freq,
                  src.open AS src_open,
                  dst.open AS dst_open,
                  src.close AS src_close,
                  dst.close AS dst_close,
                  src.volume AS src_volume,
                  dst.volume AS dst_volume
                {base}
                ORDER BY src.time DESC, src.sector_code
                LIMIT 10
            """,
        }
    raise ValueError(f"不支持的表: {table}")


def build_execute_sql(table: str, freqs: Sequence[str]) -> str:
    """构建执行修复 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            WITH candidates AS MATERIALIZED (
                SELECT
                  src.time,
                  src.time + interval '8 hours' AS target_time,
                  src.symbol,
                  src.freq,
                  src.adj_type
                FROM kline src
                WHERE src.freq IN ({placeholders})
                  AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
                  AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
                  AND extract(hour from src.time at time zone 'UTC') = 16
            ),
            conflicts AS MATERIALIZED (
                SELECT c.*
                FROM candidates c
                JOIN kline dst
                  ON dst.time = c.target_time
                 AND dst.symbol = c.symbol
                 AND dst.freq = c.freq
                 AND dst.adj_type = c.adj_type
            ),
            merged AS (
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
                FROM conflicts c
                JOIN kline src
                  ON src.time = c.time
                 AND src.symbol = c.symbol
                 AND src.freq = c.freq
                 AND src.adj_type = c.adj_type
                WHERE dst.time = c.target_time
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
                RETURNING src.time, src.symbol, src.freq, src.adj_type
            ),
            deleted AS (
                DELETE FROM kline k
                USING conflicts c
                WHERE k.time = c.time
                  AND k.symbol = c.symbol
                  AND k.freq = c.freq
                  AND k.adj_type = c.adj_type
                RETURNING 1
            ),
            moved AS (
                UPDATE kline k
                SET time = k.time + interval '8 hours'
                FROM candidates c
                WHERE k.time = c.time
                  AND k.symbol = c.symbol
                  AND k.freq = c.freq
                  AND k.adj_type = c.adj_type
                  AND NOT EXISTS (
                    SELECT 1
                    FROM conflicts x
                    WHERE x.time = c.time
                      AND x.symbol = c.symbol
                      AND x.freq = c.freq
                      AND x.adj_type = c.adj_type
                  )
                RETURNING 1
            )
            SELECT
              (SELECT COUNT(*) FROM candidates) AS candidate_rows,
              (SELECT COUNT(*) FROM conflicts) AS conflict_rows,
              (SELECT COUNT(*) FROM merged) AS merged_rows,
              (SELECT COUNT(*) FROM moved) AS moved_rows,
              (SELECT COUNT(*) FROM deleted) AS deleted_rows
        """
    if table == "sector_kline":
        return f"""
            WITH candidates AS MATERIALIZED (
                SELECT
                  src.time,
                  src.time + interval '8 hours' AS target_time,
                  src.sector_code,
                  src.data_source,
                  src.freq
                FROM sector_kline src
                WHERE src.freq IN ({placeholders})
                  AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
                  AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
                  AND extract(hour from src.time) = 16
            ),
            conflicts AS MATERIALIZED (
                SELECT c.*
                FROM candidates c
                JOIN sector_kline dst
                  ON dst.time = c.target_time
                 AND dst.sector_code = c.sector_code
                 AND dst.data_source = c.data_source
                 AND dst.freq = c.freq
            ),
            merged AS (
                UPDATE sector_kline dst
                SET
                  open = COALESCE(dst.open, src.open),
                  high = COALESCE(dst.high, src.high),
                  low = COALESCE(dst.low, src.low),
                  close = COALESCE(dst.close, src.close),
                  volume = COALESCE(dst.volume, src.volume),
                  amount = COALESCE(dst.amount, src.amount),
                  turnover = COALESCE(dst.turnover, src.turnover),
                  change_pct = COALESCE(dst.change_pct, src.change_pct)
                FROM conflicts c
                JOIN sector_kline src
                  ON src.time = c.time
                 AND src.sector_code = c.sector_code
                 AND src.data_source = c.data_source
                 AND src.freq = c.freq
                WHERE dst.time = c.target_time
                  AND dst.sector_code = c.sector_code
                  AND dst.data_source = c.data_source
                  AND dst.freq = c.freq
                  AND (
                    (dst.open IS NULL AND src.open IS NOT NULL)
                    OR (dst.high IS NULL AND src.high IS NOT NULL)
                    OR (dst.low IS NULL AND src.low IS NOT NULL)
                    OR (dst.close IS NULL AND src.close IS NOT NULL)
                    OR (dst.volume IS NULL AND src.volume IS NOT NULL)
                    OR (dst.amount IS NULL AND src.amount IS NOT NULL)
                    OR (dst.turnover IS NULL AND src.turnover IS NOT NULL)
                    OR (dst.change_pct IS NULL AND src.change_pct IS NOT NULL)
                  )
                RETURNING src.time, src.sector_code, src.data_source, src.freq
            ),
            deleted AS (
                DELETE FROM sector_kline k
                USING conflicts c
                WHERE k.time = c.time
                  AND k.sector_code = c.sector_code
                  AND k.data_source = c.data_source
                  AND k.freq = c.freq
                RETURNING 1
            ),
            moved AS (
                UPDATE sector_kline k
                SET time = k.time + interval '8 hours'
                FROM candidates c
                WHERE k.time = c.time
                  AND k.sector_code = c.sector_code
                  AND k.data_source = c.data_source
                  AND k.freq = c.freq
                  AND NOT EXISTS (
                    SELECT 1
                    FROM conflicts x
                    WHERE x.time = c.time
                      AND x.sector_code = c.sector_code
                      AND x.data_source = c.data_source
                      AND x.freq = c.freq
                  )
                RETURNING 1
            )
            SELECT
              (SELECT COUNT(*) FROM candidates) AS candidate_rows,
              (SELECT COUNT(*) FROM conflicts) AS conflict_rows,
              (SELECT COUNT(*) FROM merged) AS merged_rows,
              (SELECT COUNT(*) FROM moved) AS moved_rows,
              (SELECT COUNT(*) FROM deleted) AS deleted_rows
        """
    raise ValueError(f"不支持的表: {table}")


def build_move_only_sql(table: str, freqs: Sequence[str]) -> str:
    """构建无冲突候选的轻量移动 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            UPDATE kline src
            SET time = src.time + interval '8 hours'
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
              AND NOT EXISTS (
                SELECT 1
                FROM kline dst
                WHERE dst.time = src.time + interval '8 hours'
                  AND dst.symbol = src.symbol
                  AND dst.freq = src.freq
                  AND dst.adj_type = src.adj_type
              )
        """
    if table == "sector_kline":
        return f"""
            UPDATE sector_kline src
            SET time = src.time + interval '8 hours'
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
              AND NOT EXISTS (
                SELECT 1
                FROM sector_kline dst
                WHERE dst.time = src.time + interval '8 hours'
                  AND dst.sector_code = src.sector_code
                  AND dst.data_source = src.data_source
                  AND dst.freq = src.freq
              )
        """
    raise ValueError(f"不支持的表: {table}")


def build_fill_needed_sql(table: str, freqs: Sequence[str]) -> str:
    """构建冲突记录是否需要补空字段的统计 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            SELECT COUNT(*) AS need_fill_rows
            FROM kline src
            JOIN kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
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
        """
    if table == "sector_kline":
        return f"""
            SELECT COUNT(*) AS need_fill_rows
            FROM sector_kline src
            JOIN sector_kline dst
              ON dst.time = src.time + interval '8 hours'
             AND dst.sector_code = src.sector_code
             AND dst.data_source = src.data_source
             AND dst.freq = src.freq
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
              AND (
                (dst.open IS NULL AND src.open IS NOT NULL)
                OR (dst.high IS NULL AND src.high IS NOT NULL)
                OR (dst.low IS NULL AND src.low IS NOT NULL)
                OR (dst.close IS NULL AND src.close IS NOT NULL)
                OR (dst.volume IS NULL AND src.volume IS NOT NULL)
                OR (dst.amount IS NULL AND src.amount IS NOT NULL)
                OR (dst.turnover IS NULL AND src.turnover IS NOT NULL)
                OR (dst.change_pct IS NULL AND src.change_pct IS NOT NULL)
              )
        """
    raise ValueError(f"不支持的表: {table}")


def build_delete_conflicts_only_sql(table: str, freqs: Sequence[str]) -> str:
    """构建无需补字段时删除冲突偏移记录的轻量 SQL。"""
    placeholders, _ = _freq_clause(freqs)
    if table == "kline":
        return f"""
            DELETE FROM kline src
            USING kline dst
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time at time zone 'UTC') = 16
              AND dst.time = src.time + interval '8 hours'
              AND dst.symbol = src.symbol
              AND dst.freq = src.freq
              AND dst.adj_type = src.adj_type
        """
    if table == "sector_kline":
        return f"""
            DELETE FROM sector_kline src
            USING sector_kline dst
            WHERE src.freq IN ({placeholders})
              AND src.time >= CAST(:start_date AS timestamp) - interval '8 hours'
              AND src.time < CAST(:end_next AS timestamp) - interval '8 hours'
              AND extract(hour from src.time) = 16
              AND dst.time = src.time + interval '8 hours'
              AND dst.sector_code = src.sector_code
              AND dst.data_source = src.data_source
              AND dst.freq = src.freq
        """
    raise ValueError(f"不支持的表: {table}")


async def dry_run(table: str, batches: Sequence[RepairBatch], freqs: Sequence[str]) -> None:
    sqls = build_dry_run_sql(table, freqs)
    distribution_sql = build_target_distribution_sql(table, freqs)
    duplicate_sql = build_local_duplicate_sql(table, freqs)
    duplicate_samples_sql = build_local_duplicate_samples_sql(table, freqs)
    diff_sqls = build_ohlcv_diff_sql(table, freqs)
    async with AsyncSessionTS() as session:
        for batch in batches:
            params = _base_params(batch, freqs)
            summary = (
                await session.execute(text(sqls["summary"]), params)
            ).mappings().one()
            print(
                f"[dry-run] {table} {batch.start_date}~{batch.end_date} "
                f"candidates={summary['candidate_rows']} "
                f"conflicts={summary['conflict_rows']} "
                f"movable={summary['movable_rows']}"
            )
            samples = (
                await session.execute(text(sqls["samples"]), params)
            ).mappings().all()
            for sample in samples:
                print("  sample", dict(sample))

            distribution = (
                await session.execute(text(distribution_sql), params)
            ).mappings().all()
            for row in distribution:
                print("  target_distribution", dict(row))

            duplicates = (
                await session.execute(text(duplicate_sql), params)
            ).mappings().one()
            print(
                f"  local_duplicates groups={duplicates['duplicate_groups']} "
                f"extra_rows={duplicates['duplicate_extra_rows']}"
            )
            duplicate_samples = (
                await session.execute(text(duplicate_samples_sql), params)
            ).mappings().all()
            for sample in duplicate_samples:
                print("  duplicate_sample", dict(sample))

            diff_summary = (
                await session.execute(text(diff_sqls["summary"]), params)
            ).mappings().one()
            print(f"  ohlcv_conflict_diffs rows={diff_summary['diff_rows']}")
            diff_samples = (
                await session.execute(text(diff_sqls["samples"]), params)
            ).mappings().all()
            for sample in diff_samples:
                print("  ohlcv_diff_sample", dict(sample))


async def execute_repair(table: str, batches: Sequence[RepairBatch], freqs: Sequence[str]) -> None:
    sql = build_execute_sql(table, freqs)
    move_only_sql = build_move_only_sql(table, freqs)
    fill_needed_sql = build_fill_needed_sql(table, freqs)
    delete_conflicts_only_sql = build_delete_conflicts_only_sql(table, freqs)
    dry_run_sql = build_dry_run_sql(table, freqs)["summary"]
    async with AsyncSessionTS() as session:
        for batch in batches:
            params = _base_params(batch, freqs)
            try:
                before = (
                    await session.execute(text(dry_run_sql), params)
                ).mappings().one()
                if int(before["candidate_rows"] or 0) == 0:
                    result = {
                        "candidate_rows": 0,
                        "conflict_rows": 0,
                        "merged_rows": 0,
                        "moved_rows": 0,
                        "deleted_rows": 0,
                    }
                elif int(before["conflict_rows"] or 0) == 0:
                    move_result = await session.execute(text(move_only_sql), params)
                    result = {
                        "candidate_rows": before["candidate_rows"],
                        "conflict_rows": 0,
                        "merged_rows": 0,
                        "moved_rows": move_result.rowcount,
                        "deleted_rows": 0,
                    }
                elif int(before["candidate_rows"] or 0) == int(before["conflict_rows"] or 0):
                    need_fill = (
                        await session.execute(text(fill_needed_sql), params)
                    ).mappings().one()
                    if int(need_fill["need_fill_rows"] or 0) == 0:
                        delete_result = await session.execute(
                            text(delete_conflicts_only_sql), params,
                        )
                        result = {
                            "candidate_rows": before["candidate_rows"],
                            "conflict_rows": before["conflict_rows"],
                            "merged_rows": 0,
                            "moved_rows": 0,
                            "deleted_rows": delete_result.rowcount,
                        }
                    else:
                        result = (await session.execute(text(sql), params)).mappings().one()
                else:
                    result = (await session.execute(text(sql), params)).mappings().one()
                await session.commit()
                remaining = (
                    await session.execute(text(dry_run_sql), params)
                ).mappings().one()
            except Exception:
                await session.rollback()
                raise
            print(
                f"[execute] {table} {batch.start_date}~{batch.end_date} "
                f"candidates={result['candidate_rows']} "
                f"conflicts={result['conflict_rows']} "
                f"merged={result.get('merged_rows', 0)} "
                f"moved={result['moved_rows']} "
                f"deleted={result['deleted_rows']}"
            )
            print(
                f"[verify] {table} {batch.start_date}~{batch.end_date} "
                f"remaining_candidates={remaining['candidate_rows']} "
                f"remaining_conflicts={remaining['conflict_rows']}"
            )


def print_post_repair_guidance(table: str, start_date: date, end_date: date) -> None:
    """输出校正后的验证和补跑建议。"""
    if table != "kline":
        return
    print(
        "覆盖率验证 SQL：\n"
        "select time::date as trade_date,\n"
        "       count(*) as stock_kline_rows,\n"
        "       count(turnover) as turnover_rows,\n"
        "       count(vol_ratio) as vol_ratio_rows,\n"
        "       count(limit_up) as limit_up_rows,\n"
        "       count(limit_down) as limit_down_rows\n"
        "from kline\n"
        "where freq = '1d'\n"
        "  and adj_type = 0\n"
        f"  and time >= timestamp '{start_date.isoformat()}'\n"
        f"  and time < timestamp '{(end_date + timedelta(days=1)).isoformat()}'\n"
        "group by time::date\n"
        "order by time::date;"
    )
    print("补跑建议：先重跑 daily_basic 对应日期范围，再重跑 stk_limit 或调用 backfill_stk_limit_table。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", choices=["kline", "sector_kline"], required=True)
    parser.add_argument("--start-date", type=parse_repair_date, required=True)
    parser.add_argument("--end-date", type=parse_repair_date, required=True)
    parser.add_argument("--freq", action="append", default=None, help="可重复传入，默认 1d")
    parser.add_argument("--batch-days", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="演练模式，默认行为")
    parser.add_argument("--execute", action="store_true", help="执行写库修复")
    parser.add_argument(
        "--repair-kline-aux",
        action="store_true",
        help="仅输出补跑提示；daily_basic 需重跑导入，stk_limit 可补跑回填",
    )
    return parser


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        freqs = validate_freqs(args.freq)
        batches = split_date_batches(args.start_date, args.end_date, args.batch_days)
    except ValueError as exc:
        parser.error(str(exc))

    if args.execute:
        await execute_repair(args.table, batches, freqs)
    else:
        await dry_run(args.table, batches, freqs)

    if args.execute or args.repair_kline_aux:
        print_post_repair_guidance(args.table, args.start_date, args.end_date)
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
