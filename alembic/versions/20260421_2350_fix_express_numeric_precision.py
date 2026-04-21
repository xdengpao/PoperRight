"""fix express numeric precision

Revision ID: 018_express_fix
Revises: 014ebc57a2c1
Create Date: 2026-04-21 23:50:00+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '018_express_fix'
down_revision: Union[str, None] = '014ebc57a2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 扩大 express 表的 diluted_eps/yoy_net_profit/bps 精度，避免数值溢出
    op.alter_column('express', 'diluted_eps',
                    type_=sa.Numeric(20, 4), existing_type=sa.Numeric(10, 4))
    op.alter_column('express', 'yoy_net_profit',
                    type_=sa.Numeric(20, 4), existing_type=sa.Numeric(10, 4))
    op.alter_column('express', 'bps',
                    type_=sa.Numeric(20, 4), existing_type=sa.Numeric(10, 4))


def downgrade() -> None:
    op.alter_column('express', 'diluted_eps',
                    type_=sa.Numeric(10, 4), existing_type=sa.Numeric(20, 4))
    op.alter_column('express', 'yoy_net_profit',
                    type_=sa.Numeric(10, 4), existing_type=sa.Numeric(20, 4))
    op.alter_column('express', 'bps',
                    type_=sa.Numeric(10, 4), existing_type=sa.Numeric(20, 4))
