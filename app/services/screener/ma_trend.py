"""
均线趋势选股模块（MA Trend Screener）

提供：
- calculate_ma: 可配置周期的移动平均线计算
- detect_bullish_alignment: 多头排列识别
- score_ma_trend: 趋势打分算法（0-100 分）
- detect_ma_support: 均线支撑形态识别

对应需求：
- 需求 3.1：支持用户自定义均线周期，默认 5/10/20/60/120 日
- 需求 3.2：自动识别多头排列（短期 MA > 长期 MA，各均线斜率 > 0）
- 需求 3.3：趋势打分 0-100，基于排列程度、斜率、距离
- 需求 3.4：打分 >= 80 纳入初选池
- 需求 3.5：均线支撑形态识别（回调至 20/60 日均线企稳反弹）
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_MA_PERIODS: list[int] = [5, 10, 20, 60, 120]

# 趋势打分权重
_WEIGHT_ALIGNMENT = 0.40   # 排列程度权重
_WEIGHT_SLOPE = 0.30       # 斜率权重
_WEIGHT_DISTANCE = 0.30    # 价格与均线距离权重

# 均线支撑参数
_SUPPORT_TOUCH_PCT = 0.02      # 触及均线的容差（2%）
_SUPPORT_REBOUND_DAYS = 2      # 企稳反弹所需天数

# 斜率计算回看天数
_SLOPE_LOOKBACK = 5


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class MAResult:
    """单条均线计算结果"""
    period: int
    values: list[float]        # 与输入 closes 等长，前 period-1 个为 NaN


@dataclass
class BullishAlignmentResult:
    """多头排列识别结果"""
    is_aligned: bool                    # 是否完全多头排列
    aligned_pairs: int                  # 满足条件的 MA 对数
    total_pairs: int                    # 总 MA 对数
    slopes_positive: bool               # 所有均线斜率是否 > 0
    slopes: dict[int, float]            # 各周期均线斜率


@dataclass
class MATrendScore:
    """趋势打分结果"""
    score: float                        # 0-100
    alignment_score: float              # 排列程度分（0-100）
    slope_score: float                  # 斜率分（0-100）
    distance_score: float               # 距离分（0-100）
    is_bullish_aligned: bool            # 是否多头排列


@dataclass
class MASupportSignal:
    """均线支撑信号"""
    detected: bool                      # 是否检测到支撑信号
    support_ma_period: int | None       # 支撑均线周期（20 或 60）
    touch_index: int | None             # 触及均线的位置索引
    rebound_confirmed: bool             # 是否确认反弹


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def calculate_ma(
    closes: list[float],
    period: int,
) -> list[float]:
    """
    计算 N 日简单移动平均线（SMA）。

    第 t 日 N 日 MA = (closes[t-N+1] + ... + closes[t]) / N

    数据不足 N 日的位置填充 float('nan')。

    Args:
        closes: 收盘价序列（按时间升序）
        period: 均线周期

    Returns:
        与 closes 等长的 MA 值列表，前 period-1 个为 NaN
    """
    n = len(closes)
    if period <= 0:
        return [float("nan")] * n

    result = [float("nan")] * n

    if n < period:
        return result

    # 初始窗口和
    window_sum = sum(closes[:period])
    result[period - 1] = window_sum / period

    # 滑动窗口
    for i in range(period, n):
        window_sum += closes[i] - closes[i - period]
        result[i] = window_sum / period

    return result


def calculate_multi_ma(
    closes: list[float],
    periods: list[int] | None = None,
) -> dict[int, list[float]]:
    """
    批量计算多条均线。

    Args:
        closes:  收盘价序列
        periods: 均线周期列表，默认 [5, 10, 20, 60, 120]

    Returns:
        {period: ma_values} 字典
    """
    if periods is None:
        periods = DEFAULT_MA_PERIODS
    return {p: calculate_ma(closes, p) for p in periods}


def _calc_slope(ma_values: list[float], lookback: int = _SLOPE_LOOKBACK) -> float:
    """
    计算均线末端斜率（最近 lookback 天的线性回归斜率，归一化为百分比变化率）。

    返回每日平均变化率（%），如 0.5 表示每日上涨 0.5%。
    数据不足时返回 0.0。
    """
    import math

    # 收集末尾有效值
    valid = []
    for v in reversed(ma_values):
        if math.isnan(v):
            break
        valid.append(v)
        if len(valid) >= lookback:
            break

    valid.reverse()

    if len(valid) < 2:
        return 0.0

    # 简单线性回归斜率: Σ(xi - x̄)(yi - ȳ) / Σ(xi - x̄)²
    n = len(valid)
    x_mean = (n - 1) / 2.0
    y_mean = sum(valid) / n

    numerator = 0.0
    denominator = 0.0
    for i, y in enumerate(valid):
        dx = i - x_mean
        numerator += dx * (y - y_mean)
        denominator += dx * dx

    if denominator == 0 or y_mean == 0:
        return 0.0

    slope = numerator / denominator
    # 归一化为日均变化率百分比
    return (slope / y_mean) * 100.0


def detect_bullish_alignment(
    closes: list[float],
    periods: list[int] | None = None,
    ma_dict: dict[int, list[float]] | None = None,
    slope_threshold: float = 0.0,
) -> BullishAlignmentResult:
    """
    识别多头排列形态。

    多头排列条件（需求 3.2）：
    1. 短期 MA > 长期 MA（所有相邻周期对）
    2. 各均线斜率均 > slope_threshold

    Args:
        closes:  收盘价序列
        periods: 均线周期列表
        ma_dict: 预计算的均线字典（可选，避免重复计算）
        slope_threshold: 斜率阈值，默认 0.0（斜率需大于此值才视为上升）

    Returns:
        BullishAlignmentResult
    """
    import math

    if periods is None:
        periods = DEFAULT_MA_PERIODS

    if ma_dict is None:
        ma_dict = calculate_multi_ma(closes, periods)

    sorted_periods = sorted(periods)

    # 取最新一天的 MA 值
    last_idx = len(closes) - 1 if closes else -1

    if last_idx < 0:
        return BullishAlignmentResult(
            is_aligned=False, aligned_pairs=0, total_pairs=0,
            slopes_positive=False, slopes={},
        )

    # 获取各周期最新 MA 值
    latest_ma: dict[int, float] = {}
    for p in sorted_periods:
        vals = ma_dict.get(p, [])
        if last_idx < len(vals) and not math.isnan(vals[last_idx]):
            latest_ma[p] = vals[last_idx]

    # 计算各周期斜率
    slopes: dict[int, float] = {}
    for p in sorted_periods:
        vals = ma_dict.get(p, [])
        slopes[p] = _calc_slope(vals)

    # 检查排列：短期 MA > 长期 MA
    available_periods = [p for p in sorted_periods if p in latest_ma]
    total_pairs = max(len(available_periods) - 1, 0)
    aligned_pairs = 0

    for i in range(len(available_periods) - 1):
        short_p = available_periods[i]
        long_p = available_periods[i + 1]
        if latest_ma[short_p] > latest_ma[long_p]:
            aligned_pairs += 1

    # 检查斜率：所有可用均线斜率 > slope_threshold
    available_slopes = [slopes[p] for p in available_periods if p in slopes]
    slopes_positive = len(available_slopes) > 0 and all(s > slope_threshold for s in available_slopes)

    is_aligned = (
        total_pairs > 0
        and aligned_pairs == total_pairs
        and slopes_positive
    )

    return BullishAlignmentResult(
        is_aligned=is_aligned,
        aligned_pairs=aligned_pairs,
        total_pairs=total_pairs,
        slopes_positive=slopes_positive,
        slopes=slopes,
    )



def score_ma_trend(
    closes: list[float],
    periods: list[int] | None = None,
    slope_threshold: float = 0.0,
) -> MATrendScore:
    """
    计算均线趋势打分（0-100 分）。

    打分算法（需求 3.3）：
    1. 排列程度分（40%）：满足多头排列的 MA 对数占比 × 100
    2. 斜率分（30%）：各均线斜率的归一化得分（低于 slope_threshold 的斜率得 0 分）
    3. 距离分（30%）：当前价格在均线上方的程度

    Args:
        closes:  收盘价序列
        periods: 均线周期列表
        slope_threshold: 斜率阈值，低于此值的均线斜率在评分中视为 0

    Returns:
        MATrendScore（score 保证在 [0, 100]）
    """
    import math

    if periods is None:
        periods = DEFAULT_MA_PERIODS

    if not closes:
        return MATrendScore(
            score=0.0, alignment_score=0.0, slope_score=0.0,
            distance_score=0.0, is_bullish_aligned=False,
        )

    ma_dict = calculate_multi_ma(closes, periods)
    alignment = detect_bullish_alignment(closes, periods, ma_dict, slope_threshold=slope_threshold)

    # --- 1. 排列程度分 (0-100) ---
    if alignment.total_pairs > 0:
        alignment_score = (alignment.aligned_pairs / alignment.total_pairs) * 100.0
    else:
        alignment_score = 0.0

    # --- 2. 斜率分 (0-100) ---
    # 低于 slope_threshold 的斜率视为 0（不贡献分数）
    slope_values = [
        alignment.slopes[p]
        for p in sorted(periods)
        if p in alignment.slopes
    ]
    if slope_values:
        # 斜率高于阈值才贡献正分，低于阈值的视为 0
        filtered_slopes = [max(s - slope_threshold, 0.0) if s > slope_threshold else 0.0 for s in slope_values]
        avg_slope = sum(filtered_slopes) / len(filtered_slopes)
        slope_score = min(avg_slope * 100.0, 100.0)
    else:
        slope_score = 0.0

    # --- 3. 距离分 (0-100) ---
    last_idx = len(closes) - 1
    current_price = closes[last_idx]
    sorted_periods = sorted(periods)

    distance_scores = []
    for p in sorted_periods:
        vals = ma_dict.get(p, [])
        if last_idx < len(vals) and not math.isnan(vals[last_idx]):
            ma_val = vals[last_idx]
            if ma_val > 0:
                # 价格在 MA 上方的百分比距离
                pct_above = ((current_price - ma_val) / ma_val) * 100.0
                # 映射：0% → 50 分，>= 5% → 100 分，<= -5% → 0 分
                dist_score = 50.0 + pct_above * 10.0
                dist_score = max(0.0, min(100.0, dist_score))
                distance_scores.append(dist_score)

    if distance_scores:
        distance_score = sum(distance_scores) / len(distance_scores)
    else:
        distance_score = 0.0

    # --- 综合打分 ---
    raw_score = (
        alignment_score * _WEIGHT_ALIGNMENT
        + slope_score * _WEIGHT_SLOPE
        + distance_score * _WEIGHT_DISTANCE
    )

    # 确保 [0, 100]
    final_score = max(0.0, min(100.0, raw_score))

    return MATrendScore(
        score=final_score,
        alignment_score=alignment_score,
        slope_score=slope_score,
        distance_score=distance_score,
        is_bullish_aligned=alignment.is_aligned,
    )


def detect_ma_support(
    closes: list[float],
    periods: list[int] | None = None,
    support_periods: list[int] | None = None,
    touch_pct: float = _SUPPORT_TOUCH_PCT,
    rebound_days: int = _SUPPORT_REBOUND_DAYS,
) -> MASupportSignal:
    """
    识别均线支撑形态（需求 3.5）。

    均线支撑条件：
    1. 价格回调至 20 日或 60 日均线附近（在均线上下 touch_pct 范围内）
    2. 随后连续 rebound_days 天收盘价站在该均线上方

    算法：
    - 从最近的数据向前扫描，寻找"触及均线"的点
    - 确认触及后，检查后续是否企稳反弹

    Args:
        closes:          收盘价序列
        periods:         用于计算均线的周期列表
        support_periods: 用于支撑检测的均线周期，默认 [20, 60]
        touch_pct:       触及均线的容差百分比，默认 2%
        rebound_days:    企稳反弹所需天数，默认 2

    Returns:
        MASupportSignal
    """
    import math

    if periods is None:
        periods = DEFAULT_MA_PERIODS
    if support_periods is None:
        support_periods = [20, 60]

    n = len(closes)
    if n < max(support_periods, default=0) + rebound_days + 1:
        return MASupportSignal(
            detected=False, support_ma_period=None,
            touch_index=None, rebound_confirmed=False,
        )

    ma_dict = calculate_multi_ma(closes, periods)

    # 扫描窗口：从倒数第 rebound_days+1 天开始向前找触及点
    # 触及点最早可以在 max(support_periods)-1 处
    search_end = n - rebound_days - 1  # 触及点最晚位置（需要后面有足够天数确认反弹）
    search_start = max(max(support_periods, default=0) - 1, 0)

    # 从最近的触及点开始找（优先检测最近的支撑信号）
    for sp in support_periods:
        ma_vals = ma_dict.get(sp, [])
        if not ma_vals:
            continue

        # 从后向前扫描寻找触及点
        for t in range(search_end, search_start - 1, -1):
            if t >= len(ma_vals) or math.isnan(ma_vals[t]):
                continue

            ma_val = ma_vals[t]
            if ma_val <= 0:
                continue

            price = closes[t]
            # 检查是否触及均线（价格在均线附近 touch_pct 范围内）
            distance_pct = abs(price - ma_val) / ma_val
            if distance_pct > touch_pct:
                continue

            # 确认反弹：后续 rebound_days 天收盘价都在均线上方
            rebound_ok = True
            for d in range(1, rebound_days + 1):
                future_idx = t + d
                if future_idx >= n:
                    rebound_ok = False
                    break
                if future_idx >= len(ma_vals) or math.isnan(ma_vals[future_idx]):
                    rebound_ok = False
                    break
                if closes[future_idx] <= ma_vals[future_idx]:
                    rebound_ok = False
                    break

            if rebound_ok:
                return MASupportSignal(
                    detected=True,
                    support_ma_period=sp,
                    touch_index=t,
                    rebound_confirmed=True,
                )

    return MASupportSignal(
        detected=False, support_ma_period=None,
        touch_index=None, rebound_confirmed=False,
    )
