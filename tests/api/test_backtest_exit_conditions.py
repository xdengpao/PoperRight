"""
回测自定义平仓条件 API 验证单元测试

直接测试 Pydantic 模型的验证逻辑，无需启动 FastAPI 测试客户端。

Validates: Requirements 5.1, 5.2, 5.3
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.backtest import (
    BacktestRunRequest,
    ExitConditionSchema,
    ExitConditionsSchema,
)


# ---------------------------------------------------------------------------
# 1. 有效的数值运算符条件 → 无错误
# ---------------------------------------------------------------------------


class TestValidExitConditions:
    def test_valid_numeric_operator(self):
        """有效的数值运算符条件不应抛出异常。"""
        cond = ExitConditionSchema(
            indicator="rsi",
            operator=">",
            threshold=80.0,
        )
        assert cond.indicator == "rsi"
        assert cond.operator == ">"
        assert cond.threshold == 80.0

    def test_valid_cross_operator_with_cross_target(self):
        """有效的交叉运算符 + cross_target 不应抛出异常。"""
        cond = ExitConditionSchema(
            indicator="macd_dif",
            operator="cross_down",
            cross_target="macd_dea",
        )
        assert cond.indicator == "macd_dif"
        assert cond.operator == "cross_down"
        assert cond.cross_target == "macd_dea"

    def test_exit_conditions_none_on_request(self):
        """exit_conditions=None 时请求模型不应抛出异常。"""
        req = BacktestRunRequest(
            start_date="2024-01-01",
            end_date="2024-06-30",
            exit_conditions=None,
        )
        assert req.exit_conditions is None

    def test_valid_multiple_conditions(self):
        """多条有效条件不应抛出异常。"""
        schema = ExitConditionsSchema(
            conditions=[
                ExitConditionSchema(indicator="rsi", operator=">", threshold=80.0),
                ExitConditionSchema(indicator="ma", operator="<", threshold=10.0, params={"period": 20}),
                ExitConditionSchema(indicator="macd_dif", operator="cross_down", cross_target="macd_dea"),
            ],
            logic="AND",
        )
        assert len(schema.conditions) == 3

    def test_valid_logic_or(self):
        """logic="OR" 不应抛出异常。"""
        schema = ExitConditionsSchema(
            conditions=[
                ExitConditionSchema(indicator="rsi", operator=">=", threshold=70.0),
                ExitConditionSchema(indicator="close", operator="<=", threshold=50.0),
            ],
            logic="OR",
        )
        assert schema.logic == "OR"


# ---------------------------------------------------------------------------
# 2. 无效条件 → ValidationError
# ---------------------------------------------------------------------------


class TestInvalidExitConditions:
    def test_invalid_indicator_raises_422(self):
        """无效指标名称应抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="invalid_indicator",
                operator=">",
                threshold=80.0,
            )
        assert "无效的指标名称" in str(exc_info.value)

    def test_invalid_operator_raises_422(self):
        """无效运算符应抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="rsi",
                operator="==",
                threshold=80.0,
            )
        assert "无效的比较运算符" in str(exc_info.value)

    def test_cross_up_without_cross_target_raises_422(self):
        """cross_up 缺少 cross_target 应抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="macd_dif",
                operator="cross_up",
            )
        assert "交叉运算符需要指定 cross_target" in str(exc_info.value)

    def test_cross_down_without_cross_target_raises_422(self):
        """cross_down 缺少 cross_target 应抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="macd_dif",
                operator="cross_down",
            )
        assert "交叉运算符需要指定 cross_target" in str(exc_info.value)

    def test_numeric_operator_without_threshold_raises_422(self):
        """数值运算符缺少 threshold 应抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="rsi",
                operator=">",
            )
        assert "数值比较运算符需要指定 threshold" in str(exc_info.value)
