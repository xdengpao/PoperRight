# Feature: data-manage-dual-source-integration, Property 56: 清洗统计数据库查询正确性
"""
清洗统计端点属性测试（Hypothesis）

属性 56：清洗统计数据库查询正确性

**Validates: Requirements 24.7**

对任意 stock_info 和 permanent_exclusion 表数据状态，验证各统计字段与数据库查询结果一致，
valid_stocks 下限为 0。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.data import get_cleaning_stats


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 各统计计数的生成策略（非负整数，合理范围）
_count = st.integers(min_value=0, max_value=10000)

# 生成一组完整的数据库查询返回值
_db_counts = st.fixed_dictionaries({
    "total": _count,
    "st_delisted": _count,
    "new_stock": _count,
    "suspended": _count,
    "high_pledge": _count,
})


# ---------------------------------------------------------------------------
# 辅助：构建 mock session
# ---------------------------------------------------------------------------

def _build_mock_session(counts: dict):
    """构建一个 mock AsyncSession，按顺序返回各查询的 scalar_one 值。"""
    session = AsyncMock()

    # 每次 session.execute() 返回一个 mock result，其 scalar_one() 返回对应计数
    call_order = [
        counts["total"],
        counts["st_delisted"],
        counts["new_stock"],
        counts["suspended"],
        counts["high_pledge"],
    ]

    results = []
    for val in call_order:
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = val
        results.append(mock_result)

    session.execute = AsyncMock(side_effect=results)
    return session


# ---------------------------------------------------------------------------
# 属性 56：清洗统计数据库查询正确性
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(counts=_db_counts)
def test_cleaning_stats_match_db_queries(counts):
    """
    # Feature: data-manage-dual-source-integration, Property 56: 清洗统计数据库查询正确性

    **Validates: Requirements 24.7**

    对任意 stock_info 和 permanent_exclusion 表数据状态，验证：
    1. total_stocks 等于数据库返回的总数
    2. 各剔除计数字段与数据库查询结果一致
    3. valid_stocks = max(total - st_delisted - new_stock - suspended - high_pledge, 0)
    4. valid_stocks >= 0（下限为 0）
    """
    mock_session = _build_mock_session(counts)

    # Mock AsyncSessionPG 作为异步上下文管理器
    mock_session_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_ctx

    with patch("app.core.database.AsyncSessionPG", mock_session_factory):
        response = asyncio.run(get_cleaning_stats())

    # 1. total_stocks 等于数据库返回的总数
    assert response.total_stocks == counts["total"]

    # 2. 各剔除计数字段与数据库查询结果一致
    assert response.st_delisted_count == counts["st_delisted"]
    assert response.new_stock_count == counts["new_stock"]
    assert response.suspended_count == counts["suspended"]
    assert response.high_pledge_count == counts["high_pledge"]

    # 3. valid_stocks 计算正确
    expected_valid = (
        counts["total"]
        - counts["st_delisted"]
        - counts["new_stock"]
        - counts["suspended"]
        - counts["high_pledge"]
    )
    assert response.valid_stocks == max(expected_valid, 0)

    # 4. valid_stocks 下限为 0
    assert response.valid_stocks >= 0
