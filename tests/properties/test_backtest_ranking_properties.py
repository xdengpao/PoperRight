"""
BacktestEngine 候选排序属性测试（Hypothesis）

**Validates: Requirements 12.16**

属性 22f：回测候选排序正确性
- 对任意候选列表（长度 > 剩余空位数），验证实际买入标的为按优先级排序后的前 N 只
- 排序规则：趋势评分从高到低 → 风险等级从低到高（LOW > MEDIUM > HIGH）→ 触发信号数量从多到少 → 趋势强度从强到弱
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import RiskLevel, ScreenItem, SignalDetail, SignalCategory
from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_signal_categories = list(SignalCategory)

_signal_detail = st.builds(
    SignalDetail,
    category=st.sampled_from(_signal_categories),
    label=st.text(min_size=1, max_size=10),
    is_fake_breakout=st.just(False),
)

_screen_item = st.builds(
    ScreenItem,
    symbol=st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True),
    ref_buy_price=st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("500.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    trend_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    risk_level=st.sampled_from(list(RiskLevel)),
    signals=st.lists(_signal_detail, min_size=0, max_size=8),
    has_fake_breakout=st.just(False),
)

# Generate candidate lists with at least 2 items so we can test truncation
_candidates_list = st.lists(_screen_item, min_size=2, max_size=30)

# available_slots: at least 1, will be constrained to < len(candidates)
_available_slots = st.integers(min_value=1, max_value=29)


# ---------------------------------------------------------------------------
# 属性 22f：回测候选排序正确性
# ---------------------------------------------------------------------------


@given(candidates=_candidates_list, available_slots=_available_slots)
@settings(max_examples=100)
def test_rank_candidates_returns_correct_sorted_top_n(
    candidates: list[ScreenItem],
    available_slots: int,
) -> None:
    """
    **Validates: Requirements 12.16**

    属性 22f：对任意候选列表（长度 > 剩余空位数），验证：
    1. 返回列表长度 == min(available_slots, len(candidates))
    2. 返回的标的是按优先级排序后的前 N 只
    3. 排序规则：趋势评分 desc → 风险等级 asc (LOW<MEDIUM<HIGH) → 信号数量 desc → 趋势强度 desc
    """
    assume(len(candidates) > available_slots)

    engine = BacktestEngine()
    result = engine._rank_candidates(candidates, available_slots)

    # 1. 返回长度正确
    assert len(result) == available_slots, (
        f"返回数量不正确: got {len(result)}, expected {available_slots}"
    )

    # 2. 独立计算期望排序结果
    risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

    def expected_sort_key(item: ScreenItem) -> tuple:
        return (
            -item.trend_score,
            risk_order.get(item.risk_level, 1),
            -len(item.signals),
            -item.trend_score,  # trend_strength proxy
        )

    expected_sorted = sorted(candidates, key=expected_sort_key)
    expected_top_n = expected_sorted[:available_slots]

    # 3. 验证返回结果与期望一致（顺序也一致）
    for i, (actual, expected) in enumerate(zip(result, expected_top_n)):
        assert actual is expected, (
            f"位置 {i} 不匹配: "
            f"actual=(symbol={actual.symbol}, score={actual.trend_score}, "
            f"risk={actual.risk_level}, signals={len(actual.signals)}) "
            f"expected=(symbol={expected.symbol}, score={expected.trend_score}, "
            f"risk={expected.risk_level}, signals={len(expected.signals)})"
        )
