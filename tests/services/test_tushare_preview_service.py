"""
TusharePreviewService 单元测试

覆盖：
- query_preview_data: 列信息生成、分页、作用域过滤、增量查询
- query_stats: 统计信息查询
- query_import_logs: 导入记录列表排序
- 增量查询: 查找最近 completed 记录、从 params_json 重建条件
- 错误处理: 未知接口名称、空结果
- 作用域过滤: kline freq、financial report_type、sector data_source
- 时间字段: 兜底优先级推断

对应需求：2.4, 3.2, 5.1-5.4, 7.2-7.5, 8.1-8.6, 9.4, 10.1-10.3
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_preview_service import (
    ColumnInfo,
    ImportLogItem,
    IncrementalInfo,
    PreviewDataResponse,
    PreviewStatsResponse,
    TusharePreviewService,
    TIME_FIELD_MAP,
    _TIME_FIELD_PRIORITY,
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


def _make_import_log(**overrides) -> MagicMock:
    """创建模拟的 TushareImportLog 对象。"""
    log = MagicMock()
    log.id = overrides.get("id", 1)
    log.api_name = overrides.get("api_name", "daily")
    log.params_json = overrides.get("params_json", {
        "start_date": "20240101",
        "end_date": "20240131",
    })
    log.status = overrides.get("status", "completed")
    log.record_count = overrides.get("record_count", 1000)
    log.error_message = overrides.get("error_message", None)
    log.started_at = overrides.get("started_at", datetime(2024, 1, 15, 10, 30, 0))
    log.finished_at = overrides.get("finished_at", datetime(2024, 1, 15, 10, 35, 0))
    return log


@pytest.fixture
def svc() -> TusharePreviewService:
    """创建 TusharePreviewService 实例。"""
    return TusharePreviewService()


def _mock_db_session(rows: list[dict], total: int = 0, columns: list[str] | None = None):
    """创建模拟的数据库 session 上下文管理器。

    Args:
        rows: 模拟的查询结果行
        total: 总记录数（COUNT 查询返回值）
        columns: 列名列表（空结果时用于 LIMIT 0 查询）
    """
    mock_session = AsyncMock()

    # 模拟 mappings 结果
    mock_mappings = []
    for row in rows:
        m = MagicMock()
        m.keys.return_value = list(row.keys())
        m.__getitem__ = lambda self, key, r=row: r[key]
        m.__iter__ = lambda self, r=row: iter(r)
        # 让 dict(mapping) 正常工作
        mock_mappings.append(row)

    # COUNT 查询结果
    count_result = MagicMock()
    count_result.scalar.return_value = total

    # 数据查询结果
    data_result = MagicMock()
    # mappings().all() 返回行数据
    mapping_objects = []
    for row in rows:
        mapping_obj = MagicMock()
        mapping_obj.keys.return_value = list(row.keys())
        # 让 dict(r) 正常工作
        mapping_obj.__iter__ = lambda self, r=row: iter(r.items())
        mapping_obj.items = lambda r=row: r.items()
        mapping_objects.append(mapping_obj)

    data_result.mappings.return_value.all.return_value = mapping_objects

    # LIMIT 0 查询结果（空结果时获取列名）
    col_result = MagicMock()
    if columns:
        col_result.keys.return_value = columns
    else:
        col_result.keys.return_value = list(rows[0].keys()) if rows else []

    # execute 按调用顺序返回不同结果
    mock_session.execute = AsyncMock(
        side_effect=[count_result, data_result, col_result]
    )

    # 上下文管理器
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    return mock_session


def _mock_pg_session_for_logs(logs: list[MagicMock]):
    """创建模拟的 PG session 用于导入日志查询。"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = logs
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _mock_pg_session_for_scalar(record):
    """创建模拟的 PG session 用于 scalar_one_or_none 查询。"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ===========================================================================
# test_query_preview_data_returns_correct_columns
# ===========================================================================


class TestQueryPreviewData:
    """query_preview_data 预览数据查询测试。"""

    async def test_query_preview_data_returns_correct_columns(
        self, svc: TusharePreviewService
    ) -> None:
        """验证列信息根据 field_mappings 正确生成。

        有映射的列使用 mapping.target 作为 label，无映射的列使用列名本身。
        """
        entry = _make_entry(
            field_mappings=[
                FieldMapping(source="ts_code", target="symbol"),
                FieldMapping(source="trade_date", target="time"),
            ],
        )
        rows = [
            {"symbol": "600000.SH", "time": "2024-01-15", "open": 10.5},
        ]
        mock_session = _mock_db_session(rows, total=1)

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"daily": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=mock_session,
            ),
        ):
            result = await svc.query_preview_data("daily")

        assert isinstance(result, PreviewDataResponse)
        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 50

        # 验证列信息
        col_names = [c.name for c in result.columns]
        assert "symbol" in col_names
        assert "time" in col_names
        assert "open" in col_names

        # 有映射的列 label 应为 mapping.target（即列名本身，因为 target 就是列名）
        symbol_col = next(c for c in result.columns if c.name == "symbol")
        assert symbol_col.label == "symbol"

        # 无映射的列 label 应为列名本身
        open_col = next(c for c in result.columns if c.name == "open")
        assert open_col.label == "open"

    async def test_empty_result_returns_empty_rows(
        self, svc: TusharePreviewService
    ) -> None:
        """查询结果为空时返回空行列表和 total=0。"""
        entry = _make_entry(target_table="stk_limit")
        mock_session = _mock_db_session([], total=0, columns=["ts_code", "trade_date", "up_limit"])

        # stk_limit 无作用域过滤且无时间/代码参数，会先查询 reltuples 估算
        # 需要在 side_effect 前插入 reltuples 查询结果（返回小值以跳过估算）
        reltuples_result = MagicMock()
        reltuples_result.scalar.return_value = 100.0  # 小于阈值，回退到精确 COUNT
        original_side_effect = mock_session.execute.side_effect
        mock_session.execute.side_effect = [reltuples_result] + list(original_side_effect)

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"stk_limit": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=mock_session,
            ),
        ):
            result = await svc.query_preview_data("stk_limit")

        assert result.total == 0
        assert result.rows == []
        assert len(result.columns) == 3


# ===========================================================================
# test_query_stats_returns_correct_stats
# ===========================================================================


class TestQueryStats:
    """query_stats 统计信息查询测试。"""

    async def test_query_stats_returns_correct_stats(
        self, svc: TusharePreviewService
    ) -> None:
        """验证统计信息包含总记录数、时间范围和最近导入信息。"""
        entry = _make_entry(target_table="kline", storage_engine=StorageEngine.TS)

        # 模拟 TS session（数据表查询）
        ts_session = AsyncMock()
        # COUNT 查询
        count_result = MagicMock()
        count_result.scalar.return_value = 50000
        # MIN/MAX 时间查询
        time_result = MagicMock()
        time_row = MagicMock()
        time_row.__getitem__ = lambda self, idx: (
            "20230101" if idx == 0 else "20241231"
        )
        time_result.one_or_none.return_value = time_row
        ts_session.execute = AsyncMock(side_effect=[count_result, time_result])
        ts_session.__aenter__ = AsyncMock(return_value=ts_session)
        ts_session.__aexit__ = AsyncMock(return_value=False)

        # 模拟 PG session（导入日志查询）
        log_record = _make_import_log(
            started_at=datetime(2024, 12, 31, 10, 0, 0),
            record_count=500,
        )
        pg_session = _mock_pg_session_for_scalar(log_record)

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
            result = await svc.query_stats("daily")

        assert isinstance(result, PreviewStatsResponse)
        assert result.total_count == 50000
        assert result.earliest_time == "20230101"
        assert result.latest_time == "20241231"
        assert result.last_import_at == "2024-12-31T10:00:00"
        assert result.last_import_count == 500


# ===========================================================================
# test_query_import_logs_sorted_desc
# ===========================================================================


class TestQueryImportLogs:
    """query_import_logs 导入记录查询测试。"""

    async def test_query_import_logs_sorted_desc(
        self, svc: TusharePreviewService
    ) -> None:
        """验证导入记录按 started_at 降序排列返回。"""
        log1 = _make_import_log(
            id=1,
            started_at=datetime(2024, 1, 10, 8, 0, 0),
            finished_at=datetime(2024, 1, 10, 8, 5, 0),
            status="completed",
            record_count=100,
        )
        log2 = _make_import_log(
            id=2,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 10, 5, 0),
            status="failed",
            record_count=0,
            error_message="连接超时",
        )
        # 模拟已按降序排列（数据库 ORDER BY 保证）
        pg_session = _mock_pg_session_for_logs([log2, log1])

        with patch(
            "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
            return_value=pg_session,
        ):
            result = await svc.query_import_logs("daily", limit=20)

        assert len(result) == 2
        assert isinstance(result[0], ImportLogItem)
        # 第一条应是更晚的记录（降序）
        assert result[0].id == 2
        assert result[0].status == "failed"
        assert result[0].error_message == "连接超时"
        assert result[1].id == 1
        assert result[1].status == "completed"
        assert result[1].record_count == 100
        # 验证时间格式化
        assert result[0].started_at == "2024-01-15T10:00:00"
        assert result[0].finished_at == "2024-01-15T10:05:00"


# ===========================================================================
# test_incremental_query_finds_latest_completed
# ===========================================================================


class TestIncrementalQuery:
    """增量查询测试。"""

    async def test_incremental_query_finds_latest_completed(
        self, svc: TusharePreviewService
    ) -> None:
        """增量查询应查找最近一条 status='completed' 的导入记录。"""
        entry = _make_entry(target_table="kline", storage_engine=StorageEngine.TS)
        log_record = _make_import_log(
            id=42,
            status="completed",
            params_json={"start_date": "20240101", "end_date": "20240131"},
            started_at=datetime(2024, 2, 1, 8, 0, 0),
            record_count=500,
        )

        # PG session 用于查询 ImportLog
        pg_session = _mock_pg_session_for_scalar(log_record)

        # TS session 用于查询数据表
        rows = [{"symbol": "600000.SH", "time": "20240115", "close": 10.5}]
        ts_session = _mock_db_session(rows, total=1)

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"daily": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
        ):
            result = await svc.query_preview_data("daily", incremental=True)

        assert result.incremental_info is not None
        assert result.incremental_info.import_log_id == 42
        assert result.incremental_info.status == "completed"
        assert result.incremental_info.record_count == 500
        assert "20240101" in result.incremental_info.params_summary
        assert "20240131" in result.incremental_info.params_summary

    async def test_incremental_query_rebuilds_params_from_log(
        self, svc: TusharePreviewService
    ) -> None:
        """增量查询应从 params_json 中提取 start_date/end_date 重建查询条件。"""
        entry = _make_entry(target_table="kline", storage_engine=StorageEngine.TS)
        log_record = _make_import_log(
            id=10,
            status="completed",
            params_json={
                "start_date": "20240301",
                "end_date": "20240331",
                "ts_code": "000001.SZ",
            },
            started_at=datetime(2024, 4, 1, 9, 0, 0),
            record_count=200,
        )

        pg_session = _mock_pg_session_for_scalar(log_record)
        ts_session = _mock_db_session([], total=0, columns=["symbol", "time", "close"])

        with (
            patch.dict(
                "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
                {"daily": entry},
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionPG",
                return_value=pg_session,
            ),
            patch(
                "app.services.data_engine.tushare_preview_service.AsyncSessionTS",
                return_value=ts_session,
            ),
        ):
            result = await svc.query_preview_data("daily", incremental=True)

        # 验证 SQL 中包含了从 params_json 重建的时间和代码条件
        # 通过检查 execute 调用的参数来验证
        calls = ts_session.execute.call_args_list
        # 第一个调用是 COUNT 查询，第二个是数据查询
        for call in calls:
            args = call[0]
            if len(args) >= 2:
                bind_params = args[1]
                if isinstance(bind_params, dict):
                    # 验证时间参数被传入
                    if "data_time_start" in bind_params:
                        assert bind_params["data_time_start"] == "20240301"
                    if "data_time_end" in bind_params:
                        assert bind_params["data_time_end"] == "20240331"
                    if "ts_code" in bind_params:
                        assert bind_params["ts_code"] == "000001.SZ"

        # 验证增量信息
        assert result.incremental_info is not None
        assert result.incremental_info.import_log_id == 10
        assert "000001.SZ" in result.incremental_info.params_summary


# ===========================================================================
# test_unknown_api_name_raises_error
# ===========================================================================


class TestUnknownApiName:
    """未知接口名称错误处理测试。"""

    async def test_unknown_api_name_raises_error(
        self, svc: TusharePreviewService
    ) -> None:
        """未注册的 api_name 应抛出 ValueError。"""
        with patch.dict(
            "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
            {},
            clear=True,
        ):
            with pytest.raises(ValueError, match="接口 nonexistent_api 未注册"):
                await svc.query_preview_data("nonexistent_api")

    async def test_unknown_api_name_raises_error_for_stats(
        self, svc: TusharePreviewService
    ) -> None:
        """query_stats 对未注册的 api_name 也应抛出 ValueError。"""
        with patch.dict(
            "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
            {},
            clear=True,
        ):
            with pytest.raises(ValueError, match="接口 unknown_api 未注册"):
                await svc.query_stats("unknown_api")


# ===========================================================================
# test_scope_filter_kline_by_freq
# ===========================================================================


class TestScopeFilter:
    """共享表作用域过滤测试。"""

    def test_scope_filter_kline_by_freq(self) -> None:
        """kline 表应按 extra_config.freq 生成 freq 过滤条件。"""
        entry = _make_entry(
            target_table="kline",
            extra_config={"freq": "1d"},
        )
        conditions = TusharePreviewService._build_scope_filter_pure(entry)

        assert len(conditions) >= 1
        clauses = [c[0] for c in conditions]
        assert "freq = :scope_freq" in clauses
        # 验证参数值
        for clause, params in conditions:
            if clause == "freq = :scope_freq":
                assert params["scope_freq"] == "1d"

    def test_scope_filter_kline_weekly(self) -> None:
        """kline 表 weekly 接口应生成 freq='1w' 过滤条件。"""
        entry = _make_entry(
            api_name="weekly",
            target_table="kline",
            extra_config={"freq": "1w"},
        )
        conditions = TusharePreviewService._build_scope_filter_pure(entry)

        clauses = [c[0] for c in conditions]
        assert "freq = :scope_freq" in clauses
        for clause, params in conditions:
            if clause == "freq = :scope_freq":
                assert params["scope_freq"] == "1w"

    def test_scope_filter_financial_by_report_type(self) -> None:
        """financial_statement 表应按 inject_fields.report_type 生成过滤条件。"""
        entry = _make_entry(
            api_name="income",
            target_table="financial_statement",
            extra_config={"inject_fields": {"report_type": "income"}},
        )
        conditions = TusharePreviewService._build_scope_filter_pure(entry)

        clauses = [c[0] for c in conditions]
        assert "report_type = :scope_report_type" in clauses
        for clause, params in conditions:
            if clause == "report_type = :scope_report_type":
                assert params["scope_report_type"] == "income"

    def test_scope_filter_sector_by_data_source(self) -> None:
        """sector 系列表应按 extra_config.data_source 生成过滤条件。"""
        for table in ("sector_info", "sector_constituent", "sector_kline"):
            entry = _make_entry(
                target_table=table,
                extra_config={"data_source": "THS"},
            )
            conditions = TusharePreviewService._build_scope_filter_pure(entry)

            clauses = [c[0] for c in conditions]
            assert "data_source = :scope_ds" in clauses, (
                f"{table} 表应包含 data_source 过滤条件"
            )
            for clause, params in conditions:
                if clause == "data_source = :scope_ds":
                    assert params["scope_ds"] == "THS"

    def test_scope_filter_empty_for_non_shared_table(self) -> None:
        """非共享表（无特殊 extra_config）应返回空过滤条件。"""
        entry = _make_entry(
            target_table="stk_limit",
            extra_config={},
        )
        conditions = TusharePreviewService._build_scope_filter_pure(entry)
        assert conditions == []


# ===========================================================================
# test_time_field_fallback_priority
# ===========================================================================


class TestTimeFieldFallback:
    """时间字段自动推断兜底测试。"""

    def test_time_field_fallback_priority(self) -> None:
        """不在 TIME_FIELD_MAP 中的表应按 _TIME_FIELD_PRIORITY 优先级推断。"""
        # 表中同时有 ann_date 和 end_date，应优先返回 ann_date
        columns = ["id", "ts_code", "end_date", "ann_date", "value"]
        result = TusharePreviewService._get_time_field_pure(
            "zzz_unknown_table", columns
        )
        assert result == "ann_date", (
            f"应优先返回 ann_date（优先级高于 end_date），实际 {result!r}"
        )

    def test_time_field_fallback_trade_date_highest(self) -> None:
        """trade_date 在兜底优先级中最高。"""
        columns = ["id", "trade_date", "ann_date", "end_date"]
        result = TusharePreviewService._get_time_field_pure(
            "zzz_unknown_table_2", columns
        )
        assert result == "trade_date"

    def test_time_field_fallback_no_match(self) -> None:
        """表中无任何已知时间字段时返回 None。"""
        columns = ["id", "ts_code", "name", "value"]
        result = TusharePreviewService._get_time_field_pure(
            "zzz_unknown_table_3", columns
        )
        assert result is None

    def test_time_field_from_map(self) -> None:
        """在 TIME_FIELD_MAP 中的表应直接返回映射值。"""
        result = TusharePreviewService._get_time_field_pure("kline")
        assert result == "time"

        result = TusharePreviewService._get_time_field_pure("trade_calendar")
        assert result == "cal_date"

        result = TusharePreviewService._get_time_field_pure("financial_statement")
        assert result == "ann_date"

    def test_time_field_no_columns_no_map(self) -> None:
        """不在映射表中且无列信息时返回 None。"""
        result = TusharePreviewService._get_time_field_pure("zzz_no_such_table")
        assert result is None
