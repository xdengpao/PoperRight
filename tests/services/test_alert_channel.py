"""
AlertChannel 单元测试

覆盖：
- push_websocket_alert：序列化 + 消息记录
- store_notification / get_notifications：存储与查询
- get_notifications_with_status：含已读状态查询
- mark_read：标记已读
- get_unread_count：未读计数
- push_alert：组合推送 + 存储
- get_notifications limit 参数
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.core.schemas import Alert, AlertType
from app.services.alert_channel import AlertChannel, _serialize_alert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(
    user_id: str = "u1",
    title: str = "测试预警",
    message: str = "这是一条测试消息",
    symbol: str | None = "600000",
    alert_type: AlertType = AlertType.SCREEN_RESULT,
) -> Alert:
    return Alert(
        user_id=user_id,
        alert_type=alert_type,
        title=title,
        message=message,
        symbol=symbol,
        created_at=datetime(2025, 1, 6, 10, 0, 0),
    )


# ---------------------------------------------------------------------------
# _serialize_alert
# ---------------------------------------------------------------------------

class TestSerializeAlert:

    def test_returns_valid_json(self):
        alert = _make_alert()
        result = _serialize_alert(alert)
        data = json.loads(result)
        assert data["user_id"] == "u1"
        assert data["title"] == "测试预警"

    def test_datetime_serialized_as_iso(self):
        alert = _make_alert()
        result = _serialize_alert(alert)
        data = json.loads(result)
        assert data["created_at"] == "2025-01-06T10:00:00"

    def test_enum_serialized_as_value(self):
        alert = _make_alert(alert_type=AlertType.STOP_LOSS)
        result = _serialize_alert(alert)
        data = json.loads(result)
        assert data["alert_type"] == "STOP_LOSS"

    def test_symbol_none(self):
        alert = _make_alert(symbol=None)
        result = _serialize_alert(alert)
        data = json.loads(result)
        assert data["symbol"] is None


# ---------------------------------------------------------------------------
# push_websocket_alert
# ---------------------------------------------------------------------------

class TestPushWebsocketAlert:

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        channel = AlertChannel()
        alert = _make_alert()
        with patch("app.core.redis_client.publish", new_callable=AsyncMock):
            result = await channel.push_websocket_alert("u1", alert)
        data = json.loads(result)
        assert data["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_records_in_ws_history(self):
        channel = AlertChannel()
        alert = _make_alert()
        with patch("app.core.redis_client.publish", new_callable=AsyncMock):
            await channel.push_websocket_alert("u1", alert)
        assert len(channel._ws_history["u1"]) == 1

    @pytest.mark.asyncio
    async def test_publishes_to_redis(self):
        channel = AlertChannel()
        alert = _make_alert()
        mock_publish = AsyncMock()
        with patch("app.core.redis_client.publish", mock_publish):
            await channel.push_websocket_alert("u1", alert)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "alert:u1"

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        channel = AlertChannel()
        alert = _make_alert()
        with patch(
            "app.core.redis_client.publish",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ):
            result = await channel.push_websocket_alert("u1", alert)
        # Should not raise, message still stored locally
        assert result is not None
        assert len(channel._ws_history["u1"]) == 1


# ---------------------------------------------------------------------------
# store_notification / get_notifications
# ---------------------------------------------------------------------------

class TestNotificationStorage:

    def test_store_returns_index(self):
        channel = AlertChannel()
        idx = channel.store_notification("u1", _make_alert())
        assert idx == 0

    def test_store_increments_index(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert(title="first"))
        idx = channel.store_notification("u1", _make_alert(title="second"))
        assert idx == 1

    def test_get_returns_stored_alerts(self):
        channel = AlertChannel()
        alert = _make_alert()
        channel.store_notification("u1", alert)
        results = channel.get_notifications("u1")
        assert len(results) == 1
        assert results[0].title == alert.title

    def test_get_empty_user(self):
        channel = AlertChannel()
        assert channel.get_notifications("nobody") == []

    def test_get_respects_limit(self):
        channel = AlertChannel()
        for i in range(10):
            channel.store_notification("u1", _make_alert(title=f"alert-{i}"))
        results = channel.get_notifications("u1", limit=3)
        assert len(results) == 3
        # Should return the 3 most recent
        assert results[0].title == "alert-7"
        assert results[2].title == "alert-9"

    def test_get_limit_larger_than_count(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        results = channel.get_notifications("u1", limit=50)
        assert len(results) == 1

    def test_different_users_isolated(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert(user_id="u1"))
        channel.store_notification("u2", _make_alert(user_id="u2"))
        assert len(channel.get_notifications("u1")) == 1
        assert len(channel.get_notifications("u2")) == 1


# ---------------------------------------------------------------------------
# get_notifications_with_status
# ---------------------------------------------------------------------------

class TestNotificationsWithStatus:

    def test_default_unread(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        results = channel.get_notifications_with_status("u1")
        assert len(results) == 1
        _alert, read = results[0]
        assert read is False

    def test_after_mark_read(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        channel.mark_read("u1", 0)
        results = channel.get_notifications_with_status("u1")
        _alert, read = results[0]
        assert read is True


# ---------------------------------------------------------------------------
# mark_read
# ---------------------------------------------------------------------------

class TestMarkRead:

    def test_mark_valid_index(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        assert channel.mark_read("u1", 0) is True

    def test_mark_invalid_index(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        assert channel.mark_read("u1", 5) is False

    def test_mark_negative_index(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        assert channel.mark_read("u1", -1) is False

    def test_mark_empty_user(self):
        channel = AlertChannel()
        assert channel.mark_read("nobody", 0) is False


# ---------------------------------------------------------------------------
# get_unread_count
# ---------------------------------------------------------------------------

class TestUnreadCount:

    def test_all_unread(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        channel.store_notification("u1", _make_alert())
        assert channel.get_unread_count("u1") == 2

    def test_after_mark_read(self):
        channel = AlertChannel()
        channel.store_notification("u1", _make_alert())
        channel.store_notification("u1", _make_alert())
        channel.mark_read("u1", 0)
        assert channel.get_unread_count("u1") == 1

    def test_empty_user(self):
        channel = AlertChannel()
        assert channel.get_unread_count("nobody") == 0


# ---------------------------------------------------------------------------
# push_alert (combo: websocket + store)
# ---------------------------------------------------------------------------

class TestPushAlert:

    @pytest.mark.asyncio
    async def test_stores_and_pushes(self):
        channel = AlertChannel()
        alert = _make_alert()
        with patch("app.core.redis_client.publish", new_callable=AsyncMock):
            await channel.push_alert("u1", alert)
        # Stored as notification
        assert len(channel.get_notifications("u1")) == 1
        # Pushed via WebSocket
        assert len(channel._ws_history["u1"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_push_alerts(self):
        channel = AlertChannel()
        with patch("app.core.redis_client.publish", new_callable=AsyncMock):
            await channel.push_alert("u1", _make_alert(title="a1"))
            await channel.push_alert("u1", _make_alert(title="a2"))
        assert len(channel.get_notifications("u1")) == 2
        assert channel.get_unread_count("u1") == 2
