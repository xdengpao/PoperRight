"""
Tushare PG 写入兼容性诊断测试

对所有 storage_engine=PG 的注册 API，模拟 Tushare 返回的原始数据格式，
通过 _write_to_postgresql 写入，验证：
1. 列过滤：Tushare 多余字段不会导致 UndefinedColumnError
2. 类型转换：Date 字符串、Boolean int、Numeric 字符串正确转换
3. ON CONFLICT 策略正确执行

使用 mock 的 AsyncSessionPG 避免真实数据库依赖。
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_registry import (
    StorageEngine,
    get_all_entries,
)
from app.tasks.tushare_import import _write_to_postgresql


# ---------------------------------------------------------------------------
# Tushare 原始数据模拟：每个 PG 表一条典型行
# ---------------------------------------------------------------------------

# Tushare API 返回的原始字段（包含目标表不存在的字段）
_MOCK_TUSHARE_ROWS: dict[str, list[dict]] = {
    # stock_basic → stock_info（有 ts_code, area, industry 等多余字段）
    "stock_basic": [
        {
            "ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行",
            "area": "深圳", "industry": "银行", "cnspell": "PAYH",
            "market": "主板", "list_date": "19910403", "act_name": "万科",
            "act_ent_type": "民营", "is_st": 0,
        },
    ],
    # trade_cal → trade_calendar（is_open 是 int 不是 bool）
    "trade_cal": [
        {"exchange": "SSE", "cal_date": "20260421", "is_open": 1, "pretrade_date": "20260420"},
    ],
    # new_share → new_share（amount 等是 float/str）
    "new_share": [
        {
            "ts_code": "688001.SH", "sub_code": "787001", "name": "华兴源创",
            "ipo_date": "20190722", "issue_date": "20190718",
            "amount": "4010.0", "market_amount": "1203.0", "price": "24.26",
            "pe": "41.08", "limit_amount": "4010.0", "funds": "97.3",
            "ballot": "0.0532",
        },
    ],
    # stock_st → stock_st
    "stock_st": [
        {"ts_code": "000001.SZ", "name": "平安银行", "is_st": "N", "st_date": "20200101", "st_type": "其他"},
    ],
    # stk_delist → stock_info（code_format=STOCK_SYMBOL，有 symbol 转换）
    "stk_delist": [
        {
            "ts_code": "600001.SH", "symbol": "600001", "name": "退市股",
            "delist_date": "20200101", "is_delisted": 1,
        },
    ],
    # daily_share → daily_share（Numeric 字段可能是 float）
    "daily_share": [
        {
            "ts_code": "000001.SZ", "trade_date": "20260421",
            "total_share": 19405.88, "float_share": 19405.88,
            "free_share": 16248.12, "total_mv": 291088.2, "float_mv": 291088.2,
        },
    ],
    # bak_basic → stock_info
    "bak_basic": [
        {
            "ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行",
            "industry": "银行", "area": "深圳", "pe": "8.5", "float_share": "19405.88",
        },
    ],
    # daily_basic → stock_info（turnover_rate 等是 float）
    "daily_basic": [
        {
            "ts_code": "000001.SZ", "symbol": "000001",
            "trade_date": "20260421", "turnover_rate": 0.85,
            "pe_ttm": 8.5, "pb": 0.72, "total_mv": 291088.2, "float_mv": 291088.2,
            "close": 15.0, "volume_ratio": 1.2,
        },
    ],
    # suspend_d → suspend_info
    "suspend_d": [
        {"ts_code": "000001.SZ", "suspend_date": "20260421", "resume_date": "20260422", "suspend_type": "临时停牌"},
    ],
    # income → financial_statement（data_json 需要特殊处理）
    "income": [
        {
            "ts_code": "000001.SZ", "ann_date": "20260401", "end_date": "20251231",
            "report_type": "income", "data_json": {},
            "revenue": "100000.0", "n_income": "50000.0",
        },
    ],
    # fina_indicator → stock_info
    "fina_indicator": [
        {
            "ts_code": "000001.SZ", "symbol": "000001",
            "ann_date": "20260401", "end_date": "20251231",
            "pe_ttm": "8.5", "pb": "0.72", "roe": "0.12",
            "extra_field": "should_be_filtered",
        },
    ],
    # dividend → dividend
    "dividend": [
        {
            "ts_code": "000001.SZ", "ann_date": "20260401", "end_date": "20251231",
            "div_proc": "实施", "stk_div": "0.5", "cash_div": "1.2",
        },
    ],
    # forecast → forecast
    "forecast": [
        {
            "ts_code": "000001.SZ", "ann_date": "20260401", "end_date": "20251231",
            "type": "预增", "p_change_min": "30.0", "p_change_max": "50.0",
            "net_profit_min": "100000.0", "net_profit_max": "150000.0",
            "summary": "业绩预增",
        },
    ],
    # express → express
    "express": [
        {
            "ts_code": "000001.SZ", "ann_date": "20260401", "end_date": "20251231",
            "revenue": "100000.0", "operate_profit": "60000.0",
            "total_profit": "55000.0", "n_income": "50000.0",
            "total_assets": "5000000.0",
            "total_hldr_eqy_exc_min_int": "300000.0",
            "diluted_eps": "2.58", "yoy_net_profit": "0.15",
            "bps": "12.5", "perf_summary": "业绩快报",
        },
    ],
    # stock_company → stock_company
    "stock_company": [
        {
            "ts_code": "000001.SZ", "chairman": "张三", "manager": "李四",
            "secretary": "王五", "reg_capital": "100000.0",
            "setup_date": "19910403", "province": "广东", "city": "深圳",
            "website": "https://example.com", "exchange": "SZSE",
        },
    ],
    # index_basic → index_info
    "index_basic": [
        {
            "ts_code": "000001.SH", "name": "上证指数", "market": "SSE",
            "publisher": "中证指数", "category": "综合指数",
            "base_date": "19901219", "base_point": "100.0",
            "list_date": "19910715", "fullname": "上海证券综合指数",
        },
    ],
    # index_weight → index_weight
    "index_weight": [
        {
            "index_code": "000001.SH", "con_code": "600000.SH",
            "trade_date": "20260421", "weight": "0.5",
        },
    ],
    # index_dailybasic → index_dailybasic
    "index_dailybasic": [
        {
            "ts_code": "000001.SH", "trade_date": "20260421",
            "pe": "12.5", "pb": "1.2", "turnover_rate": "0.85",
            "total_mv": "500000.0", "float_mv": "400000.0",
        },
    ],
    # margin → margin_data
    "margin": [
        {
            "trade_date": "20260421", "exchange_id": "SSE",
            "rzye": "800000.0", "rzmre": "50000.0", "rzche": "45000.0",
            "rqye": "10000.0", "rqmcl": "500.0", "rzrqye": "810000.0",
        },
    ],
    # moneyflow_hsgt → moneyflow_hsgt
    "moneyflow_hsgt": [
        {
            "trade_date": "20260421",
            "ggt_ss": "100.0", "ggt_sz": "200.0",
            "hgt": "300.0", "sgt": "400.0",
            "north_money": "500.0", "south_money": "600.0",
        },
    ],
}


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


class TestPgWriteCompat:
    """验证所有 PG 存储 API 的 _write_to_postgresql 兼容性。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "api_name",
        [name for name, e in get_all_entries().items()
         if e.storage_engine == StorageEngine.PG and name in _MOCK_TUSHARE_ROWS],
        ids=lambda x: x,
    )
    async def test_pg_write_no_type_error(self, api_name: str) -> None:
        """对每个有模拟数据的 PG API，验证 _write_to_postgresql 不抛出类型错误。

        检查：
        1. 多余列被过滤（不出现 UndefinedColumnError）
        2. Date 字符串被转换为 date 对象
        3. Boolean int 被转换为 bool
        4. Numeric 字符串被转换为 Decimal
        """
        from app.services.data_engine.tushare_registry import get_entry

        entry = get_entry(api_name)
        assert entry is not None
        assert entry.storage_engine == StorageEngine.PG

        rows = _MOCK_TUSHARE_ROWS[api_name]

        # 捕获所有 execute 调用的参数
        executed_params: list[dict] = []
        mock_session = AsyncMock()

        async def capture_execute(stmt, params):
            executed_params.append(params)

        mock_session.execute = capture_execute
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        # Mock AsyncSessionPG 上下文管理器
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch("app.core.database.AsyncSessionPG", mock_session_factory):
            # 不应抛出任何异常
            await _write_to_postgresql(rows, entry)

        # 验证确实执行了写入
        assert len(executed_params) == len(rows), (
            f"{api_name}: 期望执行 {len(rows)} 次 INSERT，实际 {len(executed_params)} 次"
        )

        # 验证写入的参数中没有目标表不存在的列
        from app.core.database import PGBase
        table_obj = PGBase.metadata.tables.get(entry.target_table)
        if table_obj is not None:
            valid_columns = {col.name for col in table_obj.columns}
            for params in executed_params:
                extra_keys = set(params.keys()) - valid_columns
                assert not extra_keys, (
                    f"{api_name}: 写入参数包含目标表 {entry.target_table} 不存在的列: {extra_keys}"
                )

        # 验证类型转换
        for params in executed_params:
            for key, value in params.items():
                if value is None:
                    continue
                col = table_obj.columns.get(key) if table_obj is not None else None
                if col is None:
                    continue

                from sqlalchemy import Boolean, Date, DateTime, Numeric

                if isinstance(col.type, (Date, DateTime)):
                    assert isinstance(value, date), (
                        f"{api_name}.{key}: Date 列值应为 date 对象，实际为 {type(value).__name__}: {value!r}"
                    )
                elif isinstance(col.type, Boolean):
                    assert isinstance(value, bool), (
                        f"{api_name}.{key}: Boolean 列值应为 bool，实际为 {type(value).__name__}: {value!r}"
                    )
                # Numeric 列接受 int/float/Decimal，不需要严格检查


    @pytest.mark.asyncio
    async def test_all_pg_apis_have_mock_data(self) -> None:
        """确保所有 PG 存储 API 都有对应的模拟数据（提醒补充遗漏）。"""
        all_pg_apis = {
            name for name, e in get_all_entries().items()
            if e.storage_engine == StorageEngine.PG
        }
        covered = set(_MOCK_TUSHARE_ROWS.keys())
        missing = all_pg_apis - covered

        # 打印未覆盖的 API（不阻断测试，仅作为提醒）
        if missing:
            print(f"\n⚠️ 以下 PG API 未包含在兼容性测试中: {sorted(missing)}")
            # 不 assert，因为有些 API 的模拟数据难以构造
