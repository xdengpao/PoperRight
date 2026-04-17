"""
板块数据查询仓储层

SectorRepository 提供：
- get_sector_list：查询板块列表（支持按类型和数据源筛选）
- get_constituents：查询板块成分股
- get_sectors_by_stock：查询股票所属板块
- get_sector_kline：查询板块行情 K 线
- get_latest_trade_date：查询最新交易日
- get_sector_ranking：查询板块涨跌幅排行（双查询合并）

使用 AsyncSessionPG 查询 SectorInfo / SectorConstituent（PostgreSQL），
使用 AsyncSessionTS 查询 SectorKline（TimescaleDB）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select, func, and_

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.models.sector import (
    DataSource,
    SectorConstituent,
    SectorInfo,
    SectorKline,
    SectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class SectorRankingItem:
    """板块排行单条记录（仓储层输出）"""

    sector_code: str
    name: str
    sector_type: str
    change_pct: float | None
    close: float | None
    volume: int | None
    amount: float | None
    turnover: float | None


class SectorRepository:
    """板块数据查询仓储"""

    async def get_sector_list(
        self,
        sector_type: SectorType | None = None,
        data_source: DataSource | None = None,
    ) -> list[SectorInfo]:
        """查询板块列表，支持按板块类型和数据来源筛选。

        Args:
            sector_type: 板块类型筛选（可选）
            data_source: 数据来源筛选（可选）

        Returns:
            符合条件的 SectorInfo 列表
        """
        stmt = select(SectorInfo)

        if sector_type is not None:
            stmt = stmt.where(SectorInfo.sector_type == sector_type.value)
        if data_source is not None:
            stmt = stmt.where(SectorInfo.data_source == data_source.value)

        stmt = stmt.order_by(SectorInfo.sector_code)

        async with AsyncSessionPG() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        logger.debug(
            "查询板块列表 type=%s source=%s 共 %d 条",
            sector_type,
            data_source,
            len(rows),
        )
        return rows

    async def get_constituents(
        self,
        sector_code: str,
        data_source: DataSource,
        trade_date: date | None = None,
    ) -> list[SectorConstituent]:
        """查询指定板块的成分股列表。

        如果未指定 trade_date，默认使用最新交易日。

        Args:
            sector_code: 板块代码
            data_source: 数据来源
            trade_date: 交易日期（可选，默认最新）

        Returns:
            符合条件的 SectorConstituent 列表
        """
        if trade_date is None:
            trade_date = await self.get_latest_trade_date(data_source)
            if trade_date is None:
                return []

        stmt = (
            select(SectorConstituent)
            .where(
                and_(
                    SectorConstituent.sector_code == sector_code,
                    SectorConstituent.data_source == data_source.value,
                    SectorConstituent.trade_date == trade_date,
                )
            )
            .order_by(SectorConstituent.symbol)
        )

        async with AsyncSessionPG() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        logger.debug(
            "查询板块成分 code=%s source=%s date=%s 共 %d 条",
            sector_code,
            data_source.value,
            trade_date,
            len(rows),
        )
        return rows

    async def get_sectors_by_stock(
        self,
        symbol: str,
        trade_date: date | None = None,
    ) -> list[SectorConstituent]:
        """查询指定股票所属的全部板块。

        如果未指定 trade_date，默认使用最新交易日（跨所有数据源）。

        Args:
            symbol: 股票代码
            trade_date: 交易日期（可选，默认最新）

        Returns:
            符合条件的 SectorConstituent 列表
        """
        if trade_date is None:
            # 取所有数据源中最新的交易日
            trade_date = await self._get_latest_trade_date_all()
            if trade_date is None:
                return []

        stmt = (
            select(SectorConstituent)
            .where(
                and_(
                    SectorConstituent.symbol == symbol,
                    SectorConstituent.trade_date == trade_date,
                )
            )
            .order_by(SectorConstituent.sector_code)
        )

        async with AsyncSessionPG() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        logger.debug(
            "查询股票所属板块 symbol=%s date=%s 共 %d 条",
            symbol,
            trade_date,
            len(rows),
        )
        return rows

    async def get_sector_kline(
        self,
        sector_code: str,
        data_source: DataSource,
        freq: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> list[SectorKline]:
        """查询板块行情 K 线数据。

        Args:
            sector_code: 板块代码
            data_source: 数据来源
            freq: K 线频率，默认 "1d"
            start: 起始日期（含，可选）
            end: 结束日期（含，可选）

        Returns:
            按时间升序排列的 SectorKline 列表
        """
        conditions = [
            SectorKline.sector_code == sector_code,
            SectorKline.data_source == data_source.value,
            SectorKline.freq == freq,
        ]

        if start is not None:
            start_dt = datetime(start.year, start.month, start.day)
            conditions.append(SectorKline.time >= start_dt)
        if end is not None:
            end_dt = datetime(end.year, end.month, end.day, 23, 59, 59)
            conditions.append(SectorKline.time <= end_dt)

        stmt = (
            select(SectorKline)
            .where(and_(*conditions))
            .order_by(SectorKline.time.asc())
        )

        async with AsyncSessionTS() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        logger.debug(
            "查询板块行情 code=%s source=%s freq=%s %s~%s 共 %d 条",
            sector_code,
            data_source.value,
            freq,
            start,
            end,
            len(rows),
        )
        return rows

    async def get_latest_trade_date(
        self,
        data_source: DataSource,
    ) -> date | None:
        """查询指定数据源的最新交易日。

        Args:
            data_source: 数据来源

        Returns:
            最新交易日期，无数据时返回 None
        """
        stmt = (
            select(func.max(SectorConstituent.trade_date))
            .where(SectorConstituent.data_source == data_source.value)
        )

        async with AsyncSessionPG() as session:
            result = await session.execute(stmt)
            latest = result.scalar_one_or_none()

        logger.debug(
            "查询最新交易日 source=%s → %s",
            data_source.value,
            latest,
        )
        return latest

    # ------------------------------------------------------------------
    # 板块排行
    # ------------------------------------------------------------------

    async def _get_latest_kline_trade_date(
        self,
        data_source: DataSource,
    ) -> date | None:
        """查询 SectorKline 表中指定数据源的最新交易日。"""
        stmt = (
            select(func.max(SectorKline.time))
            .where(
                SectorKline.data_source == data_source.value,
                SectorKline.freq == "1d",
            )
        )

        async with AsyncSessionTS() as session:
            result = await session.execute(stmt)
            latest_dt = result.scalar_one_or_none()

        if latest_dt is None:
            return None
        # SectorKline.time is datetime; extract date part
        if isinstance(latest_dt, datetime):
            return latest_dt.date()
        return latest_dt

    # 板块类型 → 首选数据源映射
    # REGION 和 STYLE 仅 TDX 有数据，CONCEPT 和 INDUSTRY 优先 DC
    _TYPE_PREFERRED_SOURCE: dict[SectorType, DataSource] = {
        SectorType.CONCEPT: DataSource.DC,
        SectorType.INDUSTRY: DataSource.DC,
        SectorType.REGION: DataSource.TDX,
        SectorType.STYLE: DataSource.TDX,
    }

    async def get_sector_ranking(
        self,
        sector_type: SectorType | None = None,
        data_source: DataSource | None = None,
        trade_date: date | None = None,
    ) -> list[SectorRankingItem]:
        """查询板块涨跌幅排行。

        实现策略（双查询合并）：
        1. 确定数据源：用户显式指定时使用指定值；未指定时根据板块类型
           自动选择（REGION/STYLE → TDX，其他 → DC）；查询全部类型时
           合并多个数据源的结果
        2. 从 TimescaleDB 查询指定数据源最新交易日的日线行情
        3. 从 PostgreSQL 批量查询对应板块的名称和类型
        4. 在 Python 中合并两个结果集，按 change_pct 降序排序

        Args:
            sector_type: 板块类型筛选（可选）
            data_source: 数据来源（可选，未指定时自动选择）
            trade_date: 交易日期（可选，默认最新）

        Returns:
            按涨跌幅降序排列的 SectorRankingItem 列表
        """
        # 确定需要查询的 (data_source, sector_type) 组合
        if data_source is not None:
            # 用户显式指定了数据源，直接使用
            query_pairs: list[tuple[DataSource, SectorType | None]] = [
                (data_source, sector_type)
            ]
        elif sector_type is not None:
            # 用户指定了板块类型但未指定数据源，按类型选择首选数据源
            preferred = self._TYPE_PREFERRED_SOURCE.get(sector_type, DataSource.DC)
            query_pairs = [(preferred, sector_type)]
        else:
            # 查询全部类型：DC 查 CONCEPT+INDUSTRY，TDX 查 REGION+STYLE
            query_pairs = [
                (DataSource.DC, None),    # DC 包含 CONCEPT + INDUSTRY
                (DataSource.TDX, SectorType.REGION),
                (DataSource.TDX, SectorType.STYLE),
            ]

        all_results: list[SectorRankingItem] = []
        for ds, st in query_pairs:
            items = await self._query_ranking_single(ds, st, trade_date)
            all_results.extend(items)

        # 按 change_pct 降序排序，None 值排最后
        all_results.sort(
            key=lambda x: (x.change_pct is not None, x.change_pct or 0),
            reverse=True,
        )

        logger.debug(
            "查询板块排行 type=%s source=%s date=%s 共 %d 条",
            sector_type,
            data_source,
            trade_date,
            len(all_results),
        )
        return all_results

    async def _query_ranking_single(
        self,
        data_source: DataSource,
        sector_type: SectorType | None,
        trade_date: date | None,
    ) -> list[SectorRankingItem]:
        """查询单个数据源的板块排行（内部方法）。"""
        # 步骤 1：从 TimescaleDB 查询最新交易日行情
        if trade_date is None:
            resolved_date = await self._get_latest_kline_trade_date(data_source)
            if resolved_date is None:
                return []
        else:
            resolved_date = trade_date

        async with AsyncSessionTS() as session:
            stmt = (
                select(SectorKline)
                .where(
                    SectorKline.data_source == data_source.value,
                    SectorKline.freq == "1d",
                    SectorKline.time >= datetime(resolved_date.year, resolved_date.month, resolved_date.day),
                    SectorKline.time <= datetime(resolved_date.year, resolved_date.month, resolved_date.day, 23, 59, 59),
                )
            )
            klines = list((await session.execute(stmt)).scalars().all())

        if not klines:
            return []

        # 步骤 2：从 PostgreSQL 批量查询板块信息
        sector_codes = [k.sector_code for k in klines]
        async with AsyncSessionPG() as session:
            stmt = select(SectorInfo).where(
                SectorInfo.data_source == data_source.value,
                SectorInfo.sector_code.in_(sector_codes),
            )
            if sector_type is not None:
                stmt = stmt.where(SectorInfo.sector_type == sector_type.value)
            infos = list((await session.execute(stmt)).scalars().all())

        # 步骤 3：内存合并
        info_map = {si.sector_code: si for si in infos}
        results: list[SectorRankingItem] = []
        for k in klines:
            si = info_map.get(k.sector_code)
            if si is None:
                continue  # 无板块信息则跳过（或被 sector_type 过滤）
            results.append(
                SectorRankingItem(
                    sector_code=k.sector_code,
                    name=si.name,
                    sector_type=si.sector_type,
                    change_pct=float(k.change_pct) if k.change_pct is not None else None,
                    close=float(k.close) if k.close is not None else None,
                    volume=k.volume,
                    amount=float(k.amount) if k.amount is not None else None,
                    turnover=float(k.turnover) if k.turnover is not None else None,
                )
            )

        return results

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _get_latest_trade_date_all(self) -> date | None:
        """查询所有数据源中最新的交易日。"""
        stmt = select(func.max(SectorConstituent.trade_date))

        async with AsyncSessionPG() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
