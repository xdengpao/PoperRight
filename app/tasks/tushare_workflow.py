"""
Tushare 智能选股一键导入工作流任务

在 data_sync 队列内顺序执行智能选股依赖的 Tushare 导入步骤。
"""

from __future__ import annotations

import logging

from billiard.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.services.data_engine.tushare_smart_import_workflow import (
    TushareSmartImportWorkflowService,
)
from app.tasks.base import DataSyncTask
from app.tasks.tushare_import import _run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.tushare_workflow.run_smart_screening_import_workflow",
    bind=True,
    queue="data_sync",
    soft_time_limit=28800,
    time_limit=32400,
    autoretry_for=(),
    max_retries=0,
)
def run_smart_screening_import_workflow(
    self,
    workflow_task_id: str,
    mode: str,
    date_range: dict,
    options: dict | None = None,
    resume: bool = False,
) -> dict:
    """执行智能选股一键导入工作流。"""
    logger.info(
        "启动智能选股 Tushare 一键导入 workflow_task_id=%s mode=%s resume=%s",
        workflow_task_id,
        mode,
        resume,
    )
    service = TushareSmartImportWorkflowService()
    try:
        return _run_async(
            service.run_workflow(
                workflow_task_id=workflow_task_id,
                mode=mode,
                date_range=date_range,
                options=options or {},
                resume=resume,
            )
        )
    except SoftTimeLimitExceeded:
        logger.exception("智能选股 Tushare 工作流软超时 workflow_task_id=%s", workflow_task_id)
        return _run_async(
            service.mark_workflow_failed(
                workflow_task_id,
                "Celery 工作流任务触发 SoftTimeLimitExceeded，已标记失败并释放当前锁",
            )
        )
    except Exception as exc:
        logger.exception("智能选股 Tushare 工作流异常 workflow_task_id=%s", workflow_task_id)
        return _run_async(
            service.mark_workflow_failed(
                workflow_task_id,
                f"Celery 工作流任务异常退出：{exc}",
            )
        )
