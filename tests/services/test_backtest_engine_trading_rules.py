"""
回测引擎交易规则单元测试

覆盖场景：
- 27.15.1 涨停跳过买入
- 27.15.2 跌停延迟卖出
- 27.15.3 停牌暂停检测
- 27.15.4 空仓闲置
- 27.15.5 评分加权分配
- 27.15.6 回测不模拟黑白名单（通过 _calc_limit_prices 验证）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.schemas import (
    BacktestConfig,
    KlineBar,
    RiskLevel,
    ScreenItem,
    SignalDetail,
    StrategyConfig,
)
from app.services.backtest_engine import (
    BacktestEngine,
    _BacktestPosition,
    _BacktestState,
    _SellSignal,
    _TradeRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_bar(
    symbol: str,
    dt: date,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 100_000,
) -> KlineBar:
    return KlineBar(
        time=datetime(dt.year, dt.month, dt.day),
        symbol=symbol,
        freq="1d",
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        amount=Decimal(str(close * volume)),
        turnover=Decimal("5.0"),
        vol_ratio=Decimal("1.0"),
    )


def make_config(**overrides) -> BacktestConfig:
    sc = StrategyConfig(factors=[], logic="AND", weights={}, ma_periods=[5, 10, 20])
    defaults = dict(
        strategy_config=sc,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        max_holdings=3,
        stop_loss_pct=0.08,
        trailing_stop_pct=0.05,
        max_holding_days=20,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def _make_screen_item(
    symbol: str,
    ref_buy_price: float = 10.0,
    trend_score: float = 85.0,
    risk_level: RiskLevel = RiskLevel.LOW,
) -> ScreenItem:
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal(str(ref_buy_price)),
        trend_score=trend_score,
        risk_level=risk_level,
        signals=[],
    )


# ---------------------------------------------------------------------------
# 27.15.1 涨停跳过买入
# ---------------------------------------------------------------------------


class TestLimitUpSkipsBuy:
    """当 T+1 开盘价 == 涨停价时，买入应被跳过。"""

    def test_limit_up_skips_buy(self):
        engine = BacktestEngine()
        config = make_config()

        # Day 1 (Jan 2): close = 10.00
        # Day 2 (Jan 3): open = 11.00 == limit_up = round(10.00 * 1.10, 2)
        symbol = "000001.SZ"
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 9.80, 10.20, 9.70, 10.00),
                make_bar(symbol, date(2024, 1, 3), 11.00, 11.00, 10.80, 10.90),
            ],
        }

        candidate = _make_screen_item(symbol)
        state = _BacktestState(cash=Decimal("1000000"))
        state.trade_day_index = 0

        # Execute buys on Jan 2 → should try to buy at Jan 3 open (11.00)
        # limit_up = round(10.00 * 1.10, 2) = 11.00
        # open_price (11.00) >= limit_up (11.00) → skip
        records = engine._execute_buys(
            [candidate], date(2024, 1, 2), kline_data, state, config,
        )

        assert records == []
        assert symbol not in state.positions
        assert state.cash == Decimal("1000000")

    def test_below_limit_up_allows_buy(self):
        """Open price below limit_up should allow the buy."""
        engine = BacktestEngine()
        config = make_config()

        symbol = "000001.SZ"
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 9.80, 10.20, 9.70, 10.00),
                make_bar(symbol, date(2024, 1, 3), 10.50, 10.80, 10.30, 10.60),
            ],
        }

        candidate = _make_screen_item(symbol)
        state = _BacktestState(cash=Decimal("1000000"))
        state.trade_day_index = 0

        records = engine._execute_buys(
            [candidate], date(2024, 1, 2), kline_data, state, config,
        )

        assert len(records) == 1
        assert records[0].symbol == symbol
        assert records[0].action == "BUY"
        assert symbol in state.positions


# ---------------------------------------------------------------------------
# 27.15.2 跌停延迟卖出
# ---------------------------------------------------------------------------


class TestLimitDownDelaysSell:
    """当卖出执行日开盘价 == 跌停价时，卖出应延迟（设置 pending_sell）。"""

    def test_limit_down_delays_sell(self):
        engine = BacktestEngine()
        config = make_config()

        symbol = "000001.SZ"
        # trade_date = Jan 2, close = 10.00
        # next day (Jan 3) open = 9.00 == limit_down = round(10.00 * 0.90, 2)
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 10.20, 10.30, 9.80, 10.00),
                make_bar(symbol, date(2024, 1, 3), 9.00, 9.10, 9.00, 9.05),
            ],
        }

        position = _BacktestPosition(
            symbol=symbol,
            quantity=1000,
            cost_price=Decimal("10.50"),
            buy_date=date(2024, 1, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("10.50"),
        )
        state = _BacktestState(cash=Decimal("500000"))
        state.positions[symbol] = position

        sell_signal = _SellSignal(
            symbol=symbol,
            reason="STOP_LOSS",
            trigger_date=date(2024, 1, 2),
            priority=1,
        )

        records = engine._execute_sells(
            [sell_signal], date(2024, 1, 2), kline_data, state, config,
        )

        # Sell should NOT execute — position still held with pending_sell set
        assert records == []
        assert symbol in state.positions
        assert state.positions[symbol].pending_sell is not None
        assert state.positions[symbol].pending_sell.reason == "STOP_LOSS"

    def test_above_limit_down_executes_sell(self):
        """Open price above limit_down should execute the sell normally."""
        engine = BacktestEngine()
        config = make_config()

        symbol = "000001.SZ"
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 10.20, 10.30, 9.80, 10.00),
                make_bar(symbol, date(2024, 1, 3), 9.50, 9.60, 9.30, 9.40),
            ],
        }

        position = _BacktestPosition(
            symbol=symbol,
            quantity=1000,
            cost_price=Decimal("10.50"),
            buy_date=date(2024, 1, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("10.50"),
        )
        state = _BacktestState(cash=Decimal("500000"))
        state.positions[symbol] = position

        sell_signal = _SellSignal(
            symbol=symbol,
            reason="STOP_LOSS",
            trigger_date=date(2024, 1, 2),
            priority=1,
        )

        records = engine._execute_sells(
            [sell_signal], date(2024, 1, 2), kline_data, state, config,
        )

        assert len(records) == 1
        assert records[0].action == "SELL"
        assert symbol not in state.positions


# ---------------------------------------------------------------------------
# 27.15.3 停牌暂停检测
# ---------------------------------------------------------------------------


class TestSuspendedStockNoSellCheck:
    """持仓标的停牌（当日无 K 线数据）时，卖出条件检测应返回 None。"""

    def test_suspended_stock_returns_none(self):
        engine = BacktestEngine()
        config = make_config()

        symbol = "000001.SZ"
        # Only has bar on Jan 2, NOT on Jan 3 (suspended)
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 10.00, 10.20, 9.80, 10.00),
            ],
        }

        position = _BacktestPosition(
            symbol=symbol,
            quantity=1000,
            cost_price=Decimal("10.00"),
            buy_date=date(2024, 1, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("10.00"),
        )

        # Check sell conditions for Jan 3 — no bar exists for that date
        result = engine._check_sell_conditions(
            position, date(2024, 1, 3), kline_data, config,
        )

        assert result is None

    def test_no_kline_data_at_all_returns_none(self):
        """Stock with no kline data at all should return None."""
        engine = BacktestEngine()
        config = make_config()

        position = _BacktestPosition(
            symbol="000002.SZ",
            quantity=500,
            cost_price=Decimal("15.00"),
            buy_date=date(2024, 1, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("15.00"),
        )

        result = engine._check_sell_conditions(
            position, date(2024, 1, 3), {}, config,
        )

        assert result is None


# ---------------------------------------------------------------------------
# 27.15.4 空仓闲置
# ---------------------------------------------------------------------------


class TestEmptyPortfolioIdleCash:
    """无选股结果且无持仓时，资金应保持闲置。"""

    def test_empty_portfolio_idle_cash(self):
        engine = BacktestEngine()
        initial_capital = Decimal("1000000")
        config = make_config(
            initial_capital=initial_capital,
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 5),
            enable_market_risk=False,
        )

        # Provide kline data for trade date generation but no strategy signals
        # The ScreenExecutor will produce no results for this minimal data
        symbol = "000001.SZ"
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 10.00, 10.20, 9.80, 10.00),
                make_bar(symbol, date(2024, 1, 3), 10.10, 10.30, 9.90, 10.10),
                make_bar(symbol, date(2024, 1, 4), 10.05, 10.25, 9.85, 10.05),
                make_bar(symbol, date(2024, 1, 5), 10.15, 10.35, 9.95, 10.15),
            ],
        }

        result = engine._run_backtest_strategy_driven(config, kline_data, None)

        # With no successful trades, final equity should equal initial capital
        # (ScreenExecutor with empty factors produces no buy signals)
        assert result.total_trades == 0
        # The equity curve last value should be ~1.0 (NAV = initial)
        if result.equity_curve:
            final_nav = result.equity_curve[-1][1]
            assert final_nav == pytest.approx(1.0, abs=0.001)


# ---------------------------------------------------------------------------
# 27.15.5 评分加权分配
# ---------------------------------------------------------------------------


class TestScoreWeightedAllocation:
    """score_weighted 模式下，资金应按评分比例分配。"""

    def test_score_weighted_allocation(self):
        engine = BacktestEngine()
        # Set max_position_pct=1.0 so the cap doesn't interfere with proportional allocation
        config = make_config(
            allocation_mode="score_weighted", max_holdings=5, max_position_pct=1.0,
        )

        state = _BacktestState(cash=Decimal("1000000"))
        open_price = Decimal("10.00")

        candidate_high = _make_screen_item("000001.SZ", trend_score=80.0)
        candidate_low = _make_screen_item("000002.SZ", trend_score=20.0)

        total_score = 80.0 + 20.0

        shares_high = engine._calculate_buy_amount(
            candidate_high, state, config, open_price, total_score,
        )
        shares_low = engine._calculate_buy_amount(
            candidate_low, state, config, open_price, total_score,
        )

        # Both should get shares
        assert shares_high > 0
        assert shares_low > 0

        # High-score candidate should get ~4x the shares of low-score
        ratio = shares_high / shares_low
        assert ratio == pytest.approx(4.0, abs=0.5)

    def test_equal_scores_equal_allocation(self):
        """Equal trend scores should produce equal allocations."""
        engine = BacktestEngine()
        config = make_config(
            allocation_mode="score_weighted", max_holdings=5, max_position_pct=1.0,
        )

        state = _BacktestState(cash=Decimal("1000000"))
        open_price = Decimal("10.00")

        c1 = _make_screen_item("000001.SZ", trend_score=50.0)
        c2 = _make_screen_item("000002.SZ", trend_score=50.0)

        total_score = 100.0

        shares_1 = engine._calculate_buy_amount(c1, state, config, open_price, total_score)
        shares_2 = engine._calculate_buy_amount(c2, state, config, open_price, total_score)

        assert shares_1 == shares_2


# ---------------------------------------------------------------------------
# 27.15.6 回测不模拟黑白名单 — 通过 _calc_limit_prices 验证
# ---------------------------------------------------------------------------


class TestCalcLimitPrices:
    """验证涨跌停价格计算正确性。"""

    def test_basic_limit_prices(self):
        limit_up, limit_down = BacktestEngine._calc_limit_prices(Decimal("10.00"))
        assert limit_up == Decimal("11.00")
        assert limit_down == Decimal("9.00")

    def test_rounded_limit_prices(self):
        limit_up, limit_down = BacktestEngine._calc_limit_prices(Decimal("15.55"))
        # 15.55 * 1.10 = 17.105 → rounded to 17.11 (ROUND_HALF_EVEN)
        # 15.55 * 0.90 = 13.995 → rounded to 14.00 (ROUND_HALF_EVEN)
        expected_up = (Decimal("15.55") * Decimal("1.10")).quantize(Decimal("0.01"))
        expected_down = (Decimal("15.55") * Decimal("0.90")).quantize(Decimal("0.01"))
        assert limit_up == expected_up
        assert limit_down == expected_down

    def test_small_price_limit(self):
        limit_up, limit_down = BacktestEngine._calc_limit_prices(Decimal("1.00"))
        assert limit_up == Decimal("1.10")
        assert limit_down == Decimal("0.90")


class TestBacktestNoBlacklistWhitelist:
    """
    回测引擎不过滤黑白名单标的。

    验证方式：_execute_buys 和 _generate_buy_signals 中没有黑白名单过滤逻辑，
    任何 symbol 只要满足涨跌停和资金条件就可以买入。
    """

    def test_any_symbol_can_be_bought(self):
        """Symbols that would be blacklisted in live trading can still be bought in backtest."""
        engine = BacktestEngine()
        config = make_config()

        # Use a symbol that might be on a blacklist in production
        symbol = "600999.SH"
        kline_data = {
            symbol: [
                make_bar(symbol, date(2024, 1, 2), 10.00, 10.20, 9.80, 10.00),
                make_bar(symbol, date(2024, 1, 3), 10.10, 10.30, 9.90, 10.10),
            ],
        }

        candidate = _make_screen_item(symbol)
        state = _BacktestState(cash=Decimal("1000000"))
        state.trade_day_index = 0

        records = engine._execute_buys(
            [candidate], date(2024, 1, 2), kline_data, state, config,
        )

        # Should succeed — no blacklist filtering in backtest
        assert len(records) == 1
        assert records[0].symbol == symbol
