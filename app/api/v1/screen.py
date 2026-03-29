"""
选股 API

- POST /screen/run          — 执行选股
- GET  /screen/results       — 查询选股结果
- GET  /screen/export        — 导出选股结果
- GET  /screen/schedule      — 盘后选股调度状态
- CRUD /strategies           — 策略模板管理
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.redis_client import get_redis

router = APIRouter(tags=["选股"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class FactorConditionIn(BaseModel):
    factor_name: str
    operator: str
    threshold: float | None = None
    params: dict = Field(default_factory=dict)


class MaTrendConfigIn(BaseModel):
    ma_periods: list[int] = Field(default_factory=lambda: [5, 10, 20, 60, 120])
    slope_threshold: float = 0.0
    trend_score_threshold: int = 80
    support_ma_lines: list[int] = Field(default_factory=lambda: [20, 60])


class IndicatorParamsConfigIn(BaseModel):
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    boll_period: int = 20
    boll_std_dev: float = 2.0
    rsi_period: int = 14
    rsi_lower: int = 50
    rsi_upper: int = 80
    dma_short: int = 10
    dma_long: int = 50


class BreakoutConfigIn(BaseModel):
    box_breakout: bool = True
    high_breakout: bool = True
    trendline_breakout: bool = True
    volume_ratio_threshold: float = 1.5
    confirm_days: int = 1


class VolumePriceConfigIn(BaseModel):
    turnover_rate_min: float = 3.0
    turnover_rate_max: float = 15.0
    main_flow_threshold: float = 1000.0
    main_flow_days: int = 2
    large_order_ratio: float = 30.0
    min_daily_amount: float = 5000.0
    sector_rank_top: int = 30


class StrategyConfigIn(BaseModel):
    factors: list[FactorConditionIn] = Field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"
    weights: dict[str, float] = Field(default_factory=dict)
    ma_periods: list[int] = Field(default_factory=lambda: [5, 10, 20, 60, 120, 250])
    indicator_params: IndicatorParamsConfigIn = Field(default_factory=IndicatorParamsConfigIn)
    ma_trend: MaTrendConfigIn = Field(default_factory=MaTrendConfigIn)
    breakout: BreakoutConfigIn = Field(default_factory=BreakoutConfigIn)
    volume_price: VolumePriceConfigIn = Field(default_factory=VolumePriceConfigIn)


class ScreenRunRequest(BaseModel):
    strategy_id: UUID | None = None
    strategy_config: StrategyConfigIn | None = None
    screen_type: Literal["EOD", "REALTIME"] = "EOD"


class StrategyTemplateIn(BaseModel):
    name: str
    config: StrategyConfigIn
    is_active: bool = False


class StrategyTemplateUpdate(BaseModel):
    name: str | None = None
    config: StrategyConfigIn | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 调度状态模型
# ---------------------------------------------------------------------------


class EodScheduleStatus(BaseModel):
    """盘后选股调度状态（需求 21.14）"""
    next_run_at: datetime = Field(..., description="下一次盘后选股预计执行时间（CST）")
    last_run_at: datetime | None = Field(None, description="最近一次盘后选股执行时间")
    last_run_duration_ms: int | None = Field(None, description="最近一次执行耗时（毫秒）")
    last_run_result_count: int | None = Field(None, description="最近一次选出股票数量")


# ---------------------------------------------------------------------------
# 调度状态辅助函数
# ---------------------------------------------------------------------------

_CST = ZoneInfo("Asia/Shanghai")
_EOD_HOUR = 15
_EOD_MINUTE = 30
_REDIS_KEY = "screen:eod:last_run"


def _next_weekday_1530(now: datetime) -> datetime:
    """计算下一个工作日（周一至周五）15:30 CST 时间。"""
    # 确保 now 带时区
    if now.tzinfo is None:
        now = now.replace(tzinfo=_CST)
    else:
        now = now.astimezone(_CST)

    candidate = now.replace(hour=_EOD_HOUR, minute=_EOD_MINUTE, second=0, microsecond=0)
    # 如果今天还没到 15:30 且是工作日，就是今天
    if now < candidate and candidate.weekday() < 5:
        return candidate
    # 否则找下一个工作日
    candidate += timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=Saturday, 6=Sunday
        candidate += timedelta(days=1)
    return candidate.replace(hour=_EOD_HOUR, minute=_EOD_MINUTE, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# 选股执行
# ---------------------------------------------------------------------------


@router.post("/screen/run")
async def run_screen(body: ScreenRunRequest) -> dict:
    """执行选股（盘后/实时）。"""
    return {
        "strategy_id": str(body.strategy_id or uuid4()),
        "screen_type": body.screen_type,
        "screen_time": datetime.now().isoformat(),
        "items": [],
        "is_complete": True,
    }


@router.get("/screen/results")
async def get_screen_results(
    strategy_id: UUID | None = Query(None),
    screen_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询选股结果。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.get("/screen/export")
async def export_screen_results(
    strategy_id: UUID | None = Query(None),
    format: str = Query("xlsx", description="导出格式: xlsx/csv"),
) -> dict:
    """导出选股结果为 Excel/CSV（stub：返回下载链接占位）。"""
    return {"download_url": f"/api/v1/screen/export/file?format={format}", "status": "pending"}


@router.get("/screen/schedule", response_model=EodScheduleStatus)
async def get_eod_schedule_status(
    redis: Redis = Depends(get_redis),
) -> EodScheduleStatus:
    """查询盘后选股调度状态（需求 21.14）。

    - next_run_at：下一个工作日 15:30 CST
    - last_run_at / last_run_duration_ms / last_run_result_count：从 Redis key
      `screen:eod:last_run` 读取，不存在时返回 null
    """
    now = datetime.now(tz=_CST)
    next_run_at = _next_weekday_1530(now)

    last_run_at: datetime | None = None
    last_run_duration_ms: int | None = None
    last_run_result_count: int | None = None

    raw = await redis.get(_REDIS_KEY)
    if raw:
        try:
            data = json.loads(raw)
            if run_at_str := data.get("run_at"):
                last_run_at = datetime.fromisoformat(run_at_str)
            last_run_duration_ms = data.get("duration_ms")
            last_run_result_count = data.get("result_count")
        except (json.JSONDecodeError, ValueError):
            pass  # 数据损坏时忽略，返回 null

    return EodScheduleStatus(
        next_run_at=next_run_at,
        last_run_at=last_run_at,
        last_run_duration_ms=last_run_duration_ms,
        last_run_result_count=last_run_result_count,
    )


# ---------------------------------------------------------------------------
# 策略模板 CRUD
# ---------------------------------------------------------------------------


@router.get("/strategies")
async def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询当前用户的策略模板列表。"""
    return {"total": 0, "page": page, "page_size": page_size, "items": []}


@router.post("/strategies", status_code=201)
async def create_strategy(body: StrategyTemplateIn) -> dict:
    """创建策略模板。"""
    return {
        "id": str(uuid4()),
        "name": body.name,
        "config": body.config.model_dump(),
        "is_active": body.is_active,
        "created_at": datetime.now().isoformat(),
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: UUID) -> dict:
    """查询单个策略模板详情。"""
    return {"id": str(strategy_id), "name": "stub", "config": {}, "is_active": False}


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: UUID, body: StrategyTemplateUpdate) -> dict:
    """更新策略模板。"""
    return {"id": str(strategy_id), "updated": True}


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: UUID) -> dict:
    """删除策略模板。"""
    return {"id": str(strategy_id), "deleted": True}


@router.post("/strategies/{strategy_id}/activate")
async def activate_strategy(strategy_id: UUID) -> dict:
    """激活指定策略模板（将其他策略设为非激活）。"""
    return {"id": str(strategy_id), "is_active": True}
