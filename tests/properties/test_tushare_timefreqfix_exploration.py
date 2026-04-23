"""
Bug Condition 探索性测试：Tushare 导入频率超限与数据截断修复

**Validates: Requirements 2.1, 2.2, 2.3, 2.6**

Property 1 (5.1): 频率分组与 Tushare 官方限制匹配
  遍历注册表所有 API 条目，验证 rate_limit_group 对应的调用间隔 >= Tushare 官方最小间隔。

Property 2 (5.2): date_chunk_days 不导致截断
  验证所有 batch_by_date=True 且配置了 estimated_daily_rows 的接口，
  date_chunk_days × estimated_daily_rows < max_rows。

Property 3 (5.3): RateLimitGroup 枚举完整性
  验证 _build_rate_limit_map() 返回的映射覆盖所有 RateLimitGroup 枚举值。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.tushare_registry import (
    TUSHARE_API_REGISTRY,
    ApiEntry,
    RateLimitGroup,
)
from app.tasks.tushare_import import _build_rate_limit_map


# ---------------------------------------------------------------------------
# Tushare 官方频率限制：每个 RateLimitGroup 对应的最小调用间隔（秒）
# 基于 Tushare 官方文档：
#   KLINE        — 500次/min → 60/500 = 0.12s
#   FUNDAMENTALS — 200次/min → 60/200 = 0.30s
#   MONEY_FLOW   — 300次/min → 60/300 = 0.20s
#   LIMIT_UP     — 10次/min  → 60/10  = 6.0s
#   TIER_80      — 80次/min  → 60/80  = 0.75s
#   TIER_60      — 60次/min  → 60/60  = 1.0s
#   TIER_20      — 20次/min  → 60/20  = 3.0s
#   TIER_10      — 10次/min  → 60/10  = 6.0s
# ---------------------------------------------------------------------------

_TUSHARE_OFFICIAL_MIN_INTERVAL: dict[RateLimitGroup, float] = {
    RateLimitGroup.KLINE: 0.12,
    RateLimitGroup.FUNDAMENTALS: 0.30,
    RateLimitGroup.MONEY_FLOW: 0.20,
    RateLimitGroup.LIMIT_UP: 6.0,
    RateLimitGroup.TIER_80: 0.75,
    RateLimitGroup.TIER_60: 1.0,
    RateLimitGroup.TIER_20: 3.0,
    RateLimitGroup.TIER_10: 6.0,
}


# ---------------------------------------------------------------------------
# Property 1 (Task 5.1): 频率分组与 Tushare 官方限制匹配
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(entry=st.sampled_from(list(TUSHARE_API_REGISTRY.values())))
def test_rate_limit_group_interval_meets_official_minimum(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 2.1, 2.2**

    对任意注册的 ApiEntry，其 rate_limit_group 对应的配置调用间隔
    必须 >= Tushare 官方该分组的最小调用间隔。

    确保没有 API 被分配到调用频率过高（间隔过短）的分组。
    """
    rate_limit_map = _build_rate_limit_map()
    group = entry.rate_limit_group

    # 获取该分组的实际配置间隔
    actual_interval = rate_limit_map.get(group)
    assert actual_interval is not None, (
        f"接口 {entry.api_name} 的 rate_limit_group={group.value} "
        f"在 _build_rate_limit_map() 中无对应映射"
    )

    # 获取该分组的 Tushare 官方最小间隔
    official_min = _TUSHARE_OFFICIAL_MIN_INTERVAL.get(group)
    assert official_min is not None, (
        f"接口 {entry.api_name} 的 rate_limit_group={group.value} "
        f"未在 Tushare 官方最小间隔表中定义"
    )

    assert actual_interval >= official_min, (
        f"接口 {entry.api_name} 的 rate_limit_group={group.value} "
        f"配置间隔 {actual_interval}s < Tushare 官方最小间隔 {official_min}s。"
        f"该接口的调用频率超过 Tushare 官方限制，可能触发 code=40203 错误"
    )


# ---------------------------------------------------------------------------
# Property 2 (Task 5.2): date_chunk_days 不导致截断
# ---------------------------------------------------------------------------

# 筛选出所有 batch_by_date=True 且配置了 estimated_daily_rows 的接口
_BATCH_BY_DATE_ENTRIES_WITH_ESTIMATE = [
    entry
    for entry in TUSHARE_API_REGISTRY.values()
    if entry.batch_by_date and entry.extra_config.get("estimated_daily_rows") is not None
]


@pytest.mark.skipif(
    len(_BATCH_BY_DATE_ENTRIES_WITH_ESTIMATE) == 0,
    reason="注册表中没有同时配置 batch_by_date=True 和 estimated_daily_rows 的接口",
)
@settings(max_examples=200)
@given(entry=st.sampled_from(_BATCH_BY_DATE_ENTRIES_WITH_ESTIMATE))
def test_date_chunk_days_does_not_cause_truncation(entry: ApiEntry) -> None:
    """
    **Validates: Requirements 2.3**

    对任意 batch_by_date=True 且配置了 estimated_daily_rows 的 ApiEntry，
    date_chunk_days × estimated_daily_rows 必须严格小于 max_rows，
    确保单个日期分片不会触发 Tushare 静默数据截断。
    """
    estimated_daily_rows = entry.extra_config["estimated_daily_rows"]
    max_rows = entry.extra_config.get("max_rows", 3000)
    product = entry.date_chunk_days * estimated_daily_rows

    assert product < max_rows, (
        f"接口 {entry.api_name}: date_chunk_days={entry.date_chunk_days} × "
        f"estimated_daily_rows={estimated_daily_rows} = {product} >= "
        f"max_rows={max_rows}。"
        f"该配置可能导致单个日期分片数据被 Tushare 静默截断"
    )


# ---------------------------------------------------------------------------
# Property 3 (Task 5.3): RateLimitGroup 枚举完整性
# ---------------------------------------------------------------------------


def test_build_rate_limit_map_covers_all_enum_values() -> None:
    """
    **Validates: Requirements 2.2, 2.6**

    _build_rate_limit_map() 返回的映射必须覆盖所有 RateLimitGroup 枚举值，
    且每个值对应一个正数浮点间隔。确保所有频率层级均可通过 .env 配置。
    """
    rate_limit_map = _build_rate_limit_map()
    all_groups = set(RateLimitGroup)
    mapped_groups = set(rate_limit_map.keys())

    # 检查覆盖完整性
    missing = all_groups - mapped_groups
    assert not missing, (
        f"_build_rate_limit_map() 缺少以下 RateLimitGroup 枚举值的映射: "
        f"{[g.value for g in missing]}。"
        f"这些频率层级无法通过 .env 配置调用间隔"
    )

    # 检查每个映射值为正数浮点
    for group in all_groups:
        interval = rate_limit_map[group]
        assert isinstance(interval, (int, float)), (
            f"RateLimitGroup.{group.value} 的映射值类型为 {type(interval).__name__}，"
            f"期望 float"
        )
        assert interval > 0, (
            f"RateLimitGroup.{group.value} 的映射值 {interval} <= 0，"
            f"调用间隔必须为正数"
        )
