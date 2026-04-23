"""
选股 API 单元测试

覆盖：
- _SIGNAL_DIMENSION_MAP 覆盖所有已知 SignalCategory 值
- API 序列化中 dimension 字段值与映射一致
- 因子注册表 API 返回新增类别（CHIP、MARGIN、BOARD_HIT）（需求 18.3）
- 策略示例 API 返回 config_doc 字段（需求 20.3）
- SectorScreenConfigIn 模型 sector_type 可选（需求 22.1）

对应需求：10.1, 10.2, 18.3, 20.3, 22.1
"""

from __future__ import annotations

import pytest

from app.api.v1.screen import (
    _SIGNAL_DIMENSION_MAP,
    SectorScreenConfigIn,
    get_strategy_examples,
    get_factor_registry,
    list_factors,
)
from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
)
from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    get_factors_by_category,
)
from app.services.screener.strategy_examples import STRATEGY_EXAMPLES


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


# ---------------------------------------------------------------------------
# 因子注册表 API 返回新增类别（需求 18.3）
# ---------------------------------------------------------------------------


class TestFactorRegistryApiNewCategories:
    """验证因子注册表 API 支持 CHIP、MARGIN、BOARD_HIT 新增类别查询（需求 18.3）"""

    @pytest.mark.parametrize(
        "category_value",
        ["chip", "margin", "board_hit"],
    )
    def test_get_factors_by_new_category_returns_non_empty(self, category_value: str):
        """get_factors_by_category 对新增类别应返回非空因子列表"""
        cat_enum = FactorCategory(category_value)
        factors = get_factors_by_category(cat_enum)
        assert len(factors) > 0, (
            f"FactorCategory.{category_value} 应包含至少一个因子，实际为空"
        )

    def test_chip_category_contains_expected_factors(self):
        """CHIP 类别应包含筹码面因子"""
        factors = get_factors_by_category(FactorCategory.CHIP)
        factor_names = {f.factor_name for f in factors}
        expected = {"chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
                    "chip_cost_50pct", "chip_weight_avg", "chip_concentration"}
        assert expected.issubset(factor_names), (
            f"CHIP 类别缺少因子: {expected - factor_names}"
        )

    def test_margin_category_contains_expected_factors(self):
        """MARGIN 类别应包含两融面因子"""
        factors = get_factors_by_category(FactorCategory.MARGIN)
        factor_names = {f.factor_name for f in factors}
        expected = {"rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy"}
        assert expected.issubset(factor_names), (
            f"MARGIN 类别缺少因子: {expected - factor_names}"
        )

    def test_board_hit_category_contains_expected_factors(self):
        """BOARD_HIT 类别应包含打板面因子"""
        factors = get_factors_by_category(FactorCategory.BOARD_HIT)
        factor_names = {f.factor_name for f in factors}
        expected = {"limit_up_count", "limit_up_streak", "limit_up_open_pct",
                    "dragon_tiger_net_buy", "first_limit_up"}
        assert expected.issubset(factor_names), (
            f"BOARD_HIT 类别缺少因子: {expected - factor_names}"
        )

    def test_new_categories_in_factor_category_enum(self):
        """FactorCategory 枚举应包含 CHIP、MARGIN、BOARD_HIT"""
        all_values = {cat.value for cat in FactorCategory}
        assert "chip" in all_values, "FactorCategory 缺少 CHIP"
        assert "margin" in all_values, "FactorCategory 缺少 MARGIN"
        assert "board_hit" in all_values, "FactorCategory 缺少 BOARD_HIT"

    def test_all_new_category_factors_have_complete_metadata(self):
        """新增类别下所有因子应具有完整的元数据字段"""
        new_categories = [FactorCategory.CHIP, FactorCategory.MARGIN, FactorCategory.BOARD_HIT]
        for cat in new_categories:
            factors = get_factors_by_category(cat)
            for meta in factors:
                assert meta.factor_name, f"{cat.value} 类别因子缺少 factor_name"
                assert meta.label, f"{meta.factor_name} 缺少 label"
                assert meta.category == cat, f"{meta.factor_name} 类别不匹配"
                assert meta.threshold_type, f"{meta.factor_name} 缺少 threshold_type"
                assert meta.description, f"{meta.factor_name} 缺少 description"
                assert len(meta.examples) > 0, f"{meta.factor_name} 缺少 examples"


