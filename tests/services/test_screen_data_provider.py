"""
ScreenDataProvider 单元测试

测试因子字典转换正确性和空数据处理。
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.kline import KlineBar
from app.models.stock import StockInfo
from app.services.screener.screen_data_provider import (
    DEFAULT_LOOKBACK_DAYS,
    ScreenDataProvider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_stock(
    symbol: str = "000001.SZ",
    name: str = "平安银行",
    is_st: bool = False,
    is_delisted: bool = False,
    pe_ttm: Decimal | None = Decimal("8.50"),
    pb: Decimal | None = Decimal("0.75"),
    roe: Decimal | None = Decimal("0.1234"),
    market_cap: Decimal | None = Decimal("300000000000.00"),
) -> StockInfo:
    stock = StockInfo()
    stock.symbol = symbol
    stock.name = name
    stock.is_st = is_st
    stock.is_delisted = is_delisted
    stock.pe_ttm = pe_ttm
    stock.pb = pb
    stock.roe = roe
    stock.market_cap = market_cap
    return stock


def _make_bar(
    symbol: str = "000001.SZ",
    day_offset: int = 0,
    close: Decimal = Decimal("15.00"),
    open_: Decimal = Decimal("14.80"),
    high: Decimal = Decimal("15.20"),
    low: Decimal = Decimal("14.70"),
    volume: int = 1000000,
    amount: Decimal = Decimal("15000000.00"),
    turnover: Decimal = Decimal("5.50"),
    vol_ratio: Decimal = Decimal("1.20"),
) -> KlineBar:
    return KlineBar(
        time=datetime(2024, 1, 10 + day_offset),
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


# ---------------------------------------------------------------------------
# _build_factor_dict tests
# ---------------------------------------------------------------------------


class TestBuildFactorDict:
    """测试 _build_factor_dict 静态方法的因子字典转换正确性。"""

    def test_latest_quote_fields(self):
        """最新行情字段应取自最后一条 bar。"""
        stock = _make_stock()
        bars = [
            _make_bar(day_offset=0, close=Decimal("14.00")),
            _make_bar(day_offset=1, close=Decimal("15.00")),
            _make_bar(day_offset=2, close=Decimal("16.00")),
        ]

        result = ScreenDataProvider._build_factor_dict(stock, bars)

        assert result["close"] == Decimal("16.00")
        assert result["open"] == bars[-1].open
        assert result["high"] == bars[-1].high
        assert result["low"] == bars[-1].low
        assert result["volume"] == bars[-1].volume
        assert result["amount"] == bars[-1].amount
        assert result["turnover"] == bars[-1].turnover
        assert result["vol_ratio"] == bars[-1].vol_ratio

    def test_historical_sequences(self):
        """历史序列应包含所有 bar 的数据，时间升序。"""
        stock = _make_stock()
        bars = [
            _make_bar(day_offset=0, close=Decimal("14.00"), volume=100),
            _make_bar(day_offset=1, close=Decimal("15.00"), volume=200),
            _make_bar(day_offset=2, close=Decimal("16.00"), volume=300),
        ]

        result = ScreenDataProvider._build_factor_dict(stock, bars)

        assert result["closes"] == [Decimal("14.00"), Decimal("15.00"), Decimal("16.00")]
        assert result["volumes"] == [100, 200, 300]
        assert len(result["highs"]) == 3
        assert len(result["lows"]) == 3
        assert len(result["amounts"]) == 3
        assert len(result["turnovers"]) == 3

    def test_fundamental_factors(self):
        """基本面因子应从 StockInfo 转换为 float。"""
        stock = _make_stock(
            pe_ttm=Decimal("8.50"),
            pb=Decimal("0.75"),
            roe=Decimal("0.1234"),
            market_cap=Decimal("300000000000.00"),
        )
        bars = [_make_bar()]

        result = ScreenDataProvider._build_factor_dict(stock, bars)

        assert result["pe_ttm"] == pytest.approx(8.50)
        assert result["pb"] == pytest.approx(0.75)
        assert result["roe"] == pytest.approx(0.1234)
        assert result["market_cap"] == pytest.approx(300000000000.00)

    def test_fundamental_factors_none(self):
        """基本面因子为 None 时应保持 None。"""
        stock = _make_stock(pe_ttm=None, pb=None, roe=None, market_cap=None)
        bars = [_make_bar()]

        result = ScreenDataProvider._build_factor_dict(stock, bars)

        assert result["pe_ttm"] is None
        assert result["pb"] is None
        assert result["roe"] is None
        assert result["market_cap"] is None

    def test_single_bar(self):
        """单条 bar 时序列长度为 1，最新行情取该条。"""
        stock = _make_stock()
        bars = [_make_bar(close=Decimal("20.00"))]

        result = ScreenDataProvider._build_factor_dict(stock, bars)

        assert result["close"] == Decimal("20.00")
        assert result["closes"] == [Decimal("20.00")]
        assert len(result["volumes"]) == 1


# ---------------------------------------------------------------------------
# load_screen_data tests
# ---------------------------------------------------------------------------


class TestLoadScreenData:
    """测试 load_screen_data 异步方法。"""

    @pytest.mark.asyncio
    async def test_empty_stocks_returns_empty_dict(self):
        """stock_info 表无有效股票时返回空字典。"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )

        # Mock _load_valid_stocks 返回空列表
        provider._load_valid_stocks = AsyncMock(return_value=[])

        result = await provider.load_screen_data()

        assert result == {}

    @pytest.mark.asyncio
    async def test_stock_with_no_kline_skipped(self):
        """股票无 K 线数据时应跳过。"""
        stock = _make_stock(symbol="600000.SH")
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=[])

            result = await provider.load_screen_data()

        assert result == {}

    @pytest.mark.asyncio
    async def test_stock_with_kline_included(self):
        """有 K 线数据的股票应包含在结果中。"""
        stock = _make_stock(symbol="000001.SZ")
        bars = [_make_bar(symbol="000001.SZ", day_offset=i) for i in range(3)]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=bars)

            result = await provider.load_screen_data()

        assert "000001.SZ" in result
        assert result["000001.SZ"]["close"] == bars[-1].close

    @pytest.mark.asyncio
    async def test_failed_stock_skipped_with_warning(self):
        """单只股票加载失败时应跳过并记录 warning。"""
        stock_ok = _make_stock(symbol="000001.SZ")
        stock_fail = _make_stock(symbol="000002.SZ")
        bars = [_make_bar(symbol="000001.SZ")]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(
            return_value=[stock_fail, stock_ok]
        )

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value

            async def side_effect(symbol, **kwargs):
                if symbol == "000002.SZ":
                    raise RuntimeError("DB connection error")
                return bars

            mock_repo.query = AsyncMock(side_effect=side_effect)

            result = await provider.load_screen_data()

        # 失败的股票被跳过，成功的保留
        assert "000002.SZ" not in result
        assert "000001.SZ" in result

    @pytest.mark.asyncio
    async def test_default_lookback_days(self):
        """默认回溯天数应为 365。"""
        assert DEFAULT_LOOKBACK_DAYS == 365
