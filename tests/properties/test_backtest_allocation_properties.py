"""
BacktestEngine 资金分配属性测试（Hypothesis）

属性 22c：回测资金分配模式正确性
属性 22e：回测买入数量为 100 股整数倍

**Validates: Requirements 12.11, 12.12, 12.14**
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    BacktestConfig,
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

_signal_detail = st.builds(
    SignalDetail,
    category=st.sampled_from(list(SignalCategory)),
    label=st.text(min_size=1, max_size=6),
    is_fake_breakout=st.just(False),
)

_screen_item = st.builds(
    ScreenItem,
    symbol=st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True),
    ref_buy_price=st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("200.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    trend_score=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    risk_level=st.sampled_from(list(RiskLevel)),
    signals=st.lists(_signal_detail, min_size=0, max_size=4),
    has_fake_breakout=st.just(False),
)

_open_price = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("200.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_position = st.builds(
    _BacktestPosition,
    symbol=st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True),
    quantity=st.integers(min_value=100, max_value=10000).map(lambda x: (x // 100) * 100),
    cost_price=st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("200.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    buy_date=st.just(date(2024, 1, 1)),
    buy_trade_day_index=st.just(0),
    highest_close=st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("200.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    sector=st.just(""),
    pending_sell=st.just(None),
)

# Cash: reasonable range for backtest
_cash = st.decimals(
    min_value=Decimal("10000.00"),
    max_value=Decimal("5000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_max_holdings = st.integers(min_value=2, max_value=20)


# ---------------------------------------------------------------------------
# Helper: build BacktestConfig with specific allocation_mode
# ---------------------------------------------------------------------------

def _make_config(allocation_mode: str, max_holdings: int, max_position_pct: float = 0.15) -> BacktestConfig:
    return BacktestConfig(
        strategy_config=StrategyConfig(),
        start_date=date(2023, 1, 1),
        end_date=date(2024, 1, 1),
        initial_capital=Decimal("1000000"),
        allocation_mode=allocation_mode,
        max_holdings=max_holdings,
        max_position_pct=max_position_pct,
    )


# ---------------------------------------------------------------------------
# 属性 22c：回测资金分配模式正确性
# ---------------------------------------------------------------------------


@given(
    candidate=_screen_item,
    cash=_cash,
    open_price=_open_price,
    max_holdings=_max_holdings,
    positions=st.lists(_position, min_size=0, max_size=8),
)
@settings(max_examples=100)
def test_equal_mode_target_amount(
    candidate: ScreenItem,
    cash: Decimal,
    open_price: Decimal,
    max_holdings: int,
    positions: list[_BacktestPosition],
) -> None:
    """
    **Validates: Requirements 12.11**

    属性 22c（equal 模式）：等权模式下，目标金额 = 可用资金 / (max_holdings - 持仓数)。
    验证 _calculate_buy_amount 返回的股数与独立计算的目标金额一致。
    """
    # Ensure unique position symbols and none collide with candidate
    seen: set[str] = {candidate.symbol}
    unique_positions: dict[str, _BacktestPosition] = {}
    for p in positions:
        if p.symbol not in seen:
            seen.add(p.symbol)
            unique_positions[p.symbol] = p

    current_count = len(unique_positions)
    assume(max_holdings > current_count)  # denominator > 0

    state = _BacktestState(cash=cash, positions=unique_positions)
    config = _make_config("equal", max_holdings)

    engine = BacktestEngine()
    result = engine._calculate_buy_amount(candidate, state, config, open_price)

    # Independently compute expected target_amount
    denominator = max_holdings - current_count
    target_amount = cash / Decimal(str(denominator))

    # Cap by max_position_pct
    total_equity = cash + sum(
        pos.cost_price * pos.quantity for pos in unique_positions.values()
    )
    max_amount = total_equity * Decimal(str(config.max_position_pct))
    target_amount = min(target_amount, max_amount)

    expected_shares = int(target_amount / open_price)
    expected_shares = (expected_shares // 100) * 100
    if expected_shares < 100:
        expected_shares = 0

    assert result == expected_shares, (
        f"equal 模式股数不匹配: got {result}, expected {expected_shares}, "
        f"cash={cash}, denominator={denominator}, open_price={open_price}"
    )


@given(
    candidate=_screen_item,
    cash=_cash,
    open_price=_open_price,
    max_holdings=_max_holdings,
    other_candidates=st.lists(_screen_item, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_score_weighted_mode_proportional(
    candidate: ScreenItem,
    cash: Decimal,
    open_price: Decimal,
    max_holdings: int,
    other_candidates: list[ScreenItem],
) -> None:
    """
    **Validates: Requirements 12.12**

    属性 22c（score_weighted 模式）：评分加权模式下，目标金额与评分占比成正比。
    验证 _calculate_buy_amount 返回的股数与独立计算的评分加权目标金额一致。
    """
    all_candidates = [candidate] + other_candidates
    total_score = sum(c.trend_score for c in all_candidates)
    assume(total_score > 0)
    assume(candidate.trend_score > 0)

    state = _BacktestState(cash=cash)
    config = _make_config("score_weighted", max_holdings)

    engine = BacktestEngine()
    result = engine._calculate_buy_amount(
        candidate, state, config, open_price, total_score,
    )

    # Independently compute expected target_amount
    ratio = Decimal(str(candidate.trend_score / total_score))
    target_amount = cash * ratio

    # Cap by max_position_pct
    total_equity = cash  # no positions
    max_amount = total_equity * Decimal(str(config.max_position_pct))
    target_amount = min(target_amount, max_amount)

    expected_shares = int(target_amount / open_price)
    expected_shares = (expected_shares // 100) * 100
    if expected_shares < 100:
        expected_shares = 0

    assert result == expected_shares, (
        f"score_weighted 模式股数不匹配: got {result}, expected {expected_shares}, "
        f"score={candidate.trend_score}, total_score={total_score}, "
        f"cash={cash}, open_price={open_price}"
    )


# ---------------------------------------------------------------------------
# 属性 22e：回测买入数量为 100 股整数倍
# ---------------------------------------------------------------------------


@given(
    candidate=_screen_item,
    cash=_cash,
    open_price=_open_price,
    max_holdings=_max_holdings,
    allocation_mode=st.sampled_from(["equal", "score_weighted"]),
    other_candidates=st.lists(_screen_item, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_buy_quantity_is_positive_multiple_of_100(
    candidate: ScreenItem,
    cash: Decimal,
    open_price: Decimal,
    max_holdings: int,
    allocation_mode: str,
    other_candidates: list[ScreenItem],
) -> None:
    """
    **Validates: Requirements 12.14**

    属性 22e：对任意买入交易记录，验证 quantity > 0 且 quantity % 100 == 0。
    当 _calculate_buy_amount 返回非零值时，结果必须是 100 的正整数倍。
    """
    all_candidates = [candidate] + other_candidates
    total_score = sum(c.trend_score for c in all_candidates) if allocation_mode == "score_weighted" else None

    state = _BacktestState(cash=cash)
    config = _make_config(allocation_mode, max_holdings)

    engine = BacktestEngine()
    result = engine._calculate_buy_amount(
        candidate, state, config, open_price, total_score,
    )

    # Result is either 0 (abandoned) or a positive multiple of 100
    assert result >= 0, f"买入数量不能为负: {result}"
    if result > 0:
        assert result % 100 == 0, (
            f"买入数量必须是 100 的整数倍: got {result}"
        )
        assert result >= 100, (
            f"非零买入数量必须 >= 100: got {result}"
        )
