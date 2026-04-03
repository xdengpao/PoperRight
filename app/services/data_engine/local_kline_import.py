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
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.kline import KlineBar
from app.services.data_engine.kline_repository import KlineRepository

logger = logging.getLogger(__name__)


class LocalKlineImportService:
    """本地分钟级K线数据导入服务"""

    VALID_FREQS: set[str] = {"1m", "5m", "15m", "30m", "60m"}
    BATCH_SIZE: int = 1000
    REDIS_PROGRESS_KEY: str = "import:local_kline:progress"
    REDIS_RESULT_KEY: str = "import:local_kline:result"
    REDIS_INCREMENTAL_KEY: str = "import:local_kline:files"
    PROGRESS_TTL: int = 86400  # 24h

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

    # 中文目录名 → 标准频率映射
    DIR_FREQ_MAP: dict[str, str] = {
        "1分钟": "1m", "5分钟": "5m", "15分钟": "15m",
        "30分钟": "30m", "60分钟": "60m",
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

        支持两种目录结构：
        1. {base_dir}/{中文频率目录}/{日期_频率}.zip  (如 /AData/5分钟/20250721_5min.zip)
        2. {base_dir}/{symbol}/{freq}.zip             (如 /AData/000001/5m.zip)

        Returns:
            标准频率字符串（如 "5m"），无法推断时返回 None
        """
        # 优先从父目录中文名推断
        parent_name = zip_path.parent.name
        if parent_name in self.DIR_FREQ_MAP:
            return self.DIR_FREQ_MAP[parent_name]

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

    def infer_symbol_from_csv_name(self, csv_name: str) -> str | None:
        """
        从 ZIP 内 CSV 文件名推断股票代码。

        支持格式：
        - sz000001.csv → 000001
        - sh600000.csv → 600000
        - 000001.csv   → 000001

        Returns:
            纯数字股票代码，无法推断时返回 None
        """
        import re
        basename = Path(csv_name).stem  # e.g. "sz000001"
        # 去掉 sh/sz/bj 前缀
        cleaned = re.sub(r"^(sz|sh|bj)", "", basename, flags=re.IGNORECASE)
        # 验证是纯数字
        if cleaned and cleaned.isdigit():
            return cleaned
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
        self, csv_text: str, symbol: str, freq: str,
    ) -> tuple[list[KlineBar], int]:
        """
        解析 CSV 文本为 KlineBar 列表。

        支持两种 CSV 格式：
        1. 新格式（实际数据）: 时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额,...
        2. 旧格式: time,open,high,low,close,volume,amount

        第一行为表头时自动检测列映射。

        Args:
            csv_text: CSV 文本内容
            symbol: 股票代码（可被 CSV 中的代码列覆盖）
            freq: K线频率

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
                bar = self._parse_csv_row(row, symbol, freq, col_map)
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
    ) -> KlineBar:
        """将单行 CSV 数据解析为 KlineBar。

        如果有 col_map（从表头检测），按列名取值；否则按位置取值。
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
            volume_val = int(Decimal(row[col_map["volume"]].strip()))
            amount_val = Decimal(row[col_map.get("amount", col_map["volume"])].strip()) if "amount" in col_map else Decimal("0")

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
        """尝试多种格式解析时间字符串。"""
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
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析时间: {time_str}")

    # ------------------------------------------------------------------
    # ZIP 解压与解析
    # ------------------------------------------------------------------

    def extract_and_parse_zip(
        self, zip_path: Path, freq_filter: set[str] | None = None,
    ) -> tuple[list[KlineBar], int, int]:
        """
        内存解压 ZIP 并解析 CSV 内容。

        支持两种 ZIP 结构：
        1. 新格式：ZIP 内含多个 CSV（每个 CSV 对应一只股票），频率从路径推断
        2. 旧格式：ZIP 内含单个 CSV，symbol 和 freq 都从路径推断

        Args:
            zip_path: ZIP 文件路径
            freq_filter: 可选频率过滤集合，仅处理匹配的频率

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
                    csv_symbol = self.infer_symbol_from_csv_name(name)
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

                    bars, skipped = self.parse_csv_content(csv_text, csv_symbol, freq)
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

    async def update_progress(self, **kwargs) -> None:
        """更新 Redis 中的导入进度 JSON，合并 kwargs 到现有进度。"""
        client = get_redis_client()
        try:
            raw = await client.get(self.REDIS_PROGRESS_KEY)
            progress = json.loads(raw) if raw else {}
            progress.update(kwargs)
            await client.set(
                self.REDIS_PROGRESS_KEY,
                json.dumps(progress, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        finally:
            await client.aclose()

    async def is_running(self) -> bool:
        """检查是否有导入任务正在运行。"""
        client = get_redis_client()
        try:
            raw = await client.get(self.REDIS_PROGRESS_KEY)
            if not raw:
                return False
            progress = json.loads(raw)
            return progress.get("status") == "running"
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # 主执行流程
    # ------------------------------------------------------------------

    async def execute(
        self,
        freqs: list[str] | None = None,
        sub_dir: str | None = None,
        force: bool = False,
    ) -> dict:
        """
        执行导入流程，返回结果摘要字典。

        Args:
            freqs: 可选频率过滤列表
            sub_dir: 可选子目录
            force: 强制全量导入，忽略增量缓存

        Returns:
            结果摘要字典
        """
        start_time = time.time()
        base_dir = settings.local_kline_data_dir

        # 扫描 ZIP 文件
        zip_files = self.scan_zip_files(base_dir, sub_dir)

        scan_path = Path(base_dir)
        if sub_dir:
            scan_path = scan_path / sub_dir
        if not scan_path.exists() or not scan_path.is_dir():
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
            }
            return result

        freq_filter = set(freqs) if freqs else None

        # 初始化进度
        await self.update_progress(
            status="running",
            total_files=len(zip_files),
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

        for idx, zip_path in enumerate(zip_files):
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
                    await self.update_progress(skipped_files=skipped_files)
                    continue

            # 解压解析
            try:
                bars, parsed, skipped = self.extract_and_parse_zip(
                    zip_path, freq_filter,
                )
            except Exception as exc:
                logger.error("处理 ZIP 文件异常: %s error=%s", zip_path, exc)
                failed_files += 1
                failed_details.append({"path": str(zip_path), "error": str(exc)})
                await self.update_progress(
                    failed_files=failed_files,
                    failed_details=failed_details,
                )
                continue

            # 校验并过滤
            valid_bars = [b for b in bars if self.validate_bar(b)]
            validation_skipped = len(bars) - len(valid_bars)
            total_parsed += parsed
            total_skipped += skipped + validation_skipped

            # 分批写入
            inserted_for_file = 0
            try:
                for i in range(0, len(valid_bars), self.BATCH_SIZE):
                    batch = valid_bars[i : i + self.BATCH_SIZE]
                    inserted = await repo.bulk_insert(batch)
                    inserted_for_file += inserted
            except Exception as exc:
                logger.error("数据库写入异常: %s error=%s", zip_path, exc)
                failed_files += 1
                failed_details.append({"path": str(zip_path), "error": str(exc)})
                await self.update_progress(
                    failed_files=failed_files,
                    failed_details=failed_details,
                )
                continue

            total_inserted += inserted_for_file
            success_files += 1

            # 只有实际解析到数据时才标记为已导入，避免空解析污染增量缓存
            if parsed > 0:
                try:
                    await self.mark_imported(zip_path)
                except Exception as exc:
                    logger.warning("标记已导入失败: %s error=%s", zip_path, exc)

            logger.info(
                "文件导入完成: %s parsed=%d inserted=%d",
                zip_path, parsed, inserted_for_file,
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
            )

        elapsed = round(time.time() - start_time, 2)

        result = {
            "status": "completed",
            "total_files": len(zip_files),
            "success_files": success_files,
            "failed_files": failed_files,
            "total_parsed": total_parsed,
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "elapsed_seconds": elapsed,
            "skipped_files": skipped_files,
            "failed_details": failed_details,
        }

        # 写入最终进度
        await self.update_progress(
            status="completed",
            processed_files=len(zip_files),
            elapsed_seconds=elapsed,
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
            len(zip_files), success_files, failed_files,
            total_parsed, total_inserted, total_skipped, elapsed,
        )

        return result
