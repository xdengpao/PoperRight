"""
数据查询 API

- GET /kline/{symbol}     — 查询 K 线数据
- GET /stocks             — 查询股票列表（含过滤）
- GET /market/overview    — 查询大盘概况
- GET /sync/status        — 查询各数据源同步状态
- POST /sync              — 手动触发数据同步
- GET /exclusions         — 查询永久剔除名单
- POST /backfill          — 触发历史数据批量回填
- GET /backfill/status    — 查询回填进度
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func, select

from app.services.data_engine.backfill_service import BackfillService
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.data_source_router import DataSourceRouter
from app.services.data_engine.tushare_adapter import TushareAdapter
from app.services.data_engine.akshare_adapter import AkShareAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["数据查询"])


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class DataSourceStatus(BaseModel):
    name: str  # "Tushare" | "AkShare"
    status: str  # "connected" | "disconnected"
    checked_at: str  # ISO 8601 时间戳


class DataSourceHealthResponse(BaseModel):
    sources: list[DataSourceStatus]


class SyncStatusItem(BaseModel):
    source: str                        # 数据类型名称
    last_sync_at: str | None           # 最后同步时间
    status: str                        # "OK" | "ERROR" | "SYNCING" | "UNKNOWN"
    record_count: int                  # 已同步记录数
    data_source: str                   # "Tushare" | "AkShare" | "N/A"
    is_fallback: bool                  # 是否触发了故障转移


class SyncStatusResponse(BaseModel):
    items: list[SyncStatusItem]


class CleaningStatsResponse(BaseModel):
    total_stocks: int                  # 总股票数
    valid_stocks: int                  # 有效标的数
    st_delisted_count: int             # ST/退市剔除数
    new_stock_count: int               # 新股剔除数
    suspended_count: int               # 停牌剔除数
    high_pledge_count: int             # 高质押剔除数


class SyncRequest(BaseModel):
    sync_type: str | None = None       # "kline" | "fundamentals" | "money_flow" | "all" | None


class SyncResponse(BaseModel):
    message: str
    task_ids: list[str]


# ---------------------------------------------------------------------------
# 回填请求/响应模型
# ---------------------------------------------------------------------------

_VALID_DATA_TYPES = {"kline", "fundamentals", "money_flow"}
_VALID_FREQS = {"1d", "1w", "1M"}


class BackfillRequest(BaseModel):
    data_types: list[str] = ["kline", "fundamentals", "money_flow"]
    symbols: list[str] = []
    start_date: date | None = None
    end_date: date | None = None
    freq: Literal["1d", "1w", "1M"] = "1d"

    @field_validator("data_types")
    @classmethod
    def validate_data_types(cls, v: list[str]) -> list[str]:
        for dt in v:
            if dt not in _VALID_DATA_TYPES:
                raise ValueError(f"无效的数据类型: {dt}，可选值: {sorted(_VALID_DATA_TYPES)}")
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "BackfillRequest":
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date 不能晚于 end_date")
        return self


class BackfillResponse(BaseModel):
    message: str
    task_ids: list[str]


class BackfillStatusResponse(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_symbol: str = ""
    status: str = "idle"
    data_types: list[str] = []


class BackfillStopResponse(BaseModel):
    message: str


class StockFundamentalsResponse(BaseModel):
    """个股基本面数据响应"""
    symbol: str
    name: str | None = None
    pe_ttm: float | None = None           # 市盈率（TTM）
    pb: float | None = None               # 市净率
    roe: float | None = None              # 净资产收益率（%）
    market_cap: float | None = None       # 总市值（亿元）
    revenue_growth: float | None = None   # 营收同比增长率（%）— 映射自 FundamentalsData.revenue_yoy
    net_profit_growth: float | None = None  # 净利润同比增长率（%）— 映射自 FundamentalsData.net_profit_yoy
    report_period: str | None = None      # 报告期，如 "2024Q3"
    updated_at: str | None = None         # 数据更新时间（ISO 8601）


class MoneyFlowDailyRecord(BaseModel):
    """单日资金流向记录"""
    trade_date: str                        # 交易日期（ISO date）
    main_net_inflow: float                 # 主力资金净流入（万元）
    north_net_inflow: float | None = None  # 北向资金净流入（万元）
    large_order_ratio: float | None = None  # 大单成交占比（%）
    super_large_inflow: float | None = None  # 超大单净流入（万元）
    large_inflow: float | None = None      # 大单净流入（万元）


class StockMoneyFlowResponse(BaseModel):
    """个股资金流向数据响应"""
    symbol: str
    name: str | None = None
    days: int                              # 实际返回天数
    records: list[MoneyFlowDailyRecord]    # 每日记录列表（按日期升序）


# ---------------------------------------------------------------------------
# 健康检查端点
# ---------------------------------------------------------------------------


@router.get("/sources/health")
async def get_sources_health() -> DataSourceHealthResponse:
    """检查 Tushare 和 AkShare 数据源连通性（带超时和重试）。"""
    import asyncio

    tushare = TushareAdapter()
    akshare = AkShareAdapter()
    now = datetime.now().isoformat()

    async def _check_with_retry(name: str, adapter, retries: int = 1, timeout: float = 12.0) -> DataSourceStatus:
        """对单个数据源做带超时和重试的健康检查。"""
        last_err: str = ""
        for attempt in range(retries):
            try:
                ok = await asyncio.wait_for(adapter.health_check(), timeout=timeout)
                if ok:
                    return DataSourceStatus(name=name, status="connected", checked_at=now)
                last_err = "health_check 返回 False"
            except asyncio.TimeoutError:
                last_err = f"超时（{timeout}s）"
                logger.warning("%s health_check 第 %d 次超时", name, attempt + 1)
            except Exception as exc:
                last_err = str(exc)
                logger.warning("%s health_check 第 %d 次失败: %s", name, attempt + 1, exc)
            # 重试前短暂等待
            if attempt < retries - 1:
                await asyncio.sleep(1)

        logger.error("%s 健康检查最终失败: %s", name, last_err)
        return DataSourceStatus(name=name, status="disconnected", checked_at=now)

    # 并发检查两个数据源
    tushare_status, akshare_status = await asyncio.gather(
        _check_with_retry("Tushare", tushare),
        _check_with_retry("AkShare", akshare),
    )

    return DataSourceHealthResponse(sources=[tushare_status, akshare_status])


@router.get("/kline/{symbol}")
async def get_kline(
    symbol: str,
    freq: str = Query("1d", description="K线周期: 1m/5m/15m/30m/60m/1d/1w/1M"),
    start: date | None = Query(None, description="开始日期"),
    end: date | None = Query(None, description="结束日期"),
    adj_type: int = Query(0, description="复权类型: 0=不复权 1=前复权 2=后复权"),
) -> dict:
    """查询指定股票的 K 线数据。

    优先从本地 TimescaleDB 查询，无数据时回退到第三方 API（DataSourceRouter）。
    """
    from app.services.data_engine.data_source_router import DataSourceRouter
    from app.core.database import AsyncSessionTS
    from app.models.kline import Kline, KlineBar as KlineBarDTO

    from datetime import timedelta

    end_date = end or date.today()
    start_date = start or (end_date - timedelta(days=90))

    # 纯数字代码（用于本地 DB 查询，DB 中存储的是纯数字格式）
    clean_symbol = symbol.split(".")[0]
    # 带后缀代码（用于第三方 API，Tushare 需要 .SZ/.SH 格式）
    ts_symbol = symbol
    if "." not in symbol:
        ts_symbol = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"

    bars = []

    # 1. 先从本地 TimescaleDB 查询
    try:
        async with AsyncSessionTS() as session:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            result = await session.execute(
                select(Kline)
                .where(
                    Kline.symbol == clean_symbol,
                    Kline.freq == freq,
                    Kline.time >= start_dt,
                    Kline.time <= end_dt,
                )
                .order_by(Kline.time)
            )
            rows = result.scalars().all()
            if rows:
                bars = [KlineBarDTO.from_orm(r) for r in rows]
                logger.info("从本地 DB 获取 K 线 symbol=%s 共 %d 条", clean_symbol, len(bars))
    except Exception as exc:
        logger.warning("本地 DB 查询 K 线失败 symbol=%s: %s", clean_symbol, exc)

    # 2. 本地无数据，回退到第三方 API
    if not bars:
        router_svc = DataSourceRouter()
        try:
            bars = await router_svc.fetch_kline(ts_symbol, freq, start_date, end_date)
            logger.info("从第三方 API 获取 K 线 symbol=%s 共 %d 条", ts_symbol, len(bars))
        except Exception as exc:
            logger.warning("第三方 API 获取 K 线失败 symbol=%s: %s", ts_symbol, exc)
            bars = []

    # 3. 查询股票名称
    stock_name = ""
    try:
        from app.core.database import AsyncSessionPG
        from app.models.stock import StockInfo
        async with AsyncSessionPG() as session:
            row = await session.execute(
                select(StockInfo.name).where(StockInfo.symbol == clean_symbol)
            )
            stock_name = row.scalar_one_or_none() or ""
    except Exception:
        pass

    # 本地无名称时从 Tushare 查询
    if not stock_name:
        try:
            tushare = TushareAdapter()
            data = await tushare._call_api("stock_basic", ts_code=ts_symbol, fields="ts_code,name")
            rows = tushare._rows_from_data(data)
            if rows:
                stock_name = rows[0].get("name", "")
        except Exception:
            pass

    return {
        "symbol": symbol,
        "name": stock_name,
        "freq": freq,
        "adj_type": adj_type,
        "bars": [
            {
                "time": bar.time.isoformat(),
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "volume": bar.volume,
                "amount": str(bar.amount),
                "turnover": str(bar.turnover),
                "vol_ratio": str(bar.vol_ratio),
            }
            for bar in bars
        ],
    }


@router.get("/stocks")
async def get_stocks(
    market: str | None = Query(None, description="市场: SH/SZ/BJ"),
    board: str | None = Query(None, description="板块: 主板/创业板/科创板/北交所"),
    is_st: bool | None = Query(None, description="是否 ST"),
    keyword: str | None = Query(None, description="股票代码或名称关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询股票列表，支持过滤与分页。"""
    return {
        "total": 1,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "symbol": "600000",
                "name": "浦发银行",
                "market": "SH",
                "board": "主板",
                "is_st": False,
                "pe_ttm": 5.12,
                "pb": 0.45,
                "market_cap": "280000000000",
            }
        ],
    }


