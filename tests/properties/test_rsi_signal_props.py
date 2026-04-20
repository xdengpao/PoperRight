"""
RSI 信号属性测试（Hypothesis）

**Validates: Requirements 3.2, 3.3, 3.5**

Property 5: RSI 信号需要区间内且连续上升
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.indicators import (
    detect_rsi_signal,
    calculate_rsi,
    RSISignalResult,
    RSIResult,
    DEFAULT_RSI_PERIOD,
    _count_consecutive_rising,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 收盘价序列生成器：正浮点数，最少 20 个数据点
_close_price_strategy = st.lists(
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=20,
)


# ---------------------------------------------------------------------------
# Property 5: RSI 信号需要区间内且连续上升
# Feature: screening-parameter-optimization, Property 5: RSI 信号需要区间内且连续上升
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_strategy)
def test_rsi_signal_requires_range_and_consecutive_rising(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 5: RSI 信号需要区间内且连续上升

    **Validates: Requirements 3.2, 3.3, 3.5**

    对任意收盘价序列（长度 >= 20），RSI 检测器应满足：
    - 返回结果始终包含有效的 signal（bool）、current_rsi（float）、
      consecutive_rising（int >= 0）、values（list[float]）字段
    - signal=True 当且仅当：
      1. 当前 RSI 在 [lower_bound, upper_bound] 区间内
      2. 最近 rising_days 天 RSI 严格递增
      3. 无超买背离
    - 数据不足时（可用天数 < rising_days + period）signal=False
    """
    lower_bound = 55.0
    upper_bound = 75.0
    rising_days = 3
    period = DEFAULT_RSI_PERIOD

    result = detect_rsi_signal(
        closes,
        period=period,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        rising_days=rising_days,
    )

    # ── 结构化结果字段有效性验证 ──
    assert isinstance(result, RSISignalResult), "返回类型应为 RSISignalResult"
    assert isinstance(result.signal, bool), "signal 字段应为 bool 类型"
    assert isinstance(result.current_rsi, (int, float)), "current_rsi 字段应为数值类型"
    assert isinstance(result.consecutive_rising, int), "consecutive_rising 字段应为 int 类型"
    assert result.consecutive_rising >= 0, (
        f"consecutive_rising 应 >= 0，实际={result.consecutive_rising}"
    )
    assert isinstance(result.values, list), "values 字段应为 list 类型"
    assert len(result.values) == len(closes), "values 长度应与输入收盘价序列一致"

    n = len(closes)

    # ── 数据不足检查 ──
    if n < rising_days + period:
        assert result.signal is False, (
            f"数据不足时（n={n} < rising_days+period={rising_days + period}）不应生成信号"
        )
        return

    last = n - 1

    # 如果最后一天 RSI 为 NaN，不应生成信号
    if math.isnan(result.values[last]):
        assert result.signal is False, "RSI 值为 NaN 时不应生成信号"
        return

    # ── 必要条件验证：signal=True → 三个条件均满足 ──
    if result.signal:
        # 条件 1：RSI 在 [lower_bound, upper_bound] 区间内
        assert lower_bound <= result.current_rsi <= upper_bound, (
            f"signal=True 时 RSI 应在 [{lower_bound}, {upper_bound}] 区间内，"
            f"实际 current_rsi={result.current_rsi:.4f}"
        )

        # 条件 2：连续 rising_days 天 RSI 严格递增
        assert result.consecutive_rising >= rising_days, (
            f"signal=True 时 consecutive_rising 应 >= {rising_days}，"
            f"实际={result.consecutive_rising}"
        )

    # ── 充分条件验证：三个条件均满足 → signal=True ──
    # 检查三个条件是否满足
    cond_range = lower_bound <= result.current_rsi <= upper_bound
    cond_rising = result.consecutive_rising >= rising_days

    # 超买背离检测（复现实现逻辑）
    lookback = min(period, last)
    cond_no_divergence = True
    if lookback >= 2:
        window_start = last - lookback
        price_max_idx = window_start
        for i in range(window_start, last):
            if not math.isnan(result.values[i]) and closes[i] >= closes[price_max_idx]:
                price_max_idx = i
        if (
            closes[last] >= closes[price_max_idx]
            and price_max_idx != last
            and not math.isnan(result.values[price_max_idx])
            and result.values[last] < result.values[price_max_idx]
        ):
            cond_no_divergence = False

    expected_signal = cond_range and cond_rising and cond_no_divergence

    assert result.signal == expected_signal, (
        f"signal 应为 {expected_signal}，实际={result.signal}。"
        f"cond_range={cond_range}（RSI={result.current_rsi:.4f}），"
        f"cond_rising={cond_rising}（consecutive={result.consecutive_rising}），"
        f"cond_no_divergence={cond_no_divergence}"
    )
