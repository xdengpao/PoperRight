"""
Tushare 数据预览 API 端点

提供已导入 Tushare 数据的只读预览查询接口，包括：
- GET  /{api_name}            — 查询预览数据（分页、时间筛选、增量查询）
- GET  /{api_name}/stats      — 获取数据统计信息
- GET  /{api_name}/import-logs — 获取该接口的导入记录列表

本模块完全独立于现有 tushare.py 中的导入端点，不修改任何导入功能代码。
所有查询均为只读 SELECT 操作。

对应需求：8.1-8.6, 9.3
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import DBAPIError, OperationalError

from app.services.data_engine.tushare_preview_service import (
    ImportLogItem,
    PreviewDataResponse,
    PreviewStatsResponse,
    TusharePreviewService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/tushare/preview", tags=["tushare-preview"])


# ---------------------------------------------------------------------------
# 端点实现
# ---------------------------------------------------------------------------


@router.get("/{api_name}")
async def query_preview_data(
    api_name: str,
    page: int | None = Query(default=None, description="页码，最小 1"),
    page_size: int | None = Query(default=None, description="每页条数，范围 [1, 100]，默认 50"),
    import_time_start: datetime | None = Query(default=None, description="导入时间范围起始"),
    import_time_end: datetime | None = Query(default=None, description="导入时间范围结束"),
    data_time_start: str | None = Query(default=None, description="数据时间范围起始"),
    data_time_end: str | None = Query(default=None, description="数据时间范围结束"),
    incremental: bool = Query(default=False, description="是否增量查询"),
    import_log_id: int | None = Query(default=None, description="指定导入记录 ID"),
) -> PreviewDataResponse:
    """查询预览数据

    根据 api_name 从注册表获取元数据，动态查询对应数据表。
    支持按导入时间、数据时间过滤，以及增量查询模式。
    """
    # 校验时间范围：import_time_start 不能晚于 import_time_end
    if import_time_start and import_time_end and import_time_start > import_time_end:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    svc = TusharePreviewService()
    try:
        return await svc.query_preview_data(
            api_name,
            page=page,
            page_size=page_size,
            import_time_start=import_time_start,
            import_time_end=import_time_end,
            data_time_start=data_time_start,
            data_time_end=data_time_end,
            incremental=incremental,
            import_log_id=import_log_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OperationalError, DBAPIError) as exc:
        logger.error("数据库连接异常: %s", exc)
        raise HTTPException(status_code=503, detail="数据库连接不可用") from exc


@router.get("/{api_name}/stats")
async def query_stats(api_name: str) -> PreviewStatsResponse:
    """获取数据统计信息

    返回指定接口数据表的总记录数、最早/最晚数据时间、最近导入时间。
    """
    svc = TusharePreviewService()
    try:
        return await svc.query_stats(api_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OperationalError, DBAPIError) as exc:
        logger.error("数据库连接异常: %s", exc)
        raise HTTPException(status_code=503, detail="数据库连接不可用") from exc


@router.get("/{api_name}/import-logs")
async def query_import_logs(
    api_name: str,
    limit: int = Query(default=20, ge=1, le=100, description="返回记录数上限"),
) -> list[ImportLogItem]:
    """获取导入记录列表

    按 started_at 降序排列，返回最近的导入记录。
    """
    svc = TusharePreviewService()
    try:
        return await svc.query_import_logs(api_name, limit=limit)
    except (OperationalError, DBAPIError) as exc:
        logger.error("数据库连接异常: %s", exc)
        raise HTTPException(status_code=503, detail="数据库连接不可用") from exc
