"""
破位检测属性测试（Hypothesis）

Property 7: 放宽版破位检测（三满足二）
For any combination of three boolean conditions (below MA20, drop > 5%, high volume),
the relaxed breakdown detection SHALL return True when exactly 2 or 3 conditions are true,
and False when 0 or 1 conditions are true.

Property 8: 连续阴跌检测局部性不变量
For any closing price sequence and parameter N, prepending any arbitrary price data
to the sequence SHALL NOT change the consecutive decline detection result
(only depends on the last N+1 data points).

**Validates: Requirements 7.3, 7.6**
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import PositionRiskChecker


# ---------------------------------------------------------------------------
# 常量（与 risk_controller.py 保持一致）
# ---------------------------------------------------------------------------

_BREAKDOWN_DECLINE_THRESHOLD = -5.0  # 破位下跌幅度阈值 (%)
_RELAXED_VOLUME_RATIO = 2.0          # 放宽版放量阈值（量比）


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 价格：正浮点数
_price = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

# MA20 值：正浮点数
_ma20 = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

# 涨跌幅百分比
_daily_change_pct = st.floats(min_value=-99.0, max_value=99.0, allow_nan=False, allow_infinity=False)

# 量比
_volume_ratio = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# 收盘价序列（用于阴跌检测）
_close_price = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

# N 天参数
_n_days = st.integers(min_value=1, max_value=10)

# 阈值百分比
_threshold_pct = st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 7: 放宽版破位检测（三满足二）
# ---------------------------------------------------------------------------


class TestBreakdownRelaxedProperties:
    """放宽版破位检测属性测试。

    Feature: risk-control-enhancement, Property 7: 放宽版破位检测（三满足二）
    """

    @given(
        current_price=_price,
        ma20=_ma20,
        daily_change_pct=_daily_change_pct,
        volume_ratio=_volume_ratio,
    )
    @settings(max_examples=200)
    def test_relaxed_breakdown_two_of_three(
        self,
        current_price: float,
        ma20: float,
        daily_change_pct: float,
        volume_ratio: float,
    ) -> None:
        """放宽版破位检测 SHALL 在恰好两个或三个条件为真时返回 True，
        在零个或一个条件为真时返回 False。

        **Validates: Requirements 7.3**
        """
        # 计算三个条件
        below_ma20 = current_price < ma20
        heavy_decline = daily_change_pct < _BREAKDOWN_DECLINE_THRESHOLD
        heavy_volume = volume_ratio > _RELAXED_VOLUME_RATIO
        true_count = sum([below_ma20, heavy_decline, heavy_volume])

        result = PositionRiskChecker.check_position_breakdown_relaxed(
            current_price, ma20, daily_change_pct, volume_ratio,
        )

        if true_count >= 2:
            assert result is True, (
                f"当 {true_count} 个条件为真时应返回 True，"
                f"条件: below_ma20={below_ma20}, heavy_decline={heavy_decline}, "
                f"heavy_volume={heavy_volume}"
            )
        else:
            assert result is False, (
                f"当 {true_count} 个条件为真时应返回 False，"
                f"条件: below_ma20={below_ma20}, heavy_decline={heavy_decline}, "
                f"heavy_volume={heavy_volume}"
            )

    @given(
        current_price=_price,
        ma20=_ma20,
        daily_change_pct=_daily_change_pct,
        volume_ratio=_volume_ratio,
    )
    @settings(max_examples=200)
    def test_relaxed_is_superset_of_strict(
        self,
        current_price: float,
        ma20: float,
        daily_change_pct: float,
        volume_ratio: float,
    ) -> None:
        """放宽版破位检测触发时，原严格版不一定触发；
        但原严格版触发时，放宽版必定触发（放宽版是严格版的超集）。

        **Validates: Requirements 7.3**
        """
        strict = PositionRiskChecker.check_position_breakdown(
            current_price, ma20, daily_change_pct, volume_ratio,
        )
        relaxed = PositionRiskChecker.check_position_breakdown_relaxed(
            current_price, ma20, daily_change_pct, volume_ratio,
        )

        if strict:
            assert relaxed is True, (
                "严格版触发时，放宽版也必须触发"
            )

    def test_all_three_true(self) -> None:
        """三个条件全部为真时返回 True。

        **Validates: Requirements 7.3**
        """
        # below_ma20: 9.0 < 10.0 ✓, heavy_decline: -6.0 < -5.0 ✓, heavy_volume: 3.0 > 2.0 ✓
        assert PositionRiskChecker.check_position_breakdown_relaxed(
            9.0, 10.0, -6.0, 3.0,
        ) is True

    def test_exactly_two_true(self) -> None:
        """恰好两个条件为真时返回 True。

        **Validates: Requirements 7.3**
        """
        # below_ma20 ✓, heavy_decline ✓, heavy_volume ✗
        assert PositionRiskChecker.check_position_breakdown_relaxed(
            9.0, 10.0, -6.0, 1.0,
        ) is True

    def test_only_one_true(self) -> None:
        """仅一个条件为真时返回 False。

        **Validates: Requirements 7.3**
        """
        # below_ma20 ✓, heavy_decline ✗, heavy_volume ✗
        assert PositionRiskChecker.check_position_breakdown_relaxed(
            9.0, 10.0, -3.0, 1.0,
        ) is False

    def test_none_true(self) -> None:
        """零个条件为真时返回 False。

        **Validates: Requirements 7.3**
        """
        # below_ma20 ✗, heavy_decline ✗, heavy_volume ✗
        assert PositionRiskChecker.check_position_breakdown_relaxed(
            11.0, 10.0, 2.0, 0.5,
        ) is False


# ---------------------------------------------------------------------------
# Property 8: 连续阴跌检测局部性不变量
# ---------------------------------------------------------------------------


class TestConsecutiveDeclineProperties:
    """连续阴跌检测属性测试。

    Feature: risk-control-enhancement, Property 8: 连续阴跌检测局部性不变量
    """

    @given(
        closes=st.lists(_close_price, min_size=2, max_size=50),
        n_days=_n_days,
        threshold_pct=_threshold_pct,
        prefix=st.lists(_close_price, min_size=0, max_size=30),
    )
    @settings(max_examples=200)
    def test_locality_invariant(
        self,
        closes: list[float],
        n_days: int,
        threshold_pct: float,
        prefix: list[float],
    ) -> None:
        """在序列前面追加任意长度的任意价格数据后，
        连续阴跌检测结果 SHALL 保持不变（仅依赖最近 N+1 个数据点）。

        **Validates: Requirements 7.6**
        """
        # 确保有足够数据
        assume(len(closes) >= n_days + 1)

        # 原始序列的检测结果
        original_result = PositionRiskChecker.check_consecutive_decline_pure(
            closes, n_days, threshold_pct,
        )

        # 在前面追加任意数据后的检测结果
        extended = prefix + closes
        extended_result = PositionRiskChecker.check_consecutive_decline_pure(
            extended, n_days, threshold_pct,
        )

        assert original_result == extended_result, (
            f"追加前缀后结果不一致: 原始={original_result}, 追加后={extended_result}, "
            f"前缀长度={len(prefix)}, 原始序列长度={len(closes)}, n_days={n_days}"
        )

    @given(
        closes=st.lists(_close_price, min_size=2, max_size=50),
        n_days=_n_days,
        threshold_pct=_threshold_pct,
    )
    @settings(max_examples=200)
    def test_only_depends_on_last_n_plus_1(
        self,
        closes: list[float],
        n_days: int,
        threshold_pct: float,
    ) -> None:
        """检测结果仅依赖最近 N+1 个数据点。

        **Validates: Requirements 7.6**
        """
        assume(len(closes) >= n_days + 1)

        # 完整序列的结果
        full_result = PositionRiskChecker.check_consecutive_decline_pure(
            closes, n_days, threshold_pct,
        )

        # 仅使用最近 N+1 个数据点的结果
        tail = closes[-(n_days + 1):]
        tail_result = PositionRiskChecker.check_consecutive_decline_pure(
            tail, n_days, threshold_pct,
        )

        assert full_result == tail_result, (
            f"完整序列与尾部 N+1 个数据点结果不一致: "
            f"full={full_result}, tail={tail_result}, "
            f"序列长度={len(closes)}, n_days={n_days}"
        )

    def test_insufficient_data_returns_false(self) -> None:
        """数据不足 N+1 个时返回 False。

        **Validates: Requirements 7.6**
        """
        # n_days=3 需要 4 个数据点，只给 3 个
        assert PositionRiskChecker.check_consecutive_decline_pure(
            [10.0, 9.0, 8.0], n_days=3,
        ) is False

    def test_consecutive_decline_triggers(self) -> None:
        """连续 3 日下跌且累计跌幅超过 8% 时返回 True。

        **Validates: Requirements 7.6**
        """
        # 100 → 96 → 92 → 88: 连续 3 日下跌，累计跌幅 12%
        assert PositionRiskChecker.check_consecutive_decline_pure(
            [100.0, 96.0, 92.0, 88.0], n_days=3, threshold_pct=8.0,
        ) is True

    def test_non_consecutive_decline_returns_false(self) -> None:
        """非连续下跌时返回 False。

        **Validates: Requirements 7.6**
        """
        # 100 → 96 → 97 → 88: 第 2 天上涨，不是连续下跌
        assert PositionRiskChecker.check_consecutive_decline_pure(
            [100.0, 96.0, 97.0, 88.0], n_days=3, threshold_pct=8.0,
        ) is False

    def test_decline_below_threshold_returns_false(self) -> None:
        """连续下跌但累计跌幅未超过阈值时返回 False。

        **Validates: Requirements 7.6**
        """
        # 100 → 99 → 98 → 97: 连续 3 日下跌，但累计跌幅仅 3%
        assert PositionRiskChecker.check_consecutive_decline_pure(
            [100.0, 99.0, 98.0, 97.0], n_days=3, threshold_pct=8.0,
        ) is False

    def test_empty_closes_returns_false(self) -> None:
        """空序列返回 False。

        **Validates: Requirements 7.6**
        """
        assert PositionRiskChecker.check_consecutive_decline_pure(
            [], n_days=3,
        ) is False
