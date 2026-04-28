"""信号有效性计算器

按 10 种信号类别计算命中率、平均收益，分析信号共振效果。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from typing import Any

from app.core.schemas import SignalCategory, SignalFreshness, SignalStrength
from app.services.screener.evaluation.forward_return_calculator import ForwardReturn
from app.services.screener.evaluation.screening_simulator import DailyScreenResult


@dataclass
class SignalMetric:
    """单信号有效性指标。"""
    category: SignalCategory
    hit_rate: float = 0.0
    avg_return: float = 0.0
    trigger_count: int = 0
    exclusive_return: float = 0.0


@dataclass
class SignalCombinationMetric:
    """信号组合指标。"""
    categories: tuple[SignalCategory, ...]
    avg_return: float = 0.0
    sample_count: int = 0


class SignalMetricsCalculator:
    """信号有效性计算器。"""

    EVAL_PERIOD = 5

    def calculate(
        self,
        daily_results: list[DailyScreenResult],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
    ) -> dict[str, Any]:
        """计算信号有效性指标。"""
        # PLACEHOLDER_SIGNAL_CALC_BODY
        per_signal: dict[SignalCategory, list[float]] = defaultdict(list)
        exclusive_returns: dict[SignalCategory, list[float]] = defaultdict(list)
        by_strength: dict[SignalStrength, dict[SignalCategory, list[float]]] = {
            s: defaultdict(list) for s in SignalStrength
        }
        by_freshness: dict[SignalFreshness, dict[SignalCategory, list[float]]] = {
            f: defaultdict(list) for f in SignalFreshness
        }
        combo_returns: dict[tuple[SignalCategory, ...], list[float]] = defaultdict(list)

        for daily in daily_results:
            for item in daily.items:
                key = (daily.trade_date, item.symbol)
                fr = forward_returns_map.get(key)
                if fr is None or self.EVAL_PERIOD not in fr.returns:
                    continue
                ret = fr.returns[self.EVAL_PERIOD]

                categories = set()
                for sig in item.signals:
                    per_signal[sig.category].append(ret)
                    by_strength[sig.strength][sig.category].append(ret)
                    by_freshness[sig.freshness][sig.category].append(ret)
                    categories.add(sig.category)

                if len(categories) == 1:
                    exclusive_returns[list(categories)[0]].append(ret)

                sorted_cats = tuple(sorted(categories, key=lambda c: c.value))
                for r in range(2, min(len(sorted_cats) + 1, 4)):
                    for combo in combinations(sorted_cats, r):
                        combo_returns[combo].append(ret)

        result_per_signal: dict[str, SignalMetric] = {}
        for cat in SignalCategory:
            rets = per_signal.get(cat, [])
            exc_rets = exclusive_returns.get(cat, [])
            result_per_signal[cat.value] = SignalMetric(
                category=cat,
                hit_rate=_hit_rate(rets),
                avg_return=_mean(rets),
                trigger_count=len(rets),
                exclusive_return=_mean(exc_rets),
            )

        result_by_strength: dict[str, dict[str, SignalMetric]] = {}
        for strength, cat_map in by_strength.items():
            result_by_strength[strength.value] = {}
            for cat in SignalCategory:
                rets = cat_map.get(cat, [])
                result_by_strength[strength.value][cat.value] = SignalMetric(
                    category=cat,
                    hit_rate=_hit_rate(rets),
                    avg_return=_mean(rets),
                    trigger_count=len(rets),
                )

        result_by_freshness: dict[str, dict[str, SignalMetric]] = {}
        for freshness, cat_map in by_freshness.items():
            result_by_freshness[freshness.value] = {}
            for cat in SignalCategory:
                rets = cat_map.get(cat, [])
                result_by_freshness[freshness.value][cat.value] = SignalMetric(
                    category=cat,
                    hit_rate=_hit_rate(rets),
                    avg_return=_mean(rets),
                    trigger_count=len(rets),
                )

        top_combos = sorted(
            combo_returns.items(),
            key=lambda x: _mean(x[1]),
            reverse=True,
        )[:20]
        combinations_list = [
            SignalCombinationMetric(
                categories=combo,
                avg_return=_mean(rets),
                sample_count=len(rets),
            )
            for combo, rets in top_combos
            if len(rets) >= 5
        ]

        return {
            "per_signal": result_per_signal,
            "by_strength": result_by_strength,
            "by_freshness": result_by_freshness,
            "combinations": combinations_list,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _hit_rate(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if v > 0) / len(values) * 100
