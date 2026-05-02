"""
选股定时任务

包含：
- run_eod_screening：盘后全市场选股（每日 15:30，Celery Beat）
- run_realtime_screening：盘中实时选股（9:30-15:00，每 10 秒）

对应需求：
- 需求 2：Celery 选股任务接入数据管线
- 需求 7.4：每个交易日 15:30 自动执行盘后选股
- 需求 7.5：交易时段 9:30-15:00 每 10 秒刷新实时选股
- 需求 9：实时选股增量计算架构
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as time_mod
from datetime import datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.redis_client import get_redis_client
from app.core.schemas import ScreenType, StrategyConfig
from app.models.strategy import StrategyTemplate
from app.services.screener.screen_data_provider import ScreenDataProvider
from app.services.screener.screen_executor import ScreenExecutor
from app.services.screener.strategy_engine import (
    summarize_factor_condition_stats,
    summarize_factor_failures,
)
from app.tasks.base import ScreeningTask

logger = logging.getLogger(__name__)

# A股交易时段
TRADING_START = time(9, 30)
TRADING_END = time(15, 0)

# Redis 缓存键前缀与 TTL
_RESULT_CACHE_PREFIX = "screen:results:"
_LAST_RUN_KEY = "screen:eod:last_run"
_RESULT_CACHE_TTL = 86400  # 24 小时
_LAST_RUN_TTL = 86400  # 24 小时
_MANUAL_TASK_PREFIX = "screen:task:"
_MANUAL_TASK_TTL = 86400  # 24 小时

# 增量计算因子缓存键前缀与 TTL（需求 9）
FACTOR_CACHE_PREFIX = "screen:factor_cache:"
FACTOR_CACHE_TTL = 6 * 3600  # 6 小时（覆盖交易时段）
_FACTOR_WARMUP_KEY = "screen:factor_cache:warmed"

# 受实时数据影响的因子（需要增量重算）
_REALTIME_FACTORS = {
    "close", "open", "high", "low", "volume", "amount",
    "turnover", "vol_ratio",
    "closes", "highs", "lows", "volumes", "amounts", "turnovers",
    "ma_trend", "ma_support",
    "macd", "boll", "rsi", "dma",
    "breakout", "breakout_list",
    "turnover_check",
    "raw_close",
}

# 基本面和板块因子（使用缓存值，不重算）
_CACHED_FACTORS = {
    "pe_ttm", "pb", "roe", "market_cap",
    "money_flow", "large_order", "main_net_inflow", "large_order_ratio",
    "sector_rank", "sector_trend", "sector_name",
    "name",
}

# 实时选股单轮执行耗时告警阈值（秒）
_REALTIME_SLOW_THRESHOLD = 8.0

# 数据源代码 → API 字段名映射（与 screen API 响应保持一致）
_SOURCE_TO_API_KEY = {"DC": "eastmoney", "TI": "tonghuashun", "TDX": "tongdaxin"}

# 信号分类 → 前端展示维度
_SIGNAL_DIMENSION_MAP: dict[str, str] = {
    "MA_TREND": "技术面",
    "MACD": "技术面",
    "BOLL": "技术面",
    "RSI": "技术面",
    "DMA": "技术面",
    "BREAKOUT": "技术面",
    "MA_SUPPORT": "技术面",
    "CAPITAL_INFLOW": "资金面",
    "LARGE_ORDER": "资金面",
    "SECTOR_STRONG": "板块面",
}


def _is_trading_hours(now: datetime | None = None) -> bool:
    """判断当前是否在交易时段（9:30-15:00，周一至周五）。"""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    return TRADING_START <= current_time <= TRADING_END


# ---------------------------------------------------------------------------
# 异步数据加载函数（需求 2.1 / 2.2）
# ---------------------------------------------------------------------------


async def _load_market_data_async(
    strategy_config: dict[str, Any] | None = None,
) -> dict[str, dict]:
    """
    通过 ScreenDataProvider 异步加载全市场股票因子数据。

    替代原先返回空字典的 _load_market_data() 占位实现。

    Args:
        strategy_config: 可选的策略配置字典，传递给 ScreenDataProvider

    Returns:
        {symbol: factor_dict} 全市场股票因子数据

    Raises:
        OperationalError: 数据库连接失败时抛出，由调用方处理重试
    """
    async with AsyncSessionPG() as pg_session, AsyncSessionTS() as ts_session:
        provider = ScreenDataProvider(
            pg_session=pg_session,
            ts_session=ts_session,
            strategy_config=strategy_config or {},
        )
        return await provider.load_screen_data()


async def _load_active_strategy_async() -> tuple[StrategyConfig, str, list[str]]:
    """
    从 strategy_template 表查询 is_active=True 的策略模板。

    替代原先返回空配置的 _load_active_strategy() 占位实现。

    Returns:
        (config, strategy_id, enabled_modules) 三元组：
        - config: StrategyConfig 策略配置
        - strategy_id: 策略模板 UUID 字符串
        - enabled_modules: 启用的选股模块列表

    Raises:
        OperationalError: 数据库连接失败时抛出，由调用方处理重试
    """
    async with AsyncSessionPG() as session:
        stmt = (
            select(StrategyTemplate)
            .where(StrategyTemplate.is_active == True)  # noqa: E712
            .limit(1)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

        if template is None:
            logger.warning("未找到活跃策略模板，使用默认空策略")
            return StrategyConfig(), "", []

        config = StrategyConfig.from_dict(template.config)
        strategy_id = str(template.id)
        enabled_modules = list(template.enabled_modules) if template.enabled_modules else []

        logger.info(
            "加载活跃策略模板：id=%s name=%s modules=%s",
            strategy_id,
            template.name,
            enabled_modules,
        )
        return config, strategy_id, enabled_modules


def _load_active_strategy() -> StrategyConfig:
    """
    加载当前活跃策略配置（同步包装）。

    向后兼容：实时选股等场景仍可使用同步接口。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中无法直接 run，回退到默认策略
            logger.warning("事件循环已运行，无法同步加载策略，使用默认空策略")
            return StrategyConfig()
        config, _, _ = loop.run_until_complete(_load_active_strategy_async())
        return config
    except Exception:
        logger.warning("同步加载活跃策略失败，使用默认空策略", exc_info=True)
        return StrategyConfig()


