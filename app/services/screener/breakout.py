"""
形态突破选股模块（Breakout Pattern Screener）

提供：
- detect_box_breakout: 箱体突破识别
- detect_previous_high_breakout: 前期高点突破识别
- detect_descending_trendline_breakout: 下降趋势线突破识别
- validate_breakout: 有效突破判定（收盘价突破 + 成交量 ≥ 近 20 日均量 1.5 倍）
- check_false_breakout: 假突破撤销逻辑（突破后未站稳 1 个交易日）

对应需求：
- 需求 5.1：识别箱体突破、前期高点突破、下降趋势线突破
- 需求 5.2：有效突破 = 收盘价突破压力位 AND 成交量 ≥ 近 20 日均量 1.5 倍
- 需求 5.3：突破后收盘价未站稳突破位满 1 个交易日 → 撤销信号，标记假突破
- 需求 5.4：过滤无量突破（成交量 < 近 20 日均量 1.5 倍不生成买入信号）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 箱体突破参数
DEFAULT_BOX_PERIOD = 20          # 箱体观察期（交易日）
DEFAULT_BOX_RANGE_PCT = 0.10     # 箱体振幅阈值（高低点差 / 低点 ≤ 10%）

# 前期高点突破参数
DEFAULT_HIGH_LOOKBACK = 60       # 前期高点回看天数

# 下降趋势线参数
DEFAULT_TRENDLINE_LOOKBACK = 30  # 趋势线回看天数
DEFAULT_TRENDLINE_MIN_PEAKS = 2  # 最少需要的局部高点数

# 成交量确认参数
DEFAULT_VOLUME_AVG_PERIOD = 20   # 均量计算周期
DEFAULT_VOLUME_MULTIPLIER = 1.5  # 有效突破成交量倍数

# 假突破参数
DEFAULT_HOLD_DAYS = 1            # 需站稳的交易日数


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

class BreakoutType(str, Enum):
    """突破类型"""
    BOX = "BOX"                          # 箱体突破
    PREVIOUS_HIGH = "PREVIOUS_HIGH"      # 前期高点突破
    TRENDLINE = "TRENDLINE"              # 下降趋势线突破


@dataclass
class BreakoutSignal:
    """突破信号"""
    breakout_type: BreakoutType          # 突破类型
    resistance_level: float              # 压力位价格
    close_price: float                   # 突破日收盘价
    volume: int                          # 突破日成交量
    avg_volume_20d: float                # 近 20 日均量
    volume_ratio: float                  # 成交量 / 均量
    is_valid: bool                       # 是否有效突破（量价确认）
    is_false_breakout: bool = False      # 是否假突破（站稳检查后标记）
    generates_buy_signal: bool = False   # 是否生成买入信号
    volume_sustained: bool | None = None # 突破后成交量持续性（True=持续放量, False=缩量, None=数据不足）
    consolidation_bonus: bool = False    # 突破前横盘整理期 ≥ 30 个交易日加分标记


# ---------------------------------------------------------------------------
# 箱体突破识别
# ---------------------------------------------------------------------------

def detect_box_breakout(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[int],
    box_period: int = DEFAULT_BOX_PERIOD,
    box_range_pct: float = DEFAULT_BOX_RANGE_PCT,
    volume_avg_period: int = DEFAULT_VOLUME_AVG_PERIOD,
    volume_multiplier: float = DEFAULT_VOLUME_MULTIPLIER,
) -> BreakoutSignal | None:
    """
    识别箱体突破。

    箱体定义：在 box_period 天内，最高价与最低价的振幅 ≤ box_range_pct。
    突破条件：当日收盘价突破箱体上沿（箱体期间最高价）。

    Args:
        closes: 收盘价序列（按时间升序）
        highs: 最高价序列
        lows: 最低价序列
        volumes: 成交量序列
        box_period: 箱体观察期天数
        box_range_pct: 箱体振幅阈值
        volume_avg_period: 均量计算周期
        volume_multiplier: 有效突破成交量倍数

    Returns:
        BreakoutSignal 或 None（未检测到突破）
    """
    n = len(closes)
    # 需要至少 box_period 天的箱体 + 1 天突破
    min_required = box_period + 1
    if n < min_required or len(highs) < n or len(lows) < n or len(volumes) < n:
        return None

    last = n - 1

    # 箱体区间：倒数第 2 天往前 box_period 天
    box_end = last - 1
    box_start = box_end - box_period + 1
    if box_start < 0:
        return None

    # 计算箱体高低点
    box_high = max(highs[i] for i in range(box_start, box_end + 1))
    box_low = min(lows[i] for i in range(box_start, box_end + 1))

    if box_low <= 0:
        return None

    # 检查是否为箱体（振幅 ≤ 阈值）
    box_range = (box_high - box_low) / box_low
    if box_range > box_range_pct:
        return None

    # 检查突破：当日收盘价 > 箱体上沿
    resistance = box_high
    if closes[last] <= resistance:
        return None

    # 计算均量
    avg_volume = _calc_avg_volume(volumes, last, volume_avg_period)
    if avg_volume <= 0:
        return None

    volume_ratio = volumes[last] / avg_volume
    is_valid = volume_ratio >= volume_multiplier

    return BreakoutSignal(
        breakout_type=BreakoutType.BOX,
        resistance_level=resistance,
        close_price=closes[last],
        volume=volumes[last],
        avg_volume_20d=avg_volume,
        volume_ratio=volume_ratio,
        is_valid=is_valid,
        is_false_breakout=False,
        generates_buy_signal=is_valid,
    )


# ---------------------------------------------------------------------------
# 前期高点突破识别
# ---------------------------------------------------------------------------

def detect_previous_high_breakout(
    closes: list[float],
    volumes: list[int],
    lookback: int = DEFAULT_HIGH_LOOKBACK,
    volume_avg_period: int = DEFAULT_VOLUME_AVG_PERIOD,
    volume_multiplier: float = DEFAULT_VOLUME_MULTIPLIER,
) -> BreakoutSignal | None:
    """
    识别前期高点突破。

    前期高点：过去 lookback 天内的最高收盘价（不含当日）。
    突破条件：当日收盘价超过前期高点。

    Args:
        closes: 收盘价序列
        volumes: 成交量序列
        lookback: 回看天数
        volume_avg_period: 均量计算周期
        volume_multiplier: 有效突破成交量倍数

    Returns:
        BreakoutSignal 或 None
    """
    n = len(closes)
    if n < lookback + 1 or len(volumes) < n:
        return None

    last = n - 1

    # 前期高点：过去 lookback 天（不含当日）的最高收盘价
    search_start = last - lookback
    if search_start < 0:
        search_start = 0

    previous_high = max(closes[i] for i in range(search_start, last))

    # 突破：当日收盘价 > 前期高点
    if closes[last] <= previous_high:
        return None

    # 计算均量
    avg_volume = _calc_avg_volume(volumes, last, volume_avg_period)
    if avg_volume <= 0:
        return None

    volume_ratio = volumes[last] / avg_volume
    is_valid = volume_ratio >= volume_multiplier

    return BreakoutSignal(
        breakout_type=BreakoutType.PREVIOUS_HIGH,
        resistance_level=previous_high,
        close_price=closes[last],
        volume=volumes[last],
        avg_volume_20d=avg_volume,
        volume_ratio=volume_ratio,
        is_valid=is_valid,
        is_false_breakout=False,
        generates_buy_signal=is_valid,
    )


# ---------------------------------------------------------------------------
# 下降趋势线突破识别
# ---------------------------------------------------------------------------

def _find_local_highs(
    highs: list[float],
    start: int,
    end: int,
    min_distance: int = 3,
) -> list[tuple[int, float]]:
    """
    在 highs[start:end+1] 中寻找局部高点。

    局部高点定义：highs[i] > highs[i-1] 且 highs[i] > highs[i+1]。
    相邻高点间距至少 min_distance 天。

    Returns:
        [(index, high_value), ...] 按索引升序
    """
    peaks: list[tuple[int, float]] = []
    for i in range(start + 1, end):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            if not peaks or (i - peaks[-1][0]) >= min_distance:
                peaks.append((i, highs[i]))
    return peaks


def detect_descending_trendline_breakout(
    closes: list[float],
    highs: list[float],
    volumes: list[int],
    lookback: int = DEFAULT_TRENDLINE_LOOKBACK,
    min_peaks: int = DEFAULT_TRENDLINE_MIN_PEAKS,
    volume_avg_period: int = DEFAULT_VOLUME_AVG_PERIOD,
    volume_multiplier: float = DEFAULT_VOLUME_MULTIPLIER,
) -> BreakoutSignal | None:
    """
    识别下降趋势线突破。

    算法：
    1. 在过去 lookback 天内寻找局部高点
    2. 要求至少 min_peaks 个高点，且后一个高点低于前一个（下降趋势）
    3. 用最近两个符合条件的高点连线形成趋势线
    4. 当日收盘价突破趋势线外推值

    Args:
        closes: 收盘价序列
        highs: 最高价序列
        volumes: 成交量序列
        lookback: 回看天数
        min_peaks: 最少局部高点数
        volume_avg_period: 均量计算周期
        volume_multiplier: 有效突破成交量倍数

    Returns:
        BreakoutSignal 或 None
    """
    n = len(closes)
    if n < lookback + 1 or len(highs) < n or len(volumes) < n:
        return None

    last = n - 1
    search_start = max(last - lookback, 1)
    search_end = last  # exclusive for peak detection (need i+1)

    # 寻找局部高点
    peaks = _find_local_highs(highs, search_start, search_end)

    if len(peaks) < min_peaks:
        return None

    # 筛选下降的高点对：从最近的高点向前找
    # 取最近两个形成下降趋势的高点
    descending_peaks: list[tuple[int, float]] = []
    for i in range(len(peaks) - 1, -1, -1):
        if not descending_peaks:
            descending_peaks.append(peaks[i])
        elif peaks[i][1] > descending_peaks[-1][1]:
            descending_peaks.append(peaks[i])
            if len(descending_peaks) >= min_peaks:
                break

    if len(descending_peaks) < min_peaks:
        return None

    # 反转使其按时间升序
    descending_peaks.reverse()

    # 用最近两个下降高点连线
    p1_idx, p1_val = descending_peaks[-2]
    p2_idx, p2_val = descending_peaks[-1]

    if p2_idx == p1_idx:
        return None

    # 趋势线斜率（每天下降多少）
    slope = (p2_val - p1_val) / (p2_idx - p1_idx)

    # 趋势线在当日的外推值
    trendline_at_last = p2_val + slope * (last - p2_idx)

    # 突破：当日收盘价 > 趋势线值
    if closes[last] <= trendline_at_last:
        return None

    # 计算均量
    avg_volume = _calc_avg_volume(volumes, last, volume_avg_period)
    if avg_volume <= 0:
        return None

    volume_ratio = volumes[last] / avg_volume
    is_valid = volume_ratio >= volume_multiplier

    return BreakoutSignal(
        breakout_type=BreakoutType.TRENDLINE,
        resistance_level=trendline_at_last,
        close_price=closes[last],
        volume=volumes[last],
        avg_volume_20d=avg_volume,
        volume_ratio=volume_ratio,
        is_valid=is_valid,
        is_false_breakout=False,
        generates_buy_signal=is_valid,
    )


# ---------------------------------------------------------------------------
# 有效突破判定
# ---------------------------------------------------------------------------

def validate_breakout(
    signal: BreakoutSignal,
    volume_multiplier: float = DEFAULT_VOLUME_MULTIPLIER,
) -> BreakoutSignal:
    """
    判定突破是否有效（需求 5.2, 5.4）。

    有效突破条件：
    1. 收盘价已突破压力位（由检测函数保证）
    2. 当日成交量 ≥ 近 20 日均量 × volume_multiplier

    无量突破（成交量 < 阈值）不生成买入信号。

    Args:
        signal: 突破信号
        volume_multiplier: 成交量倍数阈值

    Returns:
        更新后的 BreakoutSignal
    """
    is_valid = signal.volume_ratio >= volume_multiplier
    return BreakoutSignal(
        breakout_type=signal.breakout_type,
        resistance_level=signal.resistance_level,
        close_price=signal.close_price,
        volume=signal.volume,
        avg_volume_20d=signal.avg_volume_20d,
        volume_ratio=signal.volume_ratio,
        is_valid=is_valid,
        is_false_breakout=signal.is_false_breakout,
        generates_buy_signal=is_valid and not signal.is_false_breakout,
    )


# ---------------------------------------------------------------------------
# 假突破撤销逻辑
# ---------------------------------------------------------------------------

def check_false_breakout(
    signal: BreakoutSignal,
    next_day_close: float,
    hold_days: int = DEFAULT_HOLD_DAYS,
) -> BreakoutSignal:
    """
    检查假突破（需求 5.3）。

    假突破条件：突破后次日收盘价 < 突破压力位。
    （hold_days=1 表示需站稳 1 个交易日，即次日收盘价需 >= 压力位）

    Args:
        signal: 突破信号
        next_day_close: 突破后次日收盘价
        hold_days: 需站稳的交易日数（默认 1）

    Returns:
        更新后的 BreakoutSignal（可能标记为假突破）
    """
    is_false = next_day_close < signal.resistance_level

    return BreakoutSignal(
        breakout_type=signal.breakout_type,
        resistance_level=signal.resistance_level,
        close_price=signal.close_price,
        volume=signal.volume,
        avg_volume_20d=signal.avg_volume_20d,
        volume_ratio=signal.volume_ratio,
        is_valid=signal.is_valid,
        is_false_breakout=is_false,
        generates_buy_signal=signal.is_valid and not is_false,
    )


# ---------------------------------------------------------------------------
# 突破后成交量持续性验证（需求 7.1, 7.2, 7.5）
# ---------------------------------------------------------------------------

def check_volume_sustainability(
    breakout_volume: int,
    post_breakout_volumes: list[int],
    sustain_threshold_pct: float = 0.70,
    fail_threshold_pct: float = 0.50,
) -> bool | None:
    """
    验证突破后成交量持续性（纯函数）。

    判定规则：
    - 突破日成交量为 0 → 返回 None（避免除零）
    - 突破后交易日不足 2 天 → 返回 None（数据不足）
    - 任一日成交量 < breakout_volume × fail_threshold_pct → 返回 False（缩量）
    - 连续 2 日成交量均 >= breakout_volume × sustain_threshold_pct → 返回 True（持续放量）
    - 其他情况 → 返回 None（介于两者之间，待确认）

    Args:
        breakout_volume: 突破日成交量
        post_breakout_volumes: 突破后各交易日成交量列表
        sustain_threshold_pct: 持续放量阈值比例（默认 70%）
        fail_threshold_pct: 缩量失败阈值比例（默认 50%）

    Returns:
        True（持续放量）、False（缩量）或 None（数据不足/待确认）
    """
    # 突破日成交量为 0，无法计算比例
    if breakout_volume == 0:
        return None

    # 数据不足（需要至少 2 个交易日）
    if len(post_breakout_volumes) < 2:
        return None

    sustain_line = breakout_volume * sustain_threshold_pct
    fail_line = breakout_volume * fail_threshold_pct

    # 检查是否有任一日低于失败阈值
    for vol in post_breakout_volumes:
        if vol < fail_line:
            return False

    # 检查前 2 日是否均达到持续放量阈值
    if post_breakout_volumes[0] >= sustain_line and post_breakout_volumes[1] >= sustain_line:
        return True

    # 介于两者之间，待确认
    return None


# ---------------------------------------------------------------------------
# 突破前横盘整理加分（需求 7.3）
# ---------------------------------------------------------------------------

def check_consolidation_bonus(
    box_period_days: int,
    min_consolidation_days: int = 30,
) -> bool:
    """
    判断箱体突破前横盘整理期是否足够长（纯函数）。

    Args:
        box_period_days: 箱体整理期天数
        min_consolidation_days: 最低整理期天数（默认 30）

    Returns:
        True 表示整理期足够长，应给予加分
    """
    return box_period_days >= min_consolidation_days


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _calc_avg_volume(
    volumes: list[int],
    current_idx: int,
    period: int = DEFAULT_VOLUME_AVG_PERIOD,
) -> float:
    """
    计算近 period 日平均成交量（不含当日）。

    Args:
        volumes: 成交量序列
        current_idx: 当前日索引
        period: 均量周期

    Returns:
        平均成交量，数据不足时返回 0.0
    """
    start = current_idx - period
    if start < 0:
        start = 0

    window = volumes[start:current_idx]
    if not window:
        return 0.0

    return sum(window) / len(window)
