"""
认证 API 单元测试

测试 app/api/v1/auth.py 中的端点：
- POST /api/v1/auth/login
- POST /api/v1/auth/register
- GET  /api/v1/auth/check-username
- GET  /api/v1/auth/me

使用 FastAPI dependency_overrides 模拟数据库会话。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import validate_password_strength
from app.core.config import settings
from app.core.database import get_pg_session
from app.core.security import JWTManager, PasswordHasher
from app.main import app
from app.models.user import AppUser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    username: str = "testuser",
    password: str = "Test1234",
    role: str = "TRADER",
    is_active: bool = True,
) -> AppUser:
    """创建一个模拟 AppUser 对象。"""
    user = MagicMock(spec=AppUser)
    user.id = uuid.uuid4()
    user.username = username
    user.password_hash = PasswordHasher.hash_password(password)
    user.role = role
    user.is_active = is_active
    user.created_at = datetime.now()
    return user


def _override_db(user: AppUser | None = None):
    """返回一个 get_pg_session 的覆盖函数，execute 返回指定用户。"""

    async def _fake_session():
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        session.execute.return_value = result_mock
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    return _fake_session


@pytest.fixture()
def client():
    return TestClient(app, headers={"Host": "localhost"})


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """每个测试后清理 dependency_overrides。"""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# validate_password_strength 单元测试
# ---------------------------------------------------------------------------


class TestPasswordValidation:
    def test_valid_password(self):
        assert validate_password_strength("Abcdef1X") == []

    def test_too_short(self):
        errors = validate_password_strength("Ab1")
        assert any("8" in e for e in errors)

    def test_no_uppercase(self):
        errors = validate_password_strength("abcdefg1")
        assert any("大写" in e for e in errors)

    def test_no_lowercase(self):
        errors = validate_password_strength("ABCDEFG1")
        assert any("小写" in e for e in errors)

    def test_no_digit(self):
        errors = validate_password_strength("Abcdefgh")
        assert any("数字" in e for e in errors)

    def test_all_failures(self):
        errors = validate_password_strength("abc")
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, client):
        user = _make_user()
        app.dependency_overrides[get_pg_session] = _override_db(user)

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "Test1234"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["role"] == "TRADER"
        assert data["user"]["id"] == str(user.id)

    def test_login_wrong_password(self, client):
        user = _make_user()
        app.dependency_overrides[get_pg_session] = _override_db(user)

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "WrongPass1"},
        )

        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_login_user_not_found(self, client):
        app.dependency_overrides[get_pg_session] = _override_db(None)

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "noone", "password": "Test1234"},
        )

        assert resp.status_code == 401

    def test_login_inactive_user(self, client):
        user = _make_user(is_active=False)
        app.dependency_overrides[get_pg_session] = _override_db(user)

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "Test1234"},
        )

        assert resp.status_code == 403
        assert "禁用" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_success(self, client):
        app.dependency_overrides[get_pg_session] = _override_db(None)

        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "NewPass1X"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "TRADER"
        assert "id" in data

    def test_register_duplicate_username(self, client):
        existing = _make_user(username="taken")
        app.dependency_overrides[get_pg_session] = _override_db(existing)

        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "taken", "password": "NewPass1X"},
        )

        assert resp.status_code == 409
        assert "已被占用" in resp.json()["detail"]

    def test_register_weak_password(self, client):
        app.dependency_overrides[get_pg_session] = _override_db(None)

        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "weak"},
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/auth/check-username
# ---------------------------------------------------------------------------


class TestCheckUsername:
    def test_username_available(self, client):
        app.dependency_overrides[get_pg_session] = _override_db(None)

        resp = client.get("/api/v1/auth/check-username?username=fresh")

        assert resp.status_code == 200
        assert resp.json()["available"] is True

    def test_username_taken(self, client):
        existing = _make_user(username="taken")
        app.dependency_overrides[get_pg_session] = _override_db(existing)

        resp = client.get("/api/v1/auth/check-username?username=taken")

        assert resp.status_code == 200
        assert resp.json()["available"] is False


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


class TestMe:
    def test_me_success(self, client):
        user = _make_user()
        token = JWTManager.create_token(
            user_id=str(user.id),
            role="TRADER",
            secret=settings.jwt_secret_key,
            expires_minutes=60,
        )
        app.dependency_overrides[get_pg_session] = _override_db(user)

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["role"] == "TRADER"
        assert data["is_active"] is True

    def test_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
