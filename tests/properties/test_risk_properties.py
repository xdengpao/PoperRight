"""
RiskController 属性测试（Hypothesis）

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 11.1, 11.2, 11.3**

属性 15：大盘风控状态转换
属性 16：个股风控过滤正确性
属性 17：黑名单不变量
属性 18：仓位限制不变量
属性 19：止损触发正确性
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import (
    MarketRiskChecker,
    StockRiskFilter,
    BlackWhiteListManager,
    PositionRiskChecker,
    StopLossChecker,
)
from app.core.schemas import MarketRiskLevel


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 正浮点价格
_price = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)

# 股票代码
_symbol = st.from_regex(r"[0-9]{6}\.(SH|SZ|BJ)", fullmatch=True)


# ---------------------------------------------------------------------------
# 属性 15：大盘风控状态转换
# Feature: a-share-quant-trading-system, Property 15: 大盘风控状态转换
# ---------------------------------------------------------------------------


@st.composite
def _index_closes_below_ma20_above_ma60(draw):
    """
    生成一段指数收盘价序列，使得最新价 < MA20 但 >= MA60。

    策略：前 40 日用较低基准价，后 19 日用较高价格拉高 MA20，
    最新价设在 MA60 之上但 MA20 之下。
    """
    base = draw(st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    bump = draw(st.floats(min_value=5.0, max_value=30.0, allow_nan=False, allow_infinity=False))
    # 前 40 日 = base，后 19 日 = base + bump
    closes = [base] * 40 + [base + bump] * 19
    # MA60 ≈ (40*base + 19*(base+bump)) / 59 ≈ base + 19*bump/59
    # MA20 = (19*(base+bump)) / 19 = base + bump  (before adding last)
    # 最新价需要 < MA20 且 >= MA60
    ma60_approx = base + 19 * bump / 59
    ma20_approx = base + bump  # roughly, since last 19 are base+bump
    # Pick last price between ma60 and ma20
    assume(ma60_approx + 0.5 < ma20_approx - 0.5)
    last_price = draw(st.floats(
        min_value=ma60_approx + 0.5,
        max_value=ma20_approx - 0.5,
        allow_nan=False, allow_infinity=False,
    ))
    closes.append(last_price)
    return closes


@settings(max_examples=100)
@given(closes=_index_closes_below_ma20_above_ma60())
def test_market_risk_caution_threshold_90(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 15: 大盘风控状态转换

    **Validates: Requirements 9.1**

    当指数跌破 20 日均线（但未跌破 60 日均线）时，
    风险等级应为 CAUTION，趋势打分阈值应为 90。
    """
    checker = MarketRiskChecker()
    level = checker.check_market_risk(closes)

    assert level == MarketRiskLevel.CAUTION, (
        f"跌破 MA20 但在 MA60 上方应为 CAUTION，实际={level}"
    )
    assert checker.get_trend_threshold(level) == 90.0, (
        "CAUTION 状态阈值应为 90"
    )
    assert checker.is_buy_suspended(level) is False, (
        "CAUTION 状态不应暂停买入"
    )


@st.composite
def _index_closes_below_ma60(draw):
    """
    生成一段指数收盘价序列，使得最新价 < MA60。

    策略：60 日稳定价格 + 最新价大幅低于均值。
    """
    base = draw(st.floats(min_value=50.0, max_value=300.0, allow_nan=False, allow_infinity=False))
    drop_pct = draw(st.floats(min_value=0.02, max_value=0.30, allow_nan=False, allow_infinity=False))
    closes = [base] * 59
    last_price = base * (1.0 - drop_pct)
    closes.append(last_price)
    # Verify MA60 > last_price
    ma60 = sum(closes) / 60
    assume(last_price < ma60)
    return closes


