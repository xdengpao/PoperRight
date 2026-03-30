"""
选股数据提供服务

从本地数据库（TimescaleDB + PostgreSQL）查询股票数据，
转换为 ScreenExecutor 所需的 {symbol: factor_dict} 格式。

数据来源：
- TimescaleDB kline 表：K 线行情数据（用于均线计算、形态识别、量价分析）
- PostgreSQL stock_info 表：基本面数据（PE/PB/ROE/市值）
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.models.kline import KlineBar
from app.models.stock import StockInfo
from app.services.data_engine.kline_repository import KlineRepository
from app.services.screener.breakout import (
    detect_box_breakout,
    detect_descending_trendline_breakout,
    detect_previous_high_breakout,
)
from app.services.screener.indicators import (
    calculate_dma,
    detect_boll_signal,
    detect_macd_signal,
    detect_rsi_signal,
)
from app.services.screener.ma_trend import detect_ma_support, score_ma_trend
from app.services.screener.volume_price import (
    check_large_order_signal,
    check_money_flow_signal,
    check_turnover_rate,
)

logger = logging.getLogger(__name__)

# 默认回溯天数（覆盖 MA250 所需的最少交易日）
DEFAULT_LOOKBACK_DAYS = 365


class ScreenDataProvider:
    """
    选股数据提供服务。

    从本地数据库查询全市场有效股票的行情和基本面数据，
    转换为 ScreenExecutor 所需的因子字典格式。
    """

    def __init__(
        self,
        pg_session: AsyncSession | None = None,
        ts_session: AsyncSession | None = None,
    ) -> None:
        self._pg_session = pg_session
        self._ts_session = ts_session

    async def load_screen_data(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        screen_date: date | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        加载选股所需的全市场股票数据。

        1. 从 PostgreSQL stock_info 查询全市场有效股票（排除 ST、退市）
        2. 从 TimescaleDB kline 查询每只股票最近 lookback_days 天的日 K 线
        3. 将 K 线数据和基本面数据转换为因子字典

        Args:
            lookback_days: K 线回溯天数，默认 365（覆盖 MA250）
            screen_date: 选股基准日期，默认今天

        Returns:
            {symbol: factor_dict} 字典，factor_dict 包含 ScreenExecutor 所需的全部因子数据
        """
        if screen_date is None:
            screen_date = date.today()

        start_date = screen_date - timedelta(days=lookback_days)

        # 1. 查询有效股票列表
        stocks = await self._load_valid_stocks()
        if not stocks:
            return {}

        # 2. 查询 K 线数据并转换为因子字典
        kline_repo = KlineRepository(self._ts_session)
        result: dict[str, dict[str, Any]] = {}

        for stock in stocks:
            try:
                bars = await kline_repo.query(
                    symbol=stock.symbol,
                    freq="1d",
                    start=start_date,
                    end=screen_date,
                )
                if not bars:
                    continue  # 无行情数据的股票跳过

                factor_dict = self._build_factor_dict(stock, bars)
                result[stock.symbol] = factor_dict
            except Exception:
                logger.warning(
                    "加载股票 %s 数据失败，跳过", stock.symbol, exc_info=True
                )
                continue

        logger.info(
            "选股数据加载完成：有效股票 %d 只，成功加载 %d 只",
            len(stocks), len(result),
        )
        return result

    async def _load_valid_stocks(self) -> list[StockInfo]:
        """查询全市场有效股票（排除 ST 和退市）。"""
        stmt = select(StockInfo).where(
            StockInfo.is_st == False,  # noqa: E712
            StockInfo.is_delisted == False,  # noqa: E712
        )
        if self._pg_session is not None:
            res = await self._pg_session.execute(stmt)
            return list(res.scalars().all())

        async with AsyncSessionPG() as session:
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    def _build_factor_dict(
        stock: StockInfo,
        bars: list[KlineBar],
    ) -> dict[str, Any]:
        """
        将 StockInfo + KlineBar 列表转换为 ScreenExecutor 所需的因子字典。

        因子字典结构：
        {
            "close": Decimal,           # 最新收盘价
            "open": Decimal,            # 最新开盘价
            "high": Decimal,            # 最新最高价
            "low": Decimal,             # 最新最低价
            "volume": int,              # 最新成交量
            "amount": Decimal,          # 最新成交额
            "turnover": Decimal,        # 最新换手率
            "vol_ratio": Decimal,       # 最新量比
            "closes": list[Decimal],    # 收盘价序列（时间升序）
            "highs": list[Decimal],     # 最高价序列
            "lows": list[Decimal],      # 最低价序列
            "volumes": list[int],       # 成交量序列
            "amounts": list[Decimal],   # 成交额序列
            "turnovers": list[Decimal], # 换手率序列
            # 基本面因子
            "pe_ttm": float | None,
            "pb": float | None,
            "roe": float | None,
            "market_cap": float | None,
            # 派生因子（由各选股模块计算）
            "ma_trend": float,          # 均线趋势打分 0-100
            "ma_support": bool,         # 均线支撑信号
            "macd": bool,               # MACD 多头信号
            "boll": bool,               # BOLL 突破信号
            "rsi": bool,                # RSI 强势信号
            "dma": dict | None,         # DMA 指标结果
            "breakout": dict | None,    # 突破信号
            "turnover_check": bool,     # 换手率筛选
            "money_flow": bool,         # 主力资金信号
            "large_order": bool,        # 大单活跃信号
        }
        """
        latest = bars[-1]  # bars 按时间升序，最后一条为最新

        stock_data: dict[str, Any] = {
            # 股票名称
            "name": stock.name if hasattr(stock, 'name') and stock.name else stock.symbol,
            # 最新行情
            "close": latest.close,
            "open": latest.open,
            "high": latest.high,
            "low": latest.low,
            "volume": latest.volume,
            "amount": latest.amount,
            "turnover": latest.turnover,
            "vol_ratio": latest.vol_ratio,
            # 历史序列（时间升序）
            "closes": [b.close for b in bars],
            "highs": [b.high for b in bars],
            "lows": [b.low for b in bars],
            "volumes": [b.volume for b in bars],
            "amounts": [b.amount for b in bars],
            "turnovers": [b.turnover for b in bars],
            # 基本面因子（来自 stock_info 表）
            "pe_ttm": float(stock.pe_ttm) if stock.pe_ttm is not None else None,
            "pb": float(stock.pb) if stock.pb is not None else None,
            "roe": float(stock.roe) if stock.roe is not None else None,
            "market_cap": float(stock.market_cap) if stock.market_cap is not None else None,
        }

        # --- 派生因子计算 ---
        # 将 Decimal 序列转为 float/int 供模块函数使用
        closes_float = [float(c) for c in stock_data["closes"]]
        highs_float = [float(h) for h in stock_data["highs"]]
        lows_float = [float(lo) for lo in stock_data["lows"]]
        volumes_int = [int(v) for v in stock_data["volumes"]]

        # 均线趋势模块
        try:
            trend_result = score_ma_trend(closes_float)
            stock_data["ma_trend"] = trend_result.score
        except Exception:
            logger.debug("计算 ma_trend 失败", exc_info=True)
            stock_data["ma_trend"] = 0.0

        try:
            support_result = detect_ma_support(closes_float)
            stock_data["ma_support"] = support_result.detected
        except Exception:
            logger.debug("计算 ma_support 失败", exc_info=True)
            stock_data["ma_support"] = False

        # 技术指标模块
        try:
            macd_result = detect_macd_signal(closes_float)
            stock_data["macd"] = macd_result.signal
        except Exception:
            logger.debug("计算 macd 失败", exc_info=True)
            stock_data["macd"] = False

        try:
            boll_result = detect_boll_signal(closes_float)
            stock_data["boll"] = boll_result.signal
        except Exception:
            logger.debug("计算 boll 失败", exc_info=True)
            stock_data["boll"] = False

        try:
            rsi_result = detect_rsi_signal(closes_float)
            stock_data["rsi"] = rsi_result.signal
        except Exception:
            logger.debug("计算 rsi 失败", exc_info=True)
            stock_data["rsi"] = False

        try:
            dma_result = calculate_dma(closes_float)
            stock_data["dma"] = {"dma": dma_result.dma, "ama": dma_result.ama}
        except Exception:
            logger.debug("计算 dma 失败", exc_info=True)
            stock_data["dma"] = None

        # 形态突破模块
        try:
            breakout_signal = None
            box = detect_box_breakout(closes_float, highs_float, lows_float, volumes_int)
            if box is not None:
                breakout_signal = {
                    "type": box.breakout_type.value,
                    "resistance": box.resistance_level,
                    "is_valid": box.is_valid,
                    "is_false_breakout": box.is_false_breakout,
                    "volume_ratio": box.volume_ratio,
                    "generates_buy_signal": box.generates_buy_signal,
                }
            if breakout_signal is None:
                prev_high = detect_previous_high_breakout(closes_float, volumes_int)
                if prev_high is not None:
                    breakout_signal = {
                        "type": prev_high.breakout_type.value,
                        "resistance": prev_high.resistance_level,
                        "is_valid": prev_high.is_valid,
                        "is_false_breakout": prev_high.is_false_breakout,
                        "volume_ratio": prev_high.volume_ratio,
                        "generates_buy_signal": prev_high.generates_buy_signal,
                    }
            if breakout_signal is None:
                trendline = detect_descending_trendline_breakout(
                    closes_float, highs_float, volumes_int
                )
                if trendline is not None:
                    breakout_signal = {
                        "type": trendline.breakout_type.value,
                        "resistance": trendline.resistance_level,
                        "is_valid": trendline.is_valid,
                        "is_false_breakout": trendline.is_false_breakout,
                        "volume_ratio": trendline.volume_ratio,
                        "generates_buy_signal": trendline.generates_buy_signal,
                    }
            stock_data["breakout"] = breakout_signal
        except Exception:
            logger.debug("计算 breakout 失败", exc_info=True)
            stock_data["breakout"] = None

        # 量价资金模块
        try:
            turnover_result = check_turnover_rate(float(latest.turnover))
            stock_data["turnover_check"] = turnover_result.passed
        except Exception:
            logger.debug("计算 turnover_check 失败", exc_info=True)
            stock_data["turnover_check"] = False

        # money_flow 和 large_order 依赖额外数据源，使用安全默认值
        stock_data["money_flow"] = False
        stock_data["large_order"] = False

        return stock_data
