"""
复盘定时任务

包含：
- generate_daily_review：盘后复盘报告生成（每日 15:45，Celery Beat）

对应需求：
- 需求 16.1：每个交易日收盘后自动生成当日复盘报告
"""

from __future__ import annotations

import logging
from datetime import date

from app.core.celery_app import celery_app
from app.services.review_analyzer import ReviewAnalyzer
from app.tasks.base import ReviewTask

logger = logging.getLogger(__name__)


def _load_trade_records(review_date: date) -> list[dict]:
    """
    加载当日交易记录。

    生产环境从数据库读取当日已成交的交易记录；
    当前返回空列表作为占位。
    """
    return []


def _load_screen_results(review_date: date) -> list[dict]:
    """
    加载当日选股结果。

    生产环境从数据库读取当日选股结果；
    当前返回空列表作为占位。
    """
    return []


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

    Args:
        review_date_str: 可选的日期字符串（YYYY-MM-DD），默认今天。

    Returns:
        复盘结果摘要字典。
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

    logger.info(
        "复盘报告生成完成: 总交易 %d 笔, 胜率 %.2f%%",
        review.total_trades,
        review.win_rate * 100,
    )

    return {
        "status": "success",
        "date": review.date.isoformat(),
        "total_trades": review.total_trades,
        "win_rate": review.win_rate,
        "total_pnl": review.total_pnl,
        "winning_trades": review.winning_trades,
        "losing_trades": review.losing_trades,
    }
