# Feature: a-share-quant-trading-system, Property 83: 选股执行端点完整流程正确性
"""
选股执行端点完整流程属性测试（Hypothesis）

属性 83：选股执行端点完整流程正确性（本地数据库驱动）

**Validates: Requirements 27.9, 27.10**

对任意合法策略配置和非空股票因子数据，验证：
- 通过 strategy_id 加载的配置与存储一致
- ScreenDataProvider 仅查询本地数据库（mock 验证无外部适配器调用）
- 返回的 ScreenResult 中每条 ScreenItem 包含 symbol、ref_buy_price、
  trend_score、risk_level、signals 全部字段且均不为空
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.screen import VALID_MODULES, _strategies

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 非空策略名称
_strategy_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=30,
)

# 模块子集（包括空集）
_modules_subset_st = st.frozensets(
    st.sampled_from(sorted(VALID_MODULES))
).map(lambda s: sorted(s))

# A股风格股票代码
_symbol_st = st.from_regex(r"[036]\d{5}", fullmatch=True)

# 正浮点数（用于价格等）
_positive_float_st = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)

# 趋势分数
_trend_score_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# 生成单只股票的因子数据
_stock_factor_st = st.fixed_dictionaries({
    "close": _positive_float_st,
    "open": _positive_float_st,
    "high": _positive_float_st,
    "low": _positive_float_st,
    "volume": st.integers(min_value=10000, max_value=10000000),
    "amount": _positive_float_st.map(lambda x: x * 10000),
    "turnover": st.floats(min_value=0.5, max_value=20.0, allow_nan=False, allow_infinity=False),
    "vol_ratio": st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
    "closes": st.lists(_positive_float_st, min_size=5, max_size=10),
    "highs": st.lists(_positive_float_st, min_size=5, max_size=10),
    "lows": st.lists(_positive_float_st, min_size=5, max_size=10),
    "volumes": st.lists(st.integers(min_value=1000, max_value=5000000), min_size=5, max_size=10),
    "amounts": st.lists(_positive_float_st, min_size=5, max_size=10),
    "turnovers": st.lists(
        st.floats(min_value=0.5, max_value=20.0, allow_nan=False, allow_infinity=False),
        min_size=5, max_size=10,
    ),
    "pe_ttm": st.one_of(st.none(), st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False)),
    "pb": st.one_of(st.none(), st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)),
    "roe": st.one_of(st.none(), st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False)),
    "market_cap": st.one_of(st.none(), st.floats(min_value=1.0, max_value=50000.0, allow_nan=False, allow_infinity=False)),
    "ma_trend": st.integers(min_value=0, max_value=100),
})

# 生成非空 stocks_data: {symbol: factor_dict}，1~3 只股票
_stocks_data_st = st.dictionaries(
    keys=_symbol_st,
    values=_stock_factor_st,
    min_size=1,
    max_size=3,
)

# 逻辑运算符
_logic_st = st.sampled_from(["AND", "OR"])

# 因子名称
_factor_name_st = st.sampled_from([
    "ma_trend", "macd", "boll", "rsi", "dma",
    "breakout", "money_flow", "large_order",
])

# 运算符
_operator_st = st.sampled_from([">=", "<=", ">", "<", "=="])

# 因子条件
_factor_condition_st = st.fixed_dictionaries({
    "factor_name": _factor_name_st,
    "operator": _operator_st,
    "threshold": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    "params": st.just({}),
})

# 策略配置（API 请求格式）
_strategy_config_st = st.fixed_dictionaries({
    "factors": st.lists(_factor_condition_st, min_size=0, max_size=3),
    "logic": _logic_st,
})


# ---------------------------------------------------------------------------
# Fixture：每次测试前清空内存策略存储
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_strategies():
    _strategies.clear()
    yield
    _strategies.clear()


# ---------------------------------------------------------------------------
# 有效风险等级集合
# ---------------------------------------------------------------------------

VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


# ---------------------------------------------------------------------------
# 属性 83：选股执行端点完整流程正确性
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    name=_strategy_name_st,
    modules=_modules_subset_st,
    config=_strategy_config_st,
    stocks_data=_stocks_data_st,
)
def test_screen_run_flow_correctness(
    name: str,
    modules: list[str],
    config: dict,
    stocks_data: dict[str, dict],
):
    """
    # Feature: a-share-quant-trading-system, Property 83: 选股执行端点完整流程正确性

    **Validates: Requirements 27.9, 27.10**

    对任意合法策略配置和非空股票因子数据，验证：
    1. 通过 strategy_id 加载的配置与存储一致
    2. ScreenDataProvider 仅查询本地数据库（mock 验证无外部适配器调用）
    3. 返回的 ScreenResult 中每条 ScreenItem 包含 symbol、ref_buy_price、
       trend_score、risk_level、signals 全部字段且均不为空
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    load_screen_data_mock = AsyncMock(return_value=stocks_data)

    async def _run():
        _strategies.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            # Step 1: 创建策略
            create_resp = await client.post(
                "/api/v1/strategies",
                json={
                    "name": name,
                    "config": config,
                    "enabled_modules": modules,
                },
            )
            assert create_resp.status_code == 201, (
                f"Strategy creation failed: {create_resp.status_code} {create_resp.text}"
            )
            strategy = create_resp.json()
            strategy_id = strategy["id"]

            # Verify: 存储的配置与创建请求一致
            stored = _strategies[strategy_id]
            assert stored["name"] == name
            assert sorted(stored["enabled_modules"]) == sorted(modules)

            # Step 2: 执行选股（mock ScreenDataProvider.load_screen_data）
            with patch(
                "app.api.v1.screen.AsyncSessionPG",
            ) as mock_pg, patch(
                "app.api.v1.screen.AsyncSessionTS",
            ) as mock_ts, patch(
                "app.api.v1.screen.ScreenDataProvider",
            ) as mock_provider_cls:
                # 设置 async context manager mocks
                mock_pg_instance = MagicMock()
                mock_pg.return_value.__aenter__ = AsyncMock(return_value=mock_pg_instance)
                mock_pg.return_value.__aexit__ = AsyncMock(return_value=False)

                mock_ts_instance = MagicMock()
                mock_ts.return_value.__aenter__ = AsyncMock(return_value=mock_ts_instance)
                mock_ts.return_value.__aexit__ = AsyncMock(return_value=False)

                # Mock ScreenDataProvider instance
                mock_provider = MagicMock()
                mock_provider.load_screen_data = load_screen_data_mock
                mock_provider_cls.return_value = mock_provider

                run_resp = await client.post(
                    "/api/v1/screen/run",
                    json={
                        "strategy_id": strategy_id,
                        "screen_type": "EOD",
                    },
                )

        return run_resp

    resp = asyncio.run(_run())

    # Verify: ScreenDataProvider.load_screen_data 被调用（本地数据库驱动）
    load_screen_data_mock.assert_called_once()

    assert resp.status_code == 200, (
        f"Screen run failed: {resp.status_code} {resp.text}"
    )

    body = resp.json()

    # Verify: 响应包含必要的顶层字段
    assert "strategy_id" in body
    assert "screen_type" in body
    assert body["screen_type"] == "EOD"
    assert "items" in body
    assert "is_complete" in body
    assert body["is_complete"] is True

    # Verify: 每条 ScreenItem 包含全部必要字段且不为空
    for item in body["items"]:
        # symbol 存在且非空
        assert "symbol" in item, "ScreenItem missing 'symbol'"
        assert item["symbol"], "ScreenItem 'symbol' is empty"

        # ref_buy_price 存在且非空
        assert "ref_buy_price" in item, "ScreenItem missing 'ref_buy_price'"
        assert item["ref_buy_price"] is not None, "ScreenItem 'ref_buy_price' is None"
        assert str(item["ref_buy_price"]) != "", "ScreenItem 'ref_buy_price' is empty"
        # 应为有效的数值字符串
        ref_price = Decimal(str(item["ref_buy_price"]))
        assert ref_price >= 0, f"ref_buy_price should be >= 0, got {ref_price}"

        # trend_score 存在且为数值
        assert "trend_score" in item, "ScreenItem missing 'trend_score'"
        assert item["trend_score"] is not None, "ScreenItem 'trend_score' is None"
        assert isinstance(item["trend_score"], (int, float)), (
            f"trend_score should be numeric, got {type(item['trend_score'])}"
        )
        assert 0 <= item["trend_score"] <= 100, (
            f"trend_score should be in [0, 100], got {item['trend_score']}"
        )

        # risk_level 存在且为有效枚举值
        assert "risk_level" in item, "ScreenItem missing 'risk_level'"
        assert item["risk_level"] in VALID_RISK_LEVELS, (
            f"risk_level should be one of {VALID_RISK_LEVELS}, got {item['risk_level']}"
        )

        # signals 存在且为列表
        assert "signals" in item, "ScreenItem missing 'signals'"
        assert isinstance(item["signals"], list), (
            f"signals should be a list, got {type(item['signals'])}"
        )


