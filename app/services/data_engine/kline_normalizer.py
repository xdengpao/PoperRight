"""K 线时间、交易日和代码归一化工具。

统一处理日/周/月 K 线的交易日语义，避免 UTC 零点与北京时间零点
在 TimescaleDB 中形成业务重复记录。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from app.core.symbol_utils import to_standard

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_DATE_FREQS = {"1d", "1w", "1M", "d", "w", "m", "daily", "weekly", "monthly"}

T = TypeVar("T")


def is_date_freq(freq: str | None) -> bool:
    """判断频率是否按交易日/周期日期归一化。"""
    if freq is None:
        return False
    return str(freq).strip() in _DATE_FREQS


def parse_trade_date(value: date | datetime | str | None) -> date | None:
    """解析常见交易日期格式。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(_SHANGHAI_TZ).date()
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("/", "-")
    try:
        if len(normalized) >= 10 and "-" in normalized:
            return date.fromisoformat(normalized[:10])
        if len(raw) >= 8 and raw[:8].isdigit():
            part = raw[:8]
            return date(int(part[:4]), int(part[4:6]), int(part[6:8]))
    except ValueError:
        return None
    return None


def derive_trade_date(
    value: date | datetime | str,
    freq: str,
    *,
    source_trade_date: date | datetime | str | None = None,
) -> date:
    """从 K 线时间或显式交易日推导业务交易日。"""
    explicit_trade_date = parse_trade_date(source_trade_date)
    if explicit_trade_date is not None:
        return explicit_trade_date

    parsed = parse_trade_date(value)
    if parsed is not None and not isinstance(value, datetime):
        return parsed

    if isinstance(value, datetime):
        if is_date_freq(freq):
            if value.tzinfo is not None:
                return value.astimezone(_SHANGHAI_TZ).date()
            return value.date()
        if value.tzinfo is not None:
            return value.astimezone(_SHANGHAI_TZ).date()
        return value.date()

    if parsed is not None:
        return parsed
    raise ValueError(f"无法推导 K 线交易日: value={value!r}, freq={freq!r}")


def _parse_datetime(value: date | datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    raw = str(value).strip().replace("/", "-")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
    )
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    parsed_date = parse_trade_date(value)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time.min)
    raise ValueError(f"无法解析 K 线时间: {value!r}")


def normalize_kline_time(
    value: date | datetime | str,
    freq: str,
    *,
    source_trade_date: date | datetime | str | None = None,
) -> datetime:
    """归一化 K 线入库时间。

    日/周/月使用交易日 UTC 零点；分钟级保留真实时间，naive 时间按
    Asia/Shanghai 本地交易时间理解后转换为 UTC。
    """
    if is_date_freq(freq):
        trade_day = derive_trade_date(value, freq, source_trade_date=source_trade_date)
        return datetime.combine(trade_day, time.min, tzinfo=timezone.utc)

    parsed = _parse_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_SHANGHAI_TZ)
    return parsed.astimezone(timezone.utc)


def normalize_kline_symbol(symbol: str) -> str | None:
    """标准化股票/指数代码，无法标准化时返回 None。"""
    try:
        return to_standard(str(symbol))
    except ValueError:
        return None


def bar_trade_date(bar: Any) -> date:
    """从 KlineBar-like 对象推导交易日。"""
    return derive_trade_date(bar.time, getattr(bar, "freq", "1d"))


def dedupe_bars_by_trade_date(bars: Sequence[T]) -> list[T]:
    """按交易日去重，保留 canonical K 线。"""
    grouped: dict[tuple[str, str, int, date], list[T]] = {}
    for bar in bars:
        trade_day = bar_trade_date(bar)
        key = (
            getattr(bar, "symbol", ""),
            getattr(bar, "freq", ""),
            int(getattr(bar, "adj_type", 0) or 0),
            trade_day,
        )
        grouped.setdefault(key, []).append(bar)
    return [choose_canonical_kline(group) for group in grouped.values()]


def choose_canonical_kline(rows: Sequence[T]) -> T:
    """从同一业务键重复 K 线中选择保留行。"""
    if not rows:
        raise ValueError("rows 不能为空")

    def score(row: T) -> tuple[int, int, datetime]:
        row_time = getattr(row, "time")
        canonical = 1 if _is_utc_midnight(row_time) else 0
        completeness = _field_completeness(row)
        comparable_time = row_time
        if isinstance(comparable_time, datetime) and comparable_time.tzinfo is None:
            comparable_time = comparable_time.replace(tzinfo=timezone.utc)
        return (canonical, completeness, comparable_time)

    return max(rows, key=score)


def _is_utc_midnight(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0


def _field_completeness(row: Any) -> int:
    fields = (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover",
        "vol_ratio",
        "limit_up",
        "limit_down",
    )
    total = 0
    for field in fields:
        value = row.get(field) if isinstance(row, Mapping) else getattr(row, field, None)
        if value is not None and value != "" and value != Decimal("0"):
            total += 1
    return total
