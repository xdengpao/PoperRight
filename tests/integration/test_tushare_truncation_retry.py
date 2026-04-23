"""Tushare 截断重试集成测试

Task 6.4: 模拟完整导入流程，验证截断重试后数据完整且 batch_stats 记录正确。

模拟 _process_batched_by_date 完整流程：
- API 返回截断数据 → 自动拆分子区间重试 → 重试数据写入 DB
- 连续截断 → 步长自动缩小 → 后续子区间使用新步长
- batch_stats 包含 truncation_recoveries、truncation_count、auto_shrink_applied

对应需求：2.4, 2.5, 8.1, 8.2
"""

from __future__ import annotations

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
    _process_batched_by_date,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _make_entry(
    api_name: str = "integration_test_api",
    date_chunk_days: int = 10,
    max_rows: int = 100,
    extra_config: dict | None = None,
) -> ApiEntry:
    """构建用于集成测试的 ApiEntry。"""
    ec = extra_config or {}
    ec.setdefault("max_rows", max_rows)
    return ApiEntry(
        api_name=api_name,
        label="集成测试接口",
        category="stock_data",
        subcategory="测试",
        token_tier=TokenTier.BASIC,
        target_table="test_table",
        storage_engine=StorageEngine.PG,
        code_format=CodeFormat.NONE,
        conflict_columns=["ts_code", "trade_date"],
        batch_by_date=True,
        date_chunk_days=date_chunk_days,
        extra_config=ec,
    )


def _make_api_response(fields: list[str], num_rows: int, prefix: str = "") -> dict:
    """构建模拟的 Tushare API 返回数据。"""
    items = []
    for i in range(num_rows):
        row = [f"{prefix}val_{i}_{j}" for j in range(len(fields))]
        items.append(row)
    return {"fields": fields, "items": items}


# ===========================================================================
# Task 6.4: 完整导入流程集成测试
# ===========================================================================


