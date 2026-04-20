"""
ATR 自适应止损属性测试（Hypothesis）

**Validates: Requirements 4.2, 4.3, 4.8**

Property 3: ATR 自适应止损计算正确性与范围不变量

For any valid ATR (> 0), cost_price (> 0), peak_price (> 0), and positive multiplier,
when ATR × fixed_multiplier < cost_price:
- Fixed stop price SHALL equal cost_price - ATR × fixed_multiplier
- Fixed stop price SHALL be > 0 and < cost_price
- Trailing retrace pct SHALL equal ATR × trailing_multiplier / peak_price
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import StopLossChecker


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 正价格：合理的 A 股价格范围
_price = st.floats(
    min_value=1.0, max_value=5000.0, allow_nan=False, allow_infinity=False,
)

# ATR 值：正数，合理范围
_atr = st.floats(
    min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False,
)

# 倍数：正数
_multiplier = st.floats(
    min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 3: ATR 自适应止损计算正确性与范围不变量
# ---------------------------------------------------------------------------


class TestATRStopLossProperties:
    """ATR 自适应止损计算属性测试。

    Feature: risk-control-enhancement, Property 3: ATR 自适应止损计算正确性与范围不变量
    """

    @given(
        cost_price=_price,
        atr=_atr,
        fixed_multiplier=_multiplier,
    )
    @settings(max_examples=200)
    def test_fixed_stop_price_equals_formula(
        self, cost_price: float, atr: float, fixed_multiplier: float,
    ) -> None:
        """固定止损价 SHALL 等于 cost_price - ATR × fixed_multiplier。

        **Validates: Requirements 4.2**
        """
        assume(atr * fixed_multiplier < cost_price)

        stop_price = StopLossChecker.compute_atr_fixed_stop_price(
            cost_price, atr, fixed_multiplier,
        )

        expected = cost_price - atr * fixed_multiplier
        assert math.isclose(stop_price, expected, rel_tol=1e-9), (
            f"stop_price={stop_price} != expected={expected}"
        )

    @given(
        cost_price=_price,
        atr=_atr,
        fixed_multiplier=_multiplier,
    )
    @settings(max_examples=200)
    def test_fixed_stop_price_range_invariant(
        self, cost_price: float, atr: float, fixed_multiplier: float,
    ) -> None:
        """当 ATR × fixed_multiplier < cost_price 时，固定止损价 SHALL > 0 且 < cost_price。

        **Validates: Requirements 4.8**
        """
        assume(atr * fixed_multiplier < cost_price)

        stop_price = StopLossChecker.compute_atr_fixed_stop_price(
            cost_price, atr, fixed_multiplier,
        )

        assert stop_price > 0, f"stop_price={stop_price} should be > 0"
        assert stop_price < cost_price, (
            f"stop_price={stop_price} should be < cost_price={cost_price}"
        )

    @given(
        atr=_atr,
        peak_price=_price,
        trailing_multiplier=_multiplier,
    )
    @settings(max_examples=200)
    def test_trailing_retrace_pct_equals_formula(
        self, atr: float, peak_price: float, trailing_multiplier: float,
    ) -> None:
        """移动止损回撤比例 SHALL 等于 ATR × trailing_multiplier / peak_price。

        **Validates: Requirements 4.3**
        """
        retrace_pct = StopLossChecker.compute_atr_trailing_retrace_pct(
            atr, peak_price, trailing_multiplier,
        )

        expected = atr * trailing_multiplier / peak_price
        assert math.isclose(retrace_pct, expected, rel_tol=1e-9), (
            f"retrace_pct={retrace_pct} != expected={expected}"
        )

    @given(
        cost_price=_price,
        current_price=_price,
        peak_price=_price,
        atr=_atr,
        fixed_multiplier=_multiplier,
        trailing_multiplier=_multiplier,
    )
    @settings(max_examples=200)
    def test_pure_function_consistency(
        self,
        cost_price: float,
        current_price: float,
        peak_price: float,
        atr: float,
        fixed_multiplier: float,
        trailing_multiplier: float,
    ) -> None:
        """纯函数版本的结果 SHALL 与单独调用各方法的结果一致。

        **Validates: Requirements 4.2, 4.3**
        """
        assume(atr * fixed_multiplier < cost_price)
        assume(peak_price >= current_price)

        result = StopLossChecker.compute_atr_stop_loss_pure(
            cost_price=cost_price,
            current_price=current_price,
            peak_price=peak_price,
            atr=atr,
            fixed_multiplier=fixed_multiplier,
            trailing_multiplier=trailing_multiplier,
        )

        # 固定止损价一致性
        expected_fixed = StopLossChecker.compute_atr_fixed_stop_price(
            cost_price, atr, fixed_multiplier,
        )
        assert math.isclose(
            result["fixed_stop_price"], expected_fixed, rel_tol=1e-9,
        )

        # 移动止损回撤比例一致性
        expected_trailing = StopLossChecker.compute_atr_trailing_retrace_pct(
            atr, peak_price, trailing_multiplier,
        )
        assert math.isclose(
            result["trailing_retrace_pct"], expected_trailing, rel_tol=1e-9,
        )

        # 固定止损触发状态一致性
        assert result["fixed_triggered"] == (current_price <= expected_fixed)

        # 移动止损触发状态一致性
        actual_retrace = (peak_price - current_price) / peak_price if peak_price > 0 else 0.0
        assert result["trailing_triggered"] == (actual_retrace >= expected_trailing)

    @given(
        atr=_atr,
        peak_price=_price,
        trailing_multiplier=_multiplier,
    )
    @settings(max_examples=200)
    def test_trailing_retrace_pct_non_negative(
        self, atr: float, peak_price: float, trailing_multiplier: float,
    ) -> None:
        """移动止损回撤比例 SHALL 始终 >= 0。

        **Validates: Requirements 4.3**
        """
        retrace_pct = StopLossChecker.compute_atr_trailing_retrace_pct(
            atr, peak_price, trailing_multiplier,
        )
        assert retrace_pct >= 0, f"retrace_pct={retrace_pct} should be >= 0"
