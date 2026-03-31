"""
复盘分析 API
- GET  /review/daily             — 每日复盘报告（cache-aside）
- GET  /review/strategy-report   — 策略绩效报表
- GET  /review/market            — 市场复盘分析
- GET  /review/export            — 报表导出（CSV / JSON）
- POST /review/compare           — 多策略对比
"""
from __future__ import annotations
import io, json, logging
from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import and_, cast, select, Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_pg_session
from app.core.redis_client import get_redis
from app.models.stock import StockInfo
from app.models.strategy import ScreenResult, StrategyTemplate
from app.models.trade import TradeOrder
from app.services.review_analyzer import MarketReviewAnalyzer, ReportExporter, ReviewAnalyzer, StrategyReportGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["复盘分析"])
_REVIEW_CACHE_PREFIX = "review:daily:"
_REVIEW_CACHE_TTL = 7 * 24 * 3600
_ZERO_METRICS = {"max_drawdown": 0.0, "sharpe_ratio": 0.0, "win_rate": 0.0, "calmar_ratio": 0.0}


class DailyReviewResponse(BaseModel):
    date: str
    win_rate: float = Field(ge=0, le=1)
    total_pnl: float
    trade_count: int = Field(ge=0)
    success_cases: list[dict] = []
    failure_cases: list[dict] = []


class StrategyReportResponse(BaseModel):
    strategy_id: str
    strategy_name: str = ""
    period: str
    returns: list[dict] = []
    risk_metrics: dict = {}


class MarketReviewResponse(BaseModel):
    sector_rotation: dict = {}
    trend_distribution: dict = {}
    money_flow: dict = {}


class ExportParams(BaseModel):
    period: str
    strategy_id: str | None = None
    format: Literal["csv", "json"] = "csv"


class CompareRequest(BaseModel):
    strategy_ids: list[str] = Field(min_length=2)
    period: str = "daily"


class CompareResponse(BaseModel):
    strategies: list[dict] = []
    best_strategy: str | None = None


def _build_case(c: dict) -> dict:
    return {"symbol": c.get("symbol", ""), "pnl": float(c.get("profit", 0)), "reason": c.get("direction", "")}


def _calc_profit(t) -> float:
    return float((t.filled_price or 0) - (t.price or 0)) * (t.filled_qty or 0)


@router.get("/daily", response_model=DailyReviewResponse)
async def get_daily_review(
    review_date: date | None = Query(None, alias="date"),
    pg_session: AsyncSession = Depends(get_pg_session),
    redis: Redis = Depends(get_redis),
) -> DailyReviewResponse:
    """获取每日复盘报告（cache-aside 模式）。"""
    target = review_date or date.today()
    cache_key = f"{_REVIEW_CACHE_PREFIX}{target.isoformat()}"
    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            return DailyReviewResponse(**json.loads(cached))
    except Exception:
        logger.warning("Redis read fail", exc_info=True)
    rows = (await pg_session.execute(select(TradeOrder).where(and_(
        TradeOrder.status == "FILLED", cast(TradeOrder.filled_at, SADate) == target)))).scalars().all()
    trade_records = [{"symbol": t.symbol, "profit": _calc_profit(t),
        "direction": t.direction, "price": float(t.price or 0), "quantity": t.filled_qty or 0} for t in rows]
    srows = (await pg_session.execute(select(ScreenResult).where(
        cast(ScreenResult.screen_time, SADate) == target))).scalars().all()
    screen_results = [{"symbol": s.symbol, "trend_score": float(s.trend_score or 0),
        "risk_level": s.risk_level, "signals": s.signals or {}} for s in srows]
    review = ReviewAnalyzer.generate_daily_review(trade_records, screen_results, review_date=target)
    response = DailyReviewResponse(
        date=target.isoformat(), win_rate=review.win_rate, total_pnl=review.total_pnl,
        trade_count=review.total_trades,
        success_cases=[_build_case(c) for c in review.successful_cases],
        failure_cases=[_build_case(c) for c in review.failed_cases])
    try:
        await redis.set(cache_key, response.model_dump_json(), ex=_REVIEW_CACHE_TTL)
    except Exception:
        logger.warning("Redis write fail", exc_info=True)
    return response


