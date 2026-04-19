"""
信号强度分级属性测试（Hypothesis）

Property 8: 信号强度分级映射

对应需求 7.2、7.3、7.4

验证 ScreenExecutor._compute_signal_strength() 纯函数满足：
- MA_TREND：ma_trend >= 90 → STRONG，>= 70 → MEDIUM，其余 → WEAK
- BREAKOUT：volume_ratio >= 2.0 → STRONG，>= 1.5 → MEDIUM，其余 → WEAK
- 技术指标（MACD/BOLL/RSI/DMA）：同时触发 >= 3 个 → STRONG，2 个 → MEDIUM，1 个 → WEAK
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalStrength,
)
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# ma_trend 评分策略：[0, 100] 闭区间
_ma_trend_score_st = st.floats(
    min_value=0.0, max_value=100.0,
    allow_nan=False, allow_infinity=False,
)

# 量比策略：[0, 10] 区间
_volume_ratio_st = st.floats(
    min_value=0.0, max_value=10.0,
    allow_nan=False, allow_infinity=False,
)

# 突破类型策略
_breakout_type_st = st.sampled_from(["BOX", "PREVIOUS_HIGH", "TRENDLINE"])

# 技术指标类别策略
_indicator_category_st = st.sampled_from([
    SignalCategory.MACD,
    SignalCategory.BOLL,
    SignalCategory.RSI,
    SignalCategory.DMA,
])


@st.composite
def ma_trend_signal_and_data(draw):
    """
    生成 MA_TREND 信号及对应的 stock_data。
    """
    ma_trend_val = draw(_ma_trend_score_st)
    signal = SignalDetail(
        category=SignalCategory.MA_TREND,
        label="ma_trend",
    )
    stock_data = {"ma_trend": ma_trend_val}
    return signal, stock_data, ma_trend_val


@st.composite
def breakout_signal_and_data(draw):
    """
    生成 BREAKOUT 信号及对应的 stock_data（含 breakout_list）。
    """
    bo_type = draw(_breakout_type_st)
    volume_ratio = draw(_volume_ratio_st)
    signal = SignalDetail(
        category=SignalCategory.BREAKOUT,
        label="breakout",
        breakout_type=bo_type,
    )
    stock_data = {
        "breakout_list": [
            {
                "type": bo_type,
                "is_valid": True,
                "volume_ratio": volume_ratio,
            }
        ],
    }
    return signal, stock_data, volume_ratio


@st.composite
def breakout_signal_legacy_data(draw):
    """
    生成 BREAKOUT 信号及对应的旧格式 stock_data（单个 breakout 字典）。
    """
    bo_type = draw(_breakout_type_st)
    volume_ratio = draw(_volume_ratio_st)
    signal = SignalDetail(
        category=SignalCategory.BREAKOUT,
        label="breakout",
        breakout_type=bo_type,
    )
    stock_data = {
        "breakout": {
            "type": bo_type,
            "is_valid": True,
            "volume_ratio": volume_ratio,
        },
    }
    return signal, stock_data, volume_ratio


@st.composite
def indicator_signal_and_data(draw):
    """
    生成技术指标信号及对应的 stock_data。

    随机选择 1-4 个技术指标触发，生成对应的 stock_data。
    """
    category = draw(_indicator_category_st)
    signal = SignalDetail(
        category=category,
        label=category.value.lower(),
    )

    # 随机决定每个指标是否触发
    macd_on = draw(st.booleans())
    boll_on = draw(st.booleans())
    rsi_on = draw(st.booleans())
    dma_on = draw(st.booleans())

    # 至少触发当前信号对应的指标
    if category == SignalCategory.MACD:
        macd_on = True
    elif category == SignalCategory.BOLL:
        boll_on = True
    elif category == SignalCategory.RSI:
        rsi_on = True
    elif category == SignalCategory.DMA:
        dma_on = True

    stock_data: dict = {}
    triggered_count = 0

    if macd_on:
        stock_data["macd"] = True
        triggered_count += 1
    if boll_on:
        stock_data["boll"] = True
        triggered_count += 1
    if rsi_on:
        stock_data["rsi"] = True
        triggered_count += 1
    if dma_on:
        # DMA 使用 dict 格式，dma > ama 表示触发
        stock_data["dma"] = {"dma": 1.5, "ama": 1.0}
        triggered_count += 1

    return signal, stock_data, triggered_count


# ---------------------------------------------------------------------------
# Property 8.1: MA_TREND 信号强度分级
# Feature: screening-system-enhancement, Property 8: MA_TREND 强度映射
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=ma_trend_signal_and_data())
def test_ma_trend_signal_strength_mapping(data):
    """
    # Feature: screening-system-enhancement, Property 8: MA_TREND 强度映射

    **Validates: Requirements 7.2**

    For any MA_TREND 信号：
    - ma_trend >= 90 → STRONG
    - ma_trend >= 70 → MEDIUM
    - 其余 → WEAK
    """
    signal, stock_data, ma_trend_val = data

    result = ScreenExecutor._compute_signal_strength(signal, stock_data)

    if ma_trend_val >= 90:
        expected = SignalStrength.STRONG
    elif ma_trend_val >= 70:
        expected = SignalStrength.MEDIUM
    else:
        expected = SignalStrength.WEAK

    assert result == expected, (
        f"MA_TREND 信号强度映射错误：ma_trend={ma_trend_val}，"
        f"期望 {expected.value}，实际 {result.value}"
    )


# ---------------------------------------------------------------------------
# Property 8.2: BREAKOUT 信号强度分级
# Feature: screening-system-enhancement, Property 8: BREAKOUT 强度映射
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=breakout_signal_and_data())
def test_breakout_signal_strength_mapping(data):
    """
    # Feature: screening-system-enhancement, Property 8: BREAKOUT 强度映射

    **Validates: Requirements 7.3**

    For any BREAKOUT 信号：
    - volume_ratio >= 2.0 → STRONG
    - volume_ratio >= 1.5 → MEDIUM
    - 其余 → WEAK
    """
    signal, stock_data, volume_ratio = data

    result = ScreenExecutor._compute_signal_strength(signal, stock_data)

    if volume_ratio >= 2.0:
        expected = SignalStrength.STRONG
    elif volume_ratio >= 1.5:
        expected = SignalStrength.MEDIUM
    else:
        expected = SignalStrength.WEAK

    assert result == expected, (
        f"BREAKOUT 信号强度映射错误：volume_ratio={volume_ratio}，"
        f"期望 {expected.value}，实际 {result.value}"
    )


@settings(max_examples=200)
@given(data=breakout_signal_legacy_data())
def test_breakout_signal_strength_legacy_format(data):
    """
    # Feature: screening-system-enhancement, Property 8: BREAKOUT 强度映射（旧格式）

    **Validates: Requirements 7.3**

    向后兼容：当 stock_data 仅包含旧格式 breakout 字典时，
    量比仍能正确用于强度分级。
    """
    signal, stock_data, volume_ratio = data

    result = ScreenExecutor._compute_signal_strength(signal, stock_data)

    if volume_ratio >= 2.0:
        expected = SignalStrength.STRONG
    elif volume_ratio >= 1.5:
        expected = SignalStrength.MEDIUM
    else:
        expected = SignalStrength.WEAK

    assert result == expected, (
        f"BREAKOUT 旧格式信号强度映射错误：volume_ratio={volume_ratio}，"
        f"期望 {expected.value}，实际 {result.value}"
    )


# ---------------------------------------------------------------------------
# Property 8.3: 技术指标信号强度分级
# Feature: screening-system-enhancement, Property 8: 技术指标强度映射
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=indicator_signal_and_data())
def test_indicator_signal_strength_mapping(data):
    """
    # Feature: screening-system-enhancement, Property 8: 技术指标强度映射

    **Validates: Requirements 7.4**

    For any 技术指标信号（MACD/BOLL/RSI/DMA）：
    - 同时触发 >= 3 个 → STRONG
    - 2 个 → MEDIUM
    - 1 个 → WEAK
    """
    signal, stock_data, triggered_count = data

    result = ScreenExecutor._compute_signal_strength(signal, stock_data)

    if triggered_count >= 3:
        expected = SignalStrength.STRONG
    elif triggered_count >= 2:
        expected = SignalStrength.MEDIUM
    else:
        expected = SignalStrength.WEAK

    assert result == expected, (
        f"技术指标信号强度映射错误：category={signal.category.value}，"
        f"triggered_count={triggered_count}，"
        f"期望 {expected.value}，实际 {result.value}"
    )


# ---------------------------------------------------------------------------
# Property 8 补充：返回值始终为有效 SignalStrength 枚举
# Feature: screening-system-enhancement, Property 8: 返回值有效性
# ---------------------------------------------------------------------------


@st.composite
def any_signal_and_data(draw):
    """
    生成任意类别的信号及对应的 stock_data。
    """
    category = draw(st.sampled_from(list(SignalCategory)))
    signal = SignalDetail(
        category=category,
        label=category.value.lower(),
        breakout_type=draw(_breakout_type_st) if category == SignalCategory.BREAKOUT else None,
    )

    stock_data: dict = {}
    # 随机填充可能的上下文数据
    stock_data["ma_trend"] = draw(_ma_trend_score_st)
    if draw(st.booleans()):
        stock_data["macd"] = True
    if draw(st.booleans()):
        stock_data["boll"] = True
    if draw(st.booleans()):
        stock_data["rsi"] = True
    if draw(st.booleans()):
        stock_data["dma"] = {"dma": 1.5, "ama": 1.0}

    if signal.breakout_type:
        vol_ratio = draw(_volume_ratio_st)
        stock_data["breakout_list"] = [
            {"type": signal.breakout_type, "is_valid": True, "volume_ratio": vol_ratio}
        ]

    return signal, stock_data


@settings(max_examples=200)
@given(data=any_signal_and_data())
def test_signal_strength_always_valid_enum(data):
    """
    # Feature: screening-system-enhancement, Property 8: 返回值有效性

    **Validates: Requirements 7.2, 7.3, 7.4**

    For any SignalDetail 和 stock_data，
    _compute_signal_strength() 始终返回有效的 SignalStrength 枚举值。
    """
    signal, stock_data = data

    result = ScreenExecutor._compute_signal_strength(signal, stock_data)

    assert isinstance(result, SignalStrength), (
        f"返回值 {result} 不是 SignalStrength 枚举类型"
    )
    assert result in (SignalStrength.STRONG, SignalStrength.MEDIUM, SignalStrength.WEAK), (
        f"返回值 {result} 不是有效的 SignalStrength 值"
    )
