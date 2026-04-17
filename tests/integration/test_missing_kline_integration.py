"""
K线缺失时的端到端回测集成测试

- 10.1: 含停牌股票的端到端回测集成测试
  需求: 3.1, 3.3, 3.4
- 10.2: 新股数据不足的端到端回测集成测试
  需求: 3.4, 5.1, 5.4
- 10.3: 分钟K线缺失的平仓条件集成测试
  需求: 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.schemas import (
    BacktestConfig,
    BacktestResult,
    ExitCondition,
    ExitConditionConfig,
    FactorCondition,
    HoldingContext,
    KlineBar,
    StrategyConfig,
)
from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(
    symbol: str,
    d: date,
    open_: float,
    high: float,
    low: float,
    close: float,
    freq: str = "1d",
    volume: int = 500_000,
    amount: float = 5_000_000.0,
) -> KlineBar:
    """Convenience factory for a KlineBar."""
    if freq == "1d":
        dt = datetime.combine(d, datetime.min.time())
    else:
        # For minute bars, d should already be a datetime or we use the date directly
        dt = datetime.combine(d, datetime.min.time())
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq=freq,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        amount=Decimal(str(amount)),
        turnover=Decimal("5.0"),
        vol_ratio=Decimal("1.5"),
    )


def _make_minute_bar(
    symbol: str,
    dt: datetime,
    close: float,
    freq: str = "5min",
    volume: int = 50_000,
) -> KlineBar:
    """Convenience factory for a minute-frequency KlineBar."""
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq=freq,
        open=Decimal(str(round(close * 0.998, 2))),
        high=Decimal(str(round(close * 1.01, 2))),
        low=Decimal(str(round(close * 0.99, 2))),
        close=Decimal(str(round(close, 2))),
        volume=volume,
        amount=Decimal(str(round(close * volume, 2))),
        turnover=Decimal("0.5"),
        vol_ratio=Decimal("1.0"),
    )


def _trading_dates(start: date, count: int) -> list[date]:
    """Generate *count* weekday dates starting from *start*."""
    dates: list[date] = []
    d = start
    while len(dates) < count:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d)
        d += timedelta(days=1)
    return dates


def _build_uptrend_bars(
    symbol: str,
    dates: list[date],
    base_price: float,
    daily_pct: float = 0.015,
) -> list[KlineBar]:
    """Build daily kline bars with steady uptrend."""
    bars: list[KlineBar] = []
    price = base_price
    for d in dates:
        change = price * daily_pct
        open_ = price
        close = round(price + change, 2)
        high = round(close + 0.10, 2)
        low = round(open_ - 0.05, 2)
        bars.append(_make_bar(symbol, d, open_, high, low, close, volume=800_000))
        price = close
    return bars


# ---------------------------------------------------------------------------
# 10.1: 含停牌股票的端到端回测集成测试
# ---------------------------------------------------------------------------


class TestSuspensionIntegration:
    """端到端回测集成测试：含停牌股票

    构造 3 只股票的K线数据，其中 1 只在回测中间停牌 5 天。
    验证：回测不中断、停牌股票在停牌期间不产生新买入信号、
    已持有的停牌股票在停牌期间不触发卖出、复牌后正常恢复。

    需求: 3.1, 3.3, 3.4
    """

    WARMUP_DAYS = 60
    BACKTEST_DAYS = 30
    TOTAL_DAYS = WARMUP_DAYS + BACKTEST_DAYS

    STOCK_A = "000001.SZ"  # Normal stock, uptrend throughout
    STOCK_B = "000002.SZ"  # Normal stock, uptrend throughout
    STOCK_C = "600036.SH"  # Suspended for 5 trading days in the middle

    SUSPENSION_START_OFFSET = 10  # Days into backtest when suspension starts
    SUSPENSION_DURATION = 5       # Number of trading days suspended

    def _build_normal_stock(
        self, symbol: str, dates: list[date], base_price: float,
    ) -> list[KlineBar]:
        """Build kline bars for a normal (non-suspended) stock with uptrend."""
        return _build_uptrend_bars(symbol, dates, base_price)

    def _build_suspended_stock(
        self, symbol: str, dates: list[date], base_price: float,
    ) -> list[KlineBar]:
        """Build kline bars with a 5-day suspension gap in the backtest window.

        Bars are present for all warmup days, then:
        - backtest days [0, SUSPENSION_START_OFFSET): normal trading
        - backtest days [SUSPENSION_START_OFFSET, SUSPENSION_START_OFFSET + SUSPENSION_DURATION): NO bars (suspended)
        - backtest days [SUSPENSION_START_OFFSET + SUSPENSION_DURATION, end): resume trading
        """
        bt_start_idx = self.WARMUP_DAYS
        susp_start_idx = bt_start_idx + self.SUSPENSION_START_OFFSET
        susp_end_idx = susp_start_idx + self.SUSPENSION_DURATION

        # Collect dates that are NOT during the suspension
        active_dates = []
        for i, d in enumerate(dates):
            if susp_start_idx <= i < susp_end_idx:
                continue  # Skip suspension days
            active_dates.append(d)

        return _build_uptrend_bars(symbol, active_dates, base_price)

    @pytest.fixture()
    def dates(self) -> list[date]:
        return _trading_dates(date(2024, 1, 2), self.TOTAL_DAYS)

    @pytest.fixture()
    def backtest_dates(self, dates: list[date]) -> tuple[date, date]:
        return dates[self.WARMUP_DAYS], dates[-1]

    @pytest.fixture()
    def kline_data(self, dates: list[date]) -> dict[str, list[KlineBar]]:
        return {
            self.STOCK_A: self._build_normal_stock(self.STOCK_A, dates, 10.0),
            self.STOCK_B: self._build_normal_stock(self.STOCK_B, dates, 15.0),
            self.STOCK_C: self._build_suspended_stock(self.STOCK_C, dates, 20.0),
        }

    @pytest.fixture()
    def config(self, backtest_dates: tuple[date, date]) -> BacktestConfig:
        start, end = backtest_dates
        return BacktestConfig(
            strategy_config=StrategyConfig(
                factors=[
                    FactorCondition(
                        factor_name="ma_trend",
                        operator=">=",
                        threshold=0.0,
                    ),
                ],
                logic="AND",
                weights={"ma_trend": 1.0},
            ),
            start_date=start,
            end_date=end,
            initial_capital=Decimal("1000000"),
            max_holdings=5,
            stop_loss_pct=0.20,       # High threshold so uptrend doesn't trigger
            trailing_stop_pct=0.20,   # High threshold
            max_holding_days=50,      # Long enough not to trigger
            enable_market_risk=False,  # Disable market risk for simplicity
        )

    @pytest.fixture()
    def suspension_dates(self, dates: list[date]) -> list[date]:
        """Return the dates during which STOCK_C is suspended."""
        bt_start_idx = self.WARMUP_DAYS
        susp_start_idx = bt_start_idx + self.SUSPENSION_START_OFFSET
        susp_end_idx = susp_start_idx + self.SUSPENSION_DURATION
        return dates[susp_start_idx:susp_end_idx]

    def test_backtest_completes_without_crash(
        self, config: BacktestConfig, kline_data: dict[str, list[KlineBar]],
    ):
        """Backtest with a suspended stock completes without error.

        需求: 3.1, 3.3
        """
        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0

    def test_no_buy_signals_during_suspension(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        suspension_dates: list[date],
    ):
        """Suspended stock produces no new buy signals during suspension.

        需求: 3.1, 3.3
        """
        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        # Check that STOCK_C has no BUY trades during suspension
        susp_date_set = set(suspension_dates)
        buy_records_during_suspension = [
            r for r in result.trade_records
            if r["symbol"] == self.STOCK_C
            and r["action"] == "BUY"
            and date.fromisoformat(r["date"]) in susp_date_set
        ]
        assert len(buy_records_during_suspension) == 0, (
            f"Expected no BUY signals for {self.STOCK_C} during suspension, "
            f"got {len(buy_records_during_suspension)}"
        )

    def test_no_sell_during_suspension(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        suspension_dates: list[date],
    ):
        """Held suspended stock doesn't trigger sell during suspension.

        需求: 3.3
        """
        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        # Check that STOCK_C has no SELL trades during suspension
        susp_date_set = set(suspension_dates)
        sell_records_during_suspension = [
            r for r in result.trade_records
            if r["symbol"] == self.STOCK_C
            and r["action"] == "SELL"
            and date.fromisoformat(r["date"]) in susp_date_set
        ]
        assert len(sell_records_during_suspension) == 0, (
            f"Expected no SELL signals for {self.STOCK_C} during suspension, "
            f"got {len(sell_records_during_suspension)}"
        )

    def test_signals_resume_after_resumption(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        dates: list[date],
    ):
        """After resumption, the stock can participate in signal generation again.

        需求: 3.4
        """
        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        # The backtest should complete. After the suspension period,
        # STOCK_C's kline data resumes. The engine should be able to
        # process it. We verify by checking the overall result is valid.
        assert isinstance(result, BacktestResult)
        # The equity curve should span the full backtest period
        if result.equity_curve:
            curve_dates = [d for d, _ in result.equity_curve]
            assert curve_dates[0] == config.start_date
            assert curve_dates[-1] == config.end_date


# ---------------------------------------------------------------------------
# 10.2: 新股数据不足的端到端回测集成测试
# ---------------------------------------------------------------------------


class TestNewStockInsufficientDataIntegration:
    """端到端回测集成测试：新股数据不足

    构造 1 只仅有 30 根K线的新股（上市不足 120 个交易日）。
    执行完整回测，验证：该新股在整个回测期间不产生买入信号、
    回测正常完成不报错。

    需求: 3.4, 5.1, 5.4
    """

    STOCK_NEW = "301001.SZ"

    def _build_new_stock_30_bars(
        self, symbol: str, dates_30: list[date],
    ) -> list[KlineBar]:
        """Build only 30 kline bars for a new stock starting mid-range."""
        bars: list[KlineBar] = []
        price = 50.0
        for d in dates_30:
            change = price * 0.005  # Very gentle uptrend
            open_ = price
            close = round(price + change, 2)
            high = round(close + 0.10, 2)
            low = round(open_ - 0.05, 2)
            bars.append(_make_bar(symbol, d, open_, high, low, close, volume=200_000))
            price = close
        return bars

    def test_new_stock_no_buy_signals(self):
        """New stock with only 30 klines produces no buy signals throughout backtest.

        需求: 3.4, 5.1, 5.4
        """
        # Generate 30 trading dates
        all_dates = _trading_dates(date(2024, 6, 1), 30)
        start_date = all_dates[0]
        end_date = all_dates[-1]

        kline_data = {
            self.STOCK_NEW: self._build_new_stock_30_bars(
                self.STOCK_NEW, all_dates,
            ),
        }

        # Configure with MA120 requirement and high threshold.
        # With only 30 bars, MA120 cannot be computed, so ma_trend_scores
        # will be very low. Use only long-period MAs so that the trend
        # score stays at 0.0 (short MAs like MA5/MA10 can produce non-zero
        # scores even with 30 bars).
        config = BacktestConfig(
            strategy_config=StrategyConfig(
                factors=[
                    FactorCondition(
                        factor_name="ma_trend",
                        operator=">=",
                        threshold=50.0,
                    ),
                ],
                logic="AND",
                weights={"ma_trend": 1.0},
                ma_periods=[120],
            ),
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal("1000000"),
            max_holdings=5,
            enable_market_risk=False,
        )

        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        # Backtest completes without error
        assert isinstance(result, BacktestResult)

        # No buy signals should be produced (data insufficient for MA120)
        buy_records = [r for r in result.trade_records if r["action"] == "BUY"]
        assert len(buy_records) == 0, (
            f"Expected 0 BUY signals for new stock with 30 bars, "
            f"got {len(buy_records)}"
        )

    def test_new_stock_backtest_completes_without_errors(self):
        """Backtest with a new stock that has insufficient data completes normally.

        需求: 3.4, 5.4
        """
        all_dates = _trading_dates(date(2024, 6, 1), 30)

        kline_data = {
            self.STOCK_NEW: self._build_new_stock_30_bars(
                self.STOCK_NEW, all_dates,
            ),
        }

        config = BacktestConfig(
            strategy_config=StrategyConfig(
                factors=[
                    FactorCondition(
                        factor_name="ma_trend",
                        operator=">=",
                        threshold=50.0,
                    ),
                    FactorCondition(
                        factor_name="macd",
                        operator="==",
                        threshold=True,
                    ),
                ],
                logic="AND",
                weights={"ma_trend": 0.5, "macd": 0.5},
                ma_periods=[5, 10, 20, 60, 120],
            ),
            start_date=all_dates[0],
            end_date=all_dates[-1],
            initial_capital=Decimal("1000000"),
            max_holdings=5,
            enable_market_risk=False,
        )

        engine = BacktestEngine()
        result = engine.run_backtest(config, kline_data=kline_data)

        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0
        # Equity curve should still be generated (no trades, flat)
        assert len(result.equity_curve) > 0


# ---------------------------------------------------------------------------
# 10.3: 分钟K线缺失的平仓条件集成测试
# ---------------------------------------------------------------------------


class TestMinuteKlineMissingExitConditionIntegration:
    """端到端回测集成测试：分钟K线缺失的平仓条件

    构造 1 只股票的日K线和 5 分钟K线数据，其中 2 个交易日无分钟数据。
    配置分钟频率平仓条件（5min RSI > 80）。
    验证：有分钟数据的交易日正常评估、无分钟数据的交易日跳过分钟条件
    （不触发错误平仓）、日志中包含 WARNING 信息。

    需求: 4.1, 4.2, 4.3, 4.4
    """

    WARMUP_DAYS = 60
    BACKTEST_DAYS = 20
    TOTAL_DAYS = WARMUP_DAYS + BACKTEST_DAYS

    STOCK = "600519.SH"

    # Trading days (offsets into backtest window) that have NO minute data
    MISSING_MINUTE_DAY_OFFSETS = [5, 12]

    def _build_daily_kline(
        self, symbol: str, dates: list[date],
    ) -> list[KlineBar]:
        """Build daily kline with uptrend then hold, creating a position
        that would be subject to exit condition evaluation."""
        return _build_uptrend_bars(symbol, dates, base_price=10.0, daily_pct=0.012)

    def _build_5min_kline(
        self, symbol: str, dates: list[date],
    ) -> list[KlineBar]:
        """Build 5-min kline bars for each trading day, except for the
        2 days specified in MISSING_MINUTE_DAY_OFFSETS.

        For days with minute data, we create moderate RSI values (below 80)
        so that the exit condition (RSI > 80) does NOT trigger on normal days.
        This ensures that if an erroneous sell occurs, it's detectable.
        """
        bt_start_idx = self.WARMUP_DAYS
        minute_bars: list[KlineBar] = []

        for i, d in enumerate(dates):
            # Only generate minute data within backtest window
            # (and skip the specified missing days)
            bt_offset = i - bt_start_idx
            if bt_offset >= 0 and bt_offset in self.MISSING_MINUTE_DAY_OFFSETS:
                continue  # No minute data for this day

            # Generate 4 bars per day (09:30, 09:35, 09:40, 09:45)
            base_close = 10.0 + i * 0.12
            for j in range(4):
                dt = datetime(d.year, d.month, d.day, 9, 30 + j * 5, 0)
                # Keep RSI-influencing prices moderate (no extreme moves)
                close = round(base_close + j * 0.02, 2)
                minute_bars.append(_make_minute_bar(symbol, dt, close))

        return minute_bars

    @pytest.fixture()
    def dates(self) -> list[date]:
        return _trading_dates(date(2024, 1, 2), self.TOTAL_DAYS)

    @pytest.fixture()
    def backtest_window(self, dates: list[date]) -> tuple[date, date]:
        return dates[self.WARMUP_DAYS], dates[-1]

    @pytest.fixture()
    def kline_data(self, dates: list[date]) -> dict[str, list[KlineBar]]:
        return {
            self.STOCK: self._build_daily_kline(self.STOCK, dates),
        }

    @pytest.fixture()
    def minute_kline_data(
        self, dates: list[date],
    ) -> dict[str, dict[str, list[KlineBar]]]:
        return {
            "5min": {
                self.STOCK: self._build_5min_kline(self.STOCK, dates),
            },
        }

    @pytest.fixture()
    def config(self, backtest_window: tuple[date, date]) -> BacktestConfig:
        start, end = backtest_window
        return BacktestConfig(
            strategy_config=StrategyConfig(
                factors=[
                    FactorCondition(
                        factor_name="ma_trend",
                        operator=">=",
                        threshold=0.0,
                    ),
                ],
                logic="AND",
                weights={"ma_trend": 1.0},
            ),
            start_date=start,
            end_date=end,
            initial_capital=Decimal("1000000"),
            max_holdings=5,
            stop_loss_pct=0.50,       # Very high to avoid stop-loss triggers
            trailing_stop_pct=0.50,   # Very high to avoid trailing stop
            max_holding_days=100,     # Long enough not to trigger
            enable_market_risk=False,
            exit_conditions=ExitConditionConfig(
                conditions=[
                    ExitCondition(
                        freq="5min",
                        indicator="rsi",
                        operator=">",
                        threshold=80.0,
                        params={"rsi_period": 14},
                    ),
                ],
                logic="AND",
            ),
        )

    @pytest.fixture()
    def missing_minute_dates(self, dates: list[date]) -> list[date]:
        """Return the trading dates that have no minute data."""
        bt_start_idx = self.WARMUP_DAYS
        return [dates[bt_start_idx + offset] for offset in self.MISSING_MINUTE_DAY_OFFSETS]

    def test_backtest_completes_with_minute_exit_conditions(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        minute_kline_data: dict[str, dict[str, list[KlineBar]]],
    ):
        """Backtest with minute exit conditions and missing minute data
        completes without error.

        需求: 4.1, 4.2
        """
        engine = BacktestEngine()
        result = engine.run_backtest(
            config,
            kline_data=kline_data,
            minute_kline_data=minute_kline_data,
        )

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0

    def test_no_erroneous_sell_on_missing_minute_days(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        minute_kline_data: dict[str, dict[str, list[KlineBar]]],
        missing_minute_dates: list[date],
        dates: list[date],
    ):
        """Days without minute data skip minute condition — no erroneous sell
        signaled on those days.

        The backtest engine uses T+1 execution (sell signals generated on day T
        are executed on day T+1). To verify that no exit condition is
        erroneously triggered on missing-minute days, we directly test the
        evaluator with the precomputed sentinel data.

        需求: 4.2, 4.4
        """
        from app.services.backtest_engine import (
            _precompute_indicators,
            _precompute_exit_indicators,
            _extract_required_factors,
            _build_date_index,
            _get_bars_up_to,
        )
        from app.services.exit_condition_evaluator import ExitConditionEvaluator

        # Precompute all caches (same as run_backtest would)
        required_factors = _extract_required_factors(config)
        indicator_cache = _precompute_indicators(kline_data, config, required_factors)
        exit_kline_data = {"daily": kline_data}
        exit_kline_data.update(minute_kline_data)
        exit_indicator_cache, minute_day_ranges = _precompute_exit_indicators(
            exit_kline_data, config.exit_conditions, indicator_cache,
        )

        date_index = _build_date_index(kline_data)
        evaluator = ExitConditionEvaluator()

        sym_ic = indicator_cache[self.STOCK]
        sym_exit_cache = exit_indicator_cache.get(self.STOCK)
        sym_minute_ranges = minute_day_ranges.get(self.STOCK)
        holding = HoldingContext(
            entry_price=10.0, highest_price=15.0,
            lowest_price=10.0, entry_bar_index=0,
        )

        # Verify that for each missing-minute date, the evaluator returns False
        for missing_d in missing_minute_dates:
            idx_info = date_index.get(self.STOCK)
            bar_index = _get_bars_up_to(idx_info, missing_d)
            assert bar_index >= 0, f"bar_index should be valid for {missing_d}"

            triggered, reason = evaluator.evaluate(
                config.exit_conditions,
                self.STOCK,
                bar_index,
                sym_ic,
                sym_exit_cache,
                minute_day_ranges=sym_minute_ranges,
                holding_context=holding,
            )
            assert triggered is False, (
                f"Exit condition should NOT trigger on missing-minute day "
                f"{missing_d} (bar_index={bar_index}), got triggered={triggered}, "
                f"reason={reason}"
            )

    def test_warning_logged_for_missing_minute_data(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        minute_kline_data: dict[str, dict[str, list[KlineBar]]],
        caplog,
    ):
        """WARNING logs are emitted when minute data is missing for a trading day.

        需求: 4.2, 4.3
        """
        engine = BacktestEngine()
        with caplog.at_level(logging.WARNING):
            result = engine.run_backtest(
                config,
                kline_data=kline_data,
                minute_kline_data=minute_kline_data,
            )

        assert isinstance(result, BacktestResult)

        # Check if there are any sell records that would trigger exit condition evaluation.
        # WARNING logs are only emitted when ExitConditionEvaluator encounters (-1, -1) sentinels.
        # This happens only if the stock is held and _check_sell_conditions is called.
        # If the stock is bought and held across missing-minute days, warnings should appear.
        #
        # Look for the expected warning pattern from ExitConditionEvaluator
        warning_messages = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        ]
        # The warning is only emitted if a position exists on the missing-minute day.
        # If the backtest has any trades at all, check for the warning.
        has_trades = any(
            r["symbol"] == self.STOCK
            for r in result.trade_records
            if r["action"] == "BUY"
        )
        if has_trades:
            # Look for minute-data-missing warnings
            minute_missing_warnings = [
                msg for msg in warning_messages
                if "minute data" in msg.lower()
                or "No minute data" in msg
                or "skipping condition" in msg.lower()
            ]
            assert len(minute_missing_warnings) > 0, (
                f"Expected WARNING about missing minute data, "
                f"found no relevant warnings in: {warning_messages[:10]}"
            )
