"""
板块数据 API

导入管理：
- POST /sector/import/full          — 触发全量导入
- POST /sector/import/incremental   — 触发增量导入
- GET  /sector/import/status        — 查询导入进度
- POST /sector/import/stop          — 停止导入任务
- GET  /sector/import/errors        — 查询错误详情（分页）
- GET  /sector/import/errors/export — 导出错误报告（CSV 下载）

数据查询：
- GET  /sector/list                 — 板块列表
- GET  /sector/ranking              — 板块涨跌幅排行
- GET  /sector/info/browse          — 分页浏览板块信息（需求 10.1）
- GET  /sector/constituent/browse   — 分页浏览板块成分股（需求 10.2）
- GET  /sector/kline/browse         — 分页浏览板块行情（需求 10.3）
- GET  /sector/{code}/constituents  — 板块成分股
- GET  /sector/by-stock/{symbol}    — 股票所属板块
- GET  /sector/{code}/kline         — 板块行情K线

覆盖率统计：
- GET  /sector/coverage             — 数据源覆盖率统计（需求 16.2）
- GET  /sector/types                — 板块类型列表（需求 22.8）
"""

from __future__ import annotations

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_pg_session
from app.core.redis_client import cache_delete, cache_get
from app.core.schemas import get_sector_type_label
from app.models.sector import DataSource, SectorConstituent, SectorInfo, SectorType
from app.services.data_engine.sector_import import SectorImportService
from app.services.data_engine.sector_repository import SectorRepository
from app.tasks.sector_sync import sector_import_full, sector_import_incremental

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sector", tags=["Sector"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class ImportFullRequest(BaseModel):
    data_sources: list[str] | None = None
    base_dir: str | None = None


class ImportIncrementalRequest(BaseModel):
    data_sources: list[str] | None = None


class ImportStatusResponse(BaseModel):
    status: str
    stage: str | None = None
    total_files: int | None = None
    processed_files: int | None = None
    imported_records: int | None = None
    current_file: str | None = None
    heartbeat: float | None = None
    error: str | None = None
    error_count: int = 0
    failed_files: list[dict] = []


class SectorInfoResponse(BaseModel):
    sector_code: str
    name: str
    sector_type: str
    data_source: str
    list_date: str | None = None
    constituent_count: int | None = None


class ConstituentResponse(BaseModel):
    trade_date: str
    sector_code: str
    data_source: str
    symbol: str
    stock_name: str | None = None


class SectorKlineResponse(BaseModel):
    time: str
    sector_code: str
    data_source: str
    freq: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    turnover: float | None = None
    change_pct: float | None = None


class SectorRankingResponse(BaseModel):
    """板块排行响应模型"""

    sector_code: str
    name: str
    sector_type: str
    change_pct: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    turnover: float | None = None


class SectorInfoBrowseItem(BaseModel):
    """板块信息浏览响应项"""

    sector_code: str
    name: str
    sector_type: str
    data_source: str
    list_date: str | None = None
    constituent_count: int | None = None


class ConstituentBrowseItem(BaseModel):
    """板块成分浏览响应项"""

    trade_date: str
    sector_code: str
    data_source: str
    symbol: str
    stock_name: str | None = None


class KlineBrowseItem(BaseModel):
    """板块行情浏览响应项"""

    time: str
    sector_code: str
    data_source: str
    freq: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    change_pct: float | None = None


class TypeBreakdownItem(BaseModel):
    """按板块类型分组的统计项（需求 22.10）"""

    sector_type: str | None  # 原始 sector_type 值
    label: str  # 中文标签
    sector_count: int  # 该类型下的板块数量
    stock_count: int  # 该类型下的不同股票数量


class CoverageSourceStats(BaseModel):
    """单个数据源的覆盖率统计"""

    data_source: str  # "DC" / "TI" / "TDX"
    total_sectors: int  # 该数据源的板块总数
    sectors_with_constituents: int  # 有成分股数据的板块数
    total_stocks: int  # 成分股覆盖的不同股票数
    coverage_ratio: float  # sectors_with_constituents / total_sectors
    type_breakdown: list[TypeBreakdownItem] = []  # 按板块类型分组的统计（需求 22.10）


