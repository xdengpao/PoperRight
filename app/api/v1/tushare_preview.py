"""
Tushare 数据预览 API 端点

提供已导入 Tushare 数据的只读预览查询接口，包括：
- GET  /{api_name}            — 查询预览数据（分页、时间筛选、增量查询）
- GET  /{api_name}/stats      — 获取数据统计信息
- GET  /{api_name}/import-logs — 获取该接口的导入记录列表
- POST /{api_name}/check-integrity — 完整性校验
- GET  /{api_name}/chart-data  — 图表数据独立加载

本模块完全独立于现有 tushare.py 中的导入端点，不修改任何导入功能代码。
所有查询均为只读 SELECT 操作。

对应需求：2.1, 8.1-8.6, 9.3, 10.1-10.4
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, OperationalError

from app.services.data_engine.tushare_preview_service import (
    ChartDataResponse,
    CompletenessReport,
    DeleteDataResponse,
    ImportLogItem,
    IntegrityRequest,
    PreviewDataResponse,
    PreviewStatsResponse,
    TusharePreviewService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/tushare/preview", tags=["tushare-preview"])


# ---------------------------------------------------------------------------
# 端点实现
# ---------------------------------------------------------------------------


@router.post("/{api_name}/check-integrity")
async def check_integrity(
    api_name: str,
    body: IntegrityRequest,
) -> CompletenessReport:
    """完整性校验

    根据 api_name 对应的数据表执行完整性校验：
    - 时序数据：基于 SSE 交易日历检测缺失交易日
    - 非时序数据：基于 A 股代码集合检测缺失代码
    - 不支持校验的表返回 unsupported 类型
    """
    svc = TusharePreviewService()
    try:
        return await svc.check_integrity(
            api_name,
            data_time_start=body.data_time_start,
            data_time_end=body.data_time_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OperationalError, DBAPIError) as exc:
        logger.error("完整性校验查询失败: %s", exc)
        raise HTTPException(status_code=500, detail="完整性校验查询失败") from exc


@router.get("/{api_name}/chart-data")
async def query_chart_data_endpoint(
    api_name: str,
    limit: int | None = Query(default=None, description="返回数据条数，范围 [1, 500]，默认 250"),
    data_time_start: str | None = Query(default=None, description="数据时间范围起始"),
    data_time_end: str | None = Query(default=None, description="数据时间范围结束"),
) -> ChartDataResponse:
    """图表数据独立加载

    返回按时间升序排列的最近 N 条数据，独立于表格分页，用于前端图表渲染。
    limit 范围 [1, 500]，默认 250。
    """
    svc = TusharePreviewService()
    try:
        return await svc.query_chart_data(
            api_name,
            limit=limit if limit is not None else 250,
            data_time_start=data_time_start,
            data_time_end=data_time_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OperationalError, DBAPIError) as exc:
        logger.error("图表数据查询失败: %s", exc)
        raise HTTPException(status_code=503, detail="数据库连接不可用") from exc


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


class DeleteDataRequest(BaseModel):
    """数据删除请求"""
    data_time_start: str | None = None
    data_time_end: str | None = None


@router.post("/{api_name}/delete-data")
async def delete_data(
    api_name: str,
    body: DeleteDataRequest,
) -> DeleteDataResponse:
    """删除指定时间范围内的数据

    根据数据时间字段删除指定范围内的记录。至少需要指定起始或结束日期之一。
    """
    svc = TusharePreviewService()
    try:
        return await svc.delete_data(
            api_name,
            data_time_start=body.data_time_start,
            data_time_end=body.data_time_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OperationalError, DBAPIError) as exc:
        logger.error("数据删除失败: %s", exc)
        raise HTTPException(status_code=500, detail="数据删除失败") from exc
