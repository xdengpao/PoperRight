"""
Tushare 数据导入 API 端点测试

覆盖 /data/tushare 下全部 6 个端点：
- GET  /health
- GET  /registry
- POST /import
- GET  /import/status/{task_id}
- POST /import/stop/{task_id}
- GET  /import/history
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# GET /data/tushare/health
# ---------------------------------------------------------------------------


class TestTushareHealth:
    @pytest.mark.asyncio
    async def test_health_connected(self):
        """Tushare 连通时返回 connected=True 和 Token 配置状态。"""
        mock_result = {
            "connected": True,
            "tokens": {
                "basic": {"configured": True},
                "advanced": {"configured": True},
                "special": {"configured": False},
            },
        }
        with patch(
            "app.api.v1.tushare.TushareImportService.check_health",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/tushare/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["tokens"]["basic"]["configured"] is True
        assert data["tokens"]["special"]["configured"] is False

    @pytest.mark.asyncio
    async def test_health_disconnected(self):
        """Tushare 不可用时返回 connected=False。"""
        mock_result = {
            "connected": False,
            "tokens": {
                "basic": {"configured": False},
                "advanced": {"configured": False},
                "special": {"configured": False},
            },
        }
        with patch(
            "app.api.v1.tushare.TushareImportService.check_health",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/tushare/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False


# ---------------------------------------------------------------------------
# GET /data/tushare/registry
# ---------------------------------------------------------------------------


class TestTushareRegistry:
    @pytest.mark.asyncio
    async def test_registry_returns_items(self):
        """注册表端点返回接口列表，包含正确字段。"""
        from app.services.data_engine.tushare_registry import (
            ApiEntry,
            CodeFormat,
            ParamType,
            StorageEngine,
            TokenTier,
        )

        mock_entries = {
            "stock_basic": ApiEntry(
                api_name="stock_basic",
                label="股票基础列表",
                category="stock_data",
                subcategory="基础数据",
                token_tier=TokenTier.BASIC,
                target_table="stock_info",
                storage_engine=StorageEngine.PG,
                code_format=CodeFormat.STOCK_SYMBOL,
                conflict_columns=["symbol"],
                required_params=[],
                optional_params=[ParamType.MARKET],
            ),
            "daily": ApiEntry(
                api_name="daily",
                label="日线行情",
                category="stock_data",
                subcategory="行情数据",
                token_tier=TokenTier.BASIC,
                target_table="kline",
                storage_engine=StorageEngine.TS,
                code_format=CodeFormat.STOCK_SYMBOL,
                conflict_columns=["time", "symbol"],
                required_params=[ParamType.DATE_RANGE],
                optional_params=[ParamType.STOCK_CODE],
            ),
        }

        with patch(
            "app.api.v1.tushare.get_all_entries",
            return_value=mock_entries,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/tushare/registry")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # 验证字段完整性
        item = data[0]
        assert "api_name" in item
        assert "label" in item
        assert "category" in item
        assert "subcategory" in item
        assert "token_tier" in item
        assert "required_params" in item
        assert "optional_params" in item
        assert "token_available" in item


# ---------------------------------------------------------------------------
# POST /data/tushare/import
# ---------------------------------------------------------------------------


class TestTushareImport:
    @pytest.mark.asyncio
    async def test_import_success(self):
        """成功启动导入任务。"""
        mock_result = {
            "task_id": "abc-123",
            "log_id": 1,
            "status": "pending",
        }
        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import",
                    json={"api_name": "stock_basic", "params": {}},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "abc-123"
        assert data["log_id"] == 1
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_import_unknown_api_returns_400(self):
        """未知接口名返回 HTTP 400。"""
        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            side_effect=ValueError("未知的 Tushare 接口：unknown_api"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import",
                    json={"api_name": "unknown_api", "params": {}},
                )

        assert resp.status_code == 400
        assert "未知的 Tushare 接口" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_concurrent_returns_409(self):
        """同一接口已有任务运行时返回 HTTP 409。"""
        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            side_effect=RuntimeError("接口 daily 已有导入任务在运行"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import",
                    json={"api_name": "daily", "params": {}},
                )

        assert resp.status_code == 409
        assert "已有导入任务在运行" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /data/tushare/import/status/{task_id}
# ---------------------------------------------------------------------------


class TestTushareImportStatus:
    @pytest.mark.asyncio
    async def test_status_returns_progress(self):
        """返回导入任务进度数据。"""
        mock_result = {
            "total": 100,
            "completed": 42,
            "failed": 3,
            "status": "running",
            "current_item": "600519.SH",
        }
        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/tushare/import/status/task-123"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 100
        assert data["completed"] == 42
        assert data["failed"] == 3
        assert data["status"] == "running"
        assert data["current_item"] == "600519.SH"

    @pytest.mark.asyncio
    async def test_status_unknown_task(self):
        """未知 task_id 返回 status=unknown。"""
        mock_result = {"status": "unknown"}
        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/tushare/import/status/nonexistent"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unknown"


# ---------------------------------------------------------------------------
# POST /data/tushare/import/stop/{task_id}
# ---------------------------------------------------------------------------


class TestTushareImportStop:
    @pytest.mark.asyncio
    async def test_stop_returns_message(self):
        """停止导入返回确认消息。"""
        mock_result = {"message": "停止信号已发送"}
        with patch(
            "app.api.v1.tushare.TushareImportService.stop_import",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import/stop/task-123"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "停止信号已发送"


# ---------------------------------------------------------------------------
# GET /data/tushare/import/history
# ---------------------------------------------------------------------------


class TestTushareImportHistory:
    @pytest.mark.asyncio
    async def test_history_returns_records(self):
        """返回导入历史记录列表。"""
        mock_records = [
            {
                "id": 1,
                "api_name": "stock_basic",
                "params_json": {"market": "SSE"},
                "status": "completed",
                "record_count": 5200,
                "error_message": None,
                "started_at": "2024-01-15T10:30:00",
                "finished_at": "2024-01-15T10:30:03",
            },
            {
                "id": 2,
                "api_name": "daily",
                "params_json": None,
                "status": "failed",
                "record_count": 0,
                "error_message": "Token 无效",
                "started_at": "2024-01-15T10:25:00",
                "finished_at": "2024-01-15T10:25:01",
            },
        ]
        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_history",
            new_callable=AsyncMock,
            return_value=mock_records,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/data/tushare/import/history")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # 验证第一条记录字段完整性
        record = data[0]
        assert record["id"] == 1
        assert record["api_name"] == "stock_basic"
        assert record["status"] == "completed"
        assert record["record_count"] == 5200
        assert record["error_message"] is None
        assert record["started_at"] is not None
        assert record["finished_at"] is not None

        # 验证失败记录
        failed = data[1]
        assert failed["status"] == "failed"
        assert failed["error_message"] == "Token 无效"

    @pytest.mark.asyncio
    async def test_history_with_custom_limit(self):
        """自定义 limit 参数查询历史记录。"""
        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_history",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/tushare/import/history?limit=5"
                )

        assert resp.status_code == 200
        mock_fn.assert_called_once_with(limit=5)
