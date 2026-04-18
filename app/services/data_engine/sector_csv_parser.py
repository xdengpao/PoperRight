"""
多源板块 CSV/ZIP 解析器

将东方财富 (DC)、同花顺 (TI)、通达信 (TDX) 三个数据源各自不同格式的
CSV/ZIP 文件解析为统一的内部数据结构 (ParsedSectorInfo / ParsedConstituent /
ParsedSectorKline)。
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.models.sector import DataSource, SectorType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 解析层 dataclass（中间数据结构）
# ---------------------------------------------------------------------------


@dataclass
class ParsedSectorInfo:
    """解析后的板块元数据"""

    sector_code: str
    name: str
    sector_type: SectorType
    data_source: DataSource
    list_date: date | None = None
    constituent_count: int | None = None


@dataclass
class ParsedConstituent:
    """解析后的板块成分股"""

    trade_date: date
    sector_code: str
    data_source: DataSource
    symbol: str
    stock_name: str | None = None


@dataclass
class ParsedSectorKline:
    """解析后的板块行情"""

    time: date
    sector_code: str
    data_source: DataSource
    freq: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None
    amount: Decimal | None = None
    turnover: Decimal | None = None
    change_pct: Decimal | None = None


# ---------------------------------------------------------------------------
# 日期推断正则
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{8})")
_DATE_DASH_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _normalize_symbol(raw: str) -> str:
    """将带后缀的股票代码（如 ``000002.SZ``）转为裸代码（``000002``）。

    业务表（stock_info, sector_constituent, position 等）统一使用裸代码，
    仅 kline 时序表使用带后缀格式。参见 data-consistency.md §3.2。
    """
    return raw.split(".")[0] if "." in raw else raw


# ---------------------------------------------------------------------------
# SectorCSVParser
# ---------------------------------------------------------------------------


class SectorCSVParser:
    """多源板块 CSV/ZIP 解析器"""

    # -----------------------------------------------------------------------
    # 板块列表解析
    # -----------------------------------------------------------------------

    def parse_sector_list_dc(self, file_path: Path) -> list[ParsedSectorInfo]:
        """解析东方财富板块列表 CSV。

        支持两种列头格式：
        1. 13列: 板块代码,交易日期,板块名称,...,idx_type,level
        2. 11列: 板块代码,交易日期,板块名称,...（无 idx_type/level）

        提取: sector_code (板块代码), name (板块名称),
              sector_type (通过 idx_type 映射，无 idx_type 时默认 CONCEPT)
        按 sector_code 去重（保留首次出现）。
        """
        text = self._read_csv(file_path)
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorInfo] = []
        seen: set[str] = set()

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                # 至少需要 3 列（板块代码, 交易日期, 板块名称）
                if len(row) < 3:
                    continue
                sector_code = row[0].strip()
                name = row[2].strip()

                # idx_type 在第 12 列（索引 11），增量文件可能只有 11 列
                idx_type = ""
                if len(row) >= 12:
                    idx_type = row[11].strip()

                if sector_code in seen:
                    continue
                seen.add(sector_code)

                results.append(ParsedSectorInfo(
                    sector_code=sector_code,
                    name=name,
                    sector_type=self._map_dc_sector_type(idx_type),
                    data_source=DataSource.DC,
                ))
            except Exception:
                logger.warning(
                    "DC 板块列表解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    def parse_sector_list_ti(self, file_path: Path) -> list[ParsedSectorInfo]:
        """解析同花顺板块列表 CSV。

        列头: 代码,名称,成分个数,交易所,上市日期,指数类型

        提取: sector_code (代码), name (名称), constituent_count (成分个数),
              list_date (上市日期), sector_type (通过指数类型映射)
        """
        text = self._read_csv(file_path)
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorInfo] = []

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                # TI CSV 至少需要 6 列
                if len(row) < 6:
                    continue
                sector_code = row[0].strip()
                name = row[1].strip()
                raw_count = row[2].strip()
                raw_list_date = row[4].strip()
                index_type = row[5].strip()

                # 解析成分股数量
                constituent_count: int | None = None
                if raw_count:
                    try:
                        constituent_count = int(raw_count)
                    except ValueError:
                        pass

                # 解析上市日期（支持 YYYY-MM-DD 和 YYYYMMDD）
                list_date: date | None = None
                if raw_list_date:
                    try:
                        if "-" in raw_list_date:
                            parts = raw_list_date.split("-")
                            list_date = date(
                                int(parts[0]), int(parts[1]), int(parts[2])
                            )
                        elif len(raw_list_date) == 8:
                            list_date = date(
                                int(raw_list_date[:4]),
                                int(raw_list_date[4:6]),
                                int(raw_list_date[6:8]),
                            )
                    except (ValueError, IndexError):
                        pass

                results.append(ParsedSectorInfo(
                    sector_code=sector_code,
                    name=name,
                    sector_type=self._map_ti_sector_type(index_type),
                    data_source=DataSource.TI,
                    list_date=list_date,
                    constituent_count=constituent_count,
                ))
            except Exception:
                logger.warning(
                    "TI 板块列表解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    def parse_sector_list_tdx(self, file_path: Path) -> list[ParsedSectorInfo]:
        """解析通达信板块列表 CSV 或 ZIP。

        CSV 列头: 板块代码,交易日期,板块名称,板块类型,成分个数,
              总股本(亿),流通股(亿),总市值(亿),流通市值(亿)

        如果 file_path 是 ZIP 文件，则解压后逐个解析内部 CSV。
        按 sector_code 去重（保留首次出现）。
        """
        if file_path.suffix.lower() == ".zip":
            entries = self._extract_zip(file_path)
            all_items: list[ParsedSectorInfo] = []
            for filename, csv_text in entries:
                all_items.extend(self._parse_sector_list_tdx_text(csv_text))
            # 去重
            seen: set[str] = set()
            results: list[ParsedSectorInfo] = []
            for item in all_items:
                if item.sector_code not in seen:
                    seen.add(item.sector_code)
                    results.append(item)
            return results

        text = self._read_csv(file_path)
        return self._parse_sector_list_tdx_text(text)

    def _parse_sector_list_tdx_text(self, text: str) -> list[ParsedSectorInfo]:
        """解析通达信板块列表 CSV 文本内容。"""
        _TDX_TYPE_MAP: dict[str, SectorType] = {
            "概念板块": SectorType.CONCEPT,
            "行业板块": SectorType.INDUSTRY,
            "地区板块": SectorType.REGION,
            "风格板块": SectorType.STYLE,
        }

        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorInfo] = []
        seen: set[str] = set()

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                # TDX CSV 至少需要 9 列
                if len(row) < 9:
                    continue
                sector_code = row[0].strip()
                name = row[2].strip()
                raw_type = row[3].strip()
                raw_count = row[4].strip()

                if sector_code in seen:
                    continue
                seen.add(sector_code)

                sector_type = _TDX_TYPE_MAP.get(raw_type, SectorType.CONCEPT)

                constituent_count: int | None = None
                if raw_count:
                    try:
                        constituent_count = int(raw_count)
                    except ValueError:
                        pass

                results.append(ParsedSectorInfo(
                    sector_code=sector_code,
                    name=name,
                    sector_type=sector_type,
                    data_source=DataSource.TDX,
                    constituent_count=constituent_count,
                ))
            except Exception:
                logger.warning(
                    "TDX 板块列表解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    # -----------------------------------------------------------------------
    # 板块成分解析
    # -----------------------------------------------------------------------

    def parse_constituents_dc_zip(
        self, zip_path: Path
    ) -> list[ParsedConstituent]:
        """解析东方财富板块成分 ZIP 文件。

        ZIP 文件名格式: ``板块成分_DC_YYYYMMDD.zip``
        ZIP 内每个 CSV 文件包含列: 交易日期,板块代码,成分股票代码,成分股票名称

        trade_date 从 ZIP 文件名推断。
        """
        trade_date = self._infer_date_from_filename(zip_path.name)
        if trade_date is None:
            logger.warning(
                "DC 成分 ZIP 文件名无法推断日期，跳过: %s", zip_path
            )
            return []

        entries = self._extract_zip(zip_path)
        results: list[ParsedConstituent] = []

        for filename, csv_text in entries:
            reader = csv.reader(io.StringIO(csv_text))
            header_skipped = False
            for row in reader:
                if not header_skipped:
                    header_skipped = True
                    continue
                try:
                    if len(row) < 4:
                        continue
                    sector_code = row[1].strip()
                    symbol = _normalize_symbol(row[2].strip())
                    stock_name = row[3].strip() or None

                    if not sector_code or not symbol:
                        continue

                    results.append(ParsedConstituent(
                        trade_date=trade_date,
                        sector_code=sector_code,
                        data_source=DataSource.DC,
                        symbol=symbol,
                        stock_name=stock_name,
                    ))
                except Exception:
                    logger.warning(
                        "DC 成分解析行失败，跳过: %s (文件: %s)",
                        row, filename, exc_info=True,
                    )
                    continue

        return results

    def parse_constituents_ti_csv(
        self, file_path: Path, trade_date: date
    ) -> list[ParsedConstituent]:
        """解析同花顺板块成分 CSV 或 ZIP 文件。

        CSV 格式有两种：
        1. 汇总 CSV 列头: 指数代码,指数名称,指数类型,股票代码,股票名称
        2. ZIP 内 CSV 列头: 指数代码,股票代码,股票名称

        trade_date 由调用方传入（从文件名推断）。
        如果 file_path 是 ZIP 文件，则解压后逐个解析内部 CSV。
        """
        if file_path.suffix.lower() == ".zip":
            entries = self._extract_zip(file_path)
            results: list[ParsedConstituent] = []
            for filename, csv_text in entries:
                results.extend(self._parse_constituents_ti_text(csv_text, trade_date))
            return results

        text = self._read_csv(file_path)
        return self._parse_constituents_ti_text(text, trade_date)

    def _parse_constituents_ti_text(
        self, text: str, trade_date: date
    ) -> list[ParsedConstituent]:
        """解析同花顺板块成分 CSV 文本内容。

        列头: 指数代码,指数名称,指数类型,股票代码,股票名称
        """
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedConstituent] = []

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                if len(row) < 5:
                    continue

                sector_code = row[0].strip()
                symbol = _normalize_symbol(row[3].strip())
                stock_name = row[4].strip() or None

                if not sector_code or not symbol:
                    continue

                results.append(ParsedConstituent(
                    trade_date=trade_date,
                    sector_code=sector_code,
                    data_source=DataSource.TI,
                    symbol=symbol,
                    stock_name=stock_name,
                ))
            except Exception:
                logger.warning(
                    "TI 成分解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    def parse_constituents_tdx_zip(
        self, zip_path: Path
    ) -> list[ParsedConstituent]:
        """解析通达信板块成分 ZIP 文件。

        ZIP 文件名格式: ``板块成分_TDX_YYYYMMDD.zip``
        ZIP 内每个 CSV 文件包含列: 板块代码,交易日期,成分股票代码,成分股票名称

        trade_date 从 ZIP 文件名推断。
        """
        trade_date = self._infer_date_from_filename(zip_path.name)
        if trade_date is None:
            logger.warning(
                "TDX 成分 ZIP 文件名无法推断日期，跳过: %s", zip_path
            )
            return []

        entries = self._extract_zip(zip_path)
        results: list[ParsedConstituent] = []

        for filename, csv_text in entries:
            reader = csv.reader(io.StringIO(csv_text))
            header_skipped = False
            for row in reader:
                if not header_skipped:
                    header_skipped = True
                    continue
                try:
                    if len(row) < 4:
                        continue
                    sector_code = row[0].strip()
                    symbol = _normalize_symbol(row[2].strip())
                    stock_name = row[3].strip() or None

                    if not sector_code or not symbol:
                        continue

                    results.append(ParsedConstituent(
                        trade_date=trade_date,
                        sector_code=sector_code,
                        data_source=DataSource.TDX,
                        symbol=symbol,
                        stock_name=stock_name,
                    ))
                except Exception:
                    logger.warning(
                        "TDX 成分解析行失败，跳过: %s (文件: %s)",
                        row, filename, exc_info=True,
                    )
                    continue

        return results

    # -----------------------------------------------------------------------
    # 板块行情解析
    # -----------------------------------------------------------------------

    def parse_kline_dc_csv(
        self, file_path: Path
    ) -> list[ParsedSectorKline]:
        """解析东方财富板块行情 CSV 或 ZIP。

        CSV 列头: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,
                  涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块

        提取: sector_code (板块代码), time (交易日期), open (开盘点位),
              close (收盘点位), high (最高点位), low (最低点位),
              volume (成交量), amount (成交额), change_pct (涨跌幅%),
              turnover (换手%)

        如果 file_path 是 ZIP 文件，则解压后逐个解析内部 CSV。
        """
        if file_path.suffix.lower() == ".zip":
            entries = self._extract_zip(file_path)
            results: list[ParsedSectorKline] = []
            for filename, csv_text in entries:
                results.extend(self._parse_kline_dc_text(csv_text))
            return results

        text = self._read_csv(file_path)
        return self._parse_kline_dc_text(text)

    def _parse_kline_dc_text(self, text: str) -> list[ParsedSectorKline]:
        """解析东方财富板块行情 CSV 文本内容。

        列头: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块
        """
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorKline] = []

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                if len(row) < 12:
                    continue

                sector_code = row[0].strip()

                # 日期: YYYY-MM-DD 或 YYYYMMDD
                raw_date = row[1].strip()
                if "-" in raw_date:
                    parts = raw_date.split("-")
                    time_ = date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(raw_date) == 8:
                    time_ = date(
                        int(raw_date[:4]),
                        int(raw_date[4:6]),
                        int(raw_date[6:8]),
                    )
                else:
                    logger.warning("DC 行情日期格式无法解析，跳过: %s", raw_date)
                    continue

                close = Decimal(row[2].strip())
                open_ = Decimal(row[3].strip())
                high = Decimal(row[4].strip())
                low = Decimal(row[5].strip())
                # row[6] = 涨跌点位 (skip)
                change_pct = Decimal(row[7].strip())
                volume = int(Decimal(row[8].strip()))
                amount = Decimal(row[9].strip())
                # row[10] = 振幅% (skip)
                turnover = Decimal(row[11].strip())

                kline = ParsedSectorKline(
                    time=time_,
                    sector_code=sector_code,
                    data_source=DataSource.DC,
                    freq="1d",
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    amount=amount,
                    change_pct=change_pct,
                    turnover=turnover,
                )

                if not self._validate_ohlc(kline):
                    logger.warning(
                        "DC 行情 OHLC 验证失败，跳过: %s %s",
                        sector_code, raw_date,
                    )
                    continue

                results.append(kline)
            except (InvalidOperation, ValueError, IndexError):
                logger.warning(
                    "DC 行情解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    def parse_kline_ti_csv(
        self, file_path: Path
    ) -> list[ParsedSectorKline]:
        """解析同花顺板块行情 CSV 或 ZIP。

        CSV 列头: 指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,
              昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率

        如果 file_path 是 ZIP 文件，则解压后逐个解析内部 CSV。
        """
        if file_path.suffix.lower() == ".zip":
            entries = self._extract_zip(file_path)
            results: list[ParsedSectorKline] = []
            for filename, csv_text in entries:
                results.extend(self._parse_kline_ti_text(csv_text))
            return results

        text = self._read_csv(file_path)
        return self._parse_kline_ti_text(text)

    def _parse_kline_ti_text(self, text: str) -> list[ParsedSectorKline]:
        """解析同花顺板块行情 CSV 文本内容。"""
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorKline] = []

        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            try:
                if len(row) < 10:
                    continue

                sector_code = row[0].strip()

                # 交易日期: YYYY-MM-DD 或 YYYYMMDD
                raw_date = row[1].strip()
                if "-" in raw_date:
                    parts = raw_date.split("-")
                    time_ = date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(raw_date) == 8:
                    time_ = date(
                        int(raw_date[:4]),
                        int(raw_date[4:6]),
                        int(raw_date[6:8]),
                    )
                else:
                    logger.warning("TI 行情日期格式无法解析，跳过: %s", raw_date)
                    continue

                open_ = Decimal(row[2].strip())
                high = Decimal(row[3].strip())
                low = Decimal(row[4].strip())
                close = Decimal(row[5].strip())
                # row[6] = 昨日收盘点 (skip)
                # row[7] = 平均价 (skip)
                # row[8] = 涨跌点位 (skip)
                change_pct = Decimal(row[9].strip()) if row[9].strip() else None

                volume: int | None = None
                if len(row) >= 11 and row[10].strip():
                    volume = int(Decimal(row[10].strip()))

                turnover: Decimal | None = None
                if len(row) >= 12 and row[11].strip():
                    turnover = Decimal(row[11].strip())

                kline = ParsedSectorKline(
                    time=time_,
                    sector_code=sector_code,
                    data_source=DataSource.TI,
                    freq="1d",
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    change_pct=change_pct,
                    turnover=turnover,
                )

                if not self._validate_ohlc(kline):
                    logger.warning(
                        "TI 行情 OHLC 验证失败，跳过: %s %s",
                        sector_code, raw_date,
                    )
                    continue

                results.append(kline)
            except (InvalidOperation, ValueError, IndexError):
                logger.warning(
                    "TI 行情解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    def parse_kline_tdx_csv(
        self, file_path: Path
    ) -> list[ParsedSectorKline]:
        """解析通达信板块行情 CSV 或 ZIP。

        CSV 格式有两种：
        1. 历史行情 ZIP 内 CSV 列头: 日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数
        2. 增量/根目录 CSV 列头: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,...

        如果 file_path 是 ZIP 文件，则解压后逐个解析内部 CSV。
        """
        if file_path.suffix.lower() == ".zip":
            entries = self._extract_zip(file_path)
            results: list[ParsedSectorKline] = []
            for filename, csv_text in entries:
                results.extend(self._parse_kline_tdx_text(csv_text))
            return results

        text = self._read_csv(file_path)
        return self._parse_kline_tdx_text(text)

    def _parse_kline_tdx_text(self, text: str) -> list[ParsedSectorKline]:
        """解析通达信板块行情 CSV 文本内容。

        自动检测两种格式：
        - 格式 A（历史 ZIP 内）: 日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,...
        - 格式 B（增量/根目录）: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,...
        """
        reader = csv.reader(io.StringIO(text))
        results: list[ParsedSectorKline] = []

        header: list[str] | None = None
        for row in reader:
            if header is None:
                header = [c.strip() for c in row]
                continue
            try:
                if not row or not row[0].strip():
                    continue

                # 检测格式
                if header and header[0] in ("日期",):
                    # 格式 A: 日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,...
                    if len(row) < 9:
                        continue
                    raw_date = row[0].strip()
                    sector_code = row[1].strip()
                    open_ = Decimal(row[3].strip())
                    close = Decimal(row[4].strip())
                    high = Decimal(row[5].strip())
                    low = Decimal(row[6].strip())
                    volume_raw = row[7].strip()
                    volume = int(Decimal(volume_raw)) if volume_raw else None
                    amount_raw = row[8].strip()
                    amount = Decimal(amount_raw) if amount_raw else None
                    change_pct = None
                    turnover = None
                    # 从文件名推断频率
                    freq = "1d"
                else:
                    # 格式 B: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,...
                    if len(row) < 10:
                        continue
                    sector_code = row[0].strip()
                    raw_date = row[1].strip()
                    close = Decimal(row[2].strip())
                    open_ = Decimal(row[3].strip())
                    high = Decimal(row[4].strip())
                    low = Decimal(row[5].strip())
                    # row[6] = 昨日收盘点 or 涨跌点位
                    # row[7] = 涨跌点位 or 涨跌幅%
                    change_pct_raw = row[8].strip() if len(row) > 8 else ""
                    change_pct = Decimal(change_pct_raw) if change_pct_raw else None
                    volume_raw = row[9].strip() if len(row) > 9 else ""
                    volume = int(Decimal(volume_raw)) if volume_raw else None
                    amount_raw = row[10].strip() if len(row) > 10 else ""
                    amount = Decimal(amount_raw) if amount_raw else None
                    turnover = None
                    if len(row) > 13:
                        turnover_raw = row[13].strip()
                        turnover = Decimal(turnover_raw) if turnover_raw else None
                    freq = "1d"

                # 解析日期
                if "-" in raw_date:
                    parts = raw_date.split("-")
                    time_ = date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(raw_date) == 8:
                    time_ = date(
                        int(raw_date[:4]),
                        int(raw_date[4:6]),
                        int(raw_date[6:8]),
                    )
                else:
                    logger.warning("TDX 行情日期格式无法解析，跳过: %s", raw_date)
                    continue

                kline = ParsedSectorKline(
                    time=time_,
                    sector_code=sector_code,
                    data_source=DataSource.TDX,
                    freq=freq,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    amount=amount,
                    change_pct=change_pct,
                    turnover=turnover,
                )

                if not self._validate_ohlc(kline):
                    logger.warning(
                        "TDX 行情 OHLC 验证失败，跳过: %s %s",
                        sector_code, raw_date,
                    )
                    continue

                results.append(kline)
            except (InvalidOperation, ValueError, IndexError):
                logger.warning(
                    "TDX 行情解析行失败，跳过: %s", row, exc_info=True
                )
                continue

        return results

    # -----------------------------------------------------------------------
    # 通用工具方法
    # -----------------------------------------------------------------------

    def _read_csv(self, file_path: Path) -> str:
        """读取 CSV 文件，自动检测编码（UTF-8 → GBK → GB2312），去除 BOM。

        Returns:
            文件文本内容。

        Raises:
            UnicodeDecodeError: 三种编码均无法解码时抛出。
        """
        raw = file_path.read_bytes()
        # 去除 UTF-8 BOM
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        for encoding in ("utf-8", "gbk", "gb2312"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError(
            "gb2312", raw, 0, len(raw),
            f"无法以 UTF-8/GBK/GB2312 解码文件: {file_path}"
        )

    def _extract_zip(
        self, zip_path: Path
    ) -> list[tuple[str, str]]:
        """内存解压 ZIP，返回 ``[(文件名, CSV 文本内容), ...]``。

        对 ZIP 内每个文件依次尝试 UTF-8 → GBK → GB2312 解码。
        遇到 ``BadZipFile`` 时记录警告并返回空列表。
        """
        try:
            data = zip_path.read_bytes()
        except OSError as exc:
            logger.warning("无法读取 ZIP 文件 %s: %s", zip_path, exc)
            return []

        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            logger.warning("损坏的 ZIP 文件，跳过: %s", zip_path)
            return []

        results: list[tuple[str, str]] = []
        with zf:
            for name in zf.namelist():
                raw = zf.read(name)
                text: str | None = None
                for encoding in ("utf-8", "gbk", "gb2312"):
                    try:
                        text = raw.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                if text is None:
                    logger.warning(
                        "ZIP 内文件 %s 编码无法识别，跳过", name
                    )
                    continue
                results.append((name, text))
        return results

    def _validate_ohlc(self, kline: ParsedSectorKline) -> bool:
        """验证 OHLC 保序性。

        规则: low ≤ open, low ≤ close, high ≥ open, high ≥ close
        """
        return (
            kline.low <= kline.open
            and kline.low <= kline.close
            and kline.high >= kline.open
            and kline.high >= kline.close
        )

    def _infer_date_from_filename(self, filename: str) -> date | None:
        """从文件名中推断日期。

        支持两种格式：
        - YYYYMMDD（如 板块成分_DC_20250401.zip）
        - YYYY-MM-DD（如 2020-05-21.csv）

        Returns:
            解析出的 ``date`` 对象，未找到合法日期时返回 ``None``。
        """
        # 先尝试 YYYY-MM-DD 格式
        m = _DATE_DASH_RE.search(filename)
        if m:
            try:
                parts = m.group(1).split("-")
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass

        # 再尝试 YYYYMMDD 格式
        m = _DATE_RE.search(filename)
        if m is None:
            return None
        try:
            return date(
                int(m.group(1)[:4]),
                int(m.group(1)[4:6]),
                int(m.group(1)[6:8]),
            )
        except ValueError:
            return None

    # -----------------------------------------------------------------------
    # 板块类型映射
    # -----------------------------------------------------------------------

    def _map_dc_sector_type(self, idx_type: str) -> SectorType:
        """东方财富 ``idx_type`` 字段映射到 ``SectorType``。

        映射规则（使用包含匹配，按优先级排序）:
        - 包含 "行业" → INDUSTRY（必须在"概念"之前，避免误匹配）
        - 包含 "地区" 或 "地域" → REGION
        - 包含 "风格" → STYLE
        - 包含 "概念" → CONCEPT
        - 默认 → CONCEPT
        """
        lower = idx_type.lower()
        # 行业优先（避免被"概念"兜底）
        if "行业" in idx_type or "industry" in lower:
            return SectorType.INDUSTRY
        if "地区" in idx_type or "地域" in idx_type or "region" in lower:
            return SectorType.REGION
        if "风格" in idx_type or "style" in lower:
            return SectorType.STYLE
        if "概念" in idx_type or "concept" in lower:
            return SectorType.CONCEPT
        return SectorType.CONCEPT

    def _map_ti_sector_type(self, index_type: str) -> SectorType:
        """同花顺指数类型字段映射到 ``SectorType``。

        映射规则:
        - "概念指数" → CONCEPT
        - "行业指数" → INDUSTRY
        - "地区指数" → REGION
        - "风格指数" → STYLE
        - 默认 → CONCEPT
        """
        mapping: dict[str, SectorType] = {
            "概念指数": SectorType.CONCEPT,
            "行业指数": SectorType.INDUSTRY,
            "地区指数": SectorType.REGION,
            "风格指数": SectorType.STYLE,
        }
        return mapping.get(index_type, SectorType.CONCEPT)
