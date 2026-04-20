"""
多维度风控属性测试（Hypothesis）

**Validates: Requirements 8.1, 8.2, 8.3, 8.5**

Property 13: 多维度市场风险评估
Property 14: DANGER 模式允许强势股通过
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import MarketRiskLevel, RiskLevel, ScreenItem
from app.services.risk_controller import MarketRiskChecker
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 指数收盘价序列：至少 65 个数据点以确保 MA60 可计算
_index_closes_strategy = st.lists(
    st.floats(1000.0, 5000.0, allow_nan=False, allow_infinity=False),
    min_size=65,
    max_size=120,
)

# 市场广度（涨跌比）
_market_breadth_strategy = st.floats(
    0.0, 5.0, allow_nan=False, allow_infinity=False,
)

# 趋势评分列表（用于 DANGER 模式强势股测试）
_trend_scores_strategy = st.lists(
    st.floats(0.0, 100.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=20,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _compute_base_risk_level(index_closes: list[float]) -> MarketRiskLevel:
    """
    参考模型：仅使用均线逻辑计算基础风险等级。
    """
    if not index_closes:
        return MarketRiskLevel.NORMAL

    current_price = index_closes[-1]

    # MA60
    if len(index_closes) >= 60:
        ma60 = sum(index_closes[-60:]) / 60
        if current_price < ma60:
            return MarketRiskLevel.DANGER

    # MA20
    if len(index_closes) >= 20:
        ma20 = sum(index_closes[-20:]) / 20
        if current_price < ma20:
            return MarketRiskLevel.CAUTION

    return MarketRiskLevel.NORMAL


def _escalate(level: MarketRiskLevel) -> MarketRiskLevel:
    """参考模型：风险等级提升一级。"""
    if level == MarketRiskLevel.NORMAL:
        return MarketRiskLevel.CAUTION
    if level == MarketRiskLevel.CAUTION:
        return MarketRiskLevel.DANGER
    return MarketRiskLevel.DANGER


def _make_screen_item(symbol: str, trend_score: float) -> ScreenItem:
    """创建测试用 ScreenItem。"""
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal("10.00"),
        trend_score=trend_score,
        risk_level=RiskLevel.LOW if trend_score >= 80 else RiskLevel.MEDIUM,
    )


# ---------------------------------------------------------------------------
# Property 13: 多维度市场风险评估
# Feature: screening-parameter-optimization, Property 13: 多维度市场风险评估
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    index_closes=_index_closes_strategy,
    market_breadth=_market_breadth_strategy,
    breadth_threshold=st.floats(0.1, 2.0, allow_nan=False, allow_infinity=False),
)
def test_market_risk_breadth_escalation(
    index_closes: list[float],
    market_breadth: float,
    breadth_threshold: float,
):
    """
    # Feature: screening-parameter-optimization, Property 13: 多维度市场风险评估

    **Validates: Requirements 8.1, 8.2**

    当 market_breadth < breadth_threshold 时，风险等级应比基础等级提升一级。
    """
    checker = MarketRiskChecker()

    base_level = _compute_base_risk_level(index_closes)
    actual = checker.check_market_risk(
        index_closes,
        market_breadth=market_breadth,
        breadth_threshold=breadth_threshold,
    )

    if market_breadth < breadth_threshold:
        expected = _escalate(base_level)
        assert actual == expected, (
            f"广度 {market_breadth} < 阈值 {breadth_threshold} 时应提升风险等级："
            f"base={base_level.value}, expected={expected.value}, actual={actual.value}"
        )
    else:
        assert actual == base_level, (
            f"广度 {market_breadth} >= 阈值 {breadth_threshold} 时应保持基础等级："
            f"base={base_level.value}, actual={actual.value}"
        )


@settings(max_examples=200)
@given(index_closes=_index_closes_strategy)
def test_market_risk_none_breadth_uses_ma_only(index_closes: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 13: 多维度市场风险评估

    **Validates: Requirements 8.5**

    当 market_breadth 为 None 时，仅使用均线判定（降级为现有逻辑）。
    """
    checker = MarketRiskChecker()

    base_level = _compute_base_risk_level(index_closes)
    actual = checker.check_market_risk(index_closes, market_breadth=None)

    assert actual == base_level, (
        f"market_breadth=None 时应仅使用均线判定："
        f"expected={base_level.value}, actual={actual.value}"
    )


