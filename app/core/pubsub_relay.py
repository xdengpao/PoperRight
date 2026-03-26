"""
Redis Pub/Sub → WebSocket 消息转发服务

频道命名规范：
  alert:{user_id}           - 用户专属预警
  market:overview           - 大盘广播（所有用户）
  screen:result:{user_id}   - 用户专属选股结果

该服务作为 FastAPI 后台任务（lifespan）运行。
"""

import asyncio
import logging

from app.core.redis_client import get_redis_client
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# 广播频道列表（消息转发给所有在线用户）
BROADCAST_CHANNELS = ["market:overview"]

# 用户专属频道前缀（消息转发给对应用户）
USER_CHANNEL_PREFIXES = ["alert:", "screen:result:"]


def _resolve_target(channel: str) -> tuple[str, str | None]:
    """
    解析频道名，返回 (mode, user_id)。
    mode: 'broadcast' | 'unicast'
    user_id: 单播时的目标用户 ID，广播时为 None
    """
    if channel in BROADCAST_CHANNELS:
        return "broadcast", None

    for prefix in USER_CHANNEL_PREFIXES:
        if channel.startswith(prefix):
            user_id = channel[len(prefix):]
            return "unicast", user_id

    # 未知频道默认广播
    return "broadcast", None


async def _relay_loop(channels: list[str]) -> None:
    """订阅指定频道并将消息转发到对应 WebSocket 连接"""
    client = get_redis_client()
    pubsub = client.pubsub()

    try:
        await pubsub.subscribe(*channels)
        logger.info("PubSub relay subscribed to channels: %s", channels)

        async for raw_message in pubsub.listen():
            if raw_message["type"] != "message":
                continue

            channel: str = raw_message["channel"]
            data: str = raw_message["data"]

            mode, user_id = _resolve_target(channel)

            try:
                if mode == "broadcast":
                    await ws_manager.broadcast(data)
                else:
                    if user_id and ws_manager.is_user_connected(user_id):
                        await ws_manager.send_to_user(user_id, data)
            except Exception:
                logger.exception("Error forwarding message from channel %s", channel)

    except asyncio.CancelledError:
        logger.info("PubSub relay task cancelled, unsubscribing...")
        raise
    finally:
        try:
            await pubsub.unsubscribe()
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass


async def _dynamic_relay_loop() -> None:
    """
    动态订阅模式：使用 psubscribe 订阅所有用户专属频道模式，
    同时订阅广播频道。
    """
    client = get_redis_client()
    pubsub = client.pubsub()

    try:
        # 订阅广播频道（精确匹配）
        await pubsub.subscribe(*BROADCAST_CHANNELS)
        # 订阅用户专属频道（模式匹配）
        await pubsub.psubscribe("alert:*", "screen:result:*")
        logger.info("PubSub relay started (dynamic mode)")

        async for raw_message in pubsub.listen():
            msg_type = raw_message["type"]
            if msg_type not in ("message", "pmessage"):
                continue

            channel: str = raw_message.get("channel") or raw_message.get("pattern", "")
            # pmessage 中实际频道在 "channel" 字段
            actual_channel: str = raw_message.get("channel", channel)
            data: str = raw_message["data"]

            mode, user_id = _resolve_target(actual_channel)

            try:
                if mode == "broadcast":
                    await ws_manager.broadcast(data)
                else:
                    if user_id and ws_manager.is_user_connected(user_id):
                        await ws_manager.send_to_user(user_id, data)
            except Exception:
                logger.exception("Error forwarding message from channel %s", actual_channel)

    except asyncio.CancelledError:
        logger.info("PubSub relay task cancelled")
        raise
    finally:
        try:
            await pubsub.punsubscribe()
            await pubsub.unsubscribe()
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass


class PubSubRelay:
    """
    Redis Pub/Sub → WebSocket 转发服务。
    在 FastAPI lifespan 中启动/停止。
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动后台转发任务"""
        if self._task is not None and not self._task.done():
            logger.warning("PubSubRelay already running")
            return
        self._task = asyncio.create_task(
            _dynamic_relay_loop(), name="pubsub-relay"
        )
        logger.info("PubSubRelay started")

    async def stop(self) -> None:
        """停止后台转发任务"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("PubSubRelay stopped")


# 全局单例
pubsub_relay = PubSubRelay()
