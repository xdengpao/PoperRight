"""
TradeExecutor 单元测试

覆盖任务 8.1 的四个子任务：
- 券商交易 API 客户端（委托/撤单/查询）
- 实盘/模拟盘模式切换
- 交易指令加密传输（SSL）
- 非交易时段委托拒绝逻辑
"""

from __future__ import annotations

import ssl
from datetime import datetime, time
from decimal import Decimal

import pytest

from app.core.schemas import (
    OrderDirection,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    TradeMode,
)
from app.services.trade_executor import (
    TRADING_END,
    TRADING_START,
    TradeExecutor,
    _LiveBrokerClient,
    _PaperBrokerClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(**overrides) -> OrderRequest:
    defaults = dict(
        symbol="600000",
        direction=OrderDirection.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=Decimal("10.00"),
        mode=TradeMode.LIVE,
    )
    defaults.update(overrides)
    return OrderRequest(**defaults)


def _fixed_now(year=2025, month=1, day=6, hour=10, minute=0):
    """返回一个固定时间的工厂函数。2025-01-06 是周一。"""
    dt = datetime(year, month, day, hour, minute)
    return lambda: dt


# ---------------------------------------------------------------------------
# PaperBrokerClient 测试
# ---------------------------------------------------------------------------

class TestPaperBrokerClient:
    def test_submit_order_returns_filled(self):
        client = _PaperBrokerClient()
        resp = client.submit_order(_make_order())
        assert resp.status == OrderStatus.FILLED
        assert resp.order_id != ""
        assert resp.symbol == "600000"

    def test_cancel_existing_order(self):
        client = _PaperBrokerClient()
        resp = client.submit_order(_make_order())
        result = client.cancel_order(resp.order_id)
        assert result["success"] is True

    def test_cancel_nonexistent_order(self):
        client = _PaperBrokerClient()
        result = client.cancel_order("nonexistent")
        assert result["success"] is False

    def test_query_orders_within_range(self):
        client = _PaperBrokerClient()
        client.submit_order(_make_order())
        start = datetime(2000, 1, 1)
        end = datetime(2099, 12, 31)
        orders = client.query_orders(start, end)
        assert len(orders) == 1

    def test_query_orders_outside_range(self):
        client = _PaperBrokerClient()
        client.submit_order(_make_order())
        start = datetime(2000, 1, 1)
        end = datetime(2000, 1, 2)
        orders = client.query_orders(start, end)
        assert len(orders) == 0


# ---------------------------------------------------------------------------
# LiveBrokerClient 测试
# ---------------------------------------------------------------------------

class TestLiveBrokerClient:
    def test_submit_order_returns_pending(self):
        client = _LiveBrokerClient()
        resp = client.submit_order(_make_order())
        assert resp.status == OrderStatus.PENDING
        assert resp.order_id != ""

    def test_ssl_context_exists(self):
        """需求 14.4：实盘客户端应使用 SSL 上下文。"""
        client = _LiveBrokerClient()
        assert isinstance(client.ssl_context, ssl.SSLContext)

    def test_cancel_order(self):
        client = _LiveBrokerClient()
        result = client.cancel_order("some_id")
        assert result["success"] is True

    def test_query_orders_returns_list(self):
        client = _LiveBrokerClient()
        result = client.query_orders(datetime(2000, 1, 1), datetime(2099, 1, 1))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TradeExecutor — 模式切换
# ---------------------------------------------------------------------------

class TestModeSwitching:
    def test_default_mode_is_live(self):
        te = TradeExecutor()
        assert te.mode == TradeMode.LIVE

    def test_init_with_paper_mode(self):
        te = TradeExecutor(mode=TradeMode.PAPER)
        assert te.mode == TradeMode.PAPER

    def test_switch_to_paper(self):
        te = TradeExecutor(mode=TradeMode.LIVE)
        te.switch_mode(TradeMode.PAPER)
        assert te.mode == TradeMode.PAPER

    def test_switch_to_live(self):
        te = TradeExecutor(mode=TradeMode.PAPER)
        te.switch_mode(TradeMode.LIVE)
        assert te.mode == TradeMode.LIVE

    def test_broker_changes_with_mode(self):
        te = TradeExecutor(mode=TradeMode.LIVE)
        assert isinstance(te.broker, _LiveBrokerClient)
        te.switch_mode(TradeMode.PAPER)
        assert isinstance(te.broker, _PaperBrokerClient)

    def test_paper_mode_order_filled(self):
        """模拟盘委托应立即成交。"""
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        resp = te.submit_order(_make_order())
        assert resp.status == OrderStatus.FILLED

    def test_live_mode_order_pending(self):
        """实盘委托应为 PENDING 状态。"""
        te = TradeExecutor(mode=TradeMode.LIVE, now_fn=_fixed_now(hour=10))
        resp = te.submit_order(_make_order())
        assert resp.status == OrderStatus.PENDING


# ---------------------------------------------------------------------------
# TradeExecutor — 交易时段判断
# ---------------------------------------------------------------------------

class TestTradingHours:
    def test_weekday_within_hours(self):
        # 周一 10:00
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 10, 0))
        assert te.is_trading_hours() is True

    def test_weekday_at_start(self):
        # 周一 9:25
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 9, 25))
        assert te.is_trading_hours() is True

    def test_weekday_at_end(self):
        # 周一 15:00
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 15, 0))
        assert te.is_trading_hours() is True

    def test_weekday_before_start(self):
        # 周一 9:24
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 9, 24))
        assert te.is_trading_hours() is False

    def test_weekday_after_end(self):
        # 周一 15:01
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 15, 1))
        assert te.is_trading_hours() is False

    def test_saturday(self):
        # 2025-01-04 是周六
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 4, 10, 0))
        assert te.is_trading_hours() is False

    def test_sunday(self):
        # 2025-01-05 是周日
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 5, 10, 0))
        assert te.is_trading_hours() is False

    def test_early_morning(self):
        # 周一 6:00
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 6, 0))
        assert te.is_trading_hours() is False

    def test_late_night(self):
        # 周一 23:00
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 23, 0))
        assert te.is_trading_hours() is False


