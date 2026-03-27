"""
交易 API

- POST   /trade/order            — 提交委托
- DELETE /trade/order/{id}       — 撤单
- GET    /trade/positions        — 查询持仓
- GET    /trade/orders           — 查询委托/成交记录
- CRUD   /trade/conditions       — 条件单管理
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/trade", tags=["交易"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class OrderRequest(BaseModel):
    symbol: str
    direction: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    quantity: int
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    mode: Literal["LIVE", "PAPER"] = "LIVE"


class ConditionOrderIn(BaseModel):
    symbol: str
    trigger_type: Literal["BREAKOUT_BUY", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP"]
    trigger_price: float
    direction: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    quantity: int
    price: float | None = None
    trailing_pct: float | None = None


class ConditionOrderUpdate(BaseModel):
    trigger_price: float | None = None
    quantity: int | None = None
    price: float | None = None
    trailing_pct: float | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 委托
# ---------------------------------------------------------------------------


@router.post("/order", status_code=201)
async def submit_order(body: OrderRequest) -> dict:
    """提交委托。"""
    return {
        "order_id": str(uuid4()),
        "symbol": body.symbol,
        "direction": body.direction,
        "order_type": body.order_type,
        "quantity": body.quantity,
        "price": body.price,
        "status": "PENDING",
        "submitted_at": datetime.now().isoformat(),
    }


@router.delete("/order/{order_id}")
async def cancel_order(order_id: UUID) -> dict:
    """撤单。"""
    return {"order_id": str(order_id), "status": "CANCELLED"}


# ---------------------------------------------------------------------------
# 持仓 & 委托记录
# ---------------------------------------------------------------------------


@router.get("/positions")
async def get_positions(
    mode: str | None = Query(None, description="LIVE/PAPER"),
) -> dict:
    """查询持仓列表。"""
    return {"positions": [], "total_assets": "0.00"}


@router.get("/orders")
async def get_orders(
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    status: str | None = Query(None, description="PENDING/FILLED/CANCELLED/REJECTED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询委托/成交记录。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


# ---------------------------------------------------------------------------
# 条件单 CRUD
# ---------------------------------------------------------------------------


@router.get("/conditions")
async def list_conditions(
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询条件单列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/conditions", status_code=201)
async def create_condition(body: ConditionOrderIn) -> dict:
    """创建条件单。"""
    return {
        "id": str(uuid4()),
        "symbol": body.symbol,
        "trigger_type": body.trigger_type,
        "trigger_price": body.trigger_price,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }


@router.get("/conditions/{condition_id}")
async def get_condition(condition_id: UUID) -> dict:
    """查询单个条件单详情。"""
    return {"id": str(condition_id), "is_active": True}


@router.put("/conditions/{condition_id}")
async def update_condition(condition_id: UUID, body: ConditionOrderUpdate) -> dict:
    """更新条件单。"""
    return {"id": str(condition_id), "updated": True}


@router.delete("/conditions/{condition_id}")
async def delete_condition(condition_id: UUID) -> dict:
    """删除条件单。"""
    return {"id": str(condition_id), "deleted": True}
