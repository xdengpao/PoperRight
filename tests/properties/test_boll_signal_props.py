"""
BOLL 信号属性测试（Hypothesis）

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 3: BOLL 信号需要连续 2 日站稳中轨
Property 4: BOLL 接近上轨风险标记
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.indicators import (
    detect_boll_signal,
    calculate_boll,
    BOLLSignalResult,
    DEFAULT_BOLL_PERIOD,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 收盘价序列生成器：正浮点数，最少 25 个数据点
_close_price_strategy = st.lists(
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=25,
)


# ---------------------------------------------------------------------------
# Property 3: BOLL 信号需要连续 2 日站稳中轨
# Feature: screening-parameter-optimization, Property 3: BOLL 信号需要连续 2 日站稳中轨
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_strategy)
def test_boll_signal_requires_two_consecutive_days_above_middle(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 3: BOLL 信号需要连续 2 日站稳中轨

    **Validates: Requirements 2.1, 2.3, 2.4**

    对任意收盘价序列，BOLL 检测器应满足：
    - 返回结果始终包含有效的 signal（bool）、near_upper_band（bool）、hold_days（int >= 0）字段
    - signal=True 当且仅当最后连续 2 日收盘价均高于各自对应的中轨值
    - hold_days >= 0
    """
    result = detect_boll_signal(closes)

    # ── 结构化结果字段有效性验证 ──
    assert isinstance(result, BOLLSignalResult), "返回类型应为 BOLLSignalResult"
    assert isinstance(result.signal, bool), "signal 字段应为 bool 类型"
    assert isinstance(result.near_upper_band, bool), "near_upper_band 字段应为 bool 类型"
    assert isinstance(result.hold_days, int), "hold_days 字段应为 int 类型"
    assert result.hold_days >= 0, f"hold_days 应 >= 0，实际={result.hold_days}"

    # ── 上轨/中轨/下轨列表长度一致性 ──
    assert len(result.upper) == len(closes), "上轨长度应与输入收盘价序列一致"
    assert len(result.middle) == len(closes), "中轨长度应与输入收盘价序列一致"
    assert len(result.lower) == len(closes), "下轨长度应与输入收盘价序列一致"

    n = len(closes)
    if n < 2:
        assert result.signal is False, "数据不足 2 天时不应生成信号"
        return

    last = n - 1
    prev = n - 2

    # 如果中轨数据无效（NaN），不应生成信号
    if math.isnan(result.middle[last]) or math.isnan(result.middle[prev]):
        assert result.signal is False, "中轨数据无效时不应生成信号"
        return

    # ── 核心属性：signal=True ⟺ 最后 2 日均站稳中轨 ──
    today_above = closes[last] > result.middle[last]
    prev_above = closes[prev] > result.middle[prev]
    expected_signal = today_above and prev_above

    assert result.signal == expected_signal, (
        f"signal 应为 {expected_signal}，实际={result.signal}。"
        f"close[last]={closes[last]:.4f}, mid[last]={result.middle[last]:.4f}, "
        f"close[prev]={closes[prev]:.4f}, mid[prev]={result.middle[prev]:.4f}"
    )

    # ── hold_days 与 signal 的一致性 ──
    if result.signal:
        assert result.hold_days >= 2, (
            f"signal=True 时 hold_days 应 >= 2，实际={result.hold_days}"
        )


# ---------------------------------------------------------------------------
# Property 4: BOLL 接近上轨风险标记
# Feature: screening-parameter-optimization, Property 4: BOLL 接近上轨风险标记
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_strategy)
def test_boll_near_upper_band_independent_of_signal(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 4: BOLL 接近上轨风险标记

    **Validates: Requirements 2.2**

    对任意收盘价序列（布林带数据有效时）：
    - near_upper_band=True 当且仅当最后一日收盘价 >= 上轨 × 0.98
    - near_upper_band 与 signal 字段独立（两者可以任意组合）
    """
    result = detect_boll_signal(closes)

    n = len(closes)
    if n < 2:
        # 数据不足时 near_upper_band 应为 False
        assert result.near_upper_band is False, "数据不足时 near_upper_band 应为 False"
        return

    last = n - 1

    # 如果上轨数据无效，near_upper_band 应为 False
    if math.isnan(result.upper[last]):
        assert result.near_upper_band is False, "上轨数据无效时 near_upper_band 应为 False"
        return

    # 如果中轨数据无效（导致 no_signal 提前返回），near_upper_band 也为 False
    prev = n - 2
    if math.isnan(result.middle[last]) or math.isnan(result.middle[prev]):
        assert result.near_upper_band is False, "中轨数据无效时 near_upper_band 应为 False"
        return

    # ── 核心属性：near_upper_band=True ⟺ close[last] >= upper[last] × 0.98 ──
    expected_near_upper = closes[last] >= result.upper[last] * 0.98

    assert result.near_upper_band == expected_near_upper, (
        f"near_upper_band 应为 {expected_near_upper}，实际={result.near_upper_band}。"
        f"close[last]={closes[last]:.4f}, upper[last]={result.upper[last]:.4f}, "
        f"threshold={result.upper[last] * 0.98:.4f}"
    )
