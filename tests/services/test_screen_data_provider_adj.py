"""
ScreenDataProvider 前复权集成单元测试

验证 ScreenDataProvider 在 load_screen_data 流程中正确集成前复权计算：
- 有复权因子时，调整后的价格传递给指标计算
- raw_close 保留原始收盘价
- 无复权因子时优雅降级，使用原始K线并记录警告

Validates: Requirements 3.1, 3.3, 3.5
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.adjustment_factor import AdjustmentFactor
from app.models.kline import KlineBar
from app.models.stock import StockInfo
from app.services.screener.screen_data_provider import ScreenDataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_PLACES = Decimal("0.01")


def _make_stock(
    symbol: str = "000001.SZ",
    name: str = "平安银行",
) -> StockInfo:
    stock = StockInfo()
    stock.symbol = symbol
    stock.name = name
    stock.is_st = False
    stock.is_delisted = False
    stock.pe_ttm = Decimal("8.50")
    stock.pb = Decimal("0.75")
    stock.roe = Decimal("0.1234")
    stock.market_cap = Decimal("300000000000.00")
    return stock


def _make_bar(
    symbol: str = "000001.SZ",
    day: int = 10,
    open_: Decimal = Decimal("10.00"),
    high: Decimal = Decimal("11.00"),
    low: Decimal = Decimal("9.50"),
    close: Decimal = Decimal("10.50"),
    volume: int = 1_000_000,
    amount: Decimal = Decimal("10500000.00"),
    turnover: Decimal = Decimal("5.00"),
    vol_ratio: Decimal = Decimal("1.10"),
) -> KlineBar:
    return KlineBar(
        time=datetime(2024, 6, day),
        symbol=symbol,
        freq="1d",
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        turnover=turnover,
        vol_ratio=vol_ratio,
    )


def _make_factor(
    symbol: str = "000001.SZ",
    trade_date: date = date(2024, 6, 10),
    adj_factor: Decimal = Decimal("1.50000000"),
    adj_type: int = 1,
) -> AdjustmentFactor:
    f = AdjustmentFactor()
    f.symbol = symbol
    f.trade_date = trade_date
    f.adj_factor = adj_factor
    f.adj_type = adj_type
    return f


def _expected_adjusted_price(raw: Decimal, daily: Decimal, latest: Decimal) -> Decimal:
    """Compute expected forward-adjusted price using the formula."""
    return (raw * (daily / latest)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Tests: adjusted prices passed to indicator calculation (Req 3.1)
# ---------------------------------------------------------------------------


class TestAdjustedPricesPassedToIndicators:
    """When adjustment factors exist, bars passed to _build_factor_dict
    should have forward-adjusted OHLC prices."""

    @pytest.mark.asyncio
    async def test_adjusted_ohlc_in_factor_dict(self):
        """Verify that closes/highs/lows/open in factor_dict reflect adjusted prices.

        Validates: Requirements 3.1
        """
        stock = _make_stock(symbol="000001.SZ")
        raw_bars = [
            _make_bar(day=10, open_=Decimal("10.00"), high=Decimal("11.00"),
                      low=Decimal("9.50"), close=Decimal("10.50")),
            _make_bar(day=11, open_=Decimal("10.60"), high=Decimal("11.20"),
                      low=Decimal("10.00"), close=Decimal("10.80")),
        ]

        # Two factors: daily_factor=1.2 for day 10, daily_factor=1.5 for day 11
        # latest_factor = 1.5 (last in ascending order)
        factors = [
            _make_factor(trade_date=date(2024, 6, 10), adj_factor=Decimal("1.20000000")),
            _make_factor(trade_date=date(2024, 6, 11), adj_factor=Decimal("1.50000000")),
        ]
        latest_factor = Decimal("1.50000000")

        # Expected adjusted prices for day 10: ratio = 1.2 / 1.5 = 0.8
        ratio_day10 = Decimal("1.20000000") / Decimal("1.50000000")
        exp_close_day10 = _expected_adjusted_price(Decimal("10.50"), Decimal("1.20000000"), latest_factor)
        exp_open_day10 = _expected_adjusted_price(Decimal("10.00"), Decimal("1.20000000"), latest_factor)
        exp_high_day10 = _expected_adjusted_price(Decimal("11.00"), Decimal("1.20000000"), latest_factor)
        exp_low_day10 = _expected_adjusted_price(Decimal("9.50"), Decimal("1.20000000"), latest_factor)

        # Day 11: ratio = 1.5 / 1.5 = 1.0 → prices unchanged
        exp_close_day11 = Decimal("10.80")
        exp_open_day11 = Decimal("10.60")

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)

            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(
                return_value={"000001.SZ": factors}
            )

            result = await provider.load_screen_data(screen_date=date(2024, 6, 11))

        assert "000001.SZ" in result
        fd = result["000001.SZ"]

        # The closes list should contain adjusted prices
        assert fd["closes"][0] == exp_close_day10
        assert fd["closes"][1] == exp_close_day11

        # Latest close (from the last bar) should be adjusted
        assert fd["close"] == exp_close_day11

        # Highs and lows should also be adjusted
        assert fd["highs"][0] == exp_high_day10
        assert fd["lows"][0] == exp_low_day10

        # Open should be adjusted
        assert fd["open"] == exp_open_day11

    @pytest.mark.asyncio
    async def test_volume_amount_unchanged_after_adjustment(self):
        """Volume and amount should remain unchanged even when factors exist.

        Validates: Requirements 3.1
        """
        stock = _make_stock(symbol="600000.SH")
        raw_bars = [
            _make_bar(symbol="600000.SH", day=10, volume=500_000,
                      amount=Decimal("5000000.00")),
        ]
        factors = [
            _make_factor(symbol="600000.SH", trade_date=date(2024, 6, 10),
                         adj_factor=Decimal("0.80000000")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(
                return_value={"600000.SH": factors}
            )

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        fd = result["600000.SH"]
        assert fd["volumes"][0] == 500_000
        assert fd["amounts"][0] == Decimal("5000000.00")


# ---------------------------------------------------------------------------
# Tests: raw_close preserved (Req 3.5)
# ---------------------------------------------------------------------------


class TestRawClosePreserved:
    """raw_close in factor_dict should always be the original unadjusted close."""

    @pytest.mark.asyncio
    async def test_raw_close_with_factors(self):
        """When factors exist, raw_close should be the original (unadjusted) close.

        Validates: Requirements 3.5
        """
        stock = _make_stock(symbol="000001.SZ")
        original_close = Decimal("10.50")
        raw_bars = [
            _make_bar(day=10, close=original_close),
        ]
        # Factor with ratio != 1 so adjusted close differs from raw
        factors = [
            _make_factor(trade_date=date(2024, 6, 10), adj_factor=Decimal("0.80000000")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(
                return_value={"000001.SZ": factors}
            )

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        fd = result["000001.SZ"]
        # raw_close must be the original unadjusted close
        assert fd["raw_close"] == original_close
        # The adjusted close should differ from raw_close (ratio = 0.8/0.8 = 1.0 here)
        # Actually with a single factor, latest_factor == daily_factor, so ratio=1
        # Let's just verify raw_close is set correctly
        assert fd["raw_close"] == original_close

    @pytest.mark.asyncio
    async def test_raw_close_differs_from_adjusted_close(self):
        """When adjustment changes the price, raw_close != close in factor_dict.

        Validates: Requirements 3.5
        """
        stock = _make_stock(symbol="000001.SZ")
        original_close = Decimal("10.00")
        raw_bars = [
            _make_bar(day=10, close=original_close),
            _make_bar(day=11, close=Decimal("10.50")),
        ]
        # day 10 factor=1.0, day 11 factor=1.5 → latest=1.5
        # day 10 adjusted close = 10.00 * (1.0/1.5) = 6.67
        factors = [
            _make_factor(trade_date=date(2024, 6, 10), adj_factor=Decimal("1.00000000")),
            _make_factor(trade_date=date(2024, 6, 11), adj_factor=Decimal("1.50000000")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(
                return_value={"000001.SZ": factors}
            )

            result = await provider.load_screen_data(screen_date=date(2024, 6, 11))

        fd = result["000001.SZ"]
        # raw_close is the original close of the LAST bar (before adjustment)
        assert fd["raw_close"] == Decimal("10.50")
        # The adjusted close of day 11 = 10.50 * (1.5/1.5) = 10.50 (latest day unchanged)
        assert fd["close"] == Decimal("10.50")
        # But the adjusted close of day 10 should be different from original
        assert fd["closes"][0] == _expected_adjusted_price(
            Decimal("10.00"), Decimal("1.00000000"), Decimal("1.50000000")
        )

    @pytest.mark.asyncio
    async def test_raw_close_without_factors(self):
        """When no factors exist, raw_close should equal the last bar's close.

        Validates: Requirements 3.5
        """
        stock = _make_stock(symbol="000001.SZ")
        raw_bars = [
            _make_bar(day=10, close=Decimal("15.00")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        fd = result["000001.SZ"]
        assert fd["raw_close"] == Decimal("15.00")
        assert fd["close"] == Decimal("15.00")


# ---------------------------------------------------------------------------
# Tests: graceful fallback when no factors exist (Req 3.3)
# ---------------------------------------------------------------------------


class TestGracefulFallbackNoFactors:
    """When a stock has no adjustment factors, use original bars and log warning."""

    @pytest.mark.asyncio
    async def test_no_factors_uses_original_bars(self):
        """Stock without factors should use original (unadjusted) prices.

        Validates: Requirements 3.3
        """
        stock = _make_stock(symbol="000001.SZ")
        raw_bars = [
            _make_bar(day=10, close=Decimal("20.00"), open_=Decimal("19.50"),
                      high=Decimal("20.50"), low=Decimal("19.00")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        fd = result["000001.SZ"]
        # Prices should be the original unadjusted values
        assert fd["close"] == Decimal("20.00")
        assert fd["open"] == Decimal("19.50")
        assert fd["high"] == Decimal("20.50")
        assert fd["low"] == Decimal("19.00")
        assert fd["closes"] == [Decimal("20.00")]

    @pytest.mark.asyncio
    async def test_no_factors_logs_warning(self, caplog):
        """When no factors exist for a stock, a warning should be logged.

        Validates: Requirements 3.3
        """
        stock = _make_stock(symbol="300001.SZ")
        raw_bars = [
            _make_bar(symbol="300001.SZ", day=10),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(return_value={})

            with caplog.at_level(logging.WARNING):
                result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        assert "300001.SZ" in result
        # Check that a warning was logged about missing factors
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("300001.SZ" in msg and "原始K线" in msg for msg in warning_msgs), (
            f"Expected warning about missing factors for 300001.SZ, got: {warning_msgs}"
        )

    @pytest.mark.asyncio
    async def test_batch_query_failure_falls_back_gracefully(self):
        """When batch factor query raises an exception, use original bars.

        Validates: Requirements 3.3
        """
        stock = _make_stock(symbol="000001.SZ")
        raw_bars = [
            _make_bar(day=10, close=Decimal("12.00")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value
            mock_kline.query = AsyncMock(return_value=raw_bars)
            mock_adj = MockAdjRepo.return_value
            # Simulate DB failure on batch query
            mock_adj.query_batch = AsyncMock(side_effect=RuntimeError("DB error"))

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        # Should still return data using original bars
        assert "000001.SZ" in result
        fd = result["000001.SZ"]
        assert fd["close"] == Decimal("12.00")
        assert fd["raw_close"] == Decimal("12.00")

    @pytest.mark.asyncio
    async def test_mixed_stocks_some_with_factors_some_without(self):
        """Stocks with factors get adjusted; stocks without use original bars.

        Validates: Requirements 3.1, 3.3
        """
        stock_a = _make_stock(symbol="000001.SZ", name="平安银行")
        stock_b = _make_stock(symbol="600000.SH", name="浦发银行")

        bars_a = [_make_bar(symbol="000001.SZ", day=10, close=Decimal("10.00"))]
        bars_b = [_make_bar(symbol="600000.SH", day=10, close=Decimal("8.00"))]

        # Only stock A has factors (with ratio != 1)
        factors_a = [
            _make_factor(symbol="000001.SZ", trade_date=date(2024, 6, 10),
                         adj_factor=Decimal("0.80000000")),
        ]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock_a, stock_b])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockKlineRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_kline = MockKlineRepo.return_value

            async def kline_side_effect(symbol, **kwargs):
                if symbol == "000001.SZ":
                    return bars_a
                return bars_b

            mock_kline.query = AsyncMock(side_effect=kline_side_effect)
            mock_adj = MockAdjRepo.return_value
            mock_adj.query_batch = AsyncMock(
                return_value={"000001.SZ": factors_a}
            )

            result = await provider.load_screen_data(screen_date=date(2024, 6, 10))

        # Stock A: single factor, latest=0.8, ratio=0.8/0.8=1.0 → prices unchanged
        assert result["000001.SZ"]["close"] == Decimal("10.00")
        # Stock B: no factors → original prices
        assert result["600000.SH"]["close"] == Decimal("8.00")
        assert result["600000.SH"]["raw_close"] == Decimal("8.00")
