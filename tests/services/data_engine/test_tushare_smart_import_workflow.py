"""
智能选股 Tushare 一键导入工作流服务测试
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.data_engine.tushare_smart_import_workflow import (
    CORE_INDEX_CODES,
    SECTOR_DAILY_SOURCE_BY_API,
    TushareSmartImportWorkflowService,
)
from app.services.data_engine.tushare_registry import get_entry


def _api_names(definition: dict) -> list[str]:
    return [
        step["api_name"]
        for stage in definition["stages"]
        for step in stage["steps"]
    ]


def test_default_definition_contains_smart_screening_dependencies():
    service = TushareSmartImportWorkflowService()

    definition = service.get_definition()
    names = _api_names(definition)

    for api_name in [
        "stock_basic",
        "trade_cal",
        "daily",
        "adj_factor",
        "daily_basic",
        "stk_factor_pro",
        "moneyflow_dc",
        "dc_index",
        "dc_member",
        "dc_daily",
        "index_daily",
        "index_dailybasic",
        "idx_factor_pro",
        "cyq_perf",
        "margin_detail",
        "limit_list_d",
        "limit_step",
        "top_list",
    ]:
        assert api_name in names


def test_daily_fast_definition_uses_minimal_daily_dependencies():
    service = TushareSmartImportWorkflowService()

    definition = service.get_definition(mode="daily_fast")
    names = _api_names(definition)

    for api_name in [
        "daily",
        "adj_factor",
        "daily_basic",
        "stk_factor_pro",
        "moneyflow_dc",
        "dc_daily",
        "index_daily",
        "index_dailybasic",
        "idx_factor_pro",
    ]:
        assert api_name in names

    for skipped_api in ["stock_basic", "trade_cal", "dc_member", "cyq_perf", "margin_detail", "top_list"]:
        assert skipped_api not in names

    plan = definition["plan"]
    assert plan["mode"] == "daily_fast"
    assert any(item["api_name"] == "stock_basic" for item in plan["skip_steps"])


def test_daily_fast_core_index_params_are_minimized():
    service = TushareSmartImportWorkflowService()

    plan = service.get_plan(
        mode="daily_fast",
        date_range={"start_date": "20260430", "end_date": "20260430"},
    )
    index_steps = {
        item["api_name"]: item
        for item in plan["execute_steps"]
        if item["api_name"] in {"index_daily", "index_dailybasic", "idx_factor_pro"}
    }

    assert set(index_steps) == {"index_daily", "index_dailybasic", "idx_factor_pro"}
    assert index_steps["index_daily"]["params"]["index_codes"] == CORE_INDEX_CODES
    assert index_steps["index_dailybasic"]["params"]["index_codes"] == CORE_INDEX_CODES
    assert index_steps["idx_factor_pro"]["params"]["index_codes"] == CORE_INDEX_CODES


def test_daily_fast_includes_selected_sector_market_apis_without_members():
    service = TushareSmartImportWorkflowService()

    definition = service.get_definition(
        mode="daily_fast",
        options={
            "include_ths_sector": True,
            "include_tdx_sector": True,
            "include_ti_sector": True,
            "include_ci_sector": True,
        },
    )
    names = _api_names(definition)

    for api_name in ["ths_daily", "tdx_daily", "sw_daily", "ci_daily"]:
        assert api_name in names
    for member_api in ["ths_member", "tdx_member", "index_member_all", "ci_index_member"]:
        assert member_api not in names


def test_gap_repair_empty_repair_plan_does_not_fallback_to_daily_fast():
    service = TushareSmartImportWorkflowService()

    definition = service._build_definition("gap_repair", {"repair_plan": {"missing_steps": []}})

    assert sum(len(stage.steps) for stage in definition.stages) == 0


def test_legacy_modes_map_to_full_initialize():
    service = TushareSmartImportWorkflowService()

    assert service.get_plan(mode="incremental")["mode"] == "full_initialize"
    assert service.get_plan(mode="initialize")["mode"] == "full_initialize"


def test_optional_sector_sources_are_included_when_enabled():
    service = TushareSmartImportWorkflowService()

    definition = service.get_definition(
        options={
            "include_ths_sector": True,
            "include_tdx_sector": True,
            "include_ti_sector": True,
            "include_ci_sector": True,
        },
    )
    names = _api_names(definition)

    for api_name in [
        "ths_index",
        "ths_member",
        "ths_daily",
        "tdx_index",
        "tdx_member",
        "tdx_daily",
        "index_classify",
        "index_member_all",
        "sw_daily",
        "ci_index_member",
        "ci_daily",
    ]:
        assert api_name in names


def test_date_range_is_applied_only_to_date_range_steps():
    service = TushareSmartImportWorkflowService()
    date_range = {"start_date": "20260430", "end_date": "20260430"}

    daily_entry = get_entry("daily")
    stock_basic_entry = get_entry("stock_basic")
    assert daily_entry is not None
    assert stock_basic_entry is not None

    daily_params = service._build_step_params(daily_entry, {}, date_range)
    stock_basic_params = service._build_step_params(stock_basic_entry, {}, date_range)

    assert daily_params["start_date"] == "20260430"
    assert daily_params["end_date"] == "20260430"
    assert "start_date" not in stock_basic_params
    assert "end_date" not in stock_basic_params


def test_daily_basic_updates_current_snapshot():
    service = TushareSmartImportWorkflowService()
    entry = get_entry("daily_basic")
    assert entry is not None

    params = service._build_step_params(
        entry,
        {},
        {"start_date": "20260430", "end_date": "20260430"},
    )

    assert params["update_current_snapshot"] is True


def test_build_step_params_preserves_plan_date_override():
    service = TushareSmartImportWorkflowService()
    entry = get_entry("adj_factor")
    assert entry is not None

    params = service._build_step_params(
        entry,
        {"start_date": "20260429", "end_date": "20260430"},
        {"start_date": "20260410", "end_date": "20260430"},
    )

    assert params["start_date"] == "20260429"
    assert params["end_date"] == "20260430"


def test_freshness_date_expr_supports_varchar_trade_date():
    expr = TushareSmartImportWorkflowService._freshness_date_expr("trade_date")

    assert "trade_date::text" in expr
    assert "to_char(trade_date::date" in expr


def test_token_check_allows_default_token_fallback(monkeypatch):
    service = TushareSmartImportWorkflowService()
    definition = service._build_definition("incremental", {})

    monkeypatch.setattr(settings, "tushare_token_basic", "")
    monkeypatch.setattr(settings, "tushare_token_advanced", "")
    monkeypatch.setattr(settings, "tushare_token_premium", "")
    monkeypatch.setattr(settings, "tushare_token_special", "")
    monkeypatch.setattr(settings, "tushare_api_token", "fallback-token")

    assert service._missing_token_tiers(definition) == []


def test_strategy_dependency_summary_marks_pe_ttm_compatibility():
    service = TushareSmartImportWorkflowService()

    summary = service.derive_strategy_dependency_summary()

    assert "pe_ttm" in summary["used_factors"]
    assert summary["compatibility_warnings"]


@pytest.mark.asyncio
async def test_merge_child_progress_from_redis(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_cache_get(key: str):
        if key == "tushare:import:child-1":
            return json.dumps({
                "total": 100,
                "completed": 42,
                "failed": 1,
                "status": "running",
                "current_item": "600000.SH",
                "batch_mode": "by_code",
                "updated_at": "2026-04-30T18:01:00",
            })
        return None

    monkeypatch.setattr(
        "app.services.data_engine.tushare_smart_import_workflow.cache_get",
        fake_cache_get,
    )

    state = await service._merge_child_progress({
        "child_tasks": [
            {"task_id": "child-1", "api_name": "daily", "status": "running", "record_count": 0},
        ],
    })

    progress = state["child_tasks"][0]["progress"]
    assert progress["completed"] == 42
    assert progress["total"] == 100
    assert progress["current_item"] == "600000.SH"


@pytest.mark.asyncio
async def test_daily_fast_plan_skips_covered_and_shrinks_gap(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_freshness(target_date: str):
        assert target_date == "20260430"
        return {
            "daily": {"latest_date": "20260430", "import_record_count": 5200, "coverage_count": None, "covered": True, "source": "import_log"},
            "adj_factor": {"latest_date": "20260428", "coverage_count": 5100, "covered": False},
            "daily_basic": {"latest_date": None, "coverage_count": 0, "covered": False},
            "stk_factor_pro": {"latest_date": "20260429", "coverage_count": 5000, "covered": False},
            "moneyflow_dc": {"latest_date": "20260430", "import_record_count": 5200, "coverage_count": None, "covered": True, "source": "import_log"},
            "dc_daily": {"latest_date": "20260430", "import_record_count": 400, "coverage_count": None, "covered": True, "source": "import_log"},
            "index_daily": {"latest_date": "20260430", "import_record_count": 6, "coverage_count": None, "covered": True, "source": "import_log"},
            "index_dailybasic": {"latest_date": "20260429", "coverage_count": 6, "covered": False},
            "idx_factor_pro": {"latest_date": "20260430", "coverage_count": 6, "covered": True},
        }

    monkeypatch.setattr(service, "_check_daily_fast_freshness", fake_freshness)
    monkeypatch.setattr(
        service,
        "_resolve_daily_fast_target_range",
        AsyncMock(return_value=({"start_date": "20260410", "end_date": "20260430"}, None)),
    )

    plan = await service.get_plan_async(
        mode="daily_fast",
        date_range={"start_date": "20260410", "end_date": "20260430"},
    )
    execute_names = [step["api_name"] for step in plan["execute_steps"]]
    skip_names = [step["api_name"] for step in plan["skip_steps"]]

    assert "daily" not in execute_names
    assert "daily" in skip_names
    assert "moneyflow_dc" in skip_names
    adj_factor = next(step for step in plan["execute_steps"] if step["api_name"] == "adj_factor")
    assert adj_factor["params"]["start_date"] == "20260429"
    assert adj_factor["params"]["end_date"] == "20260430"
    assert any(action["mode"] == "gap_repair" and action["enabled"] for action in plan["next_actions"])


@pytest.mark.asyncio
async def test_daily_fast_plan_does_not_skip_sector_api_when_table_uncovered(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_freshness(target_date: str):
        return {
            api_name: {"latest_date": "20260430", "import_record_count": 1, "covered": True, "source": "import_log"}
            for api_name in [
                "daily",
                "adj_factor",
                "daily_basic",
                "stk_factor_pro",
                "moneyflow_dc",
                "index_daily",
                "index_dailybasic",
                "idx_factor_pro",
            ]
        } | {
            "dc_daily": {
                "latest_date": "20260424",
                "coverage_count": 0,
                "covered": False,
                "source": "sector_kline",
            },
        }

    monkeypatch.setattr(service, "_check_daily_fast_freshness", fake_freshness)
    monkeypatch.setattr(
        service,
        "_resolve_daily_fast_target_range",
        AsyncMock(return_value=({"start_date": "20260410", "end_date": "20260430"}, None)),
    )

    plan = await service.get_plan_async(
        mode="daily_fast",
        date_range={"start_date": "20260410", "end_date": "20260430"},
    )

    execute_names = [step["api_name"] for step in plan["execute_steps"]]
    skip_names = [step["api_name"] for step in plan["skip_steps"]]

    assert "dc_daily" in execute_names
    assert "dc_daily" not in skip_names
    dc_daily = next(step for step in plan["execute_steps"] if step["api_name"] == "dc_daily")
    assert dc_daily["params"]["start_date"] == "20260425"
    assert dc_daily["params"]["end_date"] == "20260430"
    assert any(action["mode"] == "gap_repair" and action["enabled"] for action in plan["next_actions"])


@pytest.mark.asyncio
async def test_daily_fast_freshness_checks_sector_daily_from_sector_kline(monkeypatch):
    service = TushareSmartImportWorkflowService()
    log_calls: list[str] = []
    table_calls: list[tuple[str, str]] = []

    async def fake_log_summary(session, api_name: str, target_date: str):
        log_calls.append(api_name)
        return {
            "latest_date": target_date,
            "covered": True,
            "source": "import_log",
            "import_record_count": 1013,
        }

    async def fake_table_summary(session, table, date_column, coverage_column, where_clause, target_date):
        table_calls.append((table, where_clause))
        return {"latest_date": "20260424", "coverage_count": 0, "covered": False}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(service, "_freshness_import_log_summary", fake_log_summary)
    monkeypatch.setattr(service, "_freshness_table_summary", fake_table_summary)
    monkeypatch.setattr(
        "app.services.data_engine.tushare_smart_import_workflow.AsyncSessionPG",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "app.services.data_engine.tushare_smart_import_workflow.AsyncSessionTS",
        lambda: FakeSession(),
    )

    freshness = await service._check_daily_fast_freshness("20260430")

    assert "dc_daily" in log_calls
    assert set(SECTOR_DAILY_SOURCE_BY_API) <= set(freshness)
    assert all(freshness[api_name]["source"] == "sector_kline" for api_name in SECTOR_DAILY_SOURCE_BY_API)
    assert freshness["dc_daily"]["diagnosis"]["reason"] == "import_log_mismatch"
    assert ("sector_kline", "data_source = 'DC' AND freq = '1d'") in table_calls
    assert ("sector_kline", "data_source = 'THS' AND freq = '1d'") in table_calls


@pytest.mark.asyncio
async def test_lightweight_readiness_uses_daily_fast_freshness(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_freshness(target_date: str):
        assert target_date == "20260430"
        return {
            "dc_daily": {
                "latest_date": "20260430",
                "coverage_count": 1013,
                "covered": True,
                "source": "sector_kline",
            },
            "moneyflow_dc": {
                "latest_date": "20260429",
                "import_record_count": 0,
                "covered": False,
                "source": "import_log",
            },
        }

    monkeypatch.setattr(service, "_check_daily_fast_freshness", fake_freshness)
    definition = service._build_definition("gap_repair", {"repair_plan": {"missing_steps": []}})
    state = service._initial_state(
        "workflow-1",
        "gap_repair",
        {"start_date": "20260410", "end_date": "20260430"},
        definition,
        {},
    )

    readiness = await service._daily_fast_lightweight_readiness(state)

    assert readiness["checks"]["dc_daily"]["ok"] is True
    assert readiness["checks"]["dc_daily"]["source"] == "sector_kline"
    assert readiness["missing_key_groups"] == ["moneyflow_dc"]


@pytest.mark.asyncio
async def test_lightweight_readiness_surfaces_sector_diagnosis(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_freshness(target_date: str):
        return {
            "dc_daily": {
                "latest_date": "20260424",
                "coverage_count": 0,
                "import_record_count": 1013,
                "covered": False,
                "source": "sector_kline",
                "diagnosis": {
                    "reason": "import_log_mismatch",
                    "message": "导入日志成功但实表覆盖不足",
                    "suggestion": "执行缺口补导",
                },
            },
        }

    monkeypatch.setattr(service, "_check_daily_fast_freshness", fake_freshness)
    definition = service._build_definition("daily_fast", {"execute_api_names": []})
    state = service._initial_state(
        "workflow-1",
        "daily_fast",
        {"start_date": "20260430", "end_date": "20260430"},
        definition,
        {},
    )

    readiness = await service._daily_fast_lightweight_readiness(state)

    assert readiness["checks"]["dc_daily"]["ok"] is False
    assert readiness["checks"]["dc_daily"]["diagnosis"]["reason"] == "import_log_mismatch"
    assert readiness["missing_key_groups"] == ["dc_daily"]


@pytest.mark.asyncio
async def test_gap_repair_plan_uses_only_missing_daily_fast_steps(monkeypatch):
    service = TushareSmartImportWorkflowService()

    async def fake_freshness(target_date: str):
        return {
            api_name: {"latest_date": "20260430", "coverage_count": 1, "covered": True}
            for api_name in DAILY_FAST_FRESHNESS_APIS
        } | {
            "moneyflow_dc": {"latest_date": "20260429", "coverage_count": 0, "covered": False},
        }

    from app.services.data_engine.tushare_smart_import_workflow import DAILY_FAST_FRESHNESS_APIS

    monkeypatch.setattr(service, "_check_daily_fast_freshness", fake_freshness)
    monkeypatch.setattr(
        service,
        "_resolve_daily_fast_target_range",
        AsyncMock(return_value=({"start_date": "20260410", "end_date": "20260430"}, None)),
    )

    plan = await service.get_plan_async(
        mode="gap_repair",
        date_range={"start_date": "20260410", "end_date": "20260430"},
    )

    assert plan["mode"] == "gap_repair"
    assert [step["api_name"] for step in plan["execute_steps"]] == ["moneyflow_dc"]
    assert plan["execute_steps"][0]["params"]["start_date"] == "20260430"
