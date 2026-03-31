"""
复盘 API 集成测试

- 29.12.1: 每日复盘 round-trip 集成测试
- 29.12.2: 策略绩效报表全链路集成测试
- 29.12.3: 报表导出全链路集成测试
- 29.12.4: 多策略对比全链路集成测试

Validates: Requirements 29.1–29.17
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_pg_session
from app.core.redis_client import get_redis
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRATEGY_UUID = "00000000-0000-0000-0000-000000000001"
_STRATEGY_UUID_2 = "00000000-0000-0000-0000-000000000002"


def _mock_redis():
    """In-memory Redis mock with TTL tracking."""
    store: dict[str, str] = {}
    ttls: dict[str, int] = {}

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ex=None):
        store[key] = value
        if ex is not None:
            ttls[key] = ex

    async def mock_ttl(key):
        return ttls.get(key, -1)

    redis = AsyncMock()
    redis.get = mock_get
    redis.set = mock_set
    redis.ttl = mock_ttl
    redis._store = store
    redis._ttls = ttls
    return redis


class _FakeTradeOrder:
    def __init__(self, symbol, price, filled_price, direction, filled_qty, filled_at, status="FILLED"):
        self.symbol = symbol
        self.price = Decimal(str(price))
        self.filled_price = Decimal(str(filled_price))
        self.direction = direction
        self.filled_qty = filled_qty
        self.filled_at = filled_at
        self.status = status
        self.id = "fake-id"


class _FakeStrategy:
    def __init__(self, name, sid=_STRATEGY_UUID):
        self.id = sid
        self.name = name


class _FakeScreenResult:
    def __init__(self, symbol, trend_score, risk_level, signals, screen_type="EOD",
                 screen_time=None, strategy_id=None):
        self.symbol = symbol
        self.trend_score = Decimal(str(trend_score))
        self.risk_level = risk_level
        self.signals = signals
        self.screen_type = screen_type
        self.screen_time = screen_time or datetime.now()
        self.strategy_id = strategy_id



# ---------------------------------------------------------------------------
# 29.12.1 — 每日复盘 round-trip 集成测试
# ---------------------------------------------------------------------------


class TestDailyReviewRoundTrip:
    @pytest.mark.asyncio
    async def test_write_trades_call_daily_verify_cache(self):
        """写入 trade_order 测试数据 → 调用 GET /review/daily → 验证 win_rate 和 trade_count → 二次调用验证缓存命中。"""
        # 3 trades: 2 winning, 1 losing
        fake_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000002.SZ", 20.0, 21.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000003.SZ", 15.0, 14.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
        ]

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                m.scalars.return_value.all.return_value = fake_rows
            else:
                m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        redis = _mock_redis()

        async def pg_dep():
            yield pg_session

        async def redis_dep():
            yield redis

        app.dependency_overrides[get_pg_session] = pg_dep
        app.dependency_overrides[get_redis] = redis_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # Step 1: First call — computes from DB
                resp1 = await client.get(
                    "/api/v1/review/daily", params={"date": "2024-06-15"}
                )
                assert resp1.status_code == 200
                data1 = resp1.json()

                # Verify correctness
                assert data1["trade_count"] == 3
                assert data1["win_rate"] == pytest.approx(2 / 3, abs=1e-6)
                # profits: (12-10)*100=200, (21-20)*100=100, (14-15)*100=-100
                assert data1["total_pnl"] == pytest.approx(200.0, abs=0.01)

                # Step 2: Verify cache was written
                cache_key = "review:daily:2024-06-15"
                cached = await redis.get(cache_key)
                assert cached is not None

                # Step 3: Second call — should return cached data (identical)
                resp2 = await client.get(
                    "/api/v1/review/daily", params={"date": "2024-06-15"}
                )
                assert resp2.status_code == 200
                data2 = resp2.json()
                assert data1 == data2
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 29.12.2 — 策略绩效报表全链路集成测试
# ---------------------------------------------------------------------------


class TestStrategyReportFullChain:
    @pytest.mark.asyncio
    async def test_create_strategy_write_trades_verify_risk_metrics(self):
        """创建策略 → 写入关联交易记录 → 调用 GET /review/strategy-report → 验证 risk_metrics。"""
        fake_strategy = _FakeStrategy("IntegrationStrategy", _STRATEGY_UUID)
        fake_trade_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 13.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 8.0, "BUY", 100, datetime(2024, 6, 16, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 11.0, "BUY", 100, datetime(2024, 6, 17, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 18, 14, 30)),
        ]

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                m.scalar_one_or_none.return_value = fake_strategy
            elif pg_call_idx == 2:
                m.scalars.return_value.all.return_value = ["000001.SZ"]
            elif pg_call_idx == 3:
                m.scalars.return_value.all.return_value = fake_trade_rows
            else:
                m.scalars.return_value.all.return_value = []
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/review/strategy-report",
                    params={"strategy_id": _STRATEGY_UUID, "period": "daily"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        assert data["strategy_id"] == _STRATEGY_UUID
        assert data["strategy_name"] == "IntegrationStrategy"
        assert data["period"] == "daily"

        # 4 trades: profits = [300, -200, 100, 200], win_rate = 3/4
        rm = data["risk_metrics"]
        assert rm["win_rate"] == pytest.approx(3 / 4, abs=1e-6)
        assert rm["max_drawdown"] >= 0
        assert "sharpe_ratio" in rm


# ---------------------------------------------------------------------------
# 29.12.3 — 报表导出全链路集成测试
# ---------------------------------------------------------------------------


class TestExportFullChain:
    @pytest.mark.asyncio
    async def test_write_trades_export_csv_then_json(self):
        """写入交易记录 → 调用 GET /review/export?format=csv → 验证 CSV 内容可解析 → 调用 format=json → 验证 JSON 可解析。"""
        fake_trade_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000002.SZ", 20.0, 19.0, "BUY", 200, datetime(2024, 6, 15, 14, 35)),
        ]

        async def mock_pg_execute(stmt):
            m = MagicMock()
            m.scalars.return_value.all.return_value = fake_trade_rows
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                # Step 1: CSV export
                resp_csv = await client.get(
                    "/api/v1/review/export",
                    params={"format": "csv", "period": "daily"},
                )
                assert resp_csv.status_code == 200
                assert "text/csv" in resp_csv.headers.get("content-type", "")
                assert "attachment" in resp_csv.headers.get("content-disposition", "")

                # Verify CSV is parseable (strip BOM)
                csv_content = resp_csv.content
                assert csv_content[:3] == b"\xef\xbb\xbf"
                csv_text = csv_content[3:].decode("utf-8")
                reader = csv.reader(io.StringIO(csv_text))
                rows = list(reader)
                assert len(rows) >= 1  # at least header row

                # Step 2: JSON export
                resp_json = await client.get(
                    "/api/v1/review/export",
                    params={"format": "json", "period": "daily"},
                )
                assert resp_json.status_code == 200
                assert "application/json" in resp_json.headers.get("content-type", "")
                assert "attachment" in resp_json.headers.get("content-disposition", "")

                # Verify JSON is parseable
                parsed = json.loads(resp_json.text)
                assert isinstance(parsed, dict)
                assert "total_return" in parsed
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 29.12.4 — 多策略对比全链路集成测试
# ---------------------------------------------------------------------------


class TestMultiStrategyCompareFullChain:
    @pytest.mark.asyncio
    async def test_create_2_strategies_compare_best(self):
        """创建 2 个策略 → 写入各自交易记录 → 调用 POST /review/compare → 验证 best_strategy 正确。"""
        fake_strategy_1 = _FakeStrategy("WinnerStrategy", _STRATEGY_UUID)
        fake_strategy_2 = _FakeStrategy("LoserStrategy", _STRATEGY_UUID_2)

        # Strategy 1: high return trades
        fake_trades_1 = [
            _FakeTradeOrder("000001.SZ", 10.0, 15.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 13.0, "BUY", 100, datetime(2024, 6, 16, 14, 30)),
        ]
        # Strategy 2: low return trades
        fake_trades_2 = [
            _FakeTradeOrder("000002.SZ", 10.0, 10.5, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000002.SZ", 10.0, 9.0, "BUY", 100, datetime(2024, 6, 16, 14, 30)),
        ]

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            # Strategy 1: calls 1 (lookup), 2 (symbols), 3 (trades)
            # Strategy 2: calls 4 (lookup), 5 (symbols), 6 (trades)
            if pg_call_idx == 1:
                m.scalar_one_or_none.return_value = fake_strategy_1
            elif pg_call_idx == 2:
                m.scalars.return_value.all.return_value = ["000001.SZ"]
            elif pg_call_idx == 3:
                m.scalars.return_value.all.return_value = fake_trades_1
            elif pg_call_idx == 4:
                m.scalar_one_or_none.return_value = fake_strategy_2
            elif pg_call_idx == 5:
                m.scalars.return_value.all.return_value = ["000002.SZ"]
            elif pg_call_idx == 6:
                m.scalars.return_value.all.return_value = fake_trades_2
            else:
                m.scalars.return_value.all.return_value = []
                m.scalar_one_or_none.return_value = None
            return m

        pg_session = AsyncMock()
        pg_session.execute = mock_pg_execute

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/review/compare",
                    json={
                        "strategy_ids": [_STRATEGY_UUID, _STRATEGY_UUID_2],
                        "period": "daily",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        assert len(data["strategies"]) == 2
        # Strategy 1: (15-10)*100 + (13-10)*100 = 500+300 = 800
        # Strategy 2: (10.5-10)*100 + (9-10)*100 = 50-100 = -50
        assert data["best_strategy"] == "WinnerStrategy"

        # Verify both strategies are present
        names = [s["name"] for s in data["strategies"]]
        assert "WinnerStrategy" in names
        assert "LoserStrategy" in names
