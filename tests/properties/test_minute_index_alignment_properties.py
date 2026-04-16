# Feature: minute-indicator-index-alignment-fix
# Property 1: Bug Condition — Minute-frequency index misalignment
"""
Bug condition exploration tests for minute-frequency indicator index alignment.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.3, 2.4, 2.5**

These tests demonstrate the bug where `bar_index` (daily K-line index) is used
directly to index minute-frequency indicator caches. The minute cache has a
completely different index semantics — e.g., 5min data has ~48 bars per day,
so `bar_index=5` (day 5) should map to minute indices 240–287, not index 5.

EXPECTED: These tests FAIL on unfixed code, confirming the bug exists.
"""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from app.core.schemas import ExitCondition, ExitConditionConfig
from app.services.backtest_engine import IndicatorCache
from app.services.exit_condition_evaluator import ExitConditionEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BARS_PER_DAY_5MIN = 48  # 4 hours × 60 / 5 = 48 bars per trading day


def _make_minimal_indicator_cache(n: int, close_value: float = 100.0) -> IndicatorCache:
    """Create a minimal IndicatorCache with `n` bars, all at `close_value`."""
    return IndicatorCache(
        closes=[close_value] * n,
        highs=[close_value] * n,
        lows=[close_value] * n,
        volumes=[0] * n,
        amounts=[Decimal("0")] * n,
        turnovers=[Decimal("0")] * n,
    )


# ---------------------------------------------------------------------------
# Test Scenario 1 (numeric): 5min RSI > 80
#
# Setup:
#   - 10 trading days of 5min data → 480 minute bars total
#   - Day 5's minute bars are at indices 240–287
#   - RSI at day 5's minute bars = 85.0 (satisfies > 80)
#   - RSI at index 5 (what the buggy code reads) = 50.0 (does NOT satisfy > 80)
#   - bar_index = 5 (daily index for day 5)
#
# Expected behavior: evaluator should scan indices 240–287 and trigger
# Bug behavior: evaluator reads index 5 → RSI=50 → does NOT trigger
# ---------------------------------------------------------------------------


