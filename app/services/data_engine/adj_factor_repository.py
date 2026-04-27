"""
复权因子数据仓储层

AdjFactorRepository 提供：
- bulk_insert：批量写入复权因子到 TimescaleDB（ON CONFLICT DO NOTHING）
- query_by_symbol：查询指定股票在日期范围内的复权因子
- query_latest_factor：查询指定股票最新交易日的复权因子值
- query_batch：批量查询多只股票的复权因子
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionTS
from app.models.adjustment_factor import AdjustmentFactor

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000


class AdjFactorRepository:
    """
    复权因子数据仓储，操作 TimescaleDB adjustment_factor 表。

    可通过依赖注入传入 session，也可不传（内部自动创建 session）。
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    def _get_session_ctx(self):
        """返回 session 上下文管理器（外部传入时直接使用，否则新建）。"""
        if self._session is not None:
            return _NullContext(self._session)
        return AsyncSessionTS()

    async def bulk_insert(self, factors: list[dict]) -> int:
        """
        批量写入复权因子到 TimescaleDB。

        使用 INSERT ... ON CONFLICT DO NOTHING 保证幂等性，
        重复数据（相同 symbol + trade_date + adj_type）不会报错也不会覆盖。

        Args:
            factors: 字典列表，每个字典包含 symbol, trade_date, adj_factor, adj_type

        Returns:
            实际插入的行数
        """
        if not factors:
            return 0

        inserted = 0
        async with self._get_session_ctx() as session:
            # 批量导入时临时关闭 SQL echo，避免日志 I/O 拖慢性能
            engine = session.get_bind()
            original_echo = engine.echo
            engine.echo = False
            try:
                for i in range(0, len(factors), _BATCH_SIZE):
                    chunk = factors[i : i + _BATCH_SIZE]
                    stmt = (
                        pg_insert(AdjustmentFactor)
                        .values(chunk)
                        .on_conflict_do_nothing()
                    )
                    result = await session.execute(stmt)
                    inserted += result.rowcount or 0
                await session.commit()
            finally:
                engine.echo = original_echo

        logger.info("复权因子批量写入完成，共 %d 条，实际插入 %d 条", len(factors), inserted)
        return inserted

    async def query_by_symbol(
        self,
        symbol: str,
        adj_type: int = 1,
        start: date | None = None,
        end: date | None = None,
    ) -> list[AdjustmentFactor]:
        """
        查询指定股票在日期范围内的复权因子，按 trade_date 升序排列。

        Args:
            symbol: 股票代码
            adj_type: 复权类型，1=前复权，2=后复权
            start: 起始日期（含），None 表示不限
            end: 结束日期（含），None 表示不限

        Returns:
            复权因子列表，按 trade_date 升序
        """
        stmt = (
            select(AdjustmentFactor)
            .where(
                AdjustmentFactor.symbol == symbol,
                AdjustmentFactor.adj_type == adj_type,
            )
            .order_by(AdjustmentFactor.trade_date.asc())
        )
        if start is not None:
            stmt = stmt.where(AdjustmentFactor.trade_date >= start)
        if end is not None:
            stmt = stmt.where(AdjustmentFactor.trade_date <= end)

        async with self._get_session_ctx() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def query_latest_factor(
        self,
        symbol: str,
        adj_type: int = 1,
    ) -> Decimal | None:
        """
        查询指定股票最新交易日的复权因子值。

        Args:
            symbol: 股票代码
            adj_type: 复权类型，1=前复权，2=后复权

        Returns:
            最新复权因子值，无数据时返回 None
        """
        stmt = (
            select(AdjustmentFactor.adj_factor)
            .where(
                AdjustmentFactor.symbol == symbol,
                AdjustmentFactor.adj_type == adj_type,
            )
            .order_by(AdjustmentFactor.trade_date.desc())
            .limit(1)
        )

        async with self._get_session_ctx() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row

    async def query_batch(
        self,
        symbols: list[str],
        adj_type: int = 1,
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, list[AdjustmentFactor]]:
        """
        批量查询多只股票的复权因子，返回 {symbol: [factors]} 字典。

        单次 SQL 查询，减少数据库往返次数。

        Args:
            symbols: 股票代码列表
            adj_type: 复权类型，1=前复权，2=后复权
            start: 起始日期（含），None 表示不限
            end: 结束日期（含），None 表示不限

        Returns:
            字典，键为股票代码，值为该股票的复权因子列表（按 trade_date 升序）
        """
        if not symbols:
            return {}

        symbols = [s.split(".")[0] if "." in s else s for s in symbols]

        stmt = (
            select(AdjustmentFactor)
            .where(
                AdjustmentFactor.symbol.in_(symbols),
                AdjustmentFactor.adj_type == adj_type,
            )
            .order_by(AdjustmentFactor.symbol, AdjustmentFactor.trade_date.asc())
        )
        if start is not None:
            stmt = stmt.where(AdjustmentFactor.trade_date >= start)
        if end is not None:
            stmt = stmt.where(AdjustmentFactor.trade_date <= end)

        async with self._get_session_ctx() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        grouped: dict[str, list[AdjustmentFactor]] = defaultdict(list)
        for factor in rows:
            grouped[factor.symbol].append(factor)
        return dict(grouped)


class _NullContext:
    """将已有 session 包装成异步上下文管理器，不做额外的 commit/close。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_) -> None:
        pass
