"""回测任务模块"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal

import redis
from sqlalchemy import create_engine, select, and_, text
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.tasks.base import BaseTask

logger = logging.getLogger(__name__)


def _get_sync_pg_url() -> str:
    """将 asyncpg URL 转为同步 psycopg2 URL。"""
    return settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


def _get_sync_ts_url() -> str:
    """将 asyncpg URL 转为同步 psycopg2 URL。"""
    return settings.timescale_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


def _redis_set(key: str, value: str, ex: int = 86400) -> None:
    """同步写入 Redis。"""
    try:
        r = redis.from_url(settings.redis_url)
        r.set(key, value, ex=ex)
        r.close()
    except Exception as exc:
        logger.warning("Redis 写入失败: %s", exc)


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
    """执行回测 Celery 任务（同步数据库访问）。"""
    logger.info("回测任务启动 run_id=%s strategy_id=%s", run_id, strategy_id)

    # 写入初始进度
    _redis_set(f"backtest:result:{run_id}", json.dumps({"status": "RUNNING", "run_id": run_id}))

    try:
        from app.core.schemas import BacktestConfig, KlineBar, StrategyConfig
        from app.services.backtest_engine import BacktestEngine

        # ── 1. 加载策略配置 ──
        strategy_config = StrategyConfig(
            factors=[], logic="AND", weights={}, ma_periods=[5, 10, 20, 60, 120],
        )

        if strategy_id:
            try:
                pg_engine = create_engine(_get_sync_pg_url())
                with Session(pg_engine) as session:
                    row = session.execute(
                        text("SELECT config FROM strategy_template WHERE id = :sid"),
                        {"sid": strategy_id},
                    ).first()
                    if row and row[0]:
                        strategy_config = StrategyConfig.from_dict(row[0])
                        logger.info("已加载策略配置 strategy_id=%s", strategy_id)
                pg_engine.dispose()
            except Exception as exc:
                logger.warning("加载策略配置失败: %s", exc)

        sd = date.fromisoformat(start_date) if start_date else date(2024, 1, 1)
        ed = date.fromisoformat(end_date) if end_date else date(2024, 12, 31)

        config = BacktestConfig(
            strategy_config=strategy_config,
            start_date=sd,
            end_date=ed,
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

        # ── 2. 从 TimescaleDB 加载 K 线数据（同步） ──
        kline_data: dict[str, list[KlineBar]] = {}
        index_data: dict[str, list[KlineBar]] = {}

        try:
            ts_engine = create_engine(_get_sync_ts_url())
            with Session(ts_engine) as session:
                rows = session.execute(
                    text("""
                        SELECT symbol, time, open, high, low, close, volume, amount, turnover, vol_ratio
                        FROM kline
                        WHERE freq = '1d' AND time >= :start AND time <= :end
                        ORDER BY symbol, time
                    """),
                    {"start": sd.isoformat(), "end": ed.isoformat()},
                ).fetchall()

                for row in rows:
                    sym = row[0]
                    bar = KlineBar(
                        time=row[1],
                        symbol=sym,
                        freq="1d",
                        open=Decimal(str(row[2] or 0)),
                        high=Decimal(str(row[3] or 0)),
                        low=Decimal(str(row[4] or 0)),
                        close=Decimal(str(row[5] or 0)),
                        volume=int(row[6] or 0),
                        amount=Decimal(str(row[7] or 0)),
                        turnover=Decimal(str(row[8] or 0)),
                        vol_ratio=Decimal(str(row[9] or 0)),
                    )
                    if sym in ("000001.SH", "399006.SZ"):
                        index_data.setdefault(sym, []).append(bar)
                    else:
                        kline_data.setdefault(sym, []).append(bar)

            ts_engine.dispose()
            logger.info("K 线数据加载完成: %d 只股票, %d 条指数",
                        len(kline_data), sum(len(v) for v in index_data.values()))
        except Exception as exc:
            logger.warning("K 线数据加载失败: %s", exc)

        # ── 3. 执行回测 ──
        engine = BacktestEngine()
        result = engine.run_backtest(
            config=config,
            kline_data=kline_data,
            index_data=index_data if enable_market_risk else None,
        )

        logger.info("回测完成 run_id=%s trades=%d return=%.4f",
                     run_id, result.total_trades, result.total_return)

        # ── 4. 构建结果并写入 Redis ──
        result_data = {
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
                "equity_curve": [
                    [d.isoformat() if hasattr(d, "isoformat") else str(d), float(v)]
                    for d, v in (result.equity_curve or [])
                ],
                "trade_records": [
                    {
                        "date": t.get("date", "") if isinstance(t, dict) else str(getattr(t, "date", "")),
                        "created_at": t.get("date", "") if isinstance(t, dict) else str(getattr(t, "date", "")),
                        "symbol": t.get("symbol", "") if isinstance(t, dict) else getattr(t, "symbol", ""),
                        "action": t.get("action", "") if isinstance(t, dict) else getattr(t, "action", ""),
                        "direction": t.get("action", "") if isinstance(t, dict) else getattr(t, "action", ""),
                        "price": float(t.get("price", 0) if isinstance(t, dict) else getattr(t, "price", 0)),
                        "quantity": t.get("quantity", 0) if isinstance(t, dict) else getattr(t, "quantity", 0),
                        "cost": float(t.get("cost", 0) if isinstance(t, dict) else getattr(t, "cost", 0)),
                        "commission": float(t.get("cost", 0) if isinstance(t, dict) else getattr(t, "cost", 0)),
                        "amount": float(t.get("amount", 0) if isinstance(t, dict) else getattr(t, "amount", 0)),
                        "status": "FILLED",
                    }
                    for t in (result.trade_records or [])
                ],
            },
        }

        _redis_set(f"backtest:result:{run_id}", json.dumps(result_data, default=str))
        return result_data

    except Exception as exc:
        logger.error("回测任务失败 run_id=%s: %s", run_id, exc, exc_info=True)
        fail_data = {"run_id": run_id, "status": "FAILED", "error": str(exc)}
        _redis_set(f"backtest:result:{run_id}", json.dumps(fail_data))
        return fail_data
