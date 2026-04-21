"""
Bug Condition 探索性测试：Tushare 导入 5 项 UX 缺陷

**Validates: Requirements 1.5**

Property 1: Bug Condition — 错误信息存储

对任意 task_id 和 error_message，调用 _update_progress(task_id, status="failed", error_message=error_msg)
后，Redis 进度数据应包含 error_message 字段。

此测试编码了期望行为。在未修复代码上运行时应失败（确认缺陷存在）。
修复后运行应通过（确认修复正确性）。
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.tasks.tushare_import import _update_progress


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 任务 ID：UUID 格式字符串
_task_id_strategy = st.uuids().map(str)

# 错误信息：非空字符串，模拟真实错误消息
_error_message_strategy = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        whitelist_characters="：。，！？- ",
    ),
)


# ---------------------------------------------------------------------------
# Bug Condition 探索性测试
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    task_id=_task_id_strategy,
    error_message=_error_message_strategy,
)
@pytest.mark.asyncio
async def test_bug_condition_update_progress_stores_error_message(
    task_id: str,
    error_message: str,
) -> None:
    """
    Property 1: Bug Condition — _update_progress 应存储 error_message

    **Validates: Requirements 1.5**

    GIVEN 任意 task_id 和非空 error_message
    WHEN 调用 _update_progress(task_id, status="failed", error_message=error_message)
    THEN Redis 进度数据应包含 error_message 字段，值等于传入的 error_message

    isBugCondition: task.status=="failed" AND error_message is undefined

    在未修复代码上：_update_progress() 不接受 error_message 参数，
    Redis 数据无 error_message 字段，此测试应失败。
    """
    stored_data: dict = {}

    async def mock_cache_get(key: str) -> str | None:
        """模拟 Redis 读取：返回已存储的进度数据"""
        if stored_data:
            return json.dumps(stored_data)
        return None

    async def mock_cache_set(key: str, value: str, ex: int | None = None) -> None:
        """模拟 Redis 写入：捕获写入的数据"""
        nonlocal stored_data
        stored_data = json.loads(value)

    with patch("app.tasks.tushare_import._redis_get", side_effect=mock_cache_get), \
         patch("app.tasks.tushare_import._redis_set", side_effect=mock_cache_set):

        # 调用 _update_progress 并传入 error_message
        await _update_progress(
            task_id,
            status="failed",
            error_message=error_message,
        )

    # 断言 Redis 数据包含 error_message 字段
    assert "error_message" in stored_data, (
        f"Redis 进度数据缺少 error_message 字段。"
        f"存储的数据: {stored_data}。"
        f"Bug: _update_progress() 不接受或不存储 error_message 参数"
    )

    assert stored_data["error_message"] == error_message, (
        f"error_message 值不匹配。"
        f"期望: {error_message!r}，实际: {stored_data.get('error_message')!r}"
    )

    # 同时验证 status 正确
    assert stored_data["status"] == "failed", (
        f"status 应为 'failed'，实际为 {stored_data.get('status')!r}"
    )


# ---------------------------------------------------------------------------
# Preservation 属性测试：_update_progress / get_import_status 基线行为
# ---------------------------------------------------------------------------

# 以下测试在未修复代码上运行并通过，建立基线行为。
# 修复后重新运行以确认无回归。


# Hypothesis 策略：进度字段
_status_strategy = st.sampled_from(["pending", "running", "completed", "failed", "stopped"])
_total_strategy = st.integers(min_value=0, max_value=100000)
_completed_strategy = st.integers(min_value=0, max_value=100000)
_failed_strategy = st.integers(min_value=0, max_value=10000)
_current_item_strategy = st.text(
    min_size=0,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters="._- ",
    ),
)


@settings(max_examples=50)
@given(
    task_id=_task_id_strategy,
    status=_status_strategy,
    total=_total_strategy,
    completed=_completed_strategy,
    failed=_failed_strategy,
    current_item=_current_item_strategy,
)
@pytest.mark.asyncio
async def test_preservation_update_progress_roundtrip(
    task_id: str,
    status: str,
    total: int,
    completed: int,
    failed: int,
    current_item: str,
) -> None:
    """
    Preservation: _update_progress 写入后 get_import_status 正确读取

    **Validates: Requirements 3.3, 3.4, 3.5**

    GIVEN 任意 status/total/completed/failed/current_item 组合
    WHEN 调用 _update_progress(task_id, status, total, completed, failed, current_item)
    THEN get_import_status(task_id) 返回的字段值与写入值一致

    此测试验证现有的进度写入/读取往返行为在修复前后保持不变。
    """
    from app.services.data_engine.tushare_import_service import TushareImportService

    # 模拟 Redis 存储
    redis_store: dict[str, str] = {}

    async def mock_cache_get(key: str) -> str | None:
        return redis_store.get(key)

    async def mock_cache_set(key: str, value: str, ex: int | None = None) -> None:
        redis_store[key] = value

    with patch("app.tasks.tushare_import._redis_get", side_effect=mock_cache_get), \
         patch("app.tasks.tushare_import._redis_set", side_effect=mock_cache_set), \
         patch("app.services.data_engine.tushare_import_service.cache_get", side_effect=mock_cache_get), \
         patch("app.services.data_engine.tushare_import_service.cache_set", side_effect=mock_cache_set):

        # 写入进度
        await _update_progress(
            task_id,
            status=status,
            total=total,
            completed=completed,
            failed=failed,
            current_item=current_item,
        )

        # 通过 get_import_status 读取
        service = TushareImportService()
        result = await service.get_import_status(task_id)

    # 验证读取的字段与写入值一致
    assert result["status"] == status, (
        f"status 不匹配: 写入 {status!r}, 读取 {result['status']!r}"
    )
    assert result["total"] == total, (
        f"total 不匹配: 写入 {total}, 读取 {result['total']}"
    )
    # completed 使用 max(current, new) 逻辑，从空状态开始等于 completed
    assert result["completed"] == completed, (
        f"completed 不匹配: 写入 {completed}, 读取 {result['completed']}"
    )
    assert result["failed"] == failed, (
        f"failed 不匹配: 写入 {failed}, 读取 {result['failed']}"
    )
    assert result["current_item"] == current_item, (
        f"current_item 不匹配: 写入 {current_item!r}, 读取 {result['current_item']!r}"
    )
