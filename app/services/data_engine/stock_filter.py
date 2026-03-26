"""
数据清洗引擎（StockFilter）

提供：
- StockFilter：股票过滤器，判断是否应剔除个股，管理永久剔除名单
- AdjustmentCalculator：复权因子计算与前/后复权处理
- interpolate_missing：缺失值线性插值补全
- remove_outliers：3σ 异常极值检测与剔除
- normalize_minmax：Min-Max 归一化
- normalize_zscore：Z-Score 归一化

对应需求：
- 需求 2.1：自动剔除 ST/退市/停牌/次新股/高质押/业绩暴雷
- 需求 2.2：除权除息处理（前复权/后复权/不复权）
- 需求 2.3：缺失值线性插值补全
- 需求 2.4：异常极值检测与剔除
- 需求 2.5：因子数据归一化处理
- 需求 2.6：永久剔除名单（不可解禁）
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import PermanentExclusion, StockInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 次新股：上市未满 N 个交易日
_NEW_STOCK_MIN_TRADING_DAYS = 20

# 质押率上限（%）
_MAX_PLEDGE_RATIO = Decimal("70")

# 净利润同比亏损阈值（%，负值表示亏损）
_MAX_NET_PROFIT_YOY_LOSS = Decimal("-50")

# 永久剔除原因常量
REASON_ST = "ST"
REASON_DELISTED = "DELISTED"
REASON_NEW_STOCK = "NEW_STOCK"
REASON_SUSPENDED = "SUSPENDED"
REASON_HIGH_PLEDGE = "HIGH_PLEDGE"
REASON_PROFIT_LOSS = "PROFIT_LOSS"


# ---------------------------------------------------------------------------
# 辅助数据类
# ---------------------------------------------------------------------------

@dataclass
class StockBasicInfo:
    """
    传入 StockFilter.is_excluded 的股票基础信息。
    可从 StockInfo ORM 或 FundamentalsData 构造。
    """
    symbol: str
    is_st: bool = False
    is_delisted: bool = False
    is_suspended: bool = False          # 停牌
    list_date: date | None = None       # 上市日期
    trading_days_since_ipo: int | None = None  # 上市以来交易日数（优先使用）


@dataclass
class FundamentalsSnapshot:
    """
    传入 StockFilter.is_excluded 的基本面快照。
    """
    symbol: str
    pledge_ratio: Decimal | None = None     # 质押率（%）
    net_profit_yoy: Decimal | None = None   # 净利润同比增长率（%，负值=亏损）


@dataclass
class ExRightsRecord:
    """
    除权除息记录（单次）。
    """
    ex_date: date           # 除权除息日
    cash_dividend: Decimal  # 每股现金分红（元）
    stock_dividend: Decimal # 每股送股数（股）
    allotment_ratio: Decimal  # 每股配股数（股）
    allotment_price: Decimal  # 配股价格（元）


# ---------------------------------------------------------------------------
# StockFilter
# ---------------------------------------------------------------------------

class StockFilter:
    """
    股票过滤器。

    职责：
    1. 判断个股是否应被剔除（is_excluded）
    2. 管理永久剔除名单（get/add）

    永久剔除名单（permanent_exclusion 表）中的股票不可通过用户操作解禁（需求 2.6）。
    """

    # ------------------------------------------------------------------
    # 过滤判断
    # ------------------------------------------------------------------

    def is_excluded(
        self,
        stock_info: StockBasicInfo,
        fundamentals: FundamentalsSnapshot | None = None,
        reference_date: date | None = None,
    ) -> tuple[bool, str]:
        """
        判断个股是否应被剔除。

        Args:
            stock_info:     股票基础信息
            fundamentals:   基本面快照（可选，用于质押率/业绩过滤）
            reference_date: 参考日期，用于计算次新股（默认 today）

        Returns:
            (是否剔除, 原因)。不剔除时原因为空字符串。
        """
        # 1. ST / *ST
        if stock_info.is_st:
            return True, REASON_ST

        # 2. 退市
        if stock_info.is_delisted:
            return True, REASON_DELISTED

        # 3. 停牌
        if stock_info.is_suspended:
            return True, REASON_SUSPENDED

        # 4. 次新股（上市未满 20 个交易日）
        if self._is_new_stock(stock_info, reference_date):
            return True, REASON_NEW_STOCK

        # 5. 质押率 > 70%
        if fundamentals is not None:
            if (
                fundamentals.pledge_ratio is not None
                and fundamentals.pledge_ratio > _MAX_PLEDGE_RATIO
            ):
                return True, REASON_HIGH_PLEDGE

            # 6. 净利润同比亏损 > 50%
            if (
                fundamentals.net_profit_yoy is not None
                and fundamentals.net_profit_yoy < _MAX_NET_PROFIT_YOY_LOSS
            ):
                return True, REASON_PROFIT_LOSS

        return False, ""

    @staticmethod
    def _is_new_stock(
        stock_info: StockBasicInfo,
        reference_date: date | None,
    ) -> bool:
        """判断是否为次新股（上市未满 20 个交易日）。"""
        # 优先使用已计算好的交易日数
        if stock_info.trading_days_since_ipo is not None:
            return stock_info.trading_days_since_ipo < _NEW_STOCK_MIN_TRADING_DAYS

        # 退而求其次：用自然日粗估（20 交易日 ≈ 28 自然日）
        if stock_info.list_date is not None:
            ref = reference_date or date.today()
            calendar_days = (ref - stock_info.list_date).days
            # 保守估计：28 自然日内视为次新股
            return calendar_days < 28

        return False

    # ------------------------------------------------------------------
    # 永久剔除名单
    # ------------------------------------------------------------------

    async def get_permanent_blacklist(self, session: AsyncSession) -> set[str]:
        """
        从数据库获取永久剔除名单（symbol 集合）。

        Args:
            session: SQLAlchemy 异步 Session

        Returns:
            永久剔除的股票代码集合
        """
        stmt = select(PermanentExclusion.symbol)
        result = await session.execute(stmt)
        symbols = {row[0] for row in result.fetchall()}
        logger.debug("永久剔除名单共 %d 只", len(symbols))
        return symbols

    async def add_to_permanent_blacklist(
        self,
        symbol: str,
        reason: str,
        session: AsyncSession,
    ) -> None:
        """
        将股票加入永久剔除名单（不可解禁，需求 2.6）。

        若已存在则忽略（幂等）。

        Args:
            symbol:  股票代码
            reason:  剔除原因（'ST'/'DELISTED'/'NEW_STOCK' 等）
            session: SQLAlchemy 异步 Session
        """
        upsert_sql = text("""
            INSERT INTO permanent_exclusion (symbol, reason)
            VALUES (:symbol, :reason)
            ON CONFLICT (symbol) DO NOTHING
        """)
        await session.execute(upsert_sql, {"symbol": symbol, "reason": reason})
        await session.commit()
        logger.info("已加入永久剔除名单 symbol=%s reason=%s", symbol, reason)

    async def sync_permanent_blacklist(
        self,
        session: AsyncSession,
    ) -> int:
        """
        扫描 stock_info 表，将所有 ST/退市股票自动同步到永久剔除名单。

        Returns:
            新增的记录数
        """
        sql = text("""
            INSERT INTO permanent_exclusion (symbol, reason)
            SELECT symbol,
                   CASE WHEN is_delisted THEN 'DELISTED' ELSE 'ST' END AS reason
            FROM stock_info
            WHERE is_st = TRUE OR is_delisted = TRUE
            ON CONFLICT (symbol) DO NOTHING
        """)
        result = await session.execute(sql)
        await session.commit()
        count = result.rowcount or 0
        logger.info("永久剔除名单同步完成，新增 %d 条", count)
        return count


# ---------------------------------------------------------------------------
# AdjustmentCalculator
# ---------------------------------------------------------------------------

class AdjustmentCalculator:
    """
    复权因子计算器。

    支持前复权（Forward Adjustment）和后复权（Backward Adjustment）。

    复权因子计算公式（累乘法）：
        adj_factor[t] = ∏ (1 + stock_dividend[i] + allotment_ratio[i]) * ...
    其中每次除权除息事件都会修正因子。

    前复权：以最新价为基准，历史价格向下调整。
    后复权：以上市首日价格为基准，历史价格向上调整。
    """

    @staticmethod
    def calc_adj_factor(
        bar_dates: Sequence[date],
        ex_rights_data: Sequence[ExRightsRecord],
    ) -> dict[date, Decimal]:
        """
        计算每个交易日对应的复权因子（后复权基准）。

        算法：
        - 从最早日期开始，遇到除权除息日时更新累积因子。
        - 返回每个交易日的后复权因子（相对于上市首日）。

        Args:
            bar_dates:      K 线日期序列（升序）
            ex_rights_data: 除权除息记录列表

        Returns:
            {date: adj_factor} 字典，factor >= 1.0
        """
        if not bar_dates:
            return {}

        # 按除权日排序
        sorted_ex = sorted(ex_rights_data, key=lambda r: r.ex_date)

        factors: dict[date, Decimal] = {}
        cumulative = Decimal("1")
        ex_idx = 0

        for bar_date in sorted(bar_dates):
            # 处理在此日期之前（含）发生的所有除权除息事件
            while ex_idx < len(sorted_ex) and sorted_ex[ex_idx].ex_date <= bar_date:
                rec = sorted_ex[ex_idx]
                # 每股除权因子 = 1 + 送股比例 + 配股比例
                # 现金分红不影响股数，但影响价格（此处简化处理）
                share_factor = Decimal("1") + rec.stock_dividend + rec.allotment_ratio
                if share_factor > Decimal("0"):
                    cumulative *= share_factor
                ex_idx += 1
            factors[bar_date] = cumulative

        return factors

    @staticmethod
    def apply_forward_adj(
        bars: list[dict],
        adj_factors: dict[date, Decimal],
    ) -> list[dict]:
        """
        前复权：以最新价为基准，历史价格向下调整。

        前复权因子 = 最新累积因子 / 当日累积因子

        Args:
            bars:        K 线数据列表，每条含 'date'/'open'/'high'/'low'/'close'/'volume'
            adj_factors: calc_adj_factor 返回的后复权因子字典

        Returns:
            前复权后的 K 线列表（新对象，不修改原始数据）
        """
        if not bars or not adj_factors:
            return list(bars)

        # 最新日期的累积因子作为基准
        latest_date = max(adj_factors.keys())
        latest_factor = adj_factors.get(latest_date, Decimal("1"))

        result = []
        for bar in bars:
            bar_date = bar.get("date")
            if bar_date is None:
                result.append(dict(bar))
                continue

            current_factor = adj_factors.get(bar_date, Decimal("1"))
            # 前复权因子：最新因子 / 当日因子
            fwd_factor = latest_factor / current_factor if current_factor != 0 else Decimal("1")

            adjusted = dict(bar)
            for price_field in ("open", "high", "low", "close"):
                if bar.get(price_field) is not None:
                    adjusted[price_field] = bar[price_field] / fwd_factor
            # 成交量反向调整（价格除以因子，量乘以因子）
            if bar.get("volume") is not None:
                adjusted["volume"] = int(bar["volume"] * fwd_factor)
            result.append(adjusted)

        return result

    @staticmethod
    def apply_backward_adj(
        bars: list[dict],
        adj_factors: dict[date, Decimal],
    ) -> list[dict]:
        """
        后复权：以上市首日价格为基准，历史价格向上调整。

        后复权因子 = 当日累积因子（直接使用 calc_adj_factor 的结果）

        Args:
            bars:        K 线数据列表
            adj_factors: calc_adj_factor 返回的后复权因子字典

        Returns:
            后复权后的 K 线列表（新对象，不修改原始数据）
        """
        if not bars or not adj_factors:
            return list(bars)

        result = []
        for bar in bars:
            bar_date = bar.get("date")
            if bar_date is None:
                result.append(dict(bar))
                continue

            factor = adj_factors.get(bar_date, Decimal("1"))

            adjusted = dict(bar)
            for price_field in ("open", "high", "low", "close"):
                if bar.get(price_field) is not None:
                    adjusted[price_field] = bar[price_field] * factor
            # 成交量反向调整
            if bar.get("volume") is not None:
                adjusted["volume"] = int(bar["volume"] / factor) if factor != 0 else bar["volume"]
            result.append(adjusted)

        return result


# ---------------------------------------------------------------------------
# 独立函数：缺失值插值
# ---------------------------------------------------------------------------

def interpolate_missing(values: list[float | None]) -> list[float]:
    """
    对含缺失值（None）的序列进行线性插值补全。

    规则：
    - 两端的缺失值用最近的有效值填充（前向/后向填充）。
    - 中间的缺失值用左右两侧有效值线性插值。
    - 插值结果满足：min(left, right) ≤ interpolated ≤ max(left, right)（属性 3）。
    - 若序列全为 None，返回全 0.0 列表。

    Args:
        values: 含 None 的浮点数列表

    Returns:
        不含 None 的浮点数列表，长度与输入相同
    """
    n = len(values)
    if n == 0:
        return []

    result: list[float] = [0.0] * n

    # 找到所有有效值的索引
    valid_indices = [i for i, v in enumerate(values) if v is not None]

    if not valid_indices:
        # 全为 None，返回全 0
        return result

    # 前向填充（左端缺失）
    first_valid = valid_indices[0]
    for i in range(first_valid):
        result[i] = float(values[first_valid])  # type: ignore[arg-type]

    # 后向填充（右端缺失）
    last_valid = valid_indices[-1]
    for i in range(last_valid + 1, n):
        result[i] = float(values[last_valid])  # type: ignore[arg-type]

    # 填充有效值本身
    for i in valid_indices:
        result[i] = float(values[i])  # type: ignore[arg-type]

    # 线性插值（中间缺失段）
    for seg_start_idx in range(len(valid_indices) - 1):
        left_pos = valid_indices[seg_start_idx]
        right_pos = valid_indices[seg_start_idx + 1]

        if right_pos - left_pos <= 1:
            # 相邻，无缺失
            continue

        left_val = float(values[left_pos])   # type: ignore[arg-type]
        right_val = float(values[right_pos])  # type: ignore[arg-type]
        gap = right_pos - left_pos

        for step in range(1, gap):
            t = step / gap  # 插值比例 (0, 1)
            interpolated = left_val + t * (right_val - left_val)
            result[left_pos + step] = interpolated

    return result


# ---------------------------------------------------------------------------
# 独立函数：异常极值检测
# ---------------------------------------------------------------------------

def remove_outliers(
    values: list[float],
    n_sigma: float = 3.0,
) -> list[float | None]:
    """
    使用 3σ 法则检测并剔除异常极值。

    超出 [mean - n_sigma * std, mean + n_sigma * std] 范围的值被替换为 None。

    Args:
        values:  浮点数列表（不含 None）
        n_sigma: σ 倍数，默认 3.0

    Returns:
        与输入等长的列表，异常值位置替换为 None
    """
    if len(values) < 2:
        return list(values)  # type: ignore[return-value]

    mean = statistics.mean(values)
    std = statistics.stdev(values)

    if std == 0:
        # 所有值相同，无异常值
        return list(values)  # type: ignore[return-value]

    lower = mean - n_sigma * std
    upper = mean + n_sigma * std

    return [v if lower <= v <= upper else None for v in values]


# ---------------------------------------------------------------------------
# 独立函数：归一化
# ---------------------------------------------------------------------------

def normalize_minmax(values: list[float]) -> list[float]:
    """
    Min-Max 归一化，将数据映射到 [0, 1]。

    公式：x_norm = (x - min) / (max - min)

    若所有值相同（max == min），返回全 0.5 列表（保持中性）。

    归一化不改变相对排序关系（属性 4）。

    Args:
        values: 浮点数列表

    Returns:
        归一化后的列表，值域 [0, 1]
    """
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return [0.5] * len(values)

    span = max_val - min_val
    return [(v - min_val) / span for v in values]


def normalize_zscore(values: list[float]) -> list[float]:
    """
    Z-Score 标准化，将数据转换为均值 0、标准差 1 的分布。

    公式：x_norm = (x - mean) / std

    若标准差为 0（所有值相同），返回全 0.0 列表。

    归一化不改变相对排序关系（属性 4）。

    Args:
        values: 浮点数列表

    Returns:
        Z-Score 标准化后的列表
    """
    if not values:
        return []

    if len(values) == 1:
        return [0.0]

    mean = statistics.mean(values)
    std = statistics.stdev(values)

    if std == 0:
        return [0.0] * len(values)

    return [(v - mean) / std for v in values]
