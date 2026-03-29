"""
BackfillService 单元测试

测试回填编排服务的参数填充、并发保护、进度读取和任务分发逻辑。
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.backfill_service import (
    ALL_DATA_TYPES,
    BATCH_SIZE,
    PROGRESS_TTL,
    REDIS_KEY,
    STOP_SIGNAL_KEY,
    BackfillService,
)


@pytest.fixture
def service():
    return BackfillService()


# ---------------------------------------------------------------------------
# get_progress
# ---------------------------------------------------------------------------


class TestGetProgress:
    @pytest.mark.asyncio
    async def test_returns_idle_when_no_redis_data(self, service):
        with patch("app.services.data_engine.backfill_service.cache_get", new_callable=AsyncMock, return_value=None):
            result = await service.get_progress()
        assert result["status"] == "idle"
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_stored_progress(self, service):
        stored = {
            "total": 100,
            "completed": 50,
            "failed": 2,
            "current_symbol": "600519.SH",
            "status": "running",
            "data_types": ["kline"],
        }
        with patch(
            "app.services.data_engine.backfill_service.cache_get",
            new_callable=AsyncMock,
            return_value=json.dumps(stored),
        ):
            result = await service.get_progress()
        assert result == stored

    @pytest.mark.asyncio
    async def test_returns_idle_on_corrupt_json(self, service):
        with patch(
            "app.services.data_engine.backfill_service.cache_get",
            new_callable=AsyncMock,
            return_value="not-json{{{",
        ):
            result = await service.get_progress()
        assert result["status"] == "idle"


# ---------------------------------------------------------------------------
# _resolve_start_date
# ---------------------------------------------------------------------------


class TestResolveStartDate:
    def test_returns_provided_date(self, service):
        d = date(2020, 6, 15)
        assert service._resolve_start_date(d) == d

    def test_defaults_to_10_years_ago(self, service):
        with patch("app.services.data_engine.backfill_service.settings") as mock_settings:
            mock_settings.kline_history_years = 10
            result = service._resolve_start_date(None)
        today = date.today()
        expected = today.replace(year=today.year - 10)
        assert result == expected

    def test_respects_custom_history_years(self, service):
        with patch("app.services.data_engine.backfill_service.settings") as mock_settings:
            mock_settings.kline_history_years = 5
            result = service._resolve_start_date(None)
        today = date.today()
        expected = today.replace(year=today.year - 5)
        assert result == expected


# ---------------------------------------------------------------------------
# _resolve_symbols
# ---------------------------------------------------------------------------


class TestResolveSymbols:
    @pytest.mark.asyncio
    async def test_returns_provided_symbols(self, service):
        symbols = ["000001.SZ", "600519.SH"]
        result = await service._resolve_symbols(symbols)
        assert result == symbols

    @pytest.mark.asyncio
    async def test_queries_db_when_empty(self, service):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["000001.SZ", "600519.SH"]
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.database.AsyncSessionPG", return_value=mock_session):
            result = await service._resolve_symbols(None)

        assert result == ["000001.SZ", "600519.SH"]
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_queries_db_when_empty_list(self, service):
        """Empty list should also trigger DB query."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["300001.SZ"]
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.database.AsyncSessionPG", return_value=mock_session):
            result = await service._resolve_symbols([])

        assert result == ["300001.SZ"]


# ---------------------------------------------------------------------------
# start_backfill
# ---------------------------------------------------------------------------


