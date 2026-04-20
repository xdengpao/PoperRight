"""
黑白名单操作序列一致性属性测试（Hypothesis）

**Validates: Requirements 3.7**

Property 12: 黑白名单操作序列一致性
对于任意黑白名单操作序列（添加、删除的任意组合），执行所有操作后，
is_blacklisted_pure 的查询结果 SHALL 与对应集合的成员关系一致：
添加过且未被删除的股票返回 True，其余返回 False。
"""

from __future__ import annotations

from enum import Enum

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import BlackWhiteListManager


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_symbol = st.from_regex(r"[0-9]{6}", fullmatch=True)


class _OpType(str, Enum):
    """黑白名单操作类型"""
    ADD_BLACK = "add_black"
    REMOVE_BLACK = "remove_black"
    ADD_WHITE = "add_white"
    REMOVE_WHITE = "remove_white"


@st.composite
def _operation(draw):
    """生成单个黑白名单操作"""
    op_type = draw(st.sampled_from(list(_OpType)))
    symbol = draw(_symbol)
    return (op_type, symbol)


@st.composite
def _operation_sequence(draw):
    """生成黑白名单操作序列（1 到 50 个操作）"""
    ops = draw(st.lists(_operation(), min_size=1, max_size=50))
    return ops


# ---------------------------------------------------------------------------
# Property 12: 黑白名单操作序列一致性（黑名单）
# Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(ops=_operation_sequence())
def test_blacklist_operation_sequence_consistency(ops: list[tuple[_OpType, str]]):
    """
    # Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性

    **Validates: Requirements 3.7**

    对于任意黑名单操作序列（添加、删除的任意组合），执行所有操作后，
    is_blacklisted_pure 的查询结果 SHALL 与对应集合的成员关系一致：
    添加过且未被删除的股票返回 True，其余返回 False。
    """
    # 使用集合模拟预期状态
    expected_blacklist: set[str] = set()

    # 执行操作序列，维护预期状态
    for op_type, symbol in ops:
        if op_type == _OpType.ADD_BLACK:
            expected_blacklist.add(symbol)
        elif op_type == _OpType.REMOVE_BLACK:
            expected_blacklist.discard(symbol)
        # 白名单操作不影响黑名单
        # ADD_WHITE 和 REMOVE_WHITE 不改变 expected_blacklist

    # 收集所有涉及的股票代码
    all_symbols = {symbol for _, symbol in ops}

    # 验证 is_blacklisted_pure 与集合成员关系一致
    for symbol in all_symbols:
        result = BlackWhiteListManager.is_blacklisted_pure(symbol, expected_blacklist)
        expected = symbol in expected_blacklist
        assert result == expected, (
            f"股票 {symbol}: is_blacklisted_pure 返回 {result}，"
            f"期望 {expected}（集合成员关系）"
        )


@settings(max_examples=200)
@given(ops=_operation_sequence())
def test_whitelist_operation_sequence_consistency(ops: list[tuple[_OpType, str]]):
    """
    # Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性

    **Validates: Requirements 3.7**

    对于任意白名单操作序列（添加、删除的任意组合），执行所有操作后，
    is_whitelisted_pure 的查询结果 SHALL 与对应集合的成员关系一致：
    添加过且未被删除的股票返回 True，其余返回 False。
    """
    # 使用集合模拟预期状态
    expected_whitelist: set[str] = set()

    # 执行操作序列，维护预期状态
    for op_type, symbol in ops:
        if op_type == _OpType.ADD_WHITE:
            expected_whitelist.add(symbol)
        elif op_type == _OpType.REMOVE_WHITE:
            expected_whitelist.discard(symbol)
        # 黑名单操作不影响白名单

    # 收集所有涉及的股票代码
    all_symbols = {symbol for _, symbol in ops}

    # 验证 is_whitelisted_pure 与集合成员关系一致
    for symbol in all_symbols:
        result = BlackWhiteListManager.is_whitelisted_pure(symbol, expected_whitelist)
        expected = symbol in expected_whitelist
        assert result == expected, (
            f"股票 {symbol}: is_whitelisted_pure 返回 {result}，"
            f"期望 {expected}（集合成员关系）"
        )


@settings(max_examples=200)
@given(ops=_operation_sequence())
def test_blackwhitelist_combined_sequence_consistency(
    ops: list[tuple[_OpType, str]],
):
    """
    # Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性

    **Validates: Requirements 3.7**

    对于任意混合操作序列（黑名单和白名单操作交替），执行所有操作后，
    黑名单和白名单的查询结果 SHALL 各自独立且与对应集合的成员关系一致。
    """
    # 使用集合模拟预期状态
    expected_blacklist: set[str] = set()
    expected_whitelist: set[str] = set()

    # 执行操作序列，维护预期状态
    for op_type, symbol in ops:
        if op_type == _OpType.ADD_BLACK:
            expected_blacklist.add(symbol)
        elif op_type == _OpType.REMOVE_BLACK:
            expected_blacklist.discard(symbol)
        elif op_type == _OpType.ADD_WHITE:
            expected_whitelist.add(symbol)
        elif op_type == _OpType.REMOVE_WHITE:
            expected_whitelist.discard(symbol)

    # 收集所有涉及的股票代码
    all_symbols = {symbol for _, symbol in ops}

    # 验证黑名单和白名单各自独立
    for symbol in all_symbols:
        bl_result = BlackWhiteListManager.is_blacklisted_pure(
            symbol, expected_blacklist,
        )
        wl_result = BlackWhiteListManager.is_whitelisted_pure(
            symbol, expected_whitelist,
        )

        bl_expected = symbol in expected_blacklist
        wl_expected = symbol in expected_whitelist

        assert bl_result == bl_expected, (
            f"股票 {symbol}: 黑名单查询 {bl_result} != 期望 {bl_expected}"
        )
        assert wl_result == wl_expected, (
            f"股票 {symbol}: 白名单查询 {wl_result} != 期望 {wl_expected}"
        )


@settings(max_examples=200)
@given(
    symbol=_symbol,
    blacklist=st.frozensets(_symbol, min_size=0, max_size=20),
)
def test_is_blacklisted_pure_membership(symbol: str, blacklist: frozenset[str]):
    """
    # Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性

    **Validates: Requirements 3.7**

    is_blacklisted_pure 的返回值 SHALL 等价于 symbol in blacklist。
    """
    result = BlackWhiteListManager.is_blacklisted_pure(symbol, set(blacklist))
    expected = symbol in blacklist
    assert result == expected


@settings(max_examples=200)
@given(
    symbol=_symbol,
    whitelist=st.frozensets(_symbol, min_size=0, max_size=20),
)
def test_is_whitelisted_pure_membership(symbol: str, whitelist: frozenset[str]):
    """
    # Feature: risk-control-enhancement, Property 12: 黑白名单操作序列一致性

    **Validates: Requirements 3.7**

    is_whitelisted_pure 的返回值 SHALL 等价于 symbol in whitelist。
    """
    result = BlackWhiteListManager.is_whitelisted_pure(symbol, set(whitelist))
    expected = symbol in whitelist
    assert result == expected
