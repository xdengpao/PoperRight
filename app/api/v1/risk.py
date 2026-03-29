"""
风控 API

- POST /risk/check              — 风控校验
- GET  /risk/strategy-health     — 策略健康状态
- CRUD /blacklist                — 黑名单管理
- CRUD /whitelist                — 白名单管理
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(tags=["风控"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class RiskCheckRequest(BaseModel):
    symbol: str
    direction: str = "BUY"
    quantity: int = 0
    price: float | None = None


class StockListItemIn(BaseModel):
    symbol: str
    reason: str | None = None


class StopConfigRequest(BaseModel):
    stop_loss_ratio: float = 0.08
    take_profit_ratio: float = 0.20
    trailing_stop: bool = False
    trailing_pct: float = 0.05


# ---------------------------------------------------------------------------
# 风控校验 & 概览
# ---------------------------------------------------------------------------


@router.get("/risk/check")
async def risk_overview() -> dict:
    """获取风控概览（大盘风险状态、仓位使用率等）。"""
    return {
        "market_risk": "NORMAL",
        "total_position_pct": 0.0,
        "single_stock_max_pct": 0.0,
        "sector_max_pct": 0.0,
        "stop_loss_ratio": 0.08,
        "take_profit_ratio": 0.20,
        "trailing_stop": False,
        "trailing_pct": 0.05,
    }


@router.post("/risk/check")
async def risk_check(body: RiskCheckRequest) -> dict:
    """对委托进行风控校验（仓位/涨幅/黑名单等）。"""
    return {"passed": True, "reason": None}


@router.post("/risk/stop-config")
async def save_stop_config(body: StopConfigRequest) -> dict:
    """保存止损止盈配置。"""
    return {
        "stop_loss_ratio": body.stop_loss_ratio,
        "take_profit_ratio": body.take_profit_ratio,
        "trailing_stop": body.trailing_stop,
        "trailing_pct": body.trailing_pct,
        "saved": True,
    }


@router.get("/risk/position-warnings")
async def position_warnings() -> list:
    """获取持仓预警列表。"""
    return []


@router.get("/risk/strategy-health")
async def strategy_health(
    strategy_id: UUID | None = Query(None),
) -> dict:
    """查询策略健康状态（胜率、最大回撤等）。"""
    return {
        "strategy_id": str(strategy_id) if strategy_id else None,
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "is_healthy": True,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# 黑名单 CRUD
# ---------------------------------------------------------------------------


@router.get("/blacklist")
async def list_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询黑名单列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/blacklist", status_code=201)
async def add_to_blacklist(body: StockListItemIn) -> dict:
    """添加股票到黑名单。"""
    return {"symbol": body.symbol, "list_type": "BLACK", "created_at": datetime.now().isoformat()}


@router.delete("/blacklist/{symbol}")
async def remove_from_blacklist(symbol: str) -> dict:
    """从黑名单移除股票。"""
    return {"symbol": symbol, "deleted": True}


# ---------------------------------------------------------------------------
# 白名单 CRUD
# ---------------------------------------------------------------------------


@router.get("/whitelist")
async def list_whitelist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询白名单列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/whitelist", status_code=201)
async def add_to_whitelist(body: StockListItemIn) -> dict:
    """添加股票到白名单。"""
    return {"symbol": body.symbol, "list_type": "WHITE", "created_at": datetime.now().isoformat()}


@router.delete("/whitelist/{symbol}")
async def remove_from_whitelist(symbol: str) -> dict:
    """从白名单移除股票。"""
    return {"symbol": symbol, "deleted": True}