@settings(max_examples=200)
@given(
    index_closes=_index_closes_strategy,
    market_breadth=st.one_of(
        st.none(),
        st.floats(0.0, 5.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_market_risk_always_valid_level(
    index_closes: list[float],
    market_breadth: float | None,
):
    """
    # Feature: screening-parameter-optimization, Property 13: 多维度市场风险评估

    **Validates: Requirements 8.1**

    对任意输入，返回值始终是有效的 MarketRiskLevel 枚举值。
    """
    checker = MarketRiskChecker()
    result = checker.check_market_risk(
        index_closes, market_breadth=market_breadth,
    )
    assert result in (
        MarketRiskLevel.NORMAL,
        MarketRiskLevel.CAUTION,
        MarketRiskLevel.DANGER,
    ), f"返回值不是有效的 MarketRiskLevel: {result}"


# ---------------------------------------------------------------------------
# Property 14: DANGER 模式允许强势股通过
# Feature: screening-parameter-optimization, Property 14: DANGER 模式允许强势股通过
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    trend_scores=_trend_scores_strategy,
    danger_threshold=st.floats(80.0, 99.0, allow_nan=False, allow_infinity=False),
)
def test_danger_mode_allows_strong_stocks(
    trend_scores: list[float],
    danger_threshold: float,
):
    """
    # Feature: screening-parameter-optimization, Property 14: DANGER 模式允许强势股通过

    **Validates: Requirements 8.3**

    在 DANGER 模式下，过滤结果应恰好包含 trend_score >= danger_strong_threshold 的股票，
    而非返回空列表。
    """
    # 构建 ScreenItem 列表
    items = [
        _make_screen_item(f"stock_{i:04d}", score)
        for i, score in enumerate(trend_scores)
    ]

    # 构造 DANGER 级别的指数数据：前 59 日 = 3000，最新 = 2000（远低于 MA60）
    danger_closes = [3000.0] * 59 + [2000.0]

    checker = MarketRiskChecker()
    from app.services.risk_controller import StockRiskFilter, BlackWhiteListManager

    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data={item.symbol: {} for item in items},
        index_closes=danger_closes,
        market_risk_checker=checker,
        stock_risk_filter=StockRiskFilter(),
        blacklist_manager=BlackWhiteListManager(),
        danger_strong_threshold=danger_threshold,
    )

    assert risk_level == MarketRiskLevel.DANGER, (
        f"应为 DANGER 等级，实际为 {risk_level.value}"
    )

    # 验证过滤结果：恰好包含 trend_score >= threshold 的股票
    expected_symbols = {
        item.symbol for item in items
        if item.trend_score >= danger_threshold
    }
    actual_symbols = {item.symbol for item in filtered}

    assert actual_symbols == expected_symbols, (
        f"DANGER 模式下应仅保留 trend_score >= {danger_threshold} 的股票："
        f"expected={expected_symbols}, actual={actual_symbols}"
    )


@settings(max_examples=200)
@given(trend_scores=_trend_scores_strategy)
def test_danger_mode_default_threshold_95(trend_scores: list[float]):
    """
    # Feature: screening-parameter-optimization, Property 14: DANGER 模式允许强势股通过

    **Validates: Requirements 8.3**

    使用默认阈值 95.0 时，DANGER 模式下仅保留 trend_score >= 95 的股票。
    """
    items = [
        _make_screen_item(f"stock_{i:04d}", score)
        for i, score in enumerate(trend_scores)
    ]

    danger_closes = [3000.0] * 59 + [2000.0]

    checker = MarketRiskChecker()
    from app.services.risk_controller import StockRiskFilter, BlackWhiteListManager

    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data={item.symbol: {} for item in items},
        index_closes=danger_closes,
        market_risk_checker=checker,
        stock_risk_filter=StockRiskFilter(),
        blacklist_manager=BlackWhiteListManager(),
    )

    assert risk_level == MarketRiskLevel.DANGER

    # 默认阈值 95.0
    for item in filtered:
        assert item.trend_score >= 95.0, (
            f"DANGER 模式下默认阈值 95，但 {item.symbol} 的 trend_score={item.trend_score}"
        )

    # 确保没有遗漏强势股
    strong_count = sum(1 for s in trend_scores if s >= 95.0)
    assert len(filtered) == strong_count, (
        f"应有 {strong_count} 只强势股通过，实际 {len(filtered)} 只"
    )
