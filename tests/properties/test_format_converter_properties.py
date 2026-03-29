"""
统一格式转换不变量属性测试（Hypothesis）

属性 52：统一格式转换不变量

**Validates: Requirements 1.11**

验证对任意有效的 Tushare 或 AkShare 原始数据，经 FormatConverter 转换后：
- KlineBar 所有必填字段不为 None
- high ≥ low
- open/high/low/close 均为正数
- 两个数据源转换后结构一致
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.schemas import KlineBar
from app.services.data_engine.format_converter import (
    AkShareFormatConverter,
    TushareFormatConverter,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 股票代码：6 位数字 + 交易所后缀
_symbol_strategy = st.builds(
    lambda code, suffix: f"{code:06d}.{suffix}",
    code=st.integers(min_value=1, max_value=999999),
    suffix=st.sampled_from(["SZ", "SH", "BJ"]),
)

# K 线频率
_freq_strategy = st.sampled_from(["D", "W", "M", "1m", "5m", "15m", "30m", "60m"])

# 正数价格（A 股典型范围）
_positive_price = st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False)

# 正整数成交量
_positive_volume = st.integers(min_value=1, max_value=10_000_000_000)

# 正数成交额（千元，Tushare 单位）
_positive_amount_k = st.floats(min_value=0.01, max_value=999_999_999.99, allow_nan=False, allow_infinity=False)

# 换手率 0~100
_turnover_rate = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# 量比
_vol_ratio = st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)

# 有效交易日期字符串 YYYYMMDD
_trade_date_str = st.dates(
    min_value=datetime(2010, 1, 1).date(),
    max_value=datetime(2025, 12, 31).date(),
).map(lambda d: d.strftime("%Y%m%d"))

# 有效交易日期字符串 YYYY-MM-DD（AkShare 格式）
_trade_date_str_ak = st.dates(
    min_value=datetime(2010, 1, 1).date(),
    max_value=datetime(2025, 12, 31).date(),
).map(lambda d: d.strftime("%Y-%m-%d"))


# OHLC 生成器：确保 high >= max(open, close) 且 low <= min(open, close)
@st.composite
def _ohlc_strategy(draw):
    """生成满足 high >= low 且 open/close 在 [low, high] 范围内的 OHLC 数据。"""
    low = draw(st.floats(min_value=0.01, max_value=5000.0, allow_nan=False, allow_infinity=False))
    high = draw(st.floats(min_value=low, max_value=max(low + 0.01, 9999.99), allow_nan=False, allow_infinity=False))
    open_ = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    close = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    return open_, high, low, close


# Tushare 原始数据生成器
@st.composite
def _tushare_raw_strategy(draw):
    """生成有效的 Tushare 原始数据 dict（fields + items 格式）。"""
    trade_date = draw(_trade_date_str)
    ohlc = draw(_ohlc_strategy())
    open_, high, low, close = ohlc
    vol = draw(_positive_volume)
    amount = draw(_positive_amount_k)
    turnover = draw(_turnover_rate)
    vol_ratio = draw(_vol_ratio)

    raw = {
        "fields": [
            "trade_date", "open", "high", "low", "close",
            "vol", "amount", "turnover_rate", "volume_ratio",
        ],
        "items": [[trade_date, open_, high, low, close, vol, amount, turnover, vol_ratio]],
    }
    return raw


# AkShare DataFrame 生成器
@st.composite
def _akshare_df_strategy(draw):
    """生成有效的 AkShare pandas DataFrame（中文列名）。"""
    trade_date = draw(_trade_date_str_ak)
    ohlc = draw(_ohlc_strategy())
    open_, high, low, close = ohlc
    vol = draw(_positive_volume)
    amount = draw(st.floats(min_value=0.01, max_value=999_999_999_999.99, allow_nan=False, allow_infinity=False))
    turnover = draw(_turnover_rate)

    df = pd.DataFrame([{
        "日期": trade_date,
        "开盘": open_,
        "最高": high,
        "最低": low,
        "收盘": close,
        "成交量": vol,
        "成交额": amount,
        "换手率": turnover,
    }])
    return df



# ---------------------------------------------------------------------------
# 属性 52a：Tushare 转换后 KlineBar 必填字段不为 None，high ≥ low，OHLC 正数
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    raw=_tushare_raw_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_tushare_kline_required_fields_not_none(
    raw: dict,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 Tushare 原始数据，经 TushareFormatConverter 转换后
    KlineBar 所有必填字段不为 None。
    """
    converter = TushareFormatConverter()
    bars = converter.to_kline_bars(raw, symbol, freq)

    assert len(bars) == 1
    bar = bars[0]

    # 必填字段不为 None
    assert bar.time is not None, "time should not be None"
    assert bar.symbol is not None, "symbol should not be None"
    assert bar.freq is not None, "freq should not be None"
    assert bar.open is not None, "open should not be None"
    assert bar.high is not None, "high should not be None"
    assert bar.low is not None, "low should not be None"
    assert bar.close is not None, "close should not be None"
    assert bar.volume is not None, "volume should not be None"
    assert bar.amount is not None, "amount should not be None"
    assert bar.turnover is not None, "turnover should not be None"
    assert bar.vol_ratio is not None, "vol_ratio should not be None"


