"""
ScreenDataProvider 资金流因子接入单元测试

覆盖场景：
- 正常加载：money_flow 表有数据时正确计算 money_flow / large_order 因子
- 原始数值写入：main_net_inflow / large_order_ratio 浮点值写入 factor_dict
- 缺失数据降级：money_flow 表无记录时设 False 并记录 WARNING 日志
- 异常处理：数据库查询异常时降级为 False

相关需求：需求 1（资金流因子数据接入）
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.kline import KlineBar
from app.models.money_flow import MoneyFlow
from app.models.stock import StockInfo
from app.models.tushare_import import MoneyflowDc, MoneyflowThs
from app.services.screener.screen_data_provider import ScreenDataProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_stock(
    symbol: str = "000001.SZ",
    name: str = "平安银行",
) -> StockInfo:
    """创建测试用 StockInfo 对象"""
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
    day_offset: int = 0,
    close: Decimal = Decimal("15.00"),
) -> KlineBar:
    """创建测试用 KlineBar 对象"""
    return KlineBar(
        time=datetime(2024, 6, 10 + day_offset),
        symbol=symbol,
        freq="1d",
        open=Decimal("14.80"),
        high=Decimal("15.20"),
        low=Decimal("14.70"),
        close=close,
        volume=1000000,
        amount=Decimal("15000000.00"),
        turnover=Decimal("5.50"),
        vol_ratio=Decimal("1.20"),
    )


def _make_money_flow(
    symbol: str = "000001.SZ",
    trade_date: date = date(2024, 6, 10),
    main_net_inflow: Decimal | None = Decimal("1500.00"),
    large_order_ratio: Decimal | None = Decimal("35.00"),
) -> MoneyFlow:
    """创建测试用 MoneyFlow 对象"""
    mf = MoneyFlow()
    mf.symbol = symbol
    mf.trade_date = trade_date
    mf.main_net_inflow = main_net_inflow
    mf.large_order_ratio = large_order_ratio
    mf.main_inflow = Decimal("5000.00")
    mf.main_outflow = Decimal("3500.00")
    mf.main_net_inflow_pct = Decimal("3.50")
    mf.large_order_net = Decimal("800.00")
    mf.north_net_inflow = None
    mf.north_hold_ratio = None
    mf.on_dragon_tiger = False
    mf.dragon_tiger_net = None
    mf.block_trade_amount = None
    mf.block_trade_discount = None
    mf.bid_ask_ratio = None
    mf.inner_outer_ratio = None
    mf.updated_at = None
    return mf


def _make_moneyflow_ths(
    ts_code: str = "000001.SZ",
    trade_date: str = "20240610",
    buy_elg_amount: float | None = 5000.0,
    sell_elg_amount: float | None = 1000.0,
    buy_lg_amount: float | None = 3000.0,
    sell_lg_amount: float | None = 1000.0,
    buy_md_amount: float | None = 2000.0,
    sell_md_amount: float | None = 500.0,
) -> MoneyflowThs:
    row = MoneyflowThs()
    row.ts_code = ts_code
    row.trade_date = trade_date
    row.buy_sm_amount = 500.0
    row.sell_sm_amount = 1200.0
    row.buy_md_amount = buy_md_amount
    row.sell_md_amount = sell_md_amount
    row.buy_lg_amount = buy_lg_amount
    row.sell_lg_amount = sell_lg_amount
    row.buy_elg_amount = buy_elg_amount
    row.sell_elg_amount = sell_elg_amount
    row.net_mf_amount = 6500.0
    return row


def _make_moneyflow_dc(
    ts_code: str = "000001.SZ",
    trade_date: str = "20240610",
) -> MoneyflowDc:
    row = MoneyflowDc()
    row.ts_code = ts_code
    row.trade_date = trade_date
    row.buy_sm_amount = 300.0
    row.sell_sm_amount = 900.0
    row.buy_md_amount = 1800.0
    row.sell_md_amount = 500.0
    row.buy_lg_amount = 2600.0
    row.sell_lg_amount = 700.0
    row.buy_elg_amount = 4200.0
    row.sell_elg_amount = 800.0
    row.net_mf_amount = 5600.0
    return row


# ---------------------------------------------------------------------------
# _enrich_money_flow_factors 测试
# ---------------------------------------------------------------------------


class TestEnrichMoneyFlowFactors:
    """测试 _enrich_money_flow_factors 方法"""

    @pytest.mark.asyncio
    async def test_normal_load_with_signal(self):
        """正常加载：连续 2 日净流入 >= 1000 万且大单占比 > 30% 时信号为 True"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "money_flow"}},
        )

        # 模拟连续 2 日净流入 >= 1000 万
        rows = [
            _make_money_flow(
                trade_date=date(2024, 6, 9),
                main_net_inflow=Decimal("1200.00"),
                large_order_ratio=Decimal("32.00"),
            ),
            _make_money_flow(
                trade_date=date(2024, 6, 10),
                main_net_inflow=Decimal("1500.00"),
                large_order_ratio=Decimal("35.00"),
            ),
        ]
        provider._query_money_flow_data = AsyncMock(return_value=rows)

        factor_dict: dict = {"money_flow": False, "large_order": False}
        await provider._enrich_money_flow_factors(
            factor_dict, "000001.SZ", date(2024, 6, 10)
        )

        assert factor_dict["money_flow"] is True
        assert factor_dict["money_flow_value"] == pytest.approx(1500.0)
        assert factor_dict["large_order"] is True
        assert factor_dict["main_net_inflow"] == pytest.approx(1500.0)
        assert factor_dict["large_order_ratio"] == pytest.approx(35.0)

    @pytest.mark.asyncio
    async def test_normal_load_no_signal(self):
        """正常加载：净流入不满足连续条件或大单占比不足时信号为 False"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "money_flow"}},
        )

        # 仅 1 日净流入 >= 1000 万，不满足连续 2 日条件
        rows = [
            _make_money_flow(
                trade_date=date(2024, 6, 9),
                main_net_inflow=Decimal("500.00"),
                large_order_ratio=Decimal("20.00"),
            ),
            _make_money_flow(
                trade_date=date(2024, 6, 10),
                main_net_inflow=Decimal("1500.00"),
                large_order_ratio=Decimal("25.00"),
            ),
        ]
        provider._query_money_flow_data = AsyncMock(return_value=rows)

        factor_dict: dict = {"money_flow": False, "large_order": False}
        await provider._enrich_money_flow_factors(
            factor_dict, "000001.SZ", date(2024, 6, 10)
        )

        assert factor_dict["money_flow"] is False
        assert factor_dict["money_flow_value"] == pytest.approx(1500.0)
        assert factor_dict["large_order"] is False
        # 原始数值仍应写入
        assert factor_dict["main_net_inflow"] == pytest.approx(1500.0)
        assert factor_dict["large_order_ratio"] == pytest.approx(25.0)

    @pytest.mark.asyncio
    async def test_raw_values_written_to_factor_dict(self):
        """原始数值（main_net_inflow、large_order_ratio）应写入 factor_dict"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )

        rows = [
            _make_money_flow(
                trade_date=date(2024, 6, 10),
                main_net_inflow=Decimal("800.00"),
                large_order_ratio=Decimal("28.50"),
            ),
        ]
        provider._query_money_flow_data = AsyncMock(return_value=rows)

        factor_dict: dict = {"money_flow": False, "large_order": False}
        await provider._enrich_money_flow_factors(
            factor_dict, "000001.SZ", date(2024, 6, 10)
        )

        assert factor_dict["main_net_inflow"] == pytest.approx(800.0)
        assert factor_dict["money_flow_value"] == pytest.approx(800.0)
        assert factor_dict["large_order_ratio"] == pytest.approx(28.5)

    @pytest.mark.asyncio
    async def test_missing_data_fallback(self, caplog):
        """缺失数据降级：money_flow 表无记录时设 False 并记录 WARNING"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._query_money_flow_data = AsyncMock(return_value=[])

        factor_dict: dict = {"money_flow": False, "large_order": False}
        with caplog.at_level(logging.WARNING):
            await provider._enrich_money_flow_factors(
                factor_dict, "600000.SH", date(2024, 6, 10)
            )

        assert factor_dict["money_flow"] is False
        assert factor_dict["large_order"] is False
        assert factor_dict["main_net_inflow"] is None
        assert factor_dict["money_flow_value"] is None
        assert factor_dict["large_order_ratio"] is None
        # 验证 WARNING 日志
        assert any("600000.SH" in msg and "无数据记录" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_exception_fallback(self, caplog):
        """异常处理：数据库查询异常时降级为 False 并记录 WARNING"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._query_money_flow_data = AsyncMock(
            side_effect=RuntimeError("DB connection error")
        )

        factor_dict: dict = {"money_flow": False, "large_order": False}
        with caplog.at_level(logging.WARNING):
            await provider._enrich_money_flow_factors(
                factor_dict, "000001.SZ", date(2024, 6, 10)
            )

        assert factor_dict["money_flow"] is False
        assert factor_dict["large_order"] is False
        assert factor_dict["main_net_inflow"] is None
        assert factor_dict["money_flow_value"] is None
        assert factor_dict["large_order_ratio"] is None
        assert any("异常" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_none_values_in_money_flow_record(self):
        """money_flow 记录中 main_net_inflow 或 large_order_ratio 为 None 时使用 0.0"""
        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )

        rows = [
            _make_money_flow(
                trade_date=date(2024, 6, 10),
                main_net_inflow=None,
                large_order_ratio=None,
            ),
        ]
        provider._query_money_flow_data = AsyncMock(return_value=rows)

        factor_dict: dict = {"money_flow": False, "large_order": False}
        await provider._enrich_money_flow_factors(
            factor_dict, "000001.SZ", date(2024, 6, 10)
        )

        # 净流入为 0 不满足 >= 1000 万条件
        assert factor_dict["money_flow"] is False
        # 大单占比为 0 不满足 > 30% 条件
        assert factor_dict["large_order"] is False
        # 原始数值为 None
        assert factor_dict["main_net_inflow"] is None
        assert factor_dict["money_flow_value"] is None
        assert factor_dict["large_order_ratio"] is None


