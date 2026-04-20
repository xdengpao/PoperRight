"""
选股参数优化相关数据模型变更单元测试

覆盖任务 1.4：
- VolumePriceConfig to_dict / from_dict 新字段序列化与向后兼容
- MaTrendConfig 默认值 trend_score_threshold = 68
- IndicatorParamsConfig RSI 默认区间 [55, 75]

Requirements: 3.1, 6.6, 10.3
"""

from __future__ import annotations

import pytest

from app.core.schemas import (
    IndicatorParamsConfig,
    MaTrendConfig,
    StrategyConfig,
    VolumePriceConfig,
)


# ---------------------------------------------------------------------------
# VolumePriceConfig 新字段测试
# ---------------------------------------------------------------------------


class TestVolumePriceConfigNewFields:
    """VolumePriceConfig 新增 money_flow_mode / relative_threshold_pct 字段测试"""

    def test_default_money_flow_mode(self):
        """默认资金流模式应为 'relative'（Req 6.6）"""
        cfg = VolumePriceConfig()
        assert cfg.money_flow_mode == "relative"

    def test_default_relative_threshold_pct(self):
        """默认相对阈值百分比应为 5.0（Req 6.6）"""
        cfg = VolumePriceConfig()
        assert cfg.relative_threshold_pct == 5.0

    def test_to_dict_includes_new_fields(self):
        """to_dict 应包含 money_flow_mode 和 relative_threshold_pct（Req 6.6）"""
        cfg = VolumePriceConfig()
        d = cfg.to_dict()
        assert "money_flow_mode" in d
        assert "relative_threshold_pct" in d
        assert d["money_flow_mode"] == "relative"
        assert d["relative_threshold_pct"] == 5.0

    def test_to_dict_custom_values(self):
        """自定义新字段值应正确序列化（Req 6.6）"""
        cfg = VolumePriceConfig(
            money_flow_mode="absolute",
            relative_threshold_pct=8.0,
        )
        d = cfg.to_dict()
        assert d["money_flow_mode"] == "absolute"
        assert d["relative_threshold_pct"] == 8.0

    def test_from_dict_with_new_fields(self):
        """from_dict 应正确解析新字段（Req 6.6）"""
        data = {
            "turnover_rate_min": 3.0,
            "money_flow_mode": "absolute",
            "relative_threshold_pct": 10.0,
        }
        cfg = VolumePriceConfig.from_dict(data)
        assert cfg.money_flow_mode == "absolute"
        assert cfg.relative_threshold_pct == 10.0

    def test_from_dict_legacy_missing_new_fields(self):
        """旧配置缺少新字段时应使用默认值（向后兼容，Req 6.6）"""
        legacy_data = {
            "turnover_rate_min": 3.0,
            "turnover_rate_max": 15.0,
            "main_flow_threshold": 1000.0,
            "main_flow_days": 2,
            "large_order_ratio": 30.0,
            "min_daily_amount": 5000.0,
            "sector_rank_top": 30,
        }
        cfg = VolumePriceConfig.from_dict(legacy_data)
        assert cfg.money_flow_mode == "relative"
        assert cfg.relative_threshold_pct == 5.0
        # 原有字段应正确解析
        assert cfg.turnover_rate_min == 3.0
        assert cfg.main_flow_threshold == 1000.0

    def test_from_dict_empty_dict_uses_defaults(self):
        """from_dict 传入空字典应全部使用默认值（Req 6.6）"""
        cfg = VolumePriceConfig.from_dict({})
        assert cfg.money_flow_mode == "relative"
        assert cfg.relative_threshold_pct == 5.0
        assert cfg.turnover_rate_min == 3.0

    def test_round_trip_with_new_fields(self):
        """to_dict → from_dict 往返应保持新字段等价（Req 6.6）"""
        original = VolumePriceConfig(
            turnover_rate_min=4.0,
            money_flow_mode="absolute",
            relative_threshold_pct=7.5,
        )
        restored = VolumePriceConfig.from_dict(original.to_dict())
        assert restored.money_flow_mode == original.money_flow_mode
        assert restored.relative_threshold_pct == original.relative_threshold_pct
        assert restored.turnover_rate_min == original.turnover_rate_min

    def test_to_dict_preserves_all_fields(self):
        """to_dict 应包含所有字段（新旧字段完整性检查）"""
        cfg = VolumePriceConfig()
        d = cfg.to_dict()
        expected_keys = {
            "turnover_rate_min", "turnover_rate_max",
            "main_flow_threshold", "main_flow_days",
            "large_order_ratio", "min_daily_amount",
            "sector_rank_top",
            "money_flow_mode", "relative_threshold_pct",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# MaTrendConfig 默认值测试
# ---------------------------------------------------------------------------


class TestMaTrendConfigDefaults:
    """MaTrendConfig 默认值测试（需求 10.3）"""

    def test_default_trend_score_threshold(self):
        """默认趋势评分阈值应为 68（Req 10.3）"""
        cfg = MaTrendConfig()
        assert cfg.trend_score_threshold == 68

    def test_to_dict_threshold(self):
        """to_dict 应输出 trend_score_threshold=68（Req 10.3）"""
        cfg = MaTrendConfig()
        d = cfg.to_dict()
        assert d["trend_score_threshold"] == 68

    def test_from_dict_default_threshold(self):
        """from_dict 空字典应使用默认阈值 68（Req 10.3）"""
        cfg = MaTrendConfig.from_dict({})
        assert cfg.trend_score_threshold == 68

    def test_from_dict_custom_threshold(self):
        """from_dict 应正确解析自定义阈值"""
        cfg = MaTrendConfig.from_dict({"trend_score_threshold": 75})
        assert cfg.trend_score_threshold == 75

    def test_from_dict_legacy_missing_threshold(self):
        """旧配置缺少 trend_score_threshold 时应使用默认值 68（Req 10.3）"""
        legacy_data = {
            "ma_periods": [5, 10, 20, 60, 120],
            "slope_threshold": 0.0,
        }
        cfg = MaTrendConfig.from_dict(legacy_data)
        assert cfg.trend_score_threshold == 68
        assert cfg.ma_periods == [5, 10, 20, 60, 120]

    def test_round_trip_threshold(self):
        """to_dict → from_dict 往返应保持阈值一致"""
        original = MaTrendConfig(trend_score_threshold=72)
        restored = MaTrendConfig.from_dict(original.to_dict())
        assert restored.trend_score_threshold == original.trend_score_threshold


# ---------------------------------------------------------------------------
# IndicatorParamsConfig RSI 默认区间测试
# ---------------------------------------------------------------------------


class TestIndicatorParamsConfigRSIDefaults:
    """IndicatorParamsConfig RSI 默认区间测试（需求 3.1）"""

    def test_default_rsi_lower(self):
        """默认 RSI 下限应为 55（Req 3.1）"""
        cfg = IndicatorParamsConfig()
        assert cfg.rsi_lower == 55

    def test_default_rsi_upper(self):
        """默认 RSI 上限应为 75（Req 3.1）"""
        cfg = IndicatorParamsConfig()
        assert cfg.rsi_upper == 75

    def test_to_dict_rsi_bounds(self):
        """to_dict 应输出 rsi_lower=55, rsi_upper=75（Req 3.1）"""
        cfg = IndicatorParamsConfig()
        d = cfg.to_dict()
        assert d["rsi_lower"] == 55
        assert d["rsi_upper"] == 75

    def test_from_dict_default_rsi_bounds(self):
        """from_dict 空字典应使用默认 RSI 区间 [55, 75]（Req 3.1）"""
        cfg = IndicatorParamsConfig.from_dict({})
        assert cfg.rsi_lower == 55
        assert cfg.rsi_upper == 75

    def test_from_dict_custom_rsi_bounds(self):
        """from_dict 应正确解析自定义 RSI 区间"""
        cfg = IndicatorParamsConfig.from_dict({"rsi_lower": 60, "rsi_upper": 70})
        assert cfg.rsi_lower == 60
        assert cfg.rsi_upper == 70

    def test_from_dict_legacy_missing_rsi_bounds(self):
        """旧配置缺少 rsi_lower/rsi_upper 时应使用默认值（Req 3.1）"""
        legacy_data = {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
        }
        cfg = IndicatorParamsConfig.from_dict(legacy_data)
        assert cfg.rsi_lower == 55
        assert cfg.rsi_upper == 75
        assert cfg.macd_fast == 12

    def test_round_trip_rsi_bounds(self):
        """to_dict → from_dict 往返应保持 RSI 区间一致"""
        original = IndicatorParamsConfig(rsi_lower=60, rsi_upper=80)
        restored = IndicatorParamsConfig.from_dict(original.to_dict())
        assert restored.rsi_lower == original.rsi_lower
        assert restored.rsi_upper == original.rsi_upper


# ---------------------------------------------------------------------------
# StrategyConfig 集成测试（新默认值在顶层配置中的传播）
# ---------------------------------------------------------------------------


class TestStrategyConfigParamOptimizationDefaults:
    """StrategyConfig 中参数优化相关默认值的集成测试"""

    def test_strategy_config_default_rsi_bounds(self):
        """StrategyConfig 默认 indicator_params 应使用 RSI [55, 75]（Req 3.1）"""
        cfg = StrategyConfig()
        assert cfg.indicator_params.rsi_lower == 55
        assert cfg.indicator_params.rsi_upper == 75

    def test_strategy_config_default_trend_threshold(self):
        """StrategyConfig 默认 ma_trend 阈值应为 68（Req 10.3）"""
        cfg = StrategyConfig()
        assert cfg.ma_trend.trend_score_threshold == 68

    def test_strategy_config_default_volume_price_mode(self):
        """StrategyConfig 默认 volume_price 应使用 relative 模式（Req 6.6）"""
        cfg = StrategyConfig()
        assert cfg.volume_price.money_flow_mode == "relative"
        assert cfg.volume_price.relative_threshold_pct == 5.0

    def test_strategy_config_from_dict_legacy_propagates_defaults(self):
        """旧配置反序列化后所有新默认值应正确传播"""
        legacy_data = {
            "factors": [
                {"factor_name": "macd", "operator": "=="}
            ],
        }
        cfg = StrategyConfig.from_dict(legacy_data)
        # RSI 默认区间
        assert cfg.indicator_params.rsi_lower == 55
        assert cfg.indicator_params.rsi_upper == 75
        # MA 趋势阈值
        assert cfg.ma_trend.trend_score_threshold == 68
        # 资金流模式
        assert cfg.volume_price.money_flow_mode == "relative"
        assert cfg.volume_price.relative_threshold_pct == 5.0

    def test_strategy_config_round_trip_preserves_new_defaults(self):
        """StrategyConfig to_dict → from_dict 往返应保持所有新默认值"""
        original = StrategyConfig()
        d = original.to_dict()
        restored = StrategyConfig.from_dict(d)

        assert restored.indicator_params.rsi_lower == 55
        assert restored.indicator_params.rsi_upper == 75
        assert restored.ma_trend.trend_score_threshold == 68
        assert restored.volume_price.money_flow_mode == "relative"
        assert restored.volume_price.relative_threshold_pct == 5.0
