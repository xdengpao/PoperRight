"""
BacktestEngine T+1 规则不变量属性测试（Hypothesis）

属性 20：回测 T+1 规则不变量

对任意策略驱动回测结果的交易记录，验证不存在同一标的在同一交易日
既有买入又有卖出（严格遵守 A 股 T+1 规则）。

A 股 T+1 核心语义：当日买入的股票当日不可卖出，必须等到下一个交易日。
引擎通过 buy_date >= sig_date 检查来强制执行此规则。

**Validates: Requirements 12.30**
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    BacktestConfig,
    KlineBar,
    RiskLevel,
    ScreenItem,
    SignalCategory,
    SignalDetail,
    StrategyConfig,
)
from app.services.backtest_engine import (
    BacktestEngine,
    _BacktestPosition,
    _BacktestState,
    _SellSignal,
    _TradeRecord,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_TRADE_DATES = [
    date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12),
    date(2024, 6, 13), date(2024, 6, 14),
]

_SYMBOLS = [
    "600001.SH", "600002.SH", "600003.SH",
    "000001.SZ", "000002.SZ",
]

_close_price = st.decimals(
    min_value=Decimal("5.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_quantity = st.sampled_from([100, 200, 300, 500, 1000])

_open_price_ratio = st.floats(min_value=0.92, max_value=1.08, allow_nan=False)

_sell_reason = st.sampled_from([
    "STOP_LOSS", "TREND_BREAK", "TRAILING_STOP", "MAX_HOLDING_DAYS",
])

_initial_cash = st.decimals(
    min_value=Decimal("200000.00"),
    max_value=Decimal("2000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_config() -> BacktestConfig:
    return BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        max_holdings=5,
    )


def _make_kline_bar(
    symbol: str,
    bar_date: date,
    open_price: Decimal,
    close_price: Decimal,
) -> KlineBar:
    high = max(open_price, close_price) + Decimal("0.10")
    low = min(open_price, close_price) - Decimal("0.10")
    if low < Decimal("0.01"):
        low = Decimal("0.01")
    return KlineBar(
        time=datetime(bar_date.year, bar_date.month, bar_date.day, 15, 0),
        symbol=symbol,
        freq="1d",
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        volume=1000000,
        amount=Decimal("50000000"),
        turnover=Decimal("3.5"),
        vol_ratio=Decimal("1.2"),
    )


def _assert_t1_no_sell_on_buy_day(records: list[_TradeRecord]) -> None:
    """
    验证 T+1 不变量：当日买入的标的当日不可卖出。
    """
    buys: set[tuple[str, date]] = set()
    sells: set[tuple[str, date]] = set()

    for rec in records:
        key = (rec.symbol, rec.date)
        if rec.action == "BUY":
            buys.add(key)
        elif rec.action == "SELL":
            sells.add(key)

    overlap = buys & sells
    assert not overlap, (
        f"T+1 违规：以下 (symbol, date) 同时存在 BUY 和 SELL: {overlap}"
    )


# ---------------------------------------------------------------------------
# 属性 20（a）：引擎 T+1 规则 — 当日买入不可当日卖出
# ---------------------------------------------------------------------------


@given(
    prev_close=_close_price,
    open_ratio=_open_price_ratio,
    cash=_initial_cash,
    sell_reason=_sell_reason,
)
@settings(max_examples=100)
def test_t1_cannot_sell_on_buy_day(
    prev_close: Decimal,
    open_ratio: float,
    cash: Decimal,
    sell_reason: str,
) -> None:
    """
    **Validates: Requirements 12.30**

    属性 20：当日买入的标的当日不可卖出。

    场景：
    - 标的在 T+1 日买入（buy_date = T+1）
    - 在 T+1 日触发卖出信号，_execute_sells 在 T+2 执行
    - 验证交易记录中买入日（T+1）不会出现同标的的卖出记录
    """
    signal_date = date(2024, 6, 10)  # T
    buy_exec_date = date(2024, 6, 11)  # T+1
    day_after = date(2024, 6, 12)  # T+2

    next_open = (prev_close * Decimal(str(open_ratio))).quantize(Decimal("0.01"))
    assume(next_open > Decimal("0"))

    limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
    limit_down = (prev_close * Decimal("0.90")).quantize(Decimal("0.01"))
    assume(next_open < limit_up)
    assume(next_open > limit_down)

    symbol = "600001.SH"
    config = _make_config()

    # K 线数据：T, T+1, T+2
    bar_t = _make_kline_bar(symbol, signal_date, prev_close, prev_close)
    bar_t1 = _make_kline_bar(symbol, buy_exec_date, next_open, next_open)
    bar_t2 = _make_kline_bar(symbol, day_after, next_open, next_open)
    kline_data = {symbol: [bar_t, bar_t1, bar_t2]}

    # 模拟当日买入的持仓（buy_date = T+1）
    position = _BacktestPosition(
        symbol=symbol,
        quantity=200,
        cost_price=next_open,
        buy_date=buy_exec_date,
        buy_trade_day_index=1,
        highest_close=next_open,
        sector="",
    )

    state = _BacktestState(cash=cash, positions={symbol: position})
    engine = BacktestEngine()

    # 卖出信号在买入当日触发
    sell_signal = _SellSignal(
        symbol=symbol,
        reason=sell_reason,
        trigger_date=buy_exec_date,
        priority=1,
    )

    sell_records = engine._execute_sells(
        [sell_signal], buy_exec_date, kline_data, state, config,
    )

    # 构造买入记录（模拟当日买入）
    buy_record = _TradeRecord(
        date=buy_exec_date,
        symbol=symbol,
        action="BUY",
        price=next_open,
        quantity=200,
        cost=Decimal("0"),
        amount=next_open * 200,
    )

    all_records = [buy_record] + sell_records
    _assert_t1_no_sell_on_buy_day(all_records)


# ---------------------------------------------------------------------------
# 属性 20（b）：信号驱动路径 T+1 规则验证
#
# 注意：同一标的在同一日先卖出（之前买入的持仓）再买入是合法的，
# T+1 只禁止：当日新买入的股票当日卖出。
# ---------------------------------------------------------------------------

_signal_entry = st.fixed_dictionaries({
    "date": st.sampled_from(_TRADE_DATES),
    "symbol": st.sampled_from(_SYMBOLS),
    "action": st.sampled_from(["BUY", "SELL"]),
    "price": st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
    "quantity": st.sampled_from([100, 200, 300, 500]),
})


@given(
    signals=st.lists(_signal_entry, min_size=2, max_size=20),
    initial_capital=st.decimals(
        min_value=Decimal("100000"),
        max_value=Decimal("5000000"),
        places=0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(max_examples=100)
def test_t1_invariant_signal_driven_path(
    signals: list[dict],
    initial_capital: Decimal,
) -> None:
    """
    **Validates: Requirements 12.30**

    属性 20：对任意信号序列通过旧路径 run_backtest(config, signals) 执行后，
    验证 T+1 核心语义：不存在当日买入后当日卖出同一标的的情况。

    具体验证：对每个标的，按时间顺序检查交易记录，追踪每次买入的日期，
    确保卖出操作不会发生在最近一次买入的同一天。
    """
    config = BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=initial_capital,
    )

    engine = BacktestEngine()
    result = engine.run_backtest(config, signals=signals)

    # 按标的分组，按日期排序，验证 T+1 语义
    records_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for rec in result.trade_records:
        records_by_symbol[rec["symbol"]].append(rec)

    for symbol, recs in records_by_symbol.items():
        sorted_recs = sorted(recs, key=lambda r: r["date"])
        last_buy_date: str | None = None
        for rec in sorted_recs:
            if rec["action"] == "BUY":
                last_buy_date = rec["date"]
            elif rec["action"] == "SELL":
                assert rec["date"] != last_buy_date, (
                    f"T+1 违规：{symbol} 在 {rec['date']} 当日买入后当日卖出"
                )


# ---------------------------------------------------------------------------
# 属性 20（c）：多标的并发买卖场景下的 T+1 不变量
# ---------------------------------------------------------------------------


@given(
    num_sell=st.integers(min_value=1, max_value=3),
    num_buy=st.integers(min_value=1, max_value=3),
    prev_close=_close_price,
    open_ratio=_open_price_ratio,
    cash=_initial_cash,
)
@settings(max_examples=100)
def test_t1_invariant_multi_stock_concurrent(
    num_sell: int,
    num_buy: int,
    prev_close: Decimal,
    open_ratio: float,
    cash: Decimal,
) -> None:
    """
    **Validates: Requirements 12.30**

    属性 20：多只股票同时触发买入和卖出时（不同标的），验证所有
    交易记录均遵守 T+1 不变量。
    """
    signal_date = date(2024, 6, 10)
    exec_date = date(2024, 6, 11)

    next_open = (prev_close * Decimal(str(open_ratio))).quantize(Decimal("0.01"))
    assume(next_open > Decimal("0"))

    limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
    limit_down = (prev_close * Decimal("0.90")).quantize(Decimal("0.01"))
    assume(next_open < limit_up)
    assume(next_open > limit_down)

    config = _make_config()
    engine = BacktestEngine()

    sell_symbols = [f"6000{i:02d}.SH" for i in range(1, num_sell + 1)]
    buy_symbols = [f"0000{i:02d}.SZ" for i in range(1, num_buy + 1)]

    kline_data: dict[str, list[KlineBar]] = {}
    for sym in sell_symbols + buy_symbols:
        bar_t = _make_kline_bar(sym, signal_date, prev_close, prev_close)
        bar_t1 = _make_kline_bar(sym, exec_date, next_open, next_open)
        kline_data[sym] = [bar_t, bar_t1]

    positions: dict[str, _BacktestPosition] = {}
    for sym in sell_symbols:
        positions[sym] = _BacktestPosition(
            symbol=sym,
            quantity=200,
            cost_price=prev_close,
            buy_date=date(2024, 6, 1),
            buy_trade_day_index=0,
            highest_close=prev_close,
            sector="",
        )

    state = _BacktestState(cash=cash, positions=positions)

    sell_signals = [
        _SellSignal(
            symbol=sym, reason="STOP_LOSS",
            trigger_date=signal_date, priority=1,
        )
        for sym in sell_symbols
    ]
    sell_records = engine._execute_sells(
        sell_signals, signal_date, kline_data, state, config,
    )

    buy_candidates = [
        ScreenItem(
            symbol=sym,
            ref_buy_price=prev_close,
            trend_score=85.0,
            risk_level=RiskLevel.LOW,
            signals=[SignalDetail(
                category=SignalCategory.MA_TREND, label="多头排列",
            )],
        )
        for sym in buy_symbols
    ]
    buy_records = engine._execute_buys(
        buy_candidates, signal_date, kline_data, state, config,
    )

    all_records = sell_records + buy_records
    _assert_t1_no_sell_on_buy_day(all_records)

    sold_symbols = {r.symbol for r in sell_records}
    bought_symbols = {r.symbol for r in buy_records}
    overlap = sold_symbols & bought_symbols
    assert not overlap, (
        f"卖出和买入标的不应重叠: {overlap}"
    )
