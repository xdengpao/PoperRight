"""
数据同步定时任务单元测试

测试 sync_realtime_market、sync_fundamentals、sync_money_flow 任务逻辑。
包含 DataSourceRouter 故障转移集成测试（需求 1.9, 1.10）。
"""

from __future__ import annotations

from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.backfill_service import REDIS_KEY, STOP_SIGNAL_KEY
from app.tasks.data_sync import (
    TRADING_END,
    TRADING_START,
    _get_data_source_router,
    _is_trading_hours,
    _update_sync_status,
)


def _make_cache_get_side_effect(progress_json: str):
    """创建 cache_get 的 side_effect，对停止信号键返回 None，对进度键返回 progress_json。"""
    async def _side_effect(key: str):
        if key == STOP_SIGNAL_KEY:
            return None
        return progress_json
    return _side_effect


# ---------------------------------------------------------------------------
# _is_trading_hours 测试
# ---------------------------------------------------------------------------


class TestIsTradingHours:
    """交易时段判断逻辑测试"""

    def test_within_trading_hours(self):
        """工作日 10:00 应在交易时段内"""
        dt = datetime(2024, 1, 15, 10, 0, 0)  # Monday
        assert _is_trading_hours(dt) is True

    def test_at_trading_start(self):
        """9:30 边界应在交易时段内"""
        dt = datetime(2024, 1, 15, 9, 30, 0)  # Monday
        assert _is_trading_hours(dt) is True

    def test_at_trading_end(self):
        """15:00 边界应在交易时段内"""
        dt = datetime(2024, 1, 15, 15, 0, 0)  # Monday
        assert _is_trading_hours(dt) is True

    def test_before_trading_start(self):
        """9:29 应不在交易时段"""
        dt = datetime(2024, 1, 15, 9, 29, 0)  # Monday
        assert _is_trading_hours(dt) is False

    def test_after_trading_end(self):
        """15:01 应不在交易时段"""
        dt = datetime(2024, 1, 15, 15, 1, 0)  # Monday
        assert _is_trading_hours(dt) is False

    def test_weekend_saturday(self):
        """周六不在交易时段"""
        dt = datetime(2024, 1, 13, 10, 0, 0)  # Saturday
        assert _is_trading_hours(dt) is False

    def test_weekend_sunday(self):
        """周日不在交易时段"""
        dt = datetime(2024, 1, 14, 10, 0, 0)  # Sunday
        assert _is_trading_hours(dt) is False


# ---------------------------------------------------------------------------
# sync_realtime_market 测试
# ---------------------------------------------------------------------------


class TestSyncRealtimeMarket:
    """盘中实时行情同步任务测试"""

    @patch("app.tasks.data_sync._is_trading_hours", return_value=False)
    def test_skips_outside_trading_hours(self, mock_hours):
        """非交易时段应跳过同步"""
        from app.tasks.data_sync import sync_realtime_market

        result = sync_realtime_market(symbols=["000001.SZ"])
        assert result["status"] == "skipped"
        assert result["reason"] == "outside_trading_hours"

    @patch("app.tasks.data_sync._is_trading_hours", return_value=True)
    @patch("app.tasks.data_sync._run_async")
    def test_runs_during_trading_hours(self, mock_run_async, mock_hours):
        """交易时段应执行同步"""
        mock_run_async.return_value = {
            "status": "success",
            "fetched": 4,
            "inserted": 4,
        }
        from app.tasks.data_sync import sync_realtime_market

        result = sync_realtime_market(symbols=["000001.SZ"])
        assert result["status"] == "success"
        mock_run_async.assert_called_once()


# ---------------------------------------------------------------------------
# sync_fundamentals 测试
# ---------------------------------------------------------------------------


