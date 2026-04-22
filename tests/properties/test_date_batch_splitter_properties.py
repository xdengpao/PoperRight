"""
DateBatchSplitter 属性测试（Hypothesis）

对日期范围拆分器的核心正确性属性进行验证，使用 Hypothesis 生成随机输入覆盖边界情况。

**Feature: tushare-date-batch-import**
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.services.data_engine.date_batch_splitter import DateBatchSplitter


# ---------------------------------------------------------------------------
# 公共生成器策略
# ---------------------------------------------------------------------------

# 日期范围：2000-01-01 ~ 2030-12-31
_date_strategy = st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31))

# 步长：1 ~ 3650 天
_chunk_days_strategy = st.integers(min_value=1, max_value=3650)


def _parse(d: str) -> date:
    """将 YYYYMMDD 字符串解析为 date 对象。"""
    return datetime.strptime(d, "%Y%m%d").date()


# ---------------------------------------------------------------------------
# Property 1: 子区间跨度上界
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    start=_date_strategy,
    end=_date_strategy,
    chunk_days=_chunk_days_strategy,
)
def test_property_1_chunk_span_upper_bound(
    start: date,
    end: date,
    chunk_days: int,
) -> None:
    """
    **Feature: tushare-date-batch-import, Property 1: chunk span bound**

    **Validates: Requirements 2.2**

    对任意合法的 start_date、end_date（start <= end）和正整数 chunk_days，
    DateBatchSplitter.split() 返回的每个子区间 (chunk_start, chunk_end) 的跨度
    （chunk_end - chunk_start + 1 天）不超过 chunk_days。
    """
    assume(start <= end)

    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")

    chunks = DateBatchSplitter.split(start_str, end_str, chunk_days)

    for chunk_start_str, chunk_end_str in chunks:
        chunk_start = _parse(chunk_start_str)
        chunk_end = _parse(chunk_end_str)
        span_days = (chunk_end - chunk_start).days + 1
        assert span_days <= chunk_days, (
            f"子区间 [{chunk_start_str}, {chunk_end_str}] 跨度为 {span_days} 天，"
            f"超过 chunk_days={chunk_days}"
        )


# ---------------------------------------------------------------------------
# Property 2: 子区间连续无重叠且边界对齐
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    start=_date_strategy,
    end=_date_strategy,
    chunk_days=_chunk_days_strategy,
)
def test_property_2_contiguous_non_overlapping_boundary_aligned(
    start: date,
    end: date,
    chunk_days: int,
) -> None:
    """
    **Feature: tushare-date-batch-import, Property 2: contiguous non-overlapping boundary-aligned**

    **Validates: Requirements 2.3, 2.7**

    对任意合法的 start_date、end_date 和正整数 chunk_days，
    DateBatchSplitter.split() 返回的子区间列表满足：
    - 第一个子区间的 chunk_start 等于 start_date
    - 最后一个子区间的 chunk_end 等于 end_date
    - 对于任意相邻的两个子区间，前一个的 chunk_end 加 1 天恰好等于后一个的 chunk_start
    """
    assume(start <= end)

    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")

    chunks = DateBatchSplitter.split(start_str, end_str, chunk_days)

    assert len(chunks) >= 1, "子区间列表不应为空"

    # 第一个子区间的 chunk_start 等于 start_date
    first_start = _parse(chunks[0][0])
    assert first_start == start, (
        f"第一个子区间 chunk_start={chunks[0][0]}，期望 {start_str}"
    )

    # 最后一个子区间的 chunk_end 等于 end_date
    last_end = _parse(chunks[-1][1])
    assert last_end == end, (
        f"最后一个子区间 chunk_end={chunks[-1][1]}，期望 {end_str}"
    )

    # 相邻子区间：前一个 chunk_end + 1天 == 后一个 chunk_start
    for i in range(len(chunks) - 1):
        prev_end = _parse(chunks[i][1])
        next_start = _parse(chunks[i + 1][0])
        expected_next_start = prev_end + timedelta(days=1)
        assert next_start == expected_next_start, (
            f"子区间 {i} 的 chunk_end={chunks[i][1]} + 1天 = "
            f"{expected_next_start.strftime('%Y%m%d')}，"
            f"但子区间 {i+1} 的 chunk_start={chunks[i+1][0]}"
        )


# ---------------------------------------------------------------------------
# Property 3: 日期覆盖 Round-Trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    start=_date_strategy,
    end=_date_strategy,
    chunk_days=_chunk_days_strategy,
)
def test_property_3_date_coverage_round_trip(
    start: date,
    end: date,
    chunk_days: int,
) -> None:
    """
    **Feature: tushare-date-batch-import, Property 3: date coverage round-trip**

    **Validates: Requirements 2.6**

    对任意合法的 start_date、end_date 和正整数 chunk_days，
    将 DateBatchSplitter.split() 返回的所有子区间展开为各自包含的日期集合，
    其并集恰好等于从 start_date 到 end_date 的完整日期集合（无遗漏、无多余）。
    """
    assume(start <= end)

    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")

    chunks = DateBatchSplitter.split(start_str, end_str, chunk_days)

    # 展开所有子区间为日期集合
    chunk_dates: set[date] = set()
    for chunk_start_str, chunk_end_str in chunks:
        chunk_start = _parse(chunk_start_str)
        chunk_end = _parse(chunk_end_str)
        cursor = chunk_start
        while cursor <= chunk_end:
            chunk_dates.add(cursor)
            cursor += timedelta(days=1)

    # 构建完整日期集合
    expected_dates: set[date] = set()
    cursor = start
    while cursor <= end:
        expected_dates.add(cursor)
        cursor += timedelta(days=1)

    assert chunk_dates == expected_dates, (
        f"日期覆盖不匹配：遗漏 {expected_dates - chunk_dates}，"
        f"多余 {chunk_dates - expected_dates}"
    )


# ---------------------------------------------------------------------------
# Property 4 所需导入
# ---------------------------------------------------------------------------

from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    ParamType,
    RateLimitGroup,
    StorageEngine,
    TokenTier,
)
from app.tasks.tushare_import import determine_batch_strategy


# ---------------------------------------------------------------------------
# Property 4 生成器策略
# ---------------------------------------------------------------------------

# 与路由逻辑相关的 ParamType 子集
_routing_param_types = [
    ParamType.DATE_RANGE,
    ParamType.STOCK_CODE,
    ParamType.INDEX_CODE,
]

# 生成 ParamType 子集列表（从路由相关的参数类型中选取）
_param_subset_strategy = st.lists(
    st.sampled_from(_routing_param_types),
    max_size=3,
    unique=True,
)

# 生成随机 ApiEntry 配置（仅包含影响路由的字段，其余使用固定值）
_api_entry_strategy = st.builds(
    ApiEntry,
    api_name=st.just("test_api"),
    label=st.just("测试接口"),
    category=st.just("test"),
    subcategory=st.just("test"),
    token_tier=st.just(TokenTier.BASIC),
    target_table=st.just("test_table"),
    storage_engine=st.just(StorageEngine.PG),
    code_format=st.just(CodeFormat.NONE),
    conflict_columns=st.just(["id"]),
    batch_by_code=st.booleans(),
    batch_by_date=st.booleans(),
    required_params=_param_subset_strategy,
    optional_params=_param_subset_strategy,
)

# 生成用户参数字典（可选包含 ts_code、start_date、end_date）
_user_params_strategy = st.fixed_dictionaries(
    {},
    optional={
        "ts_code": st.just("000001.SZ"),
        "start_date": st.just("20230101"),
        "end_date": st.just("20231231"),
    },
)


# ---------------------------------------------------------------------------
# Property 4: 分批策略路由优先级
# ---------------------------------------------------------------------------


def _expected_strategy(entry: ApiEntry, params: dict) -> str:
    """根据设计文档中的优先级规则，独立计算期望的分批策略。

    此函数作为属性测试的 oracle，与 determine_batch_strategy 的实现独立，
    用于验证路由选择严格遵循优先级。
    """
    has_date_params = bool(params.get("start_date") and params.get("end_date"))
    has_ts_code = bool(params.get("ts_code"))

    # 优先级 1：batch_by_code（含自动推断）
    use_batch_code = entry.batch_by_code
    if not use_batch_code and not has_ts_code:
        has_stock_param = (
            ParamType.STOCK_CODE in entry.required_params
            or ParamType.STOCK_CODE in entry.optional_params
        )
        if has_stock_param:
            use_batch_code = True

    if use_batch_code:
        if entry.batch_by_date and has_date_params:
            return "by_code_and_date"
        return "by_code"

    # 优先级 2：INDEX_CODE 且未指定 ts_code
    if not has_ts_code:
        has_index_param = (
            ParamType.INDEX_CODE in entry.required_params
            or ParamType.INDEX_CODE in entry.optional_params
        )
        if has_index_param:
            return "by_index"

    # 优先级 3：batch_by_date 声明 + 有日期范围
    if entry.batch_by_date and has_date_params:
        return "by_date"

    # 优先级 4：兜底日期分批
    if not entry.batch_by_date and has_date_params:
        has_date_range = (
            ParamType.DATE_RANGE in entry.required_params
            or ParamType.DATE_RANGE in entry.optional_params
        )
        if has_date_range:
            return "by_date_fallback"

    # 优先级 5：单次调用
    return "single"


@settings(max_examples=100)
@given(
    entry=_api_entry_strategy,
    params=_user_params_strategy,
)
def test_property_4_batch_strategy_routing_priority(
    entry: ApiEntry,
    params: dict,
) -> None:
    """
    **Feature: tushare-date-batch-import, Property 4: strategy routing priority**

    **Validates: Requirements 4.1**

    对任意 ApiEntry 配置（batch_by_code、batch_by_date、required_params、
    optional_params 的任意合法组合）和用户参数（是否包含 ts_code、start_date、
    end_date），determine_batch_strategy() 选择的分批策略严格遵循以下优先级：
    1. batch_by_code=True → "by_code"（若同时 batch_by_date 且有日期范围 → "by_code_and_date"）
    2. INDEX_CODE 且未指定 ts_code → "by_index"
    3. batch_by_date=True 且有日期范围 → "by_date"
    4. 未声明 batch_by_date 但有 DATE_RANGE 且有日期范围 → "by_date_fallback"
    5. 以上均不满足 → "single"
    """
    actual = determine_batch_strategy(entry, params)
    expected = _expected_strategy(entry, params)

    assert actual == expected, (
        f"路由优先级不匹配：\n"
        f"  entry: batch_by_code={entry.batch_by_code}, batch_by_date={entry.batch_by_date}, "
        f"required_params={entry.required_params}, optional_params={entry.optional_params}\n"
        f"  params: {params}\n"
        f"  期望: {expected}, 实际: {actual}"
    )
