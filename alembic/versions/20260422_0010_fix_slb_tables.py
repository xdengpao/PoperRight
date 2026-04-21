"""fix slb_len and slb_sec tables - ts_code nullable, unique on trade_date only

Revision ID: 019_slb_fix
Revises: 018_express_fix
Create Date: 2026-04-22 00:10:00+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '019_slb_fix'
down_revision: Union[str, None] = '018_express_fix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # slb_len: ts_code 改为 nullable，唯一约束改为只用 trade_date
    op.alter_column('slb_len', 'ts_code', nullable=True, existing_type=sa.String(10))
    op.drop_constraint('uq_slb_len', 'slb_len', type_='unique')
    op.create_unique_constraint('uq_slb_len', 'slb_len', ['trade_date'])

    # slb_sec: 同上
    op.alter_column('slb_sec', 'ts_code', nullable=True, existing_type=sa.String(10))
    op.drop_constraint('uq_slb_sec', 'slb_sec', type_='unique')
    op.create_unique_constraint('uq_slb_sec', 'slb_sec', ['trade_date'])


def downgrade() -> None:
    op.drop_constraint('uq_slb_sec', 'slb_sec', type_='unique')
    op.create_unique_constraint('uq_slb_sec', 'slb_sec', ['ts_code', 'trade_date'])
    op.alter_column('slb_sec', 'ts_code', nullable=False, existing_type=sa.String(10))

    op.drop_constraint('uq_slb_len', 'slb_len', type_='unique')
    op.create_unique_constraint('uq_slb_len', 'slb_len', ['ts_code', 'trade_date'])
    op.alter_column('slb_len', 'ts_code', nullable=False, existing_type=sa.String(10))
