"""
K 线数据入库仓储层

KlineRepository 提供：
- bulk_insert：批量写入 TimescaleDB（ON CONFLICT DO NOTHING，满足 500ms 入库要求）
- query：按股票代码、时间范围、复权类型查询 K 线数据
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Sequence

from sqlalchemy import select, and_, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionTS
from app.models.kline import Kline, KlineBar
from app.services.data_engine.kline_normalizer import (
    normalize_kline_symbol,
    normalize_kline_time,
)

logger = logging.getLogger(__name__)

# 单次批量写入的最大行数（避免单条 SQL 过大）
_BATCH_SIZE = 1000


class KlineRepository:
    """
    K 线数据仓储，操作 TimescaleDB 超表 kline。

    可通过依赖注入传入 session，也可不传（内部自动创建 session）。

    示例（手动管理 session）：
        async with AsyncSessionTS() as session:
            repo = KlineRepository(session)
            await repo.bulk_insert(bars)

    示例（自动管理 session）：
        repo = KlineRepository()
        await repo.bulk_insert(bars)
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _get_session_ctx(self):
        """返回 session 上下文管理器（外部传入时直接使用，否则新建）。"""
        if self._session is not None:
            return _NullContext(self._session)
        return AsyncSessionTS()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    async def bulk_insert(self, bars: Sequence[KlineBar]) -> int:
        """
        批量写入 K 线数据到 TimescaleDB。

        使用 INSERT ... ON CONFLICT DO NOTHING 保证幂等性，
        重复数据（相同 time+symbol+freq+adj_type）不会报错也不会覆盖。

        Args:
            bars: KlineBar 列表

        Returns:
            实际插入的行数
        """
        if not bars:
            return 0

        rows_by_key: dict[tuple[datetime, str, str, int], dict] = {}
        skipped = 0
        for b in bars:
            symbol = normalize_kline_symbol(b.symbol)
            if symbol is None:
                skipped += 1
                logger.warning("跳过无法标准化的 K 线代码: %s", b.symbol)
                continue
            try:
                normalized_time = normalize_kline_time(b.time, b.freq)
            except ValueError as exc:
                skipped += 1
                logger.warning("跳过无法归一化时间的 K 线 symbol=%s time=%s: %s", b.symbol, b.time, exc)
                continue

            row = {
                "time": normalized_time,
                "symbol": symbol,
                "freq": b.freq,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "amount": b.amount,
                "turnover": b.turnover,
                "vol_ratio": b.vol_ratio,
                "limit_up": b.limit_up,
                "limit_down": b.limit_down,
                "adj_type": b.adj_type,
            }
            key = (normalized_time, symbol, b.freq, b.adj_type)
            current = rows_by_key.get(key)
            if current is None or _row_completeness(row) >= _row_completeness(current):
                rows_by_key[key] = row

        rows = list(rows_by_key.values())
        if not rows:
            logger.info("K 线批量写入无有效行，共跳过 %d 条", skipped)
            return 0

        inserted = 0
        async with self._get_session_ctx() as session:
            for i in range(0, len(rows), _BATCH_SIZE):
                chunk = rows[i : i + _BATCH_SIZE]
                stmt = pg_insert(Kline).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["time", "symbol", "freq", "adj_type"],
                    set_={
                        "open": func.coalesce(stmt.excluded.open, Kline.open),
                        "high": func.coalesce(stmt.excluded.high, Kline.high),
                        "low": func.coalesce(stmt.excluded.low, Kline.low),
                        "close": func.coalesce(stmt.excluded.close, Kline.close),
                        "volume": func.coalesce(stmt.excluded.volume, Kline.volume),
                        "amount": func.coalesce(stmt.excluded.amount, Kline.amount),
                        "turnover": func.coalesce(stmt.excluded.turnover, Kline.turnover),
                        "vol_ratio": func.coalesce(stmt.excluded.vol_ratio, Kline.vol_ratio),
                        "limit_up": func.coalesce(stmt.excluded.limit_up, Kline.limit_up),
                        "limit_down": func.coalesce(stmt.excluded.limit_down, Kline.limit_down),
                    },
                )
                result = await session.execute(stmt)
                inserted += result.rowcount or 0
            await session.commit()

        logger.info(
            "K 线批量写入完成，有效 %d 条，跳过 %d 条，影响 %d 条",
            len(rows), skipped, inserted,
        )
        return inserted

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def query(
        self,
        symbol: str,
        freq: str,
        start: date | datetime,
        end: date | datetime,
        adj_type: int = 0,
    ) -> list[KlineBar]:
        """
        查询 K 线数据。

        Args:
            symbol:   股票代码，如 "000001.SZ" 或 "000001"
            freq:     K 线频率
            start:    起始时间（含）
            end:      结束时间（含）
            adj_type: 复权类型 0=不复权 1=前复权 2=后复权

        Returns:
            按时间升序排列的 KlineBar 列表
        """
        from app.core.symbol_utils import to_standard
        symbol = to_standard(symbol)
        # 统一转为 datetime 以便与 TimescaleDB TIMESTAMPTZ 比较
        start_dt = datetime(start.year, start.month, start.day) if isinstance(start, date) and not isinstance(start, datetime) else start
        end_dt = datetime(end.year, end.month, end.day, 23, 59, 59) if isinstance(end, date) and not isinstance(end, datetime) else end

        stmt = (
            select(Kline)
            .where(
                and_(
                    Kline.symbol == symbol,
                    Kline.freq == freq,
                    Kline.adj_type == adj_type,
                    Kline.time >= start_dt,
                    Kline.time <= end_dt,
                )
            )
            .order_by(Kline.time.asc())
        )

        async with self._get_session_ctx() as session:
            result = await session.execute(stmt)
            orm_rows = result.scalars().all()

        bars = [KlineBar.from_orm(row) for row in orm_rows]
        logger.debug(
            "K 线查询 symbol=%s freq=%s adj=%d %s~%s 共 %d 条",
            symbol, freq, adj_type, start, end, len(bars),
        )
        return bars


# ------------------------------------------------------------------
# 内部工具：空上下文管理器（用于外部传入 session 的情况）
# ------------------------------------------------------------------

class _NullContext:
    """将已有 session 包装成异步上下文管理器，不做额外的 commit/close。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_) -> None:
        pass  # 由外部调用方负责 commit/close


def _row_completeness(row: dict) -> int:
    """用于同批次重复业务键去重的字段完整度评分。"""
    fields = (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover",
        "vol_ratio",
        "limit_up",
        "limit_down",
    )
    return sum(1 for field in fields if row.get(field) not in (None, ""))
