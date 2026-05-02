"""
Tushare 日期分批路由和处理的单元测试

覆盖：
- determine_batch_strategy 纯函数路由测试
  - batch_by_date=True + 日期参数 → "by_date"
  - 兜底路由：未声明 batch_by_date 但有 DATE_RANGE → "by_date_fallback" + WARNING
  - 双重分批：batch_by_code + batch_by_date → "by_code_and_date"
- _process_batched_by_date 集成测试
  - use_trade_date_loop 参数转换：start_date → trade_date, end_date 移除

对应需求：3.1, 4.1, 4.2, 4.3
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_adapter import TushareAPIError
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
# 辅助：创建测试用 ApiEntry
# ---------------------------------------------------------------------------

def _make_entry(
    api_name: str = "test_api",
    batch_by_code: bool = False,
    batch_by_date: bool = False,
    date_chunk_days: int = 30,
    required_params: list[ParamType] | None = None,
    optional_params: list[ParamType] | None = None,
    extra_config: dict | None = None,
    code_format: CodeFormat = CodeFormat.NONE,
    storage_engine: StorageEngine = StorageEngine.PG,
) -> ApiEntry:
    """创建用于测试的最小 ApiEntry。"""
    return ApiEntry(
        api_name=api_name,
        label="测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table="test_table",
        storage_engine=storage_engine,
        code_format=code_format,
        conflict_columns=[],
        required_params=required_params or [],
        optional_params=optional_params or [],
        batch_by_code=batch_by_code,
        batch_by_date=batch_by_date,
        date_chunk_days=date_chunk_days,
        extra_config=extra_config or {},
    )


# ---------------------------------------------------------------------------
# determine_batch_strategy 路由测试
# ---------------------------------------------------------------------------


class TestDetermineBatchStrategy:
    """分批策略路由纯函数测试。"""

    def test_date_batch_routing(self):
        """batch_by_date=True + 日期参数 → "by_date"（需求 4.1 优先级 3）"""
        entry = _make_entry(
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_date"

    def test_date_batch_without_date_params_falls_to_single(self):
        """batch_by_date=True 但无日期参数 → single"""
        entry = _make_entry(
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE],
        )
        params = {}

        result = determine_batch_strategy(entry, params)

        assert result == "single"

    def test_date_batch_with_only_start_date_falls_to_single(self):
        """batch_by_date=True 但只有 start_date → single（需要两个日期参数）"""
        entry = _make_entry(
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE],
        )
        params = {"start_date": "20230101"}

        result = determine_batch_strategy(entry, params)

        assert result == "single"

    def test_fallback_routing_undeclared_batch_by_date(self):
        """未声明 batch_by_date 但有 DATE_RANGE 参数 + 日期范围 → by_date_fallback（需求 4.2）"""
        entry = _make_entry(
            batch_by_date=False,
            required_params=[ParamType.DATE_RANGE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_date_fallback"

    def test_fallback_routing_optional_date_range(self):
        """未声明 batch_by_date 但 optional_params 有 DATE_RANGE + 日期范围 → by_date_fallback"""
        entry = _make_entry(
            batch_by_date=False,
            optional_params=[ParamType.DATE_RANGE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_date_fallback"

    def test_no_date_range_param_no_fallback(self):
        """无 DATE_RANGE 参数声明 + 日期参数 → single（不触发兜底）"""
        entry = _make_entry(
            batch_by_date=False,
            required_params=[],
            optional_params=[],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "single"

    def test_dual_batch_code_and_date(self):
        """batch_by_code + batch_by_date + 日期参数 → by_code_and_date（需求 4.1 优先级 1 双重分批）"""
        entry = _make_entry(
            batch_by_code=True,
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_code_and_date"

    def test_code_batch_without_date(self):
        """batch_by_code=True 但无日期参数 → by_code（非双重分批）"""
        entry = _make_entry(
            batch_by_code=True,
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE],
        )
        params = {}

        result = determine_batch_strategy(entry, params)

        assert result == "by_code"

    def test_code_batch_only(self):
        """batch_by_code=True + batch_by_date=False → by_code"""
        entry = _make_entry(
            batch_by_code=True,
            batch_by_date=False,
            required_params=[ParamType.STOCK_CODE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_code"

    def test_index_routing(self):
        """INDEX_CODE 参数 + 未指定 ts_code → by_index（需求 4.1 优先级 2）"""
        entry = _make_entry(
            optional_params=[ParamType.INDEX_CODE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_index"

    def test_index_routing_with_ts_code_skips_index(self):
        """INDEX_CODE 参数 + 已指定 ts_code → 不走 by_index"""
        entry = _make_entry(
            optional_params=[ParamType.INDEX_CODE],
        )
        params = {"ts_code": "000001.SH", "start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        # 有 ts_code 时跳过 index 路由，无 batch_by_date 声明但有 DATE_RANGE 不在参数中 → single
        assert result == "single"

    def test_single_no_batch_no_date(self):
        """无任何分批标记且无日期参数 → single（需求 4.1 优先级 5）"""
        entry = _make_entry()
        params = {}

        result = determine_batch_strategy(entry, params)

        assert result == "single"

    def test_priority_code_over_date(self):
        """batch_by_code 优先级高于 batch_by_date（代码分批优先）"""
        entry = _make_entry(
            batch_by_code=True,
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        # 应该是双重分批（代码外层 + 日期内层），而非纯日期分批
        assert result == "by_code_and_date"

    def test_auto_batch_code_for_stock_param_without_ts_code(self):
        """接口有 STOCK_CODE 参数但用户未传 ts_code → 自动按代码分批"""
        entry = _make_entry(
            batch_by_code=False,
            optional_params=[ParamType.STOCK_CODE],
        )
        params = {"start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_code"

    def test_stock_param_with_ts_code_no_auto_batch(self):
        """接口有 STOCK_CODE 参数且用户传了 ts_code → 不自动按代码分批"""
        entry = _make_entry(
            batch_by_code=False,
            batch_by_date=True,
            optional_params=[ParamType.STOCK_CODE],
            required_params=[ParamType.DATE_RANGE],
        )
        params = {"ts_code": "600000.SH", "start_date": "20230101", "end_date": "20231231"}

        result = determine_batch_strategy(entry, params)

        assert result == "by_date"


# ---------------------------------------------------------------------------
# 兜底路由 WARNING 日志测试（集成级别）
# ---------------------------------------------------------------------------


class TestFallbackRoutingWarning:
    """兜底日期分批路由应记录 WARNING 日志。"""

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(self, caplog):
        """未声明 batch_by_date 但触发兜底分批时，_process_import 应记录 WARNING（需求 4.2）"""
        from app.tasks.tushare_import import _process_import

        entry = _make_entry(
            api_name="undeclared_api",
            batch_by_date=False,
            required_params=[ParamType.DATE_RANGE],
        )

        # mock get_entry 返回我们的测试 entry
        with patch("app.tasks.tushare_import.get_entry", return_value=entry), \
             patch("app.tasks.tushare_import.TushareAdapter") as mock_adapter_cls, \
             patch("app.tasks.tushare_import._process_batched_by_date", new_callable=AsyncMock) as mock_pbd, \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._finalize_log", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._redis_delete", new_callable=AsyncMock):

            mock_adapter_cls.return_value.close = AsyncMock()
            mock_pbd.return_value = {"status": "completed", "record_count": 100}

            with caplog.at_level(logging.WARNING):
                result = await _process_import(
                    api_name="undeclared_api",
                    params={"start_date": "20230101", "end_date": "20230301"},
                    token="test_token",
                    log_id=1,
                    task_id="task_fallback",
                )

            assert result["status"] == "completed"
            # 验证 WARNING 日志包含关键信息
            assert "undeclared_api" in caplog.text
            assert "batch_by_date" in caplog.text

            # 验证确实调用了 _process_batched_by_date
            mock_pbd.assert_called_once()


# ---------------------------------------------------------------------------
# 双重分批集成测试
# ---------------------------------------------------------------------------


class TestDualBatchIntegration:
    """双重分批（代码外层 + 日期内层）集成测试。"""

    @pytest.mark.asyncio
    async def test_dual_batch_calls_api_per_code_and_date_chunk(self):
        """batch_by_code + batch_by_date → 对每个 ts_code 的每个日期子区间调用 API（需求 4.1, 4.3）"""
        from app.tasks.tushare_import import _process_batched

        entry = _make_entry(
            api_name="stk_mins",
            batch_by_code=True,
            batch_by_date=True,
            date_chunk_days=10,
            code_format=CodeFormat.STOCK_SYMBOL,
            required_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
        )

        adapter = MagicMock()
        # 模拟 API 返回数据
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": [["600000.SH", "20230101", 10.5]],
        })

        stock_list = ["600000.SH", "000001.SZ"]
        params = {"start_date": "20230101", "end_date": "20230120"}

        with patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=stock_list), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched(
                entry, adapter, params, "task_dual", 1, 0.0,
            )

        assert result["status"] == "completed"
        assert result["record_count"] > 0

        # 20230101-20230120 按 10 天步长 → 2 个子区间
        # 2 个股票 × 2 个子区间 = 4 次 API 调用
        assert adapter._call_api.call_count == 4

        # 验证调用参数包含 ts_code 和日期子区间
        call_args_list = adapter._call_api.call_args_list
        # 第一次调用：600000.SH + 第一个子区间
        first_call_kwargs = call_args_list[0][1]
        assert first_call_kwargs["ts_code"] == "600000.SH"
        assert first_call_kwargs["start_date"] == "20230101"
        assert first_call_kwargs["end_date"] == "20230110"


# ---------------------------------------------------------------------------
# use_trade_date_loop 参数转换测试
# ---------------------------------------------------------------------------


class TestUseTradeDateLoop:
    """use_trade_date_loop 参数转换测试。"""

    @pytest.mark.asyncio
    async def test_trade_date_loop_converts_params(self):
        """use_trade_date_loop=True 时，start_date → trade_date，end_date 被移除（需求 4.3）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="top_list",
            batch_by_date=True,
            date_chunk_days=1,
            required_params=[ParamType.DATE_RANGE],
            extra_config={"use_trade_date_loop": True},
        )

        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["trade_date", "ts_code", "name"],
            "items": [["20230101", "600000.SH", "测试"]],
        })

        params = {"start_date": "20230101", "end_date": "20230103"}

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry, adapter, params, "task_trade_date", 1, 0.0,
            )

        assert result["status"] == "completed"

        # date_chunk_days=1 + 3 天范围 → 3 个子区间（逐日调用）
        assert adapter._call_api.call_count == 3

        # 验证每次调用参数：应有 trade_date，不应有 start_date/end_date
        for call in adapter._call_api.call_args_list:
            call_kwargs = call[1]
            assert "trade_date" in call_kwargs, "应包含 trade_date 参数"
            assert "start_date" not in call_kwargs, "不应包含 start_date 参数"
            assert "end_date" not in call_kwargs, "不应包含 end_date 参数"

        # 验证 trade_date 值为各子区间的 start_date
        trade_dates = [call[1]["trade_date"] for call in adapter._call_api.call_args_list]
        assert trade_dates == ["20230101", "20230102", "20230103"]

    @pytest.mark.asyncio
    async def test_non_trade_date_loop_keeps_date_range(self):
        """use_trade_date_loop=False 时，保留 start_date/end_date 参数"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="dc_daily",
            batch_by_date=True,
            date_chunk_days=6,
            required_params=[ParamType.DATE_RANGE],
            extra_config={},
        )

        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["trade_date", "ts_code", "close"],
            "items": [["20230101", "THS001", 100.0]],
        })

        params = {"start_date": "20230101", "end_date": "20230106"}

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry, adapter, params, "task_normal", 1, 0.0,
            )

        assert result["status"] == "completed"

        # 验证调用参数保留 start_date/end_date
        call_kwargs = adapter._call_api.call_args_list[0][1]
        assert "start_date" in call_kwargs
        assert "end_date" in call_kwargs
        assert "trade_date" not in call_kwargs

    @pytest.mark.asyncio
    async def test_no_date_params_falls_back_to_single(self):
        """batch_by_date=True 但无日期参数时退回 _process_single（需求 3.2）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="test_api",
            batch_by_date=True,
            required_params=[ParamType.DATE_RANGE],
        )

        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "close"],
            "items": [["600000.SH", 10.5]],
        })

        # 无 start_date/end_date
        params = {}

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry, adapter, params, "task_no_date", 1, 0.0,
            )

        # 应退回单次调用并成功完成
        assert result["status"] == "completed"
        # 单次调用也应调用 API 一次
        assert adapter._call_api.call_count == 1


