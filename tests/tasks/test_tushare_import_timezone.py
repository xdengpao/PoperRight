"""Tushare 时序写入时区与运行时频率测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.services.data_engine.tushare_registry import get_entry
from app.tasks import tushare_import


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt, params=None):
        self.executed.append(params)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class _FakeMappings:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def all(self) -> list[dict]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeQuerySession:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.executed: list[tuple[object, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt, params=None):
        self.executed.append((stmt, params))
        return _FakeResult(self.rows)


def test_parse_tushare_trade_date_utc_returns_utc_midnight():
    ts = tushare_import._parse_tushare_trade_date_utc("20260429")
    assert ts == datetime(2026, 4, 29, tzinfo=timezone.utc)
    assert tushare_import._parse_tushare_trade_date_utc("2026-04-29") == ts
    assert tushare_import._parse_tushare_trade_date_utc(date(2026, 4, 29)) == ts
    assert tushare_import._parse_tushare_trade_date_utc("bad") is None


def test_parse_tushare_datetime_utc_preserves_intraday_time():
    ts = tushare_import._parse_tushare_datetime_utc("2026-04-29 10:31:00")
    assert ts == datetime(2026, 4, 29, 10, 31, tzinfo=timezone.utc)

    aware = datetime(2026, 4, 29, 18, 31, tzinfo=timezone.utc)
    assert tushare_import._parse_tushare_datetime_utc(aware) == aware


def test_normalize_tushare_timeseries_time_uses_freq_semantics():
    daily = tushare_import._normalize_tushare_timeseries_time(
        {"trade_date": "20260429", "trade_time": "2026-04-29 10:31:00"},
        "1d",
    )
    assert daily == datetime(2026, 4, 29, tzinfo=timezone.utc)

    minute = tushare_import._normalize_tushare_timeseries_time(
        {"trade_date": "20260429", "trade_time": "2026-04-29 10:31:00"},
        "5m",
    )
    assert minute == datetime(2026, 4, 29, 10, 31, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_write_to_kline_uses_utc_time_and_runtime_freq():
    entry = get_entry("stk_mins")
    assert entry is not None
    fake = _FakeSession()

    with patch("app.core.database.AsyncSessionTS", return_value=fake):
        await tushare_import._write_to_timescaledb(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260429",
                    "trade_time": "2026-04-29 10:31:00",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                }
            ],
            entry,
            runtime_freq="5m",
        )

    batch = fake.executed[0]
    assert isinstance(batch, list)
    assert batch[0]["time"] == datetime(2026, 4, 29, 10, 31, tzinfo=timezone.utc)
    assert batch[0]["freq"] == "5m"
    assert fake.committed is True


@pytest.mark.asyncio
async def test_write_to_sector_kline_stores_naive_utc_for_db_column():
    entry = get_entry("ths_daily")
    assert entry is not None
    fake = _FakeSession()

    with patch("app.core.database.AsyncSessionTS", return_value=fake):
        await tushare_import._write_to_timescaledb(
            [
                {
                    "ts_code": "885001.TI",
                    "trade_date": "20260429",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                }
            ],
            entry,
        )

    batch = fake.executed[0]
    assert isinstance(batch, list)
    assert batch[0]["time"] == datetime(2026, 4, 29)
    assert batch[0]["data_source"] == "THS"


@pytest.mark.asyncio
async def test_write_to_sector_kline_accepts_mapped_sector_code():
    entry = get_entry("dc_daily")
    assert entry is not None
    fake = _FakeSession()

    with patch("app.core.database.AsyncSessionTS", return_value=fake):
        await tushare_import._write_to_timescaledb(
            [
                {
                    "sector_code": "BK0428.DC",
                    "trade_date": "20260430",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                }
            ],
            entry,
        )

    batch = fake.executed[0]
    assert isinstance(batch, list)
    assert batch[0]["sector_code"] == "BK0428.DC"
    assert batch[0]["time"] == datetime(2026, 4, 30)
    assert batch[0]["data_source"] == "DC"
    assert fake.committed is True


@pytest.mark.asyncio
async def test_write_adjustment_factor_keeps_date_type():
    entry = get_entry("adj_factor")
    assert entry is not None
    fake = _FakeSession()

    with patch("app.core.database.AsyncSessionTS", return_value=fake):
        await tushare_import._write_to_timescaledb(
            [{"ts_code": "000001.SZ", "trade_date": "20260429", "adj_factor": 1.23}],
            entry,
        )

    batch = fake.executed[0]
    assert isinstance(batch, list)
    assert batch[0]["trade_date"] == date(2026, 4, 29)
    assert not isinstance(batch[0]["trade_date"], datetime)


@pytest.mark.asyncio
async def test_sector_kline_postcheck_flags_import_log_mismatch(monkeypatch):
    fake = _FakeQuerySession([])

    async def fake_trade_dates(start_date: str, end_date: str):
        assert (start_date, end_date) == ("20260429", "20260430")
        return ["20260429", "20260430"], True

    monkeypatch.setattr(tushare_import, "_resolve_trade_dates", fake_trade_dates)
    monkeypatch.setattr(
        "app.core.database.AsyncSessionTS",
        lambda: fake,
    )

    result = await tushare_import._postcheck_sector_kline_import(
        "dc_daily",
        {"start_date": "20260429", "end_date": "20260430"},
        record_count=123,
    )

    assert result is not None
    assert result["ok"] is False
    assert result["reason"] == "import_log_mismatch"
    assert result["target_trade_date"] == "20260430"
    assert result["target_coverage_count"] == 0
    assert result["missing_dates"] == ["20260429", "20260430"]
    assert "invalid_code_or_time" in result["possible_causes"]


@pytest.mark.asyncio
async def test_sector_kline_postcheck_reports_partial_coverage(monkeypatch):
    fake = _FakeQuerySession([
        {"trade_date": "20260430", "coverage_count": 1013},
    ])

    async def fake_trade_dates(start_date: str, end_date: str):
        return ["20260429", "20260430"], True

    monkeypatch.setattr(tushare_import, "_resolve_trade_dates", fake_trade_dates)
    monkeypatch.setattr(
        "app.core.database.AsyncSessionTS",
        lambda: fake,
    )

    result = await tushare_import._postcheck_sector_kline_import(
        "dc_daily",
        {"start_date": "20260429", "end_date": "20260430"},
        record_count=123,
    )

    assert result is not None
    assert result["ok"] is False
    assert result["reason"] == "partial_coverage"
    assert result["target_coverage_count"] == 1013
    assert result["missing_dates"] == ["20260429"]


@pytest.mark.asyncio
async def test_sector_kline_postcheck_passes_when_all_trade_dates_covered(monkeypatch):
    fake = _FakeQuerySession([
        {"trade_date": "20260429", "coverage_count": 1000},
        {"trade_date": "20260430", "coverage_count": 1013},
    ])

    async def fake_trade_dates(start_date: str, end_date: str):
        return ["20260429", "20260430"], True

    monkeypatch.setattr(tushare_import, "_resolve_trade_dates", fake_trade_dates)
    monkeypatch.setattr(
        "app.core.database.AsyncSessionTS",
        lambda: fake,
    )

    result = await tushare_import._postcheck_sector_kline_import(
        "dc_daily",
        {"start_date": "20260429", "end_date": "20260430"},
        record_count=123,
    )

    assert result is not None
    assert result["ok"] is True
    assert result["reason"] == "covered"
    assert result["missing_dates"] == []
