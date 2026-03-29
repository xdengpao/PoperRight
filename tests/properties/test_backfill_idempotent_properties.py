# Feature: a-share-quant-trading-system, Property 63: 回填操作幂等性
"""
回填操作幂等性 属性测试（Hypothesis）

属性 63：回填操作幂等性

**Validates: Requirements 25.8**

对任意股票列表和日期范围，执行两次回填后的数据库状态应与执行一次完全相同。
- K 线：KlineRepository.bulk_insert 使用 ON CONFLICT DO NOTHING，两次调用接收相同数据
- 基本面：AsyncSessionPG 执行相同的 ON CONFLICT DO UPDATE upsert SQL
- 资金流向：AsyncSessionPG 执行相同的 ON CONFLICT DO UPDATE upsert SQL

验证方式：运行 _sync_historical_kline / _sync_historical_fundamentals /
_sync_historical_money_flow 两次，确认 router 调用次数翻倍（每次运行相同），
bulk_insert / session.execute 接收的数据两次完全一致。
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_symbols_st = st.lists(_symbol_st, min_size=1, max_size=5, unique=True)
_freq_st = st.sampled_from(["1d", "1w", "1M"])


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _make_redis_mocks():
    """返回 (mock_cache_get, mock_cache_set) 用于 patch Redis。"""
    mock_cache_get = AsyncMock(return_value=json.dumps({
        "status": "pending", "total": 0, "completed": 0,
        "failed": 0, "current_symbol": "",
    }))
    mock_cache_set = AsyncMock()
    return mock_cache_get, mock_cache_set


def _make_fundamentals_data(symbol: str) -> MagicMock:
    """构造一个 FundamentalsData mock 对象。"""
    return MagicMock(
        symbol=symbol, name="测试", market="SZ", board="主板",
        list_date=None, is_st=False, is_delisted=False,
        pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
        market_cap=None, updated_at=None,
    )


def _make_money_flow_data(symbol: str, trade_date: date) -> MagicMock:
    """构造一个 MoneyFlowData mock 对象。"""
    return MagicMock(
        symbol=symbol, trade_date=trade_date,
        main_net_inflow=None, main_inflow=None, main_outflow=None,
        main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
        north_net_inflow=None, north_hold_ratio=None,
        on_dragon_tiger=False, dragon_tiger_net=None,
        block_trade_amount=None, block_trade_discount=None,
        bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
    )


def _make_pg_session_mock():
    """构造 AsyncSessionPG 的 mock 上下文管理器。"""
    mock_session = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_session


# ---------------------------------------------------------------------------
# Property 63a: kline 回填幂等性 — 两次运行 router 和 bulk_insert 接收相同数据
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st, freq=_freq_st)
def test_kline_backfill_idempotent(symbols: list[str], freq: str):
    """
    # Feature: a-share-quant-trading-system, Property 63: 回填操作幂等性

    **Validates: Requirements 25.8**

    对任意非空股票列表和合法频率，运行 _sync_historical_kline 两次：
    - router.fetch_kline 调用次数应翻倍（第二次与第一次相同）
    - bulk_insert 两次接收的 bars 数据完全一致
    - 两次运行结果的 completed/failed 相同
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    fake_bar = MagicMock()
    mock_router = AsyncMock()
    mock_router.fetch_kline.return_value = [fake_bar]

    mock_repo = AsyncMock()
    mock_repo.bulk_insert.return_value = 1

    async def _run_once():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_kline
            return await _sync_historical_kline(
                symbols, "2024-01-01", "2024-01-31", freq,
            )

    # ── Run 1 ──
    result1 = asyncio.run(_run_once())
    router_calls_after_run1 = mock_router.fetch_kline.call_count
    bulk_calls_after_run1 = mock_repo.bulk_insert.call_count
    bulk_args_run1 = [c.args for c in mock_repo.bulk_insert.call_args_list]

    # ── Run 2 (same params, same mocks) ──
    result2 = asyncio.run(_run_once())
    router_calls_after_run2 = mock_router.fetch_kline.call_count
    bulk_calls_after_run2 = mock_repo.bulk_insert.call_count
    bulk_args_run2 = [c.args for c in mock_repo.bulk_insert.call_args_list[bulk_calls_after_run1:]]

    n = len(symbols)

    # Router called same number of times each run
    assert router_calls_after_run1 == n
    assert router_calls_after_run2 == 2 * n

    # bulk_insert called same number of times each run
    assert bulk_calls_after_run1 == n
    assert bulk_calls_after_run2 == 2 * n

    # bulk_insert received identical data both runs
    assert bulk_args_run1 == bulk_args_run2

    # Both runs produce identical result counts
    assert result1["completed"] == result2["completed"] == n
    assert result1["failed"] == result2["failed"] == 0
    assert result1["status"] == result2["status"] == "completed"


