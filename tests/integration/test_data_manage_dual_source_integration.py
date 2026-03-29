"""
数据管理页面双数据源集成测试

21.10.1 健康检查 → 状态卡片渲染 → 手动同步（指定类型）→ 同步状态刷新（含数据源列）全链路测试
21.10.2 数据库写入测试数据 → 清洗统计 API 查询 → 前端展示验证全链路测试

对应需求：24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.data import (
    get_sources_health,
    trigger_sync,
    get_sync_status,
    get_cleaning_stats,
    SyncRequest,
)


# ---------------------------------------------------------------------------
# 21.10.1 健康检查 → 手动同步 → 同步状态刷新 全链路测试
# ---------------------------------------------------------------------------


class TestHealthSyncStatusIntegration:
    """
    验证全链路：
    - GET /data/sources/health 返回 2 个数据源及正确状态映射
    - POST /data/sync (sync_type="fundamentals") 仅分发 sync_fundamentals
    - POST /data/sync (sync_type="all") 分发全部 3 个任务
    - GET /data/sync/status 返回含 data_source 和 is_fallback 字段的条目

    **Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5, 24.6**
    """

    def test_health_check_returns_two_sources_with_correct_status(self):
        """GET /data/sources/health 返回 2 个数据源，connected/disconnected 映射正确。"""

        async def _run():
            with patch(
                "app.api.v1.data.TushareAdapter"
            ) as MockTushare, patch(
                "app.api.v1.data.AkShareAdapter"
            ) as MockAkShare:
                tushare_inst = AsyncMock()
                akshare_inst = AsyncMock()
                tushare_inst.health_check.return_value = True
                akshare_inst.health_check.return_value = False
                MockTushare.return_value = tushare_inst
                MockAkShare.return_value = akshare_inst

                result = await get_sources_health()

            assert len(result.sources) == 2

            tushare_src = result.sources[0]
            akshare_src = result.sources[1]

            assert tushare_src.name == "Tushare"
            assert tushare_src.status == "connected"
            assert tushare_src.checked_at  # non-empty ISO timestamp

            assert akshare_src.name == "AkShare"
            assert akshare_src.status == "disconnected"
            assert akshare_src.checked_at

        asyncio.run(_run())

    def test_health_check_exception_maps_to_disconnected(self):
        """health_check 抛出异常时，状态映射为 disconnected。"""

        async def _run():
            with patch(
                "app.api.v1.data.TushareAdapter"
            ) as MockTushare, patch(
                "app.api.v1.data.AkShareAdapter"
            ) as MockAkShare:
                tushare_inst = AsyncMock()
                akshare_inst = AsyncMock()
                tushare_inst.health_check.side_effect = ConnectionError("timeout")
                akshare_inst.health_check.side_effect = RuntimeError("fail")
                MockTushare.return_value = tushare_inst
                MockAkShare.return_value = akshare_inst

                result = await get_sources_health()

            assert len(result.sources) == 2
            assert result.sources[0].status == "disconnected"
            assert result.sources[1].status == "disconnected"

        asyncio.run(_run())

    def test_sync_fundamentals_dispatches_only_fundamentals_task(self):
        """POST /data/sync (sync_type="fundamentals") 仅分发 sync_fundamentals 任务。"""

        async def _run():
            with patch(
                "app.tasks.data_sync.sync_realtime_market"
            ) as mock_kline, patch(
                "app.tasks.data_sync.sync_fundamentals"
            ) as mock_fund, patch(
                "app.tasks.data_sync.sync_money_flow"
            ) as mock_mf:
                mock_fund_result = MagicMock()
                mock_fund_result.id = "task-fund-001"
                mock_fund.delay.return_value = mock_fund_result

                body = SyncRequest(sync_type="fundamentals")
                result = await trigger_sync(body)

            assert len(result.task_ids) == 1
            assert result.task_ids[0] == "task-fund-001"
            mock_fund.delay.assert_called_once()
            mock_kline.delay.assert_not_called()
            mock_mf.delay.assert_not_called()

        asyncio.run(_run())

    def test_sync_all_dispatches_three_tasks(self):
        """POST /data/sync (sync_type="all") 分发全部 3 个任务。"""

        async def _run():
            with patch(
                "app.tasks.data_sync.sync_realtime_market"
            ) as mock_kline, patch(
                "app.tasks.data_sync.sync_fundamentals"
            ) as mock_fund, patch(
                "app.tasks.data_sync.sync_money_flow"
            ) as mock_mf:
                for i, mock_task in enumerate([mock_kline, mock_fund, mock_mf]):
                    r = MagicMock()
                    r.id = f"task-all-{i}"
                    mock_task.delay.return_value = r

                body = SyncRequest(sync_type="all")
                result = await trigger_sync(body)

            assert len(result.task_ids) == 3
            mock_kline.delay.assert_called_once()
            mock_fund.delay.assert_called_once()
            mock_mf.delay.assert_called_once()

        asyncio.run(_run())

    def test_sync_status_contains_data_source_and_is_fallback(self):
        """GET /data/sync/status 返回的每个条目包含 data_source 和 is_fallback 字段。"""

        cached_data = {
            "kline": json.dumps({
                "source": "行情数据",
                "last_sync_at": "2024-01-15T10:00:00",
                "status": "OK",
                "record_count": 5000,
                "data_source": "Tushare",
                "is_fallback": False,
            }),
            "fundamentals": json.dumps({
                "source": "基本面数据",
                "last_sync_at": "2024-01-15T09:30:00",
                "status": "OK",
                "record_count": 3000,
                "data_source": "AkShare",
                "is_fallback": True,
            }),
            "money_flow": None,  # no cache → defaults
        }

        async def mock_cache_get(key: str):
            dt = key.replace("sync:status:", "")
            return cached_data.get(dt)

        async def _run():
            with patch("app.core.redis_client.cache_get", side_effect=mock_cache_get):
                result = await get_sync_status()

            assert len(result.items) == 3

            # kline item — from cache
            kline_item = result.items[0]
            assert kline_item.data_source == "Tushare"
            assert kline_item.is_fallback is False
            assert kline_item.record_count == 5000

            # fundamentals item — from cache, fallback
            fund_item = result.items[1]
            assert fund_item.data_source == "AkShare"
            assert fund_item.is_fallback is True

            # money_flow item — no cache, defaults
            mf_item = result.items[2]
            assert mf_item.data_source == "N/A"
            assert mf_item.is_fallback is False
            assert mf_item.status == "UNKNOWN"
            assert mf_item.record_count == 0

        asyncio.run(_run())

    def test_full_flow_health_then_sync_then_status(self):
        """全链路：健康检查 → 按类型同步 → 查询同步状态，各步骤数据一致。"""

        cached_after_sync = json.dumps({
            "source": "基本面数据",
            "last_sync_at": "2024-01-15T11:00:00",
            "status": "OK",
            "record_count": 3200,
            "data_source": "Tushare",
            "is_fallback": False,
        })

        async def mock_cache_get(key: str):
            dt = key.replace("sync:status:", "")
            if dt == "fundamentals":
                return cached_after_sync
            return None

        async def _run():
            # Step 1: Health check
            with patch(
                "app.api.v1.data.TushareAdapter"
            ) as MockTushare, patch(
                "app.api.v1.data.AkShareAdapter"
            ) as MockAkShare:
                t = AsyncMock()
                a = AsyncMock()
                t.health_check.return_value = True
                a.health_check.return_value = True
                MockTushare.return_value = t
                MockAkShare.return_value = a

                health = await get_sources_health()

            assert len(health.sources) == 2
            assert all(s.status == "connected" for s in health.sources)

            # Step 2: Trigger sync by type
            with patch(
                "app.tasks.data_sync.sync_realtime_market"
            ) as mk, patch(
                "app.tasks.data_sync.sync_fundamentals"
            ) as mf, patch(
                "app.tasks.data_sync.sync_money_flow"
            ) as mm:
                r = MagicMock()
                r.id = "task-fund-full"
                mf.delay.return_value = r

                sync_result = await trigger_sync(SyncRequest(sync_type="fundamentals"))

            assert len(sync_result.task_ids) == 1

            # Step 3: Check sync status
            with patch("app.core.redis_client.cache_get", side_effect=mock_cache_get):
                status = await get_sync_status()

            fund_item = status.items[1]
            assert fund_item.data_source == "Tushare"
            assert fund_item.is_fallback is False
            assert fund_item.record_count == 3200

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 21.10.2 数据库写入测试数据 → 清洗统计 API 查询 → 前端展示验证
# ---------------------------------------------------------------------------


class TestCleaningStatsIntegration:
    """
    验证清洗统计端点：
    - Mock AsyncSessionPG 返回特定计数
    - GET /data/cleaning/stats 返回正确统计
    - valid_stocks = max(total - all_exclusions, 0)
    - 所有 6 个字段均存在且正确

    **Validates: Requirements 24.7, 24.8**
    """

    def test_cleaning_stats_returns_correct_counts(self):
        """GET /data/cleaning/stats 返回与数据库数据匹配的正确统计。"""

        total = 5000
        st_delisted = 200
        new_stock = 150
        suspended = 80
        high_pledge = 50
        expected_valid = total - st_delisted - new_stock - suspended - high_pledge  # 4520

        mock_session = AsyncMock()
        # Each execute() call returns a result with scalar_one()
        results = [total, st_delisted, new_stock, suspended, high_pledge]
        mock_results = []
        for val in results:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            mock_results.append(mock_result)

        mock_session.execute = AsyncMock(side_effect=mock_results)

        async def _run():
            with patch("app.core.database.AsyncSessionPG") as MockSessionFactory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                MockSessionFactory.return_value = mock_ctx

                result = await get_cleaning_stats()

            assert result.total_stocks == total
            assert result.valid_stocks == expected_valid
            assert result.st_delisted_count == st_delisted
            assert result.new_stock_count == new_stock
            assert result.suspended_count == suspended
            assert result.high_pledge_count == high_pledge

        asyncio.run(_run())

    def test_cleaning_stats_valid_stocks_never_negative(self):
        """当排除数之和超过总数时，valid_stocks = 0（不为负数）。"""

        total = 100
        st_delisted = 50
        new_stock = 30
        suspended = 20
        high_pledge = 10
        # sum of exclusions = 110 > 100 → valid = max(100 - 110, 0) = 0

        mock_session = AsyncMock()
        results = [total, st_delisted, new_stock, suspended, high_pledge]
        mock_results = []
        for val in results:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            mock_results.append(mock_result)

        mock_session.execute = AsyncMock(side_effect=mock_results)

        async def _run():
            with patch("app.core.database.AsyncSessionPG") as MockSessionFactory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                MockSessionFactory.return_value = mock_ctx

                result = await get_cleaning_stats()

            assert result.valid_stocks == 0
            assert result.total_stocks == total

        asyncio.run(_run())

    def test_cleaning_stats_all_six_fields_present(self):
        """响应包含全部 6 个字段且类型正确。"""

        mock_session = AsyncMock()
        results = [1000, 50, 30, 20, 10]
        mock_results = []
        for val in results:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            mock_results.append(mock_result)

        mock_session.execute = AsyncMock(side_effect=mock_results)

        async def _run():
            with patch("app.core.database.AsyncSessionPG") as MockSessionFactory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                MockSessionFactory.return_value = mock_ctx

                result = await get_cleaning_stats()

            # All 6 fields present
            assert hasattr(result, "total_stocks")
            assert hasattr(result, "valid_stocks")
            assert hasattr(result, "st_delisted_count")
            assert hasattr(result, "new_stock_count")
            assert hasattr(result, "suspended_count")
            assert hasattr(result, "high_pledge_count")

            # Types are int
            assert isinstance(result.total_stocks, int)
            assert isinstance(result.valid_stocks, int)
            assert isinstance(result.st_delisted_count, int)
            assert isinstance(result.new_stock_count, int)
            assert isinstance(result.suspended_count, int)
            assert isinstance(result.high_pledge_count, int)

            # valid_stocks computed correctly
            expected_valid = 1000 - 50 - 30 - 20 - 10
            assert result.valid_stocks == expected_valid

        asyncio.run(_run())

    def test_cleaning_stats_zero_totals(self):
        """所有计数为 0 时，valid_stocks = 0。"""

        mock_session = AsyncMock()
        results = [0, 0, 0, 0, 0]
        mock_results = []
        for val in results:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            mock_results.append(mock_result)

        mock_session.execute = AsyncMock(side_effect=mock_results)

        async def _run():
            with patch("app.core.database.AsyncSessionPG") as MockSessionFactory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                MockSessionFactory.return_value = mock_ctx

                result = await get_cleaning_stats()

            assert result.total_stocks == 0
            assert result.valid_stocks == 0
            assert result.st_delisted_count == 0
            assert result.new_stock_count == 0
            assert result.suspended_count == 0
            assert result.high_pledge_count == 0

        asyncio.run(_run())