# ---------------------------------------------------------------------------
# 策略示例 API 返回 config_doc 字段（需求 20.3）
# ---------------------------------------------------------------------------


class TestStrategyExamplesApiConfigDoc:
    """验证策略示例 API 响应包含 config_doc 字段（需求 20.3）"""

    def test_strategy_example_dataclass_has_config_doc(self):
        """StrategyExample 数据类应包含 config_doc 字段"""
        for ex in STRATEGY_EXAMPLES:
            assert hasattr(ex, "config_doc"), (
                f"策略示例 '{ex.name}' 缺少 config_doc 字段"
            )

    def test_new_strategy_examples_have_non_empty_config_doc(self):
        """新增策略示例（索引 >= 12）应包含非空 config_doc"""
        # 前 12 个为原有示例，第 13 个起为新增示例
        new_examples = STRATEGY_EXAMPLES[12:] if len(STRATEGY_EXAMPLES) > 12 else []
        for ex in new_examples:
            assert ex.config_doc, (
                f"新增策略示例 '{ex.name}' 的 config_doc 不应为空"
            )

    @pytest.mark.asyncio
    async def test_get_strategy_examples_includes_config_doc(self):
        """get_strategy_examples 端点响应应包含 config_doc 字段"""
        result = await get_strategy_examples()
        assert isinstance(result, list)
        assert len(result) > 0, "策略示例列表不应为空"
        for item in result:
            assert "config_doc" in item, (
                f"策略示例 '{item.get('name', '?')}' 的 API 响应缺少 config_doc 字段"
            )

    @pytest.mark.asyncio
    async def test_get_strategy_examples_config_doc_matches_dataclass(self):
        """API 响应中的 config_doc 应与 StrategyExample 数据类中的值一致"""
        result = await get_strategy_examples()
        for i, item in enumerate(result):
            if i < len(STRATEGY_EXAMPLES):
                assert item["config_doc"] == STRATEGY_EXAMPLES[i].config_doc, (
                    f"策略示例 '{item['name']}' 的 config_doc 与数据类不一致"
                )


# ---------------------------------------------------------------------------
# SectorScreenConfigIn 模型 sector_type 可选（需求 22.1）
# ---------------------------------------------------------------------------


class TestSectorScreenConfigInModel:
    """验证 SectorScreenConfigIn 模型 sector_type 为可选字段（需求 22.1）"""

    def test_sector_type_defaults_to_none(self):
        """sector_type 默认值应为 None"""
        config = SectorScreenConfigIn()
        assert config.sector_type is None, (
            f"SectorScreenConfigIn.sector_type 默认值应为 None，实际为 '{config.sector_type}'"
        )

    def test_sector_data_source_defaults_to_dc(self):
        """sector_data_source 默认值应为 'DC'"""
        config = SectorScreenConfigIn()
        assert config.sector_data_source == "DC"

    def test_can_create_without_sector_type(self):
        """不传 sector_type 时应能正常创建"""
        config = SectorScreenConfigIn(
            sector_data_source="THS",
            sector_period=10,
            sector_top_n=20,
        )
        assert config.sector_type is None
        assert config.sector_data_source == "THS"
        assert config.sector_period == 10
        assert config.sector_top_n == 20

    def test_can_create_with_sector_type(self):
        """传入 sector_type 时应能正常创建（向后兼容）"""
        config = SectorScreenConfigIn(
            sector_data_source="DC",
            sector_type="CONCEPT",
            sector_period=5,
            sector_top_n=30,
        )
        assert config.sector_type == "CONCEPT"

    def test_model_dump_without_sector_type(self):
        """model_dump 输出中 sector_type 应为 None（未传入时）"""
        config = SectorScreenConfigIn(sector_data_source="TI")
        dumped = config.model_dump()
        assert dumped["sector_type"] is None
