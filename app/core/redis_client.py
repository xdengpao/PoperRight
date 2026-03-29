"""
Redis 异步客户端

提供：
- 通用缓存客户端（DB 0）
- Pub/Sub 消息发布辅助函数
- FastAPI 依赖注入辅助函数
"""

from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.config import settings

# ---------------------------------------------------------------------------
# 连接池（全局单例）
# ---------------------------------------------------------------------------
_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


def get_redis_client() -> Redis:
    """返回共享连接池的 Redis 客户端实例"""
    return aioredis.Redis(connection_pool=_get_pool())


# ---------------------------------------------------------------------------
# FastAPI 依赖注入
# ---------------------------------------------------------------------------


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI Depends 用：获取 Redis 客户端，请求结束后自动关闭"""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Pub/Sub 辅助
# ---------------------------------------------------------------------------


async def publish(channel: str, message: str) -> int:
    """向指定频道发布消息，返回接收到消息的订阅者数量"""
    client = get_redis_client()
    try:
        return await client.publish(channel, message)
    finally:
        await client.aclose()


async def get_pubsub() -> PubSub:
    """获取 Pub/Sub 对象（调用方负责关闭）"""
    client = get_redis_client()
    return client.pubsub()


# ---------------------------------------------------------------------------
# 缓存辅助
# ---------------------------------------------------------------------------


async def cache_set(key: str, value: Any, ex: int | None = None) -> None:
    """设置缓存键值，ex 为过期秒数（None 表示永不过期）"""
    client = get_redis_client()
    try:
        await client.set(key, value, ex=ex)
    finally:
        await client.aclose()


async def cache_get(key: str) -> str | None:
    """获取缓存值，不存在时返回 None"""
    client = get_redis_client()
    try:
        return await client.get(key)
    finally:
        await client.aclose()


async def cache_delete(key: str) -> int:
    """删除缓存键，返回删除数量"""
    client = get_redis_client()
    try:
        return await client.delete(key)
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# 生命周期管理
# ---------------------------------------------------------------------------


async def init_redis() -> None:
    """应用启动时验证 Redis 连接（带重试）"""
    for attempt in range(5):
        try:
            client = get_redis_client()
            try:
                await client.ping()
                return
            finally:
                await client.aclose()
        except Exception as e:
            if attempt < 4:
                import asyncio
                await asyncio.sleep(1)
            else:
                raise RuntimeError(f"Redis 连接失败: {e}") from e


async def close_redis() -> None:
    """应用关闭时释放连接池"""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
