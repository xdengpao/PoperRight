"""
多指数风控最严重等级聚合属性测试（Hypothesis）

**Validates: Requirements 9.1, 9.3**

Property 10: 多指数风控最严重等级聚合
For any set of index closing price data, the combined risk level SHALL equal
the most severe individual index risk level (DANGER > CAUTION > NORMAL).
Empty index data SHALL be skipped.
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import MarketRiskLevel
from app.services.risk_controller import MarketRiskChecker


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 合理的收盘价范围
_price = st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False)

# 收盘价序列（至少 61 个数据点以确保 MA60 可计算）
_closes_with_ma = st.lists(_price, min_size=61, max_size=120)

# 收盘价序列（可能不足以计算均线）
_closes_short = st.lists(_price, min_size=1, max_size=19)

# 空收盘价序列
_empty_closes: list[float] = []

# 指数代码
_index_codes = ["000001.SH", "399006.SZ", "000300.SH", "000905.SH"]

# 风险等级严重度映射
_SEVERITY = {
    MarketRiskLevel.NORMAL: 0,
    MarketRiskLevel.CAUTION: 1,
    MarketRiskLevel.DANGER: 2,
}


# ---------------------------------------------------------------------------
# Property 10: 多指数风控最严重等级聚合
# ---------------------------------------------------------------------------


class TestMultiIndexRiskProperties:
    """多指数风控最严重等级聚合属性测试。

    Feature: risk-control-enhancement, Property 10: 多指数风控最严重等级聚合
    """

    @given(
        closes_list=st.lists(
            st.lists(
                _price, min_size=61, max_size=120,
            ),
            min_size=1,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_combined_level_equals_most_severe(
        self, closes_list: list[list[float]],
    ) -> None:
        """综合风险等级 SHALL 等于所有单个指数风险等级中最严重的那个。

        **Validates: Requirements 9.1, 9.3**
        """
        checker = MarketRiskChecker()

        # 构建 index_data
        index_data: dict[str, list[float]] = {}
        for i, closes in enumerate(closes_list):
            code = _index_codes[i % len(_index_codes)]
            index_data[code] = closes

        combined_level, details = checker.check_multi_index_risk(index_data)

        # 独立计算每个指数的风险等级
        expected_max_severity = 0
        for code, closes in index_data.items():
            if not closes:
                continue
            individual_level = checker.check_market_risk(closes)
            severity = _SEVERITY[individual_level]
            if severity > expected_max_severity:
                expected_max_severity = severity

        expected_level = MarketRiskLevel.NORMAL
        for level, sev in _SEVERITY.items():
            if sev == expected_max_severity:
                expected_level = level

        assert combined_level == expected_level, (
            f"综合风险等级 {combined_level} != 预期最严重等级 {expected_level}"
        )

    @given(
        closes_list=st.lists(
            st.lists(
                _price, min_size=61, max_size=120,
            ),
            min_size=1,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_details_contain_all_non_empty_indices(
        self, closes_list: list[list[float]],
    ) -> None:
        """details 字典 SHALL 包含所有非空数据指数的条目。

        **Validates: Requirements 9.1**
        """
        checker = MarketRiskChecker()

        index_data: dict[str, list[float]] = {}
        for i, closes in enumerate(closes_list):
            code = _index_codes[i % len(_index_codes)]
            index_data[code] = closes

        _, details = checker.check_multi_index_risk(index_data)

        for code, closes in index_data.items():
            if closes:
                assert code in details, (
                    f"非空指数 {code} 应出现在 details 中"
                )
                assert "risk_level" in details[code]
                assert "above_ma20" in details[code]
                assert "above_ma60" in details[code]

    @given(
        non_empty_closes=st.lists(
            _price, min_size=61, max_size=120,
        ),
    )
    @settings(max_examples=200)
    def test_empty_indices_are_skipped(
        self, non_empty_closes: list[float],
    ) -> None:
        """空数据的指数 SHALL 被跳过，不影响综合风险等级。

        **Validates: Requirements 9.1**
        """
        checker = MarketRiskChecker()

        # 混合空和非空数据
        index_data: dict[str, list[float]] = {
            "000001.SH": non_empty_closes,
            "399006.SZ": [],
            "000300.SH": [],
            "000905.SH": [],
        }

        combined_level, details = checker.check_multi_index_risk(index_data)

        # 空数据指数不应出现在 details 中
        assert "399006.SZ" not in details
        assert "000300.SH" not in details
        assert "000905.SH" not in details

        # 综合等级应等于唯一非空指数的等级
        expected_level = checker.check_market_risk(non_empty_closes)
        assert combined_level == expected_level, (
            f"仅一个非空指数时，综合等级 {combined_level} 应等于该指数等级 {expected_level}"
        )

    def test_all_empty_returns_normal(self) -> None:
        """所有指数数据为空时，综合风险等级 SHALL 为 NORMAL。

        **Validates: Requirements 9.1**
        """
        checker = MarketRiskChecker()

        index_data: dict[str, list[float]] = {
            "000001.SH": [],
            "399006.SZ": [],
        }

        combined_level, details = checker.check_multi_index_risk(index_data)

        assert combined_level == MarketRiskLevel.NORMAL
        assert len(details) == 0

    def test_empty_dict_returns_normal(self) -> None:
        """空字典输入时，综合风险等级 SHALL 为 NORMAL。

        **Validates: Requirements 9.1**
        """
        checker = MarketRiskChecker()

        combined_level, details = checker.check_multi_index_risk({})

        assert combined_level == MarketRiskLevel.NORMAL
        assert len(details) == 0

    @given(
        closes_list=st.lists(
            st.lists(
                _price, min_size=61, max_size=120,
            ),
            min_size=2,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_individual_risk_levels_match_check_market_risk(
        self, closes_list: list[list[float]],
    ) -> None:
        """每个指数的 details 中的 risk_level SHALL 与单独调用 check_market_risk 一致。

        **Validates: Requirements 9.3**
        """
        checker = MarketRiskChecker()

        index_data: dict[str, list[float]] = {}
        for i, closes in enumerate(closes_list):
            code = _index_codes[i % len(_index_codes)]
            index_data[code] = closes

        _, details = checker.check_multi_index_risk(index_data)

        for code, closes in index_data.items():
            if not closes:
                continue
            expected_level = checker.check_market_risk(closes)
            actual_level = details[code]["risk_level"]
            assert actual_level == expected_level, (
                f"指数 {code} 的风险等级 {actual_level} != 预期 {expected_level}"
            )

    @given(
        closes_list=st.lists(
            st.lists(
                _price, min_size=61, max_size=120,
            ),
            min_size=1,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_combined_level_severity_ordering(
        self, closes_list: list[list[float]],
    ) -> None:
        """综合风险等级的严重度 SHALL >= 每个单独指数的严重度。

        **Validates: Requirements 9.3**
        """
        checker = MarketRiskChecker()

        index_data: dict[str, list[float]] = {}
        for i, closes in enumerate(closes_list):
            code = _index_codes[i % len(_index_codes)]
            index_data[code] = closes

        combined_level, details = checker.check_multi_index_risk(index_data)

        combined_severity = _SEVERITY[combined_level]
        for code, detail in details.items():
            individual_severity = _SEVERITY[detail["risk_level"]]
            assert combined_severity >= individual_severity, (
                f"综合严重度 {combined_severity} 应 >= 指数 {code} 的严重度 {individual_severity}"
            )
