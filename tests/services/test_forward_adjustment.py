"""
adjust_kline_bars 单元测试

测试边界情况和具体数值验证：
- 空因子列表 → 返回原始数据
- latest_factor = 0 → 返回原始数据
- 单根K线 + 单个因子 → 验证具体数值
- 多根K线 + 部分日期缺失因子 → 验证回退逻辑

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.adjustment_factor import AdjustmentFactor
from app.models.kline import KlineBar
from app.services.data_engine.forward_adjustment import adjust_kline_bars


# ---------------------------------------------------------------------------
# 辅助工厂函数
# ---------------------------------------------------------------------------


def _make_bar(
    trade_date: date,
    open_: Decimal = Decimal("10.00"),
    high: Decimal = Decimal("11.00"),
    low: Decimal = Decimal("9.00"),
    close: Decimal = Decimal("10.50"),
    volume: int = 10000,
    amount: Decimal = Decimal("100000.00"),
) -> KlineBar:
    return KlineBar(
        time=datetime.combine(trade_date, datetime.min.time()),
        symbol="000001.SZ",
        freq="1d",
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        turnover=Decimal("2.50"),
        vol_ratio=Decimal("1.20"),
    )


def _make_factor(trade_date: date, adj_factor: Decimal) -> AdjustmentFactor:
    return AdjustmentFactor(
        symbol="000001.SZ",
        trade_date=trade_date,
        adj_type=1,
        adj_factor=adj_factor,
    )


# ---------------------------------------------------------------------------
# Test: 空因子列表返回原始 bars
# ---------------------------------------------------------------------------


class TestEmptyFactors:
    """Requirements: 2.5"""

    def test_empty_factors_returns_original_bars(self):
        """空因子列表应返回原始K线数据不做调整。"""
        bar = _make_bar(date(2024, 1, 15))
        result = adjust_kline_bars([bar], [], Decimal("1.0"))

        assert len(result) == 1
        assert result[0].open == bar.open
        assert result[0].high == bar.high
        assert result[0].low == bar.low
        assert result[0].close == bar.close
        assert result[0].volume == bar.volume
        assert result[0].amount == bar.amount

    def test_empty_factors_returns_new_list(self):
        """即使不做调整，也应返回新列表（不修改原始列表）。"""
        bar = _make_bar(date(2024, 1, 15))
        original_list = [bar]
        result = adjust_kline_bars(original_list, [], Decimal("1.0"))

        assert len(result) == 1
        assert result is not original_list


# ---------------------------------------------------------------------------
# Test: latest_factor = 0 返回原始 bars
# ---------------------------------------------------------------------------


class TestZeroLatestFactor:
    """Requirements: 2.5"""

    def test_zero_latest_factor_returns_original_bars(self):
        """最新复权因子为零时应返回原始K线数据不做调整。"""
        bar = _make_bar(date(2024, 1, 15))
        factor = _make_factor(date(2024, 1, 15), Decimal("1.5"))

        result = adjust_kline_bars([bar], [factor], Decimal("0"))

        assert len(result) == 1
        assert result[0].open == bar.open
        assert result[0].close == bar.close
        assert result[0].volume == bar.volume


# ---------------------------------------------------------------------------
# Test: 单根K线 + 单个因子 → 验证具体数值
# ---------------------------------------------------------------------------


class TestSingleBarSingleFactor:
    """Requirements: 2.1, 2.2, 2.3"""

    def test_single_bar_exact_numeric_result(self):
        """单根K线 + 单个因子，验证具体计算结果。

        raw_open=10.00, daily_factor=0.8, latest_factor=1.0
        ratio = 0.8 / 1.0 = 0.8
        adjusted_open = round(10.00 * 0.8, 2) = 8.00
        adjusted_high = round(11.00 * 0.8, 2) = 8.80
        adjusted_low  = round(9.00 * 0.8, 2) = 7.20
        adjusted_close = round(10.50 * 0.8, 2) = 8.40
        """
        bar = _make_bar(
            date(2024, 1, 15),
            open_=Decimal("10.00"),
            high=Decimal("11.00"),
            low=Decimal("9.00"),
            close=Decimal("10.50"),
            volume=10000,
            amount=Decimal("100000.00"),
        )
        factor = _make_factor(date(2024, 1, 15), Decimal("0.8"))
        latest_factor = Decimal("1.0")

        result = adjust_kline_bars([bar], [factor], latest_factor)

        assert len(result) == 1
        adjusted = result[0]

        assert adjusted.open == Decimal("8.00")
        assert adjusted.high == Decimal("8.80")
        assert adjusted.low == Decimal("7.20")
        assert adjusted.close == Decimal("8.40")

        # volume and amount unchanged
        assert adjusted.volume == 10000
        assert adjusted.amount == Decimal("100000.00")

    def test_single_bar_rounding(self):
        """验证四舍五入到两位小数。

        raw_open=10.00, daily_factor=0.333, latest_factor=1.0
        ratio = 0.333 / 1.0 = 0.333
        adjusted_open = round(10.00 * 0.333, 2) = round(3.33, 2) = 3.33
        """
        bar = _make_bar(
            date(2024, 1, 15),
            open_=Decimal("10.00"),
            high=Decimal("10.00"),
            low=Decimal("10.00"),
            close=Decimal("10.00"),
        )
        factor = _make_factor(date(2024, 1, 15), Decimal("0.33300000"))
        latest_factor = Decimal("1.00000000")

        result = adjust_kline_bars([bar], [factor], latest_factor)
        adjusted = result[0]

        assert adjusted.open == Decimal("3.33")

    def test_single_bar_preserves_non_price_fields(self):
        """验证非价格字段（symbol, freq, time, turnover, vol_ratio 等）保持不变。"""
        bar = _make_bar(date(2024, 1, 15))
        factor = _make_factor(date(2024, 1, 15), Decimal("0.5"))

        result = adjust_kline_bars([bar], [factor], Decimal("1.0"))
        adjusted = result[0]

        assert adjusted.symbol == bar.symbol
        assert adjusted.freq == bar.freq
        assert adjusted.time == bar.time
        assert adjusted.turnover == bar.turnover
        assert adjusted.vol_ratio == bar.vol_ratio


# ---------------------------------------------------------------------------
# Test: 多根K线 + 部分日期缺失因子 → 验证回退逻辑
# ---------------------------------------------------------------------------


class TestMultipleBarsPartialCoverage:
    """Requirements: 2.1, 2.4"""

    def test_fallback_to_preceding_factor(self):
        """K线日期无精确因子匹配时，使用最近前一日的因子。

        bar1: 2024-01-15, factor exists for 2024-01-15 (factor=0.8)
        bar2: 2024-01-16, NO factor for 2024-01-16, should use 2024-01-15's factor (0.8)
        bar3: 2024-01-17, factor exists for 2024-01-17 (factor=0.9)
        """
        bar1 = _make_bar(date(2024, 1, 15), close=Decimal("10.00"))
        bar2 = _make_bar(date(2024, 1, 16), close=Decimal("10.00"))
        bar3 = _make_bar(date(2024, 1, 17), close=Decimal("10.00"))

        factor1 = _make_factor(date(2024, 1, 15), Decimal("0.80000000"))
        factor3 = _make_factor(date(2024, 1, 17), Decimal("0.90000000"))

        latest_factor = Decimal("1.00000000")

        result = adjust_kline_bars(
            [bar1, bar2, bar3],
            [factor1, factor3],  # No factor for 2024-01-16
            latest_factor,
        )

        assert len(result) == 3

        # bar1: uses factor 0.8 → close = 10.00 * 0.8 = 8.00
        assert result[0].close == Decimal("8.00")

        # bar2: no exact match, falls back to 2024-01-15's factor (0.8)
        assert result[1].close == Decimal("8.00")

        # bar3: uses factor 0.9 → close = 10.00 * 0.9 = 9.00
        assert result[2].close == Decimal("9.00")

    def test_bar_before_all_factors_keeps_original(self):
        """K线日期早于所有因子日期时，保持原始价格。"""
        bar = _make_bar(date(2024, 1, 10), close=Decimal("10.00"))
        factor = _make_factor(date(2024, 1, 15), Decimal("0.80000000"))

        result = adjust_kline_bars([bar], [factor], Decimal("1.00000000"))

        assert len(result) == 1
        # No preceding factor available → original price preserved
        assert result[0].close == Decimal("10.00")

    def test_mixed_coverage_scenario(self):
        """混合场景：部分K线有精确因子，部分需要回退，部分无因子。

        Factors: 2024-01-12 (0.7), 2024-01-15 (0.8)
        Bars:    2024-01-10 (before all factors → original)
                 2024-01-13 (falls back to 2024-01-12 → 0.7)
                 2024-01-15 (exact match → 0.8)
        """
        bars = [
            _make_bar(date(2024, 1, 10), close=Decimal("10.00")),
            _make_bar(date(2024, 1, 13), close=Decimal("10.00")),
            _make_bar(date(2024, 1, 15), close=Decimal("10.00")),
        ]
        factors = [
            _make_factor(date(2024, 1, 12), Decimal("0.70000000")),
            _make_factor(date(2024, 1, 15), Decimal("0.80000000")),
        ]
        latest_factor = Decimal("1.00000000")

        result = adjust_kline_bars(bars, factors, latest_factor)

        assert len(result) == 3
        # bar at 01-10: before all factors → original
        assert result[0].close == Decimal("10.00")
        # bar at 01-13: falls back to 01-12 factor (0.7) → 10.00 * 0.7 = 7.00
        assert result[1].close == Decimal("7.00")
        # bar at 01-15: exact match (0.8) → 10.00 * 0.8 = 8.00
        assert result[2].close == Decimal("8.00")
