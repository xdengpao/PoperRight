"""
Preservation 属性测试：Tushare 数据预览功能修复

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

本测试在未修复代码上运行，预期全部 PASS，以确认基线行为。
修复后重新运行，仍应全部 PASS（确保无回归）。

Property 5 (P5): 非共享表删除行为不变
  生成随机非共享表 ApiEntry（_build_scope_filter_pure() 返回空列表），
  观察 delete_data() 在未修复代码上的 DELETE SQL 仅包含时间范围条件。

Property 6 (P6): 按数据时间删除保持
  生成随机 data_time_start/data_time_end（不指定 import_time_start/import_time_end），
  验证 delete_data() 行为与修复前一致。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.tushare_preview_service import (
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
# 辅助函数
# ---------------------------------------------------------------------------


def _make_non_shared_table_entry(target_table: str) -> ApiEntry:
    """创建非共享表的 ApiEntry，_build_scope_filter_pure() 返回空列表。"""
    return ApiEntry(
        api_name=f"test_{target_table}",
        label=f"测试 {target_table}",
        category="stock_data",
        subcategory="基础数据",
        token_tier=TokenTier.BASIC,
        target_table=target_table,
        storage_engine=StorageEngine.PG,
        code_format=CodeFormat.NONE,
        conflict_columns=[],
        field_mappings=[],
        extra_config={},
    )


def _mock_db_session_for_delete(table_columns: list[str]):
    """创建模拟的数据库 session，用于 delete_data() 测试。

    模拟两次 session 使用：
    1. 第一次：LIMIT 0 查询获取列名
    2. 第二次：执行 DELETE SQL
    """
    col_result = MagicMock()
    col_result.keys.return_value = table_columns

    delete_result = MagicMock()
    delete_result.rowcount = 5

    call_count = 0

    class FakeSession:
        """模拟异步 session 上下文管理器。"""

        def __init__(self):
            nonlocal call_count
            self._call_index = call_count
            call_count += 1
            self.executed_sql = None
            self.executed_params = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql, params=None):
            self.executed_sql = str(sql)
            self.executed_params = params
            if self._call_index == 0:
                return col_result
            return delete_result

        async def commit(self):
            pass

        async def rollback(self):
            pass

    sessions: list[FakeSession] = []

    def session_factory():
        s = FakeSession()
        sessions.append(s)
        return s

    return session_factory, sessions


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------

# 非共享表名列表（_build_scope_filter_pure 返回空列表的表）
_NON_SHARED_TABLES = [
    "adjustment_factor",
    "trade_calendar",
    "stock_st",
    "stk_limit",
    "suspend_info",
    "hsgt_top10",
    "dividend",
    "forecast",
    "express",
    "stk_shock",
    "margin_data",
    "margin_detail",
]

non_shared_table_strategy = st.sampled_from(_NON_SHARED_TABLES).map(
    _make_non_shared_table_entry
)

# 日期字符串生成器（YYYYMMDD 或 YYYY-MM-DD 格式）
import datetime as _dt

_date_str_strategy = st.dates(
    min_value=_dt.date(2000, 1, 1),
    max_value=_dt.date(2025, 12, 28),
).map(lambda d: d.strftime("%Y%m%d"))


# ---------------------------------------------------------------------------
# Property 5 (P5): 非共享表删除行为不变
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(entry=non_shared_table_strategy)
def test_non_shared_table_delete_has_only_time_conditions(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 3.4, 3.5**

    P5 非共享表删除行为不变：对非共享表执行 delete_data()，
    验证 DELETE SQL 仅包含时间范围条件，不包含任何作用域过滤条件。

    在未修复代码和修复后代码上均应 PASS。
    """
    # 验证 entry 确实是非共享表
    scope_filters = TusharePreviewService._build_scope_filter_pure(entry)
    assert len(scope_filters) == 0, "测试前提：entry 应为非共享表"

    # 获取该表的时间字段
    time_field = TusharePreviewService._get_time_field_pure(entry.target_table)
    assert time_field is not None, f"测试前提：{entry.target_table} 应有时间字段"

    # 模拟 DB session
    table_columns = [time_field, "ts_code", "value"]
    session_factory, sessions = _mock_db_session_for_delete(table_columns)

    svc = TusharePreviewService()

    with patch.dict(
        "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
        {entry.api_name: entry},
    ), patch.object(svc, "_get_session", return_value=session_factory):
        result = asyncio.get_event_loop().run_until_complete(
            svc.delete_data(
                entry.api_name,
                data_time_start="2024-01-01",
                data_time_end="2024-03-31",
            )
        )

    # 获取执行 DELETE 的 session（第二个）
    assert len(sessions) >= 2, "应有至少两次 session 调用"
    delete_session = sessions[1]
    executed_sql = delete_session.executed_sql

    assert executed_sql is not None, "DELETE SQL 应已执行"

    # 验证 DELETE SQL 以 DELETE FROM 开头
    assert executed_sql.startswith("DELETE FROM"), (
        f"SQL 应以 DELETE FROM 开头，实际: {executed_sql}"
    )

    # 验证 DELETE SQL 包含时间范围条件
    assert ":start_time" in executed_sql, (
        f"DELETE SQL 应包含 :start_time 参数，实际: {executed_sql}"
    )
    assert ":end_time" in executed_sql, (
        f"DELETE SQL 应包含 :end_time 参数，实际: {executed_sql}"
    )

    # 验证 DELETE SQL 不包含作用域过滤条件
    assert "scope_freq" not in executed_sql, (
        f"非共享表 DELETE SQL 不应包含 scope_freq，实际: {executed_sql}"
    )
    assert "scope_report_type" not in executed_sql, (
        f"非共享表 DELETE SQL 不应包含 scope_report_type，实际: {executed_sql}"
    )
    assert "scope_ds" not in executed_sql, (
        f"非共享表 DELETE SQL 不应包含 scope_ds，实际: {executed_sql}"
    )
    assert "scope_ht" not in executed_sql, (
        f"非共享表 DELETE SQL 不应包含 scope_ht，实际: {executed_sql}"
    )

    # 验证返回结果
    assert result.target_table == entry.target_table
    assert result.data_time_start == "2024-01-01"
    assert result.data_time_end == "2024-03-31"


