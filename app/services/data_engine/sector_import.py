"""
板块数据导入服务

负责扫描文件、调用解析器、批量写入数据库、管理导入进度。
与 LocalKlineImportService 完全独立，使用独立的 Redis 键前缀 ``sector_import:``。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.core.redis_client import cache_delete, cache_get, cache_set, get_redis_client
from app.models.sector import DataSource
from app.services.data_engine.sector_csv_parser import (
    ParsedConstituent,
    ParsedSectorInfo,
    ParsedSectorKline,
    SectorCSVParser,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据源 → 子目录映射（保留用于日志等场景）
# ---------------------------------------------------------------------------

_SOURCE_DIR_MAP: dict[DataSource, str] = {
    DataSource.DC: "东方财富",
    DataSource.TI: "同花顺",
    DataSource.TDX: "通达信",
}


class SectorImportService:
    """板块数据导入服务"""

    BATCH_SIZE: int = 5000
    REDIS_PROGRESS_KEY: str = "sector_import:progress"
    REDIS_INCREMENTAL_KEY: str = "sector_import:files"
    REDIS_STOP_KEY: str = "sector_import:stop"
    PROGRESS_TTL: int = 86400       # 24h
    HEARTBEAT_TIMEOUT: int = 120    # 秒

    def __init__(self, base_dir: str = "/Volumes/light/行业概念板块") -> None:
        self.base_dir = Path(base_dir)
        self.parser = SectorCSVParser()

    # ------------------------------------------------------------------
    # 文件扫描
    # ------------------------------------------------------------------

    def _scan_sector_list_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块列表文件。

        实际文件系统布局：
        - DC: 根目录/概念板块列表_东财.csv
              根目录/东方财富_概念板块_历史行情数据/东方财富概念板块列表.csv
              根目录/东方财富_行业板块_历史行情数据/东方财富行业板块列表.csv
              增量: 根目录/增量数据/概念板块_东财/YYYY-MM/YYYY-MM-DD.csv
        - TI: 根目录/行业概念板块_同花顺.csv
        - TDX: 根目录/通达信板块列表.csv
               根目录/板块信息_通达信.zip
               增量: 根目录/增量数据/板块信息_通达信/YYYY-MM/YYYY-MM-DD.csv
        """
        results: list[Path] = []
        base = self.base_dir

        if source == DataSource.DC:
            # 根目录板块列表
            f = base / "概念板块列表_东财.csv"
            if f.is_file():
                results.append(f)
            # 历史行情目录中的板块列表
            for sub in ("东方财富_概念板块_历史行情数据", "东方财富_行业板块_历史行情数据"):
                d = base / sub
                if d.is_dir():
                    for ff in sorted(d.iterdir()):
                        if ff.is_file() and ff.name.endswith("板块列表.csv"):
                            results.append(ff)
            # 增量数据
            incr_dir = base / "增量数据" / "概念板块_东财"
            if incr_dir.is_dir():
                for month_dir in sorted(incr_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for ff in sorted(month_dir.iterdir()):
                        if ff.is_file() and ff.name.endswith(".csv"):
                            results.append(ff)

        elif source == DataSource.TI:
            f = base / "行业概念板块_同花顺.csv"
            if f.is_file():
                results.append(f)

        elif source == DataSource.TDX:
            f = base / "通达信板块列表.csv"
            if f.is_file():
                results.append(f)
            zf = base / "板块信息_通达信.zip"
            if zf.is_file():
                results.append(zf)
            # 增量数据
            incr_dir = base / "增量数据" / "板块信息_通达信"
            if incr_dir.is_dir():
                for month_dir in sorted(incr_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for ff in sorted(month_dir.iterdir()):
                        if ff.is_file() and ff.name.endswith(".csv"):
                            results.append(ff)

        logger.info("扫描 %s 板块列表文件，发现 %d 个", source.value, len(results))
        return results

    def _scan_constituent_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块成分文件。

        实际文件系统布局：
        - DC: 根目录/概念板块_东财.zip
              根目录/板块成分_东财/YYYY-MM/板块成分_DC_YYYYMMDD.zip
        - TI: 根目录/概念板块成分汇总_同花顺.csv
              根目录/行业板块成分汇总_同花顺.csv
              根目录/概念板块成分_同花顺.zip
              根目录/板块成分_同花顺/概念板块成分汇总_同花顺/YYYY-MM/*.csv
              根目录/板块成分_同花顺/行业板块成分汇总_同花顺/YYYY-MM/*.csv
        - TDX: 根目录/板块成分_通达信/YYYY-MM/板块成分_TDX_YYYYMMDD.zip
        """
        results: list[Path] = []
        base = self.base_dir

        if source == DataSource.DC:
            # 根目录 ZIP
            zf = base / "概念板块_东财.zip"
            if zf.is_file():
                results.append(zf)
            # 板块成分_东财/ 目录下按月份组织的 ZIP 文件
            dc_dir = base / "板块成分_东财"
            if dc_dir.is_dir():
                for month_dir in sorted(dc_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for f in sorted(month_dir.iterdir()):
                        if f.is_file() and f.name.startswith("板块成分_DC_") and f.name.endswith(".zip"):
                            results.append(f)

        elif source == DataSource.TI:
            # 根目录汇总 CSV
            for name in ("概念板块成分汇总_同花顺.csv", "行业板块成分汇总_同花顺.csv"):
                f = base / name
                if f.is_file():
                    results.append(f)
            # 根目录 ZIP
            zf = base / "概念板块成分_同花顺.zip"
            if zf.is_file():
                results.append(zf)
            # 增量成分目录
            ti_dir = base / "板块成分_同花顺"
            if ti_dir.is_dir():
                for sub_dir in sorted(ti_dir.iterdir()):
                    if not sub_dir.is_dir():
                        continue
                    for month_dir in sorted(sub_dir.iterdir()):
                        if not month_dir.is_dir():
                            continue
                        for f in sorted(month_dir.iterdir()):
                            if f.is_file() and f.name.endswith(".csv"):
                                results.append(f)

        elif source == DataSource.TDX:
            # 板块成分_通达信/ 目录下按月份组织的 ZIP 文件
            tdx_dir = base / "板块成分_通达信"
            if tdx_dir.is_dir():
                for month_dir in sorted(tdx_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for f in sorted(month_dir.iterdir()):
                        if f.is_file() and f.name.startswith("板块成分_TDX_") and f.name.endswith(".zip"):
                            results.append(f)

        logger.info("扫描 %s 板块成分文件，发现 %d 个", source.value, len(results))
        return results

    def _scan_kline_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块行情文件。

        实际文件系统布局：
        - DC: 根目录/板块行情_东财.zip
              根目录/东方财富_概念板块_历史行情数据/概念板块_日k.zip
              根目录/东方财富_行业板块_历史行情数据/行业板块_日k.zip
              增量: 根目录/增量数据/板块行情_东财/YYYY-MM/YYYY-MM-DD.csv
        - TI: 根目录/板块指数行情_同花顺.zip
              增量: 根目录/增量数据/板块指数行情_同花顺/YYYY-MM/YYYY-MM-DD.csv
        - TDX: 根目录/板块行情_通达信.zip
               根目录/通达信_*板块_历史行情数据/*.zip
               增量: 根目录/增量数据/板块行情_通达信/YYYY-MM/YYYY-MM-DD.csv
        """
        results: list[Path] = []
        base = self.base_dir

        if source == DataSource.DC:
            zf = base / "板块行情_东财.zip"
            if zf.is_file():
                results.append(zf)
            # 历史行情目录中的 ZIP
            for sub in ("东方财富_概念板块_历史行情数据", "东方财富_行业板块_历史行情数据"):
                d = base / sub
                if d.is_dir():
                    for f in sorted(d.iterdir()):
                        if f.is_file() and f.name.endswith(".zip"):
                            results.append(f)
            # 增量数据
            incr_dir = base / "增量数据" / "板块行情_东财"
            if incr_dir.is_dir():
                for month_dir in sorted(incr_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for f in sorted(month_dir.iterdir()):
                        if f.is_file() and f.name.endswith(".csv"):
                            results.append(f)

        elif source == DataSource.TI:
            zf = base / "板块指数行情_同花顺.zip"
            if zf.is_file():
                results.append(zf)
            # 增量数据
            incr_dir = base / "增量数据" / "板块指数行情_同花顺"
            if incr_dir.is_dir():
                for month_dir in sorted(incr_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for f in sorted(month_dir.iterdir()):
                        if f.is_file() and f.name.endswith(".csv"):
                            results.append(f)

        elif source == DataSource.TDX:
            zf = base / "板块行情_通达信.zip"
            if zf.is_file():
                results.append(zf)
            # 按板块类型分目录的历史行情 ZIP
            for sub_name in (
                "通达信_概念板块_历史行情数据",
                "通达信_行业板块_历史行情数据",
                "通达信_地区板块_历史行情数据",
                "通达信_风格板块_历史行情数据",
            ):
                sub_dir = base / sub_name
                if sub_dir.is_dir():
                    for f in sorted(sub_dir.iterdir()):
                        if f.is_file() and f.name.endswith(".zip"):
                            results.append(f)
            # 增量数据
            incr_dir = base / "增量数据" / "板块行情_通达信"
            if incr_dir.is_dir():
                for month_dir in sorted(incr_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for f in sorted(month_dir.iterdir()):
                        if f.is_file() and f.name.endswith(".csv"):
                            results.append(f)

        logger.info("扫描 %s 板块行情文件，发现 %d 个", source.value, len(results))
        return results

    # ------------------------------------------------------------------
    # 批量写入
    # ------------------------------------------------------------------

    async def _bulk_upsert_sector_info(self, items: list[ParsedSectorInfo]) -> int:
        """批量 UPSERT 板块元数据到 PostgreSQL。

        使用 ON CONFLICT (sector_code, data_source) DO UPDATE 策略。
        返回处理的记录总数。
        """
        if not items:
            return 0

        upsert_sql = text("""
            INSERT INTO sector_info (
                sector_code, name, sector_type, data_source,
                list_date, constituent_count, updated_at
            ) VALUES (
                :sector_code, :name, :sector_type, :data_source,
                :list_date, :constituent_count, :updated_at
            )
            ON CONFLICT (sector_code, data_source) DO UPDATE SET
                name              = EXCLUDED.name,
                sector_type       = EXCLUDED.sector_type,
                list_date         = EXCLUDED.list_date,
                constituent_count = EXCLUDED.constituent_count,
                updated_at        = EXCLUDED.updated_at
        """)

        now = datetime.now()
        total = 0

        for batch_start in range(0, len(items), self.BATCH_SIZE):
            if await self._check_stop_signal():
                logger.info("板块列表批量写入收到停止信号，已写入 %d 条", total)
                return total

            batch = items[batch_start : batch_start + self.BATCH_SIZE]
            params = [
                {
                    "sector_code": item.sector_code,
                    "name": item.name,
                    "sector_type": item.sector_type.value,
                    "data_source": item.data_source.value,
                    "list_date": item.list_date,
                    "constituent_count": item.constituent_count,
                    "updated_at": now,
                }
                for item in batch
            ]
            try:
                async with AsyncSessionPG() as session:
                    await session.execute(upsert_sql, params)
                    await session.commit()
                total += len(batch)
            except Exception:
                logger.error(
                    "板块列表批量写入失败 (batch %d-%d)",
                    batch_start, batch_start + len(batch),
                    exc_info=True,
                )

        return total

    async def _bulk_insert_constituents(self, items: list[ParsedConstituent]) -> int:
        """批量插入板块成分股到 PostgreSQL。

        使用 ON CONFLICT DO NOTHING 策略，executemany 批量提交。
        每个批次之间检查停止信号。
        返回处理的记录总数。
        """
        if not items:
            return 0

        insert_sql = text("""
            INSERT INTO sector_constituent (
                trade_date, sector_code, data_source, symbol, stock_name
            ) VALUES (
                :trade_date, :sector_code, :data_source, :symbol, :stock_name
            )
            ON CONFLICT (trade_date, sector_code, data_source, symbol) DO NOTHING
        """)

        total = 0

        for batch_start in range(0, len(items), self.BATCH_SIZE):
            # 每个批次之间检查停止信号
            if await self._check_stop_signal():
                logger.info("板块成分批量写入收到停止信号，已写入 %d 条", total)
                return total

            batch = items[batch_start : batch_start + self.BATCH_SIZE]
            params = [
                {
                    "trade_date": item.trade_date,
                    "sector_code": item.sector_code,
                    "data_source": item.data_source.value,
                    "symbol": item.symbol,
                    "stock_name": item.stock_name,
                }
                for item in batch
            ]
            try:
                async with AsyncSessionPG() as session:
                    await session.execute(insert_sql, params)
                    await session.commit()
                total += len(batch)
            except Exception:
                logger.error(
                    "板块成分批量写入失败 (batch %d-%d)",
                    batch_start, batch_start + len(batch),
                    exc_info=True,
                )

        return total

    async def _bulk_insert_klines(self, items: list[ParsedSectorKline]) -> int:
        """批量插入板块行情到 TimescaleDB。

        使用 ON CONFLICT DO NOTHING 策略。
        返回处理的记录总数。
        """
        if not items:
            return 0

        insert_sql = text("""
            INSERT INTO sector_kline (
                time, sector_code, data_source, freq,
                open, high, low, close,
                volume, amount, turnover, change_pct
            ) VALUES (
                :time, :sector_code, :data_source, :freq,
                :open, :high, :low, :close,
                :volume, :amount, :turnover, :change_pct
            )
            ON CONFLICT (time, sector_code, data_source, freq) DO NOTHING
        """)

        total = 0

        for batch_start in range(0, len(items), self.BATCH_SIZE):
            if await self._check_stop_signal():
                logger.info("板块行情批量写入收到停止信号，已写入 %d 条", total)
                return total

            batch = items[batch_start : batch_start + self.BATCH_SIZE]
            params = [
                {
                    "time": item.time,
                    "sector_code": item.sector_code,
                    "data_source": item.data_source.value,
                    "freq": item.freq,
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                    "amount": item.amount,
                    "turnover": item.turnover,
                    "change_pct": item.change_pct,
                }
                for item in batch
            ]
            try:
                async with AsyncSessionTS() as session:
                    await session.execute(insert_sql, params)
                    await session.commit()
                total += len(batch)
            except Exception:
                logger.error(
                    "板块行情批量写入失败 (batch %d-%d)",
                    batch_start, batch_start + len(batch),
                    exc_info=True,
                )

        return total

    # ------------------------------------------------------------------
    # 进度追踪
    # ------------------------------------------------------------------

    async def update_progress(self, **kwargs) -> None:
        """更新 Redis 中的导入进度 JSON，合并 kwargs 到现有进度。

        每次更新自动写入 heartbeat 时间戳，用于僵尸任务检测。
        """
        try:
            raw = await cache_get(self.REDIS_PROGRESS_KEY)
            progress: dict = json.loads(raw) if raw else {}
            progress.update(kwargs)
            progress["heartbeat"] = time.time()
            await cache_set(
                self.REDIS_PROGRESS_KEY,
                json.dumps(progress, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        except Exception:
            logger.error("更新板块导入进度失败", exc_info=True)

    async def is_running(self) -> bool:
        """检查是否有板块导入任务正在运行。

        通过心跳机制检测僵尸任务：如果 status 为 running/pending 但心跳超时
        或缺失心跳字段，自动将状态标记为 failed 并返回 False。
        """
        try:
            raw = await cache_get(self.REDIS_PROGRESS_KEY)
            if not raw:
                return False
            progress = json.loads(raw)
            status = progress.get("status")
            if status not in ("running", "pending"):
                return False

            # 心跳超时检测
            heartbeat = progress.get("heartbeat")
            if heartbeat is None:
                logger.warning(
                    "板块导入任务无心跳字段，判定为僵尸任务，自动清理状态",
                )
                progress["status"] = "failed"
                progress["error"] = "任务异常终止（无心跳记录）"
                await cache_set(
                    self.REDIS_PROGRESS_KEY,
                    json.dumps(progress, ensure_ascii=False),
                    ex=self.PROGRESS_TTL,
                )
                return False

            elapsed = time.time() - heartbeat
            if elapsed > self.HEARTBEAT_TIMEOUT:
                logger.warning(
                    "板块导入任务心跳超时（%.0f 秒），判定为僵尸任务，自动清理状态",
                    elapsed,
                )
                progress["status"] = "failed"
                progress["error"] = f"任务异常终止（心跳超时 {int(elapsed)} 秒）"
                await cache_set(
                    self.REDIS_PROGRESS_KEY,
                    json.dumps(progress, ensure_ascii=False),
                    ex=self.PROGRESS_TTL,
                )
                return False

            return True
        except Exception:
            logger.error("检查板块导入运行状态失败", exc_info=True)
            return False

    async def request_stop(self) -> None:
        """发送板块导入停止信号。"""
        client = get_redis_client()
        try:
            await client.set(self.REDIS_STOP_KEY, "1", ex=3600)
        finally:
            await client.aclose()

    async def _check_stop_signal(self) -> bool:
        """检查是否收到停止信号。

        Returns:
            True 表示应该停止。
        """
        client = get_redis_client()
        try:
            val = await client.get(self.REDIS_STOP_KEY)
            return val is not None
        finally:
            await client.aclose()

    async def _clear_stop_signal(self) -> None:
        """清除停止信号。"""
        await cache_delete(self.REDIS_STOP_KEY)

    # ------------------------------------------------------------------
    # 增量检测
    # ------------------------------------------------------------------

    async def check_incremental(self, file_path: Path) -> bool:
        """检查文件是否可跳过（已导入且 mtime 未变化）。

        Returns:
            True 表示文件应被跳过。
        """
        client = get_redis_client()
        try:
            stored_mtime = await client.hget(self.REDIS_INCREMENTAL_KEY, str(file_path))
            if stored_mtime is None:
                return False
            current_mtime = str(file_path.stat().st_mtime)
            return stored_mtime == current_mtime
        finally:
            await client.aclose()

    async def mark_imported(self, file_path: Path) -> None:
        """将文件路径和 mtime 写入 Redis 增量缓存。"""
        client = get_redis_client()
        try:
            mtime = str(file_path.stat().st_mtime)
            await client.hset(self.REDIS_INCREMENTAL_KEY, str(file_path), mtime)
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # 各阶段导入（内部方法）
    # ------------------------------------------------------------------

    async def _import_sector_list(self, data_sources: list[DataSource]) -> int:
        """扫描并导入板块列表文件，返回导入记录总数。"""
        total = 0
        processed_files = 0
        # 预扫描计算总文件数
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_sector_list_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_sector_list_dc(f)
                elif source == DataSource.TI:
                    items = self.parser.parse_sector_list_ti(f)
                else:
                    items = self.parser.parse_sector_list_tdx(f)
                count = await self._bulk_upsert_sector_info(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块列表文件处理失败: %s", f, exc_info=True)
        return total

    async def _import_constituents(self, data_sources: list[DataSource]) -> int:
        """扫描并导入板块成分文件，返回导入记录总数。"""
        total = 0
        processed_files = 0
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_constituent_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_constituents_dc_zip(f)
                elif source == DataSource.TI:
                    trade_date = self.parser._infer_date_from_filename(f.name)
                    if trade_date is None:
                        logger.error(
                            "TI 成分文件名无法推断日期，跳过: %s", f,
                        )
                        continue
                    items = self.parser.parse_constituents_ti_csv(f, trade_date)
                else:
                    items = self.parser.parse_constituents_tdx_zip(f)
                count = await self._bulk_insert_constituents(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块成分文件处理失败: %s", f, exc_info=True)
        return total

    async def _import_klines(self, data_sources: list[DataSource]) -> int:
        """扫描并导入板块行情文件，返回导入记录总数。"""
        total = 0
        processed_files = 0
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_kline_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_kline_dc_csv(f)
                elif source == DataSource.TI:
                    items = self.parser.parse_kline_ti_csv(f)
                else:
                    items = self.parser.parse_kline_tdx_csv(f)
                count = await self._bulk_insert_klines(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块行情文件处理失败: %s", f, exc_info=True)
        return total

    # ------------------------------------------------------------------
    # 增量版各阶段导入（内部方法）
    # ------------------------------------------------------------------

    async def _import_sector_list_incremental(
        self, data_sources: list[DataSource],
    ) -> int:
        """增量扫描并导入板块列表文件，跳过已导入文件。"""
        total = 0
        processed_files = 0
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_sector_list_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            if await self.check_incremental(f):
                continue
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_sector_list_dc(f)
                elif source == DataSource.TI:
                    items = self.parser.parse_sector_list_ti(f)
                else:
                    items = self.parser.parse_sector_list_tdx(f)
                count = await self._bulk_upsert_sector_info(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块列表文件处理失败: %s", f, exc_info=True)
        return total

    async def _import_constituents_incremental(
        self, data_sources: list[DataSource],
    ) -> int:
        """增量扫描并导入板块成分文件，跳过已导入文件。"""
        total = 0
        processed_files = 0
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_constituent_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            if await self.check_incremental(f):
                continue
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_constituents_dc_zip(f)
                elif source == DataSource.TI:
                    trade_date = self.parser._infer_date_from_filename(f.name)
                    if trade_date is None:
                        logger.error(
                            "TI 成分文件名无法推断日期，跳过: %s", f,
                        )
                        continue
                    items = self.parser.parse_constituents_ti_csv(f, trade_date)
                else:
                    items = self.parser.parse_constituents_tdx_zip(f)
                count = await self._bulk_insert_constituents(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块成分文件处理失败: %s", f, exc_info=True)
        return total

    async def _import_klines_incremental(
        self, data_sources: list[DataSource],
    ) -> int:
        """增量扫描并导入板块行情文件，跳过已导入文件。"""
        total = 0
        processed_files = 0
        all_files: list[tuple[DataSource, Path]] = []
        for source in data_sources:
            for f in self._scan_kline_files(source):
                all_files.append((source, f))
        total_files = len(all_files)
        await self.update_progress(total_files=total_files, processed_files=0)

        for source, f in all_files:
            if await self._check_stop_signal():
                return total
            if await self.check_incremental(f):
                continue
            await self.update_progress(current_file=f.name)
            try:
                if source == DataSource.DC:
                    items = self.parser.parse_kline_dc_csv(f)
                elif source == DataSource.TI:
                    items = self.parser.parse_kline_ti_csv(f)
                else:
                    items = self.parser.parse_kline_tdx_csv(f)
                count = await self._bulk_insert_klines(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception:
                logger.error("板块行情文件处理失败: %s", f, exc_info=True)
        return total

    # ------------------------------------------------------------------
    # 全量/增量导入
    # ------------------------------------------------------------------

    async def import_full(
        self,
        data_sources: list[DataSource] | None = None,
    ) -> dict:
        """全量导入：板块列表 → 成分 → 行情"""
        data_sources = data_sources or list(DataSource)
        await self._clear_stop_signal()

        await self.update_progress(
            status="running",
            stage="板块列表",
            processed_files=0,
            imported_records=0,
        )

        sector_count = await self._import_sector_list(data_sources)
        if await self._check_stop_signal():
            await self.update_progress(status="stopped")
            return {
                "status": "stopped",
                "sectors": sector_count,
                "constituents": 0,
                "klines": 0,
            }

        await self.update_progress(
            stage="板块成分",
            processed_files=0,
            imported_records=0,
        )
        constituent_count = await self._import_constituents(data_sources)
        if await self._check_stop_signal():
            await self.update_progress(status="stopped")
            return {
                "status": "stopped",
                "sectors": sector_count,
                "constituents": constituent_count,
                "klines": 0,
            }

        await self.update_progress(
            stage="板块行情",
            processed_files=0,
            imported_records=0,
        )
        kline_count = await self._import_klines(data_sources)

        await self.update_progress(status="completed")
        return {
            "status": "completed",
            "sectors": sector_count,
            "constituents": constituent_count,
            "klines": kline_count,
        }

    async def import_incremental(
        self,
        data_sources: list[DataSource] | None = None,
    ) -> dict:
        """增量导入：仅处理尚未导入的新数据文件"""
        data_sources = data_sources or list(DataSource)
        await self._clear_stop_signal()

        await self.update_progress(
            status="running",
            stage="板块列表",
            processed_files=0,
            imported_records=0,
        )

        sector_count = await self._import_sector_list_incremental(data_sources)
        if await self._check_stop_signal():
            await self.update_progress(status="stopped")
            return {
                "status": "stopped",
                "sectors": sector_count,
                "constituents": 0,
                "klines": 0,
            }

        await self.update_progress(
            stage="板块成分",
            processed_files=0,
            imported_records=0,
        )
        constituent_count = await self._import_constituents_incremental(data_sources)
        if await self._check_stop_signal():
            await self.update_progress(status="stopped")
            return {
                "status": "stopped",
                "sectors": sector_count,
                "constituents": constituent_count,
                "klines": 0,
            }

        await self.update_progress(
            stage="板块行情",
            processed_files=0,
            imported_records=0,
        )
        kline_count = await self._import_klines_incremental(data_sources)

        await self.update_progress(status="completed")
        return {
            "status": "completed",
            "sectors": sector_count,
            "constituents": constituent_count,
            "klines": kline_count,
        }
