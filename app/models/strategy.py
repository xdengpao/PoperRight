"""
策略模板与选股结果 ORM 模型（PostgreSQL）

对应数据库表：
- strategy_template：选股策略模板（单用户最多 20 套）
- screen_result：选股结果
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class StrategyTemplate(PGBase):
    """选股策略模板（单用户最多 20 套）"""

    __tablename__ = "strategy_template"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)             # StrategyConfig 序列化
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    # 注意：CHECK constraint 在 Alembic 迁移脚本中通过 DDL 实现，
    # 应用层也应在创建前校验 COUNT(*) <= 20（需求 7.2）
    __table_args__ = (
        # CHECK constraint 由迁移脚本添加，此处仅作文档说明
        # CheckConstraint(
        #     "(SELECT COUNT(*) FROM strategy_template WHERE user_id = strategy_template.user_id) <= 20",
        #     name="max_strategies"
        # ),
    )

    def __repr__(self) -> str:
        return f"<StrategyTemplate {self.id} name={self.name} user={self.user_id}>"


class ScreenResult(PGBase):
    """选股结果"""

    __tablename__ = "screen_result"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    strategy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("strategy_template.id"),
        nullable=True,
    )
    screen_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    screen_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'EOD'|'REALTIME'
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ref_buy_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)   # 'LOW'|'MEDIUM'|'HIGH'
    signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)          # 触发的信号详情
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScreenResult {self.id} symbol={self.symbol} score={self.trend_score}>"
