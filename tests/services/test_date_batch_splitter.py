"""DateBatchSplitter 单元测试。

测试场景：
- 基本拆分（30天/10天步长→3个子区间）
- 单日范围（start == end → 1个子区间）
- 范围小于步长（5天/30天步长→1个子区间）
- 步长为1逐日拆分
- 跨月/跨年边界
- 无效输入（start > end → ValueError、chunk_days <= 0 → ValueError）

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import pytest

from app.services.data_engine.date_batch_splitter import DateBatchSplitter


# ---------------------------------------------------------------------------
# 基本拆分 (Req 2.1, 2.2, 2.3)
# ---------------------------------------------------------------------------


class TestBasicSplit:
    """验证基本日期范围拆分逻辑"""

    def test_30_day_range_with_10_day_chunk_yields_3_chunks(self):
        """30天范围 / 10天步长 → 3个子区间"""
        # 20230101 ~ 20230130 = 30天
        result = DateBatchSplitter.split("20230101", "20230130", 10)
        assert len(result) == 3

    def test_30_day_range_first_chunk_starts_at_start_date(self):
        result = DateBatchSplitter.split("20230101", "20230130", 10)
        assert result[0][0] == "20230101"

    def test_30_day_range_last_chunk_ends_at_end_date(self):
        result = DateBatchSplitter.split("20230101", "20230130", 10)
        assert result[-1][1] == "20230130"

    def test_30_day_range_chunks_are_contiguous(self):
        """相邻子区间无间隙：前一个 chunk_end + 1天 == 下一个 chunk_start"""
        from datetime import datetime, timedelta

        result = DateBatchSplitter.split("20230101", "20230130", 10)
        for i in range(len(result) - 1):
            prev_end = datetime.strptime(result[i][1], "%Y%m%d").date()
            next_start = datetime.strptime(result[i + 1][0], "%Y%m%d").date()
            assert next_start - prev_end == timedelta(days=1)

    def test_each_chunk_span_does_not_exceed_chunk_days(self):
        """每个子区间跨度不超过 chunk_days"""
        from datetime import datetime

        result = DateBatchSplitter.split("20230101", "20230130", 10)
        for chunk_start, chunk_end in result:
            start = datetime.strptime(chunk_start, "%Y%m%d").date()
            end = datetime.strptime(chunk_end, "%Y%m%d").date()
            span = (end - start).days + 1
            assert span <= 10


# ---------------------------------------------------------------------------
# 单日范围 (Req 2.4)
# ---------------------------------------------------------------------------


class TestSingleDayRange:
    """验证 start_date == end_date 时返回单个子区间"""

    def test_single_day_returns_one_chunk(self):
        result = DateBatchSplitter.split("20230615", "20230615", 10)
        assert len(result) == 1

    def test_single_day_chunk_matches_input(self):
        result = DateBatchSplitter.split("20230615", "20230615", 10)
        assert result[0] == ("20230615", "20230615")

    def test_single_day_with_chunk_days_1(self):
        result = DateBatchSplitter.split("20230615", "20230615", 1)
        assert len(result) == 1
        assert result[0] == ("20230615", "20230615")


# ---------------------------------------------------------------------------
# 范围小于步长 (Req 2.5)
# ---------------------------------------------------------------------------


class TestRangeSmallerThanChunk:
    """验证日期范围小于 chunk_days 时返回单个子区间"""

    def test_5_day_range_with_30_day_chunk_returns_one_chunk(self):
        """5天范围 / 30天步长 → 1个子区间"""
        result = DateBatchSplitter.split("20230101", "20230105", 30)
        assert len(result) == 1

    def test_5_day_range_chunk_covers_full_range(self):
        result = DateBatchSplitter.split("20230101", "20230105", 30)
        assert result[0] == ("20230101", "20230105")


# ---------------------------------------------------------------------------
# 步长为1逐日拆分 (Req 2.1, 2.2)
# ---------------------------------------------------------------------------


class TestChunkDaysOne:
    """验证 chunk_days=1 时逐日拆分"""

    def test_chunk_days_1_yields_one_chunk_per_day(self):
        """5天范围 / 步长1 → 5个子区间"""
        result = DateBatchSplitter.split("20230101", "20230105", 1)
        assert len(result) == 5

    def test_chunk_days_1_each_chunk_is_single_day(self):
        result = DateBatchSplitter.split("20230101", "20230105", 1)
        for chunk_start, chunk_end in result:
            assert chunk_start == chunk_end

    def test_chunk_days_1_covers_all_dates(self):
        result = DateBatchSplitter.split("20230101", "20230105", 1)
        expected_dates = [
            ("20230101", "20230101"),
            ("20230102", "20230102"),
            ("20230103", "20230103"),
            ("20230104", "20230104"),
            ("20230105", "20230105"),
        ]
        assert result == expected_dates


# ---------------------------------------------------------------------------
# 跨月/跨年边界 (Req 2.3)
# ---------------------------------------------------------------------------


class TestCrossMonthAndYearBoundaries:
    """验证跨月和跨年边界的正确处理"""

    def test_cross_month_boundary(self):
        """跨月拆分：1月28日到2月5日，步长5天"""
        result = DateBatchSplitter.split("20230128", "20230205", 5)
        # 1/28-2/1 (5天), 2/2-2/5 (4天)
        assert len(result) == 2
        assert result[0] == ("20230128", "20230201")
        assert result[1] == ("20230202", "20230205")

    def test_cross_year_boundary(self):
        """跨年拆分：12月29日到1月3日，步长3天"""
        result = DateBatchSplitter.split("20231229", "20240103", 3)
        # 12/29-12/31 (3天), 1/1-1/3 (3天)
        assert len(result) == 2
        assert result[0] == ("20231229", "20231231")
        assert result[1] == ("20240101", "20240103")

    def test_february_leap_year(self):
        """闰年2月边界：2月27日到3月2日，步长3天"""
        result = DateBatchSplitter.split("20240227", "20240302", 3)
        # 2/27-2/29 (3天), 3/1-3/2 (2天)
        assert len(result) == 2
        assert result[0] == ("20240227", "20240229")
        assert result[1] == ("20240301", "20240302")


# ---------------------------------------------------------------------------
# 无效输入 (Req 2.1)
# ---------------------------------------------------------------------------


class TestInvalidInput:
    """验证无效输入抛出 ValueError"""

    def test_start_after_end_raises_value_error(self):
        """start_date > end_date → ValueError"""
        with pytest.raises(ValueError, match="不能大于"):
            DateBatchSplitter.split("20230201", "20230101", 10)

    def test_chunk_days_zero_raises_value_error(self):
        """chunk_days == 0 → ValueError"""
        with pytest.raises(ValueError, match="正整数"):
            DateBatchSplitter.split("20230101", "20230130", 0)

    def test_chunk_days_negative_raises_value_error(self):
        """chunk_days < 0 → ValueError"""
        with pytest.raises(ValueError, match="正整数"):
            DateBatchSplitter.split("20230101", "20230130", -5)
