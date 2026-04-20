"""
MA 趋势评分属性测试（Hypothesis）

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

Property 6: MA 趋势距离分钟形曲线形状
Property 7: MA 趋势短期均线斜率优先
Property 8: MA 趋势评分范围不变量与幂等性
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.ma_trend import (
    _bell_curve_distance_score,
    score_ma_trend,
    MATrendScore,
    _SHORT_TERM_SLOPE_WEIGHT,
    _LONG_TERM_SLOPE_WEIGHT,
    _SHORT_TERM_PERIODS,
    _calc_slope,
    calculate_multi_ma,
    detect_bullish_alignment,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 百分比距离生成器：覆盖负值到大正值
_pct_above_strategy = st.floats(
    min_value=-10.0, max_value=20.0,
    allow_nan=False, allow_infinity=False,
)

# 收盘价序列生成器：正浮点数，最少 130 个数据点（足够计算 120 日均线）
_close_price_long_strategy = st.lists(
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=130,
    max_size=200,
)

# 收盘价序列生成器：较短序列，用于测试评分范围不变量
_close_price_short_strategy = st.lists(
    st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
    min_size=5,
    max_size=200,
)


# ---------------------------------------------------------------------------
# Property 6: MA 趋势距离分钟形曲线形状
# Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(pct=_pct_above_strategy)
def test_bell_curve_score_range_always_0_to_100(pct: float):
    """
    # Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状

    **Validates: Requirements 4.1, 4.4**

    对任意百分比距离值，钟形曲线评分始终在 [0, 100] 闭区间内。
    """
    score = _bell_curve_distance_score(pct)
    assert 0.0 <= score <= 100.0, (
        f"评分应在 [0, 100]，实际={score:.4f}，pct_above={pct:.4f}"
    )


@settings(max_examples=200)
@given(
    pct_near=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    pct_far=st.floats(min_value=6.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_bell_curve_near_scores_higher_than_far(pct_near: float, pct_far: float):
    """
    # Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状

    **Validates: Requirements 4.1, 4.4**

    对任意 pct_near ∈ [0%, 2%] 和 pct_far ∈ [6%, 20%]：
    score(pct_near) >= score(pct_far)
    即靠近最优区间的评分不低于远离最优区间的评分。
    """
    score_near = _bell_curve_distance_score(pct_near)
    score_far = _bell_curve_distance_score(pct_far)
    assert score_near >= score_far, (
        f"score(pct={pct_near:.4f}%)={score_near:.4f} 应 >= "
        f"score(pct={pct_far:.4f}%)={score_far:.4f}"
    )


@settings(max_examples=200)
@given(
    pct_zero=st.just(0.0),
    pct_mid=st.floats(min_value=4.0, max_value=5.0, allow_nan=False, allow_infinity=False),
)
def test_bell_curve_zero_pct_scores_higher_than_4pct(pct_zero: float, pct_mid: float):
    """
    # Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状

    **Validates: Requirements 4.1, 4.4**

    score(pct=0%) >= score(pct=4%)：最优区间内的评分不低于 4% 处的评分。
    """
    score_zero = _bell_curve_distance_score(pct_zero)
    score_mid = _bell_curve_distance_score(pct_mid)
    assert score_zero >= score_mid, (
        f"score(0%)={score_zero:.4f} 应 >= score({pct_mid:.4f}%)={score_mid:.4f}"
    )


@settings(max_examples=200)
@given(
    pct_a=st.floats(min_value=3.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    pct_b=st.floats(min_value=3.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_bell_curve_monotonically_non_increasing_above_3pct(pct_a: float, pct_b: float):
    """
    # Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状

    **Validates: Requirements 4.1, 4.4**

    对任意 pct_a, pct_b > 3%：若 pct_a <= pct_b，则 score(pct_a) >= score(pct_b)。
    即在 3% 以上区间，评分单调不增。
    """
    score_a = _bell_curve_distance_score(pct_a)
    score_b = _bell_curve_distance_score(pct_b)
    if pct_a <= pct_b:
        assert score_a >= score_b, (
            f"pct_a={pct_a:.4f}% <= pct_b={pct_b:.4f}% 时，"
            f"score_a={score_a:.4f} 应 >= score_b={score_b:.4f}"
        )
    else:
        assert score_b >= score_a, (
            f"pct_b={pct_b:.4f}% <= pct_a={pct_a:.4f}% 时，"
            f"score_b={score_b:.4f} 应 >= score_a={score_a:.4f}"
        )


# ---------------------------------------------------------------------------
# Property 7: MA 趋势短期均线斜率优先
# Feature: screening-parameter-optimization, Property 7: MA 趋势短期均线斜率优先
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_long_strategy)
def test_short_term_slope_weight_is_double_long_term(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 7: MA 趋势短期均线斜率优先

    **Validates: Requirements 4.2**

    对任意收盘价序列，斜率分量中短期均线（5 日、10 日）的权重系数应为
    长期均线（60 日、120 日）权重系数的 2 倍。

    验证方式：检查模块常量中短期权重 = 2.0，长期权重 = 1.0，
    并验证 score_ma_trend 内部使用了这些权重进行加权平均。
    """
    # 验证权重常量关系
    assert _SHORT_TERM_SLOPE_WEIGHT == 2.0 * _LONG_TERM_SLOPE_WEIGHT, (
        f"短期权重 {_SHORT_TERM_SLOPE_WEIGHT} 应为长期权重 {_LONG_TERM_SLOPE_WEIGHT} 的 2 倍"
    )
    assert _SHORT_TERM_PERIODS == {5, 10}, (
        f"短期均线周期应为 {{5, 10}}，实际={_SHORT_TERM_PERIODS}"
    )

    # 使用默认周期计算趋势评分
    periods = [5, 10, 20, 60, 120]
    ma_dict = calculate_multi_ma(closes, periods)
    alignment = detect_bullish_alignment(closes, periods, ma_dict)

    # 手动计算加权平均斜率，验证权重分配
    sorted_periods = sorted(periods)
    weighted_sum = 0.0
    total_w = 0.0
    for p in sorted_periods:
        if p not in alignment.slopes:
            continue
        raw_slope = alignment.slopes[p]
        filtered = max(raw_slope, 0.0) if raw_slope > 0.0 else 0.0
        w = _SHORT_TERM_SLOPE_WEIGHT if p in _SHORT_TERM_PERIODS else _LONG_TERM_SLOPE_WEIGHT
        weighted_sum += filtered * w
        total_w += w

    if total_w > 0:
        expected_avg = weighted_sum / total_w
    else:
        expected_avg = 0.0

    # 验证 score_ma_trend 的斜率分与手动计算一致
    result = score_ma_trend(closes, periods)
    expected_slope_score = min(expected_avg * 100.0, 100.0)
    assert abs(result.slope_score - expected_slope_score) < 1e-6, (
        f"斜率分不一致：result.slope_score={result.slope_score:.6f}，"
        f"expected={expected_slope_score:.6f}"
    )


