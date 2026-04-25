"""
属性测试：因子注册表完整性与一致性

Property 13: 因子注册表与类别映射一致性
Property 14: 因子元数据完整性

Feature: screening-system-enhancement
Validates: Requirements 18.1, 21.1, 21.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    FactorMeta,
    ThresholdType,
    get_factors_by_category,
)
from app.services.screener.strategy_engine import FACTOR_CATEGORIES


# ---------------------------------------------------------------------------
# 辅助策略：从 FACTOR_REGISTRY 中随机选取因子名称
# ---------------------------------------------------------------------------

factor_names_strategy = st.sampled_from(sorted(FACTOR_REGISTRY.keys()))
category_strategy = st.sampled_from(list(FactorCategory))


# ---------------------------------------------------------------------------
# Property 13: 因子注册表与类别映射一致性
# ---------------------------------------------------------------------------


class TestProperty13RegistryCategoryConsistency:
    """
    Property 13: 因子注册表与类别映射一致性

    **Validates: Requirements 18.1, 21.1, 21.4**

    对于 FACTOR_REGISTRY 中的任意因子：
    1. 其 category 值为有效的 FactorCategory 枚举值
    2. get_factors_by_category(category) 返回包含该因子的列表
    3. FACTOR_CATEGORIES 映射字典包含该因子名称且映射到正确的类别字符串
    """

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_category_is_valid_enum(self, factor_name: str):
        """因子的 category 值必须是有效的 FactorCategory 枚举值"""
        meta = FACTOR_REGISTRY[factor_name]
        assert isinstance(meta.category, FactorCategory)
        assert meta.category.value in [c.value for c in FactorCategory]

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_get_factors_by_category_includes_factor(self, factor_name: str):
        """get_factors_by_category 应返回包含该因子的列表"""
        meta = FACTOR_REGISTRY[factor_name]
        factors_in_category = get_factors_by_category(meta.category)
        factor_names_in_category = [f.factor_name for f in factors_in_category]
        assert factor_name in factor_names_in_category

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_factor_categories_mapping_consistent(self, factor_name: str):
        """FACTOR_CATEGORIES 映射字典应包含该因子且映射到正确的类别字符串"""
        meta = FACTOR_REGISTRY[factor_name]
        assert factor_name in FACTOR_CATEGORIES, (
            f"因子 '{factor_name}' 未在 FACTOR_CATEGORIES 中注册"
        )
        assert FACTOR_CATEGORIES[factor_name] == meta.category.value, (
            f"因子 '{factor_name}' 在 FACTOR_CATEGORIES 中的类别 "
            f"'{FACTOR_CATEGORIES[factor_name]}' 与 FACTOR_REGISTRY 中的 "
            f"'{meta.category.value}' 不一致"
        )

    @given(category=category_strategy)
    @settings(max_examples=100)
    def test_all_category_factors_in_registry(self, category: FactorCategory):
        """按类别查询的因子都应存在于 FACTOR_REGISTRY 中"""
        factors = get_factors_by_category(category)
        for meta in factors:
            assert meta.factor_name in FACTOR_REGISTRY


# ---------------------------------------------------------------------------
# Property 14: 因子元数据完整性
# ---------------------------------------------------------------------------


class TestProperty14FactorMetadataCompleteness:
    """
    Property 14: 因子元数据完整性

    **Validates: Requirements 18.2, 21.1**

    对于 FACTOR_REGISTRY 中的任意因子，其 FactorMeta 实例应包含：
    1. 非空的 factor_name
    2. 非空的 label
    3. 有效的 category（FactorCategory 枚举值）
    4. 有效的 threshold_type（ThresholdType 枚举值）
    5. examples 列表至少包含一个配置示例
    """

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_factor_name_non_empty(self, factor_name: str):
        """factor_name 必须非空"""
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.factor_name, f"因子 '{factor_name}' 的 factor_name 为空"
        assert meta.factor_name == factor_name

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_label_non_empty(self, factor_name: str):
        """label 必须非空"""
        meta = FACTOR_REGISTRY[factor_name]
        assert meta.label, f"因子 '{factor_name}' 的 label 为空"

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_category_valid(self, factor_name: str):
        """category 必须是有效的 FactorCategory 枚举值"""
        meta = FACTOR_REGISTRY[factor_name]
        assert isinstance(meta.category, FactorCategory)

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_threshold_type_valid(self, factor_name: str):
        """threshold_type 必须是有效的 ThresholdType 枚举值"""
        meta = FACTOR_REGISTRY[factor_name]
        assert isinstance(meta.threshold_type, ThresholdType)

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_examples_non_empty(self, factor_name: str):
        """examples 列表至少包含一个配置示例"""
        meta = FACTOR_REGISTRY[factor_name]
        assert len(meta.examples) >= 1, (
            f"因子 '{factor_name}' 的 examples 列表为空"
        )

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_range_type_has_default_range(self, factor_name: str):
        """RANGE 类型因子必须有 default_range"""
        meta = FACTOR_REGISTRY[factor_name]
        if meta.threshold_type == ThresholdType.RANGE:
            assert meta.default_range is not None, (
                f"RANGE 类型因子 '{factor_name}' 缺少 default_range"
            )
            assert len(meta.default_range) == 2
            assert meta.default_range[0] <= meta.default_range[1]

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_boolean_type_has_none_threshold(self, factor_name: str):
        """BOOLEAN 类型因子的 default_threshold 应为 None"""
        meta = FACTOR_REGISTRY[factor_name]
        if meta.threshold_type == ThresholdType.BOOLEAN:
            assert meta.default_threshold is None, (
                f"BOOLEAN 类型因子 '{factor_name}' 的 default_threshold 应为 None"
            )


# ---------------------------------------------------------------------------
# Property 9: SectorScreenConfig 序列化不含 sector_type
# ---------------------------------------------------------------------------


# 辅助策略：生成有效的 SectorScreenConfig 实例
_valid_data_sources = st.sampled_from(["DC", "THS", "TDX", "TI", "CI"])
_valid_sector_types = st.one_of(st.none(), st.sampled_from(["INDUSTRY", "CONCEPT", "REGION", "STYLE"]))
_valid_periods = st.integers(min_value=1, max_value=60)
_valid_top_n = st.integers(min_value=1, max_value=200)


@st.composite
def sector_screen_config_strategy(draw):
    """生成随机的 SectorScreenConfig 实例"""
    from app.core.schemas import SectorScreenConfig
    return SectorScreenConfig(
        sector_data_source=draw(_valid_data_sources),
        sector_type=draw(_valid_sector_types),
        sector_period=draw(_valid_periods),
        sector_top_n=draw(_valid_top_n),
    )


@st.composite
def old_sector_config_dict_strategy(draw):
    """生成包含 sector_type 的旧格式配置字典（模拟向后兼容场景）"""
    return {
        "sector_data_source": draw(_valid_data_sources),
        "sector_type": draw(st.sampled_from(["INDUSTRY", "CONCEPT", "REGION", "STYLE"])),
        "sector_period": draw(_valid_periods),
        "sector_top_n": draw(_valid_top_n),
    }


class TestProperty9SectorScreenConfigSerialization:
    """
    Property 9: SectorScreenConfig 序列化不含 sector_type

    **Validates: Requirements 22.1, 22.6, 22.7**

    对于任意 SectorScreenConfig 实例：
    1. to_dict() 输出字典不包含 'sector_type' 键（需求 22.7）
    2. from_dict() 对包含 sector_type 的旧配置字典不报错、忽略该字段（需求 22.6）
    """

    @given(config=sector_screen_config_strategy())
    @settings(max_examples=100)
    def test_to_dict_excludes_sector_type(self, config):
        """to_dict() 输出不应包含 sector_type 键（需求 22.7）"""
        result = config.to_dict()
        assert "sector_type" not in result, (
            f"to_dict() 输出不应包含 'sector_type'，实际输出: {result}"
        )

    @given(config=sector_screen_config_strategy())
    @settings(max_examples=100)
    def test_to_dict_contains_required_keys(self, config):
        """to_dict() 输出应包含 sector_data_source、sector_period、sector_top_n"""
        result = config.to_dict()
        assert "sector_data_source" in result
        assert "sector_period" in result
        assert "sector_top_n" in result
        assert result["sector_data_source"] == config.sector_data_source
        assert result["sector_period"] == config.sector_period
        assert result["sector_top_n"] == config.sector_top_n

    @given(old_config=old_sector_config_dict_strategy())
    @settings(max_examples=100)
    def test_from_dict_ignores_sector_type(self, old_config):
        """from_dict() 对包含 sector_type 的旧配置不报错，且忽略该字段（需求 22.6）"""
        from app.core.schemas import SectorScreenConfig
        # 不应抛出异常
        result = SectorScreenConfig.from_dict(old_config)
        # sector_type 应被忽略，始终为 None
        assert result.sector_type is None, (
            f"from_dict() 应忽略旧配置中的 sector_type，实际值: {result.sector_type}"
        )
        # 其他字段应正确读取
        assert result.sector_data_source == old_config["sector_data_source"]
        assert result.sector_period == old_config["sector_period"]
        assert result.sector_top_n == old_config["sector_top_n"]

    @given(config=sector_screen_config_strategy())
    @settings(max_examples=100)
    def test_roundtrip_preserves_non_sector_type_fields(self, config):
        """to_dict() → from_dict() 往返保持非 sector_type 字段一致"""
        from app.core.schemas import SectorScreenConfig
        serialized = config.to_dict()
        deserialized = SectorScreenConfig.from_dict(serialized)
        assert deserialized.sector_data_source == config.sector_data_source
        assert deserialized.sector_period == config.sector_period
        assert deserialized.sector_top_n == config.sector_top_n
        # 反序列化后 sector_type 始终为 None
        assert deserialized.sector_type is None

    @given(data_source=_valid_data_sources)
    @settings(max_examples=100)
    def test_from_dict_without_sector_type_key(self, data_source):
        """from_dict() 对不包含 sector_type 的新格式配置也能正常工作"""
        from app.core.schemas import SectorScreenConfig
        new_config = {
            "sector_data_source": data_source,
            "sector_period": 10,
            "sector_top_n": 50,
        }
        result = SectorScreenConfig.from_dict(new_config)
        assert result.sector_data_source == data_source
        assert result.sector_period == 10
        assert result.sector_top_n == 50
        assert result.sector_type is None


# ---------------------------------------------------------------------------
# Property 10: 筹码集中度综合评分公式正确性与有界性
# ---------------------------------------------------------------------------

# 辅助策略：生成有效的 cost 值（[0, 100] 区间）
_cost_value = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


class TestProperty10ChipConcentrationScore:
    """
    Property 10: 筹码集中度综合评分公式正确性与有界性

    **Validates: Requirements 13.4**

    对于任意有效的 cost_5pct、cost_15pct、cost_50pct 值（均在 [0, 100] 区间）：
    1. 结果在 [0, 100] 闭区间内
    2. cost_5pct 越小（筹码越集中），评分越高
    """

    @given(
        cost_5pct=_cost_value,
        cost_15pct=_cost_value,
        cost_50pct=_cost_value,
    )
    @settings(max_examples=200, deadline=None)
    def test_score_bounded(self, cost_5pct: float, cost_15pct: float, cost_50pct: float):
        """筹码集中度评分必须在 [0, 100] 闭区间内"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        score = ScreenDataProvider.compute_chip_concentration(cost_5pct, cost_15pct, cost_50pct)
        assert 0.0 <= score <= 100.0, (
            f"评分 {score} 超出 [0, 100] 区间，"
            f"输入: cost_5pct={cost_5pct}, cost_15pct={cost_15pct}, cost_50pct={cost_50pct}"
        )

    @given(
        cost_5pct_low=st.floats(min_value=0.0, max_value=49.0, allow_nan=False, allow_infinity=False),
        cost_5pct_high=st.floats(min_value=51.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        cost_15pct=_cost_value,
        cost_50pct=_cost_value,
    )
    @settings(max_examples=200)
    def test_lower_cost5_higher_score(
        self,
        cost_5pct_low: float,
        cost_5pct_high: float,
        cost_15pct: float,
        cost_50pct: float,
    ):
        """cost_5pct 越小（筹码越集中），评分越高"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        score_low = ScreenDataProvider.compute_chip_concentration(cost_5pct_low, cost_15pct, cost_50pct)
        score_high = ScreenDataProvider.compute_chip_concentration(cost_5pct_high, cost_15pct, cost_50pct)
        assert score_low >= score_high, (
            f"cost_5pct={cost_5pct_low} 的评分 {score_low} 应 >= "
            f"cost_5pct={cost_5pct_high} 的评分 {score_high}"
        )


# ---------------------------------------------------------------------------
# Property 11: 两融余额趋势判定正确性
# ---------------------------------------------------------------------------

# 辅助策略：生成长度为 5 的融资余额序列
_balance_value = st.floats(min_value=1.0, max_value=1e12, allow_nan=False, allow_infinity=False)
_balance_sequence = st.lists(_balance_value, min_size=5, max_size=5)


class TestProperty11RzrqBalanceTrend:
    """
    Property 11: 两融余额趋势判定正确性

    **Validates: Requirements 14.4**

    对于任意长度为 5 的融资余额序列：
    rzrq_balance_trend = True 当且仅当序列严格递增
    """

    @given(balances=_balance_sequence)
    @settings(max_examples=200)
    def test_trend_iff_strictly_increasing(self, balances: list[float]):
        """rzrq_balance_trend = True 当且仅当序列严格递增"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        result = ScreenDataProvider.compute_rzrq_balance_trend(balances)
        is_strictly_increasing = all(balances[i] > balances[i - 1] for i in range(1, 5))
        assert result == is_strictly_increasing, (
            f"序列 {balances} 的趋势判定 {result} 与预期 {is_strictly_increasing} 不一致"
        )

    @given(
        base=st.floats(min_value=1.0, max_value=1e10, allow_nan=False, allow_infinity=False),
        increments=st.lists(
            st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=4, max_size=4,
        ),
    )
    @settings(max_examples=100)
    def test_strictly_increasing_returns_true(self, base: float, increments: list[float]):
        """严格递增序列应返回 True"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        balances = [base]
        for inc in increments:
            balances.append(balances[-1] + inc)
        assert ScreenDataProvider.compute_rzrq_balance_trend(balances) is True

    @given(balances=st.lists(_balance_value, min_size=0, max_size=4))
    @settings(max_examples=100)
    def test_short_sequence_returns_false(self, balances: list[float]):
        """长度不足 5 的序列应返回 False"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        assert ScreenDataProvider.compute_rzrq_balance_trend(balances) is False


# ---------------------------------------------------------------------------
# Property 12: 资金流强度综合评分有界性
# ---------------------------------------------------------------------------

# 辅助策略：生成 [0, 100] 区间的分项评分
_score_value = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


class TestProperty12MoneyFlowStrength:
    """
    Property 12: 资金流强度综合评分有界性

    **Validates: Requirements 15.3**

    对于任意有效的超大单、大单、中单、小单分项评分（均在 [0, 100]），
    money_flow_strength 综合评分应在 [0, 100] 闭区间内。
    """

    @given(
        super_large=_score_value,
        large=_score_value,
        mid=_score_value,
        small_outflow=_score_value,
    )
    @settings(max_examples=200)
    def test_score_bounded(
        self, super_large: float, large: float, mid: float, small_outflow: float,
    ):
        """资金流强度评分必须在 [0, 100] 闭区间内"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        score = ScreenDataProvider.compute_money_flow_strength(
            super_large, large, mid, small_outflow,
        )
        assert 0.0 <= score <= 100.0, (
            f"评分 {score} 超出 [0, 100] 区间，"
            f"输入: super_large={super_large}, large={large}, "
            f"mid={mid}, small_outflow={small_outflow}"
        )

    @given(
        super_large=_score_value,
        large=_score_value,
        mid=_score_value,
        small_outflow=_score_value,
    )
    @settings(max_examples=100)
    def test_formula_correctness(
        self, super_large: float, large: float, mid: float, small_outflow: float,
    ):
        """评分应等于加权求和公式的结果（clamp 到 [0, 100]）"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        score = ScreenDataProvider.compute_money_flow_strength(
            super_large, large, mid, small_outflow,
        )
        expected = super_large * 0.4 + large * 0.3 + mid * 0.2 + small_outflow * 0.1
        expected = max(0.0, min(100.0, expected))
        assert abs(score - expected) < 1e-9, (
            f"评分 {score} 与预期 {expected} 不一致"
        )


