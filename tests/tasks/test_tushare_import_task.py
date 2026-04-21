"""
Tushare 数据导入 Celery 任务单元测试

覆盖：
- _apply_field_mappings：字段映射（有映射 / 无映射 pass-through）
- _convert_codes：STOCK_SYMBOL 转换、INDEX_CODE 保留、NONE 透传
- 批处理逻辑：正确的分批数量
- 停止信号检测：任务收到信号后停止
- 错误处理：网络超时重试、Token 无效不重试

对应需求：3.2, 4.4, 4.8, 21.3
"""

from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_adapter import TushareAPIError
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    FieldMapping,
    StorageEngine,
    TokenTier,
    RateLimitGroup,
)
from app.tasks.tushare_import import (
    BATCH_SIZE,
    _apply_field_mappings,
    _convert_codes,
)


# ---------------------------------------------------------------------------
# 辅助：创建测试用 ApiEntry
# ---------------------------------------------------------------------------

def _make_entry(
    code_format: CodeFormat = CodeFormat.STOCK_SYMBOL,
    field_mappings: list[FieldMapping] | None = None,
    storage_engine: StorageEngine = StorageEngine.PG,
    conflict_columns: list[str] | None = None,
    conflict_action: str = "do_nothing",
    batch_by_code: bool = False,
    extra_config: dict | None = None,
) -> ApiEntry:
    """创建用于测试的最小 ApiEntry。"""
    return ApiEntry(
        api_name="test_api",
        label="测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table="test_table",
        storage_engine=storage_engine,
        code_format=code_format,
        conflict_columns=conflict_columns or [],
        conflict_action=conflict_action,
        field_mappings=field_mappings or [],
        batch_by_code=batch_by_code,
        extra_config=extra_config or {},
    )


# ---------------------------------------------------------------------------
# _apply_field_mappings 测试
# ---------------------------------------------------------------------------


class TestApplyFieldMappings:
    """字段映射函数测试"""

    def test_with_mappings_renames_fields(self):
        """有映射时应将 source 字段重命名为 target 字段"""
        mappings = [
            FieldMapping(source="ts_code", target="symbol"),
            FieldMapping(source="trade_date", target="date"),
        ]
        entry = _make_entry(field_mappings=mappings)
        rows = [
            {"ts_code": "600000.SH", "trade_date": "20240115", "close": 10.5},
            {"ts_code": "000001.SZ", "trade_date": "20240116", "close": 11.0},
        ]

        result = _apply_field_mappings(rows, entry)

        assert len(result) == 2
        assert result[0]["symbol"] == "600000.SH"
        assert result[0]["date"] == "20240115"
        assert result[0]["close"] == 10.5
        # 原始键名不应保留（被映射替换）
        assert "ts_code" not in result[0]
        assert "trade_date" not in result[0]

    def test_without_mappings_passthrough(self):
        """无映射时应原样返回（pass-through）"""
        entry = _make_entry(field_mappings=[])
        rows = [
            {"ts_code": "600000.SH", "close": 10.5, "vol": 1000},
        ]

        result = _apply_field_mappings(rows, entry)

        assert len(result) == 1
        assert result[0] == rows[0]

    def test_partial_mapping_keeps_unmapped_fields(self):
        """部分映射时，未映射的字段应保留原名"""
        mappings = [FieldMapping(source="ts_code", target="code")]
        entry = _make_entry(field_mappings=mappings)
        rows = [{"ts_code": "600000.SH", "close": 10.5, "vol": 1000}]

        result = _apply_field_mappings(rows, entry)

        assert result[0]["code"] == "600000.SH"
        assert result[0]["close"] == 10.5
        assert result[0]["vol"] == 1000

    def test_empty_rows_returns_empty(self):
        """空行列表应返回空列表"""
        mappings = [FieldMapping(source="ts_code", target="symbol")]
        entry = _make_entry(field_mappings=mappings)

        result = _apply_field_mappings([], entry)

        assert result == []


# ---------------------------------------------------------------------------
# _convert_codes 测试
# ---------------------------------------------------------------------------


