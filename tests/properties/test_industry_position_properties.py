"""
行业仓位属性测试（Hypothesis）

**Validates: Requirements 6.6**

Property 6: 行业仓位加和不变量
For any positions list and industry classification mapping,
the sum of all industry position percentages SHALL equal the total
position percentage (allowing floating point tolerance ≤ 0.01%).
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import PositionRiskChecker


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 股票代码：6 位数字字符串
_symbol = st.text(
    alphabet="0123456789",
    min_size=6,
    max_size=6,
)

# 正市值
_positive_market_value = st.floats(
    min_value=0.01,
    max_value=1e10,
    allow_nan=False,
    allow_infinity=False,
)

# 行业名称
_industry_name = st.sampled_from([
    "银行", "半导体", "医药生物", "食品饮料", "电力设备",
    "汽车", "房地产", "计算机", "传媒", "钢铁",
])

# 单个持仓条目
_position_entry = st.fixed_dictionaries({
    "symbol": _symbol,
    "market_value": _positive_market_value,
})

# 持仓列表（1 到 20 只股票）
_positions_list = st.lists(
    _position_entry,
    min_size=1,
    max_size=20,
)


def _industry_map_strategy(positions: list[dict]) -> st.SearchStrategy:
    """根据持仓列表生成行业映射策略，部分股票可能缺失行业数据。"""
    symbols = [p["symbol"] for p in positions]
    if not symbols:
        return st.just({})
    # 为每个 symbol 随机分配行业或不分配（模拟缺失）
    return st.fixed_dictionaries({
        sym: _industry_name for sym in symbols
    }) | st.dictionaries(
        keys=st.sampled_from(symbols),
        values=_industry_name,
        min_size=0,
        max_size=len(symbols),
    )


# ---------------------------------------------------------------------------
# Property 6: 行业仓位加和不变量
# ---------------------------------------------------------------------------


class TestIndustryPositionProperties:
    """行业仓位计算属性测试。

    Feature: risk-control-enhancement, Property 6: 行业仓位加和不变量
    """

    @given(
        positions=_positions_list,
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_industry_percentages_sum_to_100(
        self, positions: list[dict], data: st.DataObject,
    ) -> None:
        """各行业仓位占比之和 SHALL 等于 100%（允许浮点精度误差 ≤ 0.01%）。

        **Validates: Requirements 6.6**
        """
        # 确保总市值 > 0
        total_mv = sum(p["market_value"] for p in positions)
        assume(total_mv > 0)

        # 生成行业映射（部分股票可能有行业，部分可能没有）
        symbols = list({p["symbol"] for p in positions})
        industry_map = data.draw(
            st.dictionaries(
                keys=st.sampled_from(symbols) if symbols else st.nothing(),
                values=_industry_name,
                min_size=0,
                max_size=len(symbols),
            )
        )

        result = PositionRiskChecker.compute_industry_positions_pure(
            positions, industry_map,
        )

        # 所有行业占比之和应等于 100%
        total_pct = sum(result.values())
        assert math.isclose(total_pct, 100.0, abs_tol=0.01), (
            f"行业仓位占比之和 {total_pct:.4f}% != 100%，"
            f"误差 {abs(total_pct - 100.0):.4f}% 超过 0.01% 容差"
        )

    @given(positions=_positions_list)
    @settings(max_examples=200)
    def test_all_classified_when_full_map(
        self, positions: list[dict],
    ) -> None:
        """当所有股票都有行业映射时，结果中不应包含「未分类」。

        **Validates: Requirements 6.6**
        """
        total_mv = sum(p["market_value"] for p in positions)
        assume(total_mv > 0)

        # 为所有股票分配行业
        industry_map = {p["symbol"]: "银行" for p in positions}

        result = PositionRiskChecker.compute_industry_positions_pure(
            positions, industry_map,
        )

        assert "未分类" not in result, (
            "所有股票都有行业映射时，不应出现「未分类」"
        )

    @given(positions=_positions_list)
    @settings(max_examples=200)
    def test_unclassified_when_no_map(
        self, positions: list[dict],
    ) -> None:
        """当行业映射为空时，所有股票归入「未分类」，占比 100%。

        **Validates: Requirements 6.6**
        """
        total_mv = sum(p["market_value"] for p in positions)
        assume(total_mv > 0)

        result = PositionRiskChecker.compute_industry_positions_pure(
            positions, {},
        )

        assert len(result) == 1, (
            f"空行业映射时应只有一个行业（未分类），实际有 {len(result)} 个"
        )
        assert "未分类" in result, "空行业映射时应包含「未分类」"
        assert math.isclose(result["未分类"], 100.0, abs_tol=0.01), (
            f"空行业映射时「未分类」占比应为 100%，实际为 {result['未分类']:.4f}%"
        )

    def test_empty_positions_returns_empty(self) -> None:
        """空持仓列表返回空字典。

        **Validates: Requirements 6.6**
        """
        result = PositionRiskChecker.compute_industry_positions_pure([], {})
        assert result == {}

    def test_zero_market_value_returns_empty(self) -> None:
        """总市值为 0 时返回空字典。

        **Validates: Requirements 6.6**
        """
        positions = [{"symbol": "600000", "market_value": 0.0}]
        result = PositionRiskChecker.compute_industry_positions_pure(
            positions, {"600000": "银行"},
        )
        assert result == {}

    @given(
        positions=_positions_list,
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_each_percentage_non_negative(
        self, positions: list[dict], data: st.DataObject,
    ) -> None:
        """每个行业的仓位占比 SHALL 为非负数。

        **Validates: Requirements 6.6**
        """
        total_mv = sum(p["market_value"] for p in positions)
        assume(total_mv > 0)

        symbols = list({p["symbol"] for p in positions})
        industry_map = data.draw(
            st.dictionaries(
                keys=st.sampled_from(symbols) if symbols else st.nothing(),
                values=_industry_name,
                min_size=0,
                max_size=len(symbols),
            )
        )

        result = PositionRiskChecker.compute_industry_positions_pure(
            positions, industry_map,
        )

        for industry, pct in result.items():
            assert pct >= 0.0, (
                f"行业 {industry} 的仓位占比 {pct} 不应为负数"
            )
