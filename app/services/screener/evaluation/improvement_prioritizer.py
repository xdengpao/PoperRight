"""改进方案汇总与优先级排序

将所有改进建议按预期效果和实施难度排序，分阶段输出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImprovementItem:
    """单条改进建议。"""
    item_id: str
    category: str
    description: str
    expected_effect: str
    difficulty: str
    files: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    phase: int = 1


class ImprovementPrioritizer:
    """改进方案汇总排序。"""

    DIFFICULTY_SCORES = {"低": 0.2, "中": 0.5, "高": 0.8}

    def prioritize(
        self,
        factor_recommendations: dict[str, Any],
        risk_recommendations: list[Any],
        signal_recommendations: dict[str, Any],
        strategy_recommendations: dict[str, Any],
        ref_price_recommendation: Any,
    ) -> dict[str, Any]:
        items: list[ImprovementItem] = []

        for rec in factor_recommendations.get("ineffective_factors", []):
            items.append(ImprovementItem(
                item_id=rec.item_id,
                category="因子权重",
                description=f"降权无效因子 {rec.factor_name}",
                expected_effect="减少噪音干扰",
                difficulty="低",
                files=[rec.file_path],
                phase=1,
            ))

        for rec in factor_recommendations.get("redundant_pairs", []):
            items.append(ImprovementItem(
                item_id=rec.item_id,
                category="因子权重",
                description=f"合并冗余因子 {rec.factor_name}",
                expected_effect="降低过拟合风险",
                difficulty="低",
                files=[rec.file_path],
                phase=1,
            ))

        for rec in risk_recommendations:
            if hasattr(rec, 'item_id'):
                items.append(ImprovementItem(
                    item_id=rec.item_id,
                    category="风控规则",
                    description=f"调整 {rec.rule_name} 阈值: {rec.current_threshold} → {rec.recommended_threshold}",
                    expected_effect=f"预计增加 {rec.expected_additional_stocks} 只选股",
                    difficulty="低",
                    files=[rec.file_path],
                    phase=1,
                ))

        for rec in signal_recommendations.get("ineffective_signals", []):
            items.append(ImprovementItem(
                item_id=rec.item_id,
                category="信号参数",
                description=f"优化低效信号 {rec.signal_category} 参数",
                expected_effect="提升信号命中率",
                difficulty="中",
                files=[rec.file_path],
                phase=2,
            ))

        for rec in strategy_recommendations.get("retire", []):
            items.append(ImprovementItem(
                item_id=rec.item_id,
                category="策略模板",
                description=f"淘汰低效策略 {rec.strategy_name}",
                expected_effect="清理无效策略",
                difficulty="低",
                files=[rec.file_path],
                phase=1,
            ))

        for rec in strategy_recommendations.get("optimize", []):
            items.append(ImprovementItem(
                item_id=rec.item_id,
                category="策略模板",
                description=f"优化策略 {rec.strategy_name} 参数",
                expected_effect="提升策略综合得分",
                difficulty="中",
                files=[rec.file_path],
                phase=2,
            ))

        if hasattr(ref_price_recommendation, 'recommended_method') and ref_price_recommendation.code_snippet:
            items.append(ImprovementItem(
                item_id="IMP-RP-001",
                category="买入参考价",
                description=f"调整参考价计算: {ref_price_recommendation.recommended_method}",
                expected_effect=f"减少偏离度 (当前均值 {ref_price_recommendation.avg_deviation:.1f}%)",
                difficulty="低",
                files=[ref_price_recommendation.file_path],
                phase=1,
            ))

        for item in items:
            diff_score = self.DIFFICULTY_SCORES.get(item.difficulty, 0.5)
            effect_score = 0.7 if item.phase == 1 else 0.5 if item.phase == 2 else 0.3
            item.priority_score = effect_score * 0.6 + (1 - diff_score) * 0.4

        items.sort(key=lambda x: x.priority_score, reverse=True)

        phase_1 = [i for i in items if i.phase == 1]
        phase_2 = [i for i in items if i.phase == 2]
        phase_3 = [i for i in items if i.phase == 3]

        return {
            "items": items,
            "phase_1": phase_1,
            "phase_2": phase_2,
            "phase_3": phase_3,
            "phase_effects": {
                1: {"description": "快速见效：仅改参数/配置，预计 1-2 天"},
                2: {"description": "核心优化：改业务逻辑代码，预计 3-5 天"},
                3: {"description": "深度重构：架构调整，预计 1-2 周"},
            },
        }
