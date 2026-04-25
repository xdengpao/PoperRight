"""修复 hm_list 表列名：desc → description

desc 是 SQL 保留字，ORM 模型使用 description 作为列名。
使用幂等 SQL，避免列已重命名时报错。

Revision ID: 20260424_0030
"""

from alembic import op

revision = "20260424_0030"
down_revision = "20260424_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hm_list' AND column_name = 'desc'
            ) THEN
                ALTER TABLE hm_list RENAME COLUMN "desc" TO "description";
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hm_list' AND column_name = 'description'
            ) THEN
                ALTER TABLE hm_list RENAME COLUMN "description" TO "desc";
            END IF;
        END $$;
    """)
