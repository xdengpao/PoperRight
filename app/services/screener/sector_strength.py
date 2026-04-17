"""
板块强势筛选器（Sector Strength Filter）

提供：
- SectorStrengthFilter: 板块强弱排名与候选股票过滤

纯函数设计，便于属性测试。数据库交互由调用方（ScreenDataProvider）负责。

对应需求：
- 需求 10.1：加载板块行情K线数据，计算板块强弱指标
- 需求 10.2：计算板块指数短期涨跌幅，按涨跌幅排序识别强势板块
- 需求 10.3：仅保留属于强势板块成分股的候选股票
- 需求 10.4：支持配置数据来源、涨幅计算周期、排名阈值
- 需求 10.5：板块行情数据不可用时跳过筛选，记录警告日志
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SectorStrengthFilter:
    """板块强势筛选器

    所有核心方法为 staticmethod / 纯函数，不依赖数据库连接，
    方便属性测试直接调用。
    """

    @staticmethod
    def compute_sector_strength(
        kline_data: list[dict],
    ) -> list[tuple[str, float]]:
        """Pure function: compute and rank sector strength from kline data.

        Each dict in *kline_data* must contain at least:
        - ``sector_code`` (str)
        - ``change_pct`` (float | Decimal | None)

        The function aggregates ``change_pct`` per sector (summing all
        available values) and returns a list of ``(sector_code, total_change_pct)``
        sorted **descending** by total change percentage.

        Args:
            kline_data: List of kline dicts, each with ``sector_code`` and
                ``change_pct``.

        Returns:
            Sorted list of ``(sector_code, total_change_pct)`` descending.
        """
        sector_pct: dict[str, float] = defaultdict(float)

        for row in kline_data:
            code = row.get("sector_code")
            pct = row.get("change_pct")
            if code is None or pct is None:
                continue
            sector_pct[code] += float(pct)

        ranked = sorted(sector_pct.items(), key=lambda x: x[1], reverse=True)
        return ranked

    @staticmethod
    def rank_sectors_by_strength(
        sector_klines: list[dict],
        period: int = 5,
    ) -> list[tuple[str, float]]:
        """Rank sectors by change_pct over the given period.

        For each sector, takes the last *period* kline records (by order of
        appearance) and sums their ``change_pct``.  Returns a sorted list of
        ``(sector_code, total_change_pct)`` descending.

        Args:
            sector_klines: Flat list of kline dicts, each with
                ``sector_code`` and ``change_pct``.
            period: Number of most-recent records per sector to consider.

        Returns:
            Sorted list of ``(sector_code, total_change_pct)`` descending.
        """
        # Group klines by sector_code, preserving insertion order
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in sector_klines:
            code = row.get("sector_code")
            if code is not None:
                grouped[code].append(row)

        # Take last `period` records per sector and sum change_pct
        trimmed: list[dict] = []
        for code, rows in grouped.items():
            tail = rows[-period:]  # last N records
            for r in tail:
                trimmed.append(r)

        return SectorStrengthFilter.compute_sector_strength(trimmed)

    @staticmethod
    def filter_by_top_sectors(
        candidates: list[str],
        stock_sectors: dict[str, list[str]],
        top_sector_codes: set[str],
    ) -> list[str]:
        """Retain only candidates belonging to at least one top-N sector.

        Args:
            candidates: Stock symbols to filter.
            stock_sectors: Mapping of ``symbol → [sector_code, ...]``.
            top_sector_codes: Set of sector codes considered "top-N".

        Returns:
            Filtered list preserving original order, containing only stocks
            that belong to at least one sector in *top_sector_codes*.
        """
        result: list[str] = []
        for symbol in candidates:
            sectors = stock_sectors.get(symbol, [])
            if any(sc in top_sector_codes for sc in sectors):
                result.append(symbol)
        return result
