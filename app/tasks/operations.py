"""
实操模块 Celery 定时任务

- post_market_screening: 盘后自动选股 + 候选筛选（每交易日 15:35）
- stop_loss_evaluation: 止损阶段评估（每交易日 15:40）
- daily_checklist: 复盘清单生成（每交易日 16:00）
- weekly_health_check: 周度策略健康检查（周五 17:00）
"""

import logging

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask

logger = logging.getLogger(__name__)


class OperationsTask(BaseTask):
    """实操模块任务基类（operations 队列）"""
    task_module = "operations"
    soft_time_limit = 300
    time_limit = 600


@celery_app.task(base=OperationsTask, name="app.tasks.operations.post_market_screening")
def post_market_screening() -> dict:
    """盘后自动选股 + 候选筛选"""
    import asyncio
    from datetime import date
    from sqlalchemy import select
    from app.core.database import async_pg_session
    from app.core.schemas import CandidateFilterConfig, MarketRiskLevel, PlanStatus
    from app.models.operations import TradingPlan
    from app.services.operations_service import OperationsService

    async def _run() -> dict:
        async with async_pg_session() as session:
            plans = (await session.execute(
                select(TradingPlan).where(TradingPlan.status == PlanStatus.ACTIVE.value)
            )).scalars().all()

            total_candidates = 0
            for plan in plans:
                filter_config = CandidateFilterConfig.from_dict(plan.candidate_filter)
                # 实际实现中调用 ScreenExecutor 执行选股
                # screen_result = await screen_executor.execute_eod(strategy_config)
                # filtered = OperationsService.filter_candidates_pure(
                #     screen_result.items, filter_config, market_risk
                # )
                # count = await OperationsService.save_candidates(
                #     session, plan.id, date.today(), filtered
                # )
                # total_candidates += count
                logger.info("盘后选股: plan=%s", plan.name)

            await session.commit()
            return {"plans_processed": len(plans), "total_candidates": total_candidates}

    return asyncio.run(_run())


@celery_app.task(base=OperationsTask, name="app.tasks.operations.stop_loss_evaluation")
def stop_loss_evaluation() -> dict:
    """止损阶段评估"""
    import asyncio
    from app.core.database import async_pg_session
    from app.services.operations_service import OperationsService

    async def _run() -> dict:
        async with async_pg_session() as session:
            # 实际实现中从行情接口获取 market_data
            market_data: dict = {}
            result = await OperationsService.run_stop_loss_evaluation(session, market_data)
            await session.commit()
            return result

    return asyncio.run(_run())


@celery_app.task(base=OperationsTask, name="app.tasks.operations.daily_checklist")
def daily_checklist() -> dict:
    """复盘清单生成"""
    import asyncio
    from datetime import date
    from sqlalchemy import select
    from app.core.database import async_pg_session
    from app.core.schemas import MarketRiskLevel, PlanStatus
    from app.models.operations import TradingPlan
    from app.services.operations_service import OperationsService

    async def _run() -> dict:
        async with async_pg_session() as session:
            plans = (await session.execute(
                select(TradingPlan).where(TradingPlan.status == PlanStatus.ACTIVE.value)
            )).scalars().all()

            generated = 0
            for plan in plans:
                # 实际实现中从行情接口获取 market_data 和 market_risk
                market_data: dict = {}
                market_risk = MarketRiskLevel.NORMAL
                await OperationsService.generate_checklist(
                    session, plan.id, date.today(), market_data, market_risk
                )
                generated += 1

            await session.commit()
            return {"checklists_generated": generated}

    return asyncio.run(_run())


@celery_app.task(base=OperationsTask, name="app.tasks.operations.weekly_health_check")
def weekly_health_check() -> dict:
    """周度策略健康检查"""
    logger.info("周度策略健康检查（待实现完整逻辑）")
    return {"status": "ok"}
