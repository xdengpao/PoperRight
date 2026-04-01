"""
_precompute_indicators / IndicatorCache 属性测试（Hypothesis）

Property 4: 指标缓存结构不变量
**Validates: Requirements 3.1, 3.2**

Property 5: 条件因子计算
**Validates: Requirements 3.3, 3.4**

Property 6: 预计算一致性
**Validates: Requirement 3.5**
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    BacktestConfig,
    IndicatorParamsConfig,
    KlineBar,
    StrategyConfig,
)
from app.services.backtest_engine import (
    ALL_FACTORS,
    IndicatorCache,
    _precompute_indicators,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# Factor name → IndicatorCache field name mapping
FACTOR_FIELD_MAP: dict[str, str] = {
    "ma_trend": "ma_trend_scores",
    "ma_support": "ma_support_flags",
    "macd": "macd_signals",
    "boll": "boll_signals",
    "rsi": "rsi_signals",
    "dma": "dma_values",
    "breakout": "breakout_results",
}


def _kline_bar_strategy(symbol: str, idx: int) -> st.SearchStrategy[KlineBar]:
    """Generate a single KlineBar with realistic OHLCV data."""
    return st.builds(
        _make_kline_bar,
        symbol=st.just(symbol),
        day_offset=st.just(idx),
        close=st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        spread=st.floats(min_value=0.01, max_value=3.0, allow_nan=False, allow_infinity=False),
        volume=st.integers(min_value=1000, max_value=1_000_000),
        amount=st.floats(min_value=10000.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False),
        turnover=st.floats(min_value=0.1, max_value=30.0, allow_nan=False, allow_infinity=False),
        vol_ratio=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
    )


def _make_kline_bar(
    symbol: str,
    day_offset: int,
    close: float,
    spread: float,
    volume: int,
    amount: float,
    turnover: float,
    vol_ratio: float,
) -> KlineBar:
    """Build a KlineBar from generated values."""
    base_date = datetime(2024, 1, 2, 15, 0, 0)
    bar_time = base_date + timedelta(days=day_offset)
    low = close - spread
    high = close + spread
    open_price = close + (spread * 0.3)  # slightly above close
    return KlineBar(
        time=bar_time,
        symbol=symbol,
        freq="1d",
        open=Decimal(str(round(open_price, 2))),
        high=Decimal(str(round(high, 2))),
        low=Decimal(str(round(max(low, 0.01), 2))),
        close=Decimal(str(round(close, 2))),
        volume=volume,
        amount=Decimal(str(round(amount, 2))),
        turnover=Decimal(str(round(turnover, 4))),
        vol_ratio=Decimal(str(round(vol_ratio, 4))),
    )


@st.composite
def kline_data_strategy(draw: st.DrawFn) -> dict[str, list[KlineBar]]:
    """Generate a small kline_data dict with 1-2 stocks, 5-20 bars each."""
    num_stocks = draw(st.integers(min_value=1, max_value=2))
    symbols = [f"00000{i}.SZ" for i in range(1, num_stocks + 1)]
    result: dict[str, list[KlineBar]] = {}
    for sym in symbols:
        num_bars = draw(st.integers(min_value=5, max_value=20))
        bars = [draw(_kline_bar_strategy(sym, i)) for i in range(num_bars)]
        result[sym] = bars
    return result


# Generate required_factors as a subset of ALL_FACTORS
_required_factors = st.frozensets(
    st.sampled_from(sorted(ALL_FACTORS)),
    min_size=0,
    max_size=7,
).map(set)


def _make_config() -> BacktestConfig:
    """Create a default BacktestConfig for testing."""
    return BacktestConfig(
        strategy_config=StrategyConfig(
            ma_periods=[5, 10, 20],
            indicator_params=IndicatorParamsConfig(),
        ),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )


# ---------------------------------------------------------------------------
# Property 4: 指标缓存结构不变量
# ---------------------------------------------------------------------------


class TestIndicatorCacheStructure:
    """Property 4: 指标缓存结构不变量

    *For any* kline_data and required_factors,
    `_precompute_indicators(kline_data, config, required_factors)` returns dict with:
    - Keys == kline_data keys
    - For each stock: closes, highs, lows, volumes lengths == len(bars)

    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        kline_data=kline_data_strategy(),
        required_factors=_required_factors,
    )
    @settings(max_examples=50, deadline=None)
    def test_cache_keys_match_kline_data_keys(
        self,
        kline_data: dict[str, list[KlineBar]],
        required_factors: set[str],
    ):
        """Cache keys must equal kline_data keys.

        **Validates: Requirements 3.1**
        """
        config = _make_config()
        cache = _precompute_indicators(kline_data, config, required_factors)
        assert set(cache.keys()) == set(kline_data.keys())

    @given(
        kline_data=kline_data_strategy(),
        required_factors=_required_factors,
    )
    @settings(max_examples=50, deadline=None)
    def test_base_sequences_length_equals_bars_length(
        self,
        kline_data: dict[str, list[KlineBar]],
        required_factors: set[str],
    ):
        """closes, highs, lows, volumes must have length == len(bars).

        **Validates: Requirements 3.2**
        """
        config = _make_config()
        cache = _precompute_indicators(kline_data, config, required_factors)
        for symbol, bars in kline_data.items():
            ic = cache[symbol]
            n = len(bars)
            assert len(ic.closes) == n, f"{symbol}: closes len {len(ic.closes)} != {n}"
            assert len(ic.highs) == n, f"{symbol}: highs len {len(ic.highs)} != {n}"
            assert len(ic.lows) == n, f"{symbol}: lows len {len(ic.lows)} != {n}"
            assert len(ic.volumes) == n, f"{symbol}: volumes len {len(ic.volumes)} != {n}"


