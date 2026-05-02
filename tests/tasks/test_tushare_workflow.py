"""
Tushare 智能选股工作流 Celery 任务测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from billiard.exceptions import SoftTimeLimitExceeded

from app.tasks.tushare_workflow import run_smart_screening_import_workflow


def test_run_smart_screening_import_workflow_delegates_to_service():
    mock_service = AsyncMock()
    mock_service.run_workflow.return_value = {
        "workflow_task_id": "workflow-1",
        "status": "completed",
    }

    with patch(
        "app.tasks.tushare_workflow.TushareSmartImportWorkflowService",
        return_value=mock_service,
    ):
        result = run_smart_screening_import_workflow.run(
            workflow_task_id="workflow-1",
            mode="incremental",
            date_range={"start_date": "20260430", "end_date": "20260430"},
            options={"include_tdx_sector": True},
            resume=False,
        )

    assert result["status"] == "completed"
    mock_service.run_workflow.assert_awaited_once_with(
        workflow_task_id="workflow-1",
        mode="incremental",
        date_range={"start_date": "20260430", "end_date": "20260430"},
        options={"include_tdx_sector": True},
        resume=False,
    )


def test_run_smart_screening_import_workflow_marks_failed_on_soft_timeout():
    mock_service = AsyncMock()
    mock_service.run_workflow.side_effect = SoftTimeLimitExceeded()
    mock_service.mark_workflow_failed.return_value = {
        "workflow_task_id": "workflow-1",
        "status": "failed",
    }

    with patch(
        "app.tasks.tushare_workflow.TushareSmartImportWorkflowService",
        return_value=mock_service,
    ):
        result = run_smart_screening_import_workflow.run(
            workflow_task_id="workflow-1",
            mode="daily_fast",
            date_range={"start_date": "20260430", "end_date": "20260430"},
            options={},
            resume=False,
        )

    assert result["status"] == "failed"
    mock_service.mark_workflow_failed.assert_awaited_once()