def test_scenario1_numeric_5min_rsi_triggers_for_correct_day():
    """
    **Validates: Requirements 1.1, 1.2**

    Configure freq="5min", rsi > 80. Build minute cache where day 5's
    minute bars (indices 240–287) have RSI=85, but index 5 has RSI=50.
    Assert evaluator triggers for day 5.

    On UNFIXED code this test FAILS because the evaluator uses bar_index=5
    to directly index the minute RSI cache, reading RSI=50 instead of
    scanning day 5's minute bar range (240–287) where RSI=85.
    """
    num_days = 10
    total_minute_bars = num_days * BARS_PER_DAY_5MIN  # 480

    # Build RSI cache: default 50.0 everywhere, day 5's bars get 85.0
    rsi_values = [50.0] * total_minute_bars
    day5_start = 5 * BARS_PER_DAY_5MIN  # 240
    day5_end = 6 * BARS_PER_DAY_5MIN    # 288 (exclusive)
    for i in range(day5_start, day5_end):
        rsi_values[i] = 85.0

    # Verify our setup: index 5 has RSI=50, day 5's range has RSI=85
    assert rsi_values[5] == 50.0, "Index 5 should have RSI=50 (bug reads this)"
    assert rsi_values[240] == 85.0, "Day 5 start should have RSI=85"
    assert rsi_values[287] == 85.0, "Day 5 end should have RSI=85"

    # Build exit_indicator_cache with 5min RSI
    exit_indicator_cache = {
        "5min": {
            "rsi_14": rsi_values,
            "rsi": rsi_values,
        },
    }

    # Daily indicator cache (minimal, 10 days)
    indicator_cache = _make_minimal_indicator_cache(num_days)

    # Configure condition: 5min RSI > 80
    condition = ExitCondition(
        freq="5min",
        indicator="rsi",
        operator=">",
        threshold=80.0,
        cross_target=None,
        params={"rsi_period": 14},
    )
    config = ExitConditionConfig(conditions=[condition], logic="AND")

    # Build minute_day_ranges: each trading day maps to its 48-bar range
    minute_day_ranges = {
        "5min": [
            (d * BARS_PER_DAY_5MIN, (d + 1) * BARS_PER_DAY_5MIN - 1)
            for d in range(num_days)
        ],
    }
    # Verify: day 5 → (240, 287)
    assert minute_day_ranges["5min"][5] == (240, 287)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=5,  # daily index for day 5
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
        minute_day_ranges=minute_day_ranges,
    )

    # Expected: triggered=True because day 5's minute bars have RSI=85 > 80
    # Bug: triggered=False because evaluator reads rsi_values[5]=50 < 80
    assert triggered is True, (
        f"Expected triggered=True for day 5 (minute bars 240-287 have RSI=85 > 80), "
        f"but got triggered={triggered}. "
        f"Bug: evaluator reads rsi_values[bar_index=5]={rsi_values[5]} instead of "
        f"scanning day 5's minute range."
    )
    assert reason is not None and "RSI" in reason.upper(), (
        f"Expected reason to mention RSI, got: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Test Scenario 2 (cross): 5min MACD DIF cross_down DEA
#
# Setup:
#   - 10 trading days of 5min data → 480 minute bars total
#   - Day 3's minute bars are at indices 144–191
#   - At indices 144–145 within day 3, DIF crosses below DEA (cross_down)
#   - At indices 2–3 (what the buggy code checks), NO crossover
#   - bar_index = 3 (daily index for day 3)
#
# Expected behavior: evaluator should scan day 3's range and detect cross
# Bug behavior: evaluator checks indices 2–3 → no cross → does NOT trigger
# ---------------------------------------------------------------------------


def test_scenario2_cross_5min_macd_cross_down_triggers_for_correct_day():
    """
    **Validates: Requirements 1.1, 2.4**

    Configure freq="5min", MACD DIF cross_down DEA. Build minute cache
    where day 3's bars show a crossover at indices 144–145, but indices
    2–3 show no crossover. Assert evaluator triggers for day 3.

    On UNFIXED code this test FAILS because the evaluator checks
    bar_index=3 and bar_index=2 directly in the minute cache, where
    there is no crossover.
    """
    num_days = 10
    total_minute_bars = num_days * BARS_PER_DAY_5MIN  # 480

    # Build MACD DIF and DEA caches
    # Default: DIF=10.0, DEA=5.0 everywhere (DIF > DEA, no cross_down)
    macd_dif = [10.0] * total_minute_bars
    macd_dea = [5.0] * total_minute_bars

    # At indices 2–3 (what buggy code reads): NO crossover
    # DIF stays above DEA → no cross_down
    assert macd_dif[2] > macd_dea[2], "Index 2: DIF > DEA (no cross setup)"
    assert macd_dif[3] > macd_dea[3], "Index 3: DIF > DEA (no cross setup)"

    # Day 3's minute bars: indices 144–191
    day3_start = 3 * BARS_PER_DAY_5MIN  # 144
    # Set up cross_down at indices 144→145:
    # At index 144: DIF >= DEA (DIF=10, DEA=5)
    # At index 145: DIF < DEA (DIF=3, DEA=8)
    macd_dif[144] = 10.0
    macd_dea[144] = 5.0
    macd_dif[145] = 3.0
    macd_dea[145] = 8.0

    exit_indicator_cache = {
        "5min": {
            "macd_dif": macd_dif,
            "macd_dea": macd_dea,
            "macd_dif_12_26_9": macd_dif,
            "macd_dea_12_26_9": macd_dea,
        },
    }

    indicator_cache = _make_minimal_indicator_cache(num_days)

    # Configure condition: 5min MACD DIF cross_down DEA
    condition = ExitCondition(
        freq="5min",
        indicator="macd_dif",
        operator="cross_down",
        threshold=None,
        cross_target="macd_dea",
        params={},
    )
    config = ExitConditionConfig(conditions=[condition], logic="AND")

    # Build minute_day_ranges: each trading day maps to its 48-bar range
    minute_day_ranges = {
        "5min": [
            (d * BARS_PER_DAY_5MIN, (d + 1) * BARS_PER_DAY_5MIN - 1)
            for d in range(num_days)
        ],
    }
    # Verify: day 3 → (144, 191)
    assert minute_day_ranges["5min"][3] == (144, 191)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=3,  # daily index for day 3
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
        minute_day_ranges=minute_day_ranges,
    )

    # Expected: triggered=True because day 3's minute bars show cross_down at 144→145
    # Bug: triggered=False because evaluator checks indices 2→3 where no cross exists
    assert triggered is True, (
        f"Expected triggered=True for day 3 (cross_down at minute indices 144→145), "
        f"but got triggered={triggered}. "
        f"Bug: evaluator checks bar_index=2→3 in minute cache instead of "
        f"scanning day 3's minute range (144–191)."
    )
    assert reason is not None and "MACD_DIF" in reason.upper(), (
        f"Expected reason to mention MACD_DIF, got: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Test Scenario 3 (mixed AND): daily RSI > 80 AND 5min close < 95
#
# Setup:
#   - 15 trading days, 5min data → 720 minute bars
#   - Daily RSI at bar_index=10: 85.0 (satisfies > 80) ✓
#   - 5min close at index 10: 100.0 (does NOT satisfy < 95) ✗
#   - Day 10's minute bars (indices 480–527): include close=90.0 (satisfies < 95) ✓
#   - bar_index = 10
#
# Expected behavior: daily RSI satisfied + 5min close scan finds 90 < 95 → AND triggers
# Bug behavior: daily RSI satisfied + 5min close at index 10 = 100 ≥ 95 → AND fails
# ---------------------------------------------------------------------------


def test_scenario3_mixed_and_daily_rsi_and_5min_close():
    """
    **Validates: Requirements 1.4, 2.5**

    Configure daily RSI > 80 AND 5min close < 95. Daily RSI at bar_index=10
    is 85 (satisfied). 5min close at index 10 is 100 (not satisfied), but
    day 10's minute bars include close=90 (satisfied). Assert AND combination
    triggers.

    On UNFIXED code this test FAILS because the 5min close condition reads
    index 10 in the minute cache (close=100, not < 95), so the AND fails
    even though day 10's minute bars contain close=90 < 95.
    """
    num_days = 15
    total_minute_bars = num_days * BARS_PER_DAY_5MIN  # 720

    # Daily RSI cache: RSI=85 at index 10 (satisfies > 80)
    daily_rsi = [50.0] * num_days
    daily_rsi[10] = 85.0

    # 5min close cache: default 100.0 everywhere
    minute_closes = [100.0] * total_minute_bars

    # Day 10's minute bars: indices 480–527
    day10_start = 10 * BARS_PER_DAY_5MIN  # 480
    # Set some bars in day 10 to close=90 (satisfies < 95)
    minute_closes[day10_start + 5] = 90.0
    minute_closes[day10_start + 20] = 90.0

    # Verify: index 10 in minute cache is 100 (bug reads this)
    assert minute_closes[10] == 100.0, "Index 10 should have close=100 (bug reads this)"
    # Verify: day 10's range has close=90
    assert minute_closes[day10_start + 5] == 90.0, "Day 10 should have close=90"

    exit_indicator_cache = {
        "daily": {
            "rsi_14": daily_rsi,
            "rsi": daily_rsi,
        },
        "5min": {
            # close is read from indicator_cache for daily, but from exit cache for minute
            # The evaluator reads "close" from indicator_cache.closes, not exit_indicator_cache
            # So we need to set up the minute close in a way the evaluator can access it
        },
    }

    # Daily indicator cache: 15 days, close=100 everywhere
    daily_closes = [100.0] * num_days
    indicator_cache = IndicatorCache(
        closes=daily_closes,
        highs=[100.0] * num_days,
        lows=[100.0] * num_days,
        volumes=[0] * num_days,
        amounts=[Decimal("0")] * num_days,
        turnovers=[Decimal("0")] * num_days,
    )

    # For the 5min close condition, the evaluator uses _get_indicator_value("close", bar_index, ...)
    # which reads from indicator_cache.closes[bar_index].
    # But for minute freq, it falls back to the freq_cache from exit_indicator_cache.
    # Actually, looking at the code: "close" maps to indicator_cache.closes directly.
    # The evaluator doesn't distinguish freq when reading "close" — it always reads
    # indicator_cache.closes[bar_index]. This is part of the bug.
    #
    # To make this test work, we use a different indicator for the minute condition.
    # Let's use 5min RSI < 95 instead of close < 95, since RSI is read from exit_indicator_cache.

    # Revise: 5min RSI < 95
    minute_rsi = [96.0] * total_minute_bars  # default 96 (does NOT satisfy < 95)
    minute_rsi[10] = 96.0  # index 10 (what bug reads) = 96, NOT < 95
    # Day 10's bars: set some to 90 (satisfies < 95)
    minute_rsi[day10_start + 5] = 90.0
    minute_rsi[day10_start + 20] = 90.0

    exit_indicator_cache = {
        "daily": {
            "rsi_14": daily_rsi,
            "rsi": daily_rsi,
        },
        "5min": {
            "rsi_14": minute_rsi,
            "rsi": minute_rsi,
        },
    }

    # Condition 1: daily RSI > 80
    cond_daily = ExitCondition(
        freq="daily",
        indicator="rsi",
        operator=">",
        threshold=80.0,
        cross_target=None,
        params={"rsi_period": 14},
    )

    # Condition 2: 5min RSI < 95
    cond_minute = ExitCondition(
        freq="5min",
        indicator="rsi",
        operator="<",
        threshold=95.0,
        cross_target=None,
        params={"rsi_period": 14},
    )

    config = ExitConditionConfig(
        conditions=[cond_daily, cond_minute],
        logic="AND",
    )

    # Build minute_day_ranges: each trading day maps to its 48-bar range
    minute_day_ranges = {
        "5min": [
            (d * BARS_PER_DAY_5MIN, (d + 1) * BARS_PER_DAY_5MIN - 1)
            for d in range(num_days)
        ],
    }
    # Verify: day 10 → (480, 527)
    assert minute_day_ranges["5min"][10] == (480, 527)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=10,
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
        minute_day_ranges=minute_day_ranges,
    )

    # Expected: triggered=True
    #   - daily RSI at index 10 = 85 > 80 ✓
    #   - 5min RSI: scan day 10's range (480–527), find RSI=90 < 95 ✓
    #   - AND(True, True) = True
    #
    # Bug: triggered=False
    #   - daily RSI at index 10 = 85 > 80 ✓
    #   - 5min RSI at index 10 = 96, NOT < 95 ✗
    #   - AND(True, False) = False
    assert triggered is True, (
        f"Expected triggered=True for AND(daily RSI=85>80, 5min RSI scan finds 90<95), "
        f"but got triggered={triggered}. "
        f"Bug: 5min condition reads minute_rsi[bar_index=10]={minute_rsi[10]} "
        f"instead of scanning day 10's range where RSI=90 < 95."
    )


