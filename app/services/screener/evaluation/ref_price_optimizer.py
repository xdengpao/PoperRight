"""买入参考价优化方案生成器

分析参考价偏离度，给出计算逻辑调整建议。
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.services.screener.evaluation.forward_return_calculator import ForwardReturn


@dataclass
class RefPriceRecommendation:
    """买入参考价调整建议。"""
    item_id: str = "IMP-RP-001"
    current_method: str = "收盘价"
    recommended_method: str = ""
    avg_deviation: float = 0.0
    deviation_std: float = 0.0
    by_market_cap: dict = field(default_factory=dict)
    by_signal_strength: dict = field(default_factory=dict)
    file_path: str = "app/services/screener/screen_executor.py"
    code_snippet: str = ""


class RefPriceOptimizer:
    """买入参考价优化方案生成器。"""

    def generate(
        self,
        forward_returns: list[ForwardReturn],
        stock_info: dict[str, dict[str, Any]] | None = None,
    ) -> RefPriceRecommendation:
        buyable = [fr for fr in forward_returns if fr.can_buy]
        if not buyable:
            return RefPriceRecommendation()

        deviations = [fr.ref_price_deviation for fr in buyable]
        avg_dev = statistics.mean(deviations)
        std_dev = statistics.stdev(deviations) if len(deviations) > 1 else 0.0

        by_cap: dict[str, float] = {}
        if stock_info:
            cap_groups: dict[str, list[float]] = defaultdict(list)
            for fr in buyable:
                info = stock_info.get(fr.symbol, {})
                group = info.get("cap_group", "未知")
                cap_groups[group].append(fr.ref_price_deviation)
            by_cap = {g: statistics.mean(devs) for g, devs in cap_groups.items() if devs}

        if avg_dev > 2.0:
            method = f"收盘价 × (1 + {avg_dev:.2f}%) 补偿偏离"
            snippet = f"ref_buy_price = Decimal(str(close * (1 + {avg_dev / 100:.4f})))"
        elif avg_dev < -2.0:
            method = f"收盘价 × (1 + {avg_dev:.2f}%) 折扣"
            snippet = f"ref_buy_price = Decimal(str(close * (1 + {avg_dev / 100:.4f})))"
        elif std_dev > 3.0:
            method = "改为参考价区间 [close×0.98, close×1.02]"
            snippet = (
                "ref_buy_price_low = Decimal(str(close * 0.98))\n"
                "ref_buy_price_high = Decimal(str(close * 1.02))"
            )
        else:
            method = "保持收盘价（偏离度可接受）"
            snippet = ""

        return RefPriceRecommendation(
            current_method="收盘价",
            recommended_method=method,
            avg_deviation=avg_dev,
            deviation_std=std_dev,
            by_market_cap=by_cap,
            file_path="app/services/screener/screen_executor.py",
            code_snippet=snippet,
        )
