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
import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.schemas import SectorScreenConfig
from app.models.kline import KlineBar
from app.models.money_flow import MoneyFlow
from app.models.sector import SectorConstituent, SectorInfo
from app.models.stock import StockInfo
from app.services.data_engine.adj_factor_repository import AdjFactorRepository
from app.services.data_engine.forward_adjustment import adjust_kline_bars
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
from app.services.screener.sector_strength import SectorStrengthFilter
from app.services.screener.volume_price import (
    check_large_order_signal,
    check_money_flow_signal,
    check_turnover_rate,
)

logger = logging.getLogger(__name__)

# 默认回溯天数（覆盖 MA250 所需的最少交易日）
DEFAULT_LOOKBACK_DAYS = 365

# 资金流数据默认回溯交易日数
_MONEY_FLOW_LOOKBACK_DAYS = 5


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
        strategy_config: dict[str, Any] | None = None,
    ) -> None:
        self._pg_session = pg_session
        self._ts_session = ts_session
        self._strategy_config = strategy_config or {}

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

        # 2. 批量查询所有股票的前复权因子
        adj_repo = AdjFactorRepository(self._ts_session)
        all_symbols = [s.symbol for s in stocks]
        try:
            batch_factors = await adj_repo.query_batch(
                symbols=all_symbols,
                adj_type=1,
                start=start_date,
                end=screen_date,
            )
        except Exception:
            logger.warning("批量查询前复权因子失败，将使用原始K线数据", exc_info=True)
            batch_factors = {}

        # 3. 查询 K 线数据，应用前复权，转换为因子字典
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

                # 前复权处理：在指标计算前调整 OHLC 价格
                raw_close = bars[-1].close  # 保留原始收盘价
                factors = batch_factors.get(stock.symbol, [])
                if factors:
                    latest_factor = factors[-1].adj_factor  # 因子按日期升序，最后一个即最新
                    bars = adjust_kline_bars(bars, factors, latest_factor)
                else:
                    logger.warning(
                        "股票 %s 无前复权因子数据，使用原始K线", stock.symbol
                    )

                factor_dict = self._build_factor_dict(stock, bars, self._strategy_config)
                factor_dict["raw_close"] = raw_close

                # 资金流因子接入（需求 1）：查询 money_flow 表数据
                await self._enrich_money_flow_factors(
                    factor_dict, stock.symbol, screen_date,
                )

                result[stock.symbol] = factor_dict
            except Exception:
                logger.warning(
                    "加载股票 %s 数据失败，跳过", stock.symbol, exc_info=True
                )
                continue

        # 4. 计算百分位排名（percentile 类型因子）
        try:
            percentile_factors = [
                "money_flow", "volume_price", "roe",
                "profit_growth", "market_cap", "revenue_growth",
            ]
            self._compute_percentile_ranks(result, percentile_factors)
        except Exception:
            logger.warning("计算百分位排名失败，跳过", exc_info=True)

        # 5. 计算行业相对值（industry_relative 类型因子）
        try:
            industry_map = await self._build_industry_map()
            # pe 的源字段是 pe_ttm，但注册表名是 pe，需要特殊处理
            # 先用 pe_ttm 作为源字段计算，结果写入 pe_ind_rel
            industry_rel_factors = ["pe_ttm", "pb"]
            self._compute_industry_relative_values(
                result, industry_rel_factors, industry_map,
            )
            # 将 pe_ttm_ind_rel 重命名为 pe_ind_rel（注册表名）
            for symbol_data in result.values():
                if "pe_ttm_ind_rel" in symbol_data:
                    symbol_data["pe_ind_rel"] = symbol_data.pop("pe_ttm_ind_rel")
        except Exception:
            logger.warning("计算行业相对值失败，跳过", exc_info=True)

        # 6. 加载板块强势数据（需求 3）
        #    确保 sector_rank（int|None）和 sector_trend（bool）写入每只股票的
        #    Factor_Dict 内部。加载失败或会话不可用时降级为默认值，选股流程不中断。
        sector_loaded = False
        try:
            sector_cfg_raw = self._strategy_config.get("sector_config")
            if isinstance(sector_cfg_raw, dict):
                sector_cfg = SectorScreenConfig.from_dict(sector_cfg_raw)
            elif isinstance(sector_cfg_raw, SectorScreenConfig):
                sector_cfg = sector_cfg_raw
            else:
                sector_cfg = SectorScreenConfig()

            ssf = SectorStrengthFilter()
            ts_sess = self._ts_session
            pg_sess = self._pg_session

            if ts_sess is not None and pg_sess is not None:
                sector_ranks = await ssf.compute_sector_ranks(
                    ts_session=ts_sess,
                    pg_session=pg_sess,
                    data_source=sector_cfg.sector_data_source,
                    sector_type=sector_cfg.sector_type,
                    period=sector_cfg.sector_period,
                )
                stock_sector_map = await ssf.map_stocks_to_sectors(
                    pg_session=pg_sess,
                    data_source=sector_cfg.sector_data_source,
                    sector_type=sector_cfg.sector_type,
                )
                ssf.filter_by_sector_strength(
                    stocks_data=result,
                    sector_ranks=sector_ranks,
                    stock_sector_map=stock_sector_map,
                    top_n=sector_cfg.sector_top_n,
                )
                sector_loaded = True

                # 需求 3.1：验证 sector_rank 和 sector_trend 类型正确性
                for sym, fd in result.items():
                    sr = fd.get("sector_rank")
                    if sr is not None and not isinstance(sr, int):
                        fd["sector_rank"] = int(sr)
                    st_val = fd.get("sector_trend")
                    if not isinstance(st_val, bool):
                        fd["sector_trend"] = bool(st_val) if st_val else False
            else:
                logger.warning(
                    "数据库会话不可用，板块因子降级为默认值 "
                    "(sector_rank=None, sector_trend=False)"
                )
        except Exception:
            logger.warning(
                "加载板块强势数据失败，板块因子降级为默认值 "
                "(sector_rank=None, sector_trend=False)",
                exc_info=True,
            )

        # 需求 3.2：板块数据加载失败时的降级逻辑
        if not sector_loaded:
            for fd in result.values():
                fd.setdefault("sector_rank", None)
                fd.setdefault("sector_trend", False)
                fd.setdefault("sector_name", None)

        # 7. 加载板块分类数据（需求 9）
        #    批量查询三个数据源（DC/TI/TDX）的板块归属信息，写入每只股票的
        #    factor_dict["sector_classifications"]。加载失败时降级为空分类，
        #    不阻断选股主流程。
        try:
            sector_classifications = await self._load_sector_classifications(
                pg_session=self._pg_session,
                symbols=list(result.keys()),
            )
            for sym, fd in result.items():
                fd["sector_classifications"] = sector_classifications.get(
                    sym, {"DC": [], "TI": [], "TDX": []}
                )
        except Exception:
            logger.warning(
                "加载板块分类数据失败，降级为空分类",
                exc_info=True,
            )
            for fd in result.values():
                fd.setdefault(
                    "sector_classifications", {"DC": [], "TI": [], "TDX": []}
                )

        logger.info(
            "选股数据加载完成：有效股票 %d 只，成功加载 %d 只",
            len(stocks), len(result),
        )
        return result

    # ------------------------------------------------------------------
    # 资金流因子接入（需求 1）
    # ------------------------------------------------------------------

    async def _query_money_flow_data(
        self,
        symbol: str,
        trade_date: date,
        days: int = _MONEY_FLOW_LOOKBACK_DAYS,
    ) -> list[MoneyFlow]:
        """
        从 money_flow 表查询指定股票最近 N 个交易日的资金流数据。

        Args:
            symbol: 股票代码
            trade_date: 基准日期
            days: 回溯交易日数

        Returns:
            MoneyFlow 记录列表（按 trade_date 升序）
        """
        stmt = (
            select(MoneyFlow)
            .where(
                MoneyFlow.symbol == symbol,
                MoneyFlow.trade_date <= trade_date,
            )
            .order_by(MoneyFlow.trade_date.desc())
            .limit(days)
        )

        if self._pg_session is not None:
            res = await self._pg_session.execute(stmt)
            rows = list(res.scalars().all())
        else:
            async with AsyncSessionPG() as session:
                res = await session.execute(stmt)
                rows = list(res.scalars().all())

        # 返回按日期升序
        rows.reverse()
        return rows

    async def _enrich_money_flow_factors(
        self,
        factor_dict: dict[str, Any],
        symbol: str,
        screen_date: date,
    ) -> None:
        """
        查询资金流数据并补充 money_flow / large_order 因子到 factor_dict。

        - 调用 check_money_flow_signal() 计算 money_flow 信号
        - 调用 check_large_order_signal() 计算 large_order 信号
        - 将原始数值（main_net_inflow、large_order_ratio）写入 factor_dict
        - 无数据时降级为 False 并记录 WARNING 日志

        Args:
            factor_dict: 待补充的因子字典（就地修改）
            symbol: 股票代码
            screen_date: 选股基准日期
        """
        try:
            rows = await self._query_money_flow_data(symbol, screen_date)

            if not rows:
                # 缺失数据降级（需求 1.3）
                logger.warning(
                    "股票 %s 在 money_flow 表中无数据记录，资金流因子降级为 False",
                    symbol,
                )
                factor_dict["money_flow"] = False
                factor_dict["large_order"] = False
                factor_dict["main_net_inflow"] = None
                factor_dict["large_order_ratio"] = None
                return

            # 提取最近 N 日主力净流入序列（万元）
            daily_inflows: list[float] = [
                float(r.main_net_inflow) if r.main_net_inflow is not None else 0.0
                for r in rows
            ]

            # 计算 money_flow 信号
            mf_result = check_money_flow_signal(daily_inflows)
            factor_dict["money_flow"] = mf_result.signal

            # 提取当日大单成交占比（最后一条记录）
            latest_row = rows[-1]
            latest_large_order_ratio = (
                float(latest_row.large_order_ratio)
                if latest_row.large_order_ratio is not None
                else 0.0
            )

            # 计算 large_order 信号
            lo_result = check_large_order_signal(latest_large_order_ratio)
            factor_dict["large_order"] = lo_result.signal

            # 写入原始数值以便百分位排名计算（需求 1.4）
            latest_inflow = (
                float(latest_row.main_net_inflow)
                if latest_row.main_net_inflow is not None
                else None
            )
            factor_dict["main_net_inflow"] = latest_inflow
            factor_dict["large_order_ratio"] = (
                float(latest_row.large_order_ratio)
                if latest_row.large_order_ratio is not None
                else None
            )

        except Exception:
            # 异常时降级
            logger.warning(
                "查询股票 %s 资金流数据异常，资金流因子降级为 False",
                symbol,
                exc_info=True,
            )
            factor_dict["money_flow"] = False
            factor_dict["large_order"] = False
            factor_dict["main_net_inflow"] = None
            factor_dict["large_order_ratio"] = None

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
        strategy_config: dict[str, Any] | None = None,
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
            "macd_strength": SignalStrength | None,  # MACD 信号强度（需求 1.4）
            "macd_signal_type": str,    # MACD 信号类型（需求 1.4）
            "boll": bool,               # BOLL 突破信号
            "boll_near_upper_band": bool,  # BOLL 接近上轨风险提示（需求 2.4）
            "boll_hold_days": int,      # BOLL 连续站稳中轨天数（需求 2.4）
            "rsi": bool,                # RSI 强势信号
            "rsi_current": float,       # 当前 RSI 值（需求 3.4）
            "rsi_consecutive_rising": int,  # RSI 连续上升天数（需求 3.4）
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

        # 从策略配置中提取均线参数
        _cfg = strategy_config or {}
        ma_cfg = _cfg.get("ma_trend", {}) if isinstance(_cfg.get("ma_trend"), dict) else {}
        cfg_ma_periods = ma_cfg.get("ma_periods") if isinstance(ma_cfg.get("ma_periods"), list) else None
        cfg_support_ma_lines = ma_cfg.get("support_ma_lines") if isinstance(ma_cfg.get("support_ma_lines"), list) else None
        cfg_slope_threshold = float(ma_cfg.get("slope_threshold", 0.0))

        # 均线趋势模块
        try:
            trend_result = score_ma_trend(closes_float, periods=cfg_ma_periods, slope_threshold=cfg_slope_threshold)
            stock_data["ma_trend"] = trend_result.score
        except Exception:
            logger.debug("计算 ma_trend 失败", exc_info=True)
            stock_data["ma_trend"] = 0.0

        try:
            support_result = detect_ma_support(
                closes_float,
                periods=cfg_ma_periods,
                support_periods=cfg_support_ma_lines,
            )
            stock_data["ma_support"] = support_result.detected
        except Exception:
            logger.debug("计算 ma_support 失败", exc_info=True)
            stock_data["ma_support"] = False

        # 技术指标模块
        # 适配结构化返回值（需求 1.4, 2.4, 3.4）：
        # 各检测函数返回 MACDSignalResult / BOLLSignalResult / RSISignalResult，
        # 将 signal 及附加字段写入 stock_data 供 ScreenExecutor 使用。
        try:
            macd_result = detect_macd_signal(closes_float)
            stock_data["macd"] = macd_result.signal
            stock_data["macd_strength"] = macd_result.strength
            stock_data["macd_signal_type"] = macd_result.signal_type
        except Exception:
            logger.debug("计算 macd 失败", exc_info=True)
            stock_data["macd"] = False
            stock_data["macd_strength"] = None
            stock_data["macd_signal_type"] = "none"

        try:
            boll_result = detect_boll_signal(closes_float)
            stock_data["boll"] = boll_result.signal
            stock_data["boll_near_upper_band"] = boll_result.near_upper_band
            stock_data["boll_hold_days"] = boll_result.hold_days
        except Exception:
            logger.debug("计算 boll 失败", exc_info=True)
            stock_data["boll"] = False
            stock_data["boll_near_upper_band"] = False
            stock_data["boll_hold_days"] = 0

        try:
            rsi_result = detect_rsi_signal(closes_float)
            stock_data["rsi"] = rsi_result.signal
            stock_data["rsi_current"] = rsi_result.current_rsi
            stock_data["rsi_consecutive_rising"] = rsi_result.consecutive_rising
        except Exception:
            logger.debug("计算 rsi 失败", exc_info=True)
            stock_data["rsi"] = False
            stock_data["rsi_current"] = 0.0
            stock_data["rsi_consecutive_rising"] = 0

        try:
            dma_result = calculate_dma(closes_float)
            stock_data["dma"] = {"dma": dma_result.dma, "ama": dma_result.ama}
        except Exception:
            logger.debug("计算 dma 失败", exc_info=True)
            stock_data["dma"] = None

        # 形态突破模块（需求 6：多重突破信号并发检测）
        try:
            bo_cfg = _cfg.get("breakout", {}) if isinstance(_cfg.get("breakout"), dict) else {}
            breakout_list = ScreenDataProvider._detect_all_breakouts(
                closes_float, highs_float, lows_float, volumes_int, bo_cfg,
            )
            # 需求 6.2：向后兼容 - breakout 保留第一个信号（或 None）
            stock_data["breakout"] = breakout_list[0] if breakout_list else None
            stock_data["breakout_list"] = breakout_list
        except Exception:
            logger.debug("计算 breakout 失败", exc_info=True)
            stock_data["breakout"] = None
            stock_data["breakout_list"] = []

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

    # ------------------------------------------------------------------
    # 多重突破信号并发检测（需求 6）
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_all_breakouts(
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[int],
        bo_cfg: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        对所有启用的突破类型逐一检测，返回所有触发的突破信号列表（纯函数，用于属性测试）。

        与旧逻辑不同，不再在检测到第一个突破后停止，而是逐一检测所有启用类型。

        Args:
            closes: 收盘价序列（float，时间升序）
            highs: 最高价序列
            lows: 最低价序列
            volumes: 成交量序列
            bo_cfg: 突破配置字典，可包含 box_breakout、high_breakout、
                    trendline_breakout、volume_ratio_threshold、confirm_days

        Returns:
            list[dict]，每个 dict 包含 type、resistance、is_valid、
            is_false_breakout、volume_ratio、generates_buy_signal
        """
        if bo_cfg is None:
            bo_cfg = {}

        vol_threshold = float(bo_cfg.get("volume_ratio_threshold", 1.5))
        confirm_days = int(bo_cfg.get("confirm_days", 1))
        enable_box = bo_cfg.get("box_breakout", True)
        enable_high = bo_cfg.get("high_breakout", True)
        enable_trendline = bo_cfg.get("trendline_breakout", True)

        breakout_list: list[dict[str, Any]] = []

        def _signal_to_dict(signal) -> dict[str, Any]:
            """将 BreakoutSignal 转换为字典。"""
            return {
                "type": signal.breakout_type.value,
                "resistance": signal.resistance_level,
                "is_valid": signal.is_valid,
                "is_false_breakout": signal.is_false_breakout,
                "volume_ratio": signal.volume_ratio,
                "generates_buy_signal": signal.generates_buy_signal,
            }

        # 箱体突破
        if enable_box:
            box = detect_box_breakout(
                closes, highs, lows, volumes,
                volume_multiplier=vol_threshold,
            )
            if box is not None:
                if confirm_days > 0 and len(closes) > 1:
                    from app.services.screener.breakout import check_false_breakout
                    box = check_false_breakout(box, closes[-1], hold_days=confirm_days)
                breakout_list.append(_signal_to_dict(box))

        # 前期高点突破
        if enable_high:
            prev_high = detect_previous_high_breakout(
                closes, volumes,
                volume_multiplier=vol_threshold,
            )
            if prev_high is not None:
                if confirm_days > 0 and len(closes) > 1:
                    from app.services.screener.breakout import check_false_breakout
                    prev_high = check_false_breakout(prev_high, closes[-1], hold_days=confirm_days)
                breakout_list.append(_signal_to_dict(prev_high))

        # 下降趋势线突破
        if enable_trendline:
            trendline = detect_descending_trendline_breakout(
                closes, highs, volumes,
                volume_multiplier=vol_threshold,
            )
            if trendline is not None:
                if confirm_days > 0 and len(closes) > 1:
                    from app.services.screener.breakout import check_false_breakout
                    trendline = check_false_breakout(trendline, closes[-1], hold_days=confirm_days)
                breakout_list.append(_signal_to_dict(trendline))

        return breakout_list

    # ------------------------------------------------------------------
    # 百分位排名计算（Task 6.1）
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_percentile_ranks(
        stocks_data: dict[str, dict[str, Any]],
        factor_names: list[str],
    ) -> None:
        """
        就地计算百分位排名，写入 {factor}_pctl 字段。

        百分位公式：percentile = (rank_position / total_valid) × 100
        - 排除 None 值
        - 升序排名（值越大排名越高，百分位越高）
        - 结果保证在 [0, 100] 闭区间
        - 全部为 None 时跳过
        - 仅 1 只有效股票时百分位为 100
        - 相同值使用平均排名（average tie-breaking）
        """
        for factor_name in factor_names:
            pctl_field = f"{factor_name}_pctl"

            # 收集所有 (symbol, value) 对，排除 None
            valid_pairs: list[tuple[str, float]] = []
            none_symbols: list[str] = []

            for symbol, data in stocks_data.items():
                val = data.get(factor_name)
                if val is None:
                    none_symbols.append(symbol)
                else:
                    valid_pairs.append((symbol, float(val)))

            # 全部为 None 时跳过
            if not valid_pairs:
                for symbol in none_symbols:
                    stocks_data[symbol][pctl_field] = None
                continue

            total_valid = len(valid_pairs)

            # 仅 1 只有效股票时百分位为 100
            if total_valid == 1:
                sym, _ = valid_pairs[0]
                stocks_data[sym][pctl_field] = 100.0
                for symbol in none_symbols:
                    stocks_data[symbol][pctl_field] = None
                continue

            # 按值升序排序
            valid_pairs.sort(key=lambda x: x[1])

            # 分配排名（1-based），相同值使用平均排名
            # 先按值分组
            rank_map: dict[str, float] = {}
            i = 0
            while i < total_valid:
                j = i
                # 找到所有相同值的范围
                while j < total_valid and valid_pairs[j][1] == valid_pairs[i][1]:
                    j += 1
                # 位置 i..j-1 的排名为 (i+1 + j) / 2（平均排名）
                avg_rank = (i + 1 + j) / 2.0
                for k in range(i, j):
                    sym, _ = valid_pairs[k]
                    rank_map[sym] = avg_rank
                i = j

            # 计算百分位
            for sym, rank_pos in rank_map.items():
                pctl = (rank_pos / total_valid) * 100.0
                stocks_data[sym][pctl_field] = pctl

            # None 值股票的 _pctl 设为 None
            for symbol in none_symbols:
                stocks_data[symbol][pctl_field] = None

    # ------------------------------------------------------------------
    # 行业相对值计算（Task 6.2）
    # ------------------------------------------------------------------

    async def _build_industry_map(self) -> dict[str, str]:
        """
        从 SectorConstituent 构建 symbol → 行业板块代码 映射。
        查询 sector_type = 'INDUSTRY' 的最新成分股数据。
        """
        pg_session = self._pg_session
        if pg_session is None:
            logger.warning("PostgreSQL 会话不可用，无法构建行业映射")
            return {}

        try:
            # 查询可用的数据源，优先使用 "DC"
            data_source = "DC"

            # 查询该数据源下 INDUSTRY 类型的板块代码
            sector_codes_stmt = (
                select(SectorInfo.sector_code)
                .where(
                    SectorInfo.data_source == data_source,
                    SectorInfo.sector_type == "INDUSTRY",
                )
            )
            sector_result = await pg_session.execute(sector_codes_stmt)
            valid_sector_codes = {row[0] for row in sector_result.all()}

            if not valid_sector_codes:
                # 尝试其他数据源
                fallback_stmt = (
                    select(SectorInfo.data_source)
                    .where(SectorInfo.sector_type == "INDUSTRY")
                    .limit(1)
                )
                fb_result = await pg_session.execute(fallback_stmt)
                fb_row = fb_result.scalar_one_or_none()
                if fb_row is None:
                    logger.warning("未找到任何 INDUSTRY 类型板块信息")
                    return {}
                data_source = fb_row
                sector_codes_stmt = (
                    select(SectorInfo.sector_code)
                    .where(
                        SectorInfo.data_source == data_source,
                        SectorInfo.sector_type == "INDUSTRY",
                    )
                )
                sector_result = await pg_session.execute(sector_codes_stmt)
                valid_sector_codes = {row[0] for row in sector_result.all()}

            if not valid_sector_codes:
                return {}

            # 查询最新交易日
            latest_date_stmt = (
                select(func.max(SectorConstituent.trade_date))
                .where(
                    SectorConstituent.data_source == data_source,
                    SectorConstituent.sector_code.in_(valid_sector_codes),
                )
            )
            date_result = await pg_session.execute(latest_date_stmt)
            latest_date = date_result.scalar_one_or_none()

            if latest_date is None:
                logger.warning("未找到 INDUSTRY 成分股交易日数据")
                return {}

            # 查询成分股数据
            stmt = (
                select(SectorConstituent)
                .where(
                    SectorConstituent.data_source == data_source,
                    SectorConstituent.trade_date == latest_date,
                    SectorConstituent.sector_code.in_(valid_sector_codes),
                )
            )
            result = await pg_session.execute(stmt)
            constituents = list(result.scalars().all())

            # 构建 symbol → sector_code 映射（如果一只股票属于多个行业，取第一个）
            mapping: dict[str, str] = {}
            for c in constituents:
                if c.symbol not in mapping:
                    mapping[c.symbol] = c.sector_code

            logger.debug(
                "构建行业映射 data_source=%s date=%s 股票数=%d",
                data_source, latest_date, len(mapping),
            )
            return mapping

        except Exception:
            logger.warning("构建行业映射异常", exc_info=True)
            return {}

    @staticmethod
    def _compute_industry_relative_values(
        stocks_data: dict[str, dict[str, Any]],
        factor_names: list[str],
        industry_map: dict[str, str],
    ) -> None:
        """
        就地计算行业相对值，写入 {factor}_ind_rel 字段。

        行业相对值 = 个股因子值 / 行业中位数
        - 按 industry_map 分组
        - 计算每个行业的中位数
        - 行业中位数为零或股票无行业归属时设为 None
        """
        for factor_name in factor_names:
            ind_rel_field = f"{factor_name}_ind_rel"

            # 按行业分组收集有效值
            industry_values: dict[str, list[float]] = {}
            for symbol, data in stocks_data.items():
                industry_code = industry_map.get(symbol)
                if industry_code is None:
                    continue
                val = data.get(factor_name)
                if val is None:
                    continue
                if industry_code not in industry_values:
                    industry_values[industry_code] = []
                industry_values[industry_code].append(float(val))

            # 计算每个行业的中位数
            industry_medians: dict[str, float] = {}
            for industry_code, values in industry_values.items():
                if values:
                    industry_medians[industry_code] = statistics.median(values)

            # 计算行业相对值
            for symbol, data in stocks_data.items():
                industry_code = industry_map.get(symbol)
                val = data.get(factor_name)

                # 无行业归属 → None
                if industry_code is None:
                    data[ind_rel_field] = None
                    continue

                # 因子值为 None → None
                if val is None:
                    data[ind_rel_field] = None
                    continue

                median = industry_medians.get(industry_code)

                # 行业中位数为零或不存在 → None
                if median is None or median == 0:
                    # 行业内仅 1 只有效股票时，相对值为 1.0
                    industry_vals = industry_values.get(industry_code, [])
                    if len(industry_vals) == 1:
                        data[ind_rel_field] = 1.0
                    else:
                        data[ind_rel_field] = None
                    continue

                data[ind_rel_field] = float(val) / median

    # ------------------------------------------------------------------
    # 板块分类数据加载（需求 9）
    # ------------------------------------------------------------------

    async def _load_sector_classifications(
        self,
        pg_session: AsyncSession,
        symbols: list[str],
        trade_date: date | None = None,
    ) -> dict[str, dict[str, list[str]]]:
        """
        批量加载所有股票在三个数据源（DC/TI/TDX）的板块分类信息。

        一次查询 SectorConstituent 表获取所有目标股票的成分股记录，
        再批量查询 SectorInfo 表将 sector_code 转换为人类可读的板块名称，
        避免 N+1 查询。

        Args:
            pg_session: PostgreSQL 异步会话
            symbols: 股票代码列表
            trade_date: 交易日期（可选，默认使用表中最新交易日）

        Returns:
            {symbol: {"DC": [板块名, ...], "TI": [...], "TDX": [...]}} 映射
        """
        _DATA_SOURCES = ["DC", "TI", "TDX"]

        if not symbols:
            return {}

        # 若 trade_date 为 None，查询最新交易日
        if trade_date is None:
            latest_date_stmt = select(
                func.max(SectorConstituent.trade_date)
            ).where(
                SectorConstituent.data_source.in_(_DATA_SOURCES),
            )
            date_result = await pg_session.execute(latest_date_stmt)
            trade_date = date_result.scalar_one_or_none()
            if trade_date is None:
                logger.warning("SectorConstituent 表中无交易日数据，返回空分类")
                return {}

        # 1. 批量查询成分股记录
        constituents_stmt = (
            select(SectorConstituent)
            .where(
                SectorConstituent.symbol.in_(symbols),
                SectorConstituent.trade_date == trade_date,
                SectorConstituent.data_source.in_(_DATA_SOURCES),
            )
        )
        result = await pg_session.execute(constituents_stmt)
        constituents = list(result.scalars().all())

        if not constituents:
            return {}

        # 2. 收集所有 (sector_code, data_source) 对，批量查询 SectorInfo
        sector_keys: set[tuple[str, str]] = set()
        for c in constituents:
            sector_keys.add((c.sector_code, c.data_source))

        # 提取唯一的 sector_code 和 data_source 用于查询
        unique_codes = {k[0] for k in sector_keys}
        unique_sources = {k[1] for k in sector_keys}

        info_stmt = (
            select(
                SectorInfo.sector_code,
                SectorInfo.data_source,
                SectorInfo.name,
            )
            .where(
                SectorInfo.sector_code.in_(unique_codes),
                SectorInfo.data_source.in_(unique_sources),
            )
        )
        info_result = await pg_session.execute(info_stmt)
        info_rows = info_result.all()

        # 构建 (sector_code, data_source) → name 映射
        name_map: dict[tuple[str, str], str] = {}
        for row in info_rows:
            name_map[(row.sector_code, row.data_source)] = row.name

        # 3. 构建 symbol → {"DC": [...], "TI": [...], "TDX": [...]} 结果
        classifications: dict[str, dict[str, list[str]]] = {}
        for c in constituents:
            if c.symbol not in classifications:
                classifications[c.symbol] = {src: [] for src in _DATA_SOURCES}

            # 若 SectorInfo 中缺少该 sector_code，使用原始值作为板块名称
            sector_name = name_map.get(
                (c.sector_code, c.data_source), c.sector_code
            )
            source_list = classifications[c.symbol][c.data_source]
            if sector_name not in source_list:
                source_list.append(sector_name)

        return classifications
