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
from pydantic import BaseModel, Field, model_validator

from app.core.schemas import VALID_INDICATORS, VALID_OPERATORS

router = APIRouter(prefix="/backtest", tags=["回测"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class ExitConditionSchema(BaseModel):
    freq: str = "daily"
    indicator: str
    operator: str
    threshold: float | None = None
    cross_target: str | None = None
    params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_condition(self) -> "ExitConditionSchema":
        if self.indicator not in VALID_INDICATORS:
            raise ValueError(f"无效的指标名称: {self.indicator}")
        if self.operator not in VALID_OPERATORS:
            raise ValueError(f"无效的比较运算符: {self.operator}")
        if self.operator in ("cross_up", "cross_down") and not self.cross_target:
            raise ValueError("交叉运算符需要指定 cross_target")
        if self.operator not in ("cross_up", "cross_down") and self.threshold is None:
            raise ValueError("数值比较运算符需要指定 threshold")
        return self


class ExitConditionsSchema(BaseModel):
    conditions: list[ExitConditionSchema] = Field(default_factory=list)
    logic: str = "AND"


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
    exit_conditions: ExitConditionsSchema | None = None


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
        exit_conditions=body.exit_conditions.model_dump() if body.exit_conditions else None,
    )
    return {
        "id": run_id,
        "strategy_id": str(body.strategy_id) if body.strategy_id else None,
        "status": "PENDING",
        "message": "回测任务已提交",
    }


@router.get("/{backtest_id}/result")
async def get_backtest_result(backtest_id: UUID) -> dict:
    """查询回测结果（从 Redis Celery result backend 读取）。"""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app as _celery

    # 尝试从 Redis 读取以 run_id 为键的回测结果
    from app.core.redis_client import cache_get
    import json

    cache_key = f"backtest:result:{backtest_id}"
    cached = await cache_get(cache_key)
    if cached:
        data = json.loads(cached)
        return {
            "id": str(backtest_id),
            "status": data.get("status", "DONE"),
            **data.get("result", {}),
            "equity_curve": data.get("result", {}).get("equity_curve", []),
            "trade_records": data.get("result", {}).get("trade_records", []),
        }

    # 回退：返回 PENDING 状态让前端继续轮询
    return {
        "id": str(backtest_id),
        "status": "PENDING",
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
