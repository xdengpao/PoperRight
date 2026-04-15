"""seed 5 system exit condition templates

Revision ID: 007
Revises: 006
Create Date: 2026-04-03 00:00:00.000000

插入 5 个系统内置平仓条件模版（is_system=TRUE），使用固定系统用户 UUID。
使用 ON CONFLICT DO NOTHING 保证幂等性。
"""

import json

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# 5 个系统内置模版定义
# ---------------------------------------------------------------------------

SYSTEM_TEMPLATES = [
    {
        "name": "RSI 超买平仓",
        "description": "当 RSI 指标超过 80 时触发平仓，适用于捕捉超买回调的卖出时机",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "rsi",
                    "operator": ">",
                    "threshold": 80.0,
                    "cross_target": None,
                    "params": {},
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "MACD 死叉平仓",
        "description": "当 MACD 快线（DIF）向下穿越慢线（DEA）时触发平仓，适用于趋势转弱的卖出信号",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "macd_dif",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "macd_dea",
                    "params": {},
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "布林带上轨突破回落",
        "description": "当收盘价从上方向下穿越布林带上轨时触发平仓，适用于价格冲高回落的卖出时机",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "close",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "boll_upper",
                    "params": {},
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "均线空头排列",
        "description": "当 MA5 向下穿越 MA10 且 MA10 向下穿越 MA20 时触发平仓，适用于短中期均线转为空头排列的卖出信号",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "ma",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 5, "cross_period": 10},
                },
                {
                    "freq": "daily",
                    "indicator": "ma",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 10, "cross_period": 20},
                },
            ],
            "logic": "AND",
        },
    },
    {
        "name": "量价背离",
        "description": "当收盘价从上方跌破短期均线（MA5）且 RSI 处于超买区域时触发平仓，适用于高位量价背离的卖出信号",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "daily",
                    "indicator": "close",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 5},
                },
                {
                    "freq": "daily",
                    "indicator": "rsi",
                    "operator": ">",
                    "threshold": 70.0,
                    "cross_target": None,
                    "params": {},
                },
            ],
            "logic": "AND",
        },
    },
]


def upgrade() -> None:
    for tpl in SYSTEM_TEMPLATES:
        # json.dumps with ensure_ascii=False to preserve Chinese characters
        conditions_json = json.dumps(tpl["exit_conditions"], ensure_ascii=False)
        # Escape single quotes in JSON string for SQL safety
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
    op.execute("DELETE FROM exit_condition_template WHERE is_system = TRUE")