# ---------------------------------------------------------------------------
# Property 6 (P6): 按数据时间删除保持
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    entry=non_shared_table_strategy,
    start_date=st.dates(
        min_value=_dt.date(2000, 1, 1),
        max_value=_dt.date(2024, 6, 30),
    ),
    end_date=st.dates(
        min_value=_dt.date(2024, 7, 1),
        max_value=_dt.date(2025, 12, 28),
    ),
)
def test_data_time_only_delete_behavior_consistent(
    entry: ApiEntry,
    start_date,
    end_date,
) -> None:
    """
    **Validates: Requirements 3.4, 3.5**

    P6 按数据时间删除保持：生成随机 data_time_start/data_time_end
    （不指定 import_time_start/import_time_end），验证 delete_data()
    行为与修复前一致——仅使用数据时间范围条件。

    在未修复代码和修复后代码上均应 PASS。
    """
    data_time_start = start_date.strftime("%Y-%m-%d")
    data_time_end = end_date.strftime("%Y-%m-%d")

    # 获取该表的时间字段
    time_field = TusharePreviewService._get_time_field_pure(entry.target_table)
    assert time_field is not None, f"测试前提：{entry.target_table} 应有时间字段"

    # 模拟 DB session
    table_columns = [time_field, "ts_code", "value"]
    session_factory, sessions = _mock_db_session_for_delete(table_columns)

    svc = TusharePreviewService()

    with patch.dict(
        "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
        {entry.api_name: entry},
    ), patch.object(svc, "_get_session", return_value=session_factory):
        result = asyncio.get_event_loop().run_until_complete(
            svc.delete_data(
                entry.api_name,
                data_time_start=data_time_start,
                data_time_end=data_time_end,
            )
        )

    # 获取执行 DELETE 的 session
    assert len(sessions) >= 2, "应有至少两次 session 调用"
    delete_session = sessions[1]
    executed_sql = delete_session.executed_sql
    executed_params = delete_session.executed_params

    assert executed_sql is not None, "DELETE SQL 应已执行"

    # 验证 DELETE SQL 结构正确
    assert f"DELETE FROM {entry.target_table}" in executed_sql, (
        f"DELETE SQL 应包含正确的表名，实际: {executed_sql}"
    )
    assert "WHERE" in executed_sql, (
        f"DELETE SQL 应包含 WHERE 子句，实际: {executed_sql}"
    )

    # 验证参数包含时间范围
    assert executed_params is not None, "DELETE SQL 应有绑定参数"
    assert "start_time" in executed_params, (
        f"参数应包含 start_time，实际: {executed_params}"
    )
    assert "end_time" in executed_params, (
        f"参数应包含 end_time，实际: {executed_params}"
    )

    # 验证返回结果包含正确的时间范围
    assert result.data_time_start == data_time_start
    assert result.data_time_end == data_time_end
    assert result.target_table == entry.target_table
    assert result.time_field == time_field
    assert result.deleted_count >= 0
