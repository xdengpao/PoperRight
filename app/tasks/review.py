"""
复盘定时任务

包含：
- generate_daily_review：盘后复盘报告生成（每日 15:45，Celery Beat）

对应需求：
- 需求 16.1：每个交易日收盘后自动生成当日复盘报告
- 需求 29.13：_load_trade_records() 从 PostgreSQL 加载交易记录
- 需求 29.14：_load_screen_results() 从 PostgreSQL 加载选股结果
- 需求 29.15：生成报告后写入 Redis 缓存
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from sqlalchemy import and_, cast, select
from sqlalchemy import Date as SADate

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionPG
from app.core.redis_client import get_redis_client
from app.models.strategy import ScreenResult
from app.models.trade import TradeOrder
from app.services.review_analyzer import ReviewAnalyzer
from app.tasks.base import ReviewTask

logger = logging.getLogger(__name__)

_REVIEW_CACHE_PREFIX = "review:daily:"
_REVIEW_CACHE_TTL = 7 * 24 * 3600  # 7 天


# ---------------------------------------------------------------------------
# 数据加载函数（Task 29.8.1, 29.8.2）
# ---------------------------------------------------------------------------


async def _async_load_trade_records(review_date: date) -> list[dict]:
    """异步加载当日已成交交易记录。"""
    async with AsyncSessionPG() as session:
        stmt = select(TradeOrder).where(
            and_(
                TradeOrder.status == "FILLED",
                cast(TradeOrder.filled_at, SADate) == review_date,
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "symbol": t.symbol,
                "profit": float((t.filled_price or 0) - (t.price or 0))
                * (t.filled_qty or 0)
                * (1 if t.direction == "BUY" else -1),
                "direction": t.direction,
                "price": float(t.price or 0),
                "quantity": t.filled_qty or 0,
            }
            for t in rows
        ]


def _load_trade_records(review_date: date) -> list[dict]:
    """
    从 PostgreSQL trade_order 表查询指定日期已成交交易记录。

    Celery 任务运行在同步上下文中，通过 asyncio.run() 包装异步 session。
    """
    return asyncio.run(_async_load_trade_records(review_date))


async def _async_load_screen_results(review_date: date) -> list[dict]:
    """异步加载当日盘后选股结果。"""
    async with AsyncSessionPG() as session:
        stmt = select(ScreenResult).where(
            and_(
                cast(ScreenResult.screen_time, SADate) == review_date,
                ScreenResult.screen_type == "EOD",
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "symbol": s.symbol,
                "trend_score": float(s.trend_score or 0),
                "risk_level": s.risk_level,
                "signals": s.signals or {},
            }
            for s in rows
        ]


def _load_screen_results(review_date: date) -> list[dict]:
    """
    从 PostgreSQL screen_result 表查询指定日期盘后选股结果（screen_type='EOD'）。
    """
    return asyncio.run(_async_load_screen_results(review_date))


# ---------------------------------------------------------------------------
# Redis 缓存写入辅助（Task 29.8.3）
# ---------------------------------------------------------------------------


async def _cache_review(key: str, data: dict) -> None:
    """将复盘结果写入 Redis。"""
    client = get_redis_client()
    try:
        await client.set(key, json.dumps(data, default=str), ex=_REVIEW_CACHE_TTL)
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Celery 任务
# ---------------------------------------------------------------------------


@celery_app.task(
    base=ReviewTask,
    name="app.tasks.review.generate_daily_review",
    bind=True,
    queue="review",
)
def generate_daily_review(self, review_date_str: str | None = None) -> dict:
    """
    每日复盘报告生成任务。

    由 Celery Beat 每个交易日 15:45 调度（daily-review-1545）。
    """
    review_date = (
        date.fromisoformat(review_date_str) if review_date_str else date.today()
    )
    logger.info("开始生成 %s 复盘报告", review_date.isoformat())

    trade_records = _load_trade_records(review_date)
    screen_results = _load_screen_results(review_date)

    analyzer = ReviewAnalyzer()
    review = analyzer.generate_daily_review(
        trade_records, screen_results, review_date=review_date,
    )

    result = {
        "date": review.date.isoformat(),
        "win_rate": review.win_rate,
        "total_pnl": review.total_pnl,
        "trade_count": review.total_trades,
        "success_cases": [
            {"symbol": c.get("symbol", ""), "pnl": float(c.get("profit", 0)), "reason": c.get("direction", "")}
            for c in review.successful_cases
        ],
        "failure_cases": [
            {"symbol": c.get("symbol", ""), "pnl": float(c.get("profit", 0)), "reason": c.get("direction", "")}
            for c in review.failed_cases
        ],
    }

    # 需求 29.15：写入 Redis 缓存
    cache_key = f"{_REVIEW_CACHE_PREFIX}{review_date.isoformat()}"
    try:
        asyncio.run(_cache_review(cache_key, result))
    except Exception:
        logger.warning("复盘报告缓存写入失败", exc_info=True)

    logger.info(
        "复盘报告生成完成: 总交易 %d 笔, 胜率 %.2f%%",
        review.total_trades,
        review.win_rate * 100,
    )

    return {"status": "success", **result}