# ---------------------------------------------------------------------------
# 截断检测集成测试（在 _process_batched_by_date 内部）
# 对应需求：3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 5.1, 5.3, 6.1, 6.2, 6.3, 6.4
# ---------------------------------------------------------------------------


class TestTruncationDetectionIntegration:
    """截断检测在 _process_batched_by_date 中的集成行为。

    注意：check_chunk_config / check_truncation 纯函数的单元测试
    已在 tests/tasks/test_truncation_detection.py 中覆盖。
    此处测试它们在日期分批处理流程中的集成效果。
    """

    @pytest.mark.asyncio
    async def test_single_chunk_truncation_logs_warning(self, caplog):
        """API 返回 max_rows 行时记录 WARNING 日志（需求 6.2）"""
        from app.tasks.tushare_import import _process_batched_by_date

        max_rows = 100
        entry = _make_entry(
            api_name="trunc_api",
            batch_by_date=True,
            date_chunk_days=5,
            required_params=[ParamType.DATE_RANGE],
            extra_config={"max_rows": max_rows},
        )

        # 模拟 API 返回恰好 max_rows 行 → 触发截断检测
        rows_data = [["600000.SH", "20230101", 10.0 + i] for i in range(max_rows)]
        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": rows_data,
        })

        params = {"start_date": "20230101", "end_date": "20230105"}

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            with caplog.at_level(logging.WARNING):
                result = await _process_batched_by_date(
                    entry, adapter, params, "task_trunc", 1, 0.0,
                )

        assert result["status"] == "completed"
        # 验证 WARNING 日志包含截断信息
        assert "数据可能被截断" in caplog.text
        assert "trunc_api" in caplog.text

        # 验证 batch_stats 中记录了截断
        batch_stats = result.get("batch_stats", {})
        assert batch_stats["truncation_count"] >= 1

    @pytest.mark.asyncio
    async def test_consecutive_truncation_logs_error(self, caplog):
        """连续 3 个子区间截断时记录 ERROR 日志并标记 needs_smaller_chunk（需求 6.4）"""
        from app.tasks.tushare_import import _process_batched_by_date

        max_rows = 50
        entry = _make_entry(
            api_name="consec_trunc_api",
            batch_by_date=True,
            date_chunk_days=2,
            required_params=[ParamType.DATE_RANGE],
            extra_config={"max_rows": max_rows},
        )

        # 模拟每个子区间都返回 max_rows 行 → 连续截断
        rows_data = [["600000.SH", "20230101", 10.0 + i] for i in range(max_rows)]
        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": rows_data,
        })

        # 6 天 / 2 天步长 = 3 个子区间，全部截断
        params = {"start_date": "20230101", "end_date": "20230106"}

        progress_calls = []

        async def capture_progress(*args, **kwargs):
            progress_calls.append(kwargs)

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", side_effect=capture_progress), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            with caplog.at_level(logging.WARNING):
                result = await _process_batched_by_date(
                    entry, adapter, params, "task_consec", 1, 0.0,
                )

        assert result["status"] == "completed"

        # 验证连续截断日志（WARNING 级别记录步长缩小）
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("连续" in r.message for r in warning_records), \
            "应记录连续截断 WARNING 日志（步长自动缩小）"
        assert any("consec_trunc_api" in r.message for r in warning_records)

        # 验证 batch_stats 中截断计数 >= 3
        batch_stats = result.get("batch_stats", {})
        assert batch_stats["truncation_count"] >= 3

        # 验证进度更新中包含 needs_smaller_chunk=True
        final_progress = [c for c in progress_calls if c.get("needs_smaller_chunk")]
        assert len(final_progress) > 0, "应在进度更新中标记 needs_smaller_chunk=True"


