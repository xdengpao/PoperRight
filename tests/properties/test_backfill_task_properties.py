# Feature: a-share-quant-trading-system, Property 61: 回填任务通过 DataSourceRouter 获取数据并写入正确存储
"""
回填任务数据流正确性 属性测试（Hypothesis）

属性 61：回填任务通过 DataSourceRouter 获取数据并写入正确存储

**Validates: Requirements 25.4, 25.5, 25.6**

对任意数据类型（kline / fundamentals / money_flow）和任意非空股票列表，
对应的回填任务应对每只股票调用 DataSourceRouter 的相应方法获取数据，
并将结果写入对应存储：
- kline → TimescaleDB via KlineRepository.bulk_insert
- fundamentals → PostgreSQL via AsyncSessionPG
- money_flow → PostgreSQL via AsyncSessionPG
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

# 生成有效的 A 股股票代码（1-5 个）
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_symbols_st = st.lists(_symbol_st, min_size=1, max_size=5, unique=True)

# K 线频率
_freq_st = st.sampled_from(["1d", "1w", "1M"])


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
# Property 61a: kline 回填调用 router.fetch_kline + KlineRepository.bulk_insert
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st, freq=_freq_st)
def test_kline_backfill_calls_router_fetch_kline_and_repo_bulk_insert(
    symbols: list[str], freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 61: 回填任务数据流正确性

    **Validates: Requirements 25.4**

    对任意非空股票列表和合法频率，_sync_historical_kline 应对每只股票
    调用 router.fetch_kline，并将返回的 bars 通过 KlineRepository.bulk_insert 写入。
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    fake_bar = MagicMock()
    mock_router = AsyncMock()
    mock_router.fetch_kline.return_value = [fake_bar]

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
                symbols, "2024-01-01", "2024-01-31", freq,
            )
        return result

    result = asyncio.run(_run())

    # router.fetch_kline called once per symbol
    assert mock_router.fetch_kline.call_count == len(symbols)
    for symbol in symbols:
        mock_router.fetch_kline.assert_any_call(
            symbol, freq,
            date(2024, 1, 1), date(2024, 1, 31),
        )

    # KlineRepository.bulk_insert called once per symbol (each returned non-empty bars)
    assert mock_repo.bulk_insert.call_count == len(symbols)

    # Result should reflect all completed
    assert result["completed"] == len(symbols)
    assert result["failed"] == 0
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Property 61b: fundamentals 回填调用 router.fetch_fundamentals + AsyncSessionPG
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st)
def test_fundamentals_backfill_calls_router_and_pg_session(
    symbols: list[str],
):
    """
    # Feature: a-share-quant-trading-system, Property 61: 回填任务数据流正确性

    **Validates: Requirements 25.5**

    对任意非空股票列表，_sync_historical_fundamentals 应对每只股票
    调用 router.fetch_fundamentals，并通过 AsyncSessionPG 执行 upsert 写入 PostgreSQL。
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    # Build side_effect: one FundamentalsData mock per symbol
    fundamentals_mocks = [_make_fundamentals_data(s) for s in symbols]
    mock_router = AsyncMock()
    mock_router.fetch_fundamentals.side_effect = fundamentals_mocks

    mock_ctx, mock_session = _make_pg_session_mock()

    async def _run():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_ctx), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_fundamentals
            result = await _sync_historical_fundamentals(
                symbols, "2024-01-01", "2024-01-31",
            )
        return result

    result = asyncio.run(_run())

    # router.fetch_fundamentals called once per symbol
    assert mock_router.fetch_fundamentals.call_count == len(symbols)
    for symbol in symbols:
        mock_router.fetch_fundamentals.assert_any_call(symbol)

    # AsyncSessionPG session.execute called once per symbol (upsert)
    assert mock_session.execute.call_count == len(symbols)
    # AsyncSessionPG session.commit called once per symbol
    assert mock_session.commit.call_count == len(symbols)

    assert result["completed"] == len(symbols)
    assert result["failed"] == 0
    assert result["upserted"] == len(symbols)
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Property 61c: money_flow 回填调用 router.fetch_money_flow + AsyncSessionPG
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=100, deadline=None)
@given(symbols=_symbols_st)
def test_money_flow_backfill_calls_router_and_pg_session(
    symbols: list[str],
):
    """
    # Feature: a-share-quant-trading-system, Property 61: 回填任务数据流正确性

    **Validates: Requirements 25.6**

    对任意非空股票列表，_sync_historical_money_flow 应对每只股票
    调用 router.fetch_money_flow，并通过 AsyncSessionPG 执行 upsert 写入 PostgreSQL。
    使用单个工作日日期范围以简化测试（避免周末跳过逻辑干扰）。
    """
    mock_cache_get, mock_cache_set = _make_redis_mocks()

    # Use a single weekday (Monday 2024-01-15) to avoid weekend-skipping complexity
    test_date = date(2024, 1, 15)
    money_flow_mocks = [_make_money_flow_data(s, test_date) for s in symbols]
    mock_router = AsyncMock()
    mock_router.fetch_money_flow.side_effect = money_flow_mocks

    mock_ctx, mock_session = _make_pg_session_mock()

    async def _run():
        with patch("app.tasks.data_sync.cache_get", mock_cache_get), \
             patch("app.tasks.data_sync.cache_set", mock_cache_set), \
             patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_ctx), \
             patch("app.tasks.data_sync.asyncio.sleep", new_callable=AsyncMock):
            from app.tasks.data_sync import _sync_historical_money_flow
            result = await _sync_historical_money_flow(
                symbols,
                test_date.isoformat(),
                test_date.isoformat(),
            )
        return result

    result = asyncio.run(_run())

    # router.fetch_money_flow called once per symbol (single weekday)
    assert mock_router.fetch_money_flow.call_count == len(symbols)
    for symbol in symbols:
        mock_router.fetch_money_flow.assert_any_call(symbol, test_date)

    # AsyncSessionPG session.execute called once per symbol
    assert mock_session.execute.call_count == len(symbols)
    assert mock_session.commit.call_count == len(symbols)

    assert result["completed"] == len(symbols)
    assert result["failed"] == 0
    assert result["upserted"] == len(symbols)
    assert result["status"] == "completed"