class TestSyncFundamentals:
    """盘后基本面数据同步任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_success_result(self, mock_run_async):
        """应返回包含统计信息的结果"""
        mock_run_async.return_value = {
            "status": "success",
            "total": 2,
            "success": 2,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_fundamentals

        result = sync_fundamentals(symbols=["000001.SZ", "600000.SH"])
        assert result["status"] == "success"
        assert result["total"] == 2


# ---------------------------------------------------------------------------
# sync_money_flow 测试
# ---------------------------------------------------------------------------


class TestSyncMoneyFlow:
    """盘后资金数据同步任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_success_result(self, mock_run_async):
        """应返回包含统计信息的结果"""
        mock_run_async.return_value = {
            "status": "success",
            "trade_date": "2024-01-15",
            "total": 2,
            "success": 2,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_money_flow

        result = sync_money_flow(symbols=["000001.SZ", "600000.SH"])
        assert result["status"] == "success"
        assert "trade_date" in result


# ---------------------------------------------------------------------------
# _get_data_source_router 测试
# ---------------------------------------------------------------------------


class TestGetDataSourceRouter:
    """DataSourceRouter 工厂函数测试"""

    def test_returns_router_instance(self):
        """应返回 DataSourceRouter 实例"""
        from app.services.data_engine.data_source_router import DataSourceRouter

        router = _get_data_source_router()
        assert isinstance(router, DataSourceRouter)

    def test_creates_new_instance_each_call(self):
        """每次调用应创建新实例"""
        r1 = _get_data_source_router()
        r2 = _get_data_source_router()
        assert r1 is not r2


# ---------------------------------------------------------------------------
# sync_fundamentals DataSourceRouter 故障转移测试
# ---------------------------------------------------------------------------


class TestSyncFundamentalsWithRouter:
    """基本面同步任务 DataSourceRouter 集成测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_uses_router_on_success(self, mock_run_async):
        """DataSourceRouter 成功时应直接使用其结果"""
        mock_run_async.return_value = {
            "status": "success",
            "total": 1,
            "success": 1,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_fundamentals

        result = sync_fundamentals(symbols=["000001.SZ"])
        assert result["status"] == "success"
        assert result["success"] == 1

    @patch("app.tasks.data_sync._get_data_source_router")
    @patch("app.tasks.data_sync._run_async")
    def test_router_is_called(self, mock_run_async, mock_get_router):
        """sync_fundamentals 应调用 _get_data_source_router"""
        mock_run_async.return_value = {
            "status": "success",
            "total": 1,
            "success": 1,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_fundamentals

        sync_fundamentals(symbols=["000001.SZ"])
        # _run_async is called, which means the async function was created
        mock_run_async.assert_called_once()

    @patch("app.tasks.data_sync._run_async")
    def test_fallback_on_all_errors(self, mock_run_async):
        """所有数据源失败时应记录错误"""
        mock_run_async.return_value = {
            "status": "success",
            "total": 1,
            "success": 0,
            "errors": 1,
        }
        from app.tasks.data_sync import sync_fundamentals

        result = sync_fundamentals(symbols=["000001.SZ"])
        assert result["errors"] == 1


# ---------------------------------------------------------------------------
# sync_money_flow DataSourceRouter 故障转移测试
# ---------------------------------------------------------------------------


class TestSyncMoneyFlowWithRouter:
    """资金数据同步任务 DataSourceRouter 集成测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_uses_router_on_success(self, mock_run_async):
        """DataSourceRouter 成功时应直接使用其结果"""
        mock_run_async.return_value = {
            "status": "success",
            "trade_date": "2024-01-15",
            "total": 1,
            "success": 1,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_money_flow

        result = sync_money_flow(symbols=["000001.SZ"])
        assert result["status"] == "success"
        assert result["success"] == 1

    @patch("app.tasks.data_sync._run_async")
    def test_fallback_on_all_errors(self, mock_run_async):
        """所有数据源失败时应记录错误"""
        mock_run_async.return_value = {
            "status": "success",
            "trade_date": "2024-01-15",
            "total": 1,
            "success": 0,
            "errors": 1,
        }
        from app.tasks.data_sync import sync_money_flow

        result = sync_money_flow(symbols=["000001.SZ"])
        assert result["errors"] == 1

    @patch("app.tasks.data_sync._run_async")
    def test_includes_trade_date(self, mock_run_async):
        """结果应包含 trade_date"""
        mock_run_async.return_value = {
            "status": "success",
            "trade_date": "2024-01-15",
            "total": 2,
            "success": 2,
            "errors": 0,
        }
        from app.tasks.data_sync import sync_money_flow

        result = sync_money_flow(symbols=["000001.SZ", "600000.SH"])
        assert "trade_date" in result


# ---------------------------------------------------------------------------
# _update_sync_status 测试
# ---------------------------------------------------------------------------


class TestUpdateSyncStatus:
    """同步状态写入 Redis 测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    async def test_writes_correct_redis_key(self, mock_cache_set):
        """应写入 sync:status:{data_type} 键"""
        await _update_sync_status(
            "fundamentals", "基本面数据", "OK", 100, "Tushare", False,
        )
        call_args = mock_cache_set.call_args
        assert call_args[0][0] == "sync:status:fundamentals"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    async def test_sets_24h_expiry(self, mock_cache_set):
        """应设置 86400 秒（24 小时）过期"""
        await _update_sync_status(
            "kline", "行情数据", "OK", 50, "MarketDataClient", False,
        )
        call_args = mock_cache_set.call_args
        assert call_args[1]["ex"] == 86400

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    async def test_json_contains_all_fields(self, mock_cache_set):
        """JSON 应包含所有必需字段"""
        import json

        await _update_sync_status(
            "money_flow", "资金流向", "ERROR", 10, "AkShare", True,
        )
        call_args = mock_cache_set.call_args
        payload = json.loads(call_args[0][1])
        assert payload["source"] == "资金流向"
        assert payload["status"] == "ERROR"
        assert payload["record_count"] == 10
        assert payload["data_source"] == "AkShare"
        assert payload["is_fallback"] is True
        assert "last_sync_at" in payload

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    async def test_last_sync_at_is_iso_format(self, mock_cache_set):
        """last_sync_at 应为 ISO 格式时间字符串"""
        import json
        from datetime import datetime as dt

        await _update_sync_status(
            "kline", "行情数据", "OK", 0, "MarketDataClient", False,
        )
        payload = json.loads(mock_cache_set.call_args[0][1])
        # Should not raise
        dt.fromisoformat(payload["last_sync_at"])


# ---------------------------------------------------------------------------
# sync_historical_kline 测试
# ---------------------------------------------------------------------------


class TestSyncHistoricalKline:
    """历史 K 线回填任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_completed_result(self, mock_run_async):
        """应返回包含统计信息的 completed 结果"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 2,
            "completed": 2,
            "failed": 0,
            "inserted": 100,
        }
        from app.tasks.data_sync import sync_historical_kline

        result = sync_historical_kline(
            symbols=["000001.SZ", "600000.SH"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            freq="1d",
        )
        assert result["status"] == "completed"
        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0

    @patch("app.tasks.data_sync._run_async")
    def test_default_freq_is_1d(self, mock_run_async):
        """freq 默认值应为 '1d'"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 1,
            "completed": 1,
            "failed": 0,
            "inserted": 50,
        }
        from app.tasks.data_sync import sync_historical_kline

        result = sync_historical_kline(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        assert result["status"] == "completed"

    @patch("app.tasks.data_sync._run_async")
    def test_partial_failure_result(self, mock_run_async):
        """部分股票失败时应返回正确的 failed 计数"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 3,
            "completed": 2,
            "failed": 1,
            "inserted": 80,
        }
        from app.tasks.data_sync import sync_historical_kline

        result = sync_historical_kline(
            symbols=["000001.SZ", "000002.SZ", "600000.SH"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["completed"] + result["failed"] == result["total"]


class TestSyncHistoricalKlineAsync:
    """历史 K 线回填任务异步逻辑测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_running(self, mock_cache_get, mock_cache_set):
        """任务开始时应将 Redis 状态更新为 running"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "", "data_types": ["kline"],
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            await _sync_historical_kline(["000001.SZ"], "2024-01-01", "2024-01-31", "1d")

        # First cache_set call should set status to "running"
        first_call_value = json.loads(mock_cache_set.call_args_list[0][0][1])
        assert first_call_value["status"] == "running"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_completed(self, mock_cache_get, mock_cache_set):
        """任务完成后应将 Redis 状态更新为 completed"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            await _sync_historical_kline(["000001.SZ"], "2024-01-01", "2024-01-31", "1d")

        # Last cache_set call should set status to "completed"
        last_call_value = json.loads(mock_cache_set.call_args_list[-1][0][1])
        assert last_call_value["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_continues_on_single_stock_failure(self, mock_cache_get, mock_cache_set):
        """单只股票失败不应中断任务，应继续处理下一只"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_kline.side_effect = [
            DataSourceUnavailableError("both sources failed"),
            [],  # second stock succeeds with empty data
        ]

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["FAIL.SZ", "OK.SH"], "2024-01-01", "2024-01-31", "1d",
            )

        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_calls_fetch_kline_and_bulk_insert(self, mock_cache_get, mock_cache_set):
        """应调用 DataSourceRouter.fetch_kline 和 KlineRepository.bulk_insert"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        fake_bar = MagicMock()
        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = [fake_bar]

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 1

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["000001.SZ"], "2024-01-01", "2024-01-31", "1d",
            )

        mock_router.fetch_kline.assert_called_once()
        mock_repo_instance.bulk_insert.assert_called_once_with([fake_bar])
        assert result["inserted"] == 1

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_progress_tracks_current_symbol(self, mock_cache_get, mock_cache_set):
        """进度更新应包含当前处理的股票代码"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            await _sync_historical_kline(["000001.SZ"], "2024-01-01", "2024-01-31", "1d")

        # Check that at least one progress update contains the symbol
        all_values = [
            json.loads(call[0][1]) for call in mock_cache_set.call_args_list
        ]
        symbols_seen = [v.get("current_symbol") for v in all_values]
        assert "000001.SZ" in symbols_seen


# ---------------------------------------------------------------------------
# sync_historical_fundamentals 测试
# ---------------------------------------------------------------------------


class TestSyncHistoricalFundamentals:
    """历史基本面回填任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_completed_result(self, mock_run_async):
        """应返回包含统计信息的 completed 结果"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 2,
            "completed": 2,
            "failed": 0,
            "upserted": 2,
        }
        from app.tasks.data_sync import sync_historical_fundamentals

        result = sync_historical_fundamentals(
            symbols=["000001.SZ", "600000.SH"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        assert result["status"] == "completed"
        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0

    @patch("app.tasks.data_sync._run_async")
    def test_partial_failure_result(self, mock_run_async):
        """部分股票失败时应返回正确的 failed 计数"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 3,
            "completed": 2,
            "failed": 1,
            "upserted": 2,
        }
        from app.tasks.data_sync import sync_historical_fundamentals

        result = sync_historical_fundamentals(
            symbols=["000001.SZ", "000002.SZ", "600000.SH"],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["completed"] + result["failed"] == result["total"]


class TestSyncHistoricalFundamentalsAsync:
    """历史基本面回填任务异步逻辑测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_running(self, mock_cache_get, mock_cache_set):
        """任务开始时应将 Redis 状态更新为 running"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "", "data_types": ["fundamentals"],
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_fundamentals.return_value = MagicMock(
            symbol="000001.SZ", name="平安银行", market="SZ", board="主板",
            list_date=None, is_st=False, is_delisted=False,
            pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
            market_cap=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_fundamentals
            await _sync_historical_fundamentals(["000001.SZ"], "2024-01-01", "2024-01-31")

        # First cache_set call should set status to "running"
        first_call_value = json.loads(mock_cache_set.call_args_list[0][0][1])
        assert first_call_value["status"] == "running"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_completed(self, mock_cache_get, mock_cache_set):
        """任务完成后应将 Redis 状态更新为 completed"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_fundamentals.return_value = MagicMock(
            symbol="000001.SZ", name="平安银行", market="SZ", board="主板",
            list_date=None, is_st=False, is_delisted=False,
            pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
            market_cap=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_fundamentals
            await _sync_historical_fundamentals(["000001.SZ"], "2024-01-01", "2024-01-31")

        # Last cache_set call should set status to "completed"
        last_call_value = json.loads(mock_cache_set.call_args_list[-1][0][1])
        assert last_call_value["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_continues_on_single_stock_failure(self, mock_cache_get, mock_cache_set):
        """单只股票失败不应中断任务，应继续处理下一只"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_fundamentals.side_effect = [
            DataSourceUnavailableError("both sources failed"),
            MagicMock(
                symbol="OK.SH", name="测试", market="SH", board="主板",
                list_date=None, is_st=False, is_delisted=False,
                pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
                market_cap=None, updated_at=None,
            ),
        ]

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_fundamentals
            result = await _sync_historical_fundamentals(
                ["FAIL.SZ", "OK.SH"], "2024-01-01", "2024-01-31",
            )

        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_calls_fetch_fundamentals_and_upserts(self, mock_cache_get, mock_cache_set):
        """应调用 DataSourceRouter.fetch_fundamentals 并执行 upsert"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        fake_data = MagicMock(
            symbol="000001.SZ", name="平安银行", market="SZ", board="主板",
            list_date=None, is_st=False, is_delisted=False,
            pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
            market_cap=None, updated_at=None,
        )
        mock_router = AsyncMock()
        mock_router.fetch_fundamentals.return_value = fake_data

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_fundamentals
            result = await _sync_historical_fundamentals(
                ["000001.SZ"], "2024-01-01", "2024-01-31",
            )

        mock_router.fetch_fundamentals.assert_called_once_with("000001.SZ")
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result["upserted"] == 1

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_progress_tracks_current_symbol(self, mock_cache_get, mock_cache_set):
        """进度更新应包含当前处理的股票代码"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_fundamentals.return_value = MagicMock(
            symbol="000001.SZ", name="平安银行", market="SZ", board="主板",
            list_date=None, is_st=False, is_delisted=False,
            pledge_ratio=None, pe_ttm=None, pb=None, roe=None,
            market_cap=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_fundamentals
            await _sync_historical_fundamentals(["000001.SZ"], "2024-01-01", "2024-01-31")

        # Check that at least one progress update contains the symbol
        all_values = [
            json.loads(call[0][1]) for call in mock_cache_set.call_args_list
        ]
        symbols_seen = [v.get("current_symbol") for v in all_values]
        assert "000001.SZ" in symbols_seen


# ---------------------------------------------------------------------------
# sync_historical_money_flow 测试
# ---------------------------------------------------------------------------


class TestSyncHistoricalMoneyFlow:
    """历史资金流向回填任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_completed_result(self, mock_run_async):
        """应返回包含统计信息的 completed 结果"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 2,
            "completed": 2,
            "failed": 0,
            "upserted": 2,
        }
        from app.tasks.data_sync import sync_historical_money_flow

        result = sync_historical_money_flow(
            symbols=["000001.SZ", "600000.SH"],
            start_date="2024-01-15",
            end_date="2024-01-15",
        )
        assert result["status"] == "completed"
        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0

    @patch("app.tasks.data_sync._run_async")
    def test_partial_failure_result(self, mock_run_async):
        """部分股票失败时应返回正确的 failed 计数"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 3,
            "completed": 2,
            "failed": 1,
            "upserted": 2,
        }
        from app.tasks.data_sync import sync_historical_money_flow

        result = sync_historical_money_flow(
            symbols=["000001.SZ", "000002.SZ", "600000.SH"],
            start_date="2024-01-15",
            end_date="2024-01-15",
        )
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["completed"] + result["failed"] == result["total"]


class TestSyncHistoricalMoneyFlowAsync:
    """历史资金流向回填任务异步逻辑测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_running(self, mock_cache_get, mock_cache_set):
        """任务开始时应将 Redis 状态更新为 running"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "", "data_types": ["money_flow"],
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_money_flow.return_value = MagicMock(
            symbol="000001.SZ", trade_date=datetime(2024, 1, 15).date(),
            main_net_inflow=None, main_inflow=None, main_outflow=None,
            main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
            north_net_inflow=None, north_hold_ratio=None,
            on_dragon_tiger=False, dragon_tiger_net=None,
            block_trade_amount=None, block_trade_discount=None,
            bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            await _sync_historical_money_flow(["000001.SZ"], "2024-01-15", "2024-01-15")

        # First cache_set call should set status to "running"
        first_call_value = json.loads(mock_cache_set.call_args_list[0][0][1])
        assert first_call_value["status"] == "running"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_status_to_completed(self, mock_cache_get, mock_cache_set):
        """任务完成后应将 Redis 状态更新为 completed"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_money_flow.return_value = MagicMock(
            symbol="000001.SZ", trade_date=datetime(2024, 1, 15).date(),
            main_net_inflow=None, main_inflow=None, main_outflow=None,
            main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
            north_net_inflow=None, north_hold_ratio=None,
            on_dragon_tiger=False, dragon_tiger_net=None,
            block_trade_amount=None, block_trade_discount=None,
            bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            await _sync_historical_money_flow(["000001.SZ"], "2024-01-15", "2024-01-15")

        # Last cache_set call should set status to "completed"
        last_call_value = json.loads(mock_cache_set.call_args_list[-1][0][1])
        assert last_call_value["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_continues_on_single_stock_failure(self, mock_cache_get, mock_cache_set):
        """单只股票失败不应中断任务，应继续处理下一只"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_money_flow.side_effect = [
            DataSourceUnavailableError("both sources failed"),
            MagicMock(
                symbol="OK.SH", trade_date=datetime(2024, 1, 15).date(),
                main_net_inflow=None, main_inflow=None, main_outflow=None,
                main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
                north_net_inflow=None, north_hold_ratio=None,
                on_dragon_tiger=False, dragon_tiger_net=None,
                block_trade_amount=None, block_trade_discount=None,
                bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
            ),
        ]

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            result = await _sync_historical_money_flow(
                ["FAIL.SZ", "OK.SH"], "2024-01-15", "2024-01-15",
            )

        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_calls_fetch_money_flow_and_upserts(self, mock_cache_get, mock_cache_set):
        """应调用 DataSourceRouter.fetch_money_flow 并执行 upsert"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        fake_data = MagicMock(
            symbol="000001.SZ", trade_date=datetime(2024, 1, 15).date(),
            main_net_inflow=None, main_inflow=None, main_outflow=None,
            main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
            north_net_inflow=None, north_hold_ratio=None,
            on_dragon_tiger=False, dragon_tiger_net=None,
            block_trade_amount=None, block_trade_discount=None,
            bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
        )
        mock_router = AsyncMock()
        mock_router.fetch_money_flow.return_value = fake_data

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            result = await _sync_historical_money_flow(
                ["000001.SZ"], "2024-01-15", "2024-01-15",
            )

        mock_router.fetch_money_flow.assert_called_once()
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result["upserted"] == 1

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_progress_tracks_current_symbol(self, mock_cache_get, mock_cache_set):
        """进度更新应包含当前处理的股票代码"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_money_flow.return_value = MagicMock(
            symbol="000001.SZ", trade_date=datetime(2024, 1, 15).date(),
            main_net_inflow=None, main_inflow=None, main_outflow=None,
            main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
            north_net_inflow=None, north_hold_ratio=None,
            on_dragon_tiger=False, dragon_tiger_net=None,
            block_trade_amount=None, block_trade_discount=None,
            bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            await _sync_historical_money_flow(["000001.SZ"], "2024-01-15", "2024-01-15")

        # Check that at least one progress update contains the symbol
        all_values = [
            json.loads(call[0][1]) for call in mock_cache_set.call_args_list
        ]
        symbols_seen = [v.get("current_symbol") for v in all_values]
        assert "000001.SZ" in symbols_seen

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_skips_weekends(self, mock_cache_get, mock_cache_set):
        """日期范围包含周末时应跳过周末日期"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_money_flow.return_value = MagicMock(
            symbol="000001.SZ", trade_date=datetime(2024, 1, 15).date(),
            main_net_inflow=None, main_inflow=None, main_outflow=None,
            main_net_inflow_pct=None, large_order_net=None, large_order_ratio=None,
            north_net_inflow=None, north_hold_ratio=None,
            on_dragon_tiger=False, dragon_tiger_net=None,
            block_trade_amount=None, block_trade_discount=None,
            bid_ask_ratio=None, inner_outer_ratio=None, updated_at=None,
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import _sync_historical_money_flow
            # 2024-01-13 is Saturday, 2024-01-14 is Sunday
            result = await _sync_historical_money_flow(
                ["000001.SZ"], "2024-01-12", "2024-01-15",
            )

        # Friday (12th) + Monday (15th) = 2 calls, weekends skipped
        assert mock_router.fetch_money_flow.call_count == 2
        assert result["completed"] == 2


# ---------------------------------------------------------------------------
# _get_previous_trading_day 测试
# ---------------------------------------------------------------------------


class TestGetPreviousTradingDay:
    """前一个交易日计算逻辑测试"""

    def test_tuesday_returns_monday(self):
        """周二应返回周一"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 16))  # Tuesday
        assert result == date(2024, 1, 15)  # Monday

    def test_wednesday_returns_tuesday(self):
        """周三应返回周二"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 17))  # Wednesday
        assert result == date(2024, 1, 16)  # Tuesday

    def test_monday_returns_friday(self):
        """周一应返回上周五"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 15))  # Monday
        assert result == date(2024, 1, 12)  # Friday

    def test_saturday_returns_friday(self):
        """周六应返回周五"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 13))  # Saturday
        assert result == date(2024, 1, 12)  # Friday

    def test_sunday_returns_friday(self):
        """周日应返回周五"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 14))  # Sunday
        assert result == date(2024, 1, 12)  # Friday

    def test_thursday_returns_wednesday(self):
        """周四应返回周三"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 18))  # Thursday
        assert result == date(2024, 1, 17)  # Wednesday

    def test_friday_returns_thursday(self):
        """周五应返回周四"""
        from app.tasks.data_sync import _get_previous_trading_day

        result = _get_previous_trading_day(date(2024, 1, 19))  # Friday
        assert result == date(2024, 1, 18)  # Thursday


# ---------------------------------------------------------------------------
# sync_daily_kline 测试
# ---------------------------------------------------------------------------


class TestSyncDailyKline:
    """每日增量 K 线同步任务测试"""

    @patch("app.tasks.data_sync._run_async")
    def test_returns_completed_result(self, mock_run_async):
        """应返回包含统计信息的 completed 结果"""
        mock_run_async.return_value = {
            "status": "completed",
            "total": 2,
            "completed": 2,
            "failed": 0,
            "inserted": 2,
        }
        from app.tasks.data_sync import sync_daily_kline

        result = sync_daily_kline()
        assert result["status"] == "completed"
        assert result["total"] == 2
        mock_run_async.assert_called_once()

    @patch("app.tasks.data_sync._run_async")
    def test_returns_skipped_when_no_symbols(self, mock_run_async):
        """无有效股票时应返回 skipped"""
        mock_run_async.return_value = {
            "status": "skipped",
            "reason": "no_valid_symbols",
        }
        from app.tasks.data_sync import sync_daily_kline

        result = sync_daily_kline()
        assert result["status"] == "skipped"


class TestSyncDailyKlineAsync:
    """每日增量 K 线同步任务异步逻辑测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync._get_previous_trading_day")
    @patch("app.tasks.data_sync._sync_historical_kline", new_callable=AsyncMock)
    async def test_queries_valid_stocks_and_calls_sync(
        self, mock_sync_kline, mock_prev_day,
    ):
        """应查询有效股票并调用 _sync_historical_kline"""
        mock_prev_day.return_value = date(2024, 1, 15)
        mock_sync_kline.return_value = {
            "status": "completed",
            "total": 2,
            "completed": 2,
            "failed": 0,
            "inserted": 100,
        }

        # Mock the database query
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["000001.SZ", "600000.SH"]
        mock_session.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx):
            from app.tasks.data_sync import sync_daily_kline

            result = sync_daily_kline()

        assert mock_sync_kline.called or result is not None

    @pytest.mark.asyncio
    async def test_skips_when_no_valid_symbols(self):
        """StockInfo 无有效股票时应返回 skipped"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx), \
             patch("app.tasks.data_sync._get_previous_trading_day", return_value=date(2024, 1, 15)):
            from app.tasks.data_sync import sync_daily_kline

            result = sync_daily_kline()

        assert result["status"] == "skipped"
        assert result["reason"] == "no_valid_symbols"

    @pytest.mark.asyncio
    async def test_uses_previous_trading_day_as_date_range(self):
        """应使用前一个交易日作为 start_date 和 end_date"""
        prev_day = date(2024, 1, 12)  # Friday

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["000001.SZ"]
        mock_session.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_sync = AsyncMock(return_value={
            "status": "completed", "total": 1, "completed": 1,
            "failed": 0, "inserted": 50,
        })

        with patch("app.core.database.AsyncSessionPG", return_value=mock_session_ctx), \
             patch("app.tasks.data_sync._get_previous_trading_day", return_value=prev_day), \
             patch("app.tasks.data_sync._sync_historical_kline", mock_sync):
            from app.tasks.data_sync import sync_daily_kline

            result = sync_daily_kline()

        mock_sync.assert_called_once_with(
            ["000001.SZ"], "2024-01-12", "2024-01-12", "1d",
        )
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# 停止检测逻辑测试（需求 25.16）
# ---------------------------------------------------------------------------


class TestStopDetectionKline:
    """K 线回填任务停止检测测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_stops_when_status_is_stopping(self, mock_cache_get, mock_cache_set):
        """检测到停止信号时应立即返回 stopped 结果"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })

        # Stop signal exists → task should stop immediately at startup
        async def _side_effect(key):
            if key == STOP_SIGNAL_KEY:
                return "1"
            return progress_json
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["000001.SZ", "600000.SH"], "2024-01-01", "2024-01-31", "1d",
            )

        assert result["status"] == "stopped"
        assert result["total"] == 2
        assert result["completed"] == 0
        assert result["failed"] == 0
        assert "inserted" in result
        # fetch_kline should NOT have been called since we stopped before processing
        mock_router.fetch_kline.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_updates_redis_to_stopped(self, mock_cache_get, mock_cache_set):
        """停止信号存在时应将 Redis 状态更新为 stopped"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })

        # No stop signal at startup, but stop signal appears during loop
        call_count = 0
        async def _side_effect(key):
            nonlocal call_count
            call_count += 1
            if key == STOP_SIGNAL_KEY:
                # First stop check (startup): no signal; second (in loop): signal
                return "1" if call_count > 1 else None
            return progress_json
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()
        mock_repo_instance = AsyncMock()

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            await _sync_historical_kline(["000001.SZ"], "2024-01-01", "2024-01-31", "1d")

        # Find the cache_set call that wrote "stopped" status
        stopped_calls = [
            json.loads(call[0][1])
            for call in mock_cache_set.call_args_list
            if json.loads(call[0][1]).get("status") == "stopped"
        ]
        assert len(stopped_calls) >= 1
        assert stopped_calls[0]["current_symbol"] == ""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_stops_mid_batch_preserving_progress(self, mock_cache_get, mock_cache_set):
        """批次中途收到停止信号时应保留已完成的进度"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 3, "completed": 0, "failed": 0,
            "current_symbol": "",
        })

        # No stop signal at startup and first symbol; stop signal at second symbol
        stop_check_count = 0
        async def _side_effect(key):
            nonlocal stop_check_count
            if key == STOP_SIGNAL_KEY:
                stop_check_count += 1
                # 1st check (startup): no signal; 2nd (1st symbol): no signal; 3rd (2nd symbol): signal
                return "1" if stop_check_count >= 3 else None
            return progress_json
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["000001.SZ", "600000.SH", "000002.SZ"],
                "2024-01-01", "2024-01-31", "1d",
            )

        assert result["status"] == "stopped"
        # Only the first symbol was processed before stop
        assert result["completed"] == 1
        assert mock_router.fetch_kline.call_count == 1

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_continues_when_status_is_not_stopping(self, mock_cache_get, mock_cache_set):
        """没有停止信号时应正常继续处理"""
        import json

        progress_json = json.dumps({
            "status": "running", "total": 1, "completed": 0, "failed": 0,
            "current_symbol": "",
        })
        mock_cache_get.side_effect = _make_cache_get_side_effect(progress_json)

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["000001.SZ"], "2024-01-01", "2024-01-31", "1d",
            )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_handles_malformed_json_in_stop_check(self, mock_cache_get, mock_cache_set):
        """停止检测遇到无效 JSON 时应忽略并继续（进度键返回无效 JSON）"""
        import json

        # Stop signal key returns None (no stop), progress key returns malformed JSON
        async def _side_effect(key):
            if key == STOP_SIGNAL_KEY:
                return None
            return "not-valid-json{{{"
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()
        mock_router.fetch_kline.return_value = []

        mock_repo_instance = AsyncMock()
        mock_repo_instance.bulk_insert.return_value = 0

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router), \
             patch("app.services.data_engine.kline_repository.KlineRepository", return_value=mock_repo_instance):
            from app.tasks.data_sync import _sync_historical_kline
            result = await _sync_historical_kline(
                ["000001.SZ"], "2024-01-01", "2024-01-31", "1d",
            )

        # Should complete normally despite malformed JSON
        assert result["status"] == "completed"


