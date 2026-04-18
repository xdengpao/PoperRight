"""Unit tests for factor registry module.

Tests cover:
- ma_trend metadata definition (Req 2.1)
- All boolean factors metadata (Req 2.2-2.4, 2.6-2.7)
- rsi range metadata (Req 2.5)
- money_flow percentile metadata (Req 3.2)
- pe industry_relative metadata (Req 4.1)
- sector_rank metadata (Req 6.1)
- get_factor_meta and get_factors_by_category helpers

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.2, 4.1, 6.1
"""

import pytest

from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    FactorMeta,
    ThresholdType,
    get_factor_meta,
    get_factors_by_category,
)


# ---------------------------------------------------------------------------
# ma_trend 元数据定义 (Req 2.1)
# ---------------------------------------------------------------------------


class TestMaTrendMetadata:
    """验证 ma_trend 因子元数据定义 (Req 2.1)"""

    def test_ma_trend_exists_in_registry(self):
        assert "ma_trend" in FACTOR_REGISTRY

    def test_ma_trend_threshold_type_is_absolute(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE

    def test_ma_trend_value_range(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.value_min == 0
        assert meta.value_max == 100

    def test_ma_trend_default_threshold(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.default_threshold == 80

    def test_ma_trend_unit(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.unit == "分"

    def test_ma_trend_category(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.category == FactorCategory.TECHNICAL

    def test_ma_trend_description_mentions_trend(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert "均线" in meta.description
        assert "80" in meta.description

    def test_ma_trend_label(self):
        meta = FACTOR_REGISTRY["ma_trend"]
        assert meta.label == "MA趋势打分"


# ---------------------------------------------------------------------------
# Boolean 因子元数据 (Req 2.2, 2.3, 2.4, 2.6, 2.7)
# ---------------------------------------------------------------------------


class TestBooleanFactorsMetadata:
    """验证所有 boolean 类型因子的元数据定义"""

    BOOLEAN_FACTORS = {
        "ma_support": {
            "label": "均线支撑信号",
            "desc_keyword": "均线",
            "req": "2.2",
        },
        "macd": {
            "label": "MACD金叉信号",
            "desc_keyword": "金叉",
            "req": "2.3",
        },
        "boll": {
            "label": "布林带突破信号",
            "desc_keyword": "布林",
            "req": "2.4",
        },
        "dma": {
            "label": "DMA平行线差",
            "desc_keyword": "DMA",
            "req": "2.6",
        },
        "breakout": {
            "label": "形态突破",
            "desc_keyword": "突破",
            "req": "2.7",
        },
    }

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_threshold_type(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_default_threshold_is_none(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.default_threshold is None

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_category_is_technical(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.TECHNICAL

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_label(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        expected_label = self.BOOLEAN_FACTORS[factor_name]["label"]
        assert meta.label == expected_label

    @pytest.mark.parametrize("factor_name", BOOLEAN_FACTORS.keys())
    def test_boolean_factor_has_description(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        keyword = self.BOOLEAN_FACTORS[factor_name]["desc_keyword"]
        assert keyword in meta.description

    def test_sector_trend_is_also_boolean(self):
        """sector_trend 也是 boolean 类型，但属于 SECTOR 类别"""
        meta = FACTOR_REGISTRY["sector_trend"]
        assert meta.threshold_type == ThresholdType.BOOLEAN
        assert meta.default_threshold is None
        assert meta.category == FactorCategory.SECTOR


# ---------------------------------------------------------------------------
# rsi range 元数据 (Req 2.5)
# ---------------------------------------------------------------------------


class TestRsiRangeMetadata:
    """验证 rsi 因子 range 类型定义 (Req 2.5)"""

    def test_rsi_exists_in_registry(self):
        assert "rsi" in FACTOR_REGISTRY

    def test_rsi_threshold_type_is_range(self):
        meta = FACTOR_REGISTRY["rsi"]
        assert meta.threshold_type == ThresholdType.RANGE

    def test_rsi_default_range(self):
        meta = FACTOR_REGISTRY["rsi"]
        assert meta.default_range == (50, 80)

    def test_rsi_value_range(self):
        meta = FACTOR_REGISTRY["rsi"]
        assert meta.value_min == 0
        assert meta.value_max == 100

    def test_rsi_category(self):
        meta = FACTOR_REGISTRY["rsi"]
        assert meta.category == FactorCategory.TECHNICAL

    def test_rsi_description_mentions_range(self):
        meta = FACTOR_REGISTRY["rsi"]
        assert "50" in meta.description or "强势" in meta.description


# ---------------------------------------------------------------------------
# money_flow percentile 元数据 (Req 3.2)
# ---------------------------------------------------------------------------


class TestMoneyFlowPercentileMetadata:
    """验证 money_flow 因子 percentile 类型定义 (Req 3.2)"""

    def test_money_flow_exists_in_registry(self):
        assert "money_flow" in FACTOR_REGISTRY

    def test_money_flow_threshold_type_is_percentile(self):
        meta = FACTOR_REGISTRY["money_flow"]
        assert meta.threshold_type == ThresholdType.PERCENTILE

    def test_money_flow_default_threshold(self):
        meta = FACTOR_REGISTRY["money_flow"]
        assert meta.default_threshold == 80

    def test_money_flow_value_range(self):
        meta = FACTOR_REGISTRY["money_flow"]
        assert meta.value_min == 0
        assert meta.value_max == 100

    def test_money_flow_category(self):
        meta = FACTOR_REGISTRY["money_flow"]
        assert meta.category == FactorCategory.MONEY_FLOW

    def test_money_flow_description_mentions_percentile(self):
        meta = FACTOR_REGISTRY["money_flow"]
        assert "百分位" in meta.description


# ---------------------------------------------------------------------------
# pe industry_relative 元数据 (Req 4.1)
# ---------------------------------------------------------------------------


class TestPeIndustryRelativeMetadata:
    """验证 pe 因子 industry_relative 类型定义 (Req 4.1)"""

    def test_pe_exists_in_registry(self):
        assert "pe" in FACTOR_REGISTRY

    def test_pe_threshold_type_is_industry_relative(self):
        meta = FACTOR_REGISTRY["pe"]
        assert meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE

    def test_pe_default_threshold(self):
        meta = FACTOR_REGISTRY["pe"]
        assert meta.default_threshold == 1.0

    def test_pe_value_range(self):
        meta = FACTOR_REGISTRY["pe"]
        assert meta.value_min == 0
        assert meta.value_max == 5.0

    def test_pe_category(self):
        meta = FACTOR_REGISTRY["pe"]
        assert meta.category == FactorCategory.FUNDAMENTAL

    def test_pe_description_mentions_industry(self):
        meta = FACTOR_REGISTRY["pe"]
        assert "行业" in meta.description

    def test_pb_also_industry_relative(self):
        """pb 也使用 industry_relative 类型 (Req 4.2)"""
        meta = FACTOR_REGISTRY["pb"]
        assert meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE
        assert meta.default_threshold == 1.0
        assert meta.value_min == 0
        assert meta.value_max == 5.0


# ---------------------------------------------------------------------------
# sector_rank 元数据 (Req 6.1)
# ---------------------------------------------------------------------------


class TestSectorRankMetadata:
    """验证 sector_rank 因子元数据定义 (Req 6.1)"""

    def test_sector_rank_exists_in_registry(self):
        assert "sector_rank" in FACTOR_REGISTRY

    def test_sector_rank_threshold_type_is_absolute(self):
        meta = FACTOR_REGISTRY["sector_rank"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE

    def test_sector_rank_value_range(self):
        meta = FACTOR_REGISTRY["sector_rank"]
        assert meta.value_min == 1
        assert meta.value_max == 300

    def test_sector_rank_default_threshold(self):
        meta = FACTOR_REGISTRY["sector_rank"]
        assert meta.default_threshold == 30

    def test_sector_rank_category(self):
        meta = FACTOR_REGISTRY["sector_rank"]
        assert meta.category == FactorCategory.SECTOR

    def test_sector_rank_description(self):
        meta = FACTOR_REGISTRY["sector_rank"]
        assert "排名" in meta.description
        assert "30" in meta.description

    def test_sector_rank_examples_include_data_source_info(self):
        """Req 6.3: 配置示例中包含数据来源和板块类型说明"""
        meta = FACTOR_REGISTRY["sector_rank"]
        assert len(meta.examples) > 0
        example = meta.examples[0]
        assert "数据来源" in example
        assert "板块类型" in example

    def test_sector_trend_examples_include_data_source_info(self):
        """Req 6.3: sector_trend 配置示例也包含数据来源和板块类型说明"""
        meta = FACTOR_REGISTRY["sector_trend"]
        assert len(meta.examples) > 0
        example = meta.examples[0]
        assert "数据来源" in example
        assert "板块类型" in example


# ---------------------------------------------------------------------------
# get_factor_meta 辅助函数
# ---------------------------------------------------------------------------


class TestGetFactorMeta:
    """验证 get_factor_meta 辅助函数"""

    def test_returns_factor_meta_for_existing_factor(self):
        meta = get_factor_meta("ma_trend")
        assert meta is not None
        assert isinstance(meta, FactorMeta)
        assert meta.factor_name == "ma_trend"

    def test_returns_none_for_nonexistent_factor(self):
        meta = get_factor_meta("nonexistent_factor")
        assert meta is None

    def test_returns_none_for_empty_string(self):
        meta = get_factor_meta("")
        assert meta is None

    def test_returns_same_instance_as_registry(self):
        meta = get_factor_meta("rsi")
        assert meta is FACTOR_REGISTRY["rsi"]

    def test_all_registry_factors_are_queryable(self):
        for factor_name in FACTOR_REGISTRY:
            meta = get_factor_meta(factor_name)
            assert meta is not None
            assert meta.factor_name == factor_name


# ---------------------------------------------------------------------------
# get_factors_by_category 辅助函数
# ---------------------------------------------------------------------------


class TestGetFactorsByCategory:
    """验证 get_factors_by_category 辅助函数"""

    def test_technical_factors_count(self):
        factors = get_factors_by_category(FactorCategory.TECHNICAL)
        assert len(factors) == 7

    def test_money_flow_factors_count(self):
        factors = get_factors_by_category(FactorCategory.MONEY_FLOW)
        assert len(factors) == 4

    def test_fundamental_factors_count(self):
        factors = get_factors_by_category(FactorCategory.FUNDAMENTAL)
        assert len(factors) == 6

    def test_sector_factors_count(self):
        factors = get_factors_by_category(FactorCategory.SECTOR)
        assert len(factors) == 2

    def test_all_returned_factors_match_category(self):
        for category in FactorCategory:
            factors = get_factors_by_category(category)
            for meta in factors:
                assert meta.category == category

    def test_returns_list_of_factor_meta(self):
        factors = get_factors_by_category(FactorCategory.TECHNICAL)
        for meta in factors:
            assert isinstance(meta, FactorMeta)

    def test_technical_factors_include_expected_names(self):
        factors = get_factors_by_category(FactorCategory.TECHNICAL)
        names = {f.factor_name for f in factors}
        expected = {"ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout"}
        assert names == expected

    def test_sector_factors_include_expected_names(self):
        factors = get_factors_by_category(FactorCategory.SECTOR)
        names = {f.factor_name for f in factors}
        expected = {"sector_rank", "sector_trend"}
        assert names == expected

    def test_total_factors_across_all_categories(self):
        total = sum(
            len(get_factors_by_category(cat)) for cat in FactorCategory
        )
        assert total == len(FACTOR_REGISTRY)
