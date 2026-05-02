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

    def test_filter_valid_kline_bars_drops_incomplete_ohlcv(self):
        """OHLCV 关键字段为空的 K 线不应进入指标计算。"""
        valid_bar = _make_bar(day_offset=0)
        invalid_close = _make_bar(day_offset=1)
        invalid_close.close = None
        invalid_volume = _make_bar(day_offset=2)
        invalid_volume.volume = None

        result = ScreenDataProvider._filter_valid_kline_bars([
            valid_bar,
            invalid_close,
            invalid_volume,
        ])

        assert result == [valid_bar]

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
        ) as MockRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=[])
            mock_adj_repo = MockAdjRepo.return_value
            mock_adj_repo.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data()

        assert result == {}

    @pytest.mark.asyncio
    async def test_stock_with_kline_included(self):
        """有 K 线数据的股票应包含在结果中（无复权因子时使用原始价格）。"""
        stock = _make_stock(symbol="000001.SZ")
        bars = [_make_bar(symbol="000001.SZ", day_offset=i) for i in range(3)]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=bars)
            mock_adj_repo = MockAdjRepo.return_value
            mock_adj_repo.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data()

        assert "000001.SZ" in result
        assert result["000001.SZ"]["close"] == bars[-1].close
        assert result["000001.SZ"]["raw_close"] == bars[-1].close

    @pytest.mark.asyncio
    async def test_stock_with_incomplete_kline_filtered(self):
        """K 线序列包含空值时应过滤坏行并保留可计算数据。"""
        stock = _make_stock(symbol="000001.SZ")
        bad_bar = _make_bar(symbol="000001.SZ", day_offset=0)
        bad_bar.close = None
        good_bar = _make_bar(symbol="000001.SZ", day_offset=1, close=Decimal("16.00"))

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=[bad_bar, good_bar])
            mock_adj_repo = MockAdjRepo.return_value
            mock_adj_repo.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data()

        assert "000001.SZ" in result
        assert result["000001.SZ"]["closes"] == [Decimal("16.00")]
        assert result["000001.SZ"]["raw_close"] == Decimal("16.00")

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
        ) as MockRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_repo = MockRepo.return_value

            async def side_effect(symbol, **kwargs):
                if symbol == "000002.SZ":
                    raise RuntimeError("DB connection error")
                return bars

            mock_repo.query = AsyncMock(side_effect=side_effect)
            mock_adj_repo = MockAdjRepo.return_value
            mock_adj_repo.query_batch = AsyncMock(return_value={})

            result = await provider.load_screen_data()

        # 失败的股票被跳过，成功的保留
        assert "000002.SZ" not in result
        assert "000001.SZ" in result

    @pytest.mark.asyncio
    async def test_default_lookback_days(self):
        """默认回溯天数应为 365。"""
        assert DEFAULT_LOOKBACK_DAYS == 365


# ---------------------------------------------------------------------------
# 数据加载降级单元测试（需求 12.3, 13.5, 14.5, 15.4, 16.5, 17.3）
# ---------------------------------------------------------------------------


class TestEnrichStkFactorDegradation:
    """测试 _enrich_stk_factor_factors 空数据降级行为（需求 12.3）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_none(self):
        """stk_factor 表无数据时，所有技术面专业因子应降级为 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_stk_factor_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("kdj_k", "kdj_d", "kdj_j", "cci", "wr",
                       "trix", "bias", "psy", "obv_signal"):
            assert fd[factor] is None, f"因子 {factor} 应降级为 None"

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，因子应降级为 None 并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_stk_factor_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("kdj_k", "kdj_d", "kdj_j", "cci", "wr",
                       "trix", "bias", "psy", "obv_signal"):
            assert fd.get(factor) is None, f"因子 {factor} 应降级为 None"
        assert "stk_factor" in caplog.text.lower() or "技术面" in caplog.text


