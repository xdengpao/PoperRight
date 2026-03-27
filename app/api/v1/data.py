"""
数据查询 API

- GET /kline/{symbol}     — 查询 K 线数据
- GET /stocks             — 查询股票列表（含过滤）
- GET /market/overview    — 查询大盘概况
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
        "indices": [
            {"name": "上证指数", "code": "000001", "close": "3150.00", "change_pct": 0.35},
            {"name": "创业板指", "code": "399006", "close": "2050.00", "change_pct": -0.12},
        ],
        "advance_decline": {"up": 2800, "down": 1500, "flat": 200},
        "limit_stats": {"limit_up": 45, "limit_down": 8},
        "market_sentiment": "NORMAL",
    }
