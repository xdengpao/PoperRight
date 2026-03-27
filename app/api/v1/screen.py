"""
选股 API

- POST /screen/run          — 执行选股
- GET  /screen/results       — 查询选股结果
- GET  /screen/export        — 导出选股结果
- CRUD /strategies           — 策略模板管理
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["选股"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class FactorConditionIn(BaseModel):
    factor_name: str
    operator: str
    threshold: float | None = None
    params: dict = Field(default_factory=dict)


class StrategyConfigIn(BaseModel):
    factors: list[FactorConditionIn] = Field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"
    weights: dict[str, float] = Field(default_factory=dict)
    ma_periods: list[int] = Field(default_factory=lambda: [5, 10, 20, 60, 120, 250])
    indicator_params: dict = Field(default_factory=dict)


class ScreenRunRequest(BaseModel):
    strategy_id: UUID | None = None
    strategy_config: StrategyConfigIn | None = None
    screen_type: Literal["EOD", "REALTIME"] = "EOD"


class StrategyTemplateIn(BaseModel):
    name: str
    config: StrategyConfigIn
    is_active: bool = False


class StrategyTemplateUpdate(BaseModel):
    name: str | None = None
    config: StrategyConfigIn | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 选股执行
# ---------------------------------------------------------------------------


@router.post("/screen/run")
async def run_screen(body: ScreenRunRequest) -> dict:
    """执行选股（盘后/实时）。"""
    return {
        "strategy_id": str(body.strategy_id or uuid4()),
        "screen_type": body.screen_type,
        "screen_time": datetime.now().isoformat(),
        "items": [],
        "is_complete": True,
    }


@router.get("/screen/results")
async def get_screen_results(
    strategy_id: UUID | None = Query(None),
    screen_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询选股结果。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.get("/screen/export")
async def export_screen_results(
    strategy_id: UUID | None = Query(None),
    format: str = Query("xlsx", description="导出格式: xlsx/csv"),
) -> dict:
    """导出选股结果为 Excel/CSV（stub：返回下载链接占位）。"""
    return {"download_url": f"/api/v1/screen/export/file?format={format}", "status": "pending"}


# ---------------------------------------------------------------------------
# 策略模板 CRUD
# ---------------------------------------------------------------------------


@router.get("/strategies")
async def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询当前用户的策略模板列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/strategies", status_code=201)
async def create_strategy(body: StrategyTemplateIn) -> dict:
    """创建策略模板。"""
    return {
        "id": str(uuid4()),
        "name": body.name,
        "config": body.config.model_dump(),
        "is_active": body.is_active,
        "created_at": datetime.now().isoformat(),
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: UUID) -> dict:
    """查询单个策略模板详情。"""
    return {"id": str(strategy_id), "name": "stub", "config": {}, "is_active": False}


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: UUID, body: StrategyTemplateUpdate) -> dict:
    """更新策略模板。"""
    return {"id": str(strategy_id), "updated": True}


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: UUID) -> dict:
    """删除策略模板。"""
    return {"id": str(strategy_id), "deleted": True}
