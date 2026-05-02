"""Tushare 导入频率超限与数据截断修复 — 单元测试

Task 6.1: 验证新增 RateLimitGroup 枚举值完整性和 _build_rate_limit_map() 覆盖
Task 6.2: 验证截断自动重试逻辑（mock API 返回 max_rows 行 → 自动拆分子区间重试）
Task 6.3: 验证连续截断步长缩小（连续 3 个截断子区间 → 后续步长减半）

对应需求：2.1, 2.2, 2.4, 2.5, 2.6
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    RateLimitGroup,
    StorageEngine,
    TokenTier,
)
from app.tasks.tushare_import import (
    _CONSECUTIVE_TRUNCATION_THRESHOLD,
    _MAX_TRUNCATION_RETRY_DEPTH,
    _build_rate_limit_map,
    _process_chunk_with_retry,
    _process_batched_by_date,
)


# ---------------------------------------------------------------------------
# 辅助：构建测试用 ApiEntry
# ---------------------------------------------------------------------------

def _make_entry(
    api_name: str = "test_api",
    batch_by_date: bool = True,
    date_chunk_days: int = 10,
    max_rows: int = 3000,
    extra_config: dict | None = None,
) -> ApiEntry:
    """构建用于测试的 ApiEntry。"""
    ec = extra_config or {}
    ec.setdefault("max_rows", max_rows)
    return ApiEntry(
        api_name=api_name,
        label="测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table="test_table",
        storage_engine=StorageEngine.PG,
        code_format=CodeFormat.NONE,
        conflict_columns=["ts_code", "trade_date"],
        batch_by_date=batch_by_date,
        date_chunk_days=date_chunk_days,
        extra_config=ec,
    )


def _make_api_response(fields: list[str], num_rows: int) -> dict:
    """构建模拟的 Tushare API 返回数据。"""
    items = []
    for i in range(num_rows):
        row = [f"val_{i}_{j}" for j in range(len(fields))]
        items.append(row)
    return {"fields": fields, "items": items}


# ===========================================================================
# Task 6.1: RateLimitGroup 枚举值完整性和 _build_rate_limit_map() 覆盖
# ===========================================================================


class TestRateLimitGroupEnumCompleteness:
    """验证新增 RateLimitGroup 枚举值的完整性。

    **Validates: Requirements 2.2, 2.6**
    """

    def test_tier_80_exists(self):
        """TIER_80 枚举值存在。"""
        assert hasattr(RateLimitGroup, "TIER_80")
        assert RateLimitGroup.TIER_80.value == "tier_80"

    def test_tier_60_exists(self):
        """TIER_60 枚举值存在。"""
        assert hasattr(RateLimitGroup, "TIER_60")
        assert RateLimitGroup.TIER_60.value == "tier_60"

    def test_tier_20_exists(self):
        """TIER_20 枚举值存在。"""
        assert hasattr(RateLimitGroup, "TIER_20")
        assert RateLimitGroup.TIER_20.value == "tier_20"

    def test_tier_10_exists(self):
        """TIER_10 枚举值存在。"""
        assert hasattr(RateLimitGroup, "TIER_10")
        assert RateLimitGroup.TIER_10.value == "tier_10"

    def test_original_groups_preserved(self):
        """原有分组（KLINE/FUNDAMENTALS/MONEY_FLOW/LIMIT_UP）保留。"""
        assert RateLimitGroup.KLINE.value == "kline"
        assert RateLimitGroup.FUNDAMENTALS.value == "fundamentals"
        assert RateLimitGroup.MONEY_FLOW.value == "money_flow"
        assert RateLimitGroup.LIMIT_UP.value == "limit_up"

    def test_all_enum_values_count(self):
        """枚举值总数 = 原有 4 个 + 官方频率层级 5 个 = 9 个。"""
        all_values = list(RateLimitGroup)
        assert len(all_values) == 9


class TestBuildRateLimitMapCoverage:
    """验证 _build_rate_limit_map() 覆盖所有枚举值。

    **Validates: Requirements 2.2, 2.6**
    """

    def test_covers_all_enum_values(self):
        """映射覆盖所有 RateLimitGroup 枚举值。"""
        rate_map = _build_rate_limit_map()
        all_groups = set(RateLimitGroup)
        mapped_groups = set(rate_map.keys())
        missing = all_groups - mapped_groups
        assert not missing, f"缺少映射: {[g.value for g in missing]}"

    def test_all_values_are_positive_floats(self):
        """所有映射值为正数。"""
        rate_map = _build_rate_limit_map()
        for group, interval in rate_map.items():
            assert isinstance(interval, (int, float)), (
                f"{group.value} 映射值类型为 {type(interval).__name__}"
            )
            assert interval > 0, f"{group.value} 映射值 {interval} <= 0"

    def test_tier_80_interval(self):
        """TIER_80 间隔约 0.90s。"""
        rate_map = _build_rate_limit_map()
        assert rate_map[RateLimitGroup.TIER_80] >= 0.75

    def test_tier_60_interval(self):
        """TIER_60 间隔约 1.20s。"""
        rate_map = _build_rate_limit_map()
        assert rate_map[RateLimitGroup.TIER_60] >= 1.0

    def test_tier_20_interval(self):
        """TIER_20 间隔约 3.50s。"""
        rate_map = _build_rate_limit_map()
        assert rate_map[RateLimitGroup.TIER_20] >= 3.0

    def test_tier_10_interval(self):
        """TIER_10 间隔约 7.0s。"""
        rate_map = _build_rate_limit_map()
        assert rate_map[RateLimitGroup.TIER_10] >= 6.0

    def test_no_extra_keys(self):
        """映射不包含非枚举值的键。"""
        rate_map = _build_rate_limit_map()
        all_groups = set(RateLimitGroup)
        extra = set(rate_map.keys()) - all_groups
        assert not extra, f"映射包含多余的键: {extra}"


# ===========================================================================
# Task 6.2: 截断自动重试逻辑
# ===========================================================================


class TestTruncationAutoRetry:
    """验证截断自动重试逻辑：API 返回 max_rows 行时自动拆分子区间重试。

    **Validates: Requirements 2.4**
    """

    @pytest.mark.asyncio
    async def test_truncated_chunk_triggers_retry(self):
        """API 返回 max_rows 行 → 丢弃截断数据 → 拆分子区间重试 → 写入重试数据。"""
        entry = _make_entry(max_rows=100, date_chunk_days=10)
        fields = ["ts_code", "trade_date", "close"]

        # 第一次调用（原始区间 20230101~20230110）返回 100 行（截断）
        truncated_response = _make_api_response(fields, 100)
        # 重试子区间调用返回少于 max_rows 的行
        sub_response_1 = _make_api_response(fields, 40)
        sub_response_2 = _make_api_response(fields, 35)

        call_count = 0

        async def mock_call_api(adapter, api_name, params, entry_arg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return truncated_response
            elif call_count == 2:
                return sub_response_1
            else:
                return sub_response_2

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("time.sleep"):

            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=None,
                params={},
                task_id="test-task",
                chunk_start="20230101",
                chunk_end="20230110",
                max_rows=100,
                rate_delay=0.0,
                actual_api_name="test_api",
                default_params={},
                inject_fields=None,
                use_trade_date_loop=False,
                depth=0,
            )

        # 应触发重试
        assert result["retried"] is True
        # 截断数据不应被写入（只有重试子区间的数据被写入）
        assert result["records"] == 75  # 40 + 35
        # API 被调用 3 次：1 次原始 + 2 次子区间
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_truncated_chunk_no_retry(self):
        """API 返回少于 max_rows 行 → 正常写入，不触发重试。"""
        entry = _make_entry(max_rows=100)
        fields = ["ts_code", "trade_date", "close"]
        normal_response = _make_api_response(fields, 50)

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", new_callable=AsyncMock, return_value=normal_response), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("time.sleep"):

            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=None,
                params={},
                task_id="test-task",
                chunk_start="20230101",
                chunk_end="20230110",
                max_rows=100,
                rate_delay=0.0,
                actual_api_name="test_api",
                default_params={},
                inject_fields=None,
                use_trade_date_loop=False,
                depth=0,
            )

        assert result["retried"] is False
        assert result["truncated"] is False
        assert result["records"] == 50

    @pytest.mark.asyncio
    async def test_max_depth_stops_recursion(self):
        """达到最大重试深度时停止递归，写入已获取的（可能不完整的）数据。"""
        entry = _make_entry(max_rows=100)
        fields = ["ts_code", "trade_date", "close"]
        # 始终返回截断数据
        truncated_response = _make_api_response(fields, 100)

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", new_callable=AsyncMock, return_value=truncated_response), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("time.sleep"):

            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=None,
                params={},
                task_id="test-task",
                chunk_start="20230101",
                chunk_end="20230102",
                max_rows=100,
                rate_delay=0.0,
                actual_api_name="test_api",
                default_params={},
                inject_fields=None,
                use_trade_date_loop=False,
                depth=_MAX_TRUNCATION_RETRY_DEPTH,  # 已达最大深度
            )

        # 达到最大深度，应写入截断数据
        assert result["truncated"] is True
        assert result["retried"] is True
        assert result["records"] == 100
        # 应有 max_depth_reached 详情
        assert any(
            d.get("action") == "max_depth_reached"
            for d in result["retry_details"]
        )

    @pytest.mark.asyncio
    async def test_empty_response_no_retry(self):
        """API 返回 0 行 → 不触发重试。"""
        entry = _make_entry(max_rows=100)
        empty_response = {"fields": ["ts_code"], "items": []}

        with patch("app.tasks.tushare_import._call_api_with_retry", new_callable=AsyncMock, return_value=empty_response), \
             patch("time.sleep"):

            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=None,
                params={},
                task_id="test-task",
                chunk_start="20230101",
                chunk_end="20230110",
                max_rows=100,
                rate_delay=0.0,
                actual_api_name="test_api",
                default_params={},
                inject_fields=None,
                use_trade_date_loop=False,
                depth=0,
            )

        assert result["records"] == 0
        assert result["truncated"] is False
        assert result["retried"] is False

    @pytest.mark.asyncio
    async def test_single_day_chunk_cannot_split_further(self):
        """单日子区间截断时无法再拆分，写入已获取数据。"""
        entry = _make_entry(max_rows=100)
        fields = ["ts_code", "trade_date", "close"]
        truncated_response = _make_api_response(fields, 100)

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", new_callable=AsyncMock, return_value=truncated_response), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("time.sleep"):

            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=None,
                params={},
                task_id="test-task",
                chunk_start="20230101",
                chunk_end="20230101",  # 单日
                max_rows=100,
                rate_delay=0.0,
                actual_api_name="test_api",
                default_params={},
                inject_fields=None,
                use_trade_date_loop=False,
                depth=0,
            )

        assert result["truncated"] is True
        assert result["retried"] is True
        assert result["records"] == 100
        assert any(
            d.get("action") == "cannot_split_further"
            for d in result["retry_details"]
        )


# ===========================================================================
# Task 6.3: 连续截断步长缩小
# ===========================================================================


class TestConsecutiveTruncationStepShrink:
    """验证连续截断步长缩小：连续 3 个截断子区间 → 后续步长减半。

    **Validates: Requirements 2.5**
    """

    @pytest.mark.asyncio
    async def test_consecutive_truncation_shrinks_step(self):
        """连续 3 个子区间截断（无法完全恢复）→ 后续步长从 10 天缩小到 5 天。

        为触发 consecutive_truncation_count，result["truncated"] 必须为 True，
        即截断重试后子区间仍然截断（例如单日子区间仍返回 max_rows 行）。
        使用 date_chunk_days=3 和短日期范围，使得拆分后的单日子区间仍截断。
        """
        entry = _make_entry(
            max_rows=100,
            date_chunk_days=3,
            extra_config={"max_rows": 100},
        )

        fields = ["ts_code", "trade_date", "close"]
        truncated_response = _make_api_response(fields, 100)
        normal_response = _make_api_response(fields, 30)

        async def mock_call_api(adapter, api_name, params, entry_arg):
            start = params.get("start_date", "")
            end = params.get("end_date", "")
            # 前 9 天（3 个 chunk × 3 天）的所有调用都返回截断数据
            # 包括重试子区间和单日子区间，确保 result["truncated"]=True
            if start <= "20230109":
                return truncated_response
            return normal_response

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230228"},
                task_id="test-task",
                log_id=1,
                rate_delay=0.0,
            )

        # 任务应完成
        assert result["status"] == "completed"
        # batch_stats 应记录截断恢复信息
        batch_stats = result.get("batch_stats", {})
        assert batch_stats.get("truncation_count", 0) >= _CONSECUTIVE_TRUNCATION_THRESHOLD
        # 应触发步长自动缩小
        assert batch_stats.get("auto_shrink_applied") is True

    @pytest.mark.asyncio
    async def test_non_consecutive_truncation_no_shrink(self):
        """非连续截断（中间有正常子区间）不触发步长缩小。"""
        entry = _make_entry(
            max_rows=100,
            date_chunk_days=10,
            extra_config={"max_rows": 100},
        )

        fields = ["ts_code", "trade_date", "close"]
        truncated_response = _make_api_response(fields, 100)
        normal_response = _make_api_response(fields, 30)

        call_count = 0

        async def mock_call_api(adapter, api_name, params, entry_arg):
            nonlocal call_count
            call_count += 1
            # 交替截断和正常：chunk1 截断, chunk2 正常, chunk3 截断, chunk4 正常...
            if call_count % 2 == 1:
                # 奇数次调用：如果是原始 chunk 则截断
                # 但由于截断会触发重试，重试子区间返回正常数据
                start = params.get("start_date", "")
                end = params.get("end_date", "")
                # 只有 10 天跨度的原始 chunk 才截断
                from datetime import datetime
                try:
                    s = datetime.strptime(start, "%Y%m%d").date()
                    e = datetime.strptime(end, "%Y%m%d").date()
                    if (e - s).days >= 9:
                        return truncated_response
                except ValueError:
                    pass
            return normal_response

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230220"},
                task_id="test-task",
                log_id=1,
                rate_delay=0.0,
            )

        batch_stats = result.get("batch_stats", {})
        # 非连续截断不应触发步长缩小
        assert batch_stats.get("auto_shrink_applied") is not True

    @pytest.mark.asyncio
    async def test_truncation_recoveries_recorded(self):
        """截断重试恢复详情被记录到 batch_stats.truncation_recoveries。

        当截断无法完全恢复（单日子区间仍截断）时，result["truncated"]=True
        且 result["retried"]=True，此时 truncation_recoveries 被记录。
        """
        entry = _make_entry(
            max_rows=100,
            date_chunk_days=5,
            extra_config={"max_rows": 100},
        )

        fields = ["ts_code", "trade_date", "close"]
        truncated_response = _make_api_response(fields, 100)
        normal_response = _make_api_response(fields, 30)

        async def mock_call_api(adapter, api_name, params, entry_arg):
            start = params.get("start_date", "")
            # 第一个 chunk (01~05) 的所有调用都截断（包括重试子区间）
            if start <= "20230105":
                return truncated_response
            return normal_response

        mock_write = AsyncMock(side_effect=lambda rows, entry, inject: len(rows))

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", mock_write), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230120"},
                task_id="test-task",
                log_id=1,
                rate_delay=0.0,
            )

        batch_stats = result.get("batch_stats", {})
        # 应有截断恢复记录
        recoveries = batch_stats.get("truncation_recoveries", [])
        assert len(recoveries) >= 1
        # 恢复记录应包含 chunk 信息
        first_recovery = recoveries[0]
        assert "chunk_start" in first_recovery or "action" in first_recovery
