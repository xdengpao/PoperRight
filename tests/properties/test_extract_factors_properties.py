"""
_extract_required_factors 属性测试（Hypothesis）

**Validates: Requirements 2.1, 2.3**

Property 2: 因子提取完备性
For any BacktestConfig where strategy_config.factors is non-empty,
_extract_required_factors(config) returns a set that:
- Is a subset of {"ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout"}
- Contains the compute modules for each factor_name in the factors list
"""

from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import BacktestConfig, FactorCondition, StrategyConfig
from app.services.backtest_engine import (
    ALL_FACTORS,
    FACTOR_TO_COMPUTE,
    _extract_required_factors,
)

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# Draw factor_names from the known set of valid factors
_valid_factor_names = sorted(ALL_FACTORS)

# Generate a non-empty list of FactorCondition with factor_names from ALL_FACTORS
_factor_conditions = st.lists(
    st.builds(
        FactorCondition,
        factor_name=st.sampled_from(_valid_factor_names),
        operator=st.just(">="),
        threshold=st.just(0.0),
    ),
    min_size=1,
    max_size=7,
)

# Build a BacktestConfig with non-empty factors
_config_with_factors = st.builds(
    BacktestConfig,
    strategy_config=st.builds(
        StrategyConfig,
        factors=_factor_conditions,
    ),
    start_date=st.just(date(2024, 1, 1)),
    end_date=st.just(date(2024, 12, 31)),
)


# ---------------------------------------------------------------------------
# Property 2: 因子提取完备性
# ---------------------------------------------------------------------------


class TestExtractFactorsCompleteness:
    """Property 2: 因子提取完备性

    **Validates: Requirements 2.1, 2.3**
    """

    @given(config=_config_with_factors)
    @settings(max_examples=200)
    def test_result_is_subset_of_all_factors(self, config: BacktestConfig):
        """The returned set must be a subset of ALL_FACTORS.

        **Validates: Requirements 2.3**
        """
        result = _extract_required_factors(config)
        assert result.issubset(ALL_FACTORS)

    @given(config=_config_with_factors)
    @settings(max_examples=200)
    def test_result_contains_compute_modules_for_each_factor(
        self, config: BacktestConfig
    ):
        """For each factor_name in the input, FACTOR_TO_COMPUTE[factor_name]
        must be a subset of the result.

        **Validates: Requirements 2.1**
        """
        result = _extract_required_factors(config)
        for fc in config.strategy_config.factors:
            expected = FACTOR_TO_COMPUTE.get(fc.factor_name, set())
            assert expected.issubset(result), (
                f"factor_name={fc.factor_name!r}: expected {expected} ⊆ result {result}"
            )

    @given(config=_config_with_factors)
    @settings(max_examples=200)
    def test_result_contains_no_extra_factors(self, config: BacktestConfig):
        """The result should contain only factors that are mapped from the
        input factor_names — no extraneous compute modules.

        **Validates: Requirements 2.1**
        """
        result = _extract_required_factors(config)
        expected = set()
        for fc in config.strategy_config.factors:
            expected.update(FACTOR_TO_COMPUTE.get(fc.factor_name, set()))
        assert result == expected


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）— 空因子列表配置
# ---------------------------------------------------------------------------

# Vary ma_periods: non-empty lists of positive ints (typical MA windows)
_ma_periods = st.lists(
    st.sampled_from([5, 10, 20, 30, 60, 120, 250]),
    min_size=1,
    max_size=6,
    unique=True,
)

# Vary start_date / end_date: random date pairs where start < end
_date_pair = st.tuples(
    st.dates(min_value=date(2010, 1, 1), max_value=date(2024, 6, 30)),
    st.dates(min_value=date(2010, 1, 1), max_value=date(2024, 12, 31)),
).filter(lambda pair: pair[0] < pair[1])

# Build a BacktestConfig with EMPTY factors list, varying other fields
_config_empty_factors = _date_pair.flatmap(
    lambda pair: st.builds(
        BacktestConfig,
        strategy_config=st.builds(
            StrategyConfig,
            factors=st.just([]),
            ma_periods=_ma_periods,
        ),
        start_date=st.just(pair[0]),
        end_date=st.just(pair[1]),
    )
)


# ---------------------------------------------------------------------------
# Property 3: 因子提取向后兼容
# ---------------------------------------------------------------------------


class TestExtractFactorsBackwardCompatibility:
    """Property 3: 因子提取向后兼容

    **Validates: Requirement 2.2**
    """

    @given(config=_config_empty_factors)
    @settings(max_examples=200)
    def test_empty_factors_returns_all_factors(self, config: BacktestConfig):
        """When factors list is empty, _extract_required_factors must return
        all 7 factors (backward compatible).

        **Validates: Requirement 2.2**
        """
        result = _extract_required_factors(config)
        assert result == ALL_FACTORS, (
            f"Expected ALL_FACTORS {ALL_FACTORS}, got {result}"
        )
