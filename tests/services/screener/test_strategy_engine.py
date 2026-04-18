"""
多因子策略引擎单元测试

覆盖：
- FactorEvaluator: 单因子条件评估
- StrategyEngine: AND/OR 逻辑运算 + 权重评分
- StrategyTemplateManager: CRUD + 上限约束 + 导入导出 + 一键切换
"""

from __future__ import annotations

import json

import pytest

from app.core.schemas import FactorCondition, StrategyConfig
from app.services.screener.strategy_engine import (
    MAX_STRATEGIES_PER_USER,
    FactorEvaluator,
    FactorEvalResult,
    StrategyEngine,
    StrategyEvalResult,
    StrategyTemplate,
    StrategyTemplateManager,
)


# ---------------------------------------------------------------------------
# FactorEvaluator 测试
# ---------------------------------------------------------------------------

class TestFactorEvaluator:
    """测试单因子条件评估"""

    def test_numeric_greater_than_pass(self):
        """数值因子 > 阈值 → 通过"""
        cond = FactorCondition(factor_name="ma_trend", operator=">", threshold=80.0)
        result = FactorEvaluator.evaluate(cond, {"ma_trend": 85.0})
        assert result.passed is True
        assert result.value == 85.0

    def test_numeric_greater_than_fail(self):
        """数值因子 <= 阈值 → 不通过"""
        cond = FactorCondition(factor_name="ma_trend", operator=">", threshold=80.0)
        result = FactorEvaluator.evaluate(cond, {"ma_trend": 75.0})
        assert result.passed is False

    def test_numeric_less_than(self):
        # pe is INDUSTRY_RELATIVE in FACTOR_REGISTRY → reads pe_ind_rel
        cond = FactorCondition(factor_name="pe", operator="<", threshold=30.0)
        assert FactorEvaluator.evaluate(cond, {"pe_ind_rel": 25.0}).passed is True
        assert FactorEvaluator.evaluate(cond, {"pe_ind_rel": 35.0}).passed is False

    def test_numeric_gte(self):
        # rsi is RANGE in FACTOR_REGISTRY → use threshold_type override to test as ABSOLUTE
        cond = FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                               params={"threshold_type": "absolute"})
        assert FactorEvaluator.evaluate(cond, {"rsi": 50.0}).passed is True
        assert FactorEvaluator.evaluate(cond, {"rsi": 49.9}).passed is False

    def test_numeric_lte(self):
        # pe is INDUSTRY_RELATIVE → reads pe_ind_rel
        cond = FactorCondition(factor_name="pe", operator="<=", threshold=30.0)
        assert FactorEvaluator.evaluate(cond, {"pe_ind_rel": 30.0}).passed is True
        assert FactorEvaluator.evaluate(cond, {"pe_ind_rel": 30.1}).passed is False

    def test_numeric_equal(self):
        cond = FactorCondition(factor_name="sector_rank", operator="==", threshold=1.0)
        assert FactorEvaluator.evaluate(cond, {"sector_rank": 1.0}).passed is True
        assert FactorEvaluator.evaluate(cond, {"sector_rank": 2.0}).passed is False

    def test_boolean_factor_true(self):
        """布尔型因子（threshold=None），值为 True → 通过"""
        cond = FactorCondition(factor_name="macd", operator="==", threshold=None)
        result = FactorEvaluator.evaluate(cond, {"macd": True})
        assert result.passed is True
        assert result.value == 1.0

    def test_boolean_factor_false(self):
        """布尔型因子，值为 False → 不通过"""
        cond = FactorCondition(factor_name="macd", operator="==", threshold=None)
        result = FactorEvaluator.evaluate(cond, {"macd": False})
        assert result.passed is False
        assert result.value == 0.0

    def test_missing_factor(self):
        """因子数据缺失 → 不通过"""
        cond = FactorCondition(factor_name="missing", operator=">", threshold=0.0)
        result = FactorEvaluator.evaluate(cond, {"ma_trend": 85.0})
        assert result.passed is False
        assert result.value is None

    def test_unsupported_operator(self):
        """不支持的运算符 → 不通过"""
        cond = FactorCondition(factor_name="rsi", operator="cross_up", threshold=50.0)
        result = FactorEvaluator.evaluate(cond, {"rsi": 65.0})
        assert result.passed is False

    def test_weight_passed_through(self):
        """权重正确传递"""
        cond = FactorCondition(factor_name="rsi", operator=">", threshold=50.0)
        result = FactorEvaluator.evaluate(cond, {"rsi": 65.0}, weight=2.5)
        assert result.weight == 2.5


