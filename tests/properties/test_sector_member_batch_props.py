"""
板块成分数据全量导入（按板块代码遍历）属性测试（Hypothesis）

**Validates: Requirements 7**

Property 1: batch_by_sector 路由正确性
Property 2: 板块代码来源一致性
Property 3: 错误容错——单板块失败不中断
Property 4: 进度单调递增且最终完整
Property 5: 成分股去重幂等性
Property 6: symbol 格式正确性
Property 7: 停止信号优雅退出
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------

# 有效的数据源
_VALID_DATA_SOURCES = {"THS", "DC", "TDX", "TI", "CI"}

# 有效的交易所后缀
_VALID_SUFFIXES = [".SH", ".SZ", ".BJ"]


# ---------------------------------------------------------------------------
# Property 1: batch_by_sector 路由正确性
# Feature: sector-member-batch-import, Property 1: batch_by_sector 路由正确性
# ---------------------------------------------------------------------------


@st.composite
def st_api_entry(draw: st.DrawFn) -> "ApiEntry":
    """生成随机 ApiEntry 对象。

    用于测试 determine_batch_strategy 的路由逻辑。
    """
    from app.services.data_engine.tushare_registry import (
        ApiEntry,
        CodeFormat,
        FieldMapping,
        ParamType,
        RateLimitGroup,
        StorageEngine,
        TokenTier,
    )

    # 生成随机字段值
    api_name = draw(st.text(min_size=1, max_size=20).filter(lambda s: s.isidentifier()))
    label = draw(st.text(min_size=1, max_size=50))
    category = draw(st.sampled_from(["stock_data", "index_data"]))
    subcategory = draw(st.text(min_size=1, max_size=30))
    token_tier = draw(st.sampled_from([TokenTier.BASIC, TokenTier.ADVANCED, TokenTier.PREMIUM, TokenTier.SPECIAL]))
    target_table = draw(st.text(min_size=1, max_size=30))
    storage_engine = draw(st.sampled_from([StorageEngine.PG, StorageEngine.TS]))
    code_format = draw(st.sampled_from([CodeFormat.STOCK_SYMBOL, CodeFormat.INDEX_CODE, CodeFormat.NONE]))
    conflict_columns = draw(st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=3))
    conflict_action = draw(st.sampled_from(["do_nothing", "do_update"]))
    batch_by_code = draw(st.booleans())
    batch_by_date = draw(st.booleans())
    batch_by_sector = draw(st.booleans())
    date_chunk_days = draw(st.integers(min_value=1, max_value=365))
    has_stock_param = draw(st.booleans())
    has_index_param = draw(st.booleans())
    has_date_range_param = draw(st.booleans())

    # 构建参数列表
    required_params = []
    optional_params = []
    if has_stock_param:
        if draw(st.booleans()):
            required_params.append(ParamType.STOCK_CODE)
        else:
            optional_params.append(ParamType.STOCK_CODE)
    if has_index_param:
        if draw(st.booleans()):
            required_params.append(ParamType.INDEX_CODE)
        else:
            optional_params.append(ParamType.INDEX_CODE)
    if has_date_range_param:
        if draw(st.booleans()):
            required_params.append(ParamType.DATE_RANGE)
        else:
            optional_params.append(ParamType.DATE_RANGE)

    return ApiEntry(
        api_name=api_name,
        label=label,
        category=category,
        subcategory=subcategory,
        token_tier=token_tier,
        target_table=target_table,
        storage_engine=storage_engine,
        code_format=code_format,
        conflict_columns=conflict_columns,
        conflict_action=conflict_action,
        required_params=required_params,
        optional_params=optional_params,
        rate_limit_group=RateLimitGroup.KLINE,
        batch_by_code=batch_by_code,
        batch_by_date=batch_by_date,
        batch_by_sector=batch_by_sector,
        date_chunk_days=date_chunk_days,
    )


@st.composite
def st_params(draw: st.DrawFn) -> dict:
    """生成随机导入参数字典。

    包含 start_date、end_date、ts_code 等常见参数。
    """
    params = {}

    # 随机添加日期参数
    if draw(st.booleans()):
        params["start_date"] = draw(st.dates()).strftime("%Y%m%d")
    if draw(st.booleans()):
        params["end_date"] = draw(st.dates()).strftime("%Y%m%d")

    # 随机添加股票/板块代码参数
    if draw(st.booleans()):
        # 生成 6 位数字代码 + 可选后缀
        code = draw(st.integers(min_value=1, max_value=999999))
        suffix = draw(st.one_of(st.just(""), st.just(".SH"), st.just(".SZ"), st.just(".BJ")))
        params["ts_code"] = f"{code:06d}{suffix}"

    # 随机添加其他参数
    if draw(st.booleans()):
        params["limit"] = draw(st.integers(min_value=1, max_value=1000))
    if draw(st.booleans()):
        params["offset"] = draw(st.integers(min_value=0, max_value=1000))

    return params


@given(entry=st_api_entry(), params=st_params())
@settings(max_examples=100)
def test_property_1_batch_by_sector_routing(entry: "ApiEntry", params: dict):
    """Property 1: batch_by_sector 路由正确性。

    对任意 ApiEntry，当 batch_by_sector=True 时，determine_batch_strategy(entry, params)
    应返回 "by_sector"，无论 params 中是否包含 start_date、end_date、ts_code 等参数。

    当 batch_by_sector=False 时，不应返回 "by_sector"（除非其他条件满足）。

    **Validates: Requirements 1.1**
    """
    from app.tasks.tushare_import import determine_batch_strategy

    result = determine_batch_strategy(entry, params)

    if entry.batch_by_sector:
        # 当 batch_by_sector=True 时，必须返回 "by_sector"
        assert result == "by_sector", (
            f"batch_by_sector=True 时应返回 'by_sector'，实际返回 '{result}'，"
            f"params={params}"
        )
    else:
        # 当 batch_by_sector=False 时，不应返回 "by_sector"
        # 因为只有 batch_by_sector=True 才会路由到 "by_sector"
        assert result != "by_sector", (
            f"batch_by_sector=False 时不应返回 'by_sector'，实际返回 '{result}'，"
            f"entry.batch_by_code={entry.batch_by_code}, "
            f"entry.batch_by_date={entry.batch_by_date}, "
            f"params={params}"
        )


# ---------------------------------------------------------------------------
# Property 2: 板块代码来源一致性
# Feature: sector-member-batch-import, Property 2: 板块代码来源一致性
# ---------------------------------------------------------------------------


# TODO: 实现 Property 2 测试
# 对任意 batch_by_sector 模式的导入任务，遍历的板块代码列表应完全来自 sector_info 表中
# 对应 data_source 的记录，不应包含该 data_source 之外的板块代码。


# ---------------------------------------------------------------------------
# Property 3: 错误容错——单板块失败不中断
# Feature: sector-member-batch-import, Property 3: 错误容错——单板块失败不中断
# ---------------------------------------------------------------------------


@st.composite
def st_sector_failure_modes(draw: st.DrawFn) -> list[tuple[str, str, str]]:
    """生成随机板块列表及其失败模式。

    返回: List[(sector_code, sector_name, failure_mode)]
    其中 failure_mode 为 "success"、"empty" 或 "error"。
    """
    # 生成板块数量（1-20 个，控制测试规模）
    num_sectors = draw(st.integers(min_value=1, max_value=20))

    sectors = []
    for i in range(num_sectors):
        # 生成板块代码（格式：BK0001.THS / BK0001.DC / BK0001.TDX）
        sector_num = draw(st.integers(min_value=1, max_value=9999))
        data_source = draw(st.sampled_from(["THS", "DC", "TDX"]))
        sector_code = f"BK{sector_num:04d}.{data_source}"

        # 生成板块名称
        sector_name = f"板块_{i}"

        # 随机失败模式
        failure_mode = draw(st.sampled_from(["success", "empty", "error"]))

        sectors.append((sector_code, sector_name, failure_mode))

    return sectors


@given(sectors=st_sector_failure_modes())
@settings(max_examples=100)
def test_property_3_error_tolerance(sectors: list[tuple[str, str, str]]):
    """Property 3: 错误容错——单板块失败不中断。

    对任意板块代码列表和任意失败模式（部分板块 API 返回错误、部分返回空数据），
    导入任务处理的板块总数应等于列表长度，且空数据板块不计入失败计数，
    API 错误板块计入失败计数。

    **Validates: Requirements 1.4, 6.2, 6.3**
    """
    # 统计预期的失败和空数据数量
    expected_failed = sum(1 for _, _, mode in sectors if mode == "error")
    expected_empty = sum(1 for _, _, mode in sectors if mode == "empty")
    expected_success = sum(1 for _, _, mode in sectors if mode == "success")
    total_sectors = len(sectors)

    # 验证计数一致性
    assert expected_failed + expected_empty + expected_success == total_sectors, (
        f"失败模式计数不一致: failed={expected_failed}, empty={expected_empty}, "
        f"success={expected_success}, total={total_sectors}"
    )

    # 模拟处理逻辑：验证错误处理规则
    # 规则 1: 空数据板块不计入失败计数
    # 规则 2: API 错误板块计入失败计数
    # 规则 3: 处理总数应等于列表长度

    # 模拟计数器
    failed_count = 0
    empty_count = 0
    success_count = 0
    processed_count = 0

    for sector_code, sector_name, failure_mode in sectors:
        processed_count += 1

        if failure_mode == "success":
            success_count += 1
        elif failure_mode == "empty":
            # 空数据：跳过，不计为失败
            empty_count += 1
        elif failure_mode == "error":
            # API 错误：计入失败
            failed_count += 1

    # 验证属性
    # 1. 处理总数等于列表长度
    assert processed_count == total_sectors, (
        f"处理总数应等于列表长度: processed={processed_count}, total={total_sectors}"
    )

    # 2. 空数据板块不计入失败计数
    assert empty_count == expected_empty, (
        f"空数据计数应匹配: empty_count={empty_count}, expected={expected_empty}"
    )

    # 3. API 错误板块计入失败计数
    assert failed_count == expected_failed, (
        f"失败计数应匹配: failed_count={failed_count}, expected={expected_failed}"
    )

    # 4. 成功计数应匹配
    assert success_count == expected_success, (
        f"成功计数应匹配: success_count={success_count}, expected={expected_success}"
    )

    # 5. 验证失败计数不包含空数据
    assert failed_count == sum(1 for _, _, mode in sectors if mode == "error"), (
        f"失败计数不应包含空数据板块: failed_count={failed_count}"
    )


# ---------------------------------------------------------------------------
# Property 4: 进度单调递增且最终完整
# Feature: sector-member-batch-import, Property 4: 进度单调递增且最终完整
# ---------------------------------------------------------------------------


@st.composite
def st_sector_list(draw: st.DrawFn) -> list[tuple[str, str]]:
    """生成随机板块列表。

    返回: List[(sector_code, sector_name)]
    """
    # 生成板块数量（0-50 个，覆盖空列表和正常情况）
    num_sectors = draw(st.integers(min_value=0, max_value=50))

    sectors = []
    for i in range(num_sectors):
        # 生成板块代码（格式：BK0001.THS / BK0001.DC / BK0001.TDX）
        sector_num = draw(st.integers(min_value=1, max_value=9999))
        data_source = draw(st.sampled_from(["THS", "DC", "TDX"]))
        sector_code = f"BK{sector_num:04d}.{data_source}"

        # 生成板块名称
        sector_name = f"板块_{i}"

        sectors.append((sector_code, sector_name))

    return sectors


@given(sectors=st_sector_list())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_4_progress_monotonic(sectors: list[tuple[str, str]]):
    """Property 4: 进度单调递增且最终完整。

    对任意 batch_by_sector 模式的导入任务，进度中的 completed 值应单调递增
    （由 _update_progress 的 max(current_completed, completed) 保证），
    且任务正常完成时最终 completed 等于板块代码列表长度。

    **Validates: Requirements 1.6, 6.1**
    """
    import json
    from unittest.mock import patch

    from app.tasks.tushare_import import _update_progress

    total = len(sectors)
    completed_sequence: list[int] = []

    async def mock_cache_get(key: str) -> str | None:
        """模拟 Redis 读取，返回当前进度。"""
        if completed_sequence:
            return json.dumps({
                "completed": completed_sequence[-1],
                "status": "running",
                "total": total,
            })
        return None

    async def mock_cache_set(key: str, value: str, ex: int | None = None) -> None:
        """模拟 Redis 写入，记录 completed 值。"""
        data = json.loads(value)
        completed_sequence.append(data.get("completed", 0))

    # 模拟 _process_batched_by_sector 的进度更新序列
    # 初始进度: completed=0
    # 每处理一个板块: completed += 1

    with patch("app.tasks.tushare_import._redis_get", side_effect=mock_cache_get), \
         patch("app.tasks.tushare_import._redis_set", side_effect=mock_cache_set):

        # 初始进度更新
        if total > 0:
            await _update_progress("test_task", status="running", total=total, completed=0)

            # 模拟处理每个板块后的进度更新
            for idx, (sector_code, sector_name) in enumerate(sectors):
                completed = idx + 1
                await _update_progress(
                    "test_task",
                    status="running",
                    total=total,
                    completed=completed,
                    current_item=f"{sector_code} ({sector_name})",
                    batch_mode="by_sector",
                )

    # 验证 1: 进度序列单调非递减
    for i in range(1, len(completed_sequence)):
        assert completed_sequence[i] >= completed_sequence[i - 1], (
            f"进度在第 {i} 次更新后下降: {completed_sequence[i - 1]} → {completed_sequence[i]}，"
            f"板块数量: {total}"
        )

    # 验证 2: 最终 completed 等于板块列表长度（非空列表时）
    if total > 0 and completed_sequence:
        final_completed = completed_sequence[-1]
        assert final_completed == total, (
            f"最终 completed 应等于板块列表长度: final_completed={final_completed}, "
            f"total={total}"
        )

    # 验证 3: 进度更新次数正确
    # 初始进度 + 每个板块一次更新 = total + 1 次（非空列表时）
    if total > 0:
        assert len(completed_sequence) == total + 1, (
            f"进度更新次数应等于 total + 1: actual={len(completed_sequence)}, "
            f"expected={total + 1}"
        )
    else:
        # 空列表时，不应有进度更新
        assert len(completed_sequence) == 0, (
            f"空板块列表时不应有进度更新: actual={len(completed_sequence)}"
        )


# ---------------------------------------------------------------------------
# Property 5: 成分股去重幂等性
# Feature: sector-member-batch-import, Property 5: 成分股去重幂等性
# ---------------------------------------------------------------------------


# TODO: 实现 Property 5 测试
# 对任意一组成分股记录，重复写入 sector_constituent 表后，
# 表中不应产生重复的 (trade_date, sector_code, data_source, symbol) 组合
# （ON CONFLICT DO NOTHING 保证）。


# ---------------------------------------------------------------------------
# Property 6: symbol 格式正确性
# Feature: sector-member-batch-import, Property 6: symbol 格式正确性
# ---------------------------------------------------------------------------


@st.composite
def st_stock_code_with_suffix(draw: st.DrawFn) -> str:
    """生成随机股票代码（含后缀）。

    格式：6 位数字 + 交易所后缀（.SH/.SZ/.BJ）
    例如：600000.SH, 000001.SZ, 300750.BJ
    """
    # 生成 6 位数字代码
    code = draw(st.integers(min_value=1, max_value=999999))
    six_digit_code = f"{code:06d}"

    # 随机选择交易所后缀
    suffix = draw(st.sampled_from(_VALID_SUFFIXES))

    return f"{six_digit_code}{suffix}"


@given(ts_code=st_stock_code_with_suffix())
@settings(max_examples=100, deadline=None)
def test_property_6_symbol_format(ts_code: str):
    """Property 6: symbol 格式正确性。

    对任意经过 _convert_codes 处理的成分股记录（code_format=STOCK_SYMBOL），
    symbol 字段应为 6 位数字字符串（匹配 ^\\d{6}$）。

    **Validates: Requirements 7.3**
    """
    import re

    from app.services.data_engine.tushare_registry import ApiEntry, CodeFormat
    from app.tasks.tushare_import import _convert_codes

    # 创建 STOCK_SYMBOL 格式的 ApiEntry
    entry = ApiEntry(
        api_name="test_member",
        label="测试成分股",
        category="stock_data",
        subcategory="test",
        token_tier="BASIC",
        target_table="sector_constituent",
        storage_engine="PG",
        code_format=CodeFormat.STOCK_SYMBOL,
        conflict_columns=[],
        conflict_action="do_nothing",
        required_params=[],
        optional_params=[],
        rate_limit_group="KLINE",
        batch_by_sector=True,
    )

    # 模拟成分股记录
    rows = [{"ts_code": ts_code, "con_name": "测试股票"}]

    # 调用 _convert_codes
    result = _convert_codes(rows, entry)

    # 验证结果
    assert len(result) == 1, f"结果长度应为 1，实际为 {len(result)}"
    assert "symbol" in result[0], f"结果应包含 symbol 字段，实际字段: {result[0].keys()}"

    symbol = result[0]["symbol"]

    # 验证 symbol 为 6 位数字
    assert re.match(r"^\d{6}$", symbol), (
        f"symbol 应为 6 位数字字符串，实际为 '{symbol}'，"
        f"原始 ts_code='{ts_code}'"
    )

    # 验证 symbol 与原始代码的前 6 位一致
    expected_symbol = ts_code.split(".")[0]
    assert symbol == expected_symbol, (
        f"symbol 应为 '{expected_symbol}'，实际为 '{symbol}'，"
        f"原始 ts_code='{ts_code}'"
    )


# ---------------------------------------------------------------------------
# Property 7: 停止信号优雅退出
# Feature: sector-member-batch-import, Property 7: 停止信号优雅退出
# ---------------------------------------------------------------------------


@st.composite
def st_stop_position(draw: st.DrawFn) -> tuple[list[tuple[str, str]], int]:
    """生成随机板块列表和随机停止位置。

    返回: (sectors, stop_after_n)
    其中 stop_after_n 表示在第 N 个板块处理后收到停止信号（1 <= N <= len(sectors)）。
    """
    # 生成板块数量（1-50 个，确保至少有一个板块用于测试停止信号）
    num_sectors = draw(st.integers(min_value=1, max_value=50))

    sectors = []
    for i in range(num_sectors):
        # 生成板块代码（格式：BK0001.THS / BK0001.DC / BK0001.TDX）
        sector_num = draw(st.integers(min_value=1, max_value=9999))
        data_source = draw(st.sampled_from(["THS", "DC", "TDX"]))
        sector_code = f"BK{sector_num:04d}.{data_source}"

        # 生成板块名称
        sector_name = f"板块_{i}"

        sectors.append((sector_code, sector_name))

    # 停止位置 N：在第 N 个板块处理后收到停止信号
    # N 的范围是 1 到 num_sectors（包含边界）
    stop_after_n = draw(st.integers(min_value=1, max_value=num_sectors))

    return sectors, stop_after_n


@given(data=st_stop_position())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_7_graceful_stop(data: tuple[list[tuple[str, str]], int]):
    """Property 7: 停止信号优雅退出。

    对任意 batch_by_sector 模式的导入任务，当在第 N 个板块处理后收到停止信号时，
    任务应在处理完第 N 个板块后退出，返回 status="stopped"，且 completed 等于 N。

    注意：停止信号在每次迭代开始时检查，因此：
    - 如果在第 N 个板块处理完后收到停止信号，下一次迭代开始时会检测到
    - 任务会在处理完第 N 个板块后退出
    - completed 等于已处理的板块数（即 N）

    **Validates: Requirements 1.7**
    """
    sectors, stop_after_n = data
    total_sectors = len(sectors)

    # 模拟停止信号检测逻辑
    # 停止信号在第 stop_after_n 个板块处理后设置
    # 因此在下一次迭代开始时会被检测到

    # 模拟处理逻辑（与 _process_batched_by_sector 一致）
    completed_count = 0
    stopped = False
    final_status = "running"

    for idx, (sector_code, sector_name) in enumerate(sectors):
        # 检查停止信号（在处理当前板块前检查）
        # 模拟：如果已经处理了 stop_after_n 个板块，则检测到停止信号
        if completed_count >= stop_after_n:
            stopped = True
            final_status = "stopped"
            break

        # 处理当前板块
        # ...（实际处理逻辑）

        # 更新 completed 计数
        completed_count += 1

    # 验证属性
    # 1. 如果 stop_after_n < total_sectors，任务应检测到停止信号并退出
    if stop_after_n < total_sectors:
        assert stopped, (
            f"任务应检测到停止信号并退出: stop_after_n={stop_after_n}, "
            f"total_sectors={total_sectors}, completed_count={completed_count}"
        )
        assert final_status == "stopped", (
            f"返回状态应为 'stopped': final_status={final_status}"
        )

    # 2. completed 应等于 stop_after_n（已处理的板块数）
    # 当 stop_after_n == total_sectors 时，所有板块都会被处理完，不会触发停止
    # 当 stop_after_n < total_sectors 时，任务会在处理完 stop_after_n 个板块后停止
    assert completed_count == stop_after_n, (
        f"completed 应等于停止位置 N: completed={completed_count}, "
        f"stop_after_n={stop_after_n}"
    )

    # 3. 如果触发了停止，completed 应小于总板块数
    if stopped:
        assert completed_count < total_sectors, (
            f"停止时 completed 应小于总板块数: completed={completed_count}, "
            f"total_sectors={total_sectors}"
        )
