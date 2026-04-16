"""
数据库引擎与 Session 工厂

- pg_engine / AsyncSessionPG：PostgreSQL 业务数据库
- ts_engine / AsyncSessionTS：TimescaleDB 行情时序数据库

使用 SQLAlchemy 2.0 异步 API。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ---------------------------------------------------------------------------
# PostgreSQL 引擎（业务数据）
# ---------------------------------------------------------------------------
pg_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionPG: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=pg_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# TimescaleDB 引擎（行情时序数据）
# ---------------------------------------------------------------------------
ts_engine = create_async_engine(
    settings.timescale_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionTS: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=ts_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

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
    await pg_engine.dispose()
    await ts_engine.dispose()
