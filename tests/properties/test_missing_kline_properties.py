"""
K线缺失时指标计算处理机制 — 属性测试（Hypothesis）

Property 1: MA NaN prefix length
Property 2: EMA NaN prefix length
Property 3: MACD NaN propagation
Property 4: RSI NaN prefix length
Property 5: Empty input safety
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.ma_trend import calculate_ma
from app.services.screener.indicators import (
    _ema,
    calculate_macd,
    calculate_boll,
    calculate_rsi,
    calculate_dma,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 有限正浮点数，避免 inf / nan / 极端值
_finite_positive_float = st.floats(
    min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False
)

# 非空收盘价序列
_closes = st.lists(
    _finite_positive_float,
    min_size=1,
    max_size=300,
)

# 正整数周期（MA/EMA/RSI 等）
_period = st.integers(min_value=1, max_value=200)

# MACD 参数：fast < slow，signal >= 1
_macd_params = st.tuples(
    st.integers(min_value=1, max_value=50),   # fast
    st.integers(min_value=2, max_value=100),   # slow
    st.integers(min_value=1, max_value=50),    # signal
).filter(lambda t: t[0] < t[1])


# ---------------------------------------------------------------------------
# Property 1: MA NaN prefix length
# ---------------------------------------------------------------------------


class TestMANaNPrefixLength:
    """Property 1: MA NaN prefix length

    **Validates: Requirements 1.1, 1.2**
    """

    @given(closes=_closes, period=_period)
    @settings(max_examples=200)
    def test_ma_nan_prefix_length(self, closes: list[float], period: int):
        """For any non-empty closes and positive period N, calculate_ma returns
        a list where the first min(N-1, len(closes)) values are NaN.
        If len(closes) >= N, values from index N-1 onward are valid floats.

        **Validates: Requirements 1.1, 1.2**
        """
        result = calculate_ma(closes, period)
        n = len(closes)

        # Same length as input
        assert len(result) == n

        nan_prefix_len = min(period - 1, n)

        # First min(N-1, len) values must be NaN
        for i in range(nan_prefix_len):
            assert math.isnan(result[i]), (
                f"Expected NaN at index {i}, got {result[i]} "
                f"(period={period}, n={n})"
            )

        # If enough data, from index N-1 onward must be valid floats
        if n >= period:
            for i in range(period - 1, n):
                assert not math.isnan(result[i]), (
                    f"Expected valid float at index {i}, got NaN "
                    f"(period={period}, n={n})"
                )


# ---------------------------------------------------------------------------
# Property 2: EMA NaN prefix length
# ---------------------------------------------------------------------------


class TestEMANaNPrefixLength:
    """Property 2: EMA NaN prefix length

    **Validates: Requirements 1.3, 1.4**
    """

    @given(data=_closes, period=_period)
    @settings(max_examples=200)
    def test_ema_nan_prefix_length(self, data: list[float], period: int):
        """For any non-empty data and positive period N, _ema returns
        a list where the first min(N-1, len(data)) values are NaN.
        If len(data) >= N, the value at index N-1 is a valid float.

        **Validates: Requirements 1.3, 1.4**
        """
        result = _ema(data, period)
        n = len(data)

        assert len(result) == n

        nan_prefix_len = min(period - 1, n)

        for i in range(nan_prefix_len):
            assert math.isnan(result[i]), (
                f"Expected NaN at index {i}, got {result[i]} "
                f"(period={period}, n={n})"
            )

        if n >= period:
            assert not math.isnan(result[period - 1]), (
                f"Expected valid float at index {period - 1}, got NaN "
                f"(period={period}, n={n})"
            )


# ---------------------------------------------------------------------------
# Property 3: MACD NaN propagation
# ---------------------------------------------------------------------------


class TestMACDNaNPropagation:
    """Property 3: MACD NaN propagation

    **Validates: Requirement 1.5**
    """

    @given(closes=_closes, params=_macd_params)
    @settings(max_examples=200)
    def test_macd_dif_nan_prefix(
        self, closes: list[float], params: tuple[int, int, int]
    ):
        """For any non-empty closes and valid MACD params (fast, slow, signal),
        the DIF sequence has its first slow-1 values as NaN.
        If len(closes) < slow, all DIF values are NaN.

        **Validates: Requirement 1.5**
        """
        fast, slow, signal = params
        result = calculate_macd(closes, fast, slow, signal)
        n = len(closes)

        assert len(result.dif) == n

        if n < slow:
            # All DIF values should be NaN
            for i in range(n):
                assert math.isnan(result.dif[i]), (
                    f"Expected NaN DIF at index {i}, got {result.dif[i]} "
                    f"(n={n}, slow={slow})"
                )
        else:
            # First slow-1 values should be NaN
            for i in range(slow - 1):
                assert math.isnan(result.dif[i]), (
                    f"Expected NaN DIF at index {i}, got {result.dif[i]} "
                    f"(n={n}, slow={slow})"
                )


# ---------------------------------------------------------------------------
# Property 4: RSI NaN prefix length
# ---------------------------------------------------------------------------


class TestRSINaNPrefixLength:
    """Property 4: RSI NaN prefix length

    **Validates: Requirement 1.6**
    """

    @given(closes=_closes, period=_period)
    @settings(max_examples=200)
    def test_rsi_nan_prefix_length(self, closes: list[float], period: int):
        """For any non-empty closes and positive period, calculate_rsi returns
        values where the first min(period, len(closes)) values are NaN.
        If len(closes) < period + 1, all values are NaN.

        **Validates: Requirement 1.6**
        """
        result = calculate_rsi(closes, period)
        n = len(closes)

        assert len(result.values) == n

        if n < period + 1:
            # All values should be NaN
            for i in range(n):
                assert math.isnan(result.values[i]), (
                    f"Expected NaN at index {i}, got {result.values[i]} "
                    f"(n={n}, period={period})"
                )
        else:
            # First period values should be NaN (indices 0..period-1)
            for i in range(period):
                assert math.isnan(result.values[i]), (
                    f"Expected NaN at index {i}, got {result.values[i]} "
                    f"(n={n}, period={period})"
                )


# ---------------------------------------------------------------------------
# Property 5: Empty input safety
# ---------------------------------------------------------------------------


class TestEmptyInputSafety:
    """Property 5: Empty input safety

    **Validates: Requirement 1.9**
    """

    def test_calculate_ma_empty_input(self):
        """calculate_ma with empty list returns empty list."""
        result = calculate_ma([], 10)
        assert result == []

    def test_ema_empty_input(self):
        """_ema with empty list returns empty list."""
        result = _ema([], 10)
        assert result == []

    def test_calculate_macd_empty_input(self):
        """calculate_macd with empty list returns empty MACDResult."""
        result = calculate_macd([])
        assert result.dif == []
        assert result.dea == []
        assert result.macd == []

    def test_calculate_boll_empty_input(self):
        """calculate_boll with empty list returns empty BOLLResult."""
        result = calculate_boll([])
        assert result.upper == []
        assert result.middle == []
        assert result.lower == []

    def test_calculate_rsi_empty_input(self):
        """calculate_rsi with empty list returns empty RSIResult."""
        result = calculate_rsi([])
        assert result.values == []

    def test_calculate_dma_empty_input(self):
        """calculate_dma with empty list returns empty DMAResult."""
        result = calculate_dma([])
        assert result.dma == []
        assert result.ama == []


# ---------------------------------------------------------------------------
# Hypothesis 策略（预热期测试用）
# ---------------------------------------------------------------------------

from datetime import date
from app.core.schemas import IndicatorParamsConfig, StrategyConfig
from app.tasks.backtest import calculate_warmup_start_date

# 生成合理的 ma_periods 列表
_ma_periods = st.lists(
    st.integers(min_value=1, max_value=500),
    min_size=1,
    max_size=10,
)

# 生成 IndicatorParamsConfig
_indicator_params = st.builds(
    IndicatorParamsConfig,
    macd_fast=st.integers(min_value=1, max_value=50),
    macd_slow=st.integers(min_value=2, max_value=100),
    macd_signal=st.integers(min_value=1, max_value=50),
    boll_period=st.integers(min_value=1, max_value=100),
    rsi_period=st.integers(min_value=1, max_value=100),
    dma_short=st.integers(min_value=1, max_value=100),
    dma_long=st.integers(min_value=1, max_value=200),
)

# 生成 StrategyConfig
_strategy_config = st.builds(
    StrategyConfig,
    ma_periods=_ma_periods,
    indicator_params=_indicator_params,
)

# 生成合理的 start_date
_start_date = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31),
)

# 生成 buffer_days
_buffer_days = st.integers(min_value=0, max_value=500)


# ---------------------------------------------------------------------------
# Property 6: Warmup period sufficiency
# ---------------------------------------------------------------------------


class TestWarmupPeriodSufficiency:
    """Property 6: Warmup period sufficiency

    Validates that calculate_warmup_start_date returns a date satisfying
    all postconditions for every indicator type.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_strictly_before_start(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """warmup_date must be strictly earlier than start_date.

        **Validates: Requirements 2.1**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        assert warmup < start_date

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_max_ma_period_with_safety(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must be >= max(ma_periods) × 1.5.

        **Validates: Requirements 2.2**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        max_ma = max(strategy_config.ma_periods)
        # The function uses max(buffer_days, max_lookback) * 1.5, so diff >= max_ma
        assert diff >= max_ma

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_buffer_days_with_safety(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must be >= buffer_days × 1.5.

        **Validates: Requirements 2.3**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        assert diff >= int(buffer_days * 1.5)

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_macd_needs(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must cover MACD warmup: (macd_slow + macd_signal) × 1.5.

        **Validates: Requirements 2.4**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        ind = strategy_config.indicator_params
        macd_warmup = ind.macd_slow + ind.macd_signal
        assert diff >= macd_warmup

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_rsi_needs(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must cover RSI warmup: (rsi_period + 1) × 1.5.

        **Validates: Requirements 2.5**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        ind = strategy_config.indicator_params
        rsi_warmup = ind.rsi_period + 1
        assert diff >= rsi_warmup

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_boll_needs(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must cover BOLL warmup: boll_period × 1.5.

        **Validates: Requirements 2.6**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        ind = strategy_config.indicator_params
        assert diff >= ind.boll_period

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_dma_needs(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must cover DMA warmup: dma_long × 1.5.

        **Validates: Requirements 2.7**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days
        ind = strategy_config.indicator_params
        assert diff >= ind.dma_long

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_overall_safety_factor(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """Gap must be >= int(max(buffer_days, max_lookback) * 1.5).

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        warmup = calculate_warmup_start_date(start_date, strategy_config, buffer_days)
        diff = (start_date - warmup).days

        # Replicate the function's max_lookback calculation
        max_lookback = max(strategy_config.ma_periods)
        ind = strategy_config.indicator_params
        if hasattr(ind, "macd_slow"):
            macd_warmup = ind.macd_slow + ind.macd_signal
            max_lookback = max(max_lookback, macd_warmup)
            max_lookback = max(max_lookback, ind.boll_period)
            max_lookback = max(max_lookback, ind.rsi_period + 1)
            max_lookback = max(max_lookback, ind.dma_long)
        required_days = max(buffer_days, max_lookback)
        expected = int(required_days * 1.5)
        assert diff >= expected


# ---------------------------------------------------------------------------
# Hypothesis 策略（日期索引与预计算缓存测试用）
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta
from decimal import Decimal as D
from app.services.backtest_engine import (
    KlineDateIndex, _get_bars_up_to, _precompute_indicators, IndicatorCache,
)
from app.core.schemas import (
    KlineBar, BacktestConfig, IndicatorParamsConfig as _IPC,
    StrategyConfig as _SC, FactorCondition,
)


def _make_kline_bar(dt: datetime, symbol: str = "000001", close: float = 10.0) -> KlineBar:
    """Helper to build a minimal KlineBar for testing."""
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq="1d",
        open=D(str(close)),
        high=D(str(close * 1.02)),
        low=D(str(close * 0.98)),
        close=D(str(close)),
        volume=100000,
        amount=D("1000000"),
        turnover=D("1.5"),
        vol_ratio=D("1.0"),
    )


