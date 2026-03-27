"""
安全测试

验证：
- 角色权限隔离（越权访问应返回 403 / 拒绝）
- 二次验证拦截（未验证的核心操作应被拒绝）
- 非交易时段委托拒绝
- JWT 令牌验证（过期/无效令牌拒绝）
- API 频率限制

需求 17.1, 19.3, 19.4, 14.5
"""

from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.schemas import (
    OrderDirection,
    OrderRequest,
    OrderStatus,
    OrderType,
    TradeMode,
)
from app.core.security import JWTManager, RateLimiter, TOTPVerifier
from app.services.admin_module import (
    ADMIN_RESOURCES,
    READONLY_RESOURCES,
    ROLE_ADMIN,
    ROLE_READONLY,
    ROLE_TRADER,
    TRADE_RESOURCES,
    RBACMiddleware,
    UserManager,
)
from app.services.trade_executor import TradeExecutor


# ---------------------------------------------------------------------------
# RBAC 角色权限隔离测试（需求 17.1, 19.4）
# ---------------------------------------------------------------------------


class TestRBACPermissions:
    """验证角色权限隔离：越权访问应被拒绝。"""

    def setup_method(self):
        self.rbac = RBACMiddleware()

    def test_readonly_cannot_access_trade_resources(self):
        """READONLY 用户不可访问交易功能（属性 29）。"""
        for resource in TRADE_RESOURCES:
            assert self.rbac.check_permission(ROLE_READONLY, resource) is False

    def test_readonly_cannot_access_admin_resources(self):
        """READONLY 用户不可访问管理功能。"""
        for resource in ADMIN_RESOURCES:
            assert self.rbac.check_permission(ROLE_READONLY, resource) is False

    def test_readonly_can_access_readonly_resources(self):
        """READONLY 用户可以访问只读资源。"""
        for resource in READONLY_RESOURCES:
            assert self.rbac.check_permission(ROLE_READONLY, resource) is True

    def test_trader_cannot_access_admin_resources(self):
        """TRADER 用户不可访问系统管理功能（属性 29）。"""
        for resource in ADMIN_RESOURCES:
            assert self.rbac.check_permission(ROLE_TRADER, resource) is False

    def test_trader_can_access_trade_and_readonly(self):
        """TRADER 用户可以访问交易和只读资源。"""
        for resource in TRADE_RESOURCES:
            assert self.rbac.check_permission(ROLE_TRADER, resource) is True
        for resource in READONLY_RESOURCES:
            assert self.rbac.check_permission(ROLE_TRADER, resource) is True

    def test_admin_can_access_all_resources(self):
        """ADMIN 用户可以访问所有资源。"""
        all_resources = TRADE_RESOURCES | ADMIN_RESOURCES | READONLY_RESOURCES
        for resource in all_resources:
            assert self.rbac.check_permission(ROLE_ADMIN, resource) is True

    def test_invalid_role_denied(self):
        """无效角色应被拒绝访问所有资源。"""
        assert self.rbac.check_permission("HACKER", "market:view") is False
        assert self.rbac.check_permission("", "order:submit") is False


# ---------------------------------------------------------------------------
# TOTP 二次验证测试（需求 19.3）
# ---------------------------------------------------------------------------


class TestTOTPVerification:
    """验证二次身份验证拦截。"""

    def test_valid_totp_code_accepted(self):
        """正确的 TOTP 码应通过验证。"""
        secret = TOTPVerifier.generate_secret()
        code = TOTPVerifier.get_current_code(secret)
        assert TOTPVerifier.verify_code(secret, code) is True

    def test_invalid_totp_code_rejected(self):
        """错误的 TOTP 码应被拒绝。"""
        secret = TOTPVerifier.generate_secret()
        assert TOTPVerifier.verify_code(secret, "000000") is False
        assert TOTPVerifier.verify_code(secret, "999999") is False

    def test_wrong_secret_rejected(self):
        """使用错误 secret 生成的码应被拒绝。"""
        secret1 = TOTPVerifier.generate_secret()
        secret2 = TOTPVerifier.generate_secret()
        code = TOTPVerifier.get_current_code(secret1)
        # Verify with wrong secret
        assert TOTPVerifier.verify_code(secret2, code) is False


# ---------------------------------------------------------------------------
# 非交易时段委托拒绝测试（需求 14.5, 属性 26）
# ---------------------------------------------------------------------------


