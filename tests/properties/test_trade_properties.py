"""
TradeExecutor 属性测试（Hypothesis）

**Validates: Requirements 14.2, 14.5, 15.1, 15.3**

属性 25：条件单触发正确性
属性 26：非交易时段委托拒绝
属性 27：持仓盈亏计算正确性
属性 28：交易记录 round-trip
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.trade_executor import (
    TradeExecutor,
    ConditionOrderManager,
    PositionManager,
    TRADING_START,
    TRADING_END,
)
from app.core.schemas import (
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderDirection,
    OrderType,
    TradeMode,
    ConditionOrder,
    ConditionTriggerType,
    Position,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_symbol_strategy = st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True)

_positive_price = st.floats(
    min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False,
)

_positive_decimal_price = _positive_price.map(lambda p: Decimal(str(round(p, 2))))

_quantity = st.integers(min_value=100, max_value=100000)

_trailing_pct = st.floats(
    min_value=0.01, max_value=0.20, allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------
# 属性 25：条件单触发正确性
# Feature: a-share-quant-trading-system, Property 25: 条件单触发正确性
# ---------------------------------------------------------------------------


def _make_order_request(symbol: str, direction: OrderDirection, price: Decimal, qty: int) -> OrderRequest:
    return OrderRequest(
        symbol=symbol,
        direction=direction,
        order_type=OrderType.LIMIT,
        quantity=qty,
        price=price,
    )


def _trading_hours_executor() -> TradeExecutor:
    """返回一个固定在交易时段内（周一 10:00）的 TradeExecutor（模拟盘）。"""
    return TradeExecutor(
        mode=TradeMode.PAPER,
        now_fn=lambda: datetime(2025, 1, 6, 10, 0),  # 周一 10:00
    )


@settings(max_examples=100)
@given(
    symbol=_symbol_strategy,
    trigger_price=_positive_decimal_price,
    current_price=_positive_price,
    qty=_quantity,
    trigger_type=st.sampled_from([
        ConditionTriggerType.BREAKOUT_BUY,
        ConditionTriggerType.STOP_LOSS,
        ConditionTriggerType.TAKE_PROFIT,
    ]),
)
def test_condition_order_trigger_correctness_basic(
    symbol: str,
    trigger_price: Decimal,
    current_price: float,
    qty: int,
    trigger_type: ConditionTriggerType,
):
    """
    # Feature: a-share-quant-trading-system, Property 25: 条件单触发正确性

    **Validates: Requirements 14.2**

    对 BREAKOUT_BUY / STOP_LOSS / TAKE_PROFIT 三种条件单：
    - BREAKOUT_BUY：price >= trigger_price 时触发
    - STOP_LOSS：price <= trigger_price 时触发
    - TAKE_PROFIT：price >= trigger_price 时触发
    """
    direction = OrderDirection.BUY if trigger_type == ConditionTriggerType.BREAKOUT_BUY else OrderDirection.SELL
    order_req = _make_order_request(symbol, direction, trigger_price, qty)
    co = ConditionOrder(
        symbol=symbol,
        trigger_type=trigger_type,
        trigger_price=trigger_price,
        order_request=order_req,
    )

    mgr = ConditionOrderManager()
    mgr.register(co)
    executor = _trading_hours_executor()
    results = mgr.check_and_trigger({symbol: current_price}, executor)

    trigger_val = float(trigger_price)

    if trigger_type == ConditionTriggerType.BREAKOUT_BUY:
        should_trigger = current_price >= trigger_val
    elif trigger_type == ConditionTriggerType.STOP_LOSS:
        should_trigger = current_price <= trigger_val
    else:  # TAKE_PROFIT
        should_trigger = current_price >= trigger_val

    if should_trigger:
        assert len(results) == 1, (
            f"{trigger_type.value} 应触发：current={current_price}, trigger={trigger_val}"
        )
        assert results[0].symbol == symbol
    else:
        assert len(results) == 0, (
            f"{trigger_type.value} 不应触发：current={current_price}, trigger={trigger_val}"
        )


@settings(max_examples=100)
@given(
    symbol=_symbol_strategy,
    trigger_price=_positive_decimal_price,
    peak_price=_positive_price,
    current_price=_positive_price,
    trailing_pct=_trailing_pct,
    qty=_quantity,
)
def test_condition_order_trailing_stop_correctness(
    symbol: str,
    trigger_price: Decimal,
    peak_price: float,
    current_price: float,
    trailing_pct: float,
    qty: int,
):
    """
    # Feature: a-share-quant-trading-system, Property 25: 条件单触发正确性（TRAILING_STOP）

    **Validates: Requirements 14.2**

    TRAILING_STOP：
    - 若 current_price > peak_price，则更新 peak_price
    - 触发条件：current_price <= effective_peak * (1 - trailing_pct)
    """
    order_req = _make_order_request(symbol, OrderDirection.SELL, trigger_price, qty)
    co = ConditionOrder(
        symbol=symbol,
        trigger_type=ConditionTriggerType.TRAILING_STOP,
        trigger_price=trigger_price,
        order_request=order_req,
        trailing_pct=trailing_pct,
        peak_price=Decimal(str(round(peak_price, 2))),
    )

    mgr = ConditionOrderManager()
    mgr.register(co)
    executor = _trading_hours_executor()
    results = mgr.check_and_trigger({symbol: current_price}, executor)

    effective_peak = max(peak_price, current_price)
    threshold = effective_peak * (1 - trailing_pct)
    should_trigger = current_price <= threshold

    if should_trigger:
        assert len(results) == 1, (
            f"TRAILING_STOP 应触发：current={current_price}, "
            f"effective_peak={effective_peak}, threshold={threshold:.4f}"
        )
    else:
        assert len(results) == 0, (
            f"TRAILING_STOP 不应触发：current={current_price}, "
            f"effective_peak={effective_peak}, threshold={threshold:.4f}"
        )


# ---------------------------------------------------------------------------
# 属性 26：非交易时段委托拒绝
# Feature: a-share-quant-trading-system, Property 26: 非交易时段委托拒绝
# ---------------------------------------------------------------------------


@st.composite
def non_trading_datetime_strategy(draw):
    """生成非交易时段的 datetime（周末或工作日 9:25-15:00 之外）。"""
    choice = draw(st.sampled_from(["weekend", "before_open", "after_close"]))

    if choice == "weekend":
        # 周六=5 或 周日=6
        day_of_week = draw(st.sampled_from([5, 6]))
        # 2025-01-04 是周六, 2025-01-05 是周日
        base = datetime(2025, 1, 4) if day_of_week == 5 else datetime(2025, 1, 5)
        hour = draw(st.integers(min_value=0, max_value=23))
        minute = draw(st.integers(min_value=0, max_value=59))
        return base.replace(hour=hour, minute=minute)
    elif choice == "before_open":
        # 工作日 0:00 - 9:24
        hour = draw(st.integers(min_value=0, max_value=9))
        minute = draw(st.integers(min_value=0, max_value=59))
        if hour == 9:
            minute = draw(st.integers(min_value=0, max_value=24))
        return datetime(2025, 1, 6, hour, minute)  # 周一
    else:
        # 工作日 15:01 - 23:59
        hour = draw(st.integers(min_value=15, max_value=23))
        minute = draw(st.integers(min_value=0, max_value=59))
        if hour == 15:
            minute = draw(st.integers(min_value=1, max_value=59))
        return datetime(2025, 1, 6, hour, minute)  # 周一


@settings(max_examples=100)
@given(
    dt=non_trading_datetime_strategy(),
    symbol=_symbol_strategy,
    price=_positive_decimal_price,
    qty=_quantity,
    direction=st.sampled_from([OrderDirection.BUY, OrderDirection.SELL]),
)
def test_non_trading_hours_order_rejection(
    dt: datetime,
    symbol: str,
    price: Decimal,
    qty: int,
    direction: OrderDirection,
):
    """
    # Feature: a-share-quant-trading-system, Property 26: 非交易时段委托拒绝

    **Validates: Requirements 14.5**

    对任意在非交易时段（非 9:25-15:00 工作日）提交的委托请求，
    系统应拒绝该请求并返回 OUTSIDE_TRADING_HOURS。
    """
    executor = TradeExecutor(
        mode=TradeMode.PAPER,
        now_fn=lambda: dt,
    )
    order = OrderRequest(
        symbol=symbol,
        direction=direction,
        order_type=OrderType.LIMIT,
        quantity=qty,
        price=price,
    )
    resp = executor.submit_order(order)

    assert resp.status == OrderStatus.REJECTED, (
        f"非交易时段 {dt} 委托应被拒绝，实际状态：{resp.status}"
    )
    assert resp.message == "OUTSIDE_TRADING_HOURS", (
        f"拒绝原因应为 OUTSIDE_TRADING_HOURS，实际：{resp.message}"
    )
    assert resp.order_id == "", (
        f"被拒绝的委托 order_id 应为空，实际：{resp.order_id}"
    )


# ---------------------------------------------------------------------------
# 属性 27：持仓盈亏计算正确性
# Feature: a-share-quant-trading-system, Property 27: 持仓盈亏计算正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    symbol=_symbol_strategy,
    quantity=st.integers(min_value=1, max_value=1000000),
    cost_price=_positive_price,
    current_price=_positive_price,
    total_assets=st.floats(min_value=10000.0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_position_pnl_calculation_correctness(
    symbol: str,
    quantity: int,
    cost_price: float,
    current_price: float,
    total_assets: float,
):
    """
    # Feature: a-share-quant-trading-system, Property 27: 持仓盈亏计算正确性

    **Validates: Requirements 15.1**

    对任意持仓记录：
    - PnL = (current_price - cost_price) × quantity
    - PnL% = PnL / (cost_price × quantity)
    - 误差不超过 0.01%
    """
    dec_cost = Decimal(str(cost_price))
    dec_current = Decimal(str(current_price))
    dec_total = Decimal(str(total_assets))

    mgr = PositionManager()
    pos = mgr.update_position(symbol, quantity, dec_cost, dec_current, dec_total)

    # 验证 PnL
    expected_pnl = (dec_current - dec_cost) * quantity
    assert pos.pnl == expected_pnl, (
        f"PnL 不一致：expected={expected_pnl}, actual={pos.pnl}"
    )

    # 验证 PnL%
    cost_basis = dec_cost * quantity
    if cost_basis != 0:
        expected_pnl_pct = float(expected_pnl / cost_basis)
        if abs(expected_pnl_pct) > 1e-10:
            error = abs(pos.pnl_pct - expected_pnl_pct) / abs(expected_pnl_pct)
            assert error < 0.0001, (
                f"PnL% 误差 {error:.6f} 超过 0.01%，"
                f"expected={expected_pnl_pct:.8f}, actual={pos.pnl_pct:.8f}"
            )
        else:
            assert abs(pos.pnl_pct - expected_pnl_pct) < 1e-10


# ---------------------------------------------------------------------------
# 属性 28：交易记录 round-trip
# Feature: a-share-quant-trading-system, Property 28: 交易记录 round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    symbol=_symbol_strategy,
    price=_positive_decimal_price,
    qty=_quantity,
    direction=st.sampled_from([OrderDirection.BUY, OrderDirection.SELL]),
)
def test_trade_record_round_trip(
    symbol: str,
    price: Decimal,
    qty: int,
    direction: OrderDirection,
):
    """
    # Feature: a-share-quant-trading-system, Property 28: 交易记录 round-trip

    **Validates: Requirements 15.3**

    对任意提交并成交的委托，该委托记录应能通过交易流水查询接口检索到，
    且查询结果中的委托信息（股票代码、方向、价格、数量、状态）
    应与原始提交信息完全一致。
    """
    executor = TradeExecutor(
        mode=TradeMode.PAPER,
        now_fn=lambda: datetime(2025, 1, 6, 10, 0),  # 周一 10:00 交易时段
    )
    order = OrderRequest(
        symbol=symbol,
        direction=direction,
        order_type=OrderType.LIMIT,
        quantity=qty,
        price=price,
    )
    resp = executor.submit_order(order)

    # 模拟盘应立即成交
    assert resp.status == OrderStatus.FILLED

    # 将成交记录存入 PositionManager
    mgr = PositionManager()
    now = datetime(2025, 1, 6, 10, 0)
    record = {
        "time": now,
        "order_id": resp.order_id,
        "symbol": resp.symbol,
        "direction": resp.direction.value,
        "price": str(resp.price),
        "quantity": resp.quantity,
        "status": resp.status.value,
    }
    mgr.add_trade_record(record)

    # 查询交易记录
    records = mgr.get_trade_records(
        start_date=datetime(2025, 1, 6, 0, 0),
        end_date=datetime(2025, 1, 6, 23, 59),
    )

    assert len(records) == 1, f"应查询到 1 条记录，实际 {len(records)} 条"

    retrieved = records[0]
    assert retrieved["order_id"] == resp.order_id, "order_id 不一致"
    assert retrieved["symbol"] == symbol, "symbol 不一致"
    assert retrieved["direction"] == direction.value, "direction 不一致"
    assert retrieved["price"] == str(price), "price 不一致"
    assert retrieved["quantity"] == qty, "quantity 不一致"
    assert retrieved["status"] == OrderStatus.FILLED.value, "status 不一致"
