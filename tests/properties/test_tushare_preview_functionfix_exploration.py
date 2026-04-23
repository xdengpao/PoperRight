"""
Bug Condition 探索性测试：Tushare 数据预览功能修复

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

本测试在未修复代码上运行，预期全部 FAIL，以确认缺陷存在。

Property 3 (P3): 删除 SQL 作用域过滤
  生成随机共享表 ApiEntry（_build_scope_filter_pure() 返回非空），
  验证当前 delete_data() 构建的 DELETE SQL 缺少作用域条件（确认 Bug 存在）。

Property 4 (P4): 按导入时间删除
  验证当前 delete_data() 方法签名不接受 import_time_start/import_time_end 参数（确认 Bug 存在）。
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_shared_table_entry(freq: str) -> ApiEntry:
    """创建共享表（kline）的 ApiEntry，_build_scope_filter_pure() 返回非空。"""
    return ApiEntry(
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
        ],
        extra_config={"freq": freq},
    )


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------

# kline 表的 freq 值（共享表场景）
_KLINE_FREQ_VALUES = ["1d", "1w", "1M"]

shared_kline_entry_strategy = st.sampled_from(_KLINE_FREQ_VALUES).map(
    _make_shared_table_entry
)


# ---------------------------------------------------------------------------
# Property 3 (P3): 删除 SQL 作用域过滤
# ---------------------------------------------------------------------------


def _mock_db_session_for_delete(table_columns: list[str]):
    """创建模拟的数据库 session，用于 delete_data() 测试。

    模拟两次 session 使用：
    1. 第一次：LIMIT 0 查询获取列名
    2. 第二次：执行 DELETE SQL
    """
    # 第一次 session：获取列名
    col_result = MagicMock()
    col_result.keys.return_value = table_columns

    # 第二次 session：执行 DELETE
    delete_result = MagicMock()
    delete_result.rowcount = 0

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

    # 记录所有创建的 session 实例
    sessions: list[FakeSession] = []

    def session_factory():
        s = FakeSession()
        sessions.append(s)
        return s

    return session_factory, sessions


@settings(max_examples=50)
@given(entry=shared_kline_entry_strategy)
def test_delete_data_missing_scope_filter_for_shared_table(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 1.4**

    P3 删除 SQL 作用域过滤：对共享表（kline）执行 delete_data()，
    验证当前实现生成的 DELETE SQL 缺少作用域条件（如 freq = :scope_freq）。

    在未修复代码上，此测试应 FAIL（因为 DELETE SQL 确实缺少 scope 条件）。
    修复后，此测试应 PASS（DELETE SQL 包含 scope 条件）。
    """
    import asyncio

    # 验证 entry 确实是共享表（_build_scope_filter_pure 返回非空）
    scope_filters = TusharePreviewService._build_scope_filter_pure(entry)
    assert len(scope_filters) > 0, "测试前提：entry 应为共享表"

    # 模拟 DB session
    kline_columns = ["time", "symbol", "freq", "adj_type", "open", "close", "high", "low", "volume"]
    session_factory, sessions = _mock_db_session_for_delete(kline_columns)

    svc = TusharePreviewService()

    with patch.dict(
        "app.services.data_engine.tushare_preview_service.TUSHARE_API_REGISTRY",
        {entry.api_name: entry},
    ), patch.object(svc, "_get_session", return_value=session_factory):
        result = asyncio.get_event_loop().run_until_complete(
            svc.delete_data(entry.api_name, data_time_start="2024-01-01", data_time_end="2024-03-31")
        )

    # 获取执行 DELETE 的 session（第二个）
    assert len(sessions) >= 2, "应有至少两次 session 调用"
    delete_session = sessions[1]
    executed_sql = delete_session.executed_sql
    executed_params = delete_session.executed_params

    assert executed_sql is not None, "DELETE SQL 应已执行"

    # 验证 DELETE SQL 包含作用域过滤条件
    for clause, params in scope_filters:
        assert clause in executed_sql, (
            f"DELETE SQL 应包含作用域条件 '{clause}'，"
            f"但实际 SQL 为: {executed_sql}"
        )
        for key, value in params.items():
            assert key in (executed_params or {}), (
                f"DELETE SQL 参数应包含 '{key}={value}'，"
                f"但实际参数为: {executed_params}"
            )


# ---------------------------------------------------------------------------
# Property 4 (P4): 按导入时间删除
# ---------------------------------------------------------------------------


def test_delete_data_does_not_accept_import_time_params() -> None:
    """
    **Validates: Requirements 1.5**

    P4 按导入时间删除：验证当前 delete_data() 方法签名不接受
    import_time_start/import_time_end 参数（确认 Bug 存在）。

    在未修复代码上，此测试应 FAIL（因为方法确实不接受这些参数）。
    修复后，此测试应 PASS（方法签名已扩展）。
    """
    sig = inspect.signature(TusharePreviewService.delete_data)
    param_names = set(sig.parameters.keys())

    # 修复后，delete_data 应接受 import_time_start 和 import_time_end 参数
    assert "import_time_start" in param_names, (
        f"delete_data() 应接受 'import_time_start' 参数，"
        f"但当前参数列表为: {param_names}"
    )
    assert "import_time_end" in param_names, (
        f"delete_data() 应接受 'import_time_end' 参数，"
        f"但当前参数列表为: {param_names}"
    )