class TestSelectedMoneyFlowSource:
    """测试资金流数据源三选一接入。"""

    @pytest.mark.asyncio
    async def test_moneyflow_ths_selected_only_queries_ths(self):
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "moneyflow_ths"}},
        )
        provider._query_moneyflow_ths = AsyncMock(return_value=[_make_moneyflow_ths()])
        provider._query_moneyflow_dc = AsyncMock(return_value=[_make_moneyflow_dc()])

        stocks_data = {"000001.SZ": {"money_flow": False}}
        await provider._enrich_selected_money_flow_factors(
            stocks_data, date(2024, 6, 10), "moneyflow_ths"
        )

        data = stocks_data["000001.SZ"]
        assert data["money_flow"] is True
        assert data["money_flow_value"] == pytest.approx(7500.0)
        assert data["main_net_inflow"] == pytest.approx(7500.0)
        provider._query_moneyflow_ths.assert_awaited_once()
        provider._query_moneyflow_dc.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_moneyflow_dc_selected_only_queries_dc(self):
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "moneyflow_dc"}},
        )
        provider._query_moneyflow_ths = AsyncMock(return_value=[_make_moneyflow_ths()])
        provider._query_moneyflow_dc = AsyncMock(return_value=[_make_moneyflow_dc()])

        stocks_data = {"000001.SZ": {"money_flow": False}}
        await provider._enrich_selected_money_flow_factors(
            stocks_data, date(2024, 6, 10), "moneyflow_dc"
        )

        data = stocks_data["000001.SZ"]
        assert data["money_flow"] is True
        assert data["money_flow_value"] == pytest.approx(6600.0)
        provider._query_moneyflow_dc.assert_awaited_once()
        provider._query_moneyflow_ths.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_selected_source_uses_latest_available_date(self):
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "moneyflow_dc"}},
        )
        provider._query_moneyflow_dc = AsyncMock(side_effect=[[], [_make_moneyflow_dc()]])
        provider._resolve_latest_moneyflow_date = AsyncMock(return_value="20260429")

        rows, actual_date = await provider._query_selected_moneyflow_rows(
            MagicMock(), "moneyflow_dc", date(2026, 4, 30), "20260430",
        )

        assert actual_date == "20260429"
        assert len(rows) == 1
        assert provider._query_moneyflow_dc.await_args_list[0].args[1] == "20260430"
        assert provider._query_moneyflow_dc.await_args_list[1].args[1] == "20260429"

    @pytest.mark.asyncio
    async def test_selected_source_missing_does_not_fallback(self):
        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "moneyflow_ths"}},
        )
        provider._query_moneyflow_ths = AsyncMock(return_value=[])
        provider._query_moneyflow_dc = AsyncMock(return_value=[_make_moneyflow_dc()])
        provider._resolve_latest_moneyflow_date = AsyncMock(return_value=None)

        stocks_data = {"000001.SZ": {"money_flow": True, "money_flow_value": 1.0}}
        await provider._enrich_selected_money_flow_factors(
            stocks_data, date(2024, 6, 10), "moneyflow_ths"
        )

        data = stocks_data["000001.SZ"]
        assert data["money_flow"] is False
        assert data["money_flow_value"] is None
        assert data["main_net_inflow"] is None
        provider._query_moneyflow_ths.assert_awaited_once()
        provider._query_moneyflow_dc.assert_not_awaited()

    def test_money_flow_percentile_uses_value_not_bool(self):
        stocks_data = {
            "000001.SZ": {"money_flow": False, "money_flow_value": 10.0},
            "000002.SZ": {"money_flow": True, "money_flow_value": 30.0},
            "000003.SZ": {"money_flow": True, "money_flow_value": None},
        }

        ScreenDataProvider._compute_percentile_ranks(stocks_data, ["money_flow"])

        assert stocks_data["000001.SZ"]["money_flow_pctl"] == pytest.approx(50.0)
        assert stocks_data["000002.SZ"]["money_flow_pctl"] == pytest.approx(100.0)
        assert stocks_data["000003.SZ"]["money_flow_pctl"] is None


