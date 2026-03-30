"""
Bug Condition 探索性测试：_build_factor_dict() 派生因子值缺失

**Validates: Requirements 1.1, 1.3, 1.5, 1.7, 2.1, 2.3, 2.7, 2.11**

Property 1: Bug Condition - 派生因子值正确计算并填充

对任意包含足够 K 线数据的股票（len(bars) >= 26，满足 MACD slow period），
修复后的 _build_factor_dict() 应调用各模块计算函数，stock_data 中应包含：
  - ma_trend (float) — 来自 score_ma_trend()
  - macd (bool) — 来自 detect_macd_signal()
  - boll (bool) — 来自 detect_boll_signal()
  - rsi (bool) — 来自 detect_rsi_signal()
  - breakout (dict | None) — 来自 breakout 检测函数
  - ma_support — 来自 detect_ma_support()

此测试编码了期望行为。在未修复代码上运行时应失败（确认缺陷存在）。
修复后运行应通过（确认修复正确性）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.kline import KlineBar
from app.models.stock import StockInfo
from app.services.screener.screen_data_provider import ScreenDataProvider


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 正浮点价格（合理 A 股价格范围）
_price = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("500.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_volume = st.integers(min_value=10000, max_value=100_000_000)

_turnover = st.decimals(
    min_value=Decimal("0.10"),
    max_value=Decimal("30.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_vol_ratio = st.decimals(
    min_value=Decimal("0.10"),
    max_value=Decimal("10.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_amount = st.decimals(
    min_value=Decimal("100000.00"),
    max_value=Decimal("9999999999.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def kline_bar_strategy(draw, index: int, symbol: str = "600000.SH"):
    """Generate a single KlineBar at a given time offset."""
    base_time = datetime(2024, 1, 1)
    bar_time = base_time + timedelta(days=index)

    open_price = draw(_price)
    close_price = draw(_price)
    high_price = max(open_price, close_price) + draw(
        st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("5.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    low_price = min(open_price, close_price) - draw(
        st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("3.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    # Ensure low > 0
    if low_price <= 0:
        low_price = Decimal("0.01")

    return KlineBar(
        time=bar_time,
        symbol=symbol,
        freq="1d",
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=draw(_volume),
        amount=draw(_amount),
        turnover=draw(_turnover),
        vol_ratio=draw(_vol_ratio),
    )


@st.composite
def stock_and_bars_strategy(draw):
    """
    Generate a StockInfo + list of KlineBar with len(bars) >= 26.

    The minimum of 26 bars satisfies the MACD slow period requirement.
    """
    num_bars = draw(st.integers(min_value=26, max_value=60))
    symbol = "600000.SH"

    bars = []
    for i in range(num_bars):
        bar = draw(kline_bar_strategy(index=i, symbol=symbol))
        bars.append(bar)

    # Create a minimal StockInfo (ORM model) — set required fields only
    stock = StockInfo()
    stock.symbol = symbol
    stock.name = "测试股票"
    stock.market = "SH"
    stock.board = "主板"
    stock.list_date = None
    stock.is_st = False
    stock.is_delisted = False
    stock.pledge_ratio = None
    stock.pe_ttm = draw(st.one_of(
        st.none(),
        st.decimals(min_value=Decimal("1.00"), max_value=Decimal("200.00"), places=2,
                     allow_nan=False, allow_infinity=False),
    ))
    stock.pb = draw(st.one_of(
        st.none(),
        st.decimals(min_value=Decimal("0.50"), max_value=Decimal("50.00"), places=2,
                     allow_nan=False, allow_infinity=False),
    ))
    stock.roe = draw(st.one_of(
        st.none(),
        st.decimals(min_value=Decimal("-0.50"), max_value=Decimal("0.50"), places=4,
                     allow_nan=False, allow_infinity=False),
    ))
    stock.market_cap = draw(st.one_of(
        st.none(),
        st.decimals(min_value=Decimal("100000.00"), max_value=Decimal("99999999999.00"),
                     places=2, allow_nan=False, allow_infinity=False),
    ))
    stock.updated_at = None

    return stock, bars


# ---------------------------------------------------------------------------
# Bug Condition 探索性测试
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=stock_and_bars_strategy())
def test_build_factor_dict_contains_derived_factor_keys(data):
    """
    Property 1: Bug Condition - 派生因子值正确计算并填充

    **Validates: Requirements 1.1, 1.3, 1.5, 1.7, 2.1, 2.3, 2.7, 2.11**

    For any StockInfo + KlineBar list with len(bars) >= 26 (satisfying MACD
    slow period), _build_factor_dict() should return a factor dict containing
    derived factor keys from all screening modules:

    - "ma_trend": float (from score_ma_trend())
    - "macd": bool (from detect_macd_signal())
    - "boll": bool (from detect_boll_signal())
    - "rsi": bool (from detect_rsi_signal())
    - "breakout": dict or None (from breakout detection)
    - "ma_support": from detect_ma_support()

    On UNFIXED code this test is EXPECTED TO FAIL — the failure confirms
    the bug exists (_build_factor_dict never calls screening module functions).
    """
    stock, bars = data

    factor_dict = ScreenDataProvider._build_factor_dict(stock, bars)

    # --- Assert derived factor keys exist with correct types ---

    # ma_trend: should be a float trend score from score_ma_trend()
    assert "ma_trend" in factor_dict, (
        f"factor_dict 缺少 'ma_trend' 键。实际键: {sorted(factor_dict.keys())}"
    )
    assert isinstance(factor_dict["ma_trend"], (int, float)), (
        f"factor_dict['ma_trend'] 应为 float 类型，实际类型: {type(factor_dict['ma_trend'])}"
    )

    # macd: should be a bool from detect_macd_signal()
    assert "macd" in factor_dict, (
        f"factor_dict 缺少 'macd' 键。实际键: {sorted(factor_dict.keys())}"
    )
    assert isinstance(factor_dict["macd"], bool), (
        f"factor_dict['macd'] 应为 bool 类型，实际类型: {type(factor_dict['macd'])}"
    )

    # boll: should be a bool from detect_boll_signal()
    assert "boll" in factor_dict, (
        f"factor_dict 缺少 'boll' 键。实际键: {sorted(factor_dict.keys())}"
    )
    assert isinstance(factor_dict["boll"], bool), (
        f"factor_dict['boll'] 应为 bool 类型，实际类型: {type(factor_dict['boll'])}"
    )

    # rsi: should be a bool from detect_rsi_signal()
    assert "rsi" in factor_dict, (
        f"factor_dict 缺少 'rsi' 键。实际键: {sorted(factor_dict.keys())}"
    )
    assert isinstance(factor_dict["rsi"], bool), (
        f"factor_dict['rsi'] 应为 bool 类型，实际类型: {type(factor_dict['rsi'])}"
    )

    # breakout: should be dict or None from breakout detection
    assert "breakout" in factor_dict, (
        f"factor_dict 缺少 'breakout' 键。实际键: {sorted(factor_dict.keys())}"
    )
    assert factor_dict["breakout"] is None or isinstance(factor_dict["breakout"], dict), (
        f"factor_dict['breakout'] 应为 dict 或 None，实际类型: {type(factor_dict['breakout'])}"
    )

    # ma_support: from detect_ma_support()
    assert "ma_support" in factor_dict, (
        f"factor_dict 缺少 'ma_support' 键。实际键: {sorted(factor_dict.keys())}"
    )
