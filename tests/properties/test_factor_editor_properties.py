"""
因子条件编辑器优化 — 属性测试（Hypothesis）

Feature: factor-editor-optimization

Property 1: FACTOR_REGISTRY 结构完整性
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    FactorMeta,
    ThresholdType,
)


# ---------------------------------------------------------------------------
# Property 1: FACTOR_REGISTRY 结构完整性
# Feature: factor-editor-optimization, Property 1: FACTOR_REGISTRY 结构完整性
# ---------------------------------------------------------------------------

# Strategy: sample a factor_name key from the actual registry
_factor_name_strategy = st.sampled_from(list(FACTOR_REGISTRY.keys()))


@settings(max_examples=100)
@given(factor_name=_factor_name_strategy)
def test_factor_registry_structure_integrity(factor_name: str):
    """
    # Feature: factor-editor-optimization, Property 1: FACTOR_REGISTRY 结构完整性

    **Validates: Requirements 1.2, 1.3**

    For any factor entry in FACTOR_REGISTRY:
    - The entry SHALL be a FactorMeta instance
    - The entry SHALL have all required metadata fields with valid types:
      factor_name (str), label (str), category (FactorCategory),
      threshold_type (ThresholdType), description (str)
    - threshold_type SHALL be a valid ThresholdType enum member
    - category SHALL be a valid FactorCategory enum member
    - The dict key SHALL match the FactorMeta.factor_name field
    """
    meta = FACTOR_REGISTRY[factor_name]

    # Entry is a FactorMeta instance
    assert isinstance(meta, FactorMeta), (
        f"FACTOR_REGISTRY['{factor_name}'] should be FactorMeta, got {type(meta)}"
    )

    # Dict key matches factor_name field
    assert meta.factor_name == factor_name, (
        f"Key '{factor_name}' does not match meta.factor_name '{meta.factor_name}'"
    )

    # Required string fields are non-empty strings
    assert isinstance(meta.factor_name, str) and len(meta.factor_name) > 0, (
        f"factor_name should be a non-empty string, got {meta.factor_name!r}"
    )
    assert isinstance(meta.label, str) and len(meta.label) > 0, (
        f"label should be a non-empty string, got {meta.label!r}"
    )
    assert isinstance(meta.description, str) and len(meta.description) > 0, (
        f"description should be a non-empty string, got {meta.description!r}"
    )

    # threshold_type is a valid ThresholdType enum member
    assert isinstance(meta.threshold_type, ThresholdType), (
        f"threshold_type should be ThresholdType, got {type(meta.threshold_type)}"
    )
    assert meta.threshold_type in ThresholdType, (
        f"threshold_type '{meta.threshold_type}' is not a valid ThresholdType member"
    )

    # category is a valid FactorCategory enum member
    assert isinstance(meta.category, FactorCategory), (
        f"category should be FactorCategory, got {type(meta.category)}"
    )
    assert meta.category in FactorCategory, (
        f"category '{meta.category}' is not a valid FactorCategory member"
    )

    # Optional numeric fields have valid types when present
    if meta.default_threshold is not None:
        assert isinstance(meta.default_threshold, (int, float)), (
            f"default_threshold should be numeric, got {type(meta.default_threshold)}"
        )
    if meta.value_min is not None:
        assert isinstance(meta.value_min, (int, float)), (
            f"value_min should be numeric, got {type(meta.value_min)}"
        )
    if meta.value_max is not None:
        assert isinstance(meta.value_max, (int, float)), (
            f"value_max should be numeric, got {type(meta.value_max)}"
        )

    # When both value_min and value_max are present, min <= max
    if meta.value_min is not None and meta.value_max is not None:
        assert meta.value_min <= meta.value_max, (
            f"value_min ({meta.value_min}) should be <= value_max ({meta.value_max})"
        )

    # unit is a string (may be empty)
    assert isinstance(meta.unit, str), (
        f"unit should be a string, got {type(meta.unit)}"
    )

    # examples is a list of dicts
    assert isinstance(meta.examples, list), (
        f"examples should be a list, got {type(meta.examples)}"
    )
    for i, example in enumerate(meta.examples):
        assert isinstance(example, dict), (
            f"examples[{i}] should be a dict, got {type(example)}"
        )

    # default_range validation for RANGE type
    if meta.threshold_type == ThresholdType.RANGE:
        assert meta.default_range is not None, (
            f"RANGE-type factor '{factor_name}' should have a default_range"
        )
        assert isinstance(meta.default_range, tuple) and len(meta.default_range) == 2, (
            f"default_range should be a 2-tuple, got {meta.default_range!r}"
        )
        low, high = meta.default_range
        assert isinstance(low, (int, float)) and isinstance(high, (int, float)), (
            f"default_range elements should be numeric, got ({type(low)}, {type(high)})"
        )
        assert low <= high, (
            f"default_range low ({low}) should be <= high ({high})"
        )


# ---------------------------------------------------------------------------
# Property 9: 策略示例一致性
# Feature: factor-editor-optimization, Property 9: 策略示例一致性
# ---------------------------------------------------------------------------

from app.services.screener.strategy_examples import STRATEGY_EXAMPLES, StrategyExample

_strategy_example_strategy = st.sampled_from(STRATEGY_EXAMPLES)


@settings(max_examples=100)
@given(example=_strategy_example_strategy)
def test_strategy_examples_consistency(example: StrategyExample):
    """
    # Feature: factor-editor-optimization, Property 9: 策略示例一致性

    **Validates: Requirements 14.5, 14.8**

    For any strategy example in STRATEGY_EXAMPLES:
    - The example SHALL contain all required fields: name, description, factors,
      logic, weights, enabled_modules
    - Every factor_name referenced in the example's factors list SHALL exist
      in FACTOR_REGISTRY
    - Threshold values (when not None) SHALL be within the factor's defined
      value range [value_min, value_max]
    """
    # --- Required fields are present and have valid types ---
    assert isinstance(example.name, str) and len(example.name) > 0, (
        f"Strategy example name should be a non-empty string, got {example.name!r}"
    )
    assert isinstance(example.description, str) and len(example.description) > 0, (
        f"Strategy example description should be a non-empty string, got {example.description!r}"
    )
    assert isinstance(example.factors, list) and len(example.factors) > 0, (
        f"Strategy example '{example.name}' factors should be a non-empty list"
    )
    assert example.logic in ("AND", "OR"), (
        f"Strategy example '{example.name}' logic should be 'AND' or 'OR', got {example.logic!r}"
    )
    assert isinstance(example.weights, dict), (
        f"Strategy example '{example.name}' weights should be a dict"
    )
    assert isinstance(example.enabled_modules, list), (
        f"Strategy example '{example.name}' enabled_modules should be a list"
    )

    # --- Every factor_name exists in FACTOR_REGISTRY ---
    for i, factor in enumerate(example.factors):
        assert isinstance(factor, dict), (
            f"Strategy '{example.name}' factors[{i}] should be a dict"
        )
        factor_name = factor.get("factor_name")
        assert factor_name is not None, (
            f"Strategy '{example.name}' factors[{i}] missing 'factor_name'"
        )
        assert factor_name in FACTOR_REGISTRY, (
            f"Strategy '{example.name}' factors[{i}] factor_name '{factor_name}' "
            f"not found in FACTOR_REGISTRY"
        )

        meta = FACTOR_REGISTRY[factor_name]

        # --- Threshold within defined value range ---
        threshold = factor.get("threshold")
        if threshold is not None and meta.value_min is not None and meta.value_max is not None:
            assert meta.value_min <= threshold <= meta.value_max, (
                f"Strategy '{example.name}' factors[{i}] factor '{factor_name}' "
                f"threshold {threshold} outside range [{meta.value_min}, {meta.value_max}]"
            )

        # --- RANGE-type threshold_low/threshold_high within value range ---
        params = factor.get("params", {})
        if "threshold_low" in params and "threshold_high" in params:
            t_low = params["threshold_low"]
            t_high = params["threshold_high"]
            if meta.value_min is not None and meta.value_max is not None:
                assert meta.value_min <= t_low <= meta.value_max, (
                    f"Strategy '{example.name}' factors[{i}] factor '{factor_name}' "
                    f"threshold_low {t_low} outside range [{meta.value_min}, {meta.value_max}]"
                )
                assert meta.value_min <= t_high <= meta.value_max, (
                    f"Strategy '{example.name}' factors[{i}] factor '{factor_name}' "
                    f"threshold_high {t_high} outside range [{meta.value_min}, {meta.value_max}]"
                )
                assert t_low <= t_high, (
                    f"Strategy '{example.name}' factors[{i}] factor '{factor_name}' "
                    f"threshold_low {t_low} > threshold_high {t_high}"
                )


# ---------------------------------------------------------------------------
# Property 7: StrategyConfig 序列化往返
# Feature: factor-editor-optimization, Property 7: StrategyConfig 序列化往返
# ---------------------------------------------------------------------------

from app.core.schemas import (
    BreakoutConfig,
    FactorCondition,
    IndicatorParamsConfig,
    MaTrendConfig,
    SectorScreenConfig,
    StrategyConfig,
    VolumePriceConfig,
)

# -- Hypothesis strategies for generating random config instances --

_valid_operators = st.sampled_from([">=", "<=", ">", "<", "==", "cross_up", "cross_down"])

_factor_condition_strategy = st.builds(
    FactorCondition,
    factor_name=st.sampled_from(list(FACTOR_REGISTRY.keys())),
    operator=_valid_operators,
    threshold=st.one_of(st.none(), st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)),
    params=st.fixed_dictionaries(
        {},
        optional={
            "threshold_low": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            "threshold_high": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            "threshold_type": st.sampled_from(["absolute", "percentile", "industry_relative"]),
            "sector_data_source": st.sampled_from(["DC", "TI", "TDX"]),
            "sector_type": st.sampled_from(["INDUSTRY", "CONCEPT", "REGION", "STYLE"]),
            "sector_period": st.integers(min_value=1, max_value=60),
        },
    ),
)

_sector_screen_config_strategy = st.builds(
    SectorScreenConfig,
    sector_data_source=st.sampled_from(["DC", "TI", "TDX"]),
    sector_type=st.sampled_from(["INDUSTRY", "CONCEPT", "REGION", "STYLE"]),
    sector_period=st.integers(min_value=1, max_value=60),
    sector_top_n=st.integers(min_value=1, max_value=300),
)

_indicator_params_strategy = st.builds(
    IndicatorParamsConfig,
    macd_fast=st.integers(min_value=1, max_value=50),
    macd_slow=st.integers(min_value=1, max_value=100),
    macd_signal=st.integers(min_value=1, max_value=50),
    boll_period=st.integers(min_value=1, max_value=100),
    boll_std_dev=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    rsi_period=st.integers(min_value=1, max_value=100),
    rsi_lower=st.integers(min_value=0, max_value=100),
    rsi_upper=st.integers(min_value=0, max_value=100),
    dma_short=st.integers(min_value=1, max_value=100),
    dma_long=st.integers(min_value=1, max_value=200),
)

_ma_trend_config_strategy = st.builds(
    MaTrendConfig,
    ma_periods=st.lists(st.integers(min_value=1, max_value=250), min_size=1, max_size=6),
    slope_threshold=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    trend_score_threshold=st.integers(min_value=0, max_value=100),
    support_ma_lines=st.lists(st.integers(min_value=1, max_value=250), min_size=1, max_size=4),
)

_breakout_config_strategy = st.builds(
    BreakoutConfig,
    box_breakout=st.booleans(),
    high_breakout=st.booleans(),
    trendline_breakout=st.booleans(),
    volume_ratio_threshold=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    confirm_days=st.integers(min_value=1, max_value=10),
)

_volume_price_config_strategy = st.builds(
    VolumePriceConfig,
    turnover_rate_min=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    turnover_rate_max=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    main_flow_threshold=st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    main_flow_days=st.integers(min_value=1, max_value=10),
    large_order_ratio=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    min_daily_amount=st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    sector_rank_top=st.integers(min_value=1, max_value=300),
)

_strategy_config_strategy = st.builds(
    StrategyConfig,
    factors=st.lists(_factor_condition_strategy, min_size=0, max_size=8),
    logic=st.sampled_from(["AND", "OR"]),
    weights=st.dictionaries(
        keys=st.sampled_from(list(FACTOR_REGISTRY.keys())),
        values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=6,
    ),
    ma_periods=st.lists(st.integers(min_value=1, max_value=250), min_size=1, max_size=6),
    indicator_params=_indicator_params_strategy,
    ma_trend=_ma_trend_config_strategy,
    breakout=_breakout_config_strategy,
    volume_price=_volume_price_config_strategy,
    sector_config=_sector_screen_config_strategy,
)


@settings(max_examples=100)
@given(config=_strategy_config_strategy)
def test_strategy_config_round_trip_serialization(config: StrategyConfig):
    """
    # Feature: factor-editor-optimization, Property 7: StrategyConfig 序列化往返

    **Validates: Requirements 5.1, 13.3, 13.4**

    For any valid StrategyConfig instance (including sector_config),
    calling to_dict() then from_dict() SHALL produce a StrategyConfig
    with equivalent field values.
    """
    serialized = config.to_dict()
    restored = StrategyConfig.from_dict(serialized)

    # -- factors round-trip --
    assert len(restored.factors) == len(config.factors), (
        f"Factor count mismatch: {len(restored.factors)} != {len(config.factors)}"
    )
    for i, (orig, rest) in enumerate(zip(config.factors, restored.factors)):
        assert rest.factor_name == orig.factor_name, (
            f"factors[{i}].factor_name: {rest.factor_name!r} != {orig.factor_name!r}"
        )
        assert rest.operator == orig.operator, (
            f"factors[{i}].operator: {rest.operator!r} != {orig.operator!r}"
        )
        assert rest.threshold == orig.threshold, (
            f"factors[{i}].threshold: {rest.threshold!r} != {orig.threshold!r}"
        )
        assert rest.params == orig.params, (
            f"factors[{i}].params: {rest.params!r} != {orig.params!r}"
        )

    # -- top-level scalar fields --
    assert restored.logic == config.logic, (
        f"logic: {restored.logic!r} != {config.logic!r}"
    )
    assert restored.weights == config.weights, (
        f"weights mismatch"
    )
    assert restored.ma_periods == config.ma_periods, (
        f"ma_periods mismatch"
    )

    # -- indicator_params round-trip --
    assert restored.indicator_params.to_dict() == config.indicator_params.to_dict(), (
        "indicator_params mismatch after round-trip"
    )

    # -- ma_trend round-trip --
    assert restored.ma_trend.to_dict() == config.ma_trend.to_dict(), (
        "ma_trend mismatch after round-trip"
    )

    # -- breakout round-trip --
    assert restored.breakout.to_dict() == config.breakout.to_dict(), (
        "breakout mismatch after round-trip"
    )

    # -- volume_price round-trip --
    assert restored.volume_price.to_dict() == config.volume_price.to_dict(), (
        "volume_price mismatch after round-trip"
    )

    # -- sector_config round-trip (Requirements 5.1, 13.3, 13.4) --
    assert restored.sector_config.sector_data_source == config.sector_config.sector_data_source, (
        f"sector_config.sector_data_source: {restored.sector_config.sector_data_source!r} "
        f"!= {config.sector_config.sector_data_source!r}"
    )
    assert restored.sector_config.sector_type == config.sector_config.sector_type, (
        f"sector_config.sector_type: {restored.sector_config.sector_type!r} "
        f"!= {config.sector_config.sector_type!r}"
    )
    assert restored.sector_config.sector_period == config.sector_config.sector_period, (
        f"sector_config.sector_period: {restored.sector_config.sector_period!r} "
        f"!= {config.sector_config.sector_period!r}"
    )
    assert restored.sector_config.sector_top_n == config.sector_config.sector_top_n, (
        f"sector_config.sector_top_n: {restored.sector_config.sector_top_n!r} "
        f"!= {config.sector_config.sector_top_n!r}"
    )


# ---------------------------------------------------------------------------
# Property 8: 向后兼容默认值
# Feature: factor-editor-optimization, Property 8: 向后兼容默认值
# ---------------------------------------------------------------------------

from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
from app.services.screener.factor_registry import ThresholdType, get_factor_meta

# Strategy: generate legacy config dicts that do NOT contain sector_config,
# and legacy FactorCondition dicts that do NOT contain threshold_type in params.

_legacy_factor_condition_strategy = st.fixed_dictionaries(
    {
        "factor_name": st.sampled_from(list(FACTOR_REGISTRY.keys())),
        "operator": st.sampled_from([">=", "<=", ">", "<", "=="]),
        "threshold": st.one_of(
            st.none(),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        ),
    },
    optional={
        "params": st.fixed_dictionaries(
            {},
            optional={
                "threshold_low": st.floats(
                    min_value=0, max_value=100, allow_nan=False, allow_infinity=False
                ),
                "threshold_high": st.floats(
                    min_value=0, max_value=100, allow_nan=False, allow_infinity=False
                ),
            },
        ),
    },
)

_legacy_config_strategy = st.fixed_dictionaries(
    {
        "factors": st.lists(_legacy_factor_condition_strategy, min_size=0, max_size=5),
        "logic": st.sampled_from(["AND", "OR"]),
    },
    optional={
        "weights": st.dictionaries(
            keys=st.sampled_from(list(FACTOR_REGISTRY.keys())),
            values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=4,
        ),
        "ma_periods": st.lists(st.integers(min_value=1, max_value=250), min_size=1, max_size=6),
        "indicator_params": st.fixed_dictionaries(
            {},
            optional={
                "macd_fast": st.integers(min_value=1, max_value=50),
                "macd_slow": st.integers(min_value=1, max_value=100),
                "rsi_period": st.integers(min_value=1, max_value=100),
            },
        ),
    },
)


@settings(max_examples=100)
@given(legacy_dict=_legacy_config_strategy)
def test_backward_compatible_default_values(legacy_dict: dict):
    """
    # Feature: factor-editor-optimization, Property 8: 向后兼容默认值

    **Validates: Requirements 13.1, 13.2**

    For any legacy config dictionary that does NOT contain sector_config,
    deserialization SHALL produce a valid StrategyConfig with:
    - sector_config defaulting to SectorScreenConfig(
          sector_data_source="DC", sector_type="CONCEPT",
          sector_period=5, sector_top_n=30)

    For any legacy FactorCondition that does NOT contain threshold_type
    in params, the FactorEvaluator SHALL fall back to ABSOLUTE threshold
    type — i.e. it reads the raw factor_name field from stock_data,
    not _pctl or _ind_rel suffixed fields.
    """
    # --- Part 1: StrategyConfig.from_dict() produces valid sector_config defaults ---
    assert "sector_config" not in legacy_dict, (
        "Test generator should not produce sector_config in legacy dict"
    )

    config = StrategyConfig.from_dict(legacy_dict)

    # sector_config must be a SectorScreenConfig with expected defaults
    assert isinstance(config.sector_config, SectorScreenConfig), (
        f"sector_config should be SectorScreenConfig, got {type(config.sector_config)}"
    )
    assert config.sector_config.sector_data_source == "DC", (
        f"sector_data_source should default to 'DC', got {config.sector_config.sector_data_source!r}"
    )
    assert config.sector_config.sector_type == "CONCEPT", (
        f"sector_type should default to 'CONCEPT', got {config.sector_config.sector_type!r}"
    )
    assert config.sector_config.sector_period == 5, (
        f"sector_period should default to 5, got {config.sector_config.sector_period!r}"
    )
    assert config.sector_config.sector_top_n == 30, (
        f"sector_top_n should default to 30, got {config.sector_config.sector_top_n!r}"
    )

    # --- Part 2: FactorEvaluator falls back to ABSOLUTE when threshold_type not in params ---
    # Requirement 13.1: When loading a legacy FactorCondition without threshold_type,
    # the evaluator SHALL fall back to ABSOLUTE threshold type.
    # We test this by using a factor_name NOT in FACTOR_REGISTRY, so the evaluator
    # has no registry entry and must default to ABSOLUTE.
    for factor_dict in legacy_dict.get("factors", []):
        params = factor_dict.get("params", {})
        # Confirm no threshold_type in the generated legacy params
        assert "threshold_type" not in params, (
            "Legacy factor params should not contain threshold_type"
        )

        # Use a synthetic factor_name not in FACTOR_REGISTRY to force ABSOLUTE fallback
        condition = FactorCondition(
            factor_name="legacy_unknown_factor",
            operator=factor_dict["operator"],
            threshold=factor_dict.get("threshold"),
            params=params,
        )

        # Build stock_data with the raw factor_name field (ABSOLUTE behavior)
        raw_value = 50.0
        stock_data = {"legacy_unknown_factor": raw_value}

        result = FactorEvaluator.evaluate(condition, stock_data, weight=1.0)
        assert isinstance(result, FactorEvalResult), (
            f"evaluate() should return FactorEvalResult, got {type(result)}"
        )

        # The evaluator should NOT look for _pctl or _ind_rel fields
        # since it falls back to ABSOLUTE for unknown factors.
        if condition.threshold is None:
            # Boolean-like: raw_value=50.0 is truthy → passed
            assert result.passed is True, (
                f"Boolean fallback with truthy value should pass, got passed={result.passed}"
            )
        else:
            op_fn = FactorEvaluator._OPERATORS.get(condition.operator)
            if op_fn is not None:
                expected = op_fn(raw_value, condition.threshold)
                assert result.passed == expected, (
                    f"ABSOLUTE fallback: {raw_value} {condition.operator} {condition.threshold} "
                    f"should be {expected}, got {result.passed}"
                )


# ---------------------------------------------------------------------------
# Property 6: 板块涨跌幅排名有序性
# Feature: factor-editor-optimization, Property 6: 板块涨跌幅排名有序性
# ---------------------------------------------------------------------------

from app.services.screener.sector_strength import (
    SectorRankResult,
    SectorStrengthFilter,
)

# -- Hypothesis strategies for sector rank data --

# Generate unique sector codes with associated change_pct values.
# We use unique sector codes to avoid ambiguity in ranking.
_sector_code_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Nd")),
    min_size=3,
    max_size=8,
)

_sector_rank_result_strategy = st.builds(
    SectorRankResult,
    sector_code=_sector_code_strategy,
    sector_name=st.text(min_size=1, max_size=10),
    rank=st.just(0),  # placeholder, will be reassigned
    change_pct=st.floats(
        min_value=-50.0, max_value=50.0,
        allow_nan=False, allow_infinity=False,
    ),
    is_bullish=st.booleans(),
)

# Strategy: generate a list of SectorRankResult with unique sector_codes,
# then sort by change_pct descending and assign correct ranks.
@st.composite
def _sector_ranks_strategy(draw):
    """Generate a properly ranked list of SectorRankResult instances.

    Produces 1-20 sectors with unique codes, sorted by change_pct descending,
    with ranks assigned starting from 1.
    """
    n = draw(st.integers(min_value=1, max_value=20))
    codes = draw(
        st.lists(
            _sector_code_strategy,
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    results = []
    for code in codes:
        name = draw(st.text(min_size=1, max_size=10))
        change = draw(st.floats(
            min_value=-50.0, max_value=50.0,
            allow_nan=False, allow_infinity=False,
        ))
        bullish = draw(st.booleans())
        results.append(SectorRankResult(
            sector_code=code,
            sector_name=name,
            rank=0,
            change_pct=change,
            is_bullish=bullish,
        ))

    # Sort by change_pct descending and assign ranks
    results.sort(key=lambda r: r.change_pct, reverse=True)
    for idx, r in enumerate(results, start=1):
        r.rank = idx

    return results


# Strategy: generate stock-to-sector mapping where stocks reference
# sector codes from the generated sector_ranks.
@st.composite
def _stocks_and_mapping_strategy(draw):
    """Generate stocks_data, sector_ranks, and stock_sector_map together.

    Returns (stocks_data, sector_ranks, stock_sector_map, top_n) where:
    - sector_ranks is a properly ranked list of SectorRankResult
    - stock_sector_map maps some stocks to sector codes from sector_ranks
    - stocks_data contains factor dicts for all stocks
    - Some stocks may have no sector mapping (to test None handling)
    """
    sector_ranks = draw(_sector_ranks_strategy())
    sector_codes = [r.sector_code for r in sector_ranks]

    # Generate stock symbols
    n_stocks = draw(st.integers(min_value=1, max_value=30))
    stock_symbols = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Nd")),
                min_size=4,
                max_size=10,
            ),
            min_size=n_stocks,
            max_size=n_stocks,
            unique=True,
        )
    )

    stocks_data: dict[str, dict] = {}
    stock_sector_map: dict[str, list[str]] = {}

    for symbol in stock_symbols:
        stocks_data[symbol] = {}
        # Randomly decide if this stock has sector mapping
        has_mapping = draw(st.booleans())
        if has_mapping and sector_codes:
            # Assign 1-3 sector codes from the available sectors
            n_sectors = draw(st.integers(
                min_value=1,
                max_value=min(3, len(sector_codes)),
            ))
            chosen = draw(st.lists(
                st.sampled_from(sector_codes),
                min_size=n_sectors,
                max_size=n_sectors,
                unique=True,
            ))
            stock_sector_map[symbol] = chosen

    top_n = draw(st.integers(min_value=1, max_value=max(len(sector_ranks), 1)))

    return stocks_data, sector_ranks, stock_sector_map, top_n


@settings(max_examples=100)
@given(data=_sector_ranks_strategy())
def test_sector_rank_ordering(data: list[SectorRankResult]):
    """
    # Feature: factor-editor-optimization, Property 6: 板块涨跌幅排名有序性

    **Validates: Requirements 5.4, 5.5**

    Part A — Rank ordering:
    For any set of sector rank results, the ranks SHALL be in descending
    order of cumulative change_pct (rank 1 = highest change).

    This verifies that:
    - Rank 1 has the highest change_pct
    - For any two sectors, if sector A has a higher change_pct than sector B,
      then sector A's rank ≤ sector B's rank
    - Ranks are consecutive integers starting from 1
    """
    if not data:
        return

    # Verify ranks are consecutive integers starting from 1
    ranks = [r.rank for r in data]
    assert ranks == list(range(1, len(data) + 1)), (
        f"Ranks should be consecutive 1..{len(data)}, got {ranks}"
    )

    # Verify descending order of change_pct by rank
    for i in range(len(data) - 1):
        assert data[i].change_pct >= data[i + 1].change_pct, (
            f"Rank {data[i].rank} (change_pct={data[i].change_pct}) should have "
            f">= change_pct than rank {data[i + 1].rank} "
            f"(change_pct={data[i + 1].change_pct})"
        )

    # Verify rank 1 has the highest change_pct
    max_change = max(r.change_pct for r in data)
    assert data[0].change_pct == max_change, (
        f"Rank 1 should have the highest change_pct ({max_change}), "
        f"got {data[0].change_pct}"
    )

    # Also verify via compute_sector_strength pure function:
    # Build kline data from the sector ranks and verify ordering matches
    kline_data = [
        {"sector_code": r.sector_code, "change_pct": r.change_pct}
        for r in data
    ]
    ranked = SectorStrengthFilter.compute_sector_strength(kline_data)

    # ranked is sorted descending by total change_pct
    for i in range(len(ranked) - 1):
        assert ranked[i][1] >= ranked[i + 1][1], (
            f"compute_sector_strength result not sorted descending: "
            f"{ranked[i][1]} < {ranked[i + 1][1]}"
        )


@settings(max_examples=100)
@given(bundle=_stocks_and_mapping_strategy())
def test_sector_stock_mapping_consistency(bundle):
    """
    # Feature: factor-editor-optimization, Property 6: 板块涨跌幅排名有序性

    **Validates: Requirements 5.4, 5.5**

    Part B — Stock-to-sector mapping consistency:
    For any stock appearing in a sector's constituent list, the
    filter_by_sector_strength method SHALL:
    - Write sector_rank equal to the best (lowest) rank among the stock's sectors
    - Write sector_trend and sector_name from the best-ranked sector
    - Set sector_rank = None for stocks not in any sector mapping
    """
    stocks_data, sector_ranks, stock_sector_map, top_n = bundle

    ssf = SectorStrengthFilter()
    ssf.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map, top_n)

    # Build lookup for verification
    rank_map: dict[str, SectorRankResult] = {
        r.sector_code: r for r in sector_ranks
    }

    for symbol, factor_dict in stocks_data.items():
        sector_codes = stock_sector_map.get(symbol, [])

        if not sector_codes:
            # Stock not in any sector → sector_rank should be None
            assert factor_dict["sector_rank"] is None, (
                f"Stock '{symbol}' has no sector mapping but got "
                f"sector_rank={factor_dict['sector_rank']}"
            )
            assert factor_dict["sector_trend"] is False, (
                f"Stock '{symbol}' has no sector mapping but got "
                f"sector_trend={factor_dict['sector_trend']}"
            )
            assert factor_dict["sector_name"] is None, (
                f"Stock '{symbol}' has no sector mapping but got "
                f"sector_name={factor_dict['sector_name']}"
            )
        else:
            # Find the best (lowest rank) sector among the stock's sectors
            best_result: SectorRankResult | None = None
            for code in sector_codes:
                result = rank_map.get(code)
                if result is not None:
                    if best_result is None or result.rank < best_result.rank:
                        best_result = result

            if best_result is not None:
                assert factor_dict["sector_rank"] == best_result.rank, (
                    f"Stock '{symbol}' sector_rank should be {best_result.rank}, "
                    f"got {factor_dict['sector_rank']}"
                )
                assert factor_dict["sector_trend"] == best_result.is_bullish, (
                    f"Stock '{symbol}' sector_trend should be {best_result.is_bullish}, "
                    f"got {factor_dict['sector_trend']}"
                )
                assert factor_dict["sector_name"] == best_result.sector_name, (
                    f"Stock '{symbol}' sector_name should be {best_result.sector_name!r}, "
                    f"got {factor_dict['sector_name']!r}"
                )
            else:
                # Stock's sector codes not found in rank_map
                assert factor_dict["sector_rank"] is None, (
                    f"Stock '{symbol}' sectors not in rank_map but got "
                    f"sector_rank={factor_dict['sector_rank']}"
                )


# ---------------------------------------------------------------------------
# Property 2: 百分位排名不变量
# Feature: factor-editor-optimization, Property 2: 百分位排名不变量
# ---------------------------------------------------------------------------

from app.services.screener.screen_data_provider import ScreenDataProvider

# Strategy: generate random lists of float/None values representing factor values
# for a set of stocks. We use finite floats to avoid NaN/Inf edge cases that
# are not meaningful for percentile ranking.
_float_or_none = st.one_of(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.none(),
)

_factor_values_strategy = st.lists(
    _float_or_none,
    min_size=1,
    max_size=200,
)


@settings(max_examples=100)
@given(values=_factor_values_strategy)
def test_percentile_ranking_invariants(values: list[float | None]):
    """
    # Feature: factor-editor-optimization, Property 2: 百分位排名不变量

    **Validates: Requirements 3.3, 3.6, 9.1, 9.2, 9.3, 9.6**

    For any non-empty set of stock factor values (with None values excluded),
    the computed percentile ranks SHALL satisfy:
    1. All rank values are in the closed interval [0, 100]
    2. None-valued stocks receive no percentile rank (their _pctl field is None)
    3. The stock with the maximum raw value receives the highest percentile rank
    4. The stock with the minimum raw value receives the lowest percentile rank
    5. Monotonicity: if stock A's raw value > stock B's raw value,
       then A's percentile >= B's percentile
    """
    test_factor = "test_factor"
    pctl_field = f"{test_factor}_pctl"

    # Build stocks_data dict: symbol -> {test_factor: value}
    stocks_data: dict[str, dict] = {}
    for i, val in enumerate(values):
        symbol = f"S{i:04d}"
        stocks_data[symbol] = {test_factor: val}

    # Call _compute_percentile_ranks
    ScreenDataProvider._compute_percentile_ranks(stocks_data, [test_factor])

    # Separate valid (non-None) and None stocks
    valid_symbols = [
        (sym, stocks_data[sym][test_factor], stocks_data[sym].get(pctl_field))
        for sym in stocks_data
        if stocks_data[sym][test_factor] is not None
    ]
    none_symbols = [
        sym for sym in stocks_data
        if stocks_data[sym][test_factor] is None
    ]

    # --- Invariant 2: None-valued stocks get None percentile rank ---
    for sym in none_symbols:
        assert stocks_data[sym].get(pctl_field) is None, (
            f"Stock '{sym}' has None factor value but got "
            f"pctl={stocks_data[sym].get(pctl_field)}"
        )

    # If no valid stocks, nothing more to check
    if not valid_symbols:
        return

    # --- Invariant 1: All rank values are in [0, 100] ---
    for sym, raw_val, pctl_val in valid_symbols:
        assert pctl_val is not None, (
            f"Stock '{sym}' has valid factor value {raw_val} but pctl is None"
        )
        assert 0 <= pctl_val <= 100, (
            f"Stock '{sym}' pctl={pctl_val} is outside [0, 100]"
        )

    # --- Invariant 3: Max raw value gets highest percentile rank ---
    max_raw = max(raw_val for _, raw_val, _ in valid_symbols)
    max_pctl = max(pctl_val for _, _, pctl_val in valid_symbols)
    # All stocks with the maximum raw value should have the highest percentile
    for sym, raw_val, pctl_val in valid_symbols:
        if raw_val == max_raw:
            assert pctl_val == max_pctl, (
                f"Stock '{sym}' has max raw value {raw_val} but pctl={pctl_val} "
                f"!= max_pctl={max_pctl}"
            )

    # --- Invariant 4: Min raw value gets lowest percentile rank ---
    min_raw = min(raw_val for _, raw_val, _ in valid_symbols)
    min_pctl = min(pctl_val for _, _, pctl_val in valid_symbols)
    # All stocks with the minimum raw value should have the lowest percentile
    for sym, raw_val, pctl_val in valid_symbols:
        if raw_val == min_raw:
            assert pctl_val == min_pctl, (
                f"Stock '{sym}' has min raw value {raw_val} but pctl={pctl_val} "
                f"!= min_pctl={min_pctl}"
            )

    # --- Invariant 5: Monotonicity ---
    # For any two stocks, if A's raw value > B's raw value,
    # then A's percentile >= B's percentile
    for i in range(len(valid_symbols)):
        for j in range(i + 1, len(valid_symbols)):
            sym_a, raw_a, pctl_a = valid_symbols[i]
            sym_b, raw_b, pctl_b = valid_symbols[j]
            if raw_a > raw_b:
                assert pctl_a >= pctl_b, (
                    f"Monotonicity violated: {sym_a} raw={raw_a} pctl={pctl_a} "
                    f"vs {sym_b} raw={raw_b} pctl={pctl_b}"
                )
            elif raw_b > raw_a:
                assert pctl_b >= pctl_a, (
                    f"Monotonicity violated: {sym_b} raw={raw_b} pctl={pctl_b} "
                    f"vs {sym_a} raw={raw_a} pctl={pctl_a}"
                )


# ---------------------------------------------------------------------------
# Property 3: 行业相对值计算正确性
# Feature: factor-editor-optimization, Property 3: 行业相对值计算正确性
# ---------------------------------------------------------------------------

import statistics as _statistics

# Strategy: generate stocks grouped by industry with positive factor values.
# Each industry has 1-10 stocks, and we generate 1-5 industries.
# All factor values are positive (> 0) to ensure valid median division.

@st.composite
def _industry_stocks_strategy(draw):
    """Generate stocks_data, industry_map, and factor_name for testing
    industry-relative value computation.

    Returns (stocks_data, industry_map, factor_name) where:
    - stocks_data: dict[str, dict] with {factor_name: positive_float} per stock
    - industry_map: dict[str, str] mapping symbol -> industry_code
    - factor_name: the factor name used in stocks_data
    - Some stocks may intentionally have no industry mapping (to test None handling)
    """
    factor_name = "test_ind_factor"

    # Generate 1-5 unique industry codes
    n_industries = draw(st.integers(min_value=1, max_value=5))
    industry_codes = [f"IND{i:03d}" for i in range(n_industries)]

    stocks_data: dict[str, dict] = {}
    industry_map: dict[str, str] = {}
    stock_idx = 0

    # For each industry, generate 1-10 stocks with positive values
    for ind_code in industry_codes:
        n_stocks = draw(st.integers(min_value=1, max_value=10))
        for _ in range(n_stocks):
            symbol = f"STK{stock_idx:04d}"
            val = draw(st.floats(
                min_value=0.01, max_value=1e6,
                allow_nan=False, allow_infinity=False,
            ))
            stocks_data[symbol] = {factor_name: val}
            industry_map[symbol] = ind_code
            stock_idx += 1

    # Optionally add some stocks with no industry mapping
    n_unmapped = draw(st.integers(min_value=0, max_value=3))
    for _ in range(n_unmapped):
        symbol = f"STK{stock_idx:04d}"
        val = draw(st.floats(
            min_value=0.01, max_value=1e6,
            allow_nan=False, allow_infinity=False,
        ))
        stocks_data[symbol] = {factor_name: val}
        # Deliberately NOT adding to industry_map
        stock_idx += 1

    return stocks_data, industry_map, factor_name


@settings(max_examples=100)
@given(bundle=_industry_stocks_strategy())
def test_industry_relative_value_correctness(bundle):
    """
    # Feature: factor-editor-optimization, Property 3: 行业相对值计算正确性

    **Validates: Requirements 4.7, 10.1, 10.3**

    For any set of stocks grouped by industry with positive factor values,
    the industry relative value SHALL equal (stock_value / industry_median),
    and a stock whose factor value equals the industry median SHALL have
    an industry relative value of 1.0.

    Additionally, stocks with no industry mapping SHALL get None for the
    _ind_rel field.
    """
    stocks_data, industry_map, factor_name = bundle
    ind_rel_field = f"{factor_name}_ind_rel"

    # Call the method under test
    ScreenDataProvider._compute_industry_relative_values(
        stocks_data, [factor_name], industry_map,
    )

    # --- Pre-compute expected industry medians ---
    industry_values: dict[str, list[float]] = {}
    for symbol, data in stocks_data.items():
        ind_code = industry_map.get(symbol)
        if ind_code is None:
            continue
        val = data.get(factor_name)
        if val is None:
            continue
        if ind_code not in industry_values:
            industry_values[ind_code] = []
        industry_values[ind_code].append(float(val))

    industry_medians: dict[str, float] = {}
    for ind_code, vals in industry_values.items():
        if vals:
            industry_medians[ind_code] = _statistics.median(vals)

    # --- Verify each stock's _ind_rel value ---
    for symbol, data in stocks_data.items():
        ind_code = industry_map.get(symbol)
        val = data.get(factor_name)
        ind_rel = data.get(ind_rel_field)

        # Stocks with no industry mapping get None
        if ind_code is None:
            assert ind_rel is None, (
                f"Stock '{symbol}' has no industry mapping but got "
                f"ind_rel={ind_rel} (expected None)"
            )
            continue

        # Stocks with None factor value get None
        if val is None:
            assert ind_rel is None, (
                f"Stock '{symbol}' has None factor value but got "
                f"ind_rel={ind_rel} (expected None)"
            )
            continue

        median = industry_medians.get(ind_code)

        # If median is zero (shouldn't happen with positive values, but handle it)
        if median is None or median == 0:
            # Single-stock industry: relative value should be 1.0
            ind_vals = industry_values.get(ind_code, [])
            if len(ind_vals) == 1:
                assert ind_rel == 1.0, (
                    f"Stock '{symbol}' is sole member of industry '{ind_code}' "
                    f"but got ind_rel={ind_rel} (expected 1.0)"
                )
            else:
                assert ind_rel is None, (
                    f"Stock '{symbol}' in industry '{ind_code}' with zero median "
                    f"but got ind_rel={ind_rel} (expected None)"
                )
            continue

        # Core property: relative value = stock_value / industry_median
        expected_rel = float(val) / median
        assert abs(ind_rel - expected_rel) < 1e-9, (
            f"Stock '{symbol}' ind_rel={ind_rel} != expected "
            f"{val}/{median}={expected_rel}"
        )

    # --- Special check: stock at median gets 1.0 ---
    # For each industry with a non-zero median, verify that a stock whose
    # value equals the median would get relative value of 1.0.
    for ind_code, median in industry_medians.items():
        if median == 0:
            continue
        # Find stocks in this industry whose value equals the median
        for symbol, data in stocks_data.items():
            if industry_map.get(symbol) != ind_code:
                continue
            val = data.get(factor_name)
            if val is not None and float(val) == median:
                ind_rel = data.get(ind_rel_field)
                assert ind_rel is not None and abs(ind_rel - 1.0) < 1e-9, (
                    f"Stock '{symbol}' value={val} equals industry median "
                    f"{median} but got ind_rel={ind_rel} (expected 1.0)"
                )


# ---------------------------------------------------------------------------
# Property 4: FactorEvaluator 阈值类型字段解析
# Feature: factor-editor-optimization, Property 4: FactorEvaluator 阈值类型字段解析
# ---------------------------------------------------------------------------

# Group factors by threshold type for targeted generation.
_PERCENTILE_FACTORS = [
    name for name, meta in FACTOR_REGISTRY.items()
    if meta.threshold_type == ThresholdType.PERCENTILE
]
_INDUSTRY_RELATIVE_FACTORS = [
    name for name, meta in FACTOR_REGISTRY.items()
    if meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE
]
_ABSOLUTE_FACTORS = [
    name for name, meta in FACTOR_REGISTRY.items()
    if meta.threshold_type == ThresholdType.ABSOLUTE
]
_BOOLEAN_FACTORS = [
    name for name, meta in FACTOR_REGISTRY.items()
    if meta.threshold_type == ThresholdType.BOOLEAN
]

# Strategies for generating comparison operators and thresholds
_comparison_operators = st.sampled_from([">=", "<=", ">", "<", "=="])
_positive_float = st.floats(min_value=0.01, max_value=99.99, allow_nan=False, allow_infinity=False)


@st.composite
def _percentile_factor_scenario(draw):
    """Generate a PERCENTILE factor scenario: condition, stock_data, expected field."""
    factor_name = draw(st.sampled_from(_PERCENTILE_FACTORS))
    operator = draw(_comparison_operators)
    threshold = draw(_positive_float)
    pctl_value = draw(_positive_float)

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )
    # Stock data has both the raw field and the _pctl field.
    # The evaluator MUST read {factor_name}_pctl, not {factor_name}.
    stock_data = {
        factor_name: 999999.0,  # decoy raw value — should NOT be used
        f"{factor_name}_pctl": pctl_value,
    }
    return condition, stock_data, f"{factor_name}_pctl", pctl_value, operator, threshold


@st.composite
def _industry_relative_factor_scenario(draw):
    """Generate an INDUSTRY_RELATIVE factor scenario."""
    factor_name = draw(st.sampled_from(_INDUSTRY_RELATIVE_FACTORS))
    operator = draw(_comparison_operators)
    threshold = draw(st.floats(min_value=0.01, max_value=4.99, allow_nan=False, allow_infinity=False))
    ind_rel_value = draw(st.floats(min_value=0.01, max_value=4.99, allow_nan=False, allow_infinity=False))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )
    stock_data = {
        factor_name: 999999.0,  # decoy raw value
        f"{factor_name}_ind_rel": ind_rel_value,
    }
    return condition, stock_data, f"{factor_name}_ind_rel", ind_rel_value, operator, threshold


@st.composite
def _absolute_factor_scenario(draw):
    """Generate an ABSOLUTE factor scenario."""
    factor_name = draw(st.sampled_from(_ABSOLUTE_FACTORS))
    meta = FACTOR_REGISTRY[factor_name]
    v_min = meta.value_min if meta.value_min is not None else 0.0
    v_max = meta.value_max if meta.value_max is not None else 300.0
    operator = draw(_comparison_operators)
    threshold = draw(st.floats(min_value=v_min + 0.01, max_value=v_max - 0.01, allow_nan=False, allow_infinity=False))
    raw_value = draw(st.floats(min_value=v_min + 0.01, max_value=v_max - 0.01, allow_nan=False, allow_infinity=False))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )
    stock_data = {
        factor_name: raw_value,
    }
    return condition, stock_data, factor_name, raw_value, operator, threshold


@st.composite
def _boolean_factor_scenario(draw):
    """Generate a BOOLEAN factor scenario."""
    factor_name = draw(st.sampled_from(_BOOLEAN_FACTORS))
    bool_value = draw(st.sampled_from([True, False, 1, 0, 1.0, 0.0]))

    condition = FactorCondition(
        factor_name=factor_name,
        operator="==",
        threshold=None,  # boolean factors have no threshold
    )
    stock_data = {
        factor_name: bool_value,
    }
    return condition, stock_data, factor_name, bool_value


@settings(max_examples=100)
@given(scenario=st.one_of(
    _percentile_factor_scenario(),
    _industry_relative_factor_scenario(),
    _absolute_factor_scenario(),
))
def test_factor_evaluator_threshold_type_field_resolution(scenario):
    """
    # Feature: factor-editor-optimization, Property 4: FactorEvaluator 阈值类型字段解析

    **Validates: Requirements 9.5, 10.5, 12.1, 12.2, 12.3, 12.4**

    For any FactorCondition with a factor whose threshold_type is known
    in FACTOR_REGISTRY, the FactorEvaluator SHALL:
    - Read `{factor_name}_pctl` when threshold_type is PERCENTILE
    - Read `{factor_name}_ind_rel` when threshold_type is INDUSTRY_RELATIVE
    - Read `{factor_name}` when threshold_type is ABSOLUTE
    and the evaluation result (passed) SHALL be consistent with applying
    the comparison operator to the resolved field value and the threshold.
    """
    condition, stock_data, expected_field, resolved_value, operator, threshold = scenario

    result = FactorEvaluator.evaluate(condition, stock_data, weight=1.0)

    assert isinstance(result, FactorEvalResult), (
        f"evaluate() should return FactorEvalResult, got {type(result)}"
    )

    # The evaluator should have read the correct field
    assert result.value is not None, (
        f"Factor '{condition.factor_name}' with field '{expected_field}' present "
        f"in stock_data should have a non-None value, got None"
    )
    assert abs(result.value - float(resolved_value)) < 1e-9, (
        f"Factor '{condition.factor_name}': evaluator read value {result.value} "
        f"but expected {resolved_value} from field '{expected_field}'"
    )

    # Verify the comparison result is consistent
    op_fn = FactorEvaluator._OPERATORS.get(operator)
    if op_fn is not None:
        expected_passed = op_fn(float(resolved_value), threshold)
        assert result.passed == expected_passed, (
            f"Factor '{condition.factor_name}': "
            f"{resolved_value} {operator} {threshold} should be {expected_passed}, "
            f"got passed={result.passed}"
        )


@settings(max_examples=100)
@given(scenario=_boolean_factor_scenario())
def test_factor_evaluator_boolean_field_resolution(scenario):
    """
    # Feature: factor-editor-optimization, Property 4: FactorEvaluator 阈值类型字段解析

    **Validates: Requirements 12.1, 12.4**

    For any BOOLEAN-type factor, the FactorEvaluator SHALL read the raw
    `{factor_name}` field directly and evaluate passed = bool(value).
    """
    condition, stock_data, expected_field, bool_value = scenario

    result = FactorEvaluator.evaluate(condition, stock_data, weight=1.0)

    assert isinstance(result, FactorEvalResult), (
        f"evaluate() should return FactorEvalResult, got {type(result)}"
    )

    # Boolean evaluation: passed = bool(value)
    expected_passed = bool(bool_value)
    assert result.passed == expected_passed, (
        f"Boolean factor '{condition.factor_name}': "
        f"bool({bool_value}) should be {expected_passed}, "
        f"got passed={result.passed}"
    )

    # Value should be 1.0 if truthy, 0.0 if falsy
    expected_value = 1.0 if expected_passed else 0.0
    assert result.value == expected_value, (
        f"Boolean factor '{condition.factor_name}': "
        f"value should be {expected_value}, got {result.value}"
    )


@settings(max_examples=100)
@given(
    factor_name=st.sampled_from(
        _PERCENTILE_FACTORS + _INDUSTRY_RELATIVE_FACTORS
    ),
)
def test_factor_evaluator_missing_resolved_field(factor_name: str):
    """
    # Feature: factor-editor-optimization, Property 4: FactorEvaluator 阈值类型字段解析

    **Validates: Requirements 12.6**

    If the resolved field (_pctl or _ind_rel) is missing from stock_data,
    the FactorEvaluator SHALL set passed=False.
    """
    meta = FACTOR_REGISTRY[factor_name]

    condition = FactorCondition(
        factor_name=factor_name,
        operator=">=",
        threshold=50.0,
    )

    # Stock data has only the raw field, NOT the _pctl or _ind_rel field
    stock_data = {
        factor_name: 75.0,
    }

    result = FactorEvaluator.evaluate(condition, stock_data, weight=1.0)

    assert isinstance(result, FactorEvalResult)
    assert result.passed is False, (
        f"Factor '{factor_name}' (threshold_type={meta.threshold_type.value}): "
        f"missing resolved field should result in passed=False, got {result.passed}"
    )
    assert result.value is None, (
        f"Factor '{factor_name}': missing resolved field should result in "
        f"value=None, got {result.value}"
    )


# ---------------------------------------------------------------------------
# Property 5: Range 类型区间评估
# Feature: factor-editor-optimization, Property 5: Range 类型区间评估
# ---------------------------------------------------------------------------

# RANGE-type factors from FACTOR_REGISTRY: rsi (0-100), turnover (0-100)
_RANGE_FACTORS = [
    name for name, meta in FACTOR_REGISTRY.items()
    if meta.threshold_type == ThresholdType.RANGE
]


@st.composite
def _range_evaluation_scenario(draw):
    """Generate a RANGE-type factor evaluation scenario.

    Produces (factor_name, value, low, high) where:
    - factor_name is a RANGE-type factor from FACTOR_REGISTRY
    - value is a random float within the factor's value range
    - low and high are random bounds within the factor's value range with low <= high
    """
    factor_name = draw(st.sampled_from(_RANGE_FACTORS))
    meta = FACTOR_REGISTRY[factor_name]

    v_min = meta.value_min if meta.value_min is not None else 0.0
    v_max = meta.value_max if meta.value_max is not None else 100.0

    value = draw(st.floats(
        min_value=v_min, max_value=v_max,
        allow_nan=False, allow_infinity=False,
    ))

    # Generate low and high bounds ensuring low <= high
    bound_a = draw(st.floats(
        min_value=v_min, max_value=v_max,
        allow_nan=False, allow_infinity=False,
    ))
    bound_b = draw(st.floats(
        min_value=v_min, max_value=v_max,
        allow_nan=False, allow_infinity=False,
    ))
    low = min(bound_a, bound_b)
    high = max(bound_a, bound_b)

    return factor_name, value, low, high


@settings(max_examples=100)
@given(scenario=_range_evaluation_scenario())
def test_range_type_evaluation(scenario):
    """
    # Feature: factor-editor-optimization, Property 5: Range 类型区间评估

    **Validates: Requirements 12.5**

    For any numeric value and range bounds [low, high], the FactorEvaluator
    SHALL evaluate a RANGE-type factor condition as passed if and only if
    low ≤ value ≤ high.
    """
    factor_name, value, low, high = scenario

    # Build a FactorCondition with operator="BETWEEN" and range params
    condition = FactorCondition(
        factor_name=factor_name,
        operator="BETWEEN",
        threshold=None,
        params={
            "threshold_low": low,
            "threshold_high": high,
        },
    )

    # Build stock_data with the factor value
    stock_data = {
        factor_name: value,
    }

    # Evaluate
    result = FactorEvaluator.evaluate(condition, stock_data, weight=1.0)

    assert isinstance(result, FactorEvalResult), (
        f"evaluate() should return FactorEvalResult, got {type(result)}"
    )

    # The value should be recorded
    assert result.value is not None, (
        f"Factor '{factor_name}' with value {value} should have non-None result.value"
    )
    assert abs(result.value - float(value)) < 1e-9, (
        f"Factor '{factor_name}': result.value={result.value} != expected {value}"
    )

    # Core property: passed iff low <= value <= high
    expected_passed = low <= float(value) <= high
    assert result.passed == expected_passed, (
        f"Factor '{factor_name}': value={value}, range=[{low}, {high}], "
        f"expected passed={expected_passed}, got passed={result.passed}"
    )
