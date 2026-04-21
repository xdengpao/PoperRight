"""
Tushare 数据导入完整流程集成测试

验证完整导入链路：
- POST /import → 返回 task_id
- Celery 任务执行（mock 实际 Tushare API 调用）
- 数据写入 DB（mock DB 写入）
- 进度更新 Redis（mock Redis，使用内存字典）
- 状态变为 completed
- import_log 记录正确

测试场景：
1. stock_basic 成功导入（非分批，PG 写入）
2. daily 成功导入（分批，TS 写入）
3. 空数据导入（API 返回无行）

对应需求：3.1-3.2, 4.3-4.5, 20.1-20.4, 24.3-24.6
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.tushare_adapter import TushareAdapter

# 保留真实的 _rows_from_data 静态方法引用，用于 mock 类
_real_rows_from_data = TushareAdapter._rows_from_data


# ---------------------------------------------------------------------------
# 辅助：内存 Redis 模拟
# ---------------------------------------------------------------------------


class InMemoryRedis:
    """使用内存字典模拟 Redis cache_get / cache_set / cache_delete。"""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def cache_get(self, key: str) -> str | None:
        return self.store.get(key)

    async def cache_set(self, key: str, value, ex: int | None = None) -> None:
        self.store[key] = str(value)

    async def cache_delete(self, key: str) -> int:
        if key in self.store:
            del self.store[key]
            return 1
        return 0


def _make_mock_adapter_class(mock_adapter):
    """创建一个 mock TushareAdapter 类，保留真实的 _rows_from_data 静态方法。"""
    mock_cls = MagicMock(return_value=mock_adapter)
    mock_cls._rows_from_data = _real_rows_from_data
    return mock_cls


# ---------------------------------------------------------------------------
# 辅助：fixture 数据
# ---------------------------------------------------------------------------

STOCK_BASIC_FIXTURE = {
    "fields": ["ts_code", "name", "market", "is_st"],
    "items": [
        ["600000.SH", "浦发银行", "主板", "N"],
        ["000001.SZ", "平安银行", "主板", "N"],
        ["300001.SZ", "特锐德", "创业板", "N"],
    ],
}

DAILY_FIXTURE = {
    "fields": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
    "items": [
        ["600000.SH", "20240115", 10.0, 10.5, 9.8, 10.3, 50000, 5100000],
        ["600000.SH", "20240116", 10.3, 10.8, 10.1, 10.6, 60000, 6300000],
    ],
}

EMPTY_FIXTURE = {
    "fields": ["ts_code", "trade_date"],
    "items": [],
}


# ---------------------------------------------------------------------------
# 场景 1：stock_basic 成功导入（非分批，PG 写入）
# ---------------------------------------------------------------------------


class TestStockBasicImportFlow:
    """stock_basic 完整导入流程集成测试（非分批，PG 写入）

    **Validates: Requirements 3.1, 3.2, 20.1, 20.2, 20.4, 24.3, 24.6**
    """

    @pytest.mark.asyncio
    async def test_stock_basic_full_flow(self):
        """stock_basic 完整流程：POST /import → 任务执行 → 数据写入 PG → 进度完成 → 日志正确"""

        redis_mock = InMemoryRedis()
        pg_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []

        # --- Phase 1: POST /import 启动导入任务 ---
        mock_start_result = {
            "task_id": "test-task-stock-basic-001",
            "log_id": 1,
            "status": "pending",
        }

        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            return_value=mock_start_result,
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
        assert data["task_id"] == "test-task-stock-basic-001"
        assert data["log_id"] == 1
        assert data["status"] == "pending"

        # --- Phase 2: 模拟 Celery 任务执行 _process_import ---
        task_id = data["task_id"]

        async def mock_write_pg(rows, entry):
            pg_write_calls.append({"rows": list(rows), "table": entry.target_table})

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
                "error_message": error_message,
            })

        mock_adapter = MagicMock()
        mock_adapter._call_api = AsyncMock(return_value=STOCK_BASIC_FIXTURE)
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_postgresql", side_effect=mock_write_pg), \
             patch("app.tasks.tushare_import._finalize_log", side_effect=mock_finalize), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="stock_basic",
                params={},
                token="test-token",
                log_id=1,
                task_id=task_id,
            )

        # --- Phase 3: 验证数据写入 ---
        assert len(pg_write_calls) == 1
        assert pg_write_calls[0]["table"] == "stock_info"
        written_rows = pg_write_calls[0]["rows"]
        assert len(written_rows) == 3
        # stock_basic 使用 STOCK_SYMBOL 格式，应生成 symbol 字段
        assert written_rows[0]["symbol"] == "600000"
        assert written_rows[1]["symbol"] == "000001"
        assert written_rows[2]["symbol"] == "300001"

        # --- Phase 4: 验证进度更新 ---
        progress_key = f"tushare:import:{task_id}"
        raw_progress = redis_mock.store.get(progress_key)
        assert raw_progress is not None
        progress = json.loads(raw_progress)
        assert progress["status"] == "completed"
        assert progress["completed"] == 3

        # --- Phase 5: 验证 import_log 记录 ---
        assert len(finalize_log_calls) == 1
        log_call = finalize_log_calls[0]
        assert log_call["log_id"] == 1
        assert log_call["status"] == "completed"
        assert log_call["record_count"] == 3
        assert log_call["error_message"] is None

        # --- Phase 6: 验证任务返回结果 ---
        assert result["status"] == "completed"
        assert result["record_count"] == 3

    @pytest.mark.asyncio
    async def test_stock_basic_status_polling(self):
        """导入进行中 → GET /import/status 返回正确进度"""

        running_progress = {
            "total": 3,
            "completed": 2,
            "failed": 0,
            "status": "running",
            "current_item": "300001.SZ",
        }

        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_status",
            new_callable=AsyncMock,
            return_value=running_progress,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/tushare/import/status/test-task-stock-basic-001"
                )

        assert resp.status_code == 200
        status = resp.json()
        assert status["status"] == "running"
        assert status["completed"] == 2
        assert status["total"] == 3
        assert status["current_item"] == "300001.SZ"


# ---------------------------------------------------------------------------
# 场景 2：daily 成功导入（分批，TS 写入）
# ---------------------------------------------------------------------------


class TestDailyImportFlow:
    """daily 日线行情完整导入流程集成测试（分批，TS 写入）

    **Validates: Requirements 4.3, 4.4, 4.5, 20.2, 20.4, 24.3**
    """

    @pytest.mark.asyncio
    async def test_daily_batched_flow(self):
        """daily 分批流程：获取股票列表 → 逐只调用 API → 写入 TS → 进度完成"""

        redis_mock = InMemoryRedis()
        ts_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []

        task_id = "test-task-daily-001"

        async def mock_write_ts(rows, entry):
            ts_write_calls.append({"rows": list(rows), "table": entry.target_table})

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
                "error_message": error_message,
            })

        mock_adapter = MagicMock()
        mock_adapter._call_api = AsyncMock(return_value=DAILY_FIXTURE)
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        mock_stock_list = ["600000.SH", "000001.SZ"]

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_timescaledb", side_effect=mock_write_ts), \
             patch("app.tasks.tushare_import._finalize_log", side_effect=mock_finalize), \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=mock_stock_list), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls), \
             patch("time.sleep"):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="daily",
                params={"start_date": "20240115", "end_date": "20240116"},
                token="test-token",
                log_id=2,
                task_id=task_id,
            )

        # --- 验证 TS 写入 ---
        assert len(ts_write_calls) == 2
        for call in ts_write_calls:
            assert call["table"] == "kline"
            assert len(call["rows"]) == 2

        # --- 验证进度 ---
        progress_key = f"tushare:import:{task_id}"
        raw_progress = redis_mock.store.get(progress_key)
        assert raw_progress is not None
        progress = json.loads(raw_progress)
        assert progress["status"] == "completed"
        # completed 最终值为 total_records（4），因为 _process_import 完成时
        # 调用 _update_progress(completed=total_records)，且 completed 单调递增取 max
        assert progress["completed"] == 4

        # --- 验证 import_log ---
        assert len(finalize_log_calls) == 1
        log_call = finalize_log_calls[0]
        assert log_call["log_id"] == 2
        assert log_call["status"] == "completed"
        assert log_call["record_count"] == 4

        # --- 验证返回结果 ---
        assert result["status"] == "completed"
        assert result["record_count"] == 4

    @pytest.mark.asyncio
    async def test_daily_api_called_per_stock(self):
        """daily 分批模式下，每只股票应独立调用一次 API"""

        redis_mock = InMemoryRedis()
        api_call_params: list[dict] = []

        task_id = "test-task-daily-002"

        mock_adapter = MagicMock()

        async def capture_api_call(api_name, **params):
            api_call_params.append({"api_name": api_name, **params})
            return DAILY_FIXTURE

        mock_adapter._call_api = capture_api_call
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        mock_stock_list = ["600000.SH", "000001.SZ", "300001.SZ"]

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_timescaledb", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._finalize_log", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=mock_stock_list), \
             patch("app.tasks.tushare_import._check_stop_signal", new_callable=AsyncMock, return_value=False), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls), \
             patch("time.sleep"):

            from app.tasks.tushare_import import _process_import

            await _process_import(
                api_name="daily",
                params={"start_date": "20240115"},
                token="test-token",
                log_id=3,
                task_id=task_id,
            )

        assert len(api_call_params) == 3
        ts_codes_called = [p["ts_code"] for p in api_call_params]
        assert "600000.SH" in ts_codes_called
        assert "000001.SZ" in ts_codes_called
        assert "300001.SZ" in ts_codes_called


# ---------------------------------------------------------------------------
# 场景 3：空数据导入（API 返回无行）
# ---------------------------------------------------------------------------


class TestEmptyDataImportFlow:
    """空数据导入集成测试

    **Validates: Requirements 20.4, 24.6**
    """

    @pytest.mark.asyncio
    async def test_empty_data_completes_with_zero_records(self):
        """API 返回空数据时，任务应正常完成，record_count=0"""

        redis_mock = InMemoryRedis()
        pg_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []

        task_id = "test-task-empty-001"

        async def mock_write_pg(rows, entry):
            pg_write_calls.append({"rows": list(rows), "table": entry.target_table})

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
                "error_message": error_message,
            })

        mock_adapter = MagicMock()
        mock_adapter._call_api = AsyncMock(return_value=EMPTY_FIXTURE)
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_postgresql", side_effect=mock_write_pg), \
             patch("app.tasks.tushare_import._finalize_log", side_effect=mock_finalize), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="stock_basic",
                params={},
                token="test-token",
                log_id=10,
                task_id=task_id,
            )

        # 空数据不应触发 PG 写入
        assert len(pg_write_calls) == 0

        # 任务应正常完成
        assert result["status"] == "completed"
        assert result["record_count"] == 0

        # import_log 应记录 completed + 0 条
        assert len(finalize_log_calls) == 1
        assert finalize_log_calls[0]["status"] == "completed"
        assert finalize_log_calls[0]["record_count"] == 0

    @pytest.mark.asyncio
    async def test_empty_batched_data_completes(self):
        """分批模式下空股票列表时，任务应正常完成"""

        redis_mock = InMemoryRedis()
        finalize_log_calls: list[dict] = []

        task_id = "test-task-empty-batch-001"

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
            })

        mock_adapter = MagicMock()
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._finalize_log", side_effect=mock_finalize), \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=[]), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="daily",
                params={"start_date": "20240115"},
                token="test-token",
                log_id=11,
                task_id=task_id,
            )

        assert result["status"] == "completed"
        assert result["record_count"] == 0
        assert len(finalize_log_calls) == 1
        assert finalize_log_calls[0]["status"] == "completed"
        assert finalize_log_calls[0]["record_count"] == 0


# ---------------------------------------------------------------------------
# 端到端 API 链路测试
# ---------------------------------------------------------------------------


class TestImportAPIEndToEnd:
    """API 端点链路集成测试

    **Validates: Requirements 20.1, 20.3, 24.5**
    """

    @pytest.mark.asyncio
    async def test_import_start_returns_task_id_and_log_id(self):
        """POST /import 应返回 task_id、log_id 和 pending 状态"""

        mock_result = {
            "task_id": "uuid-test-123",
            "log_id": 42,
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
        body = resp.json()
        assert body["task_id"] == "uuid-test-123"
        assert body["log_id"] == 42
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_import_invalid_api_returns_400(self):
        """POST /import 传入未知接口名 → 返回 400"""

        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            side_effect=ValueError("未知的 Tushare 接口：invalid_api"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import",
                    json={"api_name": "invalid_api", "params": {}},
                )

        assert resp.status_code == 400
        assert "未知的 Tushare 接口" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_concurrent_returns_409(self):
        """同一接口已有任务运行中 → POST /import 返回 409"""

        with patch(
            "app.api.v1.tushare.TushareImportService.start_import",
            new_callable=AsyncMock,
            side_effect=RuntimeError("接口 stock_basic 已有导入任务在运行"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import",
                    json={"api_name": "stock_basic", "params": {}},
                )

        assert resp.status_code == 409
        assert "已有导入任务在运行" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_history_returns_records(self):
        """GET /import/history 应返回导入历史记录列表"""

        mock_records = [
            {
                "id": 1,
                "api_name": "stock_basic",
                "params_json": {},
                "status": "completed",
                "record_count": 5200,
                "error_message": None,
                "started_at": "2024-01-15T10:30:00",
                "finished_at": "2024-01-15T10:30:03",
            },
            {
                "id": 2,
                "api_name": "daily",
                "params_json": {"start_date": "20240115"},
                "status": "completed",
                "record_count": 12000,
                "error_message": None,
                "started_at": "2024-01-15T10:25:00",
                "finished_at": "2024-01-15T10:26:00",
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
        records = resp.json()
        assert len(records) == 2
        assert records[0]["api_name"] == "stock_basic"
        assert records[0]["record_count"] == 5200
        assert records[0]["status"] == "completed"
        assert records[1]["api_name"] == "daily"
