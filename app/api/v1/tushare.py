"""
Tushare 数据在线导入 API 端点

提供 Tushare 数据导入的 REST API，包括：
- GET  /health           — 检查 Tushare 连通性和 Token 配置状态
- GET  /registry         — 获取全部可导入接口列表
- POST /import           — 启动导入任务
- GET  /import/status/{task_id} — 获取导入任务进度
- POST /import/stop/{task_id}  — 停止导入任务
- GET  /import/history   — 获取最近导入记录

对应需求：22.1, 22.2, 22.3, 22.4, 20.3, 21.1, 24.5
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.services.data_engine.tushare_import_service import TushareImportService
from app.services.data_engine.tushare_registry import (
    TokenTier,
    get_all_entries,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/tushare", tags=["tushare"])


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class TushareImportRequest(BaseModel):
    """导入请求"""
    api_name: str
    params: dict = {}


class TushareImportResponse(BaseModel):
    """导入启动响应"""
    task_id: str
    log_id: int
    status: str


class TushareImportStatusResponse(BaseModel):
    """导入进度响应"""
    total: int
    completed: int
    failed: int
    status: str
    current_item: str
    error_message: str = ""


class TushareImportStopResponse(BaseModel):
    """停止导入响应"""
    message: str


class TushareHealthResponse(BaseModel):
    """Tushare 健康检查响应"""
    connected: bool
    tokens: dict


class ApiRegistryItem(BaseModel):
    """接口注册表条目"""
    api_name: str
    label: str
    category: str
    subcategory: str
    token_tier: str
    required_params: list[str]
    optional_params: list[str]
    token_available: bool
    vip_variant: str | None = None


class TushareImportLogItem(BaseModel):
    """导入历史记录条目"""
    id: int
    api_name: str
    params_json: dict | None
    status: str
    record_count: int
    error_message: str | None
    celery_task_id: str | None
    extra_info: dict | None = None
    started_at: str | None
    finished_at: str | None


# ---------------------------------------------------------------------------
# 端点实现
# ---------------------------------------------------------------------------


@router.get("/health")
async def check_tushare_health() -> TushareHealthResponse:
    """检查 Tushare 连通性和 Token 配置状态"""
    svc = TushareImportService()
    result = await svc.check_health()
    return TushareHealthResponse(
        connected=result["connected"],
        tokens=result["tokens"],
    )


@router.get("/registry")
async def get_api_registry() -> list[ApiRegistryItem]:
    """获取全部可导入接口列表（前端渲染菜单用）"""
    entries = get_all_entries()

    # Token 可用性映射：根据配置判断各级别 Token 是否已配置
    token_available_map = {
        TokenTier.BASIC: bool(settings.tushare_token_basic or settings.tushare_api_token),
        TokenTier.ADVANCED: bool(settings.tushare_token_advanced or settings.tushare_api_token),
        TokenTier.PREMIUM: bool(settings.tushare_token_premium or settings.tushare_api_token),
        TokenTier.SPECIAL: bool(settings.tushare_token_special or settings.tushare_api_token),
    }

    items = []
    for entry in entries.values():
        items.append(ApiRegistryItem(
            api_name=entry.api_name,
            label=entry.label,
            category=entry.category,
            subcategory=entry.subcategory,
            token_tier=entry.token_tier.value,
            required_params=[p.value for p in entry.required_params],
            optional_params=[p.value for p in entry.optional_params],
            token_available=token_available_map.get(entry.token_tier, False),
            vip_variant=entry.vip_variant,
        ))

    return items


@router.post("/import")
async def start_import(body: TushareImportRequest) -> TushareImportResponse:
    """启动导入任务"""
    svc = TushareImportService()
    try:
        result = await svc.start_import(body.api_name, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return TushareImportResponse(
        task_id=result["task_id"],
        log_id=result["log_id"],
        status=result["status"],
    )


@router.get("/import/status/{task_id}")
async def get_import_status(task_id: str) -> TushareImportStatusResponse:
    """获取导入任务进度"""
    svc = TushareImportService()
    result = await svc.get_import_status(task_id)
    return TushareImportStatusResponse(
        total=result.get("total", 0),
        completed=result.get("completed", 0),
        failed=result.get("failed", 0),
        status=result.get("status", "unknown"),
        current_item=result.get("current_item", ""),
        error_message=result.get("error_message", ""),
    )


@router.post("/import/stop/{task_id}")
async def stop_import(task_id: str) -> TushareImportStopResponse:
    """停止导入任务"""
    svc = TushareImportService()
    result = await svc.stop_import(task_id)
    return TushareImportStopResponse(message=result["message"])


@router.get("/import/last-times")
async def get_last_import_times() -> dict[str, str]:
    """获取每个 API 接口的最近成功导入时间"""
    svc = TushareImportService()
    return await svc.get_last_import_times()


@router.get("/import/running")
async def get_running_tasks() -> list[TushareImportLogItem]:
    """获取所有 running 状态的导入任务（前端恢复活跃任务用）"""
    svc = TushareImportService()
    records = await svc.get_running_tasks()
    return [TushareImportLogItem(**record) for record in records]


@router.get("/import/history")
async def get_import_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[TushareImportLogItem]:
    """获取最近导入记录"""
    svc = TushareImportService()
    records = await svc.get_import_history(limit=limit)
    return [TushareImportLogItem(**record) for record in records]
