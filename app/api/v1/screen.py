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
import logging
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.redis_client import cache_get, cache_set, get_redis
from app.core.schemas import ScreenType, StrategyConfig
from app.services.screener.screen_data_provider import ScreenDataProvider
from app.services.screener.screen_executor import ScreenExecutor

router = APIRouter(tags=["选股"])

logger = logging.getLogger(__name__)


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


class MacdParamsIn(BaseModel):
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


class BollParamsIn(BaseModel):
    period: int = 20
    std_dev: float = 2.0


class RsiParamsIn(BaseModel):
    period: int = 14
    lower_bound: int = 50
    upper_bound: int = 80


class DmaParamsIn(BaseModel):
    short_period: int = 10
    long_period: int = 50


class IndicatorParamsConfigIn(BaseModel):
    macd: MacdParamsIn = Field(default_factory=MacdParamsIn)
    boll: BollParamsIn = Field(default_factory=BollParamsIn)
    rsi: RsiParamsIn = Field(default_factory=RsiParamsIn)
    dma: DmaParamsIn = Field(default_factory=DmaParamsIn)


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


# ---------------------------------------------------------------------------
# 可选配置模块常量（需求 27）
# ---------------------------------------------------------------------------

VALID_MODULES: set[str] = {
    "factor_editor",
    "ma_trend",
    "indicator_params",
    "breakout",
    "volume_price",
}


class StrategyTemplateIn(BaseModel):
    name: str
    config: StrategyConfigIn
    is_active: bool = False
    enabled_modules: list[str] = Field(default_factory=list)


class StrategyTemplateUpdate(BaseModel):
    name: str | None = None
    config: StrategyConfigIn | None = None
    is_active: bool | None = None
    enabled_modules: list[str] | None = None


# ---------------------------------------------------------------------------
# 内存策略存储（开发阶段，后续替换为数据库）
# ---------------------------------------------------------------------------

_strategies: dict[str, dict] = {}  # id -> strategy dict


# ---------------------------------------------------------------------------
# 内置策略模板（系统预置，可编辑）
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "均线趋势选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["ma_trend"],
        "config": {
            "factors": [],
            "logic": "AND",
            "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {
                "ma_periods": [5, 10, 20, 60, 120],
                "slope_threshold": 0.0,
                "trend_score_threshold": 80,
                "support_ma_lines": [20, 60],
            },
            "indicator_params": {},
            "breakout": {},
            "volume_price": {},
        },
        "created_at": "2026-01-01T00:00:00",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "MACD+RSI 技术信号",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["indicator_params"],
        "config": {
            "factors": [],
            "logic": "AND",
            "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {},
            "indicator_params": {
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "rsi_period": 14,
                "rsi_lower": 50,
                "rsi_upper": 80,
                "boll_period": 20,
                "boll_std_dev": 2.0,
                "dma_short": 10,
                "dma_long": 50,
            },
            "breakout": {},
            "volume_price": {},
        },
        "created_at": "2026-01-01T00:00:01",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "name": "形态突破选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["breakout"],
        "config": {
            "factors": [],
            "logic": "AND",
            "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {},
            "indicator_params": {},
            "breakout": {
                "box_breakout": True,
                "high_breakout": True,
                "trendline_breakout": True,
                "volume_ratio_threshold": 1.5,
                "confirm_days": 1,
            },
            "volume_price": {},
        },
        "created_at": "2026-01-01T00:00:02",
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "name": "多模块联合选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["ma_trend", "indicator_params", "breakout"],
        "config": {
            "factors": [],
            "logic": "AND",
            "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {
                "ma_periods": [5, 10, 20, 60, 120],
                "slope_threshold": 0.0,
                "trend_score_threshold": 80,
                "support_ma_lines": [20, 60],
            },
            "indicator_params": {
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "boll_period": 20,
                "boll_std_dev": 2.0,
                "rsi_period": 14,
                "rsi_lower": 50,
                "rsi_upper": 80,
                "dma_short": 10,
                "dma_long": 50,
            },
            "breakout": {
                "box_breakout": True,
                "high_breakout": True,
                "trendline_breakout": True,
                "volume_ratio_threshold": 1.5,
                "confirm_days": 1,
            },
            "volume_price": {},
        },
        "created_at": "2026-01-01T00:00:03",
    },
    {
        "id": "00000000-0000-0000-0000-000000000005",
        "name": "价值成长+趋势",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["factor_editor", "ma_trend"],
        "config": {
            "factors": [
                {"factor_name": "pe_ttm", "operator": "<=", "threshold": 30.0, "params": {}},
                {"factor_name": "roe", "operator": ">=", "threshold": 0.08, "params": {}},
                {"factor_name": "market_cap", "operator": ">=", "threshold": 5000000000.0, "params": {}},
            ],
            "logic": "AND",
            "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {
                "ma_periods": [5, 10, 20, 60, 120],
                "slope_threshold": 0.0,
                "trend_score_threshold": 80,
                "support_ma_lines": [20, 60],
            },
            "indicator_params": {},
            "breakout": {},
            "volume_price": {},
        },
        "created_at": "2026-01-01T00:00:04",
    },
]


