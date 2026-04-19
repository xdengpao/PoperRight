"""
加权求和评分属性测试（Hypothesis）

Property 5: 加权求和评分公式与范围

对应需求 5.1、5.3、5.4

验证 ScreenExecutor._compute_weighted_score() 纯函数满足：
1. 结果等于 Σ(score × weight) / Σ(weight)（仅计入 score > 0 的模块）
2. 结果在 [0, 100] 闭区间内
3. score 为 0 的模块不计入分母
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import DEFAULT_MODULE_WEIGHTS
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 模块名称池（与 DEFAULT_MODULE_WEIGHTS 一致）
_MODULE_NAMES = list(DEFAULT_MODULE_WEIGHTS.keys())

# 模块评分策略：[0, 100] 闭区间
_score_st = st.floats(min_value=0.0, max_value=100.0,
                       allow_nan=False, allow_infinity=False)

# 正权重策略：(0, 10] 区间
_weight_st = st.floats(min_value=0.01, max_value=10.0,
                        allow_nan=False, allow_infinity=False)


@st.composite
def module_scores_strategy(draw):
    """
    生成随机的 module_scores 字典。

    从默认模块名称池中随机选取 0-5 个模块，
    为每个模块生成 [0, 100] 范围内的评分。
    """
    n = draw(st.integers(min_value=0, max_value=len(_MODULE_NAMES)))
    selected = draw(st.lists(
        st.sampled_from(_MODULE_NAMES),
        min_size=n,
        max_size=n,
        unique=True,
    ))
    scores: dict[str, float] = {}
    for name in selected:
        scores[name] = draw(_score_st)
    return scores


@st.composite
def module_scores_with_custom_weights_strategy(draw):
    """
    生成随机的 (module_scores, weights) 对。

    模块名称使用自定义字符串（不限于默认模块），
    权重为正浮点数。
    """
    module_names = [f"mod_{i}" for i in range(5)]
    n = draw(st.integers(min_value=0, max_value=5))
    selected = draw(st.lists(
        st.sampled_from(module_names),
        min_size=n,
        max_size=n,
        unique=True,
    ))

    scores: dict[str, float] = {}
    weights: dict[str, float] = {}
    for name in selected:
        scores[name] = draw(_score_st)
        weights[name] = draw(_weight_st)

    return scores, weights


@st.composite
def nonzero_module_scores_strategy(draw):
    """
    生成至少包含一个 score > 0 的 module_scores 字典。
    用于验证公式计算的精确性。
    """
    n = draw(st.integers(min_value=1, max_value=len(_MODULE_NAMES)))
    selected = draw(st.lists(
        st.sampled_from(_MODULE_NAMES),
        min_size=n,
        max_size=n,
        unique=True,
    ))
    scores: dict[str, float] = {}
    for name in selected:
        # 至少一个 > 0
        scores[name] = draw(st.floats(
            min_value=0.01, max_value=100.0,
            allow_nan=False, allow_infinity=False,
        ))
    return scores


# ---------------------------------------------------------------------------
# Property 5.1: 加权求和公式正确性
# Feature: screening-system-enhancement, Property 5: 加权求和公式
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(data=module_scores_with_custom_weights_strategy())
def test_weighted_score_formula_correctness(data):
    """
    # Feature: screening-system-enhancement, Property 5: 加权求和公式

    **Validates: Requirements 5.1**

    For any module_scores 和 weights（所有评分在 [0, 100]，所有权重 > 0），
    结果等于 Σ(score × weight) / Σ(weight)（仅计入 score > 0 的模块）。
    """
    module_scores, weights = data

    result = ScreenExecutor._compute_weighted_score(module_scores, weights)

    # 手动计算期望值
    numerator = 0.0
    denominator = 0.0
    for module, score in module_scores.items():
        if score <= 0.0:
            continue
        w = weights.get(module, 0.0)
        if w <= 0.0:
            continue
        numerator += score * w
        denominator += w

    if denominator <= 0.0:
        expected = 0.0
    else:
        expected = numerator / denominator
        expected = max(0.0, min(100.0, expected))

    assert math.isclose(result, expected, rel_tol=1e-9, abs_tol=1e-9), (
        f"加权求和结果不正确：期望 {expected}，实际 {result}。"
        f"module_scores={module_scores}, weights={weights}"
    )


# ---------------------------------------------------------------------------
# Property 5.2: 结果在 [0, 100] 闭区间内
# Feature: screening-system-enhancement, Property 5: 结果范围
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(scores=module_scores_strategy())
def test_weighted_score_in_range(scores):
    """
    # Feature: screening-system-enhancement, Property 5: 结果范围

    **Validates: Requirements 5.4**

    For any module_scores（所有评分在 [0, 100]），
    结果在 [0, 100] 闭区间内。
    """
    result = ScreenExecutor._compute_weighted_score(scores)

    assert 0.0 <= result <= 100.0, (
        f"加权求和结果 {result} 超出 [0, 100] 范围。"
        f"module_scores={scores}"
    )


@settings(max_examples=200)
@given(data=module_scores_with_custom_weights_strategy())
def test_weighted_score_in_range_custom_weights(data):
    """
    # Feature: screening-system-enhancement, Property 5: 结果范围（自定义权重）

    **Validates: Requirements 5.4**

    For any module_scores 和 weights（所有评分在 [0, 100]，所有权重 > 0），
    结果在 [0, 100] 闭区间内。
    """
    module_scores, weights = data

    result = ScreenExecutor._compute_weighted_score(module_scores, weights)

    assert 0.0 <= result <= 100.0, (
        f"加权求和结果 {result} 超出 [0, 100] 范围。"
        f"module_scores={module_scores}, weights={weights}"
    )


# ---------------------------------------------------------------------------
# Property 5.3: score=0 的模块不计入分母
# Feature: screening-system-enhancement, Property 5: 零分排除
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(scores=nonzero_module_scores_strategy())
def test_zero_score_excluded_from_denominator(scores):
    """
    # Feature: screening-system-enhancement, Property 5: 零分排除

    **Validates: Requirements 5.3**

    score=0 的模块不计入分母：
    添加一个 score=0 的模块不应改变结果。
    """
    # 计算不含零分模块的结果
    result_without_zero = ScreenExecutor._compute_weighted_score(scores)

    # 添加一个 score=0 的模块
    zero_module = "zero_test_module"
    scores_with_zero = dict(scores)
    scores_with_zero[zero_module] = 0.0

    # 需要确保 zero_module 有权重
    weights = dict(DEFAULT_MODULE_WEIGHTS)
    weights[zero_module] = 0.5  # 给零分模块一个非零权重

    # 用自定义权重重新计算两个版本
    result_without = ScreenExecutor._compute_weighted_score(scores, weights)
    result_with = ScreenExecutor._compute_weighted_score(scores_with_zero, weights)

    assert math.isclose(result_without, result_with, rel_tol=1e-9, abs_tol=1e-9), (
        f"添加 score=0 的模块后结果发生变化："
        f"无零分={result_without}，有零分={result_with}。"
        f"score=0 的模块不应计入分母。"
        f"scores={scores}"
    )


@settings(max_examples=100)
@given(
    score=st.floats(min_value=0.01, max_value=100.0,
                    allow_nan=False, allow_infinity=False),
    module=st.sampled_from(_MODULE_NAMES),
)
def test_single_nonzero_module_equals_its_score(score, module):
    """
    # Feature: screening-system-enhancement, Property 5: 单模块等价

    **Validates: Requirements 5.1**

    当仅有一个 score > 0 的模块时，
    加权求和结果等于该模块的评分（因为 Σ(s×w)/Σ(w) = s）。
    """
    module_scores = {module: score}
    result = ScreenExecutor._compute_weighted_score(module_scores)

    assert math.isclose(result, score, rel_tol=1e-9, abs_tol=1e-9), (
        f"单模块 {module} 评分 {score} 的加权求和结果应为 {score}，"
        f"实际为 {result}"
    )


@settings(max_examples=100)
@given(scores=module_scores_strategy())
def test_empty_scores_returns_zero(scores):
    """
    # Feature: screening-system-enhancement, Property 5: 空输入

    **Validates: Requirements 5.1, 5.3**

    当所有模块评分为 0 或无模块时，结果为 0.0。
    """
    # 将所有评分设为 0
    zero_scores = {k: 0.0 for k in scores}
    result = ScreenExecutor._compute_weighted_score(zero_scores)

    assert result == 0.0, (
        f"所有模块评分为 0 时结果应为 0.0，实际为 {result}"
    )

    # 空字典也应返回 0
    empty_result = ScreenExecutor._compute_weighted_score({})
    assert empty_result == 0.0, (
        f"空 module_scores 时结果应为 0.0，实际为 {empty_result}"
    )
