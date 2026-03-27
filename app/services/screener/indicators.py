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


def detect_macd_signal(
    closes: list[float],
    fast_period: int = DEFAULT_MACD_FAST,
    slow_period: int = DEFAULT_MACD_SLOW,
    signal_period: int = DEFAULT_MACD_SIGNAL,
    macd_result: MACDResult | None = None,
) -> MACDResult:
    """
    检测 MACD 多头信号。

    信号条件（需求 4.2）：
    1. DIF 和 DEA 均在零轴上方（> 0）
    2. DIF 上穿 DEA（金叉：前一日 DIF <= DEA，当日 DIF > DEA）
    3. MACD 红柱持续放大（当日 MACD 柱 > 前一日 MACD 柱 > 0）
    4. DEA 向上运行（当日 DEA > 前一日 DEA）

    Args:
        closes: 收盘价序列
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期
        macd_result: 预计算的 MACD 结果（可选）

    Returns:
        MACDResult（含 signal 字段）
    """
    if macd_result is None:
        macd_result = calculate_macd(closes, fast_period, slow_period, signal_period)

    n = len(macd_result.dif)
    if n < 2:
        return macd_result

    dif = macd_result.dif
    dea = macd_result.dea
    macd_bar = macd_result.macd

    # 检查最后一个有效点
    last = n - 1
    prev = n - 2

    if any(math.isnan(v) for v in [dif[last], dea[last], dif[prev], dea[prev],
                                     macd_bar[last], macd_bar[prev]]):
        return macd_result

    # 条件 1：DIF 和 DEA 均在零轴上方
    cond_above_zero = dif[last] > 0 and dea[last] > 0

    # 条件 2：DIF 上穿 DEA（金叉）
    cond_golden_cross = dif[prev] <= dea[prev] and dif[last] > dea[last]

    # 条件 3：红柱持续放大
    cond_bar_expanding = macd_bar[last] > macd_bar[prev] and macd_bar[last] > 0

    # 条件 4：DEA 向上运行
    cond_dea_up = dea[last] > dea[prev]

    signal = cond_above_zero and cond_golden_cross and cond_bar_expanding and cond_dea_up

    return MACDResult(
        dif=macd_result.dif,
        dea=macd_result.dea,
        macd=macd_result.macd,
        signal=signal,
    )


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


def detect_boll_signal(
    closes: list[float],
    period: int = DEFAULT_BOLL_PERIOD,
    std_dev: float = DEFAULT_BOLL_STD_DEV,
    boll_result: BOLLResult | None = None,
) -> BOLLResult:
    """
    检测 BOLL 突破信号。

    信号条件（需求 4.3）：
    1. 股价站稳中轨（当日收盘价 > 中轨）
    2. 向上触碰上轨（当日最高价或收盘价 >= 上轨 * 0.98，即接近上轨）
    3. 布林带开口向上（当日带宽 > 前一日带宽）

    Args:
        closes: 收盘价序列
        period: 均线周期
        std_dev: 标准差倍数
        boll_result: 预计算的 BOLL 结果（可选）

    Returns:
        BOLLResult（含 signal 字段）
    """
    if boll_result is None:
        boll_result = calculate_boll(closes, period, std_dev)

    n = len(closes)
    if n < 2:
        return boll_result

    last = n - 1
    prev = n - 2

    up = boll_result.upper
    mid = boll_result.middle
    low = boll_result.lower

    if any(math.isnan(v) for v in [up[last], mid[last], low[last],
                                     up[prev], mid[prev], low[prev]]):
        return boll_result

    # 条件 1：股价站稳中轨
    cond_above_middle = closes[last] > mid[last]

    # 条件 2：向上触碰上轨（收盘价接近或超过上轨的 98%）
    cond_touch_upper = closes[last] >= up[last] * 0.98

    # 条件 3：布林带开口向上（带宽扩大）
    bandwidth_last = up[last] - low[last]
    bandwidth_prev = up[prev] - low[prev]
    cond_opening_up = bandwidth_last > bandwidth_prev

    signal = cond_above_middle and cond_touch_upper and cond_opening_up

    return BOLLResult(
        upper=boll_result.upper,
        middle=boll_result.middle,
        lower=boll_result.lower,
        signal=signal,
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


def detect_rsi_signal(
    closes: list[float],
    period: int = DEFAULT_RSI_PERIOD,
    rsi_result: RSIResult | None = None,
) -> RSIResult:
    """
    检测 RSI 强势信号。

    信号条件（需求 4.4）：
    1. RSI 值在 [50, 80] 区间
    2. 无超买背离（价格创新高时 RSI 也应创新高，否则为背离）

    背离检测：比较最近两个局部高点，若价格新高但 RSI 未新高则为背离。
    简化实现：检查最近 N 天内价格是否创新高而 RSI 下降。

    Args:
        closes: 收盘价序列
        period: RSI 周期
        rsi_result: 预计算的 RSI 结果（可选）

    Returns:
        RSIResult（含 signal 字段）
    """
    if rsi_result is None:
        rsi_result = calculate_rsi(closes, period)

    n = len(closes)
    values = rsi_result.values

    if n < period + 1:
        return rsi_result

    last = n - 1
    if math.isnan(values[last]):
        return rsi_result

    # 条件 1：RSI 在 [50, 80]
    cond_range = 50.0 <= values[last] <= 80.0

    # 条件 2：无超买背离
    # 检查最近 period 天内是否存在背离：
    # 价格创新高但 RSI 未创新高
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

    signal = cond_range and cond_no_divergence

    return RSIResult(values=rsi_result.values, signal=signal)


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
