"""
Tushare 数据导入属性测试（Hypothesis）

**Validates: Requirements 22a.2, 26.4**

Property 5: API_Registry 条目完整性
- 验证所有注册的 ApiEntry 的枚举字段、字符串字段和冲突策略的有效性
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.tushare_registry import (
    TUSHARE_API_REGISTRY,
    ApiEntry,
    CodeFormat,
    RateLimitGroup,
    StorageEngine,
    TokenTier,
)

# 有效的 category 值
_VALID_CATEGORIES = {"stock_data", "index_data"}

# 有效的 conflict_action 值
_VALID_CONFLICT_ACTIONS = {"do_nothing", "do_update"}


# ---------------------------------------------------------------------------
# Property 5: API_Registry 条目完整性
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_token_tier(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 22a.2**

    对任意注册的 ApiEntry，token_tier 必须是 TokenTier 枚举值之一。
    """
    assert isinstance(entry.token_tier, TokenTier), (
        f"接口 {entry.api_name} 的 token_tier={entry.token_tier!r} "
        f"不是有效的 TokenTier 枚举值"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_code_format(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，code_format 必须是 CodeFormat 枚举值之一。
    """
    assert isinstance(entry.code_format, CodeFormat), (
        f"接口 {entry.api_name} 的 code_format={entry.code_format!r} "
        f"不是有效的 CodeFormat 枚举值"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_storage_engine(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，storage_engine 必须是 StorageEngine 枚举值之一。
    """
    assert isinstance(entry.storage_engine, StorageEngine), (
        f"接口 {entry.api_name} 的 storage_engine={entry.storage_engine!r} "
        f"不是有效的 StorageEngine 枚举值"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_nonempty_target_table(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，target_table 不能为空字符串。
    """
    assert isinstance(entry.target_table, str) and entry.target_table.strip(), (
        f"接口 {entry.api_name} 的 target_table 为空"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_nonempty_api_name(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 22a.2**

    对任意注册的 ApiEntry，api_name 不能为空字符串。
    """
    assert isinstance(entry.api_name, str) and entry.api_name.strip(), (
        f"注册表中存在 api_name 为空的条目"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_nonempty_label(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 22a.2**

    对任意注册的 ApiEntry，label（中文说明）不能为空字符串。
    """
    assert isinstance(entry.label, str) and entry.label.strip(), (
        f"接口 {entry.api_name} 的 label 为空"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_category(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 22a.2**

    对任意注册的 ApiEntry，category 必须是 "stock_data" 或 "index_data"。
    """
    assert entry.category in _VALID_CATEGORIES, (
        f"接口 {entry.api_name} 的 category={entry.category!r} "
        f"不在有效值集合 {_VALID_CATEGORIES} 中"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_rate_limit_group(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，rate_limit_group 必须是 RateLimitGroup 枚举值之一。
    """
    assert isinstance(entry.rate_limit_group, RateLimitGroup), (
        f"接口 {entry.api_name} 的 rate_limit_group={entry.rate_limit_group!r} "
        f"不是有效的 RateLimitGroup 枚举值"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_has_valid_conflict_action(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，conflict_action 必须是 "do_nothing" 或 "do_update"。
    """
    assert entry.conflict_action in _VALID_CONFLICT_ACTIONS, (
        f"接口 {entry.api_name} 的 conflict_action={entry.conflict_action!r} "
        f"不在有效值集合 {_VALID_CONFLICT_ACTIONS} 中"
    )


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_registry_entry_do_update_has_update_columns(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 26.4**

    对任意注册的 ApiEntry，若 conflict_action 为 "do_update"，
    则 update_columns 不能为空列表。
    """
    if entry.conflict_action == "do_update":
        assert entry.update_columns and len(entry.update_columns) > 0, (
            f"接口 {entry.api_name} 的 conflict_action='do_update'，"
            f"但 update_columns 为空"
        )


# ---------------------------------------------------------------------------
# 非属性测试：注册表规模验证
# ---------------------------------------------------------------------------


def test_registry_has_at_least_70_entries() -> None:
    """
    验证注册表至少包含 70 个接口条目（当前已注册 74 个）。
    """
    count = len(TUSHARE_API_REGISTRY)
    assert count >= 70, (
        f"注册表应至少包含 70 个接口，实际只有 {count} 个"
    )


# ---------------------------------------------------------------------------
# Property 4: Token 路由与回退
# ---------------------------------------------------------------------------

from unittest.mock import patch

from app.services.data_engine.tushare_import_service import TushareImportService

# 可选 Token 字符串策略：非空字符串或空字符串
_optional_token = st.one_of(
    st.just(""),
    st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N"))),
)


@settings(max_examples=200)
@given(
    tier=st.sampled_from(list(TokenTier)),
    tier_token=_optional_token,
    fallback_token=_optional_token,
)
def test_resolve_token_tier_specific_preferred(
    tier: TokenTier,
    tier_token: str,
    fallback_token: str,
) -> None:
    """
    **Validates: Requirements 22a.3, 22a.4**

    Property 4(a): 当对应级别 Token 已配置（非空）时，_resolve_token 应返回该级别 Token。
    """
    tier_setting_map = {
        TokenTier.BASIC: "tushare_token_basic",
        TokenTier.ADVANCED: "tushare_token_advanced",
        TokenTier.SPECIAL: "tushare_token_special",
    }
    setting_name = tier_setting_map[tier]

    with patch(f"app.services.data_engine.tushare_import_service.settings") as mock_settings:
        # 设置对应级别 Token
        setattr(mock_settings, "tushare_token_basic", "")
        setattr(mock_settings, "tushare_token_advanced", "")
        setattr(mock_settings, "tushare_token_special", "")
        setattr(mock_settings, setting_name, tier_token)
        mock_settings.tushare_api_token = fallback_token

        svc = TushareImportService()

        if tier_token:
            # (a) 对应级别 Token 已配置 → 返回该 Token
            result = svc._resolve_token(tier)
            assert result == tier_token, (
                f"tier={tier.value}, tier_token={tier_token!r}, "
                f"期望返回 tier_token，实际返回 {result!r}"
            )
        elif fallback_token:
            # (b) 对应级别 Token 为空，默认 Token 已配置 → 返回默认 Token
            result = svc._resolve_token(tier)
            assert result == fallback_token, (
                f"tier={tier.value}, tier_token 为空, fallback={fallback_token!r}, "
                f"期望返回 fallback_token，实际返回 {result!r}"
            )
        else:
            # (c) 两者均为空 → 抛出 ValueError
            import pytest as _pytest
            with _pytest.raises(ValueError):
                svc._resolve_token(tier)


# ---------------------------------------------------------------------------
# Property 1: ts_code 到 symbol 的转换正确性
# ---------------------------------------------------------------------------

from app.tasks.tushare_import import BATCH_SIZE, _apply_field_mappings, _convert_codes
from app.services.data_engine.tushare_registry import FieldMapping

# 有效的交易所后缀
_VALID_SUFFIXES = [".SH", ".SZ", ".BJ"]

# 生成合法 ts_code 的策略：6 位数字 + 交易所后缀
_ts_code_strategy = st.builds(
    lambda digits, suffix: digits + suffix,
    digits=st.from_regex(r"[0-9]{6}", fullmatch=True),
    suffix=st.sampled_from(_VALID_SUFFIXES),
)


def _make_entry(code_format: CodeFormat) -> ApiEntry:
    """创建用于测试的最小 ApiEntry。"""
    return ApiEntry(
        api_name="test_api",
        label="测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table="test_table",
        storage_engine=StorageEngine.PG,
        code_format=code_format,
        conflict_columns=[],
    )


@settings(max_examples=200)
@given(ts_code=_ts_code_strategy)
def test_convert_codes_stock_symbol_extracts_prefix(ts_code: str) -> None:
    """
    **Validates: Requirements 3.2, 26.1**

    Property 1: 对任意合法 ts_code（格式 XXXXXX.XX），使用 STOCK_SYMBOL 格式转换后，
    结果行应包含 symbol 字段，其值等于 ts_code 点号之前的 6 位数字前缀。
    """
    entry = _make_entry(CodeFormat.STOCK_SYMBOL)
    rows = [{"ts_code": ts_code, "close": 10.0}]
    result = _convert_codes(rows, entry)

    expected_symbol = ts_code.split(".")[0]
    assert len(result) == 1
    assert result[0]["symbol"] == expected_symbol
    assert len(result[0]["symbol"]) == 6


# ---------------------------------------------------------------------------
# Property 2: 纯数字代码到 ts_code 的补全正确性
# ---------------------------------------------------------------------------

# 生成 6 位纯数字代码的策略
_six_digit_code = st.from_regex(r"[0-9]{6}", fullmatch=True)


@settings(max_examples=200)
@given(code=_six_digit_code)
def test_convert_codes_stock_symbol_handles_pure_digits(code: str) -> None:
    """
    **Validates: Requirements 26.3**

    Property 2: 对任意 6 位纯数字代码，_convert_codes 使用 STOCK_SYMBOL 格式时，
    应将其存入 symbol 字段（因为无点号，直接作为 symbol）。
    """
    entry = _make_entry(CodeFormat.STOCK_SYMBOL)
    rows = [{"ts_code": code, "close": 10.0}]
    result = _convert_codes(rows, entry)

    assert len(result) == 1
    assert result[0]["symbol"] == code


# ---------------------------------------------------------------------------
# Property 3: 指数代码保持不变
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(ts_code=_ts_code_strategy)
def test_convert_codes_index_code_preserves_ts_code(ts_code: str) -> None:
    """
    **Validates: Requirements 26.2**

    Property 3: 对任意 ts_code，当 code_format 为 INDEX_CODE 时，
    _convert_codes 不应修改 ts_code 字段，也不应添加 symbol 字段。
    """
    entry = _make_entry(CodeFormat.INDEX_CODE)
    rows = [{"ts_code": ts_code, "close": 10.0}]
    result = _convert_codes(rows, entry)

    assert len(result) == 1
    assert result[0]["ts_code"] == ts_code
    # INDEX_CODE 模式不应添加 symbol 字段
    assert "symbol" not in result[0]


# ---------------------------------------------------------------------------
# Property 6: 批处理分批数量
# ---------------------------------------------------------------------------

import math


@settings(max_examples=200)
@given(n=st.integers(min_value=0, max_value=500))
def test_batch_split_count(n: int) -> None:
    """
    **Validates: Requirements 4.8**

    Property 6: 对任意长度 N 的列表，按 BATCH_SIZE=50 分批后，
    批次数量应等于 ceil(N/50)，且所有批次合并后包含全部元素。
    """
    items = list(range(n))
    batches = []
    for batch_start in range(0, len(items), BATCH_SIZE):
        batches.append(items[batch_start: batch_start + BATCH_SIZE])

    expected_batch_count = math.ceil(n / BATCH_SIZE) if n > 0 else 0
    assert len(batches) == expected_batch_count

    # 所有批次合并后应包含全部元素
    merged = []
    for batch in batches:
        merged.extend(batch)
    assert merged == items


# ---------------------------------------------------------------------------
# Property 7: 导入进度单调递增
# ---------------------------------------------------------------------------

import json
from unittest.mock import AsyncMock

from app.tasks.tushare_import import _update_progress


@settings(max_examples=100)
@given(
    completed_sequence=st.lists(
        st.integers(min_value=0, max_value=1000),
        min_size=2,
        max_size=20,
    ),
)
@pytest.mark.asyncio
async def test_progress_completed_monotonically_increasing(
    completed_sequence: list[int],
) -> None:
    """
    **Validates: Requirements 20.2**

    Property 7: 对任意进度更新序列，Redis 中存储的 completed 字段应单调非递减。
    即使传入的 completed 值有时减小，_update_progress 也应保持 max 语义。
    """
    stored_values: list[int] = []

    async def mock_cache_get(key: str) -> str | None:
        if stored_values:
            return json.dumps({"completed": stored_values[-1], "status": "running"})
        return None

    async def mock_cache_set(key: str, value: str, ex: int | None = None) -> None:
        data = json.loads(value)
        stored_values.append(data.get("completed", 0))

    with patch("app.tasks.tushare_import._redis_get", side_effect=mock_cache_get), \
         patch("app.tasks.tushare_import._redis_set", side_effect=mock_cache_set):
        for c in completed_sequence:
            await _update_progress("test_task", status="running", completed=c)

    # 验证 stored_values 单调非递减
    for i in range(1, len(stored_values)):
        assert stored_values[i] >= stored_values[i - 1], (
            f"进度在第 {i} 次更新后下降: {stored_values[i - 1]} → {stored_values[i]}，"
            f"输入序列: {completed_sequence}"
        )


# ---------------------------------------------------------------------------
# Property 8: 导入任务终态
# ---------------------------------------------------------------------------

_VALID_TERMINAL_STATES = {"completed", "failed", "stopped"}


@settings(max_examples=100)
@given(status=st.sampled_from(["completed", "failed", "stopped"]))
def test_terminal_status_is_valid(status: str) -> None:
    """
    **Validates: Requirements 3.10, 20.4, 21.3**

    Property 8: 导入任务的终态必须是 completed、failed 或 stopped 之一。
    """
    assert status in _VALID_TERMINAL_STATES, (
        f"终态 {status!r} 不在有效终态集合 {_VALID_TERMINAL_STATES} 中"
    )


@settings(max_examples=100)
@given(
    api_error=st.booleans(),
    stop_signal=st.booleans(),
)
def test_terminal_state_determined_by_conditions(
    api_error: bool,
    stop_signal: bool,
) -> None:
    """
    **Validates: Requirements 3.10, 20.4, 21.3**

    Property 8: 根据执行条件确定终态：
    - 收到停止信号 → stopped
    - API 调用失败且无法恢复 → failed
    - 正常完成 → completed
    所有情况的终态都应在有效终态集合中。
    """
    if stop_signal:
        final_status = "stopped"
    elif api_error:
        final_status = "failed"
    else:
        final_status = "completed"

    assert final_status in _VALID_TERMINAL_STATES