def _seed_builtin_templates() -> None:
    """将内置策略模板注入内存存储（仅在尚未存在时）。"""
    for tpl in _BUILTIN_TEMPLATES:
        if tpl["id"] not in _strategies:
            _strategies[tpl["id"]] = dict(tpl)


_seed_builtin_templates()


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
    """
    执行选股（盘后/实时）。

    流程：
    1. 加载策略配置（从 strategy_id 或 strategy_config）
    2. 从本地数据库查询全市场股票数据
    3. 实例化 ScreenExecutor 执行选股
    4. 返回选股结果

    错误处理：
    - strategy_id 不存在 → HTTP 404
    - 本地数据库无行情数据 → 返回空结果（items=[], is_complete=true）
    """
    # 1. 加载策略配置
    strategy_id_str: str | None = None
    config_dict: dict | None = None
    enabled_modules: list[str] | None = None

    if body.strategy_id is not None:
        sid = str(body.strategy_id)
        if sid not in _strategies:
            raise HTTPException(status_code=404, detail="策略不存在")
        strategy = _strategies[sid]
        strategy_id_str = sid
        config_dict = strategy.get("config", {})
        enabled_modules = strategy.get("enabled_modules", [])
    elif body.strategy_config is not None:
        strategy_id_str = str(uuid4())
        config_dict = body.strategy_config.model_dump()
        enabled_modules = None  # 无 strategy_id 时视为全部启用
    else:
        # 既无 strategy_id 也无 strategy_config，返回空结果
        return {
            "strategy_id": str(uuid4()),
            "screen_type": body.screen_type,
            "screen_time": datetime.now().isoformat(),
            "items": [],
            "is_complete": True,
        }

    # 解析策略配置
    strategy_config = StrategyConfig.from_dict(config_dict)

    logger.info(
        "选股请求: strategy_id=%s, enabled_modules=%s, factors=%d",
        strategy_id_str, enabled_modules, len(strategy_config.factors),
    )

    # 2. 从本地数据库查询股票数据
    async with AsyncSessionPG() as pg_session, AsyncSessionTS() as ts_session:
        provider = ScreenDataProvider(
            pg_session=pg_session,
            ts_session=ts_session,
            strategy_config=config_dict,
        )
        stocks_data = await provider.load_screen_data()

    logger.info("数据加载完成: stocks_data 共 %d 只股票", len(stocks_data))

    # 抽样输出第一只股票的因子键，帮助诊断
    if stocks_data:
        sample_sym = next(iter(stocks_data))
        sample_data = stocks_data[sample_sym]
        derived_keys = ["ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout",
                        "turnover_check", "money_flow", "large_order"]
        sample_factors = {k: sample_data.get(k, "MISSING") for k in derived_keys}
        logger.info(
            "抽样股票 %s 派生因子: %s, bars数量(closes): %d",
            sample_sym, sample_factors, len(sample_data.get("closes", [])),
        )

    # 3. 无行情数据时返回空结果（需求 27.12）
    if not stocks_data:
        return {
            "strategy_id": strategy_id_str,
            "screen_type": body.screen_type,
            "screen_time": datetime.now().isoformat(),
            "items": [],
            "is_complete": True,
        }

    # 4. 执行选股
    executor = ScreenExecutor(
        strategy_config=strategy_config,
        strategy_id=strategy_id_str,
        enabled_modules=enabled_modules,
        raw_config=config_dict,
    )

    logger.info(
        "ScreenExecutor 初始化: enabled_modules=%s, factor_editor启用=%s",
        executor._enabled_modules, executor._is_module_enabled("factor_editor"),
    )

    screen_type = ScreenType(body.screen_type)
    if screen_type == ScreenType.EOD:
        result = executor.run_eod_screen(stocks_data)
    else:
        result = executor.run_realtime_screen(stocks_data)

    logger.info(
        "选股完成: 共 %d 只股票入选, screen_type=%s",
        len(result.items), result.screen_type.value,
    )
    if result.items:
        for item in result.items[:3]:
            logger.info(
                "  入选: %s, trend_score=%.1f, signals=%s",
                item.symbol, item.trend_score,
                [(s.category.value, s.label) for s in item.signals],
            )
    else:
        logger.warning("选股结果为空 — 无股票满足筛选条件")

    # 5. 缓存结果到 Redis（供 GET /screen/results 查询）
    screen_time_str = result.screen_time.isoformat()
    response = {
        "strategy_id": str(result.strategy_id),
        "screen_type": result.screen_type.value,
        "screen_time": screen_time_str,
        "items": [
            {
                "symbol": item.symbol,
                "name": stocks_data.get(item.symbol, {}).get("name", item.symbol),
                "ref_buy_price": float(item.ref_buy_price),
                "trend_score": item.trend_score,
                "risk_level": item.risk_level.value,
                "signals": [
                    {
                        "category": s.category.value,
                        "label": s.label,
                        "is_fake_breakout": s.is_fake_breakout,
                    }
                    for s in item.signals
                ],
                "has_fake_breakout": item.has_fake_breakout,
                "screen_time": screen_time_str,
            }
            for item in result.items
        ],
        "is_complete": result.is_complete,
    }

    # 缓存到 Redis，24 小时过期
    cache_key = f"screen:results:{strategy_id_str}"
    await cache_set(cache_key, json.dumps(response), ex=86400)
    # 同时缓存最新一次结果的 key，方便无参查询
    await cache_set("screen:results:latest", json.dumps(response), ex=86400)

    return response