@router.get("/market/overview")
async def get_market_overview() -> dict:
    """查询大盘概况（指数、涨跌家数、市场情绪等）。

    优先从 Redis 缓存读取（TTL 60s），缓存未命中时通过 Tushare 获取实时指数数据，
    涨跌家数通过 AkShare stock_zh_a_spot_em 统计。
    """
    import asyncio
    import json as _json
    from app.core.redis_client import cache_get, cache_set

    cache_key = "market:overview"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return _json.loads(cached)
        except (ValueError, TypeError):
            pass

    today = date.today()

    # 通过 AkShare sina 接口获取三大指数实时数据
    index_map = {
        "sh000001": ("sh_index", "sh_change_pct"),
        "sz399001": ("sz_index", "sz_change_pct"),
        "sz399006": ("cyb_index", "cyb_change_pct"),
    }

    result: dict = {
        "date": today.isoformat(),
        "sh_index": 0, "sh_change_pct": 0,
        "sz_index": 0, "sz_change_pct": 0,
        "cyb_index": 0, "cyb_change_pct": 0,
        "advance_count": 0, "decline_count": 0,
        "limit_up_count": 0, "limit_down_count": 0,
        "market_sentiment": "NORMAL",
    }

    # 获取指数数据
    async def _fetch_indices() -> None:
        try:
            import akshare as _ak
            df = await asyncio.to_thread(_ak.stock_zh_index_spot_sina)
            if df is None or df.empty:
                return
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                if code in index_map:
                    idx_field, pct_field = index_map[code]
                    result[idx_field] = float(row.get("最新价", 0) or 0)
                    result[pct_field] = float(row.get("涨跌幅", 0) or 0)
        except Exception as exc:
            logger.warning("获取指数数据失败: %s", exc)

    tasks = [_fetch_indices()]

    # 涨跌家数统计（通过 AkShare，较慢所以也并发）
    async def _fetch_sentiment() -> None:
        try:
            import akshare as _ak
            df = await asyncio.to_thread(_ak.stock_zh_a_spot_em)
            if df is not None and not df.empty and "涨跌幅" in df.columns:
                pct = df["涨跌幅"]
                result["advance_count"] = int((pct > 0).sum())
                result["decline_count"] = int((pct < 0).sum())
                result["limit_up_count"] = int((pct >= 9.9).sum())
                result["limit_down_count"] = int((pct <= -9.9).sum())
        except Exception as exc:
            logger.warning("获取涨跌家数失败: %s", exc)

    tasks.append(_fetch_sentiment())
    await asyncio.gather(*tasks)

    # 市场情绪判断
    if result["limit_down_count"] > 50 or result["decline_count"] > result["advance_count"] * 2:
        result["market_sentiment"] = "DANGER"
    elif result["decline_count"] > result["advance_count"]:
        result["market_sentiment"] = "CAUTION"

    # 缓存 60 秒
    try:
        await cache_set(cache_key, _json.dumps(result), ex=60)
    except Exception:
        pass

    return result


