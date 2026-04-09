# Feature: minute-kline-chart, Property 5: KlineBar JSON 序列化往返一致性
"""
KlineBar JSON 序列化往返一致性属性测试（Hypothesis）

属性 5：KlineBar JSON 序列化往返一致性

**Validates: Requirements 6.2, 6.3**

对任意有效的 KlineBar 对象（包含 time、open、high、low、close、volume、amount、
turnover、vol_ratio 字段），将其序列化为 JSON dict 再反序列化后，应产生与原始数据
等价的对象。

序列化格式与 GET /api/v1/data/kline/{symbol} 端点返回的 bars 数组元素一致：
- time → ISO 8601 字符串
- open/high/low/close/amount/turnover/vol_ratio → str(Decimal)
- volume → int
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.models.kline import KlineBar


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 股票代码：6 位数字
_symbol_strategy = st.builds(
    lambda code: f"{code:06d}",
    code=st.integers(min_value=1, max_value=999999),
)

# K 线频率（分钟级 + 日级）
_freq_strategy = st.sampled_from(["1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"])

# 正数 Decimal 价格（A 股典型范围）
_positive_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 正整数成交量
_positive_volume = st.integers(min_value=0, max_value=10_000_000_000)

# 非负 Decimal（成交额）
_non_negative_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 换手率 0~100
_turnover_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 量比
_vol_ratio_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("50.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# 有效交易时间
_trade_datetime = st.datetimes(
    min_value=datetime(2010, 1, 1),
    max_value=datetime(2025, 12, 31, 23, 59, 59),
)

# 复权类型
_adj_type_strategy = st.sampled_from([0, 1, 2])

# 可选 Decimal（limit_up / limit_down）
_optional_decimal = st.one_of(st.none(), _positive_decimal)


# ---------------------------------------------------------------------------
# 组合策略：生成完整 KlineBar（确保 high >= low, open/close 在 [low, high] 内）
# ---------------------------------------------------------------------------


@st.composite
def _kline_bar_strategy(draw):
    """生成满足 high >= max(open, close) 且 low <= min(open, close) 的 KlineBar。"""
    low = draw(st.decimals(
        min_value=Decimal("0.01"), max_value=Decimal("5000.00"),
        places=2, allow_nan=False, allow_infinity=False,
    ))
    high = draw(st.decimals(
        min_value=low, max_value=max(low + Decimal("0.01"), Decimal("9999.99")),
        places=2, allow_nan=False, allow_infinity=False,
    ))
    open_ = draw(st.decimals(
        min_value=low, max_value=high,
        places=2, allow_nan=False, allow_infinity=False,
    ))
    close = draw(st.decimals(
        min_value=low, max_value=high,
        places=2, allow_nan=False, allow_infinity=False,
    ))

    return KlineBar(
        time=draw(_trade_datetime),
        symbol=draw(_symbol_strategy),
        freq=draw(_freq_strategy),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=draw(_positive_volume),
        amount=draw(_non_negative_decimal),
        turnover=draw(_turnover_decimal),
        vol_ratio=draw(_vol_ratio_decimal),
        limit_up=draw(_optional_decimal),
        limit_down=draw(_optional_decimal),
        adj_type=draw(_adj_type_strategy),
    )


# ---------------------------------------------------------------------------
# 序列化 / 反序列化辅助函数
# （与 get_kline 端点返回格式一致）
# ---------------------------------------------------------------------------


def serialize_bar(bar: KlineBar) -> dict:
    """将 KlineBar 序列化为 API 响应 dict 格式。

    与 app/api/v1/data.py get_kline 端点的序列化逻辑完全一致。
    """
    return {
        "time": bar.time.isoformat(),
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": bar.volume,
        "amount": str(bar.amount),
        "turnover": str(bar.turnover),
        "vol_ratio": str(bar.vol_ratio),
    }


def deserialize_bar(
    d: dict, *, symbol: str, freq: str, adj_type: int = 0,
) -> KlineBar:
    """从 API 响应 dict 反序列化为 KlineBar。"""
    return KlineBar(
        time=datetime.fromisoformat(d["time"]),
        symbol=symbol,
        freq=freq,
        open=Decimal(d["open"]),
        high=Decimal(d["high"]),
        low=Decimal(d["low"]),
        close=Decimal(d["close"]),
        volume=d["volume"],
        amount=Decimal(d["amount"]),
        turnover=Decimal(d["turnover"]),
        vol_ratio=Decimal(d["vol_ratio"]),
        adj_type=adj_type,
    )


# ---------------------------------------------------------------------------
# 自定义 JSON encoder 用于验证完整 JSON 往返
# ---------------------------------------------------------------------------


class _DecimalEncoder(json.JSONEncoder):
    """支持 Decimal 的 JSON 编码器。"""

    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


# ---------------------------------------------------------------------------
# Property 5: KlineBar JSON 序列化往返一致性
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(bar=_kline_bar_strategy())
def test_kline_bar_json_roundtrip(bar: KlineBar):
    """
    # Feature: minute-kline-chart, Property 5: KlineBar JSON 序列化往返一致性

    **Validates: Requirements 6.2, 6.3**

    对任意有效的 KlineBar，序列化为 API JSON dict 再反序列化后，
    核心字段（time、open、high、low、close、volume、amount、turnover、vol_ratio）
    应与原始数据等价。
    """
    serialized = serialize_bar(bar)

    # 验证序列化 dict 包含所有必需字段（需求 6.2）
    required_fields = {
        "time", "open", "high", "low", "close",
        "volume", "amount", "turnover", "vol_ratio",
    }
    assert set(serialized.keys()) == required_fields, (
        f"序列化 dict 字段不完整: 期望 {required_fields}, 实际 {set(serialized.keys())}"
    )

    # 验证 JSON 序列化/反序列化不丢失数据（完整 JSON 往返）
    json_str = json.dumps(serialized, cls=_DecimalEncoder)
    parsed = json.loads(json_str)
    assert parsed == serialized, "JSON string 往返不一致"

    # 反序列化回 KlineBar
    restored = deserialize_bar(
        serialized,
        symbol=bar.symbol,
        freq=bar.freq,
        adj_type=bar.adj_type,
    )

    # 验证往返一致性（需求 6.3）
    assert restored.time == bar.time, f"time 不一致: {restored.time} != {bar.time}"
    assert restored.symbol == bar.symbol
    assert restored.freq == bar.freq
    assert restored.open == bar.open, f"open 不一致: {restored.open} != {bar.open}"
    assert restored.high == bar.high, f"high 不一致: {restored.high} != {bar.high}"
    assert restored.low == bar.low, f"low 不一致: {restored.low} != {bar.low}"
    assert restored.close == bar.close, f"close 不一致: {restored.close} != {bar.close}"
    assert restored.volume == bar.volume, f"volume 不一致: {restored.volume} != {bar.volume}"
    assert restored.amount == bar.amount, f"amount 不一致: {restored.amount} != {bar.amount}"
    assert restored.turnover == bar.turnover, f"turnover 不一致: {restored.turnover} != {bar.turnover}"
    assert restored.vol_ratio == bar.vol_ratio, f"vol_ratio 不一致: {restored.vol_ratio} != {bar.vol_ratio}"
    assert restored.adj_type == bar.adj_type
