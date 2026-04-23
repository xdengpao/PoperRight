from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionPG
from app.core.pubsub_relay import pubsub_relay
from app.core.security import PasswordHasher
from app.models.user import AppUser


async def _ensure_default_admin() -> None:
    """如果不存在默认管理员，则自动创建"""
    async with AsyncSessionPG() as session:
        result = await session.execute(
            select(AppUser).where(AppUser.username == settings.default_admin_username)
        )
        if result.scalar_one_or_none() is None:
            admin = AppUser(
                username=settings.default_admin_username,
                password_hash=PasswordHasher.hash_password(settings.default_admin_password),
                role="ADMIN",
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            print(f"[init] 默认管理员 '{settings.default_admin_username}' 已创建")
        else:
            print(f"[init] 管理员 '{settings.default_admin_username}' 已存在，跳过创建")


async def _cleanup_stale_import_tasks() -> None:
    """清理服务重启后残留的 running 状态导入任务。

    处理流程：
    1. 为每个残留任务设置 Redis 停止信号，让 worker 中正在执行的任务优雅退出
    2. 通过 Celery revoke 撤销尚在队列中或正在执行的任务
    3. 将数据库中 status='running' 的记录标记为 failed
    4. 清理对应的 Redis 并发锁
    """
    from sqlalchemy import update

    from app.models.tushare_import import TushareImportLog

    async with AsyncSessionPG() as session:
        result = await session.execute(
            select(TushareImportLog).where(TushareImportLog.status == "running")
        )
        stale_logs = result.scalars().all()

        if not stale_logs:
            return

        from datetime import datetime
        now = datetime.utcnow()
        stale_ids = [log.id for log in stale_logs]
        stale_api_names = {log.api_name for log in stale_logs}
        # 收集 celery_task_id 用于发送停止信号和 revoke
        stale_task_ids = [
            log.celery_task_id for log in stale_logs if log.celery_task_id
        ]

        # 1. 为每个残留任务设置 Redis 停止信号，worker 的 _check_stop_signal() 会检测到并优雅退出
        try:
            from app.core.redis_client import cache_set
            for task_id in stale_task_ids:
                try:
                    await cache_set(
                        f"tushare:import:stop:{task_id}", "1", ex=3600,
                    )
                except Exception:
                    pass
            if stale_task_ids:
                print(f"[init] 已为 {len(stale_task_ids)} 个残留任务设置停止信号")
        except Exception:
            pass

        # 2. 通过 Celery revoke 撤销任务（terminate=True 会发送 SIGTERM）
        try:
            from app.core.celery_app import celery_app
            for task_id in stale_task_ids:
                try:
                    celery_app.control.revoke(task_id, terminate=True)
                except Exception:
                    pass
            if stale_task_ids:
                print(f"[init] 已 revoke {len(stale_task_ids)} 个 Celery 任务")
        except Exception:
            pass

        # 3. 更新数据库状态
        await session.execute(
            update(TushareImportLog)
            .where(TushareImportLog.id.in_(stale_ids))
            .values(
                status="failed",
                error_message="服务重启，任务中断",
                finished_at=now,
            )
        )
        await session.commit()

    # 4. 清理 Redis 并发锁（独立 try，不影响数据库更新）
    try:
        from app.core.redis_client import cache_delete
        for api_name in stale_api_names:
            try:
                await cache_delete(f"tushare:import:lock:{api_name}")
            except Exception:
                pass
    except Exception:
        pass

    # 5. 清空 Celery 消息队列，防止 worker 重启后拉取到旧任务
    try:
        from app.core.celery_app import celery_app
        celery_app.control.purge()
        print("[init] 已清空 Celery 消息队列")
    except Exception:
        pass

    print(f"[init] 已清理 {len(stale_ids)} 个残留导入任务: {stale_api_names}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源
    await pubsub_relay.start()
    await _ensure_default_admin()
    try:
        await _cleanup_stale_import_tasks()
    except Exception as exc:
        print(f"[init] ⚠ 清理残留导入任务失败（不影响启动）: {exc}")
    yield
    # 关闭时释放资源
    await pubsub_relay.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="A股右侧量化选股系统",
        description="专为A股市场设计的量化右侧交易选股平台",
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # 可信主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.app_allowed_hosts,
    )

    # CORS 中间件（生产环境应限制 origins）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else settings.app_allowed_hosts,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health", tags=["系统"])
    async def health_check():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