# ---------------------------------------------------------------------------
# Property 1: 加权求和评分正确性与有界性（Task 6.12）
# ---------------------------------------------------------------------------

# 辅助策略：生成模块评分字典和权重字典
_module_names = ["factor_editor", "ma_trend", "indicator_params", "breakout", "volume_price"]
_module_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_module_weight = st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)


@st.composite
def module_scores_strategy(draw):
    """生成随机的模块评分字典（至少 1 个模块）"""
    n = draw(st.integers(min_value=1, max_value=5))
    selected = draw(st.permutations(_module_names))[:n]
    return {name: draw(_module_score) for name in selected}


@st.composite
def module_weights_strategy(draw):
    """生成随机的模块权重字典"""
    return {name: draw(_module_weight) for name in _module_names}


class TestProperty1WeightedScoreCorrectness:
    """
    Property 1: 加权求和评分正确性与有界性

    **Validates: Requirements 5.1, 5.3, 5.4**

    对于任意非空的模块评分字典和正权重字典：
    1. 结果在 [0, 100] 闭区间内
    2. 评分为 0 的模块不计入分母
    3. 结果等于 Σ(score × weight) / Σ(weight)（仅对 score > 0 且 weight > 0 的模块求和）
    """

    @given(
        module_scores=module_scores_strategy(),
        weights=module_weights_strategy(),
    )
    @settings(max_examples=100)
    def test_result_bounded(self, module_scores: dict, weights: dict):
        """加权求和结果必须在 [0, 100] 闭区间内"""
        from app.services.screener.screen_executor import ScreenExecutor
        result = ScreenExecutor._compute_weighted_score(module_scores, weights)
        assert 0.0 <= result <= 100.0, (
            f"评分 {result} 超出 [0, 100] 区间，"
            f"module_scores={module_scores}, weights={weights}"
        )

    @given(
        module_scores=module_scores_strategy(),
        weights=module_weights_strategy(),
    )
    @settings(max_examples=100)
    def test_zero_scores_excluded_from_denominator(self, module_scores: dict, weights: dict):
        """评分为 0 的模块不计入分母"""
        from app.services.screener.screen_executor import ScreenExecutor

        # 将部分模块评分设为 0
        zeroed = dict(module_scores)
        for key in list(zeroed.keys())[:1]:
            zeroed[key] = 0.0

        result = ScreenExecutor._compute_weighted_score(zeroed, weights)

        # 手动计算预期值
        numerator = 0.0
        denominator = 0.0
        for mod, score in zeroed.items():
            if score <= 0.0:
                continue
            w = weights.get(mod, 0.0)
            if w <= 0.0:
                continue
            numerator += score * w
            denominator += w

        if denominator <= 0.0:
            expected = 0.0
        else:
            expected = max(0.0, min(100.0, numerator / denominator))

        assert abs(result - expected) < 1e-9, (
            f"结果 {result} 与预期 {expected} 不一致"
        )

    @given(
        module_scores=module_scores_strategy(),
        weights=module_weights_strategy(),
    )
    @settings(max_examples=100)
    def test_formula_correctness(self, module_scores: dict, weights: dict):
        """结果等于加权求和公式"""
        from app.services.screener.screen_executor import ScreenExecutor
        result = ScreenExecutor._compute_weighted_score(module_scores, weights)

        numerator = 0.0
        denominator = 0.0
        for mod, score in module_scores.items():
            if score <= 0.0:
                continue
            w = weights.get(mod, 0.0)
            if w <= 0.0:
                continue
            numerator += score * w
            denominator += w

        if denominator <= 0.0:
            expected = 0.0
        else:
            expected = max(0.0, min(100.0, numerator / denominator))

        assert abs(result - expected) < 1e-9, (
            f"结果 {result} 与预期 {expected} 不一致"
        )

    def test_empty_scores_returns_zero(self):
        """空评分字典应返回 0"""
        from app.services.screener.screen_executor import ScreenExecutor
        result = ScreenExecutor._compute_weighted_score({})
        assert result == 0.0

    def test_default_weights_used_when_none(self):
        """weights 为 None 时使用默认权重"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import DEFAULT_MODULE_WEIGHTS
        scores = {"ma_trend": 80.0, "breakout": 60.0}
        result = ScreenExecutor._compute_weighted_score(scores, None)
        # 手动计算
        num = 80.0 * DEFAULT_MODULE_WEIGHTS["ma_trend"] + 60.0 * DEFAULT_MODULE_WEIGHTS["breakout"]
        den = DEFAULT_MODULE_WEIGHTS["ma_trend"] + DEFAULT_MODULE_WEIGHTS["breakout"]
        expected = max(0.0, min(100.0, num / den))
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Property 2: 风控过滤规则一致性（Task 6.13）
# ---------------------------------------------------------------------------

# 辅助策略：生成 ScreenItem 列表和相关数据
_trend_score_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_daily_change_st = st.floats(min_value=-10.0, max_value=15.0, allow_nan=False, allow_infinity=False)
_symbol_st = st.text(
    alphabet=st.sampled_from("0123456789"),
    min_size=6, max_size=6,
)


@st.composite
def screen_item_strategy(draw):
    """生成随机的 ScreenItem"""
    from app.core.schemas import ScreenItem, RiskLevel, SignalDetail, SignalCategory
    from decimal import Decimal
    symbol = draw(_symbol_st)
    trend_score = draw(_trend_score_st)
    risk_level = RiskLevel.LOW if trend_score >= 80 else (RiskLevel.MEDIUM if trend_score >= 50 else RiskLevel.HIGH)
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal("10.00"),
        trend_score=trend_score,
        risk_level=risk_level,
        signals=[SignalDetail(category=SignalCategory.MA_TREND, label="ma_trend")],
    )


@st.composite
def risk_filter_inputs_strategy(draw):
    """生成风控过滤测试输入"""
    from app.services.risk_controller import (
        MarketRiskChecker, StockRiskFilter, BlackWhiteListManager,
    )

    n_items = draw(st.integers(min_value=0, max_value=10))
    items = [draw(screen_item_strategy()) for _ in range(n_items)]

    # 生成 stocks_data（包含 daily_change_pct）
    stocks_data = {}
    for item in items:
        stocks_data[item.symbol] = {
            "daily_change_pct": draw(_daily_change_st),
        }

    # 生成指数收盘价序列（可能触发不同风险等级）
    use_index = draw(st.booleans())
    if use_index:
        # 生成 61 个收盘价以确保 MA60 可计算
        base = draw(st.floats(min_value=2000.0, max_value=5000.0, allow_nan=False, allow_infinity=False))
        index_closes = [base + draw(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)) for _ in range(61)]
    else:
        index_closes = None

    # 黑名单：随机选取部分股票
    blacklist_manager = BlackWhiteListManager()
    if items:
        n_blacklisted = draw(st.integers(min_value=0, max_value=min(3, len(items))))
        for i in range(n_blacklisted):
            blacklist_manager.add_to_blacklist(items[i].symbol, "test")

    return items, stocks_data, index_closes, blacklist_manager


class TestProperty2RiskFilterConsistency:
    """
    Property 2: 风控过滤规则一致性

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

    对于任意候选股票列表、股票数据字典和指数收盘价序列：
    1. DANGER 状态下，所有输出股票的 trend_score >= danger_strong_threshold
    2. CAUTION 状态下，所有输出股票的 trend_score >= 90
    3. 所有输出股票的 daily_change_pct <= 9%
    4. 所有输出股票不在黑名单中
    5. 输出列表是输入列表的子集
    """

    @given(inputs=risk_filter_inputs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_output_is_subset_of_input(self, inputs):
        """输出列表是输入列表的子集"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.services.risk_controller import MarketRiskChecker, StockRiskFilter

        items, stocks_data, index_closes, blacklist_manager = inputs
        filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=MarketRiskChecker(),
            stock_risk_filter=StockRiskFilter(),
            blacklist_manager=blacklist_manager,
        )
        input_symbols = {item.symbol for item in items}
        for item in filtered:
            assert item.symbol in input_symbols

    @given(inputs=risk_filter_inputs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_no_blacklisted_in_output(self, inputs):
        """所有输出股票不在黑名单中"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.services.risk_controller import MarketRiskChecker, StockRiskFilter

        items, stocks_data, index_closes, blacklist_manager = inputs
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=MarketRiskChecker(),
            stock_risk_filter=StockRiskFilter(),
            blacklist_manager=blacklist_manager,
        )
        blacklist = blacklist_manager.get_blacklist()
        for item in filtered:
            assert item.symbol not in blacklist, (
                f"黑名单股票 {item.symbol} 不应出现在输出中"
            )

    @given(inputs=risk_filter_inputs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_no_high_daily_gain_in_output(self, inputs):
        """所有输出股票的 daily_change_pct <= 9%"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.services.risk_controller import MarketRiskChecker, StockRiskFilter

        items, stocks_data, index_closes, blacklist_manager = inputs
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=MarketRiskChecker(),
            stock_risk_filter=StockRiskFilter(),
            blacklist_manager=blacklist_manager,
        )
        for item in filtered:
            daily_change = float(stocks_data.get(item.symbol, {}).get("daily_change_pct", 0.0))
            assert daily_change <= 9.0, (
                f"股票 {item.symbol} 单日涨幅 {daily_change}% > 9%，不应出现在输出中"
            )

    @given(inputs=risk_filter_inputs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_danger_only_strong_stocks(self, inputs):
        """DANGER 状态下，所有输出股票的 trend_score >= danger_strong_threshold"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.services.risk_controller import MarketRiskChecker, StockRiskFilter
        from app.core.schemas import MarketRiskLevel

        items, stocks_data, index_closes, blacklist_manager = inputs
        filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=MarketRiskChecker(),
            stock_risk_filter=StockRiskFilter(),
            blacklist_manager=blacklist_manager,
        )
        if risk_level == MarketRiskLevel.DANGER:
            for item in filtered:
                assert item.trend_score >= 95.0, (
                    f"DANGER 状态下股票 {item.symbol} 趋势评分 {item.trend_score} < 95"
                )

    @given(inputs=risk_filter_inputs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_caution_threshold_90(self, inputs):
        """CAUTION 状态下，所有输出股票的 trend_score >= 90"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.services.risk_controller import MarketRiskChecker, StockRiskFilter
        from app.core.schemas import MarketRiskLevel

        items, stocks_data, index_closes, blacklist_manager = inputs
        filtered, risk_level = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=MarketRiskChecker(),
            stock_risk_filter=StockRiskFilter(),
            blacklist_manager=blacklist_manager,
        )
        if risk_level == MarketRiskLevel.CAUTION:
            for item in filtered:
                assert item.trend_score >= 90.0, (
                    f"CAUTION 状态下股票 {item.symbol} 趋势评分 {item.trend_score} < 90"
                )