# ---------------------------------------------------------------------------
# Property 63b: fundamentals 回填幂等性 — 两次运行 upsert 接收相同数据
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st)
def test_fundamentals_backfill_idempotent(symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 63: 回填操作幂等性

    **Validates: Requirements 25.8**

    对任意非空股票列表，运行 _sync_historical_fundamentals 两次：
    - router.fetch_fundamentals 调用次数应翻倍
    - session.execute 两次接收的 upsert 参数完全一致
    - ON CONFLICT DO UPDATE 保证幂等
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    # Build deterministic side_effect that repeats for both runs
    fundamentals_mocks = [_make_fundamentals_data(s) for s in symbols]
    mock_router = AsyncMock()
    mock_router.fetch_fundamentals.side_effect = fundamentals_mocks * 2  # enough for 2 runs

    mock_ctx, mock_session = _make_pg_session_mock()

    async def _run_once():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_ctx), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_fundamentals
            return await _sync_historical_fundamentals(
                symbols, "2024-01-01", "2024-01-31",
            )

    # ── Run 1 ──
    result1 = asyncio.run(_run_once())
    router_calls_after_run1 = mock_router.fetch_fundamentals.call_count
    execute_calls_after_run1 = mock_session.execute.call_count
    execute_args_run1 = [c.args[1] for c in mock_session.execute.call_args_list[:execute_calls_after_run1]]

    # ── Run 2 ──
    result2 = asyncio.run(_run_once())
    router_calls_after_run2 = mock_router.fetch_fundamentals.call_count
    execute_calls_after_run2 = mock_session.execute.call_count
    execute_args_run2 = [
        c.args[1]
        for c in mock_session.execute.call_args_list[execute_calls_after_run1:execute_calls_after_run2]
    ]

    n = len(symbols)

    # Router called same number of times each run
    assert router_calls_after_run1 == n
    assert router_calls_after_run2 == 2 * n

    # session.execute called same number of times each run
    assert execute_calls_after_run1 == n
    assert execute_calls_after_run2 == 2 * n

    # Upsert params identical both runs (same data → ON CONFLICT DO UPDATE is idempotent)
    assert execute_args_run1 == execute_args_run2

    # Both runs produce identical result counts
    assert result1["completed"] == result2["completed"]
    assert result1["failed"] == result2["failed"] == 0
    assert result1["upserted"] == result2["upserted"]
    assert result1["status"] == result2["status"] == "completed"


# ---------------------------------------------------------------------------
# Property 63c: money_flow 回填幂等性 — 两次运行 upsert 接收相同数据
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st)
def test_money_flow_backfill_idempotent(symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 63: 回填操作幂等性

    **Validates: Requirements 25.8**

    对任意非空股票列表，运行 _sync_historical_money_flow 两次（单个工作日）：
    - router.fetch_money_flow 调用次数应翻倍
    - session.execute 两次接收的 upsert 参数完全一致
    - ON CONFLICT DO UPDATE 保证幂等
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    # Use a single weekday (Monday 2024-01-15) to avoid weekend-skipping complexity
    test_date = date(2024, 1, 15)
    money_flow_mocks = [_make_money_flow_data(s, test_date) for s in symbols]
    mock_router = AsyncMock()
    mock_router.fetch_money_flow.side_effect = money_flow_mocks * 2  # enough for 2 runs

    mock_ctx, mock_session = _make_pg_session_mock()

    async def _run_once():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_ctx), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_money_flow
            return await _sync_historical_money_flow(
                symbols,
                test_date.isoformat(),
                test_date.isoformat(),
            )

    # ── Run 1 ──
    result1 = asyncio.run(_run_once())
    router_calls_after_run1 = mock_router.fetch_money_flow.call_count
    execute_calls_after_run1 = mock_session.execute.call_count
    execute_args_run1 = [c.args[1] for c in mock_session.execute.call_args_list[:execute_calls_after_run1]]

    # ── Run 2 ──
    result2 = asyncio.run(_run_once())
    router_calls_after_run2 = mock_router.fetch_money_flow.call_count
    execute_calls_after_run2 = mock_session.execute.call_count
    execute_args_run2 = [
        c.args[1]
        for c in mock_session.execute.call_args_list[execute_calls_after_run1:execute_calls_after_run2]
    ]

    n = len(symbols)

    # Router called same number of times each run
    assert router_calls_after_run1 == n
    assert router_calls_after_run2 == 2 * n

    # session.execute called same number of times each run
    assert execute_calls_after_run1 == n
    assert execute_calls_after_run2 == 2 * n

    # Upsert params identical both runs
    assert execute_args_run1 == execute_args_run2

    # Both runs produce identical result counts
    assert result1["completed"] == result2["completed"]
    assert result1["failed"] == result2["failed"] == 0
    assert result1["upserted"] == result2["upserted"]
    assert result1["status"] == result2["status"] == "completed"
