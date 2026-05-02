"""Tushare 按交易日导入的交易日解析测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks import tushare_import


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _SessionContext:
    def __init__(self, values):
        self.session = MagicMock()
        self.session.execute = AsyncMock(return_value=_ScalarResult(values))

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_resolve_trade_dates_uses_calendar_and_formats_dates(monkeypatch):
    monkeypatch.setattr(
        "app.core.database.AsyncSessionPG",
        lambda: _SessionContext([date(2026, 4, 27), date(2026, 4, 28)]),
    )

    dates, used_calendar = await tushare_import._resolve_trade_dates(
        "20260426", "20260429"
    )

    assert used_calendar is True
    assert dates == ["20260427", "20260428"]


@pytest.mark.asyncio
async def test_resolve_trade_dates_falls_back_to_natural_days(monkeypatch, caplog):
    monkeypatch.setattr("app.core.database.AsyncSessionPG", lambda: _SessionContext([]))

    dates, used_calendar = await tushare_import._resolve_trade_dates(
        "20260427", "20260429"
    )

    assert used_calendar is False
    assert dates == ["20260427", "20260428", "20260429"]
    assert "交易日历缺失" in caplog.text
