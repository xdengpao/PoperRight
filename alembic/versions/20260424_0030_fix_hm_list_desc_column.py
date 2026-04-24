"""修复 hm_list 表列名：desc → description

desc 是 SQL 保留字，ORM 模型使用 description 作为列名。

Revision ID: 20260424_0030
"""

from alembic import op

revision = "20260424_0030"
down_revision = "20260424_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE hm_list RENAME COLUMN "desc" TO "description"')


def downgrade() -> None:
    op.execute('ALTER TABLE hm_list RENAME COLUMN "description" TO "desc"')
