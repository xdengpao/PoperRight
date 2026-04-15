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
        result = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            None,
            {SYMBOL: ic},
        )
        assert result == {}

    def test_empty_conditions(self):
        ic = _make_indicator_cache(CLOSES)
        config = ExitConditionConfig(conditions=[], logic="AND")
        result = _precompute_exit_indicators(
            _daily_kline_data(CLOSES),
            config,
            {SYMBOL: ic},
        )
        assert result == {}


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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
        result = _precompute_exit_indicators(
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
