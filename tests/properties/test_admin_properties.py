"""
AdminModule 属性测试（Hypothesis）

**Validates: Requirements 17.1, 17.2, 17.4, 17.5, 19.4**

属性 29：角色权限不变量
属性 30：操作日志 round-trip
属性 31：数据备份恢复 round-trip
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.admin_module import (
    ADMIN_RESOURCES,
    READONLY_RESOURCES,
    ROLE_ADMIN,
    ROLE_READONLY,
    ROLE_TRADER,
    TRADE_RESOURCES,
    VALID_ROLES,
    AuditLogger,
    DataManager,
    RBACMiddleware,
    UserManager,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_role_strategy = st.sampled_from([ROLE_TRADER, ROLE_ADMIN, ROLE_READONLY])

_all_resources = sorted(TRADE_RESOURCES | ADMIN_RESOURCES | READONLY_RESOURCES)
_resource_strategy = st.sampled_from(_all_resources)

_username_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

_action_strategy = st.sampled_from([
    "CREATE", "DELETE", "UPDATE", "VIEW", "SUBMIT_ORDER",
    "CANCEL_ORDER", "RUN_BACKTEST", "CONFIGURE",
])

_target_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
)

_detail_strategy = st.text(min_size=0, max_size=100)

# Strategy for generating arbitrary JSON-serializable data for backup tests
_json_leaf = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=20),
    st.booleans(),
    st.none(),
)

_json_value = st.recursive(
    _json_leaf,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=10,
            ),
            children,
            max_size=5,
        ),
    ),
    max_leaves=20,
)

_backup_data_strategy = st.dictionaries(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=10,
    ),
    _json_value,
    min_size=1,
    max_size=5,
)


# ---------------------------------------------------------------------------
# 属性 29：角色权限不变量
# Feature: a-share-quant-trading-system, Property 29: 角色权限不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(resource=st.sampled_from(sorted(TRADE_RESOURCES)))
def test_readonly_cannot_access_trade_resources(resource: str):
    """
    # Feature: a-share-quant-trading-system, Property 29: 角色权限不变量

    **Validates: Requirements 17.1, 19.4**

    READONLY 角色不应能访问任何交易功能资源。
    """
    rbac = RBACMiddleware()
    assert rbac.check_permission(ROLE_READONLY, resource) is False, (
        f"READONLY should NOT access trade resource '{resource}'"
    )


@settings(max_examples=100)
@given(resource=st.sampled_from(sorted(ADMIN_RESOURCES)))
def test_readonly_cannot_access_admin_resources(resource: str):
    """
    # Feature: a-share-quant-trading-system, Property 29: 角色权限不变量

    **Validates: Requirements 17.1, 19.4**

    READONLY 角色不应能访问任何管理功能资源。
    """
    rbac = RBACMiddleware()
    assert rbac.check_permission(ROLE_READONLY, resource) is False, (
        f"READONLY should NOT access admin resource '{resource}'"
    )


@settings(max_examples=100)
@given(resource=st.sampled_from(sorted(ADMIN_RESOURCES)))
def test_trader_cannot_access_admin_resources(resource: str):
    """
    # Feature: a-share-quant-trading-system, Property 29: 角色权限不变量

    **Validates: Requirements 17.1, 19.4**

    TRADER 角色不应能访问任何管理功能资源。
    """
    rbac = RBACMiddleware()
    assert rbac.check_permission(ROLE_TRADER, resource) is False, (
        f"TRADER should NOT access admin resource '{resource}'"
    )


@settings(max_examples=100)
@given(resource=_resource_strategy)
def test_admin_can_access_all_resources(resource: str):
    """
    # Feature: a-share-quant-trading-system, Property 29: 角色权限不变量

    **Validates: Requirements 17.1, 19.4**

    ADMIN 角色应能访问所有资源。
    """
    rbac = RBACMiddleware()
    assert rbac.check_permission(ROLE_ADMIN, resource) is True, (
        f"ADMIN should access resource '{resource}'"
    )


# ---------------------------------------------------------------------------
# 属性 30：操作日志 round-trip
# Feature: a-share-quant-trading-system, Property 30: 操作日志 round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    user_id=_username_strategy,
    action=_action_strategy,
    target=_target_strategy,
    detail=_detail_strategy,
)
def test_audit_log_round_trip(
    user_id: str,
    action: str,
    target: str,
    detail: str,
):
    """
    # Feature: a-share-quant-trading-system, Property 30: 操作日志 round-trip

    **Validates: Requirements 17.2, 17.5**

    对任意用户执行的操作，该操作应在日志中留有记录，
    且日志记录应包含操作人、操作时间、操作类型、操作对象四个字段，均不为空。
    """
    logger = AuditLogger()
    entry = logger.log(user_id, action, target, detail=detail)

    # 验证日志条目字段非空
    assert entry["user_id"] != "", "user_id must not be empty"
    assert entry["action"] != "", "action must not be empty"
    assert entry["target"] != "", "target must not be empty"
    assert entry["timestamp"] is not None, "timestamp must not be None"

    # 验证可通过查询接口检索到
    now = datetime.now()
    results = logger.query(
        start_date=now - timedelta(seconds=5),
        end_date=now + timedelta(seconds=5),
    )
    assert len(results) >= 1, "Log entry should be queryable"

    found = results[0]
    assert found["user_id"] == user_id
    assert found["action"] == action
    assert found["target"] == target


# ---------------------------------------------------------------------------
# 属性 31：数据备份恢复 round-trip
# Feature: a-share-quant-trading-system, Property 31: 数据备份恢复 round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(data=_backup_data_strategy)
def test_backup_restore_round_trip(data: dict):
    """
    # Feature: a-share-quant-trading-system, Property 31: 数据备份恢复 round-trip

    **Validates: Requirements 17.4**

    对任意系统数据状态，执行备份后再执行恢复操作，
    恢复后的数据应与备份时的数据完全一致。
    """
    dm = DataManager()
    backup_id = dm.backup(data)
    restored = dm.restore(backup_id)
    assert restored == data, (
        f"Restored data should equal original.\n"
        f"Original: {data}\n"
        f"Restored: {restored}"
    )


@settings(max_examples=100)
@given(data=_backup_data_strategy)
def test_backup_restore_isolation(data: dict):
    """
    # Feature: a-share-quant-trading-system, Property 31: 数据备份恢复 round-trip

    **Validates: Requirements 17.4**

    恢复后修改返回的数据不应影响后续恢复结果（深拷贝隔离）。
    """
    dm = DataManager()
    backup_id = dm.backup(data)

    restored1 = dm.restore(backup_id)
    # Mutate the first restoration
    if isinstance(restored1, dict) and restored1:
        first_key = next(iter(restored1))
        restored1[first_key] = "MUTATED"

    restored2 = dm.restore(backup_id)
    assert restored2 == data, "Second restore should still match original data"