class TestTruncationRetryIntegration:
    """模拟完整导入流程，验证截断重试后数据完整且 batch_stats 记录正确。

    **Validates: Requirements 2.4, 2.5, 8.1, 8.2**
    """

    @pytest.mark.asyncio
    async def test_full_flow_with_truncation_recovery(self):
        """完整流程：多个 chunk 中部分截断 → 自动重试 → 数据完整 → batch_stats 正确。

        场景：日期范围 20230101~20230130，步长 10 天 → 3 个 chunk
        - chunk1 (01~10): 返回 100 行（截断）→ 拆分重试 → 子区间返回正常数据
        - chunk2 (11~20): 返回 50 行（正常）
        - chunk3 (21~30): 返回 60 行（正常）

        注意：成功重试后 result["truncated"]=False，所以 truncation_count=0，
        但 result["retried"]=True 表明发生了重试。验证数据完整性和总记录数。
        """
        entry = _make_entry(max_rows=100, date_chunk_days=10)
        fields = ["ts_code", "trade_date", "close"]

        written_rows: list[int] = []

        async def mock_call_api(adapter, api_name, params, entry_arg):
            start = params.get("start_date", "")
            end = params.get("end_date", "")

            # chunk1 原始区间截断
            if start == "20230101" and end == "20230110":
                return _make_api_response(fields, 100, prefix="trunc_")
            # chunk2 正常
            if start == "20230111" and end == "20230120":
                return _make_api_response(fields, 50, prefix="c2_")
            # chunk3 正常
            if start == "20230121" and end == "20230130":
                return _make_api_response(fields, 60, prefix="c3_")
            # 重试子区间返回正常数据
            return _make_api_response(fields, 40, prefix="retry_")

        async def mock_write(rows, entry_arg, inject):
            written_rows.append(len(rows))
            return len(rows)

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", AsyncMock(side_effect=mock_write)), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230130"},
                task_id="integration-test-001",
                log_id=1,
                rate_delay=0.0,
            )

        # 任务完成
        assert result["status"] == "completed"

        # 数据完整性：chunk1 重试 2 个子区间各 40 行 + chunk2 50 行 + chunk3 60 行
        total_records = result["record_count"]
        assert total_records == 40 + 40 + 50 + 60  # 190

        # batch_stats 结构验证
        batch_stats = result.get("batch_stats", {})
        assert batch_stats["batch_mode"] == "by_date"
        assert batch_stats["total_chunks"] >= 3
        # 成功重试后 truncated=False，所以 truncation_count=0
        # 但数据完整性已通过 total_records 验证
        assert "truncation_count" in batch_stats

    @pytest.mark.asyncio
    async def test_full_flow_with_consecutive_truncation_and_step_shrink(self):
        """完整流程：连续 3 个 chunk 截断（无法完全恢复）→ 步长自动缩小。

        场景：日期范围 20230101~20230228，步长 3 天
        - 前 9 天（3 个 chunk）的所有调用（包括重试子区间）都返回截断数据
        - 这导致 result["truncated"]=True，consecutive_truncation_count 递增
        - 达到阈值 3 后触发步长缩小
        """
        entry = _make_entry(max_rows=100, date_chunk_days=3)
        fields = ["ts_code", "trade_date", "close"]

        async def mock_call_api(adapter, api_name, params, entry_arg):
            start = params.get("start_date", "")
            # 前 9 天的所有调用都截断
            if start <= "20230109":
                return _make_api_response(fields, 100, prefix="trunc_")
            return _make_api_response(fields, 20, prefix="ok_")

        async def mock_write(rows, entry_arg, inject):
            return len(rows)

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", AsyncMock(side_effect=mock_write)), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230228"},
                task_id="integration-test-002",
                log_id=2,
                rate_delay=0.0,
            )

        assert result["status"] == "completed"
        assert result["record_count"] > 0

        # batch_stats 验证
        batch_stats = result.get("batch_stats", {})
        assert batch_stats.get("truncation_count", 0) >= _CONSECUTIVE_TRUNCATION_THRESHOLD
        assert batch_stats.get("auto_shrink_applied") is True

        # 截断恢复记录应包含 auto_shrink_step 条目
        recoveries = batch_stats.get("truncation_recoveries", [])
        shrink_entries = [r for r in recoveries if r.get("action") == "auto_shrink_step"]
        assert len(shrink_entries) >= 1
        shrink_entry = shrink_entries[0]
        assert shrink_entry["old_chunk_days"] == 3
        assert shrink_entry["new_chunk_days"] == 1

    @pytest.mark.asyncio
    async def test_full_flow_no_truncation(self):
        """完整流程：无截断 → 正常完成 → batch_stats 无截断记录。"""
        entry = _make_entry(max_rows=100, date_chunk_days=10)
        fields = ["ts_code", "trade_date", "close"]

        async def mock_call_api(adapter, api_name, params, entry_arg):
            return _make_api_response(fields, 30, prefix="ok_")

        async def mock_write(rows, entry_arg, inject):
            return len(rows)

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", AsyncMock(side_effect=mock_write)), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230130"},
                task_id="integration-test-003",
                log_id=3,
                rate_delay=0.0,
            )

        assert result["status"] == "completed"
        # 3 chunks × 30 rows = 90
        assert result["record_count"] == 90

        batch_stats = result.get("batch_stats", {})
        assert batch_stats["truncation_count"] == 0
        assert batch_stats.get("auto_shrink_applied") is None or batch_stats.get("auto_shrink_applied") is not True
        assert batch_stats.get("truncation_recoveries") is None or len(batch_stats.get("truncation_recoveries", [])) == 0

    @pytest.mark.asyncio
    async def test_batch_stats_structure_completeness(self):
        """验证 batch_stats 包含所有必要字段（截断无法完全恢复场景）。"""
        entry = _make_entry(max_rows=100, date_chunk_days=5)
        fields = ["ts_code", "trade_date", "close"]

        async def mock_call_api(adapter, api_name, params, entry_arg):
            start = params.get("start_date", "")
            # 第一个 chunk (01~05) 的所有调用都截断（包括重试子区间和单日）
            if start <= "20230105":
                return _make_api_response(fields, 100, prefix="trunc_")
            return _make_api_response(fields, 30, prefix="ok_")

        async def mock_write(rows, entry_arg, inject):
            return len(rows)

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", AsyncMock(side_effect=mock_write)), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230130"},
                task_id="integration-test-004",
                log_id=4,
                rate_delay=0.0,
            )

        batch_stats = result.get("batch_stats", {})

        # 必要字段验证
        assert "batch_mode" in batch_stats
        assert batch_stats["batch_mode"] == "by_date"
        assert "total_chunks" in batch_stats
        assert "success_chunks" in batch_stats
        assert "truncation_count" in batch_stats
        assert "truncation_details" in batch_stats

        # 截断详情结构
        assert batch_stats["truncation_count"] >= 1
        details = batch_stats["truncation_details"]
        assert len(details) >= 1
        first_detail = details[0]
        assert "chunk" in first_detail
        assert "rows" in first_detail
        assert "max_rows" in first_detail
        assert "retried" in first_detail
        assert first_detail["retried"] is True

        # 截断恢复记录
        recoveries = batch_stats.get("truncation_recoveries", [])
        assert len(recoveries) >= 1

    @pytest.mark.asyncio
    async def test_stop_signal_during_truncation_retry(self):
        """截断重试过程中收到停止信号 → 正确中断并返回 stopped 状态。"""
        entry = _make_entry(max_rows=100, date_chunk_days=10)
        fields = ["ts_code", "trade_date", "close"]

        stop_after_calls = 2
        call_count = 0

        async def mock_call_api(adapter, api_name, params, entry_arg):
            nonlocal call_count
            call_count += 1
            # 始终返回截断数据，触发重试
            return _make_api_response(fields, 100, prefix="trunc_")

        async def mock_check_stop(task_id):
            # 在第 2 次 API 调用后发送停止信号
            return call_count >= stop_after_calls

        async def mock_write(rows, entry_arg, inject):
            return len(rows)

        with patch("app.tasks.tushare_import._call_api_with_retry", side_effect=mock_call_api), \
             patch("app.tasks.tushare_import._write_chunk_rows", AsyncMock(side_effect=mock_write)), \
             patch("app.tasks.tushare_import._check_stop_signal", side_effect=mock_check_stop), \
             patch("app.tasks.tushare_import._update_progress", new_callable=AsyncMock), \
             patch("time.sleep"):

            result = await _process_batched_by_date(
                entry=entry,
                adapter=None,
                params={"start_date": "20230101", "end_date": "20230130"},
                task_id="integration-test-005",
                log_id=5,
                rate_delay=0.0,
            )

        assert result["status"] == "stopped"
        # batch_stats 应存在
        batch_stats = result.get("batch_stats")
        assert batch_stats is not None
