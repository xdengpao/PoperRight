"""
Tushare 数据预览增强属性测试（Hypothesis）

验证 TusharePreviewService 中增强功能纯函数方法的正确性属性，
覆盖 Property 1、2、3、4、7、8。

所有测试使用 _pure 静态方法，不依赖数据库连接。

对应需求：2.5, 2.6, 3.3, 3.4, 3.6, 5.6, 9.1, 9.3, 9.4, 10.2
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.tushare_preview_service import (
    CHART_TYPE_MAP,
    KLINE_TABLES,
    TusharePreviewService,
)


# ---------------------------------------------------------------------------
# 共享 Hypothesis 策略
# ---------------------------------------------------------------------------

# 合法标识符风格的字符串（用于日期、代码等集合元素）
_identifier = st.from_regex(r"[a-z][a-z0-9_]{0,29}", fullmatch=True)

# 日期风格字符串（如 "20240101"）
_date_str = st.from_regex(r"20[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])", fullmatch=True)

# 代码风格字符串（如 "000001.SZ"）
_code_str = st.from_regex(r"[0-9]{6}\.(SZ|SH|BJ)", fullmatch=True)

# 字符串集合策略
_string_set = st.frozensets(st.text(min_size=1, max_size=20), min_size=0, max_size=50)

# subcategory 值（包含 CHART_TYPE_MAP 中所有子分类以覆盖图表推断分支）
_subcategory = st.one_of(
    st.sampled_from(list(CHART_TYPE_MAP.keys())),
    st.text(
        min_size=1,
        max_size=10,
        alphabet=st.characters(whitelist_categories=("L",)),
    ),
)

# target_table 策略：包含 kline 表和非 kline 表
_target_table_for_chart = st.one_of(
    st.sampled_from(sorted(KLINE_TABLES)),
    _identifier,
)

# time_field 策略：None 或标识符
_time_field = st.one_of(st.none(), _identifier)


# ---------------------------------------------------------------------------
# Property 1: Set difference computation for missing items
# Feature: tushare-data-preview-enhancement, Property 1: Set difference computation for missing items
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    expected=_string_set,
    actual=_string_set,
)
def test_property1_compute_missing_dates_pure(
    expected: frozenset[str],
    actual: frozenset[str],
) -> None:
    """
    **Validates: Requirements 2.5**

    # Feature: tushare-data-preview-enhancement, Property 1: Set difference computation for missing items

    对任意两个字符串集合（expected 和 actual），
    _compute_missing_dates_pure 返回 sorted(expected - actual)。
    结果长度等于 len(expected) - len(expected ∩ actual)，
    每个元素都在 expected 中但不在 actual 中，且结果按升序排列。
    """
    result = TusharePreviewService._compute_missing_dates_pure(
        set(expected), set(actual)
    )

    expected_diff = sorted(expected - actual)

    # 结果等于 sorted(expected - actual)
    assert result == expected_diff, (
        f"期望 {expected_diff}，实际 {result}"
    )

    # 结果长度等于 len(expected) - len(expected ∩ actual)
    intersection_size = len(expected & actual)
    assert len(result) == len(expected) - intersection_size, (
        f"结果长度 {len(result)} != len(expected) - len(expected ∩ actual) = "
        f"{len(expected)} - {intersection_size}"
    )

    # 每个元素在 expected 中但不在 actual 中
    for item in result:
        assert item in expected, f"{item!r} 不在 expected 中"
        assert item not in actual, f"{item!r} 在 actual 中"

    # 结果按升序排列
    assert result == sorted(result), "结果未按升序排列"


@settings(max_examples=100)
@given(
    expected=_string_set,
    actual=_string_set,
)
def test_property1_compute_missing_codes_pure(
    expected: frozenset[str],
    actual: frozenset[str],
) -> None:
    """
    **Validates: Requirements 3.3**

    # Feature: tushare-data-preview-enhancement, Property 1: Set difference computation for missing items

    对任意两个字符串集合（expected 和 actual），
    _compute_missing_codes_pure 返回 sorted(expected - actual)。
    结果长度等于 len(expected) - len(expected ∩ actual)，
    每个元素都在 expected 中但不在 actual 中，且结果按升序排列。
    """
    result = TusharePreviewService._compute_missing_codes_pure(
        set(expected), set(actual)
    )

    expected_diff = sorted(expected - actual)

    # 结果等于 sorted(expected - actual)
    assert result == expected_diff, (
        f"期望 {expected_diff}，实际 {result}"
    )

    # 结果长度等于 len(expected) - len(expected ∩ actual)
    intersection_size = len(expected & actual)
    assert len(result) == len(expected) - intersection_size, (
        f"结果长度 {len(result)} != len(expected) - len(expected ∩ actual) = "
        f"{len(expected)} - {intersection_size}"
    )

    # 每个元素在 expected 中但不在 actual 中
    for item in result:
        assert item in expected, f"{item!r} 不在 expected 中"
        assert item not in actual, f"{item!r} 在 actual 中"

    # 结果按升序排列
    assert result == sorted(result), "结果未按升序排列"


# ---------------------------------------------------------------------------
# Property 2: Completeness report field consistency
# Feature: tushare-data-preview-enhancement, Property 2: Completeness report field consistency
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    expected=_string_set,
    actual=_string_set,
    check_type=st.sampled_from(["time_series", "code_based", "unsupported"]),
    time_range=st.one_of(
        st.none(),
        st.fixed_dictionaries({"start": _date_str, "end": _date_str}),
    ),
    message=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
)
def test_property2_completeness_report_field_consistency(
    expected: frozenset[str],
    actual: frozenset[str],
    check_type: str,
    time_range: dict | None,
    message: str | None,
) -> None:
    """
    **Validates: Requirements 2.6, 3.4**

    # Feature: tushare-data-preview-enhancement, Property 2: Completeness report field consistency

    对任意 expected/actual 集合及其计算出的 missing 列表，
    _build_completeness_report_pure 返回的报告满足：
    (a) expected_count == len(expected)
    (b) actual_count == len(actual)
    (c) missing_count == len(missing)
    (d) completeness_rate == actual_count / expected_count（expected 为空时为 1.0）
    (e) completeness_rate 在 [0.0, 1.0] 范围内
    (f) missing_items 等于传入的 missing 列表
    (g) 报告包含所有必需字段
    """
    expected_set = set(expected)
    actual_set = set(actual)
    missing = sorted(expected_set - actual_set)

    report = TusharePreviewService._build_completeness_report_pure(
        check_type=check_type,
        expected=expected_set,
        actual=actual_set,
        missing=missing,
        time_range=time_range,
        message=message,
    )

    # (a) expected_count
    assert report["expected_count"] == len(expected_set), (
        f"expected_count {report['expected_count']} != {len(expected_set)}"
    )

    # (b) actual_count
    assert report["actual_count"] == len(actual_set), (
        f"actual_count {report['actual_count']} != {len(actual_set)}"
    )

    # (c) missing_count
    assert report["missing_count"] == len(missing), (
        f"missing_count {report['missing_count']} != {len(missing)}"
    )

    # (d) completeness_rate
    if len(expected_set) > 0:
        expected_rate = round(len(actual_set) / len(expected_set), 4)
        assert report["completeness_rate"] == expected_rate, (
            f"completeness_rate {report['completeness_rate']} != {expected_rate}"
        )
    else:
        assert report["completeness_rate"] == 1.0, (
            f"expected 为空时 completeness_rate 应为 1.0，"
            f"实际 {report['completeness_rate']}"
        )

    # (e) completeness_rate 非负（actual_count / expected_count 可能 > 1.0）
    assert report["completeness_rate"] >= 0.0, (
        f"completeness_rate {report['completeness_rate']} 不应为负数"
    )

    # (f) missing_items
    assert report["missing_items"] == missing, (
        f"missing_items 不匹配"
    )

    # (g) 必需字段
    required_fields = {
        "check_type", "expected_count", "actual_count",
        "missing_count", "completeness_rate", "missing_items",
        "time_range", "message",
    }
    assert set(report.keys()) == required_fields, (
        f"报告字段 {set(report.keys())} != 预期字段 {required_fields}"
    )

    # check_type 一致
    assert report["check_type"] == check_type
    assert report["time_range"] == time_range
    assert report["message"] == message


# ---------------------------------------------------------------------------
# Property 3: Check type determination
# Feature: tushare-data-preview-enhancement, Property 3: Check type determination
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    time_field=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    has_ts_code=st.booleans(),
)
def test_property3_check_type_determination(
    time_field: str | None,
    has_ts_code: bool,
) -> None:
    """
    **Validates: Requirements 3.6**

    # Feature: tushare-data-preview-enhancement, Property 3: Check type determination

    对任意 (time_field, has_ts_code) 组合，
    _determine_check_type_pure 返回：
    - time_field 非 None → "time_series"
    - time_field 为 None 且 has_ts_code 为 True → "code_based"
    - time_field 为 None 且 has_ts_code 为 False → "unsupported"
    结果完全由这两个输入决定。
    """
    result = TusharePreviewService._determine_check_type_pure(
        time_field, has_ts_code
    )

    if time_field is not None:
        assert result == "time_series", (
            f"time_field={time_field!r} 时应返回 'time_series'，实际 {result!r}"
        )
    elif has_ts_code:
        assert result == "code_based", (
            f"time_field=None, has_ts_code=True 时应返回 'code_based'，"
            f"实际 {result!r}"
        )
    else:
        assert result == "unsupported", (
            f"time_field=None, has_ts_code=False 时应返回 'unsupported'，"
            f"实际 {result!r}"
        )

    # 结果只能是三种之一
    assert result in ("time_series", "code_based", "unsupported"), (
        f"返回值 {result!r} 不在合法范围内"
    )


# ---------------------------------------------------------------------------
# Property 4: COUNT estimation threshold
# Feature: tushare-data-preview-enhancement, Property 4: COUNT estimation threshold
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    reltuples=st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False),
)
def test_property4_count_estimation_threshold(
    reltuples: float,
) -> None:
    """
    **Validates: Requirements 5.6**

    # Feature: tushare-data-preview-enhancement, Property 4: COUNT estimation threshold

    对任意非负浮点数 reltuples：
    - reltuples > 1_000_000 → (True, int(reltuples))
    - reltuples <= 1_000_000 → (False, 0)
    阈值边界严格：恰好 1,000,000 返回 (False, 0)。
    """
    use_estimate, count = TusharePreviewService._estimate_count_pure(reltuples)

    if reltuples > 1_000_000:
        assert use_estimate is True, (
            f"reltuples={reltuples} > 1_000_000 时应返回 use_estimate=True"
        )
        assert count == int(reltuples), (
            f"reltuples={reltuples} 时 count 应为 {int(reltuples)}，实际 {count}"
        )
    else:
        assert use_estimate is False, (
            f"reltuples={reltuples} <= 1_000_000 时应返回 use_estimate=False"
        )
        assert count == 0, (
            f"reltuples={reltuples} <= 1_000_000 时 count 应为 0，实际 {count}"
        )


@settings(max_examples=100)
@given(
    reltuples=st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False),
    threshold=st.integers(min_value=0, max_value=10_000_000),
)
def test_property4_count_estimation_custom_threshold(
    reltuples: float,
    threshold: int,
) -> None:
    """
    **Validates: Requirements 5.6**

    # Feature: tushare-data-preview-enhancement, Property 4: COUNT estimation threshold

    对任意非负浮点数 reltuples 和自定义阈值 threshold：
    - reltuples > threshold → (True, int(reltuples))
    - reltuples <= threshold → (False, 0)
    """
    use_estimate, count = TusharePreviewService._estimate_count_pure(
        reltuples, threshold=threshold
    )

    if reltuples > threshold:
        assert use_estimate is True, (
            f"reltuples={reltuples} > threshold={threshold} 时应返回 True"
        )
        assert count == int(reltuples), (
            f"count 应为 {int(reltuples)}，实际 {count}"
        )
    else:
        assert use_estimate is False, (
            f"reltuples={reltuples} <= threshold={threshold} 时应返回 False"
        )
        assert count == 0, (
            f"count 应为 0，实际 {count}"
        )


# ---------------------------------------------------------------------------
# Property 7: Expanded chart type inference follows priority rules
# Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    target_table=_target_table_for_chart,
    subcategory=_subcategory,
    time_field=_time_field,
)
def test_property7_expanded_chart_type_inference(
    target_table: str,
    subcategory: str,
    time_field: str | None,
) -> None:
    """
    **Validates: Requirements 9.1, 9.3, 9.4**

    # Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules

    对任意 (target_table, subcategory, time_field) 组合，
    扩展后的 _infer_chart_type_pure 遵循严格优先级：
    1. target_table 在 KLINE_TABLES 中 → "candlestick"（无论 subcategory 和 time_field）
    2. subcategory 在 CHART_TYPE_MAP 中 → 对应类型（无论 time_field）
    3. time_field 非 None → "line"（默认折线图）
    4. time_field 为 None → None
    """
    result = TusharePreviewService._infer_chart_type_pure(
        target_table, subcategory, time_field
    )

    # 优先级 1：KLINE_TABLES
    if target_table in KLINE_TABLES:
        assert result == "candlestick", (
            f"target_table={target_table!r} 在 KLINE_TABLES 中，"
            f"应返回 'candlestick'，实际 {result!r}"
        )
        return

    # 优先级 2：CHART_TYPE_MAP
    if subcategory in CHART_TYPE_MAP:
        assert result == CHART_TYPE_MAP[subcategory], (
            f"subcategory={subcategory!r} 在 CHART_TYPE_MAP 中，"
            f"应返回 {CHART_TYPE_MAP[subcategory]!r}，实际 {result!r}"
        )
        return

    # 优先级 3：有 time_field → line
    if time_field is not None:
        assert result == "line", (
            f"time_field={time_field!r} 非 None，应返回 'line'，实际 {result!r}"
        )
        return

    # 优先级 4：无 time_field → None
    assert result is None, (
        f"time_field=None 且不匹配其他规则，应返回 None，实际 {result!r}"
    )


@settings(max_examples=100)
@given(
    subcategory=_subcategory,
    time_field=_time_field,
)
def test_property7_kline_tables_always_candlestick(
    subcategory: str,
    time_field: str | None,
) -> None:
    """
    **Validates: Requirements 9.1**

    # Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules

    对 KLINE_TABLES 中的所有表名，无论 subcategory 和 time_field 如何，
    _infer_chart_type_pure 始终返回 "candlestick"。
    """
    for kline_table in sorted(KLINE_TABLES):
        result = TusharePreviewService._infer_chart_type_pure(
            kline_table, subcategory, time_field
        )
        assert result == "candlestick", (
            f"KLINE_TABLES 中的 {kline_table!r} 应始终返回 'candlestick'，"
            f"subcategory={subcategory!r}, time_field={time_field!r}, "
            f"实际 {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 8: Chart data limit clamping
# Feature: tushare-data-preview-enhancement, Property 8: Chart data limit clamping
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    limit=st.integers(min_value=-1000, max_value=2000),
)
def test_property8_chart_data_limit_clamping(
    limit: int,
) -> None:
    """
    **Validates: Requirements 10.2**

    # Feature: tushare-data-preview-enhancement, Property 8: Chart data limit clamping

    对任意整数 limit：
    - limit <= 0 → 结果为 1
    - limit > 500 → 结果为 500
    - 1 <= limit <= 500 → 结果为 limit 本身
    结果始终在 [1, 500] 范围内。
    """
    result = TusharePreviewService._clamp_chart_limit_pure(limit)

    # 结果范围
    assert 1 <= result <= 500, (
        f"limit={limit} 时结果 {result} 不在 [1, 500] 范围内"
    )

    # 具体行为
    if limit <= 0:
        assert result == 1, (
            f"limit={limit} <= 0 时应返回 1，实际 {result}"
        )
    elif limit > 500:
        assert result == 500, (
            f"limit={limit} > 500 时应返回 500，实际 {result}"
        )
    else:
        assert result == limit, (
            f"limit={limit} 在 [1, 500] 范围内时应返回 {limit}，实际 {result}"
        )


@settings(max_examples=100)
@given(
    data=st.data(),
)
def test_property8_chart_data_limit_none_default(
    data: st.DataObject,
) -> None:
    """
    **Validates: Requirements 10.2**

    # Feature: tushare-data-preview-enhancement, Property 8: Chart data limit clamping

    当 limit 为 None 时，_clamp_chart_limit_pure 返回默认值 250。
    """
    result = TusharePreviewService._clamp_chart_limit_pure(None)
    assert result == 250, (
        f"limit=None 时应返回默认值 250，实际 {result}"
    )
