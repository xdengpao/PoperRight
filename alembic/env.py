"""
Alembic 迁移环境（异步模式）

支持双数据库：
- PostgreSQL（业务数据）：使用 DATABASE_URL
- TimescaleDB（行情时序数据）：使用 TIMESCALE_URL

运行方式：
  # 生成迁移脚本
  alembic revision --autogenerate -m "描述"

  # 执行迁移（默认 PostgreSQL）
  alembic upgrade head

  # 执行 TimescaleDB 迁移
  alembic -x db=timescale upgrade head
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

# ---------------------------------------------------------------------------
# Alembic 配置对象
# ---------------------------------------------------------------------------
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# 导入 ORM 元数据（用于 autogenerate）
# ---------------------------------------------------------------------------
# 在此导入所有模型，确保 autogenerate 能检测到表结构变更
# 随着模型增加，在此处添加对应导入
from app.core.database import PGBase, TSBase  # noqa: E402

# ---------------------------------------------------------------------------
# 根据命令行参数选择目标数据库
# ---------------------------------------------------------------------------
_db_target = context.get_x_argument(as_dictionary=True).get("db", "postgres")

if _db_target == "timescale":
    target_metadata = TSBase.metadata
    _db_url = settings.timescale_url
else:
    target_metadata = PGBase.metadata
    _db_url = settings.database_url


# ---------------------------------------------------------------------------
# 离线迁移（不需要真实数据库连接）
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """在离线模式下生成 SQL 脚本，不连接数据库"""
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# 在线迁移（连接真实数据库）
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步方式执行在线迁移"""
    engine = create_async_engine(
        _db_url,
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """在线迁移入口"""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