# ---------------------------------------------------------------------------
# 停止信号集成测试
# ---------------------------------------------------------------------------


class TestStopSignalIntegration:
    """停止信号在 _process_batched_by_date 中的集成行为。

    对应需求：3.3
    """

    @pytest.mark.asyncio
    async def test_stop_signal_returns_partial_records(self):
        """中途收到停止信号 → 返回已导入的记录数（需求 3.3）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="stop_api",
            batch_by_date=True,
            date_chunk_days=1,
            required_params=[ParamType.DATE_RANGE],
        )

        # 模拟 API 每次返回 5 行
        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": [["600000.SH", "20230101", 10.0 + i] for i in range(5)],
        })

        # 5 天范围 / 1 天步长 = 5 个子区间
        params = {"start_date": "20230101", "end_date": "20230105"}

        # 第 3 个子区间前收到停止信号（前 2 个正常处理）
        call_count = 0

        async def stop_after_2(task_id):
            nonlocal call_count
            call_count += 1
            return call_count > 2

        with patch("app.tasks.tushare_import._check_stop_signal", side_effect=stop_after_2), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry, adapter, params, "task_stop", 1, 0.0,
            )

        assert result["status"] == "stopped"
        # 前 2 个子区间各 5 行 = 10 行
        assert result["record_count"] == 10
        # API 只调用了 2 次（第 3 次前被停止）
        assert adapter._call_api.call_count == 2


# ---------------------------------------------------------------------------
# Token 无效立即终止测试
# ---------------------------------------------------------------------------


class TestTokenInvalidIntegration:
    """Token 无效（-2001）在 _process_batched_by_date 中的集成行为。

    对应需求：3.7
    """

    @pytest.mark.asyncio
    async def test_token_invalid_raises_immediately(self):
        """Token 无效错误（code=-2001）→ 立即终止，抛出 TushareAPIError（需求 3.7）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="token_api",
            batch_by_date=True,
            date_chunk_days=2,
            required_params=[ParamType.DATE_RANGE],
        )

        adapter = MagicMock()
        # 第一个子区间正常返回，第二个子区间抛出 Token 无效
        adapter._call_api = AsyncMock(
            side_effect=[
                {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [["600000.SH", "20230101", 10.0]],
                },
                TushareAPIError("Token 无效", api_name="token_api", code=-2001),
            ]
        )

        # 4 天 / 2 天步长 = 2 个子区间
        params = {"start_date": "20230101", "end_date": "20230104"}

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            with pytest.raises(TushareAPIError) as exc_info:
                await _process_batched_by_date(
                    entry, adapter, params, "task_token", 1, 0.0,
                )

            assert exc_info.value.code == -2001

        # 只调用了 2 次 API（第 2 次抛出异常后立即终止）
        assert adapter._call_api.call_count == 2


