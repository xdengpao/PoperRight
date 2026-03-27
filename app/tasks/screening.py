"""
选股定时任务

包含：
- run_eod_screening：盘后全市场选股（每日 15:30，Celery Beat）
- run_realtime_screening：盘中实时选股（9:30-15:00，每 10 秒）

对应需求：
- 需求 7.4：每个交易日 15:30 自动执行盘后选股
- 需求 7.5：交易时段 9:30-15:00 每 10 秒刷新实时选股
"""

from __future__ import annotations

import logging
from datetime import datetime, time

from app.core.celery_app import celery_app
from app.core.schemas import StrategyConfig
from app.services.screener.screen_executor import ScreenExecutor
from app.tasks.base import ScreeningTask

logger = logging.getLogger(__name__)

# A股交易时段
TRADING_START = time(9, 30)
TRADING_END = time(15, 0)


def _is_trading_hours(now: datetime | None = None) -> bool:
    """判断当前是否在交易时段（9:30-15:00，周一至周五）。"""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    return TRADING_START <= current_time <= TRADING_END


def _load_active_strategy() -> StrategyConfig:
    """
    加载当前活跃策略配置。

    生产环境从数据库读取用户活跃策略模板；
    当前返回默认空策略作为占位。
    """
    return StrategyConfig()


def _load_market_data() -> dict[str, dict]:
    """
    加载全市场股票因子数据。

    生产环境从 TimescaleDB / Redis 缓存读取；
    当前返回空字典作为占位。
    """
    return {}


# ---------------------------------------------------------------------------
# 盘后选股任务（需求 7.4）
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
    2. 加载全市场股票因子数据
    3. 执行 ScreenExecutor.run_eod_screen
    4. 返回选股结果摘要

    Args:
        strategy_dict: 可选的策略配置字典（覆盖活跃策略）

    Returns:
        选股结果摘要字典
    """
    logger.info("开始盘后选股任务")

    if strategy_dict is not None:
        config = StrategyConfig.from_dict(strategy_dict)
    else:
        config = _load_active_strategy()

    stocks_data = _load_market_data()

    executor = ScreenExecutor(config)
    result = executor.run_eod_screen(stocks_data)

    logger.info(
        "盘后选股完成，筛选出 %d 只标的",
        len(result.items),
    )

    return {
        "status": "success",
        "screen_type": "EOD",
        "total_screened": len(stocks_data),
        "passed": len(result.items),
        "screen_time": result.screen_time.isoformat(),
    }


# ---------------------------------------------------------------------------
# 盘中实时选股任务（需求 7.5）
# ---------------------------------------------------------------------------

@celery_app.task(
    base=ScreeningTask,
    name="app.tasks.screening.run_realtime_screening",
    bind=True,
    queue="screening",
)
def run_realtime_screening(self, strategy_dict: dict | None = None) -> dict:
    """
    盘中实时选股任务。

    仅在交易时段（9:30-15:00，工作日）执行，
    非交易时段直接跳过。

    Args:
        strategy_dict: 可选的策略配置字典

    Returns:
        选股结果摘要字典
    """
    if not _is_trading_hours():
        logger.debug("非交易时段，跳过实时选股")
        return {"status": "skipped", "reason": "outside_trading_hours"}

    logger.info("开始盘中实时选股")

    if strategy_dict is not None:
        config = StrategyConfig.from_dict(strategy_dict)
    else:
        config = _load_active_strategy()

    stocks_data = _load_market_data()

    executor = ScreenExecutor(config)
    result = executor.run_realtime_screen(stocks_data)

    logger.info(
        "实时选股完成，筛选出 %d 只标的",
        len(result.items),
    )

    return {
        "status": "success",
        "screen_type": "REALTIME",
        "total_screened": len(stocks_data),
        "passed": len(result.items),
        "screen_time": result.screen_time.isoformat(),
    }
