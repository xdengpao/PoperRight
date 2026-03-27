"""
数据同步定时任务单元测试

测试 sync_realtime_market、sync_fundamentals、sync_money_flow 任务逻辑。
"""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.data_sync import (
    TRADING_END,
    TRADING_START,
    _is_trading_hours,
)


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
