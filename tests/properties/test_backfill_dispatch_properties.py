# Feature: a-share-quant-trading-system, Property 59: 回填 API 按数据类型分发对应 Celery 任务
"""
回填 API 按数据类型分发对应 Celery 任务 属性测试（Hypothesis）

属性 59：回填 API 按数据类型分发对应 Celery 任务

**Validates: Requirements 25.1**

对任意合法 data_types 子集，验证 BackfillService.start_backfill 分发的
Celery 任务集合与请求的 data_types 一一对应。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.backfill_service import BackfillService, _TASK_MAP

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 生成 data_types 的非空子集
_all_types = list(_TASK_MAP.keys())  # ["kline", "fundamentals", "money_flow"]
_data_types_st = st.lists(
    st.sampled_from(_all_types),
    min_size=1,
    max_size=len(_all_types),
    unique=True,
)

# 生成有效的 A 股股票代码列表（用于 symbols 参数）
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_symbols_st = st.lists(_symbol_st, min_size=1, max_size=5, unique=True)


# ---------------------------------------------------------------------------
# Property 59: 分发的 Celery 任务与 data_types 一一对应
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50, deadline=None)
@given(data_types=_data_types_st, symbols=_symbols_st)
def test_dispatched_tasks_match_data_types(data_types: list[str], symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 59: 回填 API 按数据类型分发对应 Celery 任务

    **Validates: Requirements 25.1**

    对任意合法 data_types 子集和非空 symbols 列表：
    - celery_app.send_task 被调用的次数等于 len(data_types)
    - 每个 data_type 对应的 Celery 任务名被调用恰好一次
    - 返回的 task_ids 数量等于 len(data_types)
    """
    service = BackfillService()

    # Mock Redis: no running backfill
    mock_cache_get = AsyncMock(return_value=None)
    mock_cache_set = AsyncMock()

    # Mock celery_app.send_task — return a mock result with unique id per call
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
                data_types=data_types,
                symbols=symbols,
            )

    result = asyncio.run(_run())

    # send_task called exactly once per data_type
    assert mock_celery.send_task.call_count == len(data_types)

    # Collect the task names that were dispatched
    dispatched_task_names = [
        call.args[0] for call in mock_celery.send_task.call_args_list
    ]

    # Each data_type's corresponding task name should appear exactly once
    expected_task_names = [_TASK_MAP[dt] for dt in data_types]
    assert sorted(dispatched_task_names) == sorted(expected_task_names)

    # Returned task_ids count matches
    assert len(result["task_ids"]) == len(data_types)

    # All task_ids are unique
    assert len(set(result["task_ids"])) == len(data_types)
