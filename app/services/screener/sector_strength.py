"""
板块强势筛选器（Sector Strength Filter）

提供：
- SectorRankResult: 板块排名结果数据类
- SectorStrengthFilter: 板块强弱排名与候选股票过滤

包含两类方法：
1. 异步方法（compute_sector_ranks, map_stocks_to_sectors）：接收外部传入的
   AsyncSession 执行数据库查询
2. 纯函数（filter_by_sector_strength, compute_sector_strength 等）：不依赖
   数据库连接，方便属性测试直接调用

对应需求：
- 需求 5.2：从 SectorKline 查询板块行情数据
- 需求 5.3：从 SectorConstituent 查询成分股映射
- 需求 5.4：计算板块涨跌幅排名
- 需求 5.5：将候选股票映射到板块
- 需求 5.6：板块数据不可用时优雅降级
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sector import (
    SectorConstituent,
    SectorInfo,
    SectorKline,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class SectorRankResult:
    """板块排名结果"""

    sector_code: str
    sector_name: str
    rank: int
    change_pct: float       # 累计涨跌幅
    is_bullish: bool        # 是否多头趋势


# ---------------------------------------------------------------------------
# SectorStrengthFilter
# ---------------------------------------------------------------------------


class SectorStrengthFilter:
    """板块强势筛选器"""

    # ------------------------------------------------------------------
    # 异步数据库查询方法
    # ------------------------------------------------------------------

    async def compute_sector_ranks(
        self,
        ts_session: AsyncSession,
        pg_session: AsyncSession,
        data_source: str,       # "DC" / "TI" / "TDX"
        sector_type: str,       # "INDUSTRY" / "CONCEPT" / "REGION" / "STYLE"
        period: int = 5,        # 涨幅计算周期（天）
    ) -> list[SectorRankResult]:
        """
        计算板块涨跌幅排名。

        1. 从 SectorKline 查询指定 data_source 和 sector_type 的最近 period 天行情
        2. 计算每个板块的累计涨跌幅
        3. 按累计涨跌幅降序排列，分配排名
        4. 判断每个板块是否多头趋势（短期均线 > 长期均线）

        Args:
            ts_session: TimescaleDB 异步会话（SectorKline）
            pg_session: PostgreSQL 异步会话（SectorInfo）
            data_source: 数据来源，如 "DC" / "TI" / "TDX"
            sector_type: 板块类型，如 "INDUSTRY" / "CONCEPT"
            period: 涨幅计算周期（天），默认 5

        Returns:
            按累计涨跌幅降序排列的 SectorRankResult 列表
        """
        try:
            # 步骤 1：查询指定 data_source 的板块代码列表（按 sector_type 过滤）
            sector_info_map = await self._load_sector_info(
                pg_session, data_source, sector_type,
            )
            if not sector_info_map:
                logger.warning(
                    "未找到板块信息 data_source=%s sector_type=%s",
                    data_source, sector_type,
                )
                return []

            sector_codes = list(sector_info_map.keys())

            # 步骤 2：查询最近 period 天的 SectorKline 行情
            kline_data = await self._load_sector_klines(
                ts_session, data_source, sector_codes, period,
            )
            if not kline_data:
                logger.warning(
                    "未找到板块行情数据 data_source=%s sector_codes=%d个 period=%d",
                    data_source, len(sector_codes), period,
                )
                return []

            # 步骤 2.5：数据新鲜度检查（需求 9）
            # 从 kline_data 中提取最新交易日
            latest_data_date: date | None = None
            for _code, klines in kline_data.items():
                for k in klines:
                    k_date = k.time.date() if isinstance(k.time, datetime) else k.time
                    if latest_data_date is None or k_date > latest_data_date:
                        latest_data_date = k_date

            if latest_data_date is not None:
                current_date = date.today()
                should_warn, should_degrade, stale_days = self.check_data_freshness(
                    latest_data_date, current_date,
                )
                if should_degrade:
                    logger.warning(
                        "板块数据严重过期，降级处理 data_source=%s "
                        "最新数据日期=%s 延迟交易日=%d天，返回空排名列表",
                        data_source, latest_data_date, stale_days,
                    )
                    return []
                if should_warn:
                    logger.warning(
                        "板块数据延迟 data_source=%s "
                        "最新数据日期=%s 延迟交易日=%d天",
                        data_source, latest_data_date, stale_days,
                    )

            # 步骤 3：计算累计涨跌幅并排名
            sector_change = self._aggregate_change_pct(kline_data)

            # 步骤 4：判断多头趋势（5日均线 > 20日均线）
            sector_bullish = self._compute_bullish_flags(kline_data)

            # 步骤 5：按累计涨跌幅降序排列，分配排名
            sorted_sectors = sorted(
                sector_change.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            results: list[SectorRankResult] = []
            for rank_idx, (code, change) in enumerate(sorted_sectors, start=1):
                info = sector_info_map.get(code)
                name = info.name if info else code
                results.append(SectorRankResult(
                    sector_code=code,
                    sector_name=name,
                    rank=rank_idx,
                    change_pct=change,
                    is_bullish=sector_bullish.get(code, False),
                ))

            return results

        except Exception:
            logger.exception(
                "计算板块排名异常 data_source=%s sector_type=%s",
                data_source, sector_type,
            )
            return []

    async def map_stocks_to_sectors(
        self,
        pg_session: AsyncSession,
        data_source: str,
        sector_type: str,
        trade_date: date | None = None,
    ) -> dict[str, list[str]]:
        """
        构建 symbol → [sector_code] 映射。

        从 SectorConstituent 查询最近交易日的成分股数据。

        Args:
            pg_session: PostgreSQL 异步会话
            data_source: 数据来源
            sector_type: 板块类型
            trade_date: 交易日期（可选，默认查询最新）

        Returns:
            symbol → [sector_code, ...] 映射字典
        """
        try:
            # 如果未指定交易日，查询最新交易日
            if trade_date is None:
                trade_date = await self._get_latest_constituent_date(
                    pg_session, data_source,
                )
                if trade_date is None:
                    logger.warning(
                        "未找到成分股交易日 data_source=%s", data_source,
                    )
                    return {}

            # 查询指定 sector_type 的板块代码
            sector_codes_stmt = (
                select(SectorInfo.sector_code)
                .where(
                    SectorInfo.data_source == data_source,
                    SectorInfo.sector_type == sector_type,
                )
            )
            sector_result = await pg_session.execute(sector_codes_stmt)
            valid_sector_codes = {row[0] for row in sector_result.all()}

            if not valid_sector_codes:
                logger.warning(
                    "未找到板块代码 data_source=%s sector_type=%s",
                    data_source, sector_type,
                )
                return {}

            # 查询成分股数据
            stmt = (
                select(SectorConstituent)
                .where(
                    SectorConstituent.data_source == data_source,
                    SectorConstituent.trade_date == trade_date,
                    SectorConstituent.sector_code.in_(valid_sector_codes),
                )
            )
            result = await pg_session.execute(stmt)
            constituents = list(result.scalars().all())

            # 构建 symbol → [sector_code] 映射
            mapping: dict[str, list[str]] = defaultdict(list)
            for c in constituents:
                mapping[c.symbol].append(c.sector_code)

            logger.debug(
                "构建成分股映射 data_source=%s sector_type=%s date=%s "
                "板块数=%d 股票数=%d",
                data_source, sector_type, trade_date,
                len(valid_sector_codes), len(mapping),
            )
            return dict(mapping)

        except Exception:
            logger.exception(
                "构建成分股映射异常 data_source=%s sector_type=%s",
                data_source, sector_type,
            )
            return {}

    def filter_by_sector_strength(
        self,
        stocks_data: dict[str, dict],
        sector_ranks: list[SectorRankResult],
        stock_sector_map: dict[str, list[str]],
        top_n: int = 30,
    ) -> None:
        """
        将板块排名和趋势信息写入 stock_data 字典。

        对于每只股票：
        - 查找其所属板块中排名最高的板块
        - 写入 sector_rank (int), sector_trend (bool), sector_name (str)
        - 如果股票不属于任何板块，设为 None/False

        Args:
            stocks_data: {symbol: factor_dict} 字典，就地修改
            sector_ranks: 板块排名结果列表
            stock_sector_map: symbol → [sector_code] 映射
            top_n: 排名阈值（仅用于日志，实际写入完整排名）
        """
        # 构建 sector_code → SectorRankResult 查找表
        rank_map: dict[str, SectorRankResult] = {
            r.sector_code: r for r in sector_ranks
        }

        for symbol, factor_dict in stocks_data.items():
            sector_codes = stock_sector_map.get(symbol, [])

            if not sector_codes:
                # 股票不属于任何板块
                factor_dict["sector_rank"] = None
                factor_dict["sector_trend"] = False
                factor_dict["sector_name"] = None
                continue

            # 查找所属板块中排名最高（rank 值最小）的板块
            best_rank_result: SectorRankResult | None = None
            for code in sector_codes:
                rank_result = rank_map.get(code)
                if rank_result is None:
                    continue
                if best_rank_result is None or rank_result.rank < best_rank_result.rank:
                    best_rank_result = rank_result

            if best_rank_result is not None:
                factor_dict["sector_rank"] = best_rank_result.rank
                factor_dict["sector_trend"] = best_rank_result.is_bullish
                factor_dict["sector_name"] = best_rank_result.sector_name
            else:
                factor_dict["sector_rank"] = None
                factor_dict["sector_trend"] = False
                factor_dict["sector_name"] = None

    # ------------------------------------------------------------------
    # 纯函数：数据新鲜度检查
    # ------------------------------------------------------------------

    @staticmethod
    def check_data_freshness(
        latest_data_date: date,
        current_date: date,
        warning_threshold_days: int = 2,
        degrade_threshold_days: int = 5,
    ) -> tuple[bool, bool, int]:
        """
        检查板块数据新鲜度（纯函数）。

        使用简化工作日计算（排除周末），统计 latest_data_date 到 current_date
        之间的交易日数（不含 latest_data_date 当天，含 current_date 当天）。

        Args:
            latest_data_date: 最新数据日期
            current_date: 当前日期
            warning_threshold_days: WARNING 阈值（默认 2 个交易日）
            degrade_threshold_days: 降级阈值（默认 5 个交易日）

        Returns:
            (should_warn, should_degrade, stale_days) 元组
            - should_warn: 是否应记录 WARNING（stale_days > warning_threshold）
            - should_degrade: 是否应降级（stale_days > degrade_threshold）
            - stale_days: 数据延迟交易日数

        对应需求：
        - 需求 9.1：超过 2 个交易日记录 WARNING
        - 需求 9.2：超过 5 个交易日降级
        - 需求 9.4：支持自定义阈值
        """
        # 简化工作日计算：逐日遍历，排除周末（周六=5，周日=6）
        business_days = 0
        d = latest_data_date
        one_day = timedelta(days=1)

        # 从 latest_data_date 的下一天开始计数到 current_date
        d = d + one_day
        while d <= current_date:
            # weekday(): 0=周一 ... 4=周五, 5=周六, 6=周日
            if d.weekday() < 5:
                business_days += 1
            d = d + one_day

        should_warn = business_days > warning_threshold_days
        should_degrade = business_days > degrade_threshold_days

        return (should_warn, should_degrade, business_days)

    # ------------------------------------------------------------------
    # 纯函数（保留原有静态方法，向后兼容）
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_sector_info(
        pg_session: AsyncSession,
        data_source: str,
        sector_type: str,
    ) -> dict[str, SectorInfo]:
        """从 PostgreSQL 加载板块元数据，返回 sector_code → SectorInfo 映射。"""
        stmt = (
            select(SectorInfo)
            .where(
                SectorInfo.data_source == data_source,
                SectorInfo.sector_type == sector_type,
            )
        )
        result = await pg_session.execute(stmt)
        infos = list(result.scalars().all())
        return {info.sector_code: info for info in infos}

    @staticmethod
    async def _load_sector_klines(
        ts_session: AsyncSession,
        data_source: str,
        sector_codes: list[str],
        period: int,
    ) -> dict[str, list[SectorKline]]:
        """
        从 TimescaleDB 加载最近 period 天的板块日K线数据。

        返回 sector_code → [SectorKline, ...] 映射，每个板块的 K 线按时间升序排列。
        """
        # 先查询最新交易日
        latest_stmt = (
            select(func.max(SectorKline.time))
            .where(
                SectorKline.data_source == data_source,
                SectorKline.freq == "1d",
                SectorKline.sector_code.in_(sector_codes),
            )
        )
        latest_result = await ts_session.execute(latest_stmt)
        latest_time = latest_result.scalar_one_or_none()

        if latest_time is None:
            return {}

        # 查询所有板块最近的日K线，取足够多的数据用于 MA 计算（至少 20 天）
        # 需要 20 天数据来计算 20 日均线用于多头趋势判断
        fetch_days = max(period, 20)

        # 使用子查询获取最近 fetch_days 个不同交易日
        distinct_dates_stmt = (
            select(func.distinct(SectorKline.time))
            .where(
                SectorKline.data_source == data_source,
                SectorKline.freq == "1d",
                SectorKline.sector_code.in_(sector_codes),
                SectorKline.time <= latest_time,
            )
            .order_by(SectorKline.time.desc())
            .limit(fetch_days)
        )
        dates_result = await ts_session.execute(distinct_dates_stmt)
        trade_dates = [row[0] for row in dates_result.all()]

        if not trade_dates:
            return {}

        earliest_date = min(trade_dates)

        # 查询所有板块在这些交易日的 K 线
        stmt = (
            select(SectorKline)
            .where(
                SectorKline.data_source == data_source,
                SectorKline.freq == "1d",
                SectorKline.sector_code.in_(sector_codes),
                SectorKline.time >= earliest_date,
                SectorKline.time <= latest_time,
            )
            .order_by(SectorKline.sector_code, SectorKline.time.asc())
        )
        result = await ts_session.execute(stmt)
        klines = list(result.scalars().all())

        # 按 sector_code 分组
        grouped: dict[str, list[SectorKline]] = defaultdict(list)
        for k in klines:
            grouped[k.sector_code].append(k)

        return dict(grouped)

    @staticmethod
    async def _get_latest_constituent_date(
        pg_session: AsyncSession,
        data_source: str,
    ) -> date | None:
        """查询 SectorConstituent 表中指定数据源的最新交易日。"""
        stmt = (
            select(func.max(SectorConstituent.trade_date))
            .where(SectorConstituent.data_source == data_source)
        )
        result = await pg_session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _aggregate_change_pct(
        kline_data: dict[str, list[SectorKline]],
    ) -> dict[str, float]:
        """
        计算每个板块的累计涨跌幅。

        优先使用 change_pct 字段累加。当某板块所有 K 线的 change_pct 均为 NULL 时，
        使用收盘价序列 fallback：(最新收盘价 - 最早收盘价) / 最早收盘价 × 100。

        对应需求：
        - 需求 15.1：change_pct 全 NULL 时使用收盘价 fallback
        - 需求 15.2：有效收盘价 < 2 时设为 0.0
        - 需求 15.3：优先使用 change_pct（有效记录 > 0 时）
        - 需求 15.4：返回 float 类型

        Args:
            kline_data: sector_code → [SectorKline, ...] 映射（按时间升序）

        Returns:
            sector_code → 累计涨跌幅
        """
        result: dict[str, float] = {}
        for code, klines in kline_data.items():
            # 收集有效的 change_pct 值
            valid_pcts = [
                float(k.change_pct)
                for k in klines
                if k.change_pct is not None
            ]

            if valid_pcts:
                # 优先路径：有有效 change_pct，直接累加
                result[code] = sum(valid_pcts)
            else:
                # Fallback 路径：所有 change_pct 为 NULL，使用收盘价计算
                valid_closes = [
                    float(k.close)
                    for k in klines
                    if k.close is not None
                ]
                if len(valid_closes) >= 2:
                    earliest = valid_closes[0]   # klines 按时间升序
                    latest = valid_closes[-1]
                    if earliest != 0.0:
                        result[code] = (latest - earliest) / earliest * 100
                    else:
                        result[code] = 0.0
                else:
                    result[code] = 0.0

        return result

    @staticmethod
    def _compute_bullish_flags(
        kline_data: dict[str, list[SectorKline]],
    ) -> dict[str, bool]:
        """
        判断每个板块是否处于多头趋势。

        多头趋势定义：5 日均线（MA5）> 20 日均线（MA20），基于收盘价计算。

        Args:
            kline_data: sector_code → [SectorKline, ...] 映射（按时间升序）

        Returns:
            sector_code → is_bullish 映射
        """
        result: dict[str, bool] = {}
        for code, klines in kline_data.items():
            # 提取有效收盘价
            closes = [
                float(k.close)
                for k in klines
                if k.close is not None
            ]

            if len(closes) < 5:
                # 数据不足，无法计算均线
                result[code] = False
                continue

            # 计算 MA5（最近 5 个收盘价的平均值）
            ma5 = sum(closes[-5:]) / 5

            # 计算 MA20（最近 20 个收盘价的平均值，不足 20 个则用全部）
            ma20_window = closes[-20:] if len(closes) >= 20 else closes
            ma20 = sum(ma20_window) / len(ma20_window)

            result[code] = ma5 > ma20

        return result