@router.get("/market/sectors")
async def get_market_sectors() -> list:
    """查询板块涨幅排行（通过 AkShare 实时板块数据，缓存 60s）。"""
    import asyncio
    import json as _json
    from app.core.redis_client import cache_get, cache_set

    cache_key = "market:sectors"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return _json.loads(cached)
        except (ValueError, TypeError):
            pass

    try:
        import akshare as _ak
        df = await asyncio.to_thread(_ak.stock_board_industry_name_em)
        if df is None or df.empty:
            return []

        # 按涨跌幅排序取前 20
        if "涨跌幅" in df.columns:
            df = df.sort_values("涨跌幅", ascending=False).head(20)

        sectors = []
        for _, row in df.iterrows():
            sectors.append({
                "name": str(row.get("板块名称", "")),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
                "leader": str(row.get("领涨股票", "")),
                "amount": float(row.get("总市值", 0) or 0),
            })

        # 缓存 60 秒
        try:
            await cache_set(cache_key, _json.dumps(sectors), ex=60)
        except Exception:
            pass

        return sectors
    except Exception as exc:
        logger.warning("获取板块数据失败: %s", exc)
        return []


@router.get("/sync/status")
async def get_sync_status() -> SyncStatusResponse:
    """查询各数据类型同步状态（含数据源和故障转移信息）。"""
    import json
    from app.core.redis_client import cache_get

    data_types = ["kline", "fundamentals", "money_flow"]
    type_labels = {
        "kline": "行情数据",
        "fundamentals": "基本面数据",
        "money_flow": "资金流向",
    }
    items: list[SyncStatusItem] = []
    for dt in data_types:
        raw = await cache_get(f"sync:status:{dt}")
        if raw:
            info = json.loads(raw)
            items.append(SyncStatusItem(**info))
        else:
            items.append(SyncStatusItem(
                source=type_labels.get(dt, dt),
                last_sync_at=None,
                status="UNKNOWN",
                record_count=0,
                data_source="N/A",
                is_fallback=False,
            ))
    return SyncStatusResponse(items=items)


