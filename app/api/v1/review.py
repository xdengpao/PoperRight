"""
复盘分析 API

- GET /review/daily             — 每日复盘报告
- GET /review/strategy-report   — 策略绩效报表
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

router = APIRouter(prefix="/review", tags=["复盘分析"])


@router.get("/daily")
async def get_daily_review(
    review_date: date | None = Query(None, description="复盘日期，默认最近交易日"),
) -> dict:
    """获取每日复盘报告。"""
    target = review_date or date.today()
    return {
        "date": target.isoformat(),
        "win_rate": 0.0,
        "total_pnl": "0.00",
        "success_cases": [],
        "failure_cases": [],
        "market_review": {
            "sector_rotation": [],
            "trend_distribution": {},
            "money_flow": {},
        },
    }


@router.get("/strategy-report")
async def get_strategy_report(
    strategy_id: UUID | None = Query(None),
    period: Literal["daily", "weekly", "monthly"] = Query("daily"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> dict:
    """获取策略绩效报表（日/周/月）。"""
    return {
        "strategy_id": str(strategy_id) if strategy_id else None,
        "period": period,
        "returns": [],
        "risk_metrics": {},
        "comparison": [],
    }
