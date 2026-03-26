"""
用户与审计日志 ORM 模型（PostgreSQL）

对应数据库表：
- app_user：系统用户
- audit_log：操作日志（保留 1 年，需求 17）
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class AppUser(PGBase):
    """系统用户"""

    __tablename__ = "app_user"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str | None] = mapped_column(String(30), nullable=True)     # 'TRADER'|'ADMIN'|'READONLY'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AppUser {self.username} role={self.role}>"


class AuditLog(PGBase):
    """操作日志（BIGSERIAL 主键，保留 1 年）"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_addr: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.id} action={self.action} user={self.user_id}>"
