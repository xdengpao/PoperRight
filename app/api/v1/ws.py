"""
WebSocket 端点

路由：
  - GET /api/v1/ws/{user_id}?token=<jwt> — 用户专属 WebSocket（需认证）
  - GET /api/v1/ws/market — 公开大盘数据 WebSocket（无需认证）

用户 WebSocket：
  - 认证：从 query param `token` 获取 JWT，验证通过后建立连接
  - 自动订阅用户专属频道（alert:{user_id}、screen:result:{user_id}）
  - 自动接收大盘广播（market:overview）

大盘 WebSocket：
  - 无需认证，公开访问
  - 仅接收大盘广播（market:overview）
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.core.security import JWTManager
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_token(token: str) -> str | None:
    """
    验证 JWT token，返回 user_id（sub 字段）。
    验证失败返回 None。
    使用与 REST 认证相同的 JWTManager 实现。
    """
    payload = JWTManager.verify_token(token, settings.jwt_secret_key)
    if payload is None:
        logger.warning("WebSocket auth failed: invalid or expired token")
        return None
    return payload.get("sub")


@router.websocket("/ws/market")
async def market_websocket_endpoint(websocket: WebSocket) -> None:
    """
    公开大盘数据 WebSocket 端点（无需认证）。

    - 仅订阅大盘广播频道（market:overview）
    - 用于 Dashboard 页面实时刷新大盘数据
    """
    await websocket.accept()

    # 注册为匿名连接，仅接收 market:overview 广播
    await ws_manager.connect_anonymous(websocket, channel="market:overview")

    try:
        # 发送连接成功确认
        await websocket.send_json({
            "type": "connected",
            "channels": ["market:overview"],
        })

        # 保持连接，等待客户端消息或断开
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Market WebSocket client disconnected")
    except Exception:
        logger.exception("Market WebSocket error")
    finally:
        await ws_manager.disconnect_anonymous(websocket, channel="market:overview")


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT 访问令牌"),
) -> None:
    """
    WebSocket 连接端点。

    - 验证 JWT token
    - token 中的 sub 必须与路径参数 user_id 一致
    - 连接成功后持续接收消息（保持连接），直到客户端断开
    """
    # JWT 认证
    token_user_id = _verify_token(token)
    if token_user_id is None or token_user_id != user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(
            "WebSocket auth rejected: path user_id=%s, token sub=%s",
            user_id,
            token_user_id,
        )
        return

    await ws_manager.connect(user_id, websocket)
    try:
        # 发送连接成功确认
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "channels": [
                f"alert:{user_id}",
                f"screen:result:{user_id}",
                "market:overview",
            ],
        })

        # 保持连接，等待客户端消息或断开
        while True:
            # 接收客户端消息（心跳 ping 等），忽略内容
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: user_id=%s", user_id)
    except Exception:
        logger.exception("WebSocket error for user_id=%s", user_id)
    finally:
        await ws_manager.disconnect(user_id, websocket)
