"""
突破信号属性测试（Hypothesis）

**Validates: Requirements 7.1, 7.2, 7.3, 7.5**

Property 11: 突破成交量持续性分类
Property 12: 突破横盘整理加分
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.breakout import (
    check_consolidation_bonus,
    check_volume_sustainability,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 突破日成交量：正整数，范围 [1, 10_000_000]
_breakout_volume_strategy = st.integers(min_value=1, max_value=10_000_000)

# 突破后各交易日成交量列表：0 到 10_000_000 的整数列表
_post_volumes_strategy = st.lists(
    st.integers(min_value=0, max_value=10_000_000),
    min_size=0,
    max_size=10,
)

# 箱体整理期天数：[1, 100]
_box_period_strategy = st.integers(min_value=1, max_value=100)


# ---------------------------------------------------------------------------
# Property 11: 突破成交量持续性分类
# Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    breakout_volume=_breakout_volume_strategy,
    post_volumes=_post_volumes_strategy,
)
def test_volume_sustainability_returns_none_when_insufficient_data(
    breakout_volume: int,
    post_volumes: list[int],
):
    """
    # Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类

    **Validates: Requirements 7.5**

    当突破后交易日不足 2 天时，volume_sustained 应为 None。
    """
    if len(post_volumes) >= 2:
        return  # 仅测试数据不足的情况

    result = check_volume_sustainability(breakout_volume, post_volumes)
    assert result is None, (
        f"数据不足时应返回 None，实际={result}, "
        f"breakout_volume={breakout_volume}, post_volumes={post_volumes}"
    )


@settings(max_examples=200)
@given(
    breakout_volume=_breakout_volume_strategy,
    post_volumes=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=10,
    ),
)
def test_volume_sustainability_true_when_all_above_sustain_threshold(
    breakout_volume: int,
    post_volumes: list[int],
):
    """
    # Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类

    **Validates: Requirements 7.1**

    当前 2 日成交量均 >= breakout_volume × 70% 且无任一日 < 50% 时，
    应返回 True。
    """
    sustain_line = breakout_volume * 0.70
    fail_line = breakout_volume * 0.50

    # 仅在前 2 日均达到持续阈值且无任一日低于失败阈值时验证
    first_two_sustained = (
        post_volumes[0] >= sustain_line and post_volumes[1] >= sustain_line
    )
    any_below_fail = any(v < fail_line for v in post_volumes)

    if not first_two_sustained or any_below_fail:
        return  # 不满足 True 条件，跳过

    result = check_volume_sustainability(breakout_volume, post_volumes)
    assert result is True, (
        f"前 2 日均达到持续阈值且无缩量时应返回 True，实际={result}, "
        f"breakout_volume={breakout_volume}, post_volumes={post_volumes}"
    )


@settings(max_examples=200)
@given(
    breakout_volume=_breakout_volume_strategy,
    post_volumes=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=10,
    ),
)
def test_volume_sustainability_false_when_any_below_fail_threshold(
    breakout_volume: int,
    post_volumes: list[int],
):
    """
    # Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类

    **Validates: Requirements 7.2**

    当任一日成交量 < breakout_volume × 50% 时，应返回 False。
    """
    fail_line = breakout_volume * 0.50

    any_below_fail = any(v < fail_line for v in post_volumes)
    if not any_below_fail:
        return  # 仅测试有缩量的情况

    result = check_volume_sustainability(breakout_volume, post_volumes)
    assert result is False, (
        f"任一日低于失败阈值时应返回 False，实际={result}, "
        f"breakout_volume={breakout_volume}, post_volumes={post_volumes}"
    )


@settings(max_examples=200)
@given(
    breakout_volume=_breakout_volume_strategy,
    post_volumes=_post_volumes_strategy,
)
def test_volume_sustainability_result_type(
    breakout_volume: int,
    post_volumes: list[int],
):
    """
    # Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类

    **Validates: Requirements 7.1, 7.2, 7.5**

    返回值类型始终为 True、False 或 None 之一。
    """
    result = check_volume_sustainability(breakout_volume, post_volumes)
    assert result in (True, False, None), (
        f"返回值应为 True/False/None，实际={result}"
    )


@settings(max_examples=200)
@given(post_volumes=_post_volumes_strategy)
def test_volume_sustainability_zero_breakout_volume_returns_none(
    post_volumes: list[int],
):
    """
    # Feature: screening-parameter-optimization, Property 11: 突破成交量持续性分类

    **Validates: Requirements 7.5**

    突破日成交量为 0 时，应返回 None（避免除零）。
    """
    result = check_volume_sustainability(0, post_volumes)
    assert result is None, (
        f"突破日成交量为 0 时应返回 None，实际={result}"
    )


# ---------------------------------------------------------------------------
# Property 12: 突破横盘整理加分
# Feature: screening-parameter-optimization, Property 12: 突破横盘整理加分
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(box_period_days=_box_period_strategy)
def test_consolidation_bonus_threshold(box_period_days: int):
    """
    # Feature: screening-parameter-optimization, Property 12: 突破横盘整理加分

    **Validates: Requirements 7.3**

    consolidation_bonus 应在 box_period_days >= 30 时为 True，否则为 False。
    """
    result = check_consolidation_bonus(box_period_days)
    expected = box_period_days >= 30
    assert result == expected, (
        f"横盘加分判定不一致：box_period_days={box_period_days}, "
        f"result={result}, expected={expected}"
    )


@settings(max_examples=200)
@given(
    box_period_days=_box_period_strategy,
    min_days=st.integers(min_value=1, max_value=100),
)
def test_consolidation_bonus_custom_threshold(
    box_period_days: int,
    min_days: int,
):
    """
    # Feature: screening-parameter-optimization, Property 12: 突破横盘整理加分

    **Validates: Requirements 7.3**

    对任意自定义阈值，consolidation_bonus 应在
    box_period_days >= min_consolidation_days 时为 True。
    """
    result = check_consolidation_bonus(box_period_days, min_consolidation_days=min_days)
    expected = box_period_days >= min_days
    assert result == expected, (
        f"自定义阈值判定不一致：box_period_days={box_period_days}, "
        f"min_days={min_days}, result={result}, expected={expected}"
    )


@settings(max_examples=200)
@given(box_period_days=_box_period_strategy)
def test_consolidation_bonus_returns_bool(box_period_days: int):
    """
    # Feature: screening-parameter-optimization, Property 12: 突破横盘整理加分

    **Validates: Requirements 7.3**

    返回值类型始终为 bool。
    """
    result = check_consolidation_bonus(box_period_days)
    assert isinstance(result, bool), (
        f"返回值应为 bool，实际类型={type(result)}"
    )
