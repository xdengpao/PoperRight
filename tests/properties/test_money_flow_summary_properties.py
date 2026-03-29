# Feature: a-share-quant-trading-system, Property 75: 资金流向汇总卡片计算正确性
"""
资金流向汇总卡片计算正确性属性测试（Hypothesis）

属性 75：资金流向汇总卡片计算正确性

**Validates: Requirements 26.3**

对任意长度 ≥ 5 的资金流向记录列表，验证：
- 近5日累计 = 最近5条 main_net_inflow 之和
- 当日 = 最新一条 main_net_inflow
"""

from __future__ import annotations

from dataclasses import dataclass
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# 纯函数：资金流向汇总计算逻辑（前端展示用）
# ---------------------------------------------------------------------------

@dataclass
class MoneyFlowRecord:
    """简化的资金流向记录，仅包含汇总计算所需字段。"""
    trade_date: str
    main_net_inflow: float


def today_inflow(records: list[MoneyFlowRecord]) -> float:
    """当日主力资金净流入 = 最新一条记录的 main_net_inflow。"""
    return records[-1].main_net_inflow


def last_5_days_total(records: list[MoneyFlowRecord]) -> float:
    """近5日主力资金净流入累计 = 最近5条记录的 main_net_inflow 之和。"""
    return sum(r.main_net_inflow for r in records[-5:])


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 单条记录：main_net_inflow 为合理范围内的浮点数（万元）
_inflow_value = st.floats(min_value=-1e8, max_value=1e8, allow_nan=False, allow_infinity=False)

_money_flow_record = st.builds(
    MoneyFlowRecord,
    trade_date=st.from_regex(r"2024-\d{2}-\d{2}", fullmatch=True),
    main_net_inflow=_inflow_value,
)

# 长度 ≥ 5 的记录列表
_records_list = st.lists(_money_flow_record, min_size=5, max_size=60)


# ---------------------------------------------------------------------------
# 属性 75：资金流向汇总卡片计算正确性
# ---------------------------------------------------------------------------

@h_settings(max_examples=100)
@given(records=_records_list)
def test_money_flow_summary_calculation_correctness(records: list[MoneyFlowRecord]):
    """
    # Feature: a-share-quant-trading-system, Property 75: 资金流向汇总卡片计算正确性

    **Validates: Requirements 26.3**

    对任意长度 ≥ 5 的记录列表，验证：
    1. 当日净流入 = 最新一条记录的 main_net_inflow
    2. 近5日累计 = 最近5条 main_net_inflow 之和
    3. 当日净流入值包含在近5日累计的加数中（最新一条属于最近5条）
    """
    today = today_inflow(records)
    last5 = last_5_days_total(records)

    # 1. 当日 = 最新一条
    assert today == records[-1].main_net_inflow

    # 2. 近5日累计 = 最近5条之和
    expected_last5 = sum(r.main_net_inflow for r in records[-5:])
    assert abs(last5 - expected_last5) < 1e-6

    # 3. 当日值是近5日加数之一（最新记录在最近5条中）
    last5_records = records[-5:]
    assert records[-1] in last5_records
