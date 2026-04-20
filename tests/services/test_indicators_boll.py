"""
BOLL 信号检测单元测试

覆盖场景：
- 连续 2 日站稳中轨触发信号（signal=True）
- 仅 1 日站稳不触发信号（signal=False）
- 上轨风险标记独立性（near_upper_band 与 signal 独立）
- 数据不足（signal=False）

需求: 2.1, 2.2, 2.3
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.indicators import (
    BOLLResult,
    BOLLSignalResult,
    calculate_boll,
    detect_boll_signal,
    _count_hold_days_above_middle,
    DEFAULT_BOLL_PERIOD,
)


# ---------------------------------------------------------------------------
# 辅助：构造 BOLLResult 并直接注入 detect_boll_signal
# ---------------------------------------------------------------------------


def _make_boll_result(
    upper: list[float],
    middle: list[float],
    lower: list[float],
) -> BOLLResult:
    """构造 BOLLResult 用于直接注入测试。"""
    return BOLLResult(upper=upper, middle=middle, lower=lower)


# ---------------------------------------------------------------------------
# 连续 2 日站稳中轨触发信号
# ---------------------------------------------------------------------------


class TestTwoDayHoldTriggersSignal:
    """连续 2 日站稳中轨触发 BOLL 信号（需求 2.1）"""

    def test_two_consecutive_days_above_middle_triggers_signal(self):
        """最后 2 日收盘价均 > 中轨 → signal=True"""
        # 构造：最后 2 天收盘价高于中轨
        closes = [10.0, 10.0, 10.0, 10.5, 10.8]
        middle = [10.0, 10.0, 10.0, 10.2, 10.3]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[3]=10.5 > mid[3]=10.2 ✓
        # close[4]=10.8 > mid[4]=10.3 ✓

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is True
        assert result.hold_days >= 2

    def test_many_days_above_middle_triggers_signal(self):
        """连续多日站稳中轨 → signal=True, hold_days 反映实际天数"""
        n = 10
        closes = [15.0] * n
        middle = [10.0] * n
        upper = [20.0] * n
        lower = [5.0] * n

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is True
        assert result.hold_days == n  # 全部天数都站稳

    def test_real_calculation_two_day_hold(self):
        """使用真实 calculate_boll 计算，构造连续 2 日站稳的场景"""
        # 先用稳定价格建立布林带，然后最后 2 天价格突破中轨
        n = 25
        # 前 23 天价格稳定在 100 附近
        closes = [100.0] * 23
        # 最后 2 天价格上涨，突破中轨
        closes.append(105.0)
        closes.append(106.0)

        result = detect_boll_signal(closes)

        # 中轨约为 100 附近（20 日均线），105 和 106 应该 > 中轨
        assert result.signal is True
        assert result.hold_days >= 2


# ---------------------------------------------------------------------------
# 仅 1 日站稳不触发信号
# ---------------------------------------------------------------------------


class TestOneDayHoldNoSignal:
    """仅 1 日站稳中轨不触发信号（需求 2.3）"""

    def test_only_today_above_middle_no_signal(self):
        """仅当日收盘价 > 中轨，前一日 <= 中轨 → signal=False"""
        closes = [10.0, 10.0, 10.0, 9.8, 10.5]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[3]=9.8 <= mid[3]=10.0 ✗
        # close[4]=10.5 > mid[4]=10.0 ✓
        # 仅 1 日站稳 → signal=False

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is False

    def test_only_prev_day_above_middle_no_signal(self):
        """仅前一日收盘价 > 中轨，当日 <= 中轨 → signal=False"""
        closes = [10.0, 10.0, 10.0, 10.5, 9.8]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[3]=10.5 > mid[3]=10.0 ✓
        # close[4]=9.8 <= mid[4]=10.0 ✗

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is False

    def test_both_days_at_middle_no_signal(self):
        """最后 2 日收盘价 == 中轨（不严格大于）→ signal=False"""
        closes = [10.0, 10.0, 10.0, 10.0, 10.0]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close == mid → 不满足 close > mid

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is False


# ---------------------------------------------------------------------------
# 上轨风险标记独立性
# ---------------------------------------------------------------------------


class TestNearUpperBandIndependence:
    """near_upper_band 与 signal 独立（需求 2.2）"""

    def test_near_upper_band_true_with_signal_true(self):
        """收盘价接近上轨且站稳中轨 → near_upper_band=True, signal=True"""
        closes = [10.0, 10.0, 10.0, 11.8, 11.9]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[3]=11.8 > mid[3]=10.0 ✓
        # close[4]=11.9 > mid[4]=10.0 ✓ → signal=True
        # close[4]=11.9 >= upper[4]*0.98 = 12.0*0.98 = 11.76 ✓ → near_upper_band=True

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is True
        assert result.near_upper_band is True

    def test_near_upper_band_true_with_signal_false(self):
        """收盘价接近上轨但未站稳中轨 → near_upper_band=True, signal=False"""
        closes = [10.0, 10.0, 10.0, 9.5, 11.9]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[3]=9.5 <= mid[3]=10.0 ✗ → signal=False
        # close[4]=11.9 >= 11.76 ✓ → near_upper_band=True

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is False
        assert result.near_upper_band is True

    def test_near_upper_band_false_with_signal_true(self):
        """收盘价远离上轨但站稳中轨 → near_upper_band=False, signal=True"""
        closes = [10.0, 10.0, 10.0, 10.5, 10.8]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [15.0, 15.0, 15.0, 15.0, 15.0]
        lower = [5.0, 5.0, 5.0, 5.0, 5.0]
        # close[3]=10.5 > mid[3]=10.0 ✓
        # close[4]=10.8 > mid[4]=10.0 ✓ → signal=True
        # close[4]=10.8 < upper[4]*0.98 = 15.0*0.98 = 14.7 ✗ → near_upper_band=False

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is True
        assert result.near_upper_band is False

    def test_near_upper_band_false_with_signal_false(self):
        """收盘价远离上轨且未站稳中轨 → near_upper_band=False, signal=False"""
        closes = [10.0, 10.0, 10.0, 9.5, 9.8]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [15.0, 15.0, 15.0, 15.0, 15.0]
        lower = [5.0, 5.0, 5.0, 5.0, 5.0]
        # close[3]=9.5 <= mid[3]=10.0 ✗ → signal=False
        # close[4]=9.8 < 14.7 ✗ → near_upper_band=False

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.signal is False
        assert result.near_upper_band is False

    def test_exact_threshold_near_upper_band(self):
        """收盘价恰好等于 upper × 0.98 → near_upper_band=True"""
        closes = [10.0, 10.0, 10.0, 10.5, 11.76]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[4]=11.76 == upper[4]*0.98 = 11.76 → near_upper_band=True

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.near_upper_band is True

    def test_just_below_threshold_near_upper_band(self):
        """收盘价略低于 upper × 0.98 → near_upper_band=False"""
        closes = [10.0, 10.0, 10.0, 10.5, 11.75]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        upper = [12.0, 12.0, 12.0, 12.0, 12.0]
        lower = [8.0, 8.0, 8.0, 8.0, 8.0]
        # close[4]=11.75 < upper[4]*0.98 = 11.76 → near_upper_band=False

        boll_result = _make_boll_result(upper, middle, lower)
        result = detect_boll_signal(closes, boll_result=boll_result)

        assert result.near_upper_band is False


# ---------------------------------------------------------------------------
# 数据不足
# ---------------------------------------------------------------------------


class TestInsufficientData:
    """数据不足时返回 signal=False"""

    def test_empty_closes(self):
        """空收盘价序列 → signal=False"""
        result = detect_boll_signal([])
        assert result.signal is False
        assert result.near_upper_band is False
        assert result.hold_days == 0
        assert result.upper == []

    def test_single_close(self):
        """仅一个收盘价 → signal=False（数据不足 2 天）"""
        result = detect_boll_signal([10.0])
        assert result.signal is False
        assert result.near_upper_band is False
        assert result.hold_days == 0

    def test_short_sequence_no_valid_boll(self):
        """收盘价序列短于 BOLL 周期 → 中轨全为 NaN，signal=False"""
        closes = [float(10 + i * 0.5) for i in range(15)]
        result = detect_boll_signal(closes)  # 默认 period=20，15 < 20
        assert result.signal is False
        assert result.near_upper_band is False

    def test_exactly_period_length(self):
        """收盘价序列恰好等于 BOLL 周期 → 仅最后一天有中轨，前一天无效 → signal=False"""
        closes = [100.0] * DEFAULT_BOLL_PERIOD
        result = detect_boll_signal(closes)
        # period=20 时，middle[19] 有效，middle[18] 为 NaN → 无法判断 2 日站稳
        assert result.signal is False

    def test_period_plus_one_allows_signal(self):
        """收盘价序列为 BOLL 周期 + 1 → 最后 2 天中轨有效，可判断信号"""
        # 构造价格使得最后 2 天都高于中轨
        n = DEFAULT_BOLL_PERIOD + 1  # 21
        closes = [100.0] * n
        # 最后 2 天价格上涨
        closes[-2] = 105.0
        closes[-1] = 106.0

        result = detect_boll_signal(closes)
        # 中轨约为 100 附近，105 和 106 > 中轨 → signal=True
        assert result.signal is True


# ---------------------------------------------------------------------------
# _count_hold_days_above_middle 辅助函数
# ---------------------------------------------------------------------------


class TestCountHoldDaysAboveMiddle:
    """连续站稳中轨天数计算辅助函数"""

    def test_all_above_middle(self):
        """全部天数收盘价 > 中轨 → hold_days = n"""
        closes = [15.0, 16.0, 17.0, 18.0, 19.0]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        assert _count_hold_days_above_middle(closes, middle) == 5

    def test_none_above_middle(self):
        """全部天数收盘价 <= 中轨 → hold_days = 0"""
        closes = [9.0, 8.0, 7.0, 6.0, 5.0]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        assert _count_hold_days_above_middle(closes, middle) == 0

    def test_last_two_above_middle(self):
        """最后 2 天站稳，之前不满足 → hold_days = 2"""
        closes = [9.0, 9.0, 9.0, 11.0, 12.0]
        middle = [10.0, 10.0, 10.0, 10.0, 10.0]
        assert _count_hold_days_above_middle(closes, middle) == 2

    def test_middle_contains_nan(self):
        """中轨含 NaN 时在 NaN 处中断计数"""
        closes = [15.0, 15.0, 15.0, 15.0, 15.0]
        middle = [10.0, 10.0, float("nan"), 10.0, 10.0]
        # 从最后一天向前：close[4]>mid[4] ✓, close[3]>mid[3] ✓, mid[2]=NaN → 中断
        assert _count_hold_days_above_middle(closes, middle) == 2

    def test_empty_data(self):
        """空数据 → hold_days = 0"""
        assert _count_hold_days_above_middle([], []) == 0

    def test_close_equals_middle_not_counted(self):
        """收盘价 == 中轨不算站稳（需要严格大于）"""
        closes = [10.0, 10.0, 10.0]
        middle = [10.0, 10.0, 10.0]
        assert _count_hold_days_above_middle(closes, middle) == 0


# ---------------------------------------------------------------------------
# 结构化返回值完整性
# ---------------------------------------------------------------------------


class TestBOLLSignalResultStructure:
    """BOLLSignalResult 结构化返回值验证"""

    def test_result_contains_all_fields(self):
        """返回结果包含 signal、near_upper_band、hold_days、upper、middle、lower 字段"""
        closes = [float(10 + i * 0.5) for i in range(25)]
        result = detect_boll_signal(closes)

        assert isinstance(result, BOLLSignalResult)
        assert isinstance(result.signal, bool)
        assert isinstance(result.near_upper_band, bool)
        assert isinstance(result.hold_days, int)
        assert len(result.upper) == len(closes)
        assert len(result.middle) == len(closes)
        assert len(result.lower) == len(closes)

    def test_precomputed_boll_result_reused(self):
        """传入预计算的 BOLLResult 时复用其数据"""
        closes = [float(10 + i * 0.5) for i in range(25)]
        boll_result = calculate_boll(closes)
        result = detect_boll_signal(closes, boll_result=boll_result)

        # 上轨/中轨/下轨应与预计算结果一致
        assert result.upper == boll_result.upper
        assert result.middle == boll_result.middle
        assert result.lower == boll_result.lower