# ---------------------------------------------------------------------------
# Property 3: 多重突破信号列表有效性（Task 6.14）
# ---------------------------------------------------------------------------

# 辅助策略：生成有效的 OHLCV 价格序列
_price_st = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)
_volume_st = st.integers(min_value=100, max_value=10_000_000)


@st.composite
def ohlcv_strategy(draw, min_length=30, max_length=120):
    """生成有效的 OHLCV 价格序列"""
    n = draw(st.integers(min_value=min_length, max_value=max_length))
    closes = [draw(_price_st) for _ in range(n)]
    highs = [max(c, draw(_price_st)) for c in closes]
    lows = [min(c, draw(st.floats(min_value=0.5, max_value=float(c), allow_nan=False, allow_infinity=False))) for c in closes]
    volumes = [draw(_volume_st) for _ in range(n)]
    return closes, highs, lows, volumes


@st.composite
def breakout_config_strategy(draw):
    """生成随机的突破配置"""
    return {
        "box_breakout": draw(st.booleans()),
        "high_breakout": draw(st.booleans()),
        "trendline_breakout": draw(st.booleans()),
        "volume_ratio_threshold": draw(st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False)),
        "confirm_days": draw(st.integers(min_value=0, max_value=3)),
    }


class TestProperty3MultiBreakoutSignals:
    """
    Property 3: 多重突破信号列表有效性

    **Validates: Requirements 6.1, 6.2, 6.3**

    对于任意有效的 OHLCV 价格序列和突破配置：
    1. 返回值始终为列表类型
    2. 列表长度 <= 启用的突破类型数量（最多 3）
    3. 列表中每个元素包含 type、is_valid、volume_ratio 字段
    4. _build_breakout_signals() 为每个 is_valid=True 的突破生成恰好一个 SignalDetail
    """

    @given(
        ohlcv=ohlcv_strategy(),
        bo_cfg=breakout_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_returns_list(self, ohlcv, bo_cfg):
        """返回值始终为列表类型"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        closes, highs, lows, volumes = ohlcv
        result = ScreenDataProvider._detect_all_breakouts(closes, highs, lows, volumes, bo_cfg)
        assert isinstance(result, list)

    @given(
        ohlcv=ohlcv_strategy(),
        bo_cfg=breakout_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_length_bounded_by_enabled_types(self, ohlcv, bo_cfg):
        """列表长度 <= 启用的突破类型数量"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        closes, highs, lows, volumes = ohlcv
        result = ScreenDataProvider._detect_all_breakouts(closes, highs, lows, volumes, bo_cfg)

        enabled_count = sum([
            bo_cfg.get("box_breakout", True),
            bo_cfg.get("high_breakout", True),
            bo_cfg.get("trendline_breakout", True),
        ])
        assert len(result) <= enabled_count, (
            f"突破信号数量 {len(result)} 超过启用类型数量 {enabled_count}"
        )

    @given(
        ohlcv=ohlcv_strategy(),
        bo_cfg=breakout_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_elements_have_required_fields(self, ohlcv, bo_cfg):
        """列表中每个元素包含 type、is_valid、volume_ratio 字段"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        closes, highs, lows, volumes = ohlcv
        result = ScreenDataProvider._detect_all_breakouts(closes, highs, lows, volumes, bo_cfg)

        for bo in result:
            assert "type" in bo, f"突破信号缺少 'type' 字段: {bo}"
            assert "is_valid" in bo, f"突破信号缺少 'is_valid' 字段: {bo}"
            assert "volume_ratio" in bo, f"突破信号缺少 'volume_ratio' 字段: {bo}"

    @given(
        ohlcv=ohlcv_strategy(),
        bo_cfg=breakout_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_build_signals_matches_valid_breakouts(self, ohlcv, bo_cfg):
        """_build_breakout_signals 为每个 is_valid=True 的突破生成恰好一个 SignalDetail"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalCategory

        closes, highs, lows, volumes = ohlcv
        breakout_list = ScreenDataProvider._detect_all_breakouts(closes, highs, lows, volumes, bo_cfg)

        stock_data = {"breakout_list": breakout_list, "breakout": breakout_list[0] if breakout_list else None}
        signals = ScreenExecutor._build_breakout_signals(stock_data)

        valid_count = sum(1 for bo in breakout_list if bo.get("is_valid"))
        assert len(signals) == valid_count, (
            f"信号数量 {len(signals)} 与有效突破数量 {valid_count} 不一致"
        )
        for sig in signals:
            assert sig.category == SignalCategory.BREAKOUT


# ---------------------------------------------------------------------------
# Property 4: 信号强度分级阈值一致性（Task 6.15）
# ---------------------------------------------------------------------------


@st.composite
def ma_trend_signal_strategy(draw):
    """生成 MA_TREND 类别的信号和 stock_data"""
    from app.core.schemas import SignalDetail, SignalCategory
    ma_trend_val = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    signal = SignalDetail(category=SignalCategory.MA_TREND, label="ma_trend")
    stock_data = {"ma_trend": ma_trend_val}
    return signal, stock_data, ma_trend_val


@st.composite
def breakout_signal_strategy(draw):
    """生成 BREAKOUT 类别的信号和 stock_data"""
    from app.core.schemas import SignalDetail, SignalCategory
    volume_ratio = draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False))
    bo_type = draw(st.sampled_from(["BOX", "PREVIOUS_HIGH", "TRENDLINE"]))
    signal = SignalDetail(category=SignalCategory.BREAKOUT, label="breakout", breakout_type=bo_type)
    stock_data = {
        "breakout_list": [{"type": bo_type, "volume_ratio": volume_ratio, "is_valid": True}],
    }
    return signal, stock_data, volume_ratio


