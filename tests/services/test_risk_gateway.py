"""
RiskGateway 风控网关单元测试

覆盖：
- check_order_risk_pure: 纯函数风控校验链
  - 卖出委托直接通过
  - 黑名单检查
  - 涨幅检查
  - 单股仓位检查
  - 板块仓位检查
  - 总仓位检查
  - 短路求值行为
- check_and_submit: 风控校验 + 委托提交
  - 异常处理路径
  - 边界条件（空持仓、零仓位）

对应需求：
- 需求 1.1：委托提交前执行完整风控校验链
- 需求 1.2：任一检查未通过则拒绝委托
- 需求 1.3：卖出委托跳过买入相关风控检查
- 需求 1.6：异常时拒绝委托并记录异常
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.schemas import (
    OrderDirection,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    Position,
    TradeMode,
)
from app.services.risk_controller import RiskGateway


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buy_order(symbol: str = "600000", price: float = 10.0, quantity: int = 100) -> OrderRequest:
    """创建买入委托请求"""
    return OrderRequest(
        symbol=symbol,
        direction=OrderDirection.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=Decimal(str(price)),
        mode=TradeMode.LIVE,
    )


def _make_sell_order(symbol: str = "600000", price: float = 10.0, quantity: int = 100) -> OrderRequest:
    """创建卖出委托请求"""
    return OrderRequest(
        symbol=symbol,
        direction=OrderDirection.SELL,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=Decimal(str(price)),
        mode=TradeMode.LIVE,
    )


def _make_position(symbol: str, market_value: float, total_assets: float = 1_000_000.0) -> Position:
    """创建持仓对象"""
    return Position.from_cost(
        symbol=symbol,
        quantity=1000,
        cost_price=Decimal(str(market_value / 1000)),
        current_price=Decimal(str(market_value / 1000)),
        total_assets=Decimal(str(total_assets)),
    )


def _make_mock_broker(order_id: str = "test123") -> MagicMock:
    """创建模拟券商客户端"""
    broker = MagicMock()
    broker.submit_order.return_value = OrderResponse(
        order_id=order_id,
        symbol="600000",
        direction=OrderDirection.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=Decimal("10.00"),
        status=OrderStatus.FILLED,
    )
    return broker


# ===========================================================================
# check_order_risk_pure 测试
# ===========================================================================


class TestCheckOrderRiskPureSellOrder:
    """卖出委托直接通过（需求 1.3）"""

    def test_sell_order_passes(self):
        """卖出委托直接返回 passed=True"""
        order = _make_sell_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist={"600000"},  # 故意放入黑名单
            daily_change_pct=15.0,  # 故意设置高涨幅
            industry_map={},
            total_market_value=999_999.0,
            available_cash=1.0,
            total_position_limit=1.0,  # 故意设置极低上限
        )
        assert result.passed is True

    def test_sell_order_with_blacklisted_stock(self):
        """卖出黑名单中的股票也通过"""
        order = _make_sell_order(symbol="000001")
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist={"000001"},
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True


class TestCheckOrderRiskPureBlacklist:
    """黑名单检查"""

    def test_blacklisted_stock_rejected(self):
        """黑名单中的股票被拒绝"""
        order = _make_buy_order(symbol="600000")
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist={"600000"},
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is False
        assert "黑名单" in result.reason

    def test_non_blacklisted_stock_passes_blacklist_check(self):
        """不在黑名单中的股票通过黑名单检查"""
        order = _make_buy_order(symbol="600000")
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist={"000001"},
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True

    def test_empty_blacklist_passes(self):
        """空黑名单通过"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True


class TestCheckOrderRiskPureDailyGain:
    """涨幅检查"""

    def test_high_gain_rejected(self):
        """涨幅 > 9% 被拒绝"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=9.5,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is False
        assert "涨幅" in result.reason

    def test_gain_at_9_passes(self):
        """涨幅恰好 9% 通过"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=9.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True

    def test_negative_gain_passes(self):
        """跌幅通过"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=-5.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True


class TestCheckOrderRiskPureStockPosition:
    """单股仓位检查"""

    def test_stock_position_over_limit_rejected(self):
        """单股仓位超限被拒绝"""
        order = _make_buy_order(symbol="600000", price=10.0, quantity=100)
        # 已有持仓 160_000（16%），加上委托 1000 → 超过 15%
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[{"symbol": "600000", "market_value": 160_000.0}],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=160_000.0,
            available_cash=840_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is False
        assert "仓位" in result.reason

    def test_stock_position_within_limit_passes(self):
        """单股仓位在限制内通过"""
        order = _make_buy_order(symbol="600000", price=10.0, quantity=100)
        # 已有持仓 100_000（10%），加上委托 1000 → 10.1% < 15%
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[{"symbol": "600000", "market_value": 100_000.0}],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=100_000.0,
            available_cash=900_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True


class TestCheckOrderRiskPureSectorPosition:
    """板块仓位检查"""

    def test_sector_position_over_limit_rejected(self):
        """板块仓位超限被拒绝"""
        order = _make_buy_order(symbol="600000", price=10.0, quantity=100)
        industry_map = {"600000": "银行", "600001": "银行"}
        # 同行业持仓 310_000（31%），加上委托 → 超过 30%
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[
                {"symbol": "600001", "market_value": 310_000.0},
            ],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map=industry_map,
            total_market_value=310_000.0,
            available_cash=690_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is False
        assert "板块" in result.reason


class TestCheckOrderRiskPureTotalPosition:
    """总仓位检查"""

    def test_total_position_over_limit_rejected(self):
        """总仓位超限被拒绝"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=900_000.0,
            available_cash=100_000.0,
            total_position_limit=80.0,  # 当前 90% > 80%
        )
        assert result.passed is False
        assert "总仓位" in result.reason

    def test_total_position_within_limit_passes(self):
        """总仓位在限制内通过"""
        order = _make_buy_order(price=10.0, quantity=100)
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=500_000.0,
            available_cash=500_000.0,
            total_position_limit=80.0,  # 当前 50% < 80%
        )
        assert result.passed is True


