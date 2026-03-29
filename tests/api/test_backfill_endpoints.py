"""
回填 API 端点单元测试

测试 POST /data/backfill 和 GET /data/backfill/status 端点。
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def base_url():
    return "http://localhost"


# ---------------------------------------------------------------------------
# POST /data/backfill
# ---------------------------------------------------------------------------


class TestPostBackfill:
    @pytest.mark.asyncio
    async def test_success_default_params(self):
        """默认参数触发全部三种数据类型回填。"""
        mock_result = {"message": "已启动 3 个回填任务", "task_ids": ["t1", "t2", "t3"]}
        with patch(
            "app.api.v1.data.BackfillService.start_backfill",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/backfill",
                    json={"start_date": "2020-01-01", "end_date": "2024-01-01"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == mock_result["message"]
        assert len(data["task_ids"]) == 3

    @pytest.mark.asyncio
    async def test_returns_409_when_task_running(self):
        """已有回填任务运行中时返回 HTTP 409。"""
        with patch(
            "app.api.v1.data.BackfillService.start_backfill",
            new_callable=AsyncMock,
            side_effect=RuntimeError("已有回填任务正在执行，请等待完成后再试"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/backfill",
                    json={"start_date": "2020-01-01", "end_date": "2024-01-01"},
                )
        assert resp.status_code == 409
        assert "已有回填任务正在执行" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_freq_rejected(self):
        """freq 不在 1d/1w/1M 范围内时返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.post(
                "/api/v1/data/backfill",
                json={"freq": "5m", "start_date": "2020-01-01", "end_date": "2024-01-01"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_start_date_after_end_date_rejected(self):
        """start_date > end_date 时返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.post(
                "/api/v1/data/backfill",
                json={"start_date": "2024-06-01", "end_date": "2020-01-01"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_data_type_rejected(self):
        """无效的 data_types 值返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.post(
                "/api/v1/data/backfill",
                json={
                    "data_types": ["invalid_type"],
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                },
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_single_data_type(self):
        """指定单个数据类型回填。"""
        mock_result = {"message": "已启动 1 个回填任务", "task_ids": ["t1"]}
        with patch(
            "app.api.v1.data.BackfillService.start_backfill",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/backfill",
                    json={
                        "data_types": ["kline"],
                        "start_date": "2020-01-01",
                        "end_date": "2024-01-01",
                        "freq": "1w",
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["task_ids"] == ["t1"]

    @pytest.mark.asyncio
    async def test_empty_body_uses_defaults(self):
        """空请求体使用默认参数。"""
        mock_result = {"message": "已启动 3 个回填任务", "task_ids": ["a", "b", "c"]}
        with patch(
            "app.api.v1.data.BackfillService.start_backfill",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/data/backfill", json={})
        assert resp.status_code == 200
        assert len(resp.json()["task_ids"]) == 3


# ---------------------------------------------------------------------------
# GET /data/backfill/status
# ---------------------------------------------------------------------------


class TestGetBackfillStatus:
    @pytest.mark.asyncio
    async def test_returns_idle_when_no_data(self):
        """Redis 无数据时返回 idle 默认值。"""
        idle_progress = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "current_symbol": "",
            "status": "idle",
            "data_types": [],
        }
        with patch(
            "app.api.v1.data.BackfillService.get_progress",
            new_callable=AsyncMock,
            return_value=idle_progress,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/backfill/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["total"] == 0
        assert data["data_types"] == []

    @pytest.mark.asyncio
    async def test_returns_running_progress(self):
        """返回正在运行的回填进度。"""
        running_progress = {
            "total": 100,
            "completed": 42,
            "failed": 3,
            "current_symbol": "600519.SH",
            "status": "running",
            "data_types": ["kline", "fundamentals"],
        }
        with patch(
            "app.api.v1.data.BackfillService.get_progress",
            new_callable=AsyncMock,
            return_value=running_progress,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/backfill/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["total"] == 100
        assert data["completed"] == 42
        assert data["failed"] == 3
        assert data["current_symbol"] == "600519.SH"
        assert data["data_types"] == ["kline", "fundamentals"]

    @pytest.mark.asyncio
    async def test_returns_completed_status(self):
        """返回已完成的回填状态。"""
        completed_progress = {
            "total": 50,
            "completed": 50,
            "failed": 0,
            "current_symbol": "",
            "status": "completed",
            "data_types": ["kline"],
        }
        with patch(
            "app.api.v1.data.BackfillService.get_progress",
            new_callable=AsyncMock,
            return_value=completed_progress,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/backfill/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed"] == 50


# ---------------------------------------------------------------------------
# POST /data/backfill/stop
# ---------------------------------------------------------------------------


class TestPostBackfillStop:
    @pytest.mark.asyncio
    async def test_stop_running_task(self):
        """运行中的回填任务可以被停止。"""
        mock_result = {"message": "已发送停止信号"}
        with patch(
            "app.api.v1.data.BackfillService.stop_backfill",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/data/backfill/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "已发送停止信号"

    @pytest.mark.asyncio
    async def test_stop_when_no_task_running(self):
        """无运行中任务时返回提示信息。"""
        mock_result = {"message": "当前没有正在执行的回填任务"}
        with patch(
            "app.api.v1.data.BackfillService.stop_backfill",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/data/backfill/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "当前没有正在执行的回填任务"
