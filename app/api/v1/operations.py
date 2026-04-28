"""
实操模块 API

- CRUD  /operations/plans                          — 交易计划管理
- GET   /operations/plans/{id}/candidates           — 候选股查询
- POST  /operations/plans/{id}/buy                  — 执行买入
- GET   /operations/plans/{id}/positions             — 计划持仓
- POST  /operations/plans/{id}/positions/{pid}/sell  — 确认卖出
- GET   /operations/plans/{id}/checklist             — 复盘清单
- GET   /operations/plans/{id}/buy-records           — 买入记录
- GET/PUT /operations/plans/{id}/market-profile      — 市场环境配置
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_pg_session
from app.core.schemas import (
    CandidateFilterConfig,
    MarketProfileConfig,
    PlanStatus,
    PositionControlConfig,
    StageStopConfig,
)
from app.services.operations_service import OperationsService

router = APIRouter(prefix="/operations", tags=["实操"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class CreatePlanRequest(BaseModel):
    name: str = Field(max_length=100)
    strategy_id: str
    candidate_filter: dict | None = None
    stage_stop_config: dict | None = None
    position_control: dict | None = None
    market_profile: dict | None = None


class UpdatePlanRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    candidate_filter: dict | None = None
    stage_stop_config: dict | None = None
    position_control: dict | None = None
    market_profile: dict | None = None


class StatusUpdateRequest(BaseModel):
    status: Literal["ACTIVE", "PAUSED", "ARCHIVED"]


class BuyRequest(BaseModel):
    candidate_id: str | None = None
    symbol: str
    buy_price: float
    buy_quantity: int = Field(gt=0)
    trend_score: float | None = None
    sector_rank: int | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _standardize(cls, v: str) -> str:
        from app.core.symbol_utils import to_standard
        return to_standard(v)


class ManualBuyRequest(BaseModel):
    symbol: str
    buy_price: float
    buy_quantity: int = Field(gt=0)
    buy_time: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _standardize(cls, v: str) -> str:
        from app.core.symbol_utils import to_standard
        return to_standard(v)


class SellRequest(BaseModel):
    sell_price: float
    sell_quantity: int | None = None


class StopAdjustRequest(BaseModel):
    new_stage: int | None = Field(None, ge=1, le=5)
    new_stop_price: float | None = None


class MarketProfileRequest(BaseModel):
    normal: dict | None = None
    caution: dict | None = None
    danger: dict | None = None


# ---------------------------------------------------------------------------
# 交易计划 CRUD
# ---------------------------------------------------------------------------

# 临时用户 ID（正式环境从 JWT 获取）
_TEMP_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("/plans")
async def list_plans(
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询所有交易计划"""
    plans = await OperationsService.list_plans(pg_session, _TEMP_USER_ID)
    return {"items": plans, "total": len(plans)}


