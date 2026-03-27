"""
预警推送通道

功能：
- WebSocket 弹窗预警推送（序列化 Alert 为 JSON 并通过 Redis Pub/Sub 发布）
- 站内消息通知存储与查询（内存存储，模拟 DB）

需求 8.1
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime

from app.core.schemas import Alert

logger = logging.getLogger(__name__)


def _serialize_alert(alert: Alert) -> str:
    """将 Alert 序列化为 JSON 字符串，处理不可直接序列化的类型。"""
    data = asdict(alert)
    # datetime → ISO 格式字符串, Enum → value
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif hasattr(value, "value"):
            data[key] = value.value
    return json.dumps(data, ensure_ascii=False)


class AlertChannel:
    """预警推送通道（WebSocket + 站内消息存储）"""

    def __init__(self) -> None:
        # user_id -> list of (alert, read) tuples
        self._notifications: dict[str, list[tuple[Alert, bool]]] = defaultdict(list)
        # user_id -> list of pushed JSON messages (for testing / audit)
        self._ws_history: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # WebSocket 弹窗预警推送
    # ------------------------------------------------------------------

    async def push_websocket_alert(self, user_id: str, alert: Alert) -> str:
        """
        序列化 Alert 为 JSON 并准备 WebSocket 推送消息。

        实际推送通过 Redis Pub/Sub → PubSubRelay → WebSocketManager 完成。
        此方法负责构建消息并发布到 ``alert:{user_id}`` 频道。

        返回序列化后的 JSON 字符串。
        """
        message = _serialize_alert(alert)
        self._ws_history[user_id].append(message)

        # 尝试通过 Redis Pub/Sub 发布（如果 Redis 不可用则仅记录日志）
        try:
            from app.core.redis_client import publish
            await publish(f"alert:{user_id}", message)
            logger.info("WebSocket alert published: user=%s", user_id)
        except Exception:
            logger.warning(
                "Failed to publish WebSocket alert for user=%s, message stored locally",
                user_id,
            )

        return message

    # ------------------------------------------------------------------
    # 站内消息通知存储与查询
    # ------------------------------------------------------------------

    def store_notification(self, user_id: str, alert: Alert) -> int:
        """
        存储站内消息通知。

        返回该通知在用户通知列表中的索引。
        """
        idx = len(self._notifications[user_id])
        self._notifications[user_id].append((alert, False))
        logger.info("Notification stored: user=%s, index=%d", user_id, idx)
        return idx

    def get_notifications(
        self, user_id: str, *, limit: int = 50
    ) -> list[Alert]:
        """
        查询用户站内消息通知，按存储顺序返回最新的 ``limit`` 条。
        """
        entries = self._notifications.get(user_id, [])
        # 返回最新的 limit 条（保持时间顺序：最旧在前）
        recent = entries[-limit:] if len(entries) > limit else entries
        return [alert for alert, _read in recent]

    def get_notifications_with_status(
        self, user_id: str, *, limit: int = 50
    ) -> list[tuple[Alert, bool]]:
        """
        查询用户站内消息通知（含已读状态）。
        """
        entries = self._notifications.get(user_id, [])
        return list(entries[-limit:]) if len(entries) > limit else list(entries)

    def mark_read(self, user_id: str, alert_index: int) -> bool:
        """
        标记指定索引的通知为已读。

        返回 True 表示成功，False 表示索引无效。
        """
        entries = self._notifications.get(user_id, [])
        if 0 <= alert_index < len(entries):
            alert, _old = entries[alert_index]
            entries[alert_index] = (alert, True)
            return True
        return False

    def get_unread_count(self, user_id: str) -> int:
        """返回用户未读通知数量。"""
        entries = self._notifications.get(user_id, [])
        return sum(1 for _, read in entries if not read)

    # ------------------------------------------------------------------
    # 组合方法：推送 + 存储
    # ------------------------------------------------------------------

    async def push_alert(self, user_id: str, alert: Alert) -> None:
        """
        推送预警：同时通过 WebSocket 推送弹窗并存储站内消息。

        对应设计文档 AlertService.push_alert 接口。
        """
        await self.push_websocket_alert(user_id, alert)
        self.store_notification(user_id, alert)
