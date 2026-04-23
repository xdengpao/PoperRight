"""
风控事件日志清理任务

包含：
- cleanup_risk_event_log：每日清理超过 90 天的风控事件日志记录

需求 10.5：90 天数据自动清理
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.tasks.base import DataSyncTask

logger = logging.getLogger(__name__)

# 风控事件日志保留天数
_RETENTION_DAYS = 90


def _run_async(coro):
    """在同步 Celery worker 中运行异步协程。

    始终使用 asyncio.run() 创建全新事件循环，避免 Celery fork 进程中
    复用旧 loop 导致 'Future attached to a different loop' 错误。
    运行结束后 dispose 数据库连接池，防止连接泄漏到下一个 loop。
    """
    async def _wrapper():
        try:
            return await coro
        finally:
            from app.core.database import pg_engine, ts_engine
            await pg_engine.dispose()
            await ts_engine.dispose()

    return asyncio.run(_wrapper())


@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.risk_cleanup.cleanup_risk_event_log",
    bind=True,
    queue="data_sync",
)
def cleanup_risk_event_log(self) -> dict:
    """每日清理超过 90 天的风控事件日志记录。

    由 Celery Beat 每日凌晨 2:00 调度执行。
    删除 triggered_at 超过 90 天的 risk_event_log 记录。

    Returns:
        清理结果摘要字典
    """
    logger.info("开始清理风控事件日志（保留 %d 天）", _RETENTION_DAYS)

    async def _cleanup():
        from sqlalchemy import delete

        from app.core.database import AsyncSessionPG
        from app.models.risk_event import RiskEventLog

        cutoff = datetime.now() - timedelta(days=_RETENTION_DAYS)

        async with AsyncSessionPG() as session:
            stmt = delete(RiskEventLog).where(
                RiskEventLog.triggered_at < cutoff,
            )
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()

        logger.info("风控事件日志清理完成，删除 %d 条记录", deleted_count)
        return {
            "status": "success",
            "deleted": deleted_count,
            "cutoff": cutoff.isoformat(),
        }

    return _run_async(_cleanup())
