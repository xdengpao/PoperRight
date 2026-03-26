"""
API v1 路由入口

将各子模块路由聚合到统一的 v1 Router。
"""

from fastapi import APIRouter

from app.api.v1.ws import router as ws_router

router = APIRouter()

router.include_router(ws_router, tags=["WebSocket"])
