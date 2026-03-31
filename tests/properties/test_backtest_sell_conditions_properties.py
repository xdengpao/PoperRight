"""
BacktestEngine 卖出条件触发与优先级正确性属性测试（Hypothesis）

**Validates: Requirements 12.17, 12.18, 12.19, 12.20, 12.21, 12.22**

属性 22g：回测卖出条件触发与优先级正确性
- 固定止损优先级最高（priority=1）
- 趋势破位次之（priority=2）
- 移动止盈再次（priority=3）
- 持仓超期最低（priority=4）
- 涨停日不计入移动止盈回撤
- 同日多条件触发时记录最高优先级原因
- 停牌（无K线数据）时返回 None
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import BacktestConfig, KlineBar, StrategyConfig
from app.services.backtest_engine import BacktestEngine, _BacktestPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(
    close: Decimal,
    bar_date: date,
    symbol: str = "000001.SZ",
) -> KlineBar:
    """构造一个最小化的 KlineBar（close 为 Decimal）。"""
    return KlineBar(
        time=datetime(bar_date.year, bar_date.month, bar_date.day),
        symbol=symbol,
        freq="1d",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100_000,
        amount=Decimal("1000000"),
        turnover=Decimal("5.0"),
        vol_ratio=Decimal("1.0"),
    )


def _make_config(**overrides) -> BacktestConfig:
    """构造最小化 BacktestConfig。"""
    sc = StrategyConfig(factors=[], logic="AND", weights={}, ma_periods=[5, 10, 20])
    defaults = dict(
        strategy_config=sc,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        stop_loss_pct=0.08,
        trailing_stop_pct=0.05,
        max_holding_days=20,
        trend_stop_ma=20,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# A 股价格（2 位小数 Decimal）
_dec_price = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("200.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_stop_loss_pct = st.floats(
    min_value=0.03, max_value=0.30,
    allow_nan=False, allow_infinity=False,
)

_trailing_stop_pct = st.floats(
    min_value=0.02, max_value=0.30,
    allow_nan=False, allow_infinity=False,
)

_max_holding_days = st.integers(min_value=1, max_value=60)


# ---------------------------------------------------------------------------
# 属性 22g-1：固定止损触发时 reason="STOP_LOSS", priority=1
# ---------------------------------------------------------------------------


@given(
    cost_price=_dec_price,
    stop_loss_pct=_stop_loss_pct,
)
@settings(max_examples=100)
def test_stop_loss_triggers_with_priority_1(
    cost_price: Decimal,
    stop_loss_pct: float,
) -> None:
    """
    **Validates: Requirements 12.17, 12.18**

    属性 22g（子属性 1）：当收盘价相对成本价亏损 >= stop_loss_pct 时，
    返回 STOP_LOSS 信号，priority=1。
    """
    # 构造收盘价使得亏损恰好 >= stop_loss_pct
    close = (cost_price * Decimal(str(1 - stop_loss_pct))).quantize(Decimal("0.01"))
    assume(close >= Decimal("0.01"))

    # 验证确实触发止损
    loss_pct = float((cost_price - close) / cost_price)
    assume(loss_pct >= stop_loss_pct)

    trade_date = date(2024, 6, 15)
    prev_date = trade_date - timedelta(days=1)
    symbol = "000001.SZ"

    # 需要 2 根 bar：前一日 close = cost_price（用于涨停判断），当日 close 触发止损
    # 前一日 close = cost_price 确保当日不是涨停日
    bar_prev = _make_bar(cost_price, prev_date, symbol)
    bar_today = _make_bar(close, trade_date, symbol)
    kline_data = {symbol: [bar_prev, bar_today]}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 6, 1),
        buy_trade_day_index=0,
        highest_close=cost_price,
    )

    config = _make_config(
        stop_loss_pct=stop_loss_pct,
        trailing_stop_pct=0.99,  # 不触发移动止盈
        trend_stop_ma=20,  # 2 根 bar 不够 MA20
    )
    engine = BacktestEngine()

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is not None, (
        f"止损条件应触发: cost={cost_price}, close={close}, "
        f"loss_pct={loss_pct:.4f}, threshold={stop_loss_pct}"
    )
    assert result.reason == "STOP_LOSS"
    assert result.priority == 1


# ---------------------------------------------------------------------------
# 属性 22g-2：趋势破位触发时 reason="TREND_BREAK", priority=2（止损未触发）
# ---------------------------------------------------------------------------


@given(
    ma_close=_dec_price,
    drop_pct=st.floats(min_value=0.005, max_value=0.05, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_trend_break_triggers_with_priority_2(
    ma_close: Decimal,
    drop_pct: float,
) -> None:
    """
    **Validates: Requirements 12.17, 12.19**

    属性 22g（子属性 2）：当收盘价跌破 trend_stop_ma 均线且止损未触发时，
    返回 TREND_BREAK 信号，priority=2。
    """
    trade_date = date(2024, 6, 15)
    symbol = "000001.SZ"
    ma_period = 5  # 使用短均线以减少需要的 bar 数量

    # 当日收盘价略低于均线
    close_today = (ma_close * Decimal(str(1 - drop_pct))).quantize(Decimal("0.01"))
    assume(close_today >= Decimal("0.01"))

    # MA = (ma_close * (ma_period-1) + close_today) / ma_period
    ma_val = (float(ma_close) * (ma_period - 1) + float(close_today)) / ma_period
    assume(float(close_today) < ma_val)

    # 成本价设得很低，确保不触发止损
    cost_price = (close_today * Decimal("0.5")).quantize(Decimal("0.01"))
    assume(cost_price >= Decimal("0.01"))

    bars: list[KlineBar] = []
    for i in range(ma_period):
        bar_date = trade_date - timedelta(days=ma_period - 1 - i)
        if i < ma_period - 1:
            bars.append(_make_bar(ma_close, bar_date, symbol))
        else:
            bars.append(_make_bar(close_today, bar_date, symbol))

    kline_data = {symbol: bars}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=ma_close,
    )

    config = _make_config(
        stop_loss_pct=0.99,  # 不触发止损
        trend_stop_ma=ma_period,
        trailing_stop_pct=0.99,  # 不触发移动止盈
    )
    engine = BacktestEngine()

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is not None, (
        f"趋势破位应触发: close={close_today}, ma={ma_val:.4f}"
    )
    assert result.reason == "TREND_BREAK"
    assert result.priority == 2


# ---------------------------------------------------------------------------
# 属性 22g-3：移动止盈触发时 reason="TRAILING_STOP", priority=3
# ---------------------------------------------------------------------------


@given(
    highest_close=st.decimals(
        min_value=Decimal("5.00"), max_value=Decimal("200.00"),
        places=2, allow_nan=False, allow_infinity=False,
    ),
    trailing_stop_pct=_trailing_stop_pct,
)
@settings(max_examples=100)
def test_trailing_stop_triggers_with_priority_3(
    highest_close: Decimal,
    trailing_stop_pct: float,
) -> None:
    """
    **Validates: Requirements 12.17, 12.20**

    属性 22g（子属性 3）：当收盘价从 highest_close 回撤 >= trailing_stop_pct 时，
    且止损和趋势破位均未触发，返回 TRAILING_STOP 信号，priority=3。
    """
    # 构造收盘价使得回撤 >= trailing_stop_pct
    close_today = (highest_close * Decimal(str(1 - trailing_stop_pct))).quantize(
        Decimal("0.01")
    )
    assume(close_today >= Decimal("0.01"))

    # 验证回撤确实 >= trailing_stop_pct
    drawdown = float((highest_close - close_today) / highest_close)
    assume(drawdown >= trailing_stop_pct)

    trade_date = date(2024, 6, 15)
    prev_date = trade_date - timedelta(days=1)
    symbol = "000001.SZ"

    # 成本价设得很低，确保不触发止损
    cost_price = (close_today * Decimal("0.3")).quantize(Decimal("0.01"))
    assume(cost_price >= Decimal("0.01"))

    # 需要 2 根 bar：前一日 close = highest_close（正常非涨停日），当日 close 回撤
    # 前一日 close = highest_close 确保 highest_close 已经被正确设置
    bar_prev = _make_bar(highest_close, prev_date, symbol)
    bar_today = _make_bar(close_today, trade_date, symbol)
    kline_data = {symbol: [bar_prev, bar_today]}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=highest_close,
    )

    config = _make_config(
        stop_loss_pct=0.99,  # 不触发止损
        trailing_stop_pct=trailing_stop_pct,
        trend_stop_ma=20,  # 2 根 bar 不够 MA20，趋势破位不触发
    )
    engine = BacktestEngine()

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is not None, (
        f"移动止盈应触发: highest={highest_close}, close={close_today}, "
        f"drawdown={drawdown:.4f}, threshold={trailing_stop_pct}"
    )
    assert result.reason == "TRAILING_STOP"
    assert result.priority == 3


# ---------------------------------------------------------------------------
# 属性 22g-4：持仓超期触发时 reason="MAX_HOLDING_DAYS", priority=4
# ---------------------------------------------------------------------------


@given(
    max_holding_days=_max_holding_days,
    close_price=_dec_price,
)
@settings(max_examples=100)
def test_max_holding_days_triggers_with_priority_4(
    max_holding_days: int,
    close_price: Decimal,
) -> None:
    """
    **Validates: Requirements 12.17, 12.22**

    属性 22g（子属性 4）：当持仓交易日数 > max_holding_days 且前三种条件均未触发时，
    返回 MAX_HOLDING_DAYS 信号，priority=4。
    """
    trade_date = date(2024, 6, 15)
    prev_date = trade_date - timedelta(days=1)
    symbol = "000001.SZ"

    # 成本价 = 收盘价（无亏损，不触发止损）
    cost_price = close_price

    # 2 根 bar（不够 MA20，趋势破位不触发）
    bar_prev = _make_bar(close_price, prev_date, symbol)
    bar_today = _make_bar(close_price, trade_date, symbol)
    kline_data = {symbol: [bar_prev, bar_today]}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=close_price,
    )

    config = _make_config(
        stop_loss_pct=0.99,  # 不触发止损
        trailing_stop_pct=0.99,  # 不触发移动止盈
        max_holding_days=max_holding_days,
        trend_stop_ma=20,  # 2 根 bar 不够 MA20
    )

    engine = BacktestEngine()
    # 设置 _current_trade_day_index 使得超期
    engine._current_trade_day_index = max_holding_days + 1

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is not None, (
        f"持仓超期应触发: holding_days={max_holding_days + 1}, "
        f"max={max_holding_days}"
    )
    assert result.reason == "MAX_HOLDING_DAYS"
    assert result.priority == 4


# ---------------------------------------------------------------------------
# 属性 22g-5：多条件同时触发时，最高优先级（最低 priority 数字）胜出
# ---------------------------------------------------------------------------


@given(
    cost_price=st.decimals(
        min_value=Decimal("10.00"), max_value=Decimal("200.00"),
        places=2, allow_nan=False, allow_infinity=False,
    ),
    stop_loss_pct=st.floats(
        min_value=0.05, max_value=0.20,
        allow_nan=False, allow_infinity=False,
    ),
    trailing_stop_pct=st.floats(
        min_value=0.02, max_value=0.15,
        allow_nan=False, allow_infinity=False,
    ),
)
@settings(max_examples=100)
def test_highest_priority_wins_when_multiple_conditions_trigger(
    cost_price: Decimal,
    stop_loss_pct: float,
    trailing_stop_pct: float,
) -> None:
    """
    **Validates: Requirements 12.17, 12.18, 12.20, 12.22**

    属性 22g（子属性 5）：当同日多条件触发时，记录最高优先级原因。
    构造同时触发止损 + 移动止盈 + 超期的场景，应返回 STOP_LOSS（priority=1）。
    """
    # 构造收盘价使得止损触发
    close_today = (cost_price * Decimal(str(1 - stop_loss_pct))).quantize(
        Decimal("0.01")
    )
    assume(close_today >= Decimal("0.01"))

    # 验证止损确实触发
    loss_pct = float((cost_price - close_today) / cost_price)
    assume(loss_pct >= stop_loss_pct)

    # highest_close 设得足够高使得移动止盈也触发
    # drawdown = (highest - close) / highest >= trailing_stop_pct
    # highest >= close / (1 - trailing_stop_pct)
    highest_close = (
        close_today / Decimal(str(max(1 - trailing_stop_pct, 0.01)))
    ).quantize(Decimal("0.01"))
    assume(highest_close > close_today)
    drawdown = float((highest_close - close_today) / highest_close)
    assume(drawdown >= trailing_stop_pct)

    trade_date = date(2024, 6, 15)
    prev_date = trade_date - timedelta(days=1)
    symbol = "000001.SZ"

    # 2 根 bar（趋势破位不触发，因为 bar 数不够 MA20）
    bar_prev = _make_bar(cost_price, prev_date, symbol)
    bar_today = _make_bar(close_today, trade_date, symbol)
    kline_data = {symbol: [bar_prev, bar_today]}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=highest_close,
    )

    config = _make_config(
        stop_loss_pct=stop_loss_pct,
        trailing_stop_pct=trailing_stop_pct,
        max_holding_days=1,  # 超期也触发
        trend_stop_ma=20,
    )

    engine = BacktestEngine()
    engine._current_trade_day_index = 100  # 确保超期

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is not None
    # 止损优先级最高，应胜出
    assert result.reason == "STOP_LOSS", (
        f"多条件触发时应返回最高优先级 STOP_LOSS，实际返回 {result.reason}。"
        f" cost={cost_price}, close={close_today}, loss_pct={loss_pct:.4f},"
        f" stop_loss_pct={stop_loss_pct}"
    )
    assert result.priority == 1


# ---------------------------------------------------------------------------
# 属性 22g-6：涨停日不计入移动止盈回撤（highest_close 不更新）
# ---------------------------------------------------------------------------


@given(
    prev_close=st.decimals(
        min_value=Decimal("5.00"), max_value=Decimal("100.00"),
        places=2, allow_nan=False, allow_infinity=False,
    ),
)
@settings(max_examples=100)
def test_limit_up_day_excluded_from_trailing_stop(
    prev_close: Decimal,
) -> None:
    """
    **Validates: Requirements 12.21**

    属性 22g（子属性 6）：涨停日（close == 涨停价）不应更新 highest_close，
    从而不影响移动止盈回撤计算。
    """
    trade_date = date(2024, 6, 15)
    prev_date = trade_date - timedelta(days=1)
    symbol = "000001.SZ"

    # 计算涨停价（与 BacktestEngine._calc_limit_prices 一致）
    limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
    assume(limit_up > prev_close)

    # 当日收盘价 = 涨停价
    close_today = limit_up

    # 设置 highest_close 低于涨停价，如果涨停日被计入则 highest_close 会被更新
    initial_highest = (prev_close * Decimal("0.95")).quantize(Decimal("0.01"))
    assume(initial_highest >= Decimal("0.01"))
    assume(close_today > initial_highest)

    bar_prev = _make_bar(prev_close, prev_date, symbol)
    bar_today = _make_bar(close_today, trade_date, symbol)
    kline_data = {symbol: [bar_prev, bar_today]}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=(prev_close * Decimal("0.5")).quantize(Decimal("0.01")),
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=initial_highest,
    )

    config = _make_config(
        stop_loss_pct=0.99,
        trailing_stop_pct=0.99,
        trend_stop_ma=20,
    )
    engine = BacktestEngine()

    engine._check_sell_conditions(position, trade_date, kline_data, config)

    # 涨停日（close == limit_up）不应更新 highest_close
    # 代码逻辑：if close > highest_close and close < limit_up → 不满足 close < limit_up
    assert position.highest_close == initial_highest, (
        f"涨停日不应更新 highest_close: "
        f"initial={initial_highest}, after={position.highest_close}, "
        f"close={close_today}, limit_up={limit_up}"
    )


# ---------------------------------------------------------------------------
# 属性 22g-7：停牌（无当日K线数据）时返回 None
# ---------------------------------------------------------------------------


@given(
    cost_price=_dec_price,
    close_price=_dec_price,
)
@settings(max_examples=100)
def test_suspension_returns_none(
    cost_price: Decimal,
    close_price: Decimal,
) -> None:
    """
    **Validates: Requirements 12.17**

    属性 22g（子属性 7）：当 trade_date 无 K 线数据（停牌）时，
    _check_sell_conditions 返回 None。
    """
    trade_date = date(2024, 6, 15)
    symbol = "000001.SZ"

    # 只有前一天的 bar，当日无数据（停牌）
    bars = [_make_bar(close_price, trade_date - timedelta(days=1), symbol)]
    kline_data = {symbol: bars}

    position = _BacktestPosition(
        symbol=symbol,
        quantity=1000,
        cost_price=cost_price,
        buy_date=date(2024, 5, 1),
        buy_trade_day_index=0,
        highest_close=max(cost_price, close_price),
    )

    config = _make_config(stop_loss_pct=0.01, max_holding_days=1)
    engine = BacktestEngine()
    engine._current_trade_day_index = 100

    result = engine._check_sell_conditions(position, trade_date, kline_data, config)

    assert result is None, (
        f"停牌时应返回 None，实际返回 {result}"
    )
