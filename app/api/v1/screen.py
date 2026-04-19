"""
选股 API

- POST /screen/run          — 执行选股
- GET  /screen/results       — 查询选股结果
- GET  /screen/export        — 导出选股结果
- GET  /screen/schedule      — 盘后选股调度状态
- POST /screen/backtest      — 选股结果到回测闭环（需求 11）
- CRUD /strategies           — 策略模板管理
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS, get_pg_session
from app.core.redis_client import cache_get, cache_set, get_redis
from app.core.schemas import ScreenType, StrategyConfig
from app.models.strategy import StrategyTemplate
from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    FactorMeta,
    get_factors_by_category,
)
from app.services.screener.screen_data_provider import ScreenDataProvider
from app.services.screener.screen_executor import ScreenExecutor
from app.services.screener.strategy_examples import STRATEGY_EXAMPLES

router = APIRouter(tags=["选股"])

logger = logging.getLogger(__name__)

# Placeholder user_id (real auth would inject this)
_DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

# 数据源代码 → API 字段名映射（需求 9）
_SOURCE_TO_API_KEY = {"DC": "eastmoney", "TI": "tonghuashun", "TDX": "tongdaxin"}


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


class SectorScreenConfigIn(BaseModel):
    sector_data_source: str = "DC"
    sector_type: str = "CONCEPT"
    sector_period: int = 5
    sector_top_n: int = 30


class StrategyConfigIn(BaseModel):
    factors: list[FactorConditionIn] = Field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"
    weights: dict[str, float] = Field(default_factory=dict)
    ma_periods: list[int] = Field(default_factory=lambda: [5, 10, 20, 60, 120, 250])
    indicator_params: IndicatorParamsConfigIn = Field(default_factory=IndicatorParamsConfigIn)
    ma_trend: MaTrendConfigIn = Field(default_factory=MaTrendConfigIn)
    breakout: BreakoutConfigIn = Field(default_factory=BreakoutConfigIn)
    volume_price: VolumePriceConfigIn = Field(default_factory=VolumePriceConfigIn)
    sector_config: SectorScreenConfigIn = Field(default_factory=SectorScreenConfigIn)


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
# 内置策略模板（系统预置，首次启动时 seed 到数据库）
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "均线趋势选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["ma_trend"],
        "config": {
            "factors": [], "logic": "AND", "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {"ma_periods": [5, 10, 20, 60, 120], "slope_threshold": 0.0,
                         "trend_score_threshold": 80, "support_ma_lines": [20, 60]},
            "indicator_params": {}, "breakout": {}, "volume_price": {},
        },
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "MACD+RSI 技术信号",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["indicator_params"],
        "config": {
            "factors": [], "logic": "AND", "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {},
            "indicator_params": {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
                                 "rsi_period": 14, "rsi_lower": 50, "rsi_upper": 80,
                                 "boll_period": 20, "boll_std_dev": 2.0,
                                 "dma_short": 10, "dma_long": 50},
            "breakout": {}, "volume_price": {},
        },
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "name": "形态突破选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["breakout"],
        "config": {
            "factors": [], "logic": "AND", "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {}, "indicator_params": {},
            "breakout": {"box_breakout": True, "high_breakout": True,
                         "trendline_breakout": True, "volume_ratio_threshold": 1.5,
                         "confirm_days": 1},
            "volume_price": {},
        },
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "name": "多模块联合选股",
        "is_active": False,
        "is_builtin": True,
        "enabled_modules": ["ma_trend", "indicator_params", "breakout"],
        "config": {
            "factors": [], "logic": "AND", "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {"ma_periods": [5, 10, 20, 60, 120], "slope_threshold": 0.0,
                         "trend_score_threshold": 80, "support_ma_lines": [20, 60]},
            "indicator_params": {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
                                 "boll_period": 20, "boll_std_dev": 2.0,
                                 "rsi_period": 14, "rsi_lower": 50, "rsi_upper": 80,
                                 "dma_short": 10, "dma_long": 50},
            "breakout": {"box_breakout": True, "high_breakout": True,
                         "trendline_breakout": True, "volume_ratio_threshold": 1.5,
                         "confirm_days": 1},
            "volume_price": {},
        },
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
            "logic": "AND", "weights": {},
            "ma_periods": [5, 10, 20, 60, 120, 250],
            "ma_trend": {"ma_periods": [5, 10, 20, 60, 120], "slope_threshold": 0.0,
                         "trend_score_threshold": 80, "support_ma_lines": [20, 60]},
            "indicator_params": {}, "breakout": {}, "volume_price": {},
        },
    },
]


def _strategy_to_dict(s: StrategyTemplate) -> dict:
    """将 ORM 对象转为 API 响应 dict。"""
    return {
        "id": str(s.id),
        "name": s.name or "",
        "config": s.config or {},
        "is_active": s.is_active,
        "is_builtin": s.is_builtin,
        "enabled_modules": s.enabled_modules or [],
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


async def _seed_builtin_templates(session: AsyncSession) -> None:
    """将内置策略模板写入数据库（仅在尚未存在时）。"""
    for tpl in _BUILTIN_TEMPLATES:
        existing = await session.execute(
            select(StrategyTemplate).where(StrategyTemplate.id == UUID(tpl["id"]))
        )
        if existing.scalar_one_or_none() is None:
            entry = StrategyTemplate(
                id=UUID(tpl["id"]),
                user_id=_DEFAULT_USER_ID,
                name=tpl["name"],
                config=tpl["config"],
                is_active=tpl["is_active"],
                is_builtin=tpl["is_builtin"],
                enabled_modules=tpl["enabled_modules"],
            )
            session.add(entry)
    await session.flush()


@router.on_event("startup")
async def _startup_seed_strategies():
    """服务启动时将内置策略模板 seed 到数据库。"""
    try:
        async with AsyncSessionPG() as session:
            await _seed_builtin_templates(session)
            await session.commit()
    except Exception:
        logger.warning("内置策略模板 seed 失败（数据库可能未就绪）", exc_info=True)


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
    if now.tzinfo is None:
        now = now.replace(tzinfo=_CST)
    else:
        now = now.astimezone(_CST)
    candidate = now.replace(hour=_EOD_HOUR, minute=_EOD_MINUTE, second=0, microsecond=0)
    if now < candidate and candidate.weekday() < 5:
        return candidate
    candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.replace(hour=_EOD_HOUR, minute=_EOD_MINUTE, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# 选股执行
# ---------------------------------------------------------------------------


@router.post("/screen/run")
async def run_screen(body: ScreenRunRequest) -> dict:
    """执行选股（盘后/实时）。"""
    strategy_id_str: str | None = None
    config_dict: dict | None = None
    enabled_modules: list[str] | None = None

    if body.strategy_id is not None:
        sid = body.strategy_id
        async with AsyncSessionPG() as session:
            result = await session.execute(
                select(StrategyTemplate).where(StrategyTemplate.id == sid)
            )
            strategy = result.scalar_one_or_none()
        if strategy is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        strategy_id_str = str(sid)
        config_dict = strategy.config or {}
        enabled_modules = strategy.enabled_modules or []
    elif body.strategy_config is not None:
        strategy_id_str = str(uuid4())
        config_dict = body.strategy_config.model_dump()
        enabled_modules = None
    else:
        return {
            "strategy_id": str(uuid4()),
            "screen_type": body.screen_type,
            "screen_time": datetime.now().isoformat(),
            "items": [],
            "is_complete": True,
        }

    strategy_config = StrategyConfig.from_dict(config_dict)

    logger.info(
        "选股请求: strategy_id=%s, enabled_modules=%s, factors=%d",
        strategy_id_str, enabled_modules, len(strategy_config.factors),
    )

    async with AsyncSessionPG() as pg_session, AsyncSessionTS() as ts_session:
        provider = ScreenDataProvider(
            pg_session=pg_session, ts_session=ts_session, strategy_config=config_dict,
        )
        stocks_data = await provider.load_screen_data()

    logger.info("数据加载完成: stocks_data 共 %d 只股票", len(stocks_data))

    if stocks_data:
        sample_sym = next(iter(stocks_data))
        sample_data = stocks_data[sample_sym]
        derived_keys = ["ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout",
                        "turnover_check", "money_flow", "large_order"]
        sample_factors = {k: sample_data.get(k, "MISSING") for k in derived_keys}
        logger.info("抽样股票 %s 派生因子: %s, bars数量(closes): %d",
                     sample_sym, sample_factors, len(sample_data.get("closes", [])))

    if not stocks_data:
        return {
            "strategy_id": strategy_id_str,
            "screen_type": body.screen_type,
            "screen_time": datetime.now().isoformat(),
            "items": [],
            "is_complete": True,
        }

    executor = ScreenExecutor(
        strategy_config=strategy_config, strategy_id=strategy_id_str,
        enabled_modules=enabled_modules, raw_config=config_dict,
    )

    screen_type = ScreenType(body.screen_type)
    if screen_type == ScreenType.EOD:
        result = executor.run_eod_screen(stocks_data)
    else:
        result = executor.run_realtime_screen(stocks_data)

    logger.info("选股完成: 共 %d 只股票入选", len(result.items))

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
                        "strength": s.strength.value,
                        "freshness": s.freshness.value,
                        "description": s.description,
                    }
                    for s in item.signals
                ],
                "has_fake_breakout": item.has_fake_breakout,
                "sector_classifications": {
                    _SOURCE_TO_API_KEY[src]: names
                    for src, names in stocks_data.get(item.symbol, {})
                        .get("sector_classifications", {"DC": [], "TI": [], "TDX": []})
                        .items()
                    if src in _SOURCE_TO_API_KEY
                },
                "screen_time": screen_time_str,
            }
            for item in result.items
        ],
        "is_complete": result.is_complete,
    }

    cache_key = f"screen:results:{strategy_id_str}"
    await cache_set(cache_key, json.dumps(response), ex=86400)
    await cache_set("screen:results:latest", json.dumps(response), ex=86400)

    return response


@router.get("/screen/results")
async def get_screen_results(
    strategy_id: UUID | None = Query(None),
    screen_type: str | None = Query(None),
    sort_by: str = Query("trend_score"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
) -> dict:
    """查询选股结果（从 Redis 缓存读取）。"""
    cache_key = f"screen:results:{strategy_id}" if strategy_id else "screen:results:latest"
    raw = await cache_get(cache_key)
    if not raw:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    data = json.loads(raw)
    all_items = data.get("items", [])

    if screen_type and data.get("screen_type") != screen_type:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    _RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    reverse = sort_dir.lower() != "asc"
    if sort_by == "risk_level":
        all_items.sort(key=lambda x: _RISK_ORDER.get(x.get("risk_level", "HIGH"), 2), reverse=reverse)
    elif sort_by in ("trend_score", "ref_buy_price"):
        all_items.sort(key=lambda x: float(x.get(sort_by, 0) or 0), reverse=reverse)
    elif sort_by == "symbol":
        all_items.sort(key=lambda x: x.get("symbol", ""), reverse=reverse)

    total = len(all_items)
    start = (page - 1) * page_size
    paged_items = all_items[start:start + page_size]

    return {
        "total": total, "page": page, "page_size": page_size, "items": paged_items,
        "strategy_id": data.get("strategy_id"), "screen_type": data.get("screen_type"),
        "screen_time": data.get("screen_time"),
    }


@router.get("/screen/export")
async def export_screen_results(
    strategy_id: UUID | None = Query(None),
    format: str = Query("xlsx"),
) -> dict:
    """导出选股结果（stub）。"""
    return {"download_url": f"/api/v1/screen/export/file?format={format}", "status": "pending"}


# ---------------------------------------------------------------------------
# 选股结果到回测闭环（需求 11）
# ---------------------------------------------------------------------------


class ScreenToBacktestRequest(BaseModel):
    """选股结果到回测请求模型（需求 11）"""
    screen_result_id: str = Field(..., description="选股结果 ID（strategy_id 或 'latest'）")
    start_date: date | None = Field(None, description="回测起始日期，默认使用选股时间")
    end_date: date | None = Field(None, description="回测结束日期")
    initial_capital: float = Field(1_000_000.0, gt=0, description="初始资金")


@router.post("/screen/backtest", status_code=202)
async def screen_to_backtest(body: ScreenToBacktestRequest) -> dict:
    """将选股结果一键发送到回测引擎进行历史验证（需求 11）。

    从 Redis 缓存中读取选股结果，提取策略配置和股票列表，
    构造 BacktestConfig 并提交 Celery 回测任务。
    """
    from app.tasks.backtest import run_backtest_task

    # 1. 从 Redis 读取选股结果
    cache_key = f"screen:results:{body.screen_result_id}"
    raw = await cache_get(cache_key)
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"选股结果不存在或已过期: {body.screen_result_id}",
        )

    try:
        screen_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=404,
            detail=f"选股结果数据损坏: {body.screen_result_id}",
        )

    # 2. 提取选股结果中的关键信息
    items = screen_data.get("items", [])
    strategy_id = screen_data.get("strategy_id")
    screen_time_str = screen_data.get("screen_time")

    # 3. 确定回测起始日期（默认使用选股时间）
    if body.start_date is not None:
        start_date = body.start_date
    elif screen_time_str:
        try:
            screen_dt = datetime.fromisoformat(screen_time_str)
            start_date = screen_dt.date()
        except (ValueError, TypeError):
            start_date = date.today()
    else:
        start_date = date.today()

    # 4. 确定回测结束日期（默认为今天）
    end_date = body.end_date if body.end_date is not None else date.today()

    # 5. 提交回测任务
    run_id = str(uuid4())
    run_backtest_task.delay(
        run_id=run_id,
        strategy_id=strategy_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        initial_capital=body.initial_capital,
    )

    return {
        "backtest_id": run_id,
        "screen_result_id": body.screen_result_id,
        "strategy_id": strategy_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "initial_capital": body.initial_capital,
        "stock_count": len(items),
        "status": "PENDING",
        "message": "回测任务已提交，可通过回测 API 查询进度和结果",
    }


@router.get("/screen/schedule", response_model=EodScheduleStatus)
async def get_eod_schedule_status(redis: Redis = Depends(get_redis)) -> EodScheduleStatus:
    """查询盘后选股调度状态。"""
    now = datetime.now(tz=_CST)
    next_run_at = _next_weekday_1530(now)
    last_run_at = last_run_duration_ms = last_run_result_count = None

    raw = await redis.get(_REDIS_KEY)
    if raw:
        try:
            data = json.loads(raw)
            if run_at_str := data.get("run_at"):
                last_run_at = datetime.fromisoformat(run_at_str)
            last_run_duration_ms = data.get("duration_ms")
            last_run_result_count = data.get("result_count")
        except (json.JSONDecodeError, ValueError):
            pass

    return EodScheduleStatus(
        next_run_at=next_run_at, last_run_at=last_run_at,
        last_run_duration_ms=last_run_duration_ms, last_run_result_count=last_run_result_count,
    )


# ---------------------------------------------------------------------------
# 因子注册表 & 策略示例 API
# ---------------------------------------------------------------------------


def _factor_meta_to_dict(meta: FactorMeta) -> dict:
    """将 FactorMeta 数据类序列化为 JSON 兼容的 dict。"""
    return {
        "factor_name": meta.factor_name,
        "label": meta.label,
        "category": meta.category.value,
        "threshold_type": meta.threshold_type.value,
        "default_threshold": meta.default_threshold,
        "value_min": meta.value_min,
        "value_max": meta.value_max,
        "unit": meta.unit,
        "description": meta.description,
        "examples": meta.examples,
        "default_range": list(meta.default_range) if meta.default_range else None,
    }


@router.get("/screen/factor-registry")
async def get_factor_registry(
    category: str | None = Query(None, description="按类别筛选：technical/money_flow/fundamental/sector"),
) -> dict:
    """返回因子元数据注册表。"""
    if category is not None:
        # 验证 category 是否为有效的 FactorCategory 值
        try:
            cat_enum = FactorCategory(category)
        except ValueError:
            return {}
        factors = get_factors_by_category(cat_enum)
        return {category: [_factor_meta_to_dict(m) for m in factors]}

    # 无 category 参数时，返回所有因子按类别分组
    result: dict[str, list[dict]] = {}
    for cat in FactorCategory:
        factors = get_factors_by_category(cat)
        result[cat.value] = [_factor_meta_to_dict(m) for m in factors]
    return result


@router.get("/screen/strategy-examples")
async def get_strategy_examples() -> list[dict]:
    """返回策略示例库。"""
    return [
        {
            "name": ex.name,
            "description": ex.description,
            "factors": ex.factors,
            "logic": ex.logic,
            "weights": ex.weights,
            "enabled_modules": ex.enabled_modules,
            "sector_config": ex.sector_config,
        }
        for ex in STRATEGY_EXAMPLES
    ]


# ---------------------------------------------------------------------------
# 策略模板 CRUD（PostgreSQL 持久化）
# ---------------------------------------------------------------------------


@router.get("/strategies")
async def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> list:
    """查询当前用户的策略模板列表。"""
    try:
        stmt = (
            select(StrategyTemplate)
            .where(StrategyTemplate.user_id == _DEFAULT_USER_ID)
            .order_by(StrategyTemplate.created_at.desc())
        )
        result = await pg_session.execute(stmt)
        rows = result.scalars().all()
        return [_strategy_to_dict(s) for s in rows]
    except Exception:
        logger.warning("数据库查询策略列表失败，返回内置模板", exc_info=True)
        return [
            {
                "id": tpl["id"],
                "name": tpl["name"],
                "config": tpl["config"],
                "is_active": tpl["is_active"],
                "is_builtin": tpl["is_builtin"],
                "enabled_modules": tpl["enabled_modules"],
                "created_at": "2026-01-01T00:00:00",
            }
            for tpl in _BUILTIN_TEMPLATES
        ]


@router.post("/strategies", status_code=201)
async def create_strategy(
    body: StrategyTemplateIn,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """创建策略模板。"""
    try:
        entry = StrategyTemplate(
            user_id=_DEFAULT_USER_ID,
            name=body.name,
            config=body.config.model_dump(),
            is_active=body.is_active,
            is_builtin=False,
            enabled_modules=body.enabled_modules,
        )
        pg_session.add(entry)
        await pg_session.flush()
        return _strategy_to_dict(entry)
    except Exception:
        logger.warning("数据库创建策略失败", exc_info=True)
        raise HTTPException(status_code=503, detail="数据库暂时不可用，请稍后重试")


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """查询单个策略模板详情。"""
    result = await pg_session.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == strategy_id)
    )
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    return _strategy_to_dict(s)


@router.put("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: UUID,
    body: StrategyTemplateUpdate,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """更新策略模板。"""
    result = await pg_session.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == strategy_id)
    )
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    if body.name is not None:
        s.name = body.name
    if body.config is not None:
        s.config = body.config.model_dump()
    if body.is_active is not None:
        s.is_active = body.is_active
    if body.enabled_modules is not None:
        s.enabled_modules = body.enabled_modules
    s.updated_at = datetime.now()
    await pg_session.flush()
    return _strategy_to_dict(s)


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """删除策略模板（内置模板不可删除）。"""
    result = await pg_session.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == strategy_id)
    )
    s = result.scalar_one_or_none()
    if s is not None:
        if s.is_builtin:
            raise HTTPException(status_code=400, detail="内置策略模板不可删除")
        await pg_session.delete(s)
        await pg_session.flush()
    return {"id": str(strategy_id), "deleted": True}


@router.post("/strategies/{strategy_id}/activate")
async def activate_strategy(
    strategy_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """激活指定策略模板（将其他策略设为非激活）。"""
    # 先将所有策略设为非激活
    await pg_session.execute(
        sa_update(StrategyTemplate)
        .where(StrategyTemplate.user_id == _DEFAULT_USER_ID)
        .values(is_active=False)
    )
    # 激活目标策略
    result = await pg_session.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == strategy_id)
    )
    s = result.scalar_one_or_none()
    if s is not None:
        s.is_active = True
        await pg_session.flush()
    return {"id": str(strategy_id), "is_active": True}