@h_settings(max_examples=100)
@given(
    raw=_tushare_raw_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_tushare_kline_high_gte_low(
    raw: dict,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 Tushare 原始数据，经转换后 high ≥ low。
    """
    converter = TushareFormatConverter()
    bars = converter.to_kline_bars(raw, symbol, freq)
    bar = bars[0]

    assert bar.high >= bar.low, f"high ({bar.high}) should be >= low ({bar.low})"


@h_settings(max_examples=100)
@given(
    raw=_tushare_raw_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_tushare_kline_ohlc_positive(
    raw: dict,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 Tushare 原始数据，经转换后 open/high/low/close 均为正数。
    """
    converter = TushareFormatConverter()
    bars = converter.to_kline_bars(raw, symbol, freq)
    bar = bars[0]

    assert bar.open > 0, f"open ({bar.open}) should be > 0"
    assert bar.high > 0, f"high ({bar.high}) should be > 0"
    assert bar.low > 0, f"low ({bar.low}) should be > 0"
    assert bar.close > 0, f"close ({bar.close}) should be > 0"


# ---------------------------------------------------------------------------
# 属性 52b：AkShare 转换后 KlineBar 必填字段不为 None，high ≥ low，OHLC 正数
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    df=_akshare_df_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_akshare_kline_required_fields_not_none(
    df: pd.DataFrame,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 AkShare 原始数据，经 AkShareFormatConverter 转换后
    KlineBar 所有必填字段不为 None。
    """
    converter = AkShareFormatConverter()
    bars = converter.to_kline_bars(df, symbol, freq)

    assert len(bars) == 1
    bar = bars[0]

    assert bar.time is not None, "time should not be None"
    assert bar.symbol is not None, "symbol should not be None"
    assert bar.freq is not None, "freq should not be None"
    assert bar.open is not None, "open should not be None"
    assert bar.high is not None, "high should not be None"
    assert bar.low is not None, "low should not be None"
    assert bar.close is not None, "close should not be None"
    assert bar.volume is not None, "volume should not be None"
    assert bar.amount is not None, "amount should not be None"
    assert bar.turnover is not None, "turnover should not be None"
    assert bar.vol_ratio is not None, "vol_ratio should not be None"


@h_settings(max_examples=100)
@given(
    df=_akshare_df_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_akshare_kline_high_gte_low(
    df: pd.DataFrame,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 AkShare 原始数据，经转换后 high ≥ low。
    """
    converter = AkShareFormatConverter()
    bars = converter.to_kline_bars(df, symbol, freq)
    bar = bars[0]

    assert bar.high >= bar.low, f"high ({bar.high}) should be >= low ({bar.low})"


@h_settings(max_examples=100)
@given(
    df=_akshare_df_strategy(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_akshare_kline_ohlc_positive(
    df: pd.DataFrame,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对任意有效的 AkShare 原始数据，经转换后 open/high/low/close 均为正数。
    """
    converter = AkShareFormatConverter()
    bars = converter.to_kline_bars(df, symbol, freq)
    bar = bars[0]

    assert bar.open > 0, f"open ({bar.open}) should be > 0"
    assert bar.high > 0, f"high ({bar.high}) should be > 0"
    assert bar.low > 0, f"low ({bar.low}) should be > 0"
    assert bar.close > 0, f"close ({bar.close}) should be > 0"


# ---------------------------------------------------------------------------
# 属性 52c：两个数据源转换后结构一致
# ---------------------------------------------------------------------------


@st.composite
def _matched_tushare_akshare_data(draw):
    """生成等价的 Tushare 和 AkShare 原始数据，用于验证结构一致性。

    为避免浮点精度问题，amount 使用 Decimal 精确计算：
    Tushare amount 单位千元，AkShare 单位元，需要 amount_k * 1000 = amount_yuan。
    """
    trade_date_d = draw(st.dates(
        min_value=datetime(2010, 1, 1).date(),
        max_value=datetime(2025, 12, 31).date(),
    ))
    ohlc = draw(_ohlc_strategy())
    open_, high, low, close = ohlc
    vol = draw(_positive_volume)
    turnover = draw(_turnover_rate)

    # 使用 Decimal 精确计算 amount，避免 float * 1000 精度丢失
    amount_k = draw(_positive_amount_k)
    amount_k_dec = Decimal(str(amount_k))
    amount_yuan_dec = amount_k_dec * 1000
    # 将精确的元值转回 float 给 AkShare DataFrame
    amount_yuan = float(amount_yuan_dec)

    tushare_raw = {
        "fields": [
            "trade_date", "open", "high", "low", "close",
            "vol", "amount", "turnover_rate",
        ],
        "items": [[
            trade_date_d.strftime("%Y%m%d"),
            open_, high, low, close, vol, amount_k, turnover,
        ]],
    }

    akshare_df = pd.DataFrame([{
        "日期": trade_date_d.strftime("%Y-%m-%d"),
        "开盘": open_,
        "最高": high,
        "最低": low,
        "收盘": close,
        "成交量": vol,
        "成交额": amount_yuan,
        "换手率": turnover,
    }])

    return tushare_raw, akshare_df


@h_settings(max_examples=100)
@given(
    data=_matched_tushare_akshare_data(),
    symbol=_symbol_strategy,
    freq=_freq_strategy,
)
def test_both_converters_produce_consistent_structure(
    data: tuple,
    symbol: str,
    freq: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 52: 统一格式转换不变量

    **Validates: Requirements 1.11**

    对等价的 Tushare 和 AkShare 原始数据，两个转换器输出的 KlineBar
    在核心字段上结构一致：相同的字段名、数据类型、值（amount 经单位转换后一致）。
    """
    tushare_raw, akshare_df = data

    ts_converter = TushareFormatConverter()
    ak_converter = AkShareFormatConverter()

    ts_bars = ts_converter.to_kline_bars(tushare_raw, symbol, freq)
    ak_bars = ak_converter.to_kline_bars(akshare_df, symbol, freq)

    assert len(ts_bars) == 1, "Tushare should produce exactly 1 bar"
    assert len(ak_bars) == 1, "AkShare should produce exactly 1 bar"

    ts_bar = ts_bars[0]
    ak_bar = ak_bars[0]

    # 两者都是 KlineBar 实例
    assert isinstance(ts_bar, KlineBar)
    assert isinstance(ak_bar, KlineBar)

    # 核心字段值一致
    assert ts_bar.time == ak_bar.time, f"time mismatch: {ts_bar.time} vs {ak_bar.time}"
    assert ts_bar.symbol == ak_bar.symbol
    assert ts_bar.freq == ak_bar.freq
    assert ts_bar.open == ak_bar.open, f"open mismatch: {ts_bar.open} vs {ak_bar.open}"
    assert ts_bar.high == ak_bar.high, f"high mismatch: {ts_bar.high} vs {ak_bar.high}"
    assert ts_bar.low == ak_bar.low, f"low mismatch: {ts_bar.low} vs {ak_bar.low}"
    assert ts_bar.close == ak_bar.close, f"close mismatch: {ts_bar.close} vs {ak_bar.close}"
    assert ts_bar.volume == ak_bar.volume, f"volume mismatch: {ts_bar.volume} vs {ak_bar.volume}"
    assert ts_bar.turnover == ak_bar.turnover, f"turnover mismatch: {ts_bar.turnover} vs {ak_bar.turnover}"

    # amount: Tushare 千元 * 1000 应约等于 AkShare 元
    # 由于 float → Decimal(str(...)) 转换路径不同，允许微小精度差异
    amount_diff = abs(ts_bar.amount - ak_bar.amount)
    assert amount_diff < Decimal("0.01"), (
        f"amount mismatch beyond tolerance: {ts_bar.amount} vs {ak_bar.amount} (diff={amount_diff})"
    )

    # 数据类型一致性
    for field_name in ("open", "high", "low", "close", "amount", "turnover", "vol_ratio"):
        ts_type = type(getattr(ts_bar, field_name))
        ak_type = type(getattr(ak_bar, field_name))
        assert ts_type is ak_type, (
            f"Type mismatch for {field_name}: Tushare={ts_type.__name__}, AkShare={ak_type.__name__}"
        )
        assert ts_type is Decimal, f"{field_name} should be Decimal, got {ts_type.__name__}"

    assert type(ts_bar.volume) is int
    assert type(ak_bar.volume) is int
    assert type(ts_bar.time) is datetime
    assert type(ak_bar.time) is datetime

    # 结构字段一致
    assert ts_bar.limit_up == ak_bar.limit_up
    assert ts_bar.limit_down == ak_bar.limit_down
    assert ts_bar.adj_type == ak_bar.adj_type
