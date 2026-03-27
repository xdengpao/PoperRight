"""
数据同步定时任务

包含：
- sync_realtime_market：盘中实时行情同步（交易时段 9:30-15:00，每 10 秒）
- sync_fundamentals：盘后基本面数据日更（每日 18:00）
- sync_money_flow：盘后资金数据日更（每日 15:30 后）
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time

from app.core.celery_app import celery_app
from app.tasks.base import DataSyncTask

logger = logging.getLogger(__name__)

# A股交易时段
TRADING_START = time(9, 30)
TRADING_END = time(15, 0)

# 默认同步的股票列表（实际生产中从数据库/缓存获取全市场股票列表）
DEFAULT_SYMBOLS = [
    "000001.SZ", "000002.SZ", "600000.SH", "600519.SH",
]


def _is_trading_hours(now: datetime | None = None) -> bool:
    """判断当前是否在交易时段（9:30-15:00，周一至周五）。"""
    now = now or datetime.now()
    # 周六=5, 周日=6
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    return TRADING_START <= current_time <= TRADING_END


def _run_async(coro):
    """在同步 Celery worker 中运行异步协程。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 盘中实时行情同步任务
# ---------------------------------------------------------------------------

@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.data_sync.sync_realtime_market",
    bind=True,
    queue="data_sync",
)
def sync_realtime_market(self, symbols: list[str] | None = None) -> dict:
    """
    盘中实时行情同步任务。

    由 Celery Beat 每 10 秒调度一次。
    仅在交易时段（9:30-15:00，工作日）执行实际同步，
    非交易时段直接跳过。

    流程：
    1. 检查是否在交易时段
    2. 通过 MarketDataClient 拉取实时快照行情
    3. 解析为 KlineBar 并通过 KlineRepository 批量写入

    Args:
        symbols: 要同步的股票代码列表，默认使用全市场列表

    Returns:
        同步结果摘要字典
    """
    if not _is_trading_hours():
        logger.debug("非交易时段，跳过实时行情同步")
        return {"status": "skipped", "reason": "outside_trading_hours"}

    symbols = symbols or DEFAULT_SYMBOLS
    logger.info("开始实时行情同步，共 %d 只股票", len(symbols))

    async def _sync():
        from app.services.data_engine.market_adapter import MarketDataClient
        from app.services.data_engine.kline_repository import KlineRepository

        async with MarketDataClient() as client:
            raw_quotes = await client.fetch_realtime_quote(symbols)
            bars = client._parse_kline_response(raw_quotes, symbol="", freq="1m")
            # 修正 symbol（实时快照每条数据自带 symbol 字段）
            for item, bar in zip(raw_quotes, bars):
                if not bar.symbol:
                    bar.symbol = str(item.get("symbol", ""))

        if bars:
            repo = KlineRepository()
            inserted = await repo.bulk_insert(bars)
            logger.info("实时行情同步完成，获取 %d 条，写入 %d 条", len(bars), inserted)
            return {"status": "success", "fetched": len(bars), "inserted": inserted}

        return {"status": "success", "fetched": 0, "inserted": 0}

    return _run_async(_sync())


# ---------------------------------------------------------------------------
# 盘后基本面数据日更任务
# ---------------------------------------------------------------------------

@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.data_sync.sync_fundamentals",
    bind=True,
    queue="data_sync",
)
def sync_fundamentals(self, symbols: list[str] | None = None) -> dict:
    """
    盘后基本面数据日更任务。

    由 Celery Beat 每个交易日 18:00 调度。
    通过 FundamentalAdapter 拉取个股基本面数据并写入 stock_info 表。

    Args:
        symbols: 要同步的股票代码列表，默认使用全市场列表

    Returns:
        同步结果摘要字典
    """
    symbols = symbols or DEFAULT_SYMBOLS
    logger.info("开始基本面数据同步，共 %d 只股票", len(symbols))

    async def _sync():
        from app.services.data_engine.fundamental_adapter import FundamentalAdapter
        from app.core.database import AsyncSessionPG

        success_count = 0
        error_count = 0

        async with FundamentalAdapter() as adapter:
            for symbol in symbols:
                try:
                    async with AsyncSessionPG() as session:
                        await adapter.sync_stock_info(symbol, session)
                    success_count += 1
                except Exception as exc:
                    logger.error("基本面同步失败 symbol=%s: %s", symbol, exc)
                    error_count += 1

        logger.info(
            "基本面数据同步完成，成功 %d，失败 %d",
            success_count, error_count,
        )
        return {
            "status": "success",
            "total": len(symbols),
            "success": success_count,
            "errors": error_count,
        }

    return _run_async(_sync())


# ---------------------------------------------------------------------------
# 盘后资金数据日更任务
# ---------------------------------------------------------------------------

@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.data_sync.sync_money_flow",
    bind=True,
    queue="data_sync",
)
def sync_money_flow(self, symbols: list[str] | None = None) -> dict:
    """
    盘后资金数据日更任务。

    由 Celery Beat 每个交易日 15:30 后调度。
    通过 MoneyFlowAdapter 拉取个股资金流向和大盘概览数据。

    Args:
        symbols: 要同步的股票代码列表，默认使用全市场列表

    Returns:
        同步结果摘要字典
    """
    symbols = symbols or DEFAULT_SYMBOLS
    trade_date = date.today()
    logger.info("开始资金数据同步 date=%s，共 %d 只股票", trade_date, len(symbols))

    async def _sync():
        from app.services.data_engine.money_flow_adapter import MoneyFlowAdapter

        success_count = 0
        error_count = 0

        async with MoneyFlowAdapter() as adapter:
            # 同步大盘概览
            try:
                await adapter.fetch_market_overview(trade_date)
                logger.info("大盘概览数据同步完成 date=%s", trade_date)
            except Exception as exc:
                logger.error("大盘概览同步失败 date=%s: %s", trade_date, exc)

            # 同步个股资金流向
            for symbol in symbols:
                try:
                    await adapter.fetch_money_flow(symbol, trade_date)
                    success_count += 1
                except Exception as exc:
                    logger.error("资金数据同步失败 symbol=%s: %s", symbol, exc)
                    error_count += 1

        logger.info(
            "资金数据同步完成 date=%s，成功 %d，失败 %d",
            trade_date, success_count, error_count,
        )
        return {
            "status": "success",
            "trade_date": str(trade_date),
            "total": len(symbols),
            "success": success_count,
            "errors": error_count,
        }

    return _run_async(_sync())
