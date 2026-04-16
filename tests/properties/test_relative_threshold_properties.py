# Feature: relative-exit-thresholds, Property 1: ExitCondition round-trip
"""
ExitCondition 序列化往返一致性属性测试（含相对值阈值字段）

**Validates: Requirements 1.6, 1.7, 1.9**

对任意合法的 ExitCondition 对象（包含 threshold_mode="absolute" 和
threshold_mode="relative" 两种模式），调用 to_dict() 序列化为字典后再调用
from_dict() 反序列化，所得对象应与原对象在所有字段上等价。
新增的 threshold_mode、base_field、factor 字段在往返后应完全保留。
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.schemas import (
    VALID_BASE_FIELDS,
    VALID_FREQS,
    VALID_INDICATORS,
    VALID_OPERATORS,
    ExitCondition,
)

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_INDICATORS = sorted(VALID_INDICATORS)
_OPERATORS = sorted(VALID_OPERATORS)
_NUMERIC_OPERATORS = sorted(VALID_OPERATORS - {"cross_up", "cross_down"})
_CROSS_OPERATORS = ["cross_up", "cross_down"]
_BASE_FIELDS = sorted(VALID_BASE_FIELDS)
_FREQS = sorted(VALID_FREQS)

# 数据源频率
_freq_strategy = st.sampled_from(_FREQS)

# 指标名称
_indicator_strategy = st.sampled_from(_INDICATORS)

# 数值阈值（合理范围的浮点数）
_threshold_strategy = st.floats(
    min_value=-1e6, max_value=1e6,
    allow_nan=False, allow_infinity=False,
)

# 正数 factor（相对值模式使用）
_factor_strategy = st.floats(
    min_value=0.001, max_value=1e4,
    allow_nan=False, allow_infinity=False,
)

# 基准字段
_base_field_strategy = st.sampled_from(_BASE_FIELDS)

# 指标参数字典
_params_strategy = st.one_of(
    st.just({}),
    st.fixed_dictionaries({"period": st.integers(min_value=1, max_value=250)}),
    st.fixed_dictionaries({
        "fast": st.integers(min_value=1, max_value=100),
        "slow": st.integers(min_value=1, max_value=100),
        "signal": st.integers(min_value=1, max_value=100),
    }),
)

# 含 ma_volume_period 的参数字典（用于 ma_volume 基准字段）
_params_with_ma_volume_strategy = st.fixed_dictionaries({
    "ma_volume_period": st.integers(min_value=1, max_value=60),
})


@st.composite
def _exit_condition_strategy(draw: st.DrawFn) -> ExitCondition:
    """生成任意合法的 ExitCondition（包含 absolute 和 relative 两种模式）。"""
    freq = draw(_freq_strategy)
    indicator = draw(_indicator_strategy)
    operator = draw(st.sampled_from(_OPERATORS))
    threshold_mode = draw(st.sampled_from(["absolute", "relative"]))

    if operator in ("cross_up", "cross_down"):
        # 交叉运算符：需要 cross_target，threshold 为 None
        cross_target = draw(_indicator_strategy)
        params = draw(_params_strategy)
        return ExitCondition(
            freq=freq,
            indicator=indicator,
            operator=operator,
            threshold=None,
            cross_target=cross_target,
            params=params,
            threshold_mode=threshold_mode,
            base_field=draw(_base_field_strategy) if threshold_mode == "relative" else None,
            factor=draw(_factor_strategy) if threshold_mode == "relative" else None,
        )
    else:
        # 数值比较运算符
        if threshold_mode == "absolute":
            threshold = draw(_threshold_strategy)
            params = draw(_params_strategy)
            return ExitCondition(
                freq=freq,
                indicator=indicator,
                operator=operator,
                threshold=threshold,
                cross_target=None,
                params=params,
                threshold_mode="absolute",
                base_field=None,
                factor=None,
            )
        else:
            # relative 模式：base_field 和 factor 必须存在，threshold 可为 None
            base_field = draw(_base_field_strategy)
            factor = draw(_factor_strategy)
            # 当 base_field 为 ma_volume 时，params 应包含 ma_volume_period
            if base_field == "ma_volume":
                params = draw(_params_with_ma_volume_strategy)
            else:
                params = draw(_params_strategy)
            return ExitCondition(
                freq=freq,
                indicator=indicator,
                operator=operator,
                threshold=None,
                cross_target=None,
                params=params,
                threshold_mode="relative",
                base_field=base_field,
                factor=factor,
            )


# ---------------------------------------------------------------------------
# Property 1: ExitCondition round-trip serialization with relative threshold fields
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(condition=_exit_condition_strategy())
def test_exit_condition_roundtrip_with_relative_threshold(condition: ExitCondition):
    """
    # Feature: relative-exit-thresholds, Property 1: ExitCondition round-trip

    **Validates: Requirements 1.6, 1.7, 1.9**

    对任意合法的 ExitCondition 对象（包含 threshold_mode="absolute" 和
    threshold_mode="relative" 两种模式），序列化为 dict 再反序列化后，
    所得对象应与原对象在所有字段上等价。
    新增的 threshold_mode、base_field、factor 字段在往返后应完全保留。
    """
    serialized = condition.to_dict()
    restored = ExitCondition.from_dict(serialized)

    # 向后兼容："minute" 经 from_dict 映射为 "1min"
    expected_freq = "1min" if condition.freq == "minute" else condition.freq
    assert restored.freq == expected_freq, (
        f"freq 不一致: {restored.freq!r} != {expected_freq!r}"
    )
    assert restored.indicator == condition.indicator, (
        f"indicator 不一致: {restored.indicator!r} != {condition.indicator!r}"
    )
    assert restored.operator == condition.operator, (
        f"operator 不一致: {restored.operator!r} != {condition.operator!r}"
    )
    assert restored.threshold == condition.threshold, (
        f"threshold 不一致: {restored.threshold!r} != {condition.threshold!r}"
    )
    assert restored.cross_target == condition.cross_target, (
        f"cross_target 不一致: {restored.cross_target!r} != {condition.cross_target!r}"
    )
    assert restored.params == condition.params, (
        f"params 不一致: {restored.params!r} != {condition.params!r}"
    )

    # 验证新增的相对值阈值字段
    assert restored.threshold_mode == condition.threshold_mode, (
        f"threshold_mode 不一致: {restored.threshold_mode!r} != {condition.threshold_mode!r}"
    )
    assert restored.base_field == condition.base_field, (
        f"base_field 不一致: {restored.base_field!r} != {condition.base_field!r}"
    )
    assert restored.factor == condition.factor, (
        f"factor 不一致: {restored.factor!r} != {condition.factor!r}"
    )


# ---------------------------------------------------------------------------
# Property 2: Backward compatibility for missing threshold_mode
# ---------------------------------------------------------------------------

# 旧版 ExitCondition 字典的 Hypothesis 策略（不含 threshold_mode / base_field / factor）

_OLD_STYLE_NUMERIC_OPERATORS = sorted(VALID_OPERATORS - {"cross_up", "cross_down"})
_OLD_STYLE_CROSS_OPERATORS = ["cross_up", "cross_down"]


@st.composite
def _old_style_exit_condition_dict(draw: st.DrawFn) -> dict:
    """
    生成不包含 threshold_mode、base_field、factor 字段的旧版 ExitCondition 字典。

    旧版字典结构：
    - freq: 数据源频率
    - indicator: 指标名称
    - operator: 比较运算符
    - threshold: 数值阈值（数值比较运算符时）
    - cross_target: 交叉目标指标（交叉运算符时）
    - params: 指标参数（可选）
    """
    freq = draw(_freq_strategy)
    indicator = draw(_indicator_strategy)
    is_cross = draw(st.booleans())

    if is_cross:
        operator = draw(st.sampled_from(_OLD_STYLE_CROSS_OPERATORS))
        cross_target = draw(_indicator_strategy)
        d: dict = {
            "freq": freq,
            "indicator": indicator,
            "operator": operator,
            "cross_target": cross_target,
        }
    else:
        operator = draw(st.sampled_from(_OLD_STYLE_NUMERIC_OPERATORS))
        threshold = draw(_threshold_strategy)
        d = {
            "freq": freq,
            "indicator": indicator,
            "operator": operator,
            "threshold": threshold,
        }

    # 可选的 params 字段
    include_params = draw(st.booleans())
    if include_params:
        d["params"] = draw(_params_strategy)

    # 确保不包含新字段
    assert "threshold_mode" not in d
    assert "base_field" not in d
    assert "factor" not in d

    return d


@h_settings(max_examples=100)
@given(old_dict=_old_style_exit_condition_dict())
def test_missing_threshold_mode_backward_compat(old_dict: dict):
    """
    # Feature: relative-exit-thresholds, Property 2: backward compat

    **Validates: Requirements 1.8, 7.4, 8.3**

    对任意不包含 threshold_mode 字段的合法旧版 ExitCondition 字典，
    ExitCondition.from_dict() 应将 threshold_mode 默认设为 "absolute"，
    且 base_field 为 None，factor 为 None。
    """
    restored = ExitCondition.from_dict(old_dict)

    # threshold_mode 缺失时默认为 "absolute"
    assert restored.threshold_mode == "absolute", (
        f"threshold_mode 应为 'absolute'，实际为 {restored.threshold_mode!r}"
    )

    # base_field 应为 None
    assert restored.base_field is None, (
        f"base_field 应为 None，实际为 {restored.base_field!r}"
    )

    # factor 应为 None
    assert restored.factor is None, (
        f"factor 应为 None，实际为 {restored.factor!r}"
    )

    # 验证原有字段正确还原
    expected_freq = "1min" if old_dict["freq"] == "minute" else old_dict["freq"]
    assert restored.freq == expected_freq
    assert restored.indicator == old_dict["indicator"]
    assert restored.operator == old_dict["operator"]
    assert restored.threshold == old_dict.get("threshold")
    assert restored.cross_target == old_dict.get("cross_target")
    assert restored.params == old_dict.get("params", {})


# ---------------------------------------------------------------------------
# Imports for Property 3–6 (ThresholdResolver + IndicatorCache)
# ---------------------------------------------------------------------------

from decimal import Decimal
from statistics import mean

from app.core.schemas import HoldingContext
from app.services.backtest_engine import IndicatorCache
from app.services.threshold_resolver import resolve_threshold


# ---------------------------------------------------------------------------
# Hypothesis 策略：HoldingContext 生成器
# ---------------------------------------------------------------------------

_positive_price = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

@st.composite
def _holding_context_strategy(draw: st.DrawFn) -> HoldingContext:
    """生成任意合法的 HoldingContext。"""
    entry = draw(_positive_price)
    highest = draw(st.floats(min_value=entry, max_value=entry * 10, allow_nan=False, allow_infinity=False))
    lowest = draw(st.floats(min_value=0.01, max_value=entry, allow_nan=False, allow_infinity=False))
    bar_idx = draw(st.integers(min_value=0, max_value=500))
    return HoldingContext(
        entry_price=entry,
        highest_price=highest,
        lowest_price=lowest,
        entry_bar_index=bar_idx,
    )


# ---------------------------------------------------------------------------
# Hypothesis 策略：IndicatorCache 生成器（最小长度可配置）
# ---------------------------------------------------------------------------

@st.composite
def _indicator_cache_strategy(draw: st.DrawFn, min_length: int = 2) -> IndicatorCache:
    """生成合法的 IndicatorCache，序列长度 >= min_length。"""
    n = draw(st.integers(min_value=min_length, max_value=50))
    closes = draw(st.lists(_positive_price, min_size=n, max_size=n))
    highs = draw(st.lists(_positive_price, min_size=n, max_size=n))
    lows = draw(st.lists(_positive_price, min_size=n, max_size=n))
    opens = draw(st.lists(_positive_price, min_size=n, max_size=n))
    volumes = draw(st.lists(st.integers(min_value=1, max_value=10_000_000), min_size=n, max_size=n))
    amounts = [Decimal(0)] * n
    turnovers = [Decimal(0)] * n
    return IndicatorCache(
        closes=closes,
        highs=highs,
        lows=lows,
        opens=opens,
        volumes=volumes,
        amounts=amounts,
        turnovers=turnovers,
    )


# ---------------------------------------------------------------------------
# Hypothesis 策略：absolute 模式 ExitCondition（数值比较运算符）
# ---------------------------------------------------------------------------

@st.composite
def _absolute_exit_condition_strategy(draw: st.DrawFn) -> ExitCondition:
    """生成 threshold_mode='absolute' 的数值比较 ExitCondition。"""
    return ExitCondition(
        freq=draw(_freq_strategy),
        indicator=draw(_indicator_strategy),
        operator=draw(st.sampled_from(_NUMERIC_OPERATORS)),
        threshold=draw(_threshold_strategy),
        cross_target=None,
        params=draw(_params_strategy),
        threshold_mode="absolute",
        base_field=None,
        factor=None,
    )


# ---------------------------------------------------------------------------
# Property 3: Absolute mode backward compatibility
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    condition=_absolute_exit_condition_strategy(),
    has_ctx=st.booleans(),
    ctx=_holding_context_strategy(),
)
def test_absolute_mode_backward_compat(
    condition: ExitCondition,
    has_ctx: bool,
    ctx: HoldingContext,
):
    """
    # Feature: relative-exit-thresholds, Property 3: absolute mode compat

    **Validates: Requirements 1.2, 3.2, 4.4**

    对任意 threshold_mode="absolute" 的 ExitCondition 和任意 holding_context
    （包括 None），ThresholdResolver 应直接返回 condition.threshold。
    """
    holding_context = ctx if has_ctx else None

    # 构建一个最小的 IndicatorCache（resolve_threshold 在 absolute 模式下不使用它）
    ic = IndicatorCache(
        closes=[1.0, 2.0],
        highs=[1.0, 2.0],
        lows=[1.0, 2.0],
        opens=[1.0, 2.0],
        volumes=[100, 200],
        amounts=[Decimal(0), Decimal(0)],
        turnovers=[Decimal(0), Decimal(0)],
    )

    result = resolve_threshold(condition, holding_context, ic, bar_index=1)
    assert result == condition.threshold, (
        f"absolute 模式应直接返回 condition.threshold={condition.threshold!r}，"
        f"实际返回 {result!r}"
    )


# ---------------------------------------------------------------------------
# Property 4: HoldingContext base field resolution
# ---------------------------------------------------------------------------

_HOLDING_BASE_FIELDS = ["entry_price", "highest_price", "lowest_price"]


@h_settings(max_examples=100)
@given(
    ctx=_holding_context_strategy(),
    base_field=st.sampled_from(_HOLDING_BASE_FIELDS),
    factor=_factor_strategy,
)
def test_holding_context_base_field_resolution(
    ctx: HoldingContext,
    base_field: str,
    factor: float,
):
    """
    # Feature: relative-exit-thresholds, Property 4: HoldingContext resolution

    **Validates: Requirements 3.3, 3.4, 3.5**

    对任意合法 HoldingContext 和正数 factor，当 base_field 为
    entry_price/highest_price/lowest_price 时，ThresholdResolver 应返回
    getattr(ctx, base_field) * factor。
    """
    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator="<",
        threshold=None,
        threshold_mode="relative",
        base_field=base_field,
        factor=factor,
    )

    # 最小 IndicatorCache（HoldingContext 字段不需要它）
    ic = IndicatorCache(
        closes=[1.0, 2.0],
        highs=[1.0, 2.0],
        lows=[1.0, 2.0],
        opens=[1.0, 2.0],
        volumes=[100, 200],
        amounts=[Decimal(0), Decimal(0)],
        turnovers=[Decimal(0), Decimal(0)],
    )

    result = resolve_threshold(condition, ctx, ic, bar_index=1)
    expected = getattr(ctx, base_field) * factor

    assert result is not None, (
        f"resolve_threshold 不应返回 None（base_field={base_field!r}, factor={factor}）"
    )
    assert abs(result - expected) < 1e-6, (
        f"期望 {expected}，实际 {result}（base_field={base_field!r}, "
        f"ctx.{base_field}={getattr(ctx, base_field)}, factor={factor}）"
    )


# ---------------------------------------------------------------------------
# Property 5: IndicatorCache base field resolution
# ---------------------------------------------------------------------------

_IC_BASE_FIELDS_MAP = {
    "prev_close": ("closes", -1),
    "prev_high": ("highs", -1),
    "prev_low": ("lows", -1),
    "today_open": ("opens", 0),
    "prev_bar_open": ("opens", -1),
    "prev_bar_high": ("highs", -1),
    "prev_bar_low": ("lows", -1),
    "prev_bar_close": ("closes", -1),
}


@h_settings(max_examples=100)
@given(
    ic=_indicator_cache_strategy(min_length=2),
    base_field=st.sampled_from(sorted(_IC_BASE_FIELDS_MAP.keys())),
    factor=_factor_strategy,
)
def test_indicator_cache_base_field_resolution(
    ic: IndicatorCache,
    base_field: str,
    factor: float,
):
    """
    # Feature: relative-exit-thresholds, Property 5: IndicatorCache resolution

    **Validates: Requirements 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13**

    对任意合法 IndicatorCache（序列长度 >= 2）、合法 bar_index（>= 1）和正数 factor，
    验证 prev_close/prev_high/prev_low/today_open/prev_bar_open/prev_bar_high/
    prev_bar_low/prev_bar_close 返回正确索引处的值乘以 factor。
    """
    series_len = len(ic.closes)
    # bar_index 必须 >= 1 且 < series_len
    bar_index = series_len - 1  # 使用最后一个有效索引

    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator="<",
        threshold=None,
        threshold_mode="relative",
        base_field=base_field,
        factor=factor,
    )

    result = resolve_threshold(condition, None, ic, bar_index)

    # 计算期望值
    series_name, offset = _IC_BASE_FIELDS_MAP[base_field]
    series = getattr(ic, series_name)
    if offset == -1:
        expected_value = series[bar_index - 1]
    else:
        expected_value = series[bar_index]
    expected = expected_value * factor

    assert result is not None, (
        f"resolve_threshold 不应返回 None（base_field={base_field!r}, "
        f"bar_index={bar_index}, series_len={series_len}）"
    )
    assert abs(result - expected) < 1e-6, (
        f"期望 {expected}，实际 {result}（base_field={base_field!r}, "
        f"base_value={expected_value}, factor={factor}）"
    )


# ---------------------------------------------------------------------------
# Property 6: ma_volume base field resolution
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(data=st.data())
def test_ma_volume_base_field_resolution(data: st.DataObject):
    """
    # Feature: relative-exit-thresholds, Property 6: ma_volume resolution

    **Validates: Requirements 3.14**

    对任意合法 IndicatorCache（volumes 长度 >= N）、合法 bar_index（>= N-1）、
    正整数 N（ma_volume_period）和正数 factor，验证返回
    mean(volumes[bar_index-N+1:bar_index+1]) × factor。
    """
    # 先生成 N（ma_volume_period），再生成足够长的 volumes
    n_period = data.draw(st.integers(min_value=1, max_value=30), label="ma_volume_period")
    total_len = data.draw(
        st.integers(min_value=n_period, max_value=n_period + 30),
        label="total_len",
    )
    volumes = data.draw(
        st.lists(
            st.integers(min_value=1, max_value=10_000_000),
            min_size=total_len,
            max_size=total_len,
        ),
        label="volumes",
    )
    # bar_index 必须 >= n_period - 1 且 < total_len
    bar_index = data.draw(
        st.integers(min_value=n_period - 1, max_value=total_len - 1),
        label="bar_index",
    )
    factor = data.draw(_factor_strategy, label="factor")

    # 构建 IndicatorCache（只需 volumes 和最小的其他字段）
    ic = IndicatorCache(
        closes=[1.0] * total_len,
        highs=[1.0] * total_len,
        lows=[1.0] * total_len,
        opens=[1.0] * total_len,
        volumes=volumes,
        amounts=[Decimal(0)] * total_len,
        turnovers=[Decimal(0)] * total_len,
    )

    condition = ExitCondition(
        freq="daily",
        indicator="volume",
        operator=">",
        threshold=None,
        threshold_mode="relative",
        base_field="ma_volume",
        factor=factor,
        params={"ma_volume_period": n_period},
    )

    result = resolve_threshold(condition, None, ic, bar_index)

    # 计算期望值
    window = volumes[bar_index - n_period + 1 : bar_index + 1]
    expected = mean(window) * factor

    assert result is not None, (
        f"resolve_threshold 不应返回 None（bar_index={bar_index}, "
        f"n_period={n_period}, volumes_len={total_len}）"
    )
    assert abs(result - expected) < 1e-6, (
        f"期望 {expected}，实际 {result}（window={window}, factor={factor}）"
    )


# ---------------------------------------------------------------------------
# Imports for Property 7–9 (ExitConditionEvaluator + ExitConditionConfig)
# ---------------------------------------------------------------------------

import operator as op_module

from app.core.schemas import ExitConditionConfig
from app.services.exit_condition_evaluator import ExitConditionEvaluator

# 数值比较运算符 → Python 原生函数映射
_OP_FN_MAP = {
    ">": op_module.gt,
    "<": op_module.lt,
    ">=": op_module.ge,
    "<=": op_module.le,
}


# ---------------------------------------------------------------------------
# Hypothesis 策略：relative 模式 + HoldingContext base_field 的数值比较条件
# （使用 indicator="close" 简化，值来自 ic.closes[bar_index]）
# ---------------------------------------------------------------------------

@st.composite
def _relative_close_condition_with_context(draw: st.DrawFn):
    """
    生成 threshold_mode='relative' 的数值比较条件（indicator=close），
    配合合法的 HoldingContext 和 IndicatorCache。

    仅使用 HoldingContext base_field（entry_price/highest_price/lowest_price），
    避免 prev_* 字段对 bar_index 的额外约束。
    """
    operator = draw(st.sampled_from(_NUMERIC_OPERATORS))
    base_field = draw(st.sampled_from(_HOLDING_BASE_FIELDS))
    factor = draw(_factor_strategy)

    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator=operator,
        threshold=None,
        cross_target=None,
        params={},
        threshold_mode="relative",
        base_field=base_field,
        factor=factor,
    )

    ctx = draw(_holding_context_strategy())
    ic = draw(_indicator_cache_strategy(min_length=2))

    # bar_index: 有效范围 [1, len(ic.closes) - 1]
    bar_index = draw(st.integers(min_value=1, max_value=len(ic.closes) - 1))

    return condition, ctx, ic, bar_index


# ---------------------------------------------------------------------------
# Property 7: Evaluator uses resolved threshold
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(data=_relative_close_condition_with_context())
def test_evaluator_uses_resolved_threshold(data):
    """
    # Feature: relative-exit-thresholds, Property 7: evaluator uses resolved threshold

    **Validates: Requirements 4.2**

    对任意 threshold_mode="relative" 的数值比较条件（indicator=close）、
    合法 HoldingContext 和 IndicatorCache，ExitConditionEvaluator 的评估结果
    应等价于：先用 ThresholdResolver 解析阈值，再用 Python 原生比较。
    """
    condition, ctx, ic, bar_index = data

    # 通过 evaluator 评估
    evaluator = ExitConditionEvaluator()
    config = ExitConditionConfig(logic="OR", conditions=[condition])
    eval_triggered, _ = evaluator.evaluate(
        config, "TEST", bar_index, ic, holding_context=ctx,
    )

    # 手动计算期望结果
    resolved = resolve_threshold(condition, ctx, ic, bar_index)
    indicator_value = ic.closes[bar_index]
    op_fn = _OP_FN_MAP[condition.operator]
    expected_triggered = op_fn(indicator_value, resolved) if resolved is not None else False

    assert eval_triggered == expected_triggered, (
        f"评估器结果 {eval_triggered} != 期望 {expected_triggered}（"
        f"indicator_value={indicator_value}, resolved={resolved}, "
        f"operator={condition.operator!r}, base_field={condition.base_field!r}, "
        f"factor={condition.factor}）"
    )


# ---------------------------------------------------------------------------
# Hypothesis 策略：cross 条件生成器
# ---------------------------------------------------------------------------

@st.composite
def _cross_condition_with_cache(draw: st.DrawFn):
    """
    生成 cross_up/cross_down 条件，配合 IndicatorCache。
    使用 indicator="close", cross_target="close"（自交叉）简化。
    """
    operator = draw(st.sampled_from(_CROSS_OPERATORS))
    threshold_mode = draw(st.sampled_from(["absolute", "relative"]))

    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator=operator,
        threshold=None,
        cross_target="close",
        params={},
        threshold_mode=threshold_mode,
        base_field=draw(_base_field_strategy) if threshold_mode == "relative" else None,
        factor=draw(_factor_strategy) if threshold_mode == "relative" else None,
    )

    ic = draw(_indicator_cache_strategy(min_length=3))
    bar_index = draw(st.integers(min_value=1, max_value=len(ic.closes) - 1))

    return condition, ic, bar_index


# ---------------------------------------------------------------------------
# Property 8: Cross conditions unaffected by relative threshold
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(data=_cross_condition_with_cache())
def test_cross_conditions_unaffected_by_relative_threshold(data):
    """
    # Feature: relative-exit-thresholds, Property 8: cross unaffected

    **Validates: Requirements 4.6**

    对任意 cross_up/cross_down 条件，无论 threshold_mode 设为 "absolute"
    还是 "relative"，ExitConditionEvaluator 的评估结果应完全相同。
    交叉条件仅依赖 cross_target，不使用阈值。
    """
    condition, ic, bar_index = data

    evaluator = ExitConditionEvaluator()

    # 构建 absolute 版本
    abs_condition = ExitCondition(
        freq=condition.freq,
        indicator=condition.indicator,
        operator=condition.operator,
        threshold=None,
        cross_target=condition.cross_target,
        params=condition.params,
        threshold_mode="absolute",
        base_field=None,
        factor=None,
    )

    # 构建 relative 版本
    rel_condition = ExitCondition(
        freq=condition.freq,
        indicator=condition.indicator,
        operator=condition.operator,
        threshold=None,
        cross_target=condition.cross_target,
        params=condition.params,
        threshold_mode="relative",
        base_field="entry_price",
        factor=1.0,
    )

    abs_config = ExitConditionConfig(logic="OR", conditions=[abs_condition])
    rel_config = ExitConditionConfig(logic="OR", conditions=[rel_condition])

    # 提供一个 HoldingContext 以确保 relative 模式有上下文
    ctx = HoldingContext(
        entry_price=10.0,
        highest_price=15.0,
        lowest_price=8.0,
        entry_bar_index=0,
    )

    abs_triggered, abs_reason = evaluator.evaluate(
        abs_config, "TEST", bar_index, ic, holding_context=ctx,
    )
    rel_triggered, rel_reason = evaluator.evaluate(
        rel_config, "TEST", bar_index, ic, holding_context=ctx,
    )

    assert abs_triggered == rel_triggered, (
        f"交叉条件结果不一致: absolute={abs_triggered}, relative={rel_triggered}（"
        f"operator={condition.operator!r}, bar_index={bar_index}）"
    )


# ---------------------------------------------------------------------------
# Property 9: Trigger reason format includes resolution info
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    ctx=_holding_context_strategy(),
    operator=st.sampled_from(_NUMERIC_OPERATORS),
    base_field=st.sampled_from(_HOLDING_BASE_FIELDS),
    factor=_factor_strategy,
)
def test_trigger_reason_format_includes_resolution_info(
    ctx: HoldingContext,
    operator: str,
    base_field: str,
    factor: float,
):
    """
    # Feature: relative-exit-thresholds, Property 9: reason format

    **Validates: Requirements 4.5, 9.1**

    对任意被触发的 threshold_mode="relative" 条件，触发原因字符串应包含
    解析后的实际阈值数值和 `（{base_field}×{factor}）` 格式信息。

    为确保触发，构造一定会触发的条件：
    - ">" / ">=" 运算符：设置 close 值远大于 resolved threshold
    - "<" / "<=" 运算符：设置 close 值远小于 resolved threshold
    """
    # 计算 resolved threshold
    base_value = getattr(ctx, base_field)
    resolved = base_value * factor

    # 构造一定会触发的 close 值
    if operator in (">", ">="):
        close_value = resolved + 1000.0  # 远大于 resolved
    else:
        close_value = max(resolved - 1000.0, 0.001)  # 远小于 resolved（但保持正数）
        # 如果 resolved 太小，close_value 可能不满足 < resolved
        if not (close_value < resolved):
            # 跳过此用例（resolved 太小无法构造触发条件）
            return

    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator=operator,
        threshold=None,
        cross_target=None,
        params={},
        threshold_mode="relative",
        base_field=base_field,
        factor=factor,
    )

    # 构建 IndicatorCache，close 值设为一定触发的值
    ic = IndicatorCache(
        closes=[close_value, close_value],
        highs=[close_value, close_value],
        lows=[close_value, close_value],
        opens=[close_value, close_value],
        volumes=[100, 100],
        amounts=[Decimal(0), Decimal(0)],
        turnovers=[Decimal(0), Decimal(0)],
    )

    evaluator = ExitConditionEvaluator()
    config = ExitConditionConfig(logic="OR", conditions=[condition])
    triggered, reason = evaluator.evaluate(
        config, "TEST", 1, ic, holding_context=ctx,
    )

    assert triggered, (
        f"条件应被触发: close={close_value}, operator={operator!r}, "
        f"resolved={resolved}（base_field={base_field!r}, factor={factor}）"
    )
    assert reason is not None, "触发时 reason 不应为 None"

    # 验证 reason 包含解析后的阈值（4 位小数格式）
    resolved_str = f"{resolved:.4f}"
    assert resolved_str in reason, (
        f"reason 应包含解析后阈值 {resolved_str!r}，实际: {reason!r}"
    )

    # 验证 reason 包含 （{base_field}×{factor}） 格式
    expected_suffix = f"（{base_field}×{factor}）"
    assert expected_suffix in reason, (
        f"reason 应包含 {expected_suffix!r}，实际: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Property 10: Position extrema tracking invariant
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    initial_price=st.decimals(
        min_value="0.01", max_value="10000",
        allow_nan=False, allow_infinity=False,
        places=2,
    ),
    close_prices=st.lists(
        st.decimals(
            min_value="0.01", max_value="10000",
            allow_nan=False, allow_infinity=False,
            places=2,
        ),
        min_size=1,
        max_size=200,
    ),
)
def test_position_extrema_tracking_invariant(
    initial_price: Decimal,
    close_prices: list[Decimal],
):
    """
    # Feature: relative-exit-thresholds, Property 10: extrema tracking

    **Validates: Requirements 2.2**

    对任意初始买入价和任意收盘价序列，模拟 BacktestEngine 的每日更新逻辑后，
    highest_close 应始终等于序列（含初始价）的最大值，
    lowest_close 应始终等于序列（含初始价）的最小值。
    """
    # Initialize (mirrors BacktestEngine._BacktestPosition creation)
    highest_close = initial_price
    lowest_close = initial_price

    # Simulate daily update logic (mirrors _check_sell_conditions)
    for close in close_prices:
        if close > highest_close:
            highest_close = close
        if close < lowest_close:
            lowest_close = close

    # The full price sequence includes the initial buy price
    all_prices = [initial_price] + list(close_prices)

    assert highest_close == max(all_prices), (
        f"highest_close={highest_close} != max(all_prices)={max(all_prices)}，"
        f"initial_price={initial_price}, close_prices={close_prices}"
    )
    assert lowest_close == min(all_prices), (
        f"lowest_close={lowest_close} != min(all_prices)={min(all_prices)}，"
        f"initial_price={initial_price}, close_prices={close_prices}"
    )
