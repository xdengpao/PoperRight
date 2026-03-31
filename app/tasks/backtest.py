"""回测任务模块"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask

logger = logging.getLogger(__name__)


@celery_app.task(base=BaseTask, bind=True, queue="backtest", name="backtest.run")
def run_backtest_task(
    self,
    run_id: str,
    strategy_id: str | None = None,
    start_date: str = "",
    end_date: str = "",
    initial_capital: float = 1_000_000.0,
    commission_buy: float = 0.0003,
    commission_sell: float = 0.0013,
    slippage: float = 0.001,
    max_holdings: int = 10,
    stop_loss_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    max_holding_days: int = 20,
    allocation_mode: str = "equal",
    enable_market_risk: bool = True,
    trend_stop_ma: int = 20,
) -> dict:
    """
    执行回测 Celery 任务。

    从数据库加载 K 线数据和指数数据，构建 BacktestConfig，
    调用 BacktestEngine.run_backtest() 策略驱动路径。
    """
    logger.info("回测任务启动 run_id=%s strategy_id=%s", run_id, strategy_id)

    try:
        from app.core.schemas import BacktestConfig, StrategyConfig
        from app.services.backtest_engine import BacktestEngine

        # 构建策略配置（如果有 strategy_id，从存储加载；否则使用默认空策略）
        # TODO: 从数据库加载策略配置
        strategy_config = StrategyConfig(
            factors=[], logic="AND", weights={}, ma_periods=[5, 10, 20, 60, 120],
        )

        config = BacktestConfig(
            strategy_config=strategy_config,
            start_date=date.fromisoformat(start_date) if start_date else date(2024, 1, 1),
            end_date=date.fromisoformat(end_date) if end_date else date(2024, 12, 31),
            initial_capital=Decimal(str(initial_capital)),
            commission_buy=Decimal(str(commission_buy)),
            commission_sell=Decimal(str(commission_sell)),
            slippage=Decimal(str(slippage)),
            max_holdings=max_holdings,
            stop_loss_pct=stop_loss_pct,
            trailing_stop_pct=trailing_stop_pct,
            max_holding_days=max_holding_days,
            allocation_mode=allocation_mode,
            enable_market_risk=enable_market_risk,
            trend_stop_ma=trend_stop_ma,
        )

        engine = BacktestEngine()

        # TODO: 从数据库加载回测区间内的全市场 K 线数据和指数数据
        # kline_data = await load_kline_data(config.start_date, config.end_date)
        # index_data = await load_index_data(config.start_date, config.end_date)
        kline_data = {}
        index_data = {}

        result = engine.run_backtest(
            config=config,
            kline_data=kline_data,
            index_data=index_data if enable_market_risk else None,
        )

        logger.info(
            "回测任务完成 run_id=%s trades=%d return=%.4f",
            run_id, result.total_trades, result.total_return,
        )

        return {
            "run_id": run_id,
            "status": "DONE",
            "result": {
                "annual_return": result.annual_return,
                "total_return": result.total_return,
                "win_rate": result.win_rate,
                "profit_loss_ratio": result.profit_loss_ratio,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "calmar_ratio": result.calmar_ratio,
                "total_trades": result.total_trades,
                "avg_holding_days": result.avg_holding_days,
            },
        }

    except Exception as exc:
        logger.error("回测任务失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return {
            "run_id": run_id,
            "status": "FAILED",
            "error": str(exc),
        }
