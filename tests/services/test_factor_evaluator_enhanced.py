"""Unit tests for enhanced FactorEvaluator with threshold type awareness.

Tests cover:
- Percentile factor evaluation (Req 12.2)
- Industry_relative factor evaluation (Req 12.3)
- Range factor evaluation (Req 12.5)
- Boolean factor evaluation — unchanged behavior (Req 12.4)
- Missing _pctl field handling (Req 12.6)
- Missing _ind_rel field handling (Req 12.6)
- Legacy factor condition backward compatibility (Req 13.1)
- Range with missing threshold_low/threshold_high (Req 12.5)

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1
"""

import pytest

from app.core.schemas import FactorCondition
from app.services.screener.strategy_engine import FactorEvaluator, FactorEvalResult


# ---------------------------------------------------------------------------
# Percentile factor evaluation (Req 12.2)
# ---------------------------------------------------------------------------


class TestPercentileFactorEvaluation:
    """Verify FactorEvaluator reads {factor_name}_pctl for PERCENTILE factors."""

    def test_money_flow_reads_pctl_field(self):
        """money_flow is PERCENTILE — evaluator should read money_flow_pctl."""
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=80,
        )
        stock_data = {
            "money_flow": 1500.0,       # raw value — should be ignored
            "money_flow_pctl": 90.0,    # percentile rank — should be used
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 90.0

    def test_money_flow_pctl_below_threshold(self):
        """money_flow_pctl below threshold → not passed."""
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=80,
        )
        stock_data = {
            "money_flow": 5000.0,
            "money_flow_pctl": 50.0,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 50.0

    def test_volume_price_reads_pctl_field(self):
        """volume_price is PERCENTILE — evaluator should read volume_price_pctl."""
        condition = FactorCondition(
            factor_name="volume_price",
            operator=">=",
            threshold=70,
        )
        stock_data = {
            "volume_price": 8000.0,
            "volume_price_pctl": 85.0,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 85.0

    def test_roe_reads_pctl_field(self):
        """roe is PERCENTILE — evaluator should read roe_pctl."""
        condition = FactorCondition(
            factor_name="roe",
            operator=">=",
            threshold=70,
        )
        stock_data = {
            "roe": 15.0,
            "roe_pctl": 75.0,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 75.0

    def test_percentile_with_less_than_operator(self):
        """Percentile factor with < operator."""
        condition = FactorCondition(
            factor_name="market_cap",
            operator="<",
            threshold=50,
        )
        stock_data = {
            "market_cap": 100_000_000,
            "market_cap_pctl": 30.0,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 30.0


# ---------------------------------------------------------------------------
# Industry-relative factor evaluation (Req 12.3)
# ---------------------------------------------------------------------------


class TestIndustryRelativeFactorEvaluation:
    """Verify FactorEvaluator reads {factor_name}_ind_rel for INDUSTRY_RELATIVE factors."""

    def test_pe_reads_ind_rel_field(self):
        """pe is INDUSTRY_RELATIVE — evaluator should read pe_ind_rel."""
        condition = FactorCondition(
            factor_name="pe",
            operator="<=",
            threshold=1.0,
        )
        stock_data = {
            "pe": 25.0,             # raw PE — should be ignored
            "pe_ind_rel": 0.8,      # industry relative — should be used
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 0.8

    def test_pe_ind_rel_above_threshold(self):
        """pe_ind_rel above threshold → not passed."""
        condition = FactorCondition(
            factor_name="pe",
            operator="<=",
            threshold=1.0,
        )
        stock_data = {
            "pe": 25.0,
            "pe_ind_rel": 1.5,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 1.5

    def test_pb_reads_ind_rel_field(self):
        """pb is INDUSTRY_RELATIVE — evaluator should read pb_ind_rel."""
        condition = FactorCondition(
            factor_name="pb",
            operator="<=",
            threshold=1.2,
        )
        stock_data = {
            "pb": 3.5,
            "pb_ind_rel": 0.9,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 0.9

    def test_industry_relative_with_equal_operator(self):
        """Industry-relative factor with == operator."""
        condition = FactorCondition(
            factor_name="pe",
            operator="==",
            threshold=1.0,
        )
        stock_data = {
            "pe": 20.0,
            "pe_ind_rel": 1.0,
        }
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Range factor evaluation (Req 12.5)
# ---------------------------------------------------------------------------


class TestRangeFactorEvaluation:
    """Verify FactorEvaluator checks value in [threshold_low, threshold_high] for RANGE factors."""

    def test_rsi_in_range_passes(self):
        """rsi value within [50, 80] → passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50, "threshold_high": 80},
        )
        stock_data = {"rsi": False, "rsi_current": 65.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 65.0

    def test_rsi_below_range_fails(self):
        """rsi value below range → not passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50, "threshold_high": 80},
        )
        stock_data = {"rsi": True, "rsi_current": 30.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 30.0

    def test_rsi_above_range_fails(self):
        """rsi value above range → not passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50, "threshold_high": 80},
        )
        stock_data = {"rsi": True, "rsi_current": 90.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 90.0

    def test_rsi_at_lower_bound_passes(self):
        """rsi value exactly at lower bound → passed (inclusive)."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50, "threshold_high": 80},
        )
        stock_data = {"rsi": False, "rsi_current": 50.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True

    def test_rsi_at_upper_bound_passes(self):
        """rsi value exactly at upper bound → passed (inclusive)."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50, "threshold_high": 80},
        )
        stock_data = {"rsi": False, "rsi_current": 80.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True

    def test_rsi_range_ignores_boolean_signal(self):
        """rsi RANGE 应读取 rsi_current，不使用布尔 rsi 信号。"""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 55, "threshold_high": 80},
        )
        stock_data = {"rsi": False, "rsi_current": 60.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 60.0

    def test_rsi_range_missing_current_fails_even_when_signal_true(self):
        """缺失 rsi_current 时，即使 rsi=True 也不通过。"""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 55, "threshold_high": 80},
        )
        stock_data = {"rsi": True}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_turnover_range_evaluation(self):
        """turnover is also RANGE type — verify it works."""
        condition = FactorCondition(
            factor_name="turnover",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 3.0, "threshold_high": 15.0},
        )
        stock_data = {"turnover": 8.5}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 8.5

    def test_range_missing_threshold_low_fails(self):
        """Range factor with missing threshold_low → not passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_high": 80},
        )
        stock_data = {"rsi_current": 65.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False

    def test_range_missing_threshold_high_fails(self):
        """Range factor with missing threshold_high → not passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={"threshold_low": 50},
        )
        stock_data = {"rsi_current": 65.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False

    def test_range_missing_both_bounds_fails(self):
        """Range factor with no bounds at all → not passed."""
        condition = FactorCondition(
            factor_name="rsi",
            operator="BETWEEN",
            threshold=None,
            params={},
        )
        stock_data = {"rsi_current": 65.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Boolean factor evaluation — unchanged behavior (Req 12.4)
# ---------------------------------------------------------------------------


class TestBooleanFactorEvaluation:
    """Verify FactorEvaluator preserves existing boolean factor behavior."""

    def test_macd_true_passes(self):
        """macd is BOOLEAN — True value → passed."""
        condition = FactorCondition(
            factor_name="macd",
            operator="==",
            threshold=None,
        )
        stock_data = {"macd": True}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 1.0

    def test_macd_false_fails(self):
        """macd is BOOLEAN — False value → not passed."""
        condition = FactorCondition(
            factor_name="macd",
            operator="==",
            threshold=None,
        )
        stock_data = {"macd": False}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 0.0

    def test_boll_truthy_value_passes(self):
        """boll is BOOLEAN — truthy non-bool value → passed."""
        condition = FactorCondition(
            factor_name="boll",
            operator="==",
            threshold=None,
        )
        stock_data = {"boll": 1}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True

    def test_sector_trend_boolean(self):
        """sector_trend is BOOLEAN — verify it works."""
        condition = FactorCondition(
            factor_name="sector_trend",
            operator="==",
            threshold=None,
        )
        stock_data = {"sector_trend": True}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True

    def test_boolean_factor_reads_raw_field(self):
        """Boolean factors should read the raw field, not _pctl or _ind_rel."""
        condition = FactorCondition(
            factor_name="macd",
            operator="==",
            threshold=None,
        )
        stock_data = {"macd": True, "macd_pctl": 50.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 1.0


# ---------------------------------------------------------------------------
# Missing _pctl field handling (Req 12.6)
# ---------------------------------------------------------------------------


class TestMissingPctlFieldHandling:
    """Verify FactorEvaluator returns passed=False when _pctl field is missing."""

    def test_missing_money_flow_pctl_fails(self):
        """money_flow is PERCENTILE but money_flow_pctl is absent → not passed."""
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=80,
        )
        # Only raw value present, no _pctl field
        stock_data = {"money_flow": 1500.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_missing_volume_price_pctl_fails(self):
        """volume_price is PERCENTILE but volume_price_pctl is absent → not passed."""
        condition = FactorCondition(
            factor_name="volume_price",
            operator=">=",
            threshold=70,
        )
        stock_data = {"volume_price": 8000.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_pctl_field_is_none_fails(self):
        """_pctl field exists but is None → not passed."""
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=80,
        )
        stock_data = {"money_flow": 1500.0, "money_flow_pctl": None}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_empty_stock_data_for_percentile_factor(self):
        """Completely empty stock_data for a percentile factor → not passed."""
        condition = FactorCondition(
            factor_name="roe",
            operator=">=",
            threshold=70,
        )
        stock_data = {}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None


# ---------------------------------------------------------------------------
# Missing _ind_rel field handling (Req 12.6)
# ---------------------------------------------------------------------------


class TestMissingIndRelFieldHandling:
    """Verify FactorEvaluator returns passed=False when _ind_rel field is missing."""

    def test_missing_pe_ind_rel_fails(self):
        """pe is INDUSTRY_RELATIVE but pe_ind_rel is absent → not passed."""
        condition = FactorCondition(
            factor_name="pe",
            operator="<=",
            threshold=1.0,
        )
        stock_data = {"pe": 25.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_missing_pb_ind_rel_fails(self):
        """pb is INDUSTRY_RELATIVE but pb_ind_rel is absent → not passed."""
        condition = FactorCondition(
            factor_name="pb",
            operator="<=",
            threshold=1.2,
        )
        stock_data = {"pb": 3.5}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_ind_rel_field_is_none_fails(self):
        """_ind_rel field exists but is None → not passed."""
        condition = FactorCondition(
            factor_name="pe",
            operator="<=",
            threshold=1.0,
        )
        stock_data = {"pe": 25.0, "pe_ind_rel": None}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None


# ---------------------------------------------------------------------------
# Legacy factor condition backward compatibility (Req 13.1)
# ---------------------------------------------------------------------------


class TestLegacyFactorConditionBackwardCompatibility:
    """Verify unknown factors fall back to ABSOLUTE threshold type."""

    def test_unknown_factor_uses_absolute_type(self):
        """Factor not in FACTOR_REGISTRY → falls back to ABSOLUTE, reads raw field."""
        condition = FactorCondition(
            factor_name="custom_indicator",
            operator=">=",
            threshold=50,
        )
        stock_data = {"custom_indicator": 75.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 75.0

    def test_unknown_factor_below_threshold(self):
        """Unknown factor with value below threshold → not passed."""
        condition = FactorCondition(
            factor_name="custom_indicator",
            operator=">=",
            threshold=50,
        )
        stock_data = {"custom_indicator": 30.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value == 30.0

    def test_unknown_factor_missing_value(self):
        """Unknown factor with missing value → not passed."""
        condition = FactorCondition(
            factor_name="custom_indicator",
            operator=">=",
            threshold=50,
        )
        stock_data = {}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
        assert result.value is None

    def test_params_threshold_type_override(self):
        """params.threshold_type can override FACTOR_REGISTRY type (backward compat)."""
        # money_flow is PERCENTILE in registry, but override to ABSOLUTE via params
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=1000,
            params={"threshold_type": "absolute"},
        )
        stock_data = {"money_flow": 1500.0, "money_flow_pctl": 90.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 1500.0  # reads raw field, not _pctl

    def test_params_threshold_type_override_to_percentile(self):
        """Override an ABSOLUTE factor to PERCENTILE via params."""
        condition = FactorCondition(
            factor_name="ma_trend",
            operator=">=",
            threshold=80,
            params={"threshold_type": "percentile"},
        )
        stock_data = {"ma_trend": 60.0, "ma_trend_pctl": 95.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 95.0  # reads _pctl field due to override

    def test_invalid_params_threshold_type_falls_back_to_absolute(self):
        """Invalid threshold_type in params → falls back to ABSOLUTE."""
        condition = FactorCondition(
            factor_name="money_flow",
            operator=">=",
            threshold=1000,
            params={"threshold_type": "invalid_type"},
        )
        stock_data = {"money_flow": 1500.0, "money_flow_pctl": 90.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 1500.0  # falls back to ABSOLUTE, reads raw field


# ---------------------------------------------------------------------------
# Weight propagation
# ---------------------------------------------------------------------------


class TestWeightPropagation:
    """Verify weight is correctly propagated to FactorEvalResult."""

    def test_custom_weight_is_set(self):
        condition = FactorCondition(
            factor_name="macd",
            operator="==",
            threshold=None,
        )
        stock_data = {"macd": True}
        result = FactorEvaluator.evaluate(condition, stock_data, weight=0.4)
        assert result.weight == 0.4

    def test_default_weight_is_one(self):
        condition = FactorCondition(
            factor_name="macd",
            operator="==",
            threshold=None,
        )
        stock_data = {"macd": True}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.weight == 1.0

    def test_factor_name_in_result(self):
        condition = FactorCondition(
            factor_name="pe",
            operator="<=",
            threshold=1.0,
        )
        stock_data = {"pe_ind_rel": 0.8}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.factor_name == "pe"


# ---------------------------------------------------------------------------
# Absolute factor evaluation (Req 12.4 — unchanged behavior)
# ---------------------------------------------------------------------------


class TestAbsoluteFactorEvaluation:
    """Verify ABSOLUTE factors read raw field and use standard comparison."""

    def test_ma_trend_absolute_passes(self):
        """ma_trend is ABSOLUTE — reads raw field."""
        condition = FactorCondition(
            factor_name="ma_trend",
            operator=">=",
            threshold=80,
        )
        stock_data = {"ma_trend": 85.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 85.0

    def test_sector_rank_absolute_passes(self):
        """sector_rank is ABSOLUTE — reads raw field."""
        condition = FactorCondition(
            factor_name="sector_rank",
            operator="<=",
            threshold=30,
        )
        stock_data = {"sector_rank": 15}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 15.0

    def test_large_order_absolute(self):
        """large_order is ABSOLUTE — reads raw field."""
        condition = FactorCondition(
            factor_name="large_order",
            operator=">=",
            threshold=30,
        )
        stock_data = {"large_order": 35.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is True
        assert result.value == 35.0

    def test_unsupported_operator_fails(self):
        """Unsupported operator → not passed."""
        condition = FactorCondition(
            factor_name="ma_trend",
            operator="INVALID",
            threshold=80,
        )
        stock_data = {"ma_trend": 85.0}
        result = FactorEvaluator.evaluate(condition, stock_data)
        assert result.passed is False
