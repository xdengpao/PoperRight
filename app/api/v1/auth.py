"""
认证 API

- POST /auth/login          — 用户登录（返回 access_token + 用户信息）
- POST /auth/register       — 用户注册（用户名唯一性 + 密码强度校验）
- GET  /auth/check-username  — 用户名唯一性实时校验
- GET  /auth/me              — 获取当前登录用户信息

需求：21.1, 21.2, 21.3
"""

from __future__ import annotations

import re
from uuid import UUID as _UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_pg_session
from app.core.security import JWTManager, PasswordHasher
from app.models.user import AppUser

router = APIRouter(prefix="/auth", tags=["认证"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    user: UserInfo


class RegisterRequest(BaseModel):
    username: str
    password: str


class RegisterResponse(BaseModel):
    id: str
    username: str
    role: str


class CheckUsernameResponse(BaseModel):
    available: bool
    message: str


class MeResponse(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool


# ---------------------------------------------------------------------------
# 密码强度校验
# ---------------------------------------------------------------------------


def validate_password_strength(password: str) -> list[str]:
    """校验密码强度，返回未满足条件的列表。

    规则：≥8位、包含大写字母、包含小写字母、包含数字
    """
    errors: list[str] = []
    if len(password) < 8:
        errors.append("密码长度至少8位")
    if not re.search(r"[A-Z]", password):
        errors.append("密码需包含大写字母")
    if not re.search(r"[a-z]", password):
        errors.append("密码需包含小写字母")
    if not re.search(r"\d", password):
        errors.append("密码需包含数字")
    return errors


# ---------------------------------------------------------------------------
# JWT 依赖：从 Authorization header 解析当前用户
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_pg_session),
) -> AppUser:
    """从 Authorization: Bearer <token> 解析并返回当前用户。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供登录凭证",
        )
    token = authorization[len("Bearer "):]

    payload = JWTManager.verify_token(token, settings.jwt_secret_key)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的登录凭证",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录凭证",
        )

    result = await db.execute(
        select(AppUser).where(AppUser.id == _UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_pg_session),
) -> LoginResponse:
    """用户登录，返回 access_token 和用户信息。"""
    result = await db.execute(
        select(AppUser).where(AppUser.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not PasswordHasher.verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    access_token = JWTManager.create_token(
        user_id=str(user.id),
        role=user.role or "TRADER",
        secret=settings.jwt_secret_key,
        expires_minutes=settings.jwt_access_token_expire_minutes,
    )

    return LoginResponse(
        access_token=access_token,
        user=UserInfo(
            id=str(user.id),
            username=user.username,
            role=user.role or "TRADER",
        ),
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_pg_session),
) -> RegisterResponse:
    """用户注册，校验用户名唯一性和密码强度。"""
    # 密码强度校验
    pwd_errors = validate_password_strength(body.password)
    if pwd_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "密码强度不足", "errors": pwd_errors},
        )

    # 用户名唯一性校验
    result = await db.execute(
        select(AppUser).where(AppUser.username == body.username)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已被占用",
        )

    # 创建用户
    password_hash = PasswordHasher.hash_password(body.password)
    new_user = AppUser(
        username=body.username,
        password_hash=password_hash,
        role="TRADER",
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    return RegisterResponse(
        id=str(new_user.id),
        username=new_user.username,
        role=new_user.role or "TRADER",
    )


@router.get("/check-username", response_model=CheckUsernameResponse)
async def check_username(
    username: str = Query(..., min_length=1, max_length=50),
    db: AsyncSession = Depends(get_pg_session),
) -> CheckUsernameResponse:
    """实时校验用户名是否可用。"""
    result = await db.execute(
        select(AppUser).where(AppUser.username == username)
    )
    exists = result.scalar_one_or_none() is not None

    if exists:
        return CheckUsernameResponse(available=False, message="用户名已被占用")
    return CheckUsernameResponse(available=True, message="用户名可用")


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: AppUser = Depends(get_current_user),
) -> MeResponse:
    """获取当前登录用户信息。"""
    return MeResponse(
        id=str(current_user.id),
        username=current_user.username,
        role=current_user.role or "TRADER",
        is_active=current_user.is_active,
    )
