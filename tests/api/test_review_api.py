"""
复盘 API 单元测试

覆盖：
- GET  /review/daily — 每日复盘报告
- GET  /review/strategy-report — 策略绩效报表
- GET  /review/market — 市场复盘分析
- GET  /review/export — 报表导出
- POST /review/compare — 多策略对比

Validates: Requirements 29.1–29.17
"""

from __future__ import annotations

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


def _mock_redis(stored_data: dict | None = None):
    store: dict[str, str] = {}
    if stored_data:
        for k, v in stored_data.items():
            store[k] = json.dumps(v) if isinstance(v, dict) else v

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ex=None):
        store[key] = value

    redis = AsyncMock()
    redis.get = mock_get
    redis.set = mock_set
    redis._store = store
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
    def __init__(self, symbol, trend_score, risk_level, signals, screen_type="EOD", screen_time=None):
        self.symbol = symbol
        self.trend_score = Decimal(str(trend_score))
        self.risk_level = risk_level
        self.signals = signals
        self.screen_type = screen_type
        self.screen_time = screen_time or datetime.now()
        self.strategy_id = None



# ---------------------------------------------------------------------------
# 29.11.1 — GET /review/daily 单元测试
# ---------------------------------------------------------------------------


class TestDailyReview:
    @pytest.mark.asyncio
    async def test_has_trade_records_correct_win_rate_and_pnl(self):
        """有交易记录时返回正确 win_rate 和 total_pnl。"""
        # 3 trades: 2 winning (+100, +50), 1 losing (-30) → win_rate=2/3, total_pnl=120
        fake_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 11.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000002.SZ", 20.0, 20.5, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000003.SZ", 15.0, 14.7, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
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
                resp = await client.get("/api/v1/review/daily", params={"date": "2024-06-15"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["trade_count"] == 3
        # (11-10)*100=100, (20.5-20)*100=50, (14.7-15)*100=-30
        assert data["total_pnl"] == pytest.approx(120.0, abs=0.01)
        assert data["win_rate"] == pytest.approx(2 / 3, abs=1e-6)
        assert len(data["success_cases"]) == 2

    @pytest.mark.asyncio
    async def test_no_trade_records_returns_zero_defaults(self):
        """无交易记录时返回全零默认值。"""
        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
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
                resp = await client.get("/api/v1/review/daily", params={"date": "2024-06-15"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["win_rate"] == 0.0
        assert data["total_pnl"] == 0.0
        assert data["trade_count"] == 0
        assert data["success_cases"] == []
        assert data["failure_cases"] == []

    @pytest.mark.asyncio
    async def test_redis_cache_hit_returns_cached_data(self):
        """Redis 缓存命中时直接返回缓存数据。"""
        cached = {
            "date": "2024-06-15",
            "win_rate": 0.75,
            "total_pnl": 500.0,
            "trade_count": 4,
            "success_cases": [{"symbol": "000001.SZ", "pnl": 200.0, "reason": "BUY"}],
            "failure_cases": [],
        }
        redis = _mock_redis({"review:daily:2024-06-15": cached})

        # PG session should NOT be called if cache hits
        pg_session = AsyncMock()
        pg_session.execute = AsyncMock(side_effect=AssertionError("PG should not be called on cache hit"))

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
                resp = await client.get("/api/v1/review/daily", params={"date": "2024-06-15"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["win_rate"] == 0.75
        assert data["total_pnl"] == 500.0
        assert data["trade_count"] == 4


# ---------------------------------------------------------------------------
# 29.11.2 — GET /review/strategy-report 单元测试
# ---------------------------------------------------------------------------


class TestStrategyReport:
    @pytest.mark.asyncio
    async def test_no_strategy_id_returns_400(self):
        """未传 strategy_id 返回 HTTP 400。"""
        pg_session = AsyncMock()

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/review/strategy-report")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_has_trade_records_correct_risk_metrics(self):
        """有交易记录时返回正确 risk_metrics。"""
        fake_strategy = _FakeStrategy("TestStrategy")
        fake_trade_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 9.0, "BUY", 100, datetime(2024, 6, 16, 14, 30)),
            _FakeTradeOrder("000001.SZ", 10.0, 11.0, "BUY", 100, datetime(2024, 6, 17, 14, 30)),
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
        assert "risk_metrics" in data
        # 3 trades: profits = [200, -100, 100], win_rate = 2/3
        assert data["risk_metrics"]["win_rate"] == pytest.approx(2 / 3, abs=1e-6)
        assert data["risk_metrics"]["max_drawdown"] >= 0

    @pytest.mark.asyncio
    async def test_no_trade_records_returns_zero_risk_metrics(self):
        """无交易记录时返回空 returns 和全零 risk_metrics。"""
        fake_strategy = _FakeStrategy("EmptyStrategy")

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                m.scalar_one_or_none.return_value = fake_strategy
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
        assert data["returns"] == []
        assert data["risk_metrics"]["max_drawdown"] == 0.0
        assert data["risk_metrics"]["sharpe_ratio"] == 0.0
        assert data["risk_metrics"]["win_rate"] == 0.0


# ---------------------------------------------------------------------------
# 29.11.3 — GET /review/market 单元测试
# ---------------------------------------------------------------------------


class TestMarketReview:
    @pytest.mark.asyncio
    async def test_has_market_data_correct_sector_and_trend(self):
        """有市场数据时返回正确板块轮动和趋势分布。"""
        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            if pg_call_idx == 1:
                # Board distinct query
                m.scalars.return_value.all.return_value = ["科技", "金融", "医药"]
            elif pg_call_idx == 2:
                # ScreenResult trend_score query
                m.scalars.return_value.all.return_value = [
                    Decimal("85.0"), Decimal("45.0"), Decimal("15.0"), Decimal("65.0"),
                ]
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
                resp = await client.get("/api/v1/review/market", params={"date": "2024-06-15"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert "sector_rotation" in data
        assert "trend_distribution" in data
        assert "money_flow" in data
        # 3 sectors
        assert len(data["sector_rotation"]["top_sectors"]) == 3
        # 4 scores: bins [0-20]=1, [20-40]=0, [40-60]=1, [60-80]=1, [80-100]=1
        assert sum(data["trend_distribution"]["counts"]) == 4

    @pytest.mark.asyncio
    async def test_no_market_data_returns_empty_defaults(self):
        """无市场数据时返回空默认值。"""
        async def mock_pg_execute(stmt):
            m = MagicMock()
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
                resp = await client.get("/api/v1/review/market", params={"date": "2024-06-15"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["sector_rotation"]["top_sectors"] == []
        assert data["sector_rotation"]["bottom_sectors"] == []
        assert data["trend_distribution"]["counts"] == [0, 0, 0, 0, 0]
        assert data["money_flow"]["net_inflow_total"] == 0.0


# ---------------------------------------------------------------------------
# 29.11.4 — GET /review/export 单元测试
# ---------------------------------------------------------------------------


class TestExportReport:
    @pytest.mark.asyncio
    async def test_csv_export_correct_content_type_and_bom(self):
        """CSV 导出返回正确 Content-Type 和 BOM。"""
        fake_trade_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
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
                resp = await client.get(
                    "/api/v1/review/export",
                    params={"format": "csv", "period": "daily"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")
        # UTF-8 BOM
        assert resp.content[:3] == b"\xef\xbb\xbf"

    @pytest.mark.asyncio
    async def test_json_export_correct_content_type(self):
        """JSON 导出返回正确 Content-Type。"""
        fake_trade_rows = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
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
                resp = await client.get(
                    "/api/v1/review/export",
                    params={"format": "json", "period": "daily"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")
        # Should be valid JSON
        json.loads(resp.text)


# ---------------------------------------------------------------------------
# 29.11.5 — POST /review/compare 单元测试
# ---------------------------------------------------------------------------


class TestCompareStrategies:
    @pytest.mark.asyncio
    async def test_less_than_2_strategies_returns_400(self):
        """strategy_ids 少于 2 个返回 HTTP 400。"""
        pg_session = AsyncMock()

        async def pg_dep():
            yield pg_session

        app.dependency_overrides[get_pg_session] = pg_dep
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/review/compare",
                    json={"strategy_ids": [_STRATEGY_UUID], "period": "daily"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 422  # Pydantic validation: min_length=2

    @pytest.mark.asyncio
    async def test_normal_comparison_returns_best_strategy(self):
        """正常对比返回 best_strategy。"""
        # Strategy 1: profit=200, Strategy 2: profit=50
        fake_strategy_1 = _FakeStrategy("HighReturn", _STRATEGY_UUID)
        fake_strategy_2 = _FakeStrategy("LowReturn", _STRATEGY_UUID_2)

        fake_trades_1 = [
            _FakeTradeOrder("000001.SZ", 10.0, 12.0, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
        ]
        fake_trades_2 = [
            _FakeTradeOrder("000002.SZ", 10.0, 10.5, "BUY", 100, datetime(2024, 6, 15, 14, 30)),
        ]

        pg_call_idx = 0

        async def mock_pg_execute(stmt):
            nonlocal pg_call_idx
            pg_call_idx += 1
            m = MagicMock()
            # Strategy 1: calls 1,2,3; Strategy 2: calls 4,5,6
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
        # Strategy 1 has higher return (200 vs 50)
        assert data["best_strategy"] == "HighReturn"
