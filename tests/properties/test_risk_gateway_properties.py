"""
RiskGateway 风控网关属性测试（Hypothesis）

**Validates: Requirements 1.1, 1.2, 1.3**

Property 1: 风控网关校验正确性
Property 2: 卖出委托跳过买入风控
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    OrderDirection,
    OrderRequest,
    OrderType,
    RiskCheckResult,
    TradeMode,
)
from app.services.risk_controller import (
    RiskGateway,
    _DAILY_GAIN_LIMIT,
    _STOCK_POSITION_LIMIT,
    _SECTOR_POSITION_LIMIT,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_symbol = st.from_regex(r"[0-9]{6}", fullmatch=True)

_price = st.floats(
    min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False,
)

_quantity = st.integers(min_value=100, max_value=10000)

_pct = st.floats(
    min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False,
)

_daily_change = st.floats(
    min_value=-10.0, max_value=20.0, allow_nan=False, allow_infinity=False,
)

_market_value = st.floats(
    min_value=0.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False,
)

_cash = st.floats(
    min_value=0.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False,
)

_position_limit = st.floats(
    min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False,
)


@st.composite
def _buy_order(draw):
    """生成买入委托请求"""
    return OrderRequest(
        symbol=draw(_symbol),
        direction=OrderDirection.BUY,
        order_type=OrderType.LIMIT,
        quantity=draw(_quantity),
        price=Decimal(str(draw(_price))),
        mode=TradeMode.LIVE,
    )


@st.composite
def _sell_order(draw):
    """生成卖出委托请求"""
    return OrderRequest(
        symbol=draw(_symbol),
        direction=OrderDirection.SELL,
        order_type=OrderType.LIMIT,
        quantity=draw(_quantity),
        price=Decimal(str(draw(_price))),
        mode=TradeMode.LIVE,
    )


# ---------------------------------------------------------------------------
# Property 1: 风控网关校验正确性
# Feature: risk-control-enhancement, Property 1: 风控网关校验正确性
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(order=_buy_order())
def test_blacklisted_stock_rejected(order: OrderRequest):
    """
    # Feature: risk-control-enhancement, Property 1: 风控网关校验正确性

    **Validates: Requirements 1.1, 1.2**

    当买入委托的股票在黑名单中时，check_order_risk_pure SHALL 返回 passed=False。
    """
    blacklist = {order.symbol}
    result = RiskGateway.check_order_risk_pure(
        order=order,
        positions=[],
        blacklist=blacklist,
        daily_change_pct=0.0,
        industry_map={},
        total_market_value=0.0,
        available_cash=1_000_000.0,
        total_position_limit=80.0,
    )
    assert result.passed is False, (
        f"黑名单中的股票 {order.symbol} 应被拒绝"
    )
    assert result.reason is not None


@settings(max_examples=200)
@given(
    order=_buy_order(),
    daily_change=st.floats(
        min_value=9.01, max_value=30.0, allow_nan=False, allow_infinity=False,
    ),
)
def test_high_daily_gain_rejected(order: OrderRequest, daily_change: float):
    """
    # Feature: risk-control-enhancement, Property 1: 风控网关校验正确性

    **Validates: Requirements 1.1, 1.2**

    当买入委托的股票当日涨幅超过 9% 时，check_order_risk_pure SHALL 返回 passed=False。
    """
    result = RiskGateway.check_order_risk_pure(
        order=order,
        positions=[],
        blacklist=set(),
        daily_change_pct=daily_change,
        industry_map={},
        total_market_value=0.0,
        available_cash=1_000_000.0,
        total_position_limit=80.0,
    )
    assert result.passed is False, (
        f"涨幅 {daily_change}% > 9% 应被拒绝"
    )


@settings(max_examples=200)
@given(
    order=_buy_order(),
    total_mv=st.floats(
        min_value=100_000.0, max_value=1_000_000.0,
        allow_nan=False, allow_infinity=False,
    ),
    cash=st.floats(
        min_value=1.0, max_value=100_000.0,
        allow_nan=False, allow_infinity=False,
    ),
)
def test_total_position_over_limit_rejected(
    order: OrderRequest, total_mv: float, cash: float,
):
    """
    # Feature: risk-control-enhancement, Property 1: 风控网关校验正确性

    **Validates: Requirements 1.1, 1.2**

    当总仓位超过上限时，check_order_risk_pure SHALL 返回 passed=False。
    """
    total_assets = total_mv + cash
    total_pct = total_mv / total_assets * 100.0
    # 设置一个低于当前仓位的上限
    limit = total_pct - 1.0
    assume(limit > 0)

    result = RiskGateway.check_order_risk_pure(
        order=order,
        positions=[],
        blacklist=set(),
        daily_change_pct=0.0,
        industry_map={},
        total_market_value=total_mv,
        available_cash=cash,
        total_position_limit=limit,
    )
    assert result.passed is False, (
        f"总仓位 {total_pct:.2f}% > 上限 {limit:.2f}% 应被拒绝"
    )


@settings(max_examples=200)
@given(
    order=_buy_order(),
    daily_change=st.floats(
        min_value=-10.0, max_value=8.9, allow_nan=False, allow_infinity=False,
    ),
    cash=st.floats(
        min_value=500_000.0, max_value=10_000_000.0,
        allow_nan=False, allow_infinity=False,
    ),
)
def test_all_checks_pass_returns_true(
    order: OrderRequest, daily_change: float, cash: float,
):
    """
    # Feature: risk-control-enhancement, Property 1: 风控网关校验正确性

    **Validates: Requirements 1.1, 1.2**

    当所有检查均通过时（不在黑名单、涨幅正常、仓位正常），
    check_order_risk_pure SHALL 返回 passed=True。
    """
    # 确保委托金额不会导致单股仓位超限
    order_amount = float(order.price or 0) * order.quantity
    total_assets = cash  # 空持仓，total_market_value=0
    assume(total_assets > 0)
    stock_weight = order_amount / total_assets * 100.0
    assume(stock_weight <= 15.0)
    assume(stock_weight <= 30.0)  # 板块仓位也不超限

    result = RiskGateway.check_order_risk_pure(
        order=order,
        positions=[],
        blacklist=set(),
        daily_change_pct=daily_change,
        industry_map={},
        total_market_value=0.0,
        available_cash=cash,
        total_position_limit=80.0,
        stock_position_limit=15.0,
        sector_position_limit=30.0,
    )
    assert result.passed is True, (
        f"所有检查通过时应返回 passed=True，实际 reason={result.reason}"
    )


# ---------------------------------------------------------------------------
# Property 2: 卖出委托跳过买入风控
# Feature: risk-control-enhancement, Property 2: 卖出委托跳过买入风控
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    order=_sell_order(),
    daily_change=_daily_change,
    total_mv=_market_value,
    cash=_cash,
    total_limit=_position_limit,
)
def test_sell_order_always_passes(
    order: OrderRequest,
    daily_change: float,
    total_mv: float,
    cash: float,
    total_limit: float,
):
    """
    # Feature: risk-control-enhancement, Property 2: 卖出委托跳过买入风控

    **Validates: Requirements 1.3**

    对于任何卖出方向（SELL）的委托请求，无论股票是否在黑名单中、
    无论仓位是否超限，check_order_risk_pure SHALL 始终返回 passed=True。
    """
    # 故意将股票放入黑名单，设置极端参数
    blacklist = {order.symbol}
    result = RiskGateway.check_order_risk_pure(
        order=order,
        positions=[{"symbol": order.symbol, "market_value": 999_999.0}],
        blacklist=blacklist,
        daily_change_pct=daily_change,
        industry_map={},
        total_market_value=total_mv,
        available_cash=cash,
        total_position_limit=total_limit,
    )
    assert result.passed is True, (
        f"卖出委托应始终通过风控，实际 passed={result.passed}, reason={result.reason}"
    )


# ---------------------------------------------------------------------------
# Property 13: 止损预警消息完整性
# Feature: risk-control-enhancement, Property 13: 止损预警消息完整性
# ---------------------------------------------------------------------------

import json
from datetime import datetime

from app.services.risk_controller import build_stop_loss_alert_message


_alert_type = st.sampled_from([
    "固定止损触发", "移动止损触发", "趋势止损触发",
])

_alert_level = st.sampled_from(["danger", "warning"])

_positive_price = st.floats(
    min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False,
)

_trigger_time = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)


@settings(max_examples=200)
@given(
    symbol=_symbol,
    alert_type=_alert_type,
    current_price=_positive_price,
    trigger_threshold=_positive_price,
    alert_level=_alert_level,
    trigger_time=_trigger_time,
)
def test_stop_loss_alert_message_completeness(
    symbol: str,
    alert_type: str,
    current_price: float,
    trigger_threshold: float,
    alert_level: str,
    trigger_time: datetime,
):
    """
    # Feature: risk-control-enhancement, Property 13: 止损预警消息完整性

    **Validates: Requirements 2.2**

    对于任意止损触发事件数据（股票代码、预警类型、当前价格、触发阈值、预警级别），
    构建的预警消息 SHALL 包含所有必需字段且字段值与输入一致。
    """
    msg_str = build_stop_loss_alert_message(
        symbol=symbol,
        alert_type=alert_type,
        current_price=current_price,
        trigger_threshold=trigger_threshold,
        alert_level=alert_level,
        trigger_time=trigger_time,
    )

    # 消息应为有效 JSON
    msg = json.loads(msg_str)

    # 所有必需字段存在
    required_fields = {
        "type", "symbol", "alert_type", "current_price",
        "trigger_threshold", "alert_level", "trigger_time",
    }
    assert required_fields.issubset(msg.keys()), (
        f"缺少必需字段: {required_fields - msg.keys()}"
    )

    # 字段值与输入一致
    assert msg["type"] == "risk:alert"
    assert msg["symbol"] == symbol
    assert msg["alert_type"] == alert_type
    assert msg["current_price"] == current_price
    assert msg["trigger_threshold"] == trigger_threshold
    assert msg["alert_level"] == alert_level
    assert msg["trigger_time"] == trigger_time.isoformat()


# ---------------------------------------------------------------------------
# Property 14: 非交易时段预警抑制
# Feature: risk-control-enhancement, Property 14: 非交易时段预警抑制
# ---------------------------------------------------------------------------

from datetime import time as dt_time

from app.services.risk_controller import is_risk_alert_active


@settings(max_examples=200)
@given(
    dt=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
    ),
)
def test_risk_alert_active_during_trading_hours(dt: datetime):
    """
    # Feature: risk-control-enhancement, Property 14: 非交易时段预警抑制

    **Validates: Requirements 2.7**

    对于任意时间点，当时间在 9:25–15:00 范围内时，is_risk_alert_active SHALL 返回 True；
    当时间不在该范围内时 SHALL 返回 False。
    """
    current_time = dt.time()
    trading_start = dt_time(9, 25)
    trading_end = dt_time(15, 0)

    expected = trading_start <= current_time <= trading_end
    actual = is_risk_alert_active(dt)

    assert actual == expected, (
        f"时间 {current_time}: 期望 is_risk_alert_active={expected}，实际={actual}"
    )


# ---------------------------------------------------------------------------
# Property 15: 风控事件记录完整性
# Feature: risk-control-enhancement, Property 15: 风控事件记录完整性
# ---------------------------------------------------------------------------

from app.services.risk_controller import RiskEventLogger


_event_type = st.sampled_from([
    "ORDER_REJECTED", "STOP_LOSS", "POSITION_LIMIT", "BREAKDOWN",
])

_result_type = st.sampled_from(["REJECTED", "WARNING"])

_rule_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
)

_trigger_value = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False,
)

_threshold_value = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False,
)

_optional_symbol = st.one_of(
    st.none(),
    st.from_regex(r"[0-9]{6}", fullmatch=True),
)


@settings(max_examples=200)
@given(
    event_type=_event_type,
    symbol=_optional_symbol,
    rule_name=_rule_name,
    trigger_value=_trigger_value,
    threshold=_threshold_value,
    result=_result_type,
    triggered_at=_trigger_time,
)
def test_build_event_record_completeness(
    event_type: str,
    symbol: str | None,
    rule_name: str,
    trigger_value: float,
    threshold: float,
    result: str,
    triggered_at: datetime,
):
    """
    # Feature: risk-control-enhancement, Property 15: 风控事件记录完整性

    **Validates: Requirements 10.2**

    对于任意有效的事件输入（事件类型、股票代码、规则名称、触发值、阈值、处理结果、触发时间），
    build_event_record SHALL 返回包含所有必需字段的字典，且字段值与输入一致。
    """
    record = RiskEventLogger.build_event_record(
        event_type=event_type,
        symbol=symbol,
        rule_name=rule_name,
        trigger_value=trigger_value,
        threshold=threshold,
        result=result,
        triggered_at=triggered_at,
    )

    # 所有必需字段存在
    required_fields = {
        "event_type", "symbol", "rule_name",
        "trigger_value", "threshold", "result", "triggered_at",
    }
    assert required_fields.issubset(record.keys()), (
        f"缺少必需字段: {required_fields - record.keys()}"
    )

    # 字段值与输入一致
    assert record["event_type"] == event_type
    assert record["symbol"] == symbol
    assert record["rule_name"] == rule_name
    assert record["trigger_value"] == trigger_value
    assert record["threshold"] == threshold
    assert record["result"] == result
    assert record["triggered_at"] == triggered_at