# ---------------------------------------------------------------------------
# StrategyEngine 测试
# ---------------------------------------------------------------------------

class TestStrategyEngine:
    """测试多因子 AND/OR 逻辑运算"""

    def _make_config(self, logic: str, factors: list[FactorCondition], weights: dict | None = None) -> StrategyConfig:
        return StrategyConfig(
            factors=factors,
            logic=logic,
            weights=weights or {},
        )

    def test_and_all_pass(self):
        """AND 模式：所有因子通过 → 通过"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
            FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                            params={"threshold_type": "absolute"}),
        ])
        result = StrategyEngine.evaluate(config, {"ma_trend": 85.0, "rsi": 65.0})
        assert result.passed is True
        assert result.logic == "AND"

    def test_and_one_fails(self):
        """AND 模式：一个因子不通过 → 不通过"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
            FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                            params={"threshold_type": "absolute"}),
        ])
        result = StrategyEngine.evaluate(config, {"ma_trend": 85.0, "rsi": 40.0})
        assert result.passed is False

    def test_or_one_passes(self):
        """OR 模式：一个因子通过 → 通过"""
        config = self._make_config("OR", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
            FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                            params={"threshold_type": "absolute"}),
        ])
        result = StrategyEngine.evaluate(config, {"ma_trend": 85.0, "rsi": 40.0})
        assert result.passed is True

    def test_or_none_passes(self):
        """OR 模式：所有因子不通过 → 不通过"""
        config = self._make_config("OR", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
            FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                            params={"threshold_type": "absolute"}),
        ])
        result = StrategyEngine.evaluate(config, {"ma_trend": 70.0, "rsi": 40.0})
        assert result.passed is False

    def test_empty_factors(self):
        """空因子列表 → 通过"""
        config = self._make_config("AND", [])
        result = StrategyEngine.evaluate(config, {"ma_trend": 85.0})
        assert result.passed is True

    def test_weighted_score(self):
        """加权得分计算"""
        config = self._make_config(
            "AND",
            [
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
                FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                                params={"threshold_type": "absolute"}),
            ],
            weights={"ma_trend": 2.0, "rsi": 1.0},
        )
        result = StrategyEngine.evaluate(config, {"ma_trend": 90.0, "rsi": 60.0})
        assert result.passed is True
        # weighted_score = (90*2 + 60*1) / (2+1) = 240/3 = 80
        assert result.weighted_score == pytest.approx(80.0)

    def test_four_category_factors(self):
        """四类因子（技术/资金/基本面/板块）自由组合"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),   # 技术 (ABSOLUTE)
            FactorCondition(factor_name="money_flow", operator=">=", threshold=80.0),  # 资金 (PERCENTILE → reads _pctl)
            FactorCondition(factor_name="pe", operator="<=", threshold=1.5),          # 基本面 (INDUSTRY_RELATIVE → reads _ind_rel)
            FactorCondition(factor_name="sector_rank", operator="<=", threshold=30.0), # 板块 (ABSOLUTE)
        ])
        stock = {
            "ma_trend": 85.0,
            "money_flow_pctl": 90.0,
            "pe_ind_rel": 0.8,
            "sector_rank": 10.0,
        }
        result = StrategyEngine.evaluate(config, stock)
        assert result.passed is True
        assert len(result.factor_results) == 4

    def test_screen_stocks(self):
        """批量筛选多只股票"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0),
        ])
        stocks = {
            "000001": {"ma_trend": 90.0},
            "000002": {"ma_trend": 70.0},
            "000003": {"ma_trend": 85.0},
        }
        results = StrategyEngine.screen_stocks(config, stocks)
        symbols = [s for s, _ in results]
        assert "000001" in symbols
        assert "000003" in symbols
        assert "000002" not in symbols
        # 按得分降序
        assert symbols[0] == "000001"

    def test_and_with_boolean_and_numeric(self):
        """AND 模式混合布尔和数值因子"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="macd", operator="==", threshold=None),
            FactorCondition(factor_name="rsi", operator=">=", threshold=50.0,
                            params={"threshold_type": "absolute"}),
        ])
        assert StrategyEngine.evaluate(config, {"macd": True, "rsi": 65.0}).passed is True
        assert StrategyEngine.evaluate(config, {"macd": False, "rsi": 65.0}).passed is False


# ---------------------------------------------------------------------------
# StrategyTemplateManager 测试
# ---------------------------------------------------------------------------

class TestStrategyTemplateManager:
    """测试策略模板 CRUD + 上限 + 导入导出 + 切换"""

    def _make_config(self) -> StrategyConfig:
        return StrategyConfig(
            factors=[FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0)],
            logic="AND",
        )

    def test_create_template(self):
        mgr = StrategyTemplateManager()
        t = mgr.create("user1", "策略A", self._make_config())
        assert t.name == "策略A"
        assert t.user_id == "user1"
        assert t.is_active is False
        assert mgr.count("user1") == 1

    def test_list_templates(self):
        mgr = StrategyTemplateManager()
        mgr.create("user1", "策略A", self._make_config())
        mgr.create("user1", "策略B", self._make_config())
        templates = mgr.list_templates("user1")
        assert len(templates) == 2

    def test_get_template(self):
        mgr = StrategyTemplateManager()
        t = mgr.create("user1", "策略A", self._make_config())
        fetched = mgr.get_template("user1", t.template_id)
        assert fetched is not None
        assert fetched.name == "策略A"

    def test_get_nonexistent_template(self):
        mgr = StrategyTemplateManager()
        assert mgr.get_template("user1", "nonexistent") is None

    def test_update_template(self):
        mgr = StrategyTemplateManager()
        t = mgr.create("user1", "策略A", self._make_config())
        new_config = StrategyConfig(
            factors=[FactorCondition(factor_name="rsi", operator=">=", threshold=50.0)],
            logic="OR",
        )
        updated = mgr.update("user1", t.template_id, name="策略A改", config=new_config)
        assert updated.name == "策略A改"
        assert updated.config.logic == "OR"

    def test_update_nonexistent_raises(self):
        mgr = StrategyTemplateManager()
        with pytest.raises(KeyError):
            mgr.update("user1", "nonexistent", name="x")

    def test_delete_template(self):
        mgr = StrategyTemplateManager()
        t = mgr.create("user1", "策略A", self._make_config())
        mgr.delete("user1", t.template_id)
        assert mgr.count("user1") == 0

    def test_delete_nonexistent_raises(self):
        mgr = StrategyTemplateManager()
        with pytest.raises(KeyError):
            mgr.delete("user1", "nonexistent")

    def test_max_strategies_limit(self):
        """单用户最多 20 套策略"""
        mgr = StrategyTemplateManager()
        for i in range(MAX_STRATEGIES_PER_USER):
            mgr.create("user1", f"策略{i}", self._make_config())
        assert mgr.count("user1") == MAX_STRATEGIES_PER_USER

        with pytest.raises(ValueError, match="上限"):
            mgr.create("user1", "超限策略", self._make_config())

    def test_limit_per_user_independent(self):
        """不同用户的策略上限独立"""
        mgr = StrategyTemplateManager()
        for i in range(MAX_STRATEGIES_PER_USER):
            mgr.create("user1", f"策略{i}", self._make_config())
        # user2 不受 user1 影响
        t = mgr.create("user2", "策略0", self._make_config())
        assert t.user_id == "user2"

    def test_export_template(self):
        mgr = StrategyTemplateManager()
        config = self._make_config()
        t = mgr.create("user1", "策略A", config)
        exported = mgr.export_template("user1", t.template_id)
        data = json.loads(exported)
        assert data["name"] == "策略A"
        assert data["config"]["logic"] == "AND"
        assert len(data["config"]["factors"]) == 1

    def test_export_nonexistent_raises(self):
        mgr = StrategyTemplateManager()
        with pytest.raises(KeyError):
            mgr.export_template("user1", "nonexistent")

    def test_import_template(self):
        mgr = StrategyTemplateManager()
        config = self._make_config()
        t = mgr.create("user1", "策略A", config)
        exported = mgr.export_template("user1", t.template_id)

        imported = mgr.import_template("user2", exported)
        assert imported.name == "策略A"
        assert imported.config.logic == "AND"
        assert len(imported.config.factors) == 1

    def test_import_invalid_json_raises(self):
        mgr = StrategyTemplateManager()
        with pytest.raises(ValueError, match="JSON"):
            mgr.import_template("user1", "not valid json{{{")

    def test_serialization_round_trip(self):
        """序列化 round-trip：to_dict → from_dict 应完全等价"""
        from app.core.schemas import (
            BreakoutConfig,
            IndicatorParamsConfig,
            MaTrendConfig,
            VolumePriceConfig,
        )

        config = StrategyConfig(
            factors=[
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=80.0, params={"period": 20}),
                FactorCondition(factor_name="macd", operator="==", threshold=None),
            ],
            logic="OR",
            weights={"ma_trend": 2.0, "macd": 1.0},
            ma_periods=[5, 10, 20, 60],
            indicator_params=IndicatorParamsConfig(rsi_period=14),
            ma_trend=MaTrendConfig(ma_periods=[5, 10, 20]),
            breakout=BreakoutConfig(box_breakout=False),
            volume_price=VolumePriceConfig(turnover_rate_min=5.0),
        )
        d = config.to_dict()
        restored = StrategyConfig.from_dict(d)

        assert restored.logic == config.logic
        assert restored.weights == config.weights
        assert restored.ma_periods == config.ma_periods
        assert restored.indicator_params == config.indicator_params
        assert restored.ma_trend == config.ma_trend
        assert restored.breakout == config.breakout
        assert restored.volume_price == config.volume_price
        assert len(restored.factors) == len(config.factors)
        for orig, rest in zip(config.factors, restored.factors):
            assert rest.factor_name == orig.factor_name
            assert rest.operator == orig.operator
            assert rest.threshold == orig.threshold
            assert rest.params == orig.params

    def test_switch_active(self):
        """一键切换活跃策略"""
        mgr = StrategyTemplateManager()
        t1 = mgr.create("user1", "策略A", self._make_config())
        t2 = mgr.create("user1", "策略B", self._make_config())

        mgr.switch_active("user1", t1.template_id)
        assert mgr.get_template("user1", t1.template_id).is_active is True
        assert mgr.get_template("user1", t2.template_id).is_active is False
        assert mgr.get_active_template("user1").template_id == t1.template_id

        # 切换到 t2
        mgr.switch_active("user1", t2.template_id)
        assert mgr.get_template("user1", t1.template_id).is_active is False
        assert mgr.get_template("user1", t2.template_id).is_active is True
        assert mgr.get_active_template("user1").template_id == t2.template_id

    def test_switch_nonexistent_raises(self):
        mgr = StrategyTemplateManager()
        with pytest.raises(KeyError):
            mgr.switch_active("user1", "nonexistent")

    def test_no_active_template(self):
        """没有活跃策略时返回 None"""
        mgr = StrategyTemplateManager()
        mgr.create("user1", "策略A", self._make_config())
        assert mgr.get_active_template("user1") is None

    def test_delete_then_create_within_limit(self):
        """删除后可以重新创建到上限"""
        mgr = StrategyTemplateManager()
        templates = []
        for i in range(MAX_STRATEGIES_PER_USER):
            templates.append(mgr.create("user1", f"策略{i}", self._make_config()))
        # 删除一个
        mgr.delete("user1", templates[0].template_id)
        assert mgr.count("user1") == MAX_STRATEGIES_PER_USER - 1
        # 可以再创建一个
        mgr.create("user1", "新策略", self._make_config())
        assert mgr.count("user1") == MAX_STRATEGIES_PER_USER