# ---------------------------------------------------------------------------
# 进度更新集成测试
# ---------------------------------------------------------------------------


class TestProgressUpdateIntegration:
    """进度更新在 _process_batched_by_date 中的集成行为。

    对应需求：3.8, 7.1, 7.2, 7.3, 7.4
    """

    @pytest.mark.asyncio
    async def test_progress_updated_after_each_chunk(self):
        """每个子区间处理后 Redis 进度正确更新（需求 3.8, 7.1, 7.2）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="progress_api",
            batch_by_date=True,
            date_chunk_days=2,
            required_params=[ParamType.DATE_RANGE],
        )

        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": [["600000.SH", "20230101", 10.0]],
        })

        # 6 天 / 2 天步长 = 3 个子区间
        params = {"start_date": "20230101", "end_date": "20230106"}

        progress_calls = []

        async def capture_progress(*args, **kwargs):
            progress_calls.append(kwargs)

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", side_effect=capture_progress), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry, adapter, params, "task_progress", 1, 0.0,
            )

        assert result["status"] == "completed"

        # 第一次调用是初始进度设置（total=3, completed=0）
        init_call = progress_calls[0]
        assert init_call["total"] == 3
        assert init_call["completed"] == 0
        assert init_call["batch_mode"] == "by_date"

        # 后续每个子区间处理后都有进度更新
        chunk_progress = [c for c in progress_calls[1:] if "completed" in c and c.get("completed", 0) > 0]
        assert len(chunk_progress) == 3, "应有 3 次子区间进度更新"

        # 验证 completed 递增
        completed_values = [c["completed"] for c in chunk_progress]
        assert completed_values == [1, 2, 3]

        # 验证 current_item 包含日期范围格式
        for c in chunk_progress:
            assert "-" in c.get("current_item", ""), \
                f"current_item 应包含日期范围格式，实际: {c.get('current_item')}"

    @pytest.mark.asyncio
    async def test_progress_includes_batch_mode(self):
        """进度更新包含 batch_mode="by_date"（需求 7.4）"""
        from app.tasks.tushare_import import _process_batched_by_date

        entry = _make_entry(
            api_name="mode_api",
            batch_by_date=True,
            date_chunk_days=3,
            required_params=[ParamType.DATE_RANGE],
        )

        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "close"],
            "items": [["600000.SH", 10.0]],
        })

        params = {"start_date": "20230101", "end_date": "20230103"}

        progress_calls = []

        async def capture_progress(*args, **kwargs):
            progress_calls.append(kwargs)

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", side_effect=capture_progress), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            await _process_batched_by_date(
                entry, adapter, params, "task_mode", 1, 0.0,
            )

        # 所有进度调用都应包含 batch_mode="by_date"
        for c in progress_calls:
            if "batch_mode" in c:
                assert c["batch_mode"] == "by_date"

    @pytest.mark.asyncio
    async def test_progress_includes_truncation_warnings(self):
        """截断时进度更新包含 truncation_warnings 列表（需求 7.3）"""
        from app.tasks.tushare_import import _process_batched_by_date

        max_rows = 20
        entry = _make_entry(
            api_name="trunc_progress_api",
            batch_by_date=True,
            date_chunk_days=3,
            required_params=[ParamType.DATE_RANGE],
            extra_config={"max_rows": max_rows},
        )

        # 返回恰好 max_rows 行 → 触发截断
        rows_data = [["600000.SH", "20230101", 10.0 + i] for i in range(max_rows)]
        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value={
            "fields": ["ts_code", "trade_date", "close"],
            "items": rows_data,
        })

        params = {"start_date": "20230101", "end_date": "20230103"}

        progress_calls = []

        async def capture_progress(*args, **kwargs):
            progress_calls.append(kwargs)

        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", side_effect=capture_progress), \
             patch("app.tasks.tushare_import._write_to_postgresql", new_callable=AsyncMock), \
             patch("time.sleep"):

            await _process_batched_by_date(
                entry, adapter, params, "task_trunc_prog", 1, 0.0,
            )

        # 查找包含 truncation_warnings 的进度调用
        trunc_calls = [c for c in progress_calls if c.get("truncation_warnings")]
        assert len(trunc_calls) > 0, "截断时应在进度更新中包含 truncation_warnings"

        # 验证 truncation_warnings 结构
        warnings = trunc_calls[-1]["truncation_warnings"]
        assert len(warnings) >= 1
        assert "chunk_start" in warnings[0]
        assert "chunk_end" in warnings[0]
        assert "row_count" in warnings[0]
        assert warnings[0]["row_count"] >= max_rows


# ---------------------------------------------------------------------------
# 频率限制从配置读取测试
# ---------------------------------------------------------------------------


class TestRateLimitFromConfig:
    """_build_rate_limit_map 使用 settings 值。

    对应需求：5.1, 5.3
    """

    def test_rate_limit_map_uses_settings_values(self):
        """频率限制映射的值应与 settings 中的配置一致（需求 5.3）"""
        from app.core.config import settings
        from app.tasks.tushare_import import _build_rate_limit_map

        rate_limit_map = _build_rate_limit_map()
        assert rate_limit_map[RateLimitGroup.KLINE] == settings.rate_limit_kline
        assert rate_limit_map[RateLimitGroup.FUNDAMENTALS] == settings.rate_limit_fundamentals
        assert rate_limit_map[RateLimitGroup.MONEY_FLOW] == settings.rate_limit_money_flow

    def test_rate_limit_map_covers_all_groups(self):
        """频率限制映射应覆盖所有 RateLimitGroup 枚举值"""
        from app.tasks.tushare_import import _build_rate_limit_map

        rate_limit_map = _build_rate_limit_map()
        for group in RateLimitGroup:
            assert group in rate_limit_map, \
                f"频率限制映射缺少 {group.value} 的配置"

    def test_rate_limit_map_values_are_positive(self):
        """频率限制值应为正数"""
        from app.tasks.tushare_import import _build_rate_limit_map

        for group, delay in _build_rate_limit_map().items():
            assert delay > 0, f"{group.value} 的频率限制应为正数，实际: {delay}"