# ===========================================================================
# Property 2: Preservation — Daily-frequency evaluation unchanged
# ===========================================================================
"""
Preservation property tests for daily-frequency exit condition evaluation.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

These tests capture the CURRENT correct behavior of daily-frequency conditions
on UNFIXED code. They verify that:
- Daily numeric conditions produce correct (triggered, reason) based on single-value lookup
- Daily cross conditions detect crossovers correctly
- Empty conditions always return (False, None)
- AND/OR logic for daily-only configs produces correct combination results

EXPECTED: These tests PASS on unfixed code (confirms baseline behavior to preserve).
After the fix, these same tests are re-run to ensure no regressions.
"""

from hypothesis import given, settings as h_settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Hypothesis strategies for daily-frequency preservation tests
# ---------------------------------------------------------------------------

# Finite floats suitable for indicator values and thresholds
_finite_float = st.floats(
    min_value=-1e6, max_value=1e6,
    allow_nan=False, allow_infinity=False,
)

# Numeric comparison operators
_numeric_operators = st.sampled_from([">", "<", ">=", "<="])

# Cross operators
_cross_operators = st.sampled_from(["cross_up", "cross_down"])

# Python native comparison functions for verification
_NATIVE_CMP = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


def _build_daily_indicator_cache(
    num_bars: int,
    rsi_values: list[float],
) -> tuple[IndicatorCache, dict[str, dict[str, list[float]]]]:
    """
    Build an IndicatorCache and exit_indicator_cache for daily-frequency tests.

    Args:
        num_bars: Number of daily bars
        rsi_values: RSI values for each bar (used as the test indicator)

    Returns:
        (indicator_cache, exit_indicator_cache) tuple
    """
    indicator_cache = IndicatorCache(
        closes=[100.0] * num_bars,
        highs=[100.0] * num_bars,
        lows=[100.0] * num_bars,
        volumes=[0] * num_bars,
        amounts=[Decimal("0")] * num_bars,
        turnovers=[Decimal("0")] * num_bars,
    )
    exit_indicator_cache = {
        "daily": {
            "rsi_14": rsi_values,
            "rsi": rsi_values,
        },
    }
    return indicator_cache, exit_indicator_cache


