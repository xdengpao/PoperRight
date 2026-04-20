"""
MA 趋势评分单元测试

覆盖：
- _bell_curve_distance_score: 钟形曲线各区间边界值
- score_ma_trend: 短期斜率权重 2 倍验证、评分范围 [0, 100]

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

# Feature: screening-parameter-optimization
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.ma_trend import (
    _bell_curve_distance_score,
    score_ma_trend,
    calculate_multi_ma,
    detect_bullish_alignment,
    _SHORT_TERM_SLOPE_WEIGHT,
    _LONG_TERM_SLOPE_WEIGHT,
    _SHORT_TERM_PERIODS,
    MATrendScore,
)


# ---------------------------------------------------------------------------
# _bell_curve_distance_score 钟形曲线各区间边界值测试
# Feature: screening-parameter-optimization, Property 6: MA 趋势距离分钟形曲线形状
# ---------------------------------------------------------------------------


class TestBellCurveDistanceScore:
    """钟形曲线距离评分边界值测试"""

    # ── 最优区间 [0%, 3%]：满分 100 ──

    def test_pct_0_returns_100(self):
        """0% 距离应返回满分 100"""
        assert _bell_curve_distance_score(0.0) == pytest.approx(100.0)

    def test_pct_3_returns_100(self):
        """3% 距离（最优区间上界）应返回满分 100"""
        assert _bell_curve_distance_score(3.0) == pytest.approx(100.0)

    # ── 线性递减区间 (3%, 5%]：100 → 60 ──

    def test_pct_4_returns_80(self):
        """4% 距离应返回 80 分（3% 到 5% 线性递减中点）"""
        # 100 - (4 - 3) * (40 / 2) = 100 - 20 = 80
        assert _bell_curve_distance_score(4.0) == pytest.approx(80.0)

    def test_pct_5_returns_60(self):
        """5% 距离应返回 60 分"""
        assert _bell_curve_distance_score(5.0) == pytest.approx(60.0)

    # ── 线性递减区间 (5%, 10%]：60 → 20 ──

    def test_pct_7_5_returns_40(self):
        """7.5% 距离应返回 40 分（5% 到 10% 线性递减中点）"""
        # 60 - (7.5 - 5) * (40 / 5) = 60 - 20 = 40
        assert _bell_curve_distance_score(7.5) == pytest.approx(40.0)

    def test_pct_10_returns_20(self):
        """10% 距离应返回 20 分"""
        assert _bell_curve_distance_score(10.0) == pytest.approx(20.0)

    # ── 超过 10%：固定 20 分 ──

    def test_pct_15_returns_20(self):
        """15% 距离应返回固定 20 分"""
        assert _bell_curve_distance_score(15.0) == pytest.approx(20.0)

    # ── 负值区间（价格在均线下方）：线性递减 100 → 0 ──

    def test_pct_neg_2_5_returns_50(self):
        """-2.5% 距离应返回 50 分（-5% 到 0% 线性递减中点）"""
        # 100 + (-2.5) * (100 / 5) = 100 - 50 = 50
        assert _bell_curve_distance_score(-2.5) == pytest.approx(50.0)

    def test_pct_neg_5_returns_0(self):
        """-5% 距离应返回 0 分"""
        assert _bell_curve_distance_score(-5.0) == pytest.approx(0.0)

    def test_pct_neg_beyond_5_clamped_to_0(self):
        """低于 -5% 的距离应被截断为 0 分"""
        assert _bell_curve_distance_score(-10.0) == pytest.approx(0.0)

    # ── 评分范围 [0, 100] 不变量 ──

    def test_score_always_in_range(self):
        """各种边界值的评分均在 [0, 100] 范围内"""
        test_values = [-10.0, -5.0, -2.5, 0.0, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 100.0]
        for pct in test_values:
            score = _bell_curve_distance_score(pct)
            assert 0.0 <= score <= 100.0, (
                f"pct={pct}% 时评分 {score} 超出 [0, 100] 范围"
            )

    # ── 单调性验证 ──

    def test_monotonically_non_increasing_above_3pct(self):
        """3% 以上区间评分单调不增"""
        pcts = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 15.0, 20.0]
        scores = [_bell_curve_distance_score(p) for p in pcts]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"单调性违反：score({pcts[i]}%)={scores[i]} < score({pcts[i+1]}%)={scores[i+1]}"
            )

    def test_near_optimal_scores_higher_than_far(self):
        """最优区间内的评分高于远离区间的评分"""
        assert _bell_curve_distance_score(2.0) >= _bell_curve_distance_score(6.0)
        assert _bell_curve_distance_score(0.0) >= _bell_curve_distance_score(4.0)


# ---------------------------------------------------------------------------
# score_ma_trend 短期斜率权重 2 倍验证
# Feature: screening-parameter-optimization, Property 7: MA 趋势短期均线斜率优先
# ---------------------------------------------------------------------------


class TestMATrendSlopeWeights:
    """短期均线斜率权重 2 倍验证"""

    def test_short_term_weight_is_double_long_term(self):
        """短期均线权重系数应为长期均线权重系数的 2 倍"""
        assert _SHORT_TERM_SLOPE_WEIGHT == 2.0
        assert _LONG_TERM_SLOPE_WEIGHT == 1.0
        assert _SHORT_TERM_SLOPE_WEIGHT == 2.0 * _LONG_TERM_SLOPE_WEIGHT

    def test_short_term_periods_are_5_and_10(self):
        """短期均线周期应为 5 日和 10 日"""
        assert _SHORT_TERM_PERIODS == {5, 10}

    def test_slope_score_reflects_weighted_average(self):
        """斜率分应反映加权平均（短期权重 2 倍）"""
        # 构造持续上涨序列，确保所有均线斜率为正
        closes = [10.0 + i * 0.5 for i in range(150)]
        periods = [5, 10, 20, 60, 120]

        result = score_ma_trend(closes, periods)

        # 手动计算加权平均斜率
        ma_dict = calculate_multi_ma(closes, periods)
        alignment = detect_bullish_alignment(closes, periods, ma_dict)

        weighted_sum = 0.0
        total_w = 0.0
        for p in sorted(periods):
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

        expected_slope_score = min(expected_avg * 100.0, 100.0)
        assert result.slope_score == pytest.approx(expected_slope_score, rel=1e-6), (
            f"斜率分不一致：实际={result.slope_score:.6f}，期望={expected_slope_score:.6f}"
        )


# ---------------------------------------------------------------------------
# score_ma_trend 评分范围 [0, 100] 验证
# Feature: screening-parameter-optimization, Property 8: MA 趋势评分范围不变量与幂等性
# ---------------------------------------------------------------------------


class TestMATrendScoreRange:
    """评分范围 [0, 100] 验证"""

    def test_uptrend_score_in_range(self):
        """上涨趋势评分在 [0, 100]"""
        closes = [10.0 + i * 0.5 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert 0.0 <= result.score <= 100.0

    def test_downtrend_score_in_range(self):
        """下跌趋势评分在 [0, 100]"""
        closes = [200.0 - i * 0.5 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert 0.0 <= result.score <= 100.0

    def test_flat_price_score_in_range(self):
        """横盘价格评分在 [0, 100]"""
        closes = [50.0] * 150
        result = score_ma_trend(closes, [5, 10, 20])
        assert 0.0 <= result.score <= 100.0

    def test_empty_closes_returns_zero(self):
        """空序列返回 0 分"""
        result = score_ma_trend([])
        assert result.score == 0.0

    def test_short_sequence_score_in_range(self):
        """短序列评分在 [0, 100]"""
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = score_ma_trend(closes, [3, 5])
        assert 0.0 <= result.score <= 100.0

    def test_volatile_price_score_in_range(self):
        """剧烈波动价格评分在 [0, 100]"""
        import random
        random.seed(42)
        closes = [random.uniform(1.0, 500.0) for _ in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert 0.0 <= result.score <= 100.0

    def test_idempotent_same_input_same_output(self):
        """同一输入多次调用返回相同结果（幂等性）"""
        closes = [10.0 + i * 0.3 for i in range(150)]
        result1 = score_ma_trend(closes, [5, 10, 20])
        result2 = score_ma_trend(closes, [5, 10, 20])
        assert result1.score == result2.score
        assert result1.alignment_score == result2.alignment_score
        assert result1.slope_score == result2.slope_score
        assert result1.distance_score == result2.distance_score

    def test_all_components_in_range(self):
        """所有分项评分均在 [0, 100]"""
        closes = [10.0 + i * 0.3 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20, 60, 120])
        assert 0.0 <= result.alignment_score <= 100.0
        assert 0.0 <= result.slope_score <= 100.0
        assert 0.0 <= result.distance_score <= 100.0
