"""
SectorScreenConfig 与 StrategyConfig 板块筛选配置单元测试

覆盖任务 4.5：
- SectorScreenConfig to_dict / from_dict
- StrategyConfig.from_dict 向后兼容（旧配置缺少 sector_config）
- StrategyConfig.to_dict 包含 sector_config
- StrategyConfig 含 sector_config 的序列化往返

Requirements: 5.1, 13.1, 13.2, 13.3, 13.4
"""

from __future__ import annotations

import pytest

from app.core.schemas import (
    FactorCondition,
    SectorScreenConfig,
    StrategyConfig,
)


# ---------------------------------------------------------------------------
# SectorScreenConfig 测试
# ---------------------------------------------------------------------------


class TestSectorScreenConfig:
    """SectorScreenConfig 数据类测试"""

    def test_default_values(self):
        """默认值应为 DC / CONCEPT / 5 / 30（Req 5.1, 13.2）"""
        cfg = SectorScreenConfig()
        assert cfg.sector_data_source == "DC"
        assert cfg.sector_type == "CONCEPT"
        assert cfg.sector_period == 5
        assert cfg.sector_top_n == 30

    def test_to_dict(self):
        """to_dict 应产出包含全部字段的字典（Req 13.4）"""
        cfg = SectorScreenConfig(
            sector_data_source="TI",
            sector_type="INDUSTRY",
            sector_period=10,
            sector_top_n=20,
        )
        d = cfg.to_dict()
        assert d == {
            "sector_data_source": "TI",
            "sector_type": "INDUSTRY",
            "sector_period": 10,
            "sector_top_n": 20,
        }

    def test_from_dict_full_data(self):
        """from_dict 应正确解析完整数据（Req 13.3）"""
        data = {
            "sector_data_source": "TDX",
            "sector_type": "REGION",
            "sector_period": 3,
            "sector_top_n": 15,
        }
        cfg = SectorScreenConfig.from_dict(data)
        assert cfg.sector_data_source == "TDX"
        assert cfg.sector_type == "REGION"
        assert cfg.sector_period == 3
        assert cfg.sector_top_n == 15

    def test_from_dict_empty_dict_uses_defaults(self):
        """from_dict 传入空字典应使用默认值（Req 13.2）"""
        cfg = SectorScreenConfig.from_dict({})
        assert cfg.sector_data_source == "DC"
        assert cfg.sector_type == "CONCEPT"
        assert cfg.sector_period == 5
        assert cfg.sector_top_n == 30

    def test_to_dict_from_dict_round_trip(self):
        """to_dict → from_dict 往返应保持等价"""
        original = SectorScreenConfig(
            sector_data_source="TI",
            sector_type="STYLE",
            sector_period=20,
            sector_top_n=50,
        )
        restored = SectorScreenConfig.from_dict(original.to_dict())
        assert restored.sector_data_source == original.sector_data_source
        assert restored.sector_type == original.sector_type
        assert restored.sector_period == original.sector_period
        assert restored.sector_top_n == original.sector_top_n


# ---------------------------------------------------------------------------
# StrategyConfig 向后兼容测试
# ---------------------------------------------------------------------------