@settings(max_examples=100)
@given(closes=_index_closes_below_ma60())
def test_market_risk_danger_no_buy(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 15: 大盘风控状态转换

    **Validates: Requirements 9.2**

    当指数跌破 60 日均线时，风险等级应为 DANGER，
    应暂停所有买入信号。
    """
    checker = MarketRiskChecker()
    level = checker.check_market_risk(closes)

    assert level == MarketRiskLevel.DANGER, (
        f"跌破 MA60 应为 DANGER，实际={level}"
    )
    assert checker.is_buy_suspended(level) is True, (
        "DANGER 状态应暂停买入"
    )


@st.composite
def _index_closes_above_both_ma(draw):
    """
    生成一段指数收盘价序列，使得最新价 >= MA20 且 >= MA60。

    策略：上升趋势序列，最新价高于均线。
    """
    base = draw(st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    step = draw(st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False))
    closes = [base + i * step for i in range(60)]
    # 最新价是序列最高点，一定在两条均线上方
    return closes


@settings(max_examples=100)
@given(closes=_index_closes_above_both_ma())
def test_market_risk_normal_threshold_80(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 15: 大盘风控状态转换

    **Validates: Requirements 9.1, 9.2**

    当指数在 20 日和 60 日均线上方时，
    风险等级应为 NORMAL，趋势打分阈值应为 80。
    """
    checker = MarketRiskChecker()
    level = checker.check_market_risk(closes)

    assert level == MarketRiskLevel.NORMAL, (
        f"价格在两条均线上方应为 NORMAL，实际={level}"
    )
    assert checker.get_trend_threshold(level) == 80.0, (
        "NORMAL 状态阈值应为 80"
    )
    assert checker.is_buy_suspended(level) is False, (
        "NORMAL 状态不应暂停买入"
    )



# ---------------------------------------------------------------------------
# 属性 16：个股风控过滤正确性
# Feature: a-share-quant-trading-system, Property 16: 个股风控过滤正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    daily_change=st.floats(min_value=-20.0, max_value=30.0, allow_nan=False, allow_infinity=False),
)
def test_stock_daily_gain_filter(daily_change: float):
    """
    # Feature: a-share-quant-trading-system, Property 16: 个股风控过滤正确性

    **Validates: Requirements 9.3**

    单日涨幅 > 9% 的个股应被剔除；<= 9% 的不应被剔除。
    """
    excluded = StockRiskFilter.check_daily_gain(daily_change)

    if daily_change > 9.0:
        assert excluded is True, (
            f"涨幅 {daily_change}% > 9% 应被剔除"
        )
    else:
        assert excluded is False, (
            f"涨幅 {daily_change}% <= 9% 不应被剔除"
        )


