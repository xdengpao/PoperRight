"""
回测因子数据提供器

负责在回测环境中加载和计算完整的因子数据，对齐 ScreenDataProvider 的因子字典结构。
复用 ScreenDataProvider 的纯函数逻辑（百分位排名、行业相对值）和
SectorStrengthFilter 的纯函数逻辑（板块排名、多头趋势）。

需求：1, 2, 3, 4, 5, 6, 11, 12
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.services.screener.screen_data_provider import (
    ScreenDataProvider,
    _strip_market_suffix,
)
from app.services.screener.indicators import calculate_psy, calculate_obv_signal

logger = logging.getLogger(__name__)

# 所有 Tushare stk_factor 因子名
_STK_FACTOR_FIELDS = ("kdj_k", "kdj_d", "kdj_j", "cci", "wr", "trix", "bias")

# 筹码因子
_CHIP_FIELDS = (
    "chip_winner_rate", "chip_cost_5pct", "chip_cost_15pct",
    "chip_cost_50pct", "chip_weight_avg", "chip_concentration",
)

# 两融因子
_MARGIN_FIELDS = ("rzye_change", "rqye_ratio", "rzrq_balance_trend", "margin_net_buy")

# 增强资金流因子
_EMF_FIELDS = (
    "super_large_net_inflow", "large_net_inflow",
    "small_net_outflow", "money_flow_strength", "net_inflow_rate",
)

# 打板因子
_BOARD_FIELDS = (
    "limit_up_count", "limit_up_streak", "limit_up_open_pct",
    "dragon_tiger_net_buy", "first_limit_up",
)

# 指数因子
_INDEX_FIELDS = ("index_pe", "index_turnover", "index_ma_trend", "index_vol_ratio")


def enrich_factor_dicts(
    stocks_data: dict[str, dict[str, Any]],
    trade_date: date,
    enable_fundamental: bool = False,
    enable_money_flow: bool = False,
    enable_tushare: bool = False,
    fundamental_data: dict[str, dict[str, Any]] | None = None,
    money_flow_data: dict[str, dict[str, dict[str, Any]]] | None = None,
    tushare_factor_data: dict[str, dict[str, dict[str, Any]]] | None = None,
    sector_kline_data: list[dict] | None = None,
    stock_sector_map: dict[str, list[str]] | None = None,
    industry_map: dict[str, str] | None = None,
    sector_info_map: dict[str, str] | None = None,
    sector_top_n: int = 30,
) -> None:
    """
    就地丰富因子字典，添加基本面、资金面、Tushare因子、百分位排名、行业相对值和板块强势数据。
    """
    if not stocks_data:
        return

    _fill_fundamental_fields(stocks_data, fundamental_data, enable_fundamental)
    _fill_money_flow_fields(stocks_data, money_flow_data, trade_date, enable_money_flow)
    _fill_tushare_factor_fields(stocks_data, tushare_factor_data, trade_date, enable_tushare)
    _compute_psy_obv(stocks_data)
    _compute_volume_price(stocks_data)
    _compute_sector_strength(
        stocks_data, sector_kline_data, stock_sector_map,
        sector_info_map, sector_top_n,
    )
    _compute_conditional_percentile_ranks(stocks_data, enable_fundamental, enable_money_flow)
    _compute_conditional_industry_relative(stocks_data, industry_map, enable_fundamental)


def _fill_fundamental_fields(
    stocks_data: dict[str, dict[str, Any]],
    fundamental_data: dict[str, dict[str, Any]] | None,
    enabled: bool,
) -> None:
    """填充基本面因子字段。"""
    fields = ("pe_ttm", "pb", "roe", "market_cap", "profit_growth", "revenue_growth")
    for symbol, fd in stocks_data.items():
        if not enabled or fundamental_data is None:
            for f in fields:
                fd.setdefault(f, None)
            continue
        info = fundamental_data.get(symbol)
        if info is None:
            for f in fields:
                fd.setdefault(f, None)
            continue
        for f in fields:
            fd[f] = info.get(f)


def _fill_money_flow_fields(
    stocks_data: dict[str, dict[str, Any]],
    money_flow_data: dict[str, dict[str, dict[str, Any]]] | None,
    trade_date: date,
    enabled: bool,
) -> None:
    """填充资金面因子字段。"""
    date_str = trade_date.isoformat()
    for symbol, fd in stocks_data.items():
        if not enabled or money_flow_data is None:
            fd.setdefault("money_flow", None)
            fd.setdefault("large_order", None)
            fd.setdefault("main_net_inflow", None)
            fd.setdefault("large_order_ratio", None)
            continue
        sym_data = money_flow_data.get(symbol, {})
        day_data = sym_data.get(date_str)
        if day_data is None:
            fd.setdefault("money_flow", None)
            fd.setdefault("large_order", None)
            fd.setdefault("main_net_inflow", None)
            fd.setdefault("large_order_ratio", None)
            continue
        inflow = day_data.get("main_net_inflow")
        ratio = day_data.get("large_order_ratio")
        fd["main_net_inflow"] = inflow
        fd["large_order_ratio"] = ratio
        fd["money_flow"] = inflow is not None and inflow > 0
        fd["large_order"] = ratio is not None and ratio > 30.0


def _fill_tushare_factor_fields(
    stocks_data: dict[str, dict[str, Any]],
    tushare_factor_data: dict[str, dict[str, dict[str, Any]]] | None,
    trade_date: date,
    enabled: bool,
) -> None:
    """填充 Tushare 导入的因子字段。"""
    date_str = trade_date.strftime("%Y%m%d")
    all_fields = _STK_FACTOR_FIELDS + _CHIP_FIELDS + _MARGIN_FIELDS + _EMF_FIELDS + _BOARD_FIELDS + _INDEX_FIELDS
    board_defaults = {"limit_up_count": 0, "limit_up_streak": 0, "limit_up_open_pct": 0,
                      "dragon_tiger_net_buy": False, "first_limit_up": False}

    for symbol, fd in stocks_data.items():
        if not enabled or tushare_factor_data is None:
            for f in all_fields:
                fd.setdefault(f, board_defaults.get(f))
            continue
        sym_data = tushare_factor_data.get(symbol, {})
        day_data = sym_data.get(date_str, {})
        for f in all_fields:
            fd[f] = day_data.get(f, board_defaults.get(f))


def _compute_psy_obv(stocks_data: dict[str, dict[str, Any]]) -> None:
    """基于 K 线数据计算 PSY 和 OBV 因子（始终计算）。"""
    for fd in stocks_data.values():
        closes = fd.get("closes")
        volumes = fd.get("volumes")
        if closes and isinstance(closes, list):
            closes_f = [float(c) for c in closes]
            fd.setdefault("psy", calculate_psy(closes_f))
            if volumes and isinstance(volumes, list):
                volumes_i = [int(v) for v in volumes]
                fd.setdefault("obv_signal", calculate_obv_signal(closes_f, volumes_i))
            else:
                fd.setdefault("obv_signal", None)
        else:
            fd.setdefault("psy", None)
            fd.setdefault("obv_signal", None)


def _compute_volume_price(
    stocks_data: dict[str, dict[str, Any]],
    window: int = 20,
) -> None:
    """就地计算近 N 日日均成交额，写入 volume_price 字段。"""
    for fd in stocks_data.values():
        amounts = fd.get("amounts")
        if not amounts or not isinstance(amounts, list):
            fd["volume_price"] = None
            continue
        recent = amounts[-window:]
        valid = [float(a) for a in recent if a is not None]
        fd["volume_price"] = (sum(valid) / len(valid)) if valid else None


def _compute_sector_strength(
    stocks_data: dict[str, dict[str, Any]],
    sector_kline_data: list[dict] | None,
    stock_sector_map: dict[str, list[str]] | None,
    sector_info_map: dict[str, str] | None,
    sector_top_n: int = 30,
) -> None:
    """计算板块排名和趋势（始终计算，数据不可用时降级）。"""
    if not sector_kline_data or not stock_sector_map:
        for fd in stocks_data.values():
            fd.setdefault("sector_rank", None)
            fd.setdefault("sector_trend", False)
            fd.setdefault("sector_name", None)
        return

    # 按板块计算涨跌幅排名
    sector_changes: dict[str, float] = {}
    for rec in sector_kline_data:
        code = rec.get("sector_code", "")
        pct = rec.get("change_pct")
        if pct is not None:
            sector_changes[code] = float(pct)

    ranked = sorted(sector_changes.items(), key=lambda x: x[1], reverse=True)
    sector_rank_map: dict[str, int] = {code: i + 1 for i, (code, _) in enumerate(ranked)}

    for symbol, fd in stocks_data.items():
        sectors = stock_sector_map.get(symbol, [])
        if not sectors:
            fd["sector_rank"] = None
            fd["sector_trend"] = False
            fd["sector_name"] = None
            continue
        best_rank = None
        best_code = None
        for sc in sectors:
            r = sector_rank_map.get(sc)
            if r is not None and (best_rank is None or r < best_rank):
                best_rank = r
                best_code = sc
        fd["sector_rank"] = best_rank
        fd["sector_trend"] = best_rank is not None and best_rank <= sector_top_n
        fd["sector_name"] = sector_info_map.get(best_code, best_code) if best_code and sector_info_map else None


def _compute_conditional_percentile_ranks(
    stocks_data: dict[str, dict[str, Any]],
    enable_fundamental: bool,
    enable_money_flow: bool,
) -> None:
    """根据开关条件计算百分位排名。"""
    always_factors = ["volume_price"]
    money_flow_factors = ["money_flow"]
    fundamental_factors = ["roe", "profit_growth", "market_cap", "revenue_growth"]

    factors_to_compute = list(always_factors)
    if enable_money_flow:
        factors_to_compute.extend(money_flow_factors)
    if enable_fundamental:
        factors_to_compute.extend(fundamental_factors)

    if factors_to_compute:
        ScreenDataProvider._compute_percentile_ranks(stocks_data, factors_to_compute)

    # 未启用的因子 _pctl 设为 None
    all_pctl_factors = always_factors + money_flow_factors + fundamental_factors
    for f in all_pctl_factors:
        if f not in factors_to_compute:
            pctl_key = f"{f}_pctl"
            for fd in stocks_data.values():
                fd.setdefault(pctl_key, None)


def _compute_conditional_industry_relative(
    stocks_data: dict[str, dict[str, Any]],
    industry_map: dict[str, str] | None,
    enable_fundamental: bool,
) -> None:
    """根据开关条件计算行业相对值。"""
    if not enable_fundamental or not industry_map:
        for fd in stocks_data.values():
            fd.setdefault("pe_ind_rel", None)
            fd.setdefault("pb_ind_rel", None)
        return

    ScreenDataProvider._compute_industry_relative_values(
        stocks_data, ["pe_ttm", "pb"], industry_map,
    )
    # pe_ttm_ind_rel → pe_ind_rel
    for fd in stocks_data.values():
        if "pe_ttm_ind_rel" in fd:
            fd["pe_ind_rel"] = fd.pop("pe_ttm_ind_rel")
