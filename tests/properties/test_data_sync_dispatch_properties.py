# Feature: data-manage-dual-source-integration, Property 55: 手动同步按类型分发正确的 Celery 任务
"""
手动同步分发属性测试（Hypothesis）

属性 55：手动同步按类型分发正确的 Celery 任务

**Validates: Requirements 24.5**

对任意有效的 sync_type 参数值，POST /data/sync 接口应分发正确的 Celery 任务：
- sync_type="kline" 仅触发 sync_realtime_market
- sync_type="fundamentals" 仅触发 sync_fundamentals
- sync_type="money_flow" 仅触发 sync_money_flow
- sync_type="all" 或缺省时触发全部三个任务
返回的 task_ids 数量应与触发的任务数量一致。
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.data import SyncRequest, SyncResponse, trigger_sync

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

VALID_SYNC_TYPES = ["kline", "fundamentals", "money_flow", "all"]

# 有效 sync_type 值（含 None 表示缺省）
valid_sync_type = st.one_of(
    st.sampled_from(VALID_SYNC_TYPES),
    st.none(),
)

# 无效 sync_type：任意字符串但不在有效列表中
invalid_sync_type = st.text(min_size=1, max_size=50).filter(
    lambda s: s not in VALID_SYNC_TYPES
)

# 期望的任务数量映射
EXPECTED_TASK_COUNTS = {
    "kline": 1,
    "fundamentals": 1,
    "money_flow": 1,
    "all": 3,
    None: 3,  # 缺省等同于 "all"
}

# sync_type → 应被调用的任务名称
EXPECTED_TASKS = {
    "kline": {"sync_realtime_market"},
    "fundamentals": {"sync_fundamentals"},
    "money_flow": {"sync_money_flow"},
    "all": {"sync_realtime_market", "sync_fundamentals", "sync_money_flow"},
    None: {"sync_realtime_market", "sync_fundamentals", "sync_money_flow"},
}


def _make_mock_task(name: str) -> MagicMock:
    """创建一个模拟 Celery 任务，其 .delay() 返回带有唯一 .id 的结果。"""
    mock_task = MagicMock()
    mock_task._name = name

    def _delay(*args, **kwargs):
        result = MagicMock()
        result.id = str(uuid.uuid4())
        return result

    mock_task.delay = MagicMock(side_effect=_delay)
    return mock_task


# ---------------------------------------------------------------------------
# 属性 55：手动同步按类型分发正确的 Celery 任务
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(sync_type=valid_sync_type)
def test_valid_sync_type_dispatches_correct_tasks(sync_type):
    """
    # Feature: data-manage-dual-source-integration, Property 55: 手动同步按类型分发正确的 Celery 任务

    **Validates: Requirements 24.5**

    对任意有效 sync_type，验证：
    1. 返回 SyncResponse 类型
    2. task_ids 数量与期望触发的任务数一致
    3. 每个 task_id 是非空字符串
    4. 仅调用了对应的 Celery 任务的 .delay()
    5. message 不包含 "未知"
    """
    mock_market = _make_mock_task("sync_realtime_market")
    mock_fund = _make_mock_task("sync_fundamentals")
    mock_mf = _make_mock_task("sync_money_flow")

    with patch(
        "app.tasks.data_sync.sync_realtime_market", mock_market
    ), patch(
        "app.tasks.data_sync.sync_fundamentals", mock_fund
    ), patch(
        "app.tasks.data_sync.sync_money_flow", mock_mf
    ):
        body = SyncRequest(sync_type=sync_type) if sync_type is not None else None
        response = asyncio.run(trigger_sync(body))

    # 1. 返回类型正确
    assert isinstance(response, SyncResponse)

    # 2. task_ids 数量正确
    expected_count = EXPECTED_TASK_COUNTS[sync_type]
    assert len(response.task_ids) == expected_count

    # 3. 每个 task_id 是非空字符串
    for tid in response.task_ids:
        assert isinstance(tid, str)
        assert len(tid) > 0

    # 4. 验证正确的任务被调用
    expected_tasks = EXPECTED_TASKS[sync_type]
    if "sync_realtime_market" in expected_tasks:
        mock_market.delay.assert_called_once()
    else:
        mock_market.delay.assert_not_called()

    if "sync_fundamentals" in expected_tasks:
        mock_fund.delay.assert_called_once()
    else:
        mock_fund.delay.assert_not_called()

    if "sync_money_flow" in expected_tasks:
        mock_mf.delay.assert_called_once()
    else:
        mock_mf.delay.assert_not_called()

    # 5. 成功消息不包含 "未知"
    assert "未知" not in response.message


@h_settings(max_examples=50)
@given(sync_type=invalid_sync_type)
def test_invalid_sync_type_returns_error_with_empty_task_ids(sync_type):
    """
    # Feature: data-manage-dual-source-integration, Property 55: 手动同步按类型分发正确的 Celery 任务

    **Validates: Requirements 24.5**

    对任意无效 sync_type，验证：
    1. 返回 SyncResponse 类型
    2. task_ids 为空列表
    3. message 包含 "未知" 错误提示
    4. 不触发任何 Celery 任务
    """
    mock_market = _make_mock_task("sync_realtime_market")
    mock_fund = _make_mock_task("sync_fundamentals")
    mock_mf = _make_mock_task("sync_money_flow")

    with patch(
        "app.tasks.data_sync.sync_realtime_market", mock_market
    ), patch(
        "app.tasks.data_sync.sync_fundamentals", mock_fund
    ), patch(
        "app.tasks.data_sync.sync_money_flow", mock_mf
    ):
        body = SyncRequest(sync_type=sync_type)
        response = asyncio.run(trigger_sync(body))

    # 1. 返回类型正确
    assert isinstance(response, SyncResponse)

    # 2. task_ids 为空
    assert response.task_ids == []

    # 3. 错误消息包含 "未知"
    assert "未知" in response.message

    # 4. 不触发任何任务
    mock_market.delay.assert_not_called()
    mock_fund.delay.assert_not_called()
    mock_mf.delay.assert_not_called()
