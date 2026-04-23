"""
因子注册表完整性属性测试（Hypothesis）

**Validates: Requirements 11.1, 11.6**

Property 17: 因子注册表完整性
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    FactorMeta,
)


# ---------------------------------------------------------------------------
# 辅助：从注册表中获取所有因子名称作为参数化列表
# ---------------------------------------------------------------------------

_ALL_FACTOR_NAMES = list(FACTOR_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Property 17: 因子注册表完整性
# Feature: screening-parameter-optimization, Property 17: 因子注册表完整性
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("factor_name", _ALL_FACTOR_NAMES)
def test_factor_has_non_empty_description(factor_name: str):
    """
    # Feature: screening-parameter-optimization, Property 17: 因子注册表完整性

    **Validates: Requirements 11.1, 11.6**

    对注册表中的每个因子，description 字段必须非空。
    """
    meta = FACTOR_REGISTRY[factor_name]
    assert isinstance(meta.description, str), (
        f"因子 '{factor_name}' 的 description 应为字符串类型，实际为 {type(meta.description)}"
    )
    assert len(meta.description) > 0, (
        f"因子 '{factor_name}' 的 description 字段为空"
    )


@pytest.mark.parametrize("factor_name", _ALL_FACTOR_NAMES)
def test_factor_has_examples(factor_name: str):
    """
    # Feature: screening-parameter-optimization, Property 17: 因子注册表完整性

    **Validates: Requirements 11.1, 11.6**

    对注册表中的每个因子，examples 列表至少包含 1 个配置示例。
    """
    meta = FACTOR_REGISTRY[factor_name]
    assert isinstance(meta.examples, list), (
        f"因子 '{factor_name}' 的 examples 应为列表类型，实际为 {type(meta.examples)}"
    )
    assert len(meta.examples) >= 1, (
        f"因子 '{factor_name}' 的 examples 列表为空，至少需要 1 个配置示例"
    )


def test_factor_registry_has_19_factors():
    """
    # Feature: screening-parameter-optimization, Property 17: 因子注册表完整性

    **Validates: Requirements 11.1**

    注册表应包含恰好 52 个因子（原 19 个 + 新增 33 个）。
    """
    assert len(FACTOR_REGISTRY) == 52, (
        f"注册表应包含 52 个因子，实际为 {len(FACTOR_REGISTRY)}"
    )


def test_factor_registry_covers_all_categories():
    """
    # Feature: screening-parameter-optimization, Property 17: 因子注册表完整性

    **Validates: Requirements 11.6**

    注册表应覆盖所有 FactorCategory 枚举值。
    """
    categories_present = {meta.category for meta in FACTOR_REGISTRY.values()}
    all_categories = set(FactorCategory)
    missing = all_categories - categories_present
    assert not missing, (
        f"注册表缺少以下类别的因子: {missing}"
    )


@settings(max_examples=100)
@given(factor_name=st.sampled_from(_ALL_FACTOR_NAMES))
def test_factor_description_non_empty_property(factor_name: str):
    """
    # Feature: screening-parameter-optimization, Property 17: 因子注册表完整性

    **Validates: Requirements 11.1, 11.6**

    属性测试：对注册表中随机抽取的因子，description 字段必须非空。
    """
    meta = FACTOR_REGISTRY[factor_name]
    assert len(meta.description) > 0, (
        f"因子 '{factor_name}' 的 description 字段为空"
    )