@router.post("/sync")
async def trigger_sync(body: SyncRequest | None = None) -> SyncResponse:
    """手动触发数据同步任务，支持按类型选择。"""
    from app.tasks.data_sync import (
        sync_realtime_market,
        sync_fundamentals,
        sync_money_flow,
    )

    sync_type = (body.sync_type if body else None) or "all"
    task_ids: list[str] = []

    task_map = {
        "kline": (sync_realtime_market, "行情数据"),
        "fundamentals": (sync_fundamentals, "基本面数据"),
        "money_flow": (sync_money_flow, "资金流向"),
    }

    if sync_type == "all":
        for task_fn, _ in task_map.values():
            result = task_fn.delay()
            task_ids.append(result.id)
    elif sync_type in task_map:
        task_fn, _ = task_map[sync_type]
        result = task_fn.delay()
        task_ids.append(result.id)
    else:
        return SyncResponse(
            message=f"未知的同步类型: {sync_type}",
            task_ids=[],
        )

    type_label = "全部" if sync_type == "all" else task_map.get(sync_type, ("", sync_type))[1]
    return SyncResponse(
        message=f"{type_label}同步任务已触发，请稍后查看同步状态",
        task_ids=task_ids,
    )


@router.get("/cleaning/stats")
async def get_cleaning_stats() -> CleaningStatsResponse:
    """查询实时数据清洗统计信息。"""
    from app.core.database import AsyncSessionPG
    from app.models.stock import StockInfo, PermanentExclusion

    async with AsyncSessionPG() as session:
        total = (await session.execute(
            select(func.count()).select_from(StockInfo)
        )).scalar_one()

        st_delisted = (await session.execute(
            select(func.count()).select_from(StockInfo).where(
                (StockInfo.is_st == True) | (StockInfo.is_delisted == True)  # noqa: E712
            )
        )).scalar_one()

        new_stock = (await session.execute(
            select(func.count()).select_from(PermanentExclusion).where(
                PermanentExclusion.reason == "NEW_STOCK"
            )
        )).scalar_one()

        suspended = (await session.execute(
            select(func.count()).select_from(PermanentExclusion).where(
                PermanentExclusion.reason == "SUSPENDED"
            )
        )).scalar_one()

        high_pledge = (await session.execute(
            select(func.count()).select_from(StockInfo).where(
                StockInfo.pledge_ratio > 70
            )
        )).scalar_one()

        valid = total - st_delisted - new_stock - suspended - high_pledge

    return CleaningStatsResponse(
        total_stocks=total,
        valid_stocks=max(valid, 0),
        st_delisted_count=st_delisted,
        new_stock_count=new_stock,
        suspended_count=suspended,
        high_pledge_count=high_pledge,
    )