class CoverageResponse(BaseModel):
    """覆盖率响应"""

    sources: list[CoverageSourceStats]


# ---------------------------------------------------------------------------
# 覆盖率统计端点（需求 16.2）
# ---------------------------------------------------------------------------


@router.get("/coverage", response_model=CoverageResponse)
async def get_sector_coverage(
    pg_session: AsyncSession = Depends(get_pg_session),
) -> CoverageResponse:
    """
    返回每个数据源的板块数量和成分股覆盖数量统计。

    对应需求 16.2。
    """
    sources = []
    for ds in ["DC", "THS", "TDX", "TI", "CI"]:
        # 查询该数据源的板块总数
        total_stmt = (
            select(func.count())
            .select_from(SectorInfo)
            .where(SectorInfo.data_source == ds)
        )
        total_sectors = (await pg_session.execute(total_stmt)).scalar() or 0

        # 查询有成分股数据的板块数（最新交易日）
        latest_date_stmt = (
            select(func.max(SectorConstituent.trade_date))
            .where(SectorConstituent.data_source == ds)
        )
        latest_date = (await pg_session.execute(latest_date_stmt)).scalar()

        if latest_date:
            sectors_with_stmt = (
                select(func.count(func.distinct(SectorConstituent.sector_code)))
                .where(
                    SectorConstituent.data_source == ds,
                    SectorConstituent.trade_date == latest_date,
                )
            )
            sectors_with = (
                await pg_session.execute(sectors_with_stmt)
            ).scalar() or 0

            stocks_stmt = (
                select(func.count(func.distinct(SectorConstituent.symbol)))
                .where(
                    SectorConstituent.data_source == ds,
                    SectorConstituent.trade_date == latest_date,
                )
            )
            total_stocks = (
                await pg_session.execute(stocks_stmt)
            ).scalar() or 0
        else:
            sectors_with = 0
            total_stocks = 0

        coverage_ratio = (
            sectors_with / total_sectors if total_sectors > 0 else 0.0
        )

        # 按 sector_type 分组统计板块数量（需求 22.10）
        type_sector_count_stmt = (
            select(
                SectorInfo.sector_type,
                func.count().label("sector_count"),
            )
            .where(SectorInfo.data_source == ds)
            .group_by(SectorInfo.sector_type)
        )
        type_sector_rows = (
            await pg_session.execute(type_sector_count_stmt)
        ).all()

        # 按 sector_type 分组统计不同股票数量（需求 22.10）
        # 通过 sector_constituent 关联 sector_info 获取 sector_type
        type_stock_count_stmt = (
            select(
                SectorInfo.sector_type,
                func.count(func.distinct(SectorConstituent.symbol)).label(
                    "stock_count"
                ),
            )
            .select_from(SectorConstituent)
            .join(
                SectorInfo,
                (SectorConstituent.sector_code == SectorInfo.sector_code)
                & (SectorConstituent.data_source == SectorInfo.data_source),
            )
            .where(SectorConstituent.data_source == ds)
        )
        if latest_date:
            type_stock_count_stmt = type_stock_count_stmt.where(
                SectorConstituent.trade_date == latest_date
            )
        type_stock_count_stmt = type_stock_count_stmt.group_by(
            SectorInfo.sector_type
        )
        type_stock_rows = (
            await pg_session.execute(type_stock_count_stmt)
        ).all()

        # 构建 sector_type → stock_count 映射
        stock_count_map: dict[str | None, int] = {
            row.sector_type: row.stock_count for row in type_stock_rows
        }

        # 组装 type_breakdown 列表
        type_breakdown = [
            TypeBreakdownItem(
                sector_type=row.sector_type,
                label=get_sector_type_label(row.sector_type),
                sector_count=row.sector_count,
                stock_count=stock_count_map.get(row.sector_type, 0),
            )
            for row in type_sector_rows
        ]

        sources.append(
            CoverageSourceStats(
                data_source=ds,
                total_sectors=total_sectors,
                sectors_with_constituents=sectors_with,
                total_stocks=total_stocks,
                coverage_ratio=round(coverage_ratio, 4),
                type_breakdown=type_breakdown,
            )
        )

    return CoverageResponse(sources=sources)