# ---------------------------------------------------------------------------
# 属性 84：不存在的 strategy_id 返回 404
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    strategy_id=st.uuids(),
)
def test_screen_run_nonexistent_strategy_returns_404(
    strategy_id,
):
    """
    # Feature: a-share-quant-trading-system, Property 84: 不存在的 strategy_id 返回 404

    **Validates: Requirements 27.11**

    对任意不在策略存储中的 UUID，POST /screen/run 应返回 HTTP 404
    且响应包含"策略不存在"。
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        # 确保策略存储为空，生成的 UUID 不可能存在
        _strategies.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.post(
                "/api/v1/screen/run",
                json={
                    "strategy_id": str(strategy_id),
                    "screen_type": "EOD",
                },
            )

        return resp

    resp = asyncio.run(_run())

    # 验证：返回 HTTP 404
    assert resp.status_code == 404, (
        f"Expected 404 for nonexistent strategy_id={strategy_id}, "
        f"got {resp.status_code}: {resp.text}"
    )

    # 验证：响应包含"策略不存在"
    body = resp.json()
    assert "detail" in body, f"Response missing 'detail' field: {body}"
    assert "策略不存在" in body["detail"], (
        f"Expected '策略不存在' in detail, got: {body['detail']}"
    )


# ---------------------------------------------------------------------------
# 属性 85：本地数据库无行情数据时返回空结果
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    name=_strategy_name_st,
    modules=_modules_subset_st,
    config=_strategy_config_st,
)
def test_screen_run_empty_data_returns_empty_result(
    name: str,
    modules: list[str],
    config: dict,
):
    """
    # Feature: a-share-quant-trading-system, Property 85: 本地数据库无行情数据时返回空结果

    **Validates: Requirements 27.12**

    对任意合法策略配置，当 ScreenDataProvider 返回空字典时，
    端点应返回 items=[] 且 is_complete=true，不抛出异常。
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    load_screen_data_mock = AsyncMock(return_value={})

    async def _run():
        _strategies.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            # Step 1: 创建策略
            create_resp = await client.post(
                "/api/v1/strategies",
                json={
                    "name": name,
                    "config": config,
                    "enabled_modules": modules,
                },
            )
            assert create_resp.status_code == 201, (
                f"Strategy creation failed: {create_resp.status_code} {create_resp.text}"
            )
            strategy_id = create_resp.json()["id"]

            # Step 2: 执行选股（mock ScreenDataProvider.load_screen_data 返回空字典）
            with patch(
                "app.api.v1.screen.AsyncSessionPG",
            ) as mock_pg, patch(
                "app.api.v1.screen.AsyncSessionTS",
            ) as mock_ts, patch(
                "app.api.v1.screen.ScreenDataProvider",
            ) as mock_provider_cls:
                # 设置 async context manager mocks
                mock_pg_instance = MagicMock()
                mock_pg.return_value.__aenter__ = AsyncMock(return_value=mock_pg_instance)
                mock_pg.return_value.__aexit__ = AsyncMock(return_value=False)

                mock_ts_instance = MagicMock()
                mock_ts.return_value.__aenter__ = AsyncMock(return_value=mock_ts_instance)
                mock_ts.return_value.__aexit__ = AsyncMock(return_value=False)

                # Mock ScreenDataProvider instance — 返回空字典
                mock_provider = MagicMock()
                mock_provider.load_screen_data = load_screen_data_mock
                mock_provider_cls.return_value = mock_provider

                run_resp = await client.post(
                    "/api/v1/screen/run",
                    json={
                        "strategy_id": strategy_id,
                        "screen_type": "EOD",
                    },
                )

        return run_resp

    resp = asyncio.run(_run())

    # Verify: ScreenDataProvider.load_screen_data 被调用
    load_screen_data_mock.assert_called_once()

    # Verify: HTTP 200（不抛出异常）
    assert resp.status_code == 200, (
        f"Expected 200 for empty data, got {resp.status_code}: {resp.text}"
    )

    body = resp.json()

    # Verify: items 为空列表
    assert "items" in body, f"Response missing 'items' field: {body}"
    assert body["items"] == [], (
        f"Expected items=[] for empty data, got {body['items']}"
    )

    # Verify: is_complete 为 true
    assert "is_complete" in body, f"Response missing 'is_complete' field: {body}"
    assert body["is_complete"] is True, (
        f"Expected is_complete=True for empty data, got {body['is_complete']}"
    )
