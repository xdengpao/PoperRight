"""选股 0 入选因子失败统计测试。"""

from __future__ import annotations

from app.core.schemas import FactorCondition, FactorGroupConfig, StrategyConfig
from app.services.screener.strategy_engine import (
    summarize_factor_condition_stats,
    summarize_factor_failures,
)


def test_summarize_factor_failures_counts_passed_failed_missing():
    config = StrategyConfig(
        factors=[
            FactorCondition("ma_trend", ">=", 80),
            FactorCondition(
                "rsi",
                "BETWEEN",
                None,
                {"threshold_low": 55, "threshold_high": 80},
            ),
        ],
        logic="AND",
    )
    stocks_data = {
        "000001.SZ": {"ma_trend": 90, "rsi": False, "rsi_current": 60},
        "000002.SZ": {"ma_trend": 70, "rsi": True, "rsi_current": 90},
        "000003.SZ": {"rsi": True},
    }

    summary = summarize_factor_failures(config, stocks_data)

    assert summary["ma_trend"] == {"passed": 1, "missing": 1, "failed": 1}
    assert summary["rsi"] == {"passed": 1, "missing": 1, "failed": 1}


def test_summarize_factor_failures_uses_percentile_field_for_money_flow():
    config = StrategyConfig(
        factors=[FactorCondition("money_flow", ">=", 80)],
        logic="AND",
    )
    stocks_data = {
        "000001.SZ": {"money_flow": True, "money_flow_pctl": 90},
        "000002.SZ": {"money_flow": True, "money_flow_pctl": 70},
        "000003.SZ": {"money_flow": True},
    }

    summary = summarize_factor_failures(config, stocks_data)

    assert summary["money_flow"] == {"passed": 1, "missing": 1, "failed": 1}


def test_summarize_factor_condition_stats_keeps_role_and_group():
    config = StrategyConfig(
        factors=[
            FactorCondition("ma_trend", ">=", 75, role="primary", group_id="primary_core"),
            FactorCondition("money_flow", ">=", 80, role="confirmation", group_id="confirmation"),
        ],
        factor_groups=[
            FactorGroupConfig("primary_core", "主条件", "primary", "AND", ["ma_trend"]),
            FactorGroupConfig("confirmation", "确认因子", "confirmation", "OR", ["money_flow"]),
        ],
    )
    stocks_data = {
        "000001.SZ": {"ma_trend": 90, "money_flow_pctl": 95},
        "000002.SZ": {"ma_trend": 70, "money_flow_pctl": 60},
        "000003.SZ": {"ma_trend": 80},
    }

    stats = summarize_factor_condition_stats(config, stocks_data)
    by_name = {stat.factor_name: stat for stat in stats}

    assert by_name["ma_trend"].role == "primary"
    assert by_name["ma_trend"].group_id == "primary_core"
    assert by_name["ma_trend"].passed_count == 2
    assert by_name["money_flow"].role == "confirmation"
    assert by_name["money_flow"].group_id == "confirmation"
    assert by_name["money_flow"].passed_count == 1
    assert by_name["money_flow"].missing_count == 1


def test_summarize_factor_condition_stats_treats_breakout_none_as_failed_not_missing():
    config = StrategyConfig(
        factors=[
            FactorCondition(
                "breakout",
                "==",
                None,
                role="primary",
                group_id="primary_core",
            ),
        ],
        factor_groups=[
            FactorGroupConfig("primary_core", "主条件", "primary", "AND", ["breakout"]),
        ],
    )
    stocks_data = {
        "000001.SZ": {
            "breakout": {"type": "BOX", "is_valid": True},
            "breakout_list": [{"type": "BOX", "is_valid": True}],
        },
        "000002.SZ": {
            "breakout": None,
            "breakout_list": [],
        },
        "000003.SZ": {},
    }

    [stat] = summarize_factor_condition_stats(config, stocks_data)

    assert stat.passed_count == 1
    assert stat.failed_count == 1
    assert stat.missing_count == 1