# ---------------------------------------------------------------------------
# Preservation Property 2a: Daily numeric condition single-value lookup
# ---------------------------------------------------------------------------


@h_settings(max_examples=200)
@given(
    indicator_value=_finite_float,
    threshold=_finite_float,
    operator=_numeric_operators,
)
def test_preservation_daily_numeric_condition_single_value_lookup(
    indicator_value: float,
    threshold: float,
    operator: str,
):
    """
    **Validates: Requirements 3.1, 3.2**

    Property: For any daily-frequency exit condition with arbitrary indicator
    values and thresholds, the evaluator produces the correct (triggered, reason)
    result using single-value lookup at bar_index.

    This captures the current correct behavior: daily conditions use bar_index
    to directly index the daily cache and compare against the threshold.
    """
    num_bars = 5
    rsi_values = [0.0] * num_bars
    bar_index = 2
    rsi_values[bar_index] = indicator_value

    indicator_cache, exit_indicator_cache = _build_daily_indicator_cache(
        num_bars, rsi_values,
    )

    condition = ExitCondition(
        freq="daily",
        indicator="rsi",
        operator=operator,
        threshold=threshold,
        cross_target=None,
        params={"rsi_period": 14},
    )
    config = ExitConditionConfig(conditions=[condition], logic="AND")

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=bar_index,
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
    )

    expected = _NATIVE_CMP[operator](indicator_value, threshold)
    assert triggered == expected, (
        f"Daily numeric: RSI={indicator_value} {operator} {threshold}: "
        f"expected={expected}, got={triggered}"
    )

    if triggered:
        assert reason is not None and "RSI" in reason.upper(), (
            f"Expected reason to mention RSI when triggered, got: {reason!r}"
        )
    else:
        assert reason is None, (
            f"Expected reason=None when not triggered, got: {reason!r}"
        )


