"""create exit_condition_template table

Revision ID: 004
Revises: 003
Create Date: 2026-04-01 00:00:00.000000

创建 PostgreSQL 平仓条件模版表 exit_condition_template，
存储用户保存的自定义平仓条件配置模版，支持按用户查询和名称唯一性约束。
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS exit_condition_template (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL,
            name            VARCHAR(100) NOT NULL,
            description     VARCHAR(500),
            exit_conditions JSONB NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # 按 user_id 查询模版列表
    op.execute("CREATE INDEX IF NOT EXISTS idx_exit_condition_template_user_id ON exit_condition_template (user_id)")

    # 同一用户下模版名称唯一
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_condition_template_user_name ON exit_condition_template (user_id, name)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exit_condition_template CASCADE")
