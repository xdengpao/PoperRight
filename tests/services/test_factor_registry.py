"""Unit tests for factor registry module.

Tests cover:
- ma_trend metadata definition (Req 2.1)
- All boolean factors metadata (Req 2.2-2.4, 2.6-2.7)
- rsi range metadata (Req 2.5)
- money_flow percentile metadata (Req 3.2)
- pe industry_relative metadata (Req 4.1)
- sector_rank metadata (Req 6.1)
- get_factor_meta and get_factors_by_category helpers
- 新增 33 个因子元数据验证 (Req 12.1, 13.2, 14.2, 15.1, 16.2, 17.1)
- 新增类别 CHIP、MARGIN、BOARD_HIT 验证 (Req 13.1, 14.1, 16.1)

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.2, 4.1, 6.1,
              12.1, 13.1, 13.2, 14.1, 14.2, 15.1, 16.1, 16.2, 17.1, 18.1, 21.1
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


class TestFactorDataSourceConfig:
    """验证支持数据源选择的因子元数据声明。"""

    MONEY_FLOW_SOURCE_FACTORS = {
        "money_flow",
        "large_order",
        "super_large_net_inflow",
        "large_net_inflow",
        "small_net_outflow",
        "money_flow_strength",
        "net_inflow_rate",
    }

    SECTOR_SOURCE_FACTORS = {"sector_rank", "sector_trend"}

    NO_SOURCE_FACTORS = {
        "turnover",
        "volume_price",
        "index_pe",
        "index_turnover",
        "index_ma_trend",
        "index_vol_ratio",
    }

    @pytest.mark.parametrize("factor_name", sorted(MONEY_FLOW_SOURCE_FACTORS))
    def test_money_flow_factors_declare_source_config(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.data_source_config is not None
        assert meta.data_source_config.kind == "money_flow"
        assert meta.data_source_config.config_path == "volume_price.money_flow_source"
        assert {opt.value for opt in meta.data_source_config.options} == {
            "money_flow",
            "moneyflow_ths",
            "moneyflow_dc",
        }

    @pytest.mark.parametrize("factor_name", sorted(SECTOR_SOURCE_FACTORS))
    def test_sector_factors_declare_source_config(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.data_source_config is not None
        assert meta.data_source_config.kind == "sector"
        assert meta.data_source_config.config_path == "sector_config.sector_data_source"

    @pytest.mark.parametrize("factor_name", sorted(NO_SOURCE_FACTORS))
    def test_non_source_factors_do_not_declare_source_config(self, factor_name):
        assert FACTOR_REGISTRY[factor_name].data_source_config is None


# ---------------------------------------------------------------------------
# get_factors_by_category 辅助函数
# ---------------------------------------------------------------------------


class TestGetFactorsByCategory:
    """验证 get_factors_by_category 辅助函数"""

    def test_technical_factors_count(self):
        factors = get_factors_by_category(FactorCategory.TECHNICAL)
        assert len(factors) == 16

    def test_money_flow_factors_count(self):
        factors = get_factors_by_category(FactorCategory.MONEY_FLOW)
        assert len(factors) == 9

    def test_fundamental_factors_count(self):
        factors = get_factors_by_category(FactorCategory.FUNDAMENTAL)
        assert len(factors) == 6

    def test_sector_factors_count(self):
        factors = get_factors_by_category(FactorCategory.SECTOR)
        assert len(factors) == 6

    def test_chip_factors_count(self):
        factors = get_factors_by_category(FactorCategory.CHIP)
        assert len(factors) == 6

    def test_margin_factors_count(self):
        factors = get_factors_by_category(FactorCategory.MARGIN)
        assert len(factors) == 4

    def test_board_hit_factors_count(self):
        factors = get_factors_by_category(FactorCategory.BOARD_HIT)
        assert len(factors) == 5

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
        expected = {
            "ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout",
            "kdj_k", "kdj_d", "kdj_j", "cci", "wr", "trix", "bias", "psy", "obv_signal",
        }
        assert names == expected

    def test_sector_factors_include_expected_names(self):
        factors = get_factors_by_category(FactorCategory.SECTOR)
        names = {f.factor_name for f in factors}
        expected = {
            "sector_rank", "sector_trend",
            "index_pe", "index_turnover", "index_ma_trend", "index_vol_ratio",
        }
        assert names == expected

    def test_total_factors_across_all_categories(self):
        total = sum(
            len(get_factors_by_category(cat)) for cat in FactorCategory
        )
        assert total == len(FACTOR_REGISTRY)


# ---------------------------------------------------------------------------
# 全量 52 个因子完整性验证 (Req 18.1, 21.1)
# ---------------------------------------------------------------------------


class TestAllFactorsCompleteness:
    """验证全部 52 个因子的元数据完整性"""

    def test_total_factor_count(self):
        """注册表应包含 52 个因子"""
        assert len(FACTOR_REGISTRY) == 52

    @pytest.mark.parametrize("factor_name", sorted(FACTOR_REGISTRY.keys()))
    def test_factor_has_non_empty_label(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.label, f"因子 '{factor_name}' 的 label 为空"

    @pytest.mark.parametrize("factor_name", sorted(FACTOR_REGISTRY.keys()))
    def test_factor_has_valid_category(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert isinstance(meta.category, FactorCategory)

    @pytest.mark.parametrize("factor_name", sorted(FACTOR_REGISTRY.keys()))
    def test_factor_has_valid_threshold_type(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert isinstance(meta.threshold_type, ThresholdType)

    @pytest.mark.parametrize("factor_name", sorted(FACTOR_REGISTRY.keys()))
    def test_factor_has_non_empty_examples(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert len(meta.examples) >= 1, f"因子 '{factor_name}' 的 examples 为空"

    @pytest.mark.parametrize("factor_name", sorted(FACTOR_REGISTRY.keys()))
    def test_factor_name_matches_key(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.factor_name == factor_name


# ---------------------------------------------------------------------------
# 新增技术面专业因子验证 (Req 12.1)
# ---------------------------------------------------------------------------


class TestNewTechnicalFactors:
    """验证 9 个新增技术面专业因子 (Req 12.1)"""

    NEW_TECHNICAL_FACTORS = [
        "kdj_k", "kdj_d", "kdj_j", "cci", "wr",
        "trix", "bias", "psy", "obv_signal",
    ]

    @pytest.mark.parametrize("factor_name", NEW_TECHNICAL_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", NEW_TECHNICAL_FACTORS)
    def test_factor_category_is_technical(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.TECHNICAL

    def test_kdj_k_is_range_type(self):
        meta = FACTOR_REGISTRY["kdj_k"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (20, 80)

    def test_kdj_d_is_range_type(self):
        meta = FACTOR_REGISTRY["kdj_d"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (20, 80)

    def test_kdj_j_is_range_type(self):
        meta = FACTOR_REGISTRY["kdj_j"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (0, 100)

    def test_cci_is_absolute_type(self):
        meta = FACTOR_REGISTRY["cci"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 100

    def test_wr_is_range_type(self):
        meta = FACTOR_REGISTRY["wr"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (0, 20)

    def test_trix_is_boolean_type(self):
        meta = FACTOR_REGISTRY["trix"]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    def test_bias_is_range_type(self):
        meta = FACTOR_REGISTRY["bias"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (-5, 5)

    def test_psy_is_range_type(self):
        meta = FACTOR_REGISTRY["psy"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (40, 75)

    def test_obv_signal_is_boolean_type(self):
        meta = FACTOR_REGISTRY["obv_signal"]
        assert meta.threshold_type == ThresholdType.BOOLEAN


# ---------------------------------------------------------------------------
# 筹码面因子验证 (Req 13.1, 13.2)
# ---------------------------------------------------------------------------


class TestChipFactors:
    """验证 6 个筹码面因子 (Req 13.1, 13.2)"""

    CHIP_FACTORS = [
        "chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
        "chip_cost_50pct", "chip_weight_avg", "chip_concentration",
    ]

    @pytest.mark.parametrize("factor_name", CHIP_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", CHIP_FACTORS)
    def test_factor_category_is_chip(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.CHIP

    def test_chip_winner_rate_is_percentile(self):
        meta = FACTOR_REGISTRY["chip_winner_rate"]
        assert meta.threshold_type == ThresholdType.PERCENTILE
        assert meta.default_threshold == 50

    def test_chip_cost_5pct_is_absolute(self):
        meta = FACTOR_REGISTRY["chip_cost_5pct"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 10

    def test_chip_weight_avg_is_industry_relative(self):
        meta = FACTOR_REGISTRY["chip_weight_avg"]
        assert meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE
        assert meta.default_threshold == 1.0

    def test_chip_concentration_is_percentile(self):
        meta = FACTOR_REGISTRY["chip_concentration"]
        assert meta.threshold_type == ThresholdType.PERCENTILE
        assert meta.default_threshold == 70


# ---------------------------------------------------------------------------
# 两融面因子验证 (Req 14.1, 14.2)
# ---------------------------------------------------------------------------


class TestMarginFactors:
    """验证 4 个两融面因子 (Req 14.1, 14.2)"""

    MARGIN_FACTORS = [
        "rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy",
    ]

    @pytest.mark.parametrize("factor_name", MARGIN_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", MARGIN_FACTORS)
    def test_factor_category_is_margin(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.MARGIN

    def test_rzye_change_is_percentile(self):
        meta = FACTOR_REGISTRY["rzye_change"]
        assert meta.threshold_type == ThresholdType.PERCENTILE
        assert meta.default_threshold == 70

    def test_rqye_ratio_is_absolute(self):
        meta = FACTOR_REGISTRY["rqye_ratio"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 5

    def test_rzrq_balance_trend_is_boolean(self):
        meta = FACTOR_REGISTRY["rzrq_balance_trend"]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    def test_margin_net_buy_is_percentile(self):
        meta = FACTOR_REGISTRY["margin_net_buy"]
        assert meta.threshold_type == ThresholdType.PERCENTILE
        assert meta.default_threshold == 75


# ---------------------------------------------------------------------------
# 增强资金流因子验证 (Req 15.1)
# ---------------------------------------------------------------------------


class TestEnhancedMoneyFlowFactors:
    """验证 5 个增强资金流因子 (Req 15.1)"""

    ENHANCED_MF_FACTORS = [
        "super_large_net_inflow", "large_net_inflow",
        "small_net_outflow", "money_flow_strength", "net_inflow_rate",
    ]

    @pytest.mark.parametrize("factor_name", ENHANCED_MF_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", ENHANCED_MF_FACTORS)
    def test_factor_category_is_money_flow(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.MONEY_FLOW

    def test_super_large_net_inflow_is_percentile(self):
        meta = FACTOR_REGISTRY["super_large_net_inflow"]
        assert meta.threshold_type == ThresholdType.PERCENTILE
        assert meta.default_threshold == 80

    def test_small_net_outflow_is_boolean(self):
        meta = FACTOR_REGISTRY["small_net_outflow"]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    def test_money_flow_strength_is_absolute(self):
        meta = FACTOR_REGISTRY["money_flow_strength"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 70

    def test_net_inflow_rate_is_absolute(self):
        meta = FACTOR_REGISTRY["net_inflow_rate"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 5


# ---------------------------------------------------------------------------
# 打板面因子验证 (Req 16.1, 16.2)
# ---------------------------------------------------------------------------


class TestBoardHitFactors:
    """验证 5 个打板面因子 (Req 16.1, 16.2)"""

    BOARD_HIT_FACTORS = [
        "limit_up_count", "limit_up_streak", "limit_up_open_pct",
        "dragon_tiger_net_buy", "first_limit_up",
    ]

    @pytest.mark.parametrize("factor_name", BOARD_HIT_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", BOARD_HIT_FACTORS)
    def test_factor_category_is_board_hit(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.BOARD_HIT

    def test_limit_up_count_is_absolute(self):
        meta = FACTOR_REGISTRY["limit_up_count"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 1

    def test_limit_up_streak_is_absolute(self):
        meta = FACTOR_REGISTRY["limit_up_streak"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 2

    def test_limit_up_open_pct_is_absolute(self):
        meta = FACTOR_REGISTRY["limit_up_open_pct"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 80

    def test_dragon_tiger_net_buy_is_boolean(self):
        meta = FACTOR_REGISTRY["dragon_tiger_net_buy"]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    def test_first_limit_up_is_boolean(self):
        meta = FACTOR_REGISTRY["first_limit_up"]
        assert meta.threshold_type == ThresholdType.BOOLEAN


# ---------------------------------------------------------------------------
# 指数专题因子验证 (Req 17.1)
# ---------------------------------------------------------------------------


class TestIndexFactors:
    """验证 4 个指数专题因子 (Req 17.1)"""

    INDEX_FACTORS = [
        "index_pe", "index_turnover", "index_ma_trend", "index_vol_ratio",
    ]

    @pytest.mark.parametrize("factor_name", INDEX_FACTORS)
    def test_factor_exists(self, factor_name):
        assert factor_name in FACTOR_REGISTRY

    @pytest.mark.parametrize("factor_name", INDEX_FACTORS)
    def test_factor_category_is_sector(self, factor_name):
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.category == FactorCategory.SECTOR

    def test_index_pe_is_range(self):
        meta = FACTOR_REGISTRY["index_pe"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (10, 25)

    def test_index_turnover_is_range(self):
        meta = FACTOR_REGISTRY["index_turnover"]
        assert meta.threshold_type == ThresholdType.RANGE
        assert meta.default_range == (0.5, 3.0)

    def test_index_ma_trend_is_boolean(self):
        meta = FACTOR_REGISTRY["index_ma_trend"]
        assert meta.threshold_type == ThresholdType.BOOLEAN

    def test_index_vol_ratio_is_absolute(self):
        meta = FACTOR_REGISTRY["index_vol_ratio"]
        assert meta.threshold_type == ThresholdType.ABSOLUTE
        assert meta.default_threshold == 1.0


# ---------------------------------------------------------------------------
# 新增类别的 get_factors_by_category 验证
# ---------------------------------------------------------------------------


class TestNewCategoryQueries:
    """验证 get_factors_by_category 对新类别返回正确结果"""

    def test_chip_category_returns_correct_factors(self):
        factors = get_factors_by_category(FactorCategory.CHIP)
        names = {f.factor_name for f in factors}
        expected = {
            "chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
            "chip_cost_50pct", "chip_weight_avg", "chip_concentration",
        }
        assert names == expected

    def test_margin_category_returns_correct_factors(self):
        factors = get_factors_by_category(FactorCategory.MARGIN)
        names = {f.factor_name for f in factors}
        expected = {
            "rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy",
        }
        assert names == expected

    def test_board_hit_category_returns_correct_factors(self):
        factors = get_factors_by_category(FactorCategory.BOARD_HIT)
        names = {f.factor_name for f in factors}
        expected = {
            "limit_up_count", "limit_up_streak", "limit_up_open_pct",
            "dragon_tiger_net_buy", "first_limit_up",
        }
        assert names == expected

    def test_money_flow_includes_enhanced_factors(self):
        factors = get_factors_by_category(FactorCategory.MONEY_FLOW)
        names = {f.factor_name for f in factors}
        enhanced = {
            "super_large_net_inflow", "large_net_inflow",
            "small_net_outflow", "money_flow_strength", "net_inflow_rate",
        }
        assert enhanced.issubset(names)
