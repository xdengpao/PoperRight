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

    async def _check_with_retry(name: str, adapter, retries: int = 2, timeout: float = 20.0) -> DataSourceStatus:
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
                await asyncio.sleep(2)

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

    # 2. 本地无数据，回退到第三方 API（分钟级频率仅查本地，不回退）
    MINUTE_FREQS = {"1m", "5m", "15m", "30m", "60m"}
    if not bars and freq not in MINUTE_FREQS:
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

    # 4. 如果 adj_type=1 且有K线数据，执行前复权计算
    if adj_type == 1 and bars:
        try:
            from app.services.data_engine.adj_factor_repository import AdjFactorRepository
            from app.services.data_engine.forward_adjustment import adjust_kline_bars

            adj_repo = AdjFactorRepository()
            factors = await adj_repo.query_by_symbol(
                clean_symbol, adj_type=1, start=start_date, end=end_date,
            )
            latest = await adj_repo.query_latest_factor(clean_symbol, adj_type=1)
            if factors and latest:
                bars = adjust_kline_bars(bars, factors, latest)
            else:
                logger.warning(
                    "股票 %s 无前复权因子数据，返回原始K线", clean_symbol,
                )
        except Exception as exc:
            logger.warning(
                "查询前复权因子失败 symbol=%s: %s，返回原始K线数据", clean_symbol, exc,
            )

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

    优先从 Redis 缓存读取（TTL 60s），缓存未命中时尝试 AkShare（带超时），
    AkShare 不可用时从 TimescaleDB 读取最新指数 K 线数据作为降级。
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

    result: dict = {
        "date": today.isoformat(),
        "sh_index": 0, "sh_change_pct": 0,
        "sz_index": 0, "sz_change_pct": 0,
        "cyb_index": 0, "cyb_change_pct": 0,
        "advance_count": 0, "decline_count": 0,
        "limit_up_count": 0, "limit_down_count": 0,
        "market_sentiment": "NORMAL",
    }

    # 尝试从 TimescaleDB 读取最新指数数据（快速降级路径）
    async def _fetch_from_db() -> bool:
        """从 TimescaleDB 读取指数最新 K 线，成功返回 True。"""
        try:
            from sqlalchemy import select as sa_select
            from app.core.database import AsyncSessionTS
            from app.models.kline import Kline

            index_map_db = {
                "000001.SH": ("sh_index", "sh_change_pct"),
                "399001.SZ": ("sz_index", "sz_change_pct"),
                "399006.SZ": ("cyb_index", "cyb_change_pct"),
            }
            async with AsyncSessionTS() as session:
                for sym, (idx_field, pct_field) in index_map_db.items():
                    stmt = (
                        sa_select(Kline.close, Kline.open)
                        .where(Kline.symbol == sym, Kline.freq == "1d")
                        .order_by(Kline.time.desc())
                        .limit(1)
                    )
                    row = (await session.execute(stmt)).first()
                    if row and row[0]:
                        close_val = float(row[0])
                        open_val = float(row[1]) if row[1] else close_val
                        result[idx_field] = close_val
                        if open_val > 0:
                            result[pct_field] = round((close_val - open_val) / open_val * 100, 2)
            return result["sh_index"] > 0
        except Exception as exc:
            logger.warning("从 TimescaleDB 读取指数数据失败: %s", exc)
            return False

    # 先尝试快速的数据库路径
    db_ok = await _fetch_from_db()

    # 如果数据库有数据，异步尝试 AkShare 更新（不阻塞响应）
    # 如果数据库没数据，同步等待 AkShare（带超时）
    index_map = {
        "sh000001": ("sh_index", "sh_change_pct"),
        "sz399001": ("sz_index", "sz_change_pct"),
        "sz399006": ("cyb_index", "cyb_change_pct"),
    }

    async def _fetch_indices() -> None:
        try:
            import akshare as _ak
            df = await asyncio.wait_for(
                asyncio.to_thread(_ak.stock_zh_index_spot_sina),
                timeout=8.0,
            )
            if df is None or df.empty:
                return
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                if code in index_map:
                    idx_field, pct_field = index_map[code]
                    result[idx_field] = float(row.get("最新价", 0) or 0)
                    result[pct_field] = float(row.get("涨跌幅", 0) or 0)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("获取指数数据失败: %s", exc)

    async def _fetch_sentiment() -> None:
        try:
            import akshare as _ak
            df = await asyncio.wait_for(
                asyncio.to_thread(_ak.stock_zh_a_spot_em),
                timeout=12.0,
            )
            if df is not None and not df.empty and "涨跌幅" in df.columns:
                pct = df["涨跌幅"]
                result["advance_count"] = int((pct > 0).sum())
                result["decline_count"] = int((pct < 0).sum())
                result["limit_up_count"] = int((pct >= 9.9).sum())
                result["limit_down_count"] = int((pct <= -9.9).sum())
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("获取涨跌家数失败: %s", exc)

    if not db_ok:
        # 数据库没数据，必须等 AkShare
        await asyncio.gather(_fetch_indices(), _fetch_sentiment())
    else:
        # 数据库有数据，AkShare 作为增强（不阻塞）
        try:
            await asyncio.wait_for(
                asyncio.gather(_fetch_indices(), _fetch_sentiment()),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("AkShare 增强数据超时，使用数据库数据")

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
        df = await asyncio.wait_for(
            asyncio.to_thread(_ak.stock_board_industry_name_em),
            timeout=15.0,
        )
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


# ---------------------------------------------------------------------------
# 本地K线导入请求/响应模型
# ---------------------------------------------------------------------------


class LocalKlineImportRequest(BaseModel):
    markets: list[str] | None = None     # 市场分类: hushen/jingshi/zhishu
    freqs: list[str] | None = None       # 频率过滤列表
    start_date: str | None = None        # 起始日期 YYYY-MM-DD（兼容 YYYY-MM）
    end_date: str | None = None          # 结束日期 YYYY-MM-DD（兼容 YYYY-MM）
    force: bool = False                  # 强制全量导入


class LocalKlineImportResponse(BaseModel):
    task_id: str
    message: str


class LocalKlineImportStatusResponse(BaseModel):
    status: str = "idle"                 # idle/running/completed/failed
    total_files: int = 0
    processed_files: int = 0
    success_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0               # 增量跳过的文件数
    total_parsed: int = 0
    total_inserted: int = 0
    total_skipped: int = 0
    elapsed_seconds: float = 0
    failed_details: list[dict] = []      # [{path, error}]


# ---------------------------------------------------------------------------
# 本地K线导入端点
# ---------------------------------------------------------------------------


@router.post("/import/local-kline", status_code=202)
async def start_local_kline_import(
    body: LocalKlineImportRequest,
) -> LocalKlineImportResponse:
    """触发本地K线导入任务。

    - 已有导入任务运行中时返回 HTTP 409
    - 成功时分发 Celery 任务并返回 202 + task_id
    """
    from app.services.data_engine.local_kline_import import LocalKlineImportService
    from app.tasks.data_sync import import_local_kline

    svc = LocalKlineImportService()
    if await svc.is_running():
        raise HTTPException(status_code=409, detail="已有导入任务正在运行")

    # 立即重置 Redis 进度数据，避免前端轮询读到上次的终态
    import json
    import time as _time
    from app.core.redis_client import get_redis_client
    client = get_redis_client()
    try:
        await client.set(
            svc.REDIS_PROGRESS_KEY,
            json.dumps({"status": "pending", "total_files": 0, "processed_files": 0,
                         "success_files": 0, "failed_files": 0, "skipped_files": 0,
                         "total_parsed": 0, "total_inserted": 0, "total_skipped": 0,
                         "elapsed_seconds": 0, "failed_details": [],
                         "heartbeat": _time.time()}, ensure_ascii=False),
            ex=svc.PROGRESS_TTL,
        )
        await client.delete(svc.REDIS_RESULT_KEY)
    finally:
        await client.aclose()

    result = import_local_kline.delay(
        markets=body.markets,
        freqs=body.freqs,
        start_date=body.start_date,
        end_date=body.end_date,
        force=body.force,
    )

    return LocalKlineImportResponse(
        task_id=result.id,
        message="本地K线导入任务已触发",
    )


@router.get("/import/local-kline/status")
async def get_local_kline_import_status() -> LocalKlineImportStatusResponse:
    """查询导入进度和最近结果，无数据时返回 idle 默认值。

    如果检测到心跳超时的僵尸任务，自动将状态标记为 failed。
    """
    import json
    import time as _time

    from app.core.redis_client import get_redis_client

    client = get_redis_client()
    try:
        raw_progress = await client.get("import:local_kline:progress")
        raw_result = await client.get("import:local_kline:result")
    finally:
        await client.aclose()

    # 优先使用进度数据（任务运行中），否则使用结果数据（任务已完成）
    raw = raw_progress or raw_result
    if not raw:
        return LocalKlineImportStatusResponse()

    data = json.loads(raw)

    # 心跳超时检测：前端轮询时自动发现僵尸任务
    if data.get("status") in ("running", "pending"):
        heartbeat = data.get("heartbeat")
        is_zombie = heartbeat is None or (_time.time() - heartbeat) > 120
        if is_zombie:
            if heartbeat is None:
                data["status"] = "failed"
                data["error"] = "任务异常终止（无心跳记录）"
            else:
                data["status"] = "failed"
                data["error"] = f"任务异常终止（心跳超时 {int(_time.time() - heartbeat)} 秒）"
            client = get_redis_client()
            try:
                await client.set(
                    "import:local_kline:progress",
                    json.dumps(data, ensure_ascii=False),
                    ex=86400,
                )
            finally:
                await client.aclose()

    return LocalKlineImportStatusResponse(
        status=data.get("status", "idle"),
        total_files=data.get("total_files", 0),
        processed_files=data.get("processed_files", 0),
        success_files=data.get("success_files", 0),
        failed_files=data.get("failed_files", 0),
        skipped_files=data.get("skipped_files", 0),
        total_parsed=data.get("total_parsed", 0),
        total_inserted=data.get("total_inserted", 0),
        total_skipped=data.get("total_skipped", 0),
        elapsed_seconds=data.get("elapsed_seconds", 0),
        failed_details=data.get("failed_details", []),
    )


@router.post("/import/local-kline/stop")
async def stop_local_kline_import() -> dict:
    """发送K线导入停止信号。

    如果任务已因心跳超时被判定为僵尸任务，is_running() 会自动清理状态。
    """
    from app.services.data_engine.local_kline_import import LocalKlineImportService

    svc = LocalKlineImportService()
    if not await svc.is_running():
        raise HTTPException(status_code=409, detail="没有正在运行的导入任务")

    await svc.request_stop()
    return {"message": "停止信号已发送"}


@router.post("/import/local-kline/reset")
async def reset_local_kline_import_status() -> dict:
    """清空K线导入状态，重置为 idle。

    删除 Redis 中的进度、结果和停止信号键，前端刷新后恢复初始状态。
    运行中的任务不允许重置，需先停止。
    """
    from app.core.redis_client import get_redis_client
    from app.services.data_engine.local_kline_import import LocalKlineImportService

    svc = LocalKlineImportService()
    if await svc.is_running():
        raise HTTPException(status_code=409, detail="导入任务正在运行，请先停止")

    client = get_redis_client()
    try:
        await client.delete(
            svc.REDIS_PROGRESS_KEY,
            svc.REDIS_RESULT_KEY,
            svc.REDIS_STOP_KEY,
        )
    finally:
        await client.aclose()

    return {"message": "K线导入状态已清空"}


# ---------------------------------------------------------------------------
# 复权因子独立导入端点
# ---------------------------------------------------------------------------


class AdjFactorImportRequest(BaseModel):
    adj_factors: list[str]  # 复权因子类型: qfq/hfq（至少选一个）


class AdjFactorImportResponse(BaseModel):
    task_id: str
    message: str


class AdjFactorImportStatusResponse(BaseModel):
    status: str = "idle"  # idle/running/completed/failed
    adj_factor_stats: dict = {}  # {qfq: {status, parsed, inserted, skipped}, ...}
    elapsed_seconds: float = 0
    error: str = ""
    total_types: int = 0
    completed_types: int = 0
    current_type: str = ""
    current_step: str = ""


@router.post("/import/adj-factors", status_code=202)
async def start_adj_factor_import(
    body: AdjFactorImportRequest,
) -> AdjFactorImportResponse:
    """触发复权因子独立导入任务。

    - 已有复权因子导入任务运行中时返回 HTTP 409
    - 心跳超时的僵尸任务会被自动清理，允许重新启动
    - 成功时分发 Celery 任务并返回 202 + task_id
    """
    import json
    import time as _time

    from app.core.redis_client import get_redis_client
    from app.tasks.data_sync import import_adj_factors

    client = get_redis_client()
    try:
        raw = await client.get("import:adj_factor:progress")
        if raw:
            progress = json.loads(raw)
            if progress.get("status") == "running":
                # 心跳超时检测：进程异常终止后状态卡在 running
                heartbeat = progress.get("heartbeat")
                if heartbeat is None:
                    # 旧版数据无心跳字段，视为僵尸任务
                    logger.warning("复权因子导入任务无心跳字段，自动清理僵尸状态")
                    progress["status"] = "failed"
                    progress["error"] = "任务异常终止（无心跳记录）"
                    await client.set(
                        "import:adj_factor:progress",
                        json.dumps(progress, ensure_ascii=False),
                        ex=86400,
                    )
                elif (_time.time() - heartbeat) > 120:
                    # 僵尸任务，自动清理状态
                    elapsed = _time.time() - heartbeat
                    logger.warning(
                        "复权因子导入任务心跳超时（%.0f 秒），自动清理僵尸状态",
                        elapsed,
                    )
                    progress["status"] = "failed"
                    progress["error"] = f"任务异常终止（心跳超时 {int(elapsed)} 秒）"
                    await client.set(
                        "import:adj_factor:progress",
                        json.dumps(progress, ensure_ascii=False),
                        ex=86400,
                    )
                else:
                    raise HTTPException(status_code=409, detail="已有复权因子导入任务正在运行")
    finally:
        await client.aclose()

    result = import_adj_factors.delay(adj_factors=body.adj_factors)

    return AdjFactorImportResponse(
        task_id=result.id,
        message="复权因子导入任务已触发",
    )


@router.get("/import/adj-factors/status")
async def get_adj_factor_import_status() -> AdjFactorImportStatusResponse:
    """查询复权因子导入进度，无数据时返回 idle 默认值。

    如果检测到心跳超时的僵尸任务，自动将状态标记为 failed。
    """
    import json
    import time as _time

    from app.core.redis_client import get_redis_client

    client = get_redis_client()
    try:
        raw_progress = await client.get("import:adj_factor:progress")
        raw_result = await client.get("import:adj_factor:result")
    finally:
        await client.aclose()

    raw = raw_progress or raw_result
    if not raw:
        return AdjFactorImportStatusResponse()

    data = json.loads(raw)

    # 心跳超时检测：前端轮询时自动发现僵尸任务
    if data.get("status") == "running":
        heartbeat = data.get("heartbeat")
        is_zombie = heartbeat is None or (_time.time() - heartbeat) > 120
        if is_zombie:
            if heartbeat is None:
                data["status"] = "failed"
                data["error"] = "任务异常终止（无心跳记录）"
            else:
                data["status"] = "failed"
                data["error"] = f"任务异常终止（心跳超时 {int(_time.time() - heartbeat)} 秒）"
            # 更新 Redis 中的状态
            client = get_redis_client()
            try:
                await client.set(
                    "import:adj_factor:progress",
                    json.dumps(data, ensure_ascii=False),
                    ex=86400,
                )
            finally:
                await client.aclose()

    return AdjFactorImportStatusResponse(
        status=data.get("status", "idle"),
        adj_factor_stats=data.get("adj_factor_stats", {}),
        elapsed_seconds=data.get("elapsed_seconds", 0),
        error=data.get("error", ""),
        total_types=data.get("total_types", 0),
        completed_types=data.get("completed_types", 0),
        current_type=data.get("current_type", ""),
        current_step=data.get("current_step", ""),
    )


@router.post("/import/adj-factors/stop")
async def stop_adj_factor_import() -> dict:
    """发送复权因子导入停止信号。

    如果任务已因心跳超时被判定为僵尸任务，直接清理状态。
    """
    import json
    import time as _time

    from app.core.redis_client import get_redis_client
    from app.services.data_engine.local_kline_import import LocalKlineImportService

    # 检查是否有运行中的任务
    client = get_redis_client()
    try:
        raw = await client.get("import:adj_factor:progress")
        if not raw:
            raise HTTPException(status_code=409, detail="没有正在运行的复权因子导入任务")
        progress = json.loads(raw)
        if progress.get("status") != "running":
            raise HTTPException(status_code=409, detail="没有正在运行的复权因子导入任务")

        # 心跳超时检测：如果任务已死，直接清理状态
        heartbeat = progress.get("heartbeat")
        is_zombie = heartbeat is None or (_time.time() - heartbeat) > 120
        if is_zombie:
            progress["status"] = "failed"
            progress["error"] = "任务异常终止，已自动清理" if heartbeat is None else f"任务异常终止（心跳超时），已自动清理"
            await client.set(
                "import:adj_factor:progress",
                json.dumps(progress, ensure_ascii=False),
                ex=86400,
            )
            return {"message": "任务已异常终止，状态已清理"}
    finally:
        await client.aclose()

    svc = LocalKlineImportService()
    await svc.request_adj_stop()
    return {"message": "停止信号已发送"}


@router.post("/import/adj-factors/reset")
async def reset_adj_factor_import_status() -> dict:
    """清空复权因子导入状态，重置为 idle。

    删除 Redis 中的进度、结果和停止信号键，前端刷新后恢复初始状态。
    运行中的任务不允许重置，需先停止。
    """
    import json
    import time as _time

    from app.core.redis_client import get_redis_client
    from app.services.data_engine.local_kline_import import LocalKlineImportService

    svc = LocalKlineImportService()

    # 检查是否有运行中的任务（排除僵尸任务）
    client = get_redis_client()
    try:
        raw = await client.get(svc.REDIS_ADJ_PROGRESS_KEY)
        if raw:
            progress = json.loads(raw)
            if progress.get("status") == "running":
                heartbeat = progress.get("heartbeat")
                # 有心跳且未超时 → 真正在运行，不允许重置
                if heartbeat is not None and (_time.time() - heartbeat) <= 120:
                    raise HTTPException(status_code=409, detail="复权因子导入任务正在运行，请先停止")
                # 无心跳或已超时 → 僵尸任务，允许重置

        await client.delete(
            svc.REDIS_ADJ_PROGRESS_KEY,
            svc.REDIS_ADJ_RESULT_KEY,
            svc.REDIS_ADJ_STOP_KEY,
        )
    finally:
        await client.aclose()

    return {"message": "复权因子导入状态已清空"}


# ---------------------------------------------------------------------------
# 导入参数缓存端点
# ---------------------------------------------------------------------------

IMPORT_PARAMS_REDIS_KEY = "import:local_kline:last_params"
IMPORT_PARAMS_TTL = 86400 * 30  # 30 天


class ImportParamsCache(BaseModel):
    """缓存的导入页面参数"""
    markets: list[str] | None = None
    freqs: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    force: bool = False
    adj_factors: list[str] | None = None


@router.put("/import/params")
async def save_import_params(body: ImportParamsCache) -> dict:
    """保存导入参数到 Redis 缓存。"""
    import json

    from app.core.redis_client import get_redis_client

    client = get_redis_client()
    try:
        await client.set(
            IMPORT_PARAMS_REDIS_KEY,
            json.dumps(body.model_dump(), ensure_ascii=False),
            ex=IMPORT_PARAMS_TTL,
        )
    finally:
        await client.aclose()

    return {"message": "ok"}


@router.get("/import/params")
async def load_import_params() -> ImportParamsCache:
    """从 Redis 缓存加载上次导入参数。"""
    import json

    from app.core.redis_client import get_redis_client

    client = get_redis_client()
    try:
        raw = await client.get(IMPORT_PARAMS_REDIS_KEY)
    finally:
        await client.aclose()

    if not raw:
        return ImportParamsCache()

    data = json.loads(raw)
    return ImportParamsCache(**data)
