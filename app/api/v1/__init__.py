"""
API v1 路由入口

将各子模块路由聚合到统一的 v1 Router。
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.data import router as data_router
from app.api.v1.pool import pool_router
from app.api.v1.review import router as review_router
from app.api.v1.risk import router as risk_router
from app.api.v1.screen import router as screen_router
from app.api.v1.sector import router as sector_router
from app.api.v1.trade import router as trade_router
from app.api.v1.tushare import router as tushare_router
from app.api.v1.ws import router as ws_router

router = APIRouter()

router.include_router(ws_router, tags=["WebSocket"])
router.include_router(auth_router)
router.include_router(data_router)
router.include_router(screen_router)
router.include_router(risk_router)
router.include_router(backtest_router)
router.include_router(trade_router)
router.include_router(review_router)
router.include_router(admin_router)
router.include_router(sector_router)
router.include_router(pool_router)
router.include_router(tushare_router)


# ---------------------------------------------------------------------------
# 兼容路由：/market/overview → /data/market/overview
# 部分前端页面可能缓存了旧路径，此处做透传兼容
# ---------------------------------------------------------------------------
from fastapi.responses import RedirectResponse


@router.get("/market/overview", include_in_schema=False)
async def market_overview_compat():
    """兼容旧路径，重定向到 /data/market/overview"""
    return RedirectResponse(url="/api/v1/data/market/overview", status_code=307)
