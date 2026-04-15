# Feature: forward-adjusted-kline, Property 1-6: 前复权K线计算属性测试
"""
前复权K线计算属性测试（Hypothesis）

测试 adjust_kline_bars 纯函数的 6 个正确性属性：
- Property 1: 前复权公式正确性
- Property 2: 成交量和成交额不变性
- Property 3: 因子回退查找正确性
- Property 4: 前复权价格保序性
- Property 5: 同因子价格变动方向一致性
- Property 6: 恒定因子恒等性
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.models.adjustment_factor import AdjustmentFactor
from app.models.kline import KlineBar
from app.services.data_engine.forward_adjustment import (
    adjust_kline_bars,
    _find_factor_for_date,
    _TWO_PLACES,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 正数 Decimal 价格，范围 [0.01, 10000.00]，2 位小数
_price_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 正数复权因子，范围 [0.001, 100.0]，8 位小数
_factor_decimal = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100.0"),
    places=8,
    allow_nan=False,
    allow_infinity=False,
)

# 正整数成交量
_volume = st.integers(min_value=0, max_value=10_000_000_000)

# 非负 Decimal（成交额）
_amount_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 换手率 0~100
_turnover_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 量比
_vol_ratio_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("50.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 工作日日期生成器（2020-2025 范围）
_trade_date = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2025, 12, 31),
).filter(lambda d: d.weekday() < 5)  # 仅工作日

# 股票代码
_symbol = st.just("000001.SZ")

# K线频率
_freq = st.just("1d")


@st.composite
def _kline_bar(draw, trade_date=None):
    """生成满足 low ≤ open ≤ high 且 low ≤ close ≤ high 的 KlineBar。"""
    low = draw(_price_decimal)
    high = draw(st.decimals(
        min_value=low,
        max_value=max(low + Decimal("0.01"), Decimal("10000.00")),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))
    open_ = draw(st.decimals(
        min_value=low,
        max_value=high,
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))
    close = draw(st.decimals(
        min_value=low,
        max_value=high,
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))

    if trade_date is None:
        trade_date = draw(_trade_date)

    return KlineBar(
        time=datetime.combine(trade_date, datetime.min.time()),
        symbol=draw(_symbol),
        freq=draw(_freq),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=draw(_volume),
        amount=draw(_amount_decimal),
        turnover=draw(_turnover_decimal),
        vol_ratio=draw(_vol_ratio_decimal),
    )


@st.composite
def _bar_and_factor(draw):
    """生成一根 KlineBar 和对应日期的 AdjustmentFactor + latest_factor。"""
    bar = draw(_kline_bar())
    bar_date = bar.time.date()

    daily_factor = draw(_factor_decimal)
    latest_factor = draw(_factor_decimal)

    factor = AdjustmentFactor(
        symbol=bar.symbol,
        trade_date=bar_date,
        adj_type=1,
        adj_factor=daily_factor,
    )

    return bar, factor, daily_factor, latest_factor


@st.composite
def _bar_and_factor_with_exact_match(draw):
    """生成一根 KlineBar 和精确匹配日期的因子列表。"""
    bar = draw(_kline_bar())
    bar_date = bar.time.date()

    daily_factor = draw(_factor_decimal)
    latest_factor = draw(_factor_decimal)

    factor = AdjustmentFactor(
        symbol=bar.symbol,
        trade_date=bar_date,
        adj_type=1,
        adj_factor=daily_factor,
    )

    return bar, [factor], latest_factor


# ---------------------------------------------------------------------------
# Property 1: 前复权公式正确性
# Feature: forward-adjusted-kline, Property 1: 前复权公式正确性
# ---------------------------------------------------------------------------


class TestFormulaCorrectness:
    """Property 1: 前复权公式正确性

    **Validates: Requirements 2.1, 2.3**
    """

    @given(data=_bar_and_factor_with_exact_match())
    @settings(max_examples=200)
    def test_adjusted_ohlc_matches_formula(self, data):
        """
        # Feature: forward-adjusted-kline, Property 1: 前复权公式正确性

        **Validates: Requirements 2.1, 2.3**

        For any valid raw KlineBar and adjustment factor combination,
        each adjusted OHLC price must equal round(raw_price × (daily_factor / latest_factor), 2).
        """
        bar, factors, latest_factor = data

        result = adjust_kline_bars([bar], factors, latest_factor)
        assert len(result) == 1
        adjusted = result[0]

        daily_factor = factors[0].adj_factor
        ratio = daily_factor / latest_factor

        expected_open = (bar.open * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        expected_high = (bar.high * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        expected_low = (bar.low * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        expected_close = (bar.close * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        assert adjusted.open == expected_open, (
            f"open: {adjusted.open} != {expected_open}"
        )
        assert adjusted.high == expected_high, (
            f"high: {adjusted.high} != {expected_high}"
        )
        assert adjusted.low == expected_low, (
            f"low: {adjusted.low} != {expected_low}"
        )
        assert adjusted.close == expected_close, (
            f"close: {adjusted.close} != {expected_close}"
        )


# ---------------------------------------------------------------------------
# Property 2: 成交量和成交额不变性
# Feature: forward-adjusted-kline, Property 2: 成交量和成交额不变性
# ---------------------------------------------------------------------------


class TestVolumeAmountInvariance:
    """Property 2: 成交量和成交额不变性

    **Validates: Requirements 2.2**
    """

    @given(data=_bar_and_factor_with_exact_match())
    @settings(max_examples=200)
    def test_volume_and_amount_unchanged(self, data):
        """
        # Feature: forward-adjusted-kline, Property 2: 成交量和成交额不变性

        **Validates: Requirements 2.2**

        For any raw KlineBar and adjustment factor combination,
        volume and amount must remain identical after forward adjustment.
        """
        bar, factors, latest_factor = data

        result = adjust_kline_bars([bar], factors, latest_factor)
        assert len(result) == 1
        adjusted = result[0]

        assert adjusted.volume == bar.volume, (
            f"volume changed: {adjusted.volume} != {bar.volume}"
        )
        assert adjusted.amount == bar.amount, (
            f"amount changed: {adjusted.amount} != {bar.amount}"
        )
        # Also verify turnover and vol_ratio are unchanged
        assert adjusted.turnover == bar.turnover
        assert adjusted.vol_ratio == bar.vol_ratio


# ---------------------------------------------------------------------------
# Property 3: 因子回退查找正确性
# Feature: forward-adjusted-kline, Property 3: 因子回退查找正确性
# ---------------------------------------------------------------------------


class TestFactorFallbackLookup:
    """Property 3: 因子回退查找正确性

    **Validates: Requirements 2.4**
    """

    @given(
        bar=_kline_bar(),
        factor_value=_factor_decimal,
        latest_factor=_factor_decimal,
        days_before=st.integers(min_value=1, max_value=30),
    )
    @settings(max_examples=200)
    def test_fallback_uses_nearest_preceding_factor(
        self, bar, factor_value, latest_factor, days_before,
    ):
        """
        # Feature: forward-adjusted-kline, Property 3: 因子回退查找正确性

        **Validates: Requirements 2.4**

        When a KlineBar's trade date has no exact factor match,
        the calculator must use the nearest preceding factor.
        """
        bar_date = bar.time.date()
        # Create a factor for a date BEFORE the bar's date (no exact match)
        factor_date = bar_date - timedelta(days=days_before)

        factor = AdjustmentFactor(
            symbol=bar.symbol,
            trade_date=factor_date,
            adj_type=1,
            adj_factor=factor_value,
        )

        result = adjust_kline_bars([bar], [factor], latest_factor)
        assert len(result) == 1
        adjusted = result[0]

        # The adjustment should use factor_value (the nearest preceding factor)
        ratio = factor_value / latest_factor
        expected_close = (bar.close * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        assert adjusted.close == expected_close, (
            f"Fallback factor not used correctly: {adjusted.close} != {expected_close}"
        )

    @given(
        bar=_kline_bar(),
        factor_values=st.lists(_factor_decimal, min_size=2, max_size=5),
        latest_factor=_factor_decimal,
    )
    @settings(max_examples=200)
    def test_fallback_picks_nearest_not_earliest(
        self, bar, factor_values, latest_factor,
    ):
        """
        # Feature: forward-adjusted-kline, Property 3: 因子回退查找正确性

        **Validates: Requirements 2.4**

        When multiple preceding factors exist, the nearest one (closest date
        before the bar date) should be used, not the earliest.
        """
        bar_date = bar.time.date()

        # Create factors at different dates before the bar date
        factors = []
        for i, fv in enumerate(factor_values):
            factor_date = bar_date - timedelta(days=(i + 1) * 5)
            factors.append(AdjustmentFactor(
                symbol=bar.symbol,
                trade_date=factor_date,
                adj_type=1,
                adj_factor=fv,
            ))

        # Sort factors by date ascending (as expected by the function)
        factors.sort(key=lambda f: f.trade_date)

        result = adjust_kline_bars([bar], factors, latest_factor)
        assert len(result) == 1
        adjusted = result[0]

        # The nearest preceding factor is the one with the largest date < bar_date
        nearest_factor = factors[-1]  # Last in sorted order = closest to bar_date
        ratio = nearest_factor.adj_factor / latest_factor
        expected_close = (bar.close * ratio).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        assert adjusted.close == expected_close, (
            f"Did not use nearest preceding factor: {adjusted.close} != {expected_close}"
        )


# ---------------------------------------------------------------------------
# Property 4: 前复权价格保序性
# Feature: forward-adjusted-kline, Property 4: 前复权价格保序性
# ---------------------------------------------------------------------------


class TestOHLCOrderingPreservation:
    """Property 4: 前复权价格保序性

    **Validates: Requirements 2.6, 6.1, 7.8**
    """

    @given(data=_bar_and_factor_with_exact_match())
    @settings(max_examples=200)
    def test_ohlc_ordering_preserved_after_adjustment(self, data):
        """
        # Feature: forward-adjusted-kline, Property 4: 前复权价格保序性

        **Validates: Requirements 2.6, 6.1, 7.8**

        For any valid raw KlineBar where low ≤ open, low ≤ close,
        high ≥ open, high ≥ close, the same ordering must hold
        after forward adjustment.
        """
        bar, factors, latest_factor = data

        # Precondition: raw bar satisfies OHLC ordering
        # (guaranteed by our generator, but verify explicitly)
        assume(bar.low <= bar.open)
        assume(bar.low <= bar.close)
        assume(bar.high >= bar.open)
        assume(bar.high >= bar.close)

        result = adjust_kline_bars([bar], factors, latest_factor)
        assert len(result) == 1
        adjusted = result[0]

        assert adjusted.low <= adjusted.open, (
            f"low > open after adjustment: {adjusted.low} > {adjusted.open}"
        )
        assert adjusted.low <= adjusted.close, (
            f"low > close after adjustment: {adjusted.low} > {adjusted.close}"
        )
        assert adjusted.high >= adjusted.open, (
            f"high < open after adjustment: {adjusted.high} < {adjusted.open}"
        )
        assert adjusted.high >= adjusted.close, (
            f"high < close after adjustment: {adjusted.high} < {adjusted.close}"
        )


# ---------------------------------------------------------------------------
# Property 5: 同因子价格变动方向一致性
# Feature: forward-adjusted-kline, Property 5: 同因子价格变动方向一致性
# ---------------------------------------------------------------------------


class TestSameFactorDirectionConsistency:
    """Property 5: 同因子价格变动方向一致性

    **Validates: Requirements 6.2**
    """

    @given(
        close1=_price_decimal,
        close2=_price_decimal,
        shared_factor=_factor_decimal,
        latest_factor=_factor_decimal,
        base_date=_trade_date,
    )
    @settings(max_examples=200)
    def test_price_direction_preserved_with_same_factor(
        self, close1, close2, shared_factor, latest_factor, base_date,
    ):
        """
        # Feature: forward-adjusted-kline, Property 5: 同因子价格变动方向一致性

        **Validates: Requirements 6.2**

        For any two consecutive KlineBars sharing the same adjustment factor,
        if close[i+1] > close[i] in raw data, then adjusted_close[i+1] > adjusted_close[i]
        (and vice versa).
        """
        assume(close1 != close2)  # Need distinct prices to test direction

        date1 = base_date
        date2 = base_date + timedelta(days=1)
        # Skip weekends
        while date2.weekday() >= 5:
            date2 += timedelta(days=1)

        # Build two bars with the same factor
        bar1 = KlineBar(
            time=datetime.combine(date1, datetime.min.time()),
            symbol="000001.SZ",
            freq="1d",
            open=close1, high=max(close1, close2), low=min(close1, close2), close=close1,
            volume=1000, amount=Decimal("10000.00"),
            turnover=Decimal("1.00"), vol_ratio=Decimal("1.00"),
        )
        bar2 = KlineBar(
            time=datetime.combine(date2, datetime.min.time()),
            symbol="000001.SZ",
            freq="1d",
            open=close2, high=max(close1, close2), low=min(close1, close2), close=close2,
            volume=1000, amount=Decimal("10000.00"),
            turnover=Decimal("1.00"), vol_ratio=Decimal("1.00"),
        )

        # Both bars share the same factor
        factor1 = AdjustmentFactor(
            symbol="000001.SZ", trade_date=date1, adj_type=1, adj_factor=shared_factor,
        )
        factor2 = AdjustmentFactor(
            symbol="000001.SZ", trade_date=date2, adj_type=1, adj_factor=shared_factor,
        )

        result = adjust_kline_bars([bar1, bar2], [factor1, factor2], latest_factor)
        assert len(result) == 2

        adj_close1 = result[0].close
        adj_close2 = result[1].close

        if close1 < close2:
            assert adj_close1 <= adj_close2, (
                f"Direction not preserved: raw {close1} < {close2}, "
                f"but adjusted {adj_close1} > {adj_close2}"
            )
        elif close1 > close2:
            assert adj_close1 >= adj_close2, (
                f"Direction not preserved: raw {close1} > {close2}, "
                f"but adjusted {adj_close1} < {adj_close2}"
            )


# ---------------------------------------------------------------------------
# Property 6: 恒定因子恒等性
# Feature: forward-adjusted-kline, Property 6: 恒定因子恒等性
# ---------------------------------------------------------------------------


class TestConstantFactorIdentity:
    """Property 6: 恒定因子恒等性

    **Validates: Requirements 6.3**
    """

    @given(
        bar=_kline_bar(),
        constant_factor=_factor_decimal,
    )
    @settings(max_examples=200)
    def test_constant_factor_produces_identity(self, bar, constant_factor):
        """
        # Feature: forward-adjusted-kline, Property 6: 恒定因子恒等性

        **Validates: Requirements 6.3**

        When all daily factors equal the latest factor (no ex-dividend events),
        adjusted OHLC prices must be identical to raw prices.
        """
        bar_date = bar.time.date()

        factor = AdjustmentFactor(
            symbol=bar.symbol,
            trade_date=bar_date,
            adj_type=1,
            adj_factor=constant_factor,
        )

        # latest_factor == daily_factor → ratio = 1 → prices unchanged
        result = adjust_kline_bars([bar], [factor], constant_factor)
        assert len(result) == 1
        adjusted = result[0]

        assert adjusted.open == bar.open, (
            f"open changed with constant factor: {adjusted.open} != {bar.open}"
        )
        assert adjusted.high == bar.high, (
            f"high changed with constant factor: {adjusted.high} != {bar.high}"
        )
        assert adjusted.low == bar.low, (
            f"low changed with constant factor: {adjusted.low} != {bar.low}"
        )
        assert adjusted.close == bar.close, (
            f"close changed with constant factor: {adjusted.close} != {bar.close}"
        )

    @given(
        bars_count=st.integers(min_value=2, max_value=10),
        constant_factor=_factor_decimal,
        base_date=_trade_date,
    )
    @settings(max_examples=100)
    def test_multiple_bars_constant_factor_identity(
        self, bars_count, constant_factor, base_date,
    ):
        """
        # Feature: forward-adjusted-kline, Property 6: 恒定因子恒等性

        **Validates: Requirements 6.3**

        Multiple bars with the same constant factor should all remain unchanged.
        """
        bars = []
        factors = []
        current_date = base_date

        for _ in range(bars_count):
            # Skip weekends
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)

            bar = KlineBar(
                time=datetime.combine(current_date, datetime.min.time()),
                symbol="000001.SZ",
                freq="1d",
                open=Decimal("10.50"),
                high=Decimal("11.00"),
                low=Decimal("10.00"),
                close=Decimal("10.80"),
                volume=5000,
                amount=Decimal("50000.00"),
                turnover=Decimal("2.50"),
                vol_ratio=Decimal("1.20"),
            )
            bars.append(bar)

            factors.append(AdjustmentFactor(
                symbol="000001.SZ",
                trade_date=current_date,
                adj_type=1,
                adj_factor=constant_factor,
            ))

            current_date += timedelta(days=1)

        result = adjust_kline_bars(bars, factors, constant_factor)
        assert len(result) == len(bars)

        for original, adjusted in zip(bars, result):
            assert adjusted.open == original.open
            assert adjusted.high == original.high
            assert adjusted.low == original.low
            assert adjusted.close == original.close