# ---------------------------------------------------------------------------
# Property 8: MA 趋势评分范围不变量与幂等性
# Feature: screening-parameter-optimization, Property 8: MA 趋势评分范围不变量与幂等性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_close_price_short_strategy)
def test_score_ma_trend_range_invariant(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 8: MA 趋势评分范围不变量与幂等性

    **Validates: Requirements 4.3**

    对任意有效收盘价序列，score_ma_trend 返回的评分始终在 [0, 100] 闭区间内。
    各分项（alignment_score, slope_score, distance_score）也在 [0, 100] 内。
    """
    result = score_ma_trend(closes)

    assert isinstance(result, MATrendScore), "返回类型应为 MATrendScore"
    assert 0.0 <= result.score <= 100.0, (
        f"总评分应在 [0, 100]，实际={result.score:.4f}"
    )
    assert 0.0 <= result.alignment_score <= 100.0, (
        f"排列程度分应在 [0, 100]，实际={result.alignment_score:.4f}"
    )
    assert 0.0 <= result.slope_score <= 100.0, (
        f"斜率分应在 [0, 100]，实际={result.slope_score:.4f}"
    )
    assert 0.0 <= result.distance_score <= 100.0, (
        f"距离分应在 [0, 100]，实际={result.distance_score:.4f}"
    )


@settings(max_examples=100)
@given(closes=_close_price_short_strategy)
def test_score_ma_trend_idempotent(closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 8: MA 趋势评分范围不变量与幂等性

    **Validates: Requirements 4.5**

    对任意有效收盘价序列，多次调用 score_ma_trend 返回完全相同的结果（幂等性）。
    """
    result1 = score_ma_trend(closes)
    result2 = score_ma_trend(closes)

    assert result1.score == result2.score, (
        f"幂等性违反：第一次={result1.score:.6f}，第二次={result2.score:.6f}"
    )
    assert result1.alignment_score == result2.alignment_score, (
        f"排列程度分幂等性违反：{result1.alignment_score} != {result2.alignment_score}"
    )
    assert result1.slope_score == result2.slope_score, (
        f"斜率分幂等性违反：{result1.slope_score} != {result2.slope_score}"
    )
    assert result1.distance_score == result2.distance_score, (
        f"距离分幂等性违反：{result1.distance_score} != {result2.distance_score}"
    )
    assert result1.is_bullish_aligned == result2.is_bullish_aligned, (
        f"多头排列标记幂等性违反：{result1.is_bullish_aligned} != {result2.is_bullish_aligned}"
    )
