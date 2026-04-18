"""
ScreenDataProvider 增强功能单元测试

测试百分位排名和行业相对值计算的边界条件，以及板块数据不可用时的降级处理。

Tests:
- percentile with all None values (edge case)
- percentile with single stock (edge case)
- industry-relative with missing industry (edge case)
- industry-relative with zero median (edge case)
- sector data unavailable degradation (Req 5.6)

Requirements: 9.1, 9.2, 9.6, 10.3, 10.6, 5.6
"""

from __future__ import annotations

import pytest

from app.services.screener.screen_data_provider import ScreenDataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stocks(mapping: dict[str, dict]) -> dict[str, dict]:
    """Shortcut: return the mapping as-is (for readability)."""
    return mapping


# ---------------------------------------------------------------------------
# Test: percentile with all None values (Req 9.1, 9.2, 9.6)
# ---------------------------------------------------------------------------


class TestPercentileAllNone:
    """When every stock has None for a factor, percentile fields should be None."""

    def test_all_none_values_produce_none_percentiles(self):
        """All None factor values → all _pctl fields set to None."""
        stocks_data = _stocks({
            "A": {"score": None},
            "B": {"score": None},
            "C": {"score": None},
        })

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["score"])

        for sym in ("A", "B", "C"):
            assert stocks_data[sym]["score_pctl"] is None

    def test_all_none_with_multiple_factors(self):
        """Multiple factors all-None: each _pctl field is None independently."""
        stocks_data = _stocks({
            "A": {"f1": None, "f2": None},
            "B": {"f1": None, "f2": None},
        })

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["f1", "f2"])

        assert stocks_data["A"]["f1_pctl"] is None
        assert stocks_data["A"]["f2_pctl"] is None
        assert stocks_data["B"]["f1_pctl"] is None
        assert stocks_data["B"]["f2_pctl"] is None


# ---------------------------------------------------------------------------
# Test: percentile with single stock (Req 9.1, 9.2, 9.6)
# ---------------------------------------------------------------------------


class TestPercentileSingleStock:
    """A single valid stock should receive percentile = 100."""

    def test_single_valid_stock_gets_100(self):
        """One stock with a value → percentile = 100."""
        stocks_data = _stocks({
            "A": {"score": 42.0},
        })

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["score"])

        assert stocks_data["A"]["score_pctl"] == 100.0

    def test_single_valid_among_nones(self):
        """One valid stock among None-valued stocks → valid gets 100, Nones get None."""
        stocks_data = _stocks({
            "A": {"score": None},
            "B": {"score": 10.0},
            "C": {"score": None},
        })

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["score"])

        assert stocks_data["B"]["score_pctl"] == 100.0
        assert stocks_data["A"]["score_pctl"] is None
        assert stocks_data["C"]["score_pctl"] is None

    def test_single_stock_negative_value(self):
        """Single stock with negative value still gets percentile = 100."""
        stocks_data = _stocks({
            "A": {"score": -50.0},
        })

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["score"])

        assert stocks_data["A"]["score_pctl"] == 100.0


# ---------------------------------------------------------------------------
# Test: industry-relative with missing industry (Req 10.3, 10.6)
# ---------------------------------------------------------------------------


class TestIndustryRelativeMissingIndustry:
    """Stocks not found in industry_map should get _ind_rel = None."""

    def test_stock_not_in_industry_map(self):
        """Stock absent from industry_map → _ind_rel = None."""
        stocks_data = _stocks({
            "A": {"pe": 20.0},
            "B": {"pe": 15.0},
        })
        # Only A is mapped; B has no industry
        industry_map = {"A": "IND001"}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        # A should have a relative value (sole member → median = 20.0 → rel = 1.0)
        assert stocks_data["A"]["pe_ind_rel"] == pytest.approx(1.0)
        # B has no industry mapping → None
        assert stocks_data["B"]["pe_ind_rel"] is None

    def test_empty_industry_map(self):
        """Empty industry_map → all stocks get _ind_rel = None."""
        stocks_data = _stocks({
            "A": {"pe": 20.0},
            "B": {"pe": 15.0},
        })
        industry_map: dict[str, str] = {}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        assert stocks_data["A"]["pe_ind_rel"] is None
        assert stocks_data["B"]["pe_ind_rel"] is None

    def test_stock_with_none_value_and_no_industry(self):
        """Stock with None factor value and no industry → _ind_rel = None."""
        stocks_data = _stocks({
            "A": {"pe": None},
        })
        industry_map: dict[str, str] = {}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        assert stocks_data["A"]["pe_ind_rel"] is None


# ---------------------------------------------------------------------------
# Test: industry-relative with zero median (Req 10.3, 10.6)
# ---------------------------------------------------------------------------


