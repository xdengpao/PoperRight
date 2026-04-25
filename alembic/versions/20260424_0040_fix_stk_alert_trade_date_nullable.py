"""stk_alert.trade_date 改为 nullable

Tushare stk_alert 接口返回数据不包含 trade_date 字段。
幂等执行：DROP NOT NULL 在已经 nullable 时不会报错。

Revision ID: 20260424_0040
"""

from alembic import op

revision = "20260424_0040"
down_revision = "20260424_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE stk_alert ALTER COLUMN "trade_date" DROP NOT NULL')


def downgrade() -> None:
    op.execute('ALTER TABLE stk_alert ALTER COLUMN "trade_date" SET NOT NULL')