class TestConvertCodes:
    """代码格式转换函数测试"""

    def test_stock_symbol_removes_suffix(self):
        """STOCK_SYMBOL 模式应去除 ts_code 后缀，生成 symbol 字段"""
        entry = _make_entry(code_format=CodeFormat.STOCK_SYMBOL)
        rows = [
            {"ts_code": "600000.SH", "close": 10.5},
            {"ts_code": "000001.SZ", "close": 11.0},
            {"ts_code": "430047.BJ", "close": 5.0},
        ]

        result = _convert_codes(rows, entry)

        assert result[0]["symbol"] == "600000"
        assert result[1]["symbol"] == "000001"
        assert result[2]["symbol"] == "430047"

    def test_index_code_preserves_ts_code(self):
        """INDEX_CODE 模式应保留 ts_code 原样，不添加 symbol"""
        entry = _make_entry(code_format=CodeFormat.INDEX_CODE)
        rows = [
            {"ts_code": "000001.SH", "close": 3000.0},
            {"ts_code": "399001.SZ", "close": 10000.0},
        ]

        result = _convert_codes(rows, entry)

        assert result[0]["ts_code"] == "000001.SH"
        assert result[1]["ts_code"] == "399001.SZ"
        assert "symbol" not in result[0]
        assert "symbol" not in result[1]

    def test_none_format_passthrough(self):
        """NONE 模式应不做任何转换"""
        entry = _make_entry(code_format=CodeFormat.NONE)
        rows = [
            {"exchange": "SSE", "cal_date": "20240115", "is_open": True},
        ]

        result = _convert_codes(rows, entry)

        assert result == rows

    def test_stock_symbol_with_pure_digits(self):
        """STOCK_SYMBOL 模式处理纯数字代码（无点号）时应直接作为 symbol"""
        entry = _make_entry(code_format=CodeFormat.STOCK_SYMBOL)
        rows = [{"ts_code": "600000", "close": 10.5}]

        result = _convert_codes(rows, entry)

        assert result[0]["symbol"] == "600000"

    def test_stock_symbol_empty_ts_code(self):
        """STOCK_SYMBOL 模式处理空 ts_code 时不应崩溃"""
        entry = _make_entry(code_format=CodeFormat.STOCK_SYMBOL)
        rows = [{"ts_code": "", "close": 10.5}]

        result = _convert_codes(rows, entry)

        # 空 ts_code 不应添加 symbol
        assert len(result) == 1

    def test_stock_symbol_missing_ts_code(self):
        """STOCK_SYMBOL 模式处理缺少 ts_code 字段时不应崩溃"""
        entry = _make_entry(code_format=CodeFormat.STOCK_SYMBOL)
        rows = [{"close": 10.5}]

        result = _convert_codes(rows, entry)

        assert len(result) == 1


# ---------------------------------------------------------------------------
# 批处理逻辑测试
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    """批处理分批逻辑测试"""

    def test_batch_size_is_50(self):
        """BATCH_SIZE 常量应为 50"""
        assert BATCH_SIZE == 50

    def test_exact_multiple_batches(self):
        """列表长度为 BATCH_SIZE 整数倍时，批次数量正确"""
        items = list(range(100))
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        assert len(batches) == 2
        assert all(len(b) == BATCH_SIZE for b in batches)

    def test_non_exact_multiple_batches(self):
        """列表长度非 BATCH_SIZE 整数倍时，最后一批较小"""
        items = list(range(120))
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50
        assert len(batches[2]) == 20

    def test_empty_list_no_batches(self):
        """空列表应产生 0 个批次"""
        items = []
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        assert len(batches) == 0

    def test_single_item_one_batch(self):
        """单个元素应产生 1 个批次"""
        items = ["600000.SH"]
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        assert len(batches) == 1
        assert batches[0] == ["600000.SH"]

    def test_batch_count_formula(self):
        """批次数量应等于 ceil(N / BATCH_SIZE)"""
        for n in [0, 1, 49, 50, 51, 100, 150, 200, 499, 500]:
            items = list(range(n))
            batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
            expected = math.ceil(n / BATCH_SIZE) if n > 0 else 0
            assert len(batches) == expected, f"n={n}: expected {expected}, got {len(batches)}"


# ---------------------------------------------------------------------------
# 停止信号检测测试
# ---------------------------------------------------------------------------


