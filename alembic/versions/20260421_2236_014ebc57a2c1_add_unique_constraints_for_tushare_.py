"""add unique constraints for tushare import dedup

Revision ID: 014ebc57a2c1
Revises: 017
Create Date: 2026-04-21 22:36:41.415462+08:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '014ebc57a2c1'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 Tushare 导入数据表添加唯一约束，防止重复导入产生重复数据。
    # 配合注册表 conflict_columns 使用 ON CONFLICT DO NOTHING 去重。

    op.create_unique_constraint('uq_stock_st', 'stock_st', ['ts_code', 'st_date'])
    op.create_unique_constraint('uq_suspend_info', 'suspend_info', ['ts_code', 'suspend_date'])
    op.create_unique_constraint('uq_dividend', 'dividend', ['ts_code', 'end_date', 'div_proc'])
    op.create_unique_constraint('uq_stock_namechange', 'stock_namechange', ['ts_code', 'start_date'])
    op.create_unique_constraint('uq_hs_constituent', 'hs_constituent', ['ts_code', 'hs_type'])
    op.create_unique_constraint('uq_stk_rewards', 'stk_rewards', ['ts_code', 'ann_date', 'name'])
    op.create_unique_constraint('uq_stk_managers', 'stk_managers', ['ts_code', 'name', 'begin_date'])
    op.create_unique_constraint('uq_stk_holdernumber', 'stk_holdernumber', ['ts_code', 'end_date'])
    op.create_unique_constraint('uq_stk_holdertrade', 'stk_holdertrade', ['ts_code', 'ann_date', 'holder_name'])
    op.create_unique_constraint('uq_stk_account', 'stk_account', ['date'])
    op.create_unique_constraint('uq_margin_target', 'margin_target', ['ts_code', 'mg_type'])
    op.create_unique_constraint('uq_slb_len', 'slb_len', ['ts_code', 'trade_date'])
    op.create_unique_constraint('uq_slb_sec', 'slb_sec', ['ts_code', 'trade_date'])
    op.create_unique_constraint('uq_hm_list', 'hm_list', ['hm_name'])
    op.create_unique_constraint('uq_hm_detail', 'hm_detail', ['trade_date', 'ts_code', 'hm_name'])
    op.create_unique_constraint('uq_dc_hot', 'dc_hot', ['trade_date', 'ts_code'])
    op.create_unique_constraint('uq_ths_hot', 'ths_hot', ['trade_date', 'ts_code'])
    op.create_unique_constraint('uq_kpl_list', 'kpl_list', ['trade_date', 'ts_code'])
    op.create_unique_constraint('uq_moneyflow_ind', 'moneyflow_ind', ['trade_date', 'industry_name', 'data_source'])


def downgrade() -> None:
    op.drop_constraint('uq_moneyflow_ind', 'moneyflow_ind', type_='unique')
    op.drop_constraint('uq_kpl_list', 'kpl_list', type_='unique')
    op.drop_constraint('uq_ths_hot', 'ths_hot', type_='unique')
    op.drop_constraint('uq_dc_hot', 'dc_hot', type_='unique')
    op.drop_constraint('uq_hm_detail', 'hm_detail', type_='unique')
    op.drop_constraint('uq_hm_list', 'hm_list', type_='unique')
    op.drop_constraint('uq_slb_sec', 'slb_sec', type_='unique')
    op.drop_constraint('uq_slb_len', 'slb_len', type_='unique')
    op.drop_constraint('uq_margin_target', 'margin_target', type_='unique')
    op.drop_constraint('uq_stk_account', 'stk_account', type_='unique')
    op.drop_constraint('uq_stk_holdertrade', 'stk_holdertrade', type_='unique')
    op.drop_constraint('uq_stk_holdernumber', 'stk_holdernumber', type_='unique')
    op.drop_constraint('uq_stk_managers', 'stk_managers', type_='unique')
    op.drop_constraint('uq_stk_rewards', 'stk_rewards', type_='unique')
    op.drop_constraint('uq_hs_constituent', 'hs_constituent', type_='unique')
    op.drop_constraint('uq_stock_namechange', 'stock_namechange', type_='unique')
    op.drop_constraint('uq_dividend', 'dividend', type_='unique')
    op.drop_constraint('uq_suspend_info', 'suspend_info', type_='unique')
    op.drop_constraint('uq_stock_st', 'stock_st', type_='unique')