# ---------------------------------------------------------------------------
# 板块类型查询端点（需求 22.8）
# ---------------------------------------------------------------------------


@router.get("/types")
async def get_sector_types(
    data_source: str = Query(..., description="数据来源：DC/THS/TDX/TI/CI"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> list[dict]:
    """
    返回指定数据来源下所有不重复的 sector_type 值列表。

    每个值附带中文名称（label）和该类型下的板块数量（count）。
    按数量降序排列。

    对应需求 22.8。
    """
    # 查询该数据来源下所有不重复的 sector_type 及其板块数量
    stmt = (
        select(
            SectorInfo.sector_type,
            func.count().label("count"),
        )
        .where(SectorInfo.data_source == data_source)
        .group_by(SectorInfo.sector_type)
        .order_by(func.count().desc())
    )
    rows = (await pg_session.execute(stmt)).all()
    # 构造响应，附带中文标签
    return [
        {
            "sector_type": row.sector_type,
            "label": get_sector_type_label(row.sector_type),
            "count": row.count,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 导入管理端点
# ---------------------------------------------------------------------------


@router.post("/import/full")
async def trigger_full_import(body: ImportFullRequest | None = None):
    """触发板块数据全量导入。

    已有导入任务运行中时返回 409 Conflict。
    """
    svc = SectorImportService()
    if await svc.is_running():
        raise HTTPException(status_code=409, detail="板块导入任务正在运行中，请等待完成后再试")

    data_sources = (body.data_sources if body else None)
    base_dir = (body.base_dir if body else None)

    kwargs: dict = {}
    if data_sources is not None:
        kwargs["data_sources"] = data_sources
    if base_dir is not None:
        kwargs["base_dir"] = base_dir

    result = sector_import_full.delay(**kwargs)

    # 保存 task_id 到进度信息，用于强制停止
    await svc.update_progress(status="pending", celery_task_id=result.id)

    return {"task_id": result.id, "message": "板块全量导入任务已触发"}


@router.post("/import/incremental")
async def trigger_incremental_import(body: ImportIncrementalRequest | None = None):
    """触发板块数据增量导入。

    已有导入任务运行中时返回 409 Conflict。
    """
    svc = SectorImportService()
    if await svc.is_running():
        raise HTTPException(status_code=409, detail="板块导入任务正在运行中，请等待完成后再试")

    data_sources = (body.data_sources if body else None)

    kwargs: dict = {}
    if data_sources is not None:
        kwargs["data_sources"] = data_sources

    result = sector_import_incremental.delay(**kwargs)

    # 保存 task_id 到进度信息，用于强制停止
    await svc.update_progress(status="pending", celery_task_id=result.id)

    return {"task_id": result.id, "message": "板块增量导入任务已触发"}


@router.get("/import/status", response_model=ImportStatusResponse)
async def get_import_status():
    """查询板块导入进度。"""
    raw = await cache_get(SectorImportService.REDIS_PROGRESS_KEY)
    if not raw:
        return ImportStatusResponse(status="idle")

    try:
        progress = json.loads(raw)
    except (ValueError, TypeError):
        return ImportStatusResponse(status="idle")

    return ImportStatusResponse(
        status=progress.get("status", "idle"),
        stage=progress.get("stage"),
        total_files=progress.get("total_files"),
        processed_files=progress.get("processed_files"),
        imported_records=progress.get("imported_records"),
        current_file=progress.get("current_file"),
        heartbeat=progress.get("heartbeat"),
        error=progress.get("error"),
        error_count=progress.get("error_count", 0),
        failed_files=progress.get("failed_files", []),
    )


@router.post("/import/stop")
async def stop_import(force: bool = Query(False, description="强制终止任务（SIGTERM）")):
    """发送板块导入停止信号。

    默认发送协作式停止信号，任务在当前批次完成后终止。
    force=true 时额外通过 Celery revoke 强制终止任务进程。
    """
    svc = SectorImportService()

    # 1. 设置 Redis 停止信号（协作式）
    await svc.request_stop()

    if force:
        # 2. 从进度信息中获取 task_id，通过 Celery revoke 强制终止
        raw = await cache_get(SectorImportService.REDIS_PROGRESS_KEY)
        task_id = None
        if raw:
            try:
                progress = json.loads(raw)
                task_id = progress.get("celery_task_id")
            except (ValueError, TypeError):
                pass

        if task_id:
            from app.core.celery_app import celery_app as _celery
            _celery.control.revoke(task_id, terminate=True, signal="SIGTERM")
            logger.info("强制终止板块导入任务 task_id=%s", task_id)

        # 3. 强制更新进度状态为 stopped
        await svc.update_progress(status="stopped", error="用户强制停止")
        return {"message": "导入任务已强制终止"}

    return {"message": "停止信号已发送，导入任务将在当前批次完成后终止"}


@router.post("/import/reset")
async def reset_import_status():
    """强制清除板块导入状态（用于异常终止后恢复）。"""
    await cache_delete(SectorImportService.REDIS_PROGRESS_KEY)
    await cache_delete(SectorImportService.REDIS_STOP_KEY)
    return {"message": "板块导入状态已清除"}


@router.get("/import/errors")
async def get_import_errors(
    offset: int = Query(0, ge=0, description="起始偏移量"),
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
):
    """分页查询导入错误详情列表。"""
    svc = SectorImportService()
    errors = await svc.get_errors(offset=offset, limit=limit)
    total = await svc.get_error_count()
    return {"total": total, "offset": offset, "limit": limit, "items": errors}


@router.get("/import/errors/export")
async def export_import_errors():
    """以 CSV 格式导出全部导入错误详情。"""
    import csv
    import io

    svc = SectorImportService()
    total = await svc.get_error_count()
    # 分批读取所有错误
    all_errors: list[dict] = []
    batch_size = 500
    for offset in range(0, max(total, 1), batch_size):
        batch = await svc.get_errors(offset=offset, limit=batch_size)
        if not batch:
            break
        all_errors.extend(batch)

    def generate_csv():
        """生成 CSV 内容的生成器。"""
        output = io.StringIO()
        writer = csv.writer(output)
        # 写入表头
        writer.writerow(["file", "line", "error_type", "message", "raw_data"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        # 写入数据行
        for err in all_errors:
            writer.writerow([
                err.get("file", ""),
                err.get("line", 0),
                err.get("error_type", ""),
                err.get("message", ""),
                err.get("raw_data", ""),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=import_errors.csv"},
    )


# ---------------------------------------------------------------------------
# 数据查询端点
# ---------------------------------------------------------------------------


@router.get("/list", response_model=list[SectorInfoResponse])
async def get_sector_list(
    sector_type: str | None = Query(None, description="板块类型: CONCEPT/INDUSTRY/REGION/STYLE"),
    data_source: str | None = Query(None, description="数据来源: DC/TI/TDX"),
):
    """查询板块列表，支持按类型和数据源筛选。"""
    repo = SectorRepository()

    st = None
    if sector_type is not None:
        try:
            st = SectorType(sector_type)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的板块类型: {sector_type}，可选值: {[e.value for e in SectorType]}",
            )

    ds = None
    if data_source is not None:
        try:
            ds = DataSource(data_source)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
            )

    rows = await repo.get_sector_list(sector_type=st, data_source=ds)
    return [
        SectorInfoResponse(
            sector_code=r.sector_code,
            name=r.name,
            sector_type=r.sector_type,
            data_source=r.data_source,
            list_date=r.list_date.isoformat() if r.list_date else None,
            constituent_count=r.constituent_count,
        )
        for r in rows
    ]


@router.get("/ranking", response_model=list[SectorRankingResponse])
async def get_sector_ranking(
    sector_type: str | None = Query(None, description="板块类型: CONCEPT/INDUSTRY/REGION/STYLE"),
    data_source: str | None = Query(None, description="数据来源: DC/TI/TDX，默认 DC"),
):
    """查询板块涨跌幅排行，按涨跌幅降序排列。"""
    st = None
    if sector_type is not None:
        try:
            st = SectorType(sector_type)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的板块类型: {sector_type}，可选值: {[e.value for e in SectorType]}",
            )

    ds: DataSource | None = None
    if data_source is not None:
        try:
            ds = DataSource(data_source)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
            )

    repo = SectorRepository()
    items = await repo.get_sector_ranking(sector_type=st, data_source=ds)
    return [
        SectorRankingResponse(
            sector_code=item.sector_code,
            name=item.name,
            sector_type=item.sector_type,
            change_pct=item.change_pct,
            close=item.close,
            volume=item.volume,
            amount=item.amount,
            turnover=item.turnover,
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# 分页浏览端点（需求 10）
# ---------------------------------------------------------------------------


@router.get("/info/browse")
async def browse_sector_info(
    data_source: str | None = Query(None, description="数据来源: DC/TI/TDX"),
    sector_type: str | None = Query(None, description="板块类型: CONCEPT/INDUSTRY/REGION/STYLE"),
    keyword: str | None = Query(None, description="板块名称或代码模糊搜索"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数，1-200"),
) -> dict:
    """分页浏览板块信息。"""
    ds = None
    if data_source is not None:
        try:
            ds = DataSource(data_source)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
            )

    st = None
    if sector_type is not None:
        try:
            st = SectorType(sector_type)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的板块类型: {sector_type}，可选值: {[e.value for e in SectorType]}",
            )

    repo = SectorRepository()
    result = await repo.browse_sector_info(
        data_source=ds,
        sector_type=st,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return {
        "total": result.total,
        "page": page,
        "page_size": page_size,
        "items": [
            SectorInfoBrowseItem(
                sector_code=r.sector_code,
                name=r.name,
                sector_type=r.sector_type,
                data_source=r.data_source,
                list_date=r.list_date.isoformat() if r.list_date else None,
                constituent_count=r.constituent_count,
            ).model_dump()
            for r in result.items
        ],
    }


@router.get("/constituent/browse")
async def browse_sector_constituent(
    data_source: str = Query(..., description="数据来源: DC/TI/TDX"),
    sector_code: str | None = Query(None, description="板块代码精确匹配"),
    trade_date: str | None = Query(None, description="交易日期 YYYY-MM-DD，默认最新"),
    keyword: str | None = Query(None, description="股票代码或名称模糊搜索"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数，1-200"),
) -> dict:
    """分页浏览板块成分股。"""
    try:
        ds = DataSource(data_source)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
        )

    td: date | None = None
    if trade_date is not None:
        try:
            td = date.fromisoformat(trade_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的日期格式: {trade_date}，请使用 YYYY-MM-DD",
            )

    repo = SectorRepository()
    result = await repo.browse_sector_constituent(
        data_source=ds,
        sector_code=sector_code,
        trade_date=td,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return {
        "total": result.total,
        "page": page,
        "page_size": page_size,
        "items": [
            ConstituentBrowseItem(
                trade_date=r.trade_date.isoformat(),
                sector_code=r.sector_code,
                data_source=r.data_source,
                symbol=r.symbol,
                stock_name=r.stock_name,
            ).model_dump()
            for r in result.items
        ],
    }


@router.get("/kline/browse")
async def browse_sector_kline(
    data_source: str = Query(..., description="数据来源: DC/TI/TDX"),
    sector_code: str | None = Query(None, description="板块代码精确匹配"),
    freq: str = Query("1d", description="K线频率: 1d/1w/1M"),
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数，1-200"),
) -> dict:
    """分页浏览板块行情。"""
    try:
        ds = DataSource(data_source)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
        )

    start_date: date | None = None
    end_date: date | None = None

    if start is not None:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的开始日期格式: {start}，请使用 YYYY-MM-DD",
            )

    if end is not None:
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"无效的结束日期格式: {end}，请使用 YYYY-MM-DD",
            )

    repo = SectorRepository()
    result = await repo.browse_sector_kline(
        data_source=ds,
        sector_code=sector_code,
        freq=freq,
        start=start_date,
        end=end_date,
        page=page,
        page_size=page_size,
    )
    return {
        "total": result.total,
        "page": page,
        "page_size": page_size,
        "items": [
            KlineBrowseItem(
                time=r.time.isoformat(),
                sector_code=r.sector_code,
                data_source=r.data_source,
                freq=r.freq,
                open=float(r.open) if r.open is not None else None,
                high=float(r.high) if r.high is not None else None,
                low=float(r.low) if r.low is not None else None,
                close=float(r.close) if r.close is not None else None,
                volume=r.volume,
                amount=float(r.amount) if r.amount is not None else None,
                change_pct=float(r.change_pct) if r.change_pct is not None else None,
            ).model_dump()
            for r in result.items
        ],
    }


# ---------------------------------------------------------------------------
# 数据查询端点（路径参数路由）
# ---------------------------------------------------------------------------


@router.get("/{code}/constituents", response_model=list[ConstituentResponse])
async def get_constituents(
    code: str,
    data_source: str = Query(..., description="数据来源: DC/TI/TDX"),
    trade_date: str | None = Query(None, description="交易日期 YYYY-MM-DD，默认最新"),
):
    """查询指定板块的成分股列表。"""
    try:
        ds = DataSource(data_source)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
        )

    td: date | None = None
    if trade_date is not None:
        try:
            td = date.fromisoformat(trade_date)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"无效的日期格式: {trade_date}，请使用 YYYY-MM-DD")

    repo = SectorRepository()
    rows = await repo.get_constituents(sector_code=code, data_source=ds, trade_date=td)
    return [
        ConstituentResponse(
            trade_date=r.trade_date.isoformat(),
            sector_code=r.sector_code,
            data_source=r.data_source,
            symbol=r.symbol,
            stock_name=r.stock_name,
        )
        for r in rows
    ]


@router.get("/by-stock/{symbol}", response_model=list[ConstituentResponse])
async def get_sectors_by_stock(
    symbol: str,
    trade_date: str | None = Query(None, description="交易日期 YYYY-MM-DD，默认最新"),
):
    """查询指定股票所属的全部板块。"""
    td: date | None = None
    if trade_date is not None:
        try:
            td = date.fromisoformat(trade_date)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"无效的日期格式: {trade_date}，请使用 YYYY-MM-DD")

    repo = SectorRepository()
    rows = await repo.get_sectors_by_stock(symbol=symbol, trade_date=td)
    return [
        ConstituentResponse(
            trade_date=r.trade_date.isoformat(),
            sector_code=r.sector_code,
            data_source=r.data_source,
            symbol=r.symbol,
            stock_name=r.stock_name,
        )
        for r in rows
    ]


