"""
回测 API

- POST /backtest/run             — 启动回测
- GET  /backtest/{id}/result     — 查询回测结果
- POST /backtest/optimize        — 启动参数优化
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/backtest", tags=["回测"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class BacktestRunRequest(BaseModel):
    strategy_id: UUID | None = None
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    commission_buy: float = 0.0003
    commission_sell: float = 0.0013
    slippage: float = 0.001
    max_holdings: int = 10
    stop_loss_pct: float = 0.08
    trailing_stop_pct: float = 0.05
    max_holding_days: int = 20
    allocation_mode: str = "equal"  # "equal" | "score_weighted"
    enable_market_risk: bool = True
    trend_stop_ma: int = 20


class OptimizeRequest(BaseModel):
    strategy_id: UUID
    start_date: date
    end_date: date
    method: Literal["grid", "genetic"] = "grid"
    param_grid: dict = Field(default_factory=dict)
    initial_capital: float = 1_000_000.0


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.post("/run", status_code=202)
async def run_backtest(body: BacktestRunRequest) -> dict:
    """启动回测任务（异步）。"""
    from app.tasks.backtest import run_backtest_task

    run_id = str(uuid4())
    run_backtest_task.delay(
        run_id=run_id,
        strategy_id=str(body.strategy_id) if body.strategy_id else None,
        start_date=body.start_date.isoformat(),
        end_date=body.end_date.isoformat(),
        initial_capital=body.initial_capital,
        commission_buy=body.commission_buy,
        commission_sell=body.commission_sell,
        slippage=body.slippage,
        max_holdings=body.max_holdings,
        stop_loss_pct=body.stop_loss_pct,
        trailing_stop_pct=body.trailing_stop_pct,
        max_holding_days=body.max_holding_days,
        allocation_mode=body.allocation_mode,
        enable_market_risk=body.enable_market_risk,
        trend_stop_ma=body.trend_stop_ma,
    )
    return {
        "id": run_id,
        "strategy_id": str(body.strategy_id) if body.strategy_id else None,
        "status": "PENDING",
        "message": "回测任务已提交",
    }


@router.get("/{backtest_id}/result")
async def get_backtest_result(backtest_id: UUID) -> dict:
    """查询回测结果。"""
    return {
        "id": str(backtest_id),
        "status": "DONE",
        "result": {
            "annual_return": 0.0,
            "total_return": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
            "total_trades": 0,
            "avg_holding_days": 0.0,
            "equity_curve": [],
            "trade_records": [],
        },
    }


@router.post("/optimize", status_code=202)
async def run_optimize(body: OptimizeRequest) -> dict:
    """启动参数优化任务（异步）。"""
    run_id = str(uuid4())
    return {
        "id": run_id,
        "strategy_id": str(body.strategy_id),
        "method": body.method,
        "status": "PENDING",
        "message": "参数优化任务已提交",
    }
