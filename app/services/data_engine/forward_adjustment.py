"""
前复权K线计算模块

纯函数式设计，不依赖数据库。将原始K线价格通过复权因子转换为前复权价格。

公式：adjusted_price = raw_price × (daily_factor / latest_factor)
"""

import bisect
import logging
from dataclasses import replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.models.adjustment_factor import AdjustmentFactor
from app.models.kline import KlineBar

logger = logging.getLogger(__name__)

# 用于四舍五入到两位小数的量化参数
_TWO_PLACES = Decimal("0.01")


def adjust_kline_bars(
    bars: list[KlineBar],
    factors: list[AdjustmentFactor],
    latest_factor: Decimal,
) -> list[KlineBar]:
    """
    将原始K线数据转换为前复权K线数据。

    算法：
    1. 构建 {trade_date: adj_factor} 查找表
    2. 对每根K线，查找对应日期的复权因子（找不到则用最近前一日的因子）
    3. 计算 ratio = daily_factor / latest_factor
    4. adjusted_price = raw_price * ratio，四舍五入保留两位小数
    5. 仅调整 OHLC，volume/amount/turnover/vol_ratio 等保持不变

    边界处理：
    - factors 为空 → 返回原始 bars 不做调整，记录警告
    - latest_factor 为 0 → 返回原始 bars 不做调整，记录警告

    Args:
        bars: 原始K线列表（按时间升序）
        factors: 复权因子列表（按 trade_date 升序）
        latest_factor: 最新复权因子值

    Returns:
        前复权K线列表（新对象，不修改原始数据）
    """
    if not factors:
        logger.warning("复权因子序列为空，返回原始K线数据不做调整")
        return list(bars)

    if latest_factor == Decimal("0"):
        logger.warning("最新复权因子为零，返回原始K线数据不做调整")
        return list(bars)

    # 构建 {trade_date: adj_factor} 查找表和排序日期列表
    factor_map: dict[date, Decimal] = {
        f.trade_date: f.adj_factor for f in factors
    }
    sorted_dates: list[date] = sorted(factor_map.keys())

    adjusted_bars: list[KlineBar] = []
    for bar in bars:
        # 提取K线对应的日期（KlineBar.time 是 datetime）
        bar_date = bar.time.date() if isinstance(bar.time, datetime) else bar.time

        daily_factor = _find_factor_for_date(bar_date, factor_map, sorted_dates)

        if daily_factor is None:
            # 无法找到任何因子（该日期之前也没有因子），保持原始价格
            logger.debug(
                "K线日期 %s 无对应复权因子且无更早因子，保持原始价格",
                bar_date,
            )
            adjusted_bars.append(replace(bar))
            continue

        ratio = daily_factor / latest_factor

        adjusted_bars.append(
            replace(
                bar,
                open=_adjust_price(bar.open, ratio),
                high=_adjust_price(bar.high, ratio),
                low=_adjust_price(bar.low, ratio),
                close=_adjust_price(bar.close, ratio),
            )
        )

    return adjusted_bars


def _find_factor_for_date(
    target_date: date,
    factor_map: dict[date, Decimal],
    sorted_dates: list[date],
) -> Decimal | None:
    """
    查找目标日期对应的复权因子。

    精确匹配优先，找不到则使用 bisect 定位最近的前一个交易日因子。

    Args:
        target_date: 目标日期
        factor_map: {trade_date: adj_factor} 查找表
        sorted_dates: 按升序排列的因子日期列表

    Returns:
        对应的复权因子值，若无法找到则返回 None
    """
    # 精确匹配
    if target_date in factor_map:
        return factor_map[target_date]

    # 使用 bisect 查找最近的前一个交易日
    idx = bisect.bisect_right(sorted_dates, target_date)
    if idx > 0:
        nearest_date = sorted_dates[idx - 1]
        return factor_map[nearest_date]

    # 目标日期早于所有因子日期，无法回退
    return None


def _adjust_price(raw_price: Decimal, ratio: Decimal) -> Decimal:
    """将原始价格乘以比率并四舍五入到两位小数。"""
    return (raw_price * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
