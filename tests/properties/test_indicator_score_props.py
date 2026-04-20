"""
技术指标评分属性测试（Hypothesis）

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

Property 9: 技术指标差异化权重与共振加分
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 技术指标触发状态生成器：4 个布尔值的固定字典
_triggered_strategy = st.fixed_dictionaries({
    "macd": st.booleans(),
    "rsi": st.booleans(),
    "boll": st.booleans(),
    "dma": st.booleans(),
})

# 差异化权重常量（与实现保持一致）
_WEIGHTS = {"macd": 35.0, "rsi": 25.0, "boll": 20.0, "dma": 20.0}


# ---------------------------------------------------------------------------
# 辅助：独立计算期望评分（参考模型）
# ---------------------------------------------------------------------------

def _reference_indicator_score(triggered: dict[str, bool]) -> float:
    """
    参考模型：独立于被测函数的评分计算。

    base_score = 触发指标权重之和
    resonance_bonus = 0（count < 2）| 10（count == 2）| 20（count >= 3）
    返回 min(base_score + resonance_bonus, 100.0)
    """
    base_score = sum(
        _WEIGHTS[ind] for ind, on in triggered.items() if on
    )
    count = sum(1 for v in triggered.values() if v)
    if count >= 3:
        resonance_bonus = 20.0
    elif count == 2:
        resonance_bonus = 10.0
    else:
        resonance_bonus = 0.0
    return min(base_score + resonance_bonus, 100.0)


# ---------------------------------------------------------------------------
# Property 9: 技术指标差异化权重与共振加分
# Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(triggered=_triggered_strategy)
def test_indicator_score_matches_reference_model(triggered: dict[str, bool]):
    """
    # Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

    对任意指标触发组合，_compute_indicator_score 的返回值应等于
    min(base_score + resonance_bonus, 100)，其中：
    - base_score = 触发指标权重之和（MACD=35, RSI=25, BOLL=20, DMA=20）
    - resonance_bonus = 0（count < 2）| 10（count == 2）| 20（count >= 3）
    """
    actual = ScreenExecutor._compute_indicator_score(triggered)
    expected = _reference_indicator_score(triggered)
    assert actual == expected, (
        f"评分不一致：actual={actual}, expected={expected}, triggered={triggered}"
    )


@settings(max_examples=200)
@given(triggered=_triggered_strategy)
def test_indicator_score_range_0_to_100(triggered: dict[str, bool]):
    """
    # Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分

    **Validates: Requirements 5.4**

    对任意指标触发组合，评分始终在 [0, 100] 闭区间内。
    """
    score = ScreenExecutor._compute_indicator_score(triggered)
    assert 0.0 <= score <= 100.0, (
        f"评分应在 [0, 100]，实际={score}, triggered={triggered}"
    )


@settings(max_examples=200)
@given(triggered=_triggered_strategy)
def test_indicator_score_no_resonance_when_single(triggered: dict[str, bool]):
    """
    # Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分

    **Validates: Requirements 5.5**

    当仅 1 个或 0 个指标触发时，评分应等于 base_score（无共振加分）。
    """
    count = sum(1 for v in triggered.values() if v)
    if count > 1:
        return  # 仅测试 0 或 1 个指标触发的情况

    score = ScreenExecutor._compute_indicator_score(triggered)
    base_score = sum(_WEIGHTS[ind] for ind, on in triggered.items() if on)
    assert score == base_score, (
        f"单指标/无指标时不应有共振加分：score={score}, base_score={base_score}, "
        f"triggered={triggered}"
    )


@settings(max_examples=200)
@given(triggered=_triggered_strategy)
def test_indicator_score_resonance_bonus_correct(triggered: dict[str, bool]):
    """
    # Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分

    **Validates: Requirements 5.2, 5.3**

    共振加分规则验证：
    - 2 个指标触发 → +10
    - 3 个或以上指标触发 → +20
    """
    count = sum(1 for v in triggered.values() if v)
    score = ScreenExecutor._compute_indicator_score(triggered)
    base_score = sum(_WEIGHTS[ind] for ind, on in triggered.items() if on)

    if count == 2:
        expected = min(base_score + 10.0, 100.0)
        assert score == expected, (
            f"2 指标共振应 +10：score={score}, expected={expected}, triggered={triggered}"
        )
    elif count >= 3:
        expected = min(base_score + 20.0, 100.0)
        assert score == expected, (
            f"3+ 指标共振应 +20：score={score}, expected={expected}, triggered={triggered}"
        )


@settings(max_examples=200)
@given(triggered=_triggered_strategy)
def test_indicator_score_weight_differentiation(triggered: dict[str, bool]):
    """
    # Feature: screening-parameter-optimization, Property 9: 技术指标差异化权重与共振加分

    **Validates: Requirements 5.1**

    差异化权重验证：MACD 权重最高（35），RSI 次之（25），BOLL 和 DMA 相同（20）。
    当仅单个指标触发时，MACD 评分 > RSI 评分 > BOLL 评分 == DMA 评分。
    """
    # 验证权重常量与实现一致
    assert ScreenExecutor._INDICATOR_WEIGHTS == _WEIGHTS, (
        f"权重常量不一致：{ScreenExecutor._INDICATOR_WEIGHTS} != {_WEIGHTS}"
    )

    # 单指标触发时验证差异化
    macd_only = ScreenExecutor._compute_indicator_score(
        {"macd": True, "rsi": False, "boll": False, "dma": False}
    )
    rsi_only = ScreenExecutor._compute_indicator_score(
        {"macd": False, "rsi": True, "boll": False, "dma": False}
    )
    boll_only = ScreenExecutor._compute_indicator_score(
        {"macd": False, "rsi": False, "boll": True, "dma": False}
    )
    dma_only = ScreenExecutor._compute_indicator_score(
        {"macd": False, "rsi": False, "boll": False, "dma": True}
    )

    assert macd_only > rsi_only > boll_only, (
        f"权重顺序应为 MACD > RSI > BOLL：{macd_only}, {rsi_only}, {boll_only}"
    )
    assert boll_only == dma_only, (
        f"BOLL 和 DMA 权重应相同：{boll_only} != {dma_only}"
    )
