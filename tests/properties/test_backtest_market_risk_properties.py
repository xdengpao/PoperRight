"""
BacktestEngine 大盘风控阈值联动属性测试（Hypothesis）

**Validates: Requirements 12.26**

属性 22i：回测大盘风控阈值联动
- 指数跌破 20 日均线 → "CAUTION"（阈值 80→90）
- 指数跌破 60 日均线 → "DANGER"（暂停买入）
- enable_market_risk=False（index_data=None）→ 始终 "NORMAL"
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import KlineBar
from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kline_bar(close: float, bar_date: date, symbol: str = "000001.SH") -> KlineBar:
    """构造一个最小化的 KlineBar，仅 close 和 time 有意义。"""
    d = Decimal(str(round(close, 4)))
    return KlineBar(
        time=datetime(bar_date.year, bar_date.month, bar_date.day),
        symbol=symbol,
        freq="1d",
        open=d,
        high=d,
        low=d,
        close=d,
        volume=100000,
        amount=Decimal("1000000"),
        turnover=Decimal("1.0"),
        vol_ratio=Decimal("1.0"),
    )


def _build_index_bars(
    closes: list[float],
    end_date: date,
    symbol: str = "000001.SH",
) -> list[KlineBar]:
    """从收盘价序列构造 KlineBar 列表，日期从 end_date 往前推。"""
    n = len(closes)
    bars: list[KlineBar] = []
    for i, c in enumerate(closes):
        bar_date = end_date - timedelta(days=n - 1 - i)
        bars.append(_make_kline_bar(c, bar_date, symbol))
    return bars


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 生成 60 个正浮点数作为历史收盘价（确保足够计算 MA60）
_price = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)

# 生成 60 个历史价格序列（前 59 个为历史，最后 1 个为当日收盘）
_price_sequence_60 = st.lists(_price, min_size=60, max_size=60)

# 生成 20~59 个价格序列（足够 MA20 但不够 MA60）
_price_sequence_20 = st.lists(_price, min_size=20, max_size=59)


# ---------------------------------------------------------------------------
# 属性 22i-1：指数跌破 MA20 → CAUTION 或 DANGER
# ---------------------------------------------------------------------------

@given(history=_price_sequence_20)
@settings(max_examples=100)
def test_below_ma20_returns_caution_or_danger(history: list[float]) -> None:
    """
    **Validates: Requirements 12.26**

    属性 22i（子属性 1）：对任意 20~59 个价格的指数序列，
    当最新收盘价低于 20 日均线时，_evaluate_market_risk 返回 "CAUTION" 或 "DANGER"。
    """
    # 计算 MA20 并确保最新收盘价低于它
    ma20 = sum(history[-20:]) / 20
    assume(history[-1] < ma20)

    trade_date = date(2024, 6, 15)
    bars = _build_index_bars(history, trade_date, "000001.SH")
    index_data = {"000001.SH": bars}

    engine = BacktestEngine()
    result = engine._evaluate_market_risk(trade_date, index_data)

    assert result in ("CAUTION", "DANGER"), (
        f"指数跌破 MA20 时应返回 CAUTION 或 DANGER，实际返回 {result!r}。"
        f" latest_close={history[-1]:.4f}, ma20={ma20:.4f}"
    )


# ---------------------------------------------------------------------------
# 属性 22i-2：指数跌破 MA60 → DANGER
# ---------------------------------------------------------------------------

@given(history=_price_sequence_60)
@settings(max_examples=100)
def test_below_ma60_returns_danger(history: list[float]) -> None:
    """
    **Validates: Requirements 12.26**

    属性 22i（子属性 2）：对任意 60 个价格的指数序列，
    当最新收盘价低于 60 日均线时，_evaluate_market_risk 返回 "DANGER"。
    """
    ma60 = sum(history[-60:]) / 60
    assume(history[-1] < ma60)

    trade_date = date(2024, 6, 15)
    bars = _build_index_bars(history, trade_date, "000001.SH")
    index_data = {"000001.SH": bars}

    engine = BacktestEngine()
    result = engine._evaluate_market_risk(trade_date, index_data)

    assert result == "DANGER", (
        f"指数跌破 MA60 时应返回 DANGER，实际返回 {result!r}。"
        f" latest_close={history[-1]:.4f}, ma60={ma60:.4f}"
    )


# ---------------------------------------------------------------------------
# 属性 22i-3：enable_market_risk=False（index_data=None）→ NORMAL
# ---------------------------------------------------------------------------

@given(history=_price_sequence_60)
@settings(max_examples=100)
def test_disabled_market_risk_returns_normal(history: list[float]) -> None:
    """
    **Validates: Requirements 12.26**

    属性 22i（子属性 3）：当 enable_market_risk=False 时（即 index_data 为 None），
    无论指数价格如何，_evaluate_market_risk 始终返回 "NORMAL"。
    """
    engine = BacktestEngine()
    trade_date = date(2024, 6, 15)

    # index_data=None 模拟 enable_market_risk=False 的调用路径
    result = engine._evaluate_market_risk(trade_date, None)
    assert result == "NORMAL", (
        f"enable_market_risk=False 时应始终返回 NORMAL，实际返回 {result!r}"
    )

    # 空字典同样应返回 NORMAL
    result_empty = engine._evaluate_market_risk(trade_date, {})
    assert result_empty == "NORMAL", (
        f"空 index_data 时应返回 NORMAL，实际返回 {result_empty!r}"
    )
