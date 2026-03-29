"""
系统管理 API

- CRUD /admin/users             — 用户管理
- GET  /admin/system-health     — 系统健康状态
- GET  /admin/logs              — 日志查询
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["系统管理"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class UserCreateIn(BaseModel):
    username: str
    password: str
    role: str = "TRADER"


class UserUpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 用户管理 CRUD
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询用户列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/users", status_code=201)
async def create_user(body: UserCreateIn) -> dict:
    """创建用户。"""
    return {
        "id": str(uuid4()),
        "username": body.username,
        "role": body.role,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }


@router.get("/users/{user_id}")
async def get_user(user_id: UUID) -> dict:
    """查询单个用户详情。"""
    return {"id": str(user_id), "username": "stub", "role": "TRADER", "is_active": True}


@router.put("/users/{user_id}")
async def update_user(user_id: UUID, body: UserUpdateIn) -> dict:
    """更新用户信息。"""
    return {"id": str(user_id), "updated": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: UUID) -> dict:
    """删除用户。"""
    return {"id": str(user_id), "deleted": True}


class RoleUpdateIn(BaseModel):
    role: str


@router.patch("/users/{user_id}/role")
async def change_user_role(user_id: UUID, body: RoleUpdateIn) -> dict:
    """修改用户角色。"""
    return {"id": str(user_id), "role": body.role, "updated": True}


@router.post("/backup")
async def trigger_backup() -> dict:
    """触发数据库备份任务。"""
    return {"message": "备份任务已触发", "status": "pending"}


@router.post("/restore")
async def trigger_restore() -> dict:
    """触发数据库恢复任务。"""
    return {"message": "恢复任务已触发", "status": "pending"}


# ---------------------------------------------------------------------------
# 系统健康 & 日志
# ---------------------------------------------------------------------------


@router.get("/system-health")
async def get_system_health() -> dict:
    """查询系统健康状态。"""
    return {
        "status": "ok",
        "components": {
            "database": "ok",
            "redis": "ok",
            "celery": "ok",
            "data_api": "ok",
            "broker_api": "ok",
        },
        "uptime_seconds": 0,
        "checked_at": datetime.now().isoformat(),
    }


@router.get("/logs")
async def get_logs(
    user_id: UUID | None = Query(None),
    action: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """查询操作日志。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}
