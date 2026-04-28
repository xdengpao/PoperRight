"""因子预测力计算器

计算因子 IC/IR、识别有效/无效因子、计算因子间相关性。
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.screener.evaluation.forward_return_calculator import ForwardReturn
from app.services.screener.factor_registry import FACTOR_REGISTRY

IC_EFFECTIVE_THRESHOLD = 0.05
IC_INEFFECTIVE_THRESHOLD = 0.02
CORRELATION_REDUNDANT_THRESHOLD = 0.7


@dataclass
class FactorMetric:
    """单因子预测力指标。"""
    factor_name: str
    ic_mean: float = 0.0
    ir: float = 0.0
    ic_positive_rate: float = 0.0
    ic_std: float = 0.0
    factor_turnover: float = 0.0
    classification: str = "中性"


class FactorMetricsCalculator:
    """因子预测力计算器。"""

    def calculate(
        self,
        daily_factor_data: dict[date, dict[str, dict[str, Any]]],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
        holding_period: int = 5,
    ) -> dict[str, Any]:
        """计算因子预测力指标。"""
        factor_names = list(FACTOR_REGISTRY.keys())
        daily_ics: dict[str, list[float]] = defaultdict(list)
        daily_ranks: dict[str, dict[date, dict[str, int]]] = defaultdict(dict)

        sorted_dates = sorted(daily_factor_data.keys())

        for td in sorted_dates:
            snapshot = daily_factor_data[td]
            symbols = list(snapshot.keys())
            if len(symbols) < 30:
                continue

            fwd_rets: dict[str, float] = {}
            for sym in symbols:
                key = (td, sym)
                fr = forward_returns_map.get(key)
                if fr and holding_period in fr.returns:
                    fwd_rets[sym] = fr.returns[holding_period]

            if len(fwd_rets) < 30:
                continue

            valid_symbols = list(fwd_rets.keys())

            for fname in factor_names:
                factor_vals: dict[str, float] = {}
                for sym in valid_symbols:
                    val = snapshot.get(sym, {}).get(fname)
                    if val is not None and not isinstance(val, bool):
                        try:
                            factor_vals[sym] = float(val)
                        except (TypeError, ValueError):
                            continue
                    elif isinstance(val, bool):
                        factor_vals[sym] = 1.0 if val else 0.0

                if len(factor_vals) < 20:
                    continue

                common = [s for s in factor_vals if s in fwd_rets]
                if len(common) < 20:
                    continue

                ic = _spearman_rank_correlation(
                    [factor_vals[s] for s in common],
                    [fwd_rets[s] for s in common],
                )
                if ic is not None:
                    daily_ics[fname].append(ic)

                ranked = _rank_values({s: factor_vals[s] for s in common})
                daily_ranks[fname][td] = ranked

        per_factor: dict[str, FactorMetric] = {}
        for fname in factor_names:
            ics = daily_ics.get(fname, [])
            if not ics:
                per_factor[fname] = FactorMetric(factor_name=fname)
                continue

            ic_mean = statistics.mean(ics)
            ic_std = statistics.stdev(ics) if len(ics) > 1 else 0.0
            ir = ic_mean / ic_std if ic_std > 0 else 0.0
            ic_pos_rate = sum(1 for x in ics if x > 0) / len(ics) * 100

            turnover = self._compute_factor_turnover(daily_ranks.get(fname, {}), sorted_dates)

            if abs(ic_mean) >= IC_EFFECTIVE_THRESHOLD:
                classification = "有效"
            elif abs(ic_mean) < IC_INEFFECTIVE_THRESHOLD:
                classification = "无效"
            else:
                classification = "中性"

            per_factor[fname] = FactorMetric(
                factor_name=fname,
                ic_mean=ic_mean,
                ir=ir,
                ic_positive_rate=ic_pos_rate,
                ic_std=ic_std,
                factor_turnover=turnover,
                classification=classification,
            )

        correlation_matrix = self._compute_correlation_matrix(daily_factor_data, factor_names)
        redundant_pairs = [
            (f1, f2, corr)
            for (f1, f2), corr in correlation_matrix.items()
            if abs(corr) > CORRELATION_REDUNDANT_THRESHOLD
        ]

        effective = [f for f, m in per_factor.items() if m.classification == "有效"]
        ineffective = [f for f, m in per_factor.items() if m.classification == "无效"]

        return {
            "per_factor": per_factor,
            "correlation_matrix": correlation_matrix,
            "redundant_pairs": redundant_pairs,
            "effective_factors": effective,
            "ineffective_factors": ineffective,
        }

    @staticmethod
    def _compute_factor_turnover(
        ranks_by_date: dict[date, dict[str, int]],
        sorted_dates: list[date],
    ) -> float:
        """计算因子值排名在相邻交易日的平均变化幅度。"""
        turnovers: list[float] = []
        prev_ranks: dict[str, int] | None = None
        for td in sorted_dates:
            curr = ranks_by_date.get(td)
            if curr is None:
                continue
            if prev_ranks is not None:
                common = set(curr.keys()) & set(prev_ranks.keys())
                if common:
                    diffs = [abs(curr[s] - prev_ranks[s]) for s in common]
                    turnovers.append(statistics.mean(diffs) / len(common))
            prev_ranks = curr
        return statistics.mean(turnovers) if turnovers else 0.0

    @staticmethod
    def _compute_correlation_matrix(
        daily_factor_data: dict[date, dict[str, dict[str, Any]]],
        factor_names: list[str],
    ) -> dict[tuple[str, str], float]:
        """计算因子间相关性矩阵（取样本量最大的一天做横截面相关）。"""
        largest_date = max(daily_factor_data.keys(), key=lambda d: len(daily_factor_data[d]))
        snapshot = daily_factor_data[largest_date]
        symbols = list(snapshot.keys())

        factor_vectors: dict[str, list[float]] = {}
        for fname in factor_names:
            vals = []
            for sym in symbols:
                v = snapshot[sym].get(fname)
                if v is not None and not isinstance(v, bool):
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        vals.append(0.0)
                elif isinstance(v, bool):
                    vals.append(1.0 if v else 0.0)
                else:
                    vals.append(0.0)
            factor_vectors[fname] = vals

        result: dict[tuple[str, str], float] = {}
        for i, f1 in enumerate(factor_names):
            for f2 in factor_names[i + 1:]:
                corr = _spearman_rank_correlation(factor_vectors[f1], factor_vectors[f2])
                if corr is not None:
                    result[(f1, f2)] = corr
        return result


def _spearman_rank_correlation(x: list[float], y: list[float]) -> float | None:
    """计算 Spearman 秩相关系数。"""
    n = len(x)
    if n < 5 or len(y) != n:
        return None
    rx = _rank_list(x)
    ry = _rank_list(y)
    d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - (6 * d_sq) / (n * (n * n - 1))


def _rank_list(values: list[float]) -> list[float]:
    """平均排名法。"""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _rank_values(vals: dict[str, float]) -> dict[str, int]:
    """对字典值排名，返回 {key: rank}。"""
    sorted_items = sorted(vals.items(), key=lambda t: t[1], reverse=True)
    return {item[0]: rank + 1 for rank, item in enumerate(sorted_items)}
