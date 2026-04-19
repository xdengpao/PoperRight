"""
选股 API 单元测试

覆盖：
- _SIGNAL_DIMENSION_MAP 覆盖所有已知 SignalCategory 值
- API 序列化中 dimension 字段值与映射一致

对应需求：10.1, 10.2
"""

from __future__ import annotations

import pytest

from app.api.v1.screen import _SIGNAL_DIMENSION_MAP
from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# _SIGNAL_DIMENSION_MAP 覆盖所有已知 SignalCategory 值
# ---------------------------------------------------------------------------


class TestSignalDimensionMapCoverage:
    """验证 _SIGNAL_DIMENSION_MAP 覆盖所有已知 SignalCategory 值（需求 10.1）"""

    def test_all_signal_categories_covered(self):
        """_SIGNAL_DIMENSION_MAP 应包含所有 SignalCategory 枚举值"""
        all_categories = {cat.value for cat in SignalCategory}
        mapped_categories = set(_SIGNAL_DIMENSION_MAP.keys())

        missing = all_categories - mapped_categories
        assert not missing, (
            f"以下 SignalCategory 值未在 _SIGNAL_DIMENSION_MAP 中定义映射: {missing}"
        )

    def test_no_extra_keys_in_map(self):
        """_SIGNAL_DIMENSION_MAP 不应包含不存在的 SignalCategory 值"""
        all_categories = {cat.value for cat in SignalCategory}
        mapped_categories = set(_SIGNAL_DIMENSION_MAP.keys())

        extra = mapped_categories - all_categories
        assert not extra, (
            f"_SIGNAL_DIMENSION_MAP 包含未知的 SignalCategory 值: {extra}"
        )

    def test_dimension_values_are_valid(self):
        """_SIGNAL_DIMENSION_MAP 中所有维度值应为合法的中文维度名"""
        valid_dimensions = {"技术面", "资金面", "基本面", "板块面"}
        for category, dimension in _SIGNAL_DIMENSION_MAP.items():
            assert dimension in valid_dimensions, (
                f"SignalCategory.{category} 的维度值 '{dimension}' 不在合法维度集合中: {valid_dimensions}"
            )


# ---------------------------------------------------------------------------
# API 序列化中 dimension 字段值与映射一致
# ---------------------------------------------------------------------------


class TestApiSerializationDimension:
    """验证 API 序列化中 dimension 字段值与 _SIGNAL_DIMENSION_MAP 映射一致（需求 10.2）"""

    @pytest.mark.parametrize(
        "category,expected_dimension",
        [
            (SignalCategory.MA_TREND, "技术面"),
            (SignalCategory.MACD, "技术面"),
            (SignalCategory.BOLL, "技术面"),
            (SignalCategory.RSI, "技术面"),
            (SignalCategory.DMA, "技术面"),
            (SignalCategory.BREAKOUT, "技术面"),
            (SignalCategory.MA_SUPPORT, "技术面"),
            (SignalCategory.CAPITAL_INFLOW, "资金面"),
            (SignalCategory.LARGE_ORDER, "资金面"),
            (SignalCategory.SECTOR_STRONG, "板块面"),
        ],
    )
    def test_dimension_matches_mapping(self, category: SignalCategory, expected_dimension: str):
        """每种 SignalCategory 的 dimension 序列化值应与映射一致"""
        signal = SignalDetail(
            category=category,
            label=category.value.lower(),
        )

        # 模拟 API 序列化逻辑（与 screen.py run_screen 中一致）
        serialized = {
            "category": signal.category.value,
            "label": signal.label,
            "is_fake_breakout": signal.is_fake_breakout,
            "strength": signal.strength.value,
            "freshness": signal.freshness.value,
            "description": signal.description,
            "dimension": _SIGNAL_DIMENSION_MAP.get(signal.category.value, "其他"),
        }

        assert serialized["dimension"] == expected_dimension, (
            f"SignalCategory.{category.value} 的 dimension 应为 '{expected_dimension}', "
            f"实际为 '{serialized['dimension']}'"
        )

    def test_unknown_category_defaults_to_other(self):
        """未知 category 值应默认为 '其他'"""
        dimension = _SIGNAL_DIMENSION_MAP.get("UNKNOWN_CATEGORY", "其他")
        assert dimension == "其他"
