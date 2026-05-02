from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.services.data_engine.kline_normalizer import (
    derive_trade_date,
    normalize_kline_symbol,
    normalize_kline_time,
)


def test_normalize_daily_aware_utc_16_to_trade_day_midnight():
    ts = datetime(2026, 2, 26, 16, tzinfo=timezone.utc)

    assert derive_trade_date(ts, "1d").isoformat() == "2026-02-27"
    assert normalize_kline_time(ts, "1d") == datetime(2026, 2, 27, tzinfo=timezone.utc)


def test_explicit_trade_date_has_priority():
    ts = datetime(2026, 2, 26, 16, tzinfo=timezone.utc)

    assert normalize_kline_time(ts, "1d", source_trade_date="20260226") == datetime(
        2026, 2, 26, tzinfo=timezone.utc
    )


def test_minute_naive_time_is_shanghai_local_time():
    ts = normalize_kline_time("2026-02-27 09:30:00", "5m")

    assert ts == datetime(2026, 2, 27, 1, 30, tzinfo=timezone.utc)


def test_normalize_symbol_skips_invalid_code():
    assert normalize_kline_symbol("000001") == "000001.SZ"
    assert normalize_kline_symbol("000001.SZ") == "000001.SZ"
    assert normalize_kline_symbol("BAD") is None


@dataclass
class _Bar:
    time: datetime
    symbol: str = "000001.SZ"
    freq: str = "1d"
    open: Decimal | None = Decimal("1")
    high: Decimal | None = Decimal("1")
    low: Decimal | None = Decimal("1")
    close: Decimal | None = Decimal("1")
    volume: int | None = 1
    amount: Decimal | None = Decimal("1")
    turnover: Decimal | None = None
    vol_ratio: Decimal | None = None
    adj_type: int = 0
