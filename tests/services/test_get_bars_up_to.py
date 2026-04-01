"""
_get_bars_up_to 单元测试

覆盖：
- 正常查找：返回 <= trade_date 的最后一个 bar 索引
- 精确匹配：trade_date 恰好等于某个 bar 的日期
- 无匹配：所有 bar 日期 > trade_date → 返回 -1
- 空索引：sorted_dates 为空 → 返回 -1
- trade_date 晚于所有日期：返回最后一个 bar 索引
- 日期间隙：trade_date 落在两个 bar 日期之间

Requirements: 4.5, 4.6, 4.7
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.schemas import KlineBar
from app.services.backtest_engine import (
    KlineDateIndex,
    _build_date_index,
    _get_bars_up_to,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bar(d: date, symbol: str = "TEST") -> KlineBar:
    """创建一个最小化的 KlineBar 用于测试"""
    return KlineBar(
        time=datetime(d.year, d.month, d.day),
        symbol=symbol,
        freq="1d",
        open=Decimal("10.00"),
        high=Decimal("10.50"),
        low=Decimal("9.50"),
        close=Decimal("10.20"),
        volume=1000,
        amount=Decimal("10200"),
        turnover=Decimal("1.5"),
        vol_ratio=Decimal("1.0"),
    )


def _make_index(dates: list[date]) -> KlineDateIndex:
    """从日期列表构建 KlineDateIndex（索引与列表位置一致）"""
    date_to_idx = {d: i for i, d in enumerate(dates)}
    sorted_dates = sorted(date_to_idx.keys())
    return KlineDateIndex(date_to_idx=date_to_idx, sorted_dates=sorted_dates)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetBarsUpTo:
    """_get_bars_up_to 二分查找函数测试"""

    def test_exact_match(self):
        """trade_date 恰好等于某个 bar 日期时，返回该 bar 的索引"""
        index = _make_index([date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)])
        assert _get_bars_up_to(index, date(2024, 1, 2)) == 1

    def test_between_dates(self):
        """trade_date 落在两个日期之间时，返回前一个日期的索引"""
        index = _make_index([date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 5)])
        # 1月2日在1月1日和1月3日之间，应返回1月1日的索引 0
        assert _get_bars_up_to(index, date(2024, 1, 2)) == 0

    def test_before_all_dates_returns_minus_one(self):
        """trade_date 早于所有 bar 日期时，返回 -1"""
        index = _make_index([date(2024, 1, 2), date(2024, 1, 3)])
        assert _get_bars_up_to(index, date(2024, 1, 1)) == -1

    def test_after_all_dates(self):
        """trade_date 晚于所有 bar 日期时，返回最后一个 bar 的索引"""
        index = _make_index([date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)])
        assert _get_bars_up_to(index, date(2024, 12, 31)) == 2

    def test_empty_index_returns_minus_one(self):
        """空索引时返回 -1"""
        index = KlineDateIndex(date_to_idx={}, sorted_dates=[])
        assert _get_bars_up_to(index, date(2024, 1, 1)) == -1

    def test_single_date_match(self):
        """只有一个日期且匹配时，返回索引 0"""
        index = _make_index([date(2024, 6, 15)])
        assert _get_bars_up_to(index, date(2024, 6, 15)) == 0

    def test_single_date_after(self):
        """只有一个日期且 trade_date 在其之后，返回索引 0"""
        index = _make_index([date(2024, 6, 15)])
        assert _get_bars_up_to(index, date(2024, 6, 20)) == 0

    def test_single_date_before(self):
        """只有一个日期且 trade_date 在其之前，返回 -1"""
        index = _make_index([date(2024, 6, 15)])
        assert _get_bars_up_to(index, date(2024, 6, 10)) == -1

    def test_last_date_exact_match(self):
        """trade_date 恰好等于最后一个日期时，返回最后一个索引"""
        index = _make_index([date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)])
        assert _get_bars_up_to(index, date(2024, 1, 3)) == 2

    def test_with_build_date_index(self):
        """通过 _build_date_index 构建索引后使用 _get_bars_up_to"""
        bars = [
            _make_bar(date(2024, 3, 1)),
            _make_bar(date(2024, 3, 4)),
            _make_bar(date(2024, 3, 5)),
            _make_bar(date(2024, 3, 6)),
        ]
        indexes = _build_date_index({"TEST": bars})
        idx = indexes["TEST"]

        # 3月5日精确匹配 → 索引 2
        assert _get_bars_up_to(idx, date(2024, 3, 5)) == 2
        # 3月3日（周末）落在3月1日和3月4日之间 → 索引 0
        assert _get_bars_up_to(idx, date(2024, 3, 3)) == 0
        # 2月28日早于所有日期 → -1
        assert _get_bars_up_to(idx, date(2024, 2, 28)) == -1
        # 3月10日晚于所有日期 → 索引 3
        assert _get_bars_up_to(idx, date(2024, 3, 10)) == 3

    def test_returns_bar_index_not_sorted_dates_position(self):
        """验证返回的是 date_to_idx 中的 bar 索引，而非 sorted_dates 中的位置"""
        # 模拟 date_to_idx 中索引与 sorted_dates 位置不同的情况
        # （例如重复日期导致覆盖后的间隙）
        index = KlineDateIndex(
            date_to_idx={
                date(2024, 1, 1): 0,
                date(2024, 1, 3): 5,  # bar 索引为 5，不等于 sorted_dates 位置 1
                date(2024, 1, 5): 10,
            },
            sorted_dates=[date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 5)],
        )
        # trade_date=1月4日 → 最后 <= 的日期是1月3日 → bar 索引应为 5
        assert _get_bars_up_to(index, date(2024, 1, 4)) == 5
        # trade_date=1月5日 → 精确匹配 → bar 索引应为 10
        assert _get_bars_up_to(index, date(2024, 1, 5)) == 10
