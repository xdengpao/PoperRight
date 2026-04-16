# Feature: minute-exit-condition-templates, Property 1: ExitConditionConfig round-trip
"""
分钟级平仓条件模版 — 属性测试

Property 1: ExitConditionConfig round-trip
对任意有效的 ExitConditionConfig（仅含分钟频率条件），
to_dict() → from_dict() → to_dict() 应产生等价的字典。

**Validates: Requirements 4.1**
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.schemas import (
    VALID_INDICATORS,
    VALID_OPERATORS,
    ExitCondition,
    ExitConditionConfig,
)

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）— 分钟频率专用
# ---------------------------------------------------------------------------

_INDICATORS = sorted(VALID_INDICATORS)
_OPERATORS = sorted(VALID_OPERATORS)

# 仅分钟频率
_MINUTE_FREQS = ["1min", "5min", "15min", "30min", "60min"]
_minute_freq_strategy = st.sampled_from(_MINUTE_FREQS)

# 指标名称
_indicator_strategy = st.sampled_from(_INDICATORS)

# 数值阈值（合理范围的浮点数）
_threshold_strategy = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)

# 指标参数字典
_params_strategy = st.one_of(
    st.just({}),
    st.fixed_dictionaries({"period": st.integers(min_value=1, max_value=250)}),
    st.fixed_dictionaries({
        "period": st.integers(min_value=1, max_value=250),
        "cross_period": st.integers(min_value=1, max_value=250),
    }),
)


@st.composite
def exit_condition_minute_strategy(draw):
    """生成任意合法的分钟频率 ExitCondition。"""
    freq = draw(_minute_freq_strategy)
    indicator = draw(_indicator_strategy)
    operator = draw(st.sampled_from(_OPERATORS))

    # ma 指标必须包含正整数 period 参数
    if indicator == "ma":
        params = draw(st.one_of(
            st.fixed_dictionaries({"period": st.integers(min_value=1, max_value=250)}),
            st.fixed_dictionaries({
                "period": st.integers(min_value=1, max_value=250),
                "cross_period": st.integers(min_value=1, max_value=250),
            }),
        ))
    else:
        params = draw(_params_strategy)

    if operator in ("cross_up", "cross_down"):
        cross_target = draw(_indicator_strategy)
        return ExitCondition(
            freq=freq,
            indicator=indicator,
            operator=operator,
            threshold=None,
            cross_target=cross_target,
            params=params,
        )
    else:
        threshold = draw(_threshold_strategy)
        return ExitCondition(
            freq=freq,
            indicator=indicator,
            operator=operator,
            threshold=threshold,
            cross_target=None,
            params=params,
        )


@st.composite
def exit_condition_config_minute_strategy(draw):
    """生成任意合法的分钟频率 ExitConditionConfig。"""
    conditions = draw(
        st.lists(exit_condition_minute_strategy(), min_size=1, max_size=10)
    )
    logic = draw(st.sampled_from(["AND", "OR"]))
    return ExitConditionConfig(conditions=conditions, logic=logic)


# ---------------------------------------------------------------------------
# Property 1: ExitConditionConfig round-trip
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(config=exit_condition_config_minute_strategy())
def test_exit_condition_config_minute_roundtrip(config: ExitConditionConfig):
    """
    # Feature: minute-exit-condition-templates, Property 1: ExitConditionConfig round-trip

    **Validates: Requirements 4.1**

    对任意有效的 ExitConditionConfig（仅含分钟频率条件），
    ExitConditionConfig.from_dict(config.to_dict()).to_dict() == config.to_dict()
    """
    serialized = config.to_dict()
    restored = ExitConditionConfig.from_dict(serialized)
    re_serialized = restored.to_dict()

    assert re_serialized == serialized, (
        f"Round-trip 不一致:\n"
        f"  原始 to_dict():   {serialized}\n"
        f"  round-trip 结果:  {re_serialized}"
    )


# ---------------------------------------------------------------------------
# Property 2: ExitCondition structure validity
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(condition=exit_condition_minute_strategy())
def test_exit_condition_structure_validity(condition: ExitCondition):
    """
    # Feature: minute-exit-condition-templates, Property 2: ExitCondition structure validity

    **Validates: Requirements 1.2, 1.6, 4.2, 4.3, 4.4, 4.5**

    对任意生成的分钟频率 ExitCondition，验证：
    - indicator 属于 VALID_INDICATORS
    - operator 属于 VALID_OPERATORS
    - cross 运算符（cross_up / cross_down）的 cross_target 非空且属于 VALID_INDICATORS
    - ma 指标的 params 包含正整数 period
    """
    # 4.2: indicator must be valid
    assert condition.indicator in VALID_INDICATORS, (
        f"indicator '{condition.indicator}' 不在 VALID_INDICATORS 中"
    )

    # 4.3: operator must be valid
    assert condition.operator in VALID_OPERATORS, (
        f"operator '{condition.operator}' 不在 VALID_OPERATORS 中"
    )

    # 4.4: cross operators require a valid cross_target
    if condition.operator in ("cross_up", "cross_down"):
        assert condition.cross_target is not None, (
            f"operator '{condition.operator}' 要求 cross_target 非空，"
            f"但得到 None"
        )
        assert condition.cross_target in VALID_INDICATORS, (
            f"cross_target '{condition.cross_target}' 不在 VALID_INDICATORS 中"
        )

    # 4.5: ma indicator requires a positive integer period
    if condition.indicator == "ma":
        assert "period" in condition.params, (
            "indicator 'ma' 要求 params 包含 'period' 键，"
            f"但 params={condition.params}"
        )
        period = condition.params["period"]
        assert isinstance(period, int) and period > 0, (
            f"indicator 'ma' 的 period 应为正整数，但得到 {period!r}"
        )


# ---------------------------------------------------------------------------
# Feature: minute-exit-condition-templates, Property 3: Template metadata validity
# ---------------------------------------------------------------------------
# Example-based tests verifying the 10 seed templates from MINUTE_TEMPLATES.
#
# **Validates: Requirements 1.1, 1.3, 1.4, 1.5, 1.7**
# ---------------------------------------------------------------------------

import importlib
import os

# The migration module name starts with a digit, so we use importlib to load it.
_migration_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "alembic",
    "versions",
    "008_seed_minute_exit_templates.py",
)
_spec = importlib.util.spec_from_file_location(
    "seed_minute_exit_templates_008", _migration_path
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
MINUTE_TEMPLATES = _module.MINUTE_TEMPLATES


class TestTemplateMetadataValidity:
    """Property 3: Template metadata validity — example-based tests."""

    # -- Metadata constraints ------------------------------------------------

    def test_exactly_10_templates(self):
        """There must be exactly 10 minute-frequency seed templates."""
        assert len(MINUTE_TEMPLATES) == 10

    def test_names_non_empty_and_within_limit(self):
        """Every template name must be non-empty and ≤100 characters."""
        for tpl in MINUTE_TEMPLATES:
            name = tpl["name"]
            assert isinstance(name, str) and len(name) > 0, (
                f"Template name must be non-empty, got: {name!r}"
            )
            assert len(name) <= 100, (
                f"Template name exceeds 100 chars ({len(name)}): {name!r}"
            )

    def test_descriptions_within_limit(self):
        """Every template description must be ≤500 characters."""
        for tpl in MINUTE_TEMPLATES:
            desc = tpl["description"]
            assert len(desc) <= 500, (
                f"Template description exceeds 500 chars ({len(desc)}): "
                f"{desc[:60]}..."
            )

    def test_names_unique(self):
        """All template names must be unique (no duplicates)."""
        names = [tpl["name"] for tpl in MINUTE_TEMPLATES]
        assert len(names) == len(set(names)), (
            f"Duplicate template names found: "
            f"{[n for n in names if names.count(n) > 1]}"
        )

    # -- Coverage constraints ------------------------------------------------

    def test_at_least_5_distinct_indicator_types(self):
        """Templates must cover ≥5 distinct indicator types."""
        indicators: set[str] = set()
        for tpl in MINUTE_TEMPLATES:
            for cond in tpl["exit_conditions"]["conditions"]:
                indicators.add(cond["indicator"])
        assert len(indicators) >= 5, (
            f"Expected ≥5 distinct indicators, got {len(indicators)}: {indicators}"
        )

    def test_at_least_3_distinct_minute_frequencies(self):
        """Templates must cover ≥3 distinct minute frequencies."""
        freqs: set[str] = set()
        for tpl in MINUTE_TEMPLATES:
            for cond in tpl["exit_conditions"]["conditions"]:
                freqs.add(cond["freq"])
        assert len(freqs) >= 3, (
            f"Expected ≥3 distinct frequencies, got {len(freqs)}: {freqs}"
        )

    def test_at_least_3_distinct_operator_types(self):
        """Templates must cover ≥3 distinct operator types."""
        operators: set[str] = set()
        for tpl in MINUTE_TEMPLATES:
            for cond in tpl["exit_conditions"]["conditions"]:
                operators.add(cond["operator"])
        assert len(operators) >= 3, (
            f"Expected ≥3 distinct operators, got {len(operators)}: {operators}"
        )

    # -- Parsability ---------------------------------------------------------

    def test_each_template_parses_via_from_dict(self):
        """Every template's exit_conditions must parse via ExitConditionConfig.from_dict() without error."""
        for tpl in MINUTE_TEMPLATES:
            config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
            assert len(config.conditions) > 0, (
                f"Template '{tpl['name']}' parsed to zero conditions"
            )
            assert config.logic in ("AND", "OR"), (
                f"Template '{tpl['name']}' has invalid logic: {config.logic!r}"
            )
