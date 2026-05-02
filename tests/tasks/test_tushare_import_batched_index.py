"""
Tushare 指数分批导入测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.data_engine.tushare_registry import get_entry
from app.tasks import tushare_import


@pytest.mark.asyncio
async def test_batched_index_honors_requested_index_codes(monkeypatch):
    entry = get_entry("index_daily")
    assert entry is not None

    get_index_list = AsyncMock(return_value=["000001.SH", "399001.SZ", "399006.SZ"])
    update_progress = AsyncMock()
    check_stop_signal = AsyncMock(return_value=False)
    sleep = AsyncMock()
    call_api = AsyncMock(return_value=[])

    monkeypatch.setattr(tushare_import, "_get_index_list", get_index_list)
    monkeypatch.setattr(tushare_import, "_update_progress", update_progress)
    monkeypatch.setattr(tushare_import, "_check_stop_signal", check_stop_signal)
    monkeypatch.setattr(tushare_import.asyncio, "sleep", sleep)
    monkeypatch.setattr(tushare_import, "_call_api_with_retry", call_api)

    result = await tushare_import._process_batched_index(
        entry=entry,
        adapter=AsyncMock(),
        params={
            "start_date": "20260430",
            "end_date": "20260430",
            "index_codes": ["000001.SH", "399006.SZ"],
        },
        task_id="task-1",
        log_id=1,
        rate_delay=0,
    )

    assert result["status"] == "completed"
    assert result["batch_stats"]["total_indices"] == 2
    get_index_list.assert_not_awaited()
    assert call_api.await_count == 2
    first_params = call_api.await_args_list[0].args[2]
    assert first_params["ts_code"] == "000001.SH"
    assert "index_codes" not in first_params