class TestStartBackfill:
    @pytest.mark.asyncio
    async def test_rejects_when_running(self, service):
        running_progress = json.dumps({"status": "running"})
        with patch(
            "app.services.data_engine.backfill_service.cache_get",
            new_callable=AsyncMock,
            return_value=running_progress,
        ):
            with pytest.raises(RuntimeError, match="已有回填任务正在执行"):
                await service.start_backfill()

    @pytest.mark.asyncio
    async def test_allows_when_completed(self, service):
        completed_progress = json.dumps({"status": "completed"})
        mock_task = MagicMock()
        mock_task.id = "task-123"

        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=completed_progress,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
            patch(
                "app.services.data_engine.backfill_service.cache_delete",
                new_callable=AsyncMock,
            ),
            patch("app.core.celery_app.celery_app") as mock_celery,
            patch.object(service, "_resolve_symbols", new_callable=AsyncMock, return_value=["000001.SZ"]),
        ):
            mock_celery.send_task.return_value = mock_task
            result = await service.start_backfill(data_types=["kline"])

        assert len(result["task_ids"]) == 1
        assert result["task_ids"][0] == "task-123"
        # cache_set called twice: init progress + save task_ids
        assert mock_cache_set.call_count == 2

    @pytest.mark.asyncio
    async def test_dispatches_all_types_by_default(self, service):
        mock_task = MagicMock()
        mock_task.id = "task-abc"

        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_delete",
                new_callable=AsyncMock,
            ),
            patch("app.core.celery_app.celery_app") as mock_celery,
            patch.object(service, "_resolve_symbols", new_callable=AsyncMock, return_value=["000001.SZ"]),
        ):
            mock_celery.send_task.return_value = mock_task
            result = await service.start_backfill()

        assert len(result["task_ids"]) == 3
        assert mock_celery.send_task.call_count == 3

    @pytest.mark.asyncio
    async def test_kline_task_includes_freq(self, service):
        mock_task = MagicMock()
        mock_task.id = "task-k"

        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_delete",
                new_callable=AsyncMock,
            ),
            patch("app.core.celery_app.celery_app") as mock_celery,
            patch.object(service, "_resolve_symbols", new_callable=AsyncMock, return_value=["000001.SZ"]),
        ):
            mock_celery.send_task.return_value = mock_task
            await service.start_backfill(data_types=["kline"], freq="1w")

        call_kwargs = mock_celery.send_task.call_args
        assert call_kwargs.kwargs["kwargs"]["freq"] == "1w"

    @pytest.mark.asyncio
    async def test_initializes_redis_progress_as_pending(self, service):
        mock_task = MagicMock()
        mock_task.id = "task-p"

        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
            patch(
                "app.services.data_engine.backfill_service.cache_delete",
                new_callable=AsyncMock,
            ),
            patch("app.core.celery_app.celery_app") as mock_celery,
            patch.object(service, "_resolve_symbols", new_callable=AsyncMock, return_value=["000001.SZ"]),
        ):
            mock_celery.send_task.return_value = mock_task
            await service.start_backfill(data_types=["kline"])

        # The last cache_set call saves task_ids; the first one sets pending status
        first_call = mock_cache_set.call_args_list[0]
        progress = json.loads(first_call.args[1])
        assert progress["status"] == "pending"
        assert progress["total"] == 1
        assert first_call.kwargs["ex"] == PROGRESS_TTL


# ---------------------------------------------------------------------------
# stop_backfill
# ---------------------------------------------------------------------------


class TestStopBackfill:
    @pytest.mark.asyncio
    async def test_sets_stopping_when_running(self, service):
        running = json.dumps({"status": "running", "total": 100, "completed": 50})
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=running,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
        ):
            result = await service.stop_backfill()

        assert result == {"message": "已发送停止信号"}
        # First call sets stop signal key, second sets progress status
        assert mock_cache_set.call_count == 2
        # The progress update call should have stopping status
        progress_call = mock_cache_set.call_args_list[1]
        saved = json.loads(progress_call.args[1])
        assert saved["status"] == "stopping"

    @pytest.mark.asyncio
    async def test_sets_stopping_when_pending(self, service):
        pending = json.dumps({"status": "pending", "total": 10})
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=pending,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ) as mock_cache_set,
        ):
            result = await service.stop_backfill()

        assert result == {"message": "已发送停止信号"}
        progress_call = mock_cache_set.call_args_list[1]
        saved = json.loads(progress_call.args[1])
        assert saved["status"] == "stopping"

    @pytest.mark.asyncio
    async def test_returns_no_task_when_idle(self, service):
        idle = json.dumps({"status": "idle"})
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=idle,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
        ):
            result = await service.stop_backfill()

        assert result == {"message": "当前没有正在执行的回填任务"}

    @pytest.mark.asyncio
    async def test_returns_no_task_when_no_redis_data(self, service):
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
        ):
            result = await service.stop_backfill()

        assert result == {"message": "当前没有正在执行的回填任务"}

    @pytest.mark.asyncio
    async def test_returns_no_task_on_corrupt_json(self, service):
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value="not-json{{{",
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
        ):
            result = await service.stop_backfill()

        assert result == {"message": "当前没有正在执行的回填任务"}

    @pytest.mark.asyncio
    async def test_returns_no_task_when_completed(self, service):
        completed = json.dumps({"status": "completed"})
        with (
            patch(
                "app.services.data_engine.backfill_service.cache_get",
                new_callable=AsyncMock,
                return_value=completed,
            ),
            patch(
                "app.services.data_engine.backfill_service.cache_set",
                new_callable=AsyncMock,
            ),
        ):
            result = await service.stop_backfill()

        assert result == {"message": "当前没有正在执行的回填任务"}