# ---------------------------------------------------------------------------
# Property 5: 条件因子计算
# ---------------------------------------------------------------------------


class TestConditionalFactorComputation:
    """Property 5: 条件因子计算

    *For any* kline_data, config, and required_factors:
    - If factor_name in required_factors → corresponding field is not None and length == len(bars)
    - If factor_name not in required_factors → corresponding field is None

    **Validates: Requirements 3.3, 3.4**
    """

    @given(
        kline_data=kline_data_strategy(),
        required_factors=_required_factors,
    )
    @settings(max_examples=50, deadline=None)
    def test_active_factors_are_populated(
        self,
        kline_data: dict[str, list[KlineBar]],
        required_factors: set[str],
    ):
        """If factor in required_factors, its cache field must be non-None
        with length == len(bars).

        **Validates: Requirements 3.3**
        """
        config = _make_config()
        cache = _precompute_indicators(kline_data, config, required_factors)
        for symbol, bars in kline_data.items():
            ic = cache[symbol]
            n = len(bars)
            for factor_name, field_name in FACTOR_FIELD_MAP.items():
                if factor_name in required_factors:
                    field_val = getattr(ic, field_name)
                    assert field_val is not None, (
                        f"{symbol}: {field_name} should not be None "
                        f"when '{factor_name}' in required_factors"
                    )
                    assert len(field_val) == n, (
                        f"{symbol}: {field_name} len {len(field_val)} != {n}"
                    )

    @given(
        kline_data=kline_data_strategy(),
        required_factors=_required_factors,
    )
    @settings(max_examples=50, deadline=None)
    def test_inactive_factors_are_none(
        self,
        kline_data: dict[str, list[KlineBar]],
        required_factors: set[str],
    ):
        """If factor not in required_factors, its cache field must be None.

        **Validates: Requirements 3.4**
        """
        config = _make_config()
        cache = _precompute_indicators(kline_data, config, required_factors)
        for symbol in kline_data:
            ic = cache[symbol]
            for factor_name, field_name in FACTOR_FIELD_MAP.items():
                if factor_name not in required_factors:
                    field_val = getattr(ic, field_name)
                    assert field_val is None, (
                        f"{symbol}: {field_name} should be None "
                        f"when '{factor_name}' not in required_factors"
                    )


# ---------------------------------------------------------------------------
# Property 6: 预计算一致性
# ---------------------------------------------------------------------------


@st.composite
def kline_data_with_index(draw: st.DrawFn):
    """Generate kline_data (1 stock, 5-15 bars) plus a random valid index."""
    num_bars = draw(st.integers(min_value=5, max_value=15))
    symbol = "000001.SZ"
    bars = [draw(_kline_bar_strategy(symbol, i)) for i in range(num_bars)]
    idx = draw(st.integers(min_value=0, max_value=num_bars - 1))
    return {symbol: bars}, symbol, idx


class TestPrecomputeConsistency:
    """Property 6: 预计算一致性

    *For any* stock and index position idx, the indicator value at idx in the
    cache should equal the value computed from bars[:idx+1] using the same
    indicator function.

    **Validates: Requirement 3.5**
    """

    @given(data=kline_data_with_index())
    @settings(max_examples=30, deadline=None)
    def test_ma_trend_consistency(
        self,
        data: tuple[dict[str, list[KlineBar]], str, int],
    ):
        """ma_trend_scores[idx] must equal score_ma_trend(closes[:idx+1]).score.

        **Validates: Requirement 3.5**
        """
        from app.services.screener.ma_trend import score_ma_trend

        kline_data, symbol, idx = data
        config = _make_config()
        ma_periods = config.strategy_config.ma_periods

        cache = _precompute_indicators(kline_data, config, {"ma_trend"})
        ic = cache[symbol]

        closes = [float(b.close) for b in kline_data[symbol]]
        fresh_score = score_ma_trend(closes[: idx + 1], ma_periods).score

        assert ic.ma_trend_scores is not None
        assert ic.ma_trend_scores[idx] == fresh_score, (
            f"idx={idx}: cache={ic.ma_trend_scores[idx]}, fresh={fresh_score}"
        )

    @given(data=kline_data_with_index())
    @settings(max_examples=30, deadline=None)
    def test_macd_consistency(
        self,
        data: tuple[dict[str, list[KlineBar]], str, int],
    ):
        """macd_signals[idx] must equal detect_macd_signal(closes[:idx+1]).signal.

        **Validates: Requirement 3.5**
        """
        from app.services.screener.indicators import detect_macd_signal

        kline_data, symbol, idx = data
        config = _make_config()
        ind = config.strategy_config.indicator_params

        cache = _precompute_indicators(kline_data, config, {"macd"})
        ic = cache[symbol]

        closes = [float(b.close) for b in kline_data[symbol]]
        fresh_signal = detect_macd_signal(
            closes[: idx + 1],
            fast_period=ind.macd_fast,
            slow_period=ind.macd_slow,
            signal_period=ind.macd_signal,
        ).signal

        assert ic.macd_signals is not None
        assert ic.macd_signals[idx] == fresh_signal, (
            f"idx={idx}: cache={ic.macd_signals[idx]}, fresh={fresh_signal}"
        )