@router.post("/plans", status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """创建交易计划"""
    try:
        plan = await OperationsService.create_plan(
            session=pg_session,
            user_id=_TEMP_USER_ID,
            name=body.name,
            strategy_id=UUID(body.strategy_id),
            candidate_filter=CandidateFilterConfig.from_dict(body.candidate_filter or {}),
            stage_stop_config=StageStopConfig.from_dict(body.stage_stop_config or {}),
            position_control=PositionControlConfig.from_dict(body.position_control or {}),
            market_profile=MarketProfileConfig.from_dict(body.market_profile or {}),
        )
        await pg_session.commit()
        return {"id": str(plan.id), "name": plan.name, "status": plan.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询单个计划详情"""
    from app.models.operations import TradingPlan
    plan = await pg_session.get(TradingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="交易计划不存在")
    return {
        "id": str(plan.id),
        "name": plan.name,
        "strategy_id": str(plan.strategy_id),
        "status": plan.status,
        "candidate_filter": plan.candidate_filter,
        "stage_stop_config": plan.stage_stop_config,
        "position_control": plan.position_control,
        "market_profile": plan.market_profile,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: UUID,
    body: UpdatePlanRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """更新计划配置"""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        plan = await OperationsService.update_plan(pg_session, plan_id, updates)
        await pg_session.commit()
        return {"id": str(plan.id), "updated": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """删除交易计划"""
    try:
        await OperationsService.delete_plan(pg_session, plan_id)
        await pg_session.commit()
        return {"id": str(plan_id), "deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/plans/{plan_id}/status")
async def update_plan_status(
    plan_id: UUID,
    body: StatusUpdateRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """更新计划状态"""
    try:
        plan = await OperationsService.update_plan_status(
            pg_session, plan_id, PlanStatus(body.status)
        )
        await pg_session.commit()
        return {"id": str(plan.id), "status": plan.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# 候选股
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/candidates")
async def get_candidates(
    plan_id: UUID,
    screen_date: date | None = Query(None, alias="date"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询候选股列表"""
    items = await OperationsService.get_candidates(pg_session, plan_id, screen_date)
    return {"items": items, "total": len(items)}


@router.delete("/plans/{plan_id}/candidates/{candidate_id}")
async def skip_candidate(
    plan_id: UUID,
    candidate_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """跳过候选股"""
    await OperationsService.skip_candidate(pg_session, candidate_id)
    await pg_session.commit()
    return {"id": str(candidate_id), "status": "SKIPPED"}


# ---------------------------------------------------------------------------
# 买入
# ---------------------------------------------------------------------------


@router.post("/plans/{plan_id}/buy", status_code=201)
async def execute_buy(
    plan_id: UUID,
    body: BuyRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """执行买入"""
    try:
        record = await OperationsService.execute_buy(
            session=pg_session,
            plan_id=plan_id,
            candidate_id=UUID(body.candidate_id) if body.candidate_id else None,
            symbol=body.symbol,
            buy_price=Decimal(str(body.buy_price)),
            buy_quantity=body.buy_quantity,
            trend_score=Decimal(str(body.trend_score)) if body.trend_score else None,
            sector_rank=body.sector_rank,
        )
        await pg_session.commit()
        return {
            "id": str(record.id),
            "symbol": record.symbol,
            "buy_price": float(record.buy_price),
            "initial_stop_price": float(record.initial_stop_price),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plans/{plan_id}/buy/manual", status_code=201)
async def manual_buy(
    plan_id: UUID,
    body: ManualBuyRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """手动补录买入"""
    try:
        record = await OperationsService.execute_buy(
            session=pg_session,
            plan_id=plan_id,
            candidate_id=None,
            symbol=body.symbol,
            buy_price=Decimal(str(body.buy_price)),
            buy_quantity=body.buy_quantity,
        )
        await pg_session.commit()
        return {"id": str(record.id), "symbol": record.symbol, "is_manual": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 持仓
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/positions")
async def get_positions(
    plan_id: UUID,
    status: str | None = Query(None, description="HOLDING/PENDING_SELL/CLOSED"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询计划持仓"""
    from app.core.schemas import PositionStatus as PS
    ps = PS(status) if status else None
    items = await OperationsService.get_plan_positions(pg_session, plan_id, ps)
    return {"items": items, "total": len(items)}


@router.post("/plans/{plan_id}/positions/{position_id}/sell")
async def confirm_sell(
    plan_id: UUID,
    position_id: UUID,
    body: SellRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """确认卖出"""
    try:
        pos = await OperationsService.confirm_sell(
            pg_session, position_id,
            Decimal(str(body.sell_price)),
            body.sell_quantity,
        )
        await pg_session.commit()
        return {
            "id": str(pos.id),
            "status": pos.status,
            "pnl": float(pos.pnl) if pos.pnl else 0,
            "pnl_pct": pos.pnl_pct,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/plans/{plan_id}/positions/{position_id}/stop")
async def adjust_stop(
    plan_id: UUID,
    position_id: UUID,
    body: StopAdjustRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """手动调整止损"""
    try:
        pos = await OperationsService.adjust_stop(
            pg_session, position_id,
            body.new_stage,
            Decimal(str(body.new_stop_price)) if body.new_stop_price else None,
        )
        await pg_session.commit()
        return {"id": str(pos.id), "stop_stage": pos.stop_stage, "stop_price": float(pos.stop_price)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# 复盘清单 & 买入记录 & 市场环境
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/checklist")
async def get_checklist(
    plan_id: UUID,
    check_date: date | None = Query(None, alias="date"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询复盘清单"""
    result = await OperationsService.get_checklist(pg_session, plan_id, check_date)
    if result is None:
        return {"items": [], "summary_level": "OK", "check_date": (check_date or date.today()).isoformat()}
    return result


@router.get("/plans/{plan_id}/checklist/history")
async def get_checklist_history(
    plan_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询复盘清单历史"""
    items = await OperationsService.get_checklist_history(pg_session, plan_id, start, end)
    return {"items": items, "total": len(items)}


@router.get("/plans/{plan_id}/buy-records")
async def get_buy_records(
    plan_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询买入记录"""
    return await OperationsService.get_buy_records(pg_session, plan_id, page, page_size)


@router.get("/plans/{plan_id}/market-profile")
async def get_market_profile(
    plan_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询市场环境配置"""
    try:
        config = await OperationsService.get_market_profile(pg_session, plan_id)
        return config.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/plans/{plan_id}/market-profile")
async def update_market_profile(
    plan_id: UUID,
    body: MarketProfileRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """更新市场环境配置"""
    try:
        current = await OperationsService.get_market_profile(pg_session, plan_id)
        if body.normal:
            current.normal = body.normal
        if body.caution:
            current.caution = body.caution
        if body.danger:
            current.danger = body.danger
        await OperationsService.update_market_profile(pg_session, plan_id, current)
        await pg_session.commit()
        return {"updated": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
