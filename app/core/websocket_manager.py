"""
WebSocket 连接管理器

支持：
- 按用户 ID 管理多个 WebSocket 连接
- 按频道管理匿名连接（公开大盘数据等）
- 广播消息到所有连接
- 单播消息到指定用户
- asyncio.Lock 保证线程安全
"""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """管理所有活跃的 WebSocket 连接"""

    def __init__(self) -> None:
        # user_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # channel -> set of anonymous WebSocket connections
        self._anonymous_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """接受并注册一个新的 WebSocket 连接"""
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)
        logger.info("WebSocket connected: user_id=%s", user_id)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """注销并移除一个 WebSocket 连接"""
        async with self._lock:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WebSocket disconnected: user_id=%s", user_id)

    async def connect_anonymous(self, websocket: WebSocket, channel: str) -> None:
        """注册一个匿名 WebSocket 连接到指定频道"""
        async with self._lock:
            self._anonymous_connections[channel].add(websocket)
        logger.info("Anonymous WebSocket connected to channel: %s", channel)

    async def disconnect_anonymous(self, websocket: WebSocket, channel: str) -> None:
        """注销一个匿名 WebSocket 连接"""
        async with self._lock:
            self._anonymous_connections[channel].discard(websocket)
            if not self._anonymous_connections[channel]:
                del self._anonymous_connections[channel]
        logger.info("Anonymous WebSocket disconnected from channel: %s", channel)

    async def send_to_user(self, user_id: str, message: str) -> None:
        """向指定用户的所有连接发送消息（单播）"""
        async with self._lock:
            sockets = set(self._connections.get(user_id, set()))

        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning("Failed to send to user %s, marking connection dead", user_id)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[user_id].discard(ws)
                if not self._connections.get(user_id):
                    self._connections.pop(user_id, None)

    async def broadcast(self, message: str) -> None:
        """向所有已连接的用户广播消息"""
        async with self._lock:
            all_sockets: list[tuple[str, WebSocket]] = [
                (uid, ws)
                for uid, sockets in self._connections.items()
                for ws in sockets
            ]

        dead: list[tuple[str, WebSocket]] = []
        for user_id, ws in all_sockets:
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning("Broadcast failed for user %s, marking connection dead", user_id)
                dead.append((user_id, ws))

        if dead:
            async with self._lock:
                for user_id, ws in dead:
                    self._connections[user_id].discard(ws)
                    if not self._connections.get(user_id):
                        self._connections.pop(user_id, None)

    async def broadcast_to_channel(self, channel: str, message: str) -> None:
        """向指定频道的所有匿名连接广播消息"""
        async with self._lock:
            sockets = set(self._anonymous_connections.get(channel, set()))

        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning("Broadcast to channel %s failed, marking connection dead", channel)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._anonymous_connections[channel].discard(ws)
                if not self._anonymous_connections.get(channel):
                    self._anonymous_connections.pop(channel, None)

    @property
    def active_user_count(self) -> int:
        """当前有活跃连接的用户数"""
        return len(self._connections)

    def is_user_connected(self, user_id: str) -> bool:
        """检查指定用户是否有活跃连接"""
        return bool(self._connections.get(user_id))


# 全局单例
ws_manager = WebSocketManager()
