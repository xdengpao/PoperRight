"""seed 10 minute-frequency system exit condition templates

Revision ID: 008
Revises: 007
Create Date: 2026-04-10 00:00:00.000000

插入 10 个分钟级系统内置平仓条件模版（is_system=TRUE），使用固定系统用户 UUID。
覆盖 RSI、MACD、布林带、均线、DMA 等指标在 1min/5min/15min/30min/60min 频率下的典型平仓策略。
使用 ON CONFLICT DO NOTHING 保证幂等性。
"""

import json

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# 10 个分钟级系统内置模版定义
# ---------------------------------------------------------------------------

MINUTE_TEMPLATES = [
    {
        "name": "5分钟RSI超买平仓",
        "description": "5分钟RSI超过80时触发平仓，捕捉短线超买回调的卖出时机，适用于日内短线交易",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "5min",
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
        "name": "15分钟MACD死叉平仓",
        "description": "15分钟MACD快线（DIF）向下穿越慢线（DEA）时触发平仓，中短线趋势转弱信号，适用于波段交易",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "15min",
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
        "name": "1分钟价格跌破布林中轨",
        "description": "1分钟收盘价向下穿越布林带中轨时触发平仓，超短线支撑失守信号，适用于高频日内交易",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "1min",
                    "indicator": "close",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "boll_middle",
                    "params": {},
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "30分钟均线空头排列",
        "description": "30分钟级别MA5向下穿越MA10且MA10向下穿越MA20时触发平仓，中线趋势破位信号，适用于中短线持仓管理",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "30min",
                    "indicator": "ma",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 5, "cross_period": 10},
                },
                {
                    "freq": "30min",
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
        "name": "60分钟DMA死叉平仓",
        "description": "60分钟DMA向下穿越AMA时触发平仓，小时级别趋势反转信号，适用于日内波段交易",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "60min",
                    "indicator": "dma",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ama",
                    "params": {},
                }
            ],
            "logic": "AND",
        },
    },
    {
        "name": "5分钟布林上轨突破回落",
        "description": "5分钟收盘价从上方向下穿越布林带上轨时触发平仓，短线冲高回落信号，适用于追涨后的止盈",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "5min",
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
        "name": "15分钟RSI超卖反弹失败",
        "description": "15分钟RSI低于30且收盘价向下穿越MA10时触发平仓，弱势反弹失败信号，适用于抄底失败后的止损",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "15min",
                    "indicator": "rsi",
                    "operator": "<",
                    "threshold": 30.0,
                    "cross_target": None,
                    "params": {},
                },
                {
                    "freq": "15min",
                    "indicator": "close",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 10},
                },
            ],
            "logic": "AND",
        },
    },
    {
        "name": "1分钟放量下跌",
        "description": "1分钟收盘价跌破布林带下轨或成交量超过5日均量3倍时触发平仓（任一条件满足即触发），适用于极端行情下的快速止损",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "1min",
                    "indicator": "close",
                    "operator": "<",
                    "threshold": None,
                    "cross_target": "boll_lower",
                    "params": {},
                },
                {
                    "freq": "1min",
                    "indicator": "volume",
                    "operator": ">",
                    "threshold": None,
                    "cross_target": None,
                    "params": {"ma_volume_period": 5},
                    "threshold_mode": "relative",
                    "base_field": "ma_volume",
                    "factor": 3.0,
                },
            ],
            "logic": "OR",
        },
    },
    {
        "name": "30分钟MACD柱状体缩短",
        "description": "30分钟MACD柱状体转负且RSI仍在高位（大于70）时触发平仓，顶背离信号，适用于高位震荡行情的离场",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "30min",
                    "indicator": "macd_histogram",
                    "operator": "<",
                    "threshold": 0.0,
                    "cross_target": None,
                    "params": {},
                },
                {
                    "freq": "30min",
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
    {
        "name": "60分钟价格跌破MA20",
        "description": "60分钟收盘价向下穿越20周期均线时触发平仓，小时级别支撑失守信号，适用于中线持仓的趋势跟踪止损",
        "exit_conditions": {
            "conditions": [
                {
                    "freq": "60min",
                    "indicator": "close",
                    "operator": "cross_down",
                    "threshold": None,
                    "cross_target": "ma",
                    "params": {"period": 20},
                }
            ],
            "logic": "AND",
        },
    },
]


def upgrade() -> None:
    for tpl in MINUTE_TEMPLATES:
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
    # 仅删除本次新增的 10 个分钟级模版，按名称精确匹配，保留已有的 5 个日K线系统模版
    names = [tpl["name"] for tpl in MINUTE_TEMPLATES]
    name_list = ", ".join(f"'{n}'" for n in names)
    op.execute(
        f"DELETE FROM exit_condition_template WHERE is_system = TRUE AND name IN ({name_list})"
    )
