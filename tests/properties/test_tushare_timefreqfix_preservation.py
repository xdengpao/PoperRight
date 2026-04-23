"""
Preservation 属性测试：Tushare 导入频率超限与数据截断修复 — 保全检查

**Validates: Requirements 3.1, 3.2, 3.3, 3.6**

Property 4 (Task 5.4): 分批策略路由不变
  生成随机 (ApiEntry, params) 对，验证 determine_batch_strategy() 返回值
  属于预期策略集合，且路由优先级逻辑一致。

Property 5 (Task 5.5): 字段映射和代码转换不变
  生成随机 (rows, ApiEntry) 对，验证 _apply_field_mappings() 和 _convert_codes()
  输出确定性一致，字段映射正确重命名，代码转换按 code_format 正确执行。

Property 6 (Task 5.6): 截断检测函数行为不变（未截断场景）
  生成 row_count < max_rows 的随机输入，验证 check_truncation() 始终返回 False。
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.tushare_registry import (
    TUSHARE_API_REGISTRY,
    ApiEntry,
    CodeFormat,
    FieldMapping,
    ParamType,
    RateLimitGroup,
    StorageEngine,
    TokenTier,
)
from app.tasks.tushare_import import (
    _apply_field_mappings,
    _convert_codes,
    check_truncation,
    determine_batch_strategy,
)


# ---------------------------------------------------------------------------
# 共用策略（Hypothesis strategies）
# ---------------------------------------------------------------------------

# 所有已注册的 ApiEntry 列表
_ALL_ENTRIES = list(TUSHARE_API_REGISTRY.values())

# 预期的策略字符串集合
_VALID_STRATEGIES = {
    "by_code",
    "by_code_and_date",
    "by_index",
    "by_date",
    "by_date_fallback",
    "single",
}

# 生成随机 params 字典的策略
_params_strategy = st.fixed_dictionaries(
    {},
    optional={
        "start_date": st.sampled_from(["20230101", "20240601", "20200301", ""]),
        "end_date": st.sampled_from(["20231231", "20240630", "20200401", ""]),
        "ts_code": st.sampled_from(["600000.SH", "000001.SZ", "300750.SZ", ""]),
    },
)


# ---------------------------------------------------------------------------
# Property 4 (Task 5.4): 分批策略路由保全
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    entry=st.sampled_from(_ALL_ENTRIES),
    params=_params_strategy,
)
def test_determine_batch_strategy_returns_valid_strategy(
    entry: ApiEntry,
    params: dict,
) -> None:
    """
    **Validates: Requirements 3.1, 3.3**

    对任意注册的 ApiEntry 和随机 params，determine_batch_strategy() 必须
    返回预期策略集合中的一个值。确保路由函数不会返回意外的策略字符串。
    """
    strategy = determine_batch_strategy(entry, params)
    assert strategy in _VALID_STRATEGIES, (
        f"接口 {entry.api_name}: determine_batch_strategy() 返回了意外的策略 "
        f"'{strategy}'，预期为 {_VALID_STRATEGIES} 之一"
    )


@settings(max_examples=200)
@given(
    entry=st.sampled_from(_ALL_ENTRIES),
    params=_params_strategy,
)
def test_determine_batch_strategy_is_deterministic(
    entry: ApiEntry,
    params: dict,
) -> None:
    """
    **Validates: Requirements 3.1, 3.3**

    对同一 (ApiEntry, params) 输入，determine_batch_strategy() 的两次调用
    必须返回相同的策略字符串。确保路由函数是确定性的纯函数。
    """
    result1 = determine_batch_strategy(entry, params)
    result2 = determine_batch_strategy(entry, params)
    assert result1 == result2, (
        f"接口 {entry.api_name}: determine_batch_strategy() 两次调用返回不同结果 "
        f"'{result1}' vs '{result2}'，路由函数应为确定性纯函数"
    )


@settings(max_examples=200)
@given(
    entry=st.sampled_from(_ALL_ENTRIES),
)
def test_determine_batch_strategy_priority_batch_by_code(
    entry: ApiEntry,
) -> None:
    """
    **Validates: Requirements 3.1, 3.3**

    当 entry.batch_by_code=True 时，determine_batch_strategy() 必须返回
    "by_code" 或 "by_code_and_date"（若同时 batch_by_date 且有日期范围）。
    验证 batch_by_code 的最高优先级路由逻辑不变。
    """
    if not entry.batch_by_code:
        return  # 仅测试 batch_by_code=True 的接口

    # 无日期范围 → 应返回 "by_code"
    params_no_date = {"ts_code": ""}
    strategy = determine_batch_strategy(entry, params_no_date)
    assert strategy in ("by_code", "by_code_and_date"), (
        f"接口 {entry.api_name} (batch_by_code=True): "
        f"无日期范围时应返回 'by_code' 或 'by_code_and_date'，实际 '{strategy}'"
    )

    # 有日期范围且 batch_by_date → 应返回 "by_code_and_date"
    if entry.batch_by_date:
        params_with_date = {
            "start_date": "20230101",
            "end_date": "20231231",
            "ts_code": "",
        }
        strategy_date = determine_batch_strategy(entry, params_with_date)
        assert strategy_date == "by_code_and_date", (
            f"接口 {entry.api_name} (batch_by_code=True, batch_by_date=True): "
            f"有日期范围时应返回 'by_code_and_date'，实际 '{strategy_date}'"
        )


# ---------------------------------------------------------------------------
# Property 5 (Task 5.5): 字段映射和代码转换保全
# ---------------------------------------------------------------------------

# 筛选出有 field_mappings 的接口
_ENTRIES_WITH_MAPPINGS = [
    e for e in _ALL_ENTRIES if e.field_mappings
]

# 生成随机行数据的策略：基于 entry 的 field_mappings 生成包含 source 字段的行
_field_value_strategy = st.one_of(
    st.text(min_size=0, max_size=20),
    st.integers(min_value=-10000, max_value=10000),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.none(),
)


@st.composite
def rows_with_field_mappings(draw):
    """生成 (rows, entry) 对，其中 rows 包含 entry.field_mappings 中的 source 字段。"""
    if _ENTRIES_WITH_MAPPINGS:
        entry = draw(st.sampled_from(_ENTRIES_WITH_MAPPINGS))
    else:
        # 兜底：使用任意 entry（field_mappings 为空时 pass-through）
        entry = draw(st.sampled_from(_ALL_ENTRIES))

    # 构建行数据：包含所有 source 字段 + 可能的额外字段
    source_fields = [fm.source for fm in entry.field_mappings]
    extra_fields = draw(st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=10,
        ),
        min_size=0,
        max_size=3,
    ))

    all_fields = source_fields + extra_fields
    num_rows = draw(st.integers(min_value=1, max_value=5))

    rows = []
    for _ in range(num_rows):
        row = {}
        for field_name in all_fields:
            row[field_name] = draw(_field_value_strategy)
        rows.append(row)

    return rows, entry


@settings(max_examples=100)
@given(data=rows_with_field_mappings())
def test_apply_field_mappings_correctly_renames_fields(data) -> None:
    """
    **Validates: Requirements 3.6**

    对任意 (rows, entry) 对，_apply_field_mappings() 必须：
    1. 将 field_mappings 中定义的 source 字段重命名为 target 字段
    2. 保留未在 field_mappings 中定义的字段不变
    3. 输出行数与输入行数一致
    """
    rows, entry = data
    result = _apply_field_mappings(rows, entry)

    # 行数不变
    assert len(result) == len(rows), (
        f"接口 {entry.api_name}: _apply_field_mappings() 输出行数 {len(result)} "
        f"!= 输入行数 {len(rows)}"
    )

    # 构建映射字典
    mapping = {fm.source: fm.target for fm in entry.field_mappings}

    for i, (orig_row, mapped_row) in enumerate(zip(rows, result)):
        for key, value in orig_row.items():
            expected_key = mapping.get(key, key)
            assert expected_key in mapped_row, (
                f"接口 {entry.api_name} 行 {i}: 字段 '{key}' 应映射为 "
                f"'{expected_key}'，但在输出中未找到"
            )
            assert mapped_row[expected_key] == value, (
                f"接口 {entry.api_name} 行 {i}: 字段 '{expected_key}' 的值 "
                f"{mapped_row[expected_key]} != 原始值 {value}"
            )


@settings(max_examples=100)
@given(data=rows_with_field_mappings())
def test_apply_field_mappings_is_deterministic(data) -> None:
    """
    **Validates: Requirements 3.6**

    对同一 (rows, entry) 输入，_apply_field_mappings() 的两次调用
    必须返回相同的结果。确保字段映射是确定性的。
    """
    rows, entry = data
    result1 = _apply_field_mappings(rows, entry)
    result2 = _apply_field_mappings(rows, entry)
    assert result1 == result2, (
        f"接口 {entry.api_name}: _apply_field_mappings() 两次调用返回不同结果"
    )


# 生成包含 ts_code 字段的行数据，用于测试 _convert_codes
_TS_CODE_SAMPLES = [
    "600000.SH", "000001.SZ", "300750.SZ", "688001.SH",
    "430047.BJ", "600519", "000858", "",
]


@st.composite
def rows_with_ts_code(draw):
    """生成 (rows, entry) 对，其中 rows 包含 ts_code 字段。"""
    entry = draw(st.sampled_from(_ALL_ENTRIES))
    num_rows = draw(st.integers(min_value=1, max_value=5))

    rows = []
    for _ in range(num_rows):
        ts_code = draw(st.sampled_from(_TS_CODE_SAMPLES))
        row = {"ts_code": ts_code}
        # 添加一些额外字段
        row["trade_date"] = draw(st.sampled_from(["20230101", "20240601"]))
        row["close"] = draw(st.floats(
            min_value=1.0, max_value=500.0,
            allow_nan=False, allow_infinity=False,
        ))
        rows.append(row)

    return rows, entry


@settings(max_examples=100)
@given(data=rows_with_ts_code())
def test_convert_codes_behavior_by_code_format(data) -> None:
    """
    **Validates: Requirements 3.6**

    对任意 (rows, entry) 对，_convert_codes() 必须：
    - CodeFormat.NONE: 不修改任何字段
    - CodeFormat.STOCK_SYMBOL: 将 ts_code 去后缀存入 symbol 字段
    - CodeFormat.INDEX_CODE: 保留 ts_code 原样
    """
    rows, entry = data
    import copy
    rows_copy = copy.deepcopy(rows)
    result = _convert_codes(rows_copy, entry)

    if entry.code_format == CodeFormat.NONE:
        # 不应添加 symbol 字段（除非原始行已有）
        for i, (orig, converted) in enumerate(zip(rows, result)):
            if "symbol" not in orig:
                assert "symbol" not in converted or converted.get("symbol") == orig.get("symbol"), (
                    f"接口 {entry.api_name} (NONE): 行 {i} 不应添加 symbol 字段"
                )

    elif entry.code_format == CodeFormat.STOCK_SYMBOL:
        for i, converted in enumerate(result):
            ts_code = rows[i].get("ts_code", "")
            if ts_code and "." in str(ts_code):
                expected_symbol = str(ts_code).split(".")[0]
                assert converted.get("symbol") == expected_symbol, (
                    f"接口 {entry.api_name} (STOCK_SYMBOL): 行 {i} symbol "
                    f"'{converted.get('symbol')}' != 预期 '{expected_symbol}'"
                )
            elif ts_code:
                assert converted.get("symbol") == str(ts_code), (
                    f"接口 {entry.api_name} (STOCK_SYMBOL): 行 {i} 无后缀 ts_code "
                    f"应直接作为 symbol"
                )

    elif entry.code_format == CodeFormat.INDEX_CODE:
        # 保留 ts_code 原样，不添加 symbol
        for i, (orig, converted) in enumerate(zip(rows, result)):
            assert converted.get("ts_code") == orig.get("ts_code"), (
                f"接口 {entry.api_name} (INDEX_CODE): 行 {i} ts_code 应保持不变"
            )


@settings(max_examples=100)
@given(data=rows_with_ts_code())
def test_convert_codes_is_deterministic(data) -> None:
    """
    **Validates: Requirements 3.6**

    对同一 (rows, entry) 输入，_convert_codes() 的两次调用
    必须返回相同的结果。确保代码转换是确定性的。
    """
    rows, entry = data
    import copy
    rows_copy1 = copy.deepcopy(rows)
    rows_copy2 = copy.deepcopy(rows)
    result1 = _convert_codes(rows_copy1, entry)
    result2 = _convert_codes(rows_copy2, entry)
    assert result1 == result2, (
        f"接口 {entry.api_name}: _convert_codes() 两次调用返回不同结果"
    )


# ---------------------------------------------------------------------------
# Property 6 (Task 5.6): 截断检测函数行为不变（未截断场景）
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    max_rows=st.integers(min_value=1, max_value=10000),
    data=st.data(),
)
def test_check_truncation_returns_false_for_non_truncated(
    max_rows: int,
    data,
) -> None:
    """
    **Validates: Requirements 3.2**

    对任意 row_count < max_rows 的输入，check_truncation() 必须返回 False。
    确保未截断的子区间不会被误判为截断。
    """
    # 生成 row_count 在 [0, max_rows - 1] 范围内
    row_count = data.draw(st.integers(min_value=0, max_value=max_rows - 1))

    result = check_truncation(
        row_count=row_count,
        max_rows=max_rows,
        api_name="test_api",
        chunk_start="20230101",
        chunk_end="20230131",
    )

    assert result is False, (
        f"check_truncation(row_count={row_count}, max_rows={max_rows}) "
        f"返回 True，但 row_count < max_rows 时应返回 False"
    )


@settings(max_examples=200)
@given(
    entry=st.sampled_from(_ALL_ENTRIES),
    max_rows=st.integers(min_value=100, max_value=10000),
    data=st.data(),
)
def test_check_truncation_non_truncated_with_real_entries(
    entry: ApiEntry,
    max_rows: int,
    data,
) -> None:
    """
    **Validates: Requirements 3.2**

    对任意注册的 ApiEntry 和 row_count < max_rows 的输入，
    check_truncation() 必须返回 False。使用真实接口名称验证。
    """
    row_count = data.draw(st.integers(min_value=0, max_value=max_rows - 1))

    result = check_truncation(
        row_count=row_count,
        max_rows=max_rows,
        api_name=entry.api_name,
        chunk_start="20230101",
        chunk_end="20230630",
    )

    assert result is False, (
        f"接口 {entry.api_name}: check_truncation(row_count={row_count}, "
        f"max_rows={max_rows}) 返回 True，但 row_count < max_rows 时应返回 False"
    )
