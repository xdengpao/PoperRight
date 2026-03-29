# Feature: data-manage-dual-source-integration, Property 53: 健康检查端点返回正确状态
"""
数据源健康检查端点属性测试（Hypothesis）

属性 53：健康检查端点返回正确状态

**Validates: Requirements 24.1, 24.9**

对任意 health_check() 结果组合（True/False/异常），验证响应包含恰好 2 个数据源，
status 字段正确映射，checked_at 不为空。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.data import get_sources_health


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 单个数据源的 health_check 结果：True / False / 异常
_health_outcome = st.one_of(
    st.just(True),
    st.just(False),
    st.sampled_from([
        RuntimeError("timeout"),
        ConnectionError("connection refused"),
        TimeoutError("request timed out"),
        OSError("network unreachable"),
        Exception("unexpected error"),
    ]),
)

# 两个数据源的结果组合
_health_pair = st.tuples(_health_outcome, _health_outcome)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _make_mock_adapter(outcome):
    """创建一个 mock 适配器，其 health_check 返回指定结果或抛出异常。"""
    adapter = AsyncMock()
    if isinstance(outcome, Exception):
        adapter.health_check.side_effect = outcome
    else:
        adapter.health_check.return_value = outcome
    return adapter


# ---------------------------------------------------------------------------
# 属性 53：健康检查端点返回正确状态
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(pair=_health_pair)
def test_health_endpoint_returns_correct_status(pair):
    """
    # Feature: data-manage-dual-source-integration, Property 53: 健康检查端点返回正确状态

    **Validates: Requirements 24.1, 24.9**

    对任意 health_check() 结果组合（True/False/异常），验证：
    1. 响应包含恰好 2 个数据源
    2. status 字段正确映射（True→connected, False/异常→disconnected）
    3. checked_at 不为空
    """
    tushare_outcome, akshare_outcome = pair

    mock_tushare = _make_mock_adapter(tushare_outcome)
    mock_akshare = _make_mock_adapter(akshare_outcome)

    with patch("app.api.v1.data.TushareAdapter", return_value=mock_tushare), \
         patch("app.api.v1.data.AkShareAdapter", return_value=mock_akshare):
        response = asyncio.run(get_sources_health())

    # 1. 恰好 2 个数据源
    assert len(response.sources) == 2

    # 2. 名称正确
    assert response.sources[0].name == "Tushare"
    assert response.sources[1].name == "AkShare"

    # 3. status 正确映射
    for outcome, source in zip(pair, response.sources):
        if isinstance(outcome, Exception) or outcome is False:
            assert source.status == "disconnected"
        else:
            assert source.status == "connected"

    # 4. checked_at 不为空
    for source in response.sources:
        assert source.checked_at
        assert len(source.checked_at) > 0
