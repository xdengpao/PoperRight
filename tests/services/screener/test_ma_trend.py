"""
均线趋势选股模块单元测试

覆盖：
- calculate_ma: MA 计算正确性
- detect_bullish_alignment: 多头排列识别
- score_ma_trend: 趋势打分算法
- detect_ma_support: 均线支撑形态识别
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.ma_trend import (
    calculate_ma,
    calculate_multi_ma,
    detect_bullish_alignment,
    detect_ma_support,
    score_ma_trend,
    DEFAULT_MA_PERIODS,
)


# ---------------------------------------------------------------------------
# calculate_ma
# ---------------------------------------------------------------------------

class TestCalculateMA:
    """测试移动平均线计算"""

    def test_basic_5day_ma(self):
        """5 日 MA 基本计算"""
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        result = calculate_ma(closes, 5)
        # 前 4 个为 NaN
        for i in range(4):
            assert math.isnan(result[i])
        # MA[4] = (10+11+12+13+14)/5 = 12.0
        assert result[4] == pytest.approx(12.0)
        # MA[5] = (11+12+13+14+15)/5 = 13.0
        assert result[5] == pytest.approx(13.0)

    def test_single_period_ma(self):
        """1 日 MA 等于原始价格"""
        closes = [5.0, 10.0, 15.0]
        result = calculate_ma(closes, 1)
        assert result == [5.0, 10.0, 15.0]

    def test_ma_length_equals_input(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_ma(closes, 3)
        assert len(result) == len(closes)

    def test_insufficient_data(self):
        """数据不足时全部为 NaN"""
        closes = [1.0, 2.0]
        result = calculate_ma(closes, 5)
        assert all(math.isnan(v) for v in result)

    def test_empty_closes(self):
        result = calculate_ma([], 5)
        assert result == []

    def test_zero_period(self):
        result = calculate_ma([1.0, 2.0], 0)
        assert all(math.isnan(v) for v in result)

    def test_negative_period(self):
        result = calculate_ma([1.0, 2.0], -1)
        assert all(math.isnan(v) for v in result)

    def test_ma_arithmetic_mean_correctness(self):
        """属性 5：MA 值等于窗口内收盘价的算术平均值"""
        closes = [3.0, 7.0, 2.0, 9.0, 5.0, 8.0, 1.0, 6.0, 4.0, 10.0]
        period = 3
        result = calculate_ma(closes, period)
        for t in range(period - 1, len(closes)):
            window = closes[t - period + 1 : t + 1]
            expected = sum(window) / period
            assert result[t] == pytest.approx(expected, rel=1e-6)



# ---------------------------------------------------------------------------
# calculate_multi_ma
# ---------------------------------------------------------------------------

class TestCalculateMultiMA:
    def test_default_periods(self):
        closes = list(range(1, 130))  # 129 data points
        result = calculate_multi_ma([float(c) for c in closes])
        assert set(result.keys()) == set(DEFAULT_MA_PERIODS)

    def test_custom_periods(self):
        closes = [float(i) for i in range(1, 30)]
        result = calculate_multi_ma(closes, [3, 5, 10])
        assert set(result.keys()) == {3, 5, 10}


# ---------------------------------------------------------------------------
# detect_bullish_alignment
# ---------------------------------------------------------------------------

class TestDetectBullishAlignment:
    """测试多头排列识别"""

    def test_perfect_bullish_alignment(self):
        """完美多头排列：价格持续上涨"""
        # 生成持续上涨序列，足够长以计算所有均线
        closes = [10.0 + i * 0.5 for i in range(150)]
        result = detect_bullish_alignment(closes, [5, 10, 20])
        assert result.is_aligned is True
        assert result.aligned_pairs == result.total_pairs
        assert result.slopes_positive is True

    def test_bearish_alignment(self):
        """空头排列：价格持续下跌"""
        closes = [100.0 - i * 0.5 for i in range(150)]
        result = detect_bullish_alignment(closes, [5, 10, 20])
        assert result.is_aligned is False

    def test_empty_closes(self):
        result = detect_bullish_alignment([], [5, 10])
        assert result.is_aligned is False
        assert result.aligned_pairs == 0

    def test_partial_alignment(self):
        """部分排列：短期 MA 在上但斜率不全为正"""
        # 先涨后平
        closes = [10.0 + i * 0.5 for i in range(100)]
        closes.extend([60.0] * 50)  # 后 50 天横盘
        result = detect_bullish_alignment(closes, [5, 10, 20])
        # 横盘后短期 MA 斜率接近 0，可能不满足完全多头
        assert result.total_pairs == 2

    def test_precomputed_ma_dict(self):
        """使用预计算的 MA 字典"""
        closes = [10.0 + i * 0.5 for i in range(50)]
        periods = [5, 10]
        ma_dict = calculate_multi_ma(closes, periods)
        result = detect_bullish_alignment(closes, periods, ma_dict)
        assert result.total_pairs == 1


# ---------------------------------------------------------------------------
# score_ma_trend
# ---------------------------------------------------------------------------

class TestScoreMATrend:
    """测试趋势打分算法"""

    def test_score_range_0_100(self):
        """打分始终在 [0, 100]"""
        # 上涨趋势
        closes_up = [10.0 + i * 0.5 for i in range(150)]
        result_up = score_ma_trend(closes_up, [5, 10, 20])
        assert 0.0 <= result_up.score <= 100.0

        # 下跌趋势
        closes_down = [100.0 - i * 0.5 for i in range(150)]
        result_down = score_ma_trend(closes_down, [5, 10, 20])
        assert 0.0 <= result_down.score <= 100.0

    def test_strong_uptrend_high_score(self):
        """强上涨趋势应获得高分"""
        closes = [10.0 + i * 1.0 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert result.score >= 70.0
        assert result.is_bullish_aligned is True

    def test_strong_downtrend_low_score(self):
        """强下跌趋势应获得低分"""
        closes = [200.0 - i * 1.0 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert result.score < 50.0

    def test_empty_closes_zero_score(self):
        result = score_ma_trend([])
        assert result.score == 0.0

    def test_score_components_present(self):
        """打分结果应包含三个分项"""
        closes = [10.0 + i * 0.3 for i in range(150)]
        result = score_ma_trend(closes, [5, 10, 20])
        assert 0.0 <= result.alignment_score <= 100.0
        assert 0.0 <= result.slope_score <= 100.0
        assert 0.0 <= result.distance_score <= 100.0


# ---------------------------------------------------------------------------
# detect_ma_support
# ---------------------------------------------------------------------------

class TestDetectMASupport:
    """测试均线支撑形态识别"""

    def test_support_at_20day_ma(self):
        """价格回调至 20 日均线后反弹"""
        # 构造：先上涨建立均线，然后回调至 20 日 MA 附近，再反弹
        closes = [10.0 + i * 0.5 for i in range(30)]  # 上涨 30 天
        # 计算当前 20 日 MA 大约值
        ma20_approx = sum(closes[-20:]) / 20
        # 回调至 MA 附近
        closes.append(ma20_approx * 1.005)  # 触及 MA（在 2% 内）
        # 反弹 2 天
        closes.append(ma20_approx * 1.03)
        closes.append(ma20_approx * 1.04)

        result = detect_ma_support(
            closes, periods=[5, 10, 20], support_periods=[20],
            touch_pct=0.02, rebound_days=2,
        )
        assert result.detected is True
        assert result.support_ma_period == 20
        assert result.rebound_confirmed is True

    def test_no_support_when_price_far_from_ma(self):
        """价格远离均线时不应检测到支撑"""
        closes = [10.0 + i * 1.0 for i in range(50)]
        result = detect_ma_support(closes, periods=[5, 10, 20], support_periods=[20])
        assert result.detected is False

    def test_no_support_insufficient_data(self):
        """数据不足时不应检测到支撑"""
        closes = [10.0, 11.0, 12.0]
        result = detect_ma_support(closes, periods=[5, 10, 20], support_periods=[20])
        assert result.detected is False

    def test_no_rebound_no_signal(self):
        """触及均线但未反弹，不应生成信号"""
        closes = [10.0 + i * 0.5 for i in range(30)]
        ma20_approx = sum(closes[-20:]) / 20
        # 触及 MA
        closes.append(ma20_approx * 1.005)
        # 继续下跌（未反弹）
        closes.append(ma20_approx * 0.95)
        closes.append(ma20_approx * 0.93)

        result = detect_ma_support(
            closes, periods=[5, 10, 20], support_periods=[20],
            touch_pct=0.02, rebound_days=2,
        )
        assert result.detected is False
