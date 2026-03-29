# Feature: data-manage-dual-source-integration, Property 54: 同步状态响应包含数据源和故障转移字段
"""
同步状态端点属性测试（Hypothesis）

属性 54：同步状态响应包含数据源和故障转移字段

**Validates: Requirements 24.3**

对任意同步状态记录，GET /data/sync/status 接口返回的每条 SyncStatusItem
应包含 data_source 字段（取值为 "Tushare"、"AkShare" 或 "N/A"）和 is_fallback 布尔字段。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.data import SyncStatusItem, get_sync_status

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

VALID_DATA_SOURCES = ["Tushare", "AkShare", "N/A"]
VALID_STATUSES = ["OK", "ERROR", "SYNCING", "UNKNOWN"]
TYPE_LABELS = {"kline": "行情数据", "fundamentals": "基本面数据", "money_flow": "资金流向"}
DATA_TYPES = list(TYPE_LABELS.keys())

# 生成单条同步状态记录的 JSON 数据
_sync_status_record = st.fixed_dictionaries({
    "source": st.sampled_from(list(TYPE_LABELS.values())),
    "last_sync_at": st.one_of(st.none(), st.just("2024-01-02T15:00:00")),
    "status": st.sampled_from(VALID_STATUSES),
    "record_count": st.integers(min_value=0, max_value=10_000_000),
    "data_source": st.sampled_from(VALID_DATA_SOURCES),
    "is_fallback": st.booleans(),
})

# 生成三个 Redis 键的值：每个可以是 JSON 字符串或 None（表示 Redis 无缓存）
_redis_values = st.tuples(
    st.one_of(st.none(), _sync_status_record.map(json.dumps)),
    st.one_of(st.none(), _sync_status_record.map(json.dumps)),
    st.one_of(st.none(), _sync_status_record.map(json.dumps)),
)


# ---------------------------------------------------------------------------
# 属性 54：同步状态响应包含数据源和故障转移字段
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(redis_vals=_redis_values)
def test_sync_status_contains_data_source_and_fallback_fields(redis_vals):
    """
    # Feature: data-manage-dual-source-integration, Property 54: 同步状态响应包含数据源和故障转移字段

    **Validates: Requirements 24.3**

    对任意 Redis 缓存状态组合，验证：
    1. 响应包含恰好 3 条 SyncStatusItem
    2. 每条 data_source 取值为 "Tushare"、"AkShare" 或 "N/A"
    3. 每条 is_fallback 为布尔值
    4. 当 Redis 无缓存时，默认 data_source="N/A"、is_fallback=False
    """
    kline_val, fund_val, mf_val = redis_vals

    async def mock_cache_get(key: str) -> str | None:
        mapping = {
            "sync:status:kline": kline_val,
            "sync:status:fundamentals": fund_val,
            "sync:status:money_flow": mf_val,
        }
        return mapping.get(key)

    with patch("app.core.redis_client.cache_get", side_effect=mock_cache_get):
        response = asyncio.run(get_sync_status())

    # 1. 恰好 3 条记录
    assert len(response.items) == 3

    # 2 & 3. 每条记录包含正确的 data_source 和 is_fallback 字段
    for item in response.items:
        assert isinstance(item, SyncStatusItem)
        assert item.data_source in VALID_DATA_SOURCES
        assert isinstance(item.is_fallback, bool)

    # 4. 当 Redis 无缓存时，验证默认值
    for idx, raw_val in enumerate(redis_vals):
        if raw_val is None:
            assert response.items[idx].data_source == "N/A"
            assert response.items[idx].is_fallback is False
            assert response.items[idx].status == "UNKNOWN"
            assert response.items[idx].record_count == 0
            assert response.items[idx].last_sync_at is None
