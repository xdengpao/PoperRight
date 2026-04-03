"""
历史回测核心引擎

需求 12：策略历史回测
- 12.1: 可配置起止日期、初始资金、买入手续费(0.03%)、卖出手续费(0.13%+0.1%印花税)、滑点(0.1%)
- 12.2: 输出 9 项绩效指标
- 12.3: 收益曲线、最大回撤曲线、持仓明细、交易流水；支持数据导出
- 12.4: 按牛市/熊市/震荡市分段回测
- 12.5: 严格遵守 A 股 T+1 规则
"""

from __future__ import annotations

import csv
import io
import logging
import math
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.schemas import (
    BacktestConfig, BacktestResult, KlineBar, ScreenItem,
    ScreenResult, StrategyConfig, RiskLevel,
)
from app.services.screener.screen_executor import ScreenExecutor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class _PositionEntry:
    """内部持仓记录"""
    symbol: str
    quantity: int
    cost_price: Decimal
    buy_date: date  # 买入日期，用于 T+1 判定


@dataclass
class _TradeRecord:
    """内部交易流水"""
    date: date
    symbol: str
    action: str  # "BUY" / "SELL"
    price: Decimal
    quantity: int
    cost: Decimal  # 手续费 + 滑点
    amount: Decimal  # 成交金额（不含费用）


@dataclass
class _SellSignal:
    """卖出信号"""
    symbol: str
    reason: str   # "STOP_LOSS" | "TREND_BREAK" | "TRAILING_STOP" | "MAX_HOLDING_DAYS"
    trigger_date: date
    priority: int  # 1=止损, 2=趋势破位, 3=移动止盈, 4=持仓超期


@dataclass
class _BacktestPosition:
    """策略驱动回测持仓记录"""
    symbol: str
    quantity: int
    cost_price: Decimal
    buy_date: date
    buy_trade_day_index: int          # 买入时的交易日序号
    highest_close: Decimal            # 持仓期间最高收盘价（用于移动止盈）
    sector: str = ""                  # 所属板块（用于板块仓位限制）
    pending_sell: _SellSignal | None = None  # 跌停延迟卖出信号


@dataclass
class _BacktestState:
    """策略驱动回测状态"""
    cash: Decimal
    frozen_cash: Decimal = Decimal("0")       # 卖出回收的冻结资金（当日不可用）
    positions: dict[str, _BacktestPosition] = field(default_factory=dict)
    trade_records: list[_TradeRecord] = field(default_factory=list)
    equity_snapshots: dict[date, Decimal] = field(default_factory=dict)
    trade_day_index: int = 0


# ---------------------------------------------------------------------------
# 因子按需计算（需求 2：因子按需计算）
# ---------------------------------------------------------------------------

FACTOR_TO_COMPUTE: dict[str, set[str]] = {
    "ma_trend": {"ma_trend"},
    "ma_support": {"ma_trend", "ma_support"},
    "macd": {"macd"},
    "boll": {"boll"},
    "rsi": {"rsi"},
    "dma": {"dma"},
    "breakout": {"breakout"},
}

ALL_FACTORS: set[str] = {"ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout"}


def _extract_required_factors(config: BacktestConfig) -> set[str]:
    """
    从 BacktestConfig.strategy_config.factors 中提取需要计算的因子名称集合。

    - 若 factors 为空列表，返回全部 7 个因子（向后兼容）。
    - 若 factors 非空，返回 factors 中出现的因子名称对应的计算模块集合。
    - 未知因子名称记录 WARNING 日志并忽略。
    """
    factors = config.strategy_config.factors
    if not factors:
        return set(ALL_FACTORS)

    required: set[str] = set()
    for fc in factors:
        compute_set = FACTOR_TO_COMPUTE.get(fc.factor_name)
        if compute_set:
            required.update(compute_set)
        else:
            logger.warning("Unknown factor: %s, ignoring", fc.factor_name)

    return required


# ---------------------------------------------------------------------------
# 预计算指标缓存（需求 3：预计算指标缓存）
# ---------------------------------------------------------------------------

@dataclass
class IndicatorCache:
    """单只股票的预计算指标缓存。

    所有列表与该股票的 KlineBar 列表等长，索引一一对应。
    None 表示该指标未被策略要求，不需要计算。
    """
    closes: list[float]
    highs: list[float]
    lows: list[float]
    volumes: list[int]
    amounts: list[Decimal]
    turnovers: list[Decimal]

    # 以下字段仅在对应因子被激活时填充
    ma_trend_scores: list[float] | None = None
    ma_support_flags: list[bool] | None = None
    macd_signals: list[bool] | None = None
    boll_signals: list[bool] | None = None
    rsi_signals: list[bool] | None = None
    dma_values: list[tuple[float, float] | None] | None = None
    breakout_results: list[dict | None] | None = None