# ---------------------------------------------------------------------------
# TradeExecutor — 非交易时段委托拒绝
# ---------------------------------------------------------------------------

class TestOrderRejectionOutsideTradingHours:
    def test_reject_before_trading(self):
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 9, 0))
        resp = te.submit_order(_make_order())
        assert resp.status == OrderStatus.REJECTED
        assert resp.message == "OUTSIDE_TRADING_HOURS"

    def test_reject_after_trading(self):
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 16, 0))
        resp = te.submit_order(_make_order())
        assert resp.status == OrderStatus.REJECTED

    def test_reject_on_weekend(self):
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 4, 10, 0))
        resp = te.submit_order(_make_order())
        assert resp.status == OrderStatus.REJECTED

    def test_accept_during_trading(self):
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 6, 10, 30))
        resp = te.submit_order(_make_order())
        assert resp.status != OrderStatus.REJECTED

    def test_rejected_order_has_empty_id(self):
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 4, 10, 0))
        resp = te.submit_order(_make_order())
        assert resp.order_id == ""

    def test_rejected_preserves_order_info(self):
        order = _make_order(symbol="000001", quantity=200)
        te = TradeExecutor(now_fn=_fixed_now(2025, 1, 4, 10, 0))
        resp = te.submit_order(order)
        assert resp.symbol == "000001"
        assert resp.quantity == 200
        assert resp.direction == OrderDirection.BUY


# ---------------------------------------------------------------------------
# TradeExecutor — 撤单
# ---------------------------------------------------------------------------

class TestCancelOrder:
    def test_cancel_paper_order(self):
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        resp = te.submit_order(_make_order())
        result = te.cancel_order(resp.order_id)
        assert result["success"] is True

    def test_cancel_live_order(self):
        te = TradeExecutor(mode=TradeMode.LIVE, now_fn=_fixed_now(hour=10))
        resp = te.submit_order(_make_order())
        result = te.cancel_order(resp.order_id)
        assert result["success"] is True



# ---------------------------------------------------------------------------
# ManualTradeHelper 测试（任务 8.2）
# ---------------------------------------------------------------------------

from app.core.schemas import ScreenItem, RiskLevel, SignalCategory, SignalDetail
from app.services.trade_executor import ManualTradeHelper


def _make_screen_item(**overrides) -> ScreenItem:
    defaults = dict(
        symbol="600000",
        ref_buy_price=Decimal("10.00"),
        trend_score=85.0,
        risk_level=RiskLevel.LOW,
        signals=[SignalDetail(category=SignalCategory.MA_TREND, label="ma_trend")],
    )
    defaults.update(overrides)
    return ScreenItem(**defaults)