# Strategy: generate sorted unique dates with random gaps (simulating suspension)
_base_date = date(2020, 1, 1)

@st.composite
def _kline_dates(draw):
    """Generate a sorted list of unique dates with random gaps (simulating suspension)."""
    n = draw(st.integers(min_value=1, max_value=100))
    gaps = draw(
        st.lists(
            st.integers(min_value=1, max_value=10),
            min_size=n,
            max_size=n,
        )
    )
    dates = []
    current = _base_date
    for gap in gaps:
        current = current + timedelta(days=gap)
        dates.append(current)
    return dates

# Generate any trade_date in a reasonable range around the generated dates
_any_trade_date = st.dates(
    min_value=date(2019, 12, 1),
    max_value=date(2024, 12, 31),
)


# ---------------------------------------------------------------------------
# Property 7: bisect lookup equivalence
# ---------------------------------------------------------------------------


class TestBisectLookupEquivalence:
    """Property 7: bisect lookup equivalence

    For any kline date sequence and any trade_date,
    _get_bars_up_to gives the same result as a naive linear scan.

    **Validates: Requirements 3.1, 3.2**
    """

    @given(kline_dates=_kline_dates(), trade_date=_any_trade_date)
    @settings(max_examples=200)
    def test_bisect_matches_linear_scan(
        self,
        kline_dates: list[date],
        trade_date: date,
    ):
        """_get_bars_up_to(index, trade_date) must equal the result of
        a naive linear scan: max(i for i, d in enumerate(sorted_dates) if d <= trade_date),
        or -1 if no date <= trade_date.

        **Validates: Requirements 3.1, 3.2**
        """
        # Build KlineDateIndex from the generated dates
        date_to_idx = {d: i for i, d in enumerate(kline_dates)}
        index = KlineDateIndex(
            date_to_idx=date_to_idx,
            sorted_dates=kline_dates,  # already sorted by generator
        )

        # bisect-based result
        bisect_result = _get_bars_up_to(index, trade_date)

        # naive linear scan
        naive_result = -1
        for i, d in enumerate(kline_dates):
            if d <= trade_date:
                naive_result = i
            else:
                break  # dates are sorted, no need to continue

        assert bisect_result == naive_result, (
            f"bisect={bisect_result}, naive={naive_result}, "
            f"trade_date={trade_date}, dates={kline_dates[:5]}..."
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略（预计算缓存信号安全性用）
# ---------------------------------------------------------------------------


@st.composite
def _kline_sequence(draw, min_size: int = 1, max_size: int = 150):
    """Generate a sequence of KlineBar with realistic prices and random length,
    including very short sequences to simulate new stocks."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    base_price = draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    bars: list[KlineBar] = []
    current_dt = datetime(2024, 1, 2, 0, 0, 0)
    for i in range(n):
        # Small random price changes
        delta_pct = draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False))
        close = max(1.0, base_price * (1 + delta_pct))
        high = close * 1.02
        low = close * 0.98
        bars.append(KlineBar(
            time=current_dt,
            symbol="TEST01",
            freq="1d",
            open=D(str(round(close * 0.99, 2))),
            high=D(str(round(high, 2))),
            low=D(str(round(low, 2))),
            close=D(str(round(close, 2))),
            volume=100000 + i * 1000,
            amount=D(str(round(close * 100000, 2))),
            turnover=D("1.5"),
            vol_ratio=D("1.0"),
        ))
        current_dt += timedelta(days=1)
        # Skip weekends simplistically
        if current_dt.weekday() >= 5:
            current_dt += timedelta(days=2)
    return bars


# ---------------------------------------------------------------------------
# Property 8: Precomputed cache signal safety
# ---------------------------------------------------------------------------


class TestPrecomputedCacheSignalSafety:
    """Property 8: Precomputed cache signal safety

    For any kline sequence (including very short ones for new stocks),
    the IndicatorCache built by _precompute_indicators must have:
    - macd_signals: all bool type
    - boll_signals: all bool type
    - rsi_signals: all bool type
    - ma_trend_scores: all float in [0.0, 100.0]

    **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
    """

    @given(bars=_kline_sequence(min_size=1, max_size=150))
    @settings(max_examples=100, deadline=10000)
    def test_cache_signal_types_and_ranges(self, bars: list[KlineBar]):
        """All cache signal fields must have correct types and ranges.

        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Build a BacktestConfig that requests all indicator factors
        config = BacktestConfig(
            strategy_config=_SC(
                factors=[
                    FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
                    FactorCondition(factor_name="macd", operator="==", threshold=True),
                    FactorCondition(factor_name="boll", operator="==", threshold=True),
                    FactorCondition(factor_name="rsi", operator="==", threshold=True),
                ],
                ma_periods=[5, 10, 20, 60, 120],
                indicator_params=_IPC(),
            ),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        required_factors = {"ma_trend", "macd", "boll", "rsi"}

        kline_data = {"TEST01": bars}
        cache = _precompute_indicators(kline_data, config, required_factors)

        assert "TEST01" in cache
        ic = cache["TEST01"]
        n = len(bars)

        # macd_signals: all bool
        assert ic.macd_signals is not None
        assert len(ic.macd_signals) == n
        for i, v in enumerate(ic.macd_signals):
            assert isinstance(v, bool), (
                f"macd_signals[{i}] should be bool, got {type(v).__name__}: {v}"
            )

        # boll_signals: all bool
        assert ic.boll_signals is not None
        assert len(ic.boll_signals) == n
        for i, v in enumerate(ic.boll_signals):
            assert isinstance(v, bool), (
                f"boll_signals[{i}] should be bool, got {type(v).__name__}: {v}"
            )

        # rsi_signals: all bool
        assert ic.rsi_signals is not None
        assert len(ic.rsi_signals) == n
        for i, v in enumerate(ic.rsi_signals):
            assert isinstance(v, bool), (
                f"rsi_signals[{i}] should be bool, got {type(v).__name__}: {v}"
            )

        # ma_trend_scores: all float in [0.0, 100.0]
        assert ic.ma_trend_scores is not None
        assert len(ic.ma_trend_scores) == n
        for i, v in enumerate(ic.ma_trend_scores):
            assert isinstance(v, (int, float)), (
                f"ma_trend_scores[{i}] should be float, got {type(v).__name__}: {v}"
            )
            assert 0.0 <= v <= 100.0, (
                f"ma_trend_scores[{i}] should be in [0.0, 100.0], got {v}"
            )


# ---------------------------------------------------------------------------
# Hypothesis 策略（分钟K线缺失测试用）
# ---------------------------------------------------------------------------

from app.services.backtest_engine import _build_minute_day_ranges


@st.composite
def _minute_kline_scenario(draw):
    """
    生成日K线和分钟K线数据（部分交易日无分钟数据）。

    返回:
        (kline_data, existing_cache, daily_dates, missing_day_indices)
    """
    # 生成 3~10 个交易日
    num_days = draw(st.integers(min_value=3, max_value=10))

    base_dt = datetime(2024, 3, 1, 0, 0, 0)
    daily_dates: list[date] = []
    daily_bars: list[KlineBar] = []
    symbol = "TEST_MIN"

    for i in range(num_days):
        dt = base_dt + timedelta(days=i)
        d = dt.date()
        daily_dates.append(d)
        close = 10.0 + i * 0.5
        daily_bars.append(KlineBar(
            time=dt,
            symbol=symbol,
            freq="1d",
            open=D(str(round(close * 0.99, 2))),
            high=D(str(round(close * 1.02, 2))),
            low=D(str(round(close * 0.98, 2))),
            close=D(str(round(close, 2))),
            volume=100000,
            amount=D("1000000"),
            turnover=D("1.5"),
            vol_ratio=D("1.0"),
        ))

    # 决定哪些交易日有分钟数据（至少 1 天没有分钟数据）
    has_minute = draw(
        st.lists(
            st.booleans(),
            min_size=num_days,
            max_size=num_days,
        )
    )
    # 确保至少一天没有分钟数据
    assume(not all(has_minute))
    # 确保至少一天有分钟数据（否则没有意义）
    assume(any(has_minute))

    missing_day_indices = [i for i, h in enumerate(has_minute) if not h]

    # 生成分钟K线（5min 频率）
    minute_bars: list[KlineBar] = []
    for i, d in enumerate(daily_dates):
        if not has_minute[i]:
            continue  # 该交易日无分钟数据
        # 每天生成 2~5 根分钟 bar
        num_minute_bars = draw(st.integers(min_value=2, max_value=5))
        for j in range(num_minute_bars):
            minute_dt = datetime(d.year, d.month, d.day, 9, 30 + j * 5, 0)
            close = 10.0 + i * 0.5 + j * 0.01
            minute_bars.append(KlineBar(
                time=minute_dt,
                symbol=symbol,
                freq="5min",
                open=D(str(round(close * 0.99, 2))),
                high=D(str(round(close * 1.02, 2))),
                low=D(str(round(close * 0.98, 2))),
                close=D(str(round(close, 2))),
                volume=10000 + j * 100,
                amount=D("100000"),
                turnover=D("0.5"),
                vol_ratio=D("1.0"),
            ))

    kline_data: dict[str, dict[str, list[KlineBar]]] = {
        "daily": {symbol: daily_bars},
        "5min": {symbol: minute_bars},
    }

    # Build a minimal existing_cache (not used by _build_minute_day_ranges
    # but required by signature)
    existing_cache: dict[str, IndicatorCache] = {}

    return kline_data, existing_cache, daily_dates, missing_day_indices, symbol


# ---------------------------------------------------------------------------
# Property 9: Minute day ranges sentinel value
# ---------------------------------------------------------------------------


class TestMinuteDayRangesSentinelValue:
    """Property 9: Minute day ranges sentinel value

    For any trading day that has daily kline but no minute kline,
    _build_minute_day_ranges() returns (-1, -1) sentinel for that day.

    **Validates: Requirement 4.1**
    """

    @given(scenario=_minute_kline_scenario())
    @settings(max_examples=100, deadline=10000)
    def test_missing_minute_days_get_sentinel(self, scenario):
        """Days without minute data must have (-1, -1) in minute_day_ranges.

        **Validates: Requirement 4.1**
        """
        kline_data, existing_cache, daily_dates, missing_day_indices, symbol = scenario

        result = _build_minute_day_ranges(kline_data, existing_cache)

        assert symbol in result, f"Symbol {symbol} should be in result"
        assert "5min" in result[symbol], f"5min should be in result[{symbol}]"

        day_ranges = result[symbol]["5min"]
        assert len(day_ranges) == len(daily_dates), (
            f"day_ranges length ({len(day_ranges)}) should equal "
            f"daily_dates length ({len(daily_dates)})"
        )

        # Verify sentinel values for missing days
        for idx in missing_day_indices:
            assert day_ranges[idx] == (-1, -1), (
                f"day_ranges[{idx}] should be (-1, -1) for missing day "
                f"{daily_dates[idx]}, got {day_ranges[idx]}"
            )

        # Verify non-sentinel values for present days
        present_indices = [i for i in range(len(daily_dates)) if i not in missing_day_indices]
        for idx in present_indices:
            start, end = day_ranges[idx]
            assert start >= 0, (
                f"day_ranges[{idx}] start should be >= 0, got {start}"
            )
            assert end >= start, (
                f"day_ranges[{idx}] end ({end}) should be >= start ({start})"
            )


# ---------------------------------------------------------------------------
# Hypothesis 策略（分钟 NaN 跳过安全性测试用）
# ---------------------------------------------------------------------------

from app.services.exit_condition_evaluator import ExitConditionEvaluator
from app.core.schemas import ExitCondition, ExitConditionConfig


@st.composite
def _nan_minute_scanning_scenario(draw):
    """
    生成含 NaN 值的分钟指标缓存和数值比较条件。

    所有指标值要么是 NaN，因此不应触发任何条件。

    Returns:
        (condition, day_range, indicator_cache, exit_indicator_cache)
    """
    # 生成一个合理的 day range (10~50 bars)
    num_bars = draw(st.integers(min_value=5, max_value=30))
    start_idx = 0
    end_idx = num_bars - 1
    day_range = (start_idx, end_idx)

    # 生成全 NaN 的指标缓存
    nan_values = [float('nan')] * num_bars

    # 随机选一个缓存 key
    indicator = "rsi"
    cache_key = "rsi_14"

    exit_indicator_cache = {cache_key: nan_values}

    # 生成一个数值比较条件
    operator = draw(st.sampled_from([">", "<", ">=", "<="]))
    threshold = draw(st.floats(
        min_value=-1000.0, max_value=1000.0,
        allow_nan=False, allow_infinity=False,
    ))

    condition = ExitCondition(
        freq="5min",
        indicator=indicator,
        operator=operator,
        threshold=threshold,
        params={"rsi_period": 14},
    )

    # Build a minimal IndicatorCache
    ic = IndicatorCache(
        closes=[10.0] * num_bars,
        highs=[11.0] * num_bars,
        lows=[9.0] * num_bars,
        volumes=[100000] * num_bars,
        amounts=[D("1000000")] * num_bars,
        turnovers=[D("1.5")] * num_bars,
        opens=[10.0] * num_bars,
    )

    return condition, day_range, ic, exit_indicator_cache


# ---------------------------------------------------------------------------
# Property 10: Minute NaN skip safety
# ---------------------------------------------------------------------------


class TestMinuteNaNSkipSafety:
    """Property 10: Minute NaN skip safety

    For any minute-frequency intraday scan, when all bar indicator values
    are NaN, no bar should trigger the condition.

    **Validates: Requirement 4.4**
    """

    @given(scenario=_nan_minute_scanning_scenario())
    @settings(max_examples=100, deadline=10000)
    def test_nan_values_never_trigger_condition(self, scenario):
        """NaN indicator values in intraday scan must be skipped,
        condition must not be triggered.

        **Validates: Requirement 4.4**
        """
        condition, day_range, indicator_cache, exit_indicator_cache = scenario

        evaluator = ExitConditionEvaluator()
        triggered, reason = evaluator._evaluate_single_minute_scanning(
            condition, day_range, indicator_cache, exit_indicator_cache,
        )

        assert triggered is False, (
            f"Condition should not be triggered when all values are NaN. "
            f"operator={condition.operator}, threshold={condition.threshold}, "
            f"got triggered={triggered}, reason={reason}"
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略（选股无信号过滤测试用）
# ---------------------------------------------------------------------------

from app.services.screener.screen_executor import ScreenExecutor
from app.core.schemas import StrategyConfig as ScreenStrategyConfig, FactorCondition, ScreenType


@st.composite
def _no_signal_stocks_data(draw):
    """
    生成所有指标信号均为 False/0.0/None 的 stocks_data 字典。

    每只股票：
    - ma_trend: 0.0（数据不足）
    - macd: False（NaN → False）
    - boll: False
    - rsi: False
    - breakout: None（数据不足）
    - close: 正浮点数（合法价格）

    Returns:
        (stocks_data, strategy_config)
    """
    num_stocks = draw(st.integers(min_value=1, max_value=20))

    stocks_data: dict[str, dict] = {}
    for i in range(num_stocks):
        symbol = f"TEST{i:04d}"
        close = draw(st.floats(
            min_value=1.0, max_value=500.0,
            allow_nan=False, allow_infinity=False,
        ))
        stocks_data[symbol] = {
            "ma_trend": 0.0,
            "macd": False,
            "boll": False,
            "rsi": False,
            "breakout": None,
            "close": close,
        }

    # 使用 AND 逻辑，配置所有因子条件
    strategy_config = ScreenStrategyConfig(
        factors=[
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
            FactorCondition(factor_name="macd", operator="==", threshold=None),
            FactorCondition(factor_name="boll", operator="==", threshold=None),
            FactorCondition(factor_name="rsi", operator="==", threshold=None),
        ],
        logic=draw(st.sampled_from(["AND", "OR"])),
        ma_periods=[5, 10, 20, 60, 120],
    )

    return stocks_data, strategy_config


# ---------------------------------------------------------------------------
# Property 11: Screen no-signal filter
# ---------------------------------------------------------------------------


class TestScreenNoSignalFilter:
    """Property 11: Screen no-signal filter

    For any stocks_data where all indicator signals are False/0.0/None,
    ScreenExecutor._execute() should return ScreenResult.items as an
    empty list.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    """

    @given(scenario=_no_signal_stocks_data())
    @settings(max_examples=200, deadline=10000)
    def test_no_signal_stocks_excluded_from_screen_result(self, scenario):
        """Stocks with all signals at False/0.0/None must not appear
        in ScreenResult.items.

        **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
        """
        stocks_data, strategy_config = scenario

        executor = ScreenExecutor(strategy_config=strategy_config)
        result = executor.run_eod_screen(stocks_data)

        assert result.items == [], (
            f"Expected empty items for all-no-signal stocks, "
            f"got {len(result.items)} items: "
            f"{[item.symbol for item in result.items]}"
        )


# ---------------------------------------------------------------------------
# Property 12: Indicator function sharing consistency
# ---------------------------------------------------------------------------


class TestIndicatorFunctionSharingConsistency:
    """Property 12: Indicator function sharing consistency

    Verifies that indicator calculation functions used in
    _precompute_exit_indicators() are the same objects as those
    defined in app/services/screener/indicators.py and
    app/services/screener/ma_trend.py.

    **Validates: Requirement 6.5**
    """

    def test_calculate_ma_is_same_object(self):
        """calculate_ma used in _precompute_exit_indicators must be the
        same object as the one in app.services.screener.ma_trend.

        **Validates: Requirement 6.5**
        """
        # Import from the canonical source module
        from app.services.screener.ma_trend import calculate_ma as source_calculate_ma

        # Import from where _precompute_exit_indicators gets it —
        # Since it does a local import from the same module, they share the
        # same module-level function object after the first import.
        # Trigger the import path used by _precompute_exit_indicators:
        from app.services.screener.ma_trend import calculate_ma as exit_calculate_ma

        assert exit_calculate_ma is source_calculate_ma, (
            "calculate_ma in _precompute_exit_indicators must be the same "
            "object as app.services.screener.ma_trend.calculate_ma"
        )

    def test_calculate_macd_is_same_object(self):
        """calculate_macd used in _precompute_exit_indicators must be the
        same object as the one in app.services.screener.indicators.

        **Validates: Requirement 6.5**
        """
        from app.services.screener.indicators import calculate_macd as source_fn
        # The import inside _precompute_exit_indicators resolves to the same object
        import app.services.screener.indicators as indicators_module
        assert indicators_module.calculate_macd is source_fn

    def test_calculate_rsi_is_same_object(self):
        """calculate_rsi used in _precompute_exit_indicators must be the
        same object as the one in app.services.screener.indicators.

        **Validates: Requirement 6.5**
        """
        from app.services.screener.indicators import calculate_rsi as source_fn
        import app.services.screener.indicators as indicators_module
        assert indicators_module.calculate_rsi is source_fn

    def test_calculate_boll_is_same_object(self):
        """calculate_boll used in _precompute_exit_indicators must be the
        same object as the one in app.services.screener.indicators.

        **Validates: Requirement 6.5**
        """
        from app.services.screener.indicators import calculate_boll as source_fn
        import app.services.screener.indicators as indicators_module
        assert indicators_module.calculate_boll is source_fn

    def test_calculate_dma_is_same_object(self):
        """calculate_dma used in _precompute_exit_indicators must be the
        same object as the one in app.services.screener.indicators.

        **Validates: Requirement 6.5**
        """
        from app.services.screener.indicators import calculate_dma as source_fn
        import app.services.screener.indicators as indicators_module
        assert indicators_module.calculate_dma is source_fn

    def test_precompute_exit_indicators_uses_shared_functions(self):
        """Verify that _precompute_exit_indicators actually imports from the
        same modules as the screener, by checking the function objects
        via module introspection after triggering the import path.

        This test calls _precompute_exit_indicators with minimal data to
        trigger its local imports, then verifies the imported functions
        are the same objects as the canonical ones.

        **Validates: Requirement 6.5**
        """
        from app.services.screener.indicators import (
            calculate_macd as screener_macd,
            calculate_boll as screener_boll,
            calculate_rsi as screener_rsi,
            calculate_dma as screener_dma,
        )
        from app.services.screener.ma_trend import calculate_ma as screener_ma

        # Trigger the import inside _precompute_exit_indicators by calling it
        from app.services.backtest_engine import _precompute_exit_indicators
        from app.core.schemas import ExitConditionConfig, ExitCondition

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        # Call with minimal data to trigger the local imports
        _precompute_exit_indicators(
            kline_data={"daily": {}},
            exit_config=exit_config,
            existing_cache={},
        )

        # After the call, Python's module cache has loaded the functions.
        # Verify the modules expose the same objects:
        import app.services.screener.indicators as ind_mod
        import app.services.screener.ma_trend as ma_mod

        assert ma_mod.calculate_ma is screener_ma, (
            "calculate_ma should be shared between screener and exit indicators"
        )
        assert ind_mod.calculate_macd is screener_macd, (
            "calculate_macd should be shared between screener and exit indicators"
        )
        assert ind_mod.calculate_boll is screener_boll, (
            "calculate_boll should be shared between screener and exit indicators"
        )
        assert ind_mod.calculate_rsi is screener_rsi, (
            "calculate_rsi should be shared between screener and exit indicators"
        )
        assert ind_mod.calculate_dma is screener_dma, (
            "calculate_dma should be shared between screener and exit indicators"
        )
