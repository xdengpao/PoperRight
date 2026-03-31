"""
BacktestEngine 涨跌停价格计算属性测试（Hypothesis）

**Validates: Requirements 12.33**

属性 22j：涨跌停价格计算正确性
- 对任意正数 prev_close，涨停价 == round(prev_close × 1.10, 2)
- 对任意正数 prev_close，跌停价 == round(prev_close × 0.90, 2)
- 涨停价 > 跌停价
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# A股股价范围：最低 0.05 元（保证 ±10% 四舍五入后涨停价 > 跌停价），最高数千元
# 当 prev_close < 0.05 时，round(p*1.10, 2) == round(p*0.90, 2)，属于极端仙股边界
_prev_close = st.decimals(
    min_value=Decimal("0.05"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# 属性 22j：涨跌停价格计算正确性
# ---------------------------------------------------------------------------


@given(prev_close=_prev_close)
@settings(max_examples=100)
def test_limit_price_calculation_correctness(prev_close: Decimal) -> None:
    """
    **Validates: Requirements 12.33**

    属性 22j：对任意正数 prev_close，验证：
    1. 涨停价 == round(prev_close × 1.10, 2)
    2. 跌停价 == round(prev_close × 0.90, 2)
    3. 涨停价 > 跌停价
    """
    limit_up, limit_down = BacktestEngine._calc_limit_prices(prev_close)

    expected_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
    expected_down = (prev_close * Decimal("0.90")).quantize(Decimal("0.01"))

    assert limit_up == expected_up, (
        f"涨停价不正确: got {limit_up}, expected {expected_up} "
        f"(prev_close={prev_close})"
    )
    assert limit_down == expected_down, (
        f"跌停价不正确: got {limit_down}, expected {expected_down} "
        f"(prev_close={prev_close})"
    )
    assert limit_up > limit_down, (
        f"涨停价应大于跌停价: limit_up={limit_up}, limit_down={limit_down} "
        f"(prev_close={prev_close})"
    )
