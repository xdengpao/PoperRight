"""
总仓位控制属性测试（Hypothesis）

**Validates: Requirements 5.1, 5.3, 5.4, 5.5, 5.9**

Property 4: 总仓位比例范围不变量
For any valid total_market_value (≥ 0) and available_cash (≥ 0),
when both are not zero simultaneously, the result SHALL be in [0, 100].
When market_value is 0, result SHALL be 0.
When cash is 0, result SHALL be 100.

Property 5: 大盘风险等级与总仓位上限映射
For any MarketRiskLevel, get_total_position_limit_by_risk_level SHALL return:
NORMAL → 80.0, CAUTION → 60.0, DANGER → 30.0.
And NORMAL > CAUTION > DANGER (monotonically decreasing).
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import MarketRiskLevel
from app.services.risk_controller import PositionRiskChecker


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 非负金额：合理的资产范围
_non_negative_amount = st.floats(
    min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False,
)

# 正金额：用于非零场景
_positive_amount = st.floats(
    min_value=0.01, max_value=1e12, allow_nan=False, allow_infinity=False,
)

# 大盘风险等级
_risk_level = st.sampled_from(list(MarketRiskLevel))

# 仓位上限百分比
_limit_pct = st.floats(
    min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 4: 总仓位比例范围不变量
# ---------------------------------------------------------------------------


class TestTotalPositionPctProperties:
    """总仓位比例计算属性测试。

    Feature: risk-control-enhancement, Property 4: 总仓位比例范围不变量
    """

    @given(
        total_market_value=_non_negative_amount,
        available_cash=_non_negative_amount,
    )
    @settings(max_examples=200)
    def test_result_in_0_100_range(
        self, total_market_value: float, available_cash: float,
    ) -> None:
        """当两者不同时为零时，总仓位比例 SHALL 在 [0, 100] 范围内。

        **Validates: Requirements 5.1, 5.9**
        """
        assume(total_market_value + available_cash > 0)

        pct = PositionRiskChecker.compute_total_position_pct(
            total_market_value, available_cash,
        )

        assert 0.0 <= pct <= 100.0, (
            f"总仓位比例 {pct} 不在 [0, 100] 范围内 "
            f"(market_value={total_market_value}, cash={available_cash})"
        )

    @given(available_cash=_positive_amount)
    @settings(max_examples=200)
    def test_zero_market_value_returns_zero(
        self, available_cash: float,
    ) -> None:
        """当持仓市值为 0 时，结果 SHALL 为 0。

        **Validates: Requirements 5.9**
        """
        pct = PositionRiskChecker.compute_total_position_pct(0.0, available_cash)

        assert pct == 0.0, (
            f"持仓市值为 0 时，总仓位比例应为 0，实际为 {pct}"
        )

    @given(total_market_value=_positive_amount)
    @settings(max_examples=200)
    def test_zero_cash_returns_100(
        self, total_market_value: float,
    ) -> None:
        """当可用现金为 0 时，结果 SHALL 为 100。

        **Validates: Requirements 5.9**
        """
        pct = PositionRiskChecker.compute_total_position_pct(total_market_value, 0.0)

        assert math.isclose(pct, 100.0, rel_tol=1e-9), (
            f"可用现金为 0 时，总仓位比例应为 100，实际为 {pct}"
        )

    def test_both_zero_returns_zero(self) -> None:
        """当持仓市值和可用现金均为 0 时，结果 SHALL 为 0。

        **Validates: Requirements 5.1**
        """
        pct = PositionRiskChecker.compute_total_position_pct(0.0, 0.0)
        assert pct == 0.0

    @given(
        total_market_value=_positive_amount,
        available_cash=_positive_amount,
    )
    @settings(max_examples=200)
    def test_formula_correctness(
        self, total_market_value: float, available_cash: float,
    ) -> None:
        """总仓位比例 SHALL 等于 market_value / (market_value + cash) × 100。

        **Validates: Requirements 5.1**
        """
        pct = PositionRiskChecker.compute_total_position_pct(
            total_market_value, available_cash,
        )

        expected = total_market_value / (total_market_value + available_cash) * 100.0
        assert math.isclose(pct, expected, rel_tol=1e-9), (
            f"总仓位比例 {pct} != 预期 {expected}"
        )

    @given(
        total_market_value=_non_negative_amount,
        available_cash=_non_negative_amount,
        limit_pct=_limit_pct,
    )
    @settings(max_examples=200)
    def test_check_total_position_limit_consistency(
        self, total_market_value: float, available_cash: float, limit_pct: float,
    ) -> None:
        """check_total_position_limit 的结果 SHALL 与 compute_total_position_pct 一致。

        **Validates: Requirements 5.1**
        """
        assume(total_market_value + available_cash > 0)

        pct = PositionRiskChecker.compute_total_position_pct(
            total_market_value, available_cash,
        )
        result = PositionRiskChecker.check_total_position_limit(
            total_market_value, available_cash, limit_pct,
        )

        if pct > limit_pct:
            assert not result.passed, (
                f"仓位 {pct:.2f}% > 上限 {limit_pct:.2f}%，应返回 passed=False"
            )
        else:
            assert result.passed, (
                f"仓位 {pct:.2f}% <= 上限 {limit_pct:.2f}%，应返回 passed=True"
            )


# ---------------------------------------------------------------------------
# Property 5: 大盘风险等级与总仓位上限映射
# ---------------------------------------------------------------------------


class TestRiskLevelPositionLimitProperties:
    """大盘风险等级与总仓位上限映射属性测试。

    Feature: risk-control-enhancement, Property 5: 大盘风险等级与总仓位上限映射
    """

    @given(risk_level=_risk_level)
    @settings(max_examples=100)
    def test_mapping_correctness(self, risk_level: MarketRiskLevel) -> None:
        """get_total_position_limit_by_risk_level SHALL 返回正确的映射值。

        NORMAL → 80.0, CAUTION → 60.0, DANGER → 30.0

        **Validates: Requirements 5.3, 5.4, 5.5**
        """
        limit = PositionRiskChecker.get_total_position_limit_by_risk_level(risk_level)

        expected_map = {
            MarketRiskLevel.NORMAL: 80.0,
            MarketRiskLevel.CAUTION: 60.0,
            MarketRiskLevel.DANGER: 30.0,
        }

        assert limit == expected_map[risk_level], (
            f"风险等级 {risk_level.value} 的仓位上限应为 {expected_map[risk_level]}，"
            f"实际为 {limit}"
        )

    def test_monotonically_decreasing(self) -> None:
        """NORMAL 的上限 > CAUTION 的上限 > DANGER 的上限（单调递减）。

        **Validates: Requirements 5.3, 5.4, 5.5**
        """
        normal_limit = PositionRiskChecker.get_total_position_limit_by_risk_level(
            MarketRiskLevel.NORMAL,
        )
        caution_limit = PositionRiskChecker.get_total_position_limit_by_risk_level(
            MarketRiskLevel.CAUTION,
        )
        danger_limit = PositionRiskChecker.get_total_position_limit_by_risk_level(
            MarketRiskLevel.DANGER,
        )

        assert normal_limit > caution_limit > danger_limit, (
            f"仓位上限应单调递减: NORMAL({normal_limit}) > CAUTION({caution_limit}) > DANGER({danger_limit})"
        )

    @given(risk_level=_risk_level)
    @settings(max_examples=100)
    def test_limit_is_positive(self, risk_level: MarketRiskLevel) -> None:
        """所有风险等级的仓位上限 SHALL 为正数。

        **Validates: Requirements 5.3, 5.4, 5.5**
        """
        limit = PositionRiskChecker.get_total_position_limit_by_risk_level(risk_level)
        assert limit > 0, f"风险等级 {risk_level.value} 的仓位上限应为正数，实际为 {limit}"
