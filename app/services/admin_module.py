"""
系统管理模块 — AdminModule

实现需求 17：
- 17.1 用户账号 CRUD + 三种角色（TRADER/ADMIN/READONLY）权限配置
- 17.2 / 17.5 全流程操作日志记录（操作人/时间/类型/对象），保留 ≥ 1 年
- 17.3 数据接口连接状态 & 模块运行状态实时监控，异常自动告警
- 17.4 数据备份与恢复、策略模板统一管理、系统参数配置
- 19.4 RBAC 权限控制：READONLY 不可访问交易功能，TRADER 不可访问管理功能
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable


# ---------------------------------------------------------------------------
# 角色常量
# ---------------------------------------------------------------------------

ROLE_TRADER = "TRADER"
ROLE_ADMIN = "ADMIN"
ROLE_READONLY = "READONLY"

VALID_ROLES = {ROLE_TRADER, ROLE_ADMIN, ROLE_READONLY}


# ---------------------------------------------------------------------------
# 资源分类（用于 RBAC）
# ---------------------------------------------------------------------------

TRADE_RESOURCES = {
    "order:submit", "order:cancel", "position:modify",
    "condition_order:create", "condition_order:cancel",
}

ADMIN_RESOURCES = {
    "user:create", "user:delete", "user:assign_role",
    "system:config", "system:backup", "system:restore",
}

READONLY_RESOURCES = {
    "market:view", "screen:view", "position:view",
    "backtest:view", "review:view", "log:view",
}

# TRADER 可访问只读 + 交易资源
# ADMIN 可访问所有资源
# READONLY 只能访问只读资源


# ---------------------------------------------------------------------------
# UserManager — 用户账号管理（需求 17.1）
# ---------------------------------------------------------------------------


class UserManager:
    """用户账号新增/删除/权限分配，内存实现。"""

    def __init__(self) -> None:
        self._users: dict[str, dict] = {}

    def create_user(self, username: str, password_hash: str, role: str) -> dict:
        """创建用户，返回用户字典。"""
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")
        if not username:
            raise ValueError("Username must not be empty")
        user_id = uuid.uuid4().hex[:12]
        user = {
            "user_id": user_id,
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "is_active": True,
            "created_at": datetime.now(),
        }
        self._users[user_id] = user
        return user

    def delete_user(self, user_id: str) -> bool:
        """删除用户，成功返回 True。"""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False

    def assign_role(self, user_id: str, role: str) -> bool:
        """分配角色，成功返回 True。"""
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")
        user = self._users.get(user_id)
        if user is None:
            return False
        user["role"] = role
        return True

    def get_user(self, user_id: str) -> dict | None:
        """获取用户信息。"""
        return self._users.get(user_id)

    def list_users(self) -> list[dict]:
        """列出所有用户。"""
        return list(self._users.values())


# ---------------------------------------------------------------------------
# RBACMiddleware — 基于角色的访问控制（需求 19.4）
# ---------------------------------------------------------------------------


class RBACMiddleware:
    """RBAC 权限校验中间件。

    权限矩阵：
    - READONLY：只能访问 READONLY_RESOURCES
    - TRADER：可访问 READONLY_RESOURCES + TRADE_RESOURCES
    - ADMIN：可访问所有资源
    """

    def check_permission(self, user_role: str, resource: str) -> bool:
        """检查角色是否有权访问指定资源。"""
        if user_role not in VALID_ROLES:
            return False

        if user_role == ROLE_ADMIN:
            return True

        if user_role == ROLE_TRADER:
            return resource in TRADE_RESOURCES or resource in READONLY_RESOURCES

        # READONLY
        return resource in READONLY_RESOURCES


# ---------------------------------------------------------------------------
# SystemMonitor — 系统监控与告警（需求 17.3）
# ---------------------------------------------------------------------------


class SystemMonitor:
    """系统模块运行状态监控 & 异常自动告警。"""

    def __init__(self, alert_callback: Callable[[dict], None] | None = None) -> None:
        self._module_statuses: dict[str, dict] = {}
        self._alert_callback = alert_callback

    def register_module(self, module_name: str) -> None:
        """注册一个被监控的模块。"""
        self._module_statuses[module_name] = {
            "module": module_name,
            "status": "OK",
            "message": "",
            "last_check": datetime.now(),
        }

    def check_module_status(self, module_name: str) -> dict:
        """检查指定模块状态。"""
        status = self._module_statuses.get(module_name)
        if status is None:
            return {
                "module": module_name,
                "status": "UNKNOWN",
                "message": f"Module '{module_name}' is not registered",
            }
        status["last_check"] = datetime.now()
        return dict(status)

    def report_module_error(self, module_name: str, message: str) -> None:
        """报告模块异常，自动触发告警。"""
        if module_name in self._module_statuses:
            self._module_statuses[module_name]["status"] = "ERROR"
            self._module_statuses[module_name]["message"] = message
        alert = {
            "type": "MODULE_ERROR",
            "module": module_name,
            "message": message,
            "time": datetime.now(),
        }
        if self._alert_callback:
            self._alert_callback(alert)

    def report_module_ok(self, module_name: str) -> None:
        """报告模块恢复正常。"""
        if module_name in self._module_statuses:
            self._module_statuses[module_name]["status"] = "OK"
            self._module_statuses[module_name]["message"] = ""

    def get_system_health(self) -> dict:
        """获取系统整体健康状态摘要。"""
        modules = list(self._module_statuses.values())
        error_modules = [m for m in modules if m["status"] == "ERROR"]
        overall = "HEALTHY" if not error_modules else "DEGRADED"
        return {
            "overall": overall,
            "total_modules": len(modules),
            "error_count": len(error_modules),
            "modules": [dict(m) for m in modules],
        }


# ---------------------------------------------------------------------------
# DataManager — 数据备份/恢复 & 配置管理（需求 17.4）
# ---------------------------------------------------------------------------


class DataManager:
    """数据备份与恢复、策略模板管理、系统参数配置。"""

    def __init__(self) -> None:
        self._backups: dict[str, dict] = {}
        self._config: dict[str, Any] = {}

    # -- 备份与恢复 ---------------------------------------------------------

    def backup(self, data: dict) -> str:
        """备份数据，返回 backup_id。"""
        backup_id = uuid.uuid4().hex[:12]
        self._backups[backup_id] = {
            "backup_id": backup_id,
            "data": copy.deepcopy(data),
            "created_at": datetime.now(),
        }
        return backup_id

    def restore(self, backup_id: str) -> dict:
        """恢复数据，返回备份时的数据副本。"""
        record = self._backups.get(backup_id)
        if record is None:
            raise KeyError(f"Backup '{backup_id}' not found")
        return copy.deepcopy(record["data"])

    def list_backups(self) -> list[dict]:
        """列出所有备份记录（不含数据本体）。"""
        return [
            {"backup_id": r["backup_id"], "created_at": r["created_at"]}
            for r in self._backups.values()
        ]

    # -- 系统参数配置 -------------------------------------------------------

    def get_config(self, key: str) -> Any:
        """获取配置项。"""
        return self._config.get(key)

    def set_config(self, key: str, value: Any) -> None:
        """设置配置项。"""
        self._config[key] = value

    def get_all_config(self) -> dict:
        """获取所有配置。"""
        return dict(self._config)


# ---------------------------------------------------------------------------
# AuditLogger — 全流程日志记录（需求 17.2 / 17.5）
# ---------------------------------------------------------------------------


class AuditLogger:
    """操作日志记录与查询。

    每条日志包含：user_id, action, target, timestamp, detail
    日志保留策略：≥ 1 年（通过 retention_days 配置）。
    """

    def __init__(self, retention_days: int = 365) -> None:
        self._logs: list[dict] = []
        self._retention_days = retention_days

    def log(
        self,
        user_id: str,
        action: str,
        target: str,
        detail: str | None = None,
    ) -> dict:
        """记录一条操作日志，返回日志条目。"""
        entry = {
            "user_id": user_id,
            "action": action,
            "target": target,
            "timestamp": datetime.now(),
            "detail": detail or "",
        }
        self._logs.append(entry)
        return entry

    def query(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """查询日志，支持按时间范围和用户过滤。"""
        results = self._logs
        if start_date is not None:
            results = [r for r in results if r["timestamp"] >= start_date]
        if end_date is not None:
            results = [r for r in results if r["timestamp"] <= end_date]
        if user_id is not None:
            results = [r for r in results if r["user_id"] == user_id]
        return results

    def purge_expired(self) -> int:
        """清理超过保留期的日志，返回清理数量。"""
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        before = len(self._logs)
        self._logs = [r for r in self._logs if r["timestamp"] >= cutoff]
        return before - len(self._logs)

    @property
    def retention_days(self) -> int:
        return self._retention_days
