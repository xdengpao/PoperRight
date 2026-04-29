"""
实操模块编排服务（Operations Service）

将选股、风控、交易、复盘等现有服务串联为完整的交易工作流。
以 TradingPlan 为核心实体，实现：
- 交易计划 CRUD
- 盘后选股与候选股筛选
- 买入操作与仓位校验
- 分阶段止损状态机
- 每日复盘清单生成
- 市场环境适配
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import (
    CandidateFilterConfig,
    CandidateStatus,
    ChecklistLevel,
    MarketProfileConfig,
    MarketRiskLevel,
    PlanStatus,
    PositionControlConfig,
    PositionStatus,
    RiskCheckResult,
    ScreenItem,
    SignalFreshness,
    SignalStrength,
    StageStopConfig,
)
from app.models.operations import (
    BuyRecord,
    CandidateStock,
    DailyChecklist,
    MarketProfileLog,
    PlanPosition,
    TradingPlan,
)

logger = logging.getLogger(__name__)

_MAX_PLANS_PER_USER = 10

_PLAN_UPDATABLE_FIELDS = {"name", "candidate_filter", "stage_stop_config", "position_control", "market_profile"}

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(_TZ_SHANGHAI)


async def _get_plan_or_raise(session: AsyncSession, plan_id: UUID) -> "TradingPlan":
    plan = await session.get(TradingPlan, plan_id)
    if plan is None:
        raise ValueError("交易计划不存在")
    return plan


class OperationsService:
    """实操模块编排服务"""

    # ------------------------------------------------------------------
    # 交易计划 CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def create_plan(
        session: AsyncSession,
        user_id: UUID,
        name: str,
        strategy_id: UUID,
        candidate_filter: CandidateFilterConfig | None = None,
        stage_stop_config: StageStopConfig | None = None,
        position_control: PositionControlConfig | None = None,
        market_profile: MarketProfileConfig | None = None,
    ) -> TradingPlan:
        """创建交易计划，校验数量上限"""
        count = (await session.execute(
            select(func.count()).where(
                TradingPlan.user_id == user_id,
                TradingPlan.status != PlanStatus.ARCHIVED.value,
            )
        )).scalar_one()
        if count >= _MAX_PLANS_PER_USER:
            raise ValueError(f"交易计划数量已达上限（{_MAX_PLANS_PER_USER} 个）")

        plan = TradingPlan(
            user_id=user_id,
            name=name,
            strategy_id=strategy_id,
            status=PlanStatus.ACTIVE.value,
            candidate_filter=(candidate_filter or CandidateFilterConfig()).to_dict(),
            stage_stop_config=(stage_stop_config or StageStopConfig()).to_dict(),
            position_control=(position_control or PositionControlConfig()).to_dict(),
            market_profile=(market_profile or MarketProfileConfig()).to_dict(),
        )
        session.add(plan)
        await session.flush()
        return plan

    @staticmethod
    async def update_plan(
        session: AsyncSession,
        plan_id: UUID,
        updates: dict[str, Any],
    ) -> TradingPlan:
        """更新交易计划配置"""
        plan = await _get_plan_or_raise(session, plan_id)
        for key, value in updates.items():
            if key in _PLAN_UPDATABLE_FIELDS:
                setattr(plan, key, value)
        plan.updated_at = _now()
        await session.flush()
        return plan

    @staticmethod
    async def update_plan_status(
        session: AsyncSession,
        plan_id: UUID,
        status: PlanStatus,
    ) -> TradingPlan:
        """更新计划状态"""
        plan = await _get_plan_or_raise(session, plan_id)
        plan.status = status.value
        plan.updated_at = _now()
        await session.flush()
        return plan

    @staticmethod
    async def delete_plan(session: AsyncSession, plan_id: UUID) -> None:
        """删除交易计划（级联删除候选股、复盘清单等，保留买入记录和持仓）"""
        plan = await _get_plan_or_raise(session, plan_id)
        await session.delete(plan)
        await session.flush()

    @staticmethod
    async def list_plans(
        session: AsyncSession,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """查询用户所有交易计划，含概览统计"""
        plans = (await session.execute(
            select(TradingPlan).where(TradingPlan.user_id == user_id)
            .order_by(TradingPlan.created_at.desc())
        )).scalars().all()

        result = []
        for plan in plans:
            pos_count = (await session.execute(
                select(func.count()).where(
                    PlanPosition.plan_id == plan.id,
                    PlanPosition.status == PositionStatus.HOLDING.value,
                )
            )).scalar_one()

            today = date.today()
            candidate_count = (await session.execute(
                select(func.count()).where(
                    CandidateStock.plan_id == plan.id,
                    CandidateStock.screen_date == today,
                    CandidateStock.status == CandidateStatus.PENDING.value,
                )
            )).scalar_one()

            warning_count = (await session.execute(
                select(func.count()).where(
                    PlanPosition.plan_id == plan.id,
                    PlanPosition.status == PositionStatus.PENDING_SELL.value,
                )
            )).scalar_one()

            pc = PositionControlConfig.from_dict(plan.position_control)
            result.append({
                "id": str(plan.id),
                "name": plan.name,
                "strategy_id": str(plan.strategy_id),
                "status": plan.status,
                "position_count": pos_count,
                "max_positions": pc.max_positions,
                "candidate_count": candidate_count,
                "warning_count": warning_count,
                "created_at": plan.created_at.isoformat(),
            })
        return result

    # ------------------------------------------------------------------
    # 盘后选股与候选股筛选
    # ------------------------------------------------------------------

    @staticmethod
    def filter_candidates_pure(
        screen_items: list[ScreenItem],
        filter_config: CandidateFilterConfig,
        market_risk: MarketRiskLevel,
        blacklist: set[str] | None = None,
    ) -> list[ScreenItem]:
        """纯函数：对选股结果进行二次筛选"""
        if market_risk == MarketRiskLevel.DANGER:
            return []

        blacklist = blacklist or set()
        filtered = []
        for item in screen_items:
            if item.trend_score < filter_config.min_trend_score:
                continue
            if filter_config.exclude_fake_breakout and item.has_fake_breakout:
                continue
            if filter_config.require_new_signal and not item.has_new_signal:
                continue
            if filter_config.require_strong_signal:
                has_strong = any(
                    s.strength == SignalStrength.STRONG for s in item.signals
                )
                if not has_strong:
                    continue
            if item.symbol in blacklist:
                continue
            if item.risk_level and item.risk_level.value == "HIGH":
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    async def save_candidates(
        session: AsyncSession,
        plan_id: UUID,
        screen_date: date,
        items: list[ScreenItem],
    ) -> int:
        """将筛选后的候选股保存到数据库"""
        count = 0
        for item in items:
            risk_status = "NORMAL"
            if item.risk_level and item.risk_level.value == "HIGH":
                risk_status = "HIGH_RISK"

            signals_summary = [
                {"category": s.category.value, "label": s.label, "strength": s.strength.value}
                for s in item.signals[:10]
            ]
            candidate = CandidateStock(
                plan_id=plan_id,
                screen_date=screen_date,
                symbol=item.symbol,
                trend_score=Decimal(str(item.trend_score)),
                ref_buy_price=item.ref_buy_price,
                signal_strength=(
                    item.signals[0].strength.value if item.signals else SignalStrength.MEDIUM.value
                ),
                signal_freshness=(
                    SignalFreshness.NEW.value if item.has_new_signal else SignalFreshness.CONTINUING.value
                ),
                risk_status=risk_status,
                signals_summary=signals_summary,
                status=CandidateStatus.PENDING.value,
            )
            session.add(candidate)
            count += 1
        await session.flush()
        return count

    @staticmethod
    async def get_candidates(
        session: AsyncSession,
        plan_id: UUID,
        screen_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """查询候选股列表"""
        target = screen_date or date.today()
        rows = (await session.execute(
            select(CandidateStock).where(
                CandidateStock.plan_id == plan_id,
                CandidateStock.screen_date == target,
            ).order_by(CandidateStock.trend_score.desc())
        )).scalars().all()

        return [
            {
                "id": str(c.id),
                "symbol": c.symbol,
                "trend_score": float(c.trend_score) if c.trend_score else None,
                "ref_buy_price": float(c.ref_buy_price) if c.ref_buy_price else None,
                "signal_strength": c.signal_strength,
                "signal_freshness": c.signal_freshness,
                "sector_rank": c.sector_rank,
                "risk_status": c.risk_status,
                "signals_summary": c.signals_summary,
                "status": c.status,
                "screen_date": c.screen_date.isoformat(),
            }
            for c in rows
        ]

    @staticmethod
    async def skip_candidate(session: AsyncSession, candidate_id: UUID) -> None:
        """跳过候选股"""
        await session.execute(
            update(CandidateStock)
            .where(CandidateStock.id == candidate_id)
            .values(status=CandidateStatus.SKIPPED.value)
        )

    # ------------------------------------------------------------------
    # 买入操作
    # ------------------------------------------------------------------

    @staticmethod
    async def validate_position_control(
        session: AsyncSession,
        plan_id: UUID,
        buy_amount: Decimal,
        total_assets: Decimal,
        symbol_sector: str | None = None,
    ) -> RiskCheckResult:
        """仓位控制校验"""
        plan = await session.get(TradingPlan, plan_id)
        if plan is None:
            return RiskCheckResult(passed=False, reason="交易计划不存在")

        pc = PositionControlConfig.from_dict(plan.position_control)

        holding_count = (await session.execute(
            select(func.count()).where(
                PlanPosition.plan_id == plan_id,
                PlanPosition.status == PositionStatus.HOLDING.value,
            )
        )).scalar_one()
        if holding_count >= pc.max_positions:
            return RiskCheckResult(passed=False, reason=f"持仓数已达上限（{pc.max_positions} 只）")

        if total_assets > 0:
            stock_weight = float(buy_amount / total_assets) * 100
            if stock_weight > pc.max_stock_weight:
                return RiskCheckResult(
                    passed=False,
                    reason=f"单票仓位 {stock_weight:.1f}% 超过上限 {pc.max_stock_weight}%",
                )

        return RiskCheckResult(passed=True)

    @staticmethod
    async def execute_buy(
        session: AsyncSession,
        plan_id: UUID,
        candidate_id: UUID | None,
        symbol: str,
        buy_price: Decimal,
        buy_quantity: int,
        order_id: UUID | None = None,
        trend_score: Decimal | None = None,
        sector_rank: int | None = None,
        signals_snapshot: dict | None = None,
    ) -> BuyRecord:
        """执行买入，创建买入记录和持仓"""
        plan = await _get_plan_or_raise(session, plan_id)

        ssc = StageStopConfig.from_dict(plan.stage_stop_config)
        initial_stop = buy_price * (1 - Decimal(str(ssc.fixed_stop_pct / 100)))
        initial_stop = initial_stop.quantize(Decimal("0.0001"))

        now = _now()
        record = BuyRecord(
            plan_id=plan_id,
            candidate_id=candidate_id,
            order_id=order_id,
            symbol=symbol,
            buy_price=buy_price,
            buy_quantity=buy_quantity,
            buy_time=now,
            trend_score_at_buy=trend_score,
            sector_rank_at_buy=sector_rank,
            signals_at_buy=signals_snapshot,
            initial_stop_price=initial_stop,
            is_manual=(candidate_id is None),
        )
        session.add(record)
        await session.flush()

        position = PlanPosition(
            plan_id=plan_id,
            buy_record_id=record.id,
            symbol=symbol,
            quantity=buy_quantity,
            cost_price=buy_price,
            current_price=buy_price,
            stop_stage=1,
            stop_price=initial_stop,
            peak_price=buy_price,
            holding_days=0,
            latest_trend_score=trend_score,
            latest_sector_rank=sector_rank,
            status=PositionStatus.HOLDING.value,
            opened_at=now,
        )
        session.add(position)
        await session.flush()

        if candidate_id:
            await session.execute(
                update(CandidateStock)
                .where(CandidateStock.id == candidate_id)
                .values(status=CandidateStatus.BOUGHT.value)
            )

        return record

    @staticmethod
    async def get_plan_positions(
        session: AsyncSession,
        plan_id: UUID,
        status: PositionStatus | None = None,
    ) -> list[dict[str, Any]]:
        """查询计划持仓"""
        q = select(PlanPosition).where(PlanPosition.plan_id == plan_id)
        if status:
            q = q.where(PlanPosition.status == status.value)
        q = q.order_by(PlanPosition.opened_at.desc())
        rows = (await session.execute(q)).scalars().all()

        return [
            {
                "id": str(p.id),
                "symbol": p.symbol,
                "quantity": p.quantity,
                "cost_price": float(p.cost_price),
                "current_price": float(p.current_price) if p.current_price else None,
                "pnl_pct": p.pnl_pct,
                "holding_days": p.holding_days,
                "stop_stage": p.stop_stage,
                "stop_price": float(p.stop_price),
                "latest_trend_score": float(p.latest_trend_score) if p.latest_trend_score else None,
                "latest_sector_rank": p.latest_sector_rank,
                "status": p.status,
                "sell_signals": p.sell_signals,
                "opened_at": p.opened_at.isoformat(),
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in rows
        ]

    # ------------------------------------------------------------------
    # 分阶段止损状态机
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_stop_stage(
        cost_price: Decimal,
        current_price: Decimal,
        peak_price: Decimal,
        holding_days: int,
        ma_trend_score: float,
        ma20: float,
        config: StageStopConfig,
    ) -> tuple[int, Decimal, list[str]]:
        """
        纯函数：评估止损阶段，返回 (新阶段, 新止损价, 卖出信号列表)
        阶段只升不降（除非手动调整）
        """
        sell_signals: list[str] = []
        current_f = float(current_price)
        cost_f = float(cost_price)
        peak_f = float(peak_price)
        pnl_pct = (current_f - cost_f) / cost_f * 100 if cost_f > 0 else 0.0

        # 阶段5：趋势破位（最高优先级）
        if current_f < ma20:
            stop = current_price
            sell_signals.append(f"趋势破位：收盘价 {current_f:.2f} 跌破 MA20 {ma20:.2f}")
            return 5, stop, sell_signals

        # 阶段4：长期持仓
        if holding_days >= config.long_hold_days and ma_trend_score < config.long_hold_trend_threshold:
            stop = Decimal(str(ma20)).quantize(Decimal("0.0001"))
            sell_signals.append(
                f"长期持仓 {holding_days} 日，ma_trend {ma_trend_score:.1f} 低于 {config.long_hold_trend_threshold}"
            )
            return 4, stop, sell_signals

        # 阶段3：收紧移动止盈
        peak_pnl_pct = (peak_f - cost_f) / cost_f * 100 if cost_f > 0 else 0.0
        if peak_pnl_pct >= config.tight_trigger_pct:
            trailing = peak_f * (1 - config.tight_stop_pct / 100)
            stop = Decimal(str(trailing)).quantize(Decimal("0.0001"))
            if current_f <= trailing:
                sell_signals.append(
                    f"收紧止盈触发：从最高价 {peak_f:.2f} 回撤 {config.tight_stop_pct}%"
                )
            return 3, stop, sell_signals

        # 阶段2：移动止盈
        if peak_pnl_pct >= config.trailing_trigger_pct:
            trailing = peak_f * (1 - config.trailing_stop_pct / 100)
            stop = Decimal(str(trailing)).quantize(Decimal("0.0001"))
            if current_f <= trailing:
                sell_signals.append(
                    f"移动止盈触发：从最高价 {peak_f:.2f} 回撤 {config.trailing_stop_pct}%"
                )
            return 2, stop, sell_signals

        # 阶段1：固定止损
        fixed_stop = cost_f * (1 - config.fixed_stop_pct / 100)
        stop = Decimal(str(fixed_stop)).quantize(Decimal("0.0001"))
        if current_f <= fixed_stop:
            sell_signals.append(f"固定止损触发：亏损达 {config.fixed_stop_pct}%")
        return 1, stop, sell_signals

    @staticmethod
    async def run_stop_loss_evaluation(
        session: AsyncSession,
        market_data: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        """
        批量评估所有 ACTIVE 计划的持仓止损阶段。
        market_data: {symbol: {"current_price": ..., "ma20": ..., "ma_trend_score": ...}}
        """
        plans = (await session.execute(
            select(TradingPlan).where(TradingPlan.status == PlanStatus.ACTIVE.value)
        )).scalars().all()

        updated = 0
        pending_sell = 0
        for plan in plans:
            config = StageStopConfig.from_dict(plan.stage_stop_config)
            positions = (await session.execute(
                select(PlanPosition).where(
                    PlanPosition.plan_id == plan.id,
                    PlanPosition.status == PositionStatus.HOLDING.value,
                )
            )).scalars().all()

            for pos in positions:
                try:
                    data = market_data.get(pos.symbol, {})
                    cp = Decimal(str(data.get("current_price", float(pos.current_price or 0))))
                    ma20 = data.get("ma20", 0.0)
                    trend = data.get("ma_trend_score", 0.0)

                    if cp > (pos.peak_price or Decimal("0")):
                        pos.peak_price = cp

                    new_stage, new_stop, signals = OperationsService.evaluate_stop_stage(
                        cost_price=pos.cost_price,
                        current_price=cp,
                        peak_price=pos.peak_price or cp,
                        holding_days=pos.holding_days + 1,
                        ma_trend_score=trend,
                        ma20=ma20,
                        config=config,
                    )

                    pos.current_price = cp
                    pos.holding_days += 1
                    pos.latest_trend_score = Decimal(str(trend)) if trend else None
                    if new_stage > pos.stop_stage:
                        pos.stop_stage = new_stage
                        pos.stop_price = new_stop
                    if signals:
                        pos.sell_signals = [{"signal": s, "time": _now().isoformat()} for s in signals]
                        pos.status = PositionStatus.PENDING_SELL.value
                        pending_sell += 1
                    pos.updated_at = _now()
                    updated += 1
                except Exception:
                    logger.exception("止损评估失败: position=%s symbol=%s", pos.id, pos.symbol)

        await session.flush()
        return {"updated": updated, "pending_sell": pending_sell}

    @staticmethod
    async def confirm_sell(
        session: AsyncSession,
        position_id: UUID,
        sell_price: Decimal,
        sell_quantity: int | None = None,
    ) -> PlanPosition:
        """确认卖出，关闭持仓"""
        pos = await session.get(PlanPosition, position_id)
        if pos is None:
            raise ValueError("持仓不存在")

        qty = sell_quantity or pos.quantity
        pnl = (sell_price - pos.cost_price) * qty
        pnl_pct = float(pnl / (pos.cost_price * qty)) if pos.cost_price * qty else 0.0

        pos.status = PositionStatus.CLOSED.value
        pos.sell_price = sell_price
        pos.sell_quantity = qty
        pos.pnl = pnl
        pos.pnl_pct = pnl_pct
        pos.closed_at = _now()
        pos.updated_at = _now()
        await session.flush()
        return pos

    @staticmethod
    async def adjust_stop(
        session: AsyncSession,
        position_id: UUID,
        new_stage: int | None = None,
        new_stop_price: Decimal | None = None,
    ) -> PlanPosition:
        """手动调整止损"""
        pos = await session.get(PlanPosition, position_id)
        if pos is None:
            raise ValueError("持仓不存在")
        if new_stage is not None:
            pos.stop_stage = new_stage
        if new_stop_price is not None:
            pos.stop_price = new_stop_price
        pos.updated_at = _now()
        await session.flush()
        return pos

    # ------------------------------------------------------------------
    # 每日复盘清单
    # ------------------------------------------------------------------

    @staticmethod
    async def generate_checklist(
        session: AsyncSession,
        plan_id: UUID,
        check_date: date,
        market_data: dict[str, dict[str, float]],
        market_risk: MarketRiskLevel,
        new_signal_count: int = 0,
    ) -> DailyChecklist:
        """生成每日复盘清单"""
        positions = (await session.execute(
            select(PlanPosition).where(
                PlanPosition.plan_id == plan_id,
                PlanPosition.status == PositionStatus.HOLDING.value,
            )
        )).scalars().all()

        items: list[dict] = []
        worst_level = ChecklistLevel.OK

        for pos in positions:
            data = market_data.get(pos.symbol, {})
            trend = data.get("ma_trend_score", 0.0)
            money_flow = data.get("money_flow", 0.0)
            sector_rank = data.get("sector_rank", 999)

            # 检查 ma_trend
            if trend < 65:
                level = ChecklistLevel.DANGER if trend < 50 else ChecklistLevel.WARNING
                items.append({
                    "dimension": "ma_trend", "symbol": pos.symbol,
                    "result": level.value, "value": trend, "threshold": 65,
                    "message": f"趋势评分 {trend:.1f} 低于阈值 65",
                    "action": "关注是否需要减仓" if level == ChecklistLevel.WARNING else "建议卖出",
                })
                if level.value == "DANGER":
                    worst_level = ChecklistLevel.DANGER
                elif worst_level != ChecklistLevel.DANGER:
                    worst_level = ChecklistLevel.WARNING

            # 检查 money_flow
            if money_flow <= 0:
                items.append({
                    "dimension": "money_flow", "symbol": pos.symbol,
                    "result": ChecklistLevel.WARNING.value, "value": money_flow, "threshold": 0,
                    "message": f"主力资金净流出 {money_flow:.0f}",
                    "action": "关注资金流向变化",
                })
                if worst_level == ChecklistLevel.OK:
                    worst_level = ChecklistLevel.WARNING

            # 检查板块排名
            if sector_rank > 30:
                level = ChecklistLevel.DANGER if sector_rank > 50 else ChecklistLevel.WARNING
                items.append({
                    "dimension": "sector_rank", "symbol": pos.symbol,
                    "result": level.value, "value": sector_rank, "threshold": 30,
                    "message": f"板块排名 {sector_rank} 跌出前 30",
                    "action": "板块退潮，关注是否需要减仓",
                })
                if level == ChecklistLevel.DANGER:
                    worst_level = ChecklistLevel.DANGER
                elif worst_level == ChecklistLevel.OK:
                    worst_level = ChecklistLevel.WARNING

        # 大盘风险等级变化
        if market_risk != MarketRiskLevel.NORMAL:
            level = ChecklistLevel.DANGER if market_risk == MarketRiskLevel.DANGER else ChecklistLevel.WARNING
            items.append({
                "dimension": "market_risk", "symbol": None,
                "result": level.value, "value": market_risk.value, "threshold": "NORMAL",
                "message": f"大盘风险等级: {market_risk.value}",
                "action": "DANGER 时暂停开仓" if market_risk == MarketRiskLevel.DANGER else "提高选股阈值",
            })
            if level == ChecklistLevel.DANGER:
                worst_level = ChecklistLevel.DANGER
            elif worst_level == ChecklistLevel.OK:
                worst_level = ChecklistLevel.WARNING

        # 新信号
        if new_signal_count > 0:
            items.append({
                "dimension": "new_signals", "symbol": None,
                "result": ChecklistLevel.OK.value, "value": new_signal_count, "threshold": 0,
                "message": f"今日新增 {new_signal_count} 个选股信号",
                "action": "查看候选股列表",
            })

        checklist = DailyChecklist(
            plan_id=plan_id,
            check_date=check_date,
            items=items,
            summary_level=worst_level.value,
        )
        session.add(checklist)
        await session.flush()
        return checklist

    @staticmethod
    async def get_checklist(
        session: AsyncSession,
        plan_id: UUID,
        check_date: date | None = None,
    ) -> dict[str, Any] | None:
        """查询复盘清单"""
        target = check_date or date.today()
        row = (await session.execute(
            select(DailyChecklist).where(
                DailyChecklist.plan_id == plan_id,
                DailyChecklist.check_date == target,
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "check_date": row.check_date.isoformat(),
            "items": row.items,
            "summary_level": row.summary_level,
            "strategy_health": row.strategy_health,
        }

    @staticmethod
    async def get_checklist_history(
        session: AsyncSession,
        plan_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """查询复盘清单历史"""
        rows = (await session.execute(
            select(DailyChecklist).where(
                DailyChecklist.plan_id == plan_id,
                DailyChecklist.check_date >= start_date,
                DailyChecklist.check_date <= end_date,
            ).order_by(DailyChecklist.check_date.desc())
        )).scalars().all()
        return [
            {
                "check_date": r.check_date.isoformat(),
                "summary_level": r.summary_level,
                "item_count": len(r.items) if r.items else 0,
                "strategy_health": r.strategy_health,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 市场环境适配
    # ------------------------------------------------------------------

    @staticmethod
    async def get_market_profile(
        session: AsyncSession,
        plan_id: UUID,
    ) -> MarketProfileConfig:
        """获取市场环境配置"""
        plan = await _get_plan_or_raise(session, plan_id)
        return MarketProfileConfig.from_dict(plan.market_profile)

    @staticmethod
    async def update_market_profile(
        session: AsyncSession,
        plan_id: UUID,
        config: MarketProfileConfig,
    ) -> None:
        """更新市场环境配置"""
        plan = await _get_plan_or_raise(session, plan_id)
        plan.market_profile = config.to_dict()
        plan.updated_at = _now()
        await session.flush()

    @staticmethod
    async def log_market_level_change(
        session: AsyncSession,
        plan_id: UUID,
        prev_level: MarketRiskLevel,
        new_level: MarketRiskLevel,
        trigger_reason: str,
        params_snapshot: dict,
    ) -> MarketProfileLog:
        """记录市场环境切换"""
        log = MarketProfileLog(
            plan_id=plan_id,
            changed_at=_now(),
            prev_level=prev_level.value,
            new_level=new_level.value,
            trigger_reason=trigger_reason,
            params_snapshot=params_snapshot,
        )
        session.add(log)
        await session.flush()
        return log

    # ------------------------------------------------------------------
    # 买入记录查询
    # ------------------------------------------------------------------

    @staticmethod
    async def get_buy_records(
        session: AsyncSession,
        plan_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """查询买入记录"""
        total = (await session.execute(
            select(func.count()).where(BuyRecord.plan_id == plan_id)
        )).scalar_one()

        rows = (await session.execute(
            select(BuyRecord).where(BuyRecord.plan_id == plan_id)
            .order_by(BuyRecord.buy_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(r.id),
                    "symbol": r.symbol,
                    "buy_price": float(r.buy_price),
                    "buy_quantity": r.buy_quantity,
                    "buy_time": r.buy_time.isoformat(),
                    "trend_score_at_buy": float(r.trend_score_at_buy) if r.trend_score_at_buy else None,
                    "sector_rank_at_buy": r.sector_rank_at_buy,
                    "initial_stop_price": float(r.initial_stop_price),
                    "is_manual": r.is_manual,
                    "signals_at_buy": r.signals_at_buy,
                }
                for r in rows
            ],
        }

    # ------------------------------------------------------------------
    # 手动执行选股
    # ------------------------------------------------------------------

    @staticmethod
    async def run_screening_for_plan(
        session: AsyncSession,
        plan_id: UUID,
        stocks_data: dict[str, dict],
        market_risk: MarketRiskLevel = MarketRiskLevel.NORMAL,
        blacklist: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        为指定交易计划执行选股。

        流程：
        1. 加载计划关联的策略模板
        2. 使用策略配置执行选股
        3. 使用计划的 candidate_filter 进行二次筛选
        4. 保存候选股到数据库

        Args:
            session: 数据库会话
            plan_id: 交易计划 ID
            stocks_data: 全市场股票因子数据 {symbol: factor_dict}
            market_risk: 当前市场风险等级
            blacklist: 黑名单股票集合

        Returns:
            {
                "screened_count": 选股数量,
                "filtered_count": 二次筛选后数量,
                "saved_count": 保存候选股数量,
                "screen_time": 选股时间,
            }
        """
        from app.models.strategy import StrategyTemplate
        from app.services.screener.screen_executor import ScreenExecutor
        from app.core.schemas import StrategyConfig

        # 1. 加载交易计划
        plan = await _get_plan_or_raise(session, plan_id)

        # 2. 加载关联的策略模板
        strategy = await session.get(StrategyTemplate, plan.strategy_id)
        if strategy is None:
            raise ValueError("关联的策略模板不存在")

        # 3. 构建策略配置
        config = StrategyConfig.from_dict(strategy.config)
        enabled_modules = list(strategy.enabled_modules) if strategy.enabled_modules else []

        # 4. 执行选股
        executor = ScreenExecutor(
            config,
            strategy_id=str(plan.strategy_id),
            enabled_modules=enabled_modules or None,
            raw_config=strategy.config,
        )
        result = executor.run_eod_screen(stocks_data)

        # 5. 二次筛选
        filter_config = CandidateFilterConfig.from_dict(plan.candidate_filter)
        filtered_items = OperationsService.filter_candidates_pure(
            screen_items=result.items,
            filter_config=filter_config,
            market_risk=market_risk,
            blacklist=blacklist,
        )

        # 6. 保存候选股
        saved_count = await OperationsService.save_candidates(
            session=session,
            plan_id=plan_id,
            screen_date=date.today(),
            items=filtered_items,
        )

        return {
            "screened_count": len(result.items),
            "filtered_count": len(filtered_items),
            "saved_count": saved_count,
            "screen_time": result.screen_time.isoformat(),
        }
