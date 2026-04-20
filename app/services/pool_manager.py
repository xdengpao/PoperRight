"""
选股池管理器（Pool Manager）

提供：
- 业务约束常量：MAX_POOLS_PER_USER, MAX_STOCKS_PER_POOL, MAX_POOL_NAME_LENGTH, STOCK_SYMBOL_PATTERN
- 纯校验函数（无数据库依赖，便于属性测试）：
  - validate_pool_name: 校验选股池名称（非空、长度 ≤ 50）
  - validate_stock_symbol: 校验 A 股代码格式（6 位数字）
- 纯合并函数（无数据库依赖，便于属性测试）：
  - merge_pool_stocks_with_screen_results: 将选股池股票与选股结果合并，返回富化列表
- PoolManager: 选股池 CRUD 及池内股票增删

对应需求：
- 需求 3：创建和管理自选股池
- 需求 4：从选股结果添加股票到选股池
- 需求 5：选股池内股票管理
- 需求 6：选股池数据持久化
- 需求 7：选股池股票展示与选股结果一致
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pool import StockPool, StockPoolItem
from app.models.stock import StockInfo
from app.models.strategy import ScreenResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 业务约束常量
# ---------------------------------------------------------------------------

MAX_POOLS_PER_USER = 20          # 单用户最多 20 个选股池
MAX_STOCKS_PER_POOL = 200        # 单选股池最多 200 只股票
MAX_POOL_NAME_LENGTH = 50        # 选股池名称最大长度
STOCK_SYMBOL_PATTERN = r"^\d{6}$"  # A 股代码格式（6 位数字）

_STOCK_SYMBOL_RE = re.compile(STOCK_SYMBOL_PATTERN)


# ---------------------------------------------------------------------------
# 纯校验函数（无 DB 依赖，便于属性测试）
# ---------------------------------------------------------------------------

def validate_pool_name(name: str) -> str:
    """校验选股池名称。

    1. 去除首尾空白
    2. 拒绝空字符串或纯空白字符串
    3. 拒绝长度超过 50 个字符的名称

    Args:
        name: 用户输入的选股池名称。

    Returns:
        去除首尾空白后的名称。

    Raises:
        ValueError: 名称为空或超过长度限制。
    """
    stripped = name.strip()
    if not stripped:
        raise ValueError("选股池名称不能为空")
    if len(stripped) > MAX_POOL_NAME_LENGTH:
        raise ValueError("选股池名称长度不能超过50个字符")
    return stripped


def validate_stock_symbol(symbol: str) -> str:
    """校验 A 股代码格式。

    代码必须恰好为 6 位数字（如 "600000"、"000001"）。

    Args:
        symbol: 用户输入的股票代码。

    Returns:
        通过校验的股票代码（原样返回）。

    Raises:
        ValueError: 代码不符合 6 位数字格式。
    """
    if not _STOCK_SYMBOL_RE.match(symbol):
        raise ValueError("请输入有效的A股代码（6位数字）")
    return symbol


# ---------------------------------------------------------------------------
# 纯合并函数（无 DB 依赖，便于属性测试）
# ---------------------------------------------------------------------------

# 富化合并时需要从选股结果中提取的字段列表
_ENRICHMENT_FIELDS = (
    "ref_buy_price",
    "trend_score",
    "risk_level",
    "signals",
    "screen_time",
    "has_fake_breakout",
    "sector_classifications",
)


def merge_pool_stocks_with_screen_results(
    pool_stocks: list[dict],
    screen_results_map: dict[str, dict],
) -> list[dict]:
    """将选股池股票与选股结果合并，返回富化列表。

    对于 screen_results_map 中存在的 symbol，合并以下字段：
    ref_buy_price, trend_score, risk_level, signals, screen_time,
    has_fake_breakout, sector_classifications。

    对于不存在的 symbol，这些字段设为 None（has_fake_breakout 默认为 False）。

    Args:
        pool_stocks: get_pool_stocks 返回的基础列表，每个字典包含
            symbol, stock_name, added_at。
        screen_results_map: 以 symbol 为键、选股结果字典为值的映射。

    Returns:
        富化后的字典列表，长度等于 pool_stocks 长度，
        symbol 和 stock_name 保持不变。
    """
    enriched: list[dict] = []
    for stock in pool_stocks:
        symbol = stock["symbol"]
        merged = {
            "symbol": stock["symbol"],
            "stock_name": stock["stock_name"],
            "added_at": stock["added_at"],
        }
        screen_data = screen_results_map.get(symbol)
        if screen_data is not None:
            for field in _ENRICHMENT_FIELDS:
                merged[field] = screen_data.get(field)
        else:
            # 未匹配到选股结果，所有富化字段设为 None，
            # has_fake_breakout 按设计默认为 False
            for field in _ENRICHMENT_FIELDS:
                if field == "has_fake_breakout":
                    merged[field] = False
                else:
                    merged[field] = None
        enriched.append(merged)
    return enriched


# ---------------------------------------------------------------------------
# PoolManager — 选股池管理器
# ---------------------------------------------------------------------------

class PoolManager:
    """选股池 CRUD 及池内股票增删。

    所有方法为 staticmethod，接收 SQLAlchemy AsyncSession，
    由调用方管理事务边界。
    """

    # ------------------------------------------------------------------
    # 内部辅助：校验选股池归属
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_pool_or_raise(
        session: AsyncSession, user_id: UUID, pool_id: UUID
    ) -> StockPool:
        """查询选股池并校验归属，不存在或不属于该用户则抛 ValueError。"""
        stmt = select(StockPool).where(
            StockPool.id == pool_id,
            StockPool.user_id == user_id,
        )
        result = await session.execute(stmt)
        pool = result.scalar_one_or_none()
        if pool is None:
            raise ValueError("选股池不存在")
        return pool

    @staticmethod
    async def _count_stocks_in_pool(
        session: AsyncSession, pool_id: UUID
    ) -> int:
        """统计选股池内当前股票数量。"""
        stmt = select(func.count()).select_from(StockPoolItem).where(
            StockPoolItem.pool_id == pool_id
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # 3.1 创建选股池
    # ------------------------------------------------------------------

    @staticmethod
    async def create_pool(
        session: AsyncSession, user_id: UUID, name: str
    ) -> StockPool:
        """创建选股池。

        校验流程：
        1. 校验名称（非空、长度 ≤ 50）
        2. 检查用户选股池数量上限（≤ 20）
        3. 检查同用户名称唯一性
        4. 创建并 flush

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            name: 选股池名称。

        Returns:
            新创建的 StockPool 实例。

        Raises:
            ValueError: 名称无效、数量超限或名称重复。
        """
        clean_name = validate_pool_name(name)

        # 检查数量上限
        count_stmt = select(func.count()).select_from(StockPool).where(
            StockPool.user_id == user_id
        )
        result = await session.execute(count_stmt)
        pool_count = result.scalar_one()
        if pool_count >= MAX_POOLS_PER_USER:
            raise ValueError("选股池数量已达上限（20个）")

        # 检查名称唯一性
        dup_stmt = select(StockPool.id).where(
            StockPool.user_id == user_id,
            StockPool.name == clean_name,
        )
        result = await session.execute(dup_stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError("选股池名称已存在，请使用其他名称")

        # 创建
        pool = StockPool(user_id=user_id, name=clean_name)
        session.add(pool)
        await session.flush()
        return pool

    # ------------------------------------------------------------------
    # 3.2 删除选股池
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_pool(
        session: AsyncSession, user_id: UUID, pool_id: UUID
    ) -> None:
        """删除选股池（CASCADE 自动清理条目）。

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。

        Raises:
            ValueError: 选股池不存在或不属于该用户。
        """
        pool = await PoolManager._get_pool_or_raise(session, user_id, pool_id)
        await session.delete(pool)
        await session.flush()

    # ------------------------------------------------------------------
    # 3.3 重命名选股池
    # ------------------------------------------------------------------

    @staticmethod
    async def rename_pool(
        session: AsyncSession, user_id: UUID, pool_id: UUID, new_name: str
    ) -> StockPool:
        """重命名选股池。

        校验流程：
        1. 校验新名称
        2. 校验归属
        3. 检查同用户名称唯一性（排除自身）
        4. 更新 name 和 updated_at

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。
            new_name: 新名称。

        Returns:
            更新后的 StockPool 实例。

        Raises:
            ValueError: 名称无效、选股池不存在或名称重复。
        """
        clean_name = validate_pool_name(new_name)
        pool = await PoolManager._get_pool_or_raise(session, user_id, pool_id)

        # 检查名称唯一性（排除自身）
        dup_stmt = select(StockPool.id).where(
            StockPool.user_id == user_id,
            StockPool.name == clean_name,
            StockPool.id != pool_id,
        )
        result = await session.execute(dup_stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError("选股池名称已存在，请使用其他名称")

        pool.name = clean_name
        pool.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return pool

    # ------------------------------------------------------------------
    # 3.4 列出用户所有选股池
    # ------------------------------------------------------------------

    @staticmethod
    async def list_pools(
        session: AsyncSession, user_id: UUID
    ) -> list[dict]:
        """查询用户所有选股池，LEFT JOIN 统计每个池的股票数量。

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。

        Returns:
            选股池字典列表，每个字典包含：
            id, name, stock_count, created_at, updated_at。
        """
        stmt = (
            select(
                StockPool.id,
                StockPool.name,
                func.count(StockPoolItem.symbol).label("stock_count"),
                StockPool.created_at,
                StockPool.updated_at,
            )
            .outerjoin(StockPoolItem, StockPool.id == StockPoolItem.pool_id)
            .where(StockPool.user_id == user_id)
            .group_by(StockPool.id)
            .order_by(StockPool.created_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "stock_count": row.stock_count,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # 3.5 获取选股池内所有股票
    # ------------------------------------------------------------------

    @staticmethod
    async def get_pool_stocks(
        session: AsyncSession, user_id: UUID, pool_id: UUID
    ) -> list[dict]:
        """查询选股池内所有股票，LEFT JOIN stock_info 获取股票名称。

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。

        Returns:
            股票字典列表，每个字典包含：symbol, stock_name, added_at。

        Raises:
            ValueError: 选股池不存在或不属于该用户。
        """
        await PoolManager._get_pool_or_raise(session, user_id, pool_id)

        stmt = (
            select(
                StockPoolItem.symbol,
                StockInfo.name.label("stock_name"),
                StockPoolItem.added_at,
            )
            .outerjoin(StockInfo, StockPoolItem.symbol == StockInfo.symbol)
            .where(StockPoolItem.pool_id == pool_id)
            .order_by(StockPoolItem.added_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "symbol": row.symbol,
                "stock_name": row.stock_name,
                "added_at": row.added_at,
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # 3.6 批量添加股票
    # ------------------------------------------------------------------

    @staticmethod
    async def add_stocks(
        session: AsyncSession,
        user_id: UUID,
        pool_id: UUID,
        symbols: list[str],
    ) -> dict:
        """批量添加股票到选股池。

        使用 INSERT ... ON CONFLICT DO NOTHING 实现幂等插入。
        受 MAX_STOCKS_PER_POOL 上限约束，超出部分截断。

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。
            symbols: 股票代码列表。

        Returns:
            字典 {"added": int, "skipped": int}。

        Raises:
            ValueError: 选股池不存在或不属于该用户。
        """
        await PoolManager._get_pool_or_raise(session, user_id, pool_id)

        if not symbols:
            return {"added": 0, "skipped": 0}

        # 去重
        unique_symbols = list(dict.fromkeys(symbols))

        # 当前池内股票数量
        current_count = await PoolManager._count_stocks_in_pool(session, pool_id)
        available_slots = MAX_STOCKS_PER_POOL - current_count

        if available_slots <= 0:
            raise ValueError("选股池股票数量已达上限（200只）")

        # 截断到可用空间
        to_insert = unique_symbols[:available_slots]
        skipped_by_limit = len(unique_symbols) - len(to_insert)

        # 使用 INSERT ... ON CONFLICT DO NOTHING 批量插入
        values = [
            {"pool_id": pool_id, "symbol": sym}
            for sym in to_insert
        ]
        stmt = pg_insert(StockPoolItem).values(values).on_conflict_do_nothing(
            index_elements=["pool_id", "symbol"]
        )
        result = await session.execute(stmt)
        await session.flush()

        # rowcount 为实际插入行数（排除冲突跳过的）
        actually_added = result.rowcount
        skipped_by_conflict = len(to_insert) - actually_added
        total_skipped = skipped_by_conflict + skipped_by_limit

        return {"added": actually_added, "skipped": total_skipped}

    # ------------------------------------------------------------------
    # 3.7 批量移除股票
    # ------------------------------------------------------------------

    @staticmethod
    async def remove_stocks(
        session: AsyncSession,
        user_id: UUID,
        pool_id: UUID,
        symbols: list[str],
    ) -> int:
        """批量移除选股池内的股票。

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。
            symbols: 要移除的股票代码列表。

        Returns:
            实际删除的股票数量。

        Raises:
            ValueError: 选股池不存在或不属于该用户。
        """
        await PoolManager._get_pool_or_raise(session, user_id, pool_id)

        if not symbols:
            return 0

        stmt = delete(StockPoolItem).where(
            StockPoolItem.pool_id == pool_id,
            StockPoolItem.symbol.in_(symbols),
        )
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount

    # ------------------------------------------------------------------
    # 3.8 手动添加单只股票
    # ------------------------------------------------------------------

    @staticmethod
    async def add_stock_manual(
        session: AsyncSession,
        user_id: UUID,
        pool_id: UUID,
        symbol: str,
    ) -> StockPoolItem:
        """手动添加单只股票到选股池。

        校验流程：
        1. 校验股票代码格式（6 位数字）
        2. 校验选股池归属
        3. 检查是否已存在（已存在则抛异常）
        4. 检查 200 上限
        5. 插入

        Args:
            session: 异步数据库会话。
            user_id: 用户 ID。
            pool_id: 选股池 ID。
            symbol: 股票代码。

        Returns:
            新创建的 StockPoolItem 实例。

        Raises:
            ValueError: 代码格式无效、选股池不存在、股票已存在或超出上限。
        """
        validate_stock_symbol(symbol)
        await PoolManager._get_pool_or_raise(session, user_id, pool_id)

        # 检查是否已存在
        exists_stmt = select(StockPoolItem).where(
            StockPoolItem.pool_id == pool_id,
            StockPoolItem.symbol == symbol,
        )
        result = await session.execute(exists_stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError("该股票已在选股池中")

        # 检查上限
        current_count = await PoolManager._count_stocks_in_pool(session, pool_id)
        if current_count >= MAX_STOCKS_PER_POOL:
            raise ValueError("选股池股票数量已达上限（200只）")

        # 插入
        item = StockPoolItem(pool_id=pool_id, symbol=symbol)
        session.add(item)
        await session.flush()
        return item

    # ------------------------------------------------------------------
    # 3.9 获取富化选股池股票（需求 7）
    # ------------------------------------------------------------------

    @staticmethod
    async def get_enriched_pool_stocks(
        session: AsyncSession,
        redis: Redis,
        user_id: UUID,
        pool_id: UUID,
    ) -> list[dict]:
        """获取选股池内股票并附带完整选股结果数据。

        数据源优先级：
        1. Redis 缓存（screen:results:latest）
        2. PostgreSQL 回退（screen_result 表，每只股票最近一次记录）

        Redis 读取失败时静默降级，继续从 DB 回退查询所有 symbol。

        Args:
            session: 异步数据库会话。
            redis: Redis 异步客户端。
            user_id: 用户 ID。
            pool_id: 选股池 ID。

        Returns:
            富化后的股票字典列表，包含 ref_buy_price、trend_score、
            risk_level、signals、screen_time、has_fake_breakout、
            sector_classifications 等字段。

        Raises:
            ValueError: 选股池不存在或不属于该用户。
        """
        # 1. 获取基础股票列表
        pool_stocks = await PoolManager.get_pool_stocks(session, user_id, pool_id)
        symbols = [s["symbol"] for s in pool_stocks]

        if not symbols:
            return merge_pool_stocks_with_screen_results(pool_stocks, {})

        # 2. 从 Redis 读取最新选股结果
        screen_results_map: dict[str, dict] = {}
        try:
            raw = await redis.get("screen:results:latest")
            if raw:
                data = json.loads(raw)
                for item in data.get("items", []):
                    if item.get("symbol") in symbols:
                        screen_results_map[item["symbol"]] = item
        except Exception:
            # Redis 读取失败，静默降级，后续从 DB 回退查询所有 symbol
            logger.warning("Redis 读取选股结果缓存失败，将从数据库回退查询")

        # 3. 对 Redis 未命中的 symbol，从 PostgreSQL 回退查询
        missing_symbols = [s for s in symbols if s not in screen_results_map]
        if missing_symbols:
            stmt = (
                select(ScreenResult)
                .where(ScreenResult.symbol.in_(missing_symbols))
                .order_by(ScreenResult.symbol, ScreenResult.screen_time.desc())
                .distinct(ScreenResult.symbol)
            )
            result = await session.execute(stmt)
            for row in result.scalars().all():
                screen_results_map[row.symbol] = {
                    "ref_buy_price": float(row.ref_buy_price) if row.ref_buy_price else None,
                    "trend_score": float(row.trend_score) if row.trend_score else None,
                    "risk_level": row.risk_level,
                    "signals": row.signals or [],
                    "screen_time": row.screen_time.isoformat() if row.screen_time else None,
                    "has_fake_breakout": False,
                    "sector_classifications": None,
                }

        # 4. 合并
        return merge_pool_stocks_with_screen_results(pool_stocks, screen_results_map)
