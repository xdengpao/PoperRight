"""
全链路集成测试

测试三条核心业务链路：
1. 数据清洗 → 选股 → 风控 → 预警
2. 选股 → 下单 → 持仓同步 → 止损触发
3. 回测 → 参数优化 → 过拟合检测
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.core.schemas import (
    AlertConfig,
    AlertType,
    BacktestConfig,
    FactorCondition,
    OrderType,
    RiskLevel,
    ScreenItem,
    ScreenType,
    StrategyConfig,
    TradeMode,
)
from app.services.alert_service import AlertService
from app.services.backtest_engine import BacktestEngine
from app.services.data_engine.stock_filter import (
    FundamentalsSnapshot,
    StockBasicInfo,
    StockFilter,
)
from app.services.param_optimizer import (
    DataSplitter,
    GridSearchOptimizer,
    OverfitDetector,
)
from app.services.risk_controller import (
    MarketRiskChecker,
    PositionRiskChecker,
    StockRiskFilter,
    StopLossChecker,
)
from app.services.screener.screen_executor import ScreenExecutor
from app.services.screener.strategy_engine import StrategyEngine
from app.services.trade_executor import (
    ManualTradeHelper,
    PositionManager,
    TradeExecutor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock_data(
    symbol: str,
    ma_trend: float = 85.0,
    close: float = 10.0,
    daily_change_pct: float = 3.0,
) -> dict:
    """Create minimal stock factor data dict for screening."""
    return {
        "symbol": symbol,
        "ma_trend": ma_trend,
        "close": close,
        "daily_change_pct": daily_change_pct,
    }


def _make_strategy_config() -> StrategyConfig:
    """Create a simple ma_trend strategy config."""
    return StrategyConfig(
        factors=[
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
        ],
        logic="AND",
        weights={"ma_trend": 1.0},
    )


# ---------------------------------------------------------------------------
# Pipeline 1: 数据清洗 → 选股 → 风控 → 预警
# ---------------------------------------------------------------------------


class TestDataScreenRiskAlertPipeline:
    """数据接入 → 清洗 → 选股 → 风控 → 预警全链路测试"""

    def test_full_pipeline_filters_bad_stocks_and_generates_alerts(self):
        """
        End-to-end: filter stocks → screen → risk check → alert generation.

        Steps:
        1. StockFilter removes ST / high-pledge stocks
        2. ScreenExecutor screens remaining stocks
        3. RiskController checks individual stock risk
        4. AlertService generates alerts for qualifying stocks
        """
        # --- Step 1: Data cleaning ---
        stock_filter = StockFilter()

        stocks_raw = [
            StockBasicInfo(symbol="000001", is_st=False, trading_days_since_ipo=100),
            StockBasicInfo(symbol="000002", is_st=True, trading_days_since_ipo=200),
            StockBasicInfo(symbol="000003", is_st=False, trading_days_since_ipo=5),
            StockBasicInfo(symbol="000004", is_st=False, trading_days_since_ipo=100),
        ]
        fundamentals = {
            "000001": FundamentalsSnapshot(symbol="000001", pledge_ratio=Decimal("30")),
            "000002": FundamentalsSnapshot(symbol="000002", pledge_ratio=Decimal("10")),
            "000003": FundamentalsSnapshot(symbol="000003", pledge_ratio=Decimal("10")),
            "000004": FundamentalsSnapshot(symbol="000004", pledge_ratio=Decimal("80")),
        }

        clean_symbols = []
        for stock in stocks_raw:
            fund = fundamentals.get(stock.symbol)
            excluded, reason = stock_filter.is_excluded(stock, fund)
            if not excluded:
                clean_symbols.append(stock.symbol)

        # 000002 (ST), 000003 (new stock), 000004 (high pledge) should be excluded
        assert clean_symbols == ["000001"]

        # --- Step 2: Screening ---
        config = _make_strategy_config()
        stocks_data = {
            "000001": _make_stock_data("000001", ma_trend=90.0, close=15.0),
        }
        executor = ScreenExecutor(config, strategy_id=str(uuid.uuid4()))
        result = executor.run_eod_screen(stocks_data)

        assert result.screen_type == ScreenType.EOD
        assert len(result.items) == 1
        assert result.items[0].symbol == "000001"
        assert result.items[0].trend_score >= 0

        # --- Step 3: Risk check ---
        risk_filter = StockRiskFilter()
        daily_change = 3.0  # normal gain
        assert not risk_filter.check_daily_gain(daily_change)

        market_checker = MarketRiskChecker()
        # Normal market (price above MA20 and MA60)
        index_closes = [100.0 + i * 0.5 for i in range(70)]
        risk_level = market_checker.check_market_risk(index_closes)
        threshold = market_checker.get_trend_threshold(risk_level)
        assert result.items[0].trend_score >= 0  # score exists

        # --- Step 4: Alert generation ---
        trading_time = datetime(2024, 1, 15, 10, 30)  # Monday 10:30
        alert_svc = AlertService(now_fn=lambda: trading_time)
        alert_svc.register_threshold(
            "user1",
            AlertConfig(
                user_id="user1",
                alert_type=AlertType.SCREEN_RESULT,
                extra={"trend_score_threshold": 50.0},
            ),
        )

        stock_data_for_alert = {
            "symbol": "000001",
            "trend_score": result.items[0].trend_score,
            "money_flow": 0,
            "breakout_amp": 0,
        }
        alerts = alert_svc.check_and_generate_alerts("user1", stock_data_for_alert)
        assert len(alerts) >= 1
        assert alerts[0].symbol == "000001"

    def test_pipeline_blocks_when_market_danger(self):
        """When market is in DANGER, buy signals should be suspended."""
        market_checker = MarketRiskChecker()
        # Declining market: price well below MA60
        index_closes = [100.0 - i * 0.8 for i in range(70)]
        risk_level = market_checker.check_market_risk(index_closes)
        assert market_checker.is_buy_suspended(risk_level)


# ---------------------------------------------------------------------------
# Pipeline 2: 选股 → 下单 → 持仓同步 → 止损触发
# ---------------------------------------------------------------------------


class TestScreenOrderPositionStopLossPipeline:
    """选股 → 下单 → 持仓同步 → 止损触发全链路测试"""

    def test_screen_to_order_to_position_to_stop_loss(self):
        """
        End-to-end: screen → one-click order → position sync → stop-loss check.

        Steps:
        1. ScreenExecutor produces a ScreenItem
        2. ManualTradeHelper creates an order from the ScreenItem
        3. TradeExecutor submits the order (paper mode, during trading hours)
        4. PositionManager records the position
        5. StopLossChecker detects stop-loss trigger
        """
        # --- Step 1: Screen ---
        config = _make_strategy_config()
        stocks_data = {
            "600001": _make_stock_data("600001", ma_trend=92.0, close=20.0),
        }
        screen_exec = ScreenExecutor(config, strategy_id=str(uuid.uuid4()))
        screen_result = screen_exec.run_eod_screen(stocks_data)
        assert len(screen_result.items) == 1
        item = screen_result.items[0]
        assert item.symbol == "600001"

        # --- Step 2: Create order from screen item ---
        helper = ManualTradeHelper(stop_loss_pct=0.08, take_profit_pct=0.15)
        order_req = helper.create_order_from_screen_item(
            item, OrderType.LIMIT, quantity=100
        )
        assert order_req.symbol == "600001"
        assert order_req.price == item.ref_buy_price
        assert order_req.stop_loss is not None
        assert order_req.take_profit is not None

        # --- Step 3: Submit order (paper mode, trading hours) ---
        trading_time = datetime(2024, 3, 18, 10, 0)  # Monday 10:00
        executor = TradeExecutor(
            mode=TradeMode.PAPER,
            now_fn=lambda: trading_time,
        )
        resp = executor.submit_order(order_req)
        assert resp.order_id != ""
        assert resp.status.value == "FILLED"

        # --- Step 4: Position sync ---
        pos_mgr = PositionManager()
        cost_price = item.ref_buy_price
        current_price = cost_price  # just bought
        total_assets = Decimal("1000000")
        pos = pos_mgr.update_position(
            symbol="600001",
            quantity=100,
            cost_price=cost_price,
            current_price=current_price,
            total_assets=total_assets,
        )
        assert pos.symbol == "600001"
        assert pos.quantity == 100
        assert pos.pnl == Decimal("0")

        # Record trade
        pos_mgr.add_trade_record({
            "time": trading_time,
            "symbol": "600001",
            "action": "BUY",
            "price": float(cost_price),
            "quantity": 100,
        })
        records = pos_mgr.get_trade_records()
        assert len(records) == 1

        # --- Step 5: Stop-loss check ---
        # Price drops 10% → fixed stop-loss at 8% should trigger
        dropped_price = float(cost_price) * 0.90
        triggered = StopLossChecker.check_fixed_stop_loss(
            cost_price=float(cost_price),
            current_price=dropped_price,
            stop_pct=0.08,
        )
        assert triggered is True

    def test_position_limit_blocks_excessive_buy(self):
        """Position risk checker blocks buy when stock weight exceeds 15%."""
        result = PositionRiskChecker.check_stock_position_limit(stock_weight=20.0)
        assert result.passed is False
        assert "超过上限" in result.reason


# ---------------------------------------------------------------------------
# Pipeline 3: 回测 → 参数优化 → 过拟合检测
# ---------------------------------------------------------------------------


class TestBacktestOptimizeOverfitPipeline:
    """回测 → 参数优化 → 过拟合检测全链路测试"""

    def test_backtest_grid_search_overfit_detection(self):
        """
        End-to-end: backtest → grid search → data split → overfit detection.

        Steps:
        1. Run a backtest with known signals
        2. Grid search over parameter combinations
        3. Split data into train/test sets
        4. Detect overfitting between train and test results
        """
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_config=_make_strategy_config(),
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=Decimal("1000000"),
        )

        # --- Step 1: Run backtest with signals ---
        signals = [
            {"date": date(2023, 1, 10), "symbol": "000001", "action": "BUY",
             "price": 10.0, "quantity": 1000},
            {"date": date(2023, 2, 15), "symbol": "000001", "action": "SELL",
             "price": 11.0, "quantity": 1000},
            {"date": date(2023, 3, 10), "symbol": "000002", "action": "BUY",
             "price": 20.0, "quantity": 500},
            {"date": date(2023, 4, 20), "symbol": "000002", "action": "SELL",
             "price": 19.0, "quantity": 500},
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades >= 1
        assert len(result.equity_curve) > 0
        assert result.max_drawdown >= 0

        # --- Step 2: Grid search ---
        def eval_fn(params: dict) -> float:
            """Simulate evaluation: higher ma_short → slightly better score."""
            return params.get("ma_short", 5) * 0.1

        grid_results = GridSearchOptimizer.search(
            param_grid={"ma_short": [5, 10, 20], "ma_long": [60, 120]},
            eval_fn=eval_fn,
        )
        assert len(grid_results) == 6  # 3 × 2 combinations
        # Results sorted descending by score
        assert grid_results[0][1] >= grid_results[-1][1]

        # --- Step 3: Data split ---
        all_signals = list(range(100))
        train, test = DataSplitter.split_train_test(all_signals, train_ratio=0.7)
        assert len(train) == 70
        assert len(test) == 30
        assert set(train) & set(test) == set()  # no overlap

        # --- Step 4: Overfit detection ---
        # Simulate: train return = 30%, test return = 5% → large deviation
        is_overfit, deviation = OverfitDetector.detect(
            train_return=0.30,
            test_return=0.05,
        )
        assert is_overfit is True
        assert deviation > 0.20

        # No overfit case: similar returns
        is_overfit2, deviation2 = OverfitDetector.detect(
            train_return=0.20,
            test_return=0.18,
        )
        assert is_overfit2 is False

    def test_backtest_respects_t_plus_1(self):
        """Backtest engine enforces T+1: same-day buy+sell is rejected."""
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_config=_make_strategy_config(),
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=Decimal("1000000"),
        )
        signals = [
            {"date": date(2023, 3, 1), "symbol": "000001", "action": "BUY",
             "price": 10.0, "quantity": 100},
            # Same day sell → should be skipped by T+1 rule
            {"date": date(2023, 3, 1), "symbol": "000001", "action": "SELL",
             "price": 11.0, "quantity": 100},
        ]
        result = engine.run_backtest(config, signals)
        # Only the BUY should execute; SELL on same day is blocked
        sell_records = [r for r in result.trade_records if r.get("action") == "SELL"]
        assert len(sell_records) == 0
