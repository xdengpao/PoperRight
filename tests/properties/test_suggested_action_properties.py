"""
预警建议操作映射正确性属性测试（Hypothesis）

**Validates: Requirements 12.1, 12.2**

Property 11: 预警建议操作映射正确性
For any warning type, the suggested action SHALL follow the defined mapping:
- 固定止损触发 → 建议止损卖出
- 移动止损触发 → 建议减仓
- 破位预警（急跌/阴跌/趋势止损） → 建议关注，考虑减仓
- 仓位超限 → 建议不再加仓
- 其他未知类型 → 建议关注
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.risk_controller import get_suggested_action


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 已知的固定映射预警类型
_KNOWN_TYPES = [
    "固定止损触发",
    "移动止损触发",
    "急跌破位预警",
    "阴跌破位预警",
    "趋势止损触发",
]

# 包含「仓位超限」的预警类型
_POSITION_LIMIT_TYPES = st.one_of(
    st.just("单股仓位超限"),
    st.just("银行行业仓位超限"),
    st.just("半导体行业仓位超限"),
    st.just("未分类行业仓位超限"),
    # 带随机行业名称的仓位超限
    st.text(min_size=1, max_size=10).map(lambda s: f"{s}仓位超限"),
)

# 不包含「仓位超限」且不在已知映射中的随机字符串
_UNKNOWN_TYPES = st.text(min_size=1, max_size=50).filter(
    lambda s: s not in _KNOWN_TYPES and "仓位超限" not in s
)


# ---------------------------------------------------------------------------
# Property 11: 预警建议操作映射正确性
# ---------------------------------------------------------------------------


class TestSuggestedActionProperties:
    """预警建议操作映射正确性属性测试。

    Feature: risk-control-enhancement, Property 11: 预警建议操作映射正确性
    """

    def test_fixed_stop_loss_maps_to_sell(self) -> None:
        """固定止损触发 SHALL 映射到「建议止损卖出」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action("固定止损触发")
        assert result == "建议止损卖出", (
            f"固定止损触发应映射到「建议止损卖出」，实际: {result}"
        )

    def test_trailing_stop_loss_maps_to_reduce(self) -> None:
        """移动止损触发 SHALL 映射到「建议减仓」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action("移动止损触发")
        assert result == "建议减仓", (
            f"移动止损触发应映射到「建议减仓」，实际: {result}"
        )

    def test_rapid_breakdown_maps_to_watch(self) -> None:
        """急跌破位预警 SHALL 映射到「建议关注，考虑减仓」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action("急跌破位预警")
        assert result == "建议关注，考虑减仓", (
            f"急跌破位预警应映射到「建议关注，考虑减仓」，实际: {result}"
        )

    def test_gradual_breakdown_maps_to_watch(self) -> None:
        """阴跌破位预警 SHALL 映射到「建议关注，考虑减仓」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action("阴跌破位预警")
        assert result == "建议关注，考虑减仓", (
            f"阴跌破位预警应映射到「建议关注，考虑减仓」，实际: {result}"
        )

    def test_trend_stop_loss_maps_to_watch(self) -> None:
        """趋势止损触发 SHALL 映射到「建议关注，考虑减仓」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action("趋势止损触发")
        assert result == "建议关注，考虑减仓", (
            f"趋势止损触发应映射到「建议关注，考虑减仓」，实际: {result}"
        )

    @given(warning_type=_POSITION_LIMIT_TYPES)
    @settings(max_examples=200)
    def test_position_limit_maps_to_no_add(self, warning_type: str) -> None:
        """任何包含「仓位超限」的预警类型 SHALL 映射到「建议不再加仓」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action(warning_type)
        assert result == "建议不再加仓", (
            f"包含「仓位超限」的预警类型 '{warning_type}' 应映射到「建议不再加仓」，实际: {result}"
        )

    @given(warning_type=_UNKNOWN_TYPES)
    @settings(max_examples=200)
    def test_unknown_type_maps_to_default(self, warning_type: str) -> None:
        """未知预警类型 SHALL 映射到默认值「建议关注」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action(warning_type)
        assert result == "建议关注", (
            f"未知预警类型 '{warning_type}' 应映射到「建议关注」，实际: {result}"
        )

    @given(
        warning_type=st.sampled_from(_KNOWN_TYPES),
    )
    @settings(max_examples=200)
    def test_known_types_never_return_default(self, warning_type: str) -> None:
        """已知映射的预警类型 SHALL 不返回默认值「建议关注」。

        **Validates: Requirements 12.2**
        """
        result = get_suggested_action(warning_type)
        assert result != "建议关注", (
            f"已知预警类型 '{warning_type}' 不应返回默认值「建议关注」，实际: {result}"
        )

    @given(
        warning_type=st.one_of(
            st.sampled_from(_KNOWN_TYPES),
            _POSITION_LIMIT_TYPES,
            _UNKNOWN_TYPES,
        ),
    )
    @settings(max_examples=200)
    def test_result_is_always_non_empty_string(self, warning_type: str) -> None:
        """对任意预警类型，建议操作 SHALL 始终返回非空字符串。

        **Validates: Requirements 12.1**
        """
        result = get_suggested_action(warning_type)
        assert isinstance(result, str), f"返回值应为字符串，实际: {type(result)}"
        assert len(result) > 0, "返回值不应为空字符串"

    @given(
        warning_type=st.one_of(
            st.sampled_from(_KNOWN_TYPES),
            _POSITION_LIMIT_TYPES,
            _UNKNOWN_TYPES,
        ),
    )
    @settings(max_examples=200)
    def test_deterministic_mapping(self, warning_type: str) -> None:
        """对同一预警类型，多次调用 SHALL 返回相同结果（确定性映射）。

        **Validates: Requirements 12.2**
        """
        result1 = get_suggested_action(warning_type)
        result2 = get_suggested_action(warning_type)
        assert result1 == result2, (
            f"同一预警类型 '{warning_type}' 的两次调用结果不一致: {result1} vs {result2}"
        )
