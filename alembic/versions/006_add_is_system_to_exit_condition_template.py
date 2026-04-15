"""add is_system column to exit_condition_template

Revision ID: 006
Revises: 005
Create Date: 2026-04-02 00:00:00.000000

为 exit_condition_template 表新增 is_system 布尔列，用于区分系统内置模版和用户自定义模版。
同时新增部分唯一索引保证系统模版名称全局唯一，并将现有用户名称唯一索引改为部分索引（仅约束用户自定义模版）。
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 新增 is_system 列，默认 FALSE
    op.execute("""
        ALTER TABLE exit_condition_template
        ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # 2. 删除现有的全量唯一索引（user_id, name），将其替换为部分索引
    op.execute("DROP INDEX IF EXISTS idx_exit_condition_template_user_name")

    # 3. 新增部分唯一索引：仅约束用户自定义模版（is_system = FALSE）的 user_id + name 唯一
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_condition_template_user_name
        ON exit_condition_template (user_id, name)
        WHERE is_system = FALSE
    """)

    # 4. 新增部分唯一索引：保证系统内置模版名称全局唯一（is_system = TRUE）
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_condition_template_system_name
        ON exit_condition_template (name)
        WHERE is_system = TRUE
    """)


def downgrade() -> None:
    # 1. 删除系统模版名称唯一索引
    op.execute("DROP INDEX IF EXISTS idx_exit_condition_template_system_name")

    # 2. 删除部分唯一索引（用户自定义模版）
    op.execute("DROP INDEX IF EXISTS idx_exit_condition_template_user_name")

    # 3. 恢复原始的全量唯一索引（user_id, name）
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_condition_template_user_name
        ON exit_condition_template (user_id, name)
    """)

    # 4. 删除 is_system 列
    op.execute("ALTER TABLE exit_condition_template DROP COLUMN IF EXISTS is_system")
