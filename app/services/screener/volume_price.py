"""
量价资金筛选模块（Volume-Price & Money Flow Screener）

提供：
- check_turnover_rate: 换手率区间筛选（3%-15%）
- detect_volume_price_divergence: 量价背离检测与过滤
- check_avg_daily_amount: 日均成交额过滤（< 5000 万自动剔除）
- check_money_flow_signal: 主力资金净流入信号生成（≥ 1000 万且连续 2 日）
- check_large_order_signal: 大单成交占比信号生成（> 30%）
- check_sector_resonance: 板块共振筛选（板块涨幅前 30 且多头趋势）

对应需求：
- 需求 6.1：筛选换手率处于 3%-15% 区间
- 需求 6.2：剔除量价背离和高位放量滞涨
- 需求 6.3：主力资金单日净流入 ≥ 1000 万且连续 2 日 → 资金流入信号
- 需求 6.4：大单成交占比 > 30% → 大单活跃信号
- 需求 6.5：优先板块涨幅前 30 且多头趋势，弱势板块剔除
- 需求 6.6：近 20 日日均成交额 < 5000 万 → 自动剔除
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_TURNOVER_MIN = 3.0          # 换手率下限 %
DEFAULT_TURNOVER_MAX = 15.0         # 换手率上限 %

DEFAULT_AVG_AMOUNT_PERIOD = 20      # 日均成交额计算周期（交易日）
DEFAULT_MIN_AVG_AMOUNT = 5000.0     # 日均成交额下限（万元）

DEFAULT_MONEY_FLOW_THRESHOLD = 1000.0   # 主力资金净流入阈值（万元）
DEFAULT_MONEY_FLOW_CONSECUTIVE = 2      # 连续净流入天数

DEFAULT_LARGE_ORDER_RATIO_THRESHOLD = 30.0  # 大单成交占比阈值 %

DEFAULT_SECTOR_TOP_N = 30           # 板块涨幅排名前 N


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

class DivergenceType(str, Enum):
    """量价背离类型"""
    NONE = "NONE"                           # 无背离
    PRICE_UP_VOLUME_DOWN = "PRICE_UP_VOL_DOWN"  # 价涨量缩
    PRICE_DOWN_VOLUME_UP = "PRICE_DOWN_VOL_UP"  # 价跌量增
    HIGH_STAGNATION = "HIGH_STAGNATION"     # 高位放量滞涨


@dataclass
class TurnoverCheckResult:
    """换手率筛选结果"""
    passed: bool
    turnover_rate: float        # 当日换手率 %
    min_threshold: float        # 下限
    max_threshold: float        # 上限


@dataclass
class DivergenceCheckResult:
    """量价背离检测结果"""
    has_divergence: bool
    divergence_type: DivergenceType
    price_change_pct: float     # 价格变化百分比
    volume_change_pct: float    # 成交量变化百分比


@dataclass
class AvgAmountCheckResult:
    """日均成交额检查结果"""
    passed: bool
    avg_daily_amount: float     # 近 N 日日均成交额（万元）
    threshold: float            # 阈值（万元）


@dataclass
class MoneyFlowSignal:
    """主力资金净流入信号"""
    signal: bool                        # 是否生成信号
    consecutive_days: int               # 连续净流入天数
    latest_inflow: float                # 最近一日净流入（万元）
    threshold: float                    # 阈值（万元）
    required_consecutive: int           # 要求连续天数


@dataclass
class RelativeMoneyFlowSignal:
    """相对阈值模式的资金流信号结果"""
    signal: bool                        # 是否生成信号
    fallback_needed: bool               # 是否需要回退到其他模式（avg_daily_amount <= 0）
    consecutive_days: int               # 连续满足条件的天数
    latest_ratio: float                 # 最近一日净流入占比（%）
    avg_daily_amount: float             # 日均成交额（万元）
    relative_threshold_pct: float       # 相对阈值百分比
    required_consecutive: int           # 要求连续天数


@dataclass
class LargeOrderSignal:
    """大单成交占比信号"""
    signal: bool                        # 是否生成信号
    large_order_ratio: float            # 大单成交占比 %
    threshold: float                    # 阈值 %


@dataclass
class SectorResonanceResult:
    """板块共振筛选结果"""
    passed: bool
    sector_name: str
    sector_rank: int                    # 板块涨幅排名
    is_bullish: bool                    # 板块是否多头趋势
    top_n: int                          # 排名阈值


# ---------------------------------------------------------------------------
# 换手率区间筛选
# ---------------------------------------------------------------------------

def check_turnover_rate(
    turnover_rate: float,
    min_rate: float = DEFAULT_TURNOVER_MIN,
    max_rate: float = DEFAULT_TURNOVER_MAX,
) -> TurnoverCheckResult:
    """
    筛选换手率是否在 [min_rate, max_rate] 区间内（需求 6.1）。

    Args:
        turnover_rate: 当日换手率（%）
        min_rate: 下限（默认 3%）
        max_rate: 上限（默认 15%）

    Returns:
        TurnoverCheckResult
    """
    passed = min_rate <= turnover_rate <= max_rate
    return TurnoverCheckResult(
        passed=passed,
        turnover_rate=turnover_rate,
        min_threshold=min_rate,
        max_threshold=max_rate,
    )


# ---------------------------------------------------------------------------
# 量价背离检测
# ---------------------------------------------------------------------------

def detect_volume_price_divergence(
    closes: list[float],
    volumes: list[int],
    highs: list[float] | None = None,
    lookback: int = 5,
) -> DivergenceCheckResult:
    """
    检测量价背离（需求 6.2）。

    背离类型：
    1. 价涨量缩：近期价格上涨但成交量下降
    2. 价跌量增：近期价格下跌但成交量异常放大
    3. 高位放量滞涨：价格处于近期高位，成交量放大但价格不涨

    算法：比较最近一日与前 lookback 日均值的变化方向。

    Args:
        closes: 收盘价序列（按时间升序）
        volumes: 成交量序列
        highs: 最高价序列（用于高位判断，可选）
        lookback: 回看天数（默认 5）

    Returns:
        DivergenceCheckResult
    """
    n = len(closes)
    if n < lookback + 1 or len(volumes) < n:
        return DivergenceCheckResult(
            has_divergence=False,
            divergence_type=DivergenceType.NONE,
            price_change_pct=0.0,
            volume_change_pct=0.0,
        )

    last = n - 1

    # 计算前 lookback 日的均价和均量（不含当日）
    prev_start = last - lookback
    avg_price = sum(closes[prev_start:last]) / lookback
    avg_volume = sum(volumes[prev_start:last]) / lookback

    if avg_price <= 0 or avg_volume <= 0:
        return DivergenceCheckResult(
            has_divergence=False,
            divergence_type=DivergenceType.NONE,
            price_change_pct=0.0,
            volume_change_pct=0.0,
        )

    price_change_pct = ((closes[last] - avg_price) / avg_price) * 100.0
    volume_change_pct = ((volumes[last] - avg_volume) / avg_volume) * 100.0

    # 高位放量滞涨检测
    if highs is not None and len(highs) >= n:
        recent_high = max(highs[prev_start:last])
        if recent_high > 0:
            # 当前价格接近近期高位（在 2% 以内）
            near_high = (closes[last] >= recent_high * 0.98)
            # 放量（成交量增加 > 50%）但价格涨幅 < 1%
            heavy_volume = volume_change_pct > 50.0
            stagnant_price = abs(price_change_pct) < 1.0
            if near_high and heavy_volume and stagnant_price:
                return DivergenceCheckResult(
                    has_divergence=True,
                    divergence_type=DivergenceType.HIGH_STAGNATION,
                    price_change_pct=price_change_pct,
                    volume_change_pct=volume_change_pct,
                )

    # 价涨量缩：价格上涨 > 2% 但成交量下降 > 20%
    if price_change_pct > 2.0 and volume_change_pct < -20.0:
        return DivergenceCheckResult(
            has_divergence=True,
            divergence_type=DivergenceType.PRICE_UP_VOLUME_DOWN,
            price_change_pct=price_change_pct,
            volume_change_pct=volume_change_pct,
        )

    # 价跌量增：价格下跌 > 2% 但成交量增加 > 50%
    if price_change_pct < -2.0 and volume_change_pct > 50.0:
        return DivergenceCheckResult(
            has_divergence=True,
            divergence_type=DivergenceType.PRICE_DOWN_VOLUME_UP,
            price_change_pct=price_change_pct,
            volume_change_pct=volume_change_pct,
        )

    return DivergenceCheckResult(
        has_divergence=False,
        divergence_type=DivergenceType.NONE,
        price_change_pct=price_change_pct,
        volume_change_pct=volume_change_pct,
    )


# ---------------------------------------------------------------------------
# 日均成交额过滤
# ---------------------------------------------------------------------------

def check_avg_daily_amount(
    amounts: list[float],
    period: int = DEFAULT_AVG_AMOUNT_PERIOD,
    threshold: float = DEFAULT_MIN_AVG_AMOUNT,
) -> AvgAmountCheckResult:
    """
    检查近 N 日日均成交额是否 >= 阈值（需求 6.6）。

    Args:
        amounts: 每日成交额序列（万元，按时间升序）
        period: 计算周期（默认 20 日）
        threshold: 最低日均成交额（默认 5000 万）

    Returns:
        AvgAmountCheckResult
    """
    n = len(amounts)
    if n == 0:
        return AvgAmountCheckResult(
            passed=False,
            avg_daily_amount=0.0,
            threshold=threshold,
        )

    # 取最近 period 日
    window = amounts[-period:] if n >= period else amounts
    avg = sum(window) / len(window)

    return AvgAmountCheckResult(
        passed=avg >= threshold,
        avg_daily_amount=avg,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 主力资金净流入信号
# ---------------------------------------------------------------------------

def check_money_flow_signal(
    daily_inflows: list[float],
    threshold: float = DEFAULT_MONEY_FLOW_THRESHOLD,
    consecutive: int = DEFAULT_MONEY_FLOW_CONSECUTIVE,
) -> MoneyFlowSignal:
    """
    检测主力资金净流入信号（需求 6.3）。

    信号条件：主力资金单日净流入 >= threshold 且连续 consecutive 日。

    Args:
        daily_inflows: 每日主力资金净流入序列（万元，按时间升序）
        threshold: 单日净流入阈值（默认 1000 万）
        consecutive: 连续天数要求（默认 2 日）

    Returns:
        MoneyFlowSignal
    """
    n = len(daily_inflows)
    if n == 0:
        return MoneyFlowSignal(
            signal=False,
            consecutive_days=0,
            latest_inflow=0.0,
            threshold=threshold,
            required_consecutive=consecutive,
        )

    # 从末尾向前计算连续满足条件的天数
    count = 0
    for i in range(n - 1, -1, -1):
        if daily_inflows[i] >= threshold:
            count += 1
        else:
            break

    signal = count >= consecutive

    return MoneyFlowSignal(
        signal=signal,
        consecutive_days=count,
        latest_inflow=daily_inflows[-1],
        threshold=threshold,
        required_consecutive=consecutive,
    )


# ---------------------------------------------------------------------------
# 相对阈值模式的资金流信号
# ---------------------------------------------------------------------------

def check_money_flow_signal_relative(
    daily_inflows: list[float],
    daily_amounts: list[float],
    relative_threshold_pct: float = 5.0,
    consecutive: int = DEFAULT_MONEY_FLOW_CONSECUTIVE,
    amount_period: int = DEFAULT_AVG_AMOUNT_PERIOD,
) -> RelativeMoneyFlowSignal:
    """
    相对阈值模式的资金流信号检测（纯函数）。

    信号条件：net_inflow / avg_daily_amount >= relative_threshold_pct%
    连续 consecutive 天满足条件时触发信号。

    当 avg_daily_amount <= 0 时返回 signal=False 并标记 fallback_needed=True，
    由调用方决定回退策略。

    Args:
        daily_inflows: 每日主力资金净流入序列（万元，按时间升序）
        daily_amounts: 每日成交额序列（万元，按时间升序）
        relative_threshold_pct: 相对阈值百分比（默认 5.0，即 5%）
        consecutive: 连续天数要求（默认 2 日）
        amount_period: 日均成交额计算周期（默认 20 日）

    Returns:
        RelativeMoneyFlowSignal
    """
    n_inflows = len(daily_inflows)
    n_amounts = len(daily_amounts)

    # 数据不足时返回无信号
    if n_inflows == 0 or n_amounts == 0:
        return RelativeMoneyFlowSignal(
            signal=False,
            fallback_needed=True,
            consecutive_days=0,
            latest_ratio=0.0,
            avg_daily_amount=0.0,
            relative_threshold_pct=relative_threshold_pct,
            required_consecutive=consecutive,
        )

    # 计算日均成交额（取最近 amount_period 日）
    window = daily_amounts[-amount_period:] if n_amounts >= amount_period else daily_amounts
    avg_daily_amount = sum(window) / len(window)

    # avg_daily_amount <= 0 时需要回退
    if avg_daily_amount <= 0:
        return RelativeMoneyFlowSignal(
            signal=False,
            fallback_needed=True,
            consecutive_days=0,
            latest_ratio=0.0,
            avg_daily_amount=avg_daily_amount,
            relative_threshold_pct=relative_threshold_pct,
            required_consecutive=consecutive,
        )

    # 从末尾向前计算连续满足相对阈值条件的天数
    threshold_ratio = relative_threshold_pct / 100.0
    count = 0
    for i in range(n_inflows - 1, -1, -1):
        ratio = daily_inflows[i] / avg_daily_amount
        if ratio >= threshold_ratio:
            count += 1
        else:
            break

    signal = count >= consecutive

    # 计算最近一日的净流入占比（%）
    latest_ratio = (daily_inflows[-1] / avg_daily_amount) * 100.0

    return RelativeMoneyFlowSignal(
        signal=signal,
        fallback_needed=False,
        consecutive_days=count,
        latest_ratio=latest_ratio,
        avg_daily_amount=avg_daily_amount,
        relative_threshold_pct=relative_threshold_pct,
        required_consecutive=consecutive,
    )


# ---------------------------------------------------------------------------
# 大单成交占比信号
# ---------------------------------------------------------------------------

def check_large_order_signal(
    large_order_ratio: float,
    threshold: float = DEFAULT_LARGE_ORDER_RATIO_THRESHOLD,
) -> LargeOrderSignal:
    """
    检测大单成交占比信号（需求 6.4）。

    信号条件：大单成交占比 > threshold。

    Args:
        large_order_ratio: 大单成交占比（%）
        threshold: 阈值（默认 30%）

    Returns:
        LargeOrderSignal
    """
    return LargeOrderSignal(
        signal=large_order_ratio > threshold,
        large_order_ratio=large_order_ratio,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 板块共振筛选
# ---------------------------------------------------------------------------

def check_sector_resonance(
    sector_name: str,
    sector_rank: int,
    sector_is_bullish: bool,
    top_n: int = DEFAULT_SECTOR_TOP_N,
) -> SectorResonanceResult:
    """
    板块共振筛选（需求 6.5）。

    通过条件：板块涨幅排名 <= top_n 且板块处于多头趋势。

    Args:
        sector_name: 板块名称
        sector_rank: 板块涨幅排名（1 = 最强）
        sector_is_bullish: 板块是否处于多头趋势
        top_n: 排名阈值（默认前 30）

    Returns:
        SectorResonanceResult
    """
    passed = sector_rank <= top_n and sector_is_bullish
    return SectorResonanceResult(
        passed=passed,
        sector_name=sector_name,
        sector_rank=sector_rank,
        is_bullish=sector_is_bullish,
        top_n=top_n,
    )
