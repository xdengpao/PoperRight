"""
风控过滤属性测试（Hypothesis）

Property 2: DANGER 市场风险清空结果
Property 3: CAUTION 市场风险提升阈值
Property 4: 风控过滤排除规则

对应需求 4.2、4.3、4.4、4.5
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import (
    MarketRiskLevel,
    RiskLevel,
    ScreenItem,
    SignalCategory,
    SignalDetail,
)
from app.services.risk_controller import (
    BlackWhiteListManager,
    MarketRiskChecker,
    StockRiskFilter,
)
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 股票代码策略：6 位数字字符串
_symbol_st = st.from_regex(r"[036]\d{5}", fullmatch=True)

# 趋势评分策略
_trend_score_st = st.floats(min_value=0.0, max_value=100.0,
                            allow_nan=False, allow_infinity=False)

# 单日涨跌幅策略（百分比）
_daily_change_st = st.floats(min_value=-10.0, max_value=20.0,
                             allow_nan=False, allow_infinity=False)

# 收盘价策略
_close_price_st = st.floats(min_value=1.0, max_value=500.0,
                            allow_nan=False, allow_infinity=False)


@st.composite
def screen_item_strategy(draw):
    """生成随机的 ScreenItem 实例。"""
    score = draw(_trend_score_st)
    if score >= 80:
        risk = RiskLevel.LOW
    elif score >= 50:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.HIGH

    return ScreenItem(
        symbol=draw(_symbol_st),
        ref_buy_price=Decimal(str(round(draw(_close_price_st), 2))),
        trend_score=score,
        risk_level=risk,
        signals=[
            SignalDetail(
                category=SignalCategory.MA_TREND,
                label="ma_trend",
            )
        ],
    )


@st.composite
def screen_items_with_data_strategy(draw):
    """
    生成随机的 (items, stocks_data) 对。

    确保 items 中的 symbol 在 stocks_data 中有对应条目，
    且 daily_change_pct 字段已设置。
    """
    n = draw(st.integers(min_value=0, max_value=20))
    symbols = draw(
        st.lists(_symbol_st, min_size=n, max_size=n, unique=True)
    )

    items: list[ScreenItem] = []
    stocks_data: dict[str, dict] = {}

    for sym in symbols:
        score = draw(_trend_score_st)
        if score >= 80:
            risk = RiskLevel.LOW
        elif score >= 50:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.HIGH

        close = round(draw(_close_price_st), 2)
        daily_change = draw(_daily_change_st)

        items.append(ScreenItem(
            symbol=sym,
            ref_buy_price=Decimal(str(close)),
            trend_score=score,
            risk_level=risk,
            signals=[
                SignalDetail(
                    category=SignalCategory.MA_TREND,
                    label="ma_trend",
                )
            ],
        ))

        stocks_data[sym] = {
            "close": close,
            "daily_change_pct": daily_change,
            "ma_trend": score,
        }

    return items, stocks_data


@st.composite
def danger_index_closes_strategy(draw):
    """
    生成使大盘风险等级为 DANGER 的指数收盘价序列。

    DANGER 条件：最新收盘价 < 60 日均线。
    生成 60+ 个高价后跟一个低价。
    """
    n = draw(st.integers(min_value=60, max_value=80))
    high_price = draw(st.floats(min_value=3000.0, max_value=5000.0,
                                allow_nan=False, allow_infinity=False))
    # 生成 n 个高价
    closes = [high_price] * n
    # 最后一个价格远低于均线
    drop_factor = draw(st.floats(min_value=0.5, max_value=0.9,
                                 allow_nan=False, allow_infinity=False))
    closes.append(high_price * drop_factor)
    return closes


@st.composite
def caution_index_closes_strategy(draw):
    """
    生成使大盘风险等级为 CAUTION 的指数收盘价序列。

    CAUTION 条件：最新收盘价 < 20 日均线 但数据不足以计算 60 日均线。
    总长度在 [20, 59] 之间，确保 MA20 可计算但 MA60 不可计算。
    """
    # 总长度 20~59，不足以计算 MA60
    total_len = draw(st.integers(min_value=20, max_value=59))
    high_price = draw(st.floats(min_value=3000.0, max_value=5000.0,
                                allow_nan=False, allow_infinity=False))
    # 前 total_len - 1 个为高价
    closes = [high_price] * (total_len - 1)
    # 最后一个价格低于 20 日均线
    drop_factor = draw(st.floats(min_value=0.5, max_value=0.95,
                                 allow_nan=False, allow_infinity=False))
    closes.append(high_price * drop_factor)
    return closes


# ---------------------------------------------------------------------------
# Property 2: DANGER 市场风险清空结果
# Feature: screening-system-enhancement, Property 2: DANGER 清空
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    data=screen_items_with_data_strategy(),
    index_closes=danger_index_closes_strategy(),
)
def test_danger_clears_all_items(data, index_closes):
    """
    # Feature: screening-system-enhancement, Property 2: DANGER 清空

    **Validates: Requirements 4.2**

    For any stocks_data 和策略配置，当大盘风险等级为 DANGER 时，
    _apply_risk_filters() 返回的列表应为空。
    """
    items, stocks_data = data

    market_risk_checker = MarketRiskChecker()
    stock_risk_filter = StockRiskFilter()
    blacklist_manager = BlackWhiteListManager()

    # 验证确实是 DANGER
    actual_level = market_risk_checker.check_market_risk(index_closes)
    assert actual_level == MarketRiskLevel.DANGER, (
        f"测试数据生成的风险等级应为 DANGER，实际为 {actual_level}"
    )

    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data=stocks_data,
        index_closes=index_closes,
        market_risk_checker=market_risk_checker,
        stock_risk_filter=stock_risk_filter,
        blacklist_manager=blacklist_manager,
    )

    assert risk_level == MarketRiskLevel.DANGER, (
        f"风险等级应为 DANGER，实际为 {risk_level}"
    )
    assert filtered == [], (
        f"DANGER 状态下应返回空列表，实际返回 {len(filtered)} 只股票"
    )


# ---------------------------------------------------------------------------
# Property 3: CAUTION 市场风险提升阈值
# Feature: screening-system-enhancement, Property 3: CAUTION 阈值
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    data=screen_items_with_data_strategy(),
    index_closes=caution_index_closes_strategy(),
)
def test_caution_raises_threshold(data, index_closes):
    """
    # Feature: screening-system-enhancement, Property 3: CAUTION 阈值

    **Validates: Requirements 4.3**

    For any stocks_data 和策略配置，当大盘风险等级为 CAUTION 时，
    返回的所有 ScreenItem 的 trend_score 应 >= 90。
    """
    items, stocks_data = data

    market_risk_checker = MarketRiskChecker()
    stock_risk_filter = StockRiskFilter()
    blacklist_manager = BlackWhiteListManager()

    # 验证确实是 CAUTION
    actual_level = market_risk_checker.check_market_risk(index_closes)
    assert actual_level == MarketRiskLevel.CAUTION, (
        f"测试数据生成的风险等级应为 CAUTION，实际为 {actual_level}"
    )

    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data=stocks_data,
        index_closes=index_closes,
        market_risk_checker=market_risk_checker,
        stock_risk_filter=stock_risk_filter,
        blacklist_manager=blacklist_manager,
    )

    assert risk_level == MarketRiskLevel.CAUTION, (
        f"风险等级应为 CAUTION，实际为 {risk_level}"
    )

    for item in filtered:
        assert item.trend_score >= 90.0, (
            f"CAUTION 状态下股票 {item.symbol} 的 trend_score={item.trend_score} "
            f"应 >= 90"
        )


# ---------------------------------------------------------------------------
# Property 4: 风控过滤排除规则
# Feature: screening-system-enhancement, Property 4: 风控排除规则
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    data=screen_items_with_data_strategy(),
    blacklisted_indices=st.lists(
        st.integers(min_value=0, max_value=19),
        min_size=0,
        max_size=5,
        unique=True,
    ),
)
def test_risk_filter_exclusion_rules(data, blacklisted_indices):
    """
    # Feature: screening-system-enhancement, Property 4: 风控排除规则

    **Validates: Requirements 4.4, 4.5**

    For any stocks_data、黑名单集合和每日涨幅数据，返回的结果中
    不应包含任何单日涨幅 > 9% 的股票，也不应包含任何黑名单中的股票。
    """
    items, stocks_data = data

    market_risk_checker = MarketRiskChecker()
    stock_risk_filter = StockRiskFilter()
    blacklist_manager = BlackWhiteListManager()

    # 将部分股票加入黑名单
    blacklisted_symbols: set[str] = set()
    for idx in blacklisted_indices:
        if idx < len(items):
            sym = items[idx].symbol
            blacklist_manager.add_to_blacklist(sym, reason="测试黑名单")
            blacklisted_symbols.add(sym)

    # 使用 NORMAL 风险等级（不传 index_closes）
    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data=stocks_data,
        index_closes=None,
        market_risk_checker=market_risk_checker,
        stock_risk_filter=stock_risk_filter,
        blacklist_manager=blacklist_manager,
    )

    assert risk_level == MarketRiskLevel.NORMAL

    for item in filtered:
        # 不应包含单日涨幅 > 9% 的股票
        stock_data = stocks_data.get(item.symbol, {})
        daily_change = float(stock_data.get("daily_change_pct", 0.0))
        assert daily_change <= 9.0, (
            f"股票 {item.symbol} 单日涨幅 {daily_change}% > 9%，"
            f"不应出现在过滤后的结果中"
        )

        # 不应包含黑名单中的股票
        assert item.symbol not in blacklisted_symbols, (
            f"股票 {item.symbol} 在黑名单中，不应出现在过滤后的结果中"
        )


@settings(max_examples=200)
@given(data=screen_items_with_data_strategy())
def test_risk_filter_preserves_valid_stocks(data):
    """
    # Feature: screening-system-enhancement, Property 4: 风控排除规则

    **Validates: Requirements 4.4, 4.5**

    在 NORMAL 风险等级下，无黑名单且涨幅 <= 9% 的股票应全部保留。
    """
    items, stocks_data = data

    market_risk_checker = MarketRiskChecker()
    stock_risk_filter = StockRiskFilter()
    blacklist_manager = BlackWhiteListManager()

    filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
        items=items,
        stocks_data=stocks_data,
        index_closes=None,
        market_risk_checker=market_risk_checker,
        stock_risk_filter=stock_risk_filter,
        blacklist_manager=blacklist_manager,
    )

    assert risk_level == MarketRiskLevel.NORMAL

    # 计算预期保留的股票
    expected_symbols = set()
    for item in items:
        stock_data = stocks_data.get(item.symbol, {})
        daily_change = float(stock_data.get("daily_change_pct", 0.0))
        if daily_change <= 9.0:
            expected_symbols.add(item.symbol)

    actual_symbols = {item.symbol for item in filtered}
    assert actual_symbols == expected_symbols, (
        f"NORMAL 状态下无黑名单时，涨幅 <= 9% 的股票应全部保留。"
        f"预期: {expected_symbols}，实际: {actual_symbols}"
    )
