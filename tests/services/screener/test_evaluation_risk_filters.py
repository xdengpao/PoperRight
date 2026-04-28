"""风控过滤逻辑测试（需求 10）

验证 NORMAL/CAUTION/DANGER 三级响应和边界值过滤。
"""

from decimal import Decimal

import pytest

from app.core.schemas import (
    MarketRiskLevel,
    RiskLevel,
    ScreenItem,
    SignalDetail,
    SignalCategory,
)
from app.services.screener.screen_executor import ScreenExecutor


def _make_item(symbol: str, trend_score: float, daily_change_pct: float = 0.0) -> ScreenItem:
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal("10.00"),
        trend_score=trend_score,
        risk_level=RiskLevel.LOW,
    )


class TestMarketRiskLevels:
    """验证大盘风控三级响应。"""

    def test_normal_no_filtering(self):
        """NORMAL 状态不过滤任何股票。"""
        items = [_make_item("000001", 60), _make_item("000002", 40)]
        stocks_data = {
            "000001": {"daily_change_pct": 3.0, "change_pct_3d": 5.0},
            "000002": {"daily_change_pct": 2.0, "change_pct_3d": 4.0},
        }
        filtered, mrl = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.NORMAL,
            blacklisted_symbols=set(),
        )
        assert len(filtered) == 2

    def test_caution_threshold_90(self):
        """CAUTION 状态仅保留 trend_score >= 90。"""
        items = [
            _make_item("000001", 95),
            _make_item("000002", 85),
            _make_item("000003", 90),
        ]
        stocks_data = {s.symbol: {"daily_change_pct": 3.0, "change_pct_3d": 5.0} for s in items}
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.CAUTION,
            blacklisted_symbols=set(),
        )
        symbols = {item.symbol for item in filtered}
        assert "000001" in symbols
        assert "000003" in symbols
        assert "000002" not in symbols

    def test_danger_threshold_95(self):
        """DANGER 状态仅保留 trend_score >= 95。"""
        items = [
            _make_item("000001", 96),
            _make_item("000002", 94),
            _make_item("000003", 95),
        ]
        stocks_data = {s.symbol: {"daily_change_pct": 3.0, "change_pct_3d": 5.0} for s in items}
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.DANGER,
            blacklisted_symbols=set(),
        )
        symbols = {item.symbol for item in filtered}
        assert "000001" in symbols
        assert "000003" in symbols
        assert "000002" not in symbols


class TestDailyGainFilter:
    """验证单日涨幅过滤边界值。"""

    def test_gain_above_9_filtered(self):
        """涨幅 > 9% 被过滤。"""
        items = [_make_item("000001", 80)]
        stocks_data = {"000001": {"daily_change_pct": 9.5, "change_pct_3d": 10.0}}
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.NORMAL,
            blacklisted_symbols=set(),
        )
        assert len(filtered) == 0

    def test_gain_exactly_9_not_filtered(self):
        """涨幅恰好 9.0% 不被过滤（> 9 才过滤）。"""
        items = [_make_item("000001", 80)]
        stocks_data = {"000001": {"daily_change_pct": 9.0, "change_pct_3d": 10.0}}
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.NORMAL,
            blacklisted_symbols=set(),
        )
        assert len(filtered) == 1

    def test_gain_below_9_not_filtered(self):
        """涨幅 8.99% 不被过滤。"""
        items = [_make_item("000001", 80)]
        stocks_data = {"000001": {"daily_change_pct": 8.99, "change_pct_3d": 10.0}}
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.NORMAL,
            blacklisted_symbols=set(),
        )
        assert len(filtered) == 1


class TestBlacklistFilter:
    """验证黑名单过滤。"""

    def test_blacklisted_stock_filtered(self):
        items = [_make_item("000001", 80), _make_item("000002", 80)]
        stocks_data = {
            "000001": {"daily_change_pct": 3.0, "change_pct_3d": 5.0},
            "000002": {"daily_change_pct": 3.0, "change_pct_3d": 5.0},
        }
        filtered, _ = ScreenExecutor._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.NORMAL,
            blacklisted_symbols={"000001"},
        )
        assert len(filtered) == 1
        assert filtered[0].symbol == "000002"


class TestFilterIdempotent:
    """验证过滤顺序幂等性。"""

    def test_double_filter_same_result(self):
        """两次过滤产生相同结果。"""
        items = [
            _make_item("000001", 80),
            _make_item("000002", 95),
            _make_item("000003", 60),
        ]
        stocks_data = {
            "000001": {"daily_change_pct": 3.0, "change_pct_3d": 5.0},
            "000002": {"daily_change_pct": 3.0, "change_pct_3d": 5.0},
            "000003": {"daily_change_pct": 10.0, "change_pct_3d": 5.0},
        }
        kwargs = dict(
            stocks_data=stocks_data,
            market_risk_level=MarketRiskLevel.CAUTION,
            blacklisted_symbols=set(),
        )
        filtered1, _ = ScreenExecutor._apply_risk_filters_pure(items=items, **kwargs)
        filtered2, _ = ScreenExecutor._apply_risk_filters_pure(items=filtered1, **kwargs)
        assert len(filtered1) == len(filtered2)
        assert {i.symbol for i in filtered1} == {i.symbol for i in filtered2}
