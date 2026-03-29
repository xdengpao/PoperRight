"""
数据查询 API

- GET /kline/{symbol}     — 查询 K 线数据
- GET /stocks             — 查询股票列表（含过滤）
- GET /market/overview    — 查询大盘概况
- GET /sync/status        — 查询各数据源同步状态
- POST /sync              — 手动触发数据同步
- GET /exclusions         — 查询永久剔除名单
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Query

router = APIRouter(prefix="/data", tags=["数据查询"])


@router.get("/kline/{symbol}")
async def get_kline(
    symbol: str,
    freq: str = Query("1d", description="K线周期: 1m/5m/15m/30m/60m/1d/1w/1M"),
    start: date | None = Query(None, description="开始日期"),
    end: date | None = Query(None, description="结束日期"),
    adj_type: int = Query(0, description="复权类型: 0=不复权 1=前复权 2=后复权"),
) -> dict:
    """查询指定股票的 K 线数据。"""
    return {
        "symbol": symbol,
        "freq": freq,
        "adj_type": adj_type,
        "bars": [
            {
                "time": datetime(2024, 1, 2, 9, 30).isoformat(),
                "open": "10.00",
                "high": "10.50",
                "low": "9.90",
                "close": "10.30",
                "volume": 100000,
                "amount": "1030000.00",
                "turnover": "2.50",
                "vol_ratio": "1.20",
            }
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
    """查询大盘概况（指数、涨跌家数、市场情绪等）。"""
    return {
        "date": date.today().isoformat(),
        "sh_index": 3150.00,
        "sh_change_pct": 0.35,
        "sz_index": 10200.00,
        "sz_change_pct": 0.22,
        "cyb_index": 2050.00,
        "cyb_change_pct": -0.12,
        "advance_count": 2800,
        "decline_count": 1500,
        "limit_up_count": 45,
        "limit_down_count": 8,
        "market_sentiment": "NORMAL",
    }


@router.get("/market/sectors")
async def get_market_sectors() -> list:
    """查询板块涨幅排行。"""
    return [
        {"name": "半导体", "change_pct": 3.25, "leader": "中芯国际", "amount": 15_800_000_000},
        {"name": "新能源", "change_pct": 2.10, "leader": "宁德时代", "amount": 12_300_000_000},
        {"name": "医药生物", "change_pct": -0.85, "leader": "恒瑞医药", "amount": 8_500_000_000},
    ]


@router.get("/sync/status")
async def get_sync_status() -> dict:
    """查询各数据源同步状态。"""
    return {
        "items": [
            {
                "source": "行情数据",
                "last_sync_at": datetime(2024, 1, 2, 15, 0).isoformat(),
                "status": "OK",
                "record_count": 1250000,
            },
            {
                "source": "基本面数据",
                "last_sync_at": datetime(2024, 1, 2, 18, 0).isoformat(),
                "status": "OK",
                "record_count": 48000,
            },
            {
                "source": "资金流向",
                "last_sync_at": datetime(2024, 1, 2, 16, 30).isoformat(),
                "status": "OK",
                "record_count": 320000,
            },
        ]
    }


@router.post("/sync")
async def trigger_sync() -> dict:
    """手动触发数据同步任务。"""
    return {"message": "数据同步任务已触发，请稍后查看同步状态", "task_id": "sync-manual-001"}


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