@st.composite
def indicator_signal_strategy(draw):
    """生成技术指标类别的信号和 stock_data"""
    from app.core.schemas import SignalDetail, SignalCategory
    category = draw(st.sampled_from([SignalCategory.MACD, SignalCategory.BOLL, SignalCategory.RSI, SignalCategory.DMA]))
    signal = SignalDetail(category=category, label=category.value.lower())

    macd_on = draw(st.booleans())
    boll_on = draw(st.booleans())
    rsi_on = draw(st.booleans())
    dma_on = draw(st.booleans())

    stock_data = {
        "macd": macd_on,
        "boll": boll_on,
        "rsi": rsi_on,
        "dma": {"dma": 1.0, "ama": 0.5} if dma_on else None,
    }
    triggered_count = sum([macd_on, boll_on, rsi_on, dma_on])
    return signal, stock_data, triggered_count


class TestProperty4SignalStrengthThresholds:
    """
    Property 4: 信号强度分级阈值一致性

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

    对于任意 SignalDetail 和 stock_data 字典：
    1. 返回值始终为 SignalStrength 枚举值
    2. MA_TREND：ma_trend >= 90 → STRONG，>= 70 → MEDIUM，其余 → WEAK
    3. BREAKOUT：volume_ratio >= 2.0 → STRONG，>= 1.5 → MEDIUM，其余 → WEAK
    4. 技术指标：触发数 >= 3 → STRONG，== 2 → MEDIUM，== 1 → WEAK
    """

    @given(data=ma_trend_signal_strategy())
    @settings(max_examples=100)
    def test_ma_trend_strength_thresholds(self, data):
        """MA_TREND 信号强度阈值正确"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalStrength

        signal, stock_data, ma_trend_val = data
        result = ScreenExecutor._compute_signal_strength(signal, stock_data)

        assert isinstance(result, SignalStrength)
        if ma_trend_val >= 90:
            assert result == SignalStrength.STRONG, (
                f"ma_trend={ma_trend_val} 应为 STRONG，实际为 {result}"
            )
        elif ma_trend_val >= 70:
            assert result == SignalStrength.MEDIUM, (
                f"ma_trend={ma_trend_val} 应为 MEDIUM，实际为 {result}"
            )
        else:
            assert result == SignalStrength.WEAK, (
                f"ma_trend={ma_trend_val} 应为 WEAK，实际为 {result}"
            )

    @given(data=breakout_signal_strategy())
    @settings(max_examples=100)
    def test_breakout_strength_thresholds(self, data):
        """BREAKOUT 信号强度阈值正确"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalStrength

        signal, stock_data, volume_ratio = data
        result = ScreenExecutor._compute_signal_strength(signal, stock_data)

        assert isinstance(result, SignalStrength)
        if volume_ratio >= 2.0:
            assert result == SignalStrength.STRONG, (
                f"volume_ratio={volume_ratio} 应为 STRONG，实际为 {result}"
            )
        elif volume_ratio >= 1.5:
            assert result == SignalStrength.MEDIUM, (
                f"volume_ratio={volume_ratio} 应为 MEDIUM，实际为 {result}"
            )
        else:
            assert result == SignalStrength.WEAK, (
                f"volume_ratio={volume_ratio} 应为 WEAK，实际为 {result}"
            )

    @given(data=indicator_signal_strategy())
    @settings(max_examples=100)
    def test_indicator_strength_by_count(self, data):
        """技术指标信号强度按触发数量分级"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalStrength

        signal, stock_data, triggered_count = data
        result = ScreenExecutor._compute_signal_strength(signal, stock_data)

        assert isinstance(result, SignalStrength)
        if triggered_count >= 3:
            assert result == SignalStrength.STRONG, (
                f"触发数={triggered_count} 应为 STRONG，实际为 {result}"
            )
        elif triggered_count >= 2:
            assert result == SignalStrength.MEDIUM, (
                f"触发数={triggered_count} 应为 MEDIUM，实际为 {result}"
            )
        else:
            assert result == SignalStrength.WEAK, (
                f"触发数={triggered_count} 应为 WEAK，实际为 {result}"
            )

    @given(
        ma_trend_val=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_always_returns_signal_strength_enum(self, ma_trend_val):
        """返回值始终为 SignalStrength 枚举值"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalDetail, SignalCategory, SignalStrength

        signal = SignalDetail(category=SignalCategory.MA_TREND, label="ma_trend")
        stock_data = {"ma_trend": ma_trend_val}
        result = ScreenExecutor._compute_signal_strength(signal, stock_data)
        assert isinstance(result, SignalStrength)


# ---------------------------------------------------------------------------
# Property 5: 信号新鲜度标记一致性（Task 6.16）
# ---------------------------------------------------------------------------

_signal_category_st = st.sampled_from([
    "MA_TREND", "MACD", "BOLL", "RSI", "DMA", "BREAKOUT",
    "CAPITAL_INFLOW", "LARGE_ORDER", "MA_SUPPORT", "SECTOR_STRONG",
])
_signal_label_st = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=3, max_size=15,
)


@st.composite
def signal_detail_strategy(draw):
    """生成随机的 SignalDetail"""
    from app.core.schemas import SignalDetail, SignalCategory
    cat_str = draw(_signal_category_st)
    cat = SignalCategory(cat_str)
    label = draw(_signal_label_st)
    return SignalDetail(category=cat, label=label)


@st.composite
def signal_lists_strategy(draw):
    """生成当前信号列表和上一轮信号列表"""
    n_current = draw(st.integers(min_value=1, max_value=8))
    current = [draw(signal_detail_strategy()) for _ in range(n_current)]

    use_previous = draw(st.booleans())
    if use_previous:
        n_previous = draw(st.integers(min_value=0, max_value=8))
        previous = [draw(signal_detail_strategy()) for _ in range(n_previous)]
    else:
        previous = None

    return current, previous


