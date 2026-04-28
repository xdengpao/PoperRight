"""
选股池 ORM 模型（PostgreSQL）

对应数据库表：
- stock_pool：选股池元数据（单用户最多 20 个）
- stock_pool_item：选股池条目（联合主键 pool_id + symbol）

需求 3：创建和管理自选股池
需求 6：选股池数据持久化
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class StockPool(PGBase):
    """选股池（单用户最多 20 个）"""

    __tablename__ = "stock_pool"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_stock_pool_user_name"),
    )

    def __repr__(self) -> str:
        return f"<StockPool {self.id} name={self.name} user={self.user_id}>"


class StockPoolItem(PGBase):
    """选股池条目（联合主键 pool_id + symbol，ON DELETE CASCADE）"""

    __tablename__ = "stock_pool_item"

    pool_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stock_pool.id", ondelete="CASCADE"),
        primary_key=True,
    )
    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<StockPoolItem pool={self.pool_id} symbol={self.symbol}>"
