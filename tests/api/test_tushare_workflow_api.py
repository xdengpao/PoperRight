"""
Tushare 智能选股一键导入工作流 API 测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_smart_screening_workflow_definition():
    mock_definition = {
        "workflow_key": "smart-screening",
        "label": "智能选股一键导入",
        "mode": "incremental",
        "stages": [],
        "required_token_tiers": [],
        "dependency_summary": {},
    }
    with patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.get_definition",
        return_value=mock_definition,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.get("/api/v1/data/tushare/workflows/smart-screening")

    assert resp.status_code == 200
    assert resp.json()["workflow_key"] == "smart-screening"


@pytest.mark.asyncio
async def test_start_smart_screening_workflow_with_date_range():
    mock_start = AsyncMock(
        return_value={
            "workflow_task_id": "workflow-1",
            "status": "pending",
            "total_steps": 20,
        }
    )
    with patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.start_workflow",
        mock_start,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/data/tushare/workflows/smart-screening/start",
                json={
                    "mode": "incremental",
                    "date_range": {"start_date": "20260430", "end_date": "20260430"},
                    "options": {},
                },
            )

    assert resp.status_code == 200
    assert resp.json()["workflow_task_id"] == "workflow-1"
    mock_start.assert_awaited_once_with(
        mode="incremental",
        date_range={"start_date": "20260430", "end_date": "20260430"},
        options={},
    )


@pytest.mark.asyncio
async def test_plan_smart_screening_workflow():
    mock_plan = {
        "mode": "daily_fast",
        "target_trade_date": "20260430",
        "execute_steps": [{"api_name": "daily", "priority": 1}],
        "skip_steps": [{"api_name": "stock_basic", "skip_reason": "静态数据不每日刷新"}],
        "maintenance_suggestions": [],
        "estimated_cost": {"step_count": 1},
        "next_actions": [],
    }
    with patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.get_plan_async",
        new_callable=AsyncMock,
        return_value=mock_plan,
    ) as mock_get_plan:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/data/tushare/workflows/smart-screening/plan",
                json={
                    "mode": "daily_fast",
                    "target_date": "20260430",
                    "options": {"include_moneyflow_ths": True},
                },
            )

    assert resp.status_code == 200
    assert resp.json()["mode"] == "daily_fast"
    mock_get_plan.assert_awaited_once_with(
        mode="daily_fast",
        date_range={"start_date": "20260430", "end_date": "20260430"},
        options={"include_moneyflow_ths": True},
    )


@pytest.mark.asyncio
async def test_start_smart_screening_workflow_token_missing():
    mock_start = AsyncMock(side_effect=ValueError('{"missing_token_tiers":["premium"]}'))
    with patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.start_workflow",
        mock_start,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/data/tushare/workflows/smart-screening/start",
                json={"mode": "incremental"},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"]["missing_token_tiers"] == ["premium"]


@pytest.mark.asyncio
async def test_workflow_status_pause_and_stop():
    with patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.get_status",
        new_callable=AsyncMock,
        return_value={"workflow_task_id": "workflow-1", "status": "running"},
    ), patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.pause_workflow",
        new_callable=AsyncMock,
        return_value={"message": "暂停信号已发送"},
    ), patch(
        "app.api.v1.tushare.TushareSmartImportWorkflowService.stop_workflow",
        new_callable=AsyncMock,
        return_value={"message": "停止信号已发送"},
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            status_resp = await client.get("/api/v1/data/tushare/workflows/status/workflow-1")
            pause_resp = await client.post("/api/v1/data/tushare/workflows/pause/workflow-1")
            stop_resp = await client.post("/api/v1/data/tushare/workflows/stop/workflow-1")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "running"
    assert pause_resp.status_code == 200
    assert pause_resp.json()["message"] == "暂停信号已发送"
    assert stop_resp.status_code == 200
    assert stop_resp.json()["message"] == "停止信号已发送"