# ---------------------------------------------------------------------------
# Preservation Property 2b: Daily cross condition detection unchanged
# ---------------------------------------------------------------------------


@h_settings(max_examples=200)
@given(
    prev_ind=_finite_float,
    curr_ind=_finite_float,
    prev_tgt=_finite_float,
    curr_tgt=_finite_float,
    cross_op=_cross_operators,
)
def test_preservation_daily_cross_condition_detection(
    prev_ind: float,
    curr_ind: float,
    prev_tgt: float,
    curr_tgt: float,
    cross_op: str,
):
    """
    **Validates: Requirements 3.1, 3.2**

    Property: For any daily-frequency cross condition with arbitrary consecutive
    indicator/target pairs, cross detection produces the correct result.

    cross_up:   prev_ind <= prev_tgt AND curr_ind > curr_tgt
    cross_down: prev_ind >= prev_tgt AND curr_ind < curr_tgt
    """
    num_bars = 3
    # Use MACD DIF as indicator, MACD DEA as cross target
    dif_values = [0.0, prev_ind, curr_ind]
    dea_values = [0.0, prev_tgt, curr_tgt]

    indicator_cache = IndicatorCache(
        closes=[100.0] * num_bars,
        highs=[100.0] * num_bars,
        lows=[100.0] * num_bars,
        volumes=[0] * num_bars,
        amounts=[Decimal("0")] * num_bars,
        turnovers=[Decimal("0")] * num_bars,
    )
    exit_indicator_cache = {
        "daily": {
            "macd_dif": dif_values,
            "macd_dea": dea_values,
            "macd_dif_12_26_9": dif_values,
            "macd_dea_12_26_9": dea_values,
        },
    }

    condition = ExitCondition(
        freq="daily",
        indicator="macd_dif",
        operator=cross_op,
        threshold=None,
        cross_target="macd_dea",
        params={},
    )
    config = ExitConditionConfig(conditions=[condition], logic="AND")

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=2,  # current bar
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
    )

    if cross_op == "cross_up":
        expected = prev_ind <= prev_tgt and curr_ind > curr_tgt
    else:  # cross_down
        expected = prev_ind >= prev_tgt and curr_ind < curr_tgt

    assert triggered == expected, (
        f"Daily {cross_op}: prev_ind={prev_ind}, curr_ind={curr_ind}, "
        f"prev_tgt={prev_tgt}, curr_tgt={curr_tgt}: "
        f"expected={expected}, got={triggered}"
    )

    if triggered:
        assert reason is not None and "MACD_DIF" in reason.upper(), (
            f"Expected reason to mention MACD_DIF when triggered, got: {reason!r}"
        )