class TestStrategyConfigSectorCompat:
    """StrategyConfig 板块筛选配置的序列化与向后兼容测试"""

    def test_from_dict_legacy_missing_sector_config(self):
        """旧配置缺少 sector_config 时应使用默认值（Req 13.2）"""
        legacy_data = {
            "factors": [
                {"factor_name": "ma_trend", "operator": ">=", "threshold": 80}
            ],
            "logic": "AND",
            "weights": {"ma_trend": 1.0},
        }
        cfg = StrategyConfig.from_dict(legacy_data)
        assert cfg.sector_config.sector_data_source == "DC"
        assert cfg.sector_config.sector_type == "CONCEPT"
        assert cfg.sector_config.sector_period == 5
        assert cfg.sector_config.sector_top_n == 30

    def test_to_dict_includes_sector_config(self):
        """to_dict 输出应包含 sector_config 键（Req 13.4）"""
        cfg = StrategyConfig()
        d = cfg.to_dict()
        assert "sector_config" in d
        assert d["sector_config"] == {
            "sector_data_source": "DC",
            "sector_type": "CONCEPT",
            "sector_period": 5,
            "sector_top_n": 30,
        }

    def test_to_dict_with_custom_sector_config(self):
        """自定义 sector_config 应正确序列化（Req 13.4）"""
        cfg = StrategyConfig(
            sector_config=SectorScreenConfig(
                sector_data_source="TDX",
                sector_type="INDUSTRY",
                sector_period=10,
                sector_top_n=20,
            )
        )
        d = cfg.to_dict()
        assert d["sector_config"]["sector_data_source"] == "TDX"
        assert d["sector_config"]["sector_type"] == "INDUSTRY"
        assert d["sector_config"]["sector_period"] == 10
        assert d["sector_config"]["sector_top_n"] == 20

    def test_round_trip_with_sector_config(self):
        """StrategyConfig 含 sector_config 的完整往返（Req 5.1, 13.3, 13.4）"""
        original = StrategyConfig(
            factors=[
                FactorCondition(factor_name="sector_rank", operator="<=", threshold=15),
                FactorCondition(factor_name="ma_trend", operator=">=", threshold=70),
            ],
            logic="AND",
            weights={"sector_rank": 0.4, "ma_trend": 0.6},
            sector_config=SectorScreenConfig(
                sector_data_source="TI",
                sector_type="CONCEPT",
                sector_period=3,
                sector_top_n=15,
            ),
        )
        d = original.to_dict()
        restored = StrategyConfig.from_dict(d)

        # sector_config 字段
        assert restored.sector_config.sector_data_source == "TI"
        assert restored.sector_config.sector_type == "CONCEPT"
        assert restored.sector_config.sector_period == 3
        assert restored.sector_config.sector_top_n == 15

        # 其他核心字段
        assert restored.logic == "AND"
        assert len(restored.factors) == 2
        assert restored.factors[0].factor_name == "sector_rank"
        assert restored.factors[0].threshold == 15
        assert restored.weights == {"sector_rank": 0.4, "ma_trend": 0.6}

    def test_from_dict_legacy_missing_all_new_fields(self):
        """极简旧配置（仅 factors）应全部使用默认值（Req 13.1, 13.2）"""
        legacy_data = {
            "factors": [
                {"factor_name": "macd", "operator": "=="}
            ],
        }
        cfg = StrategyConfig.from_dict(legacy_data)

        # sector_config 默认值
        assert cfg.sector_config.sector_data_source == "DC"
        assert cfg.sector_config.sector_type == "CONCEPT"
        assert cfg.sector_config.sector_period == 5
        assert cfg.sector_config.sector_top_n == 30

        # 其他字段默认值
        assert cfg.logic == "AND"
        assert cfg.weights == {}
        assert cfg.ma_periods == [5, 10, 20, 60, 120, 250]

        # indicator_params 默认值
        assert cfg.indicator_params.macd_fast == 12

        # ma_trend 默认值
        assert cfg.ma_trend.trend_score_threshold == 80

        # breakout 默认值
        assert cfg.breakout.volume_ratio_threshold == 1.5

        # volume_price 默认值
        assert cfg.volume_price.turnover_rate_min == 3.0

        # factor 正确解析
        assert len(cfg.factors) == 1
        assert cfg.factors[0].factor_name == "macd"
        assert cfg.factors[0].threshold is None

    def test_from_dict_with_explicit_sector_config(self):
        """from_dict 应正确解析显式 sector_config（Req 13.3）"""
        data = {
            "factors": [],
            "logic": "OR",
            "weights": {},
            "sector_config": {
                "sector_data_source": "TDX",
                "sector_type": "STYLE",
                "sector_period": 60,
                "sector_top_n": 100,
            },
        }
        cfg = StrategyConfig.from_dict(data)
        assert cfg.logic == "OR"
        assert cfg.sector_config.sector_data_source == "TDX"
        assert cfg.sector_config.sector_type == "STYLE"
        assert cfg.sector_config.sector_period == 60
        assert cfg.sector_config.sector_top_n == 100
