"""
本地分钟级K线数据导入服务

LocalKlineImportService 提供：
- scan_zip_files：递归扫描目录下所有 .zip 文件
- infer_symbol_and_freq：从文件路径推断股票代码和频率
- validate_bar：校验 KlineBar 数据质量
- parse_csv_content：解析 CSV 文本为 KlineBar 列表
- extract_and_parse_zip：内存解压 ZIP 并解析 CSV
- execute / check_incremental / mark_imported / update_progress / is_running：
  批量写入、增量导入与进度追踪（Task 3.1 实现）
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
import zipfile
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.kline import KlineBar
from app.services.data_engine.kline_repository import KlineRepository

logger = logging.getLogger(__name__)


class _AdjStopRequested(Exception):
    """复权因子导入停止信号异常，用于中断解析/写入流程。"""


class LocalKlineImportService:
    """本地分钟级K线数据导入服务"""

    VALID_FREQS: set[str] = {"1m", "5m", "15m", "30m", "60m"}
    VALID_MARKETS: set[str] = {"hushen", "jingshi", "zhishu"}
    BATCH_SIZE: int = 1000
    REDIS_PROGRESS_KEY: str = "import:local_kline:progress"
    REDIS_RESULT_KEY: str = "import:local_kline:result"
    REDIS_INCREMENTAL_KEY: str = "import:local_kline:files"
    REDIS_STOP_KEY: str = "import:local_kline:stop"
    PROGRESS_TTL: int = 86400  # 24h

    # 市场分类 → 目录名映射
    MARKET_DIR_MAP: dict[str, str] = {
        "hushen": "A股_分时数据_沪深",
        "jingshi": "A股_分时数据_京市",
        "zhishu": "A股_分时数据_指数",
    }

    # 频率 → 目录名映射（新格式：{N}分钟_按月归档）
    FREQ_DIR_MAP: dict[str, str] = {
        "1m": "1分钟_按月归档",
        "5m": "5分钟_按月归档",
        "15m": "15分钟_按月归档",
        "30m": "30分钟_按月归档",
        "60m": "60分钟_按月归档",
    }

    # 反向映射：新格式目录名 → 标准频率
    DIR_FREQ_MAP_NEW: dict[str, str] = {v: k for k, v in FREQ_DIR_MAP.items()}

    # 反向映射：市场目录名 → 市场分类键
    _MARKET_DIR_REVERSE: dict[str, str] = {v: k for k, v in MARKET_DIR_MAP.items()}

    # ------------------------------------------------------------------
    # 目录扫描
    # ------------------------------------------------------------------

    def scan_zip_files(
        self, base_dir: str, sub_dir: str | None = None,
    ) -> list[Path]:
        """
        递归扫描目录下所有 .zip 文件，返回 Path 列表。

        Args:
            base_dir: 根数据目录
            sub_dir: 可选子目录，拼接到 base_dir 后

        Returns:
            .zip 文件的 Path 列表
        """
        scan_path = Path(base_dir)
        if sub_dir:
            scan_path = scan_path / sub_dir

        if not scan_path.exists() or not scan_path.is_dir():
            logger.error("数据目录不存在或不可读: %s", scan_path)
            return []

        try:
            zip_files = sorted(scan_path.rglob("*.zip"))
        except PermissionError:
            logger.error("数据目录不可读: %s", scan_path)
            return []

        logger.info("扫描目录 %s，发现 %d 个 ZIP 文件", scan_path, len(zip_files))
        return zip_files

    def scan_market_zip_files(
        self,
        base_dir: str,
        markets: list[str] | None = None,
        freqs: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[tuple[Path, str, str]]:
        """
        按四级目录结构扫描ZIP文件：{市场目录}/{频率目录}/{月份目录}/{日期ZIP}

        支持日期级别过滤（YYYY-MM-DD）和月份级别过滤（YYYY-MM）。
        日期级别过滤时，从 ZIP 文件名中提取日期（YYYYMMDD）进行精确匹配。

        Args:
            base_dir: 根数据目录
            markets: 可选市场分类过滤列表（hushen/jingshi/zhishu），None 表示全部
            freqs: 可选频率过滤列表（1m/5m/15m/30m/60m），None 表示全部
            start_date: 可选起始日期（YYYY-MM-DD 或 YYYY-MM），None 表示不限
            end_date: 可选结束日期（YYYY-MM-DD 或 YYYY-MM），None 表示不限

        Returns:
            [(zip_path, market_key, freq_key), ...] 元组列表
        """
        import re

        base_path = Path(base_dir)
        if not base_path.exists() or not base_path.is_dir():
            logger.error("数据目录不存在或不可读: %s", base_path)
            return []

        # 解析日期过滤参数
        start_month: str | None = None
        end_month: str | None = None
        start_day: str | None = None  # YYYYMMDD format for ZIP name comparison
        end_day: str | None = None

        if start_date:
            parts = start_date.split("-")
            start_month = f"{parts[0]}-{parts[1]}"
            if len(parts) >= 3:
                start_day = f"{parts[0]}{parts[1]}{parts[2]}"

        if end_date:
            parts = end_date.split("-")
            end_month = f"{parts[0]}-{parts[1]}"
            if len(parts) >= 3:
                end_day = f"{parts[0]}{parts[1]}{parts[2]}"

        # 确定要扫描的市场分类
        target_markets = list(self.VALID_MARKETS) if markets is None else [
            m for m in markets if m in self.VALID_MARKETS
        ]

        # 确定要扫描的频率
        target_freqs = list(self.VALID_FREQS) if freqs is None else [
            f for f in freqs if f in self.VALID_FREQS
        ]

        # 正则：从 ZIP 文件名提取日期部分（YYYYMMDD）
        date_pattern = re.compile(r"(\d{8})")

        results: list[tuple[Path, str, str]] = []

        for market_key in target_markets:
            market_dir_name = self.MARKET_DIR_MAP[market_key]
            market_path = base_path / market_dir_name

            if not market_path.exists() or not market_path.is_dir():
                logger.warning("市场目录不存在，跳过: %s", market_path)
                continue

            market_count = 0

            for freq_key in target_freqs:
                freq_dir_name = self.FREQ_DIR_MAP[freq_key]
                freq_path = market_path / freq_dir_name

                if not freq_path.exists() or not freq_path.is_dir():
                    continue

                # 遍历月份目录
                try:
                    month_dirs = sorted(
                        d for d in freq_path.iterdir() if d.is_dir()
                    )
                except PermissionError:
                    logger.error("频率目录不可读: %s", freq_path)
                    continue

                for month_dir in month_dirs:
                    month_name = month_dir.name

                    # 月份范围过滤（字符串比较）
                    if start_month and month_name < start_month:
                        continue
                    if end_month and month_name > end_month:
                        continue

                    # 扫描月份目录下的 ZIP 文件
                    try:
                        zip_files = sorted(month_dir.glob("*.zip"))
                    except PermissionError:
                        logger.error("月份目录不可读: %s", month_dir)
                        continue

                    for zip_path in zip_files:
                        # 日期级别过滤：从 ZIP 文件名提取 YYYYMMDD
                        if start_day or end_day:
                            match = date_pattern.search(zip_path.stem)
                            if match:
                                zip_date = match.group(1)
                                if start_day and zip_date < start_day:
                                    continue
                                if end_day and zip_date > end_day:
                                    continue

                        results.append((zip_path, market_key, freq_key))
                        market_count += 1

            logger.info(
                "市场 %s（%s）扫描完成，发现 %d 个 ZIP 文件",
                market_key, market_dir_name, market_count,
            )

        logger.info("四级目录扫描完成，共发现 %d 个 ZIP 文件", len(results))
        return results

    # 中文目录名 → 标准频率映射（旧格式 + 新格式）
    DIR_FREQ_MAP: dict[str, str] = {
        "1分钟": "1m", "5分钟": "5m", "15分钟": "15m",
        "30分钟": "30m", "60分钟": "60m",
        "1分钟_按月归档": "1m", "5分钟_按月归档": "5m", "15分钟_按月归档": "15m",
        "30分钟_按月归档": "30m", "60分钟_按月归档": "60m",
    }
    # 文件名中的英文频率标识 → 标准频率映射
    FILE_FREQ_MAP: dict[str, str] = {
        "1min": "1m", "5min": "5m", "15min": "15m",
        "30min": "30m", "60min": "60m",
        "1m": "1m", "5m": "5m", "15m": "15m",
        "30m": "30m", "60m": "60m",
    }

    # ------------------------------------------------------------------
    # 路径推断
    # ------------------------------------------------------------------

    def infer_freq_from_path(self, zip_path: Path) -> str | None:
        """
        从 ZIP 文件路径推断K线频率。

        支持三种目录结构：
        1. {base_dir}/{中文频率目录}/{日期_频率}.zip        (如 /AData/5分钟/20250721_5min.zip)
        2. {base_dir}/{symbol}/{freq}.zip                   (如 /AData/000001/5m.zip)
        3. {base_dir}/{市场}/{N分钟_按月归档}/{月份}/{日期}.zip (四级结构)

        Returns:
            标准频率字符串（如 "5m"），无法推断时返回 None
        """
        # 优先从父目录中文名推断（旧格式短名 + 新格式长名）
        parent_name = zip_path.parent.name
        if parent_name in self.DIR_FREQ_MAP:
            return self.DIR_FREQ_MAP[parent_name]

        # 检查祖父目录（四级结构：月份目录的父目录是频率目录）
        grandparent_name = zip_path.parent.parent.name
        if grandparent_name in self.DIR_FREQ_MAP:
            return self.DIR_FREQ_MAP[grandparent_name]

        # 从文件名推断：尝试 stem 直接匹配或提取 _freq 后缀
        stem = zip_path.stem  # e.g. "20250721_5min" or "5m"
        if stem in self.FILE_FREQ_MAP:
            return self.FILE_FREQ_MAP[stem]
        # 提取下划线后的部分
        if "_" in stem:
            suffix = stem.rsplit("_", 1)[-1]
            if suffix in self.FILE_FREQ_MAP:
                return self.FILE_FREQ_MAP[suffix]

        # 直接当作 freq 尝试
        if stem in self.VALID_FREQS:
            return stem

        return None

    def infer_market_from_path(self, zip_path: Path) -> str | None:
        """
        从 ZIP 文件路径推断市场分类。

        检查路径中是否包含已知的市场目录名称。

        Returns:
            市场分类键（hushen/jingshi/zhishu），无法推断时返回 None
        """
        path_parts = zip_path.parts
        for part in path_parts:
            if part in self._MARKET_DIR_REVERSE:
                return self._MARKET_DIR_REVERSE[part]
        return None

    def infer_symbol_from_csv_name(self, csv_name: str, market: str = "hushen") -> str | None:
        """
        从 ZIP 内 CSV 文件名推断股票代码（市场感知），返回标准代码格式。

        支持格式：
        - hushen: sz000001.csv → 000001.SZ, sh600000.csv → 600000.SH
        - jingshi: bj920000.csv → 920000.BJ
        - zhishu: 000001.csv → 000001.SH（指数，自动推断交易所）

        Args:
            csv_name: CSV 文件名
            market: 市场分类（hushen/jingshi/zhishu），默认 hushen

        Returns:
            标准代码格式，无法推断时返回 None
        """
        import re
        from app.core.symbol_utils import to_standard
        basename = Path(csv_name).stem
        prefix_match = re.match(r"^(sz|sh|bj)", basename, flags=re.IGNORECASE)
        exchange = None
        if prefix_match:
            exchange = {"sz": "SZ", "sh": "SH", "bj": "BJ"}[prefix_match.group(1).lower()]
        cleaned = re.sub(r"^(sz|sh|bj)", "", basename, flags=re.IGNORECASE)
        if cleaned and cleaned.isdigit():
            try:
                return to_standard(cleaned, exchange)
            except ValueError:
                return None
        return None

    def infer_symbol_from_adj_csv_name(self, csv_name: str) -> str | None:
        """
        从复权因子 CSV 文件名推断股票代码，返回标准代码格式。

        支持格式：
        - 000001.SZ.csv → 000001.SZ
        - 600000.SH.csv → 600000.SH

        Args:
            csv_name: CSV 文件名

        Returns:
            标准代码格式，无法推断时返回 None
        """
        from app.core.symbol_utils import to_standard
        basename = Path(csv_name).name
        parts = basename.split(".")
        if len(parts) >= 2 and parts[0].isdigit():
            exchange = parts[1] if len(parts) >= 3 and parts[1] in ("SH", "SZ", "BJ") else None
            try:
                return to_standard(parts[0], exchange)
            except ValueError:
                return None
        return None

    def infer_symbol_and_freq(self, zip_path: Path) -> tuple[str, str] | None:
        """
        从文件路径推断频率（symbol 从 CSV 文件名推断，此处仅返回频率）。

        保留此方法以兼容旧调用，但新流程中 symbol 从 CSV 文件名推断。
        对于旧格式 {base_dir}/{symbol}/{freq}.zip 仍然支持。

        Returns:
            (symbol, freq) 元组，无法推断时返回 None
        """
        freq = self.infer_freq_from_path(zip_path)
        if freq is None:
            logger.warning("无法从路径推断频率: %s", zip_path)
            return None

        # 尝试从父目录推断 symbol（旧格式兼容）
        parent_name = zip_path.parent.name
        if parent_name not in self.DIR_FREQ_MAP and parent_name.isdigit():
            return (parent_name, freq)

        # 新格式：symbol 将从 CSV 文件名推断，这里返回占位符
        return ("__from_csv__", freq)

    # ------------------------------------------------------------------
    # 数据校验
    # ------------------------------------------------------------------

    def validate_bar(self, bar: KlineBar) -> bool:
        """
        校验单条 KlineBar 数据质量。

        规则:
        - open/high/low/close 必须为正数
        - low ≤ open ≤ high
        - low ≤ close ≤ high
        - volume ≥ 0
        - time 为有效 datetime
        - freq 在 VALID_FREQS 中

        Returns:
            True 表示校验通过
        """
        try:
            # 价格正数检查
            if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
                return False

            # high/low 关系检查
            if not (bar.low <= bar.open <= bar.high):
                return False
            if not (bar.low <= bar.close <= bar.high):
                return False

            # 成交量非负
            if bar.volume < 0:
                return False

            # 时间有效性
            if not isinstance(bar.time, datetime):
                return False

            # 频率合法性
            if bar.freq not in self.VALID_FREQS:
                return False

        except (TypeError, AttributeError):
            return False

        return True

    # ------------------------------------------------------------------
    # CSV 解析
    # ------------------------------------------------------------------

    def parse_csv_content(
        self, csv_text: str, symbol: str, freq: str, market: str = "hushen",
    ) -> tuple[list[KlineBar], int]:
        """
        解析 CSV 文本为 KlineBar 列表（市场感知）。

        支持两种 CSV 格式：
        1. 新格式（实际数据）: 时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额,...
        2. 旧格式: time,open,high,low,close,volume,amount

        指数数据（zhishu）无成交量列时，volume 自动设为 0。

        第一行为表头时自动检测列映射。

        Args:
            csv_text: CSV 文本内容
            symbol: 股票代码（可被 CSV 中的代码列覆盖）
            freq: K线频率
            market: 市场分类（hushen/jingshi/zhishu），默认 hushen

        Returns:
            (bars, skipped_count) 元组
        """
        bars: list[KlineBar] = []
        skipped = 0
        col_map: dict[str, int] | None = None

        reader = csv.reader(io.StringIO(csv_text))
        for line_no, row in enumerate(reader, start=1):
            # 跳过空行
            if not row or all(cell.strip() == "" for cell in row):
                continue

            # 检测表头行并建立列映射
            first_cell = row[0].strip().lstrip("\ufeff")
            if line_no == 1 and first_cell.lower() in (
                "time", "date", "datetime", "日期", "时间",
            ):
                col_map = self._build_column_map(row)
                continue

            # 至少需要足够的字段
            min_fields = 7
            if len(row) < min_fields:
                logger.warning(
                    "CSV 行字段不足，跳过: symbol=%s line=%d fields=%d",
                    symbol, line_no, len(row),
                )
                skipped += 1
                continue

            try:
                bar = self._parse_csv_row(row, symbol, freq, col_map, market)
            except (ValueError, InvalidOperation, IndexError) as exc:
                logger.warning(
                    "CSV 行解析失败，跳过: symbol=%s line=%d error=%s",
                    symbol, line_no, exc,
                )
                skipped += 1
                continue

            bars.append(bar)

        return bars, skipped

    @staticmethod
    def _build_column_map(header: list[str]) -> dict[str, int]:
        """从表头行构建列名→索引映射。"""
        # 标准化列名映射
        name_map = {
            "时间": "time", "日期": "time", "time": "time", "date": "time", "datetime": "time",
            "代码": "code", "股票代码": "code", "code": "code", "symbol": "code",
            "名称": "name", "股票名称": "name", "name": "name",
            "开盘价": "open", "开盘": "open", "open": "open",
            "收盘价": "close", "收盘": "close", "close": "close",
            "最高价": "high", "最高": "high", "high": "high",
            "最低价": "low", "最低": "low", "low": "low",
            "成交量": "volume", "volume": "volume",
            "成交额": "amount", "amount": "amount",
        }
        col_map: dict[str, int] = {}
        for idx, cell in enumerate(header):
            # 去掉 BOM 和空白
            key = cell.strip().lstrip("\ufeff").lower()
            if key in name_map:
                col_map[name_map[key]] = idx
        return col_map

    def _parse_csv_row(
        self, row: list[str], symbol: str, freq: str,
        col_map: dict[str, int] | None = None,
        market: str = "hushen",
    ) -> KlineBar:
        """将单行 CSV 数据解析为 KlineBar。

        如果有 col_map（从表头检测），按列名取值；否则按位置取值。
        指数市场（zhishu）CSV 无成交量列时，volume 设为 0。
        """
        if col_map:
            # 按列名映射取值
            time_str = row[col_map["time"]].strip()
            dt = self._parse_datetime(time_str)

            # symbol 可从 CSV 代码列覆盖
            csv_symbol = symbol
            if "code" in col_map:
                raw_code = row[col_map["code"]].strip()
                # 去掉 sz/sh/bj 前缀
                import re
                cleaned = re.sub(r"^(sz|sh|bj)", "", raw_code, flags=re.IGNORECASE)
                if cleaned and cleaned.isdigit():
                    csv_symbol = cleaned

            open_val = Decimal(row[col_map["open"]].strip())
            close_val = Decimal(row[col_map["close"]].strip())
            high_val = Decimal(row[col_map["high"]].strip())
            low_val = Decimal(row[col_map["low"]].strip())

            # 指数数据可能无成交量列，volume 设为 0
            if "volume" in col_map:
                volume_val = int(Decimal(row[col_map["volume"]].strip()))
            else:
                volume_val = 0

            amount_val = Decimal(row[col_map.get("amount", col_map.get("volume", -1))].strip()) if "amount" in col_map else Decimal("0")

            return KlineBar(
                time=dt, symbol=csv_symbol, freq=freq,
                open=open_val, high=high_val, low=low_val, close=close_val,
                volume=volume_val, amount=amount_val,
                turnover=Decimal("0"), vol_ratio=Decimal("0"),
                limit_up=None, limit_down=None, adj_type=0,
            )
        else:
            # 旧格式：按位置 time,open,high,low,close,volume,amount
            time_str = row[0].strip()
            dt = self._parse_datetime(time_str)
            return KlineBar(
                time=dt, symbol=symbol, freq=freq,
                open=Decimal(row[1].strip()),
                high=Decimal(row[2].strip()),
                low=Decimal(row[3].strip()),
                close=Decimal(row[4].strip()),
                volume=int(Decimal(row[5].strip())),
                amount=Decimal(row[6].strip()),
                turnover=Decimal("0"), vol_ratio=Decimal("0"),
                limit_up=None, limit_down=None, adj_type=0,
            )

    @staticmethod
    def _parse_datetime(time_str: str) -> datetime:
        """尝试多种格式解析时间字符串，返回 UTC 时区的 datetime 对象。
        
        对于日线数据（仅日期格式），统一使用 00:00:00 UTC 时间戳。
        对于分钟级数据（带时间格式），保持原有时间戳，但明确标记为 UTC。
        """
        from datetime import timezone
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y%m%d %H:%M:%S",
            "%Y%m%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                # 明确标记为 UTC 时区
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"无法解析时间: {time_str}")

    # ------------------------------------------------------------------
    # ZIP 解压与解析
    # ------------------------------------------------------------------

    def extract_and_parse_zip(
        self, zip_path: Path, freq_filter: set[str] | None = None,
        market: str = "hushen",
    ) -> tuple[list[KlineBar], int, int]:
        """
        内存解压 ZIP 并解析 CSV 内容。

        支持两种 ZIP 结构：
        1. 新格式：ZIP 内含多个 CSV（每个 CSV 对应一只股票），频率从路径推断
        2. 旧格式：ZIP 内含单个 CSV，symbol 和 freq 都从路径推断

        K线数据始终以不复权（adj_type=0）方式存储。

        Args:
            zip_path: ZIP 文件路径
            freq_filter: 可选频率过滤集合，仅处理匹配的频率
            market: 市场分类（hushen/jingshi/zhishu），默认 hushen

        Returns:
            (bars, parsed_count, skipped_count) 元组
        """
        result = self.infer_symbol_and_freq(zip_path)
        if result is None:
            logger.warning("跳过无法推断 symbol/freq 的文件: %s", zip_path)
            return [], 0, 0

        path_symbol, freq = result

        # 频率过滤
        if freq_filter and freq not in freq_filter:
            logger.debug("频率 %s 不在过滤列表中，跳过: %s", freq, zip_path)
            return [], 0, 0

        try:
            with open(zip_path, "rb") as f:
                zip_bytes = f.read()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                all_bars: list[KlineBar] = []
                total_parsed = 0
                total_skipped = 0

                for name in zf.namelist():
                    # 跳过目录条目
                    if name.endswith("/"):
                        continue

                    # 从 CSV 文件名推断 symbol
                    csv_symbol = self.infer_symbol_from_csv_name(name, market)
                    if csv_symbol is None:
                        # 回退到路径推断的 symbol
                        csv_symbol = path_symbol if path_symbol != "__from_csv__" else None
                    if csv_symbol is None or csv_symbol == "__from_csv__":
                        logger.warning("无法推断 symbol，跳过 CSV: %s in %s", name, zip_path)
                        continue

                    csv_bytes = zf.read(name)
                    # 尝试 UTF-8，回退到 GBK
                    try:
                        csv_text = csv_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        csv_text = csv_bytes.decode("gbk", errors="replace")

                    bars, skipped = self.parse_csv_content(csv_text, csv_symbol, freq, market)
                    all_bars.extend(bars)
                    total_parsed += len(bars)
                    total_skipped += skipped

                return all_bars, total_parsed, total_skipped

        except zipfile.BadZipFile:
            logger.error("ZIP 文件损坏，跳过: %s", zip_path)
            return [], 0, 0
        except OSError as exc:
            logger.error("读取 ZIP 文件失败: %s error=%s", zip_path, exc)
            return [], 0, 0

    # ------------------------------------------------------------------
    # 复权因子 ZIP 解压与解析
    # ------------------------------------------------------------------

    def parse_adj_factor_zip(
        self, zip_path: Path, adj_type: int,
        progress_callback: "Callable[[int, int, int], None] | None" = None,
    ) -> tuple[list[dict], int, int]:
        """
        解压并解析复权因子 ZIP 文件。

        ZIP 内含多个 CSV 文件，每个 CSV 对应一只股票的复权因子数据。
        CSV 表头：股票代码,交易日期,复权因子
        交易日期格式：YYYYMMDD

        Args:
            zip_path: 复权因子 ZIP 文件路径
            adj_type: 1=前复权, 2=后复权
            progress_callback: 可选回调 (parsed_csv_files, total_csv_files, total_parsed_rows)

        Returns:
            (factors, parsed_count, skipped_count)
            factors: [{"symbol": str, "trade_date": date, "adj_factor": Decimal, "adj_type": int}, ...]
        """
        factors: list[dict] = []
        total_parsed = 0
        total_skipped = 0

        try:
            with open(zip_path, "rb") as f:
                zip_bytes = f.read()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                csv_names = [n for n in zf.namelist() if not n.endswith("/")]
                total_csv_files = len(csv_names)
                parsed_csv_files = 0

                for name in csv_names:
                    # 从文件名推断 symbol
                    csv_symbol = self.infer_symbol_from_adj_csv_name(name)
                    if csv_symbol is None:
                        logger.warning(
                            "无法从复权因子 CSV 文件名推断 symbol，跳过: %s in %s",
                            name, zip_path,
                        )
                        total_skipped += 1
                        parsed_csv_files += 1
                        continue

                    csv_bytes = zf.read(name)
                    try:
                        csv_text = csv_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        csv_text = csv_bytes.decode("gbk", errors="replace")

                    reader = csv.reader(io.StringIO(csv_text))
                    header_skipped = False

                    for line_no, row in enumerate(reader, start=1):
                        if not row or all(cell.strip() == "" for cell in row):
                            continue

                        # 跳过表头行
                        if not header_skipped:
                            first_cell = row[0].strip().lstrip("\ufeff")
                            if first_cell in ("股票代码", "code", "symbol"):
                                header_skipped = True
                                continue
                            header_skipped = True

                        if len(row) < 3:
                            total_skipped += 1
                            continue

                        try:
                            trade_date_str = row[1].strip()
                            trade_date_val = date(
                                int(trade_date_str[:4]),
                                int(trade_date_str[4:6]),
                                int(trade_date_str[6:8]),
                            )
                            adj_factor_val = Decimal(row[2].strip())

                            factors.append({
                                "symbol": csv_symbol,
                                "trade_date": trade_date_val,
                                "adj_factor": adj_factor_val,
                                "adj_type": adj_type,
                            })
                            total_parsed += 1
                        except (ValueError, InvalidOperation, IndexError) as exc:
                            logger.warning(
                                "复权因子行解析失败，跳过: file=%s line=%d error=%s",
                                name, line_no, exc,
                            )
                            total_skipped += 1

                    parsed_csv_files += 1
                    # 每解析完一个 CSV 文件回调一次进度
                    if progress_callback and parsed_csv_files % 50 == 0:
                        progress_callback(parsed_csv_files, total_csv_files, total_parsed)

                # 最终回调确保 100%
                if progress_callback:
                    progress_callback(parsed_csv_files, total_csv_files, total_parsed)

        except zipfile.BadZipFile:
            logger.error("复权因子 ZIP 文件损坏: %s", zip_path)
            return [], 0, 0
        except OSError as exc:
            logger.error("读取复权因子 ZIP 文件失败: %s error=%s", zip_path, exc)
            return [], 0, 0

        return factors, total_parsed, total_skipped

    # ------------------------------------------------------------------
    # 增量导入
    # ------------------------------------------------------------------

    async def check_incremental(self, zip_path: Path) -> bool:
        """
        检查文件是否可跳过（已导入且 mtime 未变化）。

        Args:
            zip_path: ZIP 文件路径

        Returns:
            True 表示文件应被跳过（已导入且 mtime 未变化）
        """
        client = get_redis_client()
        try:
            cached_mtime = await client.hget(
                self.REDIS_INCREMENTAL_KEY, str(zip_path),
            )
            if cached_mtime is None:
                return False
            current_mtime = str(zip_path.stat().st_mtime)
            return cached_mtime == current_mtime
        finally:
            await client.aclose()

    async def mark_imported(self, zip_path: Path) -> None:
        """将文件路径和 mtime 写入 Redis 增量缓存。"""
        client = get_redis_client()
        try:
            current_mtime = str(zip_path.stat().st_mtime)
            await client.hset(
                self.REDIS_INCREMENTAL_KEY, str(zip_path), current_mtime,
            )
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # 进度追踪
    # ------------------------------------------------------------------

    # 心跳超时阈值（秒）：超过此时间未更新心跳，认为任务已死亡
    HEARTBEAT_TIMEOUT: int = 120

    async def update_progress(self, **kwargs) -> None:
        """更新 Redis 中的导入进度 JSON，合并 kwargs 到现有进度。

        每次更新自动写入 heartbeat 时间戳，用于僵尸任务检测。
        """
        client = get_redis_client()
        try:
            raw = await client.get(self.REDIS_PROGRESS_KEY)
            progress = json.loads(raw) if raw else {}
            progress.update(kwargs)
            progress["heartbeat"] = time.time()
            await client.set(
                self.REDIS_PROGRESS_KEY,
                json.dumps(progress, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        finally:
            await client.aclose()

    async def is_running(self) -> bool:
        """检查是否有导入任务正在运行（包括 pending 等待执行状态）。

        通过心跳机制检测僵尸任务：如果 status 为 running/pending 但心跳超时
        或缺失心跳字段（旧版数据），自动将状态标记为 failed 并返回 False。
        """
        client = get_redis_client()
        try:
            raw = await client.get(self.REDIS_PROGRESS_KEY)
            if not raw:
                return False
            progress = json.loads(raw)
            status = progress.get("status")
            if status not in ("running", "pending"):
                return False
            # 心跳超时检测：进程异常终止后状态卡在 running/pending
            heartbeat = progress.get("heartbeat")
            if heartbeat is None:
                # 旧版数据无心跳字段，视为僵尸任务
                logger.warning(
                    "K线导入任务无心跳字段（旧版数据），判定为僵尸任务，自动清理状态",
                )
                progress["status"] = "failed"
                progress["error"] = "任务异常终止（无心跳记录）"
                await client.set(
                    self.REDIS_PROGRESS_KEY,
                    json.dumps(progress, ensure_ascii=False),
                    ex=self.PROGRESS_TTL,
                )
                return False
            elapsed = time.time() - heartbeat
            if elapsed > self.HEARTBEAT_TIMEOUT:
                logger.warning(
                    "K线导入任务心跳超时（%.0f 秒），判定为僵尸任务，自动清理状态",
                    elapsed,
                )
                progress["status"] = "failed"
                progress["error"] = f"任务异常终止（心跳超时 {int(elapsed)} 秒）"
                await client.set(
                    self.REDIS_PROGRESS_KEY,
                    json.dumps(progress, ensure_ascii=False),
                    ex=self.PROGRESS_TTL,
                )
                return False
            return True
        finally:
            await client.aclose()

    async def request_stop(self) -> None:
        """发送K线导入停止信号。"""
        client = get_redis_client()
        try:
            await client.set(self.REDIS_STOP_KEY, "1", ex=3600)
        finally:
            await client.aclose()

    async def _check_stop_signal(self) -> bool:
        """检查是否收到停止信号。"""
        client = get_redis_client()
        try:
            val = await client.get(self.REDIS_STOP_KEY)
            return val is not None
        finally:
            await client.aclose()

    async def _clear_stop_signal(self) -> None:
        """清除停止信号。"""
        client = get_redis_client()
        try:
            await client.delete(self.REDIS_STOP_KEY)
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # 主执行流程
    # ------------------------------------------------------------------

    async def execute(
        self,
        markets: list[str] | None = None,
        freqs: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        force: bool = False,
    ) -> dict:
        """
        执行K线数据导入流程，返回结果摘要字典。

        K线数据始终以不复权（adj_type=0）方式存储。

        Args:
            markets: 可选市场分类过滤列表（hushen/jingshi/zhishu）
            freqs: 可选频率过滤列表
            start_date: 可选起始日期（YYYY-MM-DD 或 YYYY-MM）
            end_date: 可选结束日期（YYYY-MM-DD 或 YYYY-MM）
            force: 强制全量导入，忽略增量缓存

        Returns:
            结果摘要字典
        """
        start_time = time.time()
        base_dir = settings.local_kline_data_dir

        # 检查基础目录是否存在
        base_path = Path(base_dir)
        if not base_path.exists() or not base_path.is_dir():
            result = {
                "status": "failed",
                "error": "目录不存在或不可读",
                "total_files": 0,
                "success_files": 0,
                "failed_files": 0,
                "total_parsed": 0,
                "total_inserted": 0,
                "total_skipped": 0,
                "elapsed_seconds": round(time.time() - start_time, 2),
                "skipped_files": 0,
                "failed_details": [],
                "market_stats": {},
            }
            return result

        # 按四级目录结构扫描 ZIP 文件
        scan_results = self.scan_market_zip_files(
            base_dir, markets, freqs, start_date, end_date,
        )

        # 初始化每市场统计
        market_stats: dict[str, dict] = {
            m: {"files": 0, "inserted": 0} for m in self.VALID_MARKETS
        }

        # 初始化进度
        await self.update_progress(
            status="running",
            total_files=len(scan_results),
            processed_files=0,
            success_files=0,
            failed_files=0,
            total_parsed=0,
            total_inserted=0,
            total_skipped=0,
            elapsed_seconds=0,
            started_at=datetime.now().isoformat(),
            current_file="",
            failed_details=[],
            skipped_files=0,
            market_stats=market_stats,
        )

        # 统计
        success_files = 0
        failed_files = 0
        total_parsed = 0
        total_inserted = 0
        total_skipped = 0
        skipped_files = 0
        failed_details: list[dict] = []

        repo = KlineRepository()

        # 清除可能残留的停止信号
        await self._clear_stop_signal()

        for idx, (zip_path, market, freq) in enumerate(scan_results):
            # 检查停止信号
            if await self._check_stop_signal():
                logger.info("收到停止信号，终止K线导入")
                await self._clear_stop_signal()
                elapsed = round(time.time() - start_time, 2)
                await self.update_progress(
                    status="stopped",
                    processed_files=idx,
                    elapsed_seconds=elapsed,
                )
                result = {
                    "status": "stopped",
                    "total_files": len(scan_results),
                    "success_files": success_files,
                    "failed_files": failed_files,
                    "total_parsed": total_parsed,
                    "total_inserted": total_inserted,
                    "total_skipped": total_skipped,
                    "elapsed_seconds": elapsed,
                    "skipped_files": skipped_files,
                    "failed_details": failed_details,
                    "market_stats": market_stats,
                }
                client = get_redis_client()
                try:
                    await client.set(
                        self.REDIS_RESULT_KEY,
                        json.dumps(result, ensure_ascii=False),
                        ex=self.PROGRESS_TTL,
                    )
                finally:
                    await client.aclose()
                return result

            # 更新当前文件
            await self.update_progress(
                current_file=str(zip_path),
                processed_files=idx,
                elapsed_seconds=round(time.time() - start_time, 2),
            )

            # 增量检查
            if not force:
                try:
                    should_skip = await self.check_incremental(zip_path)
                except Exception:
                    should_skip = False
                if should_skip:
                    skipped_files += 1
                    await self.update_progress(
                        skipped_files=skipped_files,
                        processed_files=idx + 1,
                        elapsed_seconds=round(time.time() - start_time, 2),
                    )
                    continue

            # 解压解析 + 流式写入（逐 CSV 处理，避免内存溢出）
            try:
                parsed_for_file = 0
                skipped_for_file = 0
                inserted_for_file = 0

                result_infer = self.infer_symbol_and_freq(zip_path)
                if result_infer is None:
                    logger.warning("跳过无法推断 symbol/freq 的文件: %s", zip_path)
                    skipped_files += 1
                    await self.update_progress(
                        skipped_files=skipped_files,
                        processed_files=idx + 1,
                        elapsed_seconds=round(time.time() - start_time, 2),
                    )
                    continue

                path_symbol, freq_val = result_infer

                with open(zip_path, "rb") as f:
                    zip_bytes = f.read()

                with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                    _stop_requested = False
                    for name in zf.namelist():
                        # 每个 CSV 文件处理前检查停止信号
                        if await self._check_stop_signal():
                            _stop_requested = True
                            break

                        if name.endswith("/"):
                            continue

                        csv_symbol = self.infer_symbol_from_csv_name(name, market)
                        if csv_symbol is None:
                            csv_symbol = path_symbol if path_symbol != "__from_csv__" else None
                        if csv_symbol is None or csv_symbol == "__from_csv__":
                            continue

                        csv_bytes = zf.read(name)
                        try:
                            csv_text = csv_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            csv_text = csv_bytes.decode("gbk", errors="replace")
                        del csv_bytes  # 释放内存

                        bars, skipped = self.parse_csv_content(csv_text, csv_symbol, freq_val, market)
                        del csv_text  # 释放内存

                        valid_bars = [b for b in bars if self.validate_bar(b)]
                        del bars  # 释放内存

                        parsed_for_file += len(valid_bars) + skipped
                        skipped_for_file += skipped + (len(valid_bars) - len(valid_bars))

                        # 立即分批写入 DB
                        for i in range(0, len(valid_bars), self.BATCH_SIZE):
                            batch = valid_bars[i : i + self.BATCH_SIZE]
                            inserted = await repo.bulk_insert(batch)
                            inserted_for_file += inserted
                            # 每批写入后更新心跳，防止被误判为僵尸任务
                            await self.update_progress(
                                elapsed_seconds=round(time.time() - start_time, 2),
                            )
                        del valid_bars  # 释放内存

                del zip_bytes  # 释放内存

                # 如果在 ZIP 内部收到停止信号，跳出文件循环
                if _stop_requested:
                    logger.info("收到停止信号，终止K线导入（ZIP 内部）")
                    await self._clear_stop_signal()
                    elapsed = round(time.time() - start_time, 2)
                    await self.update_progress(status="stopped", processed_files=idx + 1, elapsed_seconds=elapsed)
                    result = {
                        "status": "stopped",
                        "total_files": len(scan_results),
                        "success_files": success_files,
                        "failed_files": failed_files,
                        "total_parsed": total_parsed,
                        "total_inserted": total_inserted,
                        "total_skipped": total_skipped,
                        "elapsed_seconds": elapsed,
                        "skipped_files": skipped_files,
                        "failed_details": failed_details,
                        "market_stats": market_stats,
                    }
                    client = get_redis_client()
                    try:
                        await client.set(self.REDIS_RESULT_KEY, json.dumps(result, ensure_ascii=False), ex=self.PROGRESS_TTL)
                    finally:
                        await client.aclose()
                    return result

                total_parsed += parsed_for_file
                total_skipped += skipped_for_file

            except zipfile.BadZipFile:
                logger.error("ZIP 文件损坏，跳过: %s", zip_path)
                failed_files += 1
                failed_details.append({"path": str(zip_path), "error": "ZIP 文件损坏"})
                await self.update_progress(
                    failed_files=failed_files,
                    failed_details=failed_details,
                )
                continue
            except Exception as exc:
                logger.error("处理 ZIP 文件异常: %s error=%s", zip_path, exc)
                failed_files += 1
                failed_details.append({"path": str(zip_path), "error": str(exc)})
                await self.update_progress(
                    failed_files=failed_files,
                    failed_details=failed_details,
                )
                continue

            total_inserted += inserted_for_file
            success_files += 1

            # 更新每市场统计
            market_stats[market]["files"] += 1
            market_stats[market]["inserted"] += inserted_for_file

            # 只有实际解析到数据时才标记为已导入，避免空解析污染增量缓存
            if parsed_for_file > 0:
                try:
                    await self.mark_imported(zip_path)
                except Exception as exc:
                    logger.warning("标记已导入失败: %s error=%s", zip_path, exc)

            logger.info(
                "文件导入完成: %s market=%s parsed=%d inserted=%d",
                zip_path, market, parsed_for_file, inserted_for_file,
            )

            # 更新进度
            await self.update_progress(
                processed_files=idx + 1,
                success_files=success_files,
                failed_files=failed_files,
                total_parsed=total_parsed,
                total_inserted=total_inserted,
                total_skipped=total_skipped,
                skipped_files=skipped_files,
                elapsed_seconds=round(time.time() - start_time, 2),
                failed_details=failed_details,
                market_stats=market_stats,
            )

        elapsed = round(time.time() - start_time, 2)

        result = {
            "status": "completed",
            "total_files": len(scan_results),
            "success_files": success_files,
            "failed_files": failed_files,
            "total_parsed": total_parsed,
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "elapsed_seconds": elapsed,
            "skipped_files": skipped_files,
            "failed_details": failed_details,
            "market_stats": market_stats,
        }

        # 写入最终进度
        await self.update_progress(
            status="completed",
            processed_files=len(scan_results),
            elapsed_seconds=elapsed,
            market_stats=market_stats,
        )

        # 写入结果摘要到 Redis（24h TTL）
        client = get_redis_client()
        try:
            await client.set(
                self.REDIS_RESULT_KEY,
                json.dumps(result, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        finally:
            await client.aclose()

        logger.info(
            "导入任务完成: total=%d success=%d failed=%d parsed=%d inserted=%d skipped=%d elapsed=%.2fs",
            len(scan_results), success_files, failed_files,
            total_parsed, total_inserted, total_skipped, elapsed,
        )

        return result

    # ------------------------------------------------------------------
    # 复权因子独立导入
    # ------------------------------------------------------------------

    REDIS_ADJ_PROGRESS_KEY: str = "import:adj_factor:progress"
    REDIS_ADJ_RESULT_KEY: str = "import:adj_factor:result"
    REDIS_ADJ_INCREMENTAL_KEY: str = "import:adj_factor:files"
    REDIS_ADJ_STOP_KEY: str = "import:adj_factor:stop"

    async def _update_adj_progress(self, **kwargs) -> None:
        """更新复权因子导入进度到 Redis。

        每次更新自动写入 heartbeat 时间戳，用于僵尸任务检测。
        """
        client = get_redis_client()
        try:
            raw = await client.get(self.REDIS_ADJ_PROGRESS_KEY)
            progress = json.loads(raw) if raw else {}
            progress.update(kwargs)
            progress["heartbeat"] = time.time()
            await client.set(
                self.REDIS_ADJ_PROGRESS_KEY,
                json.dumps(progress, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        finally:
            await client.aclose()

    async def request_adj_stop(self) -> None:
        """发送复权因子导入停止信号。"""
        client = get_redis_client()
        try:
            await client.set(self.REDIS_ADJ_STOP_KEY, "1", ex=3600)
        finally:
            await client.aclose()

    async def _check_adj_stop_signal(self) -> bool:
        """检查复权因子导入停止信号。"""
        client = get_redis_client()
        try:
            val = await client.get(self.REDIS_ADJ_STOP_KEY)
            return val is not None
        finally:
            await client.aclose()

    async def _clear_adj_stop_signal(self) -> None:
        """清除复权因子导入停止信号。"""
        client = get_redis_client()
        try:
            await client.delete(self.REDIS_ADJ_STOP_KEY)
        finally:
            await client.aclose()

    async def _stream_adj_factor_zip(
        self,
        zip_path: Path,
        adj_type: int,
        adj_repo: "AdjFactorRepository",
        start_time: float,
    ) -> tuple[int, int, int]:
        """
        流式解压解析并写入复权因子 ZIP 文件。

        边解析边写入数据库，避免将 1750 万条数据全部加载到内存。
        每积累 STREAM_BATCH_SIZE 条记录就写入一次数据库。

        Args:
            zip_path: 复权因子 ZIP 文件路径
            adj_type: 1=前复权, 2=后复权
            adj_repo: 复权因子仓储实例
            start_time: 任务开始时间戳

        Returns:
            (total_parsed, total_inserted, total_skipped)

        Raises:
            _AdjStopRequested: 收到停止信号时抛出
        """
        import asyncio

        STREAM_BATCH = 50000  # 每 5 万条写入一次 DB
        buffer: list[dict] = []
        total_parsed = 0
        total_inserted = 0
        total_skipped = 0

        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_names = [n for n in zf.namelist() if not n.endswith("/")]
            total_csv_files = len(csv_names)
            parsed_csv_files = 0

            for name in csv_names:
                csv_symbol = self.infer_symbol_from_adj_csv_name(name)
                if csv_symbol is None:
                    total_skipped += 1
                    parsed_csv_files += 1
                    continue

                csv_bytes_data = zf.read(name)
                try:
                    csv_text = csv_bytes_data.decode("utf-8")
                except UnicodeDecodeError:
                    csv_text = csv_bytes_data.decode("gbk", errors="replace")

                reader = csv.reader(io.StringIO(csv_text))
                header_skipped = False

                for _line_no, row in enumerate(reader, start=1):
                    if not row or all(cell.strip() == "" for cell in row):
                        continue
                    if not header_skipped:
                        first_cell = row[0].strip().lstrip("\ufeff")
                        if first_cell in ("股票代码", "code", "symbol"):
                            header_skipped = True
                            continue
                        header_skipped = True
                    if len(row) < 3:
                        total_skipped += 1
                        continue
                    try:
                        trade_date_str = row[1].strip()
                        trade_date_val = date(
                            int(trade_date_str[:4]),
                            int(trade_date_str[4:6]),
                            int(trade_date_str[6:8]),
                        )
                        adj_factor_val = Decimal(row[2].strip())
                        buffer.append({
                            "symbol": csv_symbol,
                            "trade_date": trade_date_val,
                            "adj_factor": adj_factor_val,
                            "adj_type": adj_type,
                        })
                        total_parsed += 1
                    except (ValueError, InvalidOperation, IndexError):
                        total_skipped += 1

                # 缓冲区满时写入 DB
                if len(buffer) >= STREAM_BATCH:
                    batch_inserted = await adj_repo.bulk_insert(buffer)
                    total_inserted += batch_inserted
                    buffer.clear()

                parsed_csv_files += 1

                # 每 50 个文件更新进度、检查停止信号
                if parsed_csv_files % 50 == 0:
                    await asyncio.sleep(0)
                    pct = round(parsed_csv_files / total_csv_files * 100, 1)
                    await self._update_adj_progress(
                        current_step=f"导入中（{parsed_csv_files:,}/{total_csv_files:,} 文件 {pct}%，已解析 {total_parsed:,}，已入库 {total_inserted:,}）",
                        elapsed_seconds=round(time.time() - start_time, 2),
                    )
                    if await self._check_adj_stop_signal():
                        logger.info("导入阶段收到停止信号")
                        await self._clear_adj_stop_signal()
                        # 写入剩余缓冲区
                        if buffer:
                            batch_inserted = await adj_repo.bulk_insert(buffer)
                            total_inserted += batch_inserted
                            buffer.clear()
                        raise _AdjStopRequested()

            # 写入最后一批缓冲区
            if buffer:
                batch_inserted = await adj_repo.bulk_insert(buffer)
                total_inserted += batch_inserted
                buffer.clear()

        # 最终进度
        await self._update_adj_progress(
            current_step=f"导入完成（{total_csv_files:,} 文件，{total_parsed:,} 条，入库 {total_inserted:,}）",
            elapsed_seconds=round(time.time() - start_time, 2),
        )

        return total_parsed, total_inserted, total_skipped

    async def execute_adj_factors(
        self,
        adj_factors: list[str] | None = None,
    ) -> dict:
        """
        独立执行复权因子导入流程。

        Args:
            adj_factors: 复权因子类型列表（qfq/hfq）

        Returns:
            结果摘要字典
        """
        start_time = time.time()
        base_dir = settings.local_kline_data_dir

        if not adj_factors:
            return {"status": "failed", "error": "未指定复权因子类型", "adj_factor_stats": {}, "elapsed_seconds": 0, "total_types": 0, "completed_types": 0, "current_type": ""}

        total_types = len(adj_factors)

        # 写入运行中状态
        await self._update_adj_progress(
            status="running",
            adj_factor_stats={},
            elapsed_seconds=0,
            total_types=total_types,
            completed_types=0,
            current_type="",
            current_step="",
        )

        from app.services.data_engine.adj_factor_repository import AdjFactorRepository

        adj_type_map: dict[str, tuple[int, str]] = {
            "qfq": (1, "复权因子_前复权.zip"),
            "hfq": (2, "复权因子_后复权.zip"),
        }
        adj_label_map: dict[str, str] = {"qfq": "前复权", "hfq": "后复权"}

        adj_repo = AdjFactorRepository()
        adj_factor_stats: dict[str, dict] = {}
        completed_types = 0

        # 清除可能残留的停止信号
        await self._clear_adj_stop_signal()

        for adj_key in adj_factors:
            # 检查停止信号
            if await self._check_adj_stop_signal():
                logger.info("收到停止信号，终止复权因子导入")
                await self._clear_adj_stop_signal()
                elapsed = round(time.time() - start_time, 2)
                result = {
                    "status": "stopped",
                    "adj_factor_stats": adj_factor_stats,
                    "elapsed_seconds": elapsed,
                    "total_types": total_types,
                    "completed_types": completed_types,
                    "current_type": "",
                    "current_step": "",
                }
                await self._update_adj_progress(**result)
                client = get_redis_client()
                try:
                    await client.set(
                        self.REDIS_ADJ_RESULT_KEY,
                        json.dumps(result, ensure_ascii=False),
                        ex=self.PROGRESS_TTL,
                    )
                finally:
                    await client.aclose()
                return result

            if adj_key not in adj_type_map:
                logger.warning("未知的复权因子类型，跳过: %s", adj_key)
                continue

            adj_type_val, zip_name = adj_type_map[adj_key]
            adj_zip_path = Path(base_dir) / "复权因子" / zip_name
            label = adj_label_map.get(adj_key, adj_key)

            # 更新当前处理的类型
            await self._update_adj_progress(
                current_type=label,
                current_step="检查文件",
                elapsed_seconds=round(time.time() - start_time, 2),
            )

            if not adj_zip_path.exists():
                logger.error("复权因子 ZIP 文件不存在: %s", adj_zip_path)
                adj_factor_stats[adj_key] = {
                    "status": "failed",
                    "error": "文件不存在",
                    "parsed": 0,
                    "inserted": 0,
                    "skipped": 0,
                }
                completed_types += 1
                await self._update_adj_progress(
                    adj_factor_stats=adj_factor_stats,
                    completed_types=completed_types,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                continue

            # 增量检查：文件 mtime 未变化则跳过
            try:
                current_mtime = str(adj_zip_path.stat().st_mtime)
                client = get_redis_client()
                try:
                    cached_mtime = await client.hget(
                        self.REDIS_ADJ_INCREMENTAL_KEY, str(adj_zip_path),
                    )
                finally:
                    await client.aclose()

                if cached_mtime and cached_mtime == current_mtime:
                    logger.info("复权因子文件未变化，跳过: %s", adj_zip_path)
                    adj_factor_stats[adj_key] = {
                        "status": "skipped",
                        "parsed": 0,
                        "inserted": 0,
                        "skipped": 0,
                    }
                    completed_types += 1
                    await self._update_adj_progress(
                        adj_factor_stats=adj_factor_stats,
                        completed_types=completed_types,
                        current_step="已跳过（文件未变化）",
                        elapsed_seconds=round(time.time() - start_time, 2),
                    )
                    continue
            except Exception:
                pass  # 增量检查失败不影响导入

            # 流式导入：边解析边写入，避免内存溢出
            await self._update_adj_progress(
                current_step="导入中",
                elapsed_seconds=round(time.time() - start_time, 2),
            )

            try:
                adj_parsed, adj_inserted, adj_skipped = await self._stream_adj_factor_zip(
                    adj_zip_path, adj_type_val, adj_repo, start_time,
                )
            except _AdjStopRequested:
                adj_factor_stats[adj_key] = {
                    "status": "stopped",
                    "parsed": 0,
                    "inserted": 0,
                    "skipped": 0,
                }
                elapsed = round(time.time() - start_time, 2)
                result = {
                    "status": "stopped",
                    "adj_factor_stats": adj_factor_stats,
                    "elapsed_seconds": elapsed,
                    "total_types": total_types,
                    "completed_types": completed_types,
                    "current_type": "",
                    "current_step": "",
                }
                await self._update_adj_progress(**result)
                client = get_redis_client()
                try:
                    await client.set(
                        self.REDIS_ADJ_RESULT_KEY,
                        json.dumps(result, ensure_ascii=False),
                        ex=self.PROGRESS_TTL,
                    )
                finally:
                    await client.aclose()
                return result
            except Exception as exc:
                logger.error("复权因子导入异常: %s error=%s", adj_zip_path, exc)
                adj_factor_stats[adj_key] = {
                    "status": "failed",
                    "error": str(exc),
                    "parsed": 0,
                    "inserted": 0,
                    "skipped": 0,
                }
                completed_types += 1
                await self._update_adj_progress(
                    adj_factor_stats=adj_factor_stats,
                    completed_types=completed_types,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                continue

            adj_factor_stats[adj_key] = {
                "status": "completed",
                "parsed": adj_parsed,
                "inserted": adj_inserted,
                "skipped": adj_skipped,
            }
            completed_types += 1

            await self._update_adj_progress(
                adj_factor_stats=adj_factor_stats,
                completed_types=completed_types,
                elapsed_seconds=round(time.time() - start_time, 2),
            )

            logger.info(
                "复权因子导入完成: type=%s parsed=%d inserted=%d skipped=%d",
                adj_key, adj_parsed, adj_inserted, adj_skipped,
            )

            # 标记文件已导入（记录 mtime）
            try:
                client = get_redis_client()
                try:
                    mtime = str(adj_zip_path.stat().st_mtime)
                    await client.hset(
                        self.REDIS_ADJ_INCREMENTAL_KEY, str(adj_zip_path), mtime,
                    )
                finally:
                    await client.aclose()
            except Exception as exc:
                logger.warning("标记复权因子已导入失败: %s error=%s", adj_zip_path, exc)

        elapsed = round(time.time() - start_time, 2)

        result = {
            "status": "completed",
            "adj_factor_stats": adj_factor_stats,
            "elapsed_seconds": elapsed,
            "total_types": total_types,
            "completed_types": completed_types,
            "current_type": "",
            "current_step": "",
        }

        # 写入最终结果到 Redis
        client = get_redis_client()
        try:
            await client.set(
                self.REDIS_ADJ_PROGRESS_KEY,
                json.dumps(result, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
            await client.set(
                self.REDIS_ADJ_RESULT_KEY,
                json.dumps(result, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        finally:
            await client.aclose()

        logger.info("复权因子导入任务完成: elapsed=%.2fs stats=%s", elapsed, adj_factor_stats)
        return result
