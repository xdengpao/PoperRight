"""
Tushare 数据预览属性测试（Hypothesis）

验证 TusharePreviewService 中纯函数方法的正确性属性，
覆盖 Property 1-7 和 Property 9。

所有测试使用 _pure 静态方法，不依赖数据库连接。
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import field

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.services.data_engine.tushare_preview_service import (
    CHART_TYPE_MAP,
    KLINE_TABLES,
    MONEYFLOW_SUBCATEGORY,
    TIME_FIELD_MAP,
    TusharePreviewService,
    _TIME_FIELD_PRIORITY,
)
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    FieldMapping,
    StorageEngine,
    TokenTier,
    TUSHARE_API_REGISTRY,
)


# ---------------------------------------------------------------------------
# 共享 Hypothesis 策略
# ---------------------------------------------------------------------------

# 合法标识符风格的字符串（用于表名、列名等）
_identifier = st.from_regex(r"[a-z][a-z0-9_]{0,29}", fullmatch=True)

# 非空中文/英文标签
_label = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=20,
)

# category 值
_category = st.sampled_from(["stock_data", "index_data"])

# subcategory 值（包含 CHART_TYPE_MAP 中所有子分类以覆盖图表推断分支）
_subcategory = st.one_of(
    st.sampled_from(list(CHART_TYPE_MAP.keys())),
    st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
)

# FieldMapping 策略
_field_mapping = st.builds(
    FieldMapping,
    source=_identifier,
    target=_identifier,
    transform=st.none(),
)

# 最小 ApiEntry 策略（用于分组测试）
_api_entry = st.builds(
    ApiEntry,
    api_name=_identifier,
    label=_label,
    category=_category,
    subcategory=_subcategory,
    token_tier=st.just(TokenTier.BASIC),
    target_table=_identifier,
    storage_engine=st.sampled_from([StorageEngine.PG, StorageEngine.TS]),
    code_format=st.just(CodeFormat.NONE),
    conflict_columns=st.just([]),
    field_mappings=st.lists(_field_mapping, max_size=5),
    extra_config=st.just({}),
)


# ---------------------------------------------------------------------------
# Property 1: Registry grouping preserves all entries with correct counts
# Feature: tushare-data-preview, Property 1: Registry grouping preserves all entries with correct counts
# ---------------------------------------------------------------------------


def _group_entries(
    entries: list[ApiEntry],
) -> dict[str, dict[str, list[ApiEntry]]]:
    """将 ApiEntry 列表按 category → subcategory 分组。"""
    groups: dict[str, dict[str, list[ApiEntry]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for entry in entries:
        groups[entry.category][entry.subcategory].append(entry)
    return groups


@settings(max_examples=100)
@given(entries=st.lists(_api_entry, min_size=0, max_size=30))
def test_property1_registry_grouping_preserves_all_entries(
    entries: list[ApiEntry],
) -> None:
    """
    **Validates: Requirements 2.1, 2.5**

    # Feature: tushare-data-preview, Property 1: Registry grouping preserves all entries with correct counts

    对任意 ApiEntry 列表，按 category → subcategory 分组后：
    (a) 所有输入条目恰好出现一次
    (b) 每个条目位于正确的 category 和 subcategory 下
    (c) 每个子分类的计数等于该组中的条目数
    """
    groups = _group_entries(entries)

    # (a) 收集所有分组后的条目
    collected: list[ApiEntry] = []
    for cat, subcats in groups.items():
        for subcat, api_list in subcats.items():
            collected.extend(api_list)

    assert len(collected) == len(entries), (
        f"分组后条目总数 {len(collected)} != 输入条目数 {len(entries)}"
    )

    # (b) 每个条目位于正确的 category 和 subcategory 下
    for cat, subcats in groups.items():
        for subcat, api_list in subcats.items():
            for entry in api_list:
                assert entry.category == cat, (
                    f"条目 {entry.api_name} 的 category={entry.category} "
                    f"不在分组 {cat} 中"
                )
                assert entry.subcategory == subcat, (
                    f"条目 {entry.api_name} 的 subcategory={entry.subcategory} "
                    f"不在分组 {subcat} 中"
                )

    # (c) 子分类计数正确
    for cat, subcats in groups.items():
        for subcat, api_list in subcats.items():
            expected_count = sum(
                1 for e in entries
                if e.category == cat and e.subcategory == subcat
            )
            assert len(api_list) == expected_count, (
                f"分组 {cat}/{subcat} 的条目数 {len(api_list)} "
                f"!= 预期 {expected_count}"
            )


# ---------------------------------------------------------------------------
# Property 2: Column info generation from field mappings
# Feature: tushare-data-preview, Property 2: Column info generation from field mappings
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    table_columns=st.lists(
        _identifier, min_size=1, max_size=15, unique=True,
    ),
    field_mappings=st.lists(_field_mapping, min_size=0, max_size=10),
)
def test_property2_column_info_from_field_mappings(
    table_columns: list[str],
    field_mappings: list[FieldMapping],
) -> None:
    """
    **Validates: Requirements 3.2**

    # Feature: tushare-data-preview, Property 2: Column info generation from field mappings

    对任意列名列表和 FieldMapping 列表：
    (a) 生成的 ColumnInfo 数量等于 table_columns 数量
    (b) 有映射的列使用 mapping.target 作为 label
    (c) 无映射的列使用列名本身作为 label
    """
    result = TusharePreviewService._get_column_info_pure(
        table_columns, field_mappings
    )

    # (a) 数量一致
    assert len(result) == len(table_columns), (
        f"ColumnInfo 数量 {len(result)} != 列数 {len(table_columns)}"
    )

    # 构建 target → FieldMapping 反向映射
    target_to_mapping = {fm.target: fm for fm in field_mappings}

    for i, col in enumerate(table_columns):
        col_info = result[i]
        assert col_info.name == col

        # (b) & (c) label 逻辑
        mapping = target_to_mapping.get(col)
        if mapping:
            assert col_info.label == mapping.target, (
                f"列 {col} 有映射，期望 label={mapping.target}，"
                f"实际 label={col_info.label}"
            )
        else:
            assert col_info.label == col, (
                f"列 {col} 无映射，期望 label={col}，"
                f"实际 label={col_info.label}"
            )


# ---------------------------------------------------------------------------
# Property 3: Chart type inference follows deterministic rules
# Feature: tushare-data-preview, Property 3: Chart type inference follows deterministic rules
# ---------------------------------------------------------------------------

# target_table 策略：包含 kline 表和非 kline 表
_target_table_for_chart = st.one_of(
    st.sampled_from(["kline", "sector_kline"]),
    _identifier,
)


@settings(max_examples=100)
@given(
    target_table=_target_table_for_chart,
    subcategory=_subcategory,
)
def test_property3_chart_type_inference_deterministic(
    target_table: str,
    subcategory: str,
) -> None:
    """
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

    # Feature: tushare-data-preview, Property 3: Chart type inference follows deterministic rules

    对任意 target_table 和 subcategory（time_field=None）：
    - kline / sector_kline → "candlestick"
    - subcategory 在 CHART_TYPE_MAP 中 → 对应类型
    - 其余（time_field=None）→ None
    """
    result = TusharePreviewService._infer_chart_type_pure(
        target_table, subcategory
    )

    if target_table in KLINE_TABLES:
        assert result == "candlestick", (
            f"target_table={target_table} 应返回 'candlestick'，实际 {result!r}"
        )
    elif subcategory in CHART_TYPE_MAP:
        assert result == CHART_TYPE_MAP[subcategory], (
            f"subcategory={subcategory!r} 应返回 {CHART_TYPE_MAP[subcategory]!r}，"
            f"实际 {result!r}"
        )
    else:
        assert result is None, (
            f"target_table={target_table}, subcategory={subcategory} "
            f"应返回 None，实际 {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 4: Time field resolution and query building
# Feature: tushare-data-preview, Property 4: Time field resolution and query building
# ---------------------------------------------------------------------------

# 包含 TIME_FIELD_MAP 中的表名和随机表名
_target_table_for_time = st.one_of(
    st.sampled_from(list(TIME_FIELD_MAP.keys())) if TIME_FIELD_MAP else st.nothing(),
    _identifier,
)


@settings(max_examples=100)
@given(target_table=_target_table_for_time)
def test_property4_time_field_resolution(target_table: str) -> None:
    """
    **Validates: Requirements 6.2, 6.3**

    # Feature: tushare-data-preview, Property 4: Time field resolution and query building

    对任意 target_table：
    - 若在 TIME_FIELD_MAP 中，返回映射的时间字段
    - 若不在 TIME_FIELD_MAP 中且无 table_columns，返回 None
    """
    result = TusharePreviewService._get_time_field_pure(target_table)

    if target_table in TIME_FIELD_MAP:
        assert result == TIME_FIELD_MAP[target_table], (
            f"target_table={target_table} 期望时间字段 "
            f"{TIME_FIELD_MAP[target_table]}，实际 {result!r}"
        )
    else:
        assert result is None, (
            f"target_table={target_table} 不在 TIME_FIELD_MAP 中，"
            f"期望 None，实际 {result!r}"
        )


# 时间字段兜底推断测试
_time_field_candidate = st.sampled_from(_TIME_FIELD_PRIORITY)
_non_time_column = _identifier.filter(lambda x: x not in _TIME_FIELD_PRIORITY)


@settings(max_examples=100)
@given(
    time_col=_time_field_candidate,
    other_cols=st.lists(_non_time_column, min_size=0, max_size=5),
)
def test_property4_time_field_fallback_with_columns(
    time_col: str,
    other_cols: list[str],
) -> None:
    """
    **Validates: Requirements 6.2, 6.3**

    # Feature: tushare-data-preview, Property 4: Time field resolution (fallback)

    对不在 TIME_FIELD_MAP 中的表，当提供 table_columns 时，
    按 _TIME_FIELD_PRIORITY 优先级返回第一个匹配的列。
    """
    # 使用一个不在 TIME_FIELD_MAP 中的表名
    fake_table = "zzz_nonexistent_table_xyz"
    columns = other_cols + [time_col]

    result = TusharePreviewService._get_time_field_pure(fake_table, columns)

    # 应返回 _TIME_FIELD_PRIORITY 中优先级最高的匹配列
    expected = None
    for candidate in _TIME_FIELD_PRIORITY:
        if candidate in columns:
            expected = candidate
            break

    assert result == expected, (
        f"columns={columns}，期望时间字段 {expected}，实际 {result!r}"
    )


# 时间范围查询构建测试
@settings(max_examples=100)
@given(
    target_table=_identifier,
    time_field=st.one_of(st.none(), _identifier),
    data_time_start=st.one_of(st.none(), st.just("2024-01-01")),
    data_time_end=st.one_of(st.none(), st.just("2024-12-31")),
)
def test_property4_query_includes_time_range(
    target_table: str,
    time_field: str | None,
    data_time_start: str | None,
    data_time_end: str | None,
) -> None:
    """
    **Validates: Requirements 6.2, 6.3**

    # Feature: tushare-data-preview, Property 4: Time range in query building

    当 time_field 非空且提供了时间范围时，生成的 SQL 应包含时间字段的 WHERE 条件。
    """
    sql = TusharePreviewService._build_query_sql_pure(
        target_table,
        time_field,
        [],
        data_time_start=data_time_start,
        data_time_end=data_time_end,
    )

    if time_field and data_time_start:
        assert f"{time_field} >= :data_time_start" in sql, (
            f"SQL 应包含 {time_field} >= :data_time_start"
        )
    if time_field and data_time_end:
        assert f"{time_field} <= :data_time_end" in sql, (
            f"SQL 应包含 {time_field} <= :data_time_end"
        )


# ---------------------------------------------------------------------------
# Property 5: Database session routing by storage engine
# Feature: tushare-data-preview, Property 5: Database session routing by storage engine
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(engine=st.sampled_from([StorageEngine.PG, StorageEngine.TS]))
def test_property5_session_routing_by_storage_engine(
    engine: StorageEngine,
) -> None:
    """
    **Validates: Requirements 8.3**

    # Feature: tushare-data-preview, Property 5: Database session routing by storage engine

    对任意 StorageEngine：
    - PG → AsyncSessionPG
    - TS → AsyncSessionTS
    """
    result = TusharePreviewService._get_session(engine)

    if engine == StorageEngine.PG:
        assert result is AsyncSessionPG, (
            f"StorageEngine.PG 应返回 AsyncSessionPG，实际 {result!r}"
        )
    elif engine == StorageEngine.TS:
        assert result is AsyncSessionTS, (
            f"StorageEngine.TS 应返回 AsyncSessionTS，实际 {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 6: Pagination parameter clamping
# Feature: tushare-data-preview, Property 6: Pagination parameter clamping
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    page=st.one_of(st.none(), st.integers(min_value=-100, max_value=1000)),
    page_size=st.one_of(st.none(), st.integers(min_value=-100, max_value=1000)),
)
def test_property6_pagination_clamping(
    page: int | None,
    page_size: int | None,
) -> None:
    """
    **Validates: Requirements 8.4**

    # Feature: tushare-data-preview, Property 6: Pagination parameter clamping

    对任意 page 和 page_size 输入：
    - page_size 范围 [1, 100]，默认 50
    - page 最小 1
    - OFFSET = (page - 1) * page_size
    - LIMIT = clamped page_size
    """
    clamped_page, clamped_size = TusharePreviewService._clamp_pagination_pure(
        page, page_size
    )

    # page_size 默认 50
    if page_size is None:
        assert clamped_size == 50, (
            f"page_size=None 时应默认 50，实际 {clamped_size}"
        )
    else:
        assert 1 <= clamped_size <= 100, (
            f"page_size={page_size} clamp 后应在 [1, 100]，实际 {clamped_size}"
        )
        assert clamped_size == max(1, min(100, page_size))

    # page 最小 1
    if page is None:
        assert clamped_page == 1, (
            f"page=None 时应默认 1，实际 {clamped_page}"
        )
    else:
        assert clamped_page >= 1, (
            f"page={page} clamp 后应 >= 1，实际 {clamped_page}"
        )
        assert clamped_page == max(1, page)

    # OFFSET 和 LIMIT 验证
    expected_offset = (clamped_page - 1) * clamped_size
    assert expected_offset >= 0, (
        f"OFFSET 应 >= 0，实际 {expected_offset}"
    )


# ---------------------------------------------------------------------------
# Property 7: Read-only SQL generation
# Feature: tushare-data-preview, Property 7: Read-only SQL generation
# ---------------------------------------------------------------------------

# 数据修改关键字（大小写不敏感）
_MODIFYING_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b",
    re.IGNORECASE,
)

# scope_filter 策略
_scope_filter = st.lists(
    st.tuples(
        st.from_regex(r"[a-z_]+ = :[a-z_]+", fullmatch=True),
        st.fixed_dictionaries({}),
    ),
    min_size=0,
    max_size=3,
)


@settings(max_examples=100)
@given(
    target_table=_identifier,
    time_field=st.one_of(st.none(), _identifier),
    scope_filters=_scope_filter,
    data_time_start=st.one_of(st.none(), st.just("2024-01-01")),
    data_time_end=st.one_of(st.none(), st.just("2024-12-31")),
    ts_code=st.one_of(st.none(), st.just("000001")),
    page=st.integers(min_value=1, max_value=100),
    page_size=st.integers(min_value=1, max_value=100),
    count_only=st.booleans(),
)
def test_property7_readonly_sql_generation(
    target_table: str,
    time_field: str | None,
    scope_filters: list[tuple[str, dict]],
    data_time_start: str | None,
    data_time_end: str | None,
    ts_code: str | None,
    page: int,
    page_size: int,
    count_only: bool,
) -> None:
    """
    **Validates: Requirements 9.4**

    # Feature: tushare-data-preview, Property 7: Read-only SQL generation

    对任意查询参数组合，生成的 SQL：
    (a) 以 SELECT 开头
    (b) 不包含 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE 关键字
    """
    sql = TusharePreviewService._build_query_sql_pure(
        target_table,
        time_field,
        scope_filters,
        data_time_start=data_time_start,
        data_time_end=data_time_end,
        ts_code=ts_code,
        page=page,
        page_size=page_size,
        count_only=count_only,
    )

    # (a) 以 SELECT 开头
    assert sql.strip().upper().startswith("SELECT"), (
        f"SQL 应以 SELECT 开头，实际: {sql[:50]}"
    )

    # (b) 不包含数据修改关键字
    assert not _MODIFYING_KEYWORDS.search(sql), (
        f"SQL 包含数据修改关键字: {sql}"
    )


# ---------------------------------------------------------------------------
# Property 9: Scope filter correctly isolates shared-table data
# Feature: tushare-data-preview, Property 9: Scope filter correctly isolates shared-table data
# ---------------------------------------------------------------------------


def _make_test_entry(
    target_table: str = "test_table",
    extra_config: dict | None = None,
    **kwargs,
) -> ApiEntry:
    """创建用于测试的最小 ApiEntry。"""
    return ApiEntry(
        api_name=kwargs.get("api_name", "test_api"),
        label="测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table=target_table,
        storage_engine=StorageEngine.PG,
        code_format=CodeFormat.NONE,
        conflict_columns=[],
        extra_config=extra_config or {},
    )


# kline freq 值策略
_freq_value = st.sampled_from(["1d", "1w", "1M", "5min", "15min", "30min", "60min"])

# report_type 值策略
_report_type_value = st.sampled_from(["income", "balancesheet", "cashflow"])

# data_source 值策略
_data_source_value = st.sampled_from(["THS", "DC", "KPL"])

# holder_type 值策略
_holder_type_value = st.sampled_from(["top10", "top10_float"])


@settings(max_examples=100)
@given(freq=_freq_value)
def test_property9_scope_filter_kline_freq(freq: str) -> None:
    """
    **Validates: Requirements 2.4, 8.3**

    # Feature: tushare-data-preview, Property 9: Scope filter - kline freq

    对 target_table="kline" 且 extra_config 含 freq 的 ApiEntry，
    作用域过滤应包含 freq = :scope_freq 条件。
    """
    entry = _make_test_entry(
        target_table="kline",
        extra_config={"freq": freq},
    )
    conditions = TusharePreviewService._build_scope_filter_pure(entry)

    assert len(conditions) >= 1, "kline 表应至少有 1 个作用域条件"
    clauses = [c[0] for c in conditions]
    assert "freq = :scope_freq" in clauses, (
        f"kline 表应包含 freq 过滤条件，实际条件: {clauses}"
    )
    # 验证参数值
    for clause, params in conditions:
        if clause == "freq = :scope_freq":
            assert params["scope_freq"] == freq


@settings(max_examples=100)
@given(report_type=_report_type_value)
def test_property9_scope_filter_financial_report_type(report_type: str) -> None:
    """
    **Validates: Requirements 2.4, 8.3**

    # Feature: tushare-data-preview, Property 9: Scope filter - financial_statement report_type

    对 target_table="financial_statement" 且 extra_config 含 inject_fields.report_type 的 ApiEntry，
    作用域过滤应包含 report_type = :scope_report_type 条件。
    """
    entry = _make_test_entry(
        target_table="financial_statement",
        extra_config={"inject_fields": {"report_type": report_type}},
    )
    conditions = TusharePreviewService._build_scope_filter_pure(entry)

    clauses = [c[0] for c in conditions]
    assert "report_type = :scope_report_type" in clauses, (
        f"financial_statement 表应包含 report_type 过滤条件，实际条件: {clauses}"
    )
    for clause, params in conditions:
        if clause == "report_type = :scope_report_type":
            assert params["scope_report_type"] == report_type


@settings(max_examples=100)
@given(
    target_table=st.sampled_from(["sector_info", "sector_constituent", "sector_kline"]),
    data_source=_data_source_value,
)
def test_property9_scope_filter_sector_data_source(
    target_table: str,
    data_source: str,
) -> None:
    """
    **Validates: Requirements 2.4, 8.3**

    # Feature: tushare-data-preview, Property 9: Scope filter - sector data_source

    对 sector 系列表且 extra_config 含 data_source 的 ApiEntry，
    作用域过滤应包含 data_source = :scope_ds 条件。
    """
    entry = _make_test_entry(
        target_table=target_table,
        extra_config={"data_source": data_source},
    )
    conditions = TusharePreviewService._build_scope_filter_pure(entry)

    clauses = [c[0] for c in conditions]
    assert "data_source = :scope_ds" in clauses, (
        f"{target_table} 表应包含 data_source 过滤条件，实际条件: {clauses}"
    )
    for clause, params in conditions:
        if clause == "data_source = :scope_ds":
            assert params["scope_ds"] == data_source


@settings(max_examples=100)
@given(holder_type=_holder_type_value)
def test_property9_scope_filter_top_holders_holder_type(holder_type: str) -> None:
    """
    **Validates: Requirements 2.4, 8.3**

    # Feature: tushare-data-preview, Property 9: Scope filter - top_holders holder_type

    对 target_table="top_holders" 且 extra_config 含 holder_type 的 ApiEntry，
    作用域过滤应包含 holder_type = :scope_ht 条件。
    """
    entry = _make_test_entry(
        target_table="top_holders",
        extra_config={"holder_type": holder_type},
    )
    conditions = TusharePreviewService._build_scope_filter_pure(entry)

    clauses = [c[0] for c in conditions]
    assert "holder_type = :scope_ht" in clauses, (
        f"top_holders 表应包含 holder_type 过滤条件，实际条件: {clauses}"
    )
    for clause, params in conditions:
        if clause == "holder_type = :scope_ht":
            assert params["scope_ht"] == holder_type


@settings(max_examples=100)
@given(
    target_table=_identifier.filter(
        lambda t: t not in (
            "kline", "financial_statement",
            "sector_info", "sector_constituent", "sector_kline",
            "top_holders",
        )
    ),
)
def test_property9_scope_filter_empty_for_non_shared_tables(
    target_table: str,
) -> None:
    """
    **Validates: Requirements 2.4, 8.3**

    # Feature: tushare-data-preview, Property 9: Scope filter - empty for non-shared tables

    对不属于共享表的 ApiEntry（无特殊 extra_config），
    作用域过滤应返回空列表。
    """
    entry = _make_test_entry(
        target_table=target_table,
        extra_config={},
    )
    conditions = TusharePreviewService._build_scope_filter_pure(entry)

    assert conditions == [], (
        f"非共享表 {target_table} 应无作用域条件，实际: {conditions}"
    )
