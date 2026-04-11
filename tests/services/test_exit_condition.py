"""Unit tests for ExitCondition and ExitConditionConfig data models.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

import pytest

from app.core.schemas import (
    VALID_INDICATORS,
    VALID_OPERATORS,
    ExitCondition,
    ExitConditionConfig,
)


# ---------------------------------------------------------------------------
# ExitCondition 构造与默认值
# ---------------------------------------------------------------------------


class TestExitConditionConstruction:
    """测试 ExitCondition 的构造和默认值"""

    def test_full_construction(self):
        """所有字段显式赋值"""
        ec = ExitCondition(
            freq="daily",
            indicator="rsi",
            operator=">",
            threshold=80.0,
            cross_target=None,
            params={"period": 14},
        )
        assert ec.freq == "daily"
        assert ec.indicator == "rsi"
        assert ec.operator == ">"
        assert ec.threshold == 80.0
        assert ec.cross_target is None
        assert ec.params == {"period": 14}

    def test_default_values(self):
        """threshold、cross_target、params 使用默认值"""
        ec = ExitCondition(freq="daily", indicator="close", operator=">")
        assert ec.threshold is None
        assert ec.cross_target is None
        assert ec.params == {}

    def test_params_default_is_independent(self):
        """每个实例的 params 默认字典应互相独立"""
        ec1 = ExitCondition(freq="daily", indicator="close", operator=">")
        ec2 = ExitCondition(freq="daily", indicator="close", operator=">")
        ec1.params["period"] = 5
        assert ec2.params == {}


# ---------------------------------------------------------------------------
# ExitCondition 指标名称覆盖
# ---------------------------------------------------------------------------


class TestExitConditionIndicators:
    """测试 ExitCondition 支持所有合法指标名称 (Req 1.2)"""

    @pytest.mark.parametrize("indicator", sorted(VALID_INDICATORS))
    def test_valid_indicator(self, indicator: str):
        ec = ExitCondition(freq="daily", indicator=indicator, operator=">", threshold=0.0)
        assert ec.indicator == indicator


# ---------------------------------------------------------------------------
# ExitCondition 运算符覆盖
# ---------------------------------------------------------------------------


class TestExitConditionOperators:
    """测试 ExitCondition 支持所有合法运算符 (Req 1.3)"""

    @pytest.mark.parametrize("operator", sorted(VALID_OPERATORS))
    def test_valid_operator(self, operator: str):
        ec = ExitCondition(freq="daily", indicator="close", operator=operator)
        assert ec.operator == operator


# ---------------------------------------------------------------------------
# cross_up / cross_down 与 cross_target
# ---------------------------------------------------------------------------


class TestExitConditionCross:
    """测试交叉运算符与 cross_target 的组合 (Req 1.4)"""

    def test_cross_up_with_target(self):
        ec = ExitCondition(
            freq="daily",
            indicator="macd_dif",
            operator="cross_up",
            cross_target="macd_dea",
        )
        assert ec.operator == "cross_up"
        assert ec.cross_target == "macd_dea"
        assert ec.threshold is None

    def test_cross_down_with_target(self):
        ec = ExitCondition(
            freq="daily",
            indicator="macd_dif",
            operator="cross_down",
            cross_target="macd_dea",
        )
        assert ec.operator == "cross_down"
        assert ec.cross_target == "macd_dea"


# ---------------------------------------------------------------------------
# 数值运算符与 threshold
# ---------------------------------------------------------------------------


class TestExitConditionNumeric:
    """测试数值运算符与 threshold 的组合 (Req 1.3)"""

    @pytest.mark.parametrize("op", [">", "<", ">=", "<="])
    def test_numeric_operator_with_threshold(self, op: str):
        ec = ExitCondition(freq="daily", indicator="rsi", operator=op, threshold=50.0)
        assert ec.operator == op
        assert ec.threshold == 50.0
        assert ec.cross_target is None


# ---------------------------------------------------------------------------
# 自定义 params
# ---------------------------------------------------------------------------


class TestExitConditionParams:
    """测试自定义指标参数"""

    def test_ma_period_param(self):
        ec = ExitCondition(
            freq="daily", indicator="ma", operator=">", threshold=100.0,
            params={"period": 10},
        )
        assert ec.params == {"period": 10}

    def test_macd_custom_params(self):
        ec = ExitCondition(
            freq="daily", indicator="macd_dif", operator=">", threshold=0.0,
            params={"fast": 8, "slow": 21, "signal": 5},
        )
        assert ec.params == {"fast": 8, "slow": 21, "signal": 5}


# ---------------------------------------------------------------------------
# ExitConditionConfig 构造与默认值
# ---------------------------------------------------------------------------


class TestExitConditionConfigConstruction:
    """测试 ExitConditionConfig 的构造和默认值 (Req 1.5)"""

    def test_default_logic_is_and(self):
        cfg = ExitConditionConfig()
        assert cfg.logic == "AND"
        assert cfg.conditions == []

    def test_logic_or(self):
        cfg = ExitConditionConfig(logic="OR")
        assert cfg.logic == "OR"

    def test_empty_conditions_list(self):
        cfg = ExitConditionConfig(conditions=[])
        assert cfg.conditions == []
        assert cfg.logic == "AND"

    def test_with_conditions(self):
        conds = [
            ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ExitCondition(freq="minute", indicator="close", operator="<", threshold=10.0),
        ]
        cfg = ExitConditionConfig(conditions=conds, logic="OR")
        assert len(cfg.conditions) == 2
        assert cfg.logic == "OR"


# ---------------------------------------------------------------------------
# ExitCondition to_dict / from_dict 往返
# ---------------------------------------------------------------------------


class TestExitConditionSerialization:
    """测试 ExitCondition 的序列化/反序列化往返"""

    def test_round_trip_numeric(self):
        ec = ExitCondition(
            freq="daily", indicator="rsi", operator=">=", threshold=70.0,
            params={"period": 14},
        )
        d = ec.to_dict()
        restored = ExitCondition.from_dict(d)
        assert restored.freq == ec.freq
        assert restored.indicator == ec.indicator
        assert restored.operator == ec.operator
        assert restored.threshold == ec.threshold
        assert restored.cross_target == ec.cross_target
        assert restored.params == ec.params

    def test_round_trip_cross(self):
        ec = ExitCondition(
            freq="minute", indicator="macd_dif", operator="cross_down",
            cross_target="macd_dea",
        )
        d = ec.to_dict()
        restored = ExitCondition.from_dict(d)
        # 向后兼容："minute" 经 from_dict 映射为 "1min"
        assert restored.freq == "1min"
        assert restored.indicator == ec.indicator
        assert restored.operator == ec.operator
        assert restored.threshold is None
        assert restored.cross_target == ec.cross_target
        assert restored.params == {}

    def test_to_dict_keys(self):
        ec = ExitCondition(freq="daily", indicator="close", operator=">", threshold=5.0)
        d = ec.to_dict()
        assert set(d.keys()) == {"freq", "indicator", "operator", "threshold", "cross_target", "params"}


# ---------------------------------------------------------------------------
# ExitConditionConfig to_dict / from_dict 往返
# ---------------------------------------------------------------------------


class TestExitConditionConfigSerialization:
    """测试 ExitConditionConfig 的序列化/反序列化往返"""

    def test_round_trip_with_conditions(self):
        cfg = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
                ExitCondition(freq="daily", indicator="macd_dif", operator="cross_down", cross_target="macd_dea"),
            ],
            logic="OR",
        )
        d = cfg.to_dict()
        restored = ExitConditionConfig.from_dict(d)
        assert restored.logic == cfg.logic
        assert len(restored.conditions) == len(cfg.conditions)
        for orig, rest in zip(cfg.conditions, restored.conditions):
            assert rest.to_dict() == orig.to_dict()

    def test_round_trip_empty(self):
        cfg = ExitConditionConfig()
        d = cfg.to_dict()
        restored = ExitConditionConfig.from_dict(d)
        assert restored.conditions == []
        assert restored.logic == "AND"

    def test_to_dict_structure(self):
        cfg = ExitConditionConfig(
            conditions=[ExitCondition(freq="daily", indicator="close", operator=">", threshold=1.0)],
            logic="AND",
        )
        d = cfg.to_dict()
        assert set(d.keys()) == {"conditions", "logic"}
        assert isinstance(d["conditions"], list)
        assert len(d["conditions"]) == 1
        assert d["logic"] == "AND"