class TestEnrichChipFactorsDegradation:
    """测试 _enrich_chip_factors 空数据降级行为（需求 13.5）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_none(self):
        """cyq_perf 表无数据时，所有筹码因子应降级为 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_chip_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
                       "chip_cost_50pct", "chip_weight_avg", "chip_concentration"):
            assert fd[factor] is None, f"因子 {factor} 应降级为 None"

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，筹码因子应降级为 None 并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_chip_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
                       "chip_cost_50pct", "chip_weight_avg", "chip_concentration"):
            assert fd.get(factor) is None, f"因子 {factor} 应降级为 None"


class TestEnrichMarginFactorsDegradation:
    """测试 _enrich_margin_factors 空数据降级行为（需求 14.5）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_none(self):
        """margin_detail 表无数据时，所有两融因子应降级为 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_margin_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy"):
            assert fd[factor] is None, f"因子 {factor} 应降级为 None"

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，两融因子应降级为 None 并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_margin_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy"):
            assert fd.get(factor) is None, f"因子 {factor} 应降级为 None"


class TestEnrichEnhancedMoneyFlowDegradation:
    """测试 _enrich_enhanced_money_flow_factors 空数据降级行为（需求 15.4）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_none(self):
        """moneyflow_ths 和 moneyflow_dc 表均无数据时，增强资金流因子应降级为 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_enhanced_money_flow_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("super_large_net_inflow", "large_net_inflow",
                       "small_net_outflow", "money_flow_strength", "net_inflow_rate"):
            assert fd[factor] is None, f"因子 {factor} 应降级为 None"

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，增强资金流因子应降级为 None 并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_enhanced_money_flow_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("super_large_net_inflow", "large_net_inflow",
                       "small_net_outflow", "money_flow_strength", "net_inflow_rate"):
            assert fd.get(factor) is None, f"因子 {factor} 应降级为 None"


class TestEnrichBoardHitFactorsDegradation:
    """测试 _enrich_board_hit_factors 空数据降级行为（需求 16.5）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_defaults(self):
        """打板数据表无数据时，数值型因子降级为 0，布尔型降级为 False。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_board_hit_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        assert fd["limit_up_count"] == 0
        assert fd["limit_up_streak"] == 0
        assert fd["limit_up_open_pct"] == 0
        assert fd["dragon_tiger_net_buy"] is False
        assert fd["first_limit_up"] is False

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，打板因子应降级为默认值并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_board_hit_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        assert fd.get("limit_up_count", 0) == 0
        assert fd.get("limit_up_streak", 0) == 0
        assert fd.get("dragon_tiger_net_buy", False) is False
        assert fd.get("first_limit_up", False) is False


class TestEnrichIndexFactorsDegradation:
    """测试 _enrich_index_factors 空数据降级行为（需求 17.3）。"""

    @pytest.mark.asyncio
    async def test_empty_table_sets_none(self):
        """指数数据表无数据时，所有指数因子应降级为 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        # 需要处理 scalar_one_or_none 调用（用于 index_weights 查询）
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_result_2 = MagicMock()
        mock_result_2.scalars.return_value.all.return_value = []
        mock_result_2.scalar_one_or_none.return_value = None

        call_count = [0]
        async def mock_execute(stmt):
            call_count[0] += 1
            # 前两次是 index_dailybasic 和 index_tech 查询
            if call_count[0] <= 2:
                return mock_result
            # 后续是 index_weight 查询
            return mock_result_2

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        await provider._enrich_index_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("index_pe", "index_turnover", "index_ma_trend", "index_vol_ratio"):
            assert fd[factor] is None, f"因子 {factor} 应降级为 None"

    @pytest.mark.asyncio
    async def test_connection_error_sets_defaults(self, caplog):
        """数据库连接异常时，指数因子应降级为 None 并记录 WARNING。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        provider = ScreenDataProvider(pg_session=mock_session)
        stocks_data = {"000001.SZ": {"close": 15.0}}

        import logging
        with caplog.at_level(logging.WARNING):
            await provider._enrich_index_factors(stocks_data, date(2024, 1, 15))

        fd = stocks_data["000001.SZ"]
        for factor in ("index_pe", "index_turnover", "index_ma_trend", "index_vol_ratio"):
            assert fd.get(factor) is None, f"因子 {factor} 应降级为 None"
