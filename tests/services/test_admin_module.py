"""
AdminModule 单元测试

覆盖任务 10.1 ~ 10.4：
- 10.1 用户权限管理（UserManager + RBACMiddleware）
- 10.2 系统监控与告警（SystemMonitor）
- 10.3 数据管理功能（DataManager）
- 10.4 全流程日志记录（AuditLogger）
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.admin_module import (
    ADMIN_RESOURCES,
    READONLY_RESOURCES,
    ROLE_ADMIN,
    ROLE_READONLY,
    ROLE_TRADER,
    TRADE_RESOURCES,
    AuditLogger,
    DataManager,
    RBACMiddleware,
    SystemMonitor,
    UserManager,
)


# ---------------------------------------------------------------------------
# UserManager 测试（任务 10.1）
# ---------------------------------------------------------------------------


class TestUserManagerCreate:
    def test_create_user_returns_dict(self):
        mgr = UserManager()
        user = mgr.create_user("alice", "hash123", ROLE_TRADER)
        assert isinstance(user, dict)
        assert user["username"] == "alice"
        assert user["role"] == ROLE_TRADER
        assert user["is_active"] is True

    def test_create_user_has_id(self):
        mgr = UserManager()
        user = mgr.create_user("bob", "hash456", ROLE_ADMIN)
        assert "user_id" in user
        assert len(user["user_id"]) > 0

    def test_create_user_invalid_role_raises(self):
        mgr = UserManager()
        with pytest.raises(ValueError, match="Invalid role"):
            mgr.create_user("charlie", "hash", "SUPERUSER")

    def test_create_user_empty_username_raises(self):
        mgr = UserManager()
        with pytest.raises(ValueError, match="Username must not be empty"):
            mgr.create_user("", "hash", ROLE_TRADER)

    def test_create_multiple_users_unique_ids(self):
        mgr = UserManager()
        u1 = mgr.create_user("a", "h1", ROLE_TRADER)
        u2 = mgr.create_user("b", "h2", ROLE_ADMIN)
        assert u1["user_id"] != u2["user_id"]


class TestUserManagerDelete:
    def test_delete_existing_user(self):
        mgr = UserManager()
        user = mgr.create_user("alice", "hash", ROLE_TRADER)
        assert mgr.delete_user(user["user_id"]) is True
        assert mgr.get_user(user["user_id"]) is None

    def test_delete_nonexistent_user(self):
        mgr = UserManager()
        assert mgr.delete_user("nonexistent") is False


class TestUserManagerAssignRole:
    def test_assign_valid_role(self):
        mgr = UserManager()
        user = mgr.create_user("alice", "hash", ROLE_TRADER)
        assert mgr.assign_role(user["user_id"], ROLE_ADMIN) is True
        assert mgr.get_user(user["user_id"])["role"] == ROLE_ADMIN

    def test_assign_invalid_role_raises(self):
        mgr = UserManager()
        user = mgr.create_user("alice", "hash", ROLE_TRADER)
        with pytest.raises(ValueError):
            mgr.assign_role(user["user_id"], "INVALID")

    def test_assign_role_nonexistent_user(self):
        mgr = UserManager()
        assert mgr.assign_role("nonexistent", ROLE_ADMIN) is False


class TestUserManagerGetList:
    def test_get_user(self):
        mgr = UserManager()
        user = mgr.create_user("alice", "hash", ROLE_TRADER)
        retrieved = mgr.get_user(user["user_id"])
        assert retrieved is not None
        assert retrieved["username"] == "alice"

    def test_get_nonexistent_user(self):
        mgr = UserManager()
        assert mgr.get_user("nonexistent") is None

    def test_list_users(self):
        mgr = UserManager()
        mgr.create_user("a", "h1", ROLE_TRADER)
        mgr.create_user("b", "h2", ROLE_ADMIN)
        assert len(mgr.list_users()) == 2


# ---------------------------------------------------------------------------
# RBACMiddleware 测试（任务 10.1）
# ---------------------------------------------------------------------------


class TestRBACMiddleware:
    def test_admin_can_access_all(self):
        rbac = RBACMiddleware()
        for res in TRADE_RESOURCES | ADMIN_RESOURCES | READONLY_RESOURCES:
            assert rbac.check_permission(ROLE_ADMIN, res) is True

    def test_trader_can_access_trade_resources(self):
        rbac = RBACMiddleware()
        for res in TRADE_RESOURCES:
            assert rbac.check_permission(ROLE_TRADER, res) is True

    def test_trader_can_access_readonly_resources(self):
        rbac = RBACMiddleware()
        for res in READONLY_RESOURCES:
            assert rbac.check_permission(ROLE_TRADER, res) is True

    def test_trader_cannot_access_admin_resources(self):
        rbac = RBACMiddleware()
        for res in ADMIN_RESOURCES:
            assert rbac.check_permission(ROLE_TRADER, res) is False

    def test_readonly_can_access_readonly_resources(self):
        rbac = RBACMiddleware()
        for res in READONLY_RESOURCES:
            assert rbac.check_permission(ROLE_READONLY, res) is True

    def test_readonly_cannot_access_trade_resources(self):
        rbac = RBACMiddleware()
        for res in TRADE_RESOURCES:
            assert rbac.check_permission(ROLE_READONLY, res) is False

    def test_readonly_cannot_access_admin_resources(self):
        rbac = RBACMiddleware()
        for res in ADMIN_RESOURCES:
            assert rbac.check_permission(ROLE_READONLY, res) is False

    def test_invalid_role_denied(self):
        rbac = RBACMiddleware()
        assert rbac.check_permission("SUPERUSER", "market:view") is False


# ---------------------------------------------------------------------------
# SystemMonitor 测试（任务 10.2）
# ---------------------------------------------------------------------------


class TestSystemMonitor:
    def test_register_and_check_module(self):
        mon = SystemMonitor()
        mon.register_module("DataEngine")
        status = mon.check_module_status("DataEngine")
        assert status["module"] == "DataEngine"
        assert status["status"] == "OK"

    def test_check_unregistered_module(self):
        mon = SystemMonitor()
        status = mon.check_module_status("Unknown")
        assert status["status"] == "UNKNOWN"

    def test_report_error_changes_status(self):
        mon = SystemMonitor()
        mon.register_module("DataEngine")
        mon.report_module_error("DataEngine", "Connection lost")
        status = mon.check_module_status("DataEngine")
        assert status["status"] == "ERROR"
        assert status["message"] == "Connection lost"

    def test_report_error_triggers_alert_callback(self):
        alerts = []
        mon = SystemMonitor(alert_callback=lambda a: alerts.append(a))
        mon.register_module("DataEngine")
        mon.report_module_error("DataEngine", "Timeout")
        assert len(alerts) == 1
        assert alerts[0]["type"] == "MODULE_ERROR"
        assert alerts[0]["module"] == "DataEngine"

    def test_report_ok_restores_status(self):
        mon = SystemMonitor()
        mon.register_module("DataEngine")
        mon.report_module_error("DataEngine", "Error")
        mon.report_module_ok("DataEngine")
        status = mon.check_module_status("DataEngine")
        assert status["status"] == "OK"

    def test_system_health_healthy(self):
        mon = SystemMonitor()
        mon.register_module("A")
        mon.register_module("B")
        health = mon.get_system_health()
        assert health["overall"] == "HEALTHY"
        assert health["total_modules"] == 2
        assert health["error_count"] == 0

    def test_system_health_degraded(self):
        mon = SystemMonitor()
        mon.register_module("A")
        mon.register_module("B")
        mon.report_module_error("A", "down")
        health = mon.get_system_health()
        assert health["overall"] == "DEGRADED"
        assert health["error_count"] == 1


# ---------------------------------------------------------------------------
# DataManager 测试（任务 10.3）
# ---------------------------------------------------------------------------


class TestDataManagerBackupRestore:
    def test_backup_returns_id(self):
        dm = DataManager()
        bid = dm.backup({"key": "value"})
        assert isinstance(bid, str) and len(bid) > 0

    def test_restore_returns_original_data(self):
        dm = DataManager()
        data = {"strategies": [1, 2, 3], "config": {"a": 1}}
        bid = dm.backup(data)
        restored = dm.restore(bid)
        assert restored == data

    def test_restore_is_deep_copy(self):
        dm = DataManager()
        data = {"nested": {"x": 1}}
        bid = dm.backup(data)
        restored = dm.restore(bid)
        restored["nested"]["x"] = 999
        restored2 = dm.restore(bid)
        assert restored2["nested"]["x"] == 1

    def test_restore_nonexistent_raises(self):
        dm = DataManager()
        with pytest.raises(KeyError):
            dm.restore("nonexistent")

    def test_list_backups(self):
        dm = DataManager()
        dm.backup({"a": 1})
        dm.backup({"b": 2})
        backups = dm.list_backups()
        assert len(backups) == 2
        assert "backup_id" in backups[0]

    def test_backup_does_not_mutate_on_source_change(self):
        dm = DataManager()
        data = {"items": [1, 2]}
        bid = dm.backup(data)
        data["items"].append(3)
        restored = dm.restore(bid)
        assert restored["items"] == [1, 2]


class TestDataManagerConfig:
    def test_set_and_get_config(self):
        dm = DataManager()
        dm.set_config("max_strategies", 20)
        assert dm.get_config("max_strategies") == 20

    def test_get_nonexistent_config(self):
        dm = DataManager()
        assert dm.get_config("missing") is None

    def test_get_all_config(self):
        dm = DataManager()
        dm.set_config("a", 1)
        dm.set_config("b", 2)
        cfg = dm.get_all_config()
        assert cfg == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# AuditLogger 测试（任务 10.4）
# ---------------------------------------------------------------------------


class TestAuditLoggerLog:
    def test_log_returns_entry(self):
        logger = AuditLogger()
        entry = logger.log("user1", "CREATE", "strategy:123")
        assert entry["user_id"] == "user1"
        assert entry["action"] == "CREATE"
        assert entry["target"] == "strategy:123"
        assert isinstance(entry["timestamp"], datetime)

    def test_log_with_detail(self):
        logger = AuditLogger()
        entry = logger.log("user1", "DELETE", "user:456", detail="removed by admin")
        assert entry["detail"] == "removed by admin"

    def test_log_without_detail_defaults_empty(self):
        logger = AuditLogger()
        entry = logger.log("user1", "VIEW", "dashboard")
        assert entry["detail"] == ""


class TestAuditLoggerQuery:
    def test_query_all(self):
        logger = AuditLogger()
        logger.log("u1", "A", "t1")
        logger.log("u2", "B", "t2")
        assert len(logger.query()) == 2

    def test_query_by_user_id(self):
        logger = AuditLogger()
        logger.log("u1", "A", "t1")
        logger.log("u2", "B", "t2")
        results = logger.query(user_id="u1")
        assert len(results) == 1
        assert results[0]["user_id"] == "u1"

    def test_query_by_date_range(self):
        logger = AuditLogger()
        logger.log("u1", "A", "t1")
        now = datetime.now()
        results = logger.query(
            start_date=now - timedelta(seconds=5),
            end_date=now + timedelta(seconds=5),
        )
        assert len(results) == 1

    def test_query_empty(self):
        logger = AuditLogger()
        assert logger.query() == []


class TestAuditLoggerRetention:
    def test_retention_days_default(self):
        logger = AuditLogger()
        assert logger.retention_days == 365

    def test_retention_days_custom(self):
        logger = AuditLogger(retention_days=730)
        assert logger.retention_days == 730

    def test_purge_expired_removes_old_logs(self):
        logger = AuditLogger(retention_days=30)
        # Manually insert an old log
        old_entry = {
            "user_id": "u1",
            "action": "OLD",
            "target": "t1",
            "timestamp": datetime.now() - timedelta(days=60),
            "detail": "",
        }
        logger._logs.append(old_entry)
        logger.log("u2", "NEW", "t2")
        purged = logger.purge_expired()
        assert purged == 1
        assert len(logger.query()) == 1

    def test_purge_keeps_recent_logs(self):
        logger = AuditLogger(retention_days=365)
        logger.log("u1", "A", "t1")
        purged = logger.purge_expired()
        assert purged == 0
        assert len(logger.query()) == 1
