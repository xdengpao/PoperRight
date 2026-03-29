# Feature: a-share-quant-trading-system, Property 66: 并发保护——运行中拒绝新请求
"""
并发保护——运行中拒绝新请求 属性测试（Hypothesis）

属性 66：并发保护——运行中拒绝新请求

**Validates: Requirements 25.12**

对任意 Redis 中 status 为 running 的状态，验证 POST /backfill 返回 HTTP 409
且不分发新的 Celery 任务。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.backfill_service import BackfillService

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

_symbol_st = st.from_regex(r"[036]\d{5}", fullmatch=True)
_data_types_st = st.lists(
    st.sampled_from(["kline", "fundamentals", "money_flow"]),
    min_size=1,
    max_size=3,
    unique=True,
)

# Generate arbitrary running progress states
_running_progress_st = st.fixed_dictionaries({
    "total": st.integers(min_value=1, max_value=5000),
    "completed": st.integers(min_value=0, max_value=4999),
    "failed": st.integers(min_value=0, max_value=100),
    "current_symbol": _symbol_st,
    "status": st.just("running"),
    "data_types": _data_types_st,
})


# ---------------------------------------------------------------------------
# Property 66: 运行中拒绝新请求
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50, deadline=None)
@given(
    running_progress=_running_progress_st,
    request_data_types=_data_types_st,
)
def test_running_status_rejects_new_backfill(
    running_progress: dict,
    request_data_types: list[str],
):
    """
    # Feature: a-share-quant-trading-system, Property 66: 并发保护——运行中拒绝新请求

    **Validates: Requirements 25.12**

    对任意 Redis 中 status=running 的进度状态和任意新回填请求：
    - BackfillService.start_backfill 应抛出 RuntimeError
    - celery_app.send_task 不应被调用（不分发新任务）
    """
    service = BackfillService()

    # Redis returns a running progress
    mock_cache_get = AsyncMock(return_value=json.dumps(running_progress))
    mock_cache_set = AsyncMock()

    # Celery mock — should NOT be called
    mock_celery = MagicMock()

    async def _run():
        with patch("app.services.data_engine.backfill_service.cache_get", mock_cache_get), \
             patch("app.services.data_engine.backfill_service.cache_set", mock_cache_set), \
             patch("app.core.celery_app.celery_app", mock_celery):
            return await service.start_backfill(
                data_types=request_data_types,
                symbols=["000001.SZ"],  # minimal valid symbols
            )

    # Should raise RuntimeError
    raised = False
    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        raised = True
        assert "已有回填任务正在执行" in str(exc)

    assert raised, "Expected RuntimeError for concurrent backfill but none was raised"

    # Celery send_task must NOT have been called
    mock_celery.send_task.assert_not_called()

    # Redis cache_set must NOT have been called (no progress init for rejected request)
    mock_cache_set.assert_not_called()


@hyp_settings(max_examples=30, deadline=None)
@given(request_data_types=_data_types_st)
def test_non_running_status_allows_new_backfill(request_data_types: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 66: 并发保护——运行中拒绝新请求

    **Validates: Requirements 25.12**

    当 Redis 中无进度数据（None）时，新回填请求应被接受（不抛出 RuntimeError）。
    """
    service = BackfillService()

    mock_cache_get = AsyncMock(return_value=None)
    mock_cache_set = AsyncMock()

    mock_celery = MagicMock()
    task_counter = {"n": 0}

    def _fake_send_task(task_name, **kwargs):
        task_counter["n"] += 1
        result = MagicMock()
        result.id = f"task-{task_counter['n']}"
        return result

    mock_celery.send_task.side_effect = _fake_send_task

    async def _run():
        with patch("app.services.data_engine.backfill_service.cache_get", mock_cache_get), \
             patch("app.services.data_engine.backfill_service.cache_set", mock_cache_set), \
             patch("app.core.celery_app.celery_app", mock_celery):
            return await service.start_backfill(
                data_types=request_data_types,
                symbols=["000001.SZ"],
            )

    # Should NOT raise
    result = asyncio.run(_run())

    # Tasks should have been dispatched
    assert mock_celery.send_task.call_count == len(request_data_types)
    assert len(result["task_ids"]) == len(request_data_types)
