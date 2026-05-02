"""K 线辅助字段回填服务。

将 Tushare daily_basic / stk_limit 的辅助行情字段批量回填到 TimescaleDB kline。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.symbol_utils import is_standard, to_standard
from app.models.tushare_import import StkLimit

logger = logging.getLogger(__name__)

_KLINE_AUX_BACKFILL_LOCK_KEY = 2026043001
_BACKFILL_MAX_RETRIES = 3
_BACKFILL_RETRY_BASE_DELAY = 0.5


@dataclass
class BackfillStats:
    """K 线辅助字段回填统计。"""

    source_table: str
    start_date: str | None
    end_date: str | None
    source_rows: int = 0
    matched_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    retry_count: int = 0
    failed_batches: int = 0


class KlineAuxFieldBackfillService:
    """批量回填 kline.turnover/vol_ratio/limit_up/limit_down。"""

    def __init__(
        self,
        pg_session: AsyncSession | None = None,
        ts_session: AsyncSession | None = None,
        batch_size: int = 500,
    ) -> None:
        self._pg_session = pg_session
        self._ts_session = ts_session
        self._batch_size = batch_size

    async def backfill_daily_basic_rows(self, rows: list[dict[str, Any]]) -> BackfillStats:
        """用 daily_basic 导入 rows 回填 kline.turnover / kline.vol_ratio。"""
        values = []
        for row in rows:
            symbol = self._normalize_symbol(row.get("symbol") or row.get("ts_code"))
            trade_date = self._normalize_trade_date(row.get("trade_date"))
            if symbol is None or trade_date is None:
                continue
            turnover = row.get("turnover_rate")
            vol_ratio = row.get("volume_ratio")
            if turnover is None and vol_ratio is None:
                continue
            values.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "turnover": self._to_numeric_param(turnover),
                    "vol_ratio": self._to_numeric_param(vol_ratio),
                }
            )

        stats = BackfillStats(
            source_table="daily_basic",
            start_date=self._min_date(values),
            end_date=self._max_date(values),
            source_rows=len(rows),
        )
        if not values:
            stats.skipped_rows = len(rows)
            return stats

        for batch in self._chunks(values):
            matched, updated, retries = await self._update_daily_basic_batch(batch)
            stats.matched_rows += matched
            stats.updated_rows += updated
            stats.retry_count += retries
        stats.skipped_rows = max(0, stats.source_rows - stats.matched_rows)
        return stats

    async def backfill_stk_limit_rows(self, rows: list[dict[str, Any]]) -> BackfillStats:
        """用 stk_limit 导入 rows 回填 kline.limit_up / kline.limit_down。"""
        values = []
        for row in rows:
            symbol = self._normalize_symbol(row.get("symbol") or row.get("ts_code"))
            trade_date = self._normalize_trade_date(row.get("trade_date"))
            if symbol is None or trade_date is None:
                continue
            limit_up = row.get("limit_up", row.get("up_limit"))
            limit_down = row.get("limit_down", row.get("down_limit"))
            if limit_up is None and limit_down is None:
                continue
            values.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "limit_up": self._to_numeric_param(limit_up),
                    "limit_down": self._to_numeric_param(limit_down),
                }
            )

        stats = BackfillStats(
            source_table="stk_limit",
            start_date=self._min_date(values),
            end_date=self._max_date(values),
            source_rows=len(rows),
        )
        if not values:
            stats.skipped_rows = len(rows)
            return stats

        for batch in self._chunks(values):
            matched, updated, retries = await self._update_stk_limit_batch(batch)
            stats.matched_rows += matched
            stats.updated_rows += updated
            stats.retry_count += retries
        stats.skipped_rows = max(0, stats.source_rows - stats.matched_rows)
        return stats

    async def backfill_stk_limit_table(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> BackfillStats:
        """从 PostgreSQL stk_limit 历史表按日期范围补跑到 kline。"""
        stmt = select(StkLimit)
        if start_date:
            stmt = stmt.where(StkLimit.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(StkLimit.trade_date <= end_date)
        stmt = stmt.order_by(StkLimit.trade_date.asc())

        if self._pg_session is not None:
            res = await self._pg_session.execute(stmt)
            records = list(res.scalars().all())
        else:
            async with AsyncSessionPG() as session:
                res = await session.execute(stmt)
                records = list(res.scalars().all())

        rows = [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date,
                "up_limit": r.up_limit,
                "down_limit": r.down_limit,
            }
            for r in records
        ]
        stats = await self.backfill_stk_limit_rows(rows)
        stats.start_date = start_date or stats.start_date
        stats.end_date = end_date or stats.end_date
        return stats

    async def _update_daily_basic_batch(self, values: list[dict[str, Any]]) -> tuple[int, int, int]:
        value_sql, params = self._build_values_sql(
            values, ("symbol", "trade_date", "turnover", "vol_ratio")
        )
        sql = text(f"""
            WITH v(symbol, trade_date, turnover, vol_ratio) AS (
                VALUES {value_sql}
            ),
            matched AS (
                SELECT COUNT(*) AS c
                FROM kline AS k
                JOIN v ON k.symbol::text = v.symbol::text
                  AND k.time >= CAST(v.trade_date AS date)
                  AND k.time < CAST(v.trade_date AS date) + INTERVAL '1 day'
                  AND k.freq = '1d'
                  AND k.adj_type = 0
            ),
            updated AS (
                UPDATE kline AS k
                SET
                  turnover = COALESCE(CAST(v.turnover AS numeric), k.turnover),
                  vol_ratio = COALESCE(CAST(v.vol_ratio AS numeric), k.vol_ratio)
                FROM v
                WHERE k.symbol::text = v.symbol::text
                  AND k.time >= CAST(v.trade_date AS date)
                  AND k.time < CAST(v.trade_date AS date) + INTERVAL '1 day'
                  AND k.freq = '1d'
                  AND k.adj_type = 0
                  AND (
                    (v.turnover IS NOT NULL AND k.turnover IS DISTINCT FROM CAST(v.turnover AS numeric))
                    OR (v.vol_ratio IS NOT NULL AND k.vol_ratio IS DISTINCT FROM CAST(v.vol_ratio AS numeric))
                  )
                RETURNING 1
            )
            SELECT (SELECT c FROM matched) AS matched_rows,
                   (SELECT COUNT(*) FROM updated) AS updated_rows
        """)
        return await self._execute_stats_sql(sql, params)

    async def _update_stk_limit_batch(self, values: list[dict[str, Any]]) -> tuple[int, int, int]:
        value_sql, params = self._build_values_sql(
            values, ("symbol", "trade_date", "limit_up", "limit_down")
        )
        sql = text(f"""
            WITH v(symbol, trade_date, limit_up, limit_down) AS (
                VALUES {value_sql}
            ),
            matched AS (
                SELECT COUNT(*) AS c
                FROM kline AS k
                JOIN v ON k.symbol::text = v.symbol::text
                  AND k.time >= CAST(v.trade_date AS date)
                  AND k.time < CAST(v.trade_date AS date) + INTERVAL '1 day'
                  AND k.freq = '1d'
                  AND k.adj_type = 0
            ),
            updated AS (
                UPDATE kline AS k
                SET
                  limit_up = COALESCE(CAST(v.limit_up AS numeric), k.limit_up),
                  limit_down = COALESCE(CAST(v.limit_down AS numeric), k.limit_down)
                FROM v
                WHERE k.symbol::text = v.symbol::text
                  AND k.time >= CAST(v.trade_date AS date)
                  AND k.time < CAST(v.trade_date AS date) + INTERVAL '1 day'
                  AND k.freq = '1d'
                  AND k.adj_type = 0
                  AND (
                    (v.limit_up IS NOT NULL AND k.limit_up IS DISTINCT FROM CAST(v.limit_up AS numeric))
                    OR (v.limit_down IS NOT NULL AND k.limit_down IS DISTINCT FROM CAST(v.limit_down AS numeric))
                  )
                RETURNING 1
            )
            SELECT (SELECT c FROM matched) AS matched_rows,
                   (SELECT COUNT(*) FROM updated) AS updated_rows
        """)
        return await self._execute_stats_sql(sql, params)

    async def _execute_stats_sql(self, sql, params: dict[str, Any]) -> tuple[int, int, int]:
        retry_count = 0
        for attempt in range(_BACKFILL_MAX_RETRIES):
            try:
                matched, updated = await self._execute_stats_sql_once(sql, params)
                return matched, updated, retry_count
            except Exception as exc:
                if (
                    attempt >= _BACKFILL_MAX_RETRIES - 1
                    or not self._is_transient_db_error(exc)
                ):
                    raise
                retry_count += 1
                wait = _BACKFILL_RETRY_BASE_DELAY * (attempt + 1)
                logger.warning(
                    "kline 辅助字段回填瞬时异常，%.1fs 后重试 attempt=%d/%d error=%s",
                    wait,
                    attempt + 1,
                    _BACKFILL_MAX_RETRIES,
                    self._compact_error(exc),
                )
                await asyncio.sleep(wait)
        return 0, 0, retry_count

    async def _execute_stats_sql_once(self, sql, params: dict[str, Any]) -> tuple[int, int]:
        if self._ts_session is not None:
            try:
                await self._acquire_backfill_lock(self._ts_session)
                res = await self._ts_session.execute(sql, params)
                row = res.first()
                await self._ts_session.commit()
            except Exception:
                await self._ts_session.rollback()
                raise
        else:
            async with AsyncSessionTS() as session:
                try:
                    await self._acquire_backfill_lock(session)
                    res = await session.execute(sql, params)
                    row = res.first()
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        if row is None:
            return 0, 0
        return int(row.matched_rows or 0), int(row.updated_rows or 0)

    async def _acquire_backfill_lock(self, session: AsyncSession) -> None:
        """获取事务级 advisory lock，串行化 kline 辅助字段回填。"""
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _KLINE_AUX_BACKFILL_LOCK_KEY},
        )

    @staticmethod
    def _is_transient_db_error(exc: Exception) -> bool:
        raw = str(exc).lower()
        markers = (
            "deadlock detected",
            "serialization failure",
            "could not serialize access",
            "connection was closed",
            "connectiondoesnotexisterror",
            "lock timeout",
        )
        return any(marker in raw for marker in markers)

    @staticmethod
    def _compact_error(exc: Exception) -> str:
        line = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        return line[:180]

    def _chunks(self, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        return [
            rows[i : i + self._batch_size]
            for i in range(0, len(rows), self._batch_size)
        ]

    @staticmethod
    def _build_values_sql(
        rows: list[dict[str, Any]],
        columns: tuple[str, ...],
    ) -> tuple[str, dict[str, Any]]:
        params: dict[str, Any] = {}
        placeholders = []
        for i, row in enumerate(rows):
            cells = []
            for col in columns:
                key = f"{col}_{i}"
                params[key] = row.get(col)
                cells.append(f":{key}")
            placeholders.append(f"({', '.join(cells)})")
        return ", ".join(placeholders), params

    @staticmethod
    def _normalize_symbol(value: object) -> str | None:
        if value is None:
            return None
        symbol = str(value)
        if is_standard(symbol):
            return symbol
        try:
            return to_standard(symbol)
        except ValueError:
            return symbol or None

    @staticmethod
    def _normalize_trade_date(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.isoformat()
        raw = str(value)
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        if len(raw) >= 10 and "-" in raw:
            return raw[:10]
        return None

    @staticmethod
    def _to_numeric_param(value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _min_date(rows: list[dict[str, Any]]) -> str | None:
        dates = [row["trade_date"] for row in rows if row.get("trade_date")]
        return min(dates) if dates else None

    @staticmethod
    def _max_date(rows: list[dict[str, Any]]) -> str | None:
        dates = [row["trade_date"] for row in rows if row.get("trade_date")]
        return max(dates) if dates else None
