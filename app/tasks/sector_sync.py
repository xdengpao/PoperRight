"""
板块数据导入 Celery 任务

独立于现有 data_sync.py，使用独立任务名称和 Redis 键前缀。
任务在 data_sync 队列中执行。
"""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.models.sector import DataSource

logger = logging.getLogger(__name__)


def _run_async(coro):
    """在同步 Celery worker 中运行异步协程。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _parse_data_sources(
    data_sources: list[str] | None,
) -> list[DataSource] | None:
    """将字符串列表转换为 DataSource 枚举列表。

    Args:
        data_sources: 数据源字符串列表，如 ["DC", "TI"]，或 None

    Returns:
        DataSource 枚举列表，或 None（表示全部数据源）
    """
    if data_sources is None:
        return None
    return [DataSource(s) for s in data_sources]


@celery_app.task(
    name="app.tasks.sector_sync.sector_import_full",
    queue="data_sync",
    soft_time_limit=7200,   # 2 hours
    time_limit=10800,       # 3 hours hard kill
)
def sector_import_full(
    data_sources: list[str] | None = None,
    base_dir: str | None = None,
) -> dict:
    """
    板块数据全量导入任务。

    按顺序导入板块列表 → 成分 → 行情，支持指定数据源和根目录。

    Args:
        data_sources: 数据源列表（字符串），如 ["DC", "TI", "TDX"]，
                      None 表示全部数据源
        base_dir: 数据文件根目录，None 使用默认路径

    Returns:
        导入结果摘要字典
    """
    logger.info(
        "板块全量导入任务启动 data_sources=%s base_dir=%s",
        data_sources,
        base_dir,
    )

    async def _run():
        from app.services.data_engine.sector_import import SectorImportService

        kwargs = {}
        if base_dir is not None:
            kwargs["base_dir"] = base_dir

        service = SectorImportService(**kwargs)
        sources = _parse_data_sources(data_sources)
        return await service.import_full(data_sources=sources)

    try:
        return _run_async(_run())
    except SoftTimeLimitExceeded:
        logger.error("板块全量导入任务超时（soft_time_limit），标记为失败")
        _run_async(_mark_timeout_failed())
        return {"status": "timeout", "error": "任务执行超时"}


async def _mark_timeout_failed() -> None:
    """超时后将 Redis 进度标记为 failed，避免遗留 running 状态。"""
    from app.services.data_engine.sector_import import SectorImportService
    svc = SectorImportService()
    await svc.update_progress(status="failed", error="任务执行超时")


@celery_app.task(
    name="app.tasks.sector_sync.sector_import_incremental",
    queue="data_sync",
    soft_time_limit=7200,   # 2 hours
    time_limit=10800,       # 3 hours hard kill
)
def sector_import_incremental(
    data_sources: list[str] | None = None,
) -> dict:
    """
    板块数据增量导入任务。

    仅处理尚未导入的新数据文件。

    Args:
        data_sources: 数据源列表（字符串），如 ["DC", "TI", "TDX"]，
                      None 表示全部数据源

    Returns:
        导入结果摘要字典
    """
    logger.info(
        "板块增量导入任务启动 data_sources=%s",
        data_sources,
    )

    async def _run():
        from app.services.data_engine.sector_import import SectorImportService

        service = SectorImportService()
        sources = _parse_data_sources(data_sources)
        return await service.import_incremental(data_sources=sources)

    try:
        return _run_async(_run())
    except SoftTimeLimitExceeded:
        logger.error("板块增量导入任务超时（soft_time_limit），标记为失败")
        _run_async(_mark_timeout_failed())
        return {"status": "timeout", "error": "任务执行超时"}