class TestManualTradeHelperCreateOrder:
    """create_order_from_screen_item 单元测试。"""

    def test_limit_order_has_price(self):
        helper = ManualTradeHelper()
        item = _make_screen_item(ref_buy_price=Decimal("10.00"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.price == Decimal("10.00")

    def test_market_order_has_no_price(self):
        helper = ManualTradeHelper()
        item = _make_screen_item(ref_buy_price=Decimal("10.00"))
        order = helper.create_order_from_screen_item(item, OrderType.MARKET, 100)
        assert order.price is None

    def test_auto_fill_stop_loss_default(self):
        """默认 8% 止损：10.00 * 0.92 = 9.20"""
        helper = ManualTradeHelper()
        item = _make_screen_item(ref_buy_price=Decimal("10.00"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.stop_loss == Decimal("9.20")

    def test_auto_fill_take_profit_default(self):
        """默认 15% 止盈：10.00 * 1.15 = 11.50"""
        helper = ManualTradeHelper()
        item = _make_screen_item(ref_buy_price=Decimal("10.00"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.take_profit == Decimal("11.50")

    def test_custom_stop_loss_pct(self):
        """自定义 5% 止损：20.00 * 0.95 = 19.00"""
        helper = ManualTradeHelper(stop_loss_pct=0.05)
        item = _make_screen_item(ref_buy_price=Decimal("20.00"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 200)
        assert order.stop_loss == Decimal("19.00")

    def test_custom_take_profit_pct(self):
        """自定义 20% 止盈：20.00 * 1.20 = 24.00"""
        helper = ManualTradeHelper(take_profit_pct=0.20)
        item = _make_screen_item(ref_buy_price=Decimal("20.00"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 200)
        assert order.take_profit == Decimal("24.00")

    def test_order_direction_is_buy(self):
        helper = ManualTradeHelper()
        item = _make_screen_item()
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.direction == OrderDirection.BUY

    def test_order_symbol_matches_item(self):
        helper = ManualTradeHelper()
        item = _make_screen_item(symbol="000001")
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.symbol == "000001"

    def test_order_quantity_matches(self):
        helper = ManualTradeHelper()
        item = _make_screen_item()
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 500)
        assert order.quantity == 500

    def test_price_rounding(self):
        """价格应四舍五入到两位小数。"""
        helper = ManualTradeHelper(stop_loss_pct=0.08)
        # 13.57 * 0.92 = 12.4844 → 12.48
        item = _make_screen_item(ref_buy_price=Decimal("13.57"))
        order = helper.create_order_from_screen_item(item, OrderType.LIMIT, 100)
        assert order.stop_loss == Decimal("12.48")


class TestManualTradeHelperSubmit:
    """submit_one_click_order 单元测试。"""

    def test_submit_during_trading_hours(self):
        """交易时段内一键下单应成功。"""
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        helper = ManualTradeHelper()
        item = _make_screen_item()
        resp = helper.submit_one_click_order(te, item, OrderType.LIMIT, 100)
        assert resp.status == OrderStatus.FILLED
        assert resp.symbol == "600000"

    def test_submit_outside_trading_hours_rejected(self):
        """非交易时段一键下单应被拒绝。"""
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=20))
        helper = ManualTradeHelper()
        item = _make_screen_item()
        resp = helper.submit_one_click_order(te, item, OrderType.LIMIT, 100)
        assert resp.status == OrderStatus.REJECTED
        assert resp.message == "OUTSIDE_TRADING_HOURS"

    def test_submit_market_order(self):
        """市价委托一键下单。"""
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        helper = ManualTradeHelper()
        item = _make_screen_item()
        resp = helper.submit_one_click_order(te, item, OrderType.MARKET, 100)
        assert resp.status == OrderStatus.FILLED

    def test_submit_preserves_symbol(self):
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        helper = ManualTradeHelper()
        item = _make_screen_item(symbol="300001")
        resp = helper.submit_one_click_order(te, item, OrderType.LIMIT, 200)
        assert resp.symbol == "300001"
        assert resp.quantity == 200


# ---------------------------------------------------------------------------
# ConditionOrderManager 测试（任务 8.3）
# ---------------------------------------------------------------------------

from app.core.schemas import (
    ConditionOrder,
    ConditionTriggerType,
)
from app.services.trade_executor import ConditionOrderManager


def _make_condition_order(
    symbol: str = "600000",
    trigger_type: ConditionTriggerType = ConditionTriggerType.BREAKOUT_BUY,
    trigger_price: Decimal = Decimal("10.00"),
    direction: OrderDirection = OrderDirection.BUY,
    quantity: int = 100,
    trailing_pct: float | None = None,
    peak_price: Decimal | None = None,
) -> ConditionOrder:
    order_req = OrderRequest(
        symbol=symbol,
        direction=direction,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=trigger_price,
    )
    return ConditionOrder(
        symbol=symbol,
        trigger_type=trigger_type,
        trigger_price=trigger_price,
        order_request=order_req,
        trailing_pct=trailing_pct,
        peak_price=peak_price,
    )


class TestConditionOrderManagerRegisterCancel:
    def test_register_returns_id(self):
        mgr = ConditionOrderManager()
        oid = mgr.register(_make_condition_order())
        assert isinstance(oid, str) and len(oid) > 0

    def test_register_multiple_unique_ids(self):
        mgr = ConditionOrderManager()
        id1 = mgr.register(_make_condition_order())
        id2 = mgr.register(_make_condition_order())
        assert id1 != id2

    def test_cancel_active_order(self):
        mgr = ConditionOrderManager()
        oid = mgr.register(_make_condition_order())
        assert mgr.cancel(oid) is True

    def test_cancel_nonexistent_order(self):
        mgr = ConditionOrderManager()
        assert mgr.cancel("nonexistent") is False

    def test_cancel_already_cancelled(self):
        mgr = ConditionOrderManager()
        oid = mgr.register(_make_condition_order())
        mgr.cancel(oid)
        assert mgr.cancel(oid) is False

    def test_get_active_orders(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order())
        mgr.register(_make_condition_order())
        assert len(mgr.get_active_orders()) == 2

    def test_get_active_orders_excludes_cancelled(self):
        mgr = ConditionOrderManager()
        oid = mgr.register(_make_condition_order())
        mgr.register(_make_condition_order())
        mgr.cancel(oid)
        assert len(mgr.get_active_orders()) == 1


class TestBreakoutBuyCondition:
    """突破买入：current_price >= trigger_price 时触发。"""

    def test_triggers_when_price_equals_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 10.00}, te)
        assert len(results) == 1
        assert results[0].status == OrderStatus.FILLED

    def test_triggers_when_price_above_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 10.50}, te)
        assert len(results) == 1

    def test_does_not_trigger_below(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 9.99}, te)
        assert len(results) == 0

    def test_deactivated_after_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        mgr.check_and_trigger({"600000": 10.00}, te)
        assert len(mgr.get_active_orders()) == 0


