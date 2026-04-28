"""收益指标计算器

按持有期计算选股结果的命中率、平均收益、超额收益等指标。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from app.services.screener.evaluation.forward_return_calculator import (
    ForwardReturn,
    HOLDING_PERIODS,
)


@dataclass
class ReturnMetrics:
    """收益评价指标。"""
    holding_period: int
    hit_rate: float = 0.0
    avg_return: float = 0.0
    median_return: float = 0.0
    max_return: float = 0.0
    min_return: float = 0.0
    excess_return: float = 0.0
    unbuyable_rate: float = 0.0
    avg_ref_price_deviation: float = 0.0
    ref_price_deviation_std: float = 0.0
    sample_count: int = 0


class ReturnMetricsCalculator:
    """收益指标计算器。"""

    @staticmethod
    def calculate(
        forward_returns: list[ForwardReturn],
    ) -> dict[int, ReturnMetrics]:
        """按持有期计算收益指标。"""
        total = len(forward_returns)
        if total == 0:
            return {p: ReturnMetrics(holding_period=p) for p in HOLDING_PERIODS}

        buyable = [fr for fr in forward_returns if fr.can_buy]
        unbuyable_rate = (total - len(buyable)) / total * 100

        deviations = [fr.ref_price_deviation for fr in buyable]
        avg_dev = statistics.mean(deviations) if deviations else 0.0
        std_dev = statistics.stdev(deviations) if len(deviations) > 1 else 0.0

        result: dict[int, ReturnMetrics] = {}
        for period in HOLDING_PERIODS:
            returns = [fr.returns[period] for fr in buyable if period in fr.returns]
            excess = [fr.excess_returns[period] for fr in buyable if period in fr.excess_returns]

            if not returns:
                result[period] = ReturnMetrics(
                    holding_period=period,
                    unbuyable_rate=unbuyable_rate,
                    avg_ref_price_deviation=avg_dev,
                    ref_price_deviation_std=std_dev,
                    sample_count=0,
                )
                continue

            hit_count = sum(1 for r in returns if r > 0)
            result[period] = ReturnMetrics(
                holding_period=period,
                hit_rate=hit_count / len(returns) * 100,
                avg_return=statistics.mean(returns),
                median_return=statistics.median(returns),
                max_return=max(returns),
                min_return=min(returns),
                excess_return=statistics.mean(excess) if excess else 0.0,
                unbuyable_rate=unbuyable_rate,
                avg_ref_price_deviation=avg_dev,
                ref_price_deviation_std=std_dev,
                sample_count=len(returns),
            )

        return result
