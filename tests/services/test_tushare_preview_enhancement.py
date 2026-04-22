"""
TusharePreviewService 增强功能单元测试

覆盖：
- check_integrity: 时序数据完整性校验、非时序数据校验、不支持校验
- query_chart_data: 图表数据查询（升序、默认 limit、无时间字段）
- COUNT 估算: reltuples 大表估算与小表精确 COUNT
- 图表类型推断: 扩展后的 CHART_TYPE_MAP 映射

对应需求：2.1-2.8, 3.1-3.6, 5.6, 9.1-9.4, 10.1-10.4
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_preview_service import (
    CHART_TYPE_MAP,
    ChartDataResponse,
    CompletenessReport,
    KLINE_TABLES,
    TusharePreviewService,
)
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    FieldMapping,
    StorageEngine,
    TokenTier,
)


# ---------------------------------------------------------------------------
# Fixtures / 辅助函数
# ---------------------------------------------------------------------------


def _make_entry(**overrides) -> ApiEntry:
    """创建测试用 ApiEntry，可覆盖任意字段。"""
    defaults = dict(
        api_name="daily",
        label="日线行情",
        category="stock_data",
        subcategory="行情数据",
        token_tier=TokenTier.BASIC,
        target_table="kline",
        storage_engine=StorageEngine.TS,
        code_format=CodeFormat.STOCK_SYMBOL,
        conflict_columns=["time", "symbol", "freq", "adj_type"],
        field_mappings=[
            FieldMapping(source="ts_code", target="symbol"),
            FieldMapping(source="trade_date", target="time"),
            FieldMapping(source="open", target="open"),
            FieldMapping(source="close", target="close"),
        ],
        extra_config={"freq": "1d"},
    )
    defaults.update(overrides)
    return ApiEntry(**defaults)


@pytest.fixture
def svc() -> TusharePreviewService:
    """创建 TusharePreviewService 实例。"""
    return TusharePreviewService()


# ---------------------------------------------------------------------------
# 辅助：构建模拟 session
# ---------------------------------------------------------------------------


def _mock_fetchall_result(values: list) -> MagicMock:
    """创建模拟的 fetchall 结果，每个值包装为 (value,) 元组。"""
    result = MagicMock()
    result.fetchall.return_value = [(v,) for v in values]
    return result


def _mock_scalar_result(value) -> MagicMock:
    """创建模拟的 scalar 结果。"""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _mock_one_or_none_result(row) -> MagicMock:
    """创建模拟的 one_or_none 结果。"""
    result = MagicMock()
    result.one_or_none.return_value = row
    return result


def _mock_keys_result(keys: list[str]) -> MagicMock:
    """创建模拟的 keys 结果（用于 LIMIT 0 查询获取列名）。"""
    result = MagicMock()
    result.keys.return_value = keys
    return result


def _mock_mappings_result(rows: list[dict]) -> MagicMock:
    """创建模拟的 mappings().all() 结果。

    每个 mapping 对象支持 dict(r) 转换和 keys() 调用。
    使用自定义类替代 MagicMock 以确保 dict() 转换正常工作。
    """

    class FakeMapping:
        """模拟 SQLAlchemy RowMapping 对象。"""

        def __init__(self, data: dict):
            self._data = data

        def keys(self):
            return self._data.keys()

        def __iter__(self):
            return iter(self._data)

        def __getitem__(self, key):
            return self._data[key]

        def items(self):
            return self._data.items()

        def values(self):
            return self._data.values()

    result = MagicMock()
    mapping_objects = [FakeMapping(row) for row in rows]
    result.mappings.return_value.all.return_value = mapping_objects
    return result


def _make_async_session(side_effects: list) -> AsyncMock:
    """创建模拟的异步数据库 session 上下文管理器。

    Args:
        side_effects: execute 调用的返回值列表（按调用顺序）
    """
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=side_effects)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ===========================================================================
# 完整性校验测试
# ===========================================================================


class TestCheckIntegrity:
    """check_integrity 完整性校验测试。"""

    async def test_check_integrity_time_series_complete(
        self, svc: TusharePreviewService
    ) -> None:
        """时序数据完整时 missing_count=0。

        模拟交易日历返回 3 个交易日，目标表也包含这 3 个日期，
        校验结果应为完整（missing_count=0）。
        """
        entry = _make_entry(
            api_name="moneyflow",
            target_table="tushare_moneyflow",
            subcategory="资金流向数据",
            storage_engine=StorageEngine.TS,
            extra_config={},
        )

        # TS session: LIMIT 0 查询获取列名
        col_result = _mock_keys_result(["trade_date", "ts_code", "buy_sm_vol"])

        # TS session: 查询实际日期集合
        actual_dates_result = _mock_fetchall_result(
            ["20240102", "20240103", "20240104"]
        )

        ts_session = _make_async_session([col_result, actual_dates_result])

        # PG session: 查询交易日历
        cal_result = _mock_fetchall_result(
            ["20240102", "20240103", "20240104"]
        )
        pg_session = _make_async_session([cal_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"moneyflow": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
        ):
            result = await svc.check_integrity(
                "moneyflow",
                data_time_start="20240102",
                data_time_end="20240104",
            )

        assert isinstance(result, CompletenessReport)
        assert result.check_type == "time_series"
        assert result.missing_count == 0
        assert result.missing_items == []
        assert result.expected_count == 3
        assert result.actual_count == 3
        assert result.completeness_rate == 1.0

    async def test_check_integrity_time_series_with_gaps(
        self, svc: TusharePreviewService
    ) -> None:
        """时序数据有缺失时返回正确缺失日期。

        模拟交易日历返回 5 个交易日，目标表仅包含 3 个日期，
        校验结果应包含 2 个缺失日期。
        """
        entry = _make_entry(
            api_name="moneyflow",
            target_table="tushare_moneyflow",
            subcategory="资金流向数据",
            storage_engine=StorageEngine.TS,
            extra_config={},
        )

        # TS session: LIMIT 0 查询获取列名
        col_result = _mock_keys_result(["trade_date", "ts_code", "buy_sm_vol"])

        # TS session: 查询实际日期集合（缺少 20240103 和 20240105）
        actual_dates_result = _mock_fetchall_result(
            ["20240102", "20240104", "20240106"]
        )

        ts_session = _make_async_session([col_result, actual_dates_result])

        # PG session: 查询交易日历（5 个交易日）
        cal_result = _mock_fetchall_result(
            ["20240102", "20240103", "20240104", "20240105", "20240106"]
        )
        pg_session = _make_async_session([cal_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"moneyflow": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
        ):
            result = await svc.check_integrity(
                "moneyflow",
                data_time_start="20240102",
                data_time_end="20240106",
            )

        assert result.check_type == "time_series"
        assert result.missing_count == 2
        assert result.missing_items == ["20240103", "20240105"]
        assert result.expected_count == 5
        assert result.actual_count == 3
        assert result.time_range == {"start": "20240102", "end": "20240106"}

    async def test_check_integrity_code_based(
        self, svc: TusharePreviewService
    ) -> None:
        """非时序数据校验返回缺失代码。

        模拟 stock_info 返回 4 个代码，目标表仅包含 2 个代码，
        校验结果应包含 2 个缺失代码和提示信息。
        """
        # 使用无时间字段但有 ts_code 的表
        entry = _make_entry(
            api_name="stock_company",
            target_table="stock_company",
            subcategory="基础数据",
            storage_engine=StorageEngine.PG,
            extra_config={},
            field_mappings=[],
        )

        # PG session 1: LIMIT 0 查询获取列名（check_integrity 内部）
        col_result = _mock_keys_result(["ts_code", "company_name", "chairman"])

        # PG session 2: 查询 stock_info 获取预期代码集合
        expected_codes_result = _mock_fetchall_result(
            ["000001.SZ", "000002.SZ", "600000.SH", "600001.SH"]
        )

        # PG session 3: 查询目标表的实际代码集合
        actual_codes_result = _mock_fetchall_result(
            ["000001.SZ", "600000.SH"]
        )

        # 由于 check_integrity 内部会多次创建 session，
        # 需要让 AsyncSessionPG 返回不同的 session
        pg_sessions = [
            _make_async_session([col_result]),
            _make_async_session([expected_codes_result]),
            _make_async_session([actual_codes_result]),
        ]
        pg_session_iter = iter(pg_sessions)

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"stock_company": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                side_effect=lambda: next(pg_session_iter),
            ),
        ):
            result = await svc.check_integrity("stock_company")

        assert result.check_type == "code_based"
        assert result.missing_count == 2
        assert result.missing_items == ["000002.SZ", "600001.SH"]
        assert result.expected_count == 4
        assert result.actual_count == 2
        assert "预期集合基于全部 A 股代码" in result.message

    async def test_check_integrity_unsupported(
        self, svc: TusharePreviewService
    ) -> None:
        """不支持校验的表返回 unsupported。

        模拟一个既无时间字段也无 ts_code 列的表，
        校验结果应为 unsupported。
        """
        entry = _make_entry(
            api_name="hm_list",
            target_table="hm_list",
            subcategory="打板专题数据",
            storage_engine=StorageEngine.PG,
            extra_config={},
            field_mappings=[],
        )

        # PG session: LIMIT 0 查询获取列名（无 ts_code 列）
        col_result = _mock_keys_result(["id", "hm_name", "hm_type"])
        pg_session = _make_async_session([col_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"hm_list": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
        ):
            result = await svc.check_integrity("hm_list")

        assert result.check_type == "unsupported"
        assert result.missing_count == 0
        assert result.message == "该数据表不支持完整性校验"

    async def test_check_integrity_uses_sse_calendar(
        self, svc: TusharePreviewService
    ) -> None:
        """验证使用 SSE 交易日历。

        检查查询交易日历时传入的参数包含 exchange='SSE' 和 is_open=1。
        """
        entry = _make_entry(
            api_name="stk_limit",
            target_table="stk_limit",
            subcategory="行情数据",
            storage_engine=StorageEngine.TS,
            extra_config={},
        )

        # TS session: LIMIT 0 查询获取列名
        col_result = _mock_keys_result(["trade_date", "ts_code", "up_limit"])
        # TS session: 查询实际日期集合
        actual_dates_result = _mock_fetchall_result(["20240102"])
        ts_session = _make_async_session([col_result, actual_dates_result])

        # PG session: 查询交易日历
        cal_result = _mock_fetchall_result(["20240102"])
        pg_session = _make_async_session([cal_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"stk_limit": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
        ):
            await svc.check_integrity(
                "stk_limit",
                data_time_start="20240102",
                data_time_end="20240102",
            )

        # 验证 PG session 的 execute 调用参数包含 SSE 交易日历查询
        pg_execute_calls = pg_session.execute.call_args_list
        assert len(pg_execute_calls) >= 1
        # 检查交易日历查询的参数
        cal_call_params = pg_execute_calls[0][0][1]  # 第一个调用的第二个位置参数
        assert cal_call_params["exchange"] == "SSE"
        assert cal_call_params["is_open"] == 1

    async def test_check_integrity_applies_scope_filter(
        self, svc: TusharePreviewService
    ) -> None:
        """验证校验时应用作用域过滤。

        使用 kline 表（需要 freq 过滤），验证查询实际日期时
        SQL 中包含 scope_filter 条件。
        """
        entry = _make_entry(
            api_name="daily",
            target_table="kline",
            subcategory="行情数据",
            storage_engine=StorageEngine.TS,
            extra_config={"freq": "1d"},
        )

        # TS session 1: LIMIT 0 查询获取列名
        col_result = _mock_keys_result(["time", "symbol", "freq", "open", "close"])
        # TS session 2: 查询实际日期集合
        actual_dates_result = _mock_fetchall_result(["20240102"])
        ts_session = _make_async_session([col_result, actual_dates_result])

        # PG session: 查询交易日历
        cal_result = _mock_fetchall_result(["20240102"])
        pg_session = _make_async_session([cal_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"daily": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
        ):
            await svc.check_integrity(
                "daily",
                data_time_start="20240102",
                data_time_end="20240102",
            )

        # 验证 TS session 的第二个 execute 调用（查询实际日期）包含 scope_filter 参数
        ts_execute_calls = ts_session.execute.call_args_list
        # 第二个调用是查询实际日期集合
        actual_query_params = ts_execute_calls[1][0][1]  # 第二个调用的参数字典
        assert "scope_freq" in actual_query_params
        assert actual_query_params["scope_freq"] == "1d"


# ===========================================================================
# 图表数据查询测试
# ===========================================================================


class TestQueryChartData:
    """query_chart_data 图表数据查询测试。"""

    async def test_query_chart_data_returns_ascending_order(
        self, svc: TusharePreviewService
    ) -> None:
        """图表数据按时间升序返回。

        查询时按时间降序获取数据，返回前反转为升序。
        """
        entry = _make_entry(
            api_name="moneyflow",
            target_table="tushare_moneyflow",
            subcategory="资金流向数据",
            storage_engine=StorageEngine.TS,
            extra_config={},
        )

        # 模拟数据库返回降序数据
        rows_desc = [
            {"trade_date": "20240105", "ts_code": "000001.SZ", "buy_sm_vol": 300},
            {"trade_date": "20240104", "ts_code": "000001.SZ", "buy_sm_vol": 200},
            {"trade_date": "20240103", "ts_code": "000001.SZ", "buy_sm_vol": 100},
        ]

        # TS session: COUNT 查询 + 数据查询
        count_result = _mock_scalar_result(3)
        data_result = _mock_mappings_result(rows_desc)
        ts_session = _make_async_session([count_result, data_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"moneyflow": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
        ):
            result = await svc.query_chart_data("moneyflow", limit=3)

        assert isinstance(result, ChartDataResponse)
        # 验证数据按时间升序排列
        dates = [row["trade_date"] for row in result.rows]
        assert dates == ["20240103", "20240104", "20240105"]

    async def test_query_chart_data_default_limit_250(
        self, svc: TusharePreviewService
    ) -> None:
        """默认返回 250 条数据。

        不传 limit 参数时，SQL 中应使用 LIMIT 250。
        """
        entry = _make_entry(
            api_name="moneyflow",
            target_table="tushare_moneyflow",
            subcategory="资金流向数据",
            storage_engine=StorageEngine.TS,
            extra_config={},
        )

        # TS session: COUNT 查询 + 数据查询
        count_result = _mock_scalar_result(0)
        data_result = _mock_mappings_result([])
        # 空结果时需要 LIMIT 0 查询获取列名
        col_result = _mock_keys_result(["trade_date", "ts_code", "buy_sm_vol"])
        ts_session = _make_async_session([count_result, data_result, col_result])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"moneyflow": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
        ):
            result = await svc.query_chart_data("moneyflow")

        # 验证 SQL 中包含 LIMIT 250
        ts_execute_calls = ts_session.execute.call_args_list
        # 第二个调用是数据查询
        data_sql_text = str(ts_execute_calls[1][0][0])
        assert "LIMIT 250" in data_sql_text

    async def test_query_chart_data_no_time_field_returns_empty(
        self, svc: TusharePreviewService
    ) -> None:
        """无时间字段的表返回空 ChartDataResponse。

        当目标表没有时间字段时，应返回空数据和 chart_type=None。
        """
        # 使用无时间字段的表（如 stock_company，不在 TIME_FIELD_MAP 中）
        entry = _make_entry(
            api_name="stock_company",
            target_table="stock_company",
            subcategory="基础数据",
            storage_engine=StorageEngine.PG,
            extra_config={},
            field_mappings=[],
        )

        with patch.dict(
            "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
            {"stock_company": entry},
        ):
            result = await svc.query_chart_data("stock_company")

        assert isinstance(result, ChartDataResponse)
        assert result.rows == []
        assert result.time_field is None
        assert result.chart_type is None
        assert result.columns == []
        assert result.total_available == 0


# ===========================================================================
# COUNT 估算测试
# ===========================================================================


class TestEstimateCount:
    """COUNT 估算逻辑测试。"""

    def test_estimate_count_uses_reltuples_for_large_tables(self) -> None:
        """大表（reltuples > 1,000,000）使用估算值。

        当 reltuples 超过阈值时，返回 (True, int(reltuples))。
        """
        use_estimate, count = TusharePreviewService._estimate_count_pure(
            2_500_000.0
        )
        assert use_estimate is True
        assert count == 2_500_000

    def test_estimate_count_uses_exact_for_small_tables(self) -> None:
        """小表（reltuples <= 1,000,000）使用精确 COUNT。

        当 reltuples 不超过阈值时，返回 (False, 0)，表示需要精确 COUNT。
        """
        use_estimate, count = TusharePreviewService._estimate_count_pure(
            500_000.0
        )
        assert use_estimate is False
        assert count == 0

        # 边界值：恰好等于阈值时不使用估算
        use_estimate, count = TusharePreviewService._estimate_count_pure(
            1_000_000.0
        )
        assert use_estimate is False
        assert count == 0


# ===========================================================================
# 图表类型推断测试
# ===========================================================================


class TestInferChartTypeExpanded:
    """扩展后的图表类型推断测试。"""

    def test_infer_chart_type_expanded_mapping(self) -> None:
        """验证各 subcategory 的图表类型映射。

        测试 CHART_TYPE_MAP 中所有映射条目，以及 KLINE_TABLES 和兜底规则。
        """
        # 1. K 线表 → candlestick（最高优先级）
        assert (
            TusharePreviewService._infer_chart_type_pure(
                "kline", "行情数据", "time"
            )
            == "candlestick"
        )
        assert (
            TusharePreviewService._infer_chart_type_pure(
                "sector_kline", "板块行情", "time"
            )
            == "candlestick"
        )

        # 2. CHART_TYPE_MAP 中的折线图映射
        line_subcategories = [
            "资金流向数据",
            "两融及转融通",
            "特色数据",
            "大盘指数每日指标",
            "指数技术面因子（专业版）",
        ]
        for subcat in line_subcategories:
            result = TusharePreviewService._infer_chart_type_pure(
                "some_table", subcat, "trade_date"
            )
            assert result == "line", (
                f"subcategory '{subcat}' 应映射为 line，实际为 {result!r}"
            )

        # 3. CHART_TYPE_MAP 中的柱状图映射
        bar_subcategories = [
            "打板专题数据",
            "沪深市场每日交易统计",
            "深圳市场每日交易情况",
        ]
        for subcat in bar_subcategories:
            result = TusharePreviewService._infer_chart_type_pure(
                "some_table", subcat, "trade_date"
            )
            assert result == "bar", (
                f"subcategory '{subcat}' 应映射为 bar，实际为 {result!r}"
            )

        # 4. 不在 CHART_TYPE_MAP 中但有时间字段 → line（兜底）
        result = TusharePreviewService._infer_chart_type_pure(
            "index_dailybasic", "指数行情数据（低频）", "trade_date"
        )
        assert result == "line"

        # 5. 无时间字段 → None
        result = TusharePreviewService._infer_chart_type_pure(
            "stock_company", "基础数据", None
        )
        assert result is None

        # 6. K 线表优先级高于 CHART_TYPE_MAP
        result = TusharePreviewService._infer_chart_type_pure(
            "kline", "资金流向数据", "time"
        )
        assert result == "candlestick"
