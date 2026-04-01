"""
优化前后信号生成等价性集成测试

Property 10: 优化前后信号生成等价性
*For any* config, kline_data, and trade_date, the optimized
`_generate_buy_signals_optimized` should produce the same ScreenItem list
(sorted by symbol) as the original `_generate_buy_signals`.

**Validates: Requirements 5.1, 5.2**
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.schemas import (
    BacktestConfig,
    KlineBar,
    ScreenItem,
    StrategyConfig,
)
from app.services.backtest_engine import (
    BacktestEngine,
    _build_date_index,
    _extract_required_factors,
    _precompute_indicators,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trading_dates(start: date, count: int) -> list[date]:
    """Generate *count* weekday dates starting from *start*."""
    dates: list[date] = []
    d = start
    while len(dates) < count:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return dates


def _make_bar(
    symbol: str,
    d: date,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 500_000,
    amount: float = 5_000_000.0,
    turnover: float = 3.0,
) -> KlineBar:
    return KlineBar(
        time=datetime.combine(d, datetime.min.time()),
        symbol=symbol,
        freq="1d",
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        amount=Decimal(str(amount)),
        turnover=Decimal(str(turnover)),
        vol_ratio=Decimal("1.2"),
    )


def _build_uptrend_bars(
    symbol: str,
    dates: list[date],
    base_price: float,
    daily_pct: float = 0.008,
) -> list[KlineBar]:
    """Build a gentle uptrend series for a stock."""
    bars: list[KlineBar] = []
    price = base_price
    for d in dates:
        change = price * daily_pct
        open_ = round(price, 2)
        close = round(price + change, 2)
        high = round(close + 0.15, 2)
        low = round(open_ - 0.10, 2)
        vol = 600_000 + (hash(d.isoformat()) % 400_000)
        amt = round(close * vol, 2)
        bars.append(_make_bar(symbol, d, open_, high, low, close,
                              volume=vol, amount=amt))
        price = close
    return bars


def _build_sideways_bars(
    symbol: str,
    dates: list[date],
    base_price: float,
) -> list[KlineBar]:
    """Build a sideways (oscillating) series for a stock."""
    bars: list[KlineBar] = []
    price = base_price
    rng = random.Random(42)
    for d in dates:
        change = price * rng.uniform(-0.01, 0.01)
        open_ = round(price, 2)
        close = round(price + change, 2)
        high = round(max(open_, close) + 0.20, 2)
        low = round(min(open_, close) - 0.15, 2)
        vol = 400_000 + rng.randint(0, 300_000)
        amt = round(close * vol, 2)
        bars.append(_make_bar(symbol, d, open_, high, low, close,
                              volume=vol, amount=amt))
        price = close
    return bars


def _compare_screen_items(
    old_items: list[ScreenItem],
    new_items: list[ScreenItem],
    label: str,
) -> None:
    """Sort both lists by symbol and compare symbol + trend_score."""
    old_sorted = sorted(old_items, key=lambda x: x.symbol)
    new_sorted = sorted(new_items, key=lambda x: x.symbol)

    old_symbols = [it.symbol for it in old_sorted]
    new_symbols = [it.symbol for it in new_sorted]
    assert old_symbols == new_symbols, (
        f"[{label}] Symbol mismatch: old={old_symbols}, new={new_symbols}"
    )

    for o, n in zip(old_sorted, new_sorted):
        assert o.symbol == n.symbol
        assert abs(o.trend_score - n.trend_score) < 1e-9, (
            f"[{label}] trend_score mismatch for {o.symbol}: "
            f"old={o.trend_score}, new={n.trend_score}"
        )
        assert o.risk_level == n.risk_level, (
            f"[{label}] risk_level mismatch for {o.symbol}: "
            f"old={o.risk_level}, new={n.risk_level}"
        )
        assert o.ref_buy_price == n.ref_buy_price, (
            f"[{label}] ref_buy_price mismatch for {o.symbol}: "
            f"old={o.ref_buy_price}, new={n.ref_buy_price}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYMBOLS = ["SH600000", "SZ000001", "SH601318", "SZ300750"]
NUM_BARS = 45  # enough for MA indicators to have meaningful values


@pytest.fixture()
def dates() -> list[date]:
    return _trading_dates(date(2024, 1, 2), NUM_BARS)


@pytest.fixture()
def kline_data(dates: list[date]) -> dict[str, list[KlineBar]]:
    return {
        "SH600000": _build_uptrend_bars("SH600000", dates, base_price=12.0),
        "SZ000001": _build_uptrend_bars("SZ000001", dates, base_price=18.0,
                                         daily_pct=0.012),
        "SH601318": _build_sideways_bars("SH601318", dates, base_price=55.0),
        "SZ300750": _build_uptrend_bars("SZ300750", dates, base_price=30.0,
                                         daily_pct=0.006),
    }


@pytest.fixture()
def config() -> BacktestConfig:
    """Default config with factors=[] (all factors) for maximum coverage."""
    return BacktestConfig(
        strategy_config=StrategyConfig(factors=[], logic="AND"),
        start_date=date(2024, 1, 2),
        end_date=date(2024, 3, 29),
        initial_capital=Decimal("1000000"),
    )


# ---------------------------------------------------------------------------
# Property 10: 优化前后信号生成等价性
# ---------------------------------------------------------------------------

class TestSignalEquivalence:
    """Property 10: 优化前后信号生成等价性

    For several trade_dates within the data range, the optimized
    `_generate_buy_signals_optimized` produces the same ScreenItem list
    (sorted by symbol) as the original `_generate_buy_signals`.

    **Validates: Requirements 5.1, 5.2**
    """

    def test_equivalence_across_multiple_dates(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        dates: list[date],
    ):
        """Old and new signal generation must produce identical results
        for every sampled trade_date.

        **Validates: Requirements 5.1, 5.2**
        """
        engine = BacktestEngine()

        # Pre-compute optimized structures
        required_factors = _extract_required_factors(config)
        date_index = _build_date_index(kline_data)
        indicator_cache = _precompute_indicators(
            kline_data, config, required_factors,
        )

        # Sample trade dates: pick several dates spread across the range
        # Skip the first 20 bars so indicators have enough history
        test_dates = [dates[i] for i in (20, 25, 30, 35, 40, 44)]

        for td in test_dates:
            old_result = engine._generate_buy_signals(
                td, kline_data, config, "NORMAL",
            )
            new_result = engine._generate_buy_signals_optimized(
                td, kline_data, config, "NORMAL",
                indicator_cache, date_index, required_factors,
            )
            _compare_screen_items(old_result, new_result, label=str(td))

    def test_equivalence_with_caution_state(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        dates: list[date],
    ):
        """Both methods should apply the same CAUTION filtering (score >= 90).

        **Validates: Requirements 5.1, 5.2**
        """
        engine = BacktestEngine()

        required_factors = _extract_required_factors(config)
        date_index = _build_date_index(kline_data)
        indicator_cache = _precompute_indicators(
            kline_data, config, required_factors,
        )

        test_dates = [dates[25], dates[35]]

        for td in test_dates:
            old_result = engine._generate_buy_signals(
                td, kline_data, config, "CAUTION",
            )
            new_result = engine._generate_buy_signals_optimized(
                td, kline_data, config, "CAUTION",
                indicator_cache, date_index, required_factors,
            )
            _compare_screen_items(old_result, new_result, label=f"CAUTION-{td}")

    def test_equivalence_with_danger_state(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        dates: list[date],
    ):
        """Both methods should return empty list under DANGER state.

        **Validates: Requirements 5.1, 5.2**
        """
        engine = BacktestEngine()

        required_factors = _extract_required_factors(config)
        date_index = _build_date_index(kline_data)
        indicator_cache = _precompute_indicators(
            kline_data, config, required_factors,
        )

        td = dates[30]
        old_result = engine._generate_buy_signals(
            td, kline_data, config, "DANGER",
        )
        new_result = engine._generate_buy_signals_optimized(
            td, kline_data, config, "DANGER",
            indicator_cache, date_index, required_factors,
        )
        assert old_result == []
        assert new_result == []

    def test_equivalence_with_specific_factors(
        self,
        kline_data: dict[str, list[KlineBar]],
        dates: list[date],
    ):
        """When strategy specifies specific factors, both methods agree.

        **Validates: Requirements 5.1, 5.2**
        """
        from app.core.schemas import FactorCondition

        config_specific = BacktestConfig(
            strategy_config=StrategyConfig(
                factors=[
                    FactorCondition(factor_name="ma_trend", operator=">=",
                                    threshold=0.0),
                    FactorCondition(factor_name="macd", operator="==",
                                    threshold=None),
                ],
                logic="AND",
            ),
            start_date=date(2024, 1, 2),
            end_date=date(2024, 3, 29),
            initial_capital=Decimal("1000000"),
        )

        engine = BacktestEngine()
        required_factors = _extract_required_factors(config_specific)
        date_index = _build_date_index(kline_data)
        indicator_cache = _precompute_indicators(
            kline_data, config_specific, required_factors,
        )

        test_dates = [dates[25], dates[35], dates[40]]

        for td in test_dates:
            old_result = engine._generate_buy_signals(
                td, kline_data, config_specific, "NORMAL",
            )
            new_result = engine._generate_buy_signals_optimized(
                td, kline_data, config_specific, "NORMAL",
                indicator_cache, date_index, required_factors,
            )
            _compare_screen_items(
                old_result, new_result, label=f"specific-{td}",
            )
