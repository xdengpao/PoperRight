"""
策略示例库单元测试（Unit Tests for Strategy Examples）

测试覆盖：
- 22 个策略示例存在且完整（需求 14.1, 19.2）
- 每个示例包含所有必需字段（需求 14.5）
- 每个示例的 factors 列表非空
- logic 为 AND 或 OR
- weights 字典非空
- enabled_modules 为列表
- 新增示例（13-22）的 config_doc 非空（需求 20.1）
- 所有因子名称与 FACTOR_REGISTRY 一致（需求 19.2, 19.3）
- sector_config 不含 sector_type 字段（需求 22.9）

Requirements: 14.1, 14.5, 19.2, 19.3, 20.1, 22.9
"""

import pytest

from app.services.screener.factor_registry import FACTOR_REGISTRY
from app.services.screener.strategy_examples import (
    STRATEGY_EXAMPLES,
    StrategyExample,
)


# ---------------------------------------------------------------------------
# 策略示例数量（需求 14.1, 19.2）
# ---------------------------------------------------------------------------


class TestStrategyExamplesCount:
    """验证策略示例库包含 22 个示例"""

    def test_exactly_22_examples(self):
        """策略示例库应包含 22 个示例（原 12 + 新增 10）"""
        assert len(STRATEGY_EXAMPLES) == 22

    def test_all_entries_are_strategy_example_instances(self):
        for example in STRATEGY_EXAMPLES:
            assert isinstance(example, StrategyExample)


# ---------------------------------------------------------------------------
# 策略示例字段完整性（需求 14.5, 19.2）
# ---------------------------------------------------------------------------


class TestStrategyExampleRequiredFields:
    """验证每个策略示例包含所有必需字段"""

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
# 因子名称与 FACTOR_REGISTRY 一致性（需求 19.2, 19.3）
# ---------------------------------------------------------------------------


class TestFactorNameConsistency:
    """验证所有策略示例中的因子名称均在 FACTOR_REGISTRY 中注册"""

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_all_factor_names_in_registry(self, idx):
        """每个策略示例的因子名称必须在 FACTOR_REGISTRY 中注册"""
        example = STRATEGY_EXAMPLES[idx]
        for factor in example.factors:
            factor_name = factor["factor_name"]
            assert factor_name in FACTOR_REGISTRY, (
                f"策略 '{example.name}' 中的因子 '{factor_name}' "
                f"未在 FACTOR_REGISTRY 中注册"
            )


# ---------------------------------------------------------------------------
# sector_config 字段验证（需求 22.9）
# ---------------------------------------------------------------------------


class TestSectorConfig:
    """验证包含板块配置的策略示例的 sector_config 字段"""

    def test_sector_config_is_none_or_dict(self):
        for example in STRATEGY_EXAMPLES:
            assert example.sector_config is None or isinstance(
                example.sector_config, dict
            ), f"Example '{example.name}' sector_config is not None or dict"

    def test_sector_config_no_sector_type(self):
        """sector_config 不应包含 sector_type 字段（需求 22.9）"""
        for example in STRATEGY_EXAMPLES:
            if example.sector_config is not None:
                assert "sector_type" not in example.sector_config, (
                    f"Example '{example.name}' sector_config 仍包含 "
                    f"sector_type 字段，应已移除"
                )

    def test_sector_config_has_valid_keys_when_present(self):
        valid_keys = {
            "sector_data_source",
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


# ---------------------------------------------------------------------------
# config_doc 配置说明书验证（需求 20.1）
# ---------------------------------------------------------------------------


class TestConfigDoc:
    """验证策略示例的 config_doc 配置说明书"""

    def test_all_examples_have_config_doc(self):
        """所有 22 个策略示例都应有非空的 config_doc"""
        for example in STRATEGY_EXAMPLES:
            assert isinstance(example.config_doc, str), (
                f"策略 '{example.name}' 的 config_doc 不是字符串类型"
            )
            assert len(example.config_doc) > 0, (
                f"策略 '{example.name}' 的 config_doc 为空"
            )

    @pytest.mark.parametrize(
        "idx",
        range(len(STRATEGY_EXAMPLES)),
        ids=[e.name for e in STRATEGY_EXAMPLES],
    )
    def test_config_doc_contains_required_sections(self, idx):
        """config_doc 应包含策略概述、因子构成、适用场景、参数调优建议、风险提示、回测建议"""
        example = STRATEGY_EXAMPLES[idx]
        doc = example.config_doc
        required_sections = [
            "策略概述",
            "因子构成",
            "适用场景",
            "参数调优建议",
            "风险提示",
            "回测建议",
        ]
        for section in required_sections:
            assert section in doc, (
                f"策略 '{example.name}' 的 config_doc 缺少 '{section}' 章节"
            )

    def test_new_examples_have_non_empty_config_doc(self):
        """新增示例（索引 12-21，即示例 13-22）的 config_doc 必须非空"""
        for i in range(12, 22):
            example = STRATEGY_EXAMPLES[i]
            assert len(example.config_doc) > 0, (
                f"新增策略 '{example.name}' 的 config_doc 为空"
            )