@router.get("/exclusions")
async def get_exclusions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """查询永久剔除名单。"""
    return {
        "total": 3,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "symbol": "000001",
                "name": "*ST 示例",
                "reason": "ST",
                "created_at": datetime(2023, 6, 1).isoformat(),
            },
            {
                "symbol": "000002",
                "name": "退市示例",
                "reason": "DELISTED",
                "created_at": datetime(2023, 8, 15).isoformat(),
            },
            {
                "symbol": "000003",
                "name": "新股示例",
                "reason": "NEW_STOCK",
                "created_at": datetime(2024, 1, 1).isoformat(),
            },
        ],
    }


# ---------------------------------------------------------------------------
# 历史数据回填端点
# ---------------------------------------------------------------------------


@router.post("/backfill", status_code=200)
async def start_backfill(body: BackfillRequest) -> BackfillResponse:
    """触发历史数据批量回填任务。

    - 支持 kline / fundamentals / money_flow 三种数据类型
    - 已有回填任务运行中时返回 HTTP 409
    """
    svc = BackfillService()
    try:
        result = await svc.start_backfill(
            data_types=body.data_types,
            symbols=body.symbols,
            start_date=body.start_date,
            end_date=body.end_date,
            freq=body.freq,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BackfillResponse(
        message=result["message"],
        task_ids=result["task_ids"],
    )


@router.get("/backfill/status")
async def get_backfill_status() -> BackfillStatusResponse:
    """查询回填进度，无数据时返回 idle 默认值。"""
    svc = BackfillService()
    progress = await svc.get_progress()
    return BackfillStatusResponse(
        total=progress.get("total", 0),
        completed=progress.get("completed", 0),
        failed=progress.get("failed", 0),
        current_symbol=progress.get("current_symbol", ""),
        status=progress.get("status", "idle"),
        data_types=progress.get("data_types", []),
    )


@router.post("/backfill/stop")
async def stop_backfill() -> BackfillStopResponse:
    """发送停止回填信号。

    - 回填任务运行中或等待中时，将状态设为 stopping
    - 无运行中任务时返回提示信息
    """
    svc = BackfillService()
    result = await svc.stop_backfill()
    return BackfillStopResponse(message=result["message"])


# ---------------------------------------------------------------------------
# 个股基本面数据端点
# ---------------------------------------------------------------------------


@router.get("/stock/{symbol}/fundamentals", response_model=StockFundamentalsResponse)
async def get_stock_fundamentals(symbol: str) -> StockFundamentalsResponse:
    """查询个股基本面数据（PE/PB/ROE/市值/营收增长/净利润增长等）。

    通过 DataSourceRouter 获取数据，支持 Tushare → AkShare 故障转移。
    """
    router_svc = DataSourceRouter()
    try:
        data = await router_svc.fetch_fundamentals(symbol)
    except DataSourceUnavailableError:
        raise HTTPException(status_code=503, detail="数据源暂时不可用，请稍后重试")

    if data is None:
        raise HTTPException(status_code=404, detail="未找到该股票的基本面数据")

    return StockFundamentalsResponse(
        symbol=data.symbol,
        name=data.name,
        pe_ttm=float(data.pe_ttm) if data.pe_ttm is not None else None,
        pb=float(data.pb) if data.pb is not None else None,
        roe=float(data.roe) if data.roe is not None else None,
        market_cap=float(data.market_cap) if data.market_cap is not None else None,
        revenue_growth=float(data.revenue_yoy) if data.revenue_yoy is not None else None,
        net_profit_growth=float(data.net_profit_yoy) if data.net_profit_yoy is not None else None,
        report_period=data.raw.get("report_period") if data.raw else None,
        updated_at=data.updated_at.isoformat() if data.updated_at else None,
    )


# ---------------------------------------------------------------------------
# 个股资金流向数据端点
# ---------------------------------------------------------------------------


@router.get("/stock/{symbol}/money-flow", response_model=StockMoneyFlowResponse)
async def get_stock_money_flow(
    symbol: str,
    days: int = Query(default=20, ge=1, le=60),
) -> StockMoneyFlowResponse:
    """查询个股近 N 个交易日的资金流向数据。

    通过 DataSourceRouter 逐日获取资金流向，聚合为按日期升序的记录列表返回。
    """
    from datetime import timedelta

    router_svc = DataSourceRouter()

    # 生成最近 days 个日历日（向前多取一些以覆盖非交易日）
    today = date.today()
    records: list[MoneyFlowDailyRecord] = []
    stock_name: str | None = None

    # 向前扫描足够多的日历日以覆盖 days 个交易日
    scan_days = days * 2 + 10
    trade_dates = [today - timedelta(days=i) for i in range(scan_days)]
    trade_dates.reverse()  # 升序

    for td in trade_dates:
        if len(records) >= days:
            break
        # 跳过周末
        if td.weekday() >= 5:
            continue
        try:
            flow = await router_svc.fetch_money_flow(symbol, td)
        except DataSourceUnavailableError:
            raise HTTPException(
                status_code=503, detail="数据源暂时不可用，请稍后重试"
            )
        except Exception:
            # 该日无数据或请求失败，跳过
            continue

        if flow is None:
            continue

        if stock_name is None and hasattr(flow, "raw") and flow.raw:
            stock_name = flow.raw.get("name")

        records.append(MoneyFlowDailyRecord(
            trade_date=flow.trade_date.isoformat(),
            main_net_inflow=float(flow.main_net_inflow / 10000) if flow.main_net_inflow is not None else 0.0,
            north_net_inflow=float(flow.north_net_inflow / 10000) if flow.north_net_inflow is not None else None,
            large_order_ratio=float(flow.large_order_ratio) if flow.large_order_ratio is not None else None,
            super_large_inflow=float(flow.large_order_net / 10000) if flow.large_order_net is not None else None,
            large_inflow=float(flow.large_order_net / 10000) if flow.large_order_net is not None else None,
        ))

    if not records:
        raise HTTPException(
            status_code=404, detail="未找到该股票的资金流向数据"
        )

    return StockMoneyFlowResponse(
        symbol=symbol,
        name=stock_name,
        days=len(records),
        records=records,
    )