@settings(max_examples=100)
@given(
    daily_changes=st.lists(
        st.floats(min_value=-10.0, max_value=15.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=10,
    ),
)
def test_stock_3day_cumulative_gain_filter(daily_changes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 16: 个股风控过滤正确性

    **Validates: Requirements 9.4**

    连续 3 日累计涨幅 > 20% 的个股应被剔除。
    累计涨幅 = (1+d1/100)*(1+d2/100)*(1+d3/100) - 1
    """
    excluded = StockRiskFilter.check_3day_cumulative_gain(daily_changes)

    # 独立计算最近 3 日复合收益率
    last_3 = daily_changes[-3:]
    cumulative = 1.0
    for pct in last_3:
        cumulative *= (1.0 + pct / 100.0)
    cumulative_pct = (cumulative - 1.0) * 100.0

    if cumulative_pct > 20.0:
        assert excluded is True, (
            f"3 日累计涨幅 {cumulative_pct:.2f}% > 20% 应被剔除"
        )
    else:
        assert excluded is False, (
            f"3 日累计涨幅 {cumulative_pct:.2f}% <= 20% 不应被剔除"
        )



# ---------------------------------------------------------------------------
# 属性 17：黑名单不变量
# Feature: a-share-quant-trading-system, Property 17: 黑名单不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    blacklisted=st.lists(_symbol, min_size=1, max_size=20, unique=True),
    query=_symbol,
)
def test_blacklist_invariant(blacklisted: list[str], query: str):
    """
    # Feature: a-share-quant-trading-system, Property 17: 黑名单不变量

    **Validates: Requirements 9.5**

    黑名单中的股票 is_blacklisted 始终返回 True；
    不在黑名单中的股票返回 False。
    """
    mgr = BlackWhiteListManager()
    for sym in blacklisted:
        mgr.add_to_blacklist(sym, reason="test")

    if query in blacklisted:
        assert mgr.is_blacklisted(query) is True, (
            f"{query} 在黑名单中，应返回 True"
        )
    else:
        assert mgr.is_blacklisted(query) is False, (
            f"{query} 不在黑名单中，应返回 False"
        )



# ---------------------------------------------------------------------------
# 属性 18：仓位限制不变量
# Feature: a-share-quant-trading-system, Property 18: 仓位限制不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    stock_weight=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_stock_position_limit_invariant(stock_weight: float):
    """
    # Feature: a-share-quant-trading-system, Property 18: 仓位限制不变量

    **Validates: Requirements 10.1**

    单只个股仓位 > 15% → 拒绝（passed=False）；
    仓位 <= 15% → 允许（passed=True）。
    """
    result = PositionRiskChecker.check_stock_position_limit(stock_weight)

    if stock_weight > 15.0:
        assert result.passed is False, (
            f"仓位 {stock_weight}% > 15% 应拒绝"
        )
        assert result.reason is not None, "拒绝时应提供原因"
    else:
        assert result.passed is True, (
            f"仓位 {stock_weight}% <= 15% 应允许"
        )


@settings(max_examples=100)
@given(
    sector_weight=st.floats(min_value=0.0, max_value=80.0, allow_nan=False, allow_infinity=False),
)
def test_sector_position_limit_invariant(sector_weight: float):
    """
    # Feature: a-share-quant-trading-system, Property 18: 仓位限制不变量

    **Validates: Requirements 10.2**

    单一板块仓位 > 30% → 拒绝（passed=False）；
    仓位 <= 30% → 允许（passed=True）。
    """
    result = PositionRiskChecker.check_sector_position_limit(sector_weight)

    if sector_weight > 30.0:
        assert result.passed is False, (
            f"板块仓位 {sector_weight}% > 30% 应拒绝"
        )
        assert result.reason is not None, "拒绝时应提供原因"
    else:
        assert result.passed is True, (
            f"板块仓位 {sector_weight}% <= 30% 应允许"
        )



# ---------------------------------------------------------------------------
# 属性 19：止损触发正确性
# Feature: a-share-quant-trading-system, Property 19: 止损触发正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    cost_price=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    current_price=st.floats(min_value=0.1, max_value=500.0, allow_nan=False, allow_infinity=False),
    stop_pct=st.sampled_from([0.05, 0.08, 0.10]),
)
def test_fixed_stop_loss_correctness(cost_price: float, current_price: float, stop_pct: float):
    """
    # Feature: a-share-quant-trading-system, Property 19: 止损触发正确性

    **Validates: Requirements 11.1**

    固定比例止损：当 (cost - current) / cost >= stop_pct 时触发。
    """
    triggered = StopLossChecker.check_fixed_stop_loss(cost_price, current_price, stop_pct)

    loss_pct = (cost_price - current_price) / cost_price

    if loss_pct >= stop_pct:
        assert triggered is True, (
            f"亏损 {loss_pct:.4f} >= 止损比例 {stop_pct}，应触发"
        )
    else:
        assert triggered is False, (
            f"亏损 {loss_pct:.4f} < 止损比例 {stop_pct}，不应触发"
        )


@settings(max_examples=100)
@given(
    peak_price=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    current_price=st.floats(min_value=0.1, max_value=500.0, allow_nan=False, allow_infinity=False),
    retrace_pct=st.sampled_from([0.03, 0.05]),
)
def test_trailing_stop_loss_correctness(peak_price: float, current_price: float, retrace_pct: float):
    """
    # Feature: a-share-quant-trading-system, Property 19: 止损触发正确性

    **Validates: Requirements 11.2**

    移动止损：当 (peak - current) / peak >= retrace_pct 时触发。
    """
    triggered = StopLossChecker.check_trailing_stop_loss(peak_price, current_price, retrace_pct)

    retrace = (peak_price - current_price) / peak_price

    if retrace >= retrace_pct:
        assert triggered is True, (
            f"回撤 {retrace:.4f} >= 回撤比例 {retrace_pct}，应触发"
        )
    else:
        assert triggered is False, (
            f"回撤 {retrace:.4f} < 回撤比例 {retrace_pct}，不应触发"
        )


@settings(max_examples=100)
@given(
    current_price=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    ma_value=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
def test_trend_stop_loss_correctness(current_price: float, ma_value: float):
    """
    # Feature: a-share-quant-trading-system, Property 19: 止损触发正确性

    **Validates: Requirements 11.3**

    趋势止损：当 current_price < ma_value 时触发。
    """
    triggered = StopLossChecker.check_trend_stop_loss(current_price, ma_value)

    if current_price < ma_value:
        assert triggered is True, (
            f"价格 {current_price} < 均线 {ma_value}，应触发"
        )
    else:
        assert triggered is False, (
            f"价格 {current_price} >= 均线 {ma_value}，不应触发"
        )