def _precompute_indicators(
    kline_data: dict[str, list[KlineBar]],
    config: BacktestConfig,
    required_factors: set[str],
) -> dict[str, IndicatorCache]:
    """
    一次性预计算所有股票的指标时间序列。

    对每只股票，使用完整K线序列（含预热期）计算各项指标，
    结果存储为与K线等长的时间序列，回测时按索引直接查表。
    仅计算 required_factors 中包含的指标。

    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1
    """
    from app.services.screener.ma_trend import score_ma_trend, detect_ma_support
    from app.services.screener.indicators import (
        detect_macd_signal, detect_boll_signal, detect_rsi_signal, calculate_dma,
    )
    from app.services.screener.breakout import (
        detect_box_breakout, detect_previous_high_breakout,
        detect_descending_trendline_breakout,
    )

    ma_periods = config.strategy_config.ma_periods or [5, 10, 20, 60, 120]
    ind = config.strategy_config.indicator_params

    # Extract indicator params (support both IndicatorParamsConfig and dict)
    if hasattr(ind, "macd_fast"):
        macd_fast = ind.macd_fast
        macd_slow = ind.macd_slow
        macd_signal = ind.macd_signal
        boll_period = ind.boll_period
        boll_std_dev = ind.boll_std_dev
        rsi_period = ind.rsi_period
        dma_short = ind.dma_short
        dma_long = ind.dma_long
    elif isinstance(ind, dict):
        macd_fast = ind.get("macd_fast", 12)
        macd_slow = ind.get("macd_slow", 26)
        macd_signal = ind.get("macd_signal", 9)
        boll_period = ind.get("boll_period", 20)
        boll_std_dev = ind.get("boll_std_dev", 2.0)
        rsi_period = ind.get("rsi_period", 14)
        dma_short = ind.get("dma_short", 10)
        dma_long = ind.get("dma_long", 50)
    else:
        macd_fast, macd_slow, macd_signal = 12, 26, 9
        boll_period, boll_std_dev = 20, 2.0
        rsi_period = 14
        dma_short, dma_long = 10, 50

    cache: dict[str, IndicatorCache] = {}

    for symbol, bars in kline_data.items():
        n = len(bars)
        closes = [float(b.close) for b in bars]
        highs = [float(b.high) for b in bars]
        lows = [float(b.low) for b in bars]
        volumes = [b.volume for b in bars]
        amounts = [b.amount for b in bars]
        turnovers = [b.turnover for b in bars]

        ic = IndicatorCache(
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            amounts=amounts,
            turnovers=turnovers,
        )

        # ----------------------------------------------------------
        # Single-pass indicator computation (O(N) per indicator)
        # Instead of sliding window closes[:i+1] for each i (O(N²)),
        # compute the full series once and extract per-bar values.
        # ----------------------------------------------------------

        # Pre-compute full MA series once (shared by ma_trend and ma_support)
        _need_ma = ("ma_trend" in required_factors or "ma_support" in required_factors)
        if _need_ma:
            from app.services.screener.ma_trend import (
                calculate_multi_ma, _calc_slope, _SLOPE_LOOKBACK,
                _WEIGHT_ALIGNMENT, _WEIGHT_SLOPE, _WEIGHT_DISTANCE,
            )
            full_ma_dict = calculate_multi_ma(closes, ma_periods)
            sorted_ma_periods = sorted(ma_periods)

        # MA trend scores — single-pass using pre-computed MA series
        if "ma_trend" in required_factors:
            scores: list[float] = []
            for i in range(n):
                # --- alignment score ---
                latest_ma: dict[int, float] = {}
                for p in sorted_ma_periods:
                    vals = full_ma_dict.get(p, [])
                    if i < len(vals) and not math.isnan(vals[i]):
                        latest_ma[p] = vals[i]

                avail_p = [p for p in sorted_ma_periods if p in latest_ma]
                total_pairs = max(len(avail_p) - 1, 0)
                aligned_pairs = 0
                for j in range(len(avail_p) - 1):
                    if latest_ma[avail_p[j]] > latest_ma[avail_p[j + 1]]:
                        aligned_pairs += 1
                alignment_score = (aligned_pairs / total_pairs * 100.0) if total_pairs > 0 else 0.0

                # --- slope score ---
                # Compute slopes for ALL periods (matching original behavior)
                slope_values = []
                for p in sorted_ma_periods:
                    vals = full_ma_dict.get(p, [])
                    # Compute slope from vals up to index i (last _SLOPE_LOOKBACK values)
                    valid = []
                    for k in range(i, -1, -1):
                        if k >= len(vals) or math.isnan(vals[k]):
                            break
                        valid.append(vals[k])
                        if len(valid) >= _SLOPE_LOOKBACK:
                            break
                    valid.reverse()
                    if len(valid) >= 2:
                        vn = len(valid)
                        x_mean = (vn - 1) / 2.0
                        y_mean = sum(valid) / vn
                        num = sum((xi - x_mean) * (y - y_mean) for xi, y in enumerate(valid))
                        den = sum((xi - x_mean) ** 2 for xi in range(vn))
                        s = (num / den / y_mean * 100.0) if den > 0 and y_mean > 0 else 0.0
                    else:
                        s = 0.0
                    slope_values.append(s)

                if slope_values:
                    filtered = [max(sv, 0.0) for sv in slope_values]
                    avg_slope = sum(filtered) / len(filtered)
                    slope_score = min(avg_slope * 100.0, 100.0)
                else:
                    slope_score = 0.0

                # --- distance score ---
                dist_scores = []
                current_price = closes[i]
                for p in sorted_ma_periods:
                    vals = full_ma_dict.get(p, [])
                    if i < len(vals) and not math.isnan(vals[i]) and vals[i] > 0:
                        pct_above = ((current_price - vals[i]) / vals[i]) * 100.0
                        ds = max(0.0, min(100.0, 50.0 + pct_above * 10.0))
                        dist_scores.append(ds)
                distance_score = (sum(dist_scores) / len(dist_scores)) if dist_scores else 0.0

                raw = (alignment_score * _WEIGHT_ALIGNMENT
                       + slope_score * _WEIGHT_SLOPE
                       + distance_score * _WEIGHT_DISTANCE)
                scores.append(max(0.0, min(100.0, raw)))
            ic.ma_trend_scores = scores

        # MA support flags — single-pass using pre-computed MA series
        if "ma_support" in required_factors:
            from app.services.screener.ma_trend import _SUPPORT_TOUCH_PCT, _SUPPORT_REBOUND_DAYS
            support_periods = [p for p in [20, 60] if p in ma_periods] or [20, 60]
            flags: list[bool] = []
            for i in range(n):
                detected = False
                min_req = max(support_periods) + _SUPPORT_REBOUND_DAYS + 1
                if i + 1 >= min_req:
                    for sp in support_periods:
                        ma_vals = full_ma_dict.get(sp, [])
                        if not ma_vals:
                            continue
                        search_end = i - _SUPPORT_REBOUND_DAYS
                        search_start = max(sp - 1, 0)
                        for t in range(search_end, search_start - 1, -1):
                            if t >= len(ma_vals) or math.isnan(ma_vals[t]):
                                continue
                            ma_val = ma_vals[t]
                            if ma_val <= 0:
                                continue
                            distance_pct = abs(closes[t] - ma_val) / ma_val
                            if distance_pct > _SUPPORT_TOUCH_PCT:
                                continue
                            rebound_ok = True
                            for d in range(1, _SUPPORT_REBOUND_DAYS + 1):
                                fi = t + d
                                if fi > i or fi >= len(ma_vals) or math.isnan(ma_vals[fi]):
                                    rebound_ok = False
                                    break
                                if closes[fi] <= ma_vals[fi]:
                                    rebound_ok = False
                                    break
                            if rebound_ok:
                                detected = True
                                break
                        if detected:
                            break
                flags.append(detected)
            ic.ma_support_flags = flags

        # MACD signals — compute full series once, derive per-bar signals
        if "macd" in required_factors:
            from app.services.screener.indicators import calculate_macd
            full_macd = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
            macd_sigs: list[bool] = []
            for i in range(n):
                if i < 1:
                    macd_sigs.append(False)
                    continue
                dif_i = full_macd.dif[i]
                dea_i = full_macd.dea[i]
                dif_prev = full_macd.dif[i - 1]
                dea_prev = full_macd.dea[i - 1]
                bar_i = full_macd.macd[i]
                bar_prev = full_macd.macd[i - 1]
                if any(math.isnan(v) for v in [dif_i, dea_i, dif_prev, dea_prev, bar_i, bar_prev]):
                    macd_sigs.append(False)
                    continue
                sig = (
                    dif_i > 0 and dea_i > 0  # above zero
                    and dif_prev <= dea_prev and dif_i > dea_i  # golden cross
                    and bar_i > bar_prev and bar_i > 0  # bar expanding
                    and dea_i > dea_prev  # DEA rising
                )
                macd_sigs.append(sig)
            ic.macd_signals = macd_sigs

        # BOLL signals — compute full series once, derive per-bar signals
        if "boll" in required_factors:
            from app.services.screener.indicators import calculate_boll
            full_boll = calculate_boll(closes, boll_period, boll_std_dev)
            boll_sigs: list[bool] = []
            for i in range(n):
                if i < 1:
                    boll_sigs.append(False)
                    continue
                up_i = full_boll.upper[i]
                mid_i = full_boll.middle[i]
                low_i = full_boll.lower[i]
                up_prev = full_boll.upper[i - 1]
                low_prev = full_boll.lower[i - 1]
                if any(math.isnan(v) for v in [up_i, mid_i, low_i, up_prev, low_prev]):
                    boll_sigs.append(False)
                    continue
                bw_i = up_i - low_i
                bw_prev = up_prev - low_prev
                sig = (
                    closes[i] > mid_i  # above middle
                    and closes[i] >= up_i * 0.98  # touch upper
                    and bw_i > bw_prev  # opening up
                )
                boll_sigs.append(sig)
            ic.boll_signals = boll_sigs

        # RSI signals — compute full series once, derive per-bar signals
        if "rsi" in required_factors:
            from app.services.screener.indicators import calculate_rsi
            full_rsi = calculate_rsi(closes, rsi_period)
            rsi_sigs: list[bool] = []
            for i in range(n):
                if i < rsi_period:
                    rsi_sigs.append(False)
                    continue
                rsi_val = full_rsi.values[i]
                if math.isnan(rsi_val):
                    rsi_sigs.append(False)
                    continue
                cond_range = 50.0 <= rsi_val <= 80.0
                # Divergence check (same logic as detect_rsi_signal)
                lookback = min(rsi_period, i)
                cond_no_div = True
                if lookback >= 2:
                    ws = i - lookback
                    pmax_idx = ws
                    for j in range(ws, i):
                        if not math.isnan(full_rsi.values[j]) and closes[j] >= closes[pmax_idx]:
                            pmax_idx = j
                    if (closes[i] >= closes[pmax_idx]
                            and pmax_idx != i
                            and not math.isnan(full_rsi.values[pmax_idx])
                            and rsi_val < full_rsi.values[pmax_idx]):
                        cond_no_div = False
                rsi_sigs.append(cond_range and cond_no_div)
            ic.rsi_signals = rsi_sigs

        # DMA values — compute full series once, extract per-bar values
        if "dma" in required_factors:
            full_dma = calculate_dma(closes, dma_short, dma_long)
            dma_vals: list[tuple[float, float] | None] = []
            for i in range(n):
                if i < len(full_dma.dma) and i < len(full_dma.ama):
                    d_val = full_dma.dma[i]
                    a_val = full_dma.ama[i]
                    if not math.isnan(d_val) and not math.isnan(a_val):
                        dma_vals.append((d_val, a_val))
                    else:
                        dma_vals.append(None)
                else:
                    dma_vals.append(None)
            ic.dma_values = dma_vals

        # Breakout results (trailing window — O(N) instead of O(N²))
        # Breakout detectors only need the last ~80 bars (max lookback=60
        # + volume_avg=20). We use a 120-bar trailing window for safety.
        if "breakout" in required_factors:
            _BRK_WINDOW = 120
            brk_results: list[dict | None] = []
            for i in range(n):
                brk_dict: dict | None = None
                if i + 1 >= 21:
                    start = max(0, i + 1 - _BRK_WINDOW)
                    sub_closes = closes[start: i + 1]
                    sub_highs = highs[start: i + 1]
                    sub_lows = lows[start: i + 1]
                    sub_volumes = volumes[start: i + 1]
                    for detect_fn in (
                        lambda c=sub_closes, h=sub_highs, lo=sub_lows, v=sub_volumes: detect_box_breakout(c, h, lo, v),
                        lambda c=sub_closes, v=sub_volumes: detect_previous_high_breakout(c, v),
                        lambda c=sub_closes, h=sub_highs, v=sub_volumes: detect_descending_trendline_breakout(c, h, v),
                    ):
                        sig = detect_fn()
                        if sig and sig.is_valid:
                            brk_dict = {
                                "is_valid": sig.is_valid,
                                "is_false_breakout": sig.is_false_breakout,
                                "volume_ratio": sig.volume_ratio,
                            }
                            break
                brk_results.append(brk_dict)
            ic.breakout_results = brk_results

        cache[symbol] = ic

    return cache


