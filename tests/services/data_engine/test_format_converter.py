"""
Tests for TushareFormatConverter and AkShareFormatConverter.

Validates requirement 1.11: unified format conversion from Tushare/AkShare
raw data to system internal data structures (KlineBar, FundamentalsData,
MoneyFlowData, MarketOverview).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from app.core.schemas import KlineBar
from app.services.data_engine.format_converter import (
    AkShareFormatConverter,
    TushareFormatConverter,
)
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tushare_converter() -> TushareFormatConverter:
    return TushareFormatConverter()


@pytest.fixture
def akshare_converter() -> AkShareFormatConverter:
    return AkShareFormatConverter()


# ---------------------------------------------------------------------------
# TushareFormatConverter — to_kline_bars
# ---------------------------------------------------------------------------

class TestTushareKlineBars:
    def test_basic_conversion(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {
            "fields": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "turnover_rate", "volume_ratio"],
            "items": [
                ["000001.SZ", "20240101", 10.5, 11.0, 10.0, 10.8, 100000, 500.0, 3.5, 1.2],
            ],
        }
        bars = tushare_converter.to_kline_bars(raw, "000001.SZ", "D")

        assert len(bars) == 1
        bar = bars[0]
        assert isinstance(bar, KlineBar)
        assert bar.symbol == "000001.SZ"
        assert bar.freq == "D"
        assert bar.time == datetime(2024, 1, 1)
        assert bar.open == Decimal("10.5")
        assert bar.high == Decimal("11.0")
        assert bar.low == Decimal("10.0")
        assert bar.close == Decimal("10.8")
        assert bar.volume == 100000
        # amount: 500 千元 * 1000 = 500000 元
        assert bar.amount == Decimal("500.0") * 1000
        assert bar.turnover == Decimal("3.5")
        assert bar.vol_ratio == Decimal("1.2")
        assert bar.limit_up is None
        assert bar.limit_down is None
        assert bar.adj_type == 0

    def test_amount_unit_conversion(self, tushare_converter: TushareFormatConverter) -> None:
        """Tushare amount is in 千元, must be multiplied by 1000."""
        raw = {
            "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [["20240315", 20.0, 21.0, 19.5, 20.5, 50000, 1234.56]],
        }
        bars = tushare_converter.to_kline_bars(raw, "600000.SH", "D")
        assert bars[0].amount == Decimal("1234.56") * 1000

    def test_empty_items(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {"fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"], "items": []}
        bars = tushare_converter.to_kline_bars(raw, "000001.SZ", "D")
        assert bars == []

    def test_missing_fields(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {"fields": ["trade_date"], "items": [["20240101"]]}
        bars = tushare_converter.to_kline_bars(raw, "000001.SZ", "D")
        assert len(bars) == 1
        bar = bars[0]
        assert bar.open == Decimal(0)
        assert bar.volume == 0
        assert bar.amount == Decimal(0)

    def test_multiple_rows(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {
            "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [
                ["20240101", 10.0, 11.0, 9.5, 10.5, 1000, 100.0],
                ["20240102", 10.5, 12.0, 10.0, 11.5, 2000, 200.0],
            ],
        }
        bars = tushare_converter.to_kline_bars(raw, "000001.SZ", "D")
        assert len(bars) == 2
        assert bars[0].time == datetime(2024, 1, 1)
        assert bars[1].time == datetime(2024, 1, 2)

    def test_decimal_types(self, tushare_converter: TushareFormatConverter) -> None:
        """Price and amount fields must be Decimal, volume must be int."""
        raw = {
            "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [["20240101", 10.5, 11.0, 10.0, 10.8, 100000, 500.0]],
        }
        bar = tushare_converter.to_kline_bars(raw, "000001.SZ", "D")[0]
        assert isinstance(bar.open, Decimal)
        assert isinstance(bar.high, Decimal)
        assert isinstance(bar.low, Decimal)
        assert isinstance(bar.close, Decimal)
        assert isinstance(bar.amount, Decimal)
        assert isinstance(bar.turnover, Decimal)
        assert isinstance(bar.vol_ratio, Decimal)
        assert isinstance(bar.volume, int)


# ---------------------------------------------------------------------------
# TushareFormatConverter — to_fundamentals
# ---------------------------------------------------------------------------

class TestTushareFundamentals:
    def test_basic_conversion(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {
            "fields": ["name", "pe_ttm", "pb", "roe_dt", "netprofit_yoy", "or_yoy"],
            "items": [["平安银行", 8.5, 0.9, 12.3, 15.0, 10.0]],
        }
        result = tushare_converter.to_fundamentals(raw, "000001.SZ")
        assert isinstance(result, FundamentalsData)
        assert result.symbol == "000001.SZ"
        assert result.name == "平安银行"
        assert result.pe_ttm == Decimal("8.5")
        assert result.pb == Decimal("0.9")
        assert result.roe == Decimal("12.3")
        assert result.net_profit_yoy == Decimal("15.0")
        assert result.revenue_yoy == Decimal("10.0")
        assert result.updated_at is not None

    def test_empty_data(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {"fields": ["name"], "items": []}
        result = tushare_converter.to_fundamentals(raw, "000001.SZ")
        assert result.symbol == "000001.SZ"
        assert result.pe_ttm is None


# ---------------------------------------------------------------------------
# TushareFormatConverter — to_money_flow
# ---------------------------------------------------------------------------

class TestTushareMoneyFlow:
    def test_basic_conversion(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {
            "fields": ["net_mf_amount", "buy_elg_amount", "sell_elg_amount", "net_lg_amount"],
            "items": [[5000000.0, 8000000.0, 3000000.0, 2000000.0]],
        }
        result = tushare_converter.to_money_flow(raw, "000001.SZ", date(2024, 3, 15))
        assert isinstance(result, MoneyFlowData)
        assert result.symbol == "000001.SZ"
        assert result.trade_date == date(2024, 3, 15)
        assert result.main_net_inflow == Decimal("5000000.0")
        assert result.main_inflow == Decimal("8000000.0")
        assert result.main_outflow == Decimal("3000000.0")
        assert result.large_order_net == Decimal("2000000.0")

    def test_empty_data(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {"fields": [], "items": []}
        result = tushare_converter.to_money_flow(raw, "000001.SZ", date(2024, 3, 15))
        assert result.symbol == "000001.SZ"
        assert result.main_net_inflow is None


# ---------------------------------------------------------------------------
# TushareFormatConverter — to_market_overview
# ---------------------------------------------------------------------------

class TestTushareMarketOverview:
    def test_basic_conversion(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {
            "fields": ["close", "pct_chg"],
            "items": [[3200.50, 1.25]],
        }
        result = tushare_converter.to_market_overview(raw, date(2024, 3, 15))
        assert isinstance(result, MarketOverview)
        assert result.trade_date == date(2024, 3, 15)
        assert result.sh_index == Decimal("3200.50")
        assert result.sh_change_pct == Decimal("1.25")

    def test_empty_data(self, tushare_converter: TushareFormatConverter) -> None:
        raw = {"fields": [], "items": []}
        result = tushare_converter.to_market_overview(raw, date(2024, 3, 15))
        assert result.trade_date == date(2024, 3, 15)
        assert result.sh_index is None


# ---------------------------------------------------------------------------
# AkShareFormatConverter — to_kline_bars
# ---------------------------------------------------------------------------

class TestAkShareKlineBars:
    def test_basic_conversion(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame([{
            "日期": "2024-01-01",
            "开盘": 10.5,
            "最高": 11.0,
            "最低": 10.0,
            "收盘": 10.8,
            "成交量": 100000,
            "成交额": 500000.0,
            "换手率": 3.5,
        }])
        bars = akshare_converter.to_kline_bars(df, "000001.SZ", "D")

        assert len(bars) == 1
        bar = bars[0]
        assert isinstance(bar, KlineBar)
        assert bar.symbol == "000001.SZ"
        assert bar.freq == "D"
        assert bar.time == datetime(2024, 1, 1)
        assert bar.open == Decimal("10.5")
        assert bar.high == Decimal("11.0")
        assert bar.low == Decimal("10.0")
        assert bar.close == Decimal("10.8")
        assert bar.volume == 100000
        assert bar.amount == Decimal("500000.0")  # 已经是元，无需转换
        assert bar.turnover == Decimal("3.5")
        assert bar.vol_ratio == Decimal(0)  # AkShare 不提供量比
        assert bar.limit_up is None
        assert bar.limit_down is None
        assert bar.adj_type == 0

    def test_amount_already_in_yuan(self, akshare_converter: AkShareFormatConverter) -> None:
        """AkShare amount is already in yuan, no conversion needed."""
        df = pd.DataFrame([{
            "日期": "2024-03-15",
            "开盘": 20.0, "最高": 21.0, "最低": 19.5, "收盘": 20.5,
            "成交量": 50000, "成交额": 1234560.0,
        }])
        bars = akshare_converter.to_kline_bars(df, "600000.SH", "D")
        assert bars[0].amount == Decimal("1234560.0")

    def test_empty_dataframe(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame()
        bars = akshare_converter.to_kline_bars(df, "000001.SZ", "D")
        assert bars == []

    def test_none_dataframe(self, akshare_converter: AkShareFormatConverter) -> None:
        bars = akshare_converter.to_kline_bars(None, "000001.SZ", "D")
        assert bars == []

    def test_decimal_types(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame([{
            "日期": "2024-01-01",
            "开盘": 10.5, "最高": 11.0, "最低": 10.0, "收盘": 10.8,
            "成交量": 100000, "成交额": 500000.0, "换手率": 3.5,
        }])
        bar = akshare_converter.to_kline_bars(df, "000001.SZ", "D")[0]
        assert isinstance(bar.open, Decimal)
        assert isinstance(bar.high, Decimal)
        assert isinstance(bar.low, Decimal)
        assert isinstance(bar.close, Decimal)
        assert isinstance(bar.amount, Decimal)
        assert isinstance(bar.turnover, Decimal)
        assert isinstance(bar.vol_ratio, Decimal)
        assert isinstance(bar.volume, int)


# ---------------------------------------------------------------------------
# AkShareFormatConverter — to_fundamentals
# ---------------------------------------------------------------------------

class TestAkShareFundamentals:
    def test_basic_conversion(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame([{
            "净资产收益率(%)": 12.3,
            "净利润同比增长率(%)": 15.0,
            "主营业务收入同比增长率(%)": 10.0,
        }])
        result = akshare_converter.to_fundamentals(df, "000001.SZ")
        assert isinstance(result, FundamentalsData)
        assert result.symbol == "000001.SZ"
        assert result.roe == Decimal("12.3")
        assert result.net_profit_yoy == Decimal("15.0")
        assert result.revenue_yoy == Decimal("10.0")

    def test_empty_dataframe(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame()
        result = akshare_converter.to_fundamentals(df, "000001.SZ")
        assert result.symbol == "000001.SZ"
        assert result.roe is None


# ---------------------------------------------------------------------------
# AkShareFormatConverter — to_money_flow
# ---------------------------------------------------------------------------

class TestAkShareMoneyFlow:
    def test_basic_conversion(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame([{
            "日期": "2024-03-15",
            "主力净流入-净额": 5000000.0,
            "主力净流入-净占比": 2.5,
            "超大单净流入-净额": 2000000.0,
        }])
        result = akshare_converter.to_money_flow(df, "000001.SZ", date(2024, 3, 15))
        assert isinstance(result, MoneyFlowData)
        assert result.symbol == "000001.SZ"
        assert result.trade_date == date(2024, 3, 15)
        assert result.main_net_inflow == Decimal("5000000.0")

    def test_date_matching(self, akshare_converter: AkShareFormatConverter) -> None:
        """Should match the row for the specified trade_date."""
        df = pd.DataFrame([
            {"日期": "2024-03-14", "主力净流入-净额": 1000000.0},
            {"日期": "2024-03-15", "主力净流入-净额": 5000000.0},
        ])
        result = akshare_converter.to_money_flow(df, "000001.SZ", date(2024, 3, 15))
        assert result.main_net_inflow == Decimal("5000000.0")

    def test_empty_dataframe(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame()
        result = akshare_converter.to_money_flow(df, "000001.SZ", date(2024, 3, 15))
        assert result.main_net_inflow is None


# ---------------------------------------------------------------------------
# AkShareFormatConverter — to_market_overview
# ---------------------------------------------------------------------------

class TestAkShareMarketOverview:
    def test_basic_conversion(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame([{
            "date": "2024-03-15",
            "close": 3200.50,
            "pct_chg": 1.25,
        }])
        result = akshare_converter.to_market_overview(df, date(2024, 3, 15))
        assert isinstance(result, MarketOverview)
        assert result.trade_date == date(2024, 3, 15)
        assert result.sh_index == Decimal("3200.50")
        assert result.sh_change_pct == Decimal("1.25")

    def test_empty_dataframe(self, akshare_converter: AkShareFormatConverter) -> None:
        df = pd.DataFrame()
        result = akshare_converter.to_market_overview(df, date(2024, 3, 15))
        assert result.sh_index is None



# ---------------------------------------------------------------------------
# Cross-converter consistency: both converters produce identical KlineBar
# ---------------------------------------------------------------------------

class TestConverterConsistency:
    """Verify that TushareFormatConverter and AkShareFormatConverter produce
    identical KlineBar structures for equivalent input data."""

    def test_kline_bar_structure_identical(
        self,
        tushare_converter: TushareFormatConverter,
        akshare_converter: AkShareFormatConverter,
    ) -> None:
        """Same market data from both sources must produce identical KlineBar fields."""
        # Tushare raw: amount in 千元 (123.456 千元 = 123456 元)
        tushare_raw = {
            "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount", "turnover_rate", "volume_ratio"],
            "items": [["20240315", 20.0, 21.5, 19.5, 20.8, 80000, 123.456, 5.2, 1.8]],
        }

        # AkShare raw: amount already in 元 (123456 元)
        akshare_df = pd.DataFrame([{
            "日期": "2024-03-15",
            "开盘": 20.0,
            "最高": 21.5,
            "最低": 19.5,
            "收盘": 20.8,
            "成交量": 80000,
            "成交额": 123456.0,
            "换手率": 5.2,
        }])

        ts_bars = tushare_converter.to_kline_bars(tushare_raw, "000001.SZ", "D")
        ak_bars = akshare_converter.to_kline_bars(akshare_df, "000001.SZ", "D")

        assert len(ts_bars) == 1
        assert len(ak_bars) == 1

        ts_bar = ts_bars[0]
        ak_bar = ak_bars[0]

        # Core fields must match exactly
        assert ts_bar.time == ak_bar.time
        assert ts_bar.symbol == ak_bar.symbol
        assert ts_bar.freq == ak_bar.freq
        assert ts_bar.open == ak_bar.open
        assert ts_bar.high == ak_bar.high
        assert ts_bar.low == ak_bar.low
        assert ts_bar.close == ak_bar.close
        assert ts_bar.volume == ak_bar.volume
        # Amount: Tushare 123.456 * 1000 = 123456, AkShare 123456
        assert ts_bar.amount == ak_bar.amount
        assert ts_bar.turnover == ak_bar.turnover
        # vol_ratio differs: Tushare provides it, AkShare defaults to 0
        assert isinstance(ts_bar.vol_ratio, Decimal)
        assert isinstance(ak_bar.vol_ratio, Decimal)
        assert ak_bar.vol_ratio == Decimal(0)
        # Structural fields
        assert ts_bar.limit_up == ak_bar.limit_up
        assert ts_bar.limit_down == ak_bar.limit_down
        assert ts_bar.adj_type == ak_bar.adj_type

    def test_field_types_consistent(
        self,
        tushare_converter: TushareFormatConverter,
        akshare_converter: AkShareFormatConverter,
    ) -> None:
        """Both converters must produce the same Python types for all fields."""
        tushare_raw = {
            "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"],
            "items": [["20240101", 10.0, 11.0, 9.5, 10.5, 1000, 50.0]],
        }
        akshare_df = pd.DataFrame([{
            "日期": "2024-01-01",
            "开盘": 10.0, "最高": 11.0, "最低": 9.5, "收盘": 10.5,
            "成交量": 1000, "成交额": 50000.0,
        }])

        ts_bar = tushare_converter.to_kline_bars(tushare_raw, "SYM", "D")[0]
        ak_bar = akshare_converter.to_kline_bars(akshare_df, "SYM", "D")[0]

        # All price/amount fields must be Decimal
        for field in ("open", "high", "low", "close", "amount", "turnover", "vol_ratio"):
            assert type(getattr(ts_bar, field)) is Decimal, f"Tushare {field} not Decimal"
            assert type(getattr(ak_bar, field)) is Decimal, f"AkShare {field} not Decimal"

        # Volume must be int
        assert type(ts_bar.volume) is int
        assert type(ak_bar.volume) is int

        # Time must be datetime
        assert type(ts_bar.time) is datetime
        assert type(ak_bar.time) is datetime
