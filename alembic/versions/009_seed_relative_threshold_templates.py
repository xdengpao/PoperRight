"""seed 2 relative-threshold system exit condition templates

Revision ID: 009
Revises: 008
Create Date: 2026-04-15 00:00:00.000000

插入 2 个包含相对值阈值条件的系统内置平仓条件模版（is_system=TRUE），使用固定系统用户 UUID。
模版 1：买入价比例止损（close < entry_price × 0.95）
模版 2：回撤止损（close < highest_price × 0.90）
使用 ON CONFLICT DO NOTHING 保证幂等性。
"""

import json

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# 2 个相对值阈值系统内置模版定义
# ---------------------------------------------------------------------------

RELATIVE_TEMPLATES = [
    {
        "name": "买入价比例止损",
        "description": "收盘价跌破买入价的95%时触发平仓，适用于基于买入成本的固定比例止损策略",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "close",
                    "operator": "<",
                    "threshold": None,
                    "cross_target": None,
                    "params": {},
                    "threshold_mode": "relative",
                    "base_field": "entry_price",
                    "factor": 0.95,
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "回撤止损",
        "description": "收盘价跌破持仓期间最高价的90%时触发平仓，适用于保护浮盈的回撤止损策略",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "close",
                    "operator": "<",
                    "threshold": None,
                    "cross_target": None,
                    "params": {},
                    "threshold_mode": "relative",
                    "base_field": "highest_price",
                    "factor": 0.90,
                }
            ],
            "logic": "AND",
        },
    },
]


def upgrade() -> None:
    for tpl in RELATIVE_TEMPLATES:
        conditions_json = json.dumps(tpl["exit_conditions"], ensure_ascii=False)
        conditions_escaped = conditions_json.replace("'", "''")
        name_escaped = tpl["name"].replace("'", "''")
        desc_escaped = tpl["description"].replace("'", "''")

        op.execute(f"""
            INSERT INTO exit_condition_template
                (user_id, name, description, exit_conditions, is_system, created_at, updated_at)
            VALUES
                ('{SYSTEM_USER_ID}', '{name_escaped}', '{desc_escaped}',
                 '{conditions_escaped}'::jsonb, TRUE, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    names = [tpl["name"] for tpl in RELATIVE_TEMPLATES]
    name_list = ", ".join(f"'{n}'" for n in names)
    op.execute(
        f"DELETE FROM exit_condition_template WHERE is_system = TRUE AND name IN ({name_list})"
    )
