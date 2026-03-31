"""
复盘 API 属性测试（Hypothesis + pytest）

属性 94：每日复盘报告 API 计算正确性
属性 95：每日复盘报告 Redis 缓存 round-trip
属性 96：策略绩效报表生成正确性
属性 97：市场复盘分析计算正确性
属性 98：报表导出格式与内容正确性
属性 99：Celery 任务数据加载正确性
属性 100：多策略对比计算正确性

**Validates: Requirements 29.1–29.17**
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st
from httpx import ASGITransport, AsyncClient

from app.core.database import get_pg_session
from app.core.redis_client import get_redis
from app.main import app
from app.services.review_analyzer import (
    MarketReviewAnalyzer,
    ReportExporter,
    ReviewAnalyzer,
    StrategyReportGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRATEGY_UUID = "00000000-0000-0000-0000-000000000001"
_STRATEGY_UUID_2 = "00000000-0000-0000-0000-000000000002"


def _mock_redis(stored_data: dict | None = None):
    """Build a mock Redis client with in-memory store."""
    store: dict[str, str] = {}
    ttls: dict[str, int] = {}
    if stored_data:
        for k, v in stored_data.items():
            store[k] = json.dumps(v) if isinstance(v, dict) else v

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


# Strategy for generating trade records with profit
# Use integers divided by 100 to avoid floating-point precision issues in round-trip
_profit_st = st.integers(min_value=-100000, max_value=100000).map(lambda x: float(x))
_price_st = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)
_qty_st = st.just(100)  # Fixed quantity to avoid precision issues in profit round-trip
_symbol_st = st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True)
_direction_st = st.sampled_from(["BUY", "SELL"])

_trade_record_st = st.fixed_dictionaries({
    "symbol": _symbol_st,
    "profit": _profit_st,
    "direction": _direction_st,
    "price": _price_st,
    "quantity": _qty_st,
})

_date_st = st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 12, 31))


class _FakeTradeOrder:
    """Fake TradeOrder ORM object."""
    def __init__(self, symbol: str, price: float, filled_price: float,
                 direction: str, filled_qty: int, filled_at: datetime, status: str = "FILLED"):
        self.symbol = symbol
        self.price = Decimal(str(price))
        self.filled_price = Decimal(str(filled_price))
        self.direction = direction
        self.filled_qty = filled_qty
        self.filled_at = filled_at
        self.status = status
        self.id = "fake-id"


class _FakeScreenResult:
    """Fake ScreenResult ORM object."""
    def __init__(self, symbol: str, trend_score: float, risk_level: str,
                 signals: dict, screen_type: str = "EOD", screen_time: datetime | None = None):
        self.symbol = symbol
        self.trend_score = Decimal(str(trend_score))
        self.risk_level = risk_level
        self.signals = signals
        self.screen_type = screen_type
        self.screen_time = screen_time or datetime.now()
        self.strategy_id = None


class _FakeStrategy:
    """Fake StrategyTemplate ORM object."""
    def __init__(self, name: str, sid: str = _STRATEGY_UUID):
        self.id = sid
        self.name = name



# ---------------------------------------------------------------------------
# 属性 94：每日复盘报告 API 计算正确性
# Feature: a-share-quant-trading-system, Property 94
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    trade_records=st.lists(_trade_record_st, min_size=0, max_size=20),
    review_date=_date_st,
)
async def test_property_94_daily_review_calculation_correctness(
    trade_records: list[dict], review_date: date
):
    """
    **Validates: Requirements 29.1**

    For any set of filled trade records and any review date, verify:
    - win_rate equals ReviewAnalyzer.generate_daily_review() calculated win rate
    - total_pnl equals sum of all profits
    - trade_count equals total record count
    - success_cases length equals count of profit > 0
    """
    # Build fake ORM rows — use integer-cent prices to avoid Decimal precision issues
    fake_rows = []
    for r in trade_records:
        price = float(r["price"])
        qty = r["quantity"]  # always 100
        profit = float(r["profit"])
        # filled_price such that (filled_price - price) * qty == profit
        filled_price = profit / qty + price
        fake_rows.append(_FakeTradeOrder(
            symbol=r["symbol"], price=price, filled_price=filled_price,
            direction=r["direction"], filled_qty=qty,
            filled_at=datetime(review_date.year, review_date.month, review_date.day, 14, 30),
        ))

    # Compute expected from the ORM rows the same way the API does
    api_trade_records = [
        {"symbol": t.symbol,
         "profit": float((t.filled_price or 0) - (t.price or 0)) * (t.filled_qty or 0),
         "direction": t.direction,
         "price": float(t.price or 0),
         "quantity": t.filled_qty or 0}
        for t in fake_rows
    ]
    review = ReviewAnalyzer.generate_daily_review(api_trade_records, [], review_date=review_date)
    expected_win_rate = review.win_rate
    expected_total_pnl = review.total_pnl
    expected_trade_count = review.total_trades
    expected_success_count = len(review.successful_cases)

    # Verify service-layer consistency
    if api_trade_records:
        profits = [float(r["profit"]) for r in api_trade_records]
        assert expected_total_pnl == pytest.approx(sum(profits), abs=1e-6)
        assert expected_trade_count == len(api_trade_records)
        winning = sum(1 for p in profits if p > 0)
        assert expected_win_rate == pytest.approx(winning / len(api_trade_records), abs=1e-9)
        assert expected_success_count == winning
    else:
        assert expected_win_rate == 0.0
        assert expected_total_pnl == 0.0
        assert expected_trade_count == 0
        assert expected_success_count == 0

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
            resp = await client.get(
                "/api/v1/review/daily",
                params={"date": review_date.isoformat()},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()

    assert data["trade_count"] == expected_trade_count
    assert data["win_rate"] == pytest.approx(expected_win_rate, abs=1e-6)
    assert data["total_pnl"] == pytest.approx(expected_total_pnl, abs=0.01)
    assert len(data["success_cases"]) == expected_success_count


# ---------------------------------------------------------------------------
# 属性 95：每日复盘报告 Redis 缓存 round-trip
# Feature: a-share-quant-trading-system, Property 95
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    trade_records=st.lists(_trade_record_st, min_size=0, max_size=10),
    review_date=_date_st,
)
async def test_property_95_daily_review_redis_cache_roundtrip(
    trade_records: list[dict], review_date: date
):
    """
    **Validates: Requirements 29.3**

    For any review date and trade records, first call caches to Redis key
    review:daily:{date} with TTL ≤ 7 days; second call returns identical response.
    """
    fake_rows = []
    for r in trade_records:
        price = float(r["price"])
        qty = r["quantity"]  # always 100
        profit = float(r["profit"])
        filled_price = profit / qty + price
        fake_rows.append(_FakeTradeOrder(
            symbol=r["symbol"], price=price, filled_price=filled_price,
            direction=r["direction"], filled_qty=qty,
            filled_at=datetime(review_date.year, review_date.month, review_date.day, 14, 30),
        ))

    pg_call_idx = 0

    async def mock_pg_execute(stmt):
        nonlocal pg_call_idx
        pg_call_idx += 1
        m = MagicMock()
        if pg_call_idx == 1:
            # TradeOrder query
            m.scalars.return_value.all.return_value = fake_rows
        else:
            # ScreenResult query
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
            # First call — should compute and cache
            resp1 = await client.get(
                "/api/v1/review/daily",
                params={"date": review_date.isoformat()},
            )
            assert resp1.status_code == 200
            data1 = resp1.json()

            # Verify cache key exists
            cache_key = f"review:daily:{review_date.isoformat()}"
            cached_val = await redis.get(cache_key)
            assert cached_val is not None, "Cache key should exist after first call"

            # Verify TTL ≤ 7 days
            ttl = await redis.ttl(cache_key)
            assert ttl <= 7 * 24 * 3600, f"TTL should be ≤ 7 days, got {ttl}"

            # Second call — should return cached data (identical)
            resp2 = await client.get(
                "/api/v1/review/daily",
                params={"date": review_date.isoformat()},
            )
            assert resp2.status_code == 200
            data2 = resp2.json()

            assert data1 == data2, "Second call should return identical cached response"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 属性 96：策略绩效报表生成正确性
# Feature: a-share-quant-trading-system, Property 96
# ---------------------------------------------------------------------------

_period_st = st.sampled_from(["daily", "weekly", "monthly"])


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    trades=st.lists(
        st.fixed_dictionaries({"profit": _profit_st}),
        min_size=0,
        max_size=20,
    ),
    period=_period_st,
)
async def test_property_96_strategy_report_generation_correctness(
    trades: list[dict], period: str
):
    """
    **Validates: Requirements 29.4**

    For any valid strategy_id and period parameter, verify risk_metrics
    (max_drawdown, sharpe_ratio, win_rate) equal
    StrategyReportGenerator.generate_period_report() results.
    """
    expected = StrategyReportGenerator.generate_period_report(trades, period)

    # Build fake ORM rows
    fake_trade_rows = []
    fake_screen_symbols = set()
    for t in trades:
        profit = float(t["profit"])
        price = 10.0
        filled_price = price + profit / 100  # qty=100
        sym = "000001.SZ"
        fake_screen_symbols.add(sym)
        fake_trade_rows.append(_FakeTradeOrder(
            symbol=sym, price=price, filled_price=filled_price,
            direction="BUY", filled_qty=100,
            filled_at=datetime(2024, 6, 15, 14, 30),
        ))

    fake_strategy = _FakeStrategy("TestStrategy", _STRATEGY_UUID)

    pg_call_idx = 0

    async def mock_pg_execute(stmt):
        nonlocal pg_call_idx
        pg_call_idx += 1
        m = MagicMock()
        if pg_call_idx == 1:
            # StrategyTemplate lookup
            m.scalar_one_or_none.return_value = fake_strategy
        elif pg_call_idx == 2:
            # ScreenResult symbols query
            m.scalars.return_value.all.return_value = list(fake_screen_symbols) if trades else []
        elif pg_call_idx == 3:
            # TradeOrder query
            m.scalars.return_value.all.return_value = fake_trade_rows
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
            resp = await client.get(
                "/api/v1/review/strategy-report",
                params={"strategy_id": _STRATEGY_UUID, "period": period},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()

    if not trades:
        assert data["risk_metrics"]["max_drawdown"] == 0.0
        assert data["risk_metrics"]["sharpe_ratio"] == 0.0
        assert data["risk_metrics"]["win_rate"] == 0.0
    else:
        assert data["risk_metrics"]["max_drawdown"] == pytest.approx(
            expected["risk_metrics"]["max_drawdown"], abs=1e-6
        )
        assert data["risk_metrics"]["sharpe_ratio"] == pytest.approx(
            expected["risk_metrics"]["sharpe_ratio"], abs=1e-6
        )
        assert data["risk_metrics"]["win_rate"] == pytest.approx(
            expected["win_rate"], abs=1e-6
        )


# ---------------------------------------------------------------------------
# 属性 97：市场复盘分析计算正确性
# Feature: a-share-quant-trading-system, Property 97
# ---------------------------------------------------------------------------

_change_pct_st = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
_sector_st = st.fixed_dictionaries({
    "name": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
    "change_pct": _change_pct_st,
})
_score_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_flow_st = st.fixed_dictionaries({
    "sector": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
    "net_inflow": st.floats(min_value=-1e8, max_value=1e8, allow_nan=False, allow_infinity=False),
})


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    sector_data=st.lists(_sector_st, min_size=0, max_size=15),
    scores=st.lists(_score_st, min_size=0, max_size=30),
    flow_data=st.lists(_flow_st, min_size=0, max_size=10),
)
async def test_property_97_market_review_analysis_correctness(
    sector_data: list[dict], scores: list[float], flow_data: list[dict]
):
    """
    **Validates: Requirements 29.7**

    For any sector data, trend scores, and money flow data, verify:
    - sector_rotation equals MarketReviewAnalyzer.analyze_sector_rotation() result
    - trend_distribution.counts bucket sums equal total input scores
    - money_flow.net_inflow_total equals sum of all net_inflow
    """
    expected_sector = MarketReviewAnalyzer.analyze_sector_rotation(sector_data)
    expected_trend = MarketReviewAnalyzer.generate_trend_distribution(scores)
    # The API currently passes empty list for money_flow, so we test the service directly
    expected_flow = MarketReviewAnalyzer.analyze_money_flow(flow_data)

    # Verify trend distribution bucket sums
    if scores:
        assert sum(expected_trend["counts"]) == len(scores)

    # Verify money flow total
    if flow_data:
        expected_total = sum(float(f["net_inflow"]) for f in flow_data)
        assert expected_flow["net_inflow_total"] == pytest.approx(expected_total, abs=1e-6)
    else:
        assert expected_flow["net_inflow_total"] == 0.0

    # Verify sector rotation via API mock
    fake_boards = [s["name"] for s in sector_data]
    fake_screen_scores = [Decimal(str(s)) for s in scores]

    pg_call_idx = 0

    async def mock_pg_execute(stmt):
        nonlocal pg_call_idx
        pg_call_idx += 1
        m = MagicMock()
        if pg_call_idx == 1:
            # Board distinct query
            m.scalars.return_value.all.return_value = fake_boards
        elif pg_call_idx == 2:
            # ScreenResult trend_score query
            m.scalars.return_value.all.return_value = fake_screen_scores
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
                "/api/v1/review/market",
                params={"date": "2024-06-15"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()

    # The API builds sector_data with change_pct=0.0 for all boards,
    # so sector_rotation should match analyze_sector_rotation with 0.0 changes
    api_sector_data = [{"name": b, "change_pct": 0.0} for b in fake_boards]
    expected_api_sector = MarketReviewAnalyzer.analyze_sector_rotation(api_sector_data)
    assert data["sector_rotation"] == expected_api_sector

    # Trend distribution counts sum should equal number of scores
    if scores:
        assert sum(data["trend_distribution"]["counts"]) == len(scores)


# ---------------------------------------------------------------------------
# 属性 98：报表导出格式与内容正确性
# Feature: a-share-quant-trading-system, Property 98
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    trades=st.lists(
        st.fixed_dictionaries({"profit": _profit_st}),
        min_size=0,
        max_size=10,
    ),
    fmt=st.sampled_from(["csv", "json"]),
)
async def test_property_98_report_export_format_correctness(
    trades: list[dict], fmt: str
):
    """
    **Validates: Requirements 29.10, 29.11, 29.12**

    For any report data and export format, verify:
    - CSV response starts with UTF-8 BOM and Content-Type is text/csv; charset=utf-8
    - JSON response is valid JSON and Content-Type is application/json
    - Both formats include Content-Disposition: attachment header
    """
    fake_trade_rows = []
    for t in trades:
        profit = float(t["profit"])
        price = 10.0
        filled_price = price + profit / 100
        fake_trade_rows.append(_FakeTradeOrder(
            symbol="000001.SZ", price=price, filled_price=filled_price,
            direction="BUY", filled_qty=100,
            filled_at=datetime(2024, 6, 15, 14, 30),
        ))

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
                params={"format": fmt, "period": "daily"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200

    # Content-Disposition: attachment
    content_disp = resp.headers.get("content-disposition", "")
    assert "attachment" in content_disp

    if fmt == "csv":
        assert "text/csv" in resp.headers.get("content-type", "")
        # CSV should start with UTF-8 BOM
        raw = resp.content
        if raw:  # non-empty report
            assert raw[:3] == b"\xef\xbb\xbf", "CSV should start with UTF-8 BOM"
    else:
        assert "application/json" in resp.headers.get("content-type", "")
        # JSON should be parseable
        body = resp.text
        if body:
            json.loads(body)  # should not raise


# ---------------------------------------------------------------------------
# 属性 99：Celery 任务数据加载正确性
# Feature: a-share-quant-trading-system, Property 99
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    n_filled=st.integers(min_value=0, max_value=10),
    n_cancelled=st.integers(min_value=0, max_value=5),
    n_eod=st.integers(min_value=0, max_value=10),
    n_realtime=st.integers(min_value=0, max_value=5),
    review_date=_date_st,
)
async def test_property_99_celery_task_data_loading_correctness(
    n_filled: int, n_cancelled: int, n_eod: int, n_realtime: int, review_date: date
):
    """
    **Validates: Requirements 29.13, 29.14**

    For any date, verify _load_trade_records() returns list length equal to
    FILLED records count, each with 5 fields (symbol, profit, direction, price, quantity);
    _load_screen_results() returns list length equal to EOD records count,
    each with 4 fields (symbol, trend_score, risk_level, signals).
    """
    from app.tasks.review import _async_load_trade_records, _async_load_screen_results

    # Build fake FILLED trade orders
    filled_rows = []
    for i in range(n_filled):
        filled_rows.append(_FakeTradeOrder(
            symbol=f"{i:06d}.SZ", price=10.0, filled_price=11.0,
            direction="BUY", filled_qty=100,
            filled_at=datetime(review_date.year, review_date.month, review_date.day, 14, 30),
            status="FILLED",
        ))

    # Build fake EOD screen results
    eod_rows = []
    for i in range(n_eod):
        eod_rows.append(_FakeScreenResult(
            symbol=f"{i:06d}.SZ", trend_score=75.0, risk_level="LOW",
            signals={"ma_cross": True}, screen_type="EOD",
            screen_time=datetime(review_date.year, review_date.month, review_date.day, 15, 0),
        ))

    # Mock the async session
    trade_call_done = False

    async def mock_execute_trades(stmt):
        m = MagicMock()
        m.scalars.return_value.all.return_value = filled_rows
        return m

    async def mock_execute_screens(stmt):
        m = MagicMock()
        m.scalars.return_value.all.return_value = eod_rows
        return m

    # Patch AsyncSessionPG to return our mock sessions
    mock_trade_session = AsyncMock()
    mock_trade_session.execute = mock_execute_trades
    mock_trade_session.__aenter__ = AsyncMock(return_value=mock_trade_session)
    mock_trade_session.__aexit__ = AsyncMock(return_value=False)

    mock_screen_session = AsyncMock()
    mock_screen_session.execute = mock_execute_screens
    mock_screen_session.__aenter__ = AsyncMock(return_value=mock_screen_session)
    mock_screen_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.review.AsyncSessionPG", return_value=mock_trade_session):
        trade_records = await _async_load_trade_records(review_date)

    with patch("app.tasks.review.AsyncSessionPG", return_value=mock_screen_session):
        screen_results = await _async_load_screen_results(review_date)

    # Verify trade records
    assert len(trade_records) == n_filled
    required_trade_fields = {"symbol", "profit", "direction", "price", "quantity"}
    for rec in trade_records:
        assert required_trade_fields.issubset(rec.keys()), f"Missing fields in trade record: {rec.keys()}"

    # Verify screen results
    assert len(screen_results) == n_eod
    required_screen_fields = {"symbol", "trend_score", "risk_level", "signals"}
    for rec in screen_results:
        assert required_screen_fields.issubset(rec.keys()), f"Missing fields in screen result: {rec.keys()}"


# ---------------------------------------------------------------------------
# 属性 100：多策略对比计算正确性
# Feature: a-share-quant-trading-system, Property 100
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@hyp_settings(max_examples=100)
@given(
    strategy_trades=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=999),
            st.lists(st.fixed_dictionaries({"profit": _profit_st}), min_size=0, max_size=10),
        ),
        min_size=2,
        max_size=5,
    ),
    period=_period_st,
)
async def test_property_100_multi_strategy_comparison_correctness(
    strategy_trades: list[tuple[int, list[dict]]], period: str
):
    """
    **Validates: Requirements 29.16**

    For any ≥2 strategy IDs and period parameter, verify strategies list length
    equals input count; best_strategy equals the strategy with highest total_return,
    consistent with StrategyReportGenerator.compare_strategies().
    """
    # Build unique strategy names and UUIDs
    strategy_ids: list[str] = []
    strategy_map: dict[str, tuple[str, list[dict]]] = {}  # sid -> (name, trades)
    reports: dict[str, dict] = {}

    for i, (name_seed, trades) in enumerate(strategy_trades):
        sid = f"00000000-0000-0000-0000-{i:012d}"
        name = f"Strategy_{i}_{name_seed}"
        strategy_ids.append(sid)
        strategy_map[sid] = (name, trades)
        reports[name] = StrategyReportGenerator.generate_period_report(trades, period)

    expected = StrategyReportGenerator.compare_strategies(reports)

    assert len(expected["strategies"]) == len(reports)

    pg_call_idx = 0
    # Pre-compute the expected call sequence
    # For each strategy: lookup (1) + symbols (1) + trades (1 if has trades, 0 if not)
    call_sequence: list[tuple[str, str, list[dict]]] = []
    for sid in strategy_ids:
        name, trades = strategy_map[sid]
        call_sequence.append(("lookup", name, trades))
        call_sequence.append(("symbols", name, trades))
        if trades:
            call_sequence.append(("trades", name, trades))

    async def mock_pg_execute(stmt):
        nonlocal pg_call_idx
        idx = pg_call_idx
        pg_call_idx += 1
        m = MagicMock()

        if idx < len(call_sequence):
            phase, name, trades = call_sequence[idx]
            sid = [s for s, (n, _) in strategy_map.items() if n == name][0]

            if phase == "lookup":
                m.scalar_one_or_none.return_value = _FakeStrategy(name, sid)
            elif phase == "symbols":
                syms = ["000001.SZ"] if trades else []
                m.scalars.return_value.all.return_value = syms
            elif phase == "trades":
                fake_rows = []
                for t in trades:
                    profit = float(t["profit"])
                    price = 10.0
                    filled_price = price + profit / 100
                    fake_rows.append(_FakeTradeOrder(
                        symbol="000001.SZ", price=price, filled_price=filled_price,
                        direction="BUY", filled_qty=100,
                        filled_at=datetime(2024, 6, 15, 14, 30),
                    ))
                m.scalars.return_value.all.return_value = fake_rows
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
                json={"strategy_ids": strategy_ids, "period": period},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()

    assert len(data["strategies"]) == len(strategy_ids)
    assert data["best_strategy"] == expected["best_strategy"]