def _load_market_data() -> dict[str, dict]:
    """
    加载全市场股票因子数据（同步包装）。

    向后兼容：实时选股等场景仍可使用同步接口。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.warning("事件循环已运行，无法同步加载市场数据，返回空字典")
            return {}
        return loop.run_until_complete(_load_market_data_async())
    except Exception:
        logger.warning("同步加载市场数据失败，返回空字典", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# 增量实时计算（需求 9）
# ---------------------------------------------------------------------------


async def _warmup_factor_cache(
    strategy_config: dict[str, Any] | None = None,
) -> dict[str, dict]:
    """
    交易日首次执行时全量预热因子数据到 Redis（需求 9.2）。

    通过 ScreenDataProvider 加载全市场股票因子数据，将每只股票的因子字典
    序列化后写入 Redis，缓存有效期 6 小时。同时设置预热标记键。

    Args:
        strategy_config: 可选的策略配置字典

    Returns:
        {symbol: factor_dict} 全市场股票因子数据（同时返回供首次选股使用）
    """
    logger.info("开始全量因子预热")
    stocks_data = await _load_market_data_async(strategy_config=strategy_config)

    if not stocks_data:
        logger.warning("因子预热：无市场数据可缓存")
        return stocks_data

    redis = get_redis_client()
    try:
        pipe = redis.pipeline()
        for symbol, factor_dict in stocks_data.items():
            cache_key = f"{FACTOR_CACHE_PREFIX}{symbol}"
            # 将 Decimal 等不可 JSON 序列化的类型转为字符串
            serializable = _serialize_factor_dict(factor_dict)
            pipe.set(cache_key, json.dumps(serializable, ensure_ascii=False), ex=FACTOR_CACHE_TTL)

        # 设置预热标记
        pipe.set(_FACTOR_WARMUP_KEY, "1", ex=FACTOR_CACHE_TTL)
        await pipe.execute()

        logger.info(
            "因子预热完成：缓存 %d 只股票因子数据，TTL=%d秒",
            len(stocks_data),
            FACTOR_CACHE_TTL,
        )
    except Exception:
        logger.error("因子预热写入 Redis 失败，将回退到全量计算模式", exc_info=True)
    finally:
        await redis.aclose()

    return stocks_data


async def _incremental_update(
    latest_bars: dict[str, dict],
    strategy_config: dict[str, Any] | None = None,
) -> dict[str, dict]:
    """
    增量更新因子（需求 9.2）。

    从 Redis 读取缓存的历史因子数据，仅重新计算受实时数据影响的因子
    （均线、技术指标），基本面因子和板块因子使用缓存值。

    Args:
        latest_bars: {symbol: latest_bar_dict} 最新实时 K 线数据，
                     每个 bar_dict 至少包含 close/open/high/low/volume 等字段
        strategy_config: 可选的策略配置字典

    Returns:
        {symbol: merged_factor_dict} 合并后的因子数据
    """
    redis = get_redis_client()
    merged: dict[str, dict] = {}

    try:
        # 批量读取缓存因子
        symbols = list(latest_bars.keys())
        if not symbols:
            return merged

        cache_keys = [f"{FACTOR_CACHE_PREFIX}{sym}" for sym in symbols]
        cached_values = await redis.mget(cache_keys)

        for symbol, cached_json in zip(symbols, cached_values):
            if cached_json is None:
                # 缓存未命中，跳过该股票（或可回退到全量计算）
                logger.debug("股票 %s 因子缓存未命中，跳过增量更新", symbol)
                continue

            try:
                cached_factors = json.loads(cached_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning("股票 %s 因子缓存反序列化失败，跳过", symbol)
                continue

            # 合并：基本面和板块因子使用缓存值，实时因子使用最新数据
            bar_data = latest_bars[symbol]
            merged_dict: dict[str, Any] = {}

            # 先写入缓存的基本面/板块因子
            for key, value in cached_factors.items():
                if key in _CACHED_FACTORS:
                    merged_dict[key] = value

            # 再写入实时更新的因子（来自 latest_bars）
            for key, value in bar_data.items():
                if key in _REALTIME_FACTORS or key not in _CACHED_FACTORS:
                    merged_dict[key] = value

            merged[symbol] = merged_dict

    except Exception:
        logger.error("增量更新读取 Redis 缓存失败", exc_info=True)
    finally:
        await redis.aclose()

    return merged


async def _is_factor_cache_warmed() -> bool:
    """检查当日因子缓存是否已预热。"""
    redis = get_redis_client()
    try:
        val = await redis.get(_FACTOR_WARMUP_KEY)
        return val is not None
    except Exception:
        logger.warning("检查因子预热标记失败", exc_info=True)
        return False
    finally:
        await redis.aclose()


def _serialize_factor_dict(factor_dict: dict[str, Any]) -> dict[str, Any]:
    """
    将因子字典中的不可 JSON 序列化类型转为可序列化格式。

    Decimal → float，list[Decimal] → list[float]
    """
    from decimal import Decimal as Dec

    result: dict[str, Any] = {}
    for key, value in factor_dict.items():
        if isinstance(value, Dec):
            result[key] = float(value)
        elif isinstance(value, list) and value and isinstance(value[0], Dec):
            result[key] = [float(v) for v in value]
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Redis 缓存写入辅助（需求 2.3）
# ---------------------------------------------------------------------------


async def _cache_screen_results(
    strategy_id: str,
    result_summary: dict[str, Any],
    elapsed_seconds: float,
    passed_count: int,
) -> None:
    """
    将选股结果写入 Redis 缓存。

    - key screen:results:{strategy_id} → 选股结果摘要 JSON
    - key screen:eod:last_run → 执行耗时和选出股票数量

    Args:
        strategy_id: 策略模板 ID
        result_summary: 选股结果摘要字典
        elapsed_seconds: 执行耗时（秒）
        passed_count: 选出股票数量
    """
    redis = get_redis_client()
    try:
        # 写入选股结果缓存
        cache_key = f"{_RESULT_CACHE_PREFIX}{strategy_id}"
        await redis.set(
            cache_key,
            json.dumps(result_summary, ensure_ascii=False),
            ex=_RESULT_CACHE_TTL,
        )

        # 记录执行耗时和选出股票数量
        last_run_data = json.dumps({
            "strategy_id": strategy_id,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "passed_count": passed_count,
            "run_time": datetime.now().isoformat(),
        }, ensure_ascii=False)
        await redis.set(_LAST_RUN_KEY, last_run_data, ex=_LAST_RUN_TTL)

        logger.info(
            "选股结果已缓存到 Redis：strategy_id=%s, 耗时=%.3fs, 选出=%d只",
            strategy_id,
            elapsed_seconds,
            passed_count,
        )
    except Exception:
        logger.warning("写入 Redis 缓存失败，选股结果未缓存", exc_info=True)
    finally:
        await redis.aclose()


async def _set_manual_task_state(task_id: str, payload: dict[str, Any]) -> None:
    """写入手动选股任务状态。"""
    redis = get_redis_client()
    try:
        await redis.set(
            f"{_MANUAL_TASK_PREFIX}{task_id}",
            json.dumps(payload, ensure_ascii=False),
            ex=_MANUAL_TASK_TTL,
        )
    finally:
        await redis.aclose()


async def _cache_manual_screen_response(strategy_id: str, response: dict[str, Any]) -> None:
    """缓存前端结果页使用的完整选股响应。"""
    redis = get_redis_client()
    try:
        payload = json.dumps(response, ensure_ascii=False)
        await redis.set(f"{_RESULT_CACHE_PREFIX}{strategy_id}", payload, ex=_RESULT_CACHE_TTL)
        await redis.set(f"{_RESULT_CACHE_PREFIX}latest", payload, ex=_RESULT_CACHE_TTL)
    finally:
        await redis.aclose()


def _build_screen_response(
    strategy_id: str,
    screen_type: ScreenType,
    result,
    stocks_data: dict[str, dict],
) -> dict[str, Any]:
    """构建与 /screen/run 旧同步接口兼容的完整响应。"""
    screen_time_str = result.screen_time.isoformat()
    factor_stats = [
        stat.to_dict() if hasattr(stat, "to_dict") else dict(stat)
        for stat in getattr(result, "factor_stats", [])
    ]
    return {
        "strategy_id": strategy_id,
        "screen_type": screen_type.value,
        "screen_time": screen_time_str,
        "items": [
            {
                "symbol": item.symbol,
                "name": stocks_data.get(item.symbol, {}).get("name", item.symbol),
                "ref_buy_price": float(item.ref_buy_price),
                "trend_score": item.trend_score,
                "risk_level": item.risk_level.value,
                "signals": [
                    {
                        "category": s.category.value,
                        "label": s.label,
                        "is_fake_breakout": s.is_fake_breakout,
                        "strength": s.strength.value,
                        "freshness": s.freshness.value,
                        "description": s.description,
                        "dimension": _SIGNAL_DIMENSION_MAP.get(s.category.value, "其他"),
                    }
                    for s in item.signals
                ],
                "has_fake_breakout": item.has_fake_breakout,
                "sector_classifications": {
                    _SOURCE_TO_API_KEY[src]: names
                    for src, names in stocks_data.get(item.symbol, {})
                        .get("sector_classifications", {"DC": [], "TI": [], "TDX": []})
                        .items()
                    if src in _SOURCE_TO_API_KEY
                },
                "screen_time": screen_time_str,
            }
            for item in result.items
        ],
        "is_complete": result.is_complete,
        "factor_stats": factor_stats,
        "group_stats": getattr(result, "group_stats", []),
    }


@celery_app.task(
    base=ScreeningTask,
    name="app.tasks.screening.run_manual_screening",
    bind=True,
    queue="screening",
    soft_time_limit=1800,
    time_limit=3600,
    autoretry_for=(),
    max_retries=0,
)
def run_manual_screening(
    self,
    task_id: str,
    strategy_id: str,
    config_dict: dict,
    enabled_modules: list[str] | None,
    screen_type: str,
) -> dict:
    """手动触发的异步选股任务。"""
    logger.info("开始手动选股任务 task_id=%s strategy_id=%s", task_id, strategy_id)
    start_time = time_mod.monotonic()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_set_manual_task_state(task_id, {
            "task_id": task_id,
            "status": "running",
            "message": "正在加载市场数据",
            "strategy_id": strategy_id,
            "started_at": datetime.now().isoformat(),
        }))

        strategy_config = StrategyConfig.from_dict(config_dict)
        raw_config = strategy_config.to_dict()
        stocks_data = loop.run_until_complete(
            _load_market_data_async(strategy_config=raw_config)
        )

        loop.run_until_complete(_set_manual_task_state(task_id, {
            "task_id": task_id,
            "status": "running",
            "message": "正在执行策略筛选",
            "strategy_id": strategy_id,
            "total_screened": len(stocks_data),
        }))

        executor = ScreenExecutor(
            strategy_config=strategy_config,
            strategy_id=strategy_id,
            enabled_modules=enabled_modules,
            raw_config=raw_config,
        )
        screen_type_enum = ScreenType(screen_type)
        if screen_type_enum == ScreenType.EOD:
            result = executor.run_eod_screen(stocks_data)
        else:
            result = executor.run_realtime_screen(stocks_data)

        if getattr(result, "group_stats", None):
            logger.info(
                "手动选股分组统计 task_id=%s strategy_id=%s group_stats=%s 入选=%d",
                task_id,
                strategy_id,
                json.dumps(result.group_stats, ensure_ascii=False),
                len(result.items),
            )

        if len(result.items) == 0 and stocks_data:
            factor_summary = summarize_factor_failures(strategy_config, stocks_data)
            logger.info(
                "手动选股 0 入选因子统计 task_id=%s summary=%s",
                task_id,
                json.dumps(factor_summary, ensure_ascii=False),
            )
        factor_stats = [
            stat.to_dict()
            for stat in summarize_factor_condition_stats(strategy_config, stocks_data)
        ]

        response = _build_screen_response(
            strategy_id=strategy_id,
            screen_type=screen_type_enum,
            result=result,
            stocks_data=stocks_data,
        )
        loop.run_until_complete(_cache_manual_screen_response(strategy_id, response))

        elapsed = time_mod.monotonic() - start_time
        final_state = {
            "task_id": task_id,
            "status": "completed",
            "message": "选股完成",
            "strategy_id": strategy_id,
            "screen_type": screen_type_enum.value,
            "total_screened": len(stocks_data),
            "passed": len(result.items),
            "screen_time": response["screen_time"],
            "factor_stats": response.get("factor_stats", factor_stats),
            "elapsed_seconds": round(elapsed, 3),
            "result_cache_key": f"{_RESULT_CACHE_PREFIX}{strategy_id}",
            "completed_at": datetime.now().isoformat(),
        }
        loop.run_until_complete(_set_manual_task_state(task_id, final_state))
        logger.info(
            "手动选股任务完成 task_id=%s 筛选=%d 入选=%d 耗时=%.3fs",
            task_id, len(stocks_data), len(result.items), elapsed,
        )
        return final_state

    except Exception as exc:
        elapsed = time_mod.monotonic() - start_time
        error_state = {
            "task_id": task_id,
            "status": "failed",
            "message": str(exc)[:500],
            "strategy_id": strategy_id,
            "elapsed_seconds": round(elapsed, 3),
            "failed_at": datetime.now().isoformat(),
        }
        try:
            loop.run_until_complete(_set_manual_task_state(task_id, error_state))
        finally:
            logger.error("手动选股任务失败 task_id=%s: %s", task_id, exc, exc_info=True)
        return error_state

    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 盘后选股任务（需求 7.4 + 需求 2）
# ---------------------------------------------------------------------------

@celery_app.task(
    base=ScreeningTask,
    name="app.tasks.screening.run_eod_screening",
    bind=True,
    queue="screening",
)
def run_eod_screening(self, strategy_dict: dict | None = None) -> dict:
    """
    盘后全市场选股任务。

    由 Celery Beat 每个交易日 15:30 调度（eod-screening-1530）。

    流程：
    1. 加载活跃策略配置（或使用传入的策略字典）
    2. 通过 ScreenDataProvider 异步加载全市场股票因子数据
    3. 执行 ScreenExecutor.run_eod_screen
    4. 将选股结果写入 Redis 缓存
    5. 返回选股结果摘要

    Args:
        strategy_dict: 可选的策略配置字典（覆盖活跃策略）

    Returns:
        选股结果摘要字典
    """
    logger.info("开始盘后选股任务")
    start_time = time_mod.monotonic()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 1. 加载策略配置
            if strategy_dict is not None:
                config = StrategyConfig.from_dict(strategy_dict)
                strategy_id = ""
                enabled_modules: list[str] = []
            else:
                config, strategy_id, enabled_modules = loop.run_until_complete(
                    _load_active_strategy_async()
                )

            # 2. 异步加载全市场股票因子数据
            raw_config = config.to_dict() if config else {}
            stocks_data = loop.run_until_complete(
                _load_market_data_async(strategy_config=raw_config)
            )

            # 3. 执行选股
            executor = ScreenExecutor(
                config,
                strategy_id=strategy_id or None,
                enabled_modules=enabled_modules or None,
                raw_config=raw_config,
            )
            result = executor.run_eod_screen(stocks_data)

            elapsed = time_mod.monotonic() - start_time

            logger.info(
                "盘后选股完成，筛选出 %d 只标的，耗时 %.3fs",
                len(result.items),
                elapsed,
            )

            result_summary = {
                "status": "success",
                "screen_type": "EOD",
                "total_screened": len(stocks_data),
                "passed": len(result.items),
                "screen_time": result.screen_time.isoformat(),
                "strategy_id": strategy_id,
                "elapsed_seconds": round(elapsed, 3),
            }

            # 4. 写入 Redis 缓存（需求 2.3）
            loop.run_until_complete(
                _cache_screen_results(
                    strategy_id=strategy_id,
                    result_summary=result_summary,
                    elapsed_seconds=elapsed,
                    passed_count=len(result.items),
                )
            )

            return result_summary

        finally:
            loop.close()

    except (OperationalError, ConnectionError, OSError) as exc:
        # 数据库连接失败时的 Celery 重试逻辑（需求 2.4）
        logger.error(
            "盘后选股任务数据库连接失败，准备重试：%s",
            exc,
            exc_info=True,
        )
        self.retry_with_backoff(exc)

    except SQLAlchemyError as exc:
        # 其他数据库异常也触发重试
        logger.error(
            "盘后选股任务数据库异常，准备重试：%s",
            exc,
            exc_info=True,
        )
        self.retry_with_backoff(exc)


# ---------------------------------------------------------------------------
# 盘中实时选股任务（需求 7.5 + 需求 9）
# ---------------------------------------------------------------------------

@celery_app.task(
    base=ScreeningTask,
    name="app.tasks.screening.run_realtime_screening",
    bind=True,
    queue="screening",
)
def run_realtime_screening(self, strategy_dict: dict | None = None) -> dict:
    """
    盘中实时选股任务（增量计算模式，需求 9）。

    仅在交易时段（9:30-15:00，工作日）执行，非交易时段直接跳过。

    增量计算流程：
    1. 首次执行时调用 _warmup_factor_cache() 全量预热因子数据到 Redis
    2. 后续执行使用 _incremental_update() 增量模式：
       - 从 Redis 读取缓存因子
       - 仅重新计算受实时数据影响的因子（均线、技术指标）
       - 基本面和板块因子使用缓存值
    3. 每轮完成后记录执行耗时，超过 8 秒记录 WARNING 日志

    Args:
        strategy_dict: 可选的策略配置字典

    Returns:
        选股结果摘要字典
    """
    if not _is_trading_hours():
        logger.debug("非交易时段，跳过实时选股")
        return {"status": "skipped", "reason": "outside_trading_hours"}

    logger.info("开始盘中实时选股")
    start_time = time_mod.monotonic()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 加载策略配置
            if strategy_dict is not None:
                config = StrategyConfig.from_dict(strategy_dict)
            else:
                config, _, _ = loop.run_until_complete(_load_active_strategy_async())

            raw_config = config.to_dict() if config else {}

            # 检查是否需要预热（需求 9.2：首次执行全量预热）
            is_warmed = loop.run_until_complete(_is_factor_cache_warmed())

            if not is_warmed:
                # 首次执行：全量预热因子缓存，同时获取全量数据用于本轮选股
                logger.info("因子缓存未预热，执行全量预热")
                stocks_data = loop.run_until_complete(
                    _warmup_factor_cache(strategy_config=raw_config)
                )
            else:
                # 后续执行：增量模式（需求 9.1）
                # 加载最新实时数据（全量加载，但仅用实时因子部分）
                stocks_data = loop.run_until_complete(
                    _load_market_data_async(strategy_config=raw_config)
                )

                if stocks_data:
                    # 增量合并：从缓存读取基本面/板块因子，与实时因子合并
                    merged = loop.run_until_complete(
                        _incremental_update(stocks_data, strategy_config=raw_config)
                    )
                    if merged:
                        stocks_data = merged

            # 执行选股
            executor = ScreenExecutor(config)
            result = executor.run_realtime_screen(stocks_data)

            elapsed = time_mod.monotonic() - start_time

            # 需求 9.4：超过 8 秒记录 WARNING 日志
            if elapsed > _REALTIME_SLOW_THRESHOLD:
                logger.warning(
                    "实时选股单轮执行耗时 %.3fs，超过 %.1f 秒阈值",
                    elapsed,
                    _REALTIME_SLOW_THRESHOLD,
                )
            else:
                logger.info(
                    "实时选股完成，筛选出 %d 只标的，耗时 %.3fs",
                    len(result.items),
                    elapsed,
                )

            return {
                "status": "success",
                "screen_type": "REALTIME",
                "total_screened": len(stocks_data),
                "passed": len(result.items),
                "screen_time": result.screen_time.isoformat(),
                "elapsed_seconds": round(elapsed, 3),
                "mode": "warmup" if not is_warmed else "incremental",
            }

        finally:
            loop.close()

    except (OperationalError, ConnectionError, OSError) as exc:
        logger.error(
            "实时选股任务连接失败，准备重试：%s",
            exc,
            exc_info=True,
        )
        self.retry_with_backoff(exc)

    except SQLAlchemyError as exc:
        logger.error(
            "实时选股任务数据库异常，准备重试：%s",
            exc,
            exc_info=True,
        )
        self.retry_with_backoff(exc)
