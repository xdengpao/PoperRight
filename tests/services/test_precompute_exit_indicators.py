"""
Unit tests for _precompute_exit_indicators() in backtest_engine.py.

Tests Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 13.1, 13.2
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.schemas import (
    ExitCondition,
    ExitConditionConfig,
    KlineBar,
)
from app.services.backtest_engine import (
    IndicatorCache,
    _precompute_exit_indicators,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kline_bar(close: float, symbol: str = "000001.SZ") -> KlineBar:
    return KlineBar(
        time=datetime(2024, 1, 1),
        symbol=symbol,
        freq="daily",
        open=Decimal(str(close)),
        high=Decimal(str(close * 1.02)),
        low=Decimal(str(close * 0.98)),
        close=Decimal(str(close)),
        volume=100000,
        amount=Decimal("1000000"),
        turnover=Decimal("3.5"),
        vol_ratio=Decimal("1.2"),
    )


def _make_indicator_cache(closes: list[float]) -> IndicatorCache:
    n = len(closes)
    return IndicatorCache(
        closes=closes,
        highs=[c * 1.02 for c in closes],
        lows=[c * 0.98 for c in closes],
        volumes=[100000] * n,
        amounts=[Decimal("1000000")] * n,
        turnovers=[Decimal("3.5")] * n,
    )


def _daily_kline_data(
    closes: list[float], symbol: str = "000001.SZ",
) -> dict[str, dict[str, list[KlineBar]]]:
    """Build freq-grouped kline_data with daily bars for a single symbol."""
    return {"daily": {symbol: [_make_kline_bar(c, symbol) for c in closes]}}


SYMBOL = "000001.SZ"
# Generate 60 bars of close prices for sufficient indicator data
CLOSES = [10.0 + 0.1 * i for i in range(60)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPrecomputeExitIndicatorsNone:
    """When exit_config is None or empty, return empty dict."""

    def test_none_config(self):
        ic = _make_indicator_cache(CLOSES)
        result, minute_day_ranges = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            None,
            {SYMBOL: ic},
        )
        assert result == {}
        assert minute_day_ranges == {}

    def test_empty_conditions(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(conditions=[], logic="AND")
        result, minute_day_ranges = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        assert result == {}
        assert minute_day_ranges == {}


class TestPrecomputeMA:
    """MA indicator with custom period."""

    def test_ma_custom_period(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="ma",
                    operator="<",
                    threshold=15.0,
                    params={"period": 10},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        assert SYMBOL in result
        assert "daily" in result[SYMBOL]
        assert "ma_10" in result[SYMBOL]["daily"]
        values = result[SYMBOL]["daily"]["ma_10"]
        assert len(values) == len(CLOSES)
        # First 9 values should be NaN
        for i in range(9):
            assert math.isnan(values[i])
        # 10th value should be the average of first 10 closes
        expected = sum(CLOSES[:10]) / 10
        assert abs(values[9] - expected) < 1e-9

    def test_ma_multiple_periods(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="ma", operator=">",
                    threshold=10.0, params={"period": 5},
                ),
                ExitCondition(
                    freq="daily", indicator="ma", operator="<",
                    threshold=20.0, params={"period": 20},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym_daily = result[SYMBOL]["daily"]
        assert "ma_5" in sym_daily
        assert "ma_20" in sym_daily


class TestPrecomputeMACD:
    """MACD indicators with custom and default params."""

    def test_macd_default_params(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator=">",
                    threshold=0.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        # Default params: should have both suffixed and unsuffixed keys
        assert "macd_dif_12_26_9" in sym
        assert "macd_dif" in sym
        assert "macd_dea_12_26_9" in sym
        assert "macd_dea" in sym
        assert "macd_histogram_12_26_9" in sym
        assert "macd_histogram" in sym
        assert len(sym["macd_dif"]) == len(CLOSES)

    def test_macd_custom_params(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator=">",
                    threshold=0.0,
                    params={"macd_fast": 8, "macd_slow": 21, "macd_signal": 5},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "macd_dif_8_21_5" in sym
        assert "macd_dea_8_21_5" in sym
        assert "macd_histogram_8_21_5" in sym
        # Default params also included since macd_dif is referenced
        assert "macd_dif_12_26_9" in sym
        assert "macd_dif" in sym


class TestPrecomputeBOLL:
    """BOLL indicators with custom and default params."""

    def test_boll_default_params(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="boll_upper", operator="<",
                    threshold=20.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "boll_upper_20_2.0" in sym
        assert "boll_upper" in sym
        assert "boll_middle_20_2.0" in sym
        assert "boll_middle" in sym
        assert "boll_lower_20_2.0" in sym
        assert "boll_lower" in sym

    def test_boll_custom_params(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="boll_lower", operator=">",
                    threshold=5.0,
                    params={"boll_period": 15, "boll_std_dev": 1.5},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "boll_lower_15_1.5" in sym
        # Default also included
        assert "boll_lower_20_2.0" in sym
        assert "boll_lower" in sym


class TestPrecomputeRSI:
    """RSI indicator with custom and default period."""

    def test_rsi_custom_period(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="rsi", operator=">",
                    threshold=80.0,
                    params={"rsi_period": 7},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "rsi_7" in sym
        # Default also included
        assert "rsi_14" in sym
        assert "rsi" in sym
        assert len(sym["rsi_7"]) == len(CLOSES)

    def test_rsi_default_period(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="rsi", operator=">",
                    threshold=80.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "rsi_14" in sym
        assert "rsi" in sym


class TestPrecomputeDMA:
    """DMA/AMA indicators with custom and default params."""

    def test_dma_custom_params(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="dma", operator=">",
                    threshold=0.0,
                    params={"dma_short": 5, "dma_long": 30},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "dma_5_30" in sym
        assert "ama_5_30" in sym
        # Default also included
        assert "dma_10_50" in sym
        assert "dma" in sym
        assert "ama_10_50" in sym
        assert "ama" in sym

    def test_ama_indicator(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="ama", operator="<",
                    threshold=0.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        assert "dma_10_50" in sym
        assert "ama_10_50" in sym
        assert "dma" in sym
        assert "ama" in sym


class TestPrecomputeCrossTarget:
    """Cross conditions should also precompute the cross_target indicator."""

    def test_cross_target_precomputed(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="macd_dif",
                    operator="cross_down",
                    cross_target="macd_dea",
                    params={"macd_fast": 8, "macd_slow": 21, "macd_signal": 5},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        sym = result[SYMBOL]["daily"]
        # Both dif and dea should be precomputed with custom params
        assert "macd_dif_8_21_5" in sym
        assert "macd_dea_8_21_5" in sym


class TestPrecomputeMultipleSymbols:
    """Cache should be per-symbol."""

    def test_multiple_symbols(self):
        sym1 = "000001.SZ"
        sym2 = "600519.SH"
        closes1 = CLOSES
        closes2 = [20.0 + 0.2 * i for i in range(60)]
        ic1 = _make_indicator_cache(closes1)
        ic2 = _make_indicator_cache(closes2)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="rsi", operator=">",
                    threshold=80.0, params={"rsi_period": 7},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            {
                "daily": {
                    sym1: [_make_kline_bar(c, sym1) for c in closes1],
                    sym2: [_make_kline_bar(c, sym2) for c in closes2],
                },
            },
            config,
            {sym1: ic1, sym2: ic2},
        )
        assert sym1 in result
        assert sym2 in result
        assert "rsi_7" in result[sym1]["daily"]
        assert "rsi_7" in result[sym2]["daily"]
        # Values should differ between symbols
        assert result[sym1]["daily"]["rsi_7"] != result[sym2]["daily"]["rsi_7"]


class TestPrecomputeNonIndicatorConditions:
    """Conditions referencing close/volume/turnover should not add to cache."""

    def test_close_only_no_cache(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="close", operator=">",
                    threshold=15.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        # close/volume/turnover are read directly from IndicatorCache,
        # no exit_indicator_cache entries needed
        assert result == {}


class TestPrecomputeMinuteFreq:
    """Minute frequency kline data should use kline_data[freq] (Req 13.1)."""

    def test_5min_freq_uses_minute_kline_data(self):
        """5min freq conditions should compute from kline_data['5min']."""
        ic = _make_indicator_cache(CLOSES)
        min_closes = [10.0 + 0.05 * i for i in range(120)]
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="rsi", operator=">",
                    threshold=80.0,
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            {
                "daily": {SYMBOL: [_make_kline_bar(c) for c in CLOSES]},
                "5min": {SYMBOL: [_make_kline_bar(c) for c in min_closes]},
            },
            config,
            {SYMBOL: ic},
        )
        assert SYMBOL in result
        assert "5min" in result[SYMBOL]
        assert "rsi_14" in result[SYMBOL]["5min"]
        assert "rsi" in result[SYMBOL]["5min"]
        # Length should match minute data, not daily
        assert len(result[SYMBOL]["5min"]["rsi_14"]) == len(min_closes)

    def test_minute_freq_migration(self):
        """Legacy 'minute' freq should be mapped to '1min'."""
        ic = _make_indicator_cache(CLOSES)
        min_closes = [10.0 + 0.05 * i for i in range(120)]
        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="1min", indicator="ma", operator=">",
                    threshold=10.0, params={"period": 5},
                ),
            ],
        )
        result, _ = _precompute_exit_indicators(
            {
                "daily": {SYMBOL: [_make_kline_bar(c) for c in CLOSES]},
                "1min": {SYMBOL: [_make_kline_bar(c) for c in min_closes]},
            },
            config,
            {SYMBOL: ic},
        )
        assert SYMBOL in result
        assert "1min" in result[SYMBOL]
        assert "ma_5" in result[SYMBOL]["1min"]


# ---------------------------------------------------------------------------
# Tests for _build_minute_day_ranges()
# ---------------------------------------------------------------------------

from app.services.backtest_engine import _build_minute_day_ranges
from datetime import date, timedelta


def _make_minute_bar(
    dt: datetime,
    close: float,
    symbol: str = "000001.SZ",
    freq: str = "5min",
) -> KlineBar:
    """Create a minute KlineBar with a specific datetime."""
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq=freq,
        open=Decimal(str(close)),
        high=Decimal(str(close * 1.02)),
        low=Decimal(str(close * 0.98)),
        close=Decimal(str(close)),
        volume=100000,
        amount=Decimal("1000000"),
        turnover=Decimal("3.5"),
        vol_ratio=Decimal("1.2"),
    )


def _make_daily_bar(
    d: date,
    close: float,
    symbol: str = "000001.SZ",
) -> KlineBar:
    """Create a daily KlineBar for a specific date."""
    return KlineBar(
        time=datetime(d.year, d.month, d.day, 15, 0, 0),
        symbol=symbol,
        freq="daily",
        open=Decimal(str(close)),
        high=Decimal(str(close * 1.02)),
        low=Decimal(str(close * 0.98)),
        close=Decimal(str(close)),
        volume=100000,
        amount=Decimal("1000000"),
        turnover=Decimal("3.5"),
        vol_ratio=Decimal("1.2"),
    )


class TestBuildMinuteDayRanges:
    """Unit tests for _build_minute_day_ranges() helper function."""

    def test_basic_5min_two_days(self):
        """Two trading days with 48 bars each (5min frequency)."""
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 3)
        symbol = SYMBOL

        # Daily bars
        daily_bars = [
            _make_daily_bar(d1, 10.0, symbol),
            _make_daily_bar(d2, 11.0, symbol),
        ]

        # 5min bars: 48 per day (9:30-15:00, 4 hours = 240 min / 5 = 48)
        minute_bars = []
        for day_idx, d in enumerate([d1, d2]):
            for i in range(48):
                hour = 9 + (30 + i * 5) // 60
                minute = (30 + i * 5) % 60
                dt = datetime(d.year, d.month, d.day, hour, minute, 0)
                minute_bars.append(
                    _make_minute_bar(dt, 10.0 + day_idx + i * 0.01, symbol, "5min")
                )

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0, 11.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)

        assert symbol in result
        assert "5min" in result[symbol]
        ranges = result[symbol]["5min"]
        assert len(ranges) == 2  # Two trading days
        assert ranges[0] == (0, 47)   # Day 1: indices 0-47
        assert ranges[1] == (48, 95)  # Day 2: indices 48-95

    def test_varying_bars_per_day(self):
        """Days with different numbers of minute bars."""
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 3)
        d3 = date(2024, 1, 4)
        symbol = SYMBOL

        daily_bars = [
            _make_daily_bar(d1, 10.0, symbol),
            _make_daily_bar(d2, 11.0, symbol),
            _make_daily_bar(d3, 12.0, symbol),
        ]

        # Day 1: 10 bars, Day 2: 5 bars, Day 3: 8 bars
        minute_bars = []
        for i in range(10):
            total_min = 30 + i * 5
            dt = datetime(2024, 1, 2, 9 + total_min // 60, total_min % 60, 0)
            minute_bars.append(_make_minute_bar(dt, 10.0, symbol))
        for i in range(5):
            total_min = 30 + i * 5
            dt = datetime(2024, 1, 3, 9 + total_min // 60, total_min % 60, 0)
            minute_bars.append(_make_minute_bar(dt, 11.0, symbol))
        for i in range(8):
            total_min = 30 + i * 5
            dt = datetime(2024, 1, 4, 9 + total_min // 60, total_min % 60, 0)
            minute_bars.append(_make_minute_bar(dt, 12.0, symbol))

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0, 11.0, 12.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        ranges = result[symbol]["5min"]

        assert len(ranges) == 3
        assert ranges[0] == (0, 9)    # Day 1: 10 bars
        assert ranges[1] == (10, 14)  # Day 2: 5 bars
        assert ranges[2] == (15, 22)  # Day 3: 8 bars

    def test_missing_minute_data_for_some_days(self):
        """Some trading days have no minute data (e.g., suspension)."""
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 3)  # No minute data
        d3 = date(2024, 1, 4)
        symbol = SYMBOL

        daily_bars = [
            _make_daily_bar(d1, 10.0, symbol),
            _make_daily_bar(d2, 11.0, symbol),
            _make_daily_bar(d3, 12.0, symbol),
        ]

        # Only day 1 and day 3 have minute bars
        minute_bars = []
        for i in range(5):
            dt = datetime(2024, 1, 2, 9, 30 + i * 5, 0)
            minute_bars.append(_make_minute_bar(dt, 10.0, symbol))
        for i in range(5):
            dt = datetime(2024, 1, 4, 9, 30 + i * 5, 0)
            minute_bars.append(_make_minute_bar(dt, 12.0, symbol))

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0, 11.0, 12.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        ranges = result[symbol]["5min"]

        assert len(ranges) == 3
        assert ranges[0] == (0, 4)     # Day 1: 5 bars
        assert ranges[1] == (-1, -1)   # Day 2: no minute data
        assert ranges[2] == (5, 9)     # Day 3: 5 bars

    def test_single_bar_day(self):
        """A trading day with only one minute bar."""
        d1 = date(2024, 1, 2)
        symbol = SYMBOL

        daily_bars = [_make_daily_bar(d1, 10.0, symbol)]
        minute_bars = [
            _make_minute_bar(datetime(2024, 1, 2, 9, 30, 0), 10.0, symbol),
        ]

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        ranges = result[symbol]["5min"]

        assert len(ranges) == 1
        assert ranges[0] == (0, 0)  # Single bar: start == end

    def test_empty_minute_data(self):
        """Empty minute bar list produces no ranges."""
        symbol = SYMBOL
        daily_bars = [_make_daily_bar(date(2024, 1, 2), 10.0, symbol)]

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: []},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        # Empty bars → symbol not in result
        assert symbol not in result

    def test_no_daily_data_for_symbol(self):
        """Symbol has minute data but no daily data → skipped with warning."""
        symbol = SYMBOL
        minute_bars = [
            _make_minute_bar(datetime(2024, 1, 2, 9, 30, 0), 10.0, symbol),
        ]

        kline_data = {
            "daily": {},  # No daily data
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        assert symbol not in result

    def test_multiple_minute_frequencies(self):
        """Both 1min and 5min frequencies produce separate ranges."""
        d1 = date(2024, 1, 2)
        symbol = SYMBOL

        daily_bars = [_make_daily_bar(d1, 10.0, symbol)]

        # 5min: 3 bars
        bars_5min = []
        for i in range(3):
            dt = datetime(2024, 1, 2, 9, 30 + i * 5, 0)
            bars_5min.append(_make_minute_bar(dt, 10.0, symbol, "5min"))

        # 1min: 10 bars
        bars_1min = []
        for i in range(10):
            dt = datetime(2024, 1, 2, 9, 30 + i, 0)
            bars_1min.append(_make_minute_bar(dt, 10.0, symbol, "1min"))

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: bars_5min},
            "1min": {symbol: bars_1min},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)

        assert "5min" in result[symbol]
        assert "1min" in result[symbol]
        assert result[symbol]["5min"] == [(0, 2)]
        assert result[symbol]["1min"] == [(0, 9)]

    def test_multiple_symbols(self):
        """Multiple symbols each get their own ranges."""
        d1 = date(2024, 1, 2)
        sym1 = "000001.SZ"
        sym2 = "600519.SH"

        daily_bars_1 = [_make_daily_bar(d1, 10.0, sym1)]
        daily_bars_2 = [_make_daily_bar(d1, 20.0, sym2)]

        minute_bars_1 = [
            _make_minute_bar(datetime(2024, 1, 2, 9, 30 + i * 5, 0), 10.0, sym1)
            for i in range(4)
        ]
        minute_bars_2 = [
            _make_minute_bar(datetime(2024, 1, 2, 9, 30 + i * 5, 0), 20.0, sym2)
            for i in range(6)
        ]

        kline_data = {
            "daily": {sym1: daily_bars_1, sym2: daily_bars_2},
            "5min": {sym1: minute_bars_1, sym2: minute_bars_2},
        }
        existing_cache = {
            sym1: _make_indicator_cache([10.0]),
            sym2: _make_indicator_cache([20.0]),
        }

        result = _build_minute_day_ranges(kline_data, existing_cache)

        assert result[sym1]["5min"] == [(0, 3)]
        assert result[sym2]["5min"] == [(0, 5)]

    def test_daily_only_returns_empty(self):
        """When kline_data has only 'daily' freq, result is empty."""
        symbol = SYMBOL
        daily_bars = [_make_daily_bar(date(2024, 1, 2), 10.0, symbol)]

        kline_data = {"daily": {symbol: daily_bars}}
        existing_cache = {symbol: _make_indicator_cache([10.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        assert result == {}

    def test_ranges_are_contiguous_and_non_overlapping(self):
        """Ranges for consecutive days are contiguous and non-overlapping."""
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 3)
        d3 = date(2024, 1, 4)
        symbol = SYMBOL

        daily_bars = [
            _make_daily_bar(d, 10.0 + i, symbol)
            for i, d in enumerate([d1, d2, d3])
        ]

        # 20 bars per day
        minute_bars = []
        for d in [d1, d2, d3]:
            for i in range(20):
                dt = datetime(d.year, d.month, d.day, 9, 30 + i, 0)
                minute_bars.append(_make_minute_bar(dt, 10.0, symbol, "1min"))

        kline_data = {
            "daily": {symbol: daily_bars},
            "1min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0, 11.0, 12.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        ranges = result[symbol]["1min"]

        assert len(ranges) == 3
        # Check contiguous: end of day i + 1 == start of day i+1
        for i in range(len(ranges) - 1):
            assert ranges[i][1] + 1 == ranges[i + 1][0], (
                f"Ranges not contiguous: {ranges[i]} and {ranges[i + 1]}"
            )
        # Check non-overlapping: start <= end for each
        for start, end in ranges:
            assert start <= end
        # Check total coverage
        total_bars = sum(end - start + 1 for start, end in ranges)
        assert total_bars == 60  # 3 days × 20 bars

    def test_alignment_with_daily_date_order(self):
        """Minute ranges align with daily K-line date order, not minute data order."""
        # Daily has dates: Jan 2, Jan 3, Jan 4
        # Minute data only has Jan 2 and Jan 4 (Jan 3 missing)
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 3)
        d3 = date(2024, 1, 4)
        symbol = SYMBOL

        daily_bars = [
            _make_daily_bar(d1, 10.0, symbol),
            _make_daily_bar(d2, 11.0, symbol),
            _make_daily_bar(d3, 12.0, symbol),
        ]

        minute_bars = []
        for i in range(5):
            dt = datetime(2024, 1, 2, 9, 30 + i * 5, 0)
            minute_bars.append(_make_minute_bar(dt, 10.0, symbol))
        for i in range(5):
            dt = datetime(2024, 1, 4, 9, 30 + i * 5, 0)
            minute_bars.append(_make_minute_bar(dt, 12.0, symbol))

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache = {symbol: _make_indicator_cache([10.0, 11.0, 12.0])}

        result = _build_minute_day_ranges(kline_data, existing_cache)
        ranges = result[symbol]["5min"]

        # bar_index=0 (Jan 2) → (0, 4)
        # bar_index=1 (Jan 3) → (-1, -1) missing
        # bar_index=2 (Jan 4) → (5, 9)
        assert ranges[0] == (0, 4)
        assert ranges[1] == (-1, -1)
        assert ranges[2] == (5, 9)
