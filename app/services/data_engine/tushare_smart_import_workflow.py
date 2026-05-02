"""
智能选股 Tushare 一键导入工作流服务

负责生成智能选股依赖的数据导入工作流、管理工作流级 Redis 状态、
启动/停止/恢复 Celery 工作流任务，并提供数据完整性摘要。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text, update

from app.core.config import settings
from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.redis_client import cache_delete, cache_get, cache_set, get_redis_client
from app.models.tushare_import import TushareImportLog
from app.services.data_engine.tushare_import_service import TushareImportService
from app.services.data_engine.tushare_registry import (
    ParamType,
    TokenTier,
    get_entry,
)

logger = logging.getLogger(__name__)

WORKFLOW_KEY = "smart-screening"
WORKFLOW_TTL = 86400
WORKFLOW_STATE_PREFIX = "tushare:workflow:"
WORKFLOW_PAUSE_PREFIX = "tushare:workflow:pause:"
WORKFLOW_STOP_PREFIX = "tushare:workflow:stop:"
WORKFLOW_RUNNING_KEY = "tushare:workflow:running:smart-screening"
IMPORT_LOCK_PREFIX = "tushare:import:lock:"
IMPORT_PROGRESS_PREFIX = "tushare:import:"
IMPORT_STOP_PREFIX = "tushare:import:stop:"
IMPORT_LOCK_TTL = 32400
DATE_RE = re.compile(r"^\d{8}$")
SH_TZ = ZoneInfo("Asia/Shanghai")
PLAN_MODES = {"daily_fast", "gap_repair", "weekly_maintenance", "full_initialize"}
FULL_MODE_ALIASES = {"incremental", "initialize", "full_initialize"}
STALE_RUNNING_MESSAGE = "任务已不在 Celery active/reserved/scheduled 中，按 stale running 自动标记失败"

CORE_INDEX_CODES = [
    "000001.SH",
    "399001.SZ",
    "399006.SZ",
    "000300.SH",
    "000905.SH",
    "000852.SH",
]

DAILY_FAST_FRESHNESS_APIS = {
    "daily",
    "adj_factor",
    "daily_basic",
    "stk_factor_pro",
    "moneyflow_dc",
    "moneyflow_ths",
    "dc_daily",
    "ths_daily",
    "tdx_daily",
    "sw_daily",
    "ci_daily",
    "index_daily",
    "index_dailybasic",
    "idx_factor_pro",
}

SECTOR_DAILY_SOURCE_BY_API = {
    "dc_daily": "DC",
    "ths_daily": "THS",
    "tdx_daily": "TDX",
    "sw_daily": "TI",
    "ci_daily": "CI",
}


@dataclass(frozen=True)
class WorkflowStep:
    """工作流单个导入步骤。"""

    api_name: str
    label: str
    factor_groups: list[str]
    default_params: dict[str, Any] = field(default_factory=dict)
    required_token_tier: str = ""
    optional: bool = False
    continue_on_failure: bool = False


@dataclass(frozen=True)
class WorkflowStage:
    """工作流阶段。"""

    key: str
    label: str
    description: str
    steps: list[WorkflowStep]


@dataclass(frozen=True)
class WorkflowDefinition:
    """工作流定义。"""

    workflow_key: str
    label: str
    mode: str
    stages: list[WorkflowStage]
    required_token_tiers: list[str]
    dependency_summary: dict[str, Any]


@dataclass(frozen=True)
class WorkflowPlanStep:
    """工作流计划步骤。"""

    api_name: str
    label: str
    params: dict[str, Any]
    reason: str
    priority: int
    estimated_rows: int | None = None
    estimated_duration: str | None = None
    skip_reason: str | None = None


@dataclass
class WorkflowRunState:
    """工作流运行态。"""

    workflow_task_id: str
    workflow_key: str
    status: str
    mode: str
    date_range: dict[str, str]
    options: dict[str, Any]
    current_stage_key: str | None
    current_stage_label: str | None
    current_api_name: str | None
    completed_steps: int
    failed_steps: int
    total_steps: int
    child_tasks: list[dict[str, Any]]
    readiness: dict[str, Any] | None = None
    error_message: str | None = None
    skip_steps: list[dict[str, Any]] = field(default_factory=list)
    maintenance_suggestions: list[dict[str, Any]] = field(default_factory=list)
    estimated_cost: dict[str, Any] = field(default_factory=dict)
    actual_cost: dict[str, Any] = field(default_factory=dict)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    target_trade_date: str | None = None
    created_at: str = ""
    updated_at: str = ""


class TushareSmartImportWorkflowService:
    """智能选股一键导入工作流服务。"""

    def __init__(self) -> None:
        self.import_service = TushareImportService()

    def get_definition(self, mode: str = "incremental", options: dict | None = None) -> dict:
        """返回工作流定义。"""
        options = options or {}
        normalized_mode = self._normalize_mode(mode)
        definition = self._build_definition(mode=normalized_mode, options=options)
        result = self._definition_to_dict(definition)
        result["plan"] = self._build_plan_dict(
            mode=normalized_mode,
            definition=definition,
            date_range=self._normalize_date_range(None),
            options=options,
        )
        return result

    def get_plan(
        self,
        mode: str = "daily_fast",
        date_range: dict[str, str] | None = None,
        options: dict | None = None,
    ) -> dict:
        """生成导入计划但不启动任务。"""
        options = options or {}
        normalized_mode = self._normalize_mode(mode)
        normalized_range = self._normalize_date_range(date_range)
        definition = self._build_definition(mode=normalized_mode, options=options)
        return self._build_plan_dict(
            mode=normalized_mode,
            definition=definition,
            date_range=normalized_range,
            options=options,
        )

    async def get_plan_async(
        self,
        mode: str = "daily_fast",
        date_range: dict[str, str] | None = None,
        options: dict | None = None,
    ) -> dict:
        """生成带新鲜度检查的导入计划。"""
        options = options or {}
        normalized_mode = self._normalize_mode(mode)
        normalized_range = self._normalize_date_range(date_range)
        normalized_range, target_adjustment = await self._resolve_daily_fast_target_range(
            normalized_mode,
            normalized_range,
        )

        if normalized_mode == "gap_repair" and not options.get("repair_plan"):
            daily_definition = self._build_definition(mode="daily_fast", options=options)
            daily_plan = self._build_plan_dict(
                mode="daily_fast",
                definition=daily_definition,
                date_range=normalized_range,
                options=options,
            )
            return await self._apply_daily_fast_freshness(
                daily_plan,
                normalized_range,
                mode="gap_repair",
                target_adjustment=target_adjustment,
            )

        definition = self._build_definition(mode=normalized_mode, options=options)
        plan = self._build_plan_dict(
            mode=normalized_mode,
            definition=definition,
            date_range=normalized_range,
            options=options,
        )
        if normalized_mode == "daily_fast":
            return await self._apply_daily_fast_freshness(
                plan,
                normalized_range,
                mode=normalized_mode,
                target_adjustment=target_adjustment,
            )
        if target_adjustment:
            plan["target_trade_date_adjustment"] = target_adjustment
        return plan

    async def start_workflow(
        self,
        mode: str = "incremental",
        date_range: dict[str, str] | None = None,
        options: dict | None = None,
    ) -> dict:
        """启动智能选股一键导入工作流。"""
        options = options or {}
        mode = self._normalize_mode(mode)
        date_range = self._normalize_date_range(date_range)
        plan = await self.get_plan_async(mode=mode, date_range=date_range, options=options)
        options = dict(options)
        if mode == "daily_fast":
            options["execute_api_names"] = [step["api_name"] for step in plan["execute_steps"]]
        elif mode == "gap_repair" and not options.get("repair_plan"):
            options["repair_plan"] = {"missing_steps": plan["execute_steps"]}
        options["plan_step_params"] = {
            step["api_name"]: step.get("params", {})
            for step in plan["execute_steps"]
        }

        definition = self._build_definition(mode=mode, options=options)
        missing = self._missing_token_tiers(definition)
        if missing:
            raise ValueError(json.dumps({"missing_token_tiers": missing}, ensure_ascii=False))

        workflow_task_id = str(uuid4())
        state = self._initial_state(workflow_task_id, mode, date_range, definition, options, plan=plan)

        redis = get_redis_client()
        try:
            acquired = await redis.set(WORKFLOW_RUNNING_KEY, workflow_task_id, ex=WORKFLOW_TTL, nx=True)
            if not acquired:
                running_id = await redis.get(WORKFLOW_RUNNING_KEY)
                raise RuntimeError(f"已有智能选股一键导入工作流正在运行：{running_id}")
        finally:
            await redis.aclose()

        await self._set_state(state)

        from app.core.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.tushare_workflow.run_smart_screening_import_workflow",
            kwargs={
                "workflow_task_id": workflow_task_id,
                "mode": mode,
                "date_range": date_range,
                "options": options,
                "resume": False,
            },
            queue="data_sync",
            task_id=workflow_task_id,
        )
        return {
            "workflow_task_id": workflow_task_id,
            "status": "pending",
            "total_steps": state.total_steps,
        }

    async def resume_workflow(self, workflow_task_id: str) -> dict:
        """从失败或停止状态继续执行工作流。"""
        state = await self._get_state_obj(workflow_task_id)
        if state is None:
            raise KeyError(workflow_task_id)
        if state.status not in {"failed", "paused"}:
            raise RuntimeError(f"工作流当前状态为 {state.status}，不可继续执行")

        redis = get_redis_client()
        try:
            acquired = await redis.set(WORKFLOW_RUNNING_KEY, workflow_task_id, ex=WORKFLOW_TTL, nx=True)
            if not acquired:
                running_id = await redis.get(WORKFLOW_RUNNING_KEY)
                raise RuntimeError(f"已有智能选股一键导入工作流正在运行：{running_id}")
        finally:
            await redis.aclose()

        await cache_delete(f"{WORKFLOW_PAUSE_PREFIX}{workflow_task_id}")
        await cache_delete(f"{WORKFLOW_STOP_PREFIX}{workflow_task_id}")
        state.status = "pending"
        state.error_message = None
        self._touch_state(state)
        await self._set_state(state)

        from app.core.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.tushare_workflow.run_smart_screening_import_workflow",
            kwargs={
                "workflow_task_id": workflow_task_id,
                "mode": state.mode,
                "date_range": state.date_range,
                "options": state.options,
                "resume": True,
            },
            queue="data_sync",
            task_id=str(uuid4()),
        )
        return {"workflow_task_id": workflow_task_id, "status": "pending"}

    async def get_status(self, workflow_task_id: str) -> dict:
        """查询工作流状态。"""
        state = await self._get_state(workflow_task_id)
        if not state:
            return {"workflow_task_id": workflow_task_id, "status": "unknown"}
        return await self._merge_child_progress(state)

    async def get_running_workflow(self) -> dict | None:
        """获取当前运行中的智能选股工作流。"""
        running_id = await cache_get(WORKFLOW_RUNNING_KEY)
        if not running_id:
            return None
        state = await self._get_state(running_id)
        if not state:
            await cache_delete(WORKFLOW_RUNNING_KEY)
            return None
        return await self._merge_child_progress(state)

    async def stop_workflow(self, workflow_task_id: str) -> dict:
        """停止工作流。"""
        await cache_set(f"{WORKFLOW_STOP_PREFIX}{workflow_task_id}", "1", ex=WORKFLOW_TTL)
        state = await self._get_state_obj(workflow_task_id)
        if state:
            current_child_id = None
            for child in reversed(state.child_tasks):
                if child.get("status") == "running":
                    current_child_id = child.get("task_id")
                    break
            if current_child_id:
                await cache_set(f"{IMPORT_STOP_PREFIX}{current_child_id}", "1", ex=WORKFLOW_TTL)
            state.status = "stopped"
            state.error_message = "用户手动停止"
            self._touch_state(state)
            await self._set_state(state)
        return {"message": "停止信号已发送"}

    async def pause_workflow(self, workflow_task_id: str) -> dict:
        """暂停工作流。

        暂停会停止当前子接口导入并阻止后续步骤启动，工作流保持可恢复。
        """
        await cache_set(f"{WORKFLOW_PAUSE_PREFIX}{workflow_task_id}", "1", ex=WORKFLOW_TTL)
        state = await self._get_state_obj(workflow_task_id)
        if state:
            current_child_id = None
            for child in reversed(state.child_tasks):
                if child.get("status") == "running":
                    current_child_id = child.get("task_id")
                    break
            if current_child_id:
                await cache_set(f"{IMPORT_STOP_PREFIX}{current_child_id}", "1", ex=WORKFLOW_TTL)
            state.status = "paused"
            state.error_message = "用户手动暂停"
            self._touch_state(state)
            await self._set_state(state)
        return {"message": "暂停信号已发送"}

    async def run_workflow(
        self,
        workflow_task_id: str,
        mode: str,
        date_range: dict[str, str],
        options: dict | None = None,
        resume: bool = False,
    ) -> dict:
        """在 Celery 任务内执行工作流。"""
        options = options or {}
        mode = self._normalize_mode(mode)
        definition = self._build_definition(mode=mode, options=options)
        state = await self._get_state_obj(workflow_task_id)
        if state is None:
            state = self._initial_state(workflow_task_id, mode, date_range, definition, options)

        if resume:
            state.child_tasks = [
                child for child in state.child_tasks if child.get("status") == "completed"
            ]

        state.status = "running"
        state.completed_steps = self._count_children(state, "completed")
        state.failed_steps = self._count_children(state, "failed")
        state.error_message = None
        self._touch_state(state)
        await self._set_state(state)

        try:
            if state.total_steps == 0 and state.mode in {"daily_fast", "gap_repair"}:
                state.current_stage_key = "readiness"
                state.current_stage_label = "轻量完整性检查"
                state.current_api_name = None
                state.readiness = await self._daily_fast_lightweight_readiness(state)
                state.status = "completed"
                state.error_message = None
                state.actual_cost = self._build_actual_cost(state)
                self._touch_state(state)
                await self._set_state(state)
                return asdict(state)

            for stage in definition.stages:
                for step in stage.steps:
                    if self._child_completed(state, step.api_name):
                        continue
                    if await self._pause_requested(workflow_task_id):
                        return await self._finalize_paused(state)
                    if await self._stop_requested(workflow_task_id):
                        return await self._finalize_stopped(state)

                    state.current_stage_key = stage.key
                    state.current_stage_label = stage.label
                    state.current_api_name = step.api_name
                    self._touch_state(state)
                    await self._set_state(state)

                    result = await self._run_step(workflow_task_id, state, step)
                    if result.get("status") == "stopped":
                        if await self._pause_requested(workflow_task_id):
                            return await self._finalize_paused(state)
                        return await self._finalize_stopped(state)
                    if result.get("status") != "completed":
                        if step.continue_on_failure:
                            continue
                        state.status = "failed"
                        state.error_message = result.get("error") or f"{step.api_name} 导入失败"
                        self._touch_state(state)
                        await self._set_state(state)
                        return asdict(state)

            state.current_stage_key = "readiness"
            state.current_stage_label = "完整性检查"
            state.current_api_name = None
            if state.mode in {"daily_fast", "gap_repair"}:
                state.readiness = await self._daily_fast_lightweight_readiness(state)
            else:
                state.readiness = await self.run_readiness_check()
            state.status = "completed"
            state.error_message = None
            state.actual_cost = self._build_actual_cost(state)
            self._touch_state(state)
            await self._set_state(state)
            return asdict(state)
        except Exception as exc:
            await self._mark_state_failed(
                state,
                error_message=f"工作流异常中断：{exc}",
                stale_child=False,
            )
            raise
        finally:
            if state.status in {"completed", "failed", "stopped"}:
                await cache_delete(WORKFLOW_RUNNING_KEY)

    async def mark_workflow_failed(self, workflow_task_id: str, error_message: str) -> dict:
        """外部任务异常时标记工作流失败并释放锁。"""
        state = await self._get_state_obj(workflow_task_id)
        if state is None:
            return {"workflow_task_id": workflow_task_id, "status": "unknown"}
        await self._mark_state_failed(state, error_message=error_message, stale_child=True)
        return asdict(state)

    async def run_readiness_check(self) -> dict[str, Any]:
        """生成智能选股数据完整性摘要。"""
        pg_checks = {
            "daily_basic": ("stock_info", "updated_at", "symbol"),
            "moneyflow_dc": ("moneyflow_dc", "trade_date", "ts_code"),
            "stk_factor": ("stk_factor", "trade_date", "ts_code"),
            "sector_info_dc": ("sector_info", None, "sector_code", "data_source = 'DC'"),
            "sector_constituent_dc": ("sector_constituent", "trade_date", "symbol", "data_source = 'DC'"),
            "index_dailybasic": ("index_dailybasic", "trade_date", "ts_code"),
            "index_tech": ("index_tech", "trade_date", "ts_code"),
            "cyq_perf": ("cyq_perf", "trade_date", "ts_code"),
            "margin_detail": ("margin_detail", "trade_date", "ts_code"),
            "limit_list": ("limit_list", "trade_date", "ts_code"),
            "limit_step": ("limit_step", "trade_date", "ts_code"),
            "top_list": ("top_list", "trade_date", "ts_code"),
        }
        ts_checks = {
            "kline_daily": ("kline", "time", "symbol", "freq = '1d'"),
            "adj_factor": ("adjustment_factor", "trade_date", "symbol", None),
            "sector_kline_dc": ("sector_kline", "time", "sector_code", "data_source = 'DC' AND freq = '1d'"),
            "index_daily": ("kline", "time", "symbol", "freq = '1d' AND (symbol LIKE '%.SH' OR symbol LIKE '%.SZ')"),
        }
        checks: dict[str, Any] = {}
        async with AsyncSessionPG() as session:
            for name, item in pg_checks.items():
                checks[name] = await self._table_summary(session, *item)
        async with AsyncSessionTS() as session:
            for name, item in ts_checks.items():
                checks[name] = await self._table_summary(session, *item)

        missing = [
            name for name, summary in checks.items()
            if not summary.get("ok") and name in {"kline_daily", "daily_basic", "moneyflow_dc", "stk_factor"}
        ]
        dependency_summary = self.derive_strategy_dependency_summary()
        return {
            "generated_at": datetime.now(SH_TZ).isoformat(),
            "checks": checks,
            "missing_key_groups": missing,
            "recommendations": [
                f"{name} 数据缺失或为空，建议重新导入相关阶段" for name in missing
            ],
            "dependency_summary": dependency_summary,
            "compatibility_warnings": dependency_summary.get("compatibility_warnings", []),
        }

    def derive_strategy_dependency_summary(self) -> dict[str, Any]:
        """扫描当前策略示例/内置模板的因子覆盖摘要。"""
        used_factors: set[str] = set()
        try:
            from app.api.v1.screen import _BUILTIN_TEMPLATES
            for tpl in _BUILTIN_TEMPLATES:
                config = tpl.get("config", {})
                for factor in config.get("factors", []):
                    name = factor.get("factor_name")
                    if name:
                        used_factors.add(str(name))
        except Exception as exc:
            logger.debug("扫描内置策略模板失败: %s", exc)

        try:
            from app.services.screener.strategy_examples import STRATEGY_EXAMPLES
            for example in STRATEGY_EXAMPLES:
                for factor in example.factors:
                    name = factor.get("factor_name")
                    if name:
                        used_factors.add(str(name))
        except Exception as exc:
            logger.debug("扫描策略示例失败: %s", exc)

        covered = {
            "ma_trend", "ma_support", "breakout", "macd", "boll", "rsi", "dma",
            "turnover", "volume_price", "kdj_k", "kdj_d", "kdj_j",
            "money_flow", "large_order", "super_large_net_inflow", "large_net_inflow",
            "small_net_outflow", "money_flow_strength", "sector_rank", "sector_trend",
            "index_ma_trend", "index_pe", "index_turnover", "index_vol_ratio",
            "chip_winner_rate", "chip_concentration", "margin_net_buy",
            "rzrq_balance_trend", "limit_up_open_pct", "limit_up_streak",
            "first_limit_up", "dragon_tiger_net_buy", "roe", "profit_growth",
            "market_cap", "pe", "pb", "pe_ttm",
        }
        compatibility = []
        if "pe_ttm" in used_factors:
            compatibility.append("旧策略字段 pe_ttm 不在因子注册表标准字段中，当前通过 daily_basic/stock_info 兼容。")
        return {
            "used_factors": sorted(used_factors),
            "covered_factors": sorted(used_factors & covered),
            "uncovered_factors": sorted(used_factors - covered),
            "compatibility_warnings": compatibility,
        }

    async def _run_step(
        self,
        workflow_task_id: str,
        state: WorkflowRunState,
        step: WorkflowStep,
    ) -> dict:
        entry = get_entry(step.api_name)
        if entry is None:
            return await self._record_child_result(state, step, "", 0, "failed", "接口不存在")

        lock_key = f"{IMPORT_LOCK_PREFIX}{step.api_name}"
        child_task_id = str(uuid4())
        redis = get_redis_client()
        try:
            acquired = await redis.set(lock_key, child_task_id, ex=IMPORT_LOCK_TTL, nx=True)
            if not acquired:
                locked_task_id = await redis.get(lock_key)
                if locked_task_id and await self._release_stale_import_lock(step.api_name, locked_task_id):
                    acquired = await redis.set(lock_key, child_task_id, ex=IMPORT_LOCK_TTL, nx=True)
            if not acquired:
                return await self._record_child_result(
                    state, step, child_task_id, 0, "failed", "该接口已有导入任务正在运行",
                )
        finally:
            await redis.aclose()

        params = self._build_step_params(entry, step.default_params, state.date_range)
        self.import_service._validate_params(entry, params)
        warning = await self.import_service._check_dependency(entry)
        token = self.import_service._resolve_token(entry.token_tier)
        log_id = await self.import_service._create_import_log(step.api_name, params, child_task_id)
        await cache_set(
            f"{IMPORT_PROGRESS_PREFIX}{child_task_id}",
            json.dumps({"total": 0, "completed": 0, "failed": 0, "status": "pending", "current_item": ""}),
            ex=WORKFLOW_TTL,
        )
        child = {
            "task_id": child_task_id,
            "log_id": log_id,
            "api_name": step.api_name,
            "label": step.label,
            "status": "running",
            "record_count": 0,
            "params": params,
            "warning": warning,
            "started_at": datetime.now(SH_TZ).isoformat(),
        }
        state.child_tasks.append(child)
        self._touch_state(state)
        await self._set_state(state)

        from app.tasks.tushare_import import _process_import

        result = await _process_import(step.api_name, params, token, log_id, child_task_id)
        status = result.get("status", "completed")
        if status not in {"completed", "stopped"}:
            status = "failed"
        child["status"] = status
        child["record_count"] = result.get("record_count", 0)
        child["error_message"] = result.get("error")
        if result.get("batch_stats"):
            child["extra_info"] = result.get("batch_stats")
        child["finished_at"] = datetime.now(SH_TZ).isoformat()
        state.completed_steps = self._count_children(state, "completed")
        state.failed_steps = self._count_children(state, "failed")
        self._touch_state(state)
        await self._set_state(state)
        return {"status": status, "error": result.get("error")}

    async def _record_child_result(
        self,
        state: WorkflowRunState,
        step: WorkflowStep,
        child_task_id: str,
        log_id: int,
        status: str,
        error_message: str,
    ) -> dict:
        state.child_tasks.append({
            "task_id": child_task_id,
            "log_id": log_id,
            "api_name": step.api_name,
            "label": step.label,
            "status": status,
            "record_count": 0,
            "error_message": error_message,
            "finished_at": datetime.now(SH_TZ).isoformat(),
        })
        state.failed_steps = self._count_children(state, "failed")
        self._touch_state(state)
        await self._set_state(state)
        return {"status": status, "error": error_message}

    def _build_definition(self, mode: str, options: dict) -> WorkflowDefinition:
        mode = self._normalize_mode(mode)
        if mode == "daily_fast":
            stages = self._daily_fast_stages(options)
        elif mode == "gap_repair":
            stages = self._gap_repair_stages(options)
        elif mode == "weekly_maintenance":
            stages = self._weekly_maintenance_stages(options)
        else:
            stages = self._full_initialize_stages(options)

        execute_api_names = options.get("execute_api_names")
        if isinstance(execute_api_names, list):
            allowed = {str(name) for name in execute_api_names}
            stages = [
                WorkflowStage(
                    key=stage.key,
                    label=stage.label,
                    description=stage.description,
                    steps=[step for step in stage.steps if step.api_name in allowed],
                )
                for stage in stages
            ]
            stages = [stage for stage in stages if stage.steps]
        plan_step_params = options.get("plan_step_params")
        if isinstance(plan_step_params, dict):
            stages = [
                WorkflowStage(
                    key=stage.key,
                    label=stage.label,
                    description=stage.description,
                    steps=[
                        WorkflowStep(
                            api_name=step.api_name,
                            label=step.label,
                            factor_groups=step.factor_groups,
                            default_params=dict(plan_step_params.get(step.api_name) or step.default_params),
                            required_token_tier=step.required_token_tier,
                            optional=step.optional,
                            continue_on_failure=step.continue_on_failure,
                        )
                        for step in stage.steps
                    ],
                )
                for stage in stages
            ]

        tiers = sorted({
            step.required_token_tier
            for stage in stages
            for step in stage.steps
            if step.required_token_tier
        })
        return WorkflowDefinition(
            workflow_key=WORKFLOW_KEY,
            label="智能选股一键导入",
            mode=mode,
            stages=stages,
            required_token_tiers=tiers,
            dependency_summary=self.derive_strategy_dependency_summary(),
        )

    def _full_initialize_stages(self, options: dict) -> list[WorkflowStage]:
        stages: list[WorkflowStage] = [
            self._stage("base", "基础证券和交易日历", "股票池和交易日依赖", [
                self._step("stock_basic", ["基础证券"]),
                self._step("trade_cal", ["交易日历"]),
            ]),
            self._stage("kline", "股票日线主行情和复权", "技术面和突破形态基础", [
                self._step("daily", ["K线", "技术面"]),
                self._step("adj_factor", ["复权因子"]),
            ]),
            self._stage("daily_basic", "日指标和 K 线辅助字段", "换手率、市值和估值字段", [
                self._step("daily_basic", ["换手率", "基本面"]),
            ]),
            self._stage("tech_factor", "技术专题指标", "KDJ 等技术专题因子", [
                self._step("stk_factor_pro", ["技术专题"]),
            ]),
            self._stage("money_flow", "资金流专题", "主力资金和大单资金流", [
                self._step("moneyflow_dc", ["资金流"]),
            ]),
            self._stage("sector", "板块数据", "默认 DC 板块链路", [
                self._step("dc_index", ["板块"]),
                self._step("dc_member", ["板块"]),
                self._step("dc_daily", ["板块"]),
            ]),
            self._stage("index", "指数专题", "大盘指数行情和指标", [
                self._step("index_basic", ["指数"]),
                self._step("index_daily", ["指数"]),
                self._step("index_weight", ["指数"], {"index_codes": CORE_INDEX_CODES}),
                self._step("index_dailybasic", ["指数"]),
                self._step("idx_factor_pro", ["指数"]),
            ]),
            self._stage("extended", "扩展专题因子", "筹码、两融、打板和龙虎榜", [
                self._step("cyq_perf", ["筹码"]),
                self._step("margin_detail", ["两融"]),
                self._step("limit_list_d", ["打板"]),
                self._step("limit_step", ["打板"]),
                self._step("top_list", ["龙虎榜"]),
            ]),
        ]
        if options.get("include_moneyflow_ths"):
            stages[4].steps.append(self._step("moneyflow_ths", ["资金流"], optional=True, continue_on_failure=True))
        if options.get("include_ths_sector"):
            stages[5].steps.extend([
                self._step("ths_index", ["板块"], optional=True, continue_on_failure=True),
                self._step("ths_member", ["板块"], optional=True, continue_on_failure=True),
                self._step("ths_daily", ["板块"], optional=True, continue_on_failure=True),
            ])
        if options.get("include_tdx_sector"):
            stages[5].steps.extend([
                self._step("tdx_index", ["板块"], optional=True, continue_on_failure=True),
                self._step("tdx_member", ["板块"], optional=True, continue_on_failure=True),
                self._step("tdx_daily", ["板块"], optional=True, continue_on_failure=True),
            ])
        if options.get("include_ti_sector"):
            stages[5].steps.extend([
                self._step("index_classify", ["板块"], optional=True, continue_on_failure=True),
                self._step("index_member_all", ["板块"], optional=True, continue_on_failure=True),
                self._step("sw_daily", ["板块"], optional=True, continue_on_failure=True),
            ])
        if options.get("include_ci_sector"):
            stages[5].steps.extend([
                self._step("ci_index_member", ["板块"], optional=True, continue_on_failure=True),
                self._step("ci_daily", ["板块"], optional=True, continue_on_failure=True),
            ])
        return stages

    def _daily_fast_stages(self, options: dict) -> list[WorkflowStage]:
        stages = [
            self._stage("daily_core", "每日核心行情", "每日选股必要的行情、复权和日指标", [
                self._step("daily", ["K线", "技术面"]),
                self._step("adj_factor", ["复权因子"]),
                self._step("daily_basic", ["换手率", "基本面"]),
                self._step("stk_factor_pro", ["技术专题"]),
            ]),
            self._stage("daily_money_sector", "资金流和默认板块", "默认 DC 资金流和板块行情", [
                self._step("moneyflow_dc", ["资金流"]),
                self._step("dc_daily", ["板块"]),
            ]),
            self._stage("daily_index", "核心指数专题", "每日快速默认核心指数行情和指标", [
                self._step("index_daily", ["指数"], {"index_codes": CORE_INDEX_CODES}),
                self._step("index_dailybasic", ["指数"], {"index_codes": CORE_INDEX_CODES}),
                self._step("idx_factor_pro", ["指数"], {"index_codes": CORE_INDEX_CODES}),
            ]),
        ]
        if options.get("include_moneyflow_ths"):
            stages[1].steps.append(self._step("moneyflow_ths", ["资金流"], optional=True, continue_on_failure=True))
        if options.get("include_ths_sector"):
            stages[1].steps.append(self._step("ths_daily", ["板块"], optional=True, continue_on_failure=True))
        if options.get("include_tdx_sector"):
            stages[1].steps.append(self._step("tdx_daily", ["板块"], optional=True, continue_on_failure=True))
        if options.get("include_ti_sector"):
            stages[1].steps.append(self._step("sw_daily", ["板块"], optional=True, continue_on_failure=True))
        if options.get("include_ci_sector"):
            stages[1].steps.append(self._step("ci_daily", ["板块"], optional=True, continue_on_failure=True))
        if options.get("include_extended_topics") is True:
            stages.append(self._stage("strategy_extended", "策略扩展专题", "按策略启用的筹码、两融、打板和龙虎榜", [
                self._step("cyq_perf", ["筹码"], optional=True, continue_on_failure=True),
                self._step("margin_detail", ["两融"], optional=True, continue_on_failure=True),
                self._step("limit_list_d", ["打板"], optional=True, continue_on_failure=True),
                self._step("limit_step", ["打板"], optional=True, continue_on_failure=True),
                self._step("top_list", ["龙虎榜"], optional=True, continue_on_failure=True),
            ]))
        return stages

    def _gap_repair_stages(self, options: dict) -> list[WorkflowStage]:
        repair_plan = options.get("repair_plan") if isinstance(options.get("repair_plan"), dict) else None
        missing_steps = repair_plan.get("missing_steps", []) if repair_plan else []
        steps: list[WorkflowStep] = []
        for item in missing_steps:
            api_name = item.get("api_name") if isinstance(item, dict) else None
            if api_name:
                params = {
                    k: v for k, v in item.items()
                    if k in {"start_date", "end_date", "ts_code", "trade_date"}
                }
                steps.append(self._step(str(api_name), ["缺口补导"], params))
        if repair_plan is not None:
            return [self._stage("gap_repair", "缺口补导", "只补完整性检查识别出的缺失接口和日期", steps)]
        if not steps:
            for stage in self._daily_fast_stages(options):
                steps.extend(stage.steps)
        return [self._stage("gap_repair", "缺口补导", "只补完整性检查识别出的缺失接口和日期", steps)]

    def _weekly_maintenance_stages(self, options: dict) -> list[WorkflowStage]:
        stages = [
            self._stage("weekly_base", "低频基础数据", "股票、交易日历和指数基础信息", [
                self._step("stock_basic", ["基础证券"]),
                self._step("trade_cal", ["交易日历"]),
                self._step("index_basic", ["指数"]),
            ]),
            self._stage("weekly_sector", "板块和成分维护", "低频板块基础和成分数据", [
                self._step("dc_index", ["板块"]),
                self._step("dc_member", ["板块"]),
            ]),
        ]
        if options.get("include_ths_sector"):
            stages[1].steps.extend([self._step("ths_index", ["板块"]), self._step("ths_member", ["板块"])])
        if options.get("include_tdx_sector"):
            stages[1].steps.extend([self._step("tdx_index", ["板块"]), self._step("tdx_member", ["板块"])])
        if options.get("include_ti_sector"):
            stages[1].steps.extend([self._step("index_classify", ["板块"]), self._step("index_member_all", ["板块"])])
        if options.get("include_ci_sector"):
            stages[1].steps.append(self._step("ci_index_member", ["板块"]))
        return stages

    def _step(
        self,
        api_name: str,
        factor_groups: list[str],
        default_params: dict[str, Any] | None = None,
        optional: bool = False,
        continue_on_failure: bool = False,
    ) -> WorkflowStep:
        entry = get_entry(api_name)
        return WorkflowStep(
            api_name=api_name,
            label=entry.label if entry else api_name,
            factor_groups=factor_groups,
            default_params=default_params or {},
            required_token_tier=entry.token_tier.value if entry else "",
            optional=optional,
            continue_on_failure=continue_on_failure,
        )

    @staticmethod
    def _stage(key: str, label: str, description: str, steps: list[WorkflowStep]) -> WorkflowStage:
        return WorkflowStage(key=key, label=label, description=description, steps=steps)

    def _build_step_params(
        self,
        entry: Any,
        default_params: dict[str, Any],
        date_range: dict[str, str],
    ) -> dict[str, Any]:
        params = {k: v for k, v in default_params.items() if k != "index_codes"}
        has_date_range = (
            ParamType.DATE_RANGE in entry.required_params
            or ParamType.DATE_RANGE in entry.optional_params
        )
        if has_date_range:
            params.setdefault("start_date", date_range["start_date"])
            params.setdefault("end_date", date_range["end_date"])
        if entry.api_name == "daily_basic":
            params["update_current_snapshot"] = True
        if entry.api_name in {"index_daily", "index_dailybasic", "idx_factor_pro", "index_weight"}:
            index_codes = default_params.get("index_codes")
            if index_codes:
                params["index_codes"] = index_codes
        return params

    def _definition_to_dict(self, definition: WorkflowDefinition) -> dict:
        return asdict(definition)

    def _initial_state(
        self,
        workflow_task_id: str,
        mode: str,
        date_range: dict[str, str],
        definition: WorkflowDefinition,
        options: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
    ) -> WorkflowRunState:
        now = datetime.now(SH_TZ).isoformat()
        total = sum(len(stage.steps) for stage in definition.stages)
        if plan is None:
            plan = self._build_plan_dict(
                mode=mode,
                definition=definition,
                date_range=date_range,
                options=options or {},
            )
        return WorkflowRunState(
            workflow_task_id=workflow_task_id,
            workflow_key=WORKFLOW_KEY,
            status="pending",
            mode=mode,
            date_range=date_range,
            options=options or {},
            current_stage_key=None,
            current_stage_label=None,
            current_api_name=None,
            completed_steps=0,
            failed_steps=0,
            total_steps=total,
            child_tasks=[],
            skip_steps=plan["skip_steps"],
            maintenance_suggestions=plan["maintenance_suggestions"],
            estimated_cost=plan["estimated_cost"],
            actual_cost={},
            next_actions=plan["next_actions"],
            target_trade_date=plan["target_trade_date"],
            created_at=now,
            updated_at=now,
        )

    def _build_plan_dict(
        self,
        mode: str,
        definition: WorkflowDefinition,
        date_range: dict[str, str],
        options: dict[str, Any],
    ) -> dict:
        execute_steps: list[dict[str, Any]] = []
        priority = 1
        for stage in definition.stages:
            for step in stage.steps:
                entry = get_entry(step.api_name)
                params = self._build_step_params(entry, step.default_params, date_range) if entry else step.default_params
                execute_steps.append(asdict(WorkflowPlanStep(
                    api_name=step.api_name,
                    label=step.label,
                    params=params,
                    reason=self._plan_reason(mode, step.api_name),
                    priority=priority,
                    estimated_duration=self._estimate_duration_label(mode, step.api_name),
                )))
                priority += 1

        return {
            "mode": mode,
            "target_trade_date": date_range["end_date"],
            "execute_steps": execute_steps,
            "skip_steps": self._skip_steps_for_mode(mode, options),
            "maintenance_suggestions": self._maintenance_suggestions_for_mode(mode),
            "estimated_cost": {
                "step_count": len(execute_steps),
                "slow_step_count": sum(1 for item in execute_steps if item["api_name"] in {
                    "dc_member", "tdx_member", "ths_member", "index_member_all",
                    "ci_index_member", "cyq_perf", "margin_detail", "index_weight",
                }),
                "label": self._estimated_cost_label(mode),
            },
            "next_actions": self._next_actions_for_mode(mode),
        }

    async def _apply_daily_fast_freshness(
        self,
        plan: dict[str, Any],
        date_range: dict[str, str],
        mode: str,
        target_adjustment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """按现有数据覆盖情况压缩每日快速/缺口补导执行计划。"""
        target_date = date_range["end_date"]
        freshness = await self._check_daily_fast_freshness(target_date)
        execute_steps: list[dict[str, Any]] = []
        freshness_skip_steps: list[dict[str, Any]] = []

        for step in plan["execute_steps"]:
            api_name = step["api_name"]
            summary = freshness.get(api_name, {})
            if api_name in DAILY_FAST_FRESHNESS_APIS and summary.get("covered"):
                source = summary.get("source", "import_log")
                skip_reason = (
                    f"{target_date} 实表已有覆盖"
                    if source == "sector_kline"
                    else f"{target_date} 已有成功导入记录"
                )
                freshness_skip_steps.append({
                    "api_name": api_name,
                    "label": step.get("label", api_name),
                    "reason": "目标交易日已覆盖",
                    "skip_reason": skip_reason,
                    "latest_date": summary.get("latest_date"),
                    "import_record_count": summary.get("import_record_count"),
                    "coverage_count": summary.get("coverage_count"),
                    "source": source,
                })
                continue

            if api_name in DAILY_FAST_FRESHNESS_APIS:
                gap_start = self._gap_start_date(
                    requested_start=date_range["start_date"],
                    latest_date=summary.get("latest_date"),
                    target_date=target_date,
                )
                params = dict(step.get("params") or {})
                if "start_date" in params and "end_date" in params:
                    params["start_date"] = gap_start
                    params["end_date"] = target_date
                    step = {
                        **step,
                        "params": params,
                        "reason": self._freshness_reason(api_name, summary, target_date),
                    }
            execute_steps.append(step)

        if mode == "gap_repair":
            plan = {
                **plan,
                "mode": "gap_repair",
                "execute_steps": execute_steps,
                "skip_steps": freshness_skip_steps,
                "maintenance_suggestions": plan.get("maintenance_suggestions", []),
                "estimated_cost": {
                    **(plan.get("estimated_cost") or {}),
                    "step_count": len(execute_steps),
                    "label": "按缺口最小范围补导，完成后会再次检查完整性",
                },
                "next_actions": self._next_actions_for_mode("gap_repair"),
                "freshness": freshness,
            }
        else:
            plan = {
                **plan,
                "execute_steps": execute_steps,
                "skip_steps": freshness_skip_steps + plan.get("skip_steps", []),
                "estimated_cost": {
                    **(plan.get("estimated_cost") or {}),
                    "step_count": len(execute_steps),
                },
                "freshness": freshness,
            }
            next_actions = list(plan.get("next_actions") or [])
            has_gap = any(
                not freshness.get(api_name, {}).get("covered", False)
                for api_name in DAILY_FAST_FRESHNESS_APIS
            )
            for action in next_actions:
                if action.get("mode") == "gap_repair":
                    action["enabled"] = has_gap
            plan["next_actions"] = next_actions
        if target_adjustment:
            plan["target_trade_date_adjustment"] = target_adjustment
        return plan

    async def _resolve_daily_fast_target_range(
        self,
        mode: str,
        date_range: dict[str, str],
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """单日快速链路遇到休市日时回退到最近交易日。"""
        if mode not in {"daily_fast", "gap_repair"}:
            return date_range, None
        if date_range["start_date"] != date_range["end_date"]:
            return date_range, None

        requested = date_range["end_date"]
        async with AsyncSessionPG() as session:
            result = await session.execute(
                text(
                    """
                    SELECT MAX(cal_date)
                    FROM trade_calendar
                    WHERE is_open = true
                      AND cal_date <= to_date(:requested, 'YYYYMMDD')
                    """
                ),
                {"requested": requested},
            )
            value = result.scalar_one_or_none()

        if value is None:
            return date_range, None
        resolved = value.strftime("%Y%m%d") if hasattr(value, "strftime") else str(value).replace("-", "")
        if resolved == requested:
            return date_range, None
        return (
            {"start_date": resolved, "end_date": resolved},
            {
                "requested_date": requested,
                "target_trade_date": resolved,
                "reason": "所选日期不是交易日，已回退到最近交易日",
            },
        )

    async def _check_daily_fast_freshness(self, target_date: str) -> dict[str, dict[str, Any]]:
        """检查每日快速关键接口是否覆盖目标交易日。

        确认面板需要快速返回，因此计划阶段优先读取导入日志，而不是扫描
        kline/sector_kline 等大表；最终数据可用性仍由工作流终态完整性检查兜底。
        """
        checks: dict[str, dict[str, Any]] = {}
        sector_log_summaries: dict[str, dict[str, Any]] = {}
        async with AsyncSessionPG() as session:
            for api_name in DAILY_FAST_FRESHNESS_APIS:
                if api_name in SECTOR_DAILY_SOURCE_BY_API:
                    sector_log_summaries[api_name] = await self._freshness_import_log_summary(
                        session,
                        api_name=api_name,
                        target_date=target_date,
                    )
                    continue
                checks[api_name] = await self._freshness_import_log_summary(
                    session,
                    api_name=api_name,
                    target_date=target_date,
                )
        async with AsyncSessionTS() as session:
            for api_name, data_source in SECTOR_DAILY_SOURCE_BY_API.items():
                if api_name not in DAILY_FAST_FRESHNESS_APIS:
                    continue
                summary = await self._freshness_table_summary(
                    session=session,
                    table="sector_kline",
                    date_column="time",
                    coverage_column="sector_code",
                    where_clause=f"data_source = '{data_source}' AND freq = '1d'",
                    target_date=target_date,
                )
                summary["source"] = "sector_kline"
                log_summary = sector_log_summaries.get(api_name) or {}
                if log_summary.get("import_record_count") is not None:
                    summary["import_record_count"] = log_summary.get("import_record_count")
                if not summary.get("covered"):
                    if log_summary.get("import_record_count"):
                        summary["diagnosis"] = {
                            "reason": "import_log_mismatch",
                            "message": (
                                f"{api_name} 导入日志显示目标日成功且记录数 "
                                f"{log_summary.get('import_record_count')}，但 sector_kline 实表覆盖不足"
                            ),
                            "suggestion": "执行缺口补导，并检查字段映射、交易日期解析和 TS 写入错误",
                        }
                    elif summary.get("latest_date") and str(summary.get("latest_date")) < target_date:
                        summary["diagnosis"] = {
                            "reason": "sector_kline_latest_before_target",
                            "message": (
                                f"{api_name} sector_kline 最新日期 {summary.get('latest_date')} "
                                f"早于目标交易日 {target_date}"
                            ),
                            "suggestion": "执行对应板块日行情缺口补导",
                        }
                    else:
                        summary["diagnosis"] = {
                            "reason": "sector_kline_no_target_coverage",
                            "message": f"{api_name} sector_kline 目标交易日 {target_date} 无覆盖",
                            "suggestion": "确认目标日是否为交易日；若是交易日，请执行缺口补导",
                        }
                checks[api_name] = summary
        return checks

    async def _freshness_table_summary(
        self,
        session: Any,
        table: str,
        date_column: str,
        coverage_column: str,
        where_clause: str | None,
        target_date: str,
    ) -> dict[str, Any]:
        """查询表级最新日期和目标日覆盖数。"""
        where_sql = f"WHERE {where_clause}" if where_clause else ""
        params = {
            "target_date": target_date,
            "target_iso": f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}",
            "index_codes": CORE_INDEX_CODES,
        }

        if date_column == "time":
            latest_sql = text(
                f"""
                SELECT to_char(MAX(time), 'YYYYMMDD') AS latest_date
                FROM {table}
                {where_sql}
                """
            )
            coverage_filter = (
                "time >= to_date(:target_date, 'YYYYMMDD') "
                "AND time < to_date(:target_date, 'YYYYMMDD') + INTERVAL '1 day'"
            )
        else:
            latest_sql = text(
                f"""
                SELECT MAX({self._freshness_date_expr(date_column)}) AS latest_date
                FROM {table}
                {where_sql}
                """
            )
            coverage_filter = (
                f"({date_column}::text = :target_date OR {date_column}::text = :target_iso)"
            )

        latest_result = await session.execute(latest_sql, params)
        latest_date = latest_result.scalar_one_or_none()

        coverage_where = (
            f"{where_sql} AND {coverage_filter}"
            if where_clause
            else f"WHERE {coverage_filter}"
        )
        coverage_sql = text(
            f"""
            SELECT COUNT(DISTINCT {coverage_column}) AS coverage_count
            FROM {table}
            {coverage_where}
            """
        )
        coverage_result = await session.execute(coverage_sql, params)
        coverage_count = int(coverage_result.scalar_one_or_none() or 0)
        return {
            "latest_date": latest_date,
            "coverage_count": coverage_count,
            "covered": bool(latest_date and str(latest_date) >= target_date and coverage_count > 0),
        }

    @staticmethod
    def _freshness_date_expr(date_column: str) -> str:
        """兼容 DATE/TIMESTAMPTZ/VARCHAR 的 YYYYMMDD 日期表达式。"""
        if date_column == "time":
            return "to_char(time, 'YYYYMMDD')"
        return (
            f"CASE "
            f"WHEN {date_column} IS NULL THEN NULL "
            f"WHEN {date_column}::text ~ '^\\d{{8}}$' THEN {date_column}::text "
            f"ELSE to_char({date_column}::date, 'YYYYMMDD') "
            f"END"
        )

    async def _freshness_import_log_summary(
        self,
        session: Any,
        api_name: str,
        target_date: str,
    ) -> dict[str, Any]:
        """通过导入日志估算没有独立历史表的接口覆盖情况。"""
        today = datetime.now(SH_TZ).strftime("%Y%m%d")
        result = await session.execute(
            text(
                """
                WITH normalized_logs AS (
                    SELECT
                        record_count,
                        COALESCE(
                            NULLIF(replace(params_json->>'start_date', '-', ''), ''),
                            NULLIF(replace(params_json->>'trade_date', '-', ''), ''),
                            NULLIF(replace(params_json->>'end_date', '-', ''), '')
                        ) AS start_date,
                        COALESCE(
                            NULLIF(replace(params_json->>'end_date', '-', ''), ''),
                            NULLIF(replace(params_json->>'trade_date', '-', ''), ''),
                            NULLIF(replace(params_json->>'start_date', '-', ''), '')
                        ) AS end_date
                    FROM tushare_import_log
                    WHERE api_name = :api_name
                      AND status = 'completed'
                )
                SELECT
                    MAX(end_date) FILTER (
                        WHERE end_date <= :today
                    ) AS latest_success_date,
                    MAX(record_count) FILTER (
                        WHERE start_date <= :target_date
                          AND end_date >= :target_date
                          AND end_date <= :today
                    ) AS import_record_count
                FROM normalized_logs
                WHERE start_date ~ '^\\d{8}$'
                  AND end_date ~ '^\\d{8}$'
                """
            ),
            {"api_name": api_name, "target_date": target_date, "today": today},
        )
        row = result.mappings().one()
        latest_success_date = self._compact_date(row.get("latest_success_date"))
        import_record_count = row.get("import_record_count")
        covered = import_record_count is not None
        return {
            "latest_date": target_date if covered else latest_success_date,
            "coverage_count": None,
            "import_record_count": int(import_record_count) if import_record_count is not None else None,
            "covered": covered,
            "source": "import_log",
        }

    @staticmethod
    def _gap_start_date(requested_start: str, latest_date: str | None, target_date: str) -> str:
        if not latest_date or latest_date < requested_start:
            return requested_start
        if latest_date >= target_date:
            return target_date
        parsed = datetime.strptime(latest_date, "%Y%m%d") + timedelta(days=1)
        return parsed.strftime("%Y%m%d")

    @staticmethod
    def _freshness_reason(api_name: str, summary: dict[str, Any], target_date: str) -> str:
        latest_date = summary.get("latest_date")
        if latest_date:
            return f"{api_name} 最近覆盖到 {latest_date}，补导至 {target_date}"
        return f"{api_name} 尚无覆盖记录，按所选日期范围导入"

    @staticmethod
    def _compact_date(value: Any) -> str | None:
        if not value:
            return None
        compacted = str(value).replace("-", "")[:8]
        return compacted if DATE_RE.match(compacted) else None

    @staticmethod
    def _plan_reason(mode: str, api_name: str) -> str:
        if mode == "daily_fast":
            return "每日选股核心依赖" if api_name != "moneyflow_ths" else "用户启用的资金流扩展"
        if mode == "gap_repair":
            return "缺口补导计划"
        if mode == "weekly_maintenance":
            return "低频基础和成分维护"
        return "完整初始化/修复链路"

    @staticmethod
    def _estimate_duration_label(mode: str, api_name: str) -> str:
        if api_name in {"dc_member", "tdx_member", "ths_member", "index_member_all", "ci_index_member"}:
            return "慢：全量成分维护"
        if api_name in {"cyq_perf", "margin_detail", "index_weight"}:
            return "慢：全市场分批专题"
        if mode == "daily_fast":
            return "快：按目标交易日"
        return "中等"

    @staticmethod
    def _estimated_cost_label(mode: str) -> str:
        if mode == "daily_fast":
            return "预计较快，适合每日 18:00 后选股前更新"
        if mode == "gap_repair":
            return "取决于缺口范围，通常快于完整初始化"
        if mode == "weekly_maintenance":
            return "预计较慢，建议周维护或盘后空闲执行"
        return "预计较慢，适合首次初始化或大范围修复"

    @staticmethod
    def _skip_steps_for_mode(mode: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        if mode != "daily_fast":
            return []
        skipped = [
            ("stock_basic", "静态基础表不在每日快速默认链路中"),
            ("trade_cal", "每日快速只本地读取交易日历，缺失时建议周维护"),
            ("index_basic", "低频指数基础信息不每日刷新"),
            ("dc_index", "低频板块基础信息不每日刷新"),
            ("dc_member", "板块成分低频变化，进入周维护"),
            ("ths_member", "非默认板块源且低频成分维护"),
            ("tdx_member", "非默认板块源且低频成分维护"),
            ("index_member_all", "申万行业成分进入周维护"),
            ("ci_index_member", "中信行业成分进入周维护"),
            ("cyq_perf", "当前未启用筹码扩展专题"),
            ("margin_detail", "当前未启用两融扩展专题"),
            ("limit_list_d", "当前未启用打板扩展专题"),
            ("limit_step", "当前未启用打板扩展专题"),
            ("top_list", "当前未启用龙虎榜扩展专题"),
        ]
        if options.get("include_extended_topics") is True:
            skipped = [item for item in skipped if item[0] not in {
                "cyq_perf", "margin_detail", "limit_list_d", "limit_step", "top_list",
            }]
        return [{"api_name": api_name, "reason": reason, "skip_reason": reason} for api_name, reason in skipped]

    @staticmethod
    def _maintenance_suggestions_for_mode(mode: str) -> list[dict[str, Any]]:
        if mode == "daily_fast":
            return [
                {"api_name": "stock_basic", "reason": "超过 TTL 或新股/退市变化时执行周维护"},
                {"api_name": "dc_member", "reason": "板块成分超过 TTL 时执行周维护"},
            ]
        return []

    @staticmethod
    def _next_actions_for_mode(mode: str) -> list[dict[str, Any]]:
        if mode == "daily_fast":
            return [
                {"mode": "gap_repair", "label": "补齐缺口", "enabled": False},
                {"mode": "weekly_maintenance", "label": "执行周维护", "enabled": False},
                {"mode": "full_initialize", "label": "完整初始化", "enabled": True},
            ]
        if mode == "gap_repair":
            return [{"mode": "daily_fast", "label": "重新检查每日快速", "enabled": True}]
        return [{"mode": "daily_fast", "label": "回到每日快速", "enabled": True}]

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        if mode in FULL_MODE_ALIASES:
            return "full_initialize"
        if mode in PLAN_MODES:
            return mode
        raise ValueError(f"未知工作流模式：{mode}")

    @staticmethod
    def _normalize_date_range(date_range: dict[str, str] | None) -> dict[str, str]:
        if not date_range:
            today = datetime.now(SH_TZ).strftime("%Y%m%d")
            return {"start_date": today, "end_date": today}
        start_date = str(date_range.get("start_date", "")).replace("-", "")
        end_date = str(date_range.get("end_date", "")).replace("-", "")
        if not DATE_RE.match(start_date) or not DATE_RE.match(end_date):
            raise ValueError("日期格式错误，应为 YYYYMMDD")
        if start_date > end_date:
            raise ValueError("起始日期不能晚于结束日期")
        return {"start_date": start_date, "end_date": end_date}

    def _missing_token_tiers(self, definition: WorkflowDefinition) -> list[str]:
        token_map = {
            TokenTier.BASIC.value: bool(settings.tushare_token_basic or settings.tushare_api_token),
            TokenTier.ADVANCED.value: bool(settings.tushare_token_advanced or settings.tushare_api_token),
            TokenTier.PREMIUM.value: bool(settings.tushare_token_premium or settings.tushare_api_token),
            TokenTier.SPECIAL.value: bool(settings.tushare_token_special or settings.tushare_api_token),
        }
        return [tier for tier in definition.required_token_tiers if not token_map.get(tier, False)]

    async def _get_state(self, workflow_task_id: str) -> dict | None:
        raw = await cache_get(f"{WORKFLOW_STATE_PREFIX}{workflow_task_id}")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def _get_state_obj(self, workflow_task_id: str) -> WorkflowRunState | None:
        data = await self._get_state(workflow_task_id)
        if data and "options" not in data:
            data["options"] = {}
        if data:
            data.setdefault("skip_steps", [])
            data.setdefault("maintenance_suggestions", [])
            data.setdefault("estimated_cost", {})
            data.setdefault("actual_cost", {})
            data.setdefault("next_actions", [])
            data.setdefault("target_trade_date", None)
        return WorkflowRunState(**data) if data else None

    async def _set_state(self, state: WorkflowRunState) -> None:
        await cache_set(
            f"{WORKFLOW_STATE_PREFIX}{state.workflow_task_id}",
            json.dumps(asdict(state), ensure_ascii=False, default=str),
            ex=WORKFLOW_TTL,
        )

    @staticmethod
    def _touch_state(state: WorkflowRunState) -> None:
        state.updated_at = datetime.now(SH_TZ).isoformat()

    async def _stop_requested(self, workflow_task_id: str) -> bool:
        return bool(await cache_get(f"{WORKFLOW_STOP_PREFIX}{workflow_task_id}"))

    async def _pause_requested(self, workflow_task_id: str) -> bool:
        return bool(await cache_get(f"{WORKFLOW_PAUSE_PREFIX}{workflow_task_id}"))

    async def _finalize_paused(self, state: WorkflowRunState) -> dict:
        state.status = "paused"
        state.error_message = "用户手动暂停"
        self._touch_state(state)
        await self._set_state(state)
        await cache_delete(WORKFLOW_RUNNING_KEY)
        return asdict(state)

    async def _finalize_stopped(self, state: WorkflowRunState) -> dict:
        state.status = "stopped"
        state.error_message = "用户手动停止"
        self._touch_state(state)
        await self._set_state(state)
        await cache_delete(WORKFLOW_RUNNING_KEY)
        return asdict(state)

    async def _merge_child_progress(self, state: dict[str, Any]) -> dict[str, Any]:
        for child in state.get("child_tasks", []):
            if child.get("status") not in {"running", "pending"}:
                continue
            task_id = child.get("task_id")
            if not task_id:
                continue
            raw = await cache_get(f"{IMPORT_PROGRESS_PREFIX}{task_id}")
            if not raw:
                continue
            try:
                progress = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            child["progress"] = {
                "total": int(progress.get("total") or 0),
                "completed": int(progress.get("completed") or 0),
                "failed": int(progress.get("failed") or 0),
                "status": progress.get("status", child.get("status")),
                "current_item": progress.get("current_item", ""),
                "error_message": progress.get("error_message", ""),
                "batch_mode": progress.get("batch_mode", ""),
                "updated_at": progress.get("updated_at", ""),
            }
        return state

    async def _mark_state_failed(
        self,
        state: WorkflowRunState,
        error_message: str,
        stale_child: bool,
    ) -> None:
        state.status = "failed"
        state.error_message = error_message
        for child in reversed(state.child_tasks):
            if child.get("status") not in {"running", "pending"}:
                continue
            child["status"] = "stale_failed" if stale_child else "failed"
            child["error_message"] = error_message
            child["finished_at"] = datetime.now(SH_TZ).isoformat()
            task_id = child.get("task_id")
            api_name = child.get("api_name")
            if task_id:
                await self._mark_import_log_failed(str(task_id), error_message, stale_child)
                raw = await cache_get(f"{IMPORT_PROGRESS_PREFIX}{task_id}")
                progress: dict[str, Any] = {}
                if raw:
                    try:
                        progress = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        progress = {}
                progress.update({
                    "status": "stale_failed" if stale_child else "failed",
                    "error_message": error_message,
                })
                await cache_set(
                    f"{IMPORT_PROGRESS_PREFIX}{task_id}",
                    json.dumps(progress, ensure_ascii=False),
                    ex=WORKFLOW_TTL,
                )
            if api_name:
                await self._delete_import_lock_if_matches(str(api_name), str(task_id) if task_id else None)
            break
        state.completed_steps = self._count_children(state, "completed")
        state.failed_steps = self._count_children(state, "failed") + self._count_children(state, "stale_failed")
        state.actual_cost = self._build_actual_cost(state)
        self._touch_state(state)
        await self._set_state(state)
        await cache_delete(WORKFLOW_RUNNING_KEY)

    async def _mark_import_log_failed(self, task_id: str, error_message: str, stale: bool) -> None:
        async with AsyncSessionPG() as session:
            await session.execute(
                update(TushareImportLog)
                .where(TushareImportLog.celery_task_id == task_id)
                .where(TushareImportLog.status.in_(["pending", "running"]))
                .values(
                    status="failed",
                    error_message=(f"{'[stale] ' if stale else ''}{error_message}")[:1000],
                    finished_at=datetime.utcnow(),
                )
            )
            await session.commit()

    async def _delete_import_lock_if_matches(self, api_name: str, task_id: str | None) -> None:
        lock_key = f"{IMPORT_LOCK_PREFIX}{api_name}"
        current = await cache_get(lock_key)
        if task_id is None or current == task_id:
            await cache_delete(lock_key)

    async def _release_stale_import_lock(self, api_name: str, locked_task_id: str) -> bool:
        raw = await cache_get(f"{IMPORT_PROGRESS_PREFIX}{locked_task_id}")
        if await self._is_import_task_active(locked_task_id):
            return False

        message = f"{STALE_RUNNING_MESSAGE}：{api_name}"
        await self._mark_import_log_failed(locked_task_id, message, stale=True)
        progress: dict[str, Any] = {}
        if raw:
            try:
                progress = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                progress = {}
        progress.update({"status": "stale_failed", "error_message": message})
        await cache_set(f"{IMPORT_PROGRESS_PREFIX}{locked_task_id}", json.dumps(progress, ensure_ascii=False), ex=WORKFLOW_TTL)
        await self._delete_import_lock_if_matches(api_name, locked_task_id)
        logger.warning("释放 stale Tushare 导入锁 api=%s task_id=%s", api_name, locked_task_id)
        return True

    async def _is_import_task_active(self, task_id: str) -> bool:
        running_workflow_id = await cache_get(WORKFLOW_RUNNING_KEY)
        if running_workflow_id:
            running_state = await self._get_state(running_workflow_id)
            for child in (running_state.get("child_tasks", []) if running_state else []):
                if child.get("task_id") == task_id and child.get("status") in {"running", "pending"}:
                    return await self._celery_task_exists(str(running_workflow_id))
        return await self._celery_task_exists(task_id)

    async def _celery_task_exists(self, task_id: str) -> bool:
        try:
            from app.core.celery_app import celery_app

            inspector = celery_app.control.inspect(timeout=1)
            snapshots = [
                inspector.active() or {},
                inspector.reserved() or {},
                inspector.scheduled() or {},
            ]
            for snapshot in snapshots:
                for tasks in snapshot.values():
                    for task in tasks:
                        request = task.get("request", task)
                        if request.get("id") == task_id:
                            return True
        except Exception as exc:
            logger.debug("检查 Celery active 任务失败 task_id=%s: %s", task_id, exc)
            return True
        return False

    @staticmethod
    def _count_children(state: WorkflowRunState, status: str) -> int:
        return sum(1 for child in state.child_tasks if child.get("status") == status)

    @staticmethod
    def _build_actual_cost(state: WorkflowRunState) -> dict[str, Any]:
        rankings: list[dict[str, Any]] = []
        total_seconds = 0.0
        for child in state.child_tasks:
            started_at = child.get("started_at")
            finished_at = child.get("finished_at")
            if not started_at or not finished_at:
                continue
            try:
                start = datetime.fromisoformat(str(started_at))
                finish = datetime.fromisoformat(str(finished_at))
            except ValueError:
                continue
            seconds = max(0.0, (finish - start).total_seconds())
            total_seconds += seconds
            rankings.append({
                "api_name": child.get("api_name"),
                "status": child.get("status"),
                "duration_seconds": round(seconds, 3),
                "record_count": child.get("record_count", 0),
            })
        rankings.sort(key=lambda item: item["duration_seconds"], reverse=True)
        return {
            "total_duration_seconds": round(total_seconds, 3),
            "slowest_steps": rankings[:10],
        }

    @staticmethod
    def _lightweight_readiness_from_plan(state: WorkflowRunState) -> dict[str, Any]:
        checks = {
            item.get("api_name"): {
                "ok": True,
                "latest_date": item.get("latest_date"),
                "coverage_count": item.get("coverage_count"),
                "import_record_count": item.get("import_record_count"),
                "source": "import_log_plan",
            }
            for item in state.skip_steps
            if item.get("latest_date") and item.get("source") == "import_log"
        }
        return {
            "generated_at": datetime.now(SH_TZ).isoformat(),
            "checks": checks,
            "missing_key_groups": [],
            "recommendations": [],
            "dependency_summary": {},
            "compatibility_warnings": [],
            "message": "每日快速计划接口均已覆盖，未执行导入，基于导入日志完成轻量检查。",
        }

    async def _daily_fast_lightweight_readiness(self, state: WorkflowRunState) -> dict[str, Any]:
        """每日快速/缺口补导收尾只校验关键目标日覆盖，避免扫描大表。"""
        target_date = state.target_trade_date or state.date_range.get("end_date")
        if not target_date:
            return self._lightweight_readiness_from_plan(state)

        freshness = await self._check_daily_fast_freshness(str(target_date))
        checks = {
            api_name: {
                "ok": bool(summary.get("covered")),
                "latest_date": summary.get("latest_date"),
                "coverage_count": summary.get("coverage_count"),
                "import_record_count": summary.get("import_record_count"),
                "source": summary.get("source"),
                "diagnosis": summary.get("diagnosis"),
            }
            for api_name, summary in freshness.items()
        }
        missing = [
            api_name
            for api_name, summary in freshness.items()
            if api_name in DAILY_FAST_FRESHNESS_APIS and not summary.get("covered")
        ]
        return {
            "generated_at": datetime.now(SH_TZ).isoformat(),
            "checks": checks,
            "missing_key_groups": missing,
            "recommendations": [
                f"{api_name} 目标交易日覆盖不足，建议执行缺口补导" for api_name in missing
            ],
            "dependency_summary": {},
            "compatibility_warnings": [],
            "message": "每日快速/缺口补导已完成轻量覆盖检查，板块行情以 sector_kline 实表为准。",
        }

    @staticmethod
    def _child_completed(state: WorkflowRunState, api_name: str) -> bool:
        return any(
            child.get("api_name") == api_name and child.get("status") == "completed"
            for child in state.child_tasks
        )

    async def _table_summary(
        self,
        session: Any,
        table_name: str,
        date_column: str | None,
        count_column: str,
        where_clause: str | None = None,
    ) -> dict[str, Any]:
        where_sql = f" WHERE {where_clause}" if where_clause else ""
        date_expr = f"MAX({date_column}) AS latest_date," if date_column else "NULL AS latest_date,"
        sql = text(
            f"SELECT {date_expr} COUNT(DISTINCT {count_column}) AS coverage_count "
            f"FROM {table_name}{where_sql}"
        )
        try:
            result = await session.execute(sql)
            row = result.mappings().first()
            latest = row["latest_date"] if row else None
            count = row["coverage_count"] if row else 0
            return {
                "ok": bool(count),
                "latest_date": str(latest) if latest is not None else None,
                "coverage_count": int(count or 0),
            }
        except Exception as exc:
            logger.debug("完整性检查失败 table=%s: %s", table_name, exc)
            return {
                "ok": False,
                "latest_date": None,
                "coverage_count": 0,
                "error_message": str(exc)[:200],
            }
