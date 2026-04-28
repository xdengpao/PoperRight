"""
风控 API

- GET  /risk/overview            — 大盘风控状态实时计算
- GET  /risk/total-position      — 总仓位状态
- POST /risk/check               — 委托风控校验（短路求值）
- POST /risk/stop-config         — 保存止损止盈配置
- GET  /risk/stop-config         — 读取止损止盈配置
- GET  /risk/position-warnings   — 持仓预警实时检测
- GET  /risk/strategy-health     — 策略健康状态
- GET  /risk/index-kline         — 指数 K 线数据（60 日 OHLC + MA20/MA60）
- CRUD /blacklist                — 黑名单管理
- CRUD /whitelist                — 白名单管理
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_pg_session, get_ts_session
from app.core.redis_client import get_redis
from app.core.schemas import MarketRiskLevel
from app.models.backtest import BacktestRun
from app.models.kline import Kline
from app.models.stock import StockList
from app.models.trade import Position as PositionModel, TradeOrder
from app.services.risk_controller import (
    BlackWhiteListManager,
    MarketRiskChecker,
    PositionRiskChecker,
    StockRiskFilter,
    StopLossChecker,
    StrategyHealthMonitor,
    RiskEventLogger,
    build_stop_loss_alert_message,
    get_suggested_action,
    is_risk_alert_active,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["风控"])

# ---------------------------------------------------------------------------
# 共享黑白名单管理器实例
# ---------------------------------------------------------------------------

_bw_manager = BlackWhiteListManager()

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_RISK_SEVERITY = {
    MarketRiskLevel.NORMAL: 0,
    MarketRiskLevel.CAUTION: 1,
    MarketRiskLevel.DANGER: 2,
}

from app.core.symbol_utils import INDEX_SH, INDEX_CYB, INDEX_HS300, INDEX_ZZ500

_SH_SYMBOL = INDEX_SH
_CYB_SYMBOL = INDEX_CYB
_HS300_SYMBOL = INDEX_HS300
_ZZ500_SYMBOL = INDEX_ZZ500
_KLINE_LIMIT = 60

# 监控指数列表（需求 9）
_MONITORED_INDICES: dict[str, str] = {
    _SH_SYMBOL: "上证指数",
    _CYB_SYMBOL: "创业板指",
    _HS300_SYMBOL: "沪深300",
    _ZZ500_SYMBOL: "中证500",
}

_STOP_CONFIG_TTL = 30 * 24 * 3600  # 30 days in seconds

# Placeholder user_id (real auth would inject this)
_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Pydantic 响应/请求模型
# ---------------------------------------------------------------------------


class IndexRiskItem(BaseModel):
    """单个监控指数的风控状态（需求 9）"""
    index_code: str
    index_name: str
    above_ma20: bool
    above_ma60: bool
    risk_level: str


class RiskOverviewResponse(BaseModel):
    market_risk_level: str
    sh_above_ma20: bool
    sh_above_ma60: bool
    cyb_above_ma20: bool
    cyb_above_ma60: bool
    current_threshold: float
    data_insufficient: bool = False
    indices: list[IndexRiskItem] = []


class RiskCheckRequest(BaseModel):
    symbol: str
    direction: str = "BUY"
    quantity: int = 0
    price: float | None = None


class RiskCheckResponse(BaseModel):
    passed: bool
    reason: str | None = None


class StopConfigRequest(BaseModel):
    mode: str = "fixed"
    fixed_stop_loss: float = 8.0
    trailing_stop: float = 5.0
    trend_stop_ma: int = 20
    atr_fixed_multiplier: float = 2.0
    atr_trailing_multiplier: float = 1.5


class StopConfigResponse(BaseModel):
    mode: str = "fixed"
    fixed_stop_loss: float
    trailing_stop: float
    trend_stop_ma: int
    atr_fixed_multiplier: float = 2.0
    atr_trailing_multiplier: float = 1.5


class PositionWarningItem(BaseModel):
    symbol: str
    type: str
    level: str
    current_value: str
    threshold: str
    time: str
    cost_price: float | None = None       # 持仓成本价（需求 12）
    current_price: float | None = None    # 当前价格（需求 12）
    pnl_pct: float | None = None          # 盈亏比例，如 -5.2 表示 -5.2%（需求 12）
    suggested_action: str | None = None   # 建议操作（需求 12）


class StockListItemIn(BaseModel):
    symbol: str
    reason: str | None = None


class StockListItemOut(BaseModel):
    symbol: str
    reason: str | None = None
    created_at: str


class StockListPageResponse(BaseModel):
    total: int
    items: list[StockListItemOut]


class StrategyHealthResponse(BaseModel):
    strategy_id: str | None = None
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    is_healthy: bool = True
    warnings: list[str] = []
    # 实盘指标（需求 8）
    live_win_rate: float | None = None
    live_max_drawdown: float | None = None
    live_is_healthy: bool | None = None
    live_data_sufficient: bool | None = None


class TotalPositionResponse(BaseModel):
    """总仓位状态响应（需求 5.2）"""
    total_position_pct: float       # 当前总仓位比例 (%)
    total_market_value: float       # 持仓总市值
    available_cash: float           # 可用现金
    position_limit_pct: float       # 仓位上限 (%)
    market_risk_level: str          # 当前大盘风险等级


class IndexKlineItem(BaseModel):
    """指数 K 线数据条目（需求 11.3）"""
    time: str                       # 交易日期 ISO 格式
    open: float
    high: float
    low: float
    close: float
    ma20: float | None = None       # 20 日均线值
    ma60: float | None = None       # 60 日均线值


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


async def _fetch_closes(
    session: AsyncSession, symbol: str,
) -> list[float]:
    """查询指定指数最近 60 个交易日的日 K 线收盘价（按时间升序）。"""
    stmt = (
        select(Kline.close)
        .where(Kline.symbol == symbol, Kline.freq == "1d")
        .order_by(Kline.time.desc())
        .limit(_KLINE_LIMIT)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [float(c) for c in reversed(rows) if c is not None]


def _get_stop_config_key(user_id: str) -> str:
    return f"risk:stop_config:{user_id}"


async def _load_stop_config(redis: Redis, user_id: str) -> StopConfigResponse:
    """从 Redis 加载止损配置，无数据时返回默认值。"""
    key = _get_stop_config_key(user_id)
    raw = await redis.get(key)
    if raw:
        data = json.loads(raw)
        return StopConfigResponse(
            mode=data.get("mode", "fixed"),
            fixed_stop_loss=data.get("fixed_stop_loss", 8.0),
            trailing_stop=data.get("trailing_stop", 5.0),
            trend_stop_ma=data.get("trend_stop_ma", 20),
            atr_fixed_multiplier=data.get("atr_fixed_multiplier", 2.0),
            atr_trailing_multiplier=data.get("atr_trailing_multiplier", 1.5),
        )
    return StopConfigResponse(
        mode="fixed",
        fixed_stop_loss=8.0,
        trailing_stop=5.0,
        trend_stop_ma=20,
        atr_fixed_multiplier=2.0,
        atr_trailing_multiplier=1.5,
    )


# ---------------------------------------------------------------------------
# 黑白名单内部函数
# ---------------------------------------------------------------------------


async def _list_stock_list(
    session: AsyncSession,
    list_type: str,
    user_id: str,
    page: int,
    page_size: int,
) -> StockListPageResponse:
    """分页查询黑名单或白名单。"""
    # 总数
    count_stmt = (
        select(func.count())
        .select_from(StockList)
        .where(StockList.list_type == list_type, StockList.user_id == user_id)
    )
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页数据
    offset = (page - 1) * page_size
    data_stmt = (
        select(StockList)
        .where(StockList.list_type == list_type, StockList.user_id == user_id)
        .order_by(StockList.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    data_result = await session.execute(data_stmt)
    rows = data_result.scalars().all()

    items = [
        StockListItemOut(
            symbol=r.symbol,
            reason=r.reason,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return StockListPageResponse(total=total, items=items)


async def _add_to_stock_list(
    session: AsyncSession,
    list_type: str,
    user_id: str,
    symbol: str,
    reason: str | None,
) -> StockListItemOut:
    """添加到黑名单或白名单，已存在则抛出 HTTPException 409。"""
    # 检查是否已存在
    check_stmt = select(StockList).where(
        StockList.symbol == symbol,
        StockList.list_type == list_type,
        StockList.user_id == user_id,
    )
    existing = await session.execute(check_stmt)
    if existing.scalar_one_or_none() is not None:
        label = "黑名单" if list_type == "BLACK" else "白名单"
        raise HTTPException(status_code=409, detail=f"该股票已在{label}中")

    entry = StockList(
        symbol=symbol,
        list_type=list_type,
        user_id=user_id,
        reason=reason,
    )
    session.add(entry)
    await session.flush()

    return StockListItemOut(
        symbol=entry.symbol,
        reason=entry.reason,
        created_at=entry.created_at.isoformat() if entry.created_at else datetime.now().isoformat(),
    )


async def _remove_from_stock_list(
    session: AsyncSession,
    list_type: str,
    user_id: str,
    symbol: str,
) -> None:
    """从黑名单或白名单移除，不存在则抛出 HTTPException 404。"""
    check_stmt = select(StockList).where(
        StockList.symbol == symbol,
        StockList.list_type == list_type,
        StockList.user_id == user_id,
    )
    existing = await session.execute(check_stmt)
    if existing.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="记录不存在")

    del_stmt = delete(StockList).where(
        StockList.symbol == symbol,
        StockList.list_type == list_type,
        StockList.user_id == user_id,
    )
    await session.execute(del_stmt)


# ---------------------------------------------------------------------------
# 风控概览 — GET /risk/overview
# ---------------------------------------------------------------------------


@router.get("/risk/overview", response_model=RiskOverviewResponse)
async def risk_overview(
    ts_session: AsyncSession = Depends(get_ts_session),
) -> RiskOverviewResponse:
    """获取大盘风控状态（实时计算多个监控指数均线状态）。"""
    checker = MarketRiskChecker()

    # 查询所有监控指数的 K 线数据
    index_data: dict[str, list[float]] = {}
    try:
        for symbol in _MONITORED_INDICES:
            closes = await _fetch_closes(ts_session, symbol)
            index_data[symbol] = closes
    except Exception:
        logger.exception("查询指数 K 线数据失败")
        return RiskOverviewResponse(
            market_risk_level=MarketRiskLevel.NORMAL.value,
            sh_above_ma20=True,
            sh_above_ma60=True,
            cyb_above_ma20=True,
            cyb_above_ma60=True,
            current_threshold=80.0,
            data_insufficient=True,
        )

    # 至少需要上证和创业板有数据
    sh_closes = index_data.get(_SH_SYMBOL, [])
    cyb_closes = index_data.get(_CYB_SYMBOL, [])
    if not sh_closes and not cyb_closes:
        return RiskOverviewResponse(
            market_risk_level=MarketRiskLevel.NORMAL.value,
            sh_above_ma20=True,
            sh_above_ma60=True,
            cyb_above_ma20=True,
            cyb_above_ma60=True,
            current_threshold=80.0,
            data_insufficient=True,
        )

    # 使用多指数综合风控
    combined_risk, details = checker.check_multi_index_risk(index_data)

    # 计算均线状态（向后兼容原有字段）
    def _above_ma(closes: list[float], period: int) -> bool:
        ma = checker._simple_ma(closes, period)
        if ma is None:
            return True  # 数据不足时保守返回 True
        return closes[-1] >= ma

    # 构建各指数风控状态列表
    indices: list[IndexRiskItem] = []
    for symbol, name in _MONITORED_INDICES.items():
        detail = details.get(symbol)
        if detail is not None:
            indices.append(IndexRiskItem(
                index_code=symbol,
                index_name=name,
                above_ma20=detail["above_ma20"],
                above_ma60=detail["above_ma60"],
                risk_level=detail["risk_level"].value,
            ))

    return RiskOverviewResponse(
        market_risk_level=combined_risk.value,
        sh_above_ma20=_above_ma(sh_closes, 20) if sh_closes else True,
        sh_above_ma60=_above_ma(sh_closes, 60) if sh_closes else True,
        cyb_above_ma20=_above_ma(cyb_closes, 20) if cyb_closes else True,
        cyb_above_ma60=_above_ma(cyb_closes, 60) if cyb_closes else True,
        current_threshold=checker.get_trend_threshold(combined_risk),
        data_insufficient=False,
        indices=indices,
    )


# ---------------------------------------------------------------------------
# 总仓位状态 — GET /risk/total-position（需求 5）
# ---------------------------------------------------------------------------


@router.get("/risk/total-position", response_model=TotalPositionResponse)
async def total_position(
    pg_session: AsyncSession = Depends(get_pg_session),
    ts_session: AsyncSession = Depends(get_ts_session),
) -> TotalPositionResponse:
    """获取当前总仓位比例、持仓总市值、可用现金和仓位上限。"""
    user_id = _DEFAULT_USER_ID
    checker = MarketRiskChecker()

    # 查询持仓
    pos_stmt = select(PositionModel).where(PositionModel.user_id == user_id)
    pos_result = await pg_session.execute(pos_stmt)
    positions = pos_result.scalars().all()

    total_market_value = sum(
        float(p.cost_price or 0) * (p.quantity or 0) for p in positions
    )

    # 可用现金：简化实现，使用固定初始资金减去持仓市值
    # 实际生产环境应从账户余额查询
    _INITIAL_CAPITAL = 1_000_000.0
    available_cash = max(_INITIAL_CAPITAL - total_market_value, 0.0)

    # 计算大盘风险等级以确定仓位上限
    try:
        sh_closes = await _fetch_closes(ts_session, _SH_SYMBOL)
        cyb_closes = await _fetch_closes(ts_session, _CYB_SYMBOL)
        sh_risk = checker.check_market_risk(sh_closes) if sh_closes else MarketRiskLevel.NORMAL
        cyb_risk = checker.check_market_risk(cyb_closes) if cyb_closes else MarketRiskLevel.NORMAL
        combined_risk = (
            sh_risk
            if _RISK_SEVERITY[sh_risk] >= _RISK_SEVERITY[cyb_risk]
            else cyb_risk
        )
    except Exception:
        logger.warning("查询指数数据失败，使用默认风险等级", exc_info=True)
        combined_risk = MarketRiskLevel.NORMAL

    position_limit = PositionRiskChecker.get_total_position_limit_by_risk_level(combined_risk)
    total_pct = PositionRiskChecker.compute_total_position_pct(total_market_value, available_cash)

    return TotalPositionResponse(
        total_position_pct=round(total_pct, 2),
        total_market_value=round(total_market_value, 2),
        available_cash=round(available_cash, 2),
        position_limit_pct=position_limit,
        market_risk_level=combined_risk.value,
    )


# ---------------------------------------------------------------------------
# 委托风控校验 — POST /risk/check (短路求值)
# ---------------------------------------------------------------------------


@router.post("/risk/check", response_model=RiskCheckResponse)
async def risk_check(
    body: RiskCheckRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
    ts_session: AsyncSession = Depends(get_ts_session),
) -> RiskCheckResponse:
    """对委托进行风控校验（黑名单→涨幅→单股仓位→板块仓位，短路求值）。"""
    user_id = _DEFAULT_USER_ID

    # 1. 黑名单检查
    bl_stmt = select(StockList).where(
        StockList.symbol == body.symbol,
        StockList.list_type == "BLACK",
        StockList.user_id == user_id,
    )
    bl_result = await pg_session.execute(bl_stmt)
    if bl_result.scalar_one_or_none() is not None:
        return RiskCheckResponse(passed=False, reason="该股票在黑名单中")

    # 2. 当日涨幅检查
    try:
        today = date.today()
        kline_stmt = (
            select(Kline.open, Kline.close)
            .where(
                Kline.symbol == body.symbol,
                Kline.freq == "1d",
                func.date(Kline.time) == today,
            )
            .order_by(Kline.time.desc())
            .limit(1)
        )
        kline_result = await ts_session.execute(kline_stmt)
        kline_row = kline_result.first()
        if kline_row and kline_row[0] and float(kline_row[0]) > 0:
            daily_change = (float(kline_row[1]) - float(kline_row[0])) / float(kline_row[0]) * 100
            if StockRiskFilter.check_daily_gain(daily_change):
                return RiskCheckResponse(passed=False, reason="个股单日涨幅超过9%")
    except Exception:
        logger.warning("查询当日 K 线失败，跳过涨幅检查", exc_info=True)

    # 3. 单股仓位检查
    try:
        pos_stmt = select(PositionModel).where(
            PositionModel.user_id == user_id,
        )
        pos_result = await pg_session.execute(pos_stmt)
        positions = pos_result.scalars().all()

        if positions:
            total_value = sum(
                float(p.cost_price or 0) * (p.quantity or 0) for p in positions
            )
            if total_value > 0:
                # 找到当前股票的持仓
                stock_pos = next((p for p in positions if p.symbol == body.symbol), None)
                if stock_pos:
                    stock_value = float(stock_pos.cost_price or 0) * (stock_pos.quantity or 0)
                    stock_weight = (stock_value / total_value) * 100
                    check = PositionRiskChecker.check_stock_position_limit(stock_weight)
                    if not check.passed:
                        return RiskCheckResponse(passed=False, reason="单股仓位超过15%上限")

                # 4. 板块仓位检查 (使用申万行业分类)
                # 获取当前股票的行业分类
                from app.models.stock import StockInfo
                info_stmt = select(StockInfo.industry_name).where(StockInfo.symbol == body.symbol)
                info_result = await pg_session.execute(info_stmt)
                industry = info_result.scalar_one_or_none() or "未分类"

                if industry:
                    # 查询同行业所有持仓股票
                    all_symbols = [p.symbol for p in positions if p.symbol]
                    if all_symbols:
                        industry_stmt = select(StockInfo.symbol).where(
                            StockInfo.symbol.in_(all_symbols),
                            StockInfo.industry_name == industry,
                        )
                        industry_result = await pg_session.execute(industry_stmt)
                        sector_symbols = set(industry_result.scalars().all())

                        # 未分类的股票也需要纳入（行业数据缺失的）
                        if industry == "未分类":
                            classified_stmt = select(StockInfo.symbol).where(
                                StockInfo.symbol.in_(all_symbols),
                                StockInfo.industry_name.isnot(None),
                            )
                            classified_result = await pg_session.execute(classified_stmt)
                            classified_symbols = set(classified_result.scalars().all())
                            unclassified = set(all_symbols) - classified_symbols
                            sector_symbols = sector_symbols | unclassified

                        sector_value = sum(
                            float(p.cost_price or 0) * (p.quantity or 0)
                            for p in positions
                            if p.symbol in sector_symbols
                        )
                        sector_weight = (sector_value / total_value) * 100
                        check = PositionRiskChecker.check_sector_position_limit(sector_weight)
                        if not check.passed:
                            return RiskCheckResponse(passed=False, reason=f"{industry}行业仓位超过30%上限")
    except Exception:
        logger.warning("仓位检查异常，跳过", exc_info=True)

    return RiskCheckResponse(passed=True, reason=None)


# ---------------------------------------------------------------------------
# 止损止盈配置 — POST/GET /risk/stop-config
# ---------------------------------------------------------------------------


@router.post("/risk/stop-config", response_model=StopConfigResponse)
async def save_stop_config(
    body: StopConfigRequest,
    redis: Redis = Depends(get_redis),
) -> StopConfigResponse:
    """保存止损止盈配置到 Redis。"""
    user_id = _DEFAULT_USER_ID
    key = _get_stop_config_key(user_id)
    data = {
        "mode": body.mode,
        "fixed_stop_loss": body.fixed_stop_loss,
        "trailing_stop": body.trailing_stop,
        "trend_stop_ma": body.trend_stop_ma,
        "atr_fixed_multiplier": body.atr_fixed_multiplier,
        "atr_trailing_multiplier": body.atr_trailing_multiplier,
    }
    await redis.set(key, json.dumps(data), ex=_STOP_CONFIG_TTL)
    return StopConfigResponse(**data)


@router.get("/risk/stop-config", response_model=StopConfigResponse)
async def get_stop_config(
    redis: Redis = Depends(get_redis),
) -> StopConfigResponse:
    """从 Redis 读取止损止盈配置，无数据时返回默认值。"""
    user_id = _DEFAULT_USER_ID
    return await _load_stop_config(redis, user_id)


# ---------------------------------------------------------------------------
# 持仓预警 — GET /risk/position-warnings
# ---------------------------------------------------------------------------


@router.get("/risk/position-warnings", response_model=list[PositionWarningItem])
async def position_warnings(
    pg_session: AsyncSession = Depends(get_pg_session),
    ts_session: AsyncSession = Depends(get_ts_session),
    redis: Redis = Depends(get_redis),
) -> list[PositionWarningItem]:
    """获取持仓预警列表（6 项风控检测）。"""
    user_id = _DEFAULT_USER_ID
    now_str = datetime.now().isoformat()

    # 查询当前用户所有持仓
    pos_stmt = select(PositionModel).where(PositionModel.user_id == user_id)
    pos_result = await pg_session.execute(pos_stmt)
    positions = pos_result.scalars().all()

    if not positions:
        return []

    # 计算总资产
    total_value = sum(
        float(p.cost_price or 0) * (p.quantity or 0) for p in positions
    )
    if total_value <= 0:
        return []

    # 加载止损配置
    stop_cfg = await _load_stop_config(redis, user_id)

    warnings: list[PositionWarningItem] = []

    # 跟踪每个标的的当前价格，用于止损预警消息构建
    _symbol_prices: dict[str, float] = {}
    # 跟踪每个标的的成本价，用于盈亏比例计算（需求 12）
    _symbol_costs: dict[str, float] = {}

    for pos in positions:
        symbol = pos.symbol
        if not symbol:
            continue

        cost_price = float(pos.cost_price or 0)
        quantity = pos.quantity or 0
        stock_value = cost_price * quantity

        # 记录成本价用于盈亏比例计算（需求 12）
        _symbol_costs[symbol] = cost_price

        # 1. 单股仓位检查
        stock_weight = (stock_value / total_value) * 100
        check = PositionRiskChecker.check_stock_position_limit(stock_weight)
        if not check.passed:
            warnings.append(PositionWarningItem(
                symbol=symbol,
                type="单股仓位超限",
                level="danger",
                current_value=f"{stock_weight:.2f}%",
                threshold="15.00%",
                time=now_str,
            ))

        # 2. 板块仓位检查（使用申万行业分类）
        try:
            from app.models.stock import StockInfo
            info_stmt = select(StockInfo.industry_name).where(StockInfo.symbol == symbol)
            info_result = await pg_session.execute(info_stmt)
            industry = info_result.scalar_one_or_none() or "未分类"
            if industry:
                all_symbols = [p.symbol for p in positions if p.symbol]
                industry_stmt = select(StockInfo.symbol).where(
                    StockInfo.symbol.in_(all_symbols),
                    StockInfo.industry_name == industry,
                )
                industry_result = await pg_session.execute(industry_stmt)
                sector_symbols = set(industry_result.scalars().all())

                # 未分类的股票也需要纳入（行业数据缺失的）
                if industry == "未分类":
                    classified_stmt = select(StockInfo.symbol).where(
                        StockInfo.symbol.in_(all_symbols),
                        StockInfo.industry_name.isnot(None),
                    )
                    classified_result = await pg_session.execute(classified_stmt)
                    classified_symbols = set(classified_result.scalars().all())
                    unclassified = set(all_symbols) - classified_symbols
                    sector_symbols = sector_symbols | unclassified

                sector_value = sum(
                    float(p.cost_price or 0) * (p.quantity or 0)
                    for p in positions
                    if p.symbol in sector_symbols
                )
                sector_weight = (sector_value / total_value) * 100
                sector_check = PositionRiskChecker.check_sector_position_limit(sector_weight)
                if not sector_check.passed:
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type=f"{industry}行业仓位超限",
                        level="warning",
                        current_value=f"{sector_weight:.2f}%",
                        threshold="30.00%",
                        time=now_str,
                    ))
        except Exception:
            logger.warning("行业仓位检查失败: %s", symbol, exc_info=True)

        # 查询该标的 K 线数据用于后续检查
        try:
            kline_stmt = (
                select(Kline.close, Kline.open, Kline.volume, Kline.high)
                .where(Kline.symbol == symbol, Kline.freq == "1d")
                .order_by(Kline.time.desc())
                .limit(60)
            )
            kline_result = await ts_session.execute(kline_stmt)
            kline_rows = kline_result.all()

            if not kline_rows:
                continue

            # 最新一根 K 线
            latest = kline_rows[0]
            current_price = float(latest[0]) if latest[0] else 0
            open_price = float(latest[1]) if latest[1] else 0
            latest_volume = int(latest[2]) if latest[2] else 0

            # 记录当前价格用于预警消息
            _symbol_prices[symbol] = current_price

            # 收盘价序列（升序）
            closes = [float(r[0]) for r in reversed(kline_rows) if r[0] is not None]
            volumes = [int(r[2]) for r in reversed(kline_rows) if r[2] is not None]
            highs = [float(r[3]) for r in reversed(kline_rows) if r[3] is not None]

            # 计算 MA20
            ma20 = sum(closes[-20:]) / min(len(closes), 20) if len(closes) >= 20 else None

            # 计算当日涨跌幅
            daily_change = ((current_price - open_price) / open_price * 100) if open_price > 0 else 0

            # 计算量比
            avg_vol = sum(volumes[-20:]) / min(len(volumes), 20) if len(volumes) >= 20 else 0
            volume_ratio = (latest_volume / avg_vol) if avg_vol > 0 else 0

            # 持仓期间最高价
            peak_price = max(highs) if highs else current_price

            # 计算趋势止损均线
            trend_ma_period = stop_cfg.trend_stop_ma
            trend_ma_value = (
                sum(closes[-trend_ma_period:]) / min(len(closes), trend_ma_period)
                if len(closes) >= trend_ma_period
                else None
            )

            # 3. 急跌破位预警（放宽版：三个条件满足其中两个）
            if ma20 is not None:
                if PositionRiskChecker.check_position_breakdown_relaxed(
                    current_price, ma20, daily_change, volume_ratio
                ):
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type="急跌破位预警",
                        level="danger",
                        current_value=f"价格{current_price:.2f} < MA20({ma20:.2f})",
                        threshold="三条件满足其二",
                        time=now_str,
                    ))

            # 3b. 阴跌破位预警（连续阴跌检测）
            if len(closes) >= 4:  # 至少需要 N+1=4 个数据点
                if PositionRiskChecker.check_consecutive_decline_pure(closes):
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type="阴跌破位预警",
                        level="warning",
                        current_value=f"连续3日下跌",
                        threshold="累计跌幅>8%",
                        time=now_str,
                    ))

            # 4. 固定止损 & 5. 移动止损（支持 ATR 自适应模式）
            if stop_cfg.mode == "atr_adaptive":
                # 计算 14 日 ATR
                atr_value = None
                if len(highs) >= 14 and len(closes) >= 15:
                    lows = [float(r[3]) for r in reversed(kline_rows) if r[3] is not None]
                    # 使用 high-low 近似 True Range（简化版，无前收盘价）
                    # 完整 TR = max(high-low, |high-prev_close|, |low-prev_close|)
                    tr_list = []
                    for i in range(len(closes) - 1, max(len(closes) - 15, 0), -1):
                        if i > 0:
                            h = highs[i] if i < len(highs) else closes[i]
                            low_val = lows[i] if i < len(lows) else closes[i]
                            prev_close = closes[i - 1]
                            tr = max(
                                h - low_val,
                                abs(h - prev_close),
                                abs(low_val - prev_close),
                            )
                            tr_list.append(tr)
                    if len(tr_list) >= 14:
                        atr_value = sum(tr_list[:14]) / 14

                if atr_value is not None and atr_value > 0:
                    atr_result = StopLossChecker.compute_atr_stop_loss_pure(
                        cost_price=cost_price,
                        current_price=current_price,
                        peak_price=peak_price,
                        atr=atr_value,
                        fixed_multiplier=stop_cfg.atr_fixed_multiplier,
                        trailing_multiplier=stop_cfg.atr_trailing_multiplier,
                    )

                    # ATR 固定止损
                    if cost_price > 0 and atr_result["fixed_triggered"]:
                        loss_pct = (cost_price - current_price) / cost_price * 100
                        warnings.append(PositionWarningItem(
                            symbol=symbol,
                            type="固定止损触发",
                            level="danger",
                            current_value=f"亏损{loss_pct:.2f}%",
                            threshold=f"ATR止损价{atr_result['fixed_stop_price']:.2f}",
                            time=now_str,
                        ))

                    # ATR 移动止损
                    if peak_price > 0 and atr_result["trailing_triggered"]:
                        retrace_pct = (peak_price - current_price) / peak_price * 100
                        warnings.append(PositionWarningItem(
                            symbol=symbol,
                            type="移动止损触发",
                            level="warning",
                            current_value=f"回撤{retrace_pct:.2f}%",
                            threshold=f"ATR回撤{atr_result['trailing_retrace_pct'] * 100:.2f}%",
                            time=now_str,
                        ))
                else:
                    # ATR 数据不可用，回退到固定比例止损
                    if cost_price > 0 and StopLossChecker.check_fixed_stop_loss(
                        cost_price, current_price, stop_cfg.fixed_stop_loss / 100
                    ):
                        loss_pct = (cost_price - current_price) / cost_price * 100
                        warnings.append(PositionWarningItem(
                            symbol=symbol,
                            type="固定止损触发",
                            level="danger",
                            current_value=f"亏损{loss_pct:.2f}%",
                            threshold=f"{stop_cfg.fixed_stop_loss:.1f}%(ATR不可用)",
                            time=now_str,
                        ))

                    if peak_price > 0 and StopLossChecker.check_trailing_stop_loss(
                        peak_price, current_price, stop_cfg.trailing_stop / 100
                    ):
                        retrace_pct = (peak_price - current_price) / peak_price * 100
                        warnings.append(PositionWarningItem(
                            symbol=symbol,
                            type="移动止损触发",
                            level="warning",
                            current_value=f"回撤{retrace_pct:.2f}%",
                            threshold=f"{stop_cfg.trailing_stop:.1f}%(ATR不可用)",
                            time=now_str,
                        ))
            else:
                # 固定比例模式（原有逻辑）
                if cost_price > 0 and StopLossChecker.check_fixed_stop_loss(
                    cost_price, current_price, stop_cfg.fixed_stop_loss / 100
                ):
                    loss_pct = (cost_price - current_price) / cost_price * 100
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type="固定止损触发",
                        level="danger",
                        current_value=f"亏损{loss_pct:.2f}%",
                        threshold=f"{stop_cfg.fixed_stop_loss:.1f}%",
                        time=now_str,
                    ))

                # 5. 移动止损
                if peak_price > 0 and StopLossChecker.check_trailing_stop_loss(
                    peak_price, current_price, stop_cfg.trailing_stop / 100
                ):
                    retrace_pct = (peak_price - current_price) / peak_price * 100
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type="移动止损触发",
                        level="warning",
                        current_value=f"回撤{retrace_pct:.2f}%",
                        threshold=f"{stop_cfg.trailing_stop:.1f}%",
                        time=now_str,
                    ))

            # 6. 趋势止损
            if trend_ma_value is not None and StopLossChecker.check_trend_stop_loss(
                current_price, trend_ma_value
            ):
                warnings.append(PositionWarningItem(
                    symbol=symbol,
                    type="趋势止损触发",
                    level="warning",
                    current_value=f"价格{current_price:.2f}",
                    threshold=f"MA{trend_ma_period}={trend_ma_value:.2f}",
                    time=now_str,
                ))

        except Exception:
            logger.warning("K 线查询失败，跳过标的: %s", symbol, exc_info=True)
            continue

    # 填充预警条目的成本价、当前价、盈亏比例和建议操作（需求 12）
    for w in warnings:
        sym = w.symbol
        c_price = _symbol_costs.get(sym)
        cur_price = _symbol_prices.get(sym)
        w.cost_price = c_price
        w.current_price = cur_price
        # 计算盈亏比例：pnl_pct = (current_price - cost_price) / cost_price * 100
        if c_price and c_price > 0 and cur_price is not None:
            w.pnl_pct = round((cur_price - c_price) / c_price * 100, 2)
        w.suggested_action = get_suggested_action(w.type)

    # 止损预警实时推送：当处于交易时段且检测到止损类预警时，通过 Redis Pub/Sub 发布
    if warnings and is_risk_alert_active(datetime.now()):
        stop_loss_types = {"固定止损触发", "移动止损触发", "趋势止损触发"}
        alert_channel = f"risk:alert:{user_id}"
        now = datetime.now()
        for w in warnings:
            if w.type in stop_loss_types:
                try:
                    alert_msg = build_stop_loss_alert_message(
                        symbol=w.symbol,
                        alert_type=w.type,
                        current_price=_symbol_prices.get(w.symbol, 0.0),
                        trigger_threshold=0.0,
                        alert_level=w.level,
                        trigger_time=now,
                    )
                    await redis.publish(alert_channel, alert_msg)
                except Exception:
                    logger.warning(
                        "发布止损预警消息失败: %s %s", w.symbol, w.type, exc_info=True,
                    )

    # 风控事件日志记录：将检测到的预警事件写入数据库（需求 10）
    if warnings:
        _EVENT_TYPE_MAP = {
            "单股仓位超限": "POSITION_LIMIT",
            "固定止损触发": "STOP_LOSS",
            "移动止损触发": "STOP_LOSS",
            "趋势止损触发": "STOP_LOSS",
            "急跌破位预警": "BREAKDOWN",
            "阴跌破位预警": "BREAKDOWN",
        }
        now_dt = datetime.now()
        for w in warnings:
            event_type = _EVENT_TYPE_MAP.get(w.type, "POSITION_LIMIT")
            # 行业仓位超限也归类为 POSITION_LIMIT
            if "行业仓位超限" in w.type:
                event_type = "POSITION_LIMIT"
            await RiskEventLogger.log_event(
                session=pg_session,
                user_id=user_id,
                event_type=event_type,
                symbol=w.symbol,
                rule_name=w.type,
                trigger_value=0.0,
                threshold=0.0,
                result="WARNING",
                triggered_at=now_dt,
            )

    return warnings


# ---------------------------------------------------------------------------
# 策略健康状态 — GET /risk/strategy-health
# ---------------------------------------------------------------------------


@router.get("/risk/strategy-health", response_model=StrategyHealthResponse)
async def strategy_health(
    strategy_id: UUID | None = Query(None),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StrategyHealthResponse:
    """查询策略健康状态（回测指标 + 实盘指标）。"""
    user_id = _DEFAULT_USER_ID

    # --- 回测指标 ---
    bt_win_rate = 0.0
    bt_max_drawdown = 0.0
    bt_is_healthy = True
    bt_warnings: list[str] = []

    if strategy_id is not None:
        stmt = (
            select(BacktestRun)
            .where(
                BacktestRun.strategy_id == strategy_id,
                BacktestRun.status == "DONE",
            )
            .order_by(BacktestRun.created_at.desc())
            .limit(1)
        )
        result = await pg_session.execute(stmt)
        run = result.scalar_one_or_none()

        if run is not None and run.result is not None:
            bt_result = run.result
            bt_win_rate = float(bt_result.get("win_rate", 0))
            bt_max_drawdown = float(bt_result.get("max_drawdown", 0))

            is_unhealthy = StopLossChecker.check_strategy_health(bt_win_rate, bt_max_drawdown)
            bt_is_healthy = not is_unhealthy

            if bt_win_rate < 0.5:
                bt_warnings.append(f"策略胜率 {bt_win_rate * 100:.1f}% 低于 50%")
            if bt_max_drawdown > 0.15:
                bt_warnings.append(f"最大回撤 {bt_max_drawdown * 100:.1f}% 超过 15%")

    # --- 实盘指标（需求 8）---
    # 查询 status=FILLED 的实盘交易记录，计算实盘健康指标
    live_stmt = (
        select(TradeOrder)
        .where(
            TradeOrder.user_id == user_id,
            TradeOrder.status == "FILLED",
        )
        .order_by(TradeOrder.filled_at.asc())
    )
    live_result = await pg_session.execute(live_stmt)
    live_orders = live_result.scalars().all()

    # 将成交记录转换为 PnL 记录
    # 简化实现：配对买卖计算 PnL（按 symbol 分组，FIFO 匹配）
    trade_records: list[dict] = []
    buy_queue: dict[str, list[dict]] = {}  # symbol → [{"price": ..., "qty": ...}]

    for order in live_orders:
        symbol = order.symbol or ""
        price = float(order.filled_price or order.price or 0)
        qty = order.filled_qty or order.quantity or 0

        if order.direction == "BUY":
            if symbol not in buy_queue:
                buy_queue[symbol] = []
            buy_queue[symbol].append({"price": price, "qty": qty})
        elif order.direction == "SELL":
            # FIFO 匹配买入记录
            remaining_qty = qty
            pnl = 0.0
            if symbol in buy_queue:
                while remaining_qty > 0 and buy_queue[symbol]:
                    buy = buy_queue[symbol][0]
                    match_qty = min(remaining_qty, buy["qty"])
                    pnl += (price - buy["price"]) * match_qty
                    remaining_qty -= match_qty
                    buy["qty"] -= match_qty
                    if buy["qty"] <= 0:
                        buy_queue[symbol].pop(0)
            # 未匹配的卖出部分按卖出价计算（无成本基准，PnL 为 0）
            trade_records.append({"pnl": pnl})

    live_health = StrategyHealthMonitor.compute_live_health_pure(trade_records)

    # 实盘预警追加到 warnings
    if live_health["data_sufficient"]:
        if live_health["win_rate"] < 0.4:
            bt_warnings.append(f"实盘胜率 {live_health['win_rate'] * 100:.1f}% 低于 40%")
        if live_health["max_drawdown"] > 0.2:
            bt_warnings.append(f"实盘最大回撤 {live_health['max_drawdown'] * 100:.1f}% 超过 20%")
    else:
        if trade_records:
            bt_warnings.append("实盘数据不足，仅供参考")

    return StrategyHealthResponse(
        strategy_id=str(strategy_id) if strategy_id else None,
        win_rate=bt_win_rate,
        max_drawdown=bt_max_drawdown,
        is_healthy=bt_is_healthy,
        warnings=bt_warnings,
        live_win_rate=live_health["win_rate"],
        live_max_drawdown=live_health["max_drawdown"],
        live_is_healthy=live_health["is_healthy"],
        live_data_sufficient=live_health["data_sufficient"],
    )


# ---------------------------------------------------------------------------
# 风控事件日志 — GET /risk/event-log（需求 10）
# ---------------------------------------------------------------------------


class RiskEventLogItem(BaseModel):
    """风控事件日志条目"""
    id: str
    user_id: str
    event_type: str
    symbol: str | None = None
    rule_name: str
    trigger_value: float
    threshold: float
    result: str
    triggered_at: str
    created_at: str


class RiskEventLogPageResponse(BaseModel):
    """风控事件日志分页响应"""
    total: int
    items: list[RiskEventLogItem]


@router.get("/risk/event-log", response_model=RiskEventLogPageResponse)
async def risk_event_log(
    start_date: str | None = Query(None, description="起始日期（ISO 格式，如 2024-01-01）"),
    end_date: str | None = Query(None, description="结束日期（ISO 格式，如 2024-12-31）"),
    event_type: str | None = Query(None, description="事件类型筛选"),
    symbol: str | None = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> RiskEventLogPageResponse:
    """查询风控事件历史日志（分页+筛选）。

    支持按时间范围、事件类型和股票代码筛选。
    """
    from app.models.risk_event import RiskEventLog

    user_id = _DEFAULT_USER_ID

    # 构建筛选条件
    conditions = [RiskEventLog.user_id == user_id]

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            conditions.append(RiskEventLog.triggered_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式无效")

    if end_date:
        try:
            # 结束日期包含当天，设置为次日 00:00
            end_dt = datetime.fromisoformat(end_date)
            # 如果只传了日期（无时间部分），加一天
            if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                from datetime import timedelta
                end_dt = end_dt + timedelta(days=1)
            conditions.append(RiskEventLog.triggered_at < end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式无效")

    if event_type:
        conditions.append(RiskEventLog.event_type == event_type)

    if symbol:
        conditions.append(RiskEventLog.symbol == symbol)

    # 查询总数
    count_stmt = (
        select(func.count())
        .select_from(RiskEventLog)
        .where(*conditions)
    )
    total_result = await pg_session.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    data_stmt = (
        select(RiskEventLog)
        .where(*conditions)
        .order_by(RiskEventLog.triggered_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    data_result = await pg_session.execute(data_stmt)
    rows = data_result.scalars().all()

    items = [
        RiskEventLogItem(
            id=str(r.id),
            user_id=str(r.user_id),
            event_type=r.event_type,
            symbol=r.symbol,
            rule_name=r.rule_name,
            trigger_value=r.trigger_value,
            threshold=r.threshold,
            result=r.result,
            triggered_at=r.triggered_at.isoformat() if r.triggered_at else "",
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]

    return RiskEventLogPageResponse(total=total, items=items)


# ---------------------------------------------------------------------------
# 指数 K 线数据 — GET /risk/index-kline（需求 11）
# ---------------------------------------------------------------------------


@router.get("/risk/index-kline", response_model=list[IndexKlineItem])
async def index_kline(
    symbol: str = Query("000001.SH", description="指数代码，如 000001.SH"),
    ts_session: AsyncSession = Depends(get_ts_session),
) -> list[IndexKlineItem]:
    """返回指定指数最近 60 个交易日的 OHLC 数据及 MA20/MA60 值。

    查询 Kline 表中 freq='1d' 的记录，按时间升序返回。
    MA20/MA60 基于收盘价序列计算，数据不足时对应字段为 null。
    """
    # 查询最近 60 + 60 条记录（需要额外数据来计算 MA60）
    _MA_BUFFER = 60
    stmt = (
        select(Kline.time, Kline.open, Kline.high, Kline.low, Kline.close)
        .where(Kline.symbol == symbol, Kline.freq == "1d")
        .order_by(Kline.time.desc())
        .limit(_KLINE_LIMIT + _MA_BUFFER)
    )
    result = await ts_session.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    # 按时间升序排列
    rows = list(reversed(rows))

    # 提取收盘价序列用于计算均线
    closes = [float(r[4]) for r in rows if r[4] is not None]

    items: list[IndexKlineItem] = []
    # 只返回最近 _KLINE_LIMIT 条
    start_idx = max(len(rows) - _KLINE_LIMIT, 0)

    for i in range(start_idx, len(rows)):
        row = rows[i]
        if row[4] is None:
            continue

        # 计算 MA20：使用当前位置及之前共 20 个数据点
        ma20: float | None = None
        if i >= 19:
            window = closes[i - 19 : i + 1]
            if len(window) == 20:
                ma20 = round(sum(window) / 20, 4)

        # 计算 MA60：使用当前位置及之前共 60 个数据点
        ma60: float | None = None
        if i >= 59:
            window = closes[i - 59 : i + 1]
            if len(window) == 60:
                ma60 = round(sum(window) / 60, 4)

        items.append(IndexKlineItem(
            time=row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
            open=round(float(row[1]), 4) if row[1] is not None else 0.0,
            high=round(float(row[2]), 4) if row[2] is not None else 0.0,
            low=round(float(row[3]), 4) if row[3] is not None else 0.0,
            close=round(float(row[4]), 4),
            ma20=ma20,
            ma60=ma60,
        ))

    return items


# ---------------------------------------------------------------------------
# 黑名单 CRUD
# ---------------------------------------------------------------------------


@router.get("/blacklist", response_model=StockListPageResponse)
async def list_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StockListPageResponse:
    """查询黑名单列表（分页）。"""
    return await _list_stock_list(pg_session, "BLACK", _DEFAULT_USER_ID, page, page_size)


@router.post("/blacklist", status_code=201, response_model=StockListItemOut)
async def add_to_blacklist(
    body: StockListItemIn,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StockListItemOut:
    """添加股票到黑名单。"""
    # 检查是否已存在
    if _bw_manager.is_blacklisted(body.symbol):
        raise HTTPException(status_code=409, detail="该股票已在黑名单中")

    try:
        await _bw_manager.add_to_blacklist_persistent(
            symbol=body.symbol,
            reason=body.reason or "",
            session=pg_session,
            user_id=_DEFAULT_USER_ID,
        )
    except Exception:
        logger.exception("添加黑名单失败: %s", body.symbol)
        raise HTTPException(status_code=500, detail="数据库写入失败")

    return StockListItemOut(
        symbol=body.symbol,
        reason=body.reason,
        created_at=datetime.now().isoformat(),
    )


@router.delete("/blacklist/{symbol}")
async def remove_from_blacklist(
    symbol: str,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """从黑名单移除股票。"""
    if not _bw_manager.is_blacklisted(symbol):
        raise HTTPException(status_code=404, detail="记录不存在")

    try:
        await _bw_manager.remove_from_blacklist_persistent(
            symbol=symbol,
            session=pg_session,
            user_id=_DEFAULT_USER_ID,
        )
    except Exception:
        logger.exception("移除黑名单失败: %s", symbol)
        raise HTTPException(status_code=500, detail="数据库删除失败")

    return {"symbol": symbol, "deleted": True}


# ---------------------------------------------------------------------------
# 白名单 CRUD
# ---------------------------------------------------------------------------


@router.get("/whitelist", response_model=StockListPageResponse)
async def list_whitelist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StockListPageResponse:
    """查询白名单列表（分页）。"""
    return await _list_stock_list(pg_session, "WHITE", _DEFAULT_USER_ID, page, page_size)


@router.post("/whitelist", status_code=201, response_model=StockListItemOut)
async def add_to_whitelist(
    body: StockListItemIn,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StockListItemOut:
    """添加股票到白名单。"""
    # 检查是否已存在
    if _bw_manager.is_whitelisted(body.symbol):
        raise HTTPException(status_code=409, detail="该股票已在白名单中")

    try:
        await _bw_manager.add_to_whitelist_persistent(
            symbol=body.symbol,
            reason=body.reason,
            session=pg_session,
            user_id=_DEFAULT_USER_ID,
        )
    except Exception:
        logger.exception("添加白名单失败: %s", body.symbol)
        raise HTTPException(status_code=500, detail="数据库写入失败")

    return StockListItemOut(
        symbol=body.symbol,
        reason=body.reason,
        created_at=datetime.now().isoformat(),
    )


@router.delete("/whitelist/{symbol}")
async def remove_from_whitelist(
    symbol: str,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """从白名单移除股票。"""
    if not _bw_manager.is_whitelisted(symbol):
        raise HTTPException(status_code=404, detail="记录不存在")

    try:
        await _bw_manager.remove_from_whitelist_persistent(
            symbol=symbol,
            session=pg_session,
            user_id=_DEFAULT_USER_ID,
        )
    except Exception:
        logger.exception("移除白名单失败: %s", symbol)
        raise HTTPException(status_code=500, detail="数据库删除失败")

    return {"symbol": symbol, "deleted": True}