@router.get("/screen/results")
async def get_screen_results(
    strategy_id: UUID | None = Query(None),
    screen_type: str | None = Query(None),
    sort_by: str = Query("trend_score", description="排序字段: trend_score, ref_buy_price, symbol, risk_level"),
    sort_dir: str = Query("desc", description="排序方向: asc, desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
) -> dict:
    """查询选股结果（从 Redis 缓存读取最近一次执行结果）。"""
    # 优先按 strategy_id 查询，否则取最新结果
    if strategy_id:
        cache_key = f"screen:results:{strategy_id}"
    else:
        cache_key = "screen:results:latest"

    raw = await cache_get(cache_key)
    if not raw:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    data = json.loads(raw)
    all_items = data.get("items", [])

    # 按 screen_type 过滤
    if screen_type and data.get("screen_type") != screen_type:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    # 全局排序（分页前）
    _RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    reverse = sort_dir.lower() != "asc"
    if sort_by == "risk_level":
        all_items.sort(key=lambda x: _RISK_ORDER.get(x.get("risk_level", "HIGH"), 2), reverse=reverse)
    elif sort_by in ("trend_score", "ref_buy_price"):
        all_items.sort(key=lambda x: float(x.get(sort_by, 0) or 0), reverse=reverse)
    elif sort_by == "symbol":
        all_items.sort(key=lambda x: x.get("symbol", ""), reverse=reverse)

    # 分页
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = all_items[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": paged_items,
        "strategy_id": data.get("strategy_id"),
        "screen_type": data.get("screen_type"),
        "screen_time": data.get("screen_time"),
    }


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
) -> list:
    """查询当前用户的策略模板列表。"""
    items = sorted(_strategies.values(), key=lambda s: s.get("created_at", ""), reverse=True)
    for item in items:
        item.setdefault("enabled_modules", [])
    return items


@router.post("/strategies", status_code=201)
async def create_strategy(body: StrategyTemplateIn) -> dict:
    """创建策略模板。"""
    sid = str(uuid4())
    strategy = {
        "id": sid,
        "name": body.name,
        "config": body.config.model_dump(),
        "is_active": body.is_active,
        "enabled_modules": body.enabled_modules,
        "created_at": datetime.now().isoformat(),
    }
    _strategies[sid] = strategy
    return strategy


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: UUID) -> dict:
    """查询单个策略模板详情。"""
    sid = str(strategy_id)
    if sid not in _strategies:
        raise HTTPException(status_code=404, detail="策略不存在")
    s = _strategies[sid]
    s.setdefault("enabled_modules", [])
    return s


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: UUID, body: StrategyTemplateUpdate) -> dict:
    """更新策略模板。"""
    sid = str(strategy_id)
    if sid not in _strategies:
        raise HTTPException(status_code=404, detail="策略不存在")
    s = _strategies[sid]
    if body.name is not None:
        s["name"] = body.name
    if body.config is not None:
        s["config"] = body.config.model_dump()
    if body.is_active is not None:
        s["is_active"] = body.is_active
    if body.enabled_modules is not None:
        s["enabled_modules"] = body.enabled_modules
    s.setdefault("enabled_modules", [])
    return s


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: UUID) -> dict:
    """删除策略模板（内置模板不可删除）。"""
    sid = str(strategy_id)
    if sid in _strategies:
        if _strategies[sid].get("is_builtin"):
            raise HTTPException(status_code=400, detail="内置策略模板不可删除")
        del _strategies[sid]
    return {"id": sid, "deleted": True}


@router.post("/strategies/{strategy_id}/activate")
async def activate_strategy(strategy_id: UUID) -> dict:
    """激活指定策略模板（将其他策略设为非激活）。"""
    sid = str(strategy_id)
    for s in _strategies.values():
        s["is_active"] = (s["id"] == sid)
    return {"id": sid, "is_active": True}
