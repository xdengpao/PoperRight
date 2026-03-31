"""
BacktestEngine 卖出执行属性测试（Hypothesis）

属性 22h：回测资金 T+1 可用规则

**Validates: Requirements 12.24**
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    BacktestConfig,
    KlineBar,
    StrategyConfig,
)
from app.services.backtest_engine import (
    BacktestEngine,
    _BacktestPosition,
    _BacktestState,
    _SellSignal,
)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_SIGNAL_DATE = date(2024, 6, 10)  # T: 卖出信号日
_EXEC_DATE = date(2024, 6, 11)    # T+1: 卖出执行日


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_close_price = st.decimals(
    min_value=Decimal("2.00"),
    max_value=Decimal("200.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# T+1 开盘价比例：在 prev_close 的 (0.91, 1.09) 范围内（避免跌停）
_open_price_ratio = st.floats(min_value=0.92, max_value=1.09, allow_nan=False)

_quantity = st.sampled_from([100, 200, 300, 500, 1000, 2000])

_initial_cash = st.decimals(
    min_value=Decimal("10000.00"),
    max_value=Decimal("2000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_sell_reason = st.sampled_from(["STOP_LOSS", "TREND_BREAK", "TRAILING_STOP", "MAX_HOLDING_DAYS"])
_sell_priority = st.sampled_from([1, 2, 3, 4])

_commission_sell = st.decimals(
    min_value=Decimal("0.0005"),
    max_value=Decimal("0.005"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

_slippage = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("0.005"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_config(
    commission_sell: Decimal = Decimal("0.0013"),
    slippage: Decimal = Decimal("0.001"),
) -> BacktestConfig:
    return BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        commission_sell=commission_sell,
        slippage=slippage,
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


def _build_kline_data(
    symbol: str,
    prev_close: Decimal,
    next_open: Decimal,
) -> dict[str, list[KlineBar]]:
    bar_t = _make_kline_bar(symbol, _SIGNAL_DATE, prev_close, prev_close)
    bar_t1 = _make_kline_bar(symbol, _EXEC_DATE, next_open, next_open)
    return {symbol: [bar_t, bar_t1]}


# ---------------------------------------------------------------------------
# 属性 22h：回测资金 T+1 可用规则
# ---------------------------------------------------------------------------


@given(
    prev_close=_close_price,
    open_ratio=_open_price_ratio,
    quantity=_quantity,
    initial_cash=_initial_cash,
    reason=_sell_reason,
    priority=_sell_priority,
    comm_sell=_commission_sell,
    slippage=_slippage,
)
@settings(max_examples=100)
def test_sell_proceeds_go_to_frozen_cash_not_cash(
    prev_close: Decimal,
    open_ratio: float,
    quantity: int,
    initial_cash: Decimal,
    reason: str,
    priority: int,
    comm_sell: Decimal,
    slippage: Decimal,
) -> None:
    """
    **Validates: Requirements 12.24**

    属性 22h：对任意回测交易日，验证当日卖出回收资金不用于当日买入；
    次日起方可用于新买入。

    具体验证：
    1. _execute_sells 后，卖出收益进入 frozen_cash（非 cash）
    2. cash 不因卖出收益而增加
    3. frozen_cash 增加额 == 净卖出收益（卖出金额 - 手续费 - 滑点）
    """
    next_open = (prev_close * Decimal(str(open_ratio))).quantize(Decimal("0.01"))
    assume(next_open > Decimal("0"))

    # 确保不是跌停价（跌停无法卖出）
    limit_down = (prev_close * Decimal("0.90")).quantize(Decimal("0.01"))
    assume(next_open > limit_down)

    symbol = "600001.SH"
    config = _make_config(commission_sell=comm_sell, slippage=slippage)

    # 构建持仓（买入日早于信号日，满足 T+1）
    position = _BacktestPosition(
        symbol=symbol,
        quantity=quantity,
        cost_price=prev_close,
        buy_date=date(2024, 6, 1),
        buy_trade_day_index=0,
        highest_close=prev_close,
        sector="",
    )

    state = _BacktestState(
        cash=initial_cash,
        frozen_cash=Decimal("0"),
        positions={symbol: position},
    )

    kline_data = _build_kline_data(symbol, prev_close, next_open)

    sell_signal = _SellSignal(
        symbol=symbol,
        reason=reason,
        trigger_date=_SIGNAL_DATE,
        priority=priority,
    )

    cash_before = state.cash
    frozen_before = state.frozen_cash

    engine = BacktestEngine()
    records = engine._execute_sells([sell_signal], _SIGNAL_DATE, kline_data, state, config)

    if not records:
        # 卖出未执行（可能跌停等），状态不变
        assert state.cash == cash_before
        assert state.frozen_cash == frozen_before
        return

    assert len(records) == 1
    rec = records[0]

    # 计算预期净收益
    sell_amount = next_open * quantity
    sell_cost = sell_amount * comm_sell + sell_amount * slippage
    expected_proceeds = sell_amount - sell_cost

    # 验证 1：cash 不因卖出而增加（当日不可用）
    assert state.cash == cash_before, (
        f"卖出后 cash 应保持不变 {cash_before}，实际为 {state.cash}"
    )

    # 验证 2：frozen_cash 增加了净卖出收益
    frozen_increase = state.frozen_cash - frozen_before
    assert frozen_increase == expected_proceeds, (
        f"frozen_cash 增加额应为 {expected_proceeds}，"
        f"实际增加 {frozen_increase}"
    )

    # 验证 3：frozen_cash 中包含卖出收益（非 cash）
    assert state.frozen_cash > Decimal("0"), (
        "卖出后 frozen_cash 应大于 0"
    )
