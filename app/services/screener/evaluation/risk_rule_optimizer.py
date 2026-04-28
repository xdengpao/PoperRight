"""风控规则优化方案生成器

基于风控有效性评估结果生成阈值调整建议。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.screener.evaluation.score_metrics import RiskFilterMetric


@dataclass
class RiskRuleRecommendation:
    """风控规则调整建议。"""
    item_id: str
    rule_name: str
    current_threshold: str
    recommended_threshold: str
    expected_additional_stocks: int = 0
    expected_hit_rate_change: float = 0.0
    worst_case_loss: float = 0.0
    priority: int = 0
    file_path: str = "app/services/screener/screen_executor.py"
    code_snippet: str = ""


class RiskRuleOptimizer:
    """风控规则优化方案生成器。"""

    def generate(self, score_metrics: dict[str, Any]) -> list[RiskRuleRecommendation]:
        risk_filters: list[RiskFilterMetric] = score_metrics.get("risk_filters", [])
        counter = 0
        results: list[RiskRuleRecommendation] = []

        threshold_map = {
            "单日涨幅>9%": ("9%", "_apply_risk_filters_pure 方法中 daily_change_pct > 9.0"),
            "3日累计涨幅>20%": ("20%", "_apply_risk_filters_pure 方法中 change_3d > 20.0"),
        }

        for rf in risk_filters:
            counter += 1
            current, location = threshold_map.get(rf.rule_name, (rf.rule_name, ""))

            if rf.is_over_filtering:
                if "涨幅>9%" in rf.rule_name:
                    new_threshold = "9.5% 或取消该规则"
                    snippet = "# 建议将 9.0 调整为 9.5\nif daily_change_pct > 9.5:"
                elif "累计涨幅>20%" in rf.rule_name:
                    new_threshold = "25%"
                    snippet = "# 建议将 20.0 调整为 25.0\nif change_3d > 25.0:"
                else:
                    new_threshold = "放宽"
                    snippet = ""

                results.append(RiskRuleRecommendation(
                    item_id=f"IMP-RR-{counter:03d}",
                    rule_name=rf.rule_name,
                    current_threshold=current,
                    recommended_threshold=new_threshold,
                    expected_additional_stocks=rf.filtered_count,
                    expected_hit_rate_change=rf.filtered_avg_return - rf.retained_avg_return,
                    worst_case_loss=min(rf.filtered_avg_return, 0),
                    priority=counter,
                    file_path="app/services/screener/screen_executor.py",
                    code_snippet=snippet,
                ))
            else:
                results.append(RiskRuleRecommendation(
                    item_id=f"IMP-RR-{counter:03d}",
                    rule_name=rf.rule_name,
                    current_threshold=current,
                    recommended_threshold=f"保持 {current}（过滤有效）",
                    priority=counter + 100,
                    file_path="app/services/screener/screen_executor.py",
                ))

        results.sort(key=lambda r: r.priority)
        return results
