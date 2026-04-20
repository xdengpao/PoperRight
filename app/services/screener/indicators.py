"""
技术指标选股模块（Technical Indicators Screener）

提供：
- calculate_macd: MACD 指标计算（DIF、DEA、MACD 柱）
- detect_macd_signal: MACD 多头信号识别
- calculate_boll: 布林带指标计算（上轨、中轨、下轨）
- detect_boll_signal: BOLL 突破信号识别
- calculate_rsi: RSI 相对强弱指数计算
- detect_rsi_signal: RSI 强势信号识别
- calculate_dma: DMA 平行线差指标计算

对应需求：
- 需求 4.1：集成 MACD、BOLL、RSI、DMA 四种技术指标，所有参数支持自定义
- 需求 4.2：MACD 金叉信号（DIF/DEA 零轴上方 + DIF 上穿 DEA + 红柱放大 + DEA 向上）
- 需求 4.3：BOLL 突破信号（站稳中轨 + 触碰上轨 + 开口向上）
- 需求 4.4：RSI 强势信号（RSI 在 [50, 80] 且无超买背离）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.schemas import SignalStrength


# ---------------------------------------------------------------------------
# 默认参数
# ---------------------------------------------------------------------------

# MACD 默认参数
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9

# BOLL 默认参数
DEFAULT_BOLL_PERIOD = 20
DEFAULT_BOLL_STD_DEV = 2.0

# RSI 默认参数
DEFAULT_RSI_PERIOD = 14

# DMA 默认参数
DEFAULT_DMA_SHORT = 10
DEFAULT_DMA_LONG = 50
DEFAULT_DMA_SIGNAL = 10


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class MACDResult:
    """MACD 计算结果"""
    dif: list[float]       # DIF 线 = EMA(fast) - EMA(slow)
    dea: list[float]       # DEA 线 = EMA(DIF, signal)
    macd: list[float]      # MACD 柱 = 2 * (DIF - DEA)
    signal: bool = False   # 是否生成多头信号


@dataclass
class BOLLResult:
    """布林带计算结果"""
    upper: list[float]     # 上轨
    middle: list[float]    # 中轨（MA）
    lower: list[float]     # 下轨
    signal: bool = False   # 是否生成突破信号


@dataclass
class RSIResult:
    """RSI 计算结果"""
    values: list[float]    # RSI 值序列
    signal: bool = False   # 是否生成强势信号


@dataclass
class DMAResult:
    """DMA 计算结果"""
    dma: list[float]       # DMA 线 = MA(short) - MA(long)
    ama: list[float]       # AMA 线 = MA(DMA, signal)


@dataclass
class MACDSignalResult:
    """MACD 信号检测结构化结果（需求 1.4）

    包含信号判定、强度等级、信号类型以及原始 MACD 计算数据。
    """
    signal: bool                          # 是否生成信号
    strength: SignalStrength              # 信号强度
    signal_type: str                      # "above_zero" | "below_zero_second" | "none"
    dif: list[float]                      # DIF 线
    dea: list[float]                      # DEA 线
    macd: list[float]                     # MACD 柱


@dataclass
class BOLLSignalResult:
    """BOLL 信号检测结构化结果（需求 2.4）

    包含中轨突破信号、接近上轨风险提示、站稳天数以及原始布林带数据。
    """
    signal: bool                          # 中轨突破 + 站稳信号
    near_upper_band: bool                 # 接近上轨风险提示
    hold_days: int                        # 连续站稳中轨天数
    upper: list[float]                    # 上轨
    middle: list[float]                   # 中轨
    lower: list[float]                    # 下轨


@dataclass
class RSISignalResult:
    """RSI 信号检测结构化结果（需求 3.4）

    包含信号判定、当前 RSI 值、连续上升天数以及原始 RSI 值序列。
    """
    signal: bool                          # 是否生成强势信号
    current_rsi: float                    # 当前 RSI 值
    consecutive_rising: int               # 连续上升天数
    values: list[float]                   # RSI 值序列


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _ema(data: list[float], period: int) -> list[float]:
    """
    计算指数移动平均线（EMA）。

    EMA_t = close_t * k + EMA_{t-1} * (1 - k)，其中 k = 2 / (period + 1)。
    前 period-1 个值为 NaN，第 period-1 个值用前 period 个数据的 SMA 初始化。

    Args:
        data: 数值序列
        period: EMA 周期

    Returns:
        与 data 等长的 EMA 值列表
    """
    n = len(data)
    if period <= 0 or n == 0:
        return [float("nan")] * n

    result = [float("nan")] * n

    if n < period:
        return result

    # 用前 period 个值的 SMA 作为初始 EMA
    sma = sum(data[:period]) / period
    result[period - 1] = sma

    k = 2.0 / (period + 1)
    for i in range(period, n):
        result[i] = data[i] * k + result[i - 1] * (1 - k)

    return result


def _sma(data: list[float], period: int) -> list[float]:
    """
    计算简单移动平均线（SMA）。

    Args:
        data: 数值序列（可含 NaN）
        period: 均线周期

    Returns:
        与 data 等长的 SMA 值列表，数据不足处为 NaN
    """
    n = len(data)
    if period <= 0 or n == 0:
        return [float("nan")] * n

    result = [float("nan")] * n

    # 收集有效值并用滑动窗口计算
    # 对于含 NaN 的输入，需要找到连续有效段
    # 简化处理：跳过 NaN 前缀，从第一个有效值开始
    valid_start = 0
    for i in range(n):
        if not math.isnan(data[i]):
            valid_start = i
            break
    else:
        return result  # 全部 NaN

    # 从 valid_start 开始，需要 period 个有效值
    count = 0
    window_sum = 0.0
    for i in range(valid_start, n):
        if math.isnan(data[i]):
            # 遇到 NaN 重置
            count = 0
            window_sum = 0.0
            continue

        count += 1
        window_sum += data[i]

        if count > period:
            # 滑出窗口最早的有效值
            # 向前找 period 个位置前的值
            remove_idx = i - period
            while remove_idx >= valid_start and math.isnan(data[remove_idx]):
                remove_idx -= 1
            if remove_idx >= valid_start:
                window_sum -= data[remove_idx]
                count -= 1

        if count >= period:
            result[i] = window_sum / period

    return result


def _simple_sma(data: list[float], period: int) -> list[float]:
    """
    计算简单移动平均线（SMA），假设输入不含 NaN（或 NaN 仅在前缀）。

    用于对 DMA 等已计算序列做二次平均。
    """
    n = len(data)
    if period <= 0 or n == 0:
        return [float("nan")] * n

    result = [float("nan")] * n

    # 找到第一个非 NaN 位置
    start = -1
    for i in range(n):
        if not math.isnan(data[i]):
            start = i
            break

    if start < 0 or (n - start) < period:
        return result

    window_sum = sum(data[start : start + period])
    result[start + period - 1] = window_sum / period

    for i in range(start + period, n):
        if math.isnan(data[i]):
            break
        window_sum += data[i] - data[i - period]
        result[i] = window_sum / period

    return result


# ---------------------------------------------------------------------------
# MACD 指标
# ---------------------------------------------------------------------------

def calculate_macd(
    closes: list[float],
    fast_period: int = DEFAULT_MACD_FAST,
    slow_period: int = DEFAULT_MACD_SLOW,
    signal_period: int = DEFAULT_MACD_SIGNAL,
) -> MACDResult:
    """
    计算 MACD 指标。

    DIF = EMA(fast) - EMA(slow)
    DEA = EMA(DIF, signal)
    MACD 柱 = 2 * (DIF - DEA)

    Args:
        closes: 收盘价序列
        fast_period: 快线周期，默认 12
        slow_period: 慢线周期，默认 26
        signal_period: 信号线周期，默认 9

    Returns:
        MACDResult
    """
    n = len(closes)
    if n == 0:
        return MACDResult(dif=[], dea=[], macd=[])

    ema_fast = _ema(closes, fast_period)
    ema_slow = _ema(closes, slow_period)

    # DIF = EMA(fast) - EMA(slow)
    dif = [float("nan")] * n
    for i in range(n):
        if not math.isnan(ema_fast[i]) and not math.isnan(ema_slow[i]):
            dif[i] = ema_fast[i] - ema_slow[i]

    # DEA = EMA(DIF, signal_period)
    # 需要从 DIF 有效值开始计算 EMA
    dea = _ema_from_valid(dif, signal_period)

    # MACD 柱 = 2 * (DIF - DEA)
    macd_bar = [float("nan")] * n
    for i in range(n):
        if not math.isnan(dif[i]) and not math.isnan(dea[i]):
            macd_bar[i] = 2.0 * (dif[i] - dea[i])

    return MACDResult(dif=dif, dea=dea, macd=macd_bar)


def _ema_from_valid(data: list[float], period: int) -> list[float]:
    """
    对含 NaN 前缀的序列计算 EMA。
    从第一个有效值开始，用前 period 个有效值的 SMA 初始化。
    """
    n = len(data)
    result = [float("nan")] * n

    if period <= 0 or n == 0:
        return result

    # 找到第一个有效值
    start = -1
    for i in range(n):
        if not math.isnan(data[i]):
            start = i
            break

    if start < 0:
        return result

    valid_count = n - start
    if valid_count < period:
        return result

    # 用前 period 个有效值的 SMA 初始化
    sma_init = sum(data[start : start + period]) / period
    init_idx = start + period - 1
    result[init_idx] = sma_init

    k = 2.0 / (period + 1)
    for i in range(init_idx + 1, n):
        if math.isnan(data[i]):
            break
        result[i] = data[i] * k + result[i - 1] * (1 - k)

    return result


def _count_below_zero_golden_crosses(
    dif: list[float],
    dea: list[float],
    lookback: int = 60,
) -> int:
    """
    统计最近 lookback 天内零轴下方金叉次数（纯函数）。

    金叉定义：DIF[i-1] <= DEA[i-1] 且 DIF[i] > DEA[i] 且 DIF[i] < 0。
    仅统计 lookback 窗口内（不含最后一天）的历史金叉，最后一天的金叉由调用方判断。

    Args:
        dif: DIF 线序列
        dea: DEA 线序列
        lookback: 回溯天数，默认 60

    Returns:
        零轴下方金叉次数（不含最后一天）

    需求: 1.2, 1.5
    """
    n = len(dif)
    if n < 2:
        return 0

    count = 0
    # 回溯窗口起始位置（不含最后一天，最后一天由调用方判断）
    start = max(1, n - 1 - lookback)
    end = n - 1  # 不含最后一天

    for i in range(start, end):
        if (
            not math.isnan(dif[i])
            and not math.isnan(dea[i])
            and not math.isnan(dif[i - 1])
            and not math.isnan(dea[i - 1])
            and dif[i - 1] <= dea[i - 1]
            and dif[i] > dea[i]
            and dif[i] < 0
        ):
            count += 1

    return count


def detect_macd_signal(
    closes: list[float],
    fast_period: int = DEFAULT_MACD_FAST,
    slow_period: int = DEFAULT_MACD_SLOW,
    signal_period: int = DEFAULT_MACD_SIGNAL,
    macd_result: MACDResult | None = None,
) -> MACDSignalResult:
    """
    检测 MACD 多头信号（需求 1.1 ~ 1.5）。

    信号分类：
    - 零轴上方金叉：DIF > 0, DEA > 0, DIF 上穿 DEA, MACD 红柱放大
      → signal=True, strength=STRONG, signal_type="above_zero"
    - 零轴下方二次金叉：最近 60 天内已有一次零轴下方金叉，当前再次金叉
      → signal=True, strength=WEAK, signal_type="below_zero_second"
    - 零轴下方首次金叉：signal=False

    DEA 趋势修饰符：DEA[last] > DEA[prev] 时 strength 提升一级
    （WEAK→MEDIUM, MEDIUM→STRONG, STRONG 不变）。

    Args:
        closes: 收盘价序列
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期
        macd_result: 预计算的 MACD 结果（可选）

    Returns:
        MACDSignalResult（含 signal、strength、signal_type 字段）
    """
    if macd_result is None:
        macd_result = calculate_macd(closes, fast_period, slow_period, signal_period)

    dif = macd_result.dif
    dea = macd_result.dea
    macd_bar = macd_result.macd
    n = len(dif)

    # 默认无信号结果
    no_signal = MACDSignalResult(
        signal=False,
        strength=SignalStrength.WEAK,
        signal_type="none",
        dif=dif,
        dea=dea,
        macd=macd_bar,
    )

    if n < 2:
        return no_signal

    last = n - 1
    prev = n - 2

    # 数据有效性检查
    if any(
        math.isnan(v)
        for v in [dif[last], dea[last], dif[prev], dea[prev],
                  macd_bar[last], macd_bar[prev]]
    ):
        return no_signal

    # 金叉判定：DIF 上穿 DEA
    cond_golden_cross = dif[prev] <= dea[prev] and dif[last] > dea[last]

    if not cond_golden_cross:
        return no_signal

    # DEA 趋势向上（用于强度修饰）
    dea_trending_up = dea[last] > dea[prev]

    # ── 零轴上方金叉 ──
    cond_above_zero = dif[last] > 0 and dea[last] > 0
    cond_bar_expanding = macd_bar[last] > macd_bar[prev] and macd_bar[last] > 0

    if cond_above_zero and cond_bar_expanding:
        strength = SignalStrength.STRONG
        # STRONG 不变，DEA 修饰符不再提升
        return MACDSignalResult(
            signal=True,
            strength=strength,
            signal_type="above_zero",
            dif=dif,
            dea=dea,
            macd=macd_bar,
        )

    # ── 零轴下方金叉 ──
    if dif[last] < 0:
        # 统计历史零轴下方金叉次数（不含当前这次）
        history_count = _count_below_zero_golden_crosses(dif, dea, lookback=60)

        if history_count >= 1:
            # 二次（或更多次）金叉 → 信号触发
            base_strength = SignalStrength.WEAK
            # DEA 趋势修饰符
            if dea_trending_up:
                strength = SignalStrength.MEDIUM
            else:
                strength = base_strength

            return MACDSignalResult(
                signal=True,
                strength=strength,
                signal_type="below_zero_second",
                dif=dif,
                dea=dea,
                macd=macd_bar,
            )

        # 首次金叉 → 不生成信号
        return no_signal

    # 其他情况（如 DIF >= 0 但不满足零轴上方金叉的红柱放大条件）
    return no_signal


# ---------------------------------------------------------------------------
# BOLL 指标
# ---------------------------------------------------------------------------

def calculate_boll(
    closes: list[float],
    period: int = DEFAULT_BOLL_PERIOD,
    std_dev: float = DEFAULT_BOLL_STD_DEV,
) -> BOLLResult:
    """
    计算布林带指标。

    中轨 = MA(period)
    上轨 = 中轨 + std_dev × 标准差
    下轨 = 中轨 - std_dev × 标准差

    Args:
        closes: 收盘价序列
        period: 均线周期，默认 20
        std_dev: 标准差倍数，默认 2.0

    Returns:
        BOLLResult
    """
    n = len(closes)
    if n == 0:
        return BOLLResult(upper=[], middle=[], lower=[])

    middle = [float("nan")] * n
    upper = [float("nan")] * n
    lower = [float("nan")] * n

    if n < period:
        return BOLLResult(upper=upper, middle=middle, lower=lower)

    # 计算初始窗口
    window_sum = sum(closes[:period])
    ma_val = window_sum / period
    middle[period - 1] = ma_val

    # 标准差
    variance = sum((c - ma_val) ** 2 for c in closes[:period]) / period
    std = math.sqrt(variance)
    upper[period - 1] = ma_val + std_dev * std
    lower[period - 1] = ma_val - std_dev * std

    # 滑动窗口
    for i in range(period, n):
        window_sum += closes[i] - closes[i - period]
        ma_val = window_sum / period
        middle[i] = ma_val

        variance = sum(
            (closes[j] - ma_val) ** 2 for j in range(i - period + 1, i + 1)
        ) / period
        std = math.sqrt(variance)
        upper[i] = ma_val + std_dev * std
        lower[i] = ma_val - std_dev * std

    return BOLLResult(upper=upper, middle=middle, lower=lower)


def _count_hold_days_above_middle(
    closes: list[float],
    middle: list[float],
) -> int:
    """
    从最新一天向前扫描，统计连续收盘价 > 中轨的天数（纯函数）。

    Args:
        closes: 收盘价序列
        middle: 布林带中轨序列

    Returns:
        连续站稳中轨天数（从最新一天开始向前计数）

    需求: 2.4
    """
    n = len(closes)
    count = 0
    for i in range(n - 1, -1, -1):
        if math.isnan(middle[i]):
            break
        if closes[i] > middle[i]:
            count += 1
        else:
            break
    return count


def detect_boll_signal(
    closes: list[float],
    period: int = DEFAULT_BOLL_PERIOD,
    std_dev: float = DEFAULT_BOLL_STD_DEV,
    boll_result: BOLLResult | None = None,
) -> BOLLSignalResult:
    """
    检测 BOLL 突破信号（需求 2.1 ~ 2.4）。

    信号条件：
    - 主信号：当日收盘价 > 中轨 AND 前一日收盘价 > 前一日中轨（连续 2 日站稳）→ signal=True
    - 风险提示：当日收盘价 >= 上轨 × 0.98 → near_upper_band=True（独立于 signal）
    - hold_days：从最新一天向前扫描连续收盘价 > 中轨的天数

    移除原有"触碰上轨"作为买入条件的逻辑。

    Args:
        closes: 收盘价序列
        period: 均线周期
        std_dev: 标准差倍数
        boll_result: 预计算的 BOLL 结果（可选）

    Returns:
        BOLLSignalResult（含 signal、near_upper_band、hold_days 字段）
    """
    if boll_result is None:
        boll_result = calculate_boll(closes, period, std_dev)

    n = len(closes)
    up = boll_result.upper
    mid = boll_result.middle
    low = boll_result.lower

    # 默认无信号结果
    no_signal = BOLLSignalResult(
        signal=False,
        near_upper_band=False,
        hold_days=0,
        upper=up,
        middle=mid,
        lower=low,
    )

    if n < 2:
        return no_signal

    last = n - 1
    prev = n - 2

    # 数据有效性检查：至少最后两天的中轨和最后一天的上轨需要有效
    if math.isnan(mid[last]) or math.isnan(mid[prev]) or math.isnan(up[last]):
        return no_signal

    # ── 主信号条件：连续 2 日站稳中轨 ──
    cond_today_above = closes[last] > mid[last]
    cond_prev_above = closes[prev] > mid[prev]
    signal = cond_today_above and cond_prev_above

    # ── 风险提示：接近上轨（独立于 signal） ──
    near_upper_band = closes[last] >= up[last] * 0.98

    # ── hold_days：连续站稳中轨天数 ──
    hold_days = _count_hold_days_above_middle(closes, mid)

    return BOLLSignalResult(
        signal=signal,
        near_upper_band=near_upper_band,
        hold_days=hold_days,
        upper=up,
        middle=mid,
        lower=low,
    )


# ---------------------------------------------------------------------------
# RSI 指标
# ---------------------------------------------------------------------------

def calculate_rsi(
    closes: list[float],
    period: int = DEFAULT_RSI_PERIOD,
) -> RSIResult:
    """
    计算 RSI 相对强弱指数。

    RS = avg_gain / avg_loss（Wilder 平滑法）
    RSI = 100 - 100 / (1 + RS)

    初始 avg_gain/avg_loss 用前 period 个变化的简单平均。
    后续用指数平滑：avg = (prev_avg * (period-1) + current) / period。

    Args:
        closes: 收盘价序列
        period: RSI 周期，默认 14

    Returns:
        RSIResult
    """
    n = len(closes)
    if n == 0:
        return RSIResult(values=[])

    values = [float("nan")] * n

    if n < period + 1:
        return RSIResult(values=values)

    # 计算价格变化
    changes = [0.0] * n
    for i in range(1, n):
        changes[i] = closes[i] - closes[i - 1]

    # 初始 avg_gain / avg_loss（前 period 个变化的简单平均）
    gains = [max(changes[i], 0.0) for i in range(1, period + 1)]
    losses = [abs(min(changes[i], 0.0)) for i in range(1, period + 1)]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        values[period] = 100.0 - 100.0 / (1.0 + rs)

    # Wilder 平滑
    for i in range(period + 1, n):
        gain = max(changes[i], 0.0)
        loss = abs(min(changes[i], 0.0))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            values[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            values[i] = 100.0 - 100.0 / (1.0 + rs)

    return RSIResult(values=values)


def _count_consecutive_rising(values: list[float], end_idx: int) -> int:
    """
    从 end_idx 向前统计 RSI 连续严格递增的天数（纯函数）。

    从 end_idx 开始，向前检查 values[i] > values[i-1]，
    直到条件不满足或遇到 NaN 为止。

    Args:
        values: RSI 值序列
        end_idx: 结束索引（含）

    Returns:
        连续严格递增天数（不含起始天本身，即比较次数）
    """
    count = 0
    for i in range(end_idx, 0, -1):
        if math.isnan(values[i]) or math.isnan(values[i - 1]):
            break
        if values[i] > values[i - 1]:
            count += 1
        else:
            break
    return count


def detect_rsi_signal(
    closes: list[float],
    period: int = DEFAULT_RSI_PERIOD,
    lower_bound: float = 55.0,
    upper_bound: float = 75.0,
    rising_days: int = 3,
    rsi_result: RSIResult | None = None,
) -> RSISignalResult:
    """
    检测 RSI 强势信号（需求 3.1 ~ 3.5）。

    信号条件：
    1. RSI 值在 [lower_bound, upper_bound] 区间内
    2. 最近 rising_days 天 RSI 严格递增
    3. 无超买背离（价格创新高时 RSI 也应创新高，否则为背离）

    数据不足时（可用天数 < rising_days + period）返回 signal=False。

    Args:
        closes: 收盘价序列
        period: RSI 周期，默认 14
        lower_bound: 强势区间下限，默认 55.0（原 50.0）
        upper_bound: 强势区间上限，默认 75.0（原 80.0）
        rising_days: 连续上升天数要求，默认 3
        rsi_result: 预计算的 RSI 结果（可选）

    Returns:
        RSISignalResult（含 signal、current_rsi、consecutive_rising、values 字段）
    """
    if rsi_result is None:
        rsi_result = calculate_rsi(closes, period)

    n = len(closes)
    values = rsi_result.values

    # 默认无信号结果
    def _no_signal(current_rsi: float = 0.0, consecutive_rising: int = 0) -> RSISignalResult:
        return RSISignalResult(
            signal=False,
            current_rsi=current_rsi,
            consecutive_rising=consecutive_rising,
            values=values,
        )

    # 数据不足检查：可用天数 < rising_days + period
    if n < rising_days + period:
        return _no_signal()

    last = n - 1
    if math.isnan(values[last]):
        return _no_signal()

    current_rsi = values[last]

    # 计算连续上升天数
    consecutive_rising = _count_consecutive_rising(values, last)

    # 条件 1：RSI 在 [lower_bound, upper_bound] 区间内
    cond_range = lower_bound <= current_rsi <= upper_bound

    # 条件 2：最近 rising_days 天 RSI 严格递增
    cond_rising = consecutive_rising >= rising_days

    # 条件 3：无超买背离
    # 检查最近 period 天内是否存在背离：价格创新高但 RSI 未创新高
    lookback = min(period, last)
    cond_no_divergence = True

    if lookback >= 2:
        # 找 lookback 窗口内的价格最高点和对应 RSI
        window_start = last - lookback
        price_max_idx = window_start
        for i in range(window_start, last):
            if not math.isnan(values[i]) and closes[i] >= closes[price_max_idx]:
                price_max_idx = i

        # 如果当前价格 >= 窗口内最高价，但 RSI 低于该点的 RSI → 背离
        if (closes[last] >= closes[price_max_idx]
                and price_max_idx != last
                and not math.isnan(values[price_max_idx])
                and values[last] < values[price_max_idx]):
            cond_no_divergence = False

    signal = cond_range and cond_rising and cond_no_divergence

    return RSISignalResult(
        signal=signal,
        current_rsi=current_rsi,
        consecutive_rising=consecutive_rising,
        values=values,
    )


# ---------------------------------------------------------------------------
# DMA 指标
# ---------------------------------------------------------------------------

def calculate_dma(
    closes: list[float],
    short_period: int = DEFAULT_DMA_SHORT,
    long_period: int = DEFAULT_DMA_LONG,
    signal_period: int = DEFAULT_DMA_SIGNAL,
) -> DMAResult:
    """
    计算 DMA 平行线差指标。

    DMA = MA(short) - MA(long)
    AMA = MA(DMA, signal)

    Args:
        closes: 收盘价序列
        short_period: 短期均线周期，默认 10
        long_period: 长期均线周期，默认 50
        signal_period: 信号线周期，默认 10

    Returns:
        DMAResult
    """
    n = len(closes)
    if n == 0:
        return DMAResult(dma=[], ama=[])

    # 计算短期和长期 SMA
    from app.services.screener.ma_trend import calculate_ma

    ma_short = calculate_ma(closes, short_period)
    ma_long = calculate_ma(closes, long_period)

    # DMA = MA(short) - MA(long)
    dma = [float("nan")] * n
    for i in range(n):
        if not math.isnan(ma_short[i]) and not math.isnan(ma_long[i]):
            dma[i] = ma_short[i] - ma_long[i]

    # AMA = SMA(DMA, signal_period)
    ama = _simple_sma(dma, signal_period)

    return DMAResult(dma=dma, ama=ama)
