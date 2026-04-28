"""因子权重优化方案生成器

基于 IC/IR 评估结果生成因子权重调整建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.schemas import DEFAULT_MODULE_WEIGHTS
from app.services.screener.evaluation.factor_metrics import (
    IC_EFFECTIVE_THRESHOLD,
    IC_INEFFECTIVE_THRESHOLD,
    CORRELATION_REDUNDANT_THRESHOLD,
    FactorMetric,
)


@dataclass
class FactorWeightRecommendation:
    """因子权重调整建议。"""
    item_id: str
    factor_name: str
    current_status: str
    action: str
    detail: str
    file_path: str
    code_location: str
    expected_effect: str


@dataclass
class ModuleWeightRecommendation:
    """模块权重调整建议。"""
    current_weights: dict[str, float] = field(default_factory=dict)
    recommended_weights: dict[str, float] = field(default_factory=dict)
    expected_hit_rate_change: float = 0.0
    file_path: str = "app/core/schemas.py"
    code_location: str = "DEFAULT_MODULE_WEIGHTS"


class FactorWeightOptimizer:
    """因子权重优化方案生成器。"""

    def generate(self, factor_metrics: dict[str, Any], score_metrics: dict[str, Any]) -> dict[str, Any]:
        counter = _Counter()
        ineffective: list[FactorWeightRecommendation] = []
        effective: list[FactorWeightRecommendation] = []
        redundant: list[FactorWeightRecommendation] = []

        per_factor: dict[str, FactorMetric] = factor_metrics.get("per_factor", {})

        for fname, fm in per_factor.items():
            if fm.classification == "无效":
                ineffective.append(FactorWeightRecommendation(
                    item_id=counter.next("FW"),
                    factor_name=fname,
                    current_status="无效 (|IC|<0.02)",
                    action="降权至0或从默认策略移除",
                    detail=f"IC均值={fm.ic_mean:.4f}, IR={fm.ir:.2f}",
                    file_path="app/services/screener/factor_registry.py",
                    code_location=f"FACTOR_REGISTRY['{fname}']",
                    expected_effect="减少噪音因子干扰，提升选股精度",
                ))
            elif fm.classification == "有效":
                effective.append(FactorWeightRecommendation(
                    item_id=counter.next("FW"),
                    factor_name=fname,
                    current_status="有效 (|IC|>0.05)",
                    action="在默认策略中提升权重",
                    detail=f"IC均值={fm.ic_mean:.4f}, IR={fm.ir:.2f}, IC正比例={fm.ic_positive_rate:.1f}%",
                    file_path="app/services/screener/strategy_examples.py",
                    code_location=f"策略模板中 {fname} 因子的 weight 配置",
                    expected_effect="增强有效因子的选股贡献",
                ))

        for f1, f2, corr in factor_metrics.get("redundant_pairs", []):
            fm1 = per_factor.get(f1, FactorMetric(factor_name=f1))
            fm2 = per_factor.get(f2, FactorMetric(factor_name=f2))
            keep = f1 if abs(fm1.ic_mean) >= abs(fm2.ic_mean) else f2
            remove = f2 if keep == f1 else f1
            redundant.append(FactorWeightRecommendation(
                item_id=counter.next("FW"),
                factor_name=remove,
                current_status=f"冗余 (与{keep}相关系数={corr:.2f})",
                action=f"合并：保留{keep}，移除{remove}",
                detail=f"{keep} IC={per_factor.get(keep, fm1).ic_mean:.4f}, {remove} IC={per_factor.get(remove, fm2).ic_mean:.4f}",
                file_path="app/services/screener/factor_registry.py",
                code_location=f"FACTOR_REGISTRY['{remove}']",
                expected_effect="减少因子冗余，降低过拟合风险",
            ))

        module_corrs = score_metrics.get("module_correlations", {})
        module_rec = ModuleWeightRecommendation(
            current_weights=dict(DEFAULT_MODULE_WEIGHTS),
            recommended_weights=score_metrics.get("optimal_weights", dict(DEFAULT_MODULE_WEIGHTS)),
        )

        return {
            "ineffective_factors": ineffective,
            "effective_factors": effective,
            "redundant_pairs": redundant,
            "module_weights": module_rec,
        }


class _Counter:
    def __init__(self) -> None:
        self._n = 0

    def next(self, prefix: str) -> str:
        self._n += 1
        return f"IMP-{prefix}-{self._n:03d}"