# ---------------------------------------------------------------------------
# load_screen_data 集成测试（验证资金流因子在主流程中被调用）
# ---------------------------------------------------------------------------


class TestLoadScreenDataMoneyFlow:
    """测试 load_screen_data 中资金流因子的集成"""

    @pytest.mark.asyncio
    async def test_money_flow_enriched_in_main_loop(self):
        """load_screen_data 主循环中应调用 _enrich_money_flow_factors"""
        stock = _make_stock(symbol="000001.SZ")
        bars = [_make_bar(symbol="000001.SZ", day_offset=i) for i in range(3)]

        provider = ScreenDataProvider(
            pg_session=MagicMock(),
            ts_session=MagicMock(),
            strategy_config={"volume_price": {"money_flow_source": "money_flow"}},
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])

        # 模拟资金流数据
        money_flow_rows = [
            _make_money_flow(
                symbol="000001.SZ",
                trade_date=date(2024, 6, 9 + i),
                main_net_inflow=Decimal("1500.00"),
                large_order_ratio=Decimal("35.00"),
            )
            for i in range(2)
        ]
        provider._query_money_flow_data = AsyncMock(return_value=money_flow_rows)

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
        data = result["000001.SZ"]
        # 资金流因子应已被填充（不再是默认的 False）
        assert data["money_flow"] is True
        assert data["large_order"] is True
        assert data["main_net_inflow"] is not None
        assert data["large_order_ratio"] is not None

    @pytest.mark.asyncio
    async def test_money_flow_missing_data_in_main_loop(self, caplog):
        """load_screen_data 中 money_flow 无数据时应降级且不影响其他因子"""
        stock = _make_stock(symbol="600000.SH")
        bars = [_make_bar(symbol="600000.SH", day_offset=i) for i in range(3)]

        provider = ScreenDataProvider(
            pg_session=MagicMock(), ts_session=MagicMock()
        )
        provider._load_valid_stocks = AsyncMock(return_value=[stock])
        provider._query_money_flow_data = AsyncMock(return_value=[])

        with patch(
            "app.services.screener.screen_data_provider.KlineRepository"
        ) as MockRepo, patch(
            "app.services.screener.screen_data_provider.AdjFactorRepository"
        ) as MockAdjRepo:
            mock_repo = MockRepo.return_value
            mock_repo.query = AsyncMock(return_value=bars)
            mock_adj_repo = MockAdjRepo.return_value
            mock_adj_repo.query_batch = AsyncMock(return_value={})

            with caplog.at_level(logging.WARNING):
                result = await provider.load_screen_data()

        assert "600000.SH" in result
        data = result["600000.SH"]
        assert data["money_flow"] is False
        assert data["large_order"] is False
        assert data["main_net_inflow"] is None
        assert data["large_order_ratio"] is None
        # 其他因子应正常存在
        assert "close" in data
        assert "ma_trend" in data
