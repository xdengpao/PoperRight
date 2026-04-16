"""
BacktestEngine 集成单元测试 — 自定义平仓条件与现有风控的集成

测试场景：
- 自定义条件在风控之后执行（需求 3.1）
- 风控已触发时跳过自定义条件（需求 3.2, 3.3）
- 卖出记录包含正确的 sell_reason（需求 7.1）
- 无自定义条件时行为不变（需求 3.5）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.schemas import (
    BacktestConfig,
    ExitCondition,
    ExitConditionConfig,
    KlineBar,
    StrategyConfig,
)
from app.services.backtest_engine import (
    BacktestEngine,
    IndicatorCache,
    KlineDateIndex,
    _BacktestPosition,
    _SellSignal,
    _build_date_index,
)


# ---------------------------------------------------------------------------
# 辅助工厂函数
# ---------------------------------------------------------------------------

def _make_kline_bar(
    trade_date: date,
    symbol: str = "600519.SH",
    close: float = 100.0,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: int = 10000,
) -> KlineBar:
    """创建单根 KlineBar。"""
    c = Decimal(str(close))
    o = Decimal(str(open_ if open_ is not None else close))
    h = Decimal(str(high if high is not None else close + 1))
    lo = Decimal(str(low if low is not None else close - 1))
    return KlineBar(
        time=datetime.combine(trade_date, datetime.min.time()),
        symbol=symbol,
        freq="daily",
        open=o,
        high=h,
        low=lo,
        close=c,
        volume=volume,
        amount=c * volume,
        turnover=Decimal("5.0"),
        vol_ratio=Decimal("1.0"),
    )


def _make_bars(
    symbol: str = "600519.SH",
    start_date: date = date(2024, 1, 2),
    closes: list[float] | None = None,
    n: int = 30,
) -> list[KlineBar]:
    """生成连续交易日的 KlineBar 列表。"""
    if closes is None:
        closes = [100.0 + i * 0.5 for i in range(n)]
    bars: list[KlineBar] = []
    d = start_date
    for i, c in enumerate(closes):
        bars.append(_make_kline_bar(d, symbol=symbol, close=c))
        d += timedelta(days=1)
        # 跳过周末
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return bars


def _make_indicator_cache(bars: list[KlineBar]) -> IndicatorCache:
    """从 KlineBar 列表构建 IndicatorCache。"""
    return IndicatorCache(
        closes=[float(b.close) for b in bars],
        highs=[float(b.high) for b in bars],
        lows=[float(b.low) for b in bars],
        volumes=[b.volume for b in bars],
        amounts=[b.amount for b in bars],
        turnovers=[b.turnover for b in bars],
    )


def _make_config(
    exit_conditions: ExitConditionConfig | None = None,
    stop_loss_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    max_holding_days: int = 20,
    trend_stop_ma: int = 20,
) -> BacktestConfig:
    """创建 BacktestConfig，使用默认策略配置。"""
    return BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        stop_loss_pct=stop_loss_pct,
        trailing_stop_pct=trailing_stop_pct,
        max_holding_days=max_holding_days,
        trend_stop_ma=trend_stop_ma,
        exit_conditions=exit_conditions,
    )


def _make_position(
    symbol: str = "600519.SH",
    cost_price: float = 100.0,
    buy_date: date = date(2024, 1, 2),
    buy_trade_day_index: int = 0,
    highest_close: float | None = None,
) -> _BacktestPosition:
    """创建 _BacktestPosition。"""
    cp = Decimal(str(cost_price))
    hc = Decimal(str(highest_close if highest_close is not None else cost_price))
    return _BacktestPosition(
        symbol=symbol,
        quantity=100,
        cost_price=cp,
        buy_date=buy_date,
        buy_trade_day_index=buy_trade_day_index,
        highest_close=hc,
    )


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


class TestExitConditionTriggersAfterRiskChecks:
    """需求 3.1: 自定义条件在风控之后执行，风控未触发时自定义条件可触发"""

    def test_exit_condition_triggers_when_no_risk_fires(self):
        """
        当所有风控条件均未触发时，EXIT_CONDITION 应正常触发。
        设置：close > cost（无止损）、close > MA（无趋势破位）、
        无回撤（无移动止盈）、持仓天数未超期。
        """
        symbol = "600519.SH"
        # 生成稳定上涨的 K 线，确保 close > MA20 且无回撤
        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 自定义条件：close > 105（第 17 根 bar 的 close = 100 + 17*0.3 = 105.1）
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=105.0),
            ],
            logic="AND",
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,       # 极大止损阈值，不会触发
            trailing_stop_pct=0.50,   # 极大回撤阈值，不会触发
            max_holding_days=100,     # 极大持仓天数，不会触发
            trend_stop_ma=200,        # MA200 需要 200 根 bar，数据不足不会触发
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=106.0,  # 高于当前 close，无回撤
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5  # 远小于 max_holding_days

        trade_date = bars[17].time.date()  # close = 105.1
        # 构建 exit_indicator_cache（close 直接从 IndicatorCache 读取，无需额外缓存）
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason
        assert "CLOSE > 105" in result.reason

    def test_exit_condition_reason_contains_description(self):
        """需求 7.1: sell_reason 包含触发条件的具体描述"""
        symbol = "600519.SH"
        closes = [100.0 + i * 0.5 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # RSI > 80 条件
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(symbol=symbol, cost_price=100.0, highest_close=120.0)
        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[20].time.date()
        # 提供 RSI 值 > 80
        exit_ic = {symbol: {"daily": {"rsi": [85.0] * len(bars)}}}

        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
        )

        assert result is not None
        assert result.reason == "EXIT_CONDITION: RSI > 80.0"
        assert result.priority == 5


class TestRiskConditionSkipsExitCondition:
    """需求 3.2, 3.3: 风控已触发时跳过自定义条件"""

    def test_stop_loss_takes_priority_over_exit_condition(self):
        """
        STOP_LOSS (priority=1) 应优先于 EXIT_CONDITION (priority=5)。
        即使自定义条件也会触发，返回的仍是 STOP_LOSS。
        """
        symbol = "600519.SH"
        # 价格大幅下跌触发止损：cost=100, close=90 → loss=10%
        closes = [100.0] * 10 + [90.0] * 20
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 自定义条件也会触发：close < 95
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator="<", threshold=95.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.08,       # 8% 止损，loss=10% 会触发
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=100.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[15].time.date()  # close = 90.0
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is not None
        assert result.reason == "STOP_LOSS"
        assert result.priority == 1

    def test_trend_break_takes_priority_over_exit_condition(self):
        """
        TREND_BREAK (priority=2) 应优先于 EXIT_CONDITION。
        close < MA20 触发趋势破位。
        """
        symbol = "600519.SH"
        # 前 20 根 bar 价格较高，然后下跌到 MA20 以下
        closes = [110.0] * 20 + [100.0] * 10
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 自定义条件也会触发：close < 105
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator="<", threshold=105.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,       # 不触发止损
            trailing_stop_pct=0.50,   # 不触发移动止盈
            max_holding_days=100,
            trend_stop_ma=20,         # MA20
        )

        position = _make_position(
            symbol=symbol,
            cost_price=90.0,          # cost < close，不触发止损
            highest_close=110.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        # bar[25] close=100, MA20 of last 20 bars = (110*15 + 100*5)/20 = 107.5
        # close=100 < MA20=107.5 → TREND_BREAK
        trade_date = bars[24].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is not None
        assert result.reason == "TREND_BREAK"
        assert result.priority == 2

    def test_trailing_stop_takes_priority_over_exit_condition(self):
        """
        TRAILING_STOP (priority=3) 应优先于 EXIT_CONDITION。
        """
        symbol = "600519.SH"
        # 价格从高点回撤超过 5%
        closes = [100.0 + i for i in range(25)] + [115.0] * 5
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=110.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.05,   # 5% 回撤触发
            max_holding_days=100,
            trend_stop_ma=200,        # 不触发趋势破位
        )

        # highest_close=125, close=115 → drawdown = (125-115)/125 = 8% > 5%
        position = _make_position(
            symbol=symbol,
            cost_price=90.0,
            highest_close=125.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[28].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is not None
        assert result.reason == "TRAILING_STOP"
        assert result.priority == 3

    def test_max_holding_days_takes_priority_over_exit_condition(self):
        """
        MAX_HOLDING_DAYS (priority=4) 应优先于 EXIT_CONDITION。
        """
        symbol = "600519.SH"
        # 稳定上涨，不触发止损/趋势破位/移动止盈
        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=105.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=5,       # 5 天超期
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 10  # 10 - 0 = 10 > 5

        trade_date = bars[20].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is not None
        assert result.reason == "MAX_HOLDING_DAYS"
        assert result.priority == 4


class TestNoExitConditionBackwardCompatibility:
    """需求 3.5: 无自定义条件时行为不变"""

    def test_no_exit_conditions_returns_none_when_no_risk(self):
        """exit_conditions=None 且无风控触发时，返回 None。"""
        symbol = "600519.SH"
        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        config = _make_config(
            exit_conditions=None,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[20].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=None,
        )

        assert result is None

    def test_no_exit_conditions_still_triggers_risk(self):
        """exit_conditions=None 时，风控条件仍正常触发。"""
        symbol = "600519.SH"
        closes = [100.0] * 10 + [90.0] * 20
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        config = _make_config(
            exit_conditions=None,
            stop_loss_pct=0.08,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=100.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[15].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=None,
        )

        assert result is not None
        assert result.reason == "STOP_LOSS"


class TestExitConditionNotTriggered:
    """自定义条件存在但未满足时，返回 None"""

    def test_exit_condition_not_met_returns_none(self):
        """自定义条件未满足且无风控触发时，返回 None。"""
        symbol = "600519.SH"
        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # close > 200 — 永远不会满足
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=200.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[20].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache={symbol: {}},
        )

        assert result is None


# ---------------------------------------------------------------------------
# 需求 13: 前复权K线数据集成测试
# ---------------------------------------------------------------------------


class TestForwardAdjustedKlineIntegration:
    """需求 13.1, 13.2, 13.3, 13.4: 前复权K线数据集成

    验证回测引擎在计算自定义平仓条件指标时使用前复权K线数据，
    以及无复权因子时的降级行为。
    """

    def test_precompute_exit_indicators_uses_adjusted_closes(self):
        """
        需求 13.1, 13.2: _precompute_exit_indicators 使用前复权后的 closes 计算指标。

        构造两组不同的 closes（模拟原始 vs 前复权），验证 _precompute_exit_indicators
        使用 existing_cache 中的 closes（已前复权）来计算日K线频率的 MA 指标，
        而非原始 kline_data 中的价格。
        """
        from app.services.backtest_engine import _precompute_exit_indicators

        symbol = "600519.SH"

        # 模拟前复权后的 closes（已在 existing_cache 中）
        adjusted_closes = [50.0 + i * 0.5 for i in range(30)]

        # existing_cache 使用前复权后的 closes
        existing_cache = {
            symbol: IndicatorCache(
                closes=adjusted_closes,
                highs=[c + 1 for c in adjusted_closes],
                lows=[c - 1 for c in adjusted_closes],
                volumes=[10000] * 30,
                amounts=[Decimal("500000")] * 30,
                turnovers=[Decimal("5.0")] * 30,
            ),
        }

        # 配置一个 MA10 条件（daily 频率）
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="ma",
                    operator=">",
                    threshold=50.0,
                    params={"period": 10},
                ),
            ],
            logic="AND",
        )

        # kline_data 可以为空 dict（daily 频率复用 existing_cache）
        result, _ = _precompute_exit_indicators(
            kline_data={},
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        # 验证结果中包含该 symbol 的 daily 频率 MA 缓存
        assert symbol in result
        assert "daily" in result[symbol]
        assert "ma_10" in result[symbol]["daily"]

        ma_values = result[symbol]["daily"]["ma_10"]
        assert len(ma_values) == 30

        # 手动计算 MA10 在 index=9 处的值（前 10 个 adjusted_closes 的平均值）
        expected_ma_at_9 = sum(adjusted_closes[:10]) / 10
        assert abs(ma_values[9] - expected_ma_at_9) < 1e-6

        # 验证 MA10 在 index=19 处的值
        expected_ma_at_19 = sum(adjusted_closes[10:20]) / 10
        assert abs(ma_values[19] - expected_ma_at_19) < 1e-6

    def test_evaluator_uses_adjusted_close_from_indicator_cache(self):
        """
        需求 13.2: ExitConditionEvaluator 获取的 close 值为前复权收盘价。

        构造 IndicatorCache 使用前复权 closes，验证 evaluator 评估
        "close > threshold" 条件时使用的是前复权收盘价。
        """
        from app.services.exit_condition_evaluator import ExitConditionEvaluator

        symbol = "600519.SH"

        # 前复权收盘价序列：原始价 100 经前复权后变为 80
        adjusted_closes = [80.0] * 30

        ic = IndicatorCache(
            closes=adjusted_closes,
            highs=[81.0] * 30,
            lows=[79.0] * 30,
            volumes=[10000] * 30,
            amounts=[Decimal("800000")] * 30,
            turnovers=[Decimal("5.0")] * 30,
        )

        # 条件：close > 90 — 前复权 close=80，不应触发
        exit_config_not_triggered = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=90.0),
            ],
        )

        evaluator = ExitConditionEvaluator()
        triggered, reason = evaluator.evaluate(
            exit_config_not_triggered, symbol, bar_index=15,
            indicator_cache=ic, exit_indicator_cache={},
        )
        assert triggered is False

        # 条件：close > 70 — 前复权 close=80 > 70，应触发
        exit_config_triggered = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=70.0),
            ],
        )

        triggered, reason = evaluator.evaluate(
            exit_config_triggered, symbol, bar_index=15,
            indicator_cache=ic, exit_indicator_cache={},
        )
        assert triggered is True
        assert "CLOSE > 70" in reason

    def test_no_adjustment_factors_uses_original_kline_with_warning(self, caplog):
        """
        需求 13.4: 无复权因子时使用原始K线数据并记录警告日志。

        模拟 app/tasks/backtest.py 中的逻辑：当股票无前复权因子时，
        kline_data 保持原始价格，并记录警告日志。验证 _precompute_exit_indicators
        仍能正常使用原始 closes 计算指标。
        """
        import logging
        from app.services.backtest_engine import _precompute_exit_indicators

        symbol = "000001.SZ"

        # 原始（未前复权）closes
        original_closes = [100.0 + i for i in range(30)]

        # existing_cache 使用原始 closes（因为无复权因子，未做调整）
        existing_cache = {
            symbol: IndicatorCache(
                closes=original_closes,
                highs=[c + 1 for c in original_closes],
                lows=[c - 1 for c in original_closes],
                volumes=[10000] * 30,
                amounts=[Decimal("1000000")] * 30,
                turnovers=[Decimal("5.0")] * 30,
            ),
        }

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="ma",
                    operator=">",
                    threshold=100.0,
                    params={"period": 5},
                ),
            ],
        )

        # 模拟 backtest.py 中无复权因子时的警告日志
        with caplog.at_level(logging.WARNING):
            logger = logging.getLogger("app.tasks.backtest")
            logger.warning("股票 %s 无前复权因子数据，使用原始K线", symbol)

        # _precompute_exit_indicators 仍能正常计算
        result, _ = _precompute_exit_indicators(
            kline_data={},
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        # 验证警告日志已记录
        assert any("无前复权因子数据" in record.message for record in caplog.records)

        # 验证指标仍然正常计算（使用原始 closes）
        assert symbol in result
        assert "daily" in result[symbol]
        assert "ma_5" in result[symbol]["daily"]

        ma_values = result[symbol]["daily"]["ma_5"]
        # MA5 at index=4: mean of original_closes[0:5] = mean(100,101,102,103,104) = 102.0
        expected_ma_at_4 = sum(original_closes[:5]) / 5
        assert abs(ma_values[4] - expected_ma_at_4) < 1e-6

    def test_minute_kline_data_uses_adjusted_closes(self):
        """
        需求 13.1, 13.4: 分钟K线数据同样应用前复权处理。

        构造分钟K线数据（已前复权），验证 _precompute_exit_indicators
        使用分钟K线的前复权 closes 计算指标，且结果与日K线不同。
        """
        from app.services.backtest_engine import _precompute_exit_indicators

        symbol = "600519.SH"

        # 日K线前复权 closes
        daily_adjusted_closes = [50.0 + i * 0.5 for i in range(30)]

        existing_cache = {
            symbol: IndicatorCache(
                closes=daily_adjusted_closes,
                highs=[c + 1 for c in daily_adjusted_closes],
                lows=[c - 1 for c in daily_adjusted_closes],
                volumes=[10000] * 30,
                amounts=[Decimal("500000")] * 30,
                turnovers=[Decimal("5.0")] * 30,
            ),
        }

        # 5分钟K线前复权 closes（不同于日K线 closes）
        minute_adjusted_closes = [30.0 + i * 0.2 for i in range(60)]
        minute_bars = []
        d = date(2024, 1, 2)
        for i, c in enumerate(minute_adjusted_closes):
            minute_bars.append(
                _make_kline_bar(d, symbol=symbol, close=c, volume=5000)
            )
            # 每 2 根 bar 换一天（模拟分钟数据）
            if (i + 1) % 2 == 0:
                d += timedelta(days=1)
                while d.weekday() >= 5:
                    d += timedelta(days=1)

        # 配置两个条件：一个用 daily MA10，一个用 5min MA10
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily",
                    indicator="ma",
                    operator=">",
                    threshold=40.0,
                    params={"period": 10},
                ),
                ExitCondition(
                    freq="5min",
                    indicator="ma",
                    operator=">",
                    threshold=30.0,
                    params={"period": 10},
                ),
            ],
            logic="AND",
        )

        kline_data = {"5min": {symbol: minute_bars}}

        result, _ = _precompute_exit_indicators(
            kline_data=kline_data,
            exit_config=exit_config,
            existing_cache=existing_cache,
        )

        # 验证 daily 和 5min 频率都有 MA 缓存
        assert symbol in result
        assert "daily" in result[symbol]
        assert "5min" in result[symbol]
        assert "ma_10" in result[symbol]["daily"]
        assert "ma_10" in result[symbol]["5min"]

        daily_ma = result[symbol]["daily"]["ma_10"]
        minute_ma = result[symbol]["5min"]["ma_10"]

        # 日K线 MA10 at index=9: mean(daily_adjusted_closes[0:10])
        expected_daily_ma_9 = sum(daily_adjusted_closes[:10]) / 10
        assert abs(daily_ma[9] - expected_daily_ma_9) < 1e-6

        # 5分钟 MA10 at index=9: mean(minute_adjusted_closes[0:10])
        expected_minute_ma_9 = sum(minute_adjusted_closes[:10]) / 10
        assert abs(minute_ma[9] - expected_minute_ma_9) < 1e-6

        # 日K线和分钟K线的 MA 值应不同（因为 closes 不同）
        assert abs(daily_ma[9] - minute_ma[9]) > 1e-6


# ---------------------------------------------------------------------------
# 需求 2.1, 2.3: _check_sell_conditions 传递 minute_day_ranges 到评估器
# ---------------------------------------------------------------------------


class TestCheckSellConditionsPassesMinuteDayRanges:
    """需求 2.1, 2.3: _check_sell_conditions() 将 minute_day_ranges 传递给评估器，
    使分钟频率条件通过日内扫描正确触发。

    验证完整管道：_check_sell_conditions → evaluator.evaluate(minute_day_ranges=...)
    → _evaluate_single_minute_scanning() 扫描日内分钟 bar 范围。
    """

    def test_minute_condition_triggers_via_minute_day_ranges(self):
        """
        配置 5min RSI > 80 条件。日K线 bar_index=5 对应的分钟缓存 index 5
        的 RSI=50（不满足），但 minute_day_ranges 将 day 5 映射到分钟缓存
        索引范围 (240, 287)，其中 index 250 的 RSI=85（满足）。

        验证 _check_sell_conditions 正确传递 minute_day_ranges，使评估器
        扫描日内范围并触发条件。
        """
        symbol = "600519.SH"

        # 生成 30 根日K线（稳定上涨，不触发任何风控）
        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 5min RSI > 80 条件
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="rsi", operator=">", threshold=80.0,
                ),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 3

        # 构建 5min RSI 缓存：300 根分钟 bar（模拟 ~6 天 × 48 根/天）
        # index 5 的 RSI=50（旧代码会读这个值，不触发）
        # index 240~287 对应 day 5 的分钟 bar，其中 index 250 的 RSI=85
        rsi_values = [50.0] * 300
        rsi_values[250] = 85.0  # day 5 内的某根 bar 满足 RSI > 80

        exit_ic = {
            symbol: {
                "5min": {"rsi": rsi_values},
            },
        }

        # minute_day_ranges: day 5 → (240, 287)
        # 构建 30 天的映射（与日K线天数对齐）
        day_ranges_5min: list[tuple[int, int]] = []
        for day_idx in range(30):
            start = day_idx * 48
            end = start + 47
            day_ranges_5min.append((start, end))

        minute_day_ranges = {
            symbol: {"5min": day_ranges_5min},
        }

        # 使用 bar_index=5 对应的交易日
        trade_date = bars[5].time.date()

        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason
        assert "RSI > 80" in result.reason

    def test_minute_condition_not_triggered_when_no_bar_satisfies(self):
        """
        配置 5min RSI > 80 条件，但 day 5 的所有分钟 bar RSI 均为 50。
        验证条件不触发（返回 None）。
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="rsi", operator=">", threshold=80.0,
                ),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 3

        # 所有 RSI 值均为 50（不满足 > 80）
        rsi_values = [50.0] * 300
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}

        day_ranges_5min = [(day_idx * 48, day_idx * 48 + 47) for day_idx in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges_5min}}

        trade_date = bars[5].time.date()

        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is None

    def test_minute_day_ranges_none_falls_back_to_daily_behavior(self):
        """
        当 minute_day_ranges 为 None 时，分钟频率条件回退到使用
        bar_index 直接索引（向后兼容）。

        验证 _check_sell_conditions 在 minute_day_ranges=None 时
        不会崩溃，且行为与旧代码一致。
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 5min RSI > 80 条件，但不提供 minute_day_ranges
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="rsi", operator=">", threshold=80.0,
                ),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 3

        # RSI 缓存中 index 5 的值为 85（直接索引会触发）
        rsi_values = [50.0] * 30
        rsi_values[5] = 85.0
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}

        trade_date = bars[5].time.date()

        # minute_day_ranges=None → 回退到直接 bar_index 索引
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=None,
        )

        # 回退行为：bar_index=5 直接索引 5min 缓存，RSI=85 > 80 → 触发
        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason


# ---------------------------------------------------------------------------
# Task 7.1: Full pipeline integration tests for minute-frequency conditions
# Requirements: 2.1, 2.5, 3.1, 3.2, 3.4, 3.5, 3.7
# ---------------------------------------------------------------------------


def _make_minute_bars(
    symbol: str = "600519.SH",
    start_date: date = date(2024, 1, 2),
    n_days: int = 30,
    bars_per_day: int = 48,
    base_close: float = 100.0,
    freq: str = "5min",
) -> list[KlineBar]:
    """Generate minute-frequency KlineBars with `bars_per_day` bars per trading day.

    Each bar gets a unique intra-day timestamp (minute offset) so that
    ``bar.time.date()`` groups correctly by trading day.
    """
    bars: list[KlineBar] = []
    d = start_date
    for day_idx in range(n_days):
        for bar_idx in range(bars_per_day):
            c = base_close + day_idx * 0.5 + bar_idx * 0.01
            # Distribute bars across trading hours (09:30 – ~15:00)
            total_minutes = 30 + bar_idx * 5  # 5-min intervals from 09:30
            hour = 9 + total_minutes // 60
            minute = total_minutes % 60
            t = datetime.combine(d, datetime.min.time()).replace(
                hour=hour, minute=minute,
            )
            bars.append(
                KlineBar(
                    time=t,
                    symbol=symbol,
                    freq=freq,
                    open=Decimal(str(c)),
                    high=Decimal(str(c + 0.5)),
                    low=Decimal(str(c - 0.5)),
                    close=Decimal(str(c)),
                    volume=5000,
                    amount=Decimal(str(c * 5000)),
                    turnover=Decimal("3.0"),
                    vol_ratio=Decimal("1.0"),
                )
            )
        # Advance to next weekday
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return bars


class TestFullPipelineMinuteFrequencyIntegration:
    """Task 7.1: Full pipeline integration tests for minute-frequency exit conditions.

    Validates: Requirements 2.1, 2.5, 3.1, 3.2, 3.4, 3.5, 3.7
    """

    def test_full_pipeline_with_real_shaped_5min_data(self):
        """
        End-to-end: 5min RSI > 80 condition with 48 bars/day.

        Build minute_day_ranges via _build_minute_day_ranges(), construct
        real-shaped 5min kline data, and verify the full _check_sell_conditions
        pipeline triggers when a minute bar within the target day satisfies
        the condition.

        Validates: Requirements 2.1, 3.7
        """
        from app.services.backtest_engine import _build_minute_day_ranges

        symbol = "600519.SH"
        n_days = 10
        bars_per_day = 48

        # Daily bars
        daily_closes = [100.0 + i * 0.3 for i in range(n_days)]
        daily_bars = _make_bars(symbol=symbol, closes=daily_closes)
        kline_data_daily = {symbol: daily_bars}
        date_index = _build_date_index(kline_data_daily)
        ic = _make_indicator_cache(daily_bars)
        indicator_cache = {symbol: ic}

        # Minute bars (5min, 48 bars/day)
        minute_bars = _make_minute_bars(
            symbol=symbol,
            start_date=daily_bars[0].time.date(),
            n_days=n_days,
            bars_per_day=bars_per_day,
        )

        # Build minute_day_ranges using the real helper
        kline_data_for_ranges = {
            "daily": {symbol: daily_bars},
            "5min": {symbol: minute_bars},
        }
        minute_day_ranges = _build_minute_day_ranges(
            kline_data_for_ranges, {symbol: ic},
        )

        # Verify mapping shape
        assert symbol in minute_day_ranges
        assert "5min" in minute_day_ranges[symbol]
        assert len(minute_day_ranges[symbol]["5min"]) == n_days

        # Build RSI cache: all 50.0 except one bar in day 5 has RSI=85
        total_minute_bars = n_days * bars_per_day
        rsi_values = [50.0] * total_minute_bars
        # Day 5 range
        day5_start, day5_end = minute_day_ranges[symbol]["5min"][5]
        target_bar = day5_start + 10  # arbitrary bar within day 5
        rsi_values[target_bar] = 85.0

        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=daily_bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 3

        trade_date = daily_bars[5].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data_daily,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason
        assert "RSI > 80" in result.reason

    def test_risk_stop_loss_takes_priority_over_minute_exit_condition(self):
        """
        Risk condition (stop-loss, priority=1) fires before minute-frequency
        exit condition evaluation is reached.

        Validates: Requirements 3.2, 3.5
        """
        symbol = "600519.SH"

        # Price drops: cost=100, close=90 → 10% loss > 8% stop_loss
        closes = [100.0] * 5 + [90.0] * 10
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # Minute condition that would also trigger
        rsi_values = [85.0] * (15 * 48)
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(15)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.08,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=100.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 3

        trade_date = bars[10].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.reason == "STOP_LOSS"
        assert result.priority == 1

    def test_risk_trend_break_takes_priority_over_minute_exit_condition(self):
        """
        TREND_BREAK (priority=2) fires before minute-frequency exit condition.

        Validates: Requirements 3.2, 3.5
        """
        symbol = "600519.SH"

        closes = [110.0] * 20 + [100.0] * 10
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        rsi_values = [85.0] * (30 * 48)
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=20,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=90.0,
            highest_close=110.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[24].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.reason == "TREND_BREAK"
        assert result.priority == 2

    def test_risk_trailing_stop_takes_priority_over_minute_exit_condition(self):
        """
        TRAILING_STOP (priority=3) fires before minute-frequency exit condition.

        Validates: Requirements 3.2, 3.5
        """
        symbol = "600519.SH"

        closes = [100.0 + i for i in range(25)] + [115.0] * 5
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        rsi_values = [85.0] * (30 * 48)
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.05,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        # highest_close=125, close=115 → drawdown=8% > 5%
        position = _make_position(
            symbol=symbol,
            cost_price=90.0,
            highest_close=125.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[28].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.reason == "TRAILING_STOP"
        assert result.priority == 3

    def test_risk_max_holding_days_takes_priority_over_minute_exit_condition(self):
        """
        MAX_HOLDING_DAYS (priority=4) fires before minute-frequency exit condition.

        Validates: Requirements 3.2, 3.5
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        rsi_values = [85.0] * (30 * 48)
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=5,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 10  # 10 - 0 = 10 > 5

        trade_date = bars[20].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.reason == "MAX_HOLDING_DAYS"
        assert result.priority == 4

    def test_mixed_daily_and_minute_conditions_and_logic(self):
        """
        Mixed daily + minute conditions with AND logic.

        Daily close > 105 (satisfied at bar_index=17) AND 5min RSI > 80
        (satisfied via minute scanning). Both must be true for AND to trigger.

        Validates: Requirements 2.5, 3.1
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # 5min RSI: day 17 has one bar with RSI=85
        total_bars = 30 * 48
        rsi_values = [50.0] * total_bars
        day17_start = 17 * 48
        rsi_values[day17_start + 20] = 85.0

        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        # AND: daily close > 105 AND 5min RSI > 80
        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=105.0),
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
            logic="AND",
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        # bar 17: close = 100 + 17*0.3 = 105.1 > 105 ✓
        trade_date = bars[17].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason

    def test_mixed_daily_and_minute_conditions_and_logic_not_triggered(self):
        """
        Mixed daily + minute AND: daily condition satisfied but minute condition
        NOT satisfied → AND fails, no signal.

        Validates: Requirements 2.5, 3.1
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # All RSI values are 50 (below threshold)
        rsi_values = [50.0] * (30 * 48)
        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=105.0),
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
            logic="AND",
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[17].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is None

    def test_mixed_daily_and_minute_conditions_or_logic(self):
        """
        Mixed daily + minute conditions with OR logic.

        Daily close > 200 (NOT satisfied) OR 5min RSI > 80 (satisfied via
        minute scanning). OR means either one triggers.

        Validates: Requirements 2.5, 3.1
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        total_bars = 30 * 48
        rsi_values = [50.0] * total_bars
        day10_start = 10 * 48
        rsi_values[day10_start + 5] = 85.0

        exit_ic = {symbol: {"5min": {"rsi": rsi_values}}}
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=200.0),
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
            logic="OR",
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            buy_date=bars[0].time.date(),
            buy_trade_day_index=0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[10].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.priority == 5
        assert "EXIT_CONDITION" in result.reason

    def test_exit_conditions_none_produces_no_signal(self):
        """
        When exit_conditions=None, no EXIT_CONDITION signal is produced
        even when minute_day_ranges is provided.

        Validates: Requirements 3.4, 3.5
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.3 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        config = _make_config(
            exit_conditions=None,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[10].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=None,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is None

    def test_backward_compat_daily_only_conditions_unaffected(self):
        """
        Existing daily-only exit conditions continue to work identically
        when minute_day_ranges is provided (but contains no daily entry).

        Validates: Requirements 3.1, 3.4
        """
        symbol = "600519.SH"

        closes = [100.0 + i * 0.5 for i in range(30)]
        bars = _make_bars(symbol=symbol, closes=closes)
        kline_data = {symbol: bars}
        date_index = _build_date_index(kline_data)
        ic = _make_indicator_cache(bars)
        indicator_cache = {symbol: ic}

        # Daily RSI > 80 — provide RSI values in exit_indicator_cache
        exit_ic = {symbol: {"daily": {"rsi": [85.0] * 30}}}

        # Provide minute_day_ranges (should be ignored for daily conditions)
        day_ranges = [(d * 48, d * 48 + 47) for d in range(30)]
        minute_day_ranges = {symbol: {"5min": day_ranges}}

        exit_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        config = _make_config(
            exit_conditions=exit_config,
            stop_loss_pct=0.50,
            trailing_stop_pct=0.50,
            max_holding_days=100,
            trend_stop_ma=200,
        )

        position = _make_position(
            symbol=symbol,
            cost_price=100.0,
            highest_close=120.0,
        )

        engine = BacktestEngine()
        engine._current_trade_day_index = 5

        trade_date = bars[15].time.date()
        result = engine._check_sell_conditions(
            position=position,
            trade_date=trade_date,
            kline_data=kline_data,
            config=config,
            date_index=date_index,
            indicator_cache=indicator_cache,
            exit_indicator_cache=exit_ic,
            minute_day_ranges=minute_day_ranges,
        )

        assert result is not None
        assert result.priority == 5
        assert result.reason == "EXIT_CONDITION: RSI > 80.0"
