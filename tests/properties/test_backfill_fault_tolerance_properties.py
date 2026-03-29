# Feature: a-share-quant-trading-system, Property 65: 单只股票失败不中断任务且 failed 计数正确
"""
回填任务容错性 属性测试（Hypothesis）

属性 65：单只股票失败不中断任务且 failed 计数正确

**Validates: Requirements 25.11**

对任意长度为 N 的股票列表，其中 K 只股票的 DataSourceRouter 调用失败
（抛出 DataSourceUnavailableError），任务完成后：
- completed + failed == N
- failed == K
- completed == N - K
- status == "completed"（任务不因单只股票失败而中断）
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.base_adapter import DataSourceUnavailableError

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 生成有效的 A 股股票代码（2-20 个）
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_symbols_st = st.lists(_symbol_st, min_size=2, max_size=20, unique=True)


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
# Property 65: kline 回填——单只股票失败不中断任务且 failed 计数正确
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_kline_backfill_single_stock_failure_does_not_interrupt_and_failed_count_correct(
    data,
):
    """
    # Feature: a-share-quant-trading-system, Property 65: 单只股票失败不中断任务且 failed 计数正确

    **Validates: Requirements 25.11**

    对任意长度 N 的股票列表（2-20），随机选择 K 只股票失败（DataSourceUnavailableError），
    验证 _sync_historical_kline 完成后：
    - completed + failed == N
    - failed == K
    - completed == N - K
    - status == "completed"
    """
    symbols = data.draw(_symbols_st, label="symbols")
    n = len(symbols)

    # Draw a random subset of symbols that will fail
    fail_indices = data.draw(
        st.lists(
            st.integers(min_value=0, max_value=n - 1),
            min_size=0,
            max_size=n,
            unique=True,
        ),
        label="fail_indices",
    )
    fail_symbols = {symbols[i] for i in fail_indices}
    k = len(fail_symbols)

    mock_cache_get, mock_cache_set = _make_redis_mocks()

    fake_bar = MagicMock()
    mock_router = AsyncMock()

    # Side effect: raise DataSourceUnavailableError for failing symbols
    async def _fetch_kline_side_effect(symbol, freq, start, end):
        if symbol in fail_symbols:
            raise DataSourceUnavailableError(f"模拟失败: {symbol}")
        return [fake_bar]

    mock_router.fetch_kline = AsyncMock(side_effect=_fetch_kline_side_effect)

    mock_repo = AsyncMock()
    mock_repo.bulk_insert.return_value = 1

    async def _run():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                symbols, "2024-01-01", "2024-01-31", "1d",
            )
        return result

    result = asyncio.run(_run())

    # Core assertions: fault tolerance
    assert result["completed"] + result["failed"] == n, (
        f"completed({result['completed']}) + failed({result['failed']}) != N({n})"
    )
    assert result["failed"] == k, (
        f"failed({result['failed']}) != K({k})"
    )
    assert result["completed"] == n - k, (
        f"completed({result['completed']}) != N-K({n - k})"
    )
    # Task finishes despite individual failures
    assert result["status"] == "completed", (
        f"status should be 'completed' but got '{result['status']}'"
    )
