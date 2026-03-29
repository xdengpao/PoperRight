# Feature: a-share-quant-trading-system, Property 62: 批次大小不超过 50 且批间延迟 ≥ 1 秒
"""
回填任务批次大小与延迟 属性测试（Hypothesis）

属性 62：批次大小不超过 50 且批间延迟 ≥ 1 秒

**Validates: Requirements 25.7**

对任意长度 N 的股票列表，回填任务应将其分为 ⌈N/50⌉ 个批次，
每批不超过 50 只股票，且相邻批次之间调用 asyncio.sleep(BATCH_DELAY=1.0)。
sleep 调用次数应为 max(0, num_batches - 1)（第一批之前不 sleep）。
"""

from __future__ import annotations

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 生成有效的 A 股股票代码（1-200 个，覆盖多批次场景）
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_symbols_st = st.lists(_symbol_st, min_size=1, max_size=200, unique=True)


# ---------------------------------------------------------------------------
# 辅助：构造 mock 环境
# ---------------------------------------------------------------------------

def _make_redis_mocks():
    """返回 (mock_cache_get, mock_cache_set) 用于 patch Redis。"""
    mock_cache_get = AsyncMock(return_value=json.dumps({
        "status": "pending", "total": 0, "completed": 0,
        "failed": 0, "current_symbol": "",
    }))
    mock_cache_set = AsyncMock()
    return mock_cache_get, mock_cache_set


# ---------------------------------------------------------------------------
# Property 62: 批次大小不超过 50 且批间延迟 ≥ 1 秒
# ---------------------------------------------------------------------------

BATCH_SIZE = 50
BATCH_DELAY = 1.0


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st)
def test_batch_size_and_delay_verification(symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 62: 批次大小与延迟

    **Validates: Requirements 25.7**

    对任意长度 N 的股票列表，验证：
    1. 分为 ⌈N/50⌉ 个批次
    2. 每批不超过 50 只股票
    3. asyncio.sleep(BATCH_DELAY) 调用次数 = max(0, num_batches - 1)
    """
    n = len(symbols)
    expected_num_batches = math.ceil(n / BATCH_SIZE)
    expected_sleep_calls = max(0, expected_num_batches - 1)

    mock_cache_get, mock_cache_set = _make_redis_mocks()

    # Mock router: fetch_kline returns a single fake bar per symbol
    fake_bar = MagicMock()
    mock_router = AsyncMock()
    mock_router.fetch_kline.return_value = [fake_bar]

    # Mock repo: bulk_insert succeeds
    mock_repo = AsyncMock()
    mock_repo.bulk_insert.return_value = 1

    # Track asyncio.sleep calls
    mock_sleep = AsyncMock()

    async def _run():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo), \
             patch("app.tasks.data_sync.asyncio.sleep", mock_sleep):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                symbols, "2024-01-01", "2024-01-31", "1d",
            )
        return result

    result = asyncio.run(_run())

    # ── Verify batch count via router call count ──
    # Each symbol is processed exactly once
    assert mock_router.fetch_kline.call_count == n

    # ── Verify sleep calls = max(0, num_batches - 1) ──
    assert mock_sleep.call_count == expected_sleep_calls, (
        f"Expected {expected_sleep_calls} sleep calls for {n} symbols "
        f"({expected_num_batches} batches), got {mock_sleep.call_count}"
    )

    # ── Verify each sleep call uses BATCH_DELAY ──
    for call in mock_sleep.call_args_list:
        args, kwargs = call
        assert args == (BATCH_DELAY,), (
            f"Expected sleep({BATCH_DELAY}), got sleep{args}"
        )

    # ── Verify all symbols completed ──
    assert result["completed"] == n
    assert result["failed"] == 0
    assert result["status"] == "completed"
