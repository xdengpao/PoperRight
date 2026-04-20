"""add unique index on strategy_template (user_id, name)

Revision ID: 013
Revises: 012
Create Date: 2026-04-20 00:00:00.000000

策略模板名称在同一用户下应唯一，与 exit_condition_template 表保持一致。
先清理已有重名数据（保留最新的），再创建唯一索引。
"""

from alembic import op


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 清理已有重名数据：同一 user_id 下 name 相同的记录，保留 updated_at 最新的
    op.execute("""
        DELETE FROM strategy_template
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id, name
                           ORDER BY updated_at DESC
                       ) AS rn
                FROM strategy_template
                WHERE name IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)

    # 同一用户下策略名称唯一（与 exit_condition_template 保持一致）
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "ix_strategy_template_user_name "
        "ON strategy_template (user_id, name) "
        "WHERE name IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_strategy_template_user_name")
