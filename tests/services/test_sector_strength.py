"""
SectorStrengthFilter 单元测试

Tests:
- compute_sector_strength() 正常排名计算
- compute_sector_strength() 空数据处理
- filter_by_sector_strength() 正常写入 sector_rank, sector_trend, sector_name
- filter_by_sector_strength() 空 sector_ranks 优雅降级 (Req 5.6)
- filter_by_sector_strength() 股票不属于任何板块
- filter_by_sector_strength() top_n 过滤（仅 top_n 板块被考虑）
- 股票映射到多个板块时取最优（最低）排名

Requirements: 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

import pytest

from app.services.screener.sector_strength import (
    SectorRankResult,
    SectorStrengthFilter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rank(
    code: str,
    name: str,
    rank: int,
    change_pct: float = 0.0,
    is_bullish: bool = False,
) -> SectorRankResult:
    """Shortcut to build a SectorRankResult."""
    return SectorRankResult(
        sector_code=code,
        sector_name=name,
        rank=rank,
        change_pct=change_pct,
        is_bullish=is_bullish,
    )


# ---------------------------------------------------------------------------
# Test: compute_sector_strength with sample kline data
# ---------------------------------------------------------------------------


class TestComputeSectorStrength:
    """Test the pure-function compute_sector_strength()."""

    def test_ranks_descending_by_change_pct(self):
        """Sectors should be ranked in descending order of cumulative change_pct."""
        kline_data = [
            {"sector_code": "BK001", "change_pct": 2.0},
            {"sector_code": "BK001", "change_pct": 3.0},
            {"sector_code": "BK002", "change_pct": 10.0},
            {"sector_code": "BK003", "change_pct": 1.0},
        ]

        result = SectorStrengthFilter.compute_sector_strength(kline_data)

        assert len(result) == 3
        # BK002 total=10.0, BK001 total=5.0, BK003 total=1.0
        assert result[0] == ("BK002", 10.0)
        assert result[1] == ("BK001", 5.0)
        assert result[2] == ("BK003", 1.0)

    def test_single_sector(self):
        """A single sector should produce a single-element result."""
        kline_data = [
            {"sector_code": "BK001", "change_pct": 4.5},
        ]

        result = SectorStrengthFilter.compute_sector_strength(kline_data)

        assert len(result) == 1
        assert result[0] == ("BK001", 4.5)

    def test_negative_change_pct(self):
        """Negative change_pct values should be handled correctly."""
        kline_data = [
            {"sector_code": "BK001", "change_pct": -3.0},
            {"sector_code": "BK002", "change_pct": 2.0},
        ]

        result = SectorStrengthFilter.compute_sector_strength(kline_data)

        assert result[0] == ("BK002", 2.0)
        assert result[1] == ("BK001", -3.0)

    def test_none_change_pct_skipped(self):
        """Rows with None change_pct should be skipped."""
        kline_data = [
            {"sector_code": "BK001", "change_pct": None},
            {"sector_code": "BK002", "change_pct": 5.0},
        ]

        result = SectorStrengthFilter.compute_sector_strength(kline_data)

        assert len(result) == 1
        assert result[0] == ("BK002", 5.0)

    def test_empty_kline_data(self):
        """Empty kline_data should return an empty list."""
        result = SectorStrengthFilter.compute_sector_strength([])

        assert result == []


# ---------------------------------------------------------------------------
# Test: filter_by_sector_strength with sample data
# ---------------------------------------------------------------------------


class TestFilterBySectorStrength:
    """Test filter_by_sector_strength() writes correct fields into stocks_data."""

    def test_writes_sector_rank_trend_name(self):
        """Stocks in ranked sectors get correct sector_rank, sector_trend, sector_name."""
        stocks_data = {
            "SH600001": {"close": 10.0},
            "SH600002": {"close": 20.0},
        }
        sector_ranks = [
            _rank("BK001", "人工智能", rank=1, change_pct=8.0, is_bullish=True),
            _rank("BK002", "银行", rank=2, change_pct=3.0, is_bullish=False),
        ]
        stock_sector_map = {
            "SH600001": ["BK001"],
            "SH600002": ["BK002"],
        }

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] == 1
        assert stocks_data["SH600001"]["sector_trend"] is True
        assert stocks_data["SH600001"]["sector_name"] == "人工智能"

        assert stocks_data["SH600002"]["sector_rank"] == 2
        assert stocks_data["SH600002"]["sector_trend"] is False
        assert stocks_data["SH600002"]["sector_name"] == "银行"

    def test_preserves_existing_fields(self):
        """filter_by_sector_strength should not remove existing fields in stocks_data."""
        stocks_data = {
            "SH600001": {"close": 10.0, "ma_trend": 85},
        }
        sector_ranks = [
            _rank("BK001", "测试板块", rank=1, is_bullish=True),
        ]
        stock_sector_map = {"SH600001": ["BK001"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["close"] == 10.0
        assert stocks_data["SH600001"]["ma_trend"] == 85
        assert stocks_data["SH600001"]["sector_rank"] == 1


# ---------------------------------------------------------------------------
# Test: empty sector_ranks → graceful degradation (Req 5.6)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Test graceful degradation when sector data is unavailable (Req 5.6)."""

    def test_empty_sector_ranks_sets_none(self):
        """When sector_ranks is empty, all stocks get None sector fields."""
        stocks_data = {
            "SH600001": {"close": 10.0},
            "SH600002": {"close": 20.0},
        }
        sector_ranks: list[SectorRankResult] = []
        stock_sector_map = {"SH600001": ["BK001"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        # Even though SH600001 is mapped to BK001, no rank data exists
        assert stocks_data["SH600001"]["sector_rank"] is None
        assert stocks_data["SH600001"]["sector_trend"] is False
        assert stocks_data["SH600001"]["sector_name"] is None

        assert stocks_data["SH600002"]["sector_rank"] is None
        assert stocks_data["SH600002"]["sector_trend"] is False
        assert stocks_data["SH600002"]["sector_name"] is None

    def test_empty_stock_sector_map_sets_none(self):
        """When stock_sector_map is empty, all stocks get None sector fields."""
        stocks_data = {
            "SH600001": {"close": 10.0},
        }
        sector_ranks = [
            _rank("BK001", "人工智能", rank=1, is_bullish=True),
        ]
        stock_sector_map: dict[str, list[str]] = {}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] is None
        assert stocks_data["SH600001"]["sector_trend"] is False
        assert stocks_data["SH600001"]["sector_name"] is None


# ---------------------------------------------------------------------------
# Test: stocks not in any sector → None values
# ---------------------------------------------------------------------------


class TestStocksNotInSector:
    """Test stocks that are not mapped to any sector."""

    def test_unmapped_stock_gets_none(self):
        """A stock not present in stock_sector_map gets None sector fields."""
        stocks_data = {
            "SH600001": {"close": 10.0},
            "SH600099": {"close": 50.0},  # not in any sector
        }
        sector_ranks = [
            _rank("BK001", "人工智能", rank=1, is_bullish=True),
        ]
        stock_sector_map = {
            "SH600001": ["BK001"],
            # SH600099 is not mapped
        }

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] == 1
        assert stocks_data["SH600001"]["sector_trend"] is True

        assert stocks_data["SH600099"]["sector_rank"] is None
        assert stocks_data["SH600099"]["sector_trend"] is False
        assert stocks_data["SH600099"]["sector_name"] is None

    def test_stock_mapped_to_unknown_sector(self):
        """A stock mapped to a sector_code not in sector_ranks gets None."""
        stocks_data = {
            "SH600001": {"close": 10.0},
        }
        sector_ranks = [
            _rank("BK001", "人工智能", rank=1, is_bullish=True),
        ]
        # Stock is mapped to BK999 which is not in sector_ranks
        stock_sector_map = {"SH600001": ["BK999"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] is None
        assert stocks_data["SH600001"]["sector_trend"] is False
        assert stocks_data["SH600001"]["sector_name"] is None


# ---------------------------------------------------------------------------
# Test: top_n filtering (only top_n sectors considered)
# ---------------------------------------------------------------------------


class TestTopNFiltering:
    """Test that filter_by_sector_strength writes full rank info regardless of top_n.

    Note: per the implementation, top_n is used for logging only — all ranks
    are written. The test verifies that stocks in sectors beyond top_n still
    receive their actual rank values.
    """

    def test_stocks_beyond_top_n_still_get_rank(self):
        """Stocks in sectors ranked beyond top_n still get their rank written."""
        stocks_data = {
            "SH600001": {"close": 10.0},
            "SH600002": {"close": 20.0},
            "SH600003": {"close": 30.0},
        }
        sector_ranks = [
            _rank("BK001", "板块A", rank=1, change_pct=10.0, is_bullish=True),
            _rank("BK002", "板块B", rank=2, change_pct=5.0, is_bullish=True),
            _rank("BK003", "板块C", rank=3, change_pct=1.0, is_bullish=False),
        ]
        stock_sector_map = {
            "SH600001": ["BK001"],
            "SH600002": ["BK002"],
            "SH600003": ["BK003"],
        }

        f = SectorStrengthFilter()
        # top_n=2 means only top 2 sectors are "strong", but all get rank written
        f.filter_by_sector_strength(
            stocks_data, sector_ranks, stock_sector_map, top_n=2,
        )

        # All stocks should have their sector rank written
        assert stocks_data["SH600001"]["sector_rank"] == 1
        assert stocks_data["SH600002"]["sector_rank"] == 2
        assert stocks_data["SH600003"]["sector_rank"] == 3


# ---------------------------------------------------------------------------
# Test: stock mapped to multiple sectors → best (lowest) rank used
# ---------------------------------------------------------------------------


class TestMultipleSectorMapping:
    """Test that when a stock belongs to multiple sectors, the best rank is used."""

    def test_best_rank_selected(self):
        """Stock in multiple sectors gets the lowest (best) rank."""
        stocks_data = {
            "SH600001": {"close": 10.0},
        }
        sector_ranks = [
            _rank("BK001", "板块A", rank=1, change_pct=10.0, is_bullish=True),
            _rank("BK002", "板块B", rank=5, change_pct=3.0, is_bullish=False),
            _rank("BK003", "板块C", rank=3, change_pct=6.0, is_bullish=True),
        ]
        # Stock belongs to BK002 (rank=5) and BK003 (rank=3)
        stock_sector_map = {"SH600001": ["BK002", "BK003"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        # Should pick BK003 (rank=3) as the best rank
        assert stocks_data["SH600001"]["sector_rank"] == 3
        assert stocks_data["SH600001"]["sector_trend"] is True
        assert stocks_data["SH600001"]["sector_name"] == "板块C"

    def test_best_rank_when_one_sector_missing(self):
        """Stock mapped to sectors where one is not in sector_ranks."""
        stocks_data = {
            "SH600001": {"close": 10.0},
        }
        sector_ranks = [
            _rank("BK001", "板块A", rank=2, change_pct=5.0, is_bullish=True),
        ]
        # Stock belongs to BK001 (rank=2) and BK999 (not in ranks)
        stock_sector_map = {"SH600001": ["BK999", "BK001"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        # Should pick BK001 (rank=2), ignoring BK999
        assert stocks_data["SH600001"]["sector_rank"] == 2
        assert stocks_data["SH600001"]["sector_trend"] is True
        assert stocks_data["SH600001"]["sector_name"] == "板块A"

    def test_all_mapped_sectors_missing_from_ranks(self):
        """Stock mapped to sectors that are all missing from sector_ranks gets None."""
        stocks_data = {
            "SH600001": {"close": 10.0},
        }
        sector_ranks = [
            _rank("BK001", "板块A", rank=1, is_bullish=True),
        ]
        # Stock mapped to BK888 and BK999, neither in sector_ranks
        stock_sector_map = {"SH600001": ["BK888", "BK999"]}

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] is None
        assert stocks_data["SH600001"]["sector_trend"] is False
        assert stocks_data["SH600001"]["sector_name"] is None

    def test_multiple_stocks_multiple_sectors(self):
        """Multiple stocks each mapped to multiple sectors pick their best rank."""
        stocks_data = {
            "SH600001": {"close": 10.0},
            "SH600002": {"close": 20.0},
        }
        sector_ranks = [
            _rank("BK001", "板块A", rank=1, change_pct=10.0, is_bullish=True),
            _rank("BK002", "板块B", rank=2, change_pct=8.0, is_bullish=True),
            _rank("BK003", "板块C", rank=3, change_pct=5.0, is_bullish=False),
            _rank("BK004", "板块D", rank=4, change_pct=2.0, is_bullish=False),
        ]
        stock_sector_map = {
            "SH600001": ["BK003", "BK001"],  # best = BK001 (rank=1)
            "SH600002": ["BK004", "BK002"],  # best = BK002 (rank=2)
        }

        f = SectorStrengthFilter()
        f.filter_by_sector_strength(stocks_data, sector_ranks, stock_sector_map)

        assert stocks_data["SH600001"]["sector_rank"] == 1
        assert stocks_data["SH600001"]["sector_name"] == "板块A"
        assert stocks_data["SH600001"]["sector_trend"] is True

        assert stocks_data["SH600002"]["sector_rank"] == 2
        assert stocks_data["SH600002"]["sector_name"] == "板块B"
        assert stocks_data["SH600002"]["sector_trend"] is True


# ---------------------------------------------------------------------------
# Test: check_data_freshness 数据新鲜度检查（Req 9）
# ---------------------------------------------------------------------------


class TestCheckDataFreshness:
    """
    板块数据新鲜度检查单元测试。

    覆盖：WARNING 阈值（2 天）、降级阈值（5 天）、周末跳过、自定义阈值。
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
    """

    def test_same_day_no_warning_no_degrade(self):
        """当天数据，stale_days=0，不触发 WARNING 也不降级。"""
        from datetime import date

        # 2024-01-15 是周一
        d = date(2024, 1, 15)
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(d, d)
        )

        assert stale_days == 0
        assert should_warn is False
        assert should_degrade is False

    def test_one_business_day_no_warning(self):
        """延迟 1 个工作日，不触发 WARNING。"""
        from datetime import date

        # 周一 → 周二，1 个工作日
        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 16)  # 周二
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 1
        assert should_warn is False
        assert should_degrade is False

    def test_two_business_days_no_warning(self):
        """延迟恰好 2 个工作日，不触发 WARNING（阈值为 >2）。"""
        from datetime import date

        # 周一 → 周三，2 个工作日
        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 17)  # 周三
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 2
        assert should_warn is False
        assert should_degrade is False

    def test_three_business_days_triggers_warning(self):
        """延迟 3 个工作日，触发 WARNING（>2）。"""
        from datetime import date

        # 周一 → 周四，3 个工作日
        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 18)  # 周四
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 3
        assert should_warn is True
        assert should_degrade is False

    def test_five_business_days_no_degrade(self):
        """延迟恰好 5 个工作日，不触发降级（阈值为 >5）。"""
        from datetime import date

        # 周一 → 下周一，5 个工作日（周二到周五=4，下周一=5）
        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 22)  # 下周一
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 5
        assert should_warn is True
        assert should_degrade is False

    def test_six_business_days_triggers_degrade(self):
        """延迟 6 个工作日，触发降级（>5）。"""
        from datetime import date

        # 周一 → 下周二，6 个工作日
        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 23)  # 下周二
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 6
        assert should_warn is True
        assert should_degrade is True

    def test_weekend_skipped(self):
        """周末不计入工作日。周五 → 下周一 = 0 个工作日（周六周日跳过）。"""
        from datetime import date

        # 周五 → 下周一，中间只有周六和周日
        latest = date(2024, 1, 19)  # 周五
        current = date(2024, 1, 22)  # 下周一
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        # 周六和周日不计入，周一计入 = 1 个工作日
        assert stale_days == 1
        assert should_warn is False
        assert should_degrade is False

    def test_weekend_only_gap(self):
        """周五 → 周六/周日，stale_days=0。"""
        from datetime import date

        latest = date(2024, 1, 19)  # 周五
        current_sat = date(2024, 1, 20)  # 周六
        current_sun = date(2024, 1, 21)  # 周日

        _, _, stale_sat = SectorStrengthFilter.check_data_freshness(
            latest, current_sat,
        )
        _, _, stale_sun = SectorStrengthFilter.check_data_freshness(
            latest, current_sun,
        )

        assert stale_sat == 0
        assert stale_sun == 0

    def test_custom_warning_threshold(self):
        """自定义 WARNING 阈值为 1 天。"""
        from datetime import date

        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 17)  # 周三，2 个工作日
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(
                latest, current,
                warning_threshold_days=1,
            )
        )

        assert stale_days == 2
        assert should_warn is True  # 2 > 1
        assert should_degrade is False

    def test_custom_degrade_threshold(self):
        """自定义降级阈值为 3 天。"""
        from datetime import date

        latest = date(2024, 1, 15)  # 周一
        current = date(2024, 1, 19)  # 周五，4 个工作日
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(
                latest, current,
                degrade_threshold_days=3,
            )
        )

        assert stale_days == 4
        assert should_warn is True  # 4 > 2
        assert should_degrade is True  # 4 > 3

    def test_long_gap_with_multiple_weekends(self):
        """跨越多个周末的长间隔。"""
        from datetime import date

        # 2024-01-15 (周一) → 2024-02-05 (周一)
        # 3 周 = 15 个工作日
        latest = date(2024, 1, 15)
        current = date(2024, 2, 5)
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert stale_days == 15
        assert should_warn is True
        assert should_degrade is True

    def test_degrade_implies_warn(self):
        """降级时必然也触发 WARNING。"""
        from datetime import date

        latest = date(2024, 1, 15)
        current = date(2024, 1, 23)  # 6 个工作日
        should_warn, should_degrade, stale_days = (
            SectorStrengthFilter.check_data_freshness(latest, current)
        )

        assert should_degrade is True
        assert should_warn is True
