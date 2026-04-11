"""
回测 API

- POST /backtest/run             — 启动回测
- GET  /backtest/{id}/result     — 查询回测结果
- POST /backtest/optimize        — 启动参数优化
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_pg_session
from app.core.schemas import VALID_FREQS, VALID_INDICATORS, VALID_OPERATORS
from app.models.backtest import ExitConditionTemplate
from app.models.user import AppUser

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
        # 向后兼容：接受 "minute" 并映射为 "1min"
        if self.freq == "minute":
            self.freq = "1min"
        if self.freq not in VALID_FREQS:
            raise ValueError(
                f"无效的数据源频率: {self.freq}，支持: daily, 1min, 5min, 15min, 30min, 60min"
            )
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


class ExitTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    exit_conditions: ExitConditionsSchema


class ExitTemplateUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    exit_conditions: ExitConditionsSchema | None = None


class ExitTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    exit_conditions: dict
    created_at: str
    updated_at: str


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


# ---------------------------------------------------------------------------
# 模版辅助函数
# ---------------------------------------------------------------------------


def _exit_template_to_dict(t: ExitConditionTemplate) -> dict:
    """将 ORM 对象转为 API 响应 dict。"""
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "exit_conditions": t.exit_conditions or {},
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


async def _get_template_or_404(
    template_id: UUID, session: AsyncSession
) -> ExitConditionTemplate:
    result = await session.execute(
        select(ExitConditionTemplate).where(ExitConditionTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模版不存在")
    return template


# ---------------------------------------------------------------------------
# 模版 CRUD 端点
# ---------------------------------------------------------------------------


@router.post("/exit-templates", status_code=201)
async def create_exit_template(
    body: ExitTemplateCreateRequest,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """创建平仓条件模版。"""
    # 1. 检查同名模版
    existing = await pg_session.execute(
        select(ExitConditionTemplate).where(
            ExitConditionTemplate.user_id == current_user.id,
            ExitConditionTemplate.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"模版名称已存在: {body.name}")

    # 2. 检查数量上限（50 个）
    count_result = await pg_session.execute(
        select(func.count()).select_from(ExitConditionTemplate).where(
            ExitConditionTemplate.user_id == current_user.id
        )
    )
    if count_result.scalar() >= 50:
        raise HTTPException(
            status_code=409,
            detail="模版数量已达上限（50个），请删除不需要的模版后重试",
        )

    # 3. 创建模版
    template = ExitConditionTemplate(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        exit_conditions=body.exit_conditions.model_dump(),
    )
    pg_session.add(template)
    await pg_session.flush()
    return _exit_template_to_dict(template)


@router.get("/exit-templates")
async def list_exit_templates(
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> list:
    """列出当前用户所有平仓条件模版，按 updated_at 降序。"""
    stmt = (
        select(ExitConditionTemplate)
        .where(ExitConditionTemplate.user_id == current_user.id)
        .order_by(ExitConditionTemplate.updated_at.desc())
    )
    result = await pg_session.execute(stmt)
    return [_exit_template_to_dict(t) for t in result.scalars().all()]


@router.get("/exit-templates/{template_id}")
async def get_exit_template(
    template_id: UUID,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """获取指定平仓条件模版。"""
    template = await _get_template_or_404(template_id, pg_session)
    return _exit_template_to_dict(template)


@router.put("/exit-templates/{template_id}")
async def update_exit_template(
    template_id: UUID,
    body: ExitTemplateUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """更新指定平仓条件模版。"""
    template = await _get_template_or_404(template_id, pg_session)

    # 所有权校验
    if template.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模版")

    # 若更新 name，校验唯一性
    if body.name is not None and body.name != template.name:
        existing = await pg_session.execute(
            select(ExitConditionTemplate).where(
                ExitConditionTemplate.user_id == current_user.id,
                ExitConditionTemplate.name == body.name,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"模版名称已存在: {body.name}")
        template.name = body.name

    if body.description is not None:
        template.description = body.description

    if body.exit_conditions is not None:
        template.exit_conditions = body.exit_conditions.model_dump()

    template.updated_at = datetime.now(timezone.utc)
    await pg_session.flush()
    return _exit_template_to_dict(template)


@router.delete("/exit-templates/{template_id}")
async def delete_exit_template(
    template_id: UUID,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """删除指定平仓条件模版。"""
    template = await _get_template_or_404(template_id, pg_session)

    # 所有权校验
    if template.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模版")

    await pg_session.delete(template)
    await pg_session.flush()
    return {"id": str(template_id), "deleted": True}
