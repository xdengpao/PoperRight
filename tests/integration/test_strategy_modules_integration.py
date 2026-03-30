"""
策略模块全链路集成测试

- 25.8.1: 新建策略（2 模块）→ 选中 → 验证 2 面板 → 添加模块 → 验证 3 面板
- 25.8.2: 新建空策略（0 模块）→ 执行选股 → 验证返回空结果
- 25.8.3: 新建策略（factor_editor + ma_trend）→ 执行选股 → 验证仅应用对应筛选逻辑

Validates: Requirements 27.1, 27.3, 27.5, 27.6, 27.7, 27.8
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.screen import _strategies
from app.core.schemas import FactorCondition, ScreenType, SignalCategory, StrategyConfig
from app.main import app
from app.services.screener.screen_executor import ScreenExecutor


@pytest.fixture(autouse=True)
def _clear_strategies():
    """Reset in-memory store before each test."""
    _strategies.clear()
    yield
    _strategies.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


# ---------------------------------------------------------------------------
# 25.8.1 — 新建策略（2 模块）→ 选中 → 验证 2 面板 → 管理模块添加 1 个 → 验证 3 面板
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_select_add_module_full_chain(client: AsyncClient):
    """Full chain: create with 2 modules → GET verify 2 → PUT add 1 → GET verify 3."""

    # Step 1: POST create strategy with 2 enabled modules
    create_payload = {
        "name": "dual-module-strategy",
        "config": {"factors": [], "logic": "AND"},
        "enabled_modules": ["ma_trend", "breakout"],
    }
    resp = await client.post("/api/v1/strategies", json=create_payload)
    assert resp.status_code == 201
    created = resp.json()
    strategy_id = created["id"]
    assert created["enabled_modules"] == ["ma_trend", "breakout"]

    # Step 2: GET the strategy by id — simulate "selecting" it
    resp = await client.get(f"/api/v1/strategies/{strategy_id}")
    assert resp.status_code == 200
    selected = resp.json()
    assert len(selected["enabled_modules"]) == 2

    # Step 3: Panel visibility check — only ma_trend and breakout panels visible
    visible_panels = set(selected["enabled_modules"])
    assert visible_panels == {"ma_trend", "breakout"}
    assert "indicator_params" not in visible_panels
    assert "factor_editor" not in visible_panels
    assert "volume_price" not in visible_panels

    # Step 4: PUT — "manage modules" adds indicator_params
    resp = await client.put(
        f"/api/v1/strategies/{strategy_id}",
        json={"enabled_modules": ["ma_trend", "breakout", "indicator_params"]},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert len(updated["enabled_modules"]) == 3

    # Step 5: GET again — verify 3 modules
    resp = await client.get(f"/api/v1/strategies/{strategy_id}")
    assert resp.status_code == 200
    final = resp.json()
    assert len(final["enabled_modules"]) == 3
    assert final["enabled_modules"] == ["ma_trend", "breakout", "indicator_params"]


# ---------------------------------------------------------------------------
# 25.8.2 — 新建空策略（0 模块）→ 执行选股 → 验证返回空结果
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_modules_strategy_returns_empty_screen_result(client: AsyncClient):
    """Strategy with enabled_modules=[] should produce empty screen results."""

    # Create strategy with zero modules via API
    resp = await client.post(
        "/api/v1/strategies",
        json={
            "name": "empty-strategy",
            "config": {"factors": [], "logic": "AND"},
            "enabled_modules": [],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["enabled_modules"] == []

    # Verify via ScreenExecutor directly (no stock data dependency)
    config = StrategyConfig()
    executor = ScreenExecutor(config, enabled_modules=[])
    result = executor.run_eod_screen(
        {"000001": {"close": 10.0, "ma_trend": 85}}
    )
    assert result.items == []
    assert result.screen_type == ScreenType.EOD
    assert result.is_complete is True


# ---------------------------------------------------------------------------
# 25.8.3 — factor_editor + ma_trend → 执行选股 → 仅应用因子和均线筛选逻辑
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_factor_editor_and_ma_trend_only_signals():
    """With enabled_modules=[factor_editor, ma_trend], signals should only
    contain ma_trend-category signals — no breakout, indicator_params,
    or volume_price signals."""

    config = StrategyConfig(
        factors=[
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
            FactorCondition(factor_name="breakout", operator=">=", threshold=1.0),
            FactorCondition(factor_name="macd", operator=">=", threshold=1.0),
            FactorCondition(factor_name="money_flow", operator=">=", threshold=500.0),
        ],
        logic="OR",
        weights={
            "ma_trend": 1.0,
            "breakout": 1.0,
            "macd": 1.0,
            "money_flow": 1.0,
        },
    )

    executor = ScreenExecutor(
        config,
        enabled_modules=["factor_editor", "ma_trend"],
    )

    # Stock data where all factors pass
    stocks_data = {
        "000001": {
            "close": 15.0,
            "ma_trend": 90.0,
            "breakout": 2.0,
            "macd": 1.5,
            "money_flow": 1500.0,
        },
    }

    result = executor.run_eod_screen(stocks_data)
    assert len(result.items) == 1

    item = result.items[0]
    assert item.symbol == "000001"

    # Only ma_trend category signals should be present
    signal_categories = {s.category for s in item.signals}
    assert SignalCategory.MA_TREND in signal_categories

    # breakout, indicator_params (MACD), volume_price (money_flow) must be absent
    assert SignalCategory.BREAKOUT not in signal_categories
    assert SignalCategory.MACD not in signal_categories
    assert SignalCategory.CAPITAL_INFLOW not in signal_categories
    assert SignalCategory.LARGE_ORDER not in signal_categories
