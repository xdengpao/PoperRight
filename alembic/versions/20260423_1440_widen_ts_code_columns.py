"""扩大 ts_code 列宽度：VARCHAR(10) → VARCHAR(20)

北交所特殊代码格式（如 833243!1.BJ）超过 10 个字符，
需要将所有 ts_code VARCHAR(10) 列统一扩大到 VARCHAR(20)。

Revision ID: 20260423_1440
"""

from alembic import op

revision = "20260423_1440"
down_revision = "20260422_1200"
branch_labels = None
depends_on = None

# 所有 ts_code 为 VARCHAR(10) 的表
_TABLES = [
    "block_trade",
    "daily_share",
    "dc_hot",
    "dividend",
    "express",
    "financial_statement",
    "forecast",
    "hm_detail",
    "hs_constituent",
    "kpl_list",
    "limit_list",
    "limit_step",
    "margin_detail",
    "margin_target",
    "new_share",
    "slb_len",
    "slb_sec",
    "stk_factor",
    "stk_holdernumber",
    "stk_holdertrade",
    "stk_limit",
    "stk_managers",
    "stk_rewards",
    "stock_company",
    "stock_namechange",
    "stock_st",
    "suspend_info",
    "ths_limit",
    "top_holders",
    "top_inst",
    "top_list",
    "tushare_money_flow",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "ts_code" TYPE VARCHAR(20)'
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "ts_code" TYPE VARCHAR(10)'
        )