class TestTradingHoursEnforcement:
    """验证非交易时段委托拒绝。"""

    @staticmethod
    def _make_order() -> OrderRequest:
        return OrderRequest(
            symbol="000001",
            direction=OrderDirection.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal("10.00"),
        )

    def test_order_rejected_outside_trading_hours(self):
        """非交易时段提交的委托应被拒绝（OUTSIDE_TRADING_HOURS）。"""
        # Saturday 10:00
        weekend_time = datetime(2024, 3, 16, 10, 0)
        executor = TradeExecutor(
            mode=TradeMode.PAPER,
            now_fn=lambda: weekend_time,
        )
        resp = executor.submit_order(self._make_order())
        assert resp.status == OrderStatus.REJECTED
        assert resp.message == "OUTSIDE_TRADING_HOURS"

    def test_order_rejected_before_market_open(self):
        """开盘前（9:25 之前）委托应被拒绝。"""
        early_time = datetime(2024, 3, 18, 8, 0)  # Monday 8:00
        executor = TradeExecutor(
            mode=TradeMode.PAPER,
            now_fn=lambda: early_time,
        )
        resp = executor.submit_order(self._make_order())
        assert resp.status == OrderStatus.REJECTED

    def test_order_rejected_after_market_close(self):
        """收盘后（15:00 之后）委托应被拒绝。"""
        late_time = datetime(2024, 3, 18, 16, 0)  # Monday 16:00
        executor = TradeExecutor(
            mode=TradeMode.PAPER,
            now_fn=lambda: late_time,
        )
        resp = executor.submit_order(self._make_order())
        assert resp.status == OrderStatus.REJECTED

    def test_order_accepted_during_trading_hours(self):
        """交易时段内委托应被接受。"""
        trading_time = datetime(2024, 3, 18, 10, 30)  # Monday 10:30
        executor = TradeExecutor(
            mode=TradeMode.PAPER,
            now_fn=lambda: trading_time,
        )
        resp = executor.submit_order(self._make_order())
        assert resp.status != OrderStatus.REJECTED
        assert resp.order_id != ""


# ---------------------------------------------------------------------------
# JWT 令牌安全测试（需求 19.3）
# ---------------------------------------------------------------------------


class TestJWTSecurity:
    """验证 JWT 令牌验证机制。"""

    SECRET = "test-secret-key-for-jwt"

    def test_valid_token_accepted(self):
        """有效 JWT 令牌应通过验证。"""
        token = JWTManager.create_token("user1", ROLE_TRADER, self.SECRET)
        payload = JWTManager.verify_token(token, self.SECRET)
        assert payload is not None
        assert payload["sub"] == "user1"
        assert payload["role"] == ROLE_TRADER

    def test_expired_token_rejected(self):
        """过期 JWT 令牌应被拒绝。"""
        token = JWTManager.create_token(
            "user1", ROLE_TRADER, self.SECRET, expires_minutes=-1
        )
        payload = JWTManager.verify_token(token, self.SECRET)
        assert payload is None

    def test_tampered_token_rejected(self):
        """篡改后的 JWT 令牌应被拒绝。"""
        token = JWTManager.create_token("user1", ROLE_TRADER, self.SECRET)
        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1][::-1]  # reverse payload
        tampered = ".".join(parts)
        payload = JWTManager.verify_token(tampered, self.SECRET)
        assert payload is None

    def test_wrong_secret_rejected(self):
        """使用错误密钥验证的令牌应被拒绝。"""
        token = JWTManager.create_token("user1", ROLE_TRADER, self.SECRET)
        payload = JWTManager.verify_token(token, "wrong-secret")
        assert payload is None

    def test_malformed_token_rejected(self):
        """格式错误的令牌应被拒绝。"""
        assert JWTManager.verify_token("not.a.valid.token", self.SECRET) is None
        assert JWTManager.verify_token("", self.SECRET) is None
        assert JWTManager.verify_token("abc", self.SECRET) is None


# ---------------------------------------------------------------------------
# API 频率限制测试（需求 19.3）
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """验证 API 频率限制。"""

    def test_rate_limit_blocks_excessive_requests(self):
        """超过频率限制的请求应被拒绝。"""
        limiter = RateLimiter()
        key = "test-ip-192.168.1.1"

        # Allow first 5 requests
        for _ in range(5):
            assert limiter.check(key, max_requests=5, window_seconds=60) is True

        # 6th request should be blocked
        assert limiter.check(key, max_requests=5, window_seconds=60) is False

    def test_rate_limit_resets_after_window(self):
        """窗口过期后频率限制应重置。"""
        limiter = RateLimiter()
        key = "test-ip"

        # Fill up the limit with a very short window
        for _ in range(3):
            limiter.check(key, max_requests=3, window_seconds=1)

        assert limiter.check(key, max_requests=3, window_seconds=1) is False

        # After window expires, should allow again
        time.sleep(1.1)
        assert limiter.check(key, max_requests=3, window_seconds=1) is True

    def test_remaining_requests_count(self):
        """剩余请求次数应正确计算。"""
        limiter = RateLimiter()
        key = "counter-test"

        assert limiter.get_remaining(key, max_requests=10) == 10
        limiter.check(key, max_requests=10)
        assert limiter.get_remaining(key, max_requests=10) == 9
