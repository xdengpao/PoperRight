"""
相对资金流信号属性测试（Hypothesis）

**Validates: Requirements 6.1, 6.3**

Property 10: 相对资金流信号
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.volume_price import check_money_flow_signal_relative


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 每日净流入序列：合理范围内的浮点数列表
_inflows_strategy = st.lists(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=60,
)

# 每日成交额序列：非负浮点数列表
_amounts_strategy = st.lists(
    st.floats(min_value=0.0, max_value=1e8, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=60,
)

# 相对阈值百分比
_threshold_pct_strategy = st.floats(
    min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False,
)

# 连续天数
_consecutive_strategy = st.integers(min_value=1, max_value=10)

# 日均成交额计算周期
_period_strategy = st.integers(min_value=1, max_value=60)


# ---------------------------------------------------------------------------
# 辅助：独立计算期望信号（参考模型）
# ---------------------------------------------------------------------------

def _reference_relative_signal(
    daily_inflows: list[float],
    daily_amounts: list[float],
    relative_threshold_pct: float,
    consecutive: int,
    amount_period: int,
) -> tuple[bool, bool, int]:
    """
    参考模型：独立于被测函数的相对资金流信号计算。

    返回 (signal, fallback_needed, consecutive_days)
    """
    if len(daily_inflows) == 0 or len(daily_amounts) == 0:
        return False, True, 0

    window = daily_amounts[-amount_period:] if len(daily_amounts) >= amount_period else daily_amounts
    avg = sum(window) / len(window)

    if avg <= 0:
        return False, True, 0

    threshold_ratio = relative_threshold_pct / 100.0
    count = 0
    for i in range(len(daily_inflows) - 1, -1, -1):
        if daily_inflows[i] / avg >= threshold_ratio:
            count += 1
        else:
            break

    return count >= consecutive, False, count


# ---------------------------------------------------------------------------
# Property 10: 相对资金流信号
# Feature: screening-parameter-optimization, Property 10: 相对资金流信号
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    inflows=_inflows_strategy,
    amounts=_amounts_strategy,
    threshold_pct=_threshold_pct_strategy,
    consecutive=_consecutive_strategy,
    period=_period_strategy,
)
def test_relative_money_flow_matches_reference_model(
    inflows: list[float],
    amounts: list[float],
    threshold_pct: float,
    consecutive: int,
    period: int,
):
    """
    # Feature: screening-parameter-optimization, Property 10: 相对资金流信号

    **Validates: Requirements 6.1, 6.3**

    对任意净流入序列和成交额序列，check_money_flow_signal_relative 的返回值
    应与参考模型一致：signal=True 当且仅当最近 consecutive 天的
    net_inflow / avg_daily_amount >= relative_threshold_pct%。
    """
    result = check_money_flow_signal_relative(
        daily_inflows=inflows,
        daily_amounts=amounts,
        relative_threshold_pct=threshold_pct,
        consecutive=consecutive,
        amount_period=period,
    )
    expected_signal, expected_fallback, expected_count = _reference_relative_signal(
        inflows, amounts, threshold_pct, consecutive, period,
    )

    assert result.signal == expected_signal, (
        f"信号不一致：actual={result.signal}, expected={expected_signal}, "
        f"inflows={inflows}, amounts={amounts}, threshold_pct={threshold_pct}"
    )
    assert result.fallback_needed == expected_fallback, (
        f"回退标记不一致：actual={result.fallback_needed}, expected={expected_fallback}"
    )
    assert result.consecutive_days == expected_count, (
        f"连续天数不一致：actual={result.consecutive_days}, expected={expected_count}"
    )


@settings(max_examples=200)
@given(
    inflows=_inflows_strategy,
    amounts=_amounts_strategy,
    threshold_pct=_threshold_pct_strategy,
    consecutive=_consecutive_strategy,
    period=_period_strategy,
)
def test_relative_money_flow_fallback_when_avg_amount_non_positive(
    inflows: list[float],
    amounts: list[float],
    threshold_pct: float,
    consecutive: int,
    period: int,
):
    """
    # Feature: screening-parameter-optimization, Property 10: 相对资金流信号

    **Validates: Requirements 6.1, 6.3**

    当 avg_daily_amount <= 0 时，signal 必须为 False 且 fallback_needed 为 True。
    """
    # 计算 avg_daily_amount
    window = amounts[-period:] if len(amounts) >= period else amounts
    avg = sum(window) / len(window) if window else 0.0

    result = check_money_flow_signal_relative(
        daily_inflows=inflows,
        daily_amounts=amounts,
        relative_threshold_pct=threshold_pct,
        consecutive=consecutive,
        amount_period=period,
    )

    if avg <= 0:
        assert result.signal is False, (
            f"avg_daily_amount <= 0 时 signal 应为 False，实际={result.signal}"
        )
        assert result.fallback_needed is True, (
            f"avg_daily_amount <= 0 时 fallback_needed 应为 True，实际={result.fallback_needed}"
        )


@settings(max_examples=200)
@given(
    inflows=_inflows_strategy,
    amounts=st.lists(
        st.floats(min_value=100.0, max_value=1e8, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=60,
    ),
    threshold_pct=_threshold_pct_strategy,
    consecutive=_consecutive_strategy,
    period=_period_strategy,
)
def test_relative_money_flow_signal_implies_consecutive_days(
    inflows: list[float],
    amounts: list[float],
    threshold_pct: float,
    consecutive: int,
    period: int,
):
    """
    # Feature: screening-parameter-optimization, Property 10: 相对资金流信号

    **Validates: Requirements 6.3**

    当 signal=True 时，consecutive_days 必须 >= consecutive 要求。
    当 signal=False 且 fallback_needed=False 时，consecutive_days < consecutive。
    """
    result = check_money_flow_signal_relative(
        daily_inflows=inflows,
        daily_amounts=amounts,
        relative_threshold_pct=threshold_pct,
        consecutive=consecutive,
        amount_period=period,
    )

    if result.signal:
        assert result.consecutive_days >= consecutive, (
            f"signal=True 时 consecutive_days 应 >= {consecutive}，"
            f"实际={result.consecutive_days}"
        )
    elif not result.fallback_needed:
        assert result.consecutive_days < consecutive, (
            f"signal=False 且非回退时 consecutive_days 应 < {consecutive}，"
            f"实际={result.consecutive_days}"
        )