@router.get("/{code}/kline", response_model=list[SectorKlineResponse])
async def get_sector_kline(
    code: str,
    data_source: str = Query(..., description="数据来源: DC/TI/TDX"),
    freq: str = Query("1d", description="K线频率: 1d/1w/1M"),
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """查询板块行情K线数据。"""
    try:
        ds = DataSource(data_source)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"无效的数据来源: {data_source}，可选值: {[e.value for e in DataSource]}",
        )

    start_date: date | None = None
    end_date: date | None = None

    if start is not None:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"无效的开始日期格式: {start}，请使用 YYYY-MM-DD")

    if end is not None:
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"无效的结束日期格式: {end}，请使用 YYYY-MM-DD")

    repo = SectorRepository()
    rows = await repo.get_sector_kline(
        sector_code=code,
        data_source=ds,
        freq=freq,
        start=start_date,
        end=end_date,
    )
    return [
        SectorKlineResponse(
            time=r.time.isoformat(),
            sector_code=r.sector_code,
            data_source=r.data_source,
            freq=r.freq,
            open=float(r.open) if r.open is not None else None,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
            close=float(r.close) if r.close is not None else None,
            volume=r.volume,
            amount=float(r.amount) if r.amount is not None else None,
            turnover=float(r.turnover) if r.turnover is not None else None,
            change_pct=float(r.change_pct) if r.change_pct is not None else None,
        )
        for r in rows
    ]
