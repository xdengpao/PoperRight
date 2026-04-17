"""
K线缺失时指标计算处理机制 — 边界条件单元测试

测试底层指标函数在各种边界条件下的行为。
需求: 1.1 ~ 1.10
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.ma_trend import calculate_ma
from app.services.screener.indicators import (
    _ema,
    calculate_macd,
    calculate_boll,
    calculate_rsi,
    calculate_dma,
)


# ---------------------------------------------------------------------------
# calculate_ma 边界条件
# ---------------------------------------------------------------------------


class TestCalculateMABoundary:
    """calculate_ma 周期为 0、负数、1 的行为"""

    def test_period_zero_returns_all_nan(self):
        """Period=0 should return all NaN values."""
        closes = [10.0, 20.0, 30.0]
        result = calculate_ma(closes, 0)
        assert len(result) == 3
        assert all(math.isnan(v) for v in result)

    def test_period_negative_returns_all_nan(self):
        """Negative period should return all NaN values."""
        closes = [10.0, 20.0, 30.0]
        result = calculate_ma(closes, -5)
        assert len(result) == 3
        assert all(math.isnan(v) for v in result)

    def test_period_one_returns_closes_themselves(self):
        """Period=1 means MA = each close value itself (no NaN prefix)."""
        closes = [10.0, 20.0, 30.0]
        result = calculate_ma(closes, 1)
        assert len(result) == 3
        # Period=1: NaN prefix length = 0, all values valid
        for i in range(3):
            assert not math.isnan(result[i])
            assert result[i] == pytest.approx(closes[i])

    def test_single_element_period_one(self):
        """Single element with period=1."""
        result = calculate_ma([42.0], 1)
        assert len(result) == 1
        assert result[0] == pytest.approx(42.0)

    def test_single_element_period_greater_than_one(self):
        """Single element with period > 1 returns NaN."""
        result = calculate_ma([42.0], 5)
        assert len(result) == 1
        assert math.isnan(result[0])

    def test_length_exactly_equals_period(self):
        """Input length == period: only last value is valid."""
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = calculate_ma(closes, 5)
        assert len(result) == 5
        # First 4 are NaN
        for i in range(4):
            assert math.isnan(result[i])
        # Last value is valid: average of all 5
        assert result[4] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# _ema 边界条件
# ---------------------------------------------------------------------------


class TestEmaBoundary:
    """_ema 周期为 0、负数的行为"""

    def test_period_zero_returns_all_nan(self):
        """Period=0 should return all NaN values."""
        data = [10.0, 20.0, 30.0]
        result = _ema(data, 0)
        assert len(result) == 3
        assert all(math.isnan(v) for v in result)

    def test_period_negative_returns_all_nan(self):
        """Negative period should return all NaN values."""
        data = [10.0, 20.0, 30.0]
        result = _ema(data, -3)
        assert len(result) == 3
        assert all(math.isnan(v) for v in result)

    def test_single_element_period_one(self):
        """Single element with period=1: value at index 0 is valid (SMA of 1 element)."""
        result = _ema([42.0], 1)
        assert len(result) == 1
        assert not math.isnan(result[0])
        assert result[0] == pytest.approx(42.0)

    def test_single_element_period_greater_than_one(self):
        """Single element with period > 1 returns NaN."""
        result = _ema([42.0], 5)
        assert len(result) == 1
        assert math.isnan(result[0])

    def test_length_exactly_equals_period(self):
        """Input length == period: first period-1 are NaN, last is SMA of all."""
        data = [10.0, 20.0, 30.0]
        result = _ema(data, 3)
        assert len(result) == 3
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        # Index 2 = SMA of [10, 20, 30] = 20
        assert result[2] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 各指标函数输入单元素列表的行为
# ---------------------------------------------------------------------------


class TestSingleElementInput:
    """各指标函数输入单元素列表的行为"""

    def test_macd_single_element(self):
        """MACD with single element: all NaN."""
        result = calculate_macd([100.0])
        assert len(result.dif) == 1
        assert math.isnan(result.dif[0])

    def test_boll_single_element(self):
        """BOLL with single element: all NaN."""
        result = calculate_boll([100.0])
        assert len(result.upper) == 1
        assert math.isnan(result.upper[0])
        assert math.isnan(result.middle[0])
        assert math.isnan(result.lower[0])

    def test_rsi_single_element(self):
        """RSI with single element: all NaN (needs period+1 values)."""
        result = calculate_rsi([100.0])
        assert len(result.values) == 1
        assert math.isnan(result.values[0])

    def test_dma_single_element(self):
        """DMA with single element: all NaN."""
        result = calculate_dma([100.0])
        assert len(result.dma) == 1
        assert math.isnan(result.dma[0])
        assert math.isnan(result.ama[0])


# ---------------------------------------------------------------------------
# 各指标函数输入恰好等于周期长度的列表的行为
# ---------------------------------------------------------------------------


class TestExactPeriodLengthInput:
    """各指标函数输入恰好等于周期长度的列表的行为"""

    def test_macd_exact_slow_period(self):
        """MACD with exactly slow_period elements: DIF has first slow-1 NaN,
        then one valid value at index slow-1."""
        closes = [float(i + 1) for i in range(26)]  # 26 elements = default slow
        result = calculate_macd(closes, fast_period=12, slow_period=26, signal_period=9)
        assert len(result.dif) == 26
        # First 25 are NaN (slow-1 = 25)
        for i in range(25):
            assert math.isnan(result.dif[i])
        # Index 25 should be valid
        assert not math.isnan(result.dif[25])

    def test_boll_exact_period(self):
        """BOLL with exactly period elements: first period-1 NaN, last valid."""
        closes = [float(i + 1) for i in range(20)]  # 20 = default boll period
        result = calculate_boll(closes, period=20)
        assert len(result.middle) == 20
        for i in range(19):
            assert math.isnan(result.middle[i])
        assert not math.isnan(result.middle[19])
        assert not math.isnan(result.upper[19])
        assert not math.isnan(result.lower[19])

    def test_rsi_exact_period_plus_one(self):
        """RSI with exactly period+1 elements: first period NaN, last valid."""
        closes = [float(i + 1) for i in range(15)]  # 15 = default 14 + 1
        result = calculate_rsi(closes, period=14)
        assert len(result.values) == 15
        for i in range(14):
            assert math.isnan(result.values[i])
        assert not math.isnan(result.values[14])

    def test_dma_exact_long_period(self):
        """DMA with exactly long_period elements: DMA has valid value at last index."""
        closes = [float(i + 1) for i in range(50)]  # 50 = default long period
        result = calculate_dma(closes, short_period=10, long_period=50, signal_period=10)
        assert len(result.dma) == 50
        # At index 49 both MA(10) and MA(50) have values, so DMA should be valid
        assert not math.isnan(result.dma[49])


# ---------------------------------------------------------------------------
# BOLL 和 DMA 在数据不足时返回全 NaN 的行为
# ---------------------------------------------------------------------------


class TestBollDmaInsufficientData:
    """BOLL 和 DMA 在数据不足时返回全 NaN 的行为"""

    def test_boll_insufficient_data(self):
        """BOLL with fewer than period elements: all NaN."""
        closes = [10.0, 20.0, 30.0]  # 3 < 20 (default period)
        result = calculate_boll(closes, period=20)
        assert len(result.upper) == 3
        assert all(math.isnan(v) for v in result.upper)
        assert all(math.isnan(v) for v in result.middle)
        assert all(math.isnan(v) for v in result.lower)

    def test_dma_insufficient_data(self):
        """DMA with fewer than long_period elements: DMA all NaN."""
        closes = [10.0, 20.0, 30.0]  # 3 < 50 (default long period)
        result = calculate_dma(closes, short_period=10, long_period=50)
        assert len(result.dma) == 3
        assert all(math.isnan(v) for v in result.dma)
        assert all(math.isnan(v) for v in result.ama)

    def test_boll_period_5_with_3_elements(self):
        """BOLL with period=5 but only 3 elements: all NaN."""
        closes = [10.0, 20.0, 30.0]
        result = calculate_boll(closes, period=5)
        assert len(result.upper) == 3
        assert all(math.isnan(v) for v in result.upper)
        assert all(math.isnan(v) for v in result.middle)
        assert all(math.isnan(v) for v in result.lower)

    def test_dma_long_period_10_with_5_elements(self):
        """DMA with long_period=10 but only 5 elements: all DMA NaN."""
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = calculate_dma(closes, short_period=3, long_period=10)
        assert len(result.dma) == 5
        assert all(math.isnan(v) for v in result.dma)
        assert all(math.isnan(v) for v in result.ama)


# ---------------------------------------------------------------------------
# 预热期覆盖各指标的单元测试
# ---------------------------------------------------------------------------

from datetime import date
from app.core.schemas import IndicatorParamsConfig, StrategyConfig
from app.tasks.backtest import calculate_warmup_start_date


class TestWarmupCoveragePerIndicator:
    """预热期覆盖各指标的单元测试

    验证 calculate_warmup_start_date 针对各指标配置返回的预热天数
    满足最低要求。

    需求: 2.1 ~ 2.8
    """

    def _make_config(
        self,
        ma_periods: list[int] | None = None,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_period: int = 14,
        boll_period: int = 20,
        dma_short: int = 10,
        dma_long: int = 50,
    ) -> StrategyConfig:
        """构建 StrategyConfig 以便测试。"""
        return StrategyConfig(
            ma_periods=ma_periods or [5, 10, 20, 60, 120],
            indicator_params=IndicatorParamsConfig(
                macd_fast=macd_fast,
                macd_slow=macd_slow,
                macd_signal=macd_signal,
                boll_period=boll_period,
                rsi_period=rsi_period,
                dma_short=dma_short,
                dma_long=dma_long,
            ),
        )

    def test_ma120_only_warmup(self):
        """仅配置 MA120 时，预热天数 >= 120 × 1.5 = 180。

        需求: 2.1, 2.2
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5, 10, 20, 60, 120],
            # 使指标预热需求远小于 MA120，以便 MA120 为主导
            macd_fast=2, macd_slow=3, macd_signal=1,
            rsi_period=2, boll_period=3, dma_short=2, dma_long=3,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        assert diff >= 180, f"MA120 warmup should be >= 180, got {diff}"

    def test_macd_warmup(self):
        """配置 MACD(12,26,9) 时，预热天数 >= int(35 × 1.5) = 52。

        需求: 2.4
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5],  # 小的 MA，不主导
            macd_fast=12, macd_slow=26, macd_signal=9,
            rsi_period=2, boll_period=3, dma_short=2, dma_long=3,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        # MACD warmup = macd_slow + macd_signal = 35
        # calendar_days = int(35 * 1.5) = 52
        assert diff >= 52, f"MACD warmup should be >= 52, got {diff}"

    def test_rsi_warmup(self):
        """配置 RSI(14) 时，预热天数 >= int(15 × 1.5) = 22。

        需求: 2.5
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5],
            macd_fast=2, macd_slow=3, macd_signal=1,
            rsi_period=14,
            boll_period=3, dma_short=2, dma_long=3,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        # RSI warmup = rsi_period + 1 = 15
        # calendar_days = int(15 * 1.5) = 22
        assert diff >= 22, f"RSI warmup should be >= 22, got {diff}"

    def test_boll_warmup(self):
        """配置 BOLL(20) 时，预热天数 >= 20 × 1.5 = 30。

        需求: 2.6
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5],
            macd_fast=2, macd_slow=3, macd_signal=1,
            rsi_period=2,
            boll_period=20,
            dma_short=2, dma_long=3,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        assert diff >= 30, f"BOLL warmup should be >= 30, got {diff}"

    def test_dma_warmup(self):
        """配置 DMA(10,50) 时，预热天数 >= 50 × 1.5 = 75。

        需求: 2.7
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5],
            macd_fast=2, macd_slow=3, macd_signal=1,
            rsi_period=2, boll_period=3,
            dma_short=10, dma_long=50,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        assert diff >= 75, f"DMA warmup should be >= 75, got {diff}"

    def test_multiple_indicators_takes_maximum(self):
        """同时配置多个指标时，预热天数取最大值。

        MA120=120, MACD(12,26,9)=35, RSI(14)=15, BOLL(20)=20, DMA(10,50)=50
        最大回看窗口=120, required=max(120, 0)=120, calendar=int(120*1.5)=180

        需求: 2.2, 2.4, 2.5, 2.6, 2.7
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5, 10, 20, 60, 120],
            macd_fast=12, macd_slow=26, macd_signal=9,
            rsi_period=14, boll_period=20,
            dma_short=10, dma_long=50,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=0)
        diff = (start - warmup).days
        # max_lookback = max(120, 35, 20, 15, 50) = 120
        # required = max(0, 120) = 120
        # calendar = int(120 * 1.5) = 180
        assert diff >= 180, f"Multiple indicators warmup should be >= 180, got {diff}"
        # Also must cover each individual indicator's need
        assert diff >= int(35 * 1.5), f"Should cover MACD need (52), got {diff}"
        assert diff >= int(15 * 1.5), f"Should cover RSI need (22), got {diff}"
        assert diff >= 30, f"Should cover BOLL need (30), got {diff}"
        assert diff >= 75, f"Should cover DMA need (75), got {diff}"

    def test_buffer_days_250_warmup(self):
        """buffer_days=250 时，预热天数 >= 250 × 1.5 = 375。

        需求: 2.3, 2.8
        """
        start = date(2024, 6, 1)
        config = self._make_config(
            ma_periods=[5],  # 小 MA，不主导
            macd_fast=2, macd_slow=3, macd_signal=1,
            rsi_period=2, boll_period=3,
            dma_short=2, dma_long=3,
        )
        warmup = calculate_warmup_start_date(start, config, buffer_days=250)
        diff = (start - warmup).days
        assert diff >= 375, f"buffer_days=250 warmup should be >= 375, got {diff}"


# ---------------------------------------------------------------------------
# 日K线缺失处理 — 停牌场景单元测试
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta
from decimal import Decimal as D
from app.services.backtest_engine import KlineDateIndex, _get_bars_up_to
from app.core.schemas import KlineBar


def _make_kline_bar(dt: datetime, symbol: str = "000001", close: float = 10.0) -> KlineBar:
    """Helper to build a minimal KlineBar for testing."""
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq="1d",
        open=D(str(close)),
        high=D(str(close * 1.02)),
        low=D(str(close * 0.98)),
        close=D(str(close)),
        volume=100000,
        amount=D("1000000"),
        turnover=D("1.5"),
        vol_ratio=D("1.0"),
    )


class TestSuspensionScenarios:
    """停牌场景单元测试

    需求: 3.1, 3.2, 3.3
    """

    def test_continuous_suspension_5_days(self):
        """连续停牌 5 天后查询停牌期间的日期，应返回停牌前最后一个交易日的索引。

        K线日期: 1/6, 1/7, 1/8 (然后停牌 1/9~1/13), 1/14
        查询 1/10 应返回索引 2 (1/8)
        """
        dates = [
            date(2024, 1, 6),
            date(2024, 1, 7),
            date(2024, 1, 8),
            # 停牌: 1/9, 1/10, 1/11, 1/12, 1/13
            date(2024, 1, 14),
        ]
        date_to_idx = {d: i for i, d in enumerate(dates)}
        index = KlineDateIndex(date_to_idx=date_to_idx, sorted_dates=dates)

        # Query during suspension period
        result = _get_bars_up_to(index, date(2024, 1, 10))
        assert result == 2  # index of 1/8

        # Also check 1/9 and 1/13
        assert _get_bars_up_to(index, date(2024, 1, 9)) == 2
        assert _get_bars_up_to(index, date(2024, 1, 13)) == 2

    def test_first_day_suspended(self):
        """首日即停牌（trade_date 早于所有K线日期），应返回 -1。"""
        dates = [date(2024, 3, 5), date(2024, 3, 6), date(2024, 3, 7)]
        date_to_idx = {d: i for i, d in enumerate(dates)}
        index = KlineDateIndex(date_to_idx=date_to_idx, sorted_dates=dates)

        # trade_date earlier than all kline dates
        result = _get_bars_up_to(index, date(2024, 3, 4))
        assert result == -1

        result = _get_bars_up_to(index, date(2024, 1, 1))
        assert result == -1

    def test_last_day_suspension(self):
        """末日停牌（trade_date 等于最后一根K线日期），应返回最后一个索引。"""
        dates = [date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3)]
        date_to_idx = {d: i for i, d in enumerate(dates)}
        index = KlineDateIndex(date_to_idx=date_to_idx, sorted_dates=dates)

        result = _get_bars_up_to(index, date(2024, 5, 3))
        assert result == 2  # last index

    def test_single_kline_stock(self):
        """单根K线的股票，查询该日期返回 0，查询更早日期返回 -1。"""
        dates = [date(2024, 7, 15)]
        date_to_idx = {dates[0]: 0}
        index = KlineDateIndex(date_to_idx=date_to_idx, sorted_dates=dates)

        # Query that exact date
        assert _get_bars_up_to(index, date(2024, 7, 15)) == 0

        # Query earlier date
        assert _get_bars_up_to(index, date(2024, 7, 14)) == -1

        # Query later date also returns 0 (last kline before trade_date)
        assert _get_bars_up_to(index, date(2024, 7, 16)) == 0


# ---------------------------------------------------------------------------
# 新股数据不足单元测试
# ---------------------------------------------------------------------------

from app.services.backtest_engine import _precompute_indicators, IndicatorCache
from app.core.schemas import (
    BacktestConfig,
    StrategyConfig as SC,
    IndicatorParamsConfig,
    FactorCondition,
)


def _make_bars(n: int, symbol: str = "NEW001") -> list[KlineBar]:
    """Generate n KlineBars with simple ascending prices."""
    bars = []
    base_dt = datetime(2024, 6, 1, 0, 0, 0)
    for i in range(n):
        close = 10.0 + i * 0.1
        bars.append(KlineBar(
            time=base_dt + timedelta(days=i),
            symbol=symbol,
            freq="1d",
            open=D(str(round(close * 0.99, 2))),
            high=D(str(round(close * 1.02, 2))),
            low=D(str(round(close * 0.98, 2))),
            close=D(str(round(close, 2))),
            volume=100000,
            amount=D("1000000"),
            turnover=D("1.5"),
            vol_ratio=D("1.0"),
        ))
    return bars


def _build_cache(bars: list[KlineBar], symbol: str = "NEW001") -> IndicatorCache:
    """Build IndicatorCache for a single stock with all factors enabled."""
    config = BacktestConfig(
        strategy_config=SC(
            factors=[
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
                FactorCondition(factor_name="macd", operator="==", threshold=True),
                FactorCondition(factor_name="boll", operator="==", threshold=True),
                FactorCondition(factor_name="rsi", operator="==", threshold=True),
            ],
            ma_periods=[5, 10, 20, 60, 120],
            indicator_params=IndicatorParamsConfig(),
        ),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    required_factors = {"ma_trend", "macd", "boll", "rsi"}
    kline_data = {symbol: bars}
    cache = _precompute_indicators(kline_data, config, required_factors)
    return cache[symbol]


class TestNewStockInsufficientData:
    """新股数据不足单元测试

    需求: 3.4, 3.5, 3.6, 3.7, 3.8
    """

    def test_10_klines_ma_trend_scores_all_zero_or_low(self):
        """构造仅有 10 根K线的股票，验证 IndicatorCache 中
        MA120 相关的 ma_trend_scores 远低于正常水平。

        MA120 需要 120 根K线，MA60 需要 60 根K线——均不可用。
        仅配置 MA120 时应全部为 0.0。

        需求: 3.5
        """
        # When only MA120 is configured (no short-period MAs to contribute),
        # scores must be 0.0 since we never have enough data for MA120.
        config_120_only = BacktestConfig(
            strategy_config=SC(
                factors=[
                    FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
                ],
                ma_periods=[120],
                indicator_params=IndicatorParamsConfig(),
            ),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        bars = _make_bars(10)
        cache = _precompute_indicators({"NEW001": bars}, config_120_only, {"ma_trend"})
        ic = cache["NEW001"]

        assert ic.ma_trend_scores is not None
        assert len(ic.ma_trend_scores) == 10
        for i, score in enumerate(ic.ma_trend_scores):
            assert score == 0.0, (
                f"ma_trend_scores[{i}] should be 0.0 for 10-bar stock with MA120 only, got {score}"
            )

    def test_20_klines_macd_first_34_false(self):
        """构造仅有 20 根K线的股票，验证 MACD 信号在前 34 个位置为 False。

        默认 MACD(12,26,9) 需要至少 slow-1=25 个值才能产生首个 DIF，
        20 根K线 < 26，所以所有 MACD 信号应为 False。

        需求: 3.6
        """
        bars = _make_bars(20)
        ic = _build_cache(bars)

        assert ic.macd_signals is not None
        assert len(ic.macd_signals) == 20
        # With 20 bars < slow=26, all MACD values are NaN → all signals False
        for i, sig in enumerate(ic.macd_signals):
            assert sig is False, (
                f"macd_signals[{i}] should be False for 20-bar stock, got {sig}"
            )

    def test_5_klines_all_signals_false_or_zero(self):
        """构造仅有 5 根K线的股票，验证所有指标信号均为 False/0.0/None。

        When configured with only long-period MAs (like MA120), all
        ma_trend_scores are 0.0. MACD, BOLL, RSI all produce False
        since 5 < slow(26), 5 < boll_period(20), 5 < rsi_period+1(15).

        需求: 3.4, 3.5, 3.6, 3.7, 3.8
        """
        bars = _make_bars(5)

        # Use MA120 only so that ma_trend_scores are definitely 0.0
        config = BacktestConfig(
            strategy_config=SC(
                factors=[
                    FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
                    FactorCondition(factor_name="macd", operator="==", threshold=True),
                    FactorCondition(factor_name="boll", operator="==", threshold=True),
                    FactorCondition(factor_name="rsi", operator="==", threshold=True),
                ],
                ma_periods=[120],
                indicator_params=IndicatorParamsConfig(),
            ),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        required_factors = {"ma_trend", "macd", "boll", "rsi"}
        kline_data = {"NEW001": bars}
        cache = _precompute_indicators(kline_data, config, required_factors)
        ic = cache["NEW001"]

        n = 5

        # ma_trend_scores: all 0.0
        assert ic.ma_trend_scores is not None
        assert len(ic.ma_trend_scores) == n
        for i, score in enumerate(ic.ma_trend_scores):
            assert score == 0.0, (
                f"ma_trend_scores[{i}] should be 0.0 for 5-bar stock, got {score}"
            )

        # macd_signals: all False
        assert ic.macd_signals is not None
        assert len(ic.macd_signals) == n
        for i, sig in enumerate(ic.macd_signals):
            assert sig is False, (
                f"macd_signals[{i}] should be False for 5-bar stock, got {sig}"
            )

        # boll_signals: all False
        assert ic.boll_signals is not None
        assert len(ic.boll_signals) == n
        for i, sig in enumerate(ic.boll_signals):
            assert sig is False, (
                f"boll_signals[{i}] should be False for 5-bar stock, got {sig}"
            )

        # rsi_signals: all False
        assert ic.rsi_signals is not None
        assert len(ic.rsi_signals) == n
        for i, sig in enumerate(ic.rsi_signals):
            assert sig is False, (
                f"rsi_signals[{i}] should be False for 5-bar stock, got {sig}"
            )


# ---------------------------------------------------------------------------
# 分钟K线缺失场景单元测试
# ---------------------------------------------------------------------------

from app.services.backtest_engine import _build_minute_day_ranges
from app.services.exit_condition_evaluator import ExitConditionEvaluator
from app.core.schemas import ExitCondition, ExitConditionConfig


class TestBuildMinuteDayRangesMissingData:
    """_build_minute_day_ranges：3 个交易日中第 2 日无分钟数据

    需求: 4.1
    """

    def test_second_day_no_minute_data(self):
        """3 个交易日中第 2 日无分钟数据，验证第 2 日为 (-1, -1)。"""
        symbol = "TEST_M01"
        # Daily klines for 3 days
        daily_bars = [
            _make_kline_bar(datetime(2024, 6, 3, 0, 0, 0), symbol=symbol, close=10.0),
            _make_kline_bar(datetime(2024, 6, 4, 0, 0, 0), symbol=symbol, close=11.0),
            _make_kline_bar(datetime(2024, 6, 5, 0, 0, 0), symbol=symbol, close=12.0),
        ]

        # Minute klines: day 1 and day 3 have data, day 2 doesn't
        minute_bars = [
            # Day 1: 2024-06-03
            KlineBar(
                time=datetime(2024, 6, 3, 9, 30, 0), symbol=symbol, freq="5min",
                open=D("9.90"), high=D("10.20"), low=D("9.80"), close=D("10.00"),
                volume=10000, amount=D("100000"), turnover=D("0.5"), vol_ratio=D("1.0"),
            ),
            KlineBar(
                time=datetime(2024, 6, 3, 9, 35, 0), symbol=symbol, freq="5min",
                open=D("10.00"), high=D("10.30"), low=D("9.90"), close=D("10.10"),
                volume=12000, amount=D("120000"), turnover=D("0.6"), vol_ratio=D("1.0"),
            ),
            # Day 2: 2024-06-04 — NO minute data
            # Day 3: 2024-06-05
            KlineBar(
                time=datetime(2024, 6, 5, 9, 30, 0), symbol=symbol, freq="5min",
                open=D("11.90"), high=D("12.20"), low=D("11.80"), close=D("12.00"),
                volume=15000, amount=D("150000"), turnover=D("0.7"), vol_ratio=D("1.0"),
            ),
        ]

        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        existing_cache: dict[str, IndicatorCache] = {}

        result = _build_minute_day_ranges(kline_data, existing_cache)

        assert symbol in result
        assert "5min" in result[symbol]
        day_ranges = result[symbol]["5min"]

        assert len(day_ranges) == 3

        # Day 1: has minute data → valid range
        assert day_ranges[0] != (-1, -1)
        assert day_ranges[0][0] >= 0
        assert day_ranges[0][1] >= day_ranges[0][0]

        # Day 2: no minute data → sentinel
        assert day_ranges[1] == (-1, -1)

        # Day 3: has minute data → valid range
        assert day_ranges[2] != (-1, -1)
        assert day_ranges[2][0] >= 0


class TestExitConditionEvaluatorSentinelSkip:
    """ExitConditionEvaluator：day_range 为 (-1, -1) 时跳过条件

    需求: 4.2
    """

    def _make_evaluator_context(self, num_bars: int = 10, symbol: str = "TEST_E01"):
        """Create a minimal evaluator context for testing."""
        ic = IndicatorCache(
            closes=[10.0 + i * 0.1 for i in range(num_bars)],
            highs=[10.5 + i * 0.1 for i in range(num_bars)],
            lows=[9.5 + i * 0.1 for i in range(num_bars)],
            volumes=[100000] * num_bars,
            amounts=[D("1000000")] * num_bars,
            turnovers=[D("1.5")] * num_bars,
            opens=[10.0 + i * 0.1 for i in range(num_bars)],
        )
        return ic

    def test_sentinel_day_range_skips_condition(self):
        """day_range 为 (-1, -1) 时跳过分钟频率条件，返回 (False, "")。"""
        evaluator = ExitConditionEvaluator()
        ic = self._make_evaluator_context(num_bars=5)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        # minute_day_ranges: bar_index=1 maps to day with sentinel
        minute_day_ranges = {
            "5min": [
                (0, 9),       # day 0: has data
                (-1, -1),     # day 1: no minute data (sentinel)
                (10, 19),     # day 2: has data
            ],
        }

        exit_indicator_cache = {
            "5min": {"rsi_14": [50.0] * 20},
        }

        # Evaluate at bar_index=1 (sentinel day)
        triggered, reason = evaluator.evaluate(
            config, "TEST_E01", bar_index=1,
            indicator_cache=ic,
            exit_indicator_cache=exit_indicator_cache,
            minute_day_ranges=minute_day_ranges,
        )

        assert triggered is False
        assert reason is None

    def test_bar_index_exceeds_minute_day_ranges_length(self):
        """bar_index 超出 minute_day_ranges 长度时跳过条件。

        需求: 4.5
        """
        evaluator = ExitConditionEvaluator()
        ic = self._make_evaluator_context(num_bars=10)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        # Only 3 days in minute_day_ranges, but bar_index=5
        minute_day_ranges = {
            "5min": [
                (0, 9),
                (10, 19),
                (20, 29),
            ],
        }

        exit_indicator_cache = {
            "5min": {"rsi_14": [50.0] * 30},
        }

        # Evaluate at bar_index=5 (exceeds length 3)
        triggered, reason = evaluator.evaluate(
            config, "TEST_E01", bar_index=5,
            indicator_cache=ic,
            exit_indicator_cache=exit_indicator_cache,
            minute_day_ranges=minute_day_ranges,
        )

        assert triggered is False
        assert reason is None


class TestExitConditionEvaluatorMinuteFallback:
    """ExitConditionEvaluator：分钟缓存不可用时回退到日频缓存

    需求: 4.3
    """

    def test_fallback_to_daily_when_minute_cache_unavailable(self):
        """分钟频率缓存不可用时回退到日频缓存评估。"""
        evaluator = ExitConditionEvaluator()
        num_bars = 5

        ic = IndicatorCache(
            closes=[10.0 + i * 0.1 for i in range(num_bars)],
            highs=[10.5 + i * 0.1 for i in range(num_bars)],
            lows=[9.5 + i * 0.1 for i in range(num_bars)],
            volumes=[100000] * num_bars,
            amounts=[D("1000000")] * num_bars,
            turnovers=[D("1.5")] * num_bars,
            opens=[10.0 + i * 0.1 for i in range(num_bars)],
        )

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        # exit_indicator_cache has daily but NOT 5min
        # The RSI value at bar_index=2 in daily is 85.0 (> 80)
        exit_indicator_cache = {
            "daily": {"rsi_14": [50.0, 60.0, 85.0, 70.0, 55.0]},
            # No "5min" key — will fallback to daily
        }

        # Without minute_day_ranges, it falls back to single bar evaluation
        triggered, reason = evaluator.evaluate(
            config, "TEST_E01", bar_index=2,
            indicator_cache=ic,
            exit_indicator_cache=exit_indicator_cache,
            minute_day_ranges=None,
        )

        # Should evaluate using daily cache — rsi=85 > 80 → triggered
        assert triggered is True
        assert reason is not None
        assert "RSI" in reason


class TestEvaluateSingleMinuteScanningNaN:
    """_evaluate_single_minute_scanning：日内扫描中 NaN 值被跳过

    需求: 4.4
    """

    def test_nan_values_skipped_in_intraday_scan(self):
        """指标值全部为 NaN 时，日内扫描不触发条件。"""
        evaluator = ExitConditionEvaluator()
        num_bars = 10

        ic = IndicatorCache(
            closes=[10.0] * num_bars,
            highs=[11.0] * num_bars,
            lows=[9.0] * num_bars,
            volumes=[100000] * num_bars,
            amounts=[D("1000000")] * num_bars,
            turnovers=[D("1.5")] * num_bars,
            opens=[10.0] * num_bars,
        )

        condition = ExitCondition(
            freq="5min",
            indicator="rsi",
            operator=">",
            threshold=80.0,
            params={"rsi_period": 14},
        )

        # All NaN values in exit cache
        exit_cache = {"rsi_14": [float('nan')] * num_bars}
        day_range = (0, 9)

        triggered, reason = evaluator._evaluate_single_minute_scanning(
            condition, day_range, ic, exit_cache,
        )

        assert triggered is False

    def test_mixed_nan_and_valid_values(self):
        """部分 NaN 部分有效值时，NaN 被跳过，有效值正常评估。"""
        evaluator = ExitConditionEvaluator()
        num_bars = 5

        ic = IndicatorCache(
            closes=[10.0] * num_bars,
            highs=[11.0] * num_bars,
            lows=[9.0] * num_bars,
            volumes=[100000] * num_bars,
            amounts=[D("1000000")] * num_bars,
            turnovers=[D("1.5")] * num_bars,
            opens=[10.0] * num_bars,
        )

        condition = ExitCondition(
            freq="5min",
            indicator="rsi",
            operator=">",
            threshold=80.0,
            params={"rsi_period": 14},
        )

        # Mix of NaN and valid values — bar 3 has RSI=85 which exceeds 80
        exit_cache = {"rsi_14": [float('nan'), float('nan'), 50.0, 85.0, float('nan')]}
        day_range = (0, 4)

        triggered, reason = evaluator._evaluate_single_minute_scanning(
            condition, day_range, ic, exit_cache,
        )

        # Should trigger because bar 3 has RSI=85 > 80
        assert triggered is True
        assert reason is not None
        assert "RSI" in reason


# ---------------------------------------------------------------------------
# 选股引擎缺失数据过滤 — 单元测试
# ---------------------------------------------------------------------------

from app.services.screener.screen_executor import ScreenExecutor
from app.core.schemas import ScreenType


class TestScreenNoSignalFiltering:
    """选股引擎缺失数据过滤测试

    验证选股引擎在指标数据不足/缺失时不纳入选股结果。
    需求: 5.1, 5.2, 5.3, 5.4, 5.5
    """

    def _make_strategy_config(self, logic: str = "AND") -> SC:
        """构建包含所有因子的 StrategyConfig。"""
        return SC(
            factors=[
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=50.0),
                FactorCondition(factor_name="macd", operator="==", threshold=None),
                FactorCondition(factor_name="boll", operator="==", threshold=None),
                FactorCondition(factor_name="rsi", operator="==", threshold=None),
            ],
            logic=logic,
            ma_periods=[5, 10, 20, 60, 120],
        )

    def test_all_no_signal_stock_excluded(self):
        """构造 ma_trend=0.0, macd=False, boll=False, rsi=False,
        breakout=None 的股票数据，验证不纳入选股结果。

        需求: 5.1, 5.2, 5.3, 5.4
        """
        stocks_data = {
            "000001": {
                "ma_trend": 0.0,
                "macd": False,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 15.0,
            },
            "000002": {
                "ma_trend": 0.0,
                "macd": False,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 25.0,
            },
        }

        config = self._make_strategy_config(logic="AND")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        assert len(result.items) == 0, (
            f"Expected 0 items for all-no-signal stocks, got {len(result.items)}"
        )

    def test_all_no_signal_stock_excluded_or_logic(self):
        """OR 逻辑下，ma_trend=0.0, macd=False, boll=False, rsi=False 也应不通过。

        需求: 5.1, 5.2, 5.3, 5.4
        """
        stocks_data = {
            "000001": {
                "ma_trend": 0.0,
                "macd": False,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 15.0,
            },
        }

        config = self._make_strategy_config(logic="OR")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        assert len(result.items) == 0, (
            f"Expected 0 items for all-no-signal stocks with OR logic, "
            f"got {len(result.items)}"
        )

    def test_partial_valid_signals_macd_true(self):
        """构造部分指标有效（macd=True）但其他为 False 的股票数据，
        验证仅有效信号被纳入（OR 逻辑下该股票通过）。

        需求: 5.2
        """
        stocks_data = {
            "000001": {
                "ma_trend": 0.0,
                "macd": True,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 15.0,
            },
        }

        # OR logic: at least one factor passes → stock included
        config = self._make_strategy_config(logic="OR")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        assert len(result.items) == 1
        item = result.items[0]
        assert item.symbol == "000001"
        # Check that MACD signal is present
        signal_labels = [s.label for s in item.signals]
        assert "macd" in signal_labels

    def test_partial_valid_signals_and_logic_fails(self):
        """AND 逻辑下，部分指标有效但不是全部 → 不通过。

        需求: 5.1, 5.2
        """
        stocks_data = {
            "000001": {
                "ma_trend": 0.0,
                "macd": True,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 15.0,
            },
        }

        config = self._make_strategy_config(logic="AND")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        # AND logic: ma_trend=0.0 < 50 → fails, so stock excluded
        assert len(result.items) == 0

    def test_screen_engine_no_interpolation(self):
        """验证选股引擎不对缺失数据进行插值。

        构造一只股票有 ma_trend=0.0 (数据不足)，另一只有 ma_trend=85.0 (正常)，
        验证 0.0 的那只不被插值为其他值。

        需求: 5.5
        """
        stocks_data = {
            "GOOD01": {
                "ma_trend": 85.0,
                "macd": True,
                "boll": True,
                "rsi": True,
                "breakout": None,
                "close": 30.0,
            },
            "BAD001": {
                "ma_trend": 0.0,
                "macd": False,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 10.0,
            },
        }

        config = self._make_strategy_config(logic="AND")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        # Only GOOD01 should pass, BAD001 should be excluded without interpolation
        symbols = [item.symbol for item in result.items]
        assert "GOOD01" in symbols
        assert "BAD001" not in symbols

    def test_breakout_none_not_included(self):
        """breakout=None 的股票不产生突破信号。

        需求: 5.3
        """
        stocks_data = {
            "000001": {
                "ma_trend": 0.0,
                "macd": False,
                "boll": False,
                "rsi": False,
                "breakout": None,
                "close": 15.0,
            },
        }

        # Use OR logic; even with OR, all signals are False/0.0/None → no pass
        config = self._make_strategy_config(logic="OR")
        executor = ScreenExecutor(strategy_config=config)
        result = executor.run_eod_screen(stocks_data)

        assert len(result.items) == 0


# ---------------------------------------------------------------------------
# 平仓条件预计算缺失数据验证 — 单元测试
# ---------------------------------------------------------------------------

from app.services.backtest_engine import _precompute_exit_indicators


class TestPrecomputeExitIndicatorsDailyReuse:
    """日频条件：复用 existing_cache 的 closes 序列，验证指标值与直接调用计算函数一致。

    需求: 6.1
    """

    def test_daily_reuses_existing_cache_closes(self):
        """日频平仓指标应复用 existing_cache 中的 closes 来计算，
        结果应与直接调用 calculate_rsi/calculate_ma 一致。"""
        # Build a close sequence that's long enough for RSI(14) to produce valid values
        closes = [10.0 + i * 0.2 + (i % 3) * 0.5 for i in range(50)]

        symbol = "REUSE01"
        ic = IndicatorCache(
            closes=closes,
            highs=[c * 1.02 for c in closes],
            lows=[c * 0.98 for c in closes],
            volumes=[100000] * len(closes),
            amounts=[D("1000000")] * len(closes),
            turnovers=[D("1.5")] * len(closes),
            opens=closes[:],
        )

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
                ExitCondition(
                    freq="daily",
                    indicator="ma",
                    operator=">",
                    threshold=10.0,
                    params={"period": 10},
                ),
            ],
            logic="AND",
        )

        existing_cache = {symbol: ic}
        kline_data: dict = {"daily": {}}  # daily kline_data not needed; uses existing_cache

        result_cache, _ = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        assert symbol in result_cache
        assert "daily" in result_cache[symbol]
        freq_cache = result_cache[symbol]["daily"]

        # Verify RSI values match direct calculation
        rsi_result = calculate_rsi(closes, 14)
        cached_rsi = freq_cache.get("rsi_14") or freq_cache.get("rsi")
        assert cached_rsi is not None, "RSI cache should exist"
        assert len(cached_rsi) == len(rsi_result.values)
        for i in range(len(closes)):
            if math.isnan(rsi_result.values[i]):
                assert math.isnan(cached_rsi[i]), (
                    f"RSI at index {i}: expected NaN, got {cached_rsi[i]}"
                )
            else:
                assert cached_rsi[i] == pytest.approx(rsi_result.values[i]), (
                    f"RSI at index {i}: expected {rsi_result.values[i]}, "
                    f"got {cached_rsi[i]}"
                )

        # Verify MA values match direct calculation
        ma_result = calculate_ma(closes, 10)
        cached_ma = freq_cache.get("ma_10")
        assert cached_ma is not None, "MA_10 cache should exist"
        assert len(cached_ma) == len(ma_result)
        for i in range(len(closes)):
            if math.isnan(ma_result[i]):
                assert math.isnan(cached_ma[i]), (
                    f"MA at index {i}: expected NaN, got {cached_ma[i]}"
                )
            else:
                assert cached_ma[i] == pytest.approx(ma_result[i]), (
                    f"MA at index {i}: expected {ma_result[i]}, got {cached_ma[i]}"
                )


class TestPrecomputeExitIndicatorsMinuteNoData:
    """分钟频条件：某只股票无分钟K线数据时，该股票在该频率下无缓存条目。

    需求: 6.3
    """

    def test_minute_no_kline_data_no_cache_entry(self):
        """股票在分钟频率下无K线数据时，exit_indicator_cache 中
        该股票在该频率下无缓存条目。"""
        symbol = "MIN_EMPTY"

        # Create existing_cache with daily data
        closes = [10.0 + i * 0.1 for i in range(30)]
        ic = IndicatorCache(
            closes=closes,
            highs=[c * 1.02 for c in closes],
            lows=[c * 0.98 for c in closes],
            volumes=[100000] * len(closes),
            amounts=[D("1000000")] * len(closes),
            turnovers=[D("1.5")] * len(closes),
            opens=closes[:],
        )
        existing_cache = {symbol: ic}

        # Configure a 5min exit condition
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        # kline_data has daily bars for the symbol but no 5min bars
        daily_bars = _make_bars(30, symbol=symbol)
        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {},  # empty → no minute data for this symbol
        }

        result_cache, minute_ranges = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        # The symbol should NOT have a "5min" cache entry
        if symbol in result_cache:
            assert "5min" not in result_cache[symbol], (
                f"Symbol {symbol} should not have 5min cache when no minute data exists"
            )

    def test_minute_symbol_not_in_freq_klines(self):
        """分钟频率K线字典中完全没有该股票时，无缓存条目。"""
        symbol = "MIN_MISS"

        closes = [10.0 + i * 0.1 for i in range(20)]
        ic = IndicatorCache(
            closes=closes,
            highs=[c * 1.02 for c in closes],
            lows=[c * 0.98 for c in closes],
            volumes=[100000] * len(closes),
            amounts=[D("1000000")] * len(closes),
            turnovers=[D("1.5")] * len(closes),
            opens=closes[:],
        )
        existing_cache = {symbol: ic}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="ma",
                    operator=">",
                    threshold=10.0,
                    params={"period": 5},
                ),
            ],
            logic="AND",
        )

        # 5min key exists but does not include this symbol
        kline_data = {
            "daily": {symbol: _make_bars(20, symbol=symbol)},
            "5min": {"OTHER_SYM": _make_bars(10, symbol="OTHER_SYM")},
        }

        result_cache, _ = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        # The target symbol should not have 5min cache
        if symbol in result_cache:
            assert "5min" not in result_cache[symbol], (
                f"Symbol {symbol} should not have 5min cache entry"
            )


class TestPrecomputeExitIndicatorsMinuteInsufficientData:
    """分钟频条件：K线数据不足时，缓存中保留 NaN 值。

    需求: 6.4
    """

    def test_minute_insufficient_data_preserves_nan(self):
        """分钟K线数据不足以计算指标时，缓存中保留 NaN 值。"""
        symbol = "MIN_SHORT"

        # Daily cache (not relevant for minute but required)
        daily_closes = [10.0 + i * 0.1 for i in range(30)]
        ic = IndicatorCache(
            closes=daily_closes,
            highs=[c * 1.02 for c in daily_closes],
            lows=[c * 0.98 for c in daily_closes],
            volumes=[100000] * len(daily_closes),
            amounts=[D("1000000")] * len(daily_closes),
            turnovers=[D("1.5")] * len(daily_closes),
            opens=daily_closes[:],
        )
        existing_cache = {symbol: ic}

        # Only 5 minute bars — insufficient for RSI(14) which needs 15
        minute_bars = []
        base_dt = datetime(2024, 6, 3, 9, 30, 0)
        for i in range(5):
            close = 10.0 + i * 0.01
            minute_bars.append(KlineBar(
                time=base_dt + timedelta(minutes=i * 5),
                symbol=symbol,
                freq="5min",
                open=D(str(round(close * 0.99, 2))),
                high=D(str(round(close * 1.02, 2))),
                low=D(str(round(close * 0.98, 2))),
                close=D(str(round(close, 2))),
                volume=10000,
                amount=D("100000"),
                turnover=D("0.5"),
                vol_ratio=D("1.0"),
            ))

        daily_bars = _make_bars(30, symbol=symbol)
        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="rsi",
                    operator=">",
                    threshold=80.0,
                    params={"rsi_period": 14},
                ),
            ],
            logic="AND",
        )

        result_cache, _ = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        assert symbol in result_cache
        assert "5min" in result_cache[symbol]
        freq_cache = result_cache[symbol]["5min"]

        # RSI with only 5 data points and period=14: all values should be NaN
        rsi_key = "rsi_14"
        assert rsi_key in freq_cache, f"rsi_14 should be in 5min cache"
        rsi_values = freq_cache[rsi_key]
        assert len(rsi_values) == 5

        # All 5 values should be NaN since 5 < 14 + 1 = 15
        for i, v in enumerate(rsi_values):
            assert math.isnan(v), (
                f"rsi_values[{i}] should be NaN for insufficient data "
                f"(5 bars, period=14), got {v}"
            )

    def test_minute_partial_nan_with_sufficient_data(self):
        """分钟K线数据部分足以计算指标时，前缀为 NaN，后续为有效值。"""
        symbol = "MIN_PARTIAL"

        daily_closes = [10.0 + i * 0.1 for i in range(30)]
        ic = IndicatorCache(
            closes=daily_closes,
            highs=[c * 1.02 for c in daily_closes],
            lows=[c * 0.98 for c in daily_closes],
            volumes=[100000] * len(daily_closes),
            amounts=[D("1000000")] * len(daily_closes),
            turnovers=[D("1.5")] * len(daily_closes),
            opens=daily_closes[:],
        )
        existing_cache = {symbol: ic}

        # 20 minute bars — enough for MA(5) but partial NaN prefix
        minute_bars = []
        base_dt = datetime(2024, 6, 3, 9, 30, 0)
        for i in range(20):
            close = 10.0 + i * 0.05
            minute_bars.append(KlineBar(
                time=base_dt + timedelta(minutes=i * 5),
                symbol=symbol,
                freq="5min",
                open=D(str(round(close * 0.99, 2))),
                high=D(str(round(close * 1.02, 2))),
                low=D(str(round(close * 0.98, 2))),
                close=D(str(round(close, 2))),
                volume=10000,
                amount=D("100000"),
                turnover=D("0.5"),
                vol_ratio=D("1.0"),
            ))

        daily_bars = _make_bars(30, symbol=symbol)
        kline_data = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min",
                    indicator="ma",
                    operator=">",
                    threshold=10.0,
                    params={"period": 5},
                ),
            ],
            logic="AND",
        )

        result_cache, _ = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        assert symbol in result_cache
        assert "5min" in result_cache[symbol]
        freq_cache = result_cache[symbol]["5min"]

        ma_key = "ma_5"
        assert ma_key in freq_cache
        ma_values = freq_cache[ma_key]
        assert len(ma_values) == 20

        # First 4 values (period-1 = 4) should be NaN
        for i in range(4):
            assert math.isnan(ma_values[i]), (
                f"ma_values[{i}] should be NaN (NaN prefix), got {ma_values[i]}"
            )

        # From index 4 onward, values should be valid
        for i in range(4, 20):
            assert not math.isnan(ma_values[i]), (
                f"ma_values[{i}] should be valid float, got NaN"
            )
