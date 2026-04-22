"""fix ths_hot.ts_code nullable and varchar length

Revision ID: 20260422_1100
Revises: 20260422_1050
Create Date: 2026-04-22

ths_hot.ts_code 应为 nullable 且 VARCHAR(20)，与 ORM 模型一致。
Tushare ths_hot 接口有时返回 ts_code 为 NULL 的行。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_1100"
down_revision = "20260422_1050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ths_hot "
        "ALTER COLUMN ts_code TYPE VARCHAR(20), "
        "ALTER COLUMN ts_code DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ths_hot WHERE ts_code IS NULL"
    )
    op.execute(
        "ALTER TABLE ths_hot "
        "ALTER COLUMN ts_code TYPE VARCHAR(10), "
        "ALTER COLUMN ts_code SET NOT NULL"
    )
