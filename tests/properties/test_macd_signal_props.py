"""
MACD 信号属性测试（Hypothesis）

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

Property 1: MACD 信号类型与强度分类
Property 2: DEA 趋势向上提升信号强度
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import SignalStrength
from app.services.screener.indicators import (
    detect_macd_signal,
    MACDSignalResult,
    _count_below_zero_golden_crosses,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 收盘价序列生成器：正浮点数，最少 80 个数据点
_close_price_strategy = st.lists(
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=80,
)


# ---------------------------------------------------------------------------
# Property 1: MACD 信号类型与强度分类
# Feature: screening-parameter-optimization, Property 1: MACD 信号类型与强度分类
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_strategy)
def test_macd_signal_type_and_strength_classification(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 1: MACD 信号类型与强度分类

    **Validates: Requirements 1.1, 1.2, 1.4**

    对任意有效收盘价序列，MACD 检测器应满足：
    - 返回结果始终包含有效的 signal（bool）、strength（SignalStrength）、signal_type（str）字段
    - 当 signal=True 且 signal_type="above_zero" 时：DIF > 0, DEA > 0, 金叉成立, MACD 红柱放大, strength=STRONG
    - 当 signal=True 且 signal_type="below_zero_second" 时：DIF < 0, 金叉成立, strength 为 WEAK 或 MEDIUM
    """
    result = detect_macd_signal(closes)

    # ── 结构化结果字段有效性验证 ──
    assert isinstance(result, MACDSignalResult), "返回类型应为 MACDSignalResult"
    assert isinstance(result.signal, bool), "signal 字段应为 bool 类型"
    assert isinstance(result.strength, SignalStrength), "strength 字段应为 SignalStrength 枚举"
    assert isinstance(result.signal_type, str), "signal_type 字段应为 str 类型"
    assert result.signal_type in ("above_zero", "below_zero_second", "none"), (
        f"signal_type 应为 'above_zero'、'below_zero_second' 或 'none'，实际={result.signal_type}"
    )

    # ── DIF/DEA/MACD 列表长度一致性 ──
    assert len(result.dif) == len(closes), "DIF 长度应与输入收盘价序列一致"
    assert len(result.dea) == len(closes), "DEA 长度应与输入收盘价序列一致"
    assert len(result.macd) == len(closes), "MACD 长度应与输入收盘价序列一致"

    n = len(result.dif)
    if n < 2:
        assert result.signal is False, "数据不足时不应生成信号"
        return

    last = n - 1
    prev = n - 2

    # ── 无信号时 signal_type 应为 "none" ──
    if not result.signal:
        assert result.signal_type == "none", (
            f"signal=False 时 signal_type 应为 'none'，实际={result.signal_type}"
        )
        return

    # ── 信号为 True 时，验证金叉条件（DIF 上穿 DEA） ──
    assert not math.isnan(result.dif[last]) and not math.isnan(result.dea[last]), (
        "信号为 True 时最后一天 DIF/DEA 不应为 NaN"
    )
    assert not math.isnan(result.dif[prev]) and not math.isnan(result.dea[prev]), (
        "信号为 True 时前一天 DIF/DEA 不应为 NaN"
    )
    assert result.dif[prev] <= result.dea[prev], "金叉要求前一日 DIF <= DEA"
    assert result.dif[last] > result.dea[last], "金叉要求当日 DIF > DEA"

    # ── 零轴上方金叉验证 ──
    if result.signal_type == "above_zero":
        assert result.dif[last] > 0, "零轴上方金叉要求 DIF > 0"
        assert result.dea[last] > 0, "零轴上方金叉要求 DEA > 0"
        # MACD 红柱放大
        assert not math.isnan(result.macd[last]) and not math.isnan(result.macd[prev])
        assert result.macd[last] > result.macd[prev], "零轴上方金叉要求 MACD 红柱放大"
        assert result.macd[last] > 0, "零轴上方金叉要求 MACD 红柱为正"
        # 强度为 STRONG（零轴上方金叉基础强度即为 STRONG）
        assert result.strength == SignalStrength.STRONG, (
            f"零轴上方金叉强度应为 STRONG，实际={result.strength}"
        )

    # ── 零轴下方二次金叉验证 ──
    elif result.signal_type == "below_zero_second":
        assert result.dif[last] < 0, "零轴下方二次金叉要求 DIF < 0"
        # 强度为 WEAK 或 MEDIUM（取决于 DEA 趋势修饰符）
        assert result.strength in (SignalStrength.WEAK, SignalStrength.MEDIUM), (
            f"零轴下方二次金叉强度应为 WEAK 或 MEDIUM，实际={result.strength}"
        )


# ---------------------------------------------------------------------------
# Property 2: DEA 趋势向上提升信号强度
# Feature: screening-parameter-optimization, Property 2: DEA 趋势向上提升信号强度
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_strategy)
def test_dea_trending_up_boosts_signal_strength(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 2: DEA 趋势向上提升信号强度

    **Validates: Requirements 1.3**

    对任意 MACD 信号结果中 signal=True 的情况：
    - 若 DEA 趋势向上（DEA[last] > DEA[prev]），强度应比基础强度提升一级
      （WEAK→MEDIUM, MEDIUM→STRONG, STRONG 保持 STRONG）
    - 若 DEA 趋势未向上（DEA[last] <= DEA[prev]），强度应为基础强度
    """
    result = detect_macd_signal(closes)

    if not result.signal:
        return  # 仅验证有信号的情况

    n = len(result.dea)
    assert n >= 2, "有信号时数据长度应 >= 2"

    last = n - 1
    prev = n - 2

    assert not math.isnan(result.dea[last]) and not math.isnan(result.dea[prev])

    dea_trending_up = result.dea[last] > result.dea[prev]

    if result.signal_type == "above_zero":
        # 零轴上方金叉基础强度为 STRONG，DEA 修饰符不再提升
        assert result.strength == SignalStrength.STRONG, (
            "零轴上方金叉强度始终为 STRONG"
        )

    elif result.signal_type == "below_zero_second":
        # 零轴下方二次金叉基础强度为 WEAK
        if dea_trending_up:
            # DEA 向上 → WEAK 提升为 MEDIUM
            assert result.strength == SignalStrength.MEDIUM, (
                f"DEA 趋势向上时零轴下方二次金叉强度应从 WEAK 提升为 MEDIUM，"
                f"实际={result.strength}，DEA[last]={result.dea[last]:.6f}，DEA[prev]={result.dea[prev]:.6f}"
            )
        else:
            # DEA 未向上 → 保持 WEAK
            assert result.strength == SignalStrength.WEAK, (
                f"DEA 趋势未向上时零轴下方二次金叉强度应为 WEAK，"
                f"实际={result.strength}，DEA[last]={result.dea[last]:.6f}，DEA[prev]={result.dea[prev]:.6f}"
            )
