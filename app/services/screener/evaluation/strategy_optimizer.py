"""策略模板优化方案生成器

基于策略对比评估结果生成淘汰、优化和新增建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.screener.evaluation.strategy_metrics import StrategyMetric


@dataclass
class StrategyRecommendation:
    """策略模板调整建议。"""
    item_id: str
    strategy_name: str
    action: str
    current_score: float | None = None
    recommended_changes: dict | None = None
    new_config: dict | None = None
    backtest_before: dict | None = None
    backtest_after: dict | None = None
    file_path: str = "app/services/screener/strategy_examples.py"


@dataclass
class MarketEnvRecommendation:
    """按市场环境的策略推荐。"""
    env_type: str
    top_strategies: list[str] = field(default_factory=list)
    explanation: str = ""


class StrategyTemplateOptimizer:
    """策略模板优化方案生成器。"""

    def generate(
        self,
        strategy_metrics: dict[str, Any],
        signal_metrics: dict[str, Any],
        factor_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        overall: list[StrategyMetric] = strategy_metrics.get("overall", [])
        bottom_20pct: list[str] = strategy_metrics.get("bottom_20pct", [])
        by_env = strategy_metrics.get("by_market_env", [])

        counter = 0
        retire: list[StrategyRecommendation] = []
        optimize: list[StrategyRecommendation] = []

        for sm in overall:
            if sm.strategy_name in bottom_20pct:
                counter += 1
                retire.append(StrategyRecommendation(
                    item_id=f"IMP-ST-{counter:03d}",
                    strategy_name=sm.strategy_name,
                    action="淘汰",
                    current_score=sm.composite_score,
                    backtest_before={
                        "hit_rate": sm.hit_rate,
                        "avg_return": sm.avg_return,
                        "sharpe": sm.sharpe_ratio,
                    },
                ))

        n = len(overall)
        mid_start = int(n * 0.2)
        mid_end = int(n * 0.6)
        for sm in overall[mid_start:mid_end]:
            counter += 1
            optimize.append(StrategyRecommendation(
                item_id=f"IMP-ST-{counter:03d}",
                strategy_name=sm.strategy_name,
                action="优化参数",
                current_score=sm.composite_score,
                recommended_changes={"建议": "基于因子IC调整因子权重和阈值"},
                backtest_before={
                    "hit_rate": sm.hit_rate,
                    "avg_return": sm.avg_return,
                    "sharpe": sm.sharpe_ratio,
                },
            ))

        env_recs: list[MarketEnvRecommendation] = []
        for env_metric in by_env:
            top3 = [m.strategy_name for m in env_metric.strategy_metrics[:3]]
            env_recs.append(MarketEnvRecommendation(
                env_type=env_metric.env_type,
                top_strategies=top3,
                explanation=f"{env_metric.env_type}下表现最优的策略",
            ))

        return {
            "retire": retire,
            "optimize": optimize,
            "new_strategies": [],
            "market_env_recommendations": env_recs,
        }