class TestIndustryRelativeZeroMedian:
    """When industry median is zero, _ind_rel should handle gracefully."""

    def test_zero_median_single_stock_gets_one(self):
        """Single stock in industry with value 0 → median=0, but single stock → 1.0."""
        stocks_data = _stocks({
            "A": {"pe": 0.0},
        })
        industry_map = {"A": "IND001"}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        # Single stock in industry → relative value = 1.0
        assert stocks_data["A"]["pe_ind_rel"] == pytest.approx(1.0)

    def test_zero_median_multiple_stocks_gets_none(self):
        """Multiple stocks in same industry all with value 0 → median=0 → _ind_rel = None."""
        stocks_data = _stocks({
            "A": {"pe": 0.0},
            "B": {"pe": 0.0},
        })
        industry_map = {"A": "IND001", "B": "IND001"}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        # Median is 0, multiple stocks → None (avoid division by zero)
        assert stocks_data["A"]["pe_ind_rel"] is None
        assert stocks_data["B"]["pe_ind_rel"] is None

    def test_mixed_zero_and_nonzero_median_not_zero(self):
        """When median is non-zero (mix of 0 and positive), relative values are computed."""
        stocks_data = _stocks({
            "A": {"pe": 0.0},
            "B": {"pe": 10.0},
            "C": {"pe": 20.0},
        })
        industry_map = {"A": "IND001", "B": "IND001", "C": "IND001"}

        ScreenDataProvider._compute_industry_relative_values(
            stocks_data, ["pe"], industry_map,
        )

        # Median of [0.0, 10.0, 20.0] = 10.0
        assert stocks_data["A"]["pe_ind_rel"] == pytest.approx(0.0)
        assert stocks_data["B"]["pe_ind_rel"] == pytest.approx(1.0)
        assert stocks_data["C"]["pe_ind_rel"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Test: sector data unavailable degradation (Req 5.6)
# ---------------------------------------------------------------------------


class TestSectorDataUnavailableDegradation:
    """
    When sector data is unavailable, ScreenDataProvider should degrade gracefully:
    sector_rank = None, sector_trend = False, sector_name = None.

    This tests the SectorStrengthFilter.filter_by_sector_strength() behavior
    when called with empty sector data, which is the path taken by
    ScreenDataProvider.load_screen_data() when sector queries fail.
    """

    def test_empty_sector_ranks_and_empty_map(self):
        """Both sector_ranks and stock_sector_map empty → all stocks get None sector fields."""
        from app.services.screener.sector_strength import SectorStrengthFilter

        stocks_data = _stocks({
            "A": {"close": 10.0, "ma_trend": 85},
            "B": {"close": 20.0, "pe_ttm": 15.0},
        })

        ssf = SectorStrengthFilter()
        ssf.filter_by_sector_strength(
            stocks_data=stocks_data,
            sector_ranks=[],
            stock_sector_map={},
        )

        for sym in ("A", "B"):
            assert stocks_data[sym]["sector_rank"] is None
            assert stocks_data[sym]["sector_trend"] is False
            assert stocks_data[sym]["sector_name"] is None

        # Existing fields should be preserved
        assert stocks_data["A"]["close"] == 10.0
        assert stocks_data["A"]["ma_trend"] == 85
        assert stocks_data["B"]["pe_ttm"] == 15.0

    def test_sector_degradation_does_not_block_percentile(self):
        """
        Sector data unavailable should not prevent percentile computation.

        This simulates the load_screen_data flow: percentile is computed first,
        then sector data loading may fail — percentile results should remain intact.
        """
        stocks_data = _stocks({
            "A": {"money_flow": 100.0},
            "B": {"money_flow": 200.0},
            "C": {"money_flow": 300.0},
        })

        # Step 1: compute percentile (succeeds)
        ScreenDataProvider._compute_percentile_ranks(
            stocks_data, ["money_flow"],
        )

        # Step 2: sector data unavailable → filter with empty data
        from app.services.screener.sector_strength import SectorStrengthFilter

        ssf = SectorStrengthFilter()
        ssf.filter_by_sector_strength(
            stocks_data=stocks_data,
            sector_ranks=[],
            stock_sector_map={},
        )

        # Percentile results should still be present
        assert stocks_data["A"]["money_flow_pctl"] is not None
        assert stocks_data["B"]["money_flow_pctl"] is not None
        assert stocks_data["C"]["money_flow_pctl"] is not None

        # Sector fields should be None/False
        for sym in ("A", "B", "C"):
            assert stocks_data[sym]["sector_rank"] is None
            assert stocks_data[sym]["sector_trend"] is False
