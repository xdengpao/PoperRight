"""
日期索引属性测试（Hypothesis）

Property 7: 日期索引结构不变量
Property 8: 日期索引查找正确性
Property 9: 二分查找等价性

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import KlineBar
from app.services.backtest_engine import (
    KlineDateIndex,
    _build_date_index,
    _get_bars_up_to,
)

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------


def _make_bar(d: date, symbol: str = "TEST") -> KlineBar:
    """创建一个最小化的 KlineBar 用于测试"""
    return KlineBar(
        time=datetime(d.year, d.month, d.day, 9, 30),
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


# Generate sorted unique dates, then build KlineBar lists
_unique_dates = st.lists(
    st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 12, 31)),
    min_size=1,
    max_size=50,
    unique=True,
).map(sorted)

# Generate symbol names
_symbols = st.sampled_from(["SH600000", "SZ000001", "SH601318", "SZ300750"])


# Build kline_data: dict[str, list[KlineBar]] with 1-3 stocks, each with unique sorted dates
_kline_data = st.dictionaries(
    keys=_symbols,
    values=_unique_dates.map(lambda dates: [_make_bar(d) for d in dates]),
    min_size=1,
    max_size=3,
)

# For Property 9: generate a trade_date that may or may not be in the bars
_trade_date = st.dates(min_value=date(2019, 6, 1), max_value=date(2026, 6, 30))



# ---------------------------------------------------------------------------
# Property 7: 日期索引结构不变量
# ---------------------------------------------------------------------------


class TestDateIndexStructureInvariant:
    """Property 7: 日期索引结构不变量

    *For any* kline_data, `_build_date_index(kline_data)` returns dict with:
    - Keys == kline_data keys
    - For each stock: sorted_dates is strictly increasing
    - len(date_to_idx) == len(kline_data[symbol]) (when no duplicate dates)

    **Validates: Requirements 4.1, 4.2, 4.3**
    """

    @given(kline_data=_kline_data)
    @settings(max_examples=200)
    def test_keys_match_kline_data(self, kline_data: dict[str, list[KlineBar]]):
        """Returned dict keys must equal kline_data keys.

        **Validates: Requirements 4.1**
        """
        result = _build_date_index(kline_data)
        assert set(result.keys()) == set(kline_data.keys())

    @given(kline_data=_kline_data)
    @settings(max_examples=200)
    def test_sorted_dates_strictly_increasing(
        self, kline_data: dict[str, list[KlineBar]]
    ):
        """For each stock, sorted_dates must be strictly increasing.

        **Validates: Requirements 4.2**
        """
        result = _build_date_index(kline_data)
        for symbol, index in result.items():
            for i in range(1, len(index.sorted_dates)):
                assert index.sorted_dates[i] > index.sorted_dates[i - 1], (
                    f"{symbol}: sorted_dates not strictly increasing at position {i}: "
                    f"{index.sorted_dates[i - 1]} >= {index.sorted_dates[i]}"
                )

    @given(kline_data=_kline_data)
    @settings(max_examples=200)
    def test_date_to_idx_length_equals_bars_length(
        self, kline_data: dict[str, list[KlineBar]]
    ):
        """When bars have unique dates, len(date_to_idx) == len(bars).

        Our generator produces unique dates, so this always holds.

        **Validates: Requirements 4.3**
        """
        result = _build_date_index(kline_data)
        for symbol, index in result.items():
            bars = kline_data[symbol]
            assert len(index.date_to_idx) == len(bars), (
                f"{symbol}: len(date_to_idx)={len(index.date_to_idx)} "
                f"!= len(bars)={len(bars)}"
            )


# ---------------------------------------------------------------------------
# Property 8: 日期索引查找正确性
# ---------------------------------------------------------------------------


class TestDateIndexLookupCorrectness:
    """Property 8: 日期索引查找正确性

    *For any* stock's bars and KlineDateIndex, for any date d in date_to_idx:
    bars[date_to_idx[d]].time.date() == d

    **Validates: Requirement 4.4**
    """

    @given(kline_data=_kline_data)
    @settings(max_examples=200)
    def test_date_to_idx_maps_to_correct_bar(
        self, kline_data: dict[str, list[KlineBar]]
    ):
        """For every date d in date_to_idx, bars[date_to_idx[d]].time.date() == d.

        **Validates: Requirement 4.4**
        """
        result = _build_date_index(kline_data)
        for symbol, index in result.items():
            bars = kline_data[symbol]
            for d, idx in index.date_to_idx.items():
                assert bars[idx].time.date() == d, (
                    f"{symbol}: bars[{idx}].time.date()="
                    f"{bars[idx].time.date()} != {d}"
                )


# ---------------------------------------------------------------------------
# Property 9: 二分查找等价性
# ---------------------------------------------------------------------------


def _naive_get_bars_up_to(bars: list[KlineBar], trade_date: date) -> int:
    """朴素线性扫描：返回 bars 中 date <= trade_date 的最后一个索引，无匹配返回 -1。"""
    result = -1
    for i, b in enumerate(bars):
        if b.time.date() <= trade_date:
            result = i
    return result


class TestBinarySearchEquivalence:
    """Property 9: 二分查找等价性

    *For any* bars, KlineDateIndex, and trade_date:
    `_get_bars_up_to(index, trade_date)` returns same result as naive linear scan.

    **Validates: Requirements 4.5, 4.6**
    """

    @given(kline_data=_kline_data, trade_date=_trade_date)
    @settings(max_examples=300)
    def test_bisect_matches_linear_scan(
        self,
        kline_data: dict[str, list[KlineBar]],
        trade_date: date,
    ):
        """Binary search result must equal naive linear scan result.

        **Validates: Requirements 4.5, 4.6**
        """
        indexes = _build_date_index(kline_data)
        for symbol, index in indexes.items():
            bars = kline_data[symbol]
            bisect_result = _get_bars_up_to(index, trade_date)
            naive_result = _naive_get_bars_up_to(bars, trade_date)
            assert bisect_result == naive_result, (
                f"{symbol}: bisect={bisect_result} != naive={naive_result} "
                f"for trade_date={trade_date}, "
                f"dates={[b.time.date() for b in bars]}"
            )