@router.get("/strategy-report", response_model=StrategyReportResponse)
async def get_strategy_report(
    strategy_id: str | None = Query(None),
    period: Literal["daily", "weekly", "monthly"] = Query("daily"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StrategyReportResponse:
    """获取策略绩效报表。"""
    if not strategy_id:
        raise HTTPException(status_code=400, detail="请指定策略ID")
    st = (await pg_session.execute(select(StrategyTemplate).where(
        StrategyTemplate.id == UUID(strategy_id)))).scalar_one_or_none()
    sname = st.name if st else ""
    symbols = [r for r in (await pg_session.execute(select(ScreenResult.symbol).where(
        ScreenResult.strategy_id == UUID(strategy_id)).distinct())).scalars().all() if r]
    if not symbols:
        return StrategyReportResponse(strategy_id=strategy_id, strategy_name=sname or "",
            period=period, returns=[], risk_metrics=_ZERO_METRICS)
    trows = (await pg_session.execute(select(TradeOrder).where(and_(
        TradeOrder.symbol.in_(symbols), TradeOrder.status == "FILLED")).order_by(
        TradeOrder.filled_at))).scalars().all()
    if not trows:
        return StrategyReportResponse(strategy_id=strategy_id, strategy_name=sname or "",
            period=period, returns=[], risk_metrics=_ZERO_METRICS)
    trades = [{"profit": _calc_profit(t),
        "date": t.filled_at.date().isoformat() if t.filled_at else ""} for t in trows]
    report = StrategyReportGenerator.generate_period_report(trades, period)
    rbd: dict[str, float] = {}
    for t in trades:
        rbd[t["date"]] = rbd.get(t["date"], 0.0) + t["profit"]
    return StrategyReportResponse(strategy_id=strategy_id, strategy_name=sname or "", period=period,
        returns=[{"date": d, "return_pct": v} for d, v in sorted(rbd.items())],
        risk_metrics={"max_drawdown": report["risk_metrics"]["max_drawdown"],
            "sharpe_ratio": report["risk_metrics"]["sharpe_ratio"],
            "win_rate": report["win_rate"], "calmar_ratio": 0.0})


async def _load_sector_data(session: AsyncSession, target_date: date) -> list[dict]:
    """从本地数据库加载板块涨跌幅数据。"""
    sectors = (await session.execute(select(StockInfo.board).distinct().where(
        StockInfo.board.isnot(None)))).scalars().all()
    return [{"name": s, "change_pct": 0.0} for s in sectors] if sectors else []


@router.get("/market", response_model=MarketReviewResponse)
async def get_market_review(
    review_date: date | None = Query(None, alias="date"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> MarketReviewResponse:
    """市场复盘分析。"""
    target = review_date or date.today()
    sector_data = await _load_sector_data(pg_session, target)
    scores = [float(s) for s in (await pg_session.execute(select(ScreenResult.trend_score).where(
        cast(ScreenResult.screen_time, SADate) == target,
        ScreenResult.trend_score.isnot(None)))).scalars().all()]
    return MarketReviewResponse(
        sector_rotation=MarketReviewAnalyzer.analyze_sector_rotation(sector_data),
        trend_distribution=MarketReviewAnalyzer.generate_trend_distribution(scores),
        money_flow=MarketReviewAnalyzer.analyze_money_flow([]))


@router.get("/export")
async def export_report(
    period: Literal["daily", "weekly", "monthly"] = Query("daily"),
    strategy_id: str | None = Query(None),
    format: Literal["csv", "json"] = Query("csv"),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StreamingResponse:
    """导出报表为 CSV 或 JSON 文件下载。"""
    if strategy_id:
        syms = [r for r in (await pg_session.execute(select(ScreenResult.symbol).where(
            ScreenResult.strategy_id == UUID(strategy_id)).distinct())).scalars().all() if r]
        ts = select(TradeOrder).where(and_(TradeOrder.symbol.in_(syms),
            TradeOrder.status == "FILLED")) if syms else select(TradeOrder).where(TradeOrder.id.is_(None))
    else:
        ts = select(TradeOrder).where(TradeOrder.status == "FILLED")
    trows = (await pg_session.execute(ts)).scalars().all()
    trades = [{"profit": _calc_profit(t)} for t in trows]
    report = StrategyReportGenerator.generate_period_report(trades, period)
    fn = f"review_{period}_{date.today().isoformat()}"
    if format == "csv":
        return StreamingResponse(io.BytesIO(ReportExporter.export_to_csv(report)),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fn}.csv"'})
    return StreamingResponse(io.BytesIO(ReportExporter.export_to_json(report).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fn}.json"'})


@router.post("/compare", response_model=CompareResponse)
async def compare_strategies(
    body: CompareRequest, pg_session: AsyncSession = Depends(get_pg_session),
) -> CompareResponse:
    """多策略并排对比分析。"""
    if len(body.strategy_ids) < 2:
        raise HTTPException(status_code=400, detail="请至少选择2个策略进行对比")
    reports: dict[str, dict] = {}
    for sid in body.strategy_ids:
        st = (await pg_session.execute(select(StrategyTemplate).where(
            StrategyTemplate.id == UUID(sid)))).scalar_one_or_none()
        name = st.name if st else sid
        syms = [r for r in (await pg_session.execute(select(ScreenResult.symbol).where(
            ScreenResult.strategy_id == UUID(sid)).distinct())).scalars().all() if r]
        trades: list[dict] = []
        if syms:
            trows = (await pg_session.execute(select(TradeOrder).where(and_(
                TradeOrder.symbol.in_(syms), TradeOrder.status == "FILLED")))).scalars().all()
            trades = [{"profit": _calc_profit(t)} for t in trows]
        reports[name] = StrategyReportGenerator.generate_period_report(trades, body.period)
    comp = StrategyReportGenerator.compare_strategies(reports)
    return CompareResponse(strategies=comp["strategies"], best_strategy=comp["best_strategy"])
