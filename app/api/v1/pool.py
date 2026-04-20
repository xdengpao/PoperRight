"""
选股池 API

- POST   /pools                      — 创建选股池
- GET    /pools                      — 列出用户所有选股池
- PUT    /pools/{pool_id}            — 重命名选股池
- DELETE /pools/{pool_id}            — 删除选股池
- GET    /pools/{pool_id}/stocks     — 获取选股池内股票列表
- POST   /pools/{pool_id}/stocks     — 批量添加股票到选股池
- DELETE /pools/{pool_id}/stocks     — 批量移除股票
- POST   /pools/{pool_id}/stocks/manual — 手动添加单只股票

对应需求：
- 需求 3：创建和管理自选股池
- 需求 4：从选股结果添加股票到选股池
- 需求 5：选股池内股票管理
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

from app.core.database import get_pg_session
from app.core.redis_client import get_redis
from app.services.pool_manager import PoolManager

pool_router = APIRouter(prefix="/pools", tags=["选股池"])

logger = logging.getLogger(__name__)

# 占位用户 ID（与 screen.py 保持一致，真实认证后替换）
_DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# ValueError 消息 → HTTP 状态码映射
# ---------------------------------------------------------------------------

# 需要返回 409 Conflict 的错误消息
_CONFLICT_MESSAGES = frozenset({
    "选股池名称已存在，请使用其他名称",
    "该股票已在选股池中",
})

# 需要返回 404 Not Found 的错误消息
_NOT_FOUND_MESSAGES = frozenset({
    "选股池不存在",
})


def _map_value_error(exc: ValueError) -> HTTPException:
    """将 PoolManager 抛出的 ValueError 映射为对应的 HTTPException。"""
    msg = str(exc)
    if msg in _CONFLICT_MESSAGES:
        return HTTPException(status_code=409, detail=msg)
    if msg in _NOT_FOUND_MESSAGES:
        return HTTPException(status_code=404, detail=msg)
    # 其余校验错误（名称为空、超长、数量上限、代码格式等）返回 400
    return HTTPException(status_code=400, detail=msg)


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class CreatePoolRequest(BaseModel):
    """创建选股池请求"""
    name: str


class RenamePoolRequest(BaseModel):
    """重命名选股池请求"""
    name: str


class AddStocksRequest(BaseModel):
    """批量添加股票请求"""
    symbols: list[str]


class RemoveStocksRequest(BaseModel):
    """批量移除股票请求"""
    symbols: list[str]


class ManualAddStockRequest(BaseModel):
    """手动添加单只股票请求"""
    symbol: str


# ---------------------------------------------------------------------------
# 5.2 POST /pools — 创建选股池
# ---------------------------------------------------------------------------


@pool_router.post("", status_code=201)
async def create_pool(
    body: CreatePoolRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """创建选股池。"""
    try:
        pool = await PoolManager.create_pool(
            pg_session, _DEFAULT_USER_ID, body.name
        )
    except ValueError as exc:
        raise _map_value_error(exc)

    return {
        "id": str(pool.id),
        "name": pool.name,
        "created_at": pool.created_at.isoformat() if pool.created_at else None,
        "updated_at": pool.updated_at.isoformat() if pool.updated_at else None,
    }


# ---------------------------------------------------------------------------
# 5.3 GET /pools — 列出用户所有选股池
# ---------------------------------------------------------------------------


@pool_router.get("")
async def list_pools(
    pg_session: AsyncSession = Depends(get_pg_session),
) -> list[dict]:
    """列出当前用户所有选股池。"""
    pools = await PoolManager.list_pools(pg_session, _DEFAULT_USER_ID)
    return [
        {
            "id": str(p["id"]),
            "name": p["name"],
            "stock_count": p["stock_count"],
            "created_at": p["created_at"].isoformat() if p["created_at"] else None,
            "updated_at": p["updated_at"].isoformat() if p["updated_at"] else None,
        }
        for p in pools
    ]


# ---------------------------------------------------------------------------
# 5.4 PUT /pools/{pool_id} — 重命名选股池
# ---------------------------------------------------------------------------


@pool_router.put("/{pool_id}")
async def rename_pool(
    pool_id: UUID,
    body: RenamePoolRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """重命名选股池。"""
    try:
        pool = await PoolManager.rename_pool(
            pg_session, _DEFAULT_USER_ID, pool_id, body.name
        )
    except ValueError as exc:
        raise _map_value_error(exc)

    return {
        "id": str(pool.id),
        "name": pool.name,
        "updated_at": pool.updated_at.isoformat() if pool.updated_at else None,
    }


# ---------------------------------------------------------------------------
# 5.5 DELETE /pools/{pool_id} — 删除选股池
# ---------------------------------------------------------------------------


@pool_router.delete("/{pool_id}", status_code=204)
async def delete_pool(
    pool_id: UUID,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> None:
    """删除选股池（CASCADE 自动清理池内股票）。"""
    try:
        await PoolManager.delete_pool(pg_session, _DEFAULT_USER_ID, pool_id)
    except ValueError as exc:
        raise _map_value_error(exc)


# ---------------------------------------------------------------------------
# 5.6 GET /pools/{pool_id}/stocks — 获取选股池内股票列表
# ---------------------------------------------------------------------------


@pool_router.get("/{pool_id}/stocks")
async def get_pool_stocks(
    pool_id: UUID,
    enriched: bool = False,
    pg_session: AsyncSession = Depends(get_pg_session),
    redis: Redis = Depends(get_redis),
) -> list[dict]:
    """获取选股池内股票列表。

    当 enriched=True 时返回富化数据（含买入参考价、趋势评分、风险等级、
    触发信号、选股时间、假突破标记、板块分类）；
    当 enriched=False 时返回基础数据（股票代码、名称、加入时间）。
    """
    try:
        if enriched:
            stocks = await PoolManager.get_enriched_pool_stocks(
                pg_session, redis, _DEFAULT_USER_ID, pool_id
            )
            return stocks
        else:
            stocks = await PoolManager.get_pool_stocks(
                pg_session, _DEFAULT_USER_ID, pool_id
            )
            return [
                {
                    "symbol": s["symbol"],
                    "stock_name": s["stock_name"],
                    "added_at": s["added_at"].isoformat() if s["added_at"] else None,
                }
                for s in stocks
            ]
    except ValueError as exc:
        raise _map_value_error(exc)


# ---------------------------------------------------------------------------
# 5.7 POST /pools/{pool_id}/stocks — 批量添加股票
# ---------------------------------------------------------------------------


@pool_router.post("/{pool_id}/stocks")
async def add_stocks(
    pool_id: UUID,
    body: AddStocksRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """批量添加股票到选股池。"""
    try:
        result = await PoolManager.add_stocks(
            pg_session, _DEFAULT_USER_ID, pool_id, body.symbols
        )
    except ValueError as exc:
        raise _map_value_error(exc)

    return result


# ---------------------------------------------------------------------------
# 5.8 DELETE /pools/{pool_id}/stocks — 批量移除股票
# ---------------------------------------------------------------------------


@pool_router.delete("/{pool_id}/stocks")
async def remove_stocks(
    pool_id: UUID,
    body: RemoveStocksRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """批量移除选股池内的股票。"""
    try:
        removed = await PoolManager.remove_stocks(
            pg_session, _DEFAULT_USER_ID, pool_id, body.symbols
        )
    except ValueError as exc:
        raise _map_value_error(exc)

    return {"removed": removed}


# ---------------------------------------------------------------------------
# 5.9 POST /pools/{pool_id}/stocks/manual — 手动添加单只股票
# ---------------------------------------------------------------------------


@pool_router.post("/{pool_id}/stocks/manual", status_code=201)
async def add_stock_manual(
    pool_id: UUID,
    body: ManualAddStockRequest,
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    """手动添加单只股票到选股池。"""
    try:
        item = await PoolManager.add_stock_manual(
            pg_session, _DEFAULT_USER_ID, pool_id, body.symbol
        )
    except ValueError as exc:
        raise _map_value_error(exc)

    return {
        "symbol": item.symbol,
        "added_at": item.added_at.isoformat() if item.added_at else None,
    }