class TestCheckOrderRiskPureBoundary:
    """边界条件"""

    def test_empty_positions(self):
        """空持仓通过"""
        order = _make_buy_order(price=10.0, quantity=100)
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is True

    def test_zero_total_assets(self):
        """总资产为零时通过（不触发除零错误）"""
        order = _make_buy_order()
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist=set(),
            daily_change_pct=0.0,
            industry_map={},
            total_market_value=0.0,
            available_cash=0.0,
            total_position_limit=80.0,
        )
        assert result.passed is True

    def test_short_circuit_blacklist_before_gain(self):
        """短路求值：黑名单检查在涨幅检查之前"""
        order = _make_buy_order(symbol="600000")
        result = RiskGateway.check_order_risk_pure(
            order=order,
            positions=[],
            blacklist={"600000"},
            daily_change_pct=15.0,  # 也超涨幅限制
            industry_map={},
            total_market_value=0.0,
            available_cash=1_000_000.0,
            total_position_limit=80.0,
        )
        assert result.passed is False
        assert "黑名单" in result.reason  # 应该是黑名单原因，不是涨幅


# ===========================================================================
# check_and_submit 测试
# ===========================================================================


class TestCheckAndSubmitSellOrder:
    """卖出委托直接提交"""

    def test_sell_order_submitted_directly(self):
        """卖出委托直接提交至 broker"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_sell_order()

        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions=[],
            market_data={},
            blacklist={"600000"},  # 故意放入黑名单
            total_position_limit=80.0,
        )
        broker.submit_order.assert_called_once_with(order)
        assert resp.status == OrderStatus.FILLED


class TestCheckAndSubmitBuyOrder:
    """买入委托风控校验"""

    def test_buy_order_passes_risk_check(self):
        """买入委托通过风控后提交"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_buy_order()

        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions=[],
            market_data={
                "daily_change_pct": 0.0,
                "industry_map": {},
                "total_market_value": 0.0,
                "available_cash": 1_000_000.0,
            },
            blacklist=set(),
            total_position_limit=80.0,
        )
        broker.submit_order.assert_called_once_with(order)
        assert resp.status == OrderStatus.FILLED

    def test_buy_order_rejected_by_blacklist(self):
        """买入委托被黑名单拒绝"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_buy_order(symbol="600000")

        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions=[],
            market_data={
                "daily_change_pct": 0.0,
                "industry_map": {},
                "total_market_value": 0.0,
                "available_cash": 1_000_000.0,
            },
            blacklist={"600000"},
            total_position_limit=80.0,
        )
        broker.submit_order.assert_not_called()
        assert resp.status == OrderStatus.REJECTED
        assert "黑名单" in resp.message


class TestCheckAndSubmitExceptionHandling:
    """异常处理路径（需求 1.6）"""

    def test_exception_returns_rejected(self):
        """风控校验异常时返回 REJECTED"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_buy_order()

        # 传入会导致异常的 market_data（缺少必要字段不会异常，
        # 但 broker 抛异常会被捕获）
        broker.submit_order.side_effect = RuntimeError("连接超时")

        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions=[],
            market_data={
                "daily_change_pct": 0.0,
                "industry_map": {},
                "total_market_value": 0.0,
                "available_cash": 1_000_000.0,
            },
            blacklist=set(),
            total_position_limit=80.0,
        )
        assert resp.status == OrderStatus.REJECTED
        assert "异常" in resp.message

    def test_exception_in_risk_check_returns_rejected(self):
        """风控校验过程中的异常被捕获"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_buy_order()

        # 传入非法的 positions 数据导致异常
        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions="not_a_list",  # type: ignore  # 故意传入错误类型
            market_data={
                "daily_change_pct": 0.0,
                "industry_map": {},
                "total_market_value": 0.0,
                "available_cash": 1_000_000.0,
            },
            blacklist=set(),
            total_position_limit=80.0,
        )
        assert resp.status == OrderStatus.REJECTED
        assert "异常" in resp.message


class TestCheckAndSubmitWithPositions:
    """带持仓的风控校验"""

    def test_with_existing_positions(self):
        """已有持仓时正确计算仓位"""
        gateway = RiskGateway()
        broker = _make_mock_broker()
        order = _make_buy_order(symbol="600000", price=10.0, quantity=100)

        pos = _make_position("600000", 100_000.0)

        resp = gateway.check_and_submit(
            order=order,
            broker=broker,
            positions=[pos],
            market_data={
                "daily_change_pct": 0.0,
                "industry_map": {},
                "total_market_value": 100_000.0,
                "available_cash": 900_000.0,
            },
            blacklist=set(),
            total_position_limit=80.0,
        )
        # 100_000 + 1_000 = 101_000 / 1_000_000 = 10.1% < 15% → 通过
        broker.submit_order.assert_called_once()
        assert resp.status == OrderStatus.FILLED
