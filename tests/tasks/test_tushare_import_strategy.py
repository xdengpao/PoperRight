"""Tushare 导入分批策略测试。"""

from __future__ import annotations

from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    ParamType,
    StorageEngine,
    TokenTier,
    get_entry,
)
from app.tasks.tushare_import import determine_batch_strategy


def _params(ts_code: str | None = None) -> dict:
    params = {"start_date": "20260101", "end_date": "20260429"}
    if ts_code:
        params["ts_code"] = ts_code
    return params


def test_full_market_daily_apis_route_by_trade_date_without_ts_code():
    """目标接口未传 ts_code 时走按交易日全市场导入。"""
    for api_name in ("stk_factor_pro", "daily_basic", "stk_limit"):
        entry = get_entry(api_name)
        assert entry is not None
        assert determine_batch_strategy(entry, _params()) == "by_trade_date"


def test_full_market_daily_apis_keep_compatible_path_with_ts_code():
    """显式传入 ts_code 时不走全市场交易日路径。"""
    for api_name in ("stk_factor_pro", "daily_basic", "stk_limit"):
        entry = get_entry(api_name)
        assert entry is not None
        assert determine_batch_strategy(entry, _params("000001.SZ")) == "by_date"


def test_unmarked_stock_optional_api_still_routes_by_code_and_date():
    """未显式标记的接口保持原有按股票和日期双分批逻辑。"""
    entry = ApiEntry(
        api_name="example",
        label="示例",
        category="stock_data",
        subcategory="test",
        token_tier=TokenTier.BASIC,
        target_table="example",
        storage_engine=StorageEngine.PG,
        code_format=CodeFormat.NONE,
        conflict_columns=[],
        required_params=[ParamType.DATE_RANGE],
        optional_params=[ParamType.STOCK_CODE],
        batch_by_date=True,
    )
    assert determine_batch_strategy(entry, _params()) == "by_code_and_date"
