"""选股策略引擎逻辑测试（需求 9）

验证 AND/OR 逻辑、加权评分、阈值判断和序列化一致性。
"""

from decimal import Decimal

import pytest

from app.core.schemas import (
    DEFAULT_MODULE_WEIGHTS,
    FactorCondition,
    StrategyConfig,
)
from app.services.screener.screen_executor import ScreenExecutor
from app.services.screener.strategy_engine import FactorEvaluator, StrategyEngine


class TestAndOrLogic:
    """验证 AND/OR 逻辑正确性。"""

    def _make_config(self, logic: str, factors: list[FactorCondition]) -> StrategyConfig:
        return StrategyConfig(factors=factors, logic=logic)

    def test_and_logic_all_must_pass(self):
        """AND 模式：所有因子条件都满足才通过。"""
        config = self._make_config("AND", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=70),
            FactorCondition(factor_name="macd", operator="==", threshold=1),
        ])
        engine = StrategyEngine()
        factor_dict = {"ma_trend": 80, "macd": True}
        passed, score = engine.evaluate(config, factor_dict)
        assert passed is True

        factor_dict_fail = {"ma_trend": 50, "macd": True}
        passed2, _ = engine.evaluate(config, factor_dict_fail)
        assert passed2 is False

    def test_or_logic_any_can_pass(self):
        """OR 模式：任一因子条件满足即通过。"""
        config = self._make_config("OR", [
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=90),
            FactorCondition(factor_name="macd", operator="==", threshold=1),
        ])
        engine = StrategyEngine()
        factor_dict = {"ma_trend": 50, "macd": True}
        passed, _ = engine.evaluate(config, factor_dict)
        assert passed is True


class TestWeightedScore:
    """验证加权评分计算。"""

    def test_weighted_score_basic(self):
        """基本加权求和。"""
        scores = {"factor_editor": 80, "ma_trend": 60}
        weights = {"factor_editor": 0.5, "ma_trend": 0.5}
        result = ScreenExecutor._compute_weighted_score(scores, weights)
        assert abs(result - 70.0) < 0.01

    def test_disabled_module_excluded(self):
        """评分为 0 的模块不计入分母。"""
        scores = {"factor_editor": 80, "ma_trend": 0, "breakout": 60}
        weights = {"factor_editor": 0.3, "ma_trend": 0.25, "breakout": 0.15}
        result = ScreenExecutor._compute_weighted_score(scores, weights)
        expected = (80 * 0.3 + 60 * 0.15) / (0.3 + 0.15)
        assert abs(result - expected) < 0.01

    def test_score_in_range(self):
        """最终评分在 [0, 100] 区间内。"""
        scores = {"factor_editor": 100, "ma_trend": 100, "indicator_params": 100}
        result = ScreenExecutor._compute_weighted_score(scores)
        assert 0 <= result <= 100

    def test_all_zero_returns_zero(self):
        """所有模块评分为 0 时返回 0。"""
        scores = {"factor_editor": 0, "ma_trend": 0}
        result = ScreenExecutor._compute_weighted_score(scores)
        assert result == 0.0


class TestStrategyConfigRoundtrip:
    """验证 StrategyConfig 序列化往返一致性。"""

    def test_roundtrip(self):
        """from_dict(config.to_dict()) 应保持一致。"""
        config = StrategyConfig(
            factors=[
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=70),
                FactorCondition(factor_name="rsi", operator=">=", threshold=55),
            ],
            logic="AND",
        )
        restored = StrategyConfig.from_dict(config.to_dict())
        assert len(restored.factors) == len(config.factors)
        assert restored.logic == config.logic
        assert restored.factors[0].factor_name == config.factors[0].factor_name
