"""
选股结果变化检测完备性属性测试（Hypothesis）

Property 11: 选股结果变化检测完备性

对应需求 10.1、10.2、10.3、10.4、10.5

验证 ScreenExecutor._compute_result_diff() 纯函数满足：
- current 中有但 previous 中无 → NEW
- 两者都有但信号列表不同 → UPDATED
- previous 中有但 current 中无 → REMOVED
- 两者都有且信号列表相同 → 不出现在 changes 中
- changes 的 symbol 集合 = (NEW ∪ UPDATED ∪ REMOVED)，无遗漏无多余
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import (
    ChangeType,
    RiskLevel,
    ScreenChange,
    ScreenItem,
    SignalCategory,
    SignalDetail,
)
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 股票代码策略：6 位数字字符串
_symbol_st = st.from_regex(r"[0-9]{6}", fullmatch=True)

# 信号分类策略
_signal_category_st = st.sampled_from(list(SignalCategory))

# 信号标签策略
_signal_label_st = st.sampled_from([
    "ma_trend", "macd", "boll", "rsi", "dma",
    "breakout", "money_flow", "large_order",
    "ma_support", "sector_rank",
])


@st.composite
def signal_detail_st(draw):
    """生成一个 SignalDetail 实例。"""
    category = draw(_signal_category_st)
    label = draw(_signal_label_st)
    return SignalDetail(category=category, label=label)


# 信号列表策略：0-5 个信号
_signal_list_st = st.lists(signal_detail_st(), min_size=0, max_size=5)


@st.composite
def screen_item_st(draw):
    """生成一个 ScreenItem 实例。"""
    symbol = draw(_symbol_st)
    signals = draw(_signal_list_st)
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal("10.00"),
        trend_score=80.0,
        risk_level=RiskLevel.LOW,
        signals=signals,
    )


# 使用唯一 symbol 的 ScreenItem 列表
@st.composite
def unique_screen_items_st(draw, min_size=0, max_size=8):
    """生成 symbol 唯一的 ScreenItem 列表。"""
    symbols = draw(
        st.lists(_symbol_st, min_size=min_size, max_size=max_size, unique=True)
    )
    items = []
    for sym in symbols:
        signals = draw(_signal_list_st)
        items.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=signals,
        ))
    return items


@st.composite
def current_and_previous_items(draw):
    """生成当前和上一轮选股结果列表的组合（symbol 各自唯一）。"""
    current = draw(unique_screen_items_st(min_size=0, max_size=8))
    previous = draw(st.one_of(
        st.none(),
        unique_screen_items_st(min_size=0, max_size=8),
    ))
    return current, previous


@st.composite
def items_with_explicit_overlap(draw):
    """
    生成有明确重叠的当前和上一轮结果。

    返回 (current, previous, shared_symbols, new_symbols, removed_symbols)
    其中 shared_symbols 中的股票信号列表相同（不变），
    以确保测试覆盖所有变化类型。
    """
    # 共享 symbol（信号相同，不应出现在 changes 中）
    shared_syms = draw(st.lists(_symbol_st, min_size=1, max_size=3, unique=True))
    # 仅当前轮的 symbol
    new_syms = draw(st.lists(
        _symbol_st.filter(lambda s: s not in shared_syms),
        min_size=1, max_size=3, unique=True,
    ))
    # 仅上一轮的 symbol
    all_used = set(shared_syms) | set(new_syms)
    removed_syms = draw(st.lists(
        _symbol_st.filter(lambda s: s not in all_used),
        min_size=1, max_size=3, unique=True,
    ))

    # 为共享 symbol 生成相同的信号列表
    shared_signals_map: dict[str, list[SignalDetail]] = {}
    for sym in shared_syms:
        sigs = draw(_signal_list_st)
        shared_signals_map[sym] = sigs

    # 构建 current 列表
    current: list[ScreenItem] = []
    for sym in shared_syms:
        sigs = [SignalDetail(category=s.category, label=s.label) for s in shared_signals_map[sym]]
        current.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=sigs,
        ))
    for sym in new_syms:
        sigs = draw(_signal_list_st)
        current.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=sigs,
        ))

    # 构建 previous 列表
    previous: list[ScreenItem] = []
    for sym in shared_syms:
        sigs = [SignalDetail(category=s.category, label=s.label) for s in shared_signals_map[sym]]
        previous.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=sigs,
        ))
    for sym in removed_syms:
        sigs = draw(_signal_list_st)
        previous.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=sigs,
        ))

    return current, previous, set(shared_syms), set(new_syms), set(removed_syms)


def _signal_key_set(item: ScreenItem) -> set[tuple]:
    """提取 ScreenItem 的信号 (category, label) 集合。"""
    return {(s.category, s.label) for s in item.signals}


# ---------------------------------------------------------------------------
# Property 11.1: 无上一轮时全部 NEW
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(current=unique_screen_items_st(min_size=1, max_size=8))
def test_all_new_when_no_previous(current):
    """
    # Feature: screening-system-enhancement, Property 11: 无上一轮时全部 NEW

    **Validates: Requirements 10.2**

    当上一轮结果为 None 时，所有当前股票均应标记为 NEW。
    """
    changes = ScreenExecutor._compute_result_diff(current, None)

    change_symbols = {c.symbol for c in changes}
    current_symbols = {item.symbol for item in current}

    # 所有当前股票都应出现在 changes 中
    assert change_symbols == current_symbols, (
        f"期望 changes 包含所有当前股票 {current_symbols}，"
        f"实际 {change_symbols}"
    )

    # 所有变化类型都应为 NEW
    for c in changes:
        assert c.change_type == ChangeType.NEW, (
            f"股票 {c.symbol} 应为 NEW，实际为 {c.change_type.value}"
        )
        assert c.item is not None, (
            f"NEW 类型的变化条目 {c.symbol} 的 item 不应为 None"
        )


# ---------------------------------------------------------------------------
# Property 11.2: 完全相同的结果 → 无变化
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(items=unique_screen_items_st(min_size=0, max_size=8))
def test_no_changes_when_identical(items):
    """
    # Feature: screening-system-enhancement, Property 11: 完全相同时无变化

    **Validates: Requirements 10.5**

    当前结果和上一轮结果完全相同（相同 symbol、相同信号）时，
    changes 应为空列表。
    """
    # 构建信号完全相同的副本
    previous = [
        ScreenItem(
            symbol=item.symbol,
            ref_buy_price=item.ref_buy_price,
            trend_score=item.trend_score,
            risk_level=item.risk_level,
            signals=[
                SignalDetail(category=s.category, label=s.label)
                for s in item.signals
            ],
        )
        for item in items
    ]

    changes = ScreenExecutor._compute_result_diff(items, previous)

    assert len(changes) == 0, (
        f"完全相同的结果应无变化，但发现 {len(changes)} 个变化：\n"
        + "\n".join(f"  {c.symbol}: {c.change_type.value}" for c in changes)
    )


# ---------------------------------------------------------------------------
# Property 11.3: 变化检测完备性（核心属性）
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_items())
def test_change_detection_completeness(data):
    """
    # Feature: screening-system-enhancement, Property 11: 变化检测完备性

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

    For any 当前和上一轮结果集合：
    - current 有但 previous 无 → NEW
    - 两者都有但信号不同 → UPDATED
    - previous 有但 current 无 → REMOVED
    - 两者都有且信号相同 → 不在 changes 中
    - changes symbol 集合 = NEW ∪ UPDATED ∪ REMOVED，无遗漏无多余
    """
    current, previous = data

    changes = ScreenExecutor._compute_result_diff(current, previous)

    # 构建索引
    cur_by_sym = {item.symbol: item for item in current}
    prev_by_sym = {}
    if previous:
        prev_by_sym = {item.symbol: item for item in previous}

    change_by_sym = {c.symbol: c for c in changes}

    # 计算期望的各类变化 symbol 集合
    cur_syms = set(cur_by_sym.keys())
    prev_syms = set(prev_by_sym.keys())

    expected_new = cur_syms - prev_syms
    expected_removed = prev_syms - cur_syms
    common = cur_syms & prev_syms

    expected_updated = set()
    expected_unchanged = set()
    for sym in common:
        cur_keys = _signal_key_set(cur_by_sym[sym])
        prev_keys = _signal_key_set(prev_by_sym[sym])
        if cur_keys != prev_keys:
            expected_updated.add(sym)
        else:
            expected_unchanged.add(sym)

    expected_change_syms = expected_new | expected_updated | expected_removed
    actual_change_syms = set(change_by_sym.keys())

    # 验证 changes symbol 集合完备性
    assert actual_change_syms == expected_change_syms, (
        f"changes symbol 集合不匹配：\n"
        f"  期望: {expected_change_syms}\n"
        f"  实际: {actual_change_syms}\n"
        f"  遗漏: {expected_change_syms - actual_change_syms}\n"
        f"  多余: {actual_change_syms - expected_change_syms}"
    )

    # 验证每个变化的 change_type 正确
    for sym in expected_new:
        assert change_by_sym[sym].change_type == ChangeType.NEW, (
            f"新增股票 {sym} 应为 NEW，实际为 {change_by_sym[sym].change_type.value}"
        )
        assert change_by_sym[sym].item is not None, (
            f"NEW 类型的 {sym} 的 item 不应为 None"
        )

    for sym in expected_updated:
        assert change_by_sym[sym].change_type == ChangeType.UPDATED, (
            f"信号变化股票 {sym} 应为 UPDATED，实际为 {change_by_sym[sym].change_type.value}"
        )
        assert change_by_sym[sym].item is not None, (
            f"UPDATED 类型的 {sym} 的 item 不应为 None"
        )

    for sym in expected_removed:
        assert change_by_sym[sym].change_type == ChangeType.REMOVED, (
            f"移出股票 {sym} 应为 REMOVED，实际为 {change_by_sym[sym].change_type.value}"
        )
        assert change_by_sym[sym].item is None, (
            f"REMOVED 类型的 {sym} 的 item 应为 None"
        )

    # 验证未变化的 symbol 不在 changes 中
    for sym in expected_unchanged:
        assert sym not in change_by_sym, (
            f"未变化的股票 {sym} 不应出现在 changes 中"
        )


# ---------------------------------------------------------------------------
# Property 11.4: 有明确重叠时的变化检测
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=items_with_explicit_overlap())
def test_change_detection_with_explicit_overlap(data):
    """
    # Feature: screening-system-enhancement, Property 11: 有明确重叠时的变化检测

    **Validates: Requirements 10.2, 10.3, 10.4**

    当存在明确的共享、新增、移出股票时：
    - 共享且信号相同的股票不出现在 changes 中
    - 新增股票标记为 NEW
    - 移出股票标记为 REMOVED
    """
    current, previous, shared_syms, new_syms, removed_syms = data

    changes = ScreenExecutor._compute_result_diff(current, previous)
    change_by_sym = {c.symbol: c for c in changes}

    # 新增股票应为 NEW
    for sym in new_syms:
        assert sym in change_by_sym, f"新增股票 {sym} 应出现在 changes 中"
        assert change_by_sym[sym].change_type == ChangeType.NEW, (
            f"新增股票 {sym} 应为 NEW，实际为 {change_by_sym[sym].change_type.value}"
        )

    # 移出股票应为 REMOVED
    for sym in removed_syms:
        assert sym in change_by_sym, f"移出股票 {sym} 应出现在 changes 中"
        assert change_by_sym[sym].change_type == ChangeType.REMOVED, (
            f"移出股票 {sym} 应为 REMOVED，实际为 {change_by_sym[sym].change_type.value}"
        )
        assert change_by_sym[sym].item is None, (
            f"REMOVED 类型的 {sym} 的 item 应为 None"
        )

    # 共享且信号相同的股票不应出现在 changes 中
    for sym in shared_syms:
        if sym in change_by_sym:
            # 只有信号不同时才应出现
            assert change_by_sym[sym].change_type == ChangeType.UPDATED, (
                f"共享股票 {sym} 若出现在 changes 中应为 UPDATED，"
                f"实际为 {change_by_sym[sym].change_type.value}"
            )


# ---------------------------------------------------------------------------
# Property 11.5: changes 中无重复 symbol
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_items())
def test_no_duplicate_symbols_in_changes(data):
    """
    # Feature: screening-system-enhancement, Property 11: changes 无重复 symbol

    **Validates: Requirements 10.5**

    changes 列表中每个 symbol 最多出现一次。
    """
    current, previous = data

    changes = ScreenExecutor._compute_result_diff(current, previous)

    symbols = [c.symbol for c in changes]
    assert len(symbols) == len(set(symbols)), (
        f"changes 中存在重复 symbol：{symbols}"
    )


# ---------------------------------------------------------------------------
# Property 11.6: change_type 值始终为有效枚举
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_items())
def test_change_type_always_valid_enum(data):
    """
    # Feature: screening-system-enhancement, Property 11: change_type 值有效性

    **Validates: Requirements 10.2, 10.3, 10.4**

    For any 输入，_compute_result_diff() 返回的每个变化条目的 change_type
    始终为有效的 ChangeType 枚举值。
    """
    current, previous = data

    changes = ScreenExecutor._compute_result_diff(current, previous)

    for c in changes:
        assert isinstance(c.change_type, ChangeType), (
            f"change_type {c.change_type} 不是 ChangeType 枚举类型"
        )
        assert c.change_type in (ChangeType.NEW, ChangeType.UPDATED, ChangeType.REMOVED), (
            f"change_type {c.change_type} 不是有效的 ChangeType 值"
        )


# ---------------------------------------------------------------------------
# Property 11.7: REMOVED 条目的 item 为 None，其余不为 None
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=current_and_previous_items())
def test_item_none_consistency(data):
    """
    # Feature: screening-system-enhancement, Property 11: item 与 change_type 一致性

    **Validates: Requirements 10.4, 10.5**

    REMOVED 类型的变化条目 item 应为 None，
    NEW 和 UPDATED 类型的变化条目 item 不应为 None。
    """
    current, previous = data

    changes = ScreenExecutor._compute_result_diff(current, previous)

    for c in changes:
        if c.change_type == ChangeType.REMOVED:
            assert c.item is None, (
                f"REMOVED 类型的 {c.symbol} 的 item 应为 None，"
                f"实际为 {c.item}"
            )
        else:
            assert c.item is not None, (
                f"{c.change_type.value} 类型的 {c.symbol} 的 item 不应为 None"
            )
