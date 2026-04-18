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

        # 6. 加载板块强势数据
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
            else:
                logger.warning("数据库会话不可用，跳过板块强势数据加载")
        except Exception:
            logger.warning("加载板块强势数据失败，跳过", exc_info=True)

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
            bo_cfg = _cfg.get("breakout", {}) if isinstance(_cfg.get("breakout"), dict) else {}
            vol_threshold = float(bo_cfg.get("volume_ratio_threshold", 1.5))
            confirm_days = int(bo_cfg.get("confirm_days", 1))
            enable_box = bo_cfg.get("box_breakout", True)
            enable_high = bo_cfg.get("high_breakout", True)
            enable_trendline = bo_cfg.get("trendline_breakout", True)

            if enable_box:
                box = detect_box_breakout(
                    closes_float, highs_float, lows_float, volumes_int,
                    volume_multiplier=vol_threshold,
                )
                if box is not None:
                    # 站稳确认：检查突破后 confirm_days 天是否站稳
                    if confirm_days > 0 and len(closes_float) > 1:
                        from app.services.screener.breakout import check_false_breakout
                        box = check_false_breakout(box, closes_float[-1], hold_days=confirm_days)
                    breakout_signal = {
                        "type": box.breakout_type.value,
                        "resistance": box.resistance_level,
                        "is_valid": box.is_valid,
                        "is_false_breakout": box.is_false_breakout,
                        "volume_ratio": box.volume_ratio,
                        "generates_buy_signal": box.generates_buy_signal,
                    }

            if breakout_signal is None and enable_high:
                prev_high = detect_previous_high_breakout(
                    closes_float, volumes_int,
                    volume_multiplier=vol_threshold,
                )
                if prev_high is not None:
                    if confirm_days > 0 and len(closes_float) > 1:
                        from app.services.screener.breakout import check_false_breakout
                        prev_high = check_false_breakout(prev_high, closes_float[-1], hold_days=confirm_days)
                    breakout_signal = {
                        "type": prev_high.breakout_type.value,
                        "resistance": prev_high.resistance_level,
                        "is_valid": prev_high.is_valid,
                        "is_false_breakout": prev_high.is_false_breakout,
                        "volume_ratio": prev_high.volume_ratio,
                        "generates_buy_signal": prev_high.generates_buy_signal,
                    }

            if breakout_signal is None and enable_trendline:
                trendline = detect_descending_trendline_breakout(
                    closes_float, highs_float, volumes_int,
                    volume_multiplier=vol_threshold,
                )
                if trendline is not None:
                    if confirm_days > 0 and len(closes_float) > 1:
                        from app.services.screener.breakout import check_false_breakout
                        trendline = check_false_breakout(trendline, closes_float[-1], hold_days=confirm_days)
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
