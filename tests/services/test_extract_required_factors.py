"""
_extract_required_factors 单元测试

覆盖：
- 空 factors 列表返回全部 7 个因子（向后兼容）
- 非空 factors 列表返回对应因子集合
- ma_support 依赖 ma_trend
- 未知因子名称记录 WARNING 并忽略
- 多个因子组合
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from app.core.schemas import (
    BacktestConfig, FactorCondition, StrategyConfig,
)
from app.services.backtest_engine import (
    ALL_FACTORS, FACTOR_TO_COMPUTE, _extract_required_factors,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_with_factors(factor_names: list[str]) -> BacktestConfig:
    """Create a BacktestConfig with the given factor names."""
    factors = [
        FactorCondition(factor_name=name, operator=">=", threshold=0.0)
        for name in factor_names
    ]
    return BacktestConfig(
        strategy_config=StrategyConfig(factors=factors),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )


def _config_empty_factors() -> BacktestConfig:
    """Create a BacktestConfig with an empty factors list."""
    return BacktestConfig(
        strategy_config=StrategyConfig(factors=[]),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )


# ===========================================================================
# 向后兼容：空 factors → 全部 7 个因子
# ===========================================================================


class TestEmptyFactorsBackwardCompat:
    """Req 2.2: 空 factors 列表返回全部因子"""

    def test_empty_factors_returns_all(self):
        config = _config_empty_factors()
        result = _extract_required_factors(config)
        assert result == ALL_FACTORS

    def test_empty_factors_returns_exactly_seven(self):
        config = _config_empty_factors()
        result = _extract_required_factors(config)
        assert len(result) == 7

    def test_all_factors_constant_has_seven_elements(self):
        assert len(ALL_FACTORS) == 7
        assert ALL_FACTORS == {
            "ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout",
        }


# ===========================================================================
# 非空 factors → 仅返回对应因子
# ===========================================================================


class TestNonEmptyFactors:
    """Req 2.1, 2.3: 非空 factors 返回子集"""

    def test_single_factor_macd(self):
        config = _config_with_factors(["macd"])
        result = _extract_required_factors(config)
        assert result == {"macd"}

    def test_single_factor_rsi(self):
        config = _config_with_factors(["rsi"])
        result = _extract_required_factors(config)
        assert result == {"rsi"}

    def test_multiple_factors(self):
        config = _config_with_factors(["macd", "boll", "rsi"])
        result = _extract_required_factors(config)
        assert result == {"macd", "boll", "rsi"}

    def test_result_is_subset_of_all_factors(self):
        config = _config_with_factors(["dma", "breakout"])
        result = _extract_required_factors(config)
        assert result.issubset(ALL_FACTORS)


# ===========================================================================
# ma_support 依赖 ma_trend（Req 2.4）
# ===========================================================================


class TestMaSupportDependency:
    """Req 2.4: ma_support 自动包含 ma_trend"""

    def test_ma_support_includes_ma_trend(self):
        config = _config_with_factors(["ma_support"])
        result = _extract_required_factors(config)
        assert "ma_trend" in result
        assert "ma_support" in result
        assert result == {"ma_trend", "ma_support"}

    def test_ma_trend_alone_does_not_include_ma_support(self):
        config = _config_with_factors(["ma_trend"])
        result = _extract_required_factors(config)
        assert result == {"ma_trend"}
        assert "ma_support" not in result

    def test_both_ma_trend_and_ma_support(self):
        config = _config_with_factors(["ma_trend", "ma_support"])
        result = _extract_required_factors(config)
        assert result == {"ma_trend", "ma_support"}


# ===========================================================================
# 未知因子名称（Req 6.2）
# ===========================================================================


class TestUnknownFactors:
    """Req 6.2: 未知因子记录 WARNING 并忽略"""

    def test_unknown_factor_ignored(self):
        config = _config_with_factors(["unknown_factor"])
        result = _extract_required_factors(config)
        assert result == set()

    def test_unknown_factor_logs_warning(self, caplog):
        config = _config_with_factors(["nonexistent"])
        with caplog.at_level(logging.WARNING):
            _extract_required_factors(config)
        assert any("Unknown factor" in msg for msg in caplog.messages)
        assert any("nonexistent" in msg for msg in caplog.messages)

    def test_mix_known_and_unknown(self, caplog):
        config = _config_with_factors(["macd", "fake_factor", "rsi"])
        with caplog.at_level(logging.WARNING):
            result = _extract_required_factors(config)
        assert result == {"macd", "rsi"}
        assert any("fake_factor" in msg for msg in caplog.messages)


# ===========================================================================
# FACTOR_TO_COMPUTE 映射完整性
# ===========================================================================


class TestFactorToComputeMapping:
    """验证 FACTOR_TO_COMPUTE 映射字典的完整性"""

    def test_all_seven_factors_have_mapping(self):
        for factor in ALL_FACTORS:
            assert factor in FACTOR_TO_COMPUTE

    def test_each_mapping_is_subset_of_all_factors(self):
        for factor, compute_set in FACTOR_TO_COMPUTE.items():
            assert compute_set.issubset(ALL_FACTORS), (
                f"FACTOR_TO_COMPUTE[{factor!r}] contains unknown factors"
            )
