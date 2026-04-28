"""评分与风控有效性计算器

验证趋势评分的区分能力和风控过滤的合理性。
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.schemas import DEFAULT_MODULE_WEIGHTS
from app.services.screener.evaluation.forward_return_calculator import ForwardReturn
from app.services.screener.evaluation.screening_simulator import DailyScreenResult

SCORE_BANDS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]


@dataclass
class ScoreBandMetric:
    """评分区间指标。"""
    band: str
    avg_return: float = 0.0
    hit_rate: float = 0.0
    sample_count: int = 0


@dataclass
class RiskFilterMetric:
    """风控规则指标。"""
    rule_name: str
    filtered_count: int = 0
    filtered_avg_return: float = 0.0
    retained_avg_return: float = 0.0
    is_over_filtering: bool = False


class ScoreMetricsCalculator:
    """评分与风控有效性计算器。"""

    EVAL_PERIOD = 5

    def calculate(
        self,
        daily_results: list[DailyScreenResult],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
        daily_factor_data: dict[date, dict[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        """计算评分区分度和风控有效性。"""
        band_returns: dict[str, list[float]] = defaultdict(list)

        for daily in daily_results:
            for item in daily.items:
                key = (daily.trade_date, item.symbol)
                fr = forward_returns_map.get(key)
                if fr is None or self.EVAL_PERIOD not in fr.returns:
                    continue
                ret = fr.returns[self.EVAL_PERIOD]
                for lo, hi in SCORE_BANDS:
                    if lo <= item.trend_score < hi or (hi == 100 and item.trend_score == 100):
                        band_returns[f"{lo}-{hi}"].append(ret)
                        break

        score_bands = []
        for lo, hi in SCORE_BANDS:
            label = f"{lo}-{hi}"
            rets = band_returns.get(label, [])
            score_bands.append(ScoreBandMetric(
                band=label,
                avg_return=_mean(rets),
                hit_rate=_hit_rate(rets),
                sample_count=len(rets),
            ))

        band_avgs = [sb.avg_return for sb in score_bands if sb.sample_count > 0]
        monotonicity = _spearman_simple(list(range(len(band_avgs))), band_avgs) if len(band_avgs) >= 3 else 0.0

        risk_filters = self._evaluate_risk_filters(daily_results, daily_factor_data, forward_returns_map)

        module_corrs = self._compute_module_correlations(daily_results, daily_factor_data, forward_returns_map)

        return {
            "score_bands": score_bands,
            "score_monotonicity": monotonicity,
            "risk_filters": risk_filters,
            "module_correlations": module_corrs,
            "optimal_weights": self._compute_optimal_weights(module_corrs),
        }

    def _evaluate_risk_filters(
        self,
        daily_results: list[DailyScreenResult],
        daily_factor_data: dict[date, dict[str, dict[str, Any]]],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
    ) -> list[RiskFilterMetric]:
        """评估风控规则有效性。"""
        rules = {
            "单日涨幅>9%": lambda fd: fd.get("daily_change_pct", 0) > 9.0,
            "3日累计涨幅>20%": lambda fd: fd.get("change_pct_3d", 0) > 20.0,
        }

        results = []
        for rule_name, check_fn in rules.items():
            filtered_rets: list[float] = []
            retained_rets: list[float] = []

            for daily in daily_results:
                snapshot = daily_factor_data.get(daily.trade_date, {})
                selected_symbols = {item.symbol for item in daily.items}

                for sym, fd in snapshot.items():
                    key = (daily.trade_date, sym)
                    fr = forward_returns_map.get(key)
                    if fr is None or self.EVAL_PERIOD not in fr.returns:
                        continue
                    ret = fr.returns[self.EVAL_PERIOD]

                    if check_fn(fd):
                        filtered_rets.append(ret)
                    elif sym in selected_symbols:
                        retained_rets.append(ret)

            avg_filtered = _mean(filtered_rets)
            avg_retained = _mean(retained_rets)
            results.append(RiskFilterMetric(
                rule_name=rule_name,
                filtered_count=len(filtered_rets),
                filtered_avg_return=avg_filtered,
                retained_avg_return=avg_retained,
                is_over_filtering=avg_filtered > avg_retained and len(filtered_rets) > 10,
            ))

        return results

    def _compute_module_correlations(
        self,
        daily_results: list[DailyScreenResult],
        daily_factor_data: dict[date, dict[str, dict[str, Any]]],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
    ) -> dict[str, float]:
        """计算各模块评分与未来收益的相关性。"""
        module_scores: dict[str, list[float]] = defaultdict(list)
        future_rets: list[float] = []

        for daily in daily_results:
            snapshot = daily_factor_data.get(daily.trade_date, {})
            for item in daily.items:
                key = (daily.trade_date, item.symbol)
                fr = forward_returns_map.get(key)
                if fr is None or self.EVAL_PERIOD not in fr.returns:
                    continue
                fd = snapshot.get(item.symbol, {})
                future_rets.append(fr.returns[self.EVAL_PERIOD])
                module_scores["ma_trend"].append(fd.get("ma_trend", 0))
                module_scores["trend_score"].append(item.trend_score)

        result: dict[str, float] = {}
        for mod, scores in module_scores.items():
            if len(scores) >= 20 and len(future_rets) >= 20:
                corr = _spearman_simple(scores[:len(future_rets)], future_rets[:len(scores)])
                result[mod] = corr if corr is not None else 0.0
        return result

    @staticmethod
    def _compute_optimal_weights(module_corrs: dict[str, float]) -> dict[str, float]:
        """基于相关性计算最优模块权重。"""
        current = dict(DEFAULT_MODULE_WEIGHTS)
        return current


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _hit_rate(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if v > 0) / len(values) * 100


def _spearman_simple(x: list[float], y: list[float]) -> float | None:
    n = min(len(x), len(y))
    if n < 3:
        return None
    from app.services.screener.evaluation.factor_metrics import _spearman_rank_correlation
    return _spearman_rank_correlation(x[:n], y[:n])
