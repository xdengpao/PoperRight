"""
数据库引擎与 Session 工厂

- pg_engine / AsyncSessionPG：PostgreSQL 业务数据库
- ts_engine / AsyncSessionTS：TimescaleDB 行情时序数据库

使用 SQLAlchemy 2.0 异步 API。
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Literal

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

EngineName = Literal["pg", "ts"]

_engines: dict[tuple[str, int, int], object] = {}
_sessionmakers: dict[tuple[str, int, int], async_sessionmaker[AsyncSession]] = {}


def _loop_key(name: EngineName) -> tuple[str, int, int]:
    """返回当前进程、当前 event loop 对应的数据库资源键。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    return (name, os.getpid(), id(loop))


def _database_url(name: EngineName) -> str:
    return settings.database_url if name == "pg" else settings.timescale_url


def _get_engine(name: EngineName):
    """返回当前进程、当前 event loop 专属 AsyncEngine。

    asyncpg 连接绑定创建它们的 event loop。FastAPI、Celery prefork
    子进程和测试中的多个 loop 不能共享同一个全局 AsyncEngine。
    """
    key = _loop_key(name)
    engine = _engines.get(key)
    if engine is None:
        engine = create_async_engine(
            _database_url(name),
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        _engines[key] = engine
    return engine


def _get_sessionmaker(name: EngineName) -> async_sessionmaker[AsyncSession]:
    key = _loop_key(name)
    maker = _sessionmakers.get(key)
    if maker is None:
        maker = async_sessionmaker(
            bind=_get_engine(name),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        _sessionmakers[key] = maker
    return maker


class _EngineProxy:
    """延迟解析到当前 event loop 的 AsyncEngine，兼容 pg_engine.connect()。"""

    def __init__(self, name: EngineName) -> None:
        self._name = name

    def __getattr__(self, attr: str):
        return getattr(_get_engine(self._name), attr)


class _SessionFactoryProxy:
    """延迟解析到当前 event loop 的 async_sessionmaker。"""

    def __init__(self, name: EngineName) -> None:
        self._name = name

    def __call__(self, *args, **kwargs) -> AsyncSession:
        return _get_sessionmaker(self._name)(*args, **kwargs)


# PostgreSQL 引擎（业务数据）
pg_engine = _EngineProxy("pg")
AsyncSessionPG = _SessionFactoryProxy("pg")

# TimescaleDB 引擎（行情时序数据）
ts_engine = _EngineProxy("ts")
AsyncSessionTS = _SessionFactoryProxy("ts")

# ---------------------------------------------------------------------------
# ORM 基类
# ---------------------------------------------------------------------------


class PGBase(DeclarativeBase):
    """PostgreSQL 业务数据 ORM 基类"""


class TSBase(DeclarativeBase):
    """TimescaleDB 时序数据 ORM 基类"""


# ---------------------------------------------------------------------------
# FastAPI 依赖注入辅助函数
# ---------------------------------------------------------------------------


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 PostgreSQL 异步 Session（用于 FastAPI Depends）"""
    async with AsyncSessionPG() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_ts_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 TimescaleDB 异步 Session（用于 FastAPI Depends）"""
    async with AsyncSessionTS() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# 生命周期管理
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """应用启动时初始化数据库连接（可在 lifespan 中调用）"""
    # 通过 connect 验证连接可用
    async with pg_engine.connect():
        pass
    async with ts_engine.connect():
        pass


async def close_db() -> None:
    """应用关闭时释放数据库连接池"""
    global _engines, _sessionmakers
    current_pid = os.getpid()
    engines = [
        (key, engine)
        for key, engine in _engines.items()
        if key[1] == current_pid
    ]
    for key, engine in engines:
        await engine.dispose()
        _engines.pop(key, None)
        _sessionmakers.pop(key, None)
