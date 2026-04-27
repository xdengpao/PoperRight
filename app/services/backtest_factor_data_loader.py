"""
回测因子数据加载器

从数据库批量加载回测所需的因子数据源（基本面、资金流向、Tushare因子、板块数据）。
使用同步数据库访问，与现有 K 线加载方式一致。

需求：1, 2, 8, 11
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_sync_pg_url() -> str:
    settings = get_settings()
    return str(settings.database_url).replace("+asyncpg", "")


def _strip_suffix(ts_code: str) -> str:
    return ts_code.split(".")[0] if "." in ts_code else ts_code


def load_factor_data(
    enable_fundamental: bool = False,
    enable_money_flow: bool = False,
    enable_tushare: bool = False,
    symbols: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    strategy_config: Any = None,
) -> dict[str, Any]:
    """批量加载回测因子数据，返回各数据源的映射字典。"""
    result: dict[str, Any] = {}
    pg_url = _get_sync_pg_url()

    if enable_fundamental:
        result["fundamental"] = _load_fundamental(pg_url)

    if enable_money_flow and start_date and end_date:
        result["money_flow"] = _load_money_flow(pg_url, start_date, end_date)

    if enable_tushare and start_date and end_date:
        result["tushare_factors"] = _load_tushare_factors(pg_url, start_date, end_date)

    # 板块数据始终尝试加载
    sector_data = _load_sector_data(pg_url, strategy_config, enable_fundamental)
    result.update(sector_data)

    return result


def _load_fundamental(pg_url: str) -> dict[str, dict[str, Any]]:
    """从 stock_info 表批量加载基本面数据。"""
    try:
        engine = create_engine(pg_url)
        with Session(engine) as session:
            rows = session.execute(text(
                "SELECT symbol, pe_ttm, pb, roe, market_cap FROM stock_info"
            )).fetchall()
        engine.dispose()
        return {
            row[0]: {
                "pe_ttm": float(row[1]) if row[1] is not None else None,
                "pb": float(row[2]) if row[2] is not None else None,
                "roe": float(row[3]) if row[3] is not None else None,
                "market_cap": float(row[4]) if row[4] is not None else None,
            }
            for row in rows
        }
    except Exception as exc:
        logger.warning("基本面数据加载失败: %s", exc)
        return {}


def _load_money_flow(pg_url: str, start_date: date, end_date: date) -> dict[str, dict[str, dict]]:
    """从 money_flow 表批量加载资金流向数据。"""
    try:
        engine = create_engine(pg_url)
        with Session(engine) as session:
            rows = session.execute(text("""
                SELECT symbol, trade_date, main_net_inflow, large_order_ratio
                FROM money_flow
                WHERE trade_date >= :start AND trade_date <= :end
            """), {"start": start_date.isoformat(), "end": end_date.isoformat()}).fetchall()
        engine.dispose()
        result: dict[str, dict[str, dict]] = {}
        for row in rows:
            sym = row[0]
            td = row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1])
            raw_ratio = float(row[3]) if row[3] is not None else None
            ratio = raw_ratio * 100.0 if raw_ratio is not None and raw_ratio <= 1.0 else raw_ratio
            if sym not in result:
                result[sym] = {}
            result[sym][td] = {
                "main_net_inflow": float(row[2]) if row[2] is not None else None,
                "large_order_ratio": ratio,
            }
        return result
    except Exception as exc:
        logger.warning("资金流向数据加载失败: %s", exc)
        return {}


def _load_tushare_factors(pg_url: str, start_date: date, end_date: date) -> dict[str, dict[str, dict]]:
    """从 Tushare 导入表批量加载因子数据。"""
    result: dict[str, dict[str, dict]] = {}
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    try:
        engine = create_engine(pg_url)
        with Session(engine) as session:
            # stk_factor
            rows = session.execute(text("""
                SELECT ts_code, trade_date, kdj_k, kdj_d, kdj_j, cci, wr, trix, bias
                FROM stk_factor WHERE trade_date >= :s AND trade_date <= :e
            """), {"s": start_str, "e": end_str}).fetchall()
            for r in rows:
                sym = _strip_suffix(r[0])
                if sym not in result:
                    result[sym] = {}
                result[sym][r[1]] = {
                    "kdj_k": r[2], "kdj_d": r[3], "kdj_j": r[4],
                    "cci": r[5], "wr": r[6],
                    "trix": (r[7] is not None and r[7] > 0) if r[7] is not None else None,
                    "bias": r[8],
                }

            # cyq_perf
            rows = session.execute(text("""
                SELECT ts_code, trade_date, winner_rate, cost_5pct, cost_15pct, cost_50pct, weight_avg
                FROM cyq_perf WHERE trade_date >= :s AND trade_date <= :e
            """), {"s": start_str, "e": end_str}).fetchall()
            for r in rows:
                sym = _strip_suffix(r[0])
                entry = result.setdefault(sym, {}).setdefault(r[1], {})
                entry["chip_winner_rate"] = r[2]
                entry["chip_cost_5pct"] = r[3]
                entry["chip_cost_15pct"] = r[4]
                entry["chip_cost_50pct"] = r[5]
                entry["chip_weight_avg"] = r[6]
                c5 = r[3] if r[3] is not None else 50.0
                c15 = r[4] if r[4] is not None else 50.0
                c50 = r[5] if r[5] is not None else 50.0
                entry["chip_concentration"] = max(0.0, min(100.0, 100.0 - (c5 * 0.5 + c15 * 0.3 + c50 * 0.2)))

        engine.dispose()
        logger.info("Tushare 因子数据加载完成: %d 只股票", len(result))
    except Exception as exc:
        logger.warning("Tushare 因子数据加载失败: %s", exc)

    return result


def _load_sector_data(
    pg_url: str,
    strategy_config: Any = None,
    enable_fundamental: bool = False,
) -> dict[str, Any]:
    """加载板块数据（始终尝试）。"""
    result: dict[str, Any] = {
        "sector_kline": None,
        "stock_sector_map": None,
        "industry_map": None,
        "sector_info_map": None,
    }
    try:
        ds = "DC"
        if strategy_config and hasattr(strategy_config, 'sector_config'):
            ds = strategy_config.sector_config.sector_data_source

        engine = create_engine(pg_url)
        with Session(engine) as session:
            # 板块成分股映射（symbol 转为纯数字格式）
            rows = session.execute(text("""
                SELECT DISTINCT symbol, sector_code FROM sector_constituent
                WHERE data_source = :ds
            """), {"ds": ds}).fetchall()
            ssm: dict[str, list[str]] = {}
            for r in rows:
                bare = _strip_suffix(r[0])
                if r[1] not in ssm.get(bare, []):
                    ssm.setdefault(bare, []).append(r[1])
            result["stock_sector_map"] = ssm

            # 板块名称映射
            rows = session.execute(text("""
                SELECT sector_code, name FROM sector_info WHERE data_source = :ds
            """), {"ds": ds}).fetchall()
            result["sector_info_map"] = {r[0]: r[1] for r in rows}

            # 行业映射（symbol 转为纯数字格式）
            if enable_fundamental:
                rows = session.execute(text("""
                    SELECT DISTINCT ON (symbol) symbol, sector_code
                    FROM sector_constituent
                    WHERE data_source = :ds AND sector_code IN (
                        SELECT sector_code FROM sector_info
                        WHERE data_source = :ds AND sector_type = 'INDUSTRY'
                    )
                    ORDER BY symbol, trade_date DESC
                """), {"ds": ds}).fetchall()
                result["industry_map"] = {_strip_suffix(r[0]): r[1] for r in rows}

        engine.dispose()
        logger.info("板块数据加载完成: %d 只股票映射", len(ssm))
    except Exception as exc:
        logger.warning("板块数据加载失败: %s", exc)

    return result
