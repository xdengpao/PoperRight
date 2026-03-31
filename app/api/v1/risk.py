"""
风控 API

- GET  /risk/overview            — 大盘风控状态实时计算
- POST /risk/check               — 委托风控校验（短路求值）
- POST /risk/stop-config         — 保存止损止盈配置
- GET  /risk/stop-config         — 读取止损止盈配置
- GET  /risk/position-warnings   — 持仓预警实时检测
- GET  /risk/strategy-health     — 策略健康状态
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
from app.models.trade import Position as PositionModel
from app.services.risk_controller import (
    MarketRiskChecker,
    PositionRiskChecker,
    StockRiskFilter,
    StopLossChecker,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["风控"])

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_RISK_SEVERITY = {
    MarketRiskLevel.NORMAL: 0,
    MarketRiskLevel.CAUTION: 1,
    MarketRiskLevel.DANGER: 2,
}

_SH_SYMBOL = "000001.SH"
_CYB_SYMBOL = "399006.SZ"
_KLINE_LIMIT = 60

_STOP_CONFIG_TTL = 30 * 24 * 3600  # 30 days in seconds

# Placeholder user_id (real auth would inject this)
_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Pydantic 响应/请求模型
# ---------------------------------------------------------------------------


class RiskOverviewResponse(BaseModel):
    market_risk_level: str
    sh_above_ma20: bool
    sh_above_ma60: bool
    cyb_above_ma20: bool
    cyb_above_ma60: bool
    current_threshold: float
    data_insufficient: bool = False


class RiskCheckRequest(BaseModel):
    symbol: str
    direction: str = "BUY"
    quantity: int = 0
    price: float | None = None


class RiskCheckResponse(BaseModel):
    passed: bool
    reason: str | None = None


class StopConfigRequest(BaseModel):
    fixed_stop_loss: float = 8.0
    trailing_stop: float = 5.0
    trend_stop_ma: int = 20


class StopConfigResponse(BaseModel):
    fixed_stop_loss: float
    trailing_stop: float
    trend_stop_ma: int


class PositionWarningItem(BaseModel):
    symbol: str
    type: str
    level: str
    current_value: str
    threshold: str
    time: str


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
        return StopConfigResponse(**data)
    return StopConfigResponse(fixed_stop_loss=8.0, trailing_stop=5.0, trend_stop_ma=20)


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
    """获取大盘风控状态（实时计算上证指数 & 创业板指均线状态）。"""
    checker = MarketRiskChecker()

    try:
        sh_closes = await _fetch_closes(ts_session, _SH_SYMBOL)
        cyb_closes = await _fetch_closes(ts_session, _CYB_SYMBOL)
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

    if not sh_closes or not cyb_closes:
        return RiskOverviewResponse(
            market_risk_level=MarketRiskLevel.NORMAL.value,
            sh_above_ma20=True,
            sh_above_ma60=True,
            cyb_above_ma20=True,
            cyb_above_ma60=True,
            current_threshold=80.0,
            data_insufficient=True,
        )

    # 分别计算两个指数的风险等级
    sh_risk = checker.check_market_risk(sh_closes)
    cyb_risk = checker.check_market_risk(cyb_closes)

    # 取更严重的等级
    combined_risk = (
        sh_risk
        if _RISK_SEVERITY[sh_risk] >= _RISK_SEVERITY[cyb_risk]
        else cyb_risk
    )

    # 计算均线状态
    def _above_ma(closes: list[float], period: int) -> bool:
        ma = checker._simple_ma(closes, period)
        if ma is None:
            return True  # 数据不足时保守返回 True
        return closes[-1] >= ma

    return RiskOverviewResponse(
        market_risk_level=combined_risk.value,
        sh_above_ma20=_above_ma(sh_closes, 20),
        sh_above_ma60=_above_ma(sh_closes, 60),
        cyb_above_ma20=_above_ma(cyb_closes, 20),
        cyb_above_ma60=_above_ma(cyb_closes, 60),
        current_threshold=checker.get_trend_threshold(combined_risk),
        data_insufficient=False,
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

                # 4. 板块仓位检查 (简化：同 market 视为同板块)
                # 获取当前股票的 market 信息
                from app.models.stock import StockInfo
                info_stmt = select(StockInfo.board).where(StockInfo.symbol == body.symbol)
                info_result = await pg_session.execute(info_stmt)
                board = info_result.scalar_one_or_none()

                if board:
                    # 查询同板块所有持仓股票
                    all_symbols = [p.symbol for p in positions if p.symbol]
                    if all_symbols:
                        board_stmt = select(StockInfo.symbol).where(
                            StockInfo.symbol.in_(all_symbols),
                            StockInfo.board == board,
                        )
                        board_result = await pg_session.execute(board_stmt)
                        sector_symbols = set(board_result.scalars().all())

                        sector_value = sum(
                            float(p.cost_price or 0) * (p.quantity or 0)
                            for p in positions
                            if p.symbol in sector_symbols
                        )
                        sector_weight = (sector_value / total_value) * 100
                        check = PositionRiskChecker.check_sector_position_limit(sector_weight)
                        if not check.passed:
                            return RiskCheckResponse(passed=False, reason="板块仓位超过30%上限")
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
        "fixed_stop_loss": body.fixed_stop_loss,
        "trailing_stop": body.trailing_stop,
        "trend_stop_ma": body.trend_stop_ma,
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

    for pos in positions:
        symbol = pos.symbol
        if not symbol:
            continue

        cost_price = float(pos.cost_price or 0)
        quantity = pos.quantity or 0
        stock_value = cost_price * quantity

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

        # 2. 板块仓位检查
        try:
            from app.models.stock import StockInfo
            info_stmt = select(StockInfo.board).where(StockInfo.symbol == symbol)
            info_result = await pg_session.execute(info_stmt)
            board = info_result.scalar_one_or_none()
            if board:
                all_symbols = [p.symbol for p in positions if p.symbol]
                board_stmt = select(StockInfo.symbol).where(
                    StockInfo.symbol.in_(all_symbols),
                    StockInfo.board == board,
                )
                board_result = await pg_session.execute(board_stmt)
                sector_symbols = set(board_result.scalars().all())
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
                        type="板块仓位超限",
                        level="warning",
                        current_value=f"{sector_weight:.2f}%",
                        threshold="30.00%",
                        time=now_str,
                    ))
        except Exception:
            logger.warning("板块仓位检查失败: %s", symbol, exc_info=True)

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

            # 3. 破位预警
            if ma20 is not None:
                if PositionRiskChecker.check_position_breakdown(
                    current_price, ma20, daily_change, volume_ratio
                ):
                    warnings.append(PositionWarningItem(
                        symbol=symbol,
                        type="持仓破位预警",
                        level="danger",
                        current_value=f"价格{current_price:.2f} < MA20({ma20:.2f})",
                        threshold="跌破MA20+放量下跌>5%",
                        time=now_str,
                    ))

            # 4. 固定止损
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

    return warnings


# ---------------------------------------------------------------------------
# 策略健康状态 — GET /risk/strategy-health
# ---------------------------------------------------------------------------


@router.get("/risk/strategy-health", response_model=StrategyHealthResponse)
async def strategy_health(
    strategy_id: UUID | None = Query(None),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> StrategyHealthResponse:
    """查询策略健康状态（胜率、最大回撤等）。"""
    if strategy_id is None:
        return StrategyHealthResponse()

    # 查询该策略最新回测结果
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

    if run is None or run.result is None:
        return StrategyHealthResponse(strategy_id=str(strategy_id))

    # 从 JSONB result 中提取胜率和最大回撤
    bt_result = run.result
    win_rate = float(bt_result.get("win_rate", 0))
    max_drawdown = float(bt_result.get("max_drawdown", 0))

    is_unhealthy = StopLossChecker.check_strategy_health(win_rate, max_drawdown)
    is_healthy = not is_unhealthy

    warnings: list[str] = []
    if win_rate < 0.5:
        warnings.append(f"策略胜率 {win_rate * 100:.1f}% 低于 50%")
    if max_drawdown > 0.15:
        warnings.append(f"最大回撤 {max_drawdown * 100:.1f}% 超过 15%")

    return StrategyHealthResponse(
        strategy_id=str(strategy_id),
        win_rate=win_rate,
        max_drawdown=max_drawdown,
        is_healthy=is_healthy,
        warnings=warnings,
    )


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
    return await _add_to_stock_list(pg_session, "BLACK", _DEFAULT_USER_ID, body.symbol, body.reason)


@router.delete("/blacklist/{symbol}")
async def remove_from_blacklist(
    symbol: str,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """从黑名单移除股票。"""
    await _remove_from_stock_list(pg_session, "BLACK", _DEFAULT_USER_ID, symbol)
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
    return await _add_to_stock_list(pg_session, "WHITE", _DEFAULT_USER_ID, body.symbol, body.reason)


@router.delete("/whitelist/{symbol}")
async def remove_from_whitelist(
    symbol: str,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """从白名单移除股票。"""
    await _remove_from_stock_list(pg_session, "WHITE", _DEFAULT_USER_ID, symbol)
    return {"symbol": symbol, "deleted": True}
