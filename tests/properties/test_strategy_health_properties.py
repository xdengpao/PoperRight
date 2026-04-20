"""
策略实盘健康计算属性测试（Hypothesis）

**Validates: Requirements 8.1, 8.2**

Property 9: 策略实盘健康计算正确性
For any trade records list (each containing a pnl field):
- win_rate = profitable trades / total trades
- When win_rate < 0.4 or max_drawdown > 0.2, is_healthy SHALL be False
- When trade_count < N, data_sufficient SHALL be False
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.risk_controller import StrategyHealthMonitor


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 单笔交易 PnL：合理的盈亏范围
_pnl_value = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False,
)

# 交易记录列表（1~100 笔）
_trade_records = st.lists(
    st.fixed_dictionaries({"pnl": _pnl_value}),
    min_size=1,
    max_size=100,
)

# 空交易记录
_empty_records: list[dict] = []

# N 参数（最近交易笔数）
_n_param = st.integers(min_value=1, max_value=50)


# ---------------------------------------------------------------------------
# Property 9: 策略实盘健康计算正确性
# ---------------------------------------------------------------------------


class TestStrategyHealthProperties:
    """策略实盘健康计算属性测试。

    Feature: risk-control-enhancement, Property 9: 策略实盘健康计算正确性
    """

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_win_rate_equals_profitable_over_total(
        self, records: list[dict], n: int,
    ) -> None:
        """胜率 SHALL 等于盈利交易数 / 总交易数。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        recent = records[-n:]
        expected_profitable = sum(1 for r in recent if r["pnl"] > 0)
        expected_win_rate = expected_profitable / len(recent)

        assert abs(result["win_rate"] - expected_win_rate) < 1e-9, (
            f"胜率 {result['win_rate']} != 预期 {expected_win_rate}"
        )

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_unhealthy_when_low_win_rate_or_high_drawdown(
        self, records: list[dict], n: int,
    ) -> None:
        """当胜率 < 0.4 或最大回撤 > 0.2 时，is_healthy SHALL 为 False。

        **Validates: Requirements 8.2**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        if result["win_rate"] < 0.4 or result["max_drawdown"] > 0.2:
            assert result["is_healthy"] is False, (
                f"胜率={result['win_rate']:.3f}, 回撤={result['max_drawdown']:.3f} "
                f"时 is_healthy 应为 False"
            )

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_healthy_when_good_metrics(
        self, records: list[dict], n: int,
    ) -> None:
        """当胜率 >= 0.4 且最大回撤 <= 0.2 时，is_healthy SHALL 为 True。

        **Validates: Requirements 8.2**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        if result["win_rate"] >= 0.4 and result["max_drawdown"] <= 0.2:
            assert result["is_healthy"] is True, (
                f"胜率={result['win_rate']:.3f}, 回撤={result['max_drawdown']:.3f} "
                f"时 is_healthy 应为 True"
            )

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_data_sufficient_when_enough_records(
        self, records: list[dict], n: int,
    ) -> None:
        """当交易记录数 >= N 时，data_sufficient SHALL 为 True。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        if len(records) >= n:
            assert result["data_sufficient"] is True, (
                f"记录数 {len(records)} >= N={n}，data_sufficient 应为 True"
            )
        else:
            assert result["data_sufficient"] is False, (
                f"记录数 {len(records)} < N={n}，data_sufficient 应为 False"
            )

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_trade_count_is_min_of_records_and_n(
        self, records: list[dict], n: int,
    ) -> None:
        """trade_count SHALL 等于 min(len(records), n)。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        expected_count = min(len(records), n)
        assert result["trade_count"] == expected_count, (
            f"trade_count {result['trade_count']} != 预期 {expected_count}"
        )

    def test_empty_records_returns_defaults(self) -> None:
        """空交易记录 SHALL 返回默认值。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure([])

        assert result["win_rate"] == 0.0
        assert result["max_drawdown"] == 0.0
        assert result["is_healthy"] is True
        assert result["data_sufficient"] is False
        assert result["trade_count"] == 0

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_win_rate_in_valid_range(
        self, records: list[dict], n: int,
    ) -> None:
        """胜率 SHALL 在 [0, 1] 范围内。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        assert 0.0 <= result["win_rate"] <= 1.0, (
            f"胜率 {result['win_rate']} 不在 [0, 1] 范围内"
        )

    @given(records=_trade_records, n=_n_param)
    @settings(max_examples=200)
    def test_max_drawdown_non_negative(
        self, records: list[dict], n: int,
    ) -> None:
        """最大回撤 SHALL >= 0。

        **Validates: Requirements 8.1**
        """
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        assert result["max_drawdown"] >= 0.0, (
            f"最大回撤 {result['max_drawdown']} 应 >= 0"
        )

    @given(n=_n_param)
    @settings(max_examples=100)
    def test_all_profitable_gives_win_rate_one(self, n: int) -> None:
        """当所有交易均盈利时，胜率 SHALL 为 1.0。

        **Validates: Requirements 8.1**
        """
        records = [{"pnl": 100.0}] * max(n, 1)
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        assert result["win_rate"] == 1.0, (
            f"全部盈利时胜率应为 1.0，实际为 {result['win_rate']}"
        )

    @given(n=_n_param)
    @settings(max_examples=100)
    def test_all_losing_gives_win_rate_zero(self, n: int) -> None:
        """当所有交易均亏损时，胜率 SHALL 为 0.0。

        **Validates: Requirements 8.1**
        """
        records = [{"pnl": -100.0}] * max(n, 1)
        result = StrategyHealthMonitor.compute_live_health_pure(records, n)

        assert result["win_rate"] == 0.0, (
            f"全部亏损时胜率应为 0.0，实际为 {result['win_rate']}"
        )
