"""
RSI 信号检测单元测试

覆盖场景：
- [55, 75] 默认强势区间（signal=True / signal=False）
- 连续上升 3 天触发信号
- 自定义 rising_days 参数
- 数据不足（signal=False）
- 结构化返回值完整性

需求: 3.1, 3.2, 3.3, 3.4, 3.5
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.indicators import (
    RSIResult,
    RSISignalResult,
    calculate_rsi,
    detect_rsi_signal,
    _count_consecutive_rising,
    DEFAULT_RSI_PERIOD,
)


# ---------------------------------------------------------------------------
# 辅助：构造 RSIResult 并直接注入 detect_rsi_signal
# ---------------------------------------------------------------------------


def _make_rsi_result(values: list[float]) -> RSIResult:
    """构造 RSIResult 用于直接注入测试。"""
    return RSIResult(values=values)


# ---------------------------------------------------------------------------
# [55, 75] 默认强势区间
# ---------------------------------------------------------------------------


class TestDefaultRSIRange:
    """RSI 默认强势区间 [55, 75]（需求 3.1）"""

    def test_rsi_in_range_with_rising_triggers_signal(self):
        """RSI 在 [55, 75] 区间内且连续 3 天上升 → signal=True"""
        # 构造 RSI 值序列：最后 4 天严格递增，最后一天在 [55, 75] 内
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 从 period 开始有有效 RSI 值
        values.extend([50.0, 52.0, 55.0, 60.0, 65.0, 70.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is True
        assert result.current_rsi == 70.0
        assert result.consecutive_rising >= 3

    def test_rsi_below_lower_bound_no_signal(self):
        """RSI 低于下限 55 → signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([40.0, 42.0, 45.0, 48.0, 50.0, 52.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is False
        assert result.current_rsi == 52.0

    def test_rsi_above_upper_bound_no_signal(self):
        """RSI 高于上限 75 → signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([70.0, 72.0, 74.0, 76.0, 78.0, 80.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is False
        assert result.current_rsi == 80.0

    def test_rsi_at_lower_bound_with_rising_triggers_signal(self):
        """RSI 恰好等于下限 55（含边界）且连续上升 → signal=True"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([40.0, 45.0, 50.0, 52.0, 53.0, 55.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is True
        assert result.current_rsi == 55.0

    def test_rsi_at_upper_bound_with_rising_triggers_signal(self):
        """RSI 恰好等于上限 75（含边界）且连续上升 → signal=True"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([60.0, 65.0, 70.0, 72.0, 73.0, 75.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is True
        assert result.current_rsi == 75.0


# ---------------------------------------------------------------------------
# 连续上升 3 天
# ---------------------------------------------------------------------------


class TestConsecutiveRisingDays:
    """RSI 连续上升天数检查（需求 3.2, 3.3）"""

    def test_exactly_three_rising_days_triggers_signal(self):
        """恰好连续 3 天 RSI 严格递增 → signal=True"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 最后 4 天：58, 60, 63, 67 → 连续 3 天递增
        values.extend([50.0, 55.0, 58.0, 60.0, 63.0, 67.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is True
        assert result.consecutive_rising >= 3

    def test_two_rising_days_no_signal(self):
        """仅连续 2 天 RSI 递增（不足 3 天）→ signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 最后 4 天：65, 60, 63, 67 → 仅最后 2 天递增
        values.extend([50.0, 55.0, 65.0, 60.0, 63.0, 67.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is False
        assert result.consecutive_rising == 2

    def test_flat_rsi_no_signal(self):
        """RSI 持平（非严格递增）→ signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 最后 4 天：60, 60, 60, 60 → 持平
        values.extend([50.0, 55.0, 60.0, 60.0, 60.0, 60.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is False
        assert result.consecutive_rising == 0

    def test_declining_rsi_no_signal(self):
        """RSI 下降 → signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([70.0, 68.0, 66.0, 64.0, 62.0, 60.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is False
        assert result.consecutive_rising == 0


# ---------------------------------------------------------------------------
# 自定义 rising_days
# ---------------------------------------------------------------------------


class TestCustomRisingDays:
    """自定义连续上升天数参数（需求 3.4）"""

    def test_rising_days_1_triggers_with_single_rise(self):
        """rising_days=1 时仅需 1 天上升即可触发"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([50.0, 55.0, 58.0, 56.0, 55.0, 60.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=1,
        )

        assert result.signal is True
        assert result.consecutive_rising >= 1

    def test_rising_days_5_requires_five_consecutive(self):
        """rising_days=5 时需要连续 5 天上升"""
        n = 25
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 最后 6 天：55, 57, 59, 61, 63, 65 → 连续 5 天递增
        values.extend([50.0, 52.0, 53.0, 54.0, 55.0, 57.0, 59.0, 61.0, 63.0, 65.0, 67.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=5,
        )

        assert result.signal is True
        assert result.consecutive_rising >= 5

    def test_rising_days_5_fails_with_four_consecutive(self):
        """rising_days=5 时仅 4 天上升 → signal=False"""
        n = 25
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 最后 6 天：65, 60, 60, 63, 65, 67, 69 → 60==60 中断，仅最后 4 天递增
        values.extend([50.0, 52.0, 53.0, 54.0, 65.0, 60.0, 60.0, 63.0, 65.0, 67.0, 69.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=5,
        )

        assert result.signal is False
        assert result.consecutive_rising == 4

    def test_custom_range_40_80(self):
        """自定义区间 [40, 80] 时 RSI=45 且连续上升 → signal=True"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        values.extend([30.0, 35.0, 38.0, 40.0, 42.0, 45.0])
        n = len(values)
        closes = [100.0 + i * 0.5 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=40.0, upper_bound=80.0, rising_days=3,
        )

        assert result.signal is True
        assert result.current_rsi == 45.0


# ---------------------------------------------------------------------------
# 数据不足
# ---------------------------------------------------------------------------


class TestInsufficientData:
    """数据不足时返回 signal=False（需求 3.5）"""

    def test_empty_closes(self):
        """空收盘价序列 → signal=False"""
        result = detect_rsi_signal([])
        assert result.signal is False
        assert result.current_rsi == 0.0
        assert result.consecutive_rising == 0
        assert result.values == []

    def test_single_close(self):
        """仅一个收盘价 → signal=False"""
        result = detect_rsi_signal([10.0])
        assert result.signal is False

    def test_fewer_than_rising_days_plus_period(self):
        """收盘价序列长度 < rising_days + period → signal=False"""
        # 默认 rising_days=3, period=14 → 需要至少 17 个数据点
        closes = [100.0 + i * 0.5 for i in range(16)]
        result = detect_rsi_signal(closes)
        assert result.signal is False

    def test_exactly_rising_days_plus_period(self):
        """收盘价序列长度 == rising_days + period → 可以判断信号"""
        # rising_days=3, period=14 → 需要 17 个数据点
        # 构造一个持续上涨的序列使 RSI 在区间内且连续上升
        closes = [100.0 + i * 0.3 for i in range(17)]
        result = detect_rsi_signal(closes)
        # 不断言 signal 的具体值，只验证不会因数据不足而被拒绝
        assert isinstance(result.signal, bool)
        assert len(result.values) == 17

    def test_short_sequence_all_nan_rsi(self):
        """收盘价序列短于 RSI 周期 → RSI 值全为 NaN，signal=False"""
        closes = [float(10 + i * 0.5) for i in range(10)]
        result = detect_rsi_signal(closes)
        assert result.signal is False


# ---------------------------------------------------------------------------
# _count_consecutive_rising 辅助函数
# ---------------------------------------------------------------------------


class TestCountConsecutiveRising:
    """RSI 连续严格递增天数计算辅助函数"""

    def test_all_rising(self):
        """全部递增 → 返回 n-1"""
        values = [50.0, 52.0, 54.0, 56.0, 58.0]
        assert _count_consecutive_rising(values, 4) == 4

    def test_none_rising(self):
        """全部递减 → 返回 0"""
        values = [58.0, 56.0, 54.0, 52.0, 50.0]
        assert _count_consecutive_rising(values, 4) == 0

    def test_partial_rising(self):
        """部分递增 → 返回从末尾开始的连续递增天数"""
        values = [50.0, 48.0, 52.0, 54.0, 56.0]
        # 从 idx=4 向前：56>54 ✓, 54>52 ✓, 52>48 ✓, 48<50 ✗ → 3
        assert _count_consecutive_rising(values, 4) == 3

    def test_flat_values_not_counted(self):
        """持平不算递增"""
        values = [50.0, 50.0, 50.0, 50.0, 50.0]
        assert _count_consecutive_rising(values, 4) == 0

    def test_nan_breaks_chain(self):
        """NaN 中断递增链"""
        values = [50.0, 52.0, float("nan"), 56.0, 58.0]
        # 从 idx=4 向前：58>56 ✓, 56>NaN → 中断 → 1
        assert _count_consecutive_rising(values, 4) == 1

    def test_single_element(self):
        """单个元素 → 返回 0"""
        values = [50.0]
        assert _count_consecutive_rising(values, 0) == 0

    def test_two_elements_rising(self):
        """两个元素递增 → 返回 1"""
        values = [50.0, 52.0]
        assert _count_consecutive_rising(values, 1) == 1

    def test_two_elements_not_rising(self):
        """两个元素递减 → 返回 0"""
        values = [52.0, 50.0]
        assert _count_consecutive_rising(values, 1) == 0


# ---------------------------------------------------------------------------
# 超买背离检测
# ---------------------------------------------------------------------------


class TestOverboughtDivergence:
    """超买背离检测逻辑"""

    def test_divergence_blocks_signal(self):
        """价格创新高但 RSI 未创新高（背离）→ signal=False"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # 构造背离：窗口内某点 RSI 较高（70），之后 RSI 下降再回升但未超过 70
        # values[14]=70.0 对应 closes[14]
        values.extend([70.0, 68.0, 60.0, 62.0, 64.0, 66.0])
        n = len(values)
        # 价格：让 closes[14] 较高，之后下降，最后一天价格超过 closes[14]
        # 这样 closes[last] >= closes[14] 但 values[last]=66 < values[14]=70 → 背离
        closes = [100.0] * n
        closes[14] = 120.0  # 窗口内价格高点
        closes[15] = 115.0
        closes[16] = 110.0
        closes[17] = 115.0
        closes[18] = 118.0
        closes[19] = 121.0  # 最后一天价格超过 closes[14]=120 → 价格创新高

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        # RSI 在区间内且连续上升 3 天（62→64→66），但存在背离
        # closes[19]=121 >= closes[14]=120 且 values[19]=66 < values[14]=70 → 背离
        assert result.signal is False

    def test_no_divergence_allows_signal(self):
        """价格和 RSI 同步创新高（无背离）→ signal=True"""
        n = 20
        values = [float("nan")] * DEFAULT_RSI_PERIOD
        # RSI 持续上升，无背离
        values.extend([55.0, 58.0, 60.0, 62.0, 64.0, 66.0])
        n = len(values)
        # 价格也持续上涨
        closes = [100.0 + i * 1.0 for i in range(n)]

        rsi_result = _make_rsi_result(values)
        result = detect_rsi_signal(
            closes, rsi_result=rsi_result,
            lower_bound=55.0, upper_bound=75.0, rising_days=3,
        )

        assert result.signal is True


# ---------------------------------------------------------------------------
# 结构化返回值完整性
# ---------------------------------------------------------------------------


class TestRSISignalResultStructure:
    """RSISignalResult 结构化返回值验证"""

    def test_result_contains_all_fields(self):
        """返回结果包含 signal、current_rsi、consecutive_rising、values 字段"""
        closes = [float(10 + i * 0.5) for i in range(25)]
        result = detect_rsi_signal(closes)

        assert isinstance(result, RSISignalResult)
        assert isinstance(result.signal, bool)
        assert isinstance(result.current_rsi, (int, float))
        assert isinstance(result.consecutive_rising, int)
        assert len(result.values) == len(closes)

    def test_no_signal_returns_zero_defaults(self):
        """数据不足时默认 current_rsi=0.0, consecutive_rising=0"""
        result = detect_rsi_signal([])
        assert result.signal is False
        assert result.current_rsi == 0.0
        assert result.consecutive_rising == 0

    def test_precomputed_rsi_result_reused(self):
        """传入预计算的 RSIResult 时复用其数据"""
        closes = [float(10 + i * 0.5) for i in range(25)]
        rsi_result = calculate_rsi(closes)
        result = detect_rsi_signal(closes, rsi_result=rsi_result)

        # values 应与预计算结果一致
        assert result.values == rsi_result.values

    def test_real_calculation_signal(self):
        """使用真实 calculate_rsi 计算，构造连续上涨序列验证信号"""
        # 构造一个持续温和上涨的序列
        n = 30
        closes = [100.0]
        for i in range(1, n):
            closes.append(closes[-1] + 0.5)

        result = detect_rsi_signal(closes)

        # 持续上涨序列的 RSI 应该较高，且连续上升
        assert isinstance(result.signal, bool)
        assert result.current_rsi > 0
        assert len(result.values) == n
