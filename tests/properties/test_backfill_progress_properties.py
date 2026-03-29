# Feature: a-share-quant-trading-system, Property 64: 进度追踪 Redis 读写一致性
"""
进度追踪 Redis 读写一致性 属性测试（Hypothesis）

属性 64：进度追踪 Redis 读写一致性

**Validates: Requirements 25.9, 25.10**

对任意回填进度状态，验证写入 Redis 后通过 BackfillService.get_progress()
读取的各字段值与写入值一致。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.backfill_service import BackfillService, REDIS_KEY

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

_status_st = st.sampled_from(["pending", "running", "completed", "failed"])
_data_types_st = st.lists(
    st.sampled_from(["kline", "fundamentals", "money_flow"]),
    min_size=0,
    max_size=3,
    unique=True,
)
_symbol_st = st.from_regex(r"[036]\d{5}", fullmatch=True)

# Generate arbitrary progress state dicts
_progress_st = st.fixed_dictionaries({
    "total": st.integers(min_value=0, max_value=5000),
    "completed": st.integers(min_value=0, max_value=5000),
    "failed": st.integers(min_value=0, max_value=500),
    "current_symbol": st.one_of(st.just(""), _symbol_st),
    "status": _status_st,
    "data_types": _data_types_st,
})


# ---------------------------------------------------------------------------
# Property 64: Redis 读写一致性
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50, deadline=None)
@given(progress=_progress_st)
def test_progress_write_then_read_consistent(progress: dict):
    """
    # Feature: a-share-quant-trading-system, Property 64: 进度追踪 Redis 读写一致性

    **Validates: Requirements 25.9, 25.10**

    对任意回填进度状态字典：
    1. 将其 JSON 序列化后通过 cache_set 写入 Redis
    2. 通过 BackfillService.get_progress() 读取
    3. 读取结果的 total/completed/failed/current_symbol/status/data_types 字段
       与写入值完全一致
    """
    service = BackfillService()

    # Simulate Redis as an in-memory store
    redis_store: dict[str, str] = {}

    async def fake_cache_set(key: str, value, ex=None):
        redis_store[key] = value

    async def fake_cache_get(key: str):
        return redis_store.get(key)

    async def _run():
        with patch("app.services.data_engine.backfill_service.cache_set", side_effect=fake_cache_set), \
             patch("app.services.data_engine.backfill_service.cache_get", side_effect=fake_cache_get):
            # Write progress to Redis
            await fake_cache_set(REDIS_KEY, json.dumps(progress))
            # Read it back via get_progress
            return await service.get_progress()

    result = asyncio.run(_run())

    # All key fields must match
    assert result["total"] == progress["total"]
    assert result["completed"] == progress["completed"]
    assert result["failed"] == progress["failed"]
    assert result["current_symbol"] == progress["current_symbol"]
    assert result["status"] == progress["status"]
    assert result["data_types"] == progress["data_types"]


@hyp_settings(max_examples=20, deadline=None)
@given(st.data())
def test_progress_returns_idle_when_redis_empty(data):
    """
    # Feature: a-share-quant-trading-system, Property 64: 进度追踪 Redis 读写一致性

    **Validates: Requirements 25.9**

    当 Redis 中无进度数据时，get_progress() 应返回 idle 默认值。
    """
    service = BackfillService()

    mock_cache_get = AsyncMock(return_value=None)

    async def _run():
        with patch("app.services.data_engine.backfill_service.cache_get", mock_cache_get):
            return await service.get_progress()

    result = asyncio.run(_run())

    assert result["total"] == 0
    assert result["completed"] == 0
    assert result["failed"] == 0
    assert result["current_symbol"] == ""
    assert result["status"] == "idle"
    assert result["data_types"] == []