# ---------------------------------------------------------------------------
# K线数据预索引（需求 4：K线数据预索引）
# ---------------------------------------------------------------------------

@dataclass
class KlineDateIndex:
    """单只股票的日期→K线索引映射"""
    date_to_idx: dict[date, int]   # 日期 → bars列表中的索引
    sorted_dates: list[date]       # 排序后的日期列表（用于二分查找）


def _build_date_index(
    kline_data: dict[str, list[KlineBar]],
) -> dict[str, KlineDateIndex]:
    """
    为所有股票构建日期→索引映射。

    bars[date_to_idx[d]] 即为日期 d 的K线数据。
    对于重复日期，后出现的记录覆盖先出现的（dict 赋值语义）。
    sorted_dates 保证严格递增（去重后排序）。
    """
    result: dict[str, KlineDateIndex] = {}

    for symbol, bars in kline_data.items():
        date_to_idx: dict[date, int] = {}

        for i, bar in enumerate(bars):
            d = bar.time.date()
            date_to_idx[d] = i  # 重复日期：后出现的覆盖先出现的

        # sorted_dates 从 date_to_idx 的键构建，保证唯一且严格递增
        sorted_dates = sorted(date_to_idx.keys())

        result[symbol] = KlineDateIndex(
            date_to_idx=date_to_idx,
            sorted_dates=sorted_dates,
        )

    return result


def _get_bars_up_to(
    index: KlineDateIndex,
    trade_date: date,
) -> int:
    """
    返回 <= trade_date 的最后一个K线索引（bars 列表中的位置），无匹配返回 -1。

    使用 bisect_right 在 sorted_dates 上做 O(log N) 二分查找，
    找到最后一个 <= trade_date 的日期，再通过 date_to_idx 映射到 bars 索引。

    Requirements: 4.5, 4.6, 4.7
    """
    pos = bisect_right(index.sorted_dates, trade_date)
    if pos == 0:
        return -1
    last_date = index.sorted_dates[pos - 1]
    return index.date_to_idx[last_date]


# ---------------------------------------------------------------------------
# MarketEnvironmentClassifier（需求 12.4）
# ---------------------------------------------------------------------------

