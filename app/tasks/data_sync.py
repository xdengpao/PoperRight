"""
数据同步定时任务

包含：
- sync_realtime_market：盘中实时行情同步（交易时段 9:30-15:00，每 10 秒）
- sync_fundamentals：盘后基本面数据日更（每日 18:00）
- sync_money_flow：盘后资金数据日更（每日 15:30 后）

故障转移：
- sync_fundamentals 和 sync_money_flow 优先通过 DataSourceRouter 获取数据
  （Tushare → AkShare 自动故障转移），DataSourceRouter 不可用时回退至原有适配器
- 对应需求 1.9（Tushare 失败自动切换 AkShare）和 1.10（双源不可用时告警）
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, time, timedelta

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import cache_get, cache_set
from app.services.data_engine.backfill_service import (
    BATCH_SIZE,
    BATCH_DELAY,
    REDIS_KEY,
    STOP_SIGNAL_KEY,
    PROGRESS_TTL,
)
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.data_source_router import DataSourceRouter
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


async def _update_sync_status(
    data_type: str,
    source_label: str,
    status: str,
    record_count: int,
    data_source: str,
    is_fallback: bool,
) -> None:
    """将同步状态写入 Redis 缓存，24 小时过期。"""
    await cache_set(
        f"sync:status:{data_type}",
        json.dumps({
            "source": source_label,
            "last_sync_at": datetime.now().isoformat(),
            "status": status,
            "record_count": record_count,
            "data_source": data_source,
            "is_fallback": is_fallback,
        }),
        ex=86400,
    )


def _get_data_source_router() -> DataSourceRouter:
    """创建 DataSourceRouter 实例（Tushare 主 → AkShare 备，带故障转移）。

    DataSourceRouter 内部自动从 Settings 读取 Tushare/AkShare 配置，
    并在 Tushare 失败时自动切换至 AkShare（需求 1.9），
    双源均不可用时推送告警并抛出 DataSourceUnavailableError（需求 1.10）。
    """
    return DataSourceRouter()


async def _check_stop_signal() -> bool:
    """检查独立停止信号键，不依赖 progress 的 status 字段。

    返回 True 表示应该停止。
    """
    signal = await cache_get(STOP_SIGNAL_KEY)
    return signal is not None


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
    # 行情 API 未配置时跳过（避免无效连接错误）
    if not settings.market_data_api_key or "localhost" in settings.market_data_api_url:
        logger.debug("行情 API 未配置，跳过实时行情同步")
        return {"status": "skipped", "reason": "market_api_not_configured"}

    if not _is_trading_hours():
        logger.debug("非交易时段，跳过实时行情同步")
        _run_async(_update_sync_status(
            "kline", "行情数据", "OK", 0,
            "MarketDataClient", False,
        ))
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
            await _update_sync_status(
                "kline", "行情数据", "OK", inserted,
                "MarketDataClient", False,
            )
            return {"status": "success", "fetched": len(bars), "inserted": inserted}

        await _update_sync_status(
            "kline", "行情数据", "OK", 0,
            "MarketDataClient", False,
        )
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
    优先通过 DataSourceRouter 获取基本面数据（Tushare → AkShare 故障转移），
    DataSourceRouter 不可用时回退至 FundamentalAdapter。

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

        router = _get_data_source_router()
        success_count = 0
        error_count = 0
        last_data_source = "N/A"
        last_is_fallback = False

        for symbol in symbols:
            try:
                # 优先通过 DataSourceRouter（Tushare → AkShare 故障转移）
                data, src, fallback = await router.fetch_with_fallback_info(
                    "fetch_fundamentals", symbol,
                )
                last_data_source = src
                last_is_fallback = fallback
                logger.debug("DataSourceRouter 获取基本面成功 symbol=%s source=%s", symbol, src)
                success_count += 1
            except DataSourceUnavailableError:
                # 双数据源均不可用，回退至 FundamentalAdapter
                logger.warning(
                    "DataSourceRouter 不可用，回退至 FundamentalAdapter symbol=%s",
                    symbol,
                )
                try:
                    async with FundamentalAdapter() as adapter:
                        data = await adapter.fetch_fundamentals(symbol)
                    last_data_source = "FundamentalAdapter"
                    last_is_fallback = True
                    success_count += 1
                except Exception as exc:
                    logger.error("基本面同步失败 symbol=%s: %s", symbol, exc)
                    error_count += 1
                    continue
            except Exception as exc:
                logger.error("基本面同步失败 symbol=%s: %s", symbol, exc)
                error_count += 1
                continue

            # 写入 stock_info 表
            try:
                async with FundamentalAdapter() as adapter:
                    async with AsyncSessionPG() as session:
                        await adapter.sync_stock_info(symbol, session)
            except Exception as exc:
                logger.error("基本面写入数据库失败 symbol=%s: %s", symbol, exc)

        sync_status = "OK" if error_count == 0 else "ERROR"
        await _update_sync_status(
            "fundamentals", "基本面数据", sync_status, success_count,
            last_data_source, last_is_fallback,
        )

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
    优先通过 DataSourceRouter 获取资金流向和大盘概览数据
    （Tushare → AkShare 故障转移），DataSourceRouter 不可用时回退至 MoneyFlowAdapter。

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

        router = _get_data_source_router()
        success_count = 0
        error_count = 0
        last_data_source = "N/A"
        last_is_fallback = False

        # 同步大盘概览（优先 DataSourceRouter）
        try:
            _, src, fallback = await router.fetch_with_fallback_info(
                "fetch_market_overview", trade_date,
            )
            last_data_source = src
            last_is_fallback = fallback
            logger.info("DataSourceRouter 大盘概览同步完成 date=%s source=%s", trade_date, src)
        except DataSourceUnavailableError:
            logger.warning(
                "DataSourceRouter 不可用，回退至 MoneyFlowAdapter 同步大盘概览 date=%s",
                trade_date,
            )
            try:
                async with MoneyFlowAdapter() as adapter:
                    await adapter.fetch_market_overview(trade_date)
                last_data_source = "MoneyFlowAdapter"
                last_is_fallback = True
                logger.info("MoneyFlowAdapter 大盘概览同步完成 date=%s", trade_date)
            except Exception as exc:
                logger.error("大盘概览同步失败 date=%s: %s", trade_date, exc)
        except Exception as exc:
            logger.error("大盘概览同步失败 date=%s: %s", trade_date, exc)

        # 同步个股资金流向（优先 DataSourceRouter）
        for symbol in symbols:
            try:
                _, src, fallback = await router.fetch_with_fallback_info(
                    "fetch_money_flow", symbol, trade_date,
                )
                last_data_source = src
                last_is_fallback = fallback
                success_count += 1
            except DataSourceUnavailableError:
                logger.warning(
                    "DataSourceRouter 不可用，回退至 MoneyFlowAdapter symbol=%s",
                    symbol,
                )
                try:
                    async with MoneyFlowAdapter() as adapter:
                        await adapter.fetch_money_flow(symbol, trade_date)
                    last_data_source = "MoneyFlowAdapter"
                    last_is_fallback = True
                    success_count += 1
                except Exception as exc:
                    logger.error("资金数据同步失败 symbol=%s: %s", symbol, exc)
                    error_count += 1
            except Exception as exc:
                logger.error("资金数据同步失败 symbol=%s: %s", symbol, exc)
                error_count += 1

        sync_status = "OK" if error_count == 0 else "ERROR"
        await _update_sync_status(
            "money_flow", "资金流向", sync_status, success_count,
            last_data_source, last_is_fallback,
        )

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


# ---------------------------------------------------------------------------
# 每日增量 K 线同步任务
# ---------------------------------------------------------------------------


def _get_previous_trading_day(today: date | None = None) -> date:
    """计算前一个交易日日期（跳过周末）。

    周一 → 上周五，其他工作日 → 前一天。
    """
    today = today or date.today()
    weekday = today.weekday()  # 0=Mon … 6=Sun
    if weekday == 0:
        # Monday → previous Friday
        return today - timedelta(days=3)
    elif weekday == 6:
        # Sunday → previous Friday
        return today - timedelta(days=2)
    elif weekday == 5:
        # Saturday → previous Friday
        return today - timedelta(days=1)
    else:
        return today - timedelta(days=1)


@celery_app.task(
    name="app.tasks.data_sync.sync_daily_kline",
    queue="data_sync",
)
def sync_daily_kline() -> dict:
    """
    每日增量 K 线同步任务。

    由 Celery Beat 每个交易日（周一至周五）16:00 调度。
    查询 StockInfo 全市场有效股票（is_st=False AND is_delisted=False），
    回填前一个交易日的日 K 线数据。

    Returns:
        同步结果摘要字典

    需求：25.13
    """
    prev_day = _get_previous_trading_day()
    logger.info("开始每日增量 K 线同步，交易日=%s", prev_day)

    async def _sync():
        from sqlalchemy import select

        from app.core.database import AsyncSessionPG
        from app.models.stock import StockInfo

        # 查询全市场有效股票
        async with AsyncSessionPG() as session:
            stmt = (
                select(StockInfo.symbol)
                .where(StockInfo.is_st == False)  # noqa: E712
                .where(StockInfo.is_delisted == False)  # noqa: E712
                .order_by(StockInfo.symbol)
            )
            result = await session.execute(stmt)
            symbols = list(result.scalars().all())

        if not symbols:
            logger.warning("未找到有效股票，跳过每日 K 线同步")
            return {"status": "skipped", "reason": "no_valid_symbols"}

        logger.info("查询到 %d 只有效股票，开始回填 %s 日 K 线", len(symbols), prev_day)

        # 复用 _sync_historical_kline 核心逻辑
        date_str = prev_day.isoformat()
        return await _sync_historical_kline(symbols, date_str, date_str, "1d")

    return _run_async(_sync())


# ---------------------------------------------------------------------------
# 历史 K 线数据批量回填任务
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.data_sync.sync_historical_kline",
    queue="data_sync",
    soft_time_limit=7200,
    time_limit=10800,
)
def sync_historical_kline(
    symbols: list[str],
    start_date: str,
    end_date: str,
    freq: str = "1d",
) -> dict:
    """
    历史 K 线数据批量回填任务。

    由 BackfillService.start_backfill() 分发，按 BATCH_SIZE=50 分批处理，
    每批间隔 BATCH_DELAY=1s，通过 DataSourceRouter 获取数据并写入 TimescaleDB。

    Args:
        symbols:    股票代码列表
        start_date: 起始日期（ISO 格式字符串，如 "2024-01-01"）
        end_date:   结束日期（ISO 格式字符串）
        freq:       K 线频率，"1d"/"1w"/"1M"，默认 "1d"

    Returns:
        回填结果摘要字典

    需求：25.4, 25.7, 25.8, 25.10, 25.11
    """
    return _run_async(_sync_historical_kline(symbols, start_date, end_date, freq))


async def _sync_historical_kline(
    symbols: list[str],
    start_date: str,
    end_date: str,
    freq: str,
) -> dict:
    """sync_historical_kline 的异步实现。"""
    from datetime import date as date_cls

    from app.services.data_engine.kline_repository import KlineRepository

    start = date_cls.fromisoformat(start_date)
    end = date_cls.fromisoformat(end_date)

    # ── 启动前先检查停止信号 ──
    if await _check_stop_signal():
        logger.info("K 线回填任务启动时检测到停止信号，直接退出")
        return {"status": "stopped", "total": len(symbols), "completed": 0, "failed": 0, "inserted": 0}

    # ── 更新 Redis 状态为 running ──
    progress_raw = await cache_get(REDIS_KEY)
    if progress_raw:
        try:
            progress = json.loads(progress_raw)
        except (json.JSONDecodeError, TypeError):
            progress = {}
    else:
        progress = {}

    # 仅在非 stopping 状态时才设为 running
    if progress.get("status") != "stopping":
        progress.update({
            "status": "running",
            "total": len(symbols),
            "completed": progress.get("completed", 0),
            "failed": progress.get("failed", 0),
            "current_symbol": "",
        })
        await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    router = _get_data_source_router()
    repo = KlineRepository()
    completed = progress.get("completed", 0)
    failed = progress.get("failed", 0)
    total_inserted = 0

    # ── 分批处理 ──
    for batch_idx in range(0, len(symbols), BATCH_SIZE):
        if batch_idx > 0:
            await asyncio.sleep(BATCH_DELAY)

        batch = symbols[batch_idx : batch_idx + BATCH_SIZE]

        for symbol in batch:
            # ── 停止检测（使用独立信号键）──
            if await _check_stop_signal():
                progress["status"] = "stopped"
                progress["current_symbol"] = ""
                await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)
                logger.info("K 线回填任务收到停止信号，已停止")
                return {
                    "status": "stopped",
                    "total": len(symbols),
                    "completed": completed,
                    "failed": failed,
                    "inserted": total_inserted,
                }

            # 更新当前处理的股票
            progress["current_symbol"] = symbol
            await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

            try:
                bars = await router.fetch_kline(symbol, freq, start, end)
                if bars:
                    inserted = await repo.bulk_insert(bars)
                    total_inserted += inserted
                completed += 1
            except DataSourceUnavailableError as exc:
                logger.error("K 线回填失败 symbol=%s: %s", symbol, exc)
                failed += 1
            except Exception as exc:
                logger.error("K 线回填失败 symbol=%s: %s", symbol, exc)
                failed += 1

            # 更新进度
            progress["completed"] = completed
            progress["failed"] = failed
            await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

            # API 限流延迟
            await asyncio.sleep(settings.rate_limit_kline)

    # ── 全部完成，更新状态 ──
    progress["status"] = "completed"
    progress["current_symbol"] = ""
    await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    logger.info(
        "K 线历史回填完成 freq=%s，共 %d 只，成功 %d，失败 %d，写入 %d 条",
        freq, len(symbols), completed, failed, total_inserted,
    )
    return {
        "status": "completed",
        "total": len(symbols),
        "completed": completed,
        "failed": failed,
        "inserted": total_inserted,
    }


# ---------------------------------------------------------------------------
# 历史基本面数据批量回填任务
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.data_sync.sync_historical_fundamentals",
    queue="data_sync",
    soft_time_limit=7200,
    time_limit=10800,
)
def sync_historical_fundamentals(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict:
    """
    历史基本面数据批量回填任务。

    由 BackfillService.start_backfill() 分发，按 BATCH_SIZE=50 分批处理，
    每批间隔 BATCH_DELAY=1s，通过 DataSourceRouter 获取数据并写入 PostgreSQL。

    Args:
        symbols:    股票代码列表
        start_date: 起始日期（ISO 格式字符串，如 "2024-01-01"）
        end_date:   结束日期（ISO 格式字符串）

    Returns:
        回填结果摘要字典

    需求：25.5, 25.7, 25.8, 25.10, 25.11
    """
    return _run_async(_sync_historical_fundamentals(symbols, start_date, end_date))


async def _sync_historical_fundamentals(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict:
    """sync_historical_fundamentals 的异步实现。"""
    from datetime import date as date_cls

    from sqlalchemy import text

    from app.core.database import AsyncSessionPG

    start = date_cls.fromisoformat(start_date)
    end = date_cls.fromisoformat(end_date)

    # ── 启动前先检查停止信号 ──
    if await _check_stop_signal():
        logger.info("基本面回填任务启动时检测到停止信号，直接退出")
        return {"status": "stopped", "total": len(symbols), "completed": 0, "failed": 0, "upserted": 0}

    # ── 更新 Redis 状态为 running ──
    progress_raw = await cache_get(REDIS_KEY)
    if progress_raw:
        try:
            progress = json.loads(progress_raw)
        except (json.JSONDecodeError, TypeError):
            progress = {}
    else:
        progress = {}

    if progress.get("status") != "stopping":
        progress.update({
            "status": "running",
            "total": len(symbols),
            "completed": progress.get("completed", 0),
            "failed": progress.get("failed", 0),
            "current_symbol": "",
        })
        await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    router = _get_data_source_router()
    completed = progress.get("completed", 0)
    failed = progress.get("failed", 0)
    total_upserted = 0

    upsert_sql = text("""
        INSERT INTO stock_info (
            symbol, name, market, board, list_date,
            is_st, is_delisted, pledge_ratio,
            pe_ttm, pb, roe, market_cap, updated_at
        ) VALUES (
            :symbol, :name, :market, :board, :list_date,
            :is_st, :is_delisted, :pledge_ratio,
            :pe_ttm, :pb, :roe, :market_cap, :updated_at
        )
        ON CONFLICT (symbol) DO UPDATE SET
            name         = EXCLUDED.name,
            market       = EXCLUDED.market,
            board        = EXCLUDED.board,
            list_date    = EXCLUDED.list_date,
            is_st        = EXCLUDED.is_st,
            is_delisted  = EXCLUDED.is_delisted,
            pledge_ratio = EXCLUDED.pledge_ratio,
            pe_ttm       = EXCLUDED.pe_ttm,
            pb           = EXCLUDED.pb,
            roe          = EXCLUDED.roe,
            market_cap   = EXCLUDED.market_cap,
            updated_at   = EXCLUDED.updated_at
    """)

    # ── 分批处理 ──
    for batch_idx in range(0, len(symbols), BATCH_SIZE):
        if batch_idx > 0:
            await asyncio.sleep(BATCH_DELAY)

        batch = symbols[batch_idx : batch_idx + BATCH_SIZE]

        for symbol in batch:
            # ── 停止检测（使用独立信号键）──
            if await _check_stop_signal():
                progress["status"] = "stopped"
                progress["current_symbol"] = ""
                await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)
                logger.info("基本面回填任务收到停止信号，已停止")
                return {
                    "status": "stopped",
                    "total": len(symbols),
                    "completed": completed,
                    "failed": failed,
                    "upserted": total_upserted,
                }

            # 更新当前处理的股票
            progress["current_symbol"] = symbol
            await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

            try:
                data = await router.fetch_fundamentals(symbol)
                # 写入 PostgreSQL（ON CONFLICT 去重）
                async with AsyncSessionPG() as session:
                    clean_sym = data.symbol.split(".")[0] if "." in data.symbol else data.symbol
                    await session.execute(upsert_sql, {
                        "symbol":       clean_sym,
                        "name":         data.name,
                        "market":       data.market,
                        "board":        data.board,
                        "list_date":    data.list_date,
                        "is_st":        data.is_st,
                        "is_delisted":  data.is_delisted,
                        "pledge_ratio": data.pledge_ratio,
                        "pe_ttm":       data.pe_ttm,
                        "pb":           data.pb,
                        "roe":          data.roe,
                        "market_cap":   data.market_cap,
                        "updated_at":   data.updated_at,
                    })
                    await session.commit()
                total_upserted += 1
                completed += 1
            except DataSourceUnavailableError as exc:
                logger.error("基本面回填失败 symbol=%s: %s", symbol, exc)
                failed += 1
            except Exception as exc:
                logger.error("基本面回填失败 symbol=%s: %s", symbol, exc)
                failed += 1

            # 更新进度
            progress["completed"] = completed
            progress["failed"] = failed
            await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

            # API 限流延迟
            await asyncio.sleep(settings.rate_limit_fundamentals)

    # ── 全部完成，更新状态 ──
    progress["status"] = "completed"
    progress["current_symbol"] = ""
    await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    logger.info(
        "基本面历史回填完成，共 %d 只，成功 %d，失败 %d，写入 %d 条",
        len(symbols), completed, failed, total_upserted,
    )
    return {
        "status": "completed",
        "total": len(symbols),
        "completed": completed,
        "failed": failed,
        "upserted": total_upserted,
    }


# ---------------------------------------------------------------------------
# 历史资金流向数据批量回填任务
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.data_sync.sync_historical_money_flow",
    queue="data_sync",
    soft_time_limit=7200,
    time_limit=10800,
)
def sync_historical_money_flow(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict:
    """
    历史资金流向数据批量回填任务。

    由 BackfillService.start_backfill() 分发，按 BATCH_SIZE=50 分批处理，
    每批间隔 BATCH_DELAY=1s，通过 DataSourceRouter 获取数据并写入 PostgreSQL。

    Args:
        symbols:    股票代码列表
        start_date: 起始日期（ISO 格式字符串，如 "2024-01-01"）
        end_date:   结束日期（ISO 格式字符串）

    Returns:
        回填结果摘要字典

    需求：25.6, 25.7, 25.8, 25.10, 25.11
    """
    return _run_async(_sync_historical_money_flow(symbols, start_date, end_date))


async def _sync_historical_money_flow(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict:
    """sync_historical_money_flow 的异步实现。"""
    from datetime import date as date_cls, timedelta

    from sqlalchemy import text

    from app.core.database import AsyncSessionPG

    start = date_cls.fromisoformat(start_date)
    end = date_cls.fromisoformat(end_date)

    # ── 启动前先检查停止信号 ──
    if await _check_stop_signal():
        logger.info("资金流向回填任务启动时检测到停止信号，直接退出")
        return {"status": "stopped", "total": len(symbols), "completed": 0, "failed": 0, "upserted": 0}

    # ── 更新 Redis 状态为 running ──
    progress_raw = await cache_get(REDIS_KEY)
    if progress_raw:
        try:
            progress = json.loads(progress_raw)
        except (json.JSONDecodeError, TypeError):
            progress = {}
    else:
        progress = {}

    if progress.get("status") != "stopping":
        progress.update({
            "status": "running",
            "total": len(symbols),
            "completed": progress.get("completed", 0),
            "failed": progress.get("failed", 0),
            "current_symbol": "",
        })
        await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    router = _get_data_source_router()
    completed = progress.get("completed", 0)
    failed = progress.get("failed", 0)
    total_upserted = 0

    upsert_sql = text("""
        INSERT INTO money_flow (
            symbol, trade_date,
            main_net_inflow, main_inflow, main_outflow, main_net_inflow_pct,
            large_order_net, large_order_ratio,
            north_net_inflow, north_hold_ratio,
            on_dragon_tiger, dragon_tiger_net,
            block_trade_amount, block_trade_discount,
            bid_ask_ratio, inner_outer_ratio,
            updated_at
        ) VALUES (
            :symbol, :trade_date,
            :main_net_inflow, :main_inflow, :main_outflow, :main_net_inflow_pct,
            :large_order_net, :large_order_ratio,
            :north_net_inflow, :north_hold_ratio,
            :on_dragon_tiger, :dragon_tiger_net,
            :block_trade_amount, :block_trade_discount,
            :bid_ask_ratio, :inner_outer_ratio,
            :updated_at
        )
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            main_net_inflow      = EXCLUDED.main_net_inflow,
            main_inflow          = EXCLUDED.main_inflow,
            main_outflow         = EXCLUDED.main_outflow,
            main_net_inflow_pct  = EXCLUDED.main_net_inflow_pct,
            large_order_net      = EXCLUDED.large_order_net,
            large_order_ratio    = EXCLUDED.large_order_ratio,
            north_net_inflow     = EXCLUDED.north_net_inflow,
            north_hold_ratio     = EXCLUDED.north_hold_ratio,
            on_dragon_tiger      = EXCLUDED.on_dragon_tiger,
            dragon_tiger_net     = EXCLUDED.dragon_tiger_net,
            block_trade_amount   = EXCLUDED.block_trade_amount,
            block_trade_discount = EXCLUDED.block_trade_discount,
            bid_ask_ratio        = EXCLUDED.bid_ask_ratio,
            inner_outer_ratio    = EXCLUDED.inner_outer_ratio,
            updated_at           = EXCLUDED.updated_at
    """)

    # ── 遍历交易日，分批处理 ──
    current_date = start
    while current_date <= end:
        # 跳过周末
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        for batch_idx in range(0, len(symbols), BATCH_SIZE):
            if batch_idx > 0:
                await asyncio.sleep(BATCH_DELAY)

            batch = symbols[batch_idx : batch_idx + BATCH_SIZE]

            for symbol in batch:
                # ── 停止检测（使用独立信号键）──
                if await _check_stop_signal():
                    progress["status"] = "stopped"
                    progress["current_symbol"] = ""
                    await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)
                    logger.info("资金流向回填任务收到停止信号，已停止")
                    return {
                        "status": "stopped",
                        "total": len(symbols),
                        "completed": completed,
                        "failed": failed,
                        "upserted": total_upserted,
                    }

                # 更新当前处理的股票
                progress["current_symbol"] = symbol
                await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

                try:
                    data = await router.fetch_money_flow(symbol, current_date)
                    # 写入 PostgreSQL（ON CONFLICT 去重）
                    async with AsyncSessionPG() as session:
                        clean_sym = data.symbol.split(".")[0] if "." in data.symbol else data.symbol
                        await session.execute(upsert_sql, {
                            "symbol":               clean_sym,
                            "trade_date":            data.trade_date,
                            "main_net_inflow":       data.main_net_inflow,
                            "main_inflow":           data.main_inflow,
                            "main_outflow":          data.main_outflow,
                            "main_net_inflow_pct":   data.main_net_inflow_pct,
                            "large_order_net":       data.large_order_net,
                            "large_order_ratio":     data.large_order_ratio,
                            "north_net_inflow":      data.north_net_inflow,
                            "north_hold_ratio":      data.north_hold_ratio,
                            "on_dragon_tiger":       data.on_dragon_tiger,
                            "dragon_tiger_net":      data.dragon_tiger_net,
                            "block_trade_amount":    data.block_trade_amount,
                            "block_trade_discount":  data.block_trade_discount,
                            "bid_ask_ratio":         data.bid_ask_ratio,
                            "inner_outer_ratio":     data.inner_outer_ratio,
                            "updated_at":            data.updated_at,
                        })
                        await session.commit()
                    total_upserted += 1
                    completed += 1
                except DataSourceUnavailableError as exc:
                    logger.error("资金流向回填失败 symbol=%s date=%s: %s", symbol, current_date, exc)
                    failed += 1
                except Exception as exc:
                    logger.error("资金流向回填失败 symbol=%s date=%s: %s", symbol, current_date, exc)
                    failed += 1

                # 更新进度
                progress["completed"] = completed
                progress["failed"] = failed
                await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

                # API 限流延迟
                await asyncio.sleep(settings.rate_limit_money_flow)

        current_date += timedelta(days=1)

    # ── 全部完成，更新状态 ──
    progress["status"] = "completed"
    progress["current_symbol"] = ""
    await cache_set(REDIS_KEY, json.dumps(progress), ex=PROGRESS_TTL)

    logger.info(
        "资金流向历史回填完成，共 %d 只，成功 %d，失败 %d，写入 %d 条",
        len(symbols), completed, failed, total_upserted,
    )
    return {
        "status": "completed",
        "total": len(symbols),
        "completed": completed,
        "failed": failed,
        "upserted": total_upserted,
    }


# ---------------------------------------------------------------------------
# 本地K线数据导入任务
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.data_sync.import_local_kline",
    queue="data_sync",
    soft_time_limit=86400,   # 24h 软限制
    time_limit=None,         # 无硬限制
)
def import_local_kline(
    freqs: list[str] | None = None,
    sub_dir: str | None = None,
    force: bool = False,
) -> dict:
    """
    本地K线数据导入 Celery 任务。

    通过 LocalKlineImportService 扫描本地数据目录、解压 ZIP、解析 CSV、
    校验数据质量并批量写入 TimescaleDB。支持频率过滤、子目录指定和强制全量导入。

    Args:
        freqs:   可选频率过滤列表，如 ["1m", "5m"]
        sub_dir: 可选子目录路径，限定扫描范围
        force:   强制全量导入，忽略增量缓存

    Returns:
        导入结果摘要字典

    需求：6.1, 6.2
    """
    from app.services.data_engine.local_kline_import import LocalKlineImportService

    service = LocalKlineImportService()
    return _run_async(service.execute(freqs=freqs, sub_dir=sub_dir, force=force))