class TestStopLossCondition:
    """止损卖出：current_price <= trigger_price 时触发。"""

    def test_triggers_when_price_equals_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.STOP_LOSS,
            trigger_price=Decimal("9.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 9.00}, te)
        assert len(results) == 1

    def test_triggers_when_price_below_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.STOP_LOSS,
            trigger_price=Decimal("9.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 8.50}, te)
        assert len(results) == 1

    def test_does_not_trigger_above(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.STOP_LOSS,
            trigger_price=Decimal("9.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 9.01}, te)
        assert len(results) == 0


class TestTakeProfitCondition:
    """止盈卖出：current_price >= trigger_price 时触发。"""

    def test_triggers_when_price_equals_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.TAKE_PROFIT,
            trigger_price=Decimal("12.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 12.00}, te)
        assert len(results) == 1

    def test_triggers_when_price_above_trigger(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.TAKE_PROFIT,
            trigger_price=Decimal("12.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 13.00}, te)
        assert len(results) == 1

    def test_does_not_trigger_below(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.TAKE_PROFIT,
            trigger_price=Decimal("12.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 11.99}, te)
        assert len(results) == 0


class TestTrailingStopCondition:
    """移动止盈：current_price <= peak_price * (1 - trailing_pct) 时触发。"""

    def test_triggers_on_pullback(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.TRAILING_STOP,
            trigger_price=Decimal("10.00"),
            direction=OrderDirection.SELL,
            trailing_pct=0.05,
            peak_price=Decimal("12.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        # threshold = 12.00 * 0.95 = 11.40; price 11.00 <= 11.40 → trigger
        results = mgr.check_and_trigger({"600000": 11.00}, te)
        assert len(results) == 1

    def test_does_not_trigger_above_threshold(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.TRAILING_STOP,
            trigger_price=Decimal("10.00"),
            direction=OrderDirection.SELL,
            trailing_pct=0.05,
            peak_price=Decimal("12.00"),
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        # threshold = 12.00 * 0.95 = 11.40; price 11.50 > 11.40 → no trigger
        results = mgr.check_and_trigger({"600000": 11.50}, te)
        assert len(results) == 0

    def test_peak_price_updates_on_new_high(self):
        mgr = ConditionOrderManager()
        co = _make_condition_order(
            trigger_type=ConditionTriggerType.TRAILING_STOP,
            trigger_price=Decimal("10.00"),
            direction=OrderDirection.SELL,
            trailing_pct=0.05,
            peak_price=Decimal("12.00"),
        )
        mgr.register(co)
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        # price 13.00 > peak 12.00 → update peak; threshold = 13.00 * 0.95 = 12.35 → no trigger
        results = mgr.check_and_trigger({"600000": 13.00}, te)
        assert len(results) == 0
        assert co.peak_price == Decimal("13.0")

    def test_trailing_stop_with_no_initial_peak(self):
        """peak_price 为 None 时，使用当前价格作为 peak。"""
        mgr = ConditionOrderManager()
        co = _make_condition_order(
            trigger_type=ConditionTriggerType.TRAILING_STOP,
            trigger_price=Decimal("10.00"),
            direction=OrderDirection.SELL,
            trailing_pct=0.05,
            peak_price=None,
        )
        mgr.register(co)
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        # peak defaults to current_price=11.00; threshold = 11.00 * 0.95 = 10.45 → no trigger
        results = mgr.check_and_trigger({"600000": 11.00}, te)
        assert len(results) == 0


class TestConditionOrderManagerEdgeCases:
    def test_no_price_for_symbol_skips(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(symbol="600000"))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"000001": 10.00}, te)
        assert len(results) == 0
        assert len(mgr.get_active_orders()) == 1

    def test_multiple_orders_different_symbols(self):
        mgr = ConditionOrderManager()
        mgr.register(_make_condition_order(
            symbol="600000",
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        mgr.register(_make_condition_order(
            symbol="000001",
            trigger_type=ConditionTriggerType.STOP_LOSS,
            trigger_price=Decimal("5.00"),
            direction=OrderDirection.SELL,
        ))
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 10.50, "000001": 4.50}, te)
        assert len(results) == 2

    def test_cancelled_order_not_triggered(self):
        mgr = ConditionOrderManager()
        oid = mgr.register(_make_condition_order(
            trigger_type=ConditionTriggerType.BREAKOUT_BUY,
            trigger_price=Decimal("10.00"),
        ))
        mgr.cancel(oid)
        te = TradeExecutor(mode=TradeMode.PAPER, now_fn=_fixed_now(hour=10))
        results = mgr.check_and_trigger({"600000": 10.50}, te)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# PositionManager 测试（任务 8.4）
# ---------------------------------------------------------------------------

from app.services.trade_executor import PositionManager
from app.core.schemas import Position


class TestPositionManagerUpdatePosition:
    """持仓数据实时同步（需求 15.1）。"""

    def test_update_creates_position(self):
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("11.00"), Decimal("100000"))
        assert pos.symbol == "600000"
        assert pos.quantity == 1000
        assert pos.cost_price == Decimal("10.00")
        assert pos.current_price == Decimal("11.00")

    def test_market_value_calculation(self):
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("11.00"), Decimal("100000"))
        assert pos.market_value == Decimal("11000.00")

    def test_pnl_calculation(self):
        """属性 27：PnL = (current_price - cost_price) * quantity"""
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("12.00"), Decimal("100000"))
        assert pos.pnl == Decimal("2000.00")

    def test_pnl_negative(self):
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("9.00"), Decimal("100000"))
        assert pos.pnl == Decimal("-1000.00")

    def test_pnl_pct_calculation(self):
        """属性 27：PnL% = PnL / (cost_price * quantity)"""
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("12.00"), Decimal("100000"))
        # PnL% = 2000 / 10000 = 0.2
        assert abs(pos.pnl_pct - 0.2) < 1e-9

    def test_weight_calculation(self):
        mgr = PositionManager()
        pos = mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("10.00"), Decimal("100000"))
        # weight = 10000 / 100000 = 0.1
        assert abs(pos.weight - 0.1) < 1e-9

    def test_update_overwrites_existing(self):
        mgr = PositionManager()
        mgr.update_position("600000", 1000, Decimal("10.00"), Decimal("10.00"), Decimal("100000"))
        pos = mgr.update_position("600000", 2000, Decimal("10.00"), Decimal("11.00"), Decimal("100000"))
        assert pos.quantity == 2000
        assert len(mgr.get_positions()) == 1


class TestPositionManagerGetRemove:
    def test_get_positions_empty(self):
        mgr = PositionManager()
        assert mgr.get_positions() == []

    def test_get_positions_multiple(self):
        mgr = PositionManager()
        mgr.update_position("600000", 100, Decimal("10"), Decimal("10"), Decimal("100000"))
        mgr.update_position("000001", 200, Decimal("20"), Decimal("20"), Decimal("100000"))
        assert len(mgr.get_positions()) == 2

    def test_remove_position(self):
        mgr = PositionManager()
        mgr.update_position("600000", 100, Decimal("10"), Decimal("10"), Decimal("100000"))
        mgr.remove_position("600000")
        assert mgr.get_positions() == []

    def test_remove_nonexistent_no_error(self):
        mgr = PositionManager()
        mgr.remove_position("999999")  # should not raise


class TestPositionManagerTrendBreakdown:
    """持仓个股趋势破位预警（需求 15.2）。"""

    def test_breakdown_when_below_ma20(self):
        alert = PositionManager.check_trend_breakdown("600000", 9.5, 10.0)
        assert alert is not None
        assert alert["alert"] == "TREND_BREAKDOWN"
        assert alert["symbol"] == "600000"

    def test_no_breakdown_when_above_ma20(self):
        alert = PositionManager.check_trend_breakdown("600000", 10.5, 10.0)
        assert alert is None

    def test_no_breakdown_when_equal_ma20(self):
        alert = PositionManager.check_trend_breakdown("600000", 10.0, 10.0)
        assert alert is None


class TestPositionManagerTradeRecords:
    """委托/成交/撤单记录存储与查询导出（需求 15.3）。"""

    def test_add_and_get_records(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "600000", "action": "BUY", "time": datetime(2025, 1, 6, 10, 0)})
        records = mgr.get_trade_records()
        assert len(records) == 1
        assert records[0]["symbol"] == "600000"

    def test_filter_by_start_date(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "600000", "time": datetime(2025, 1, 5)})
        mgr.add_trade_record({"symbol": "000001", "time": datetime(2025, 1, 7)})
        records = mgr.get_trade_records(start_date=datetime(2025, 1, 6))
        assert len(records) == 1
        assert records[0]["symbol"] == "000001"

    def test_filter_by_end_date(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "600000", "time": datetime(2025, 1, 5)})
        mgr.add_trade_record({"symbol": "000001", "time": datetime(2025, 1, 7)})
        records = mgr.get_trade_records(end_date=datetime(2025, 1, 6))
        assert len(records) == 1
        assert records[0]["symbol"] == "600000"

    def test_filter_by_date_range(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "A", "time": datetime(2025, 1, 1)})
        mgr.add_trade_record({"symbol": "B", "time": datetime(2025, 1, 5)})
        mgr.add_trade_record({"symbol": "C", "time": datetime(2025, 1, 10)})
        records = mgr.get_trade_records(
            start_date=datetime(2025, 1, 3),
            end_date=datetime(2025, 1, 7),
        )
        assert len(records) == 1
        assert records[0]["symbol"] == "B"

    def test_get_records_no_filter(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "A", "time": datetime(2025, 1, 1)})
        mgr.add_trade_record({"symbol": "B", "time": datetime(2025, 1, 5)})
        assert len(mgr.get_trade_records()) == 2

    def test_export_csv_empty(self):
        mgr = PositionManager()
        assert mgr.export_trade_records_csv() == b""

    def test_export_csv_content(self):
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "600000", "action": "BUY", "quantity": 100})
        mgr.add_trade_record({"symbol": "000001", "action": "SELL", "quantity": 200})
        csv_bytes = mgr.export_trade_records_csv()
        text = csv_bytes.decode("utf-8")
        assert "symbol" in text
        assert "600000" in text
        assert "000001" in text
        lines = text.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_export_csv_heterogeneous_fields(self):
        """Records with different fields should still export correctly."""
        mgr = PositionManager()
        mgr.add_trade_record({"symbol": "600000", "action": "BUY"})
        mgr.add_trade_record({"symbol": "000001", "price": "10.00"})
        csv_bytes = mgr.export_trade_records_csv()
        text = csv_bytes.decode("utf-8")
        # All field names should appear in header
        assert "symbol" in text
        assert "action" in text
        assert "price" in text
