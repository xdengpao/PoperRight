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
