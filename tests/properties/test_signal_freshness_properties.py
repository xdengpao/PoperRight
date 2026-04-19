"""
信号新鲜度标记属性测试（Hypothesis）

Property 9: 信号新鲜度正确标记
Property 10: has_new_signal 派生一致性

对应需求 8.2、8.3、8.4

验证 ScreenExecutor._mark_signal_freshness() 纯函数满足：
- 存在于上一轮的信号（按 (category, label) 比较）→ CONTINUING
- 不存在于上一轮的信号 → NEW
- 上一轮为空时全部 NEW
- has_new_signal == any(s.freshness == NEW for s in signals)
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
)
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 所有可用的信号分类
_signal_category_st = st.sampled_from(list(SignalCategory))

# 信号标签策略：使用常见的因子标签名
_signal_label_st = st.sampled_from([
    "ma_trend", "macd", "boll", "rsi", "dma",
    "breakout", "money_flow", "large_order",
    "ma_support", "sector_rank", "sector_trend",
])


@st.composite
def signal_detail_st(draw):
    """生成一个 SignalDetail 实例。"""
    category = draw(_signal_category_st)
    label = draw(_signal_label_st)
    return SignalDetail(
        category=category,
        label=label,
    )


# 信号列表策略：1-8 个信号
_signal_list_st = st.lists(signal_detail_st(), min_size=1, max_size=8)

# 可选的上一轮信号列表：None 或 0-8 个信号
_optional_prev_signal_list_st = st.one_of(
    st.none(),
    st.lists(signal_detail_st(), min_size=0, max_size=8),
)


@st.composite
def current_and_previous_signals(draw):
    """
    生成当前信号列表和上一轮信号列表的组合。

    确保当前信号列表非空。
    """
    current = draw(_signal_list_st)
    previous = draw(_optional_prev_signal_list_st)
    return current, previous


@st.composite
def signals_with_overlap(draw):
    """
    生成有明确重叠的当前信号和上一轮信号列表。

    保证至少有一个信号同时存在于当前和上一轮列表中，
    以及至少有一个信号仅存在于当前列表中。
    """
    # 共享信号（至少 1 个）
    shared = draw(st.lists(signal_detail_st(), min_size=1, max_size=3))
    # 仅当前轮的新信号（至少 1 个）
    new_only = draw(st.lists(signal_detail_st(), min_size=1, max_size=3))
    # 仅上一轮的旧信号（0-3 个）
    prev_only = draw(st.lists(signal_detail_st(), min_size=0, max_size=3))

    # 构建当前信号列表和上一轮信号列表
    current = [SignalDetail(category=s.category, label=s.label) for s in shared] + \
              [SignalDetail(category=s.category, label=s.label) for s in new_only]
    previous = [SignalDetail(category=s.category, label=s.label) for s in shared] + \
               [SignalDetail(category=s.category, label=s.label) for s in prev_only]

    return current, previous, shared, new_only


# ---------------------------------------------------------------------------
# Property 9.1: 上一轮为空时全部 NEW
# Feature: screening-system-enhancement, Property 9: 上一轮为空时全部 NEW
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(current=_signal_list_st)
def test_all_new_when_no_previous(current):
    """
    # Feature: screening-system-enhancement, Property 9: 上一轮为空时全部 NEW

    **Validates: Requirements 8.3**

    For any 当前信号列表，当上一轮结果为 None 时，
    所有信号均应标记为 NEW。
    """
    result = ScreenExecutor._mark_signal_freshness(current, None)

    for sig in result:
        assert sig.freshness == SignalFreshness.NEW, (
            f"上一轮为 None 时，信号 ({sig.category.value}, {sig.label}) "
            f"应为 NEW，实际为 {sig.freshness.value}"
        )


@settings(max_examples=200)
@given(current=_signal_list_st)
def test_all_new_when_previous_empty(current):
    """
    # Feature: screening-system-enhancement, Property 9: 上一轮为空列表时全部 NEW

    **Validates: Requirements 8.3**

    For any 当前信号列表，当上一轮结果为空列表时，
    所有信号均应标记为 NEW。
    """
    result = ScreenExecutor._mark_signal_freshness(current, [])

    for sig in result:
        assert sig.freshness == SignalFreshness.NEW, (
            f"上一轮为空列表时，信号 ({sig.category.value}, {sig.label}) "
            f"应为 NEW，实际为 {sig.freshness.value}"
        )


# ---------------------------------------------------------------------------
# Property 9.2: 存在于上一轮的信号 → CONTINUING，不存在的 → NEW
# Feature: screening-system-enhancement, Property 9: 新鲜度正确标记
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_signals())
def test_freshness_marking_correctness(data):
    """
    # Feature: screening-system-enhancement, Property 9: 新鲜度正确标记

    **Validates: Requirements 8.2**

    For any 当前信号列表和上一轮信号列表：
    - 存在于上一轮（按 (category, label) 比较）的信号 → CONTINUING
    - 不存在于上一轮的信号 → NEW
    """
    current, previous = data

    result = ScreenExecutor._mark_signal_freshness(current, previous)

    # 构建上一轮信号的 (category, label) 集合
    if previous:
        prev_keys = {(s.category, s.label) for s in previous}
    else:
        prev_keys = set()

    for sig in result:
        key = (sig.category, sig.label)
        if prev_keys and key in prev_keys:
            expected = SignalFreshness.CONTINUING
        else:
            expected = SignalFreshness.NEW

        assert sig.freshness == expected, (
            f"信号 ({sig.category.value}, {sig.label}) 新鲜度标记错误：\n"
            f"  期望 {expected.value}，实际 {sig.freshness.value}\n"
            f"  上一轮信号 keys: {prev_keys}"
        )


@settings(max_examples=200)
@given(data=signals_with_overlap())
def test_freshness_with_explicit_overlap(data):
    """
    # Feature: screening-system-enhancement, Property 9: 有重叠时的新鲜度标记

    **Validates: Requirements 8.2**

    当当前信号列表和上一轮信号列表有明确重叠时：
    - 共享信号 → CONTINUING
    - 仅当前轮的新信号 → NEW（除非其 (category, label) 恰好与共享信号重复）
    """
    current, previous, shared, new_only = data

    result = ScreenExecutor._mark_signal_freshness(current, previous)

    prev_keys = {(s.category, s.label) for s in previous}

    for sig in result:
        key = (sig.category, sig.label)
        if key in prev_keys:
            assert sig.freshness == SignalFreshness.CONTINUING, (
                f"共享信号 ({sig.category.value}, {sig.label}) 应为 CONTINUING，"
                f"实际为 {sig.freshness.value}"
            )
        else:
            assert sig.freshness == SignalFreshness.NEW, (
                f"新信号 ({sig.category.value}, {sig.label}) 应为 NEW，"
                f"实际为 {sig.freshness.value}"
            )


# ---------------------------------------------------------------------------
# Property 9.3: 返回列表长度不变
# Feature: screening-system-enhancement, Property 9: 返回列表长度不变
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_signals())
def test_freshness_preserves_signal_count(data):
    """
    # Feature: screening-system-enhancement, Property 9: 返回列表长度不变

    **Validates: Requirements 8.2**

    _mark_signal_freshness() 不应增加或减少信号数量。
    """
    current, previous = data
    original_count = len(current)

    result = ScreenExecutor._mark_signal_freshness(current, previous)

    assert len(result) == original_count, (
        f"信号数量变化：原始 {original_count}，标记后 {len(result)}"
    )


# ---------------------------------------------------------------------------
# Property 9.4: freshness 值始终为有效枚举
# Feature: screening-system-enhancement, Property 9: freshness 值有效性
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_signals())
def test_freshness_always_valid_enum(data):
    """
    # Feature: screening-system-enhancement, Property 9: freshness 值有效性

    **Validates: Requirements 8.2, 8.3**

    For any 输入，_mark_signal_freshness() 返回的每个信号的 freshness
    始终为有效的 SignalFreshness 枚举值。
    """
    current, previous = data

    result = ScreenExecutor._mark_signal_freshness(current, previous)

    for sig in result:
        assert isinstance(sig.freshness, SignalFreshness), (
            f"freshness 值 {sig.freshness} 不是 SignalFreshness 枚举类型"
        )
        assert sig.freshness in (SignalFreshness.NEW, SignalFreshness.CONTINUING), (
            f"freshness 值 {sig.freshness} 不是有效的 SignalFreshness 值"
        )


# ---------------------------------------------------------------------------
# Property 10: has_new_signal 派生一致性
# Feature: screening-system-enhancement, Property 10: has_new_signal 一致性
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_signals())
def test_has_new_signal_consistency(data):
    """
    # Feature: screening-system-enhancement, Property 10: has_new_signal 一致性

    **Validates: Requirements 8.4**

    For any ScreenItem，has_new_signal 应等于
    any(s.freshness == SignalFreshness.NEW for s in signals)。
    """
    current, previous = data

    # 标记新鲜度
    ScreenExecutor._mark_signal_freshness(current, previous)

    # 计算 has_new_signal 的期望值
    expected_has_new = any(
        s.freshness == SignalFreshness.NEW for s in current
    )

    # 验证一致性
    actual_has_new = any(
        s.freshness == SignalFreshness.NEW for s in current
    )

    assert actual_has_new == expected_has_new, (
        f"has_new_signal 不一致：期望 {expected_has_new}，实际 {actual_has_new}"
    )


@settings(max_examples=200)
@given(current=_signal_list_st)
def test_has_new_signal_true_when_no_previous(current):
    """
    # Feature: screening-system-enhancement, Property 10: 无上一轮时 has_new_signal 为 True

    **Validates: Requirements 8.3, 8.4**

    当上一轮结果为空时，所有信号为 NEW，
    因此 has_new_signal 应为 True（只要信号列表非空）。
    """
    ScreenExecutor._mark_signal_freshness(current, None)

    has_new = any(s.freshness == SignalFreshness.NEW for s in current)

    # 信号列表非空时，has_new_signal 必为 True
    assert has_new is True, (
        "上一轮为空且信号列表非空时，has_new_signal 应为 True"
    )


@settings(max_examples=200)
@given(current=_signal_list_st)
def test_has_new_signal_false_when_all_continuing(current):
    """
    # Feature: screening-system-enhancement, Property 10: 全部 CONTINUING 时 has_new_signal 为 False

    **Validates: Requirements 8.4**

    当所有当前信号都存在于上一轮时，全部标记为 CONTINUING，
    has_new_signal 应为 False。
    """
    # 上一轮包含所有当前信号
    previous = [
        SignalDetail(category=s.category, label=s.label)
        for s in current
    ]

    ScreenExecutor._mark_signal_freshness(current, previous)

    has_new = any(s.freshness == SignalFreshness.NEW for s in current)

    assert has_new is False, (
        "所有信号都存在于上一轮时，has_new_signal 应为 False，"
        f"但发现 NEW 信号: {[(s.category.value, s.label) for s in current if s.freshness == SignalFreshness.NEW]}"
    )