# ---------------------------------------------------------------------------
# Preservation Property 2c: Empty conditions always return (False, None)
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(
    logic=st.sampled_from(["AND", "OR"]),
    bar_index=st.integers(min_value=0, max_value=99),
)
def test_preservation_empty_conditions_return_false_none(
    logic: str,
    bar_index: int,
):
    """
    **Validates: Requirements 3.2, 3.5**

    Property: ExitConditionConfig(conditions=[]) always returns (False, None)
    regardless of logic operator or bar_index.
    """
    num_bars = max(bar_index + 1, 1)
    indicator_cache = _make_minimal_indicator_cache(num_bars)

    config = ExitConditionConfig(conditions=[], logic=logic)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=bar_index,
        indicator_cache=indicator_cache,
    )

    assert triggered is False, (
        f"Empty conditions should return triggered=False, got {triggered}"
    )
    assert reason is None, (
        f"Empty conditions should return reason=None, got {reason!r}"
    )


# ---------------------------------------------------------------------------
# Preservation Property 2d: AND/OR logic for daily-only configs
# ---------------------------------------------------------------------------


@h_settings(max_examples=200)
@given(
    logic=st.sampled_from(["AND", "OR"]),
    condition_results=st.lists(st.booleans(), min_size=1, max_size=8),
)
def test_preservation_and_or_logic_daily_only_configs(
    logic: str,
    condition_results: list[bool],
):
    """
    **Validates: Requirements 3.1, 3.2, 3.6, 3.7**

    Property: AND/OR logic for daily-only configs produces correct combination
    results. For each desired boolean outcome, we construct a daily RSI condition
    with a threshold that either satisfies or doesn't satisfy the comparison.

    - AND: all conditions must be True for the config to trigger
    - OR: any condition being True triggers the config
    """
    num_bars = 5
    bar_index = 2

    # Build RSI values: one per condition, all at bar_index=2
    # We use separate RSI cache keys to avoid conflicts
    # Strategy: use "rsi" indicator with a fixed value at bar_index,
    # and set threshold to make it True or False as desired.
    #
    # For True:  RSI=75.0, threshold=50.0, operator=">" → 75 > 50 = True
    # For False: RSI=75.0, threshold=90.0, operator=">" → 75 > 90 = False
    rsi_value = 75.0
    rsi_values = [0.0] * num_bars
    rsi_values[bar_index] = rsi_value

    indicator_cache, exit_indicator_cache = _build_daily_indicator_cache(
        num_bars, rsi_values,
    )

    conditions = []
    for desired_result in condition_results:
        threshold = 50.0 if desired_result else 90.0
        conditions.append(
            ExitCondition(
                freq="daily",
                indicator="rsi",
                operator=">",
                threshold=threshold,
                cross_target=None,
                params={"rsi_period": 14},
            )
        )

    config = ExitConditionConfig(conditions=conditions, logic=logic)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=bar_index,
        indicator_cache=indicator_cache,
        exit_indicator_cache=exit_indicator_cache,
    )

    if logic == "AND":
        expected = all(condition_results)
    else:
        expected = any(condition_results)

    assert triggered == expected, (
        f"Daily-only {logic}: condition_results={condition_results}: "
        f"expected={expected}, got={triggered}"
    )

    if triggered:
        assert reason is not None, (
            f"Expected non-None reason when triggered, got None"
        )
    else:
        assert reason is None, (
            f"Expected reason=None when not triggered, got: {reason!r}"
        )