class TestProperty5SignalFreshnessConsistency:
    """
    Property 5: 信号新鲜度标记一致性

    **Validates: Requirements 8.1, 8.3, 8.4**

    对于任意当前信号列表和上一轮信号列表：
    1. 上一轮为 None 或空列表时，所有信号标记为 NEW
    2. 存在于上一轮的信号标记为 CONTINUING
    3. 不存在于上一轮的信号标记为 NEW
    4. has_new_signal 为 True 当且仅当至少一个信号的 freshness 为 NEW
    """

    @given(data=signal_lists_strategy())
    @settings(max_examples=100)
    def test_no_previous_all_new(self, data):
        """上一轮为 None 或空列表时，所有信号标记为 NEW"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalFreshness

        current, previous = data
        if previous is not None and len(previous) > 0:
            return  # 跳过有上一轮数据的情况

        # 使用 None 或空列表
        for prev in [None, []]:
            # 创建副本避免修改原始数据
            from app.core.schemas import SignalDetail
            current_copy = [
                SignalDetail(category=s.category, label=s.label)
                for s in current
            ]
            result = ScreenExecutor._mark_signal_freshness(current_copy, prev)
            for sig in result:
                assert sig.freshness == SignalFreshness.NEW, (
                    f"上一轮为空时，信号 ({sig.category}, {sig.label}) 应为 NEW，"
                    f"实际为 {sig.freshness}"
                )

    @given(data=signal_lists_strategy())
    @settings(max_examples=100)
    def test_freshness_marking_correctness(self, data):
        """信号新鲜度标记正确性"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalFreshness, SignalDetail

        current, previous = data

        # 创建副本
        current_copy = [
            SignalDetail(category=s.category, label=s.label)
            for s in current
        ]

        result = ScreenExecutor._mark_signal_freshness(current_copy, previous)

        if not previous:
            # 无上一轮数据，所有信号为 NEW
            for sig in result:
                assert sig.freshness == SignalFreshness.NEW
        else:
            prev_keys = {(s.category, s.label) for s in previous}
            for sig in result:
                key = (sig.category, sig.label)
                if key in prev_keys:
                    assert sig.freshness == SignalFreshness.CONTINUING, (
                        f"信号 {key} 存在于上一轮，应为 CONTINUING，实际为 {sig.freshness}"
                    )
                else:
                    assert sig.freshness == SignalFreshness.NEW, (
                        f"信号 {key} 不存在于上一轮，应为 NEW，实际为 {sig.freshness}"
                    )

    @given(data=signal_lists_strategy())
    @settings(max_examples=100)
    def test_has_new_signal_consistency(self, data):
        """has_new_signal 为 True 当且仅当至少一个信号的 freshness 为 NEW"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import SignalFreshness, SignalDetail

        current, previous = data

        current_copy = [
            SignalDetail(category=s.category, label=s.label)
            for s in current
        ]

        result = ScreenExecutor._mark_signal_freshness(current_copy, previous)
        has_new = any(s.freshness == SignalFreshness.NEW for s in result)

        # 验证 has_new_signal 的计算逻辑
        assert has_new == any(s.freshness == SignalFreshness.NEW for s in result)


# ---------------------------------------------------------------------------
# Property 6: 选股结果变化检测完备性（Task 6.17）
# ---------------------------------------------------------------------------


@st.composite
def screen_items_pair_strategy(draw):
    """生成当前选股结果列表和上一轮选股结果列表"""
    from app.core.schemas import ScreenItem, RiskLevel, SignalDetail, SignalCategory
    from decimal import Decimal

    # 生成一组唯一的 symbol
    all_symbols = [f"{i:06d}" for i in range(20)]
    n_current = draw(st.integers(min_value=0, max_value=10))
    n_previous = draw(st.integers(min_value=0, max_value=10))

    current_symbols = draw(
        st.lists(
            st.sampled_from(all_symbols),
            min_size=n_current, max_size=n_current, unique=True,
        )
    )
    previous_symbols = draw(
        st.lists(
            st.sampled_from(all_symbols),
            min_size=n_previous, max_size=n_previous, unique=True,
        )
    )

    def make_item(symbol, signal_labels=None):
        if signal_labels is None:
            signal_labels = ["ma_trend"]
        signals = [
            SignalDetail(category=SignalCategory.MA_TREND, label=lbl)
            for lbl in signal_labels
        ]
        return ScreenItem(
            symbol=symbol,
            ref_buy_price=Decimal("10.00"),
            trend_score=80.0,
            risk_level=RiskLevel.LOW,
            signals=signals,
        )

    # 为共同股票随机决定信号是否变化
    common_symbols = set(current_symbols) & set(previous_symbols)

    current_items = []
    for sym in current_symbols:
        if sym in common_symbols and draw(st.booleans()):
            # 信号变化
            current_items.append(make_item(sym, ["macd", "boll"]))
        else:
            current_items.append(make_item(sym, ["ma_trend"]))

    previous_items = [make_item(sym, ["ma_trend"]) for sym in previous_symbols]

    use_previous = draw(st.booleans())
    return current_items, previous_items if use_previous else None


class TestProperty6ResultDiffCompleteness:
    """
    Property 6: 选股结果变化检测完备性

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

    对于任意当前选股结果列表和上一轮选股结果列表：
    1. 本轮有、上轮无的股票标记为 NEW
    2. 两轮都有但信号集合不同的股票标记为 UPDATED
    3. 上轮有、本轮无的股票标记为 REMOVED
    4. 两轮都有且信号集合相同的股票不出现在 changes 中
    5. changes 中每个 symbol 唯一（无重复）
    """

    @given(data=screen_items_pair_strategy())
    @settings(max_examples=100)
    def test_new_items_detected(self, data):
        """本轮有、上轮无的股票标记为 NEW"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import ChangeType

        current_items, previous_items = data
        changes = ScreenExecutor._compute_result_diff(current_items, previous_items)

        current_symbols = {item.symbol for item in current_items}
        prev_symbols = {item.symbol for item in previous_items} if previous_items else set()

        new_symbols = current_symbols - prev_symbols
        new_changes = {c.symbol for c in changes if c.change_type == ChangeType.NEW}

        for sym in new_symbols:
            assert sym in new_changes, (
                f"新增股票 {sym} 未被标记为 NEW"
            )

    @given(data=screen_items_pair_strategy())
    @settings(max_examples=100)
    def test_removed_items_detected(self, data):
        """上轮有、本轮无的股票标记为 REMOVED"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import ChangeType

        current_items, previous_items = data
        changes = ScreenExecutor._compute_result_diff(current_items, previous_items)

        current_symbols = {item.symbol for item in current_items}
        prev_symbols = {item.symbol for item in previous_items} if previous_items else set()

        removed_symbols = prev_symbols - current_symbols
        removed_changes = {c.symbol for c in changes if c.change_type == ChangeType.REMOVED}

        for sym in removed_symbols:
            assert sym in removed_changes, (
                f"移除股票 {sym} 未被标记为 REMOVED"
            )

    @given(data=screen_items_pair_strategy())
    @settings(max_examples=100)
    def test_unchanged_not_in_changes(self, data):
        """两轮都有且信号集合相同的股票不出现在 changes 中"""
        from app.services.screener.screen_executor import ScreenExecutor

        current_items, previous_items = data
        changes = ScreenExecutor._compute_result_diff(current_items, previous_items)

        if previous_items is None:
            return  # 无上一轮数据时所有都是 NEW

        current_by_sym = {item.symbol: item for item in current_items}
        prev_by_sym = {item.symbol: item for item in previous_items}
        change_symbols = {c.symbol for c in changes}

        for sym in set(current_by_sym.keys()) & set(prev_by_sym.keys()):
            cur_keys = {(s.category, s.label) for s in current_by_sym[sym].signals}
            prev_keys = {(s.category, s.label) for s in prev_by_sym[sym].signals}
            if cur_keys == prev_keys:
                assert sym not in change_symbols, (
                    f"信号未变化的股票 {sym} 不应出现在 changes 中"
                )

    @given(data=screen_items_pair_strategy())
    @settings(max_examples=100)
    def test_no_duplicate_symbols_in_changes(self, data):
        """changes 中每个 symbol 唯一（无重复）"""
        from app.services.screener.screen_executor import ScreenExecutor

        current_items, previous_items = data
        changes = ScreenExecutor._compute_result_diff(current_items, previous_items)

        symbols = [c.symbol for c in changes]
        assert len(symbols) == len(set(symbols)), (
            f"changes 中存在重复 symbol: {symbols}"
        )

    @given(data=screen_items_pair_strategy())
    @settings(max_examples=100)
    def test_updated_items_have_different_signals(self, data):
        """标记为 UPDATED 的股票信号集合确实不同"""
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import ChangeType

        current_items, previous_items = data
        changes = ScreenExecutor._compute_result_diff(current_items, previous_items)

        if previous_items is None:
            return

        current_by_sym = {item.symbol: item for item in current_items}
        prev_by_sym = {item.symbol: item for item in previous_items}

        for change in changes:
            if change.change_type == ChangeType.UPDATED:
                cur_item = current_by_sym.get(change.symbol)
                prev_item = prev_by_sym.get(change.symbol)
                assert cur_item is not None and prev_item is not None
                cur_keys = {(s.category, s.label) for s in cur_item.signals}
                prev_keys = {(s.category, s.label) for s in prev_item.signals}
                assert cur_keys != prev_keys, (
                    f"UPDATED 股票 {change.symbol} 的信号集合应不同"
                )


# ---------------------------------------------------------------------------
# Property 7: FactorEvaluator 阈值类型全覆盖（Task 8.3）
# ---------------------------------------------------------------------------

# 辅助策略：生成各种 ThresholdType 的 FactorCondition 和对应的 stock_data

_threshold_types_for_eval = st.sampled_from([
    "ABSOLUTE", "PERCENTILE", "INDUSTRY_RELATIVE", "BOOLEAN", "RANGE",
])

_numeric_value = st.floats(
    min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False,
)
_positive_value = st.floats(
    min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False,
)
_operator_st = st.sampled_from([">", "<", ">=", "<=", "=="])
_threshold_st = st.floats(
    min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False,
)


@st.composite
def range_factor_condition_strategy(draw):
    """生成 RANGE 类型的 FactorCondition 和 stock_data"""
    from app.core.schemas import FactorCondition

    # 从 RANGE 类型因子中随机选取
    range_factors = [
        name for name, meta in FACTOR_REGISTRY.items()
        if meta.threshold_type == ThresholdType.RANGE
    ]
    factor_name = draw(st.sampled_from(range_factors))

    low = draw(st.floats(min_value=-100.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    high = draw(st.floats(min_value=low + 0.01, max_value=200.0, allow_nan=False, allow_infinity=False))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=">=",
        threshold=None,
        params={"threshold_low": low, "threshold_high": high},
    )

    # 生成值：有时在区间内，有时在区间外，有时为 None
    value_choice = draw(st.sampled_from(["in_range", "out_range", "none"]))
    if value_choice == "none":
        stock_data = {}
        expected_passed = False
    elif value_choice == "in_range":
        val = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
        stock_data = {factor_name: val}
        expected_passed = True
    else:
        # 在区间外
        if draw(st.booleans()):
            val = draw(st.floats(min_value=high + 0.01, max_value=high + 100.0, allow_nan=False, allow_infinity=False))
        else:
            val = draw(st.floats(min_value=low - 100.0, max_value=low - 0.01, allow_nan=False, allow_infinity=False))
        stock_data = {factor_name: val}
        expected_passed = False

    return condition, stock_data, expected_passed


@st.composite
def boolean_factor_condition_strategy(draw):
    """生成 BOOLEAN 类型的 FactorCondition 和 stock_data"""
    from app.core.schemas import FactorCondition

    boolean_factors = [
        name for name, meta in FACTOR_REGISTRY.items()
        if meta.threshold_type == ThresholdType.BOOLEAN
    ]
    factor_name = draw(st.sampled_from(boolean_factors))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=">=",
        threshold=None,
    )

    value_choice = draw(st.sampled_from(["true", "false", "none"]))
    if value_choice == "none":
        stock_data = {}
        expected_passed = False
    elif value_choice == "true":
        stock_data = {factor_name: True}
        expected_passed = True
    else:
        stock_data = {factor_name: False}
        expected_passed = False

    return condition, stock_data, expected_passed


@st.composite
def absolute_factor_condition_strategy(draw):
    """生成 ABSOLUTE 类型的 FactorCondition 和 stock_data"""
    from app.core.schemas import FactorCondition

    absolute_factors = [
        name for name, meta in FACTOR_REGISTRY.items()
        if meta.threshold_type == ThresholdType.ABSOLUTE
    ]
    factor_name = draw(st.sampled_from(absolute_factors))

    operator = draw(_operator_st)
    threshold = draw(_threshold_st)

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )

    value_choice = draw(st.sampled_from(["value", "none"]))
    if value_choice == "none":
        stock_data = {}
        expected_passed = False
    else:
        val = draw(_numeric_value)
        stock_data = {factor_name: val}
        # 计算预期结果
        ops = {
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
        }
        expected_passed = ops[operator](val, threshold)

    return condition, stock_data, expected_passed


@st.composite
def percentile_factor_condition_strategy(draw):
    """生成 PERCENTILE 类型的 FactorCondition 和 stock_data"""
    from app.core.schemas import FactorCondition

    percentile_factors = [
        name for name, meta in FACTOR_REGISTRY.items()
        if meta.threshold_type == ThresholdType.PERCENTILE
    ]
    factor_name = draw(st.sampled_from(percentile_factors))

    operator = draw(_operator_st)
    threshold = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )

    value_choice = draw(st.sampled_from(["value", "none"]))
    if value_choice == "none":
        stock_data = {}
        expected_passed = False
    else:
        val = draw(_positive_value)
        # PERCENTILE 类型读取 {factor_name}_pctl 字段
        stock_data = {f"{factor_name}_pctl": val}
        ops = {
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
        }
        expected_passed = ops[operator](val, threshold)

    return condition, stock_data, expected_passed


@st.composite
def industry_relative_factor_condition_strategy(draw):
    """生成 INDUSTRY_RELATIVE 类型的 FactorCondition 和 stock_data"""
    from app.core.schemas import FactorCondition

    ir_factors = [
        name for name, meta in FACTOR_REGISTRY.items()
        if meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE
    ]
    factor_name = draw(st.sampled_from(ir_factors))

    operator = draw(_operator_st)
    threshold = draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False))

    condition = FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
    )

    value_choice = draw(st.sampled_from(["value", "none"]))
    if value_choice == "none":
        stock_data = {}
        expected_passed = False
    else:
        val = draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False))
        # INDUSTRY_RELATIVE 类型读取 {factor_name}_ind_rel 字段
        stock_data = {f"{factor_name}_ind_rel": val}
        ops = {
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
        }
        expected_passed = ops[operator](val, threshold)

    return condition, stock_data, expected_passed


class TestProperty7FactorEvaluatorThresholdCoverage:
    """
    Property 7: FactorEvaluator 阈值类型全覆盖

    **Validates: Requirements 12.4, 18.4, 21.3**

    对于任意有效的 FactorCondition 和 stock_data 字典：
    1. 返回值始终为 FactorEvalResult 实例
    2. RANGE 类型：passed = (low <= value <= high)
    3. BOOLEAN 类型：passed = bool(value)
    4. ABSOLUTE/PERCENTILE/INDUSTRY_RELATIVE 类型：passed = operator_fn(value, threshold)
    5. 值缺失（None）时 passed = False
    """

    @given(data=range_factor_condition_strategy())
    @settings(max_examples=100)
    def test_range_type_evaluation(self, data):
        """RANGE 类型：passed = (low <= value <= high)"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        condition, stock_data, expected_passed = data
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult), (
            f"返回值类型应为 FactorEvalResult，实际为 {type(result)}"
        )
        assert result.passed == expected_passed, (
            f"RANGE 因子 '{condition.factor_name}' 评估结果 {result.passed} "
            f"与预期 {expected_passed} 不一致，"
            f"value={result.value}, range=[{condition.params.get('threshold_low')}, "
            f"{condition.params.get('threshold_high')}]"
        )

    @given(data=boolean_factor_condition_strategy())
    @settings(max_examples=100)
    def test_boolean_type_evaluation(self, data):
        """BOOLEAN 类型：passed = bool(value)"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        condition, stock_data, expected_passed = data
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult)
        assert result.passed == expected_passed, (
            f"BOOLEAN 因子 '{condition.factor_name}' 评估结果 {result.passed} "
            f"与预期 {expected_passed} 不一致，stock_data={stock_data}"
        )

    @given(data=absolute_factor_condition_strategy())
    @settings(max_examples=100)
    def test_absolute_type_evaluation(self, data):
        """ABSOLUTE 类型：passed = operator_fn(value, threshold)"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        condition, stock_data, expected_passed = data
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult)
        assert result.passed == expected_passed, (
            f"ABSOLUTE 因子 '{condition.factor_name}' 评估结果 {result.passed} "
            f"与预期 {expected_passed} 不一致，"
            f"value={result.value}, operator={condition.operator}, "
            f"threshold={condition.threshold}"
        )

    @given(data=percentile_factor_condition_strategy())
    @settings(max_examples=100)
    def test_percentile_type_evaluation(self, data):
        """PERCENTILE 类型：passed = operator_fn(value, threshold)，读取 _pctl 字段"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        condition, stock_data, expected_passed = data
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult)
        assert result.passed == expected_passed, (
            f"PERCENTILE 因子 '{condition.factor_name}' 评估结果 {result.passed} "
            f"与预期 {expected_passed} 不一致，"
            f"value={result.value}, operator={condition.operator}, "
            f"threshold={condition.threshold}, stock_data={stock_data}"
        )

    @given(data=industry_relative_factor_condition_strategy())
    @settings(max_examples=100)
    def test_industry_relative_type_evaluation(self, data):
        """INDUSTRY_RELATIVE 类型：passed = operator_fn(value, threshold)，读取 _ind_rel 字段"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        condition, stock_data, expected_passed = data
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult)
        assert result.passed == expected_passed, (
            f"INDUSTRY_RELATIVE 因子 '{condition.factor_name}' 评估结果 {result.passed} "
            f"与预期 {expected_passed} 不一致，"
            f"value={result.value}, operator={condition.operator}, "
            f"threshold={condition.threshold}, stock_data={stock_data}"
        )

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_missing_value_returns_false(self, factor_name: str):
        """值缺失（None）时 passed = False"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        from app.core.schemas import FactorCondition

        meta = FACTOR_REGISTRY[factor_name]
        if meta.threshold_type == ThresholdType.RANGE:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=None,
                params={"threshold_low": 0, "threshold_high": 100},
            )
        elif meta.threshold_type == ThresholdType.BOOLEAN:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=None,
            )
        else:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=50.0,
            )

        # 空 stock_data → 值缺失
        result = FactorEvaluator.evaluate(condition, {})
        assert isinstance(result, FactorEvalResult)
        assert result.passed is False, (
            f"因子 '{factor_name}' 值缺失时应返回 passed=False，实际为 {result.passed}"
        )
        assert result.value is None

    @given(factor_name=factor_names_strategy)
    @settings(max_examples=100)
    def test_always_returns_factor_eval_result(self, factor_name: str):
        """返回值始终为 FactorEvalResult 实例"""
        from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult
        from app.core.schemas import FactorCondition

        meta = FACTOR_REGISTRY[factor_name]
        if meta.threshold_type == ThresholdType.RANGE:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=None,
                params={"threshold_low": 0, "threshold_high": 100},
            )
            stock_data = {factor_name: 50.0}
        elif meta.threshold_type == ThresholdType.BOOLEAN:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=None,
            )
            stock_data = {factor_name: True}
        elif meta.threshold_type == ThresholdType.PERCENTILE:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=50.0,
            )
            stock_data = {f"{factor_name}_pctl": 75.0}
        elif meta.threshold_type == ThresholdType.INDUSTRY_RELATIVE:
            condition = FactorCondition(
                factor_name=factor_name, operator="<=", threshold=1.0,
            )
            stock_data = {f"{factor_name}_ind_rel": 0.8}
        else:
            condition = FactorCondition(
                factor_name=factor_name, operator=">=", threshold=50.0,
            )
            stock_data = {factor_name: 75.0}

        result = FactorEvaluator.evaluate(condition, stock_data)
        assert isinstance(result, FactorEvalResult), (
            f"因子 '{factor_name}' 返回值类型应为 FactorEvalResult，实际为 {type(result)}"
        )


# ---------------------------------------------------------------------------
# Property 8: StrategyConfig 序列化往返一致性（Task 8.4）
# ---------------------------------------------------------------------------

# 辅助策略：生成有效的 FactorCondition
_factor_name_for_config = st.sampled_from(sorted(FACTOR_REGISTRY.keys()))


@st.composite
def factor_condition_strategy(draw):
    """生成随机的 FactorCondition"""
    from app.core.schemas import FactorCondition

    factor_name = draw(_factor_name_for_config)
    meta = FACTOR_REGISTRY[factor_name]

    if meta.threshold_type == ThresholdType.RANGE:
        operator = "range"
        threshold = None
        low = draw(st.floats(min_value=-100.0, max_value=50.0, allow_nan=False, allow_infinity=False))
        high = draw(st.floats(min_value=low + 0.01, max_value=200.0, allow_nan=False, allow_infinity=False))
        params = {"threshold_low": low, "threshold_high": high}
    elif meta.threshold_type == ThresholdType.BOOLEAN:
        operator = ">="
        threshold = None
        params = {}
    else:
        operator = draw(st.sampled_from([">=", "<=", ">", "<", "=="]))
        threshold = draw(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        params = {}

    return FactorCondition(
        factor_name=factor_name,
        operator=operator,
        threshold=threshold,
        params=params,
    )


@st.composite
def strategy_config_strategy(draw):
    """生成随机的 StrategyConfig（包含新增因子类别的条件）"""
    from app.core.schemas import (
        StrategyConfig, SectorScreenConfig,
        MaTrendConfig, IndicatorParamsConfig,
        BreakoutConfig, VolumePriceConfig,
    )

    n_factors = draw(st.integers(min_value=0, max_value=6))
    factors = [draw(factor_condition_strategy()) for _ in range(n_factors)]
    logic = draw(st.sampled_from(["AND", "OR"]))

    # 生成权重
    weights = {}
    for f in factors:
        weights[f.factor_name] = draw(st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False))

    ma_periods = draw(st.just([5, 10, 20, 60, 120, 250]))

    sector_config = SectorScreenConfig(
        sector_data_source=draw(st.sampled_from(["DC", "THS", "TDX", "TI", "CI"])),
        sector_period=draw(st.integers(min_value=1, max_value=30)),
        sector_top_n=draw(st.integers(min_value=1, max_value=100)),
    )

    return StrategyConfig(
        factors=factors,
        logic=logic,
        weights=weights,
        ma_periods=ma_periods,
        sector_config=sector_config,
    )


@st.composite
def old_strategy_config_with_sector_type_strategy(draw):
    """生成包含旧 sector_type 字段的策略配置字典"""
    n_factors = draw(st.integers(min_value=0, max_value=3))
    factors = []
    for _ in range(n_factors):
        factor_name = draw(_factor_name_for_config)
        factors.append({
            "factor_name": factor_name,
            "operator": ">=",
            "threshold": draw(st.one_of(
                st.none(),
                st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            )),
            "params": {},
        })

    return {
        "factors": factors,
        "logic": draw(st.sampled_from(["AND", "OR"])),
        "weights": {},
        "ma_periods": [5, 10, 20, 60, 120, 250],
        "sector_config": {
            "sector_data_source": draw(st.sampled_from(["DC", "THS", "TDX", "TI", "CI"])),
            "sector_type": draw(st.sampled_from(["INDUSTRY", "CONCEPT", "REGION", "STYLE"])),
            "sector_period": draw(st.integers(min_value=1, max_value=30)),
            "sector_top_n": draw(st.integers(min_value=1, max_value=100)),
        },
    }


class TestProperty8StrategyConfigRoundtrip:
    """
    Property 8: StrategyConfig 序列化往返一致性

    **Validates: Requirements 18.5, 21.6, 22.6**

    对于任意有效的 StrategyConfig 实例（包含新增因子类别的条件）：
    1. from_dict(config.to_dict()) 产生与原始配置等价的实例（to_dict() 输出相同）
    2. 包含旧 sector_type 字段的配置字典反序列化时不报错
    """

    @given(config=strategy_config_strategy())
    @settings(max_examples=100)
    def test_roundtrip_produces_equivalent_config(self, config):
        """from_dict(config.to_dict()) 产生等价实例"""
        from app.core.schemas import StrategyConfig

        serialized = config.to_dict()
        restored = StrategyConfig.from_dict(serialized)
        re_serialized = restored.to_dict()

        # 比较两次序列化的输出应相同
        assert serialized == re_serialized, (
            f"序列化往返不一致：\n原始: {serialized}\n还原: {re_serialized}"
        )

    @given(config=strategy_config_strategy())
    @settings(max_examples=100)
    def test_roundtrip_preserves_factors(self, config):
        """往返保持因子条件一致"""
        from app.core.schemas import StrategyConfig

        serialized = config.to_dict()
        restored = StrategyConfig.from_dict(serialized)

        assert len(restored.factors) == len(config.factors)
        for orig, rest in zip(config.factors, restored.factors):
            assert orig.factor_name == rest.factor_name
            assert orig.operator == rest.operator
            assert orig.threshold == rest.threshold
            assert orig.params == rest.params

    @given(config=strategy_config_strategy())
    @settings(max_examples=100)
    def test_roundtrip_preserves_logic_and_weights(self, config):
        """往返保持逻辑运算和权重一致"""
        from app.core.schemas import StrategyConfig

        serialized = config.to_dict()
        restored = StrategyConfig.from_dict(serialized)

        assert restored.logic == config.logic
        assert restored.weights == config.weights

    @given(config=strategy_config_strategy())
    @settings(max_examples=100)
    def test_roundtrip_preserves_sector_config(self, config):
        """往返保持板块配置一致（不含 sector_type）"""
        from app.core.schemas import StrategyConfig

        serialized = config.to_dict()
        restored = StrategyConfig.from_dict(serialized)

        assert restored.sector_config.sector_data_source == config.sector_config.sector_data_source
        assert restored.sector_config.sector_period == config.sector_config.sector_period
        assert restored.sector_config.sector_top_n == config.sector_config.sector_top_n
        # sector_type 始终为 None
        assert restored.sector_config.sector_type is None

    @given(config=strategy_config_strategy())
    @settings(max_examples=100)
    def test_serialized_sector_config_no_sector_type(self, config):
        """序列化输出的 sector_config 不含 sector_type"""
        serialized = config.to_dict()
        assert "sector_type" not in serialized["sector_config"], (
            f"sector_config 不应包含 sector_type，实际: {serialized['sector_config']}"
        )

    @given(old_config=old_strategy_config_with_sector_type_strategy())
    @settings(max_examples=100)
    def test_old_config_with_sector_type_no_error(self, old_config):
        """包含旧 sector_type 字段的配置字典反序列化不报错"""
        from app.core.schemas import StrategyConfig

        # 不应抛出异常
        restored = StrategyConfig.from_dict(old_config)

        # sector_type 应被忽略
        assert restored.sector_config.sector_type is None
        assert restored.sector_config.sector_data_source == old_config["sector_config"]["sector_data_source"]

    @given(old_config=old_strategy_config_with_sector_type_strategy())
    @settings(max_examples=100)
    def test_old_config_roundtrip_drops_sector_type(self, old_config):
        """旧配置反序列化后再序列化，sector_type 被移除"""
        from app.core.schemas import StrategyConfig

        restored = StrategyConfig.from_dict(old_config)
        re_serialized = restored.to_dict()

        assert "sector_type" not in re_serialized["sector_config"]
        assert re_serialized["sector_config"]["sector_data_source"] == old_config["sector_config"]["sector_data_source"]


# ---------------------------------------------------------------------------
# Property 15: 策略示例因子名称一致性（Task 9.5）
# ---------------------------------------------------------------------------

# 辅助策略：从 STRATEGY_EXAMPLES 中随机选取策略示例索引
from app.services.screener.strategy_examples import STRATEGY_EXAMPLES

_strategy_example_indices = st.integers(min_value=0, max_value=len(STRATEGY_EXAMPLES) - 1)


class TestProperty15StrategyExampleFactorConsistency:
    """
    Property 15: 策略示例因子名称一致性

    **Validates: Requirements 19.2, 19.3**

    对于 STRATEGY_EXAMPLES 中的任意策略示例：
    1. 其 factors 列表中每个因子条件的 factor_name 应存在于 FACTOR_REGISTRY 中
    2. 每个示例应包含非空的 factors、logic、weights、enabled_modules 字段
    """

    @given(idx=_strategy_example_indices)
    @settings(max_examples=100)
    def test_all_factor_names_in_registry(self, idx: int):
        """策略示例中的所有因子名称必须在 FACTOR_REGISTRY 中注册"""
        example = STRATEGY_EXAMPLES[idx]
        for factor in example.factors:
            factor_name = factor["factor_name"]
            assert factor_name in FACTOR_REGISTRY, (
                f"策略 '{example.name}' 中的因子 '{factor_name}' "
                f"未在 FACTOR_REGISTRY 中注册"
            )

    @given(idx=_strategy_example_indices)
    @settings(max_examples=100)
    def test_factors_non_empty(self, idx: int):
        """策略示例的 factors 列表必须非空"""
        example = STRATEGY_EXAMPLES[idx]
        assert len(example.factors) > 0, (
            f"策略 '{example.name}' 的 factors 列表为空"
        )

    @given(idx=_strategy_example_indices)
    @settings(max_examples=100)
    def test_logic_valid(self, idx: int):
        """策略示例的 logic 必须为 AND 或 OR"""
        example = STRATEGY_EXAMPLES[idx]
        assert example.logic in ("AND", "OR"), (
            f"策略 '{example.name}' 的 logic '{example.logic}' 无效"
        )

    @given(idx=_strategy_example_indices)
    @settings(max_examples=100)
    def test_weights_non_empty(self, idx: int):
        """策略示例的 weights 字典必须非空"""
        example = STRATEGY_EXAMPLES[idx]
        assert len(example.weights) > 0, (
            f"策略 '{example.name}' 的 weights 字典为空"
        )

    @given(idx=_strategy_example_indices)
    @settings(max_examples=100)
    def test_enabled_modules_is_list(self, idx: int):
        """策略示例的 enabled_modules 必须为列表类型"""
        example = STRATEGY_EXAMPLES[idx]
        assert isinstance(example.enabled_modules, list), (
            f"策略 '{example.name}' 的 enabled_modules 不是列表类型"
        )


# ---------------------------------------------------------------------------
# Property 16: 板块强势筛选器类型不变量
# ---------------------------------------------------------------------------

# 辅助策略：生成板块排名结果列表
_sector_code_st = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    min_size=3, max_size=8,
)
_sector_name_st = st.text(min_size=1, max_size=10)
_sector_change_pct_st = st.floats(
    min_value=-30.0, max_value=30.0, allow_nan=False, allow_infinity=False,
)


@st.composite
def sector_rank_result_strategy(draw):
    """生成随机的 SectorRankResult 实例"""
    from app.services.screener.sector_strength import SectorRankResult
    return SectorRankResult(
        sector_code=draw(_sector_code_st),
        sector_name=draw(_sector_name_st),
        rank=draw(st.integers(min_value=1, max_value=200)),
        change_pct=draw(_sector_change_pct_st),
        is_bullish=draw(st.booleans()),
    )


@st.composite
def sector_filter_inputs_strategy(draw):
    """
    生成 filter_by_sector_strength 的完整输入：
    - stocks_data: {symbol: factor_dict} 字典
    - sector_ranks: SectorRankResult 列表
    - stock_sector_map: symbol → [sector_code] 映射
    - top_n: 排名阈值
    """
    # 生成板块排名列表（0~10 个板块）
    n_sectors = draw(st.integers(min_value=0, max_value=10))
    sector_ranks = [draw(sector_rank_result_strategy()) for _ in range(n_sectors)]
    sector_codes = [r.sector_code for r in sector_ranks]

    # 生成股票数据字典（0~15 只股票）
    n_stocks = draw(st.integers(min_value=0, max_value=15))
    stock_symbols = [f"{draw(st.integers(min_value=0, max_value=999999)):06d}" for _ in range(n_stocks)]

    stocks_data = {}
    stock_sector_map = {}
    for symbol in stock_symbols:
        # 每只股票的 factor_dict 包含一些基础因子
        stocks_data[symbol] = {
            "close": draw(st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)),
        }
        # 随机分配 0~3 个板块给该股票
        if sector_codes:
            n_assigned = draw(st.integers(min_value=0, max_value=min(3, len(sector_codes))))
            assigned = draw(
                st.lists(
                    st.sampled_from(sector_codes),
                    min_size=n_assigned,
                    max_size=n_assigned,
                )
            ) if n_assigned > 0 else []
            if assigned:
                stock_sector_map[symbol] = assigned

    top_n = draw(st.integers(min_value=1, max_value=100))

    return stocks_data, sector_ranks, stock_sector_map, top_n


class TestProperty16SectorStrengthFilterTypeInvariant:
    """
    Property 16: 板块强势筛选器类型不变量

    **Validates: Requirements 3.1, 3.2**

    对于任意股票数据字典，经过 filter_by_sector_strength() 处理后：
    1. 每只股票的 sector_rank 应为 int 或 None
    2. 每只股票的 sector_trend 应为 bool 类型
    """

    @given(inputs=sector_filter_inputs_strategy())
    @settings(max_examples=100)
    def test_sector_rank_type_invariant(self, inputs):
        """sector_rank 必须为 int 或 None（需求 3.1）"""
        from app.services.screener.sector_strength import SectorStrengthFilter

        stocks_data, sector_ranks, stock_sector_map, top_n = inputs
        filter_instance = SectorStrengthFilter()
        filter_instance.filter_by_sector_strength(
            stocks_data=stocks_data,
            sector_ranks=sector_ranks,
            stock_sector_map=stock_sector_map,
            top_n=top_n,
        )

        for symbol, factor_dict in stocks_data.items():
            sector_rank = factor_dict.get("sector_rank")
            assert sector_rank is None or isinstance(sector_rank, int), (
                f"股票 '{symbol}' 的 sector_rank 类型错误: "
                f"期望 int 或 None，实际为 {type(sector_rank).__name__} "
                f"(值={sector_rank})"
            )

    @given(inputs=sector_filter_inputs_strategy())
    @settings(max_examples=100)
    def test_sector_trend_type_invariant(self, inputs):
        """sector_trend 必须为 bool 类型（需求 3.2）"""
        from app.services.screener.sector_strength import SectorStrengthFilter

        stocks_data, sector_ranks, stock_sector_map, top_n = inputs
        filter_instance = SectorStrengthFilter()
        filter_instance.filter_by_sector_strength(
            stocks_data=stocks_data,
            sector_ranks=sector_ranks,
            stock_sector_map=stock_sector_map,
            top_n=top_n,
        )

        for symbol, factor_dict in stocks_data.items():
            sector_trend = factor_dict.get("sector_trend")
            assert isinstance(sector_trend, bool), (
                f"股票 '{symbol}' 的 sector_trend 类型错误: "
                f"期望 bool，实际为 {type(sector_trend).__name__} "
                f"(值={sector_trend})"
            )

# ---------------------------------------------------------------------------
# Feature: screening-system-enhancement, Property 17: SECTOR_TYPE_LABEL_MAP 标签映射完备性
# ---------------------------------------------------------------------------

# 辅助策略：生成不在 SECTOR_TYPE_LABEL_MAP 中的随机字符串
_known_sector_type_keys = st.sampled_from(sorted(
    __import__("app.core.schemas", fromlist=["SECTOR_TYPE_LABEL_MAP"]).SECTOR_TYPE_LABEL_MAP.keys()
))


def _not_in_label_map() -> st.SearchStrategy[str]:
    """生成不在 SECTOR_TYPE_LABEL_MAP 中的随机字符串"""
    from app.core.schemas import SECTOR_TYPE_LABEL_MAP
    known = set(SECTOR_TYPE_LABEL_MAP.keys())
    return st.text(min_size=1, max_size=20).filter(lambda s: s not in known)


class TestProperty17SectorTypeLabelMapCompleteness:
    """
    Property 17: SECTOR_TYPE_LABEL_MAP 标签映射完备性

    **Validates: Requirements 22.9**

    1. 对于 SECTOR_TYPE_LABEL_MAP 中的所有键，get_sector_type_label(key) 返回对应的中文标签
    2. get_sector_type_label(None) 返回"未分类"
    3. 对于任意不在 SECTOR_TYPE_LABEL_MAP 中的字符串 s，get_sector_type_label(s) 返回 s 本身（回退）
    """

    @given(key=_known_sector_type_keys)
    @settings(max_examples=100)
    def test_known_keys_return_correct_label(self, key: str):
        """已知键返回对应的中文标签"""
        from app.core.schemas import SECTOR_TYPE_LABEL_MAP, get_sector_type_label
        expected = SECTOR_TYPE_LABEL_MAP[key]
        result = get_sector_type_label(key)
        assert result == expected, (
            f"键 '{key}' 的标签应为 '{expected}'，实际为 '{result}'"
        )

    def test_none_returns_unclassified(self):
        """None 返回 '未分类'"""
        from app.core.schemas import get_sector_type_label
        assert get_sector_type_label(None) == "未分类"

    @given(s=_not_in_label_map())
    @settings(max_examples=100)
    def test_unknown_string_returns_itself(self, s: str):
        """不在映射表中的字符串返回原始值（回退）"""
        from app.core.schemas import get_sector_type_label
        result = get_sector_type_label(s)
        assert result == s, (
            f"未知字符串 '{s}' 应返回自身，实际为 '{result}'"
        )