class TestStopSignalDetection:
    """停止信号检测测试"""

    @pytest.mark.asyncio
    async def test_stop_signal_detected(self):
        """Redis 中存在停止信号时应返回 True"""
        from app.tasks.tushare_import import _check_stop_signal

        with patch("app.tasks.tushare_import._redis_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "1"
            result = await _check_stop_signal("task_123")
            assert result is True
            mock_get.assert_called_once_with("tushare:import:stop:task_123")

    @pytest.mark.asyncio
    async def test_no_stop_signal(self):
        """Redis 中无停止信号时应返回 False"""
        from app.tasks.tushare_import import _check_stop_signal

        with patch("app.tasks.tushare_import._redis_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await _check_stop_signal("task_456")
            assert result is False

    @pytest.mark.asyncio
    async def test_batched_stops_on_signal(self):
        """分批处理中检测到停止信号时应返回 stopped 状态"""
        from app.tasks.tushare_import import _process_batched

        entry = _make_entry(
            code_format=CodeFormat.STOCK_SYMBOL,
            batch_by_code=True,
        )
        adapter = MagicMock()

        # 模拟停止信号：第一次检查就返回 True
        with patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock) as mock_stop, \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock) as mock_stocks, \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock):
            mock_stop.return_value = True
            mock_stocks.return_value = ["600000.SH", "000001.SZ"]

            result = await _process_batched(entry, adapter, {}, "task_stop", 1, 0.0)

        assert result["status"] == "stopped"
        assert result["record_count"] == 0


# ---------------------------------------------------------------------------
# 错误处理测试
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """API 调用错误处理测试"""

    @pytest.mark.asyncio
    async def test_network_timeout_retries(self):
        """网络超时应重试最多 3 次"""
        import httpx

        from app.tasks.tushare_import import _call_api_with_retry

        adapter = MagicMock()
        adapter._call_api = AsyncMock(
            side_effect=httpx.TimeoutException("连接超时")
        )
        entry = _make_entry()

        with patch("time.sleep"):  # 跳过退避等待
            with pytest.raises(TushareAPIError, match="重试.*次后仍失败"):
                await _call_api_with_retry(adapter, "daily", {}, entry)

        # 应调用 3 次（初始 + 2 次重试）
        assert adapter._call_api.call_count == 3

    @pytest.mark.asyncio
    async def test_token_invalid_no_retry(self):
        """Token 无效（code=-2001）不应重试，直接抛出"""
        from app.tasks.tushare_import import _call_api_with_retry

        adapter = MagicMock()
        adapter._call_api = AsyncMock(
            side_effect=TushareAPIError("Token 无效", api_name="daily", code=-2001)
        )
        entry = _make_entry()

        with pytest.raises(TushareAPIError) as exc_info:
            await _call_api_with_retry(adapter, "daily", {}, entry)

        assert exc_info.value.code == -2001
        # 应只调用 1 次，不重试
        assert adapter._call_api.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_waits_and_retries(self):
        """频率限制（code=-2002）应等待后重试"""
        from app.tasks.tushare_import import _call_api_with_retry

        adapter = MagicMock()
        # 第一次频率限制，第二次成功
        adapter._call_api = AsyncMock(
            side_effect=[
                TushareAPIError("频率限制", api_name="daily", code=-2002),
                {"fields": ["ts_code"], "items": [["600000.SH"]]},
            ]
        )
        entry = _make_entry()

        with patch("time.sleep") as mock_sleep:
            result = await _call_api_with_retry(adapter, "daily", {}, entry)

        assert result == {"fields": ["ts_code"], "items": [["600000.SH"]]}
        assert adapter._call_api.call_count == 2
        # 应等待 60 秒
        mock_sleep.assert_called_with(60)

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        """成功的 API 调用应直接返回数据"""
        from app.tasks.tushare_import import _call_api_with_retry

        expected_data = {"fields": ["ts_code", "close"], "items": [["600000.SH", 10.5]]}
        adapter = MagicMock()
        adapter._call_api = AsyncMock(return_value=expected_data)
        entry = _make_entry()

        result = await _call_api_with_retry(adapter, "daily", {}, entry)

        assert result == expected_data
        assert adapter._call_api.call_count == 1
