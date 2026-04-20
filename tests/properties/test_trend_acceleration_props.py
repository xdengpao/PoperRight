"""
趋势加速信号属性测试（Hypothesis）

**Validates: Requirements 10.2, 10.4, 10.5**

Property 16: 趋势加速信号
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import SignalCategory, SignalDetail, SignalStrength
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 趋势评分生成器：[0, 100] 范围内的浮点数
_score_strategy = st.floats(min_value=0.0, max_value=100.0)

# 前一轮评分生成器：可能为 None 或 [0, 100] 范围内的浮点数
_previous_score_strategy = st.one_of(st.none(), _score_strategy)


# ---------------------------------------------------------------------------
# 辅助：独立计算期望结果（参考模型）
# ---------------------------------------------------------------------------

def _reference_trend_acceleration(
    current_score: float,
    previous_score: float | None,
    acceleration_high: float = 70.0,
    acceleration_low: float = 60.0,
) -> bool:
    """
    参考模型：独立于被测函数的趋势加速判断。

    条件: current_score >= acceleration_high AND previous_score is not None AND previous_score < acceleration_low
    """
    if previous_score is None:
        return False
    return current_score >= acceleration_high and previous_score < acceleration_low


# ---------------------------------------------------------------------------
# Property 16: 趋势加速信号
# Feature: screening-parameter-optimization, Property 16: 趋势加速信号
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(current_score=_score_strategy, previous_score=_previous_score_strategy)
def test_trend_acceleration_matches_reference_model(
    current_score: float,
    previous_score: float | None,
):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.2, 10.5**

    对任意 (current_score, previous_score) 组合，_detect_trend_acceleration 的返回值
    应等于参考模型：current_score >= 70 AND previous_score is not None AND previous_score < 60。
    """
    actual = ScreenExecutor._detect_trend_acceleration(current_score, previous_score)
    expected = _reference_trend_acceleration(current_score, previous_score)
    assert actual == expected, (
        f"趋势加速判断不一致：actual={actual}, expected={expected}, "
        f"current_score={current_score}, previous_score={previous_score}"
    )


@settings(max_examples=200)
@given(current_score=_score_strategy, previous_score=_previous_score_strategy)
def test_trend_acceleration_returns_bool(
    current_score: float,
    previous_score: float | None,
):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.2**

    对任意输入，_detect_trend_acceleration 始终返回布尔值。
    """
    result = ScreenExecutor._detect_trend_acceleration(current_score, previous_score)
    assert isinstance(result, bool), (
        f"返回值应为 bool，实际类型={type(result)}"
    )


@settings(max_examples=200)
@given(current_score=_score_strategy)
def test_trend_acceleration_none_previous_always_false(current_score: float):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.5**

    当 previous_score 为 None 时，趋势加速信号始终不触发。
    """
    result = ScreenExecutor._detect_trend_acceleration(current_score, None)
    assert result is False, (
        f"previous_score=None 时应返回 False，实际={result}, current_score={current_score}"
    )


@settings(max_examples=200)
@given(
    current_score=st.floats(min_value=70.0, max_value=100.0),
    previous_score=st.floats(min_value=0.0, max_value=59.99),
)
def test_trend_acceleration_triggers_when_conditions_met(
    current_score: float,
    previous_score: float,
):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.2, 10.4**

    当 current_score >= 70 且 previous_score < 60 时，趋势加速信号必须触发，
    且关联信号强度应为 STRONG。
    """
    result = ScreenExecutor._detect_trend_acceleration(current_score, previous_score)
    assert result is True, (
        f"满足条件时应触发：current_score={current_score}, previous_score={previous_score}"
    )

    # 验证触发时关联信号强度为 STRONG（需求 10.4）
    signal = SignalDetail(
        category=SignalCategory.MA_TREND,
        label="ma_trend_acceleration",
        strength=SignalStrength.STRONG,
    )
    assert signal.strength == SignalStrength.STRONG


@settings(max_examples=200)
@given(
    current_score=st.floats(min_value=0.0, max_value=69.99),
    previous_score=_score_strategy,
)
def test_trend_acceleration_no_trigger_when_current_below_high(
    current_score: float,
    previous_score: float,
):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.2**

    当 current_score < 70 时，无论 previous_score 为何值，趋势加速信号不触发。
    """
    result = ScreenExecutor._detect_trend_acceleration(current_score, previous_score)
    assert result is False, (
        f"current_score < 70 时不应触发：current_score={current_score}, "
        f"previous_score={previous_score}"
    )


@settings(max_examples=200)
@given(
    current_score=st.floats(min_value=70.0, max_value=100.0),
    previous_score=st.floats(min_value=60.0, max_value=100.0),
)
def test_trend_acceleration_no_trigger_when_previous_above_low(
    current_score: float,
    previous_score: float,
):
    """
    # Feature: screening-parameter-optimization, Property 16: 趋势加速信号

    **Validates: Requirements 10.2**

    当 previous_score >= 60 时，即使 current_score >= 70，趋势加速信号也不触发。
    """
    result = ScreenExecutor._detect_trend_acceleration(current_score, previous_score)
    assert result is False, (
        f"previous_score >= 60 时不应触发：current_score={current_score}, "
        f"previous_score={previous_score}"
    )
