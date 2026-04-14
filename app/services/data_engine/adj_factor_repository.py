"""
复权因子数据入库仓储层

AdjFactorRepository 提供：
- bulk_insert：批量写入复权因子到 TimescaleDB（ON CONFLICT DO NOTHING）
"""

from __future__ import annotations

import logging

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

        logger.info("复权因子批量写入完成，共 %d 条，实际插入 %d 条", len(factors), inserted)
        return inserted


class _NullContext:
    """将已有 session 包装成异步上下文管理器，不做额外的 commit/close。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_) -> None:
        pass
