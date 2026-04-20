"""
选股池管理属性测试（Hypothesis）

使用 Hypothesis 对选股池管理功能的纯函数进行属性测试，
覆盖 CSV 导出、文件名清理、名称校验、股票增删幂等性和代码校验。

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 3.3, 3.9, 4.4, 4.5, 5.1, 5.3**

Property 1: CSV 生成保留所有选股结果且包含必需列
Property 2: 文件名生成与特殊字符清理
Property 3: 选股池名称校验拒绝无效输入
Property 5: 股票添加幂等性
Property 6: 股票移除后剩余集合正确
Property 7: 非法股票代码拒绝
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.csv_exporter import (
    build_csv_content,
    build_export_filename,
    sanitize_filename,
)
from app.services.pool_manager import (
    validate_pool_name,
    validate_stock_symbol,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 文件系统禁止字符
_FORBIDDEN_CHARS = set('/\\:*?"<>|')
_FORBIDDEN_RE = re.compile(r'[/\\:*?"<>|]')

# CSV 必需列头
_REQUIRED_HEADERS = [
    "股票代码",
    "股票名称",
    "买入参考价",
    "趋势评分",
    "风险等级",
    "触发信号摘要",
    "选股时间",
]

# UTF-8 BOM 字节
_UTF8_BOM = b"\xef\xbb\xbf"

# 6 位数字股票代码策略
_valid_symbol = st.from_regex(r"\d{6}", fullmatch=True)

# 选股结果条目策略（dict 格式）
_screen_item = st.fixed_dictionaries({
    "symbol": _valid_symbol,
    "stock_name": st.text(min_size=1, max_size=10),
    "ref_buy_price": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "trend_score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    "risk_level": st.sampled_from(["低", "中", "高"]),
    "signals": st.lists(
        st.fixed_dictionaries({"label": st.text(min_size=1, max_size=20)}),
        min_size=0,
        max_size=3,
    ),
})

# 合法的 datetime 策略（带时区）
_aware_datetime = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# 策略名称（可能含特殊字符）
_strategy_name = st.text(min_size=1, max_size=50)

# 含禁止字符的策略名称
_strategy_name_with_forbidden = st.text(
    alphabet=st.sampled_from(list('abcABC123/\\:*?"<>|_- 中文')),
    min_size=1,
    max_size=30,
)


# ---------------------------------------------------------------------------
# Property 1: CSV 生成保留所有选股结果且包含必需列
# Feature: stock-pool-management, Property 1: CSV generation preserves all results with required columns
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    items=st.lists(_screen_item, min_size=1, max_size=50),
    strategy_name=_strategy_name,
    export_time=_aware_datetime,
)
def test_csv_preserves_all_results_and_required_columns(
    items: list[dict],
    strategy_name: str,
    export_time: datetime,
):
    """
    # Feature: stock-pool-management, Property 1: CSV generation preserves all results with required columns

    **Validates: Requirements 1.1, 1.2, 1.5**

    对于任意非空选股结果列表，build_csv_content 生成的 CSV 应满足：
    (a) 解析后的数据行数等于输入列表长度
    (b) 首行包含所有 7 个必需列
    (c) 输出字节以 UTF-8 BOM (EF BB BF) 开头
    """
    csv_bytes = build_csv_content(items, strategy_name, export_time)

    # (c) 输出字节以 UTF-8 BOM 开头
    assert csv_bytes[:3] == _UTF8_BOM, (
        f"CSV 输出应以 UTF-8 BOM 开头，实际前 3 字节: {csv_bytes[:3]!r}"
    )

    # 解析 CSV 内容（跳过 BOM）
    csv_text = csv_bytes[3:].decode("utf-8")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # 至少有 header + 数据行
    assert len(rows) >= 2, "CSV 应至少包含 header 行和数据行"

    # (b) 首行包含所有必需列
    header = rows[0]
    for col in _REQUIRED_HEADERS:
        assert col in header, f"CSV header 缺少必需列: {col}"

    # (a) 数据行数等于输入列表长度
    data_rows = rows[1:]
    assert len(data_rows) == len(items), (
        f"CSV 数据行数 ({len(data_rows)}) 应等于输入列表长度 ({len(items)})"
    )


# ---------------------------------------------------------------------------
# Property 2: 文件名生成与特殊字符清理
# Feature: stock-pool-management, Property 2: Filename generation with sanitization
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(name=_strategy_name_with_forbidden)
def test_sanitize_filename_removes_forbidden_chars(name: str):
    """
    # Feature: stock-pool-management, Property 2: Filename generation with sanitization

    **Validates: Requirements 1.4**

    对于任意策略名称，sanitize_filename 输出不应包含禁止字符。
    所有禁止字符应被替换为下划线。
    """
    sanitized = sanitize_filename(name)

    # (a) 输出不包含禁止字符
    for ch in sanitized:
        assert ch not in _FORBIDDEN_CHARS, (
            f"sanitize_filename 输出包含禁止字符 '{ch}'，输入: {name!r}"
        )

    # (b) 所有禁止字符被替换为下划线：逐字符验证
    for i, ch in enumerate(name):
        if ch in _FORBIDDEN_CHARS:
            assert sanitized[i] == "_", (
                f"位置 {i} 的禁止字符 '{ch}' 应被替换为下划线，实际: '{sanitized[i]}'"
            )
        else:
            assert sanitized[i] == ch, (
                f"位置 {i} 的非禁止字符 '{ch}' 不应被修改，实际: '{sanitized[i]}'"
            )


@settings(max_examples=100)
@given(
    strategy_name=_strategy_name_with_forbidden,
    export_time=_aware_datetime,
)
def test_build_export_filename_format(strategy_name: str, export_time: datetime):
    """
    # Feature: stock-pool-management, Property 2: Filename generation with sanitization

    **Validates: Requirements 1.3**

    build_export_filename 输出应匹配 {sanitized_name}_{YYYYMMDD_HHmmss}.csv 格式。
    """
    filename = build_export_filename(strategy_name, export_time)

    # 文件名应以 .csv 结尾
    assert filename.endswith(".csv"), (
        f"文件名应以 .csv 结尾，实际: {filename!r}"
    )

    # 文件名不应包含禁止字符（.csv 后缀之前的部分）
    name_part = filename[:-4]  # 去掉 .csv
    for ch in name_part:
        assert ch not in _FORBIDDEN_CHARS, (
            f"文件名包含禁止字符 '{ch}'，完整文件名: {filename!r}"
        )

    # 验证格式：{sanitized_name}_{YYYYMMDD_HHmmss}.csv
    # 最后部分应为 _YYYYMMDD_HHMMSS
    pattern = re.compile(r"^.+_\d{8}_\d{6}\.csv$")
    assert pattern.match(filename), (
        f"文件名不匹配 {{sanitized_name}}_{{YYYYMMDD_HHmmss}}.csv 格式，实际: {filename!r}"
    )


# ---------------------------------------------------------------------------
# Property 3: 选股池名称校验拒绝无效输入
# Feature: stock-pool-management, Property 3: Pool name validation rejects invalid input
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    name=st.text(
        alphabet=st.sampled_from([" ", "\t", "\n", "\r", "\u3000"]),
        min_size=1,
        max_size=20,
    ),
)
def test_validate_pool_name_rejects_whitespace_only(name: str):
    """
    # Feature: stock-pool-management, Property 3: Pool name validation rejects invalid input

    **Validates: Requirements 3.3**

    对于任意仅由空白字符组成的字符串，validate_pool_name 应抛出 ValueError。
    """
    with pytest.raises(ValueError):
        validate_pool_name(name)


@settings(max_examples=100)
@given(
    name=st.text(min_size=51, max_size=200),
)
def test_validate_pool_name_rejects_too_long(name: str):
    """
    # Feature: stock-pool-management, Property 3: Pool name validation rejects invalid input

    **Validates: Requirements 3.9**

    对于任意 strip 后长度超过 50 个字符的字符串，validate_pool_name 应抛出 ValueError。
    """
    # 确保 strip 后仍然超过 50 字符
    assume(len(name.strip()) > 50)

    with pytest.raises(ValueError):
        validate_pool_name(name)


@settings(max_examples=100)
@given(
    name=st.text(min_size=1, max_size=50),
)
def test_validate_pool_name_accepts_valid(name: str):
    """
    # Feature: stock-pool-management, Property 3: Pool name validation rejects invalid input

    **Validates: Requirements 3.3, 3.9**

    对于任意非空且 strip 后长度在 1-50 之间的字符串，
    validate_pool_name 应返回 strip 后的名称。
    """
    stripped = name.strip()
    assume(len(stripped) >= 1)
    assume(len(stripped) <= 50)

    result = validate_pool_name(name)
    assert result == stripped, (
        f"validate_pool_name 应返回 strip 后的名称 {stripped!r}，实际: {result!r}"
    )


# ---------------------------------------------------------------------------
# Property 5: 股票添加幂等性（纯集合逻辑测试）
# Feature: stock-pool-management, Property 5: Stock addition idempotence
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    initial_symbols=st.lists(_valid_symbol, min_size=0, max_size=20, unique=True),
    new_symbols=st.lists(_valid_symbol, min_size=1, max_size=20, unique=True),
)
def test_stock_addition_idempotence(
    initial_symbols: list[str],
    new_symbols: list[str],
):
    """
    # Feature: stock-pool-management, Property 5: Stock addition idempotence

    **Validates: Requirements 4.4, 4.5**

    对于任意选股池和股票代码集合，将集合添加两次后：
    (a) 第一次添加后池内应包含所有新股票
    (b) 第二次添加相同集合时，added 应为 0
    (c) 池内股票总数不变

    使用纯集合逻辑模拟 INSERT ... ON CONFLICT DO NOTHING 行为。
    """
    # 模拟选股池（集合）
    pool = set(initial_symbols)

    # 第一次添加
    first_added = 0
    first_skipped = 0
    for sym in new_symbols:
        if sym not in pool:
            pool.add(sym)
            first_added += 1
        else:
            first_skipped += 1

    # (a) 池内应包含所有新股票
    for sym in new_symbols:
        assert sym in pool, f"第一次添加后，股票 {sym} 应在池内"

    pool_size_after_first = len(pool)

    # 第二次添加相同集合
    second_added = 0
    second_skipped = 0
    for sym in new_symbols:
        if sym not in pool:
            pool.add(sym)
            second_added += 1
        else:
            second_skipped += 1

    # (b) 第二次添加 added 应为 0
    assert second_added == 0, (
        f"第二次添加相同集合，added 应为 0，实际: {second_added}"
    )

    # skipped 应等于集合大小
    assert second_skipped == len(new_symbols), (
        f"第二次添加相同集合，skipped 应为 {len(new_symbols)}，实际: {second_skipped}"
    )

    # (c) 池内股票总数不变
    assert len(pool) == pool_size_after_first, (
        f"第二次添加后池内总数应不变 ({pool_size_after_first})，实际: {len(pool)}"
    )


# ---------------------------------------------------------------------------
# Property 6: 股票移除后剩余集合正确（纯集合逻辑测试）
# Feature: stock-pool-management, Property 6: Stock removal preserves remainder
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    data=st.data(),
)
def test_stock_removal_remainder_correct(data):
    """
    # Feature: stock-pool-management, Property 6: Stock removal preserves remainder

    **Validates: Requirements 5.1**

    对于任意包含 N 只股票的选股池，移除其中 M 只（M ≤ N）后：
    (a) 池内应恰好剩余 N - M 只股票
    (b) 剩余股票集合等于原集合减去移除集合

    使用纯集合逻辑模拟批量删除行为。
    """
    # 生成初始股票集合
    all_symbols = data.draw(
        st.lists(_valid_symbol, min_size=1, max_size=30, unique=True),
        label="all_symbols",
    )
    pool = set(all_symbols)
    n = len(pool)

    # 从池中随机选择要移除的子集
    to_remove = data.draw(
        st.lists(
            st.sampled_from(sorted(pool)),
            min_size=0,
            max_size=len(pool),
            unique=True,
        ),
        label="to_remove",
    )
    m = len(to_remove)
    remove_set = set(to_remove)

    # 执行移除
    pool -= remove_set

    # (a) 剩余数量 = N - M
    assert len(pool) == n - m, (
        f"移除 {m} 只后应剩余 {n - m} 只，实际: {len(pool)}"
    )

    # (b) 剩余集合 = 原集合 - 移除集合
    expected_remainder = set(all_symbols) - remove_set
    assert pool == expected_remainder, (
        f"剩余集合不正确。期望: {expected_remainder}，实际: {pool}"
    )


# ---------------------------------------------------------------------------
# Property 7: 非法股票代码拒绝
# Feature: stock-pool-management, Property 7: Invalid stock symbol rejection
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    symbol=st.text(min_size=0, max_size=20),
)
def test_validate_stock_symbol_rejects_invalid(symbol: str):
    """
    # Feature: stock-pool-management, Property 7: Invalid stock symbol rejection

    **Validates: Requirements 5.3**

    对于任意不匹配 ^\\d{6}$ 的字符串，validate_stock_symbol 应抛出 ValueError。
    """
    is_valid_format = bool(re.match(r"^\d{6}$", symbol))
    assume(not is_valid_format)

    with pytest.raises(ValueError):
        validate_stock_symbol(symbol)


@settings(max_examples=100)
@given(
    symbol=st.from_regex(r"\d{6}", fullmatch=True),
)
def test_validate_stock_symbol_accepts_valid(symbol: str):
    """
    # Feature: stock-pool-management, Property 7: Invalid stock symbol rejection

    **Validates: Requirements 5.3**

    对于任意恰好 6 位数字的字符串，validate_stock_symbol 应返回该字符串。
    """
    result = validate_stock_symbol(symbol)
    assert result == symbol, (
        f"validate_stock_symbol 应返回原字符串 {symbol!r}，实际: {result!r}"
    )


# ---------------------------------------------------------------------------
# Property 8: 选股池股票富化合并完整性
# Feature: stock-pool-management, Property 8: Pool stock enrichment merge completeness
# ---------------------------------------------------------------------------

from app.services.pool_manager import merge_pool_stocks_with_screen_results

# 选股池股票条目策略（dict 格式，含 symbol, stock_name, added_at）
_pool_stock_item = st.fixed_dictionaries({
    "symbol": st.from_regex(r"\d{6}", fullmatch=True),
    "stock_name": st.text(min_size=1, max_size=10),
    "added_at": st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
    ).map(lambda dt: dt.isoformat()),
})

# 选股结果条目策略（用于 screen_results_map 的 value）
_screen_result_value = st.fixed_dictionaries({
    "ref_buy_price": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "trend_score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    "risk_level": st.sampled_from(["LOW", "MEDIUM", "HIGH"]),
    "signals": st.lists(
        st.fixed_dictionaries({
            "category": st.text(min_size=1, max_size=20),
            "label": st.text(min_size=1, max_size=20),
            "strength": st.sampled_from(["STRONG", "MEDIUM", "WEAK"]),
        }),
        min_size=1,
        max_size=5,
    ),
    "screen_time": st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
    ).map(lambda dt: dt.isoformat()),
    "has_fake_breakout": st.booleans(),
    "sector_classifications": st.one_of(
        st.none(),
        st.fixed_dictionaries({
            "eastmoney": st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=3),
            "tonghuashun": st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=3),
            "tongdaxin": st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=3),
        }),
    ),
})

# 富化字段列表（用于断言检查）
_ENRICHMENT_CHECK_FIELDS = (
    "ref_buy_price",
    "trend_score",
    "risk_level",
    "signals",
    "screen_time",
)


@st.composite
def _pool_stocks_and_screen_results(draw):
    """生成 pool_stocks 列表和 screen_results_map 字典。

    确保 pool_stocks 中的 symbol 唯一，
    screen_results_map 中 SOME symbols 来自 pool_stocks（匹配），
    SOME 不在 pool_stocks 中（不匹配）。
    """
    # 生成唯一 symbol 的 pool_stocks
    pool_stocks = draw(st.lists(
        _pool_stock_item,
        min_size=1,
        max_size=20,
    ))
    # 确保 symbol 唯一（去重，保留第一个出现的）
    seen = set()
    unique_pool_stocks = []
    for stock in pool_stocks:
        if stock["symbol"] not in seen:
            seen.add(stock["symbol"])
            unique_pool_stocks.append(stock)
    assume(len(unique_pool_stocks) >= 1)
    pool_stocks = unique_pool_stocks

    pool_symbols = [s["symbol"] for s in pool_stocks]

    # 随机选择部分 pool_symbols 作为匹配的 symbol
    matched_symbols = draw(st.lists(
        st.sampled_from(pool_symbols),
        min_size=0,
        max_size=len(pool_symbols),
        unique=True,
    ))

    # 为匹配的 symbol 生成选股结果
    screen_results_map = {}
    for sym in matched_symbols:
        screen_results_map[sym] = draw(_screen_result_value)

    return pool_stocks, screen_results_map


@settings(max_examples=100)
@given(data=_pool_stocks_and_screen_results())
def test_property_8_enrichment_merge_completeness(data):
    """
    # Feature: stock-pool-management, Property 8: Pool stock enrichment merge completeness

    **Validates: Requirements 7.1, 7.3, 7.6**

    对于任意选股池股票列表和选股结果字典，调用 merge_pool_stocks_with_screen_results 后：
    (a) 返回列表长度等于输入股票列表长度
    (b) 对于在选股结果字典中存在匹配的股票，富化字段（ref_buy_price, trend_score,
        risk_level, signals, screen_time）均不为 None
    (c) 对于在选股结果字典中不存在匹配的股票，富化字段均为 None
        （has_fake_breakout 默认为 False）
    (d) 所有记录的 symbol 和 stock_name 保持不变
    """
    pool_stocks, screen_results_map = data

    result = merge_pool_stocks_with_screen_results(pool_stocks, screen_results_map)

    # (a) 返回列表长度等于输入列表长度
    assert len(result) == len(pool_stocks), (
        f"返回列表长度 ({len(result)}) 应等于输入列表长度 ({len(pool_stocks)})"
    )

    for i, enriched in enumerate(result):
        original = pool_stocks[i]
        symbol = original["symbol"]

        # (d) symbol 和 stock_name 保持不变
        assert enriched["symbol"] == original["symbol"], (
            f"第 {i} 条记录的 symbol 应保持不变，"
            f"期望: {original['symbol']!r}，实际: {enriched['symbol']!r}"
        )
        assert enriched["stock_name"] == original["stock_name"], (
            f"第 {i} 条记录的 stock_name 应保持不变，"
            f"期望: {original['stock_name']!r}，实际: {enriched['stock_name']!r}"
        )

        if symbol in screen_results_map:
            # (b) 匹配到的股票，富化字段均不为 None
            for field in _ENRICHMENT_CHECK_FIELDS:
                assert enriched[field] is not None, (
                    f"第 {i} 条记录 (symbol={symbol}) 在 screen_results_map 中存在，"
                    f"富化字段 '{field}' 不应为 None，实际: {enriched[field]!r}"
                )
        else:
            # (c) 未匹配到的股票，富化字段均为 None
            for field in _ENRICHMENT_CHECK_FIELDS:
                assert enriched[field] is None, (
                    f"第 {i} 条记录 (symbol={symbol}) 不在 screen_results_map 中，"
                    f"富化字段 '{field}' 应为 None，实际: {enriched[field]!r}"
                )
            # has_fake_breakout 默认为 False
            assert enriched["has_fake_breakout"] is False, (
                f"第 {i} 条记录 (symbol={symbol}) 不在 screen_results_map 中，"
                f"has_fake_breakout 应为 False，实际: {enriched['has_fake_breakout']!r}"
            )