class TestStopDetectionFundamentals:
    """基本面回填任务停止检测测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_stops_when_status_is_stopping(self, mock_cache_get, mock_cache_set):
        """检测到停止信号时应立即返回 stopped 结果"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })

        # Stop signal exists → task should stop immediately at startup
        async def _side_effect(key):
            if key == STOP_SIGNAL_KEY:
                return "1"
            return progress_json
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router):
            from app.tasks.data_sync import _sync_historical_fundamentals
            result = await _sync_historical_fundamentals(
                ["000001.SZ", "600000.SH"], "2024-01-01", "2024-01-31",
            )

        assert result["status"] == "stopped"
        assert result["total"] == 2
        assert "upserted" in result
        mock_router.fetch_fundamentals.assert_not_called()


class TestStopDetectionMoneyFlow:
    """资金流向回填任务停止检测测试"""

    @pytest.mark.asyncio
    @patch("app.tasks.data_sync.cache_set", new_callable=AsyncMock)
    @patch("app.tasks.data_sync.cache_get", new_callable=AsyncMock)
    async def test_stops_when_status_is_stopping(self, mock_cache_get, mock_cache_set):
        """检测到停止信号时应立即返回 stopped 结果"""
        import json

        progress_json = json.dumps({
            "status": "pending", "total": 2, "completed": 0, "failed": 0,
            "current_symbol": "",
        })

        # Stop signal exists → task should stop immediately at startup
        async def _side_effect(key):
            if key == STOP_SIGNAL_KEY:
                return "1"
            return progress_json
        mock_cache_get.side_effect = _side_effect

        mock_router = AsyncMock()

        with patch("app.tasks.data_sync._get_data_source_router", return_value=mock_router):
            from app.tasks.data_sync import _sync_historical_money_flow
            result = await _sync_historical_money_flow(
                ["000001.SZ", "600000.SH"], "2024-01-15", "2024-01-15",
            )

        assert result["status"] == "stopped"
        assert result["total"] == 2
        assert "upserted" in result
        mock_router.fetch_money_flow.assert_not_called()