class MarketEnvironmentClassifier:
    """市场环境分类器：识别牛市/熊市/震荡市"""

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"

    @staticmethod
    def classify_market(index_closes: list[float], lookback: int = 60) -> str:
        """
        根据指数收盘价序列判断当前市场环境。

        规则：
        - BULL: price > MA60 且 MA20 > MA60
        - BEAR: price < MA60 且 MA20 < MA60
        - SIDEWAYS: 其他情况

        Parameters
        ----------
        index_closes : list[float]
            指数收盘价序列（按时间升序），长度应 >= lookback
        lookback : int
            MA 长周期，默认 60

        Returns
        -------
        str  "BULL" / "BEAR" / "SIDEWAYS"
        """
        if len(index_closes) < lookback:
            return MarketEnvironmentClassifier.SIDEWAYS

        ma60 = sum(index_closes[-lookback:]) / lookback
        ma20 = sum(index_closes[-20:]) / 20 if len(index_closes) >= 20 else ma60
        price = index_closes[-1]

        if price > ma60 and ma20 > ma60:
            return MarketEnvironmentClassifier.BULL
        elif price < ma60 and ma20 < ma60:
            return MarketEnvironmentClassifier.BEAR
        else:
            return MarketEnvironmentClassifier.SIDEWAYS

    @staticmethod
    def segment_by_environment(
        index_data: list[tuple[date, float]],
        lookback: int = 60,
    ) -> list[tuple[str, date, date]]:
        """
        将指数时间序列按市场环境分段。

        Parameters
        ----------
        index_data : list[tuple[date, float]]
            (日期, 收盘价) 列表，按日期升序
        lookback : int
            MA 长周期

        Returns
        -------
        list[tuple[str, date, date]]
            [(环境, 起始日期, 结束日期), ...]
        """
        if not index_data:
            return []

        classifier = MarketEnvironmentClassifier
        segments: list[tuple[str, date, date]] = []
        closes: list[float] = []

        current_env: str | None = None
        seg_start: date | None = None

        for d, close in index_data:
            closes.append(close)
            env = classifier.classify_market(closes, lookback)

            if current_env is None:
                current_env = env
                seg_start = d
            elif env != current_env:
                # 结束上一段，开始新段
                segments.append((current_env, seg_start, d))
                current_env = env
                seg_start = d

        # 关闭最后一段
        if current_env is not None and seg_start is not None:
            segments.append((current_env, seg_start, index_data[-1][0]))

        return segments


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """历史回测引擎"""

    def run_backtest(
        self,
        config: BacktestConfig,
        signals: list[dict] | None = None,
        kline_data: dict[str, list[KlineBar]] | None = None,
        index_data: dict[str, list[KlineBar]] | None = None,
    ) -> BacktestResult:
        """
        执行回测。

        如果提供 kline_data，使用策略驱动路径；
        如果提供 signals，使用旧的信号驱动路径。

        Parameters
        ----------
        config : BacktestConfig
            回测参数配置
        signals : list[dict] | None
            交易信号列表（旧路径）
        kline_data : dict[str, list[KlineBar]] | None
            全市场前复权日 K 线数据（策略驱动路径）
        index_data : dict[str, list[KlineBar]] | None
            大盘指数 K 线数据（策略驱动路径）

        Returns
        -------
        BacktestResult
        """
        # 策略驱动路径
        if kline_data is not None:
            return self._run_backtest_strategy_driven(
                config, kline_data, index_data,
            )

        # 旧的信号驱动路径（向后兼容）
        if signals is None:
            signals = []
        cash = config.initial_capital
        positions: dict[str, _PositionEntry] = {}
        trade_records: list[_TradeRecord] = []
        # 按日期排序的净值快照: {date: equity}
        equity_snapshots: dict[date, Decimal] = {}

        # 按日期排序信号
        sorted_signals = sorted(signals, key=lambda s: s["date"])

        for sig in sorted_signals:
            sig_date: date = sig["date"]
            symbol: str = sig["symbol"]
            action: str = sig["action"].upper()
            price = Decimal(str(sig["price"]))
            quantity: int = int(sig["quantity"])

            if action == "BUY":
                buy_cost = self._calc_buy_cost(price, quantity, config)
                total_cost = price * quantity + buy_cost
                if total_cost > cash:
                    continue  # 资金不足，跳过
                cash -= total_cost
                if symbol in positions:
                    pos = positions[symbol]
                    old_total = pos.cost_price * pos.quantity
                    new_total = price * quantity
                    pos.quantity += quantity
                    pos.cost_price = (old_total + new_total) / pos.quantity
                    # 更新买入日期为最新买入日（T+1 约束用最新买入日）
                    pos.buy_date = sig_date
                else:
                    positions[symbol] = _PositionEntry(
                        symbol=symbol,
                        quantity=quantity,
                        cost_price=price,
                        buy_date=sig_date,
                    )
                trade_records.append(_TradeRecord(
                    date=sig_date, symbol=symbol, action="BUY",
                    price=price, quantity=quantity,
                    cost=buy_cost, amount=price * quantity,
                ))

            elif action == "SELL":
                if symbol not in positions:
                    continue  # 无持仓，跳过
                pos = positions[symbol]
                # T+1 规则：买入当日不可卖出
                if pos.buy_date >= sig_date:
                    continue
                sell_qty = min(quantity, pos.quantity)
                if sell_qty <= 0:
                    continue
                sell_cost = self._calc_sell_cost(price, sell_qty, config)
                proceeds = price * sell_qty - sell_cost
                cash += proceeds
                pos.quantity -= sell_qty
                trade_records.append(_TradeRecord(
                    date=sig_date, symbol=symbol, action="SELL",
                    price=price, quantity=sell_qty,
                    cost=sell_cost, amount=price * sell_qty,
                ))
                if pos.quantity <= 0:
                    del positions[symbol]

            # 记录当日净值快照
            equity = cash + sum(
                Decimal(str(sig["price"])) * p.quantity
                if p.symbol == symbol else p.cost_price * p.quantity
                for p in positions.values()
            )
            equity_snapshots[sig_date] = equity

        # 构建净值曲线（按日期排序）
        sorted_dates = sorted(equity_snapshots.keys())
        initial = config.initial_capital
        equity_curve: list[tuple[date, float]] = []
        for d in sorted_dates:
            nav = float(equity_snapshots[d] / initial) if initial else 1.0
            equity_curve.append((d, nav))

        # 如果没有交易，返回空结果
        if not equity_curve:
            return BacktestResult(
                annual_return=0.0,
                total_return=0.0,
                win_rate=0.0,
                profit_loss_ratio=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
                avg_holding_days=0.0,
                equity_curve=[],
                trade_records=[],
            )

        # 计算绩效指标
        metrics = self._calculate_metrics(
            equity_curve, trade_records, config,
        )

        # 序列化交易记录
        serialized_records = [
            {
                "date": str(tr.date),
                "symbol": tr.symbol,
                "action": tr.action,
                "price": float(tr.price),
                "quantity": tr.quantity,
                "cost": float(tr.cost),
                "amount": float(tr.amount),
            }
            for tr in trade_records
        ]

        return BacktestResult(
            annual_return=metrics["annual_return"],
            total_return=metrics["total_return"],
            win_rate=metrics["win_rate"],
            profit_loss_ratio=metrics["profit_loss_ratio"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            total_trades=metrics["total_trades"],
            avg_holding_days=metrics["avg_holding_days"],
            equity_curve=equity_curve,
            trade_records=serialized_records,
        )

    # ------------------------------------------------------------------
    # 分段回测（需求 12.4）
    # ------------------------------------------------------------------

    def run_segment_backtest(
        self,
        config: BacktestConfig,
        signals: list[dict],
        segments: list[tuple[str, date, date]],
    ) -> dict[str, BacktestResult]:
        """
        按市场环境分段执行回测，分别输出各阶段绩效指标。

        Parameters
        ----------
        config : BacktestConfig
            回测参数配置
        signals : list[dict]
            完整交易信号列表
        segments : list[tuple[str, date, date]]
            市场环境分段列表 [(环境, 起始日期, 结束日期), ...]

        Returns
        -------
        dict[str, BacktestResult]
            键为市场环境名称，值为该环境下的回测结果
        """
        results: dict[str, BacktestResult] = {}

        for env, start, end in segments:
            seg_signals = [
                s for s in signals
                if start <= s["date"] <= end
            ]
            result = self.run_backtest(config, seg_signals)
            # 如果同一环境出现多段，合并到已有结果（取最后一段）
            # 简单实现：按 "ENV" 键存储，多段同环境覆盖
            results[env] = result

        return results

    # ------------------------------------------------------------------
    # 手续费计算
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_buy_cost(
        price: Decimal, quantity: int, config: BacktestConfig,
    ) -> Decimal:
        """买入成本 = 成交金额 * 买入费率 + 成交金额 * 滑点"""
        amount = price * quantity
        return amount * config.commission_buy + amount * config.slippage

    @staticmethod
    def _calc_sell_cost(
        price: Decimal, quantity: int, config: BacktestConfig,
    ) -> Decimal:
        """卖出成本 = 成交金额 * 卖出费率 + 成交金额 * 滑点"""
        amount = price * quantity
        return amount * config.commission_sell + amount * config.slippage

    # ------------------------------------------------------------------
    # 涨跌停价格计算（需求 12.33）
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_limit_prices(prev_close: Decimal) -> tuple[Decimal, Decimal]:
        """计算涨跌停价格（主板与创业板统一 ±10%）"""
        limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
        limit_down = (prev_close * Decimal("0.90")).quantize(Decimal("0.01"))
        return limit_up, limit_down

    # ------------------------------------------------------------------
    # 大盘风控模拟（需求 12.26）
    # ------------------------------------------------------------------

    def _evaluate_market_risk(
        self,
        trade_date: date,
        index_data: dict[str, list[KlineBar]] | None,
        index_date_index: dict[str, KlineDateIndex] | None = None,
    ) -> str:
        """
        评估大盘风控状态。

        - 指数跌破 20 日均线 → "CAUTION"
        - 指数跌破 60 日均线 → "DANGER"
        - 其他 → "NORMAL"

        Requirements: 4.5, 4.7
        """
        if not index_data:
            return "NORMAL"

        for index_symbol in ("000001.SH", "399006.SZ"):
            bars = index_data.get(index_symbol)
            if not bars:
                continue
            # 截取 trade_date 及之前的 bars（使用日期索引替代线性扫描）
            idx_info = index_date_index.get(index_symbol) if index_date_index else None
            if idx_info is not None:
                end_idx = _get_bars_up_to(idx_info, trade_date)
                if end_idx < 0:
                    continue
                filtered = bars[:end_idx + 1]
            else:
                filtered = [b for b in bars if b.time.date() <= trade_date]
                if not filtered:
                    continue
            closes = [float(b.close) for b in filtered]
            latest_close = closes[-1]

            # 检查 MA60
            if len(closes) >= 60:
                ma60 = sum(closes[-60:]) / 60
                if latest_close < ma60:
                    return "DANGER"

            # 检查 MA20
            if len(closes) >= 20:
                ma20 = sum(closes[-20:]) / 20
                if latest_close < ma20:
                    return "CAUTION"

        return "NORMAL"

    # ------------------------------------------------------------------
    # 信号生成（需求 12.5–12.6）
    # ------------------------------------------------------------------

    def _generate_buy_signals(
        self,
        trade_date: date,
        kline_data: dict[str, list[KlineBar]],
        config: BacktestConfig,
        market_risk_state: str,
    ) -> list[ScreenItem]:
        """
        生成买入候选信号。

        使用 ScreenExecutor 执行盘后选股，根据大盘风控状态过滤。
        从 K 线数据实时计算各项技术指标，确保不同策略产生差异化筛选结果。
        """
        if market_risk_state == "DANGER":
            return []

        from app.services.screener.ma_trend import score_ma_trend, detect_ma_support
        from app.services.screener.indicators import (
            detect_macd_signal, detect_boll_signal, detect_rsi_signal, calculate_dma,
        )
        from app.services.screener.breakout import (
            detect_box_breakout, detect_previous_high_breakout,
            detect_descending_trendline_breakout,
        )

        ma_periods = config.strategy_config.ma_periods or [5, 10, 20, 60, 120]
        raw_ind = config.strategy_config.indicator_params
        if hasattr(raw_ind, 'macd_fast'):
            # IndicatorParamsConfig dataclass
            ind_params = {
                "macd_fast": raw_ind.macd_fast, "macd_slow": raw_ind.macd_slow,
                "macd_signal": raw_ind.macd_signal, "boll_period": raw_ind.boll_period,
                "boll_std_dev": raw_ind.boll_std_dev, "rsi_period": raw_ind.rsi_period,
                "dma_short": raw_ind.dma_short, "dma_long": raw_ind.dma_long,
            }
        elif isinstance(raw_ind, dict):
            ind_params = raw_ind
        else:
            ind_params = {}

        # 构建因子字典
        stocks_data: dict[str, dict[str, Any]] = {}
        for symbol, bars in kline_data.items():
            filtered = [b for b in bars if b.time.date() <= trade_date]
            if not filtered:
                continue

            latest = filtered[-1]
            closes_dec = [b.close for b in filtered]
            highs_dec = [b.high for b in filtered]
            lows_dec = [b.low for b in filtered]
            volumes = [b.volume for b in filtered]
            amounts = [b.amount for b in filtered]
            turnovers = [b.turnover for b in filtered]

            closes_f = [float(c) for c in closes_dec]
            highs_f = [float(h) for h in highs_dec]
            lows_f = [float(l) for l in lows_dec]

            # ── 均线趋势评分 ──
            ma_result = score_ma_trend(closes_f, ma_periods)
            ma_trend_score = ma_result.score

            # ── 均线支撑 ──
            ma_support_signal = detect_ma_support(closes_f, ma_periods)
            ma_support = ma_support_signal.detected

            # ── MACD 信号 ──
            macd_res = detect_macd_signal(
                closes_f,
                fast_period=ind_params.get("macd_fast", 12),
                slow_period=ind_params.get("macd_slow", 26),
                signal_period=ind_params.get("macd_signal", 9),
            )
            macd_signal = macd_res.signal

            # ── BOLL 信号 ──
            boll_res = detect_boll_signal(
                closes_f,
                period=ind_params.get("boll_period", 20),
                std_dev=ind_params.get("boll_std_dev", 2.0),
            )
            boll_signal = boll_res.signal

            # ── RSI 信号 ──
            rsi_res = detect_rsi_signal(
                closes_f,
                period=ind_params.get("rsi_period", 14),
            )
            rsi_signal = rsi_res.signal

            # ── DMA 指标 ──
            dma_res = calculate_dma(
                closes_f,
                short_period=ind_params.get("dma_short", 10),
                long_period=ind_params.get("dma_long", 50),
            )
            dma_dict: dict | None = None
            if dma_res.dma and dma_res.ama:
                import math as _math
                last_dma = dma_res.dma[-1] if not _math.isnan(dma_res.dma[-1]) else None
                last_ama = dma_res.ama[-1] if not _math.isnan(dma_res.ama[-1]) else None
                if last_dma is not None and last_ama is not None:
                    dma_dict = {"dma": last_dma, "ama": last_ama}

            # ── 形态突破 ──
            breakout_dict: dict | None = None
            if len(closes_f) >= 21:
                for detect_fn in (
                    lambda: detect_box_breakout(closes_f, highs_f, lows_f, volumes),
                    lambda: detect_previous_high_breakout(closes_f, volumes),
                    lambda: detect_descending_trendline_breakout(closes_f, highs_f, volumes),
                ):
                    sig = detect_fn()
                    if sig and sig.is_valid:
                        breakout_dict = {
                            "is_valid": sig.is_valid,
                            "is_false_breakout": sig.is_false_breakout,
                            "volume_ratio": sig.volume_ratio,
                        }
                        break

            stocks_data[symbol] = {
                "name": symbol,
                "close": latest.close,
                "open": latest.open,
                "high": latest.high,
                "low": latest.low,
                "volume": latest.volume,
                "amount": latest.amount,
                "turnover": latest.turnover,
                "vol_ratio": latest.vol_ratio,
                "closes": closes_dec,
                "highs": highs_dec,
                "lows": lows_dec,
                "volumes": volumes,
                "amounts": amounts,
                "turnovers": turnovers,
                "pe_ttm": None,
                "pb": None,
                "roe": None,
                "market_cap": None,
                "ma_trend": ma_trend_score,
                "ma_support": ma_support,
                "macd": macd_signal,
                "boll": boll_signal,
                "rsi": rsi_signal,
                "dma": dma_dict,
                "breakout": breakout_dict,
                "turnover_check": True,
                "money_flow": False,
                "large_order": False,
            }

        if not stocks_data:
            return []

        # 执行选股
        try:
            executor = ScreenExecutor(
                config.strategy_config,
                enabled_modules=config.enabled_modules,
                raw_config=config.raw_config,
            )
            result: ScreenResult = executor.run_eod_screen(stocks_data)
            items = list(result.items)
        except Exception:
            logger.warning("ScreenExecutor 执行失败", exc_info=True)
            return []

        # CAUTION 状态下过滤 trend_score < 90
        if market_risk_state == "CAUTION":
            items = [it for it in items if it.trend_score >= 90]

        # 过滤当日涨幅 > 9% 和连续3日累计涨幅 > 20%
        filtered_items: list[ScreenItem] = []
        for item in items:
            bars = kline_data.get(item.symbol)
            if not bars:
                continue
            day_bars = [b for b in bars if b.time.date() <= trade_date]
            if len(day_bars) < 2:
                filtered_items.append(item)
                continue

            latest_close = float(day_bars[-1].close)
            prev_close = float(day_bars[-2].close)
            daily_gain = (latest_close - prev_close) / prev_close if prev_close > 0 else 0.0
            if daily_gain > 0.09:
                continue

            # 3日累计涨幅
            if len(day_bars) >= 4:
                close_3d_ago = float(day_bars[-4].close)
                cum_gain_3d = (latest_close - close_3d_ago) / close_3d_ago if close_3d_ago > 0 else 0.0
                if cum_gain_3d > 0.20:
                    continue

            filtered_items.append(item)

        return filtered_items

    # ------------------------------------------------------------------
    # 优化后的信号生成（需求 2.1, 3.3, 4.5, 5.1）
    # ------------------------------------------------------------------

    def _generate_buy_signals_optimized(
        self,
        trade_date: date,
        kline_data: dict[str, list[KlineBar]],
        config: BacktestConfig,
        market_risk_state: str,
        indicator_cache: dict[str, IndicatorCache],
        date_index: dict[str, KlineDateIndex],
        required_factors: set[str],
    ) -> list[ScreenItem]:
        """
        优化后的买入信号生成：从缓存查表，不再逐日重算。

        使用 _get_bars_up_to 替代线性扫描，从 IndicatorCache 按索引直接
        读取预计算指标值。仅填充 required_factors 中激活的指标字段。
        保持 ScreenExecutor 调用逻辑不变。

        Requirements: 2.1, 3.3, 4.5, 5.1
        """
        if market_risk_state == "DANGER":
            return []

        ma_periods = config.strategy_config.ma_periods or [5, 10, 20, 60, 120]
        raw_ind = config.strategy_config.indicator_params
        if hasattr(raw_ind, 'macd_fast'):
            ind_params = {
                "macd_fast": raw_ind.macd_fast, "macd_slow": raw_ind.macd_slow,
                "macd_signal": raw_ind.macd_signal, "boll_period": raw_ind.boll_period,
                "boll_std_dev": raw_ind.boll_std_dev, "rsi_period": raw_ind.rsi_period,
                "dma_short": raw_ind.dma_short, "dma_long": raw_ind.dma_long,
            }
        elif isinstance(raw_ind, dict):
            ind_params = raw_ind
        else:
            ind_params = {}

        stocks_data: dict[str, dict[str, Any]] = {}
        for symbol, bars in kline_data.items():
            idx_info = date_index.get(symbol)
            if not idx_info:
                continue

            # O(log N) 查找截止索引
            end_idx = _get_bars_up_to(idx_info, trade_date)
            if end_idx < 0:
                continue

            latest = bars[end_idx]
            ic = indicator_cache.get(symbol)
            if not ic:
                continue

            # 从缓存读取基础数据（截至 end_idx 的切片）
            closes_dec = [b.close for b in bars[: end_idx + 1]]
            highs_dec = [b.high for b in bars[: end_idx + 1]]
            lows_dec = [b.low for b in bars[: end_idx + 1]]
            volumes = ic.volumes[: end_idx + 1]
            amounts = ic.amounts[: end_idx + 1]
            turnovers = ic.turnovers[: end_idx + 1]

            # 从缓存直接读取预计算指标值
            ma_trend_score = ic.ma_trend_scores[end_idx] if ic.ma_trend_scores is not None else 0.0
            ma_support = ic.ma_support_flags[end_idx] if ic.ma_support_flags is not None else False
            macd_signal = ic.macd_signals[end_idx] if ic.macd_signals is not None else False
            boll_signal = ic.boll_signals[end_idx] if ic.boll_signals is not None else False
            rsi_signal = ic.rsi_signals[end_idx] if ic.rsi_signals is not None else False

            # DMA
            dma_dict: dict | None = None
            if ic.dma_values is not None:
                dma_val = ic.dma_values[end_idx]
                if dma_val is not None:
                    dma_dict = {"dma": dma_val[0], "ama": dma_val[1]}

            # Breakout
            breakout_dict: dict | None = None
            if ic.breakout_results is not None:
                breakout_dict = ic.breakout_results[end_idx]

            stocks_data[symbol] = {
                "name": symbol,
                "close": latest.close,
                "open": latest.open,
                "high": latest.high,
                "low": latest.low,
                "volume": latest.volume,
                "amount": latest.amount,
                "turnover": latest.turnover,
                "vol_ratio": latest.vol_ratio,
                "closes": closes_dec,
                "highs": highs_dec,
                "lows": lows_dec,
                "volumes": volumes,
                "amounts": amounts,
                "turnovers": turnovers,
                "pe_ttm": None,
                "pb": None,
                "roe": None,
                "market_cap": None,
                "ma_trend": ma_trend_score,
                "ma_support": ma_support,
                "macd": macd_signal,
                "boll": boll_signal,
                "rsi": rsi_signal,
                "dma": dma_dict,
                "breakout": breakout_dict,
                "turnover_check": True,
                "money_flow": False,
                "large_order": False,
            }

        if not stocks_data:
            return []

        # 执行选股（ScreenExecutor 调用逻辑不变）
        try:
            executor = ScreenExecutor(
                config.strategy_config,
                enabled_modules=config.enabled_modules,
                raw_config=config.raw_config,
            )
            result: ScreenResult = executor.run_eod_screen(stocks_data)
            items = list(result.items)
        except Exception:
            logger.warning("ScreenExecutor 执行失败", exc_info=True)
            return []

        # CAUTION 状态下过滤 trend_score < 90
        if market_risk_state == "CAUTION":
            items = [it for it in items if it.trend_score >= 90]

        # 过滤当日涨幅 > 9% 和连续3日累计涨幅 > 20%
        filtered_items: list[ScreenItem] = []
        for item in items:
            idx_info = date_index.get(item.symbol)
            if not idx_info:
                continue

            end_idx = _get_bars_up_to(idx_info, trade_date)
            if end_idx < 0:
                continue

            sym_bars = kline_data[item.symbol]
            day_bars_len = end_idx + 1

            if day_bars_len < 2:
                filtered_items.append(item)
                continue

            latest_close = float(sym_bars[end_idx].close)
            prev_close = float(sym_bars[end_idx - 1].close)
            daily_gain = (latest_close - prev_close) / prev_close if prev_close > 0 else 0.0
            if daily_gain > 0.09:
                continue

            # 3日累计涨幅
            if day_bars_len >= 4:
                close_3d_ago = float(sym_bars[end_idx - 3].close)
                cum_gain_3d = (latest_close - close_3d_ago) / close_3d_ago if close_3d_ago > 0 else 0.0
                if cum_gain_3d > 0.20:
                    continue

            filtered_items.append(item)

        return filtered_items

    # ------------------------------------------------------------------
    # 卖出条件检测（需求 12.17–12.23）
    # ------------------------------------------------------------------

    def _check_sell_conditions(
        self,
        position: _BacktestPosition,
        trade_date: date,
        kline_data: dict[str, list[KlineBar]],
        config: BacktestConfig,
        date_index: dict[str, KlineDateIndex] | None = None,
    ) -> _SellSignal | None:
        """
        检查单只持仓标的的卖出条件。

        优先级：1=止损, 2=趋势破位, 3=移动止盈, 4=持仓超期。
        停牌（无K线数据）时暂停检测，返回 None。
        """
        bars = kline_data.get(position.symbol)
        if not bars:
            return None

        # 使用日期索引替代线性扫描（Requirements 4.5, 4.7）
        idx_info = date_index.get(position.symbol) if date_index else None
        if idx_info is not None:
            end_idx = _get_bars_up_to(idx_info, trade_date)
            if end_idx < 0:
                return None
            day_bars = bars[: end_idx + 1]
        else:
            day_bars = [b for b in bars if b.time.date() <= trade_date]
            if not day_bars:
                return None

        # 检查当日是否有数据（停牌检测）
        latest_bar = day_bars[-1]
        if latest_bar.time.date() != trade_date:
            return None  # 停牌

        close = latest_bar.close

        # 更新最高收盘价（涨停日不计入）
        if len(day_bars) >= 2:
            prev_close = day_bars[-2].close
            limit_up, _ = self._calc_limit_prices(prev_close)
            if close > position.highest_close and close < limit_up:
                position.highest_close = close
        elif close > position.highest_close:
            position.highest_close = close

        cost_price = position.cost_price

        # 1. 固定止损
        if cost_price > 0:
            loss_pct = float((cost_price - close) / cost_price)
            if loss_pct >= config.stop_loss_pct:
                return _SellSignal(
                    symbol=position.symbol,
                    reason="STOP_LOSS",
                    trigger_date=trade_date,
                    priority=1,
                )

        # 2. 趋势破位：收盘价跌破 trend_stop_ma 均线
        ma_period = config.trend_stop_ma
        closes_float = [float(b.close) for b in day_bars]
        if len(closes_float) >= ma_period:
            ma_val = sum(closes_float[-ma_period:]) / ma_period
            if float(close) < ma_val:
                return _SellSignal(
                    symbol=position.symbol,
                    reason="TREND_BREAK",
                    trigger_date=trade_date,
                    priority=2,
                )

        # 3. 移动止盈
        if position.highest_close > 0:
            drawdown = float(
                (position.highest_close - close) / position.highest_close
            )
            if drawdown >= config.trailing_stop_pct:
                return _SellSignal(
                    symbol=position.symbol,
                    reason="TRAILING_STOP",
                    trigger_date=trade_date,
                    priority=3,
                )

        # 4. 持仓超期
        state_trade_day_index = getattr(self, "_current_trade_day_index", 0)
        if state_trade_day_index - position.buy_trade_day_index > config.max_holding_days:
            return _SellSignal(
                symbol=position.symbol,
                reason="MAX_HOLDING_DAYS",
                trigger_date=trade_date,
                priority=4,
            )

        return None

    # ------------------------------------------------------------------
    # 候选排序（需求 12.16）
    # ------------------------------------------------------------------

    def _rank_candidates(
        self,
        candidates: list[ScreenItem],
        available_slots: int,
    ) -> list[ScreenItem]:
        """
        按优先级排序候选标的并取前 N 只。

        排序规则：
        1. 趋势评分从高到低
        2. 风险等级从低到高（LOW=0, MEDIUM=1, HIGH=2）
        3. 触发信号数量从多到少
        4. 趋势强度从强到弱（tiebreaker）
        """
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

        def sort_key(item: ScreenItem) -> tuple:
            return (
                -item.trend_score,
                risk_order.get(item.risk_level, 1),
                -len(item.signals),
                -item.trend_score,
            )

        sorted_candidates = sorted(candidates, key=sort_key)
        return sorted_candidates[:available_slots]

    # ------------------------------------------------------------------
    # 资金分配（需求 12.11–12.14）
    # ------------------------------------------------------------------

    def _calculate_buy_amount(
        self,
        candidate: ScreenItem,
        state: _BacktestState,
        config: BacktestConfig,
        open_price: Decimal,
        total_candidates_score: float | None = None,
    ) -> int:
        """
        计算单只标的买入数量（股数）。

        等权模式：单笔金额 = 可用资金 / (max_holdings - 当前持仓数)
        评分加权模式：单笔金额 = 可用资金 * (评分 / 总评分)
        """
        current_positions_count = len(state.positions)
        available_cash = state.cash

        if config.allocation_mode == "score_weighted" and total_candidates_score and total_candidates_score > 0:
            target_amount = available_cash * Decimal(
                str(candidate.trend_score / total_candidates_score)
            )
        else:
            # equal mode
            denominator = config.max_holdings - current_positions_count
            if denominator <= 0:
                return 0
            target_amount = available_cash / Decimal(str(denominator))

        # Cap by max_position_pct
        total_equity = state.cash + sum(
            pos.cost_price * pos.quantity for pos in state.positions.values()
        )
        max_amount = total_equity * Decimal(str(config.max_position_pct))
        target_amount = min(target_amount, max_amount)

        if open_price <= 0:
            return 0

        shares = int(target_amount / open_price)
        shares = (shares // 100) * 100  # round down to 100

        if shares < 100:
            return 0

        return shares

    # ------------------------------------------------------------------
    # 买入执行（需求 12.8–12.16）
    # ------------------------------------------------------------------

    def _execute_buys(
        self,
        candidates: list[ScreenItem],
        trade_date: date,
        kline_data: dict[str, list[KlineBar]],
        state: _BacktestState,
        config: BacktestConfig,
        date_index: dict[str, KlineDateIndex] | None = None,
    ) -> list[_TradeRecord]:
        """
        执行买入委托。

        T+1 开盘价执行，涨停跳过，仓位限制检查。
        """
        available_slots = config.max_holdings - len(state.positions)
        if available_slots <= 0:
            return []

        # 过滤已持仓标的
        new_candidates = [c for c in candidates if c.symbol not in state.positions]
        if not new_candidates:
            return []

        # 排序并取前 available_slots
        ranked = self._rank_candidates(new_candidates, available_slots)
        if not ranked:
            return []

        # 计算总评分（score_weighted 模式用）
        total_candidates_score = sum(c.trend_score for c in ranked) if config.allocation_mode == "score_weighted" else None

        trade_records: list[_TradeRecord] = []

        for candidate in ranked:
            symbol = candidate.symbol
            bars = kline_data.get(symbol)
            if not bars:
                continue

            # 使用日期索引替代线性扫描（Requirements 4.5, 4.7）
            idx_info = date_index.get(symbol) if date_index else None
            if idx_info is not None:
                end_idx = _get_bars_up_to(idx_info, trade_date)

                # 找 trade_date 之后的第一个交易日 bar（T+1 执行）
                if end_idx + 1 >= len(bars):
                    continue  # 无后续数据
                next_day_bar = bars[end_idx + 1]

                # 获取 trade_date 当日收盘价计算涨跌停
                if end_idx < 0:
                    continue
                prev_close = bars[end_idx].close
            else:
                # 找 trade_date 之后的第一个交易日 bar（T+1 执行）
                next_day_bars = [b for b in bars if b.time.date() > trade_date]
                if not next_day_bars:
                    continue  # 停牌或无后续数据
                next_day_bar = next_day_bars[0]

                # 获取 trade_date 当日收盘价计算涨跌停
                day_bars = [b for b in bars if b.time.date() <= trade_date]
                if not day_bars:
                    continue
                prev_close = day_bars[-1].close

            open_price = next_day_bar.open
            limit_up, _ = self._calc_limit_prices(prev_close)

            # 涨停无法买入
            if open_price >= limit_up:
                continue

            # 板块仓位限制检查
            sector = getattr(candidate, "sector", "") or ""
            if sector and config.max_sector_pct > 0:
                total_equity = state.cash + sum(
                    pos.cost_price * pos.quantity for pos in state.positions.values()
                )
                sector_value = sum(
                    pos.cost_price * pos.quantity
                    for pos in state.positions.values()
                    if pos.sector == sector
                )
                if total_equity > 0 and float(sector_value / total_equity) >= config.max_sector_pct:
                    continue

            # 计算买入数量
            shares = self._calculate_buy_amount(
                candidate, state, config, open_price, total_candidates_score,
            )
            if shares == 0:
                continue

            # 计算成本
            buy_cost = self._calc_buy_cost(open_price, shares, config)
            total_cost = open_price * shares + buy_cost
            if total_cost > state.cash:
                continue

            # 执行买入
            state.cash -= total_cost
            state.positions[symbol] = _BacktestPosition(
                symbol=symbol,
                quantity=shares,
                cost_price=open_price,
                buy_date=next_day_bar.time.date(),
                buy_trade_day_index=state.trade_day_index,
                highest_close=open_price,
                sector=sector,
            )

            record = _TradeRecord(
                date=next_day_bar.time.date(),
                symbol=symbol,
                action="BUY",
                price=open_price,
                quantity=shares,
                cost=buy_cost,
                amount=open_price * shares,
            )
            trade_records.append(record)
            state.trade_records.append(record)

        return trade_records

    # ------------------------------------------------------------------
    # 卖出执行（需求 12.23）
    # ------------------------------------------------------------------

    def _execute_sells(
        self,
        sell_signals: list[_SellSignal],
        trade_date: date,
        kline_data: dict[str, list[KlineBar]],
        state: _BacktestState,
        config: BacktestConfig,
        date_index: dict[str, KlineDateIndex] | None = None,
    ) -> list[_TradeRecord]:
        """
        执行卖出委托。

        T+1 开盘价执行，跌停延迟至下一个非跌停交易日。
        卖出回收资金标记为冻结（当日不可用）。
        """
        trade_records: list[_TradeRecord] = []

        for signal in sell_signals:
            symbol = signal.symbol
            if symbol not in state.positions:
                continue
            position = state.positions[symbol]

            bars = kline_data.get(symbol)
            if not bars:
                position.pending_sell = signal
                continue

            # 使用日期索引替代线性扫描（Requirements 4.5, 4.7）
            idx_info = date_index.get(symbol) if date_index else None
            if idx_info is not None:
                end_idx = _get_bars_up_to(idx_info, trade_date)

                # 找 trade_date 之后的第一个交易日 bar
                if end_idx + 1 >= len(bars):
                    position.pending_sell = signal
                    continue
                next_day_bar = bars[end_idx + 1]

                # 获取 trade_date 当日收盘价计算跌停价
                if end_idx < 0:
                    position.pending_sell = signal
                    continue
                prev_close = bars[end_idx].close
            else:
                # 找 trade_date 之后的第一个交易日 bar
                next_day_bars = [b for b in bars if b.time.date() > trade_date]
                if not next_day_bars:
                    position.pending_sell = signal
                    continue
                next_day_bar = next_day_bars[0]

                # 获取 trade_date 当日收盘价计算跌停价
                day_bars = [b for b in bars if b.time.date() <= trade_date]
                if not day_bars:
                    position.pending_sell = signal
                    continue
                prev_close = day_bars[-1].close

            open_price = next_day_bar.open
            _, limit_down = self._calc_limit_prices(prev_close)

            # 跌停无法卖出，延迟
            if open_price <= limit_down:
                position.pending_sell = signal
                continue

            # 执行卖出
            sell_cost = self._calc_sell_cost(open_price, position.quantity, config)
            proceeds = open_price * position.quantity - sell_cost

            # 卖出回收资金标记为冻结（T+1 资金可用）
            state.frozen_cash += proceeds

            record = _TradeRecord(
                date=next_day_bar.time.date(),
                symbol=symbol,
                action="SELL",
                price=open_price,
                quantity=position.quantity,
                cost=sell_cost,
                amount=open_price * position.quantity,
            )
            trade_records.append(record)
            state.trade_records.append(record)

            # 移除持仓
            del state.positions[symbol]

        return trade_records

    # ------------------------------------------------------------------
    # 策略驱动回测主循环（需求 12.5–12.7）
    # ------------------------------------------------------------------

    def _run_backtest_strategy_driven(
        self,
        config: BacktestConfig,
        kline_data: dict[str, list[KlineBar]],
        index_data: dict[str, list[KlineBar]] | None = None,
    ) -> BacktestResult:
        """
        策略驱动回测主入口。

        逐交易日执行：解冻资金 → 处理待卖 → 检查卖出条件 → 执行卖出
        → 评估大盘风控 → 生成买入信号 → 执行买入 → 记录净值快照。
        """
        state = _BacktestState(cash=config.initial_capital)

        # 构建交易日列表
        all_dates: set[date] = set()
        for bars in kline_data.values():
            for b in bars:
                all_dates.add(b.time.date())
        trade_dates = sorted(
            d for d in all_dates
            if config.start_date <= d <= config.end_date
        )

        if not trade_dates:
            return BacktestResult(
                annual_return=0.0,
                total_return=0.0,
                win_rate=0.0,
                profit_loss_ratio=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
                avg_holding_days=0.0,
                equity_curve=[],
                trade_records=[],
            )

        # ----------------------------------------------------------
        # 预计算阶段（Requirements 2.1, 3.1, 4.1）
        # ----------------------------------------------------------
        import time as _time

        _t0 = _time.monotonic()
        required_factors = _extract_required_factors(config)
        logger.info("预计算阶段：激活因子集合 = %s", required_factors)

        date_index = _build_date_index(kline_data)
        logger.info("预计算阶段：日期索引构建完成，股票数 = %d", len(date_index))

        index_date_index = _build_date_index(index_data) if index_data else {}

        indicator_cache = _precompute_indicators(kline_data, config, required_factors)
        _t1 = _time.monotonic()
        logger.info(
            "预计算阶段：指标缓存构建完成，股票数 = %d，耗时 %.2f 秒",
            len(indicator_cache),
            _t1 - _t0,
        )

        for idx, trade_date in enumerate(trade_dates):
            state.trade_day_index = idx
            self._current_trade_day_index = idx  # for _check_sell_conditions

            # 解冻前日卖出资金
            state.cash += state.frozen_cash
            state.frozen_cash = Decimal("0")

            # 处理 pending_sells（跌停延迟的卖出）
            pending_symbols = [
                sym for sym, pos in state.positions.items()
                if pos.pending_sell is not None
            ]
            if pending_symbols:
                pending_signals = []
                for sym in pending_symbols:
                    pos = state.positions[sym]
                    if pos.pending_sell is not None:
                        pending_signals.append(pos.pending_sell)
                        pos.pending_sell = None
                self._execute_sells(pending_signals, trade_date, kline_data, state, config, date_index)

            # 检查卖出条件
            sell_signals: list[_SellSignal] = []
            for symbol, position in list(state.positions.items()):
                signal = self._check_sell_conditions(
                    position, trade_date, kline_data, config, date_index,
                )
                if signal is not None:
                    sell_signals.append(signal)

            # 按优先级排序卖出信号
            sell_signals.sort(key=lambda s: s.priority)

            # 执行卖出
            if sell_signals:
                self._execute_sells(sell_signals, trade_date, kline_data, state, config, date_index)

            # 评估大盘风控
            market_risk = "NORMAL"
            if config.enable_market_risk:
                market_risk = self._evaluate_market_risk(trade_date, index_data, index_date_index)

            # 生成买入信号
            buy_candidates: list[ScreenItem] = []
            if market_risk != "DANGER":
                buy_candidates = self._generate_buy_signals_optimized(
                    trade_date, kline_data, config, market_risk,
                    indicator_cache, date_index, required_factors,
                )

            # 执行买入
            if buy_candidates:
                self._execute_buys(
                    buy_candidates, trade_date, kline_data, state, config, date_index,
                )

            # 记录净值快照（使用日期索引替代线性扫描，Requirements 4.5, 4.7）
            position_value = Decimal("0")
            for pos in state.positions.values():
                pos_bars = kline_data.get(pos.symbol)
                if pos_bars:
                    pos_idx_info = date_index.get(pos.symbol)
                    if pos_idx_info is not None:
                        pos_end_idx = _get_bars_up_to(pos_idx_info, trade_date)
                        if pos_end_idx >= 0:
                            position_value += pos_bars[pos_end_idx].close * pos.quantity
                        else:
                            position_value += pos.cost_price * pos.quantity
                    else:
                        day_bars = [b for b in pos_bars if b.time.date() <= trade_date]
                        if day_bars:
                            position_value += day_bars[-1].close * pos.quantity
                        else:
                            position_value += pos.cost_price * pos.quantity
                else:
                    position_value += pos.cost_price * pos.quantity

            equity = state.cash + state.frozen_cash + position_value
            state.equity_snapshots[trade_date] = equity

        # 构建净值曲线
        initial = config.initial_capital
        sorted_dates = sorted(state.equity_snapshots.keys())
        equity_curve: list[tuple[date, float]] = []
        for d in sorted_dates:
            nav = float(state.equity_snapshots[d] / initial) if initial else 1.0
            equity_curve.append((d, nav))

        if not equity_curve:
            return BacktestResult(
                annual_return=0.0,
                total_return=0.0,
                win_rate=0.0,
                profit_loss_ratio=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
                avg_holding_days=0.0,
                equity_curve=[],
                trade_records=[],
            )

        # 计算绩效指标
        metrics = self._calculate_metrics(
            equity_curve, state.trade_records, config,
        )

        # 序列化交易记录
        serialized_records = [
            {
                "date": str(tr.date),
                "symbol": tr.symbol,
                "action": tr.action,
                "price": float(tr.price),
                "quantity": tr.quantity,
                "cost": float(tr.cost),
                "amount": float(tr.amount),
            }
            for tr in state.trade_records
        ]

        return BacktestResult(
            annual_return=metrics["annual_return"],
            total_return=metrics["total_return"],
            win_rate=metrics["win_rate"],
            profit_loss_ratio=metrics["profit_loss_ratio"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            total_trades=metrics["total_trades"],
            avg_holding_days=metrics["avg_holding_days"],
            equity_curve=equity_curve,
            trade_records=serialized_records,
        )

    # ------------------------------------------------------------------
    # 绩效指标计算
    # ------------------------------------------------------------------

    def _calculate_metrics(
        self,
        equity_curve: list[tuple[date, float]],
        trade_records: list[_TradeRecord],
        config: BacktestConfig,
    ) -> dict:
        """
        计算 9 项绩效指标。

        Returns dict with keys:
            annual_return, total_return, win_rate, profit_loss_ratio,
            max_drawdown, sharpe_ratio, calmar_ratio, total_trades,
            avg_holding_days
        """
        # --- 累计收益率 ---
        final_nav = equity_curve[-1][1] if equity_curve else 1.0
        total_return = final_nav - 1.0

        # --- 年化收益率 ---
        if len(equity_curve) >= 2:
            days = (equity_curve[-1][0] - equity_curve[0][0]).days
            years = max(days / 365.0, 1.0 / 365.0)
            if final_nav > 0:
                annual_return = final_nav ** (1.0 / years) - 1.0
            else:
                annual_return = -1.0
        else:
            annual_return = total_return

        # --- 最大回撤 ---
        max_drawdown = self._calc_max_drawdown(equity_curve)

        # --- 日收益率序列（用于夏普比率）---
        daily_returns: list[float] = []
        for i in range(1, len(equity_curve)):
            prev_nav = equity_curve[i - 1][1]
            curr_nav = equity_curve[i][1]
            if prev_nav != 0:
                daily_returns.append(curr_nav / prev_nav - 1.0)

        # --- 夏普比率（无风险利率 = 0）---
        if daily_returns and len(daily_returns) >= 2:
            avg_ret = sum(daily_returns) / len(daily_returns)
            std_ret = (
                sum((r - avg_ret) ** 2 for r in daily_returns)
                / (len(daily_returns) - 1)
            ) ** 0.5
            if std_ret > 0:
                sharpe_ratio = (avg_ret / std_ret) * (252 ** 0.5)
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # --- 卡玛比率 ---
        if max_drawdown > 0:
            calmar_ratio = annual_return / max_drawdown
        else:
            calmar_ratio = 0.0

        # --- 交易次数、胜率、盈亏比、平均持仓天数 ---
        sell_records = [r for r in trade_records if r.action == "SELL"]
        buy_records = [r for r in trade_records if r.action == "BUY"]
        total_trades = len(sell_records)

        # 匹配买卖对计算胜率和盈亏比
        wins = 0
        total_profit = Decimal("0")
        total_loss = Decimal("0")
        holding_days_sum = 0
        matched_trades = 0

        # 按 symbol 分组匹配 FIFO
        buy_queue: dict[str, list[_TradeRecord]] = {}
        for br in buy_records:
            buy_queue.setdefault(br.symbol, []).append(br)

        for sr in sell_records:
            if sr.symbol in buy_queue and buy_queue[sr.symbol]:
                br = buy_queue[sr.symbol].pop(0)
                pnl = (sr.price - br.price) * sr.quantity - sr.cost - br.cost
                days_held = (sr.date - br.date).days
                holding_days_sum += max(days_held, 1)
                matched_trades += 1
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                elif pnl < 0:
                    total_loss += abs(pnl)

        win_rate = wins / total_trades if total_trades > 0 else 0.0
        if total_loss > 0:
            profit_loss_ratio = float(total_profit / total_loss)
        else:
            profit_loss_ratio = float(total_profit) if total_profit > 0 else 0.0
        avg_holding_days = (
            holding_days_sum / matched_trades if matched_trades > 0 else 0.0
        )

        return {
            "annual_return": annual_return,
            "total_return": total_return,
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "calmar_ratio": calmar_ratio,
            "total_trades": total_trades,
            "avg_holding_days": avg_holding_days,
        }

    @staticmethod
    def _calc_max_drawdown(equity_curve: list[tuple[date, float]]) -> float:
        """计算最大回撤 [0, 1]"""
        if not equity_curve:
            return 0.0
        peak = equity_curve[0][1]
        max_dd = 0.0
        for _, nav in equity_curve:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    # ------------------------------------------------------------------
    # 收益曲线 & 最大回撤曲线数据
    # ------------------------------------------------------------------

    @staticmethod
    def generate_drawdown_curve(
        equity_curve: list[tuple[date, float]],
    ) -> list[tuple[date, float]]:
        """
        根据净值曲线生成最大回撤曲线数据。

        Returns list of (date, drawdown_pct) where drawdown_pct in [0, 1].
        """
        if not equity_curve:
            return []
        peak = equity_curve[0][1]
        result: list[tuple[date, float]] = []
        for d, nav in equity_curve:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0.0
            result.append((d, dd))
        return result

    # ------------------------------------------------------------------
    # CSV 导出
    # ------------------------------------------------------------------

    @staticmethod
    def export_result_to_csv(result: BacktestResult) -> bytes:
        """
        将回测结果导出为 CSV 字节流。

        包含两个部分：
        1. 绩效指标摘要
        2. 交易流水明细
        """
        buf = io.StringIO()
        writer = csv.writer(buf)

        # 绩效指标
        writer.writerow(["=== 绩效指标 ==="])
        writer.writerow(["指标", "值"])
        writer.writerow(["年化收益率", f"{result.annual_return:.4f}"])
        writer.writerow(["累计收益率", f"{result.total_return:.4f}"])
        writer.writerow(["胜率", f"{result.win_rate:.4f}"])
        writer.writerow(["盈亏比", f"{result.profit_loss_ratio:.4f}"])
        writer.writerow(["最大回撤", f"{result.max_drawdown:.4f}"])
        writer.writerow(["夏普比率", f"{result.sharpe_ratio:.4f}"])
        writer.writerow(["卡玛比率", f"{result.calmar_ratio:.4f}"])
        writer.writerow(["总交易次数", result.total_trades])
        writer.writerow(["平均持仓天数", f"{result.avg_holding_days:.1f}"])
        writer.writerow([])

        # 交易流水
        writer.writerow(["=== 交易流水 ==="])
        writer.writerow(["日期", "股票代码", "方向", "价格", "数量", "手续费", "成交金额"])
        for tr in result.trade_records:
            writer.writerow([
                tr.get("date", ""),
                tr.get("symbol", ""),
                tr.get("action", ""),
                tr.get("price", ""),
                tr.get("quantity", ""),
                tr.get("cost", ""),
                tr.get("amount", ""),
            ])

        return buf.getvalue().encode("utf-8-sig")
