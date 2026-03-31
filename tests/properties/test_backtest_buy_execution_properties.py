"""
BacktestEngine 买入执行属性测试（Hypothesis）

属性 22a：回测买入以 T+1 开盘价执行
属性 22b：回测持仓数量上限不变量
属性 22d：回测仓位限制不变量

**Validates: Requirements 12.8, 12.9, 12.10, 12.13, 12.15, 12.27**
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_SIGNAL_DATE = date(2024, 6, 10)       # T: 信号日
_EXEC_DATE = date(2024, 6, 11)         # T+1: 执行日

_signal_detail = st.builds(
    SignalDetail,
    category=st.sampled_from(list(SignalCategory)),
    label=st.text(min_size=1, max_size=6),
    is_fake_breakout=st.just(False),
)

# 生成唯一 symbol 的 ScreenItem
_symbol_strategy = st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True)

_screen_item = st.builds(
    ScreenItem,
    symbol=_symbol_strategy,
    ref_buy_price=st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("200.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    trend_score=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    risk_level=st.sampled_from(list(RiskLevel)),
    signals=st.lists(_signal_detail, min_size=1, max_size=3),
    has_fake_breakout=st.just(False),
)

# 收盘价（信号日 T 的收盘价，用于计算涨停价）
_close_price = st.decimals(
    min_value=Decimal("2.00"),
    max_value=Decimal("200.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# T+1 开盘价：在 prev_close 的 ±10% 范围内
_open_price_ratio = st.floats(min_value=0.91, max_value=1.09, allow_nan=False)

_sectors = st.sampled_from(["电子", "医药", "银行", "新能源", "消费", "科技", ""])

_max_holdings = st.integers(min_value=2, max_value=10)

_cash = st.decimals(
    min_value=Decimal("50000.00"),
    max_value=Decimal("2000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_config(
    max_holdings: int = 5,
    max_position_pct: float = 0.15,
    max_sector_pct: float = 0.30,
) -> BacktestConfig:
    return BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        max_holdings=max_holdings,
        max_position_pct=max_position_pct,
        max_sector_pct=max_sector_pct,
    )


def _make_kline_bar(
    symbol: str,
    bar_date: date,
    open_price: Decimal,
    close_price: Decimal,
) -> KlineBar:
    """构造一个最小化的 KlineBar。"""
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
    """为单只股票构建包含信号日 T 和执行日 T+1 的 K 线数据。"""
    bar_t = _make_kline_bar(symbol, _SIGNAL_DATE, prev_close, prev_close)
    bar_t1 = _make_kline_bar(symbol, _EXEC_DATE, next_open, next_open)
    return {symbol: [bar_t, bar_t1]}


def _build_multi_kline_data(
    entries: list[tuple[str, Decimal, Decimal]],
) -> dict[str, list[KlineBar]]:
    """为多只股票构建 K 线数据。entries: [(symbol, prev_close, next_open), ...]"""
    kline_data: dict[str, list[KlineBar]] = {}
    for symbol, prev_close, next_open in entries:
        bar_t = _make_kline_bar(symbol, _SIGNAL_DATE, prev_close, prev_close)
        bar_t1 = _make_kline_bar(symbol, _EXEC_DATE, next_open, next_open)
        kline_data[symbol] = [bar_t, bar_t1]
    return kline_data



# ---------------------------------------------------------------------------
# 属性 22a：回测买入以 T+1 开盘价执行
# ---------------------------------------------------------------------------


@given(
    prev_close=_close_price,
    open_ratio=_open_price_ratio,
    cash=_cash,
    max_holdings=_max_holdings,
)
@settings(max_examples=100)
def test_buy_executes_at_t_plus_1_open_price(
    prev_close: Decimal,
    open_ratio: float,
    cash: Decimal,
    max_holdings: int,
) -> None:
    """
    **Validates: Requirements 12.8, 12.9**

    属性 22a：对任意回测结果中的买入记录，验证：
    1. 执行日期为信号日 T+1
    2. 执行价格为 T+1 开盘价
    3. T+1 开盘价 == 涨停价时无买入记录
    """
    next_open = (prev_close * Decimal(str(open_ratio))).quantize(Decimal("0.01"))
    assume(next_open > Decimal("0"))

    symbol = "600001.SH"
    candidate = ScreenItem(
        symbol=symbol,
        ref_buy_price=prev_close,
        trend_score=85.0,
        risk_level=RiskLevel.LOW,
        signals=[SignalDetail(category=SignalCategory.MA_TREND, label="多头排列")],
    )

    kline_data = _build_kline_data(symbol, prev_close, next_open)
    state = _BacktestState(cash=cash)
    config = _make_config(max_holdings=max_holdings)

    engine = BacktestEngine()
    records = engine._execute_buys([candidate], _SIGNAL_DATE, kline_data, state, config)

    # 计算涨停价
    limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))

    if next_open >= limit_up:
        # 涨停无法买入 → 无记录
        assert len(records) == 0, (
            f"T+1 开盘价 {next_open} >= 涨停价 {limit_up}，不应有买入记录"
        )
    else:
        # 可能有买入记录（也可能因资金不足等原因无记录）
        for rec in records:
            assert rec.date == _EXEC_DATE, (
                f"买入执行日期应为 T+1 ({_EXEC_DATE})，实际为 {rec.date}"
            )
            assert rec.price == next_open, (
                f"买入价格应为 T+1 开盘价 {next_open}，实际为 {rec.price}"
            )
            assert rec.action == "BUY", (
                f"交易方向应为 BUY，实际为 {rec.action}"
            )


# ---------------------------------------------------------------------------
# 属性 22b：回测持仓数量上限不变量
# ---------------------------------------------------------------------------


@given(
    candidates=st.lists(_screen_item, min_size=1, max_size=12),
    max_holdings=_max_holdings,
    cash=_cash,
    existing_count=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_positions_never_exceed_max_holdings(
    candidates: list[ScreenItem],
    max_holdings: int,
    cash: Decimal,
    existing_count: int,
) -> None:
    """
    **Validates: Requirements 12.10, 12.15**

    属性 22b：对任意回测运行过程中的任意交易日快照，验证：
    1. 持仓数量 ≤ max_holdings
    2. 无重复买入（已持仓标的不会再次出现在买入记录中）
    """
    assume(existing_count < max_holdings)

    # 确保候选标的 symbol 唯一
    seen_symbols: set[str] = set()
    unique_candidates: list[ScreenItem] = []
    for c in candidates:
        if c.symbol not in seen_symbols:
            seen_symbols.add(c.symbol)
            unique_candidates.append(c)
    assume(len(unique_candidates) >= 1)

    # 构建已有持仓（使用不与候选重叠的 symbol）
    existing_positions: dict[str, _BacktestPosition] = {}
    for i in range(existing_count):
        sym = f"99{i:04d}.SH"
        # 确保不与候选重叠
        if sym in seen_symbols:
            continue
        existing_positions[sym] = _BacktestPosition(
            symbol=sym,
            quantity=100,
            cost_price=Decimal("10.00"),
            buy_date=date(2024, 6, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("10.00"),
            sector="",
        )

    initial_position_count = len(existing_positions)
    assume(initial_position_count < max_holdings)

    # 为每个候选构建 K 线数据（非涨停开盘价）
    prev_close = Decimal("20.00")
    next_open = Decimal("20.50")  # 低于涨停价 22.00
    kline_entries = [(c.symbol, prev_close, next_open) for c in unique_candidates]
    kline_data = _build_multi_kline_data(kline_entries)

    state = _BacktestState(cash=cash, positions=existing_positions)
    config = _make_config(max_holdings=max_holdings)

    # 记录初始持仓 symbol（_execute_buys 会修改 state.positions）
    initial_symbols = set(existing_positions.keys())

    engine = BacktestEngine()
    records = engine._execute_buys(unique_candidates, _SIGNAL_DATE, kline_data, state, config)

    # 验证 1：持仓数量 ≤ max_holdings
    final_position_count = len(state.positions)
    assert final_position_count <= max_holdings, (
        f"持仓数量 {final_position_count} 超过 max_holdings {max_holdings}"
    )

    # 验证 2：无重复买入（买入记录中的 symbol 不在初始持仓中）
    bought_symbols = [r.symbol for r in records]
    for sym in bought_symbols:
        assert sym not in initial_symbols, (
            f"已持仓标的 {sym} 不应被重复买入"
        )

    # 验证 3：买入记录中无重复 symbol
    assert len(bought_symbols) == len(set(bought_symbols)), (
        f"买入记录中存在重复 symbol: {bought_symbols}"
    )


# ---------------------------------------------------------------------------
# 属性 22d：回测仓位限制不变量
# ---------------------------------------------------------------------------


@given(
    prev_close=_close_price,
    open_ratio=st.floats(min_value=0.92, max_value=1.08, allow_nan=False),
    cash=_cash,
    sector=_sectors,
    max_position_pct=st.floats(min_value=0.05, max_value=0.30, allow_nan=False),
    max_sector_pct=st.floats(min_value=0.10, max_value=0.50, allow_nan=False),
    existing_sector_count=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=100)
def test_position_and_sector_limits_respected(
    prev_close: Decimal,
    open_ratio: float,
    cash: Decimal,
    sector: str,
    max_position_pct: float,
    max_sector_pct: float,
    existing_sector_count: int,
) -> None:
    """
    **Validates: Requirements 12.13, 12.27**

    属性 22d：对任意买入记录，验证：
    1. 买入后单股仓位 ≤ max_position_pct × 总资产
    2. 板块仓位 ≤ max_sector_pct × 总资产（当 sector 非空时）
    """
    next_open = (prev_close * Decimal(str(open_ratio))).quantize(Decimal("0.01"))
    assume(next_open > Decimal("0"))

    # 涨停价
    limit_up = (prev_close * Decimal("1.10")).quantize(Decimal("0.01"))
    assume(next_open < limit_up)

    symbol = "600100.SH"
    candidate = ScreenItem(
        symbol=symbol,
        ref_buy_price=prev_close,
        trend_score=90.0,
        risk_level=RiskLevel.LOW,
        signals=[SignalDetail(category=SignalCategory.MA_TREND, label="多头排列")],
    )
    # 通过 setattr 设置 sector（ScreenItem 无 sector 字段，_execute_buys 用 getattr 获取）
    object.__setattr__(candidate, "sector", sector)

    # 构建同板块已有持仓
    existing_positions: dict[str, _BacktestPosition] = {}
    for i in range(existing_sector_count):
        sym = f"60{i:04d}.SH"
        existing_positions[sym] = _BacktestPosition(
            symbol=sym,
            quantity=500,
            cost_price=Decimal("15.00"),
            buy_date=date(2024, 6, 1),
            buy_trade_day_index=0,
            highest_close=Decimal("15.00"),
            sector=sector,
        )

    kline_data = _build_kline_data(symbol, prev_close, next_open)
    state = _BacktestState(cash=cash, positions=existing_positions)
    config = _make_config(
        max_holdings=10,
        max_position_pct=max_position_pct,
        max_sector_pct=max_sector_pct,
    )

    engine = BacktestEngine()
    records = engine._execute_buys([candidate], _SIGNAL_DATE, kline_data, state, config)

    if not records:
        return  # 无买入记录，无需验证

    rec = records[0]
    buy_amount = rec.price * rec.quantity

    # 买入后总资产 = 剩余现金 + 所有持仓市值
    total_equity = state.cash + sum(
        pos.cost_price * pos.quantity for pos in state.positions.values()
    )

    # 验证 1：单股仓位 ≤ max_position_pct × 总资产
    # _calculate_buy_amount 在买入前用 target_amount 限制，买入后的仓位应满足约束
    stock_value = rec.price * rec.quantity
    max_allowed_stock = total_equity * Decimal(str(max_position_pct))
    # 允许 1 手（100股 × 开盘价）的误差，因为向下取整到 100 股
    tolerance = next_open * 100
    assert stock_value <= max_allowed_stock + tolerance, (
        f"单股仓位 {stock_value} 超过上限 {max_allowed_stock} "
        f"(max_position_pct={max_position_pct}, total_equity={total_equity})"
    )

    # 验证 2：板块仓位检查（仅当 sector 非空时）
    if sector:
        sector_value = sum(
            pos.cost_price * pos.quantity
            for pos in state.positions.values()
            if pos.sector == sector
        )
        max_allowed_sector = total_equity * Decimal(str(max_sector_pct))
        # 板块仓位检查在买入前执行，如果买入成功说明检查通过
        # 买入前的板块仓位比例 < max_sector_pct（严格小于）
        pre_buy_sector_value = sector_value - stock_value
        pre_buy_equity = total_equity + buy_amount + engine._calc_buy_cost(
            rec.price, rec.quantity, config
        )
        if pre_buy_equity > 0:
            pre_buy_ratio = float(pre_buy_sector_value / pre_buy_equity)
            assert pre_buy_ratio < max_sector_pct, (
                f"买入前板块仓位比例 {pre_buy_ratio:.4f} >= max_sector_pct {max_sector_pct}，"
                f"不应执行买入"
            )
