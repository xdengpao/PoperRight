"""
Tushare 数据导入停止信号集成测试

验证停止信号传播：
1. 启动导入任务
2. 设置 Redis 停止信号
3. 任务检测信号并停止
4. 状态变为 stopped
5. import_log 更新

测试场景：
1. 分批处理中检测到停止信号
2. 任务开始处理前停止信号已存在

对应需求：21.2, 21.3, 21.4
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.tushare_adapter import TushareAdapter

# 保留真实的 _rows_from_data 静态方法引用
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

DAILY_FIXTURE = {
    "fields": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
    "items": [
        ["600000.SH", "20240115", 10.0, 10.5, 9.8, 10.3, 50000, 5100000],
    ],
}


# ---------------------------------------------------------------------------
# 场景 1：分批处理中检测到停止信号
# ---------------------------------------------------------------------------


class TestStopDuringBatchProcessing:
    """分批处理中停止信号集成测试

    **Validates: Requirements 21.2, 21.3, 21.4**
    """

    @pytest.mark.asyncio
    async def test_stop_signal_during_batched_import(self):
        """分批导入中设置停止信号 → 任务检测到信号 → 状态变为 stopped → 日志更新"""

        redis_mock = InMemoryRedis()
        ts_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []
        api_call_count = 0

        task_id = "test-task-stop-during-batch"
        stop_key = f"tushare:import:stop:{task_id}"

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

        async def mock_call_api(api_name, **params):
            nonlocal api_call_count
            api_call_count += 1
            # 第一只股票处理完后，设置停止信号
            if api_call_count == 1:
                redis_mock.store[stop_key] = "1"
            return DAILY_FIXTURE

        mock_adapter._call_api = mock_call_api
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        # 3 只股票，第 1 只处理完后设置停止信号，第 2 只应检测到信号并停止
        mock_stock_list = ["600000.SH", "000001.SZ", "300001.SZ"]

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_timescaledb", side_effect=mock_write_ts), \
             patch("app.tasks.tushare_import._finalize_log", side_effect=mock_finalize), \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=mock_stock_list), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls), \
             patch("time.sleep"):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="daily",
                params={"start_date": "20240115"},
                token="test-token",
                log_id=100,
                task_id=task_id,
            )

        # --- 验证任务停止 ---
        assert result["status"] == "stopped"

        # 只处理了第 1 只股票（第 2 只检测到停止信号前就停了）
        assert api_call_count == 1
        assert len(ts_write_calls) == 1
        assert result["record_count"] == 1  # 1 行数据

        # --- 验证 Redis 进度状态 ---
        progress_key = f"tushare:import:{task_id}"
        raw_progress = redis_mock.store.get(progress_key)
        assert raw_progress is not None
        progress = json.loads(raw_progress)
        assert progress["status"] == "stopped"

        # --- 验证 import_log 更新 ---
        assert len(finalize_log_calls) == 1
        assert finalize_log_calls[0]["status"] == "stopped"
        assert finalize_log_calls[0]["log_id"] == 100

    @pytest.mark.asyncio
    async def test_partial_data_preserved_on_stop(self):
        """停止前已处理的数据应保留（不回滚）"""

        redis_mock = InMemoryRedis()
        ts_write_calls: list[dict] = []
        api_call_count = 0

        task_id = "test-task-stop-partial"
        stop_key = f"tushare:import:stop:{task_id}"

        async def mock_write_ts(rows, entry):
            ts_write_calls.append({"rows": list(rows)})

        mock_adapter = MagicMock()

        async def mock_call_api(api_name, **params):
            nonlocal api_call_count
            api_call_count += 1
            # 处理完第 2 只股票后设置停止信号
            if api_call_count == 2:
                redis_mock.store[stop_key] = "1"
            return DAILY_FIXTURE

        mock_adapter._call_api = mock_call_api
        mock_adapter_cls = _make_mock_adapter_class(mock_adapter)

        mock_stock_list = ["600000.SH", "000001.SZ", "300001.SZ", "600519.SH"]

        with patch("app.tasks.tushare_import._redis_get", side_effect=redis_mock.cache_get), \
             patch("app.tasks.tushare_import._redis_set", side_effect=redis_mock.cache_set), \
             patch("app.tasks.tushare_import._redis_delete", side_effect=redis_mock.cache_delete), \
             patch("app.tasks.tushare_import._write_to_timescaledb", side_effect=mock_write_ts), \
             patch("app.tasks.tushare_import._finalize_log", new_callable=AsyncMock), \
             patch("app.tasks.tushare_import._get_stock_list", new_callable=AsyncMock, return_value=mock_stock_list), \
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls), \
             patch("time.sleep"):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="daily",
                params={"start_date": "20240115"},
                token="test-token",
                log_id=101,
                task_id=task_id,
            )

        # 前 2 只股票的数据应已写入
        assert api_call_count == 2
        assert len(ts_write_calls) == 2
        assert result["status"] == "stopped"
        assert result["record_count"] == 2  # 2 只股票各 1 行


# ---------------------------------------------------------------------------
# 场景 2：任务开始处理前停止信号已存在
# ---------------------------------------------------------------------------


class TestStopBeforeProcessing:
    """任务开始前停止信号已存在的集成测试

    **Validates: Requirements 21.2, 21.3**
    """

    @pytest.mark.asyncio
    async def test_stop_signal_before_first_batch(self):
        """停止信号在任务开始前已设置 → 任务立即停止，不处理任何数据"""

        redis_mock = InMemoryRedis()
        ts_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []

        task_id = "test-task-stop-before"
        stop_key = f"tushare:import:stop:{task_id}"

        # 预设停止信号
        redis_mock.store[stop_key] = "1"

        async def mock_write_ts(rows, entry):
            ts_write_calls.append({"rows": list(rows)})

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
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
             patch("app.tasks.tushare_import.TushareAdapter", mock_adapter_cls), \
             patch("time.sleep"):

            from app.tasks.tushare_import import _process_import

            result = await _process_import(
                api_name="daily",
                params={"start_date": "20240115"},
                token="test-token",
                log_id=200,
                task_id=task_id,
            )

        # --- 验证任务立即停止 ---
        assert result["status"] == "stopped"
        assert result["record_count"] == 0

        # 不应有任何 API 调用或数据写入
        mock_adapter._call_api.assert_not_called()
        assert len(ts_write_calls) == 0

        # --- 验证 import_log ---
        assert len(finalize_log_calls) == 1
        assert finalize_log_calls[0]["status"] == "stopped"
        assert finalize_log_calls[0]["record_count"] == 0

    @pytest.mark.asyncio
    async def test_stop_signal_non_batched_not_checked(self):
        """非分批模式下不检查停止信号（单次 API 调用），任务正常完成"""

        redis_mock = InMemoryRedis()
        pg_write_calls: list[dict] = []
        finalize_log_calls: list[dict] = []

        task_id = "test-task-stop-nonbatch"
        stop_key = f"tushare:import:stop:{task_id}"

        # 预设停止信号（但非分批模式不检查）
        redis_mock.store[stop_key] = "1"

        stock_basic_fixture = {
            "fields": ["ts_code", "name"],
            "items": [["600000.SH", "浦发银行"]],
        }

        async def mock_write_pg(rows, entry):
            pg_write_calls.append({"rows": list(rows)})

        async def mock_finalize(log_id, status, record_count, error_message=None):
            finalize_log_calls.append({
                "log_id": log_id,
                "status": status,
                "record_count": record_count,
            })

        mock_adapter = MagicMock()
        mock_adapter._call_api = AsyncMock(return_value=stock_basic_fixture)
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
                log_id=201,
                task_id=task_id,
            )

        # 非分批模式应正常完成（不检查停止信号）
        assert result["status"] == "completed"
        assert result["record_count"] == 1
        assert len(pg_write_calls) == 1


# ---------------------------------------------------------------------------
# API 端点停止信号测试
# ---------------------------------------------------------------------------


class TestStopAPIEndpoint:
    """停止导入 API 端点集成测试

    **Validates: Requirements 21.1, 21.2**
    """

    @pytest.mark.asyncio
    async def test_stop_endpoint_sends_signal(self):
        """POST /import/stop/{task_id} 应发送停止信号"""

        mock_result = {"message": "停止信号已发送"}

        with patch(
            "app.api.v1.tushare.TushareImportService.stop_import",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_stop:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/data/tushare/import/stop/test-task-123"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "停止信号已发送"
        mock_stop.assert_called_once_with("test-task-123")

    @pytest.mark.asyncio
    async def test_stop_then_status_shows_stopped(self):
        """停止后查询状态应显示 stopped"""

        stopped_status = {
            "total": 10,
            "completed": 5,
            "failed": 0,
            "status": "stopped",
            "current_item": "",
        }

        with patch(
            "app.api.v1.tushare.TushareImportService.get_import_status",
            new_callable=AsyncMock,
            return_value=stopped_status,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/data/tushare/import/status/test-task-123"
                )

        assert resp.status_code == 200
        status = resp.json()
        assert status["status"] == "stopped"
        assert status["completed"] == 5
        assert status["total"] == 10
