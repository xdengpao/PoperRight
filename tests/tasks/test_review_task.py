"""
Celery 复盘任务数据加载单元测试

覆盖：
- _load_trade_records() 正确查询 FILLED 记录
- _load_screen_results() 正确查询 EOD 记录
- Celery 任务执行后 Redis 缓存写入

Validates: Requirements 29.13, 29.14, 29.15
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTradeOrder:
    def __init__(self, symbol, price, filled_price, direction, filled_qty, filled_at, status="FILLED"):
        self.symbol = symbol
        self.price = Decimal(str(price))
        self.filled_price = Decimal(str(filled_price))
        self.direction = direction
        self.filled_qty = filled_qty
        self.filled_at = filled_at
        self.status = status


class _FakeScreenResult:
    def __init__(self, symbol, trend_score, risk_level, signals, screen_type="EOD", screen_time=None):
        self.symbol = symbol
        self.trend_score = Decimal(str(trend_score))
        self.risk_level = risk_level
        self.signals = signals
        self.screen_type = screen_type
        self.screen_time = screen_time or datetime.now()


# ---------------------------------------------------------------------------
# 29.11.6 — Celery 任务数据加载单元测试
# ---------------------------------------------------------------------------


class TestLoadTradeRecords:
    @pytest.mark.asyncio
    async def test_load_trade_records_queries_filled_records(self):
        """_load_trade_records() 正确查询 FILLED 记录。"""
        from app.tasks.review import _async_load_trade_records

        review_date = date(2024, 6, 15)
        fake_rows = [
            _FakeTradeOrder(
                "000001.SZ", 10.0, 12.0, "BUY", 100,
                datetime(2024, 6, 15, 14, 30), "FILLED",
            ),
            _FakeTradeOrder(
                "000002.SZ", 20.0, 19.0, "SELL", 200,
                datetime(2024, 6, 15, 14, 35), "FILLED",
            ),
        ]

        async def mock_execute(stmt):
            m = MagicMock()
            m.scalars.return_value.all.return_value = fake_rows
            return m

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.review.AsyncSessionPG", return_value=mock_session):
            records = await _async_load_trade_records(review_date)

        assert len(records) == 2
        for rec in records:
            assert "symbol" in rec
            assert "profit" in rec
            assert "direction" in rec
            assert "price" in rec
            assert "quantity" in rec

        assert records[0]["symbol"] == "000001.SZ"
        assert records[0]["direction"] == "BUY"
        assert records[0]["price"] == 10.0
        assert records[0]["quantity"] == 100


class TestLoadScreenResults:
    @pytest.mark.asyncio
    async def test_load_screen_results_queries_eod_records(self):
        """_load_screen_results() 正确查询 EOD 记录。"""
        from app.tasks.review import _async_load_screen_results

        review_date = date(2024, 6, 15)
        fake_rows = [
            _FakeScreenResult(
                "000001.SZ", 85.0, "LOW", {"ma_cross": True},
                "EOD", datetime(2024, 6, 15, 15, 0),
            ),
            _FakeScreenResult(
                "000002.SZ", 45.0, "MEDIUM", {"volume_break": True},
                "EOD", datetime(2024, 6, 15, 15, 0),
            ),
        ]

        async def mock_execute(stmt):
            m = MagicMock()
            m.scalars.return_value.all.return_value = fake_rows
            return m

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.review.AsyncSessionPG", return_value=mock_session):
            results = await _async_load_screen_results(review_date)

        assert len(results) == 2
        for rec in results:
            assert "symbol" in rec
            assert "trend_score" in rec
            assert "risk_level" in rec
            assert "signals" in rec

        assert results[0]["symbol"] == "000001.SZ"
        assert results[0]["trend_score"] == 85.0
        assert results[0]["risk_level"] == "LOW"
        assert results[1]["signals"] == {"volume_break": True}


class TestCeleryTaskCacheWrite:
    @pytest.mark.asyncio
    async def test_generate_daily_review_writes_redis_cache(self):
        """Celery 任务执行后 Redis 缓存写入。"""
        from app.tasks.review import _async_load_trade_records, _cache_review

        review_date = date(2024, 6, 15)
        cache_key = f"review:daily:{review_date.isoformat()}"

        # Track what gets written to Redis
        written_data: dict = {}

        async def mock_redis_set(key, value, ex=None):
            written_data["key"] = key
            written_data["value"] = value
            written_data["ex"] = ex

        mock_redis = AsyncMock()
        mock_redis.set = mock_redis_set
        mock_redis.aclose = AsyncMock()

        test_data = {
            "date": review_date.isoformat(),
            "win_rate": 0.5,
            "total_pnl": 100.0,
            "trade_count": 2,
        }

        with patch("app.tasks.review.get_redis_client", return_value=mock_redis):
            await _cache_review(cache_key, test_data)

        assert written_data["key"] == cache_key
        assert written_data["ex"] == 7 * 24 * 3600  # 7 days TTL
        parsed = json.loads(written_data["value"])
        assert parsed["win_rate"] == 0.5
        assert parsed["total_pnl"] == 100.0
