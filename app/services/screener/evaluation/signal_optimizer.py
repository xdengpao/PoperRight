"""信号体系优化方案生成器

基于信号有效性评估结果生成参数调整和组合推荐。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.schemas import SignalCategory
from app.services.screener.evaluation.signal_metrics import (
    SignalCombinationMetric,
    SignalMetric,
)


@dataclass
class SignalParamRecommendation:
    """信号参数调整建议。"""
    item_id: str
    signal_category: str
    current_params: dict = field(default_factory=dict)
    recommended_params: dict = field(default_factory=dict)
    expected_hit_rate_change: float = 0.0
    file_path: str = ""
    code_location: str = ""


@dataclass
class SignalCombinationRecommendation:
    """高效信号组合推荐。"""
    categories: list[str] = field(default_factory=list)
    avg_return: float = 0.0
    hit_rate: float = 0.0
    sample_count: int = 0
    suggested_strategy_name: str = ""


class SignalSystemOptimizer:
    """信号体系优化方案生成器。"""

    HIT_RATE_EFFECTIVE = 60.0
    HIT_RATE_INEFFECTIVE = 40.0

    def generate(self, signal_metrics: dict[str, Any]) -> dict[str, Any]:
        per_signal: dict[str, SignalMetric] = signal_metrics.get("per_signal", {})
        combinations: list[SignalCombinationMetric] = signal_metrics.get("combinations", [])

        counter = 0
        effective_signals: list[SignalParamRecommendation] = []
        ineffective_signals: list[SignalParamRecommendation] = []
        param_adjustments: list[SignalParamRecommendation] = []

        signal_file_map = {
            "MA_TREND": ("app/services/screener/ma_trend.py", "score_ma_trend"),
            "MACD": ("app/services/screener/indicators.py", "detect_macd_signal"),
            "BOLL": ("app/services/screener/indicators.py", "detect_boll_signal"),
            "RSI": ("app/services/screener/indicators.py", "detect_rsi_signal"),
            "DMA": ("app/services/screener/indicators.py", "calculate_dma"),
            "BREAKOUT": ("app/services/screener/breakout.py", "detect_box_breakout 等"),
            "CAPITAL_INFLOW": ("app/services/screener/volume_price.py", "check_money_flow_signal"),
            "LARGE_ORDER": ("app/services/screener/volume_price.py", "check_large_order_signal"),
            "MA_SUPPORT": ("app/services/screener/ma_trend.py", "detect_ma_support"),
            "SECTOR_STRONG": ("app/services/screener/sector_strength.py", "filter_by_sector_strength"),
        }

        for cat_name, sm in per_signal.items():
            counter += 1
            file_path, code_loc = signal_file_map.get(cat_name, ("", ""))

            if sm.hit_rate >= self.HIT_RATE_EFFECTIVE:
                effective_signals.append(SignalParamRecommendation(
                    item_id=f"IMP-SIG-{counter:03d}",
                    signal_category=cat_name,
                    expected_hit_rate_change=0.0,
                    file_path="app/services/screener/screen_executor.py",
                    code_location=f"提升 {cat_name} 在趋势评分中的权重贡献",
                ))
            elif sm.hit_rate < self.HIT_RATE_INEFFECTIVE and sm.trigger_count > 20:
                ineffective_signals.append(SignalParamRecommendation(
                    item_id=f"IMP-SIG-{counter:03d}",
                    signal_category=cat_name,
                    current_params={"hit_rate": sm.hit_rate, "trigger_count": sm.trigger_count},
                    file_path=file_path,
                    code_location=code_loc,
                ))

        dual_combos = [c for c in combinations if len(c.categories) == 2]
        triple_combos = [c for c in combinations if len(c.categories) == 3]

        top_dual = sorted(dual_combos, key=lambda c: c.avg_return, reverse=True)[:5]
        top_triple = sorted(triple_combos, key=lambda c: c.avg_return, reverse=True)[:3]

        dual_recs = [
            SignalCombinationRecommendation(
                categories=[c.value for c in combo.categories],
                avg_return=combo.avg_return,
                sample_count=combo.sample_count,
                suggested_strategy_name=f"双信号组合_{'+'.join(c.value for c in combo.categories)}",
            )
            for combo in top_dual
        ]
        triple_recs = [
            SignalCombinationRecommendation(
                categories=[c.value for c in combo.categories],
                avg_return=combo.avg_return,
                sample_count=combo.sample_count,
                suggested_strategy_name=f"三信号组合_{'+'.join(c.value for c in combo.categories)}",
            )
            for combo in top_triple
        ]

        return {
            "effective_signals": effective_signals,
            "ineffective_signals": ineffective_signals,
            "param_adjustments": param_adjustments,
            "top_dual_combinations": dual_recs,
            "top_triple_combinations": triple_recs,
        }
