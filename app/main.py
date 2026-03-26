from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.pubsub_relay import pubsub_relay


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源
    await pubsub_relay.start()
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
