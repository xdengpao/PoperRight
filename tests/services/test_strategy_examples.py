"""Unit tests for strategy examples module.

Tests cover:
- At least 12 strategy examples exist (Req 14.1)
- Each example has all required fields (Req 14.5)
- Each example's factors list is non-empty
- Logic is either "AND" or "OR"
- Weights dict is non-empty
- enabled_modules is a list

Requirements: 14.1, 14.5
"""

import pytest

from app.services.screener.strategy_examples import (
    STRATEGY_EXAMPLES,
    StrategyExample,
)


# ---------------------------------------------------------------------------
# 策略示例数量 (Req 14.1)
# ---------------------------------------------------------------------------


class TestStrategyExamplesCount:
    """验证策略示例库包含至少 12 个示例 (Req 14.1)"""

    def test_at_least_12_examples(self):
        assert len(STRATEGY_EXAMPLES) >= 12

    def test_all_entries_are_strategy_example_instances(self):
        for example in STRATEGY_EXAMPLES:
            assert isinstance(example, StrategyExample)


# ---------------------------------------------------------------------------
# 策略示例字段完整性 (Req 14.5)
# ---------------------------------------------------------------------------


class TestStrategyExampleRequiredFields:
    """验证每个策略示例包含所有必需字段 (Req 14.5)"""

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_has_name(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.name, str)
        assert len(example.name) > 0

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_has_description(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.description, str)
        assert len(example.description) > 0

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_has_non_empty_factors(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.factors, list)
        assert len(example.factors) > 0

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_logic_is_and_or_or(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert example.logic in ("AND", "OR")

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_has_non_empty_weights(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.weights, dict)
        assert len(example.weights) > 0

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_enabled_modules_is_list(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.enabled_modules, list)


# ---------------------------------------------------------------------------
# 因子条件字段完整性
# ---------------------------------------------------------------------------


class TestFactorConditionFields:
    """验证每个策略示例中的因子条件包含必需字段"""

    REQUIRED_FACTOR_KEYS = {"factor_name", "operator", "threshold", "params"}

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_each_factor_has_required_keys(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        for i, factor in enumerate(example.factors):
            missing = self.REQUIRED_FACTOR_KEYS - set(factor.keys())
            assert not missing, (
                f"Example '{example.name}' factor[{i}] missing keys: {missing}"
            )

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_each_factor_name_is_string(self, idx):
        example = STRATEGY_EXAMPLES[idx]
        for factor in example.factors:
            assert isinstance(factor["factor_name"], str)
            assert len(factor["factor_name"]) > 0


# ---------------------------------------------------------------------------
# sector_config 字段验证
# ---------------------------------------------------------------------------


class TestSectorConfig:
    """验证包含板块配置的策略示例的 sector_config 字段"""

    def test_sector_config_is_none_or_dict(self):
        for example in STRATEGY_EXAMPLES:
            assert example.sector_config is None or isinstance(
                example.sector_config, dict
            ), f"Example '{example.name}' sector_config is not None or dict"

    def test_sector_config_has_valid_keys_when_present(self):
        valid_keys = {
            "sector_data_source",
            "sector_type",
            "sector_period",
            "sector_top_n",
        }
        for example in STRATEGY_EXAMPLES:
            if example.sector_config is not None:
                for key in example.sector_config:
                    assert key in valid_keys, (
                        f"Example '{example.name}' has unexpected "
                        f"sector_config key: {key}"
                    )
