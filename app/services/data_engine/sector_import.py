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
    BaseParsingEngine,
    DCParsingEngine,
    ParsedConstituent,
    ParsedSectorInfo,
    ParsedSectorKline,
    TDXParsingEngine,
    TIParsingEngine,
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
    REDIS_ERRORS_KEY: str = "sector_import:errors"
    PROGRESS_TTL: int = 86400       # 24h
    HEARTBEAT_TIMEOUT: int = 120    # 秒

    def __init__(self, base_dir: str = "/Volumes/light/行业概念板块") -> None:
        self.base_dir = Path(base_dir)
        self.dc_engine = DCParsingEngine()
        self.ti_engine = TIParsingEngine()
        self.tdx_engine = TDXParsingEngine()

    def _get_engine(self, source: DataSource) -> BaseParsingEngine:
        """根据数据源返回对应的解析引擎实例。"""
        if source == DataSource.DC:
            return self.dc_engine
        elif source == DataSource.TI:
            return self.ti_engine
        elif source == DataSource.TDX:
            return self.tdx_engine
        raise ValueError(f"Unknown data source: {source}")

    # ------------------------------------------------------------------
    # 文件扫描
    # ------------------------------------------------------------------

    def _scan_sector_list_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块列表文件。

        按数据源子目录组织的实际文件系统布局：
        - DC: 东方财富/东方财富_板块列表/东方财富_板块列表1.csv
              东方财富/东方财富_板块列表/东方财富_板块列表2.csv
              东方财富/东方财富_板块列表/东方财富_概念板块列表/*.csv
              增量: 东方财富/东方财富_增量数据/东方财富_板块列表/YYYY-MM/*.csv
        - TI: 同花顺/同花顺_板块列表/同花顺_板块列表.csv
        - TDX: 通达信/通达信_板块列表/通达信_板块列表.csv
               通达信/通达信_板块列表/通达信_板块列表汇总/*.csv
               增量: 通达信/通达信_增量数据/通达信_板块列表/YYYY-MM/*.csv
        """
        results: list[Path] = []
        source_dir = self.base_dir / _SOURCE_DIR_MAP.get(source, "")

        if not source_dir.is_dir():
            logger.warning("数据源子目录不存在，跳过: %s", source_dir)
            return results

        if source == DataSource.DC:
            # 全量板块列表（简版）
            for name in ("东方财富_板块列表1.csv", "东方财富_板块列表2.csv"):
                f = source_dir / "东方财富_板块列表" / name
                if f.is_file():
                    results.append(f)
            # 概念板块列表目录（散装 CSV，含 idx_type 等 13 列）
            concept_list_dir = source_dir / "东方财富_板块列表" / "东方财富_概念板块列表"
            if concept_list_dir.is_dir():
                results.extend(sorted(concept_list_dir.glob("*.csv")))
            # 增量板块列表
            incr_dir = source_dir / "东方财富_增量数据" / "东方财富_板块列表"
            if incr_dir.is_dir():
                results.extend(sorted(incr_dir.rglob("*.csv")))

        elif source == DataSource.TI:
            f = source_dir / "同花顺_板块列表" / "同花顺_板块列表.csv"
            if f.is_file():
                results.append(f)

        elif source == DataSource.TDX:
            # 全量板块列表
            f = source_dir / "通达信_板块列表" / "通达信_板块列表.csv"
            if f.is_file():
                results.append(f)
            # 散装板块列表汇总
            info_dir = source_dir / "通达信_板块列表" / "通达信_板块列表汇总"
            if info_dir.is_dir():
                results.extend(sorted(info_dir.glob("*.csv")))
            # 增量板块列表
            incr_dir = source_dir / "通达信_增量数据" / "通达信_板块列表"
            if incr_dir.is_dir():
                results.extend(sorted(incr_dir.rglob("*.csv")))

        logger.info("扫描 %s 板块列表文件，发现 %d 个", source.value, len(results))
        return results

    def _scan_constituent_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块成分文件。

        按数据源子目录组织的实际文件系统布局：
        - DC: 东方财富/东方财富_板块成分/YYYY-MM/*.zip
        - TI: 同花顺/同花顺_板块成分/同花顺_概念板块成分汇总.csv
              同花顺/同花顺_板块成分/同花顺_行业板块成分汇总.csv
              同花顺/同花顺_增量数据/同花顺_概念板块成分/YYYY-MM/*.csv
              同花顺/同花顺_增量数据/同花顺_行业板块成分/YYYY-MM/*.csv
        - TDX: 通达信/通达信_板块成分/YYYY-MM/*.zip
        """
        results: list[Path] = []
        source_dir = self.base_dir / _SOURCE_DIR_MAP.get(source, "")

        if not source_dir.is_dir():
            logger.warning("数据源子目录不存在，跳过: %s", source_dir)
            return results

        if source == DataSource.DC:
            # 东方财富_板块成分/YYYY-MM/*.zip
            dc_dir = source_dir / "东方财富_板块成分"
            if dc_dir.is_dir():
                results.extend(sorted(dc_dir.rglob("*.zip")))

        elif source == DataSource.TI:
            # 概念板块成分汇总
            f = source_dir / "同花顺_板块成分" / "同花顺_概念板块成分汇总.csv"
            if f.is_file():
                results.append(f)
            # 行业板块成分汇总
            f = source_dir / "同花顺_板块成分" / "同花顺_行业板块成分汇总.csv"
            if f.is_file():
                results.append(f)
            # 增量概念板块成分
            concept_incr_dir = source_dir / "同花顺_增量数据" / "同花顺_概念板块成分"
            if concept_incr_dir.is_dir():
                results.extend(sorted(concept_incr_dir.rglob("*.csv")))
            # 增量行业板块成分
            industry_incr_dir = source_dir / "同花顺_增量数据" / "同花顺_行业板块成分"
            if industry_incr_dir.is_dir():
                results.extend(sorted(industry_incr_dir.rglob("*.csv")))

        elif source == DataSource.TDX:
            # 通达信_板块成分/YYYY-MM/*.zip
            tdx_dir = source_dir / "通达信_板块成分"
            if tdx_dir.is_dir():
                results.extend(sorted(tdx_dir.rglob("*.zip")))

        logger.info("扫描 %s 板块成分文件，发现 %d 个", source.value, len(results))
        return results

    def _scan_kline_files(self, source: DataSource) -> list[Path]:
        """扫描指定数据源的板块行情文件。

        按数据源子目录组织的实际文件系统布局：
        - DC: 东方财富_板块行情/东方财富_地区板块行情/*.csv
              东方财富_板块行情/东方财富_行业板块行情/*.csv
              增量: 东方财富_增量数据/东方财富_板块行情/YYYY-MM/*.csv
              注意: 概念板块行情已移除（原目录包含的是板块列表数据而非行情数据）
        - TI: 同花顺_板块行情/*.csv
              增量: 同花顺_增量数据/同花顺_板块行情/YYYY-MM/*.csv
        - TDX: 通达信_板块行情/通达信_板块行情汇总/*.csv
               通达信_板块行情/通达信_概念板块历史行情/*.zip
               通达信_板块行情/通达信_行业板块历史行情/*.zip
               通达信_板块行情/通达信_地区板块历史行情/*.zip
               通达信_板块行情/通达信_风格板块历史行情/*.zip
               增量: 通达信_增量数据/通达信_板块行情/YYYY-MM/*.csv
        """
        results: list[Path] = []
        source_dir = self.base_dir / _SOURCE_DIR_MAP.get(source, "")

        if not source_dir.is_dir():
            logger.warning("数据源子目录不存在，跳过: %s", source_dir)
            return results

        if source == DataSource.DC:
            # 两个散装 CSV 目录（概念板块行情已移除）
            for kline_sub in (
                "东方财富_地区板块行情",
                "东方财富_行业板块行情",
            ):
                kline_dir = source_dir / "东方财富_板块行情" / kline_sub
                if kline_dir.is_dir():
                    results.extend(sorted(kline_dir.glob("*.csv")))
            # 增量行情
            incr_dir = source_dir / "东方财富_增量数据" / "东方财富_板块行情"
            if incr_dir.is_dir():
                results.extend(sorted(incr_dir.rglob("*.csv")))

        elif source == DataSource.TI:
            # 散装行情 CSV
            kline_dir = source_dir / "同花顺_板块行情"
            if kline_dir.is_dir():
                results.extend(sorted(kline_dir.glob("*.csv")))
            # 增量行情
            incr_dir = source_dir / "同花顺_增量数据" / "同花顺_板块行情"
            if incr_dir.is_dir():
                results.extend(sorted(incr_dir.rglob("*.csv")))

        elif source == DataSource.TDX:
            # 散装行情 CSV
            kline_dir = source_dir / "通达信_板块行情" / "通达信_板块行情汇总"
            if kline_dir.is_dir():
                results.extend(sorted(kline_dir.glob("*.csv")))
            # 四个历史行情 ZIP 目录
            for sub_name in (
                "通达信_概念板块历史行情",
                "通达信_行业板块历史行情",
                "通达信_地区板块历史行情",
                "通达信_风格板块历史行情",
            ):
                zip_dir = source_dir / "通达信_板块行情" / sub_name
                if zip_dir.is_dir():
                    results.extend(sorted(zip_dir.glob("*.zip")))
            # 增量行情
            incr_dir = source_dir / "通达信_增量数据" / "通达信_板块行情"
            if incr_dir.is_dir():
                results.extend(sorted(incr_dir.rglob("*.csv")))

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
                await self._record_error(
                    file="bulk_upsert_sector_info",
                    line=0,
                    error_type="db_error",
                    message=f"板块列表批量写入失败 (batch {batch_start}-{batch_start + len(batch)})",
                    raw_data="",
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
                await self._record_error(
                    file="bulk_insert_constituents",
                    line=0,
                    error_type="db_error",
                    message=f"板块成分批量写入失败 (batch {batch_start}-{batch_start + len(batch)})",
                    raw_data="",
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
                await self._record_error(
                    file="bulk_insert_klines",
                    line=0,
                    error_type="db_error",
                    message=f"板块行情批量写入失败 (batch {batch_start}-{batch_start + len(batch)})",
                    raw_data="",
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
    # 错误统计
    # ------------------------------------------------------------------

    async def _record_error(
        self,
        file: str,
        line: int,
        error_type: str,
        message: str,
        raw_data: str = "",
    ) -> None:
        """将错误详情 JSON 追加到 Redis 列表，并递增进度中的 error_count。

        Args:
            file: 出错的文件名
            line: 出错的行号（批量写入失败时为 0）
            error_type: 错误类型（parse_error / ohlc_invalid / db_error）
            message: 错误信息
            raw_data: 原始数据（截断至 200 字符）
        """
        truncated_raw = raw_data[:200] if raw_data else ""
        error_detail = json.dumps(
            {
                "file": file,
                "line": line,
                "error_type": error_type,
                "message": message,
                "raw_data": truncated_raw,
            },
            ensure_ascii=False,
        )
        client = get_redis_client()
        try:
            await client.rpush(self.REDIS_ERRORS_KEY, error_detail)
        except Exception:
            logger.error("写入错误详情到 Redis 失败", exc_info=True)
        finally:
            await client.aclose()

        # 递增进度中的 error_count
        try:
            raw = await cache_get(self.REDIS_PROGRESS_KEY)
            progress: dict = json.loads(raw) if raw else {}
            progress["error_count"] = progress.get("error_count", 0) + 1
            # 更新 failed_files 列表
            failed_files: list[dict] = progress.get("failed_files", [])
            # 避免同一文件重复添加到 failed_files
            existing_files = {entry["file"] for entry in failed_files}
            if file not in existing_files:
                failed_files.append({"file": file, "error": message[:100]})
                progress["failed_files"] = failed_files
            await cache_set(
                self.REDIS_PROGRESS_KEY,
                json.dumps(progress, ensure_ascii=False),
                ex=self.PROGRESS_TTL,
            )
        except Exception:
            logger.error("更新错误计数失败", exc_info=True)

    async def _clear_errors(self) -> None:
        """清空错误列表（在每次新导入开始时调用）。"""
        client = get_redis_client()
        try:
            await client.delete(self.REDIS_ERRORS_KEY)
        except Exception:
            logger.error("清空错误列表失败", exc_info=True)
        finally:
            await client.aclose()

    async def get_errors(self, offset: int = 0, limit: int = 50) -> list[dict]:
        """从 Redis 列表分页读取错误详情。

        Args:
            offset: 起始偏移量
            limit: 返回条数

        Returns:
            错误详情字典列表
        """
        client = get_redis_client()
        try:
            items = await client.lrange(
                self.REDIS_ERRORS_KEY, offset, offset + limit - 1,
            )
            return [json.loads(item) for item in items]
        except Exception:
            logger.error("读取错误详情失败", exc_info=True)
            return []
        finally:
            await client.aclose()

    async def get_error_count(self) -> int:
        """返回错误总数。"""
        client = get_redis_client()
        try:
            count = await client.llen(self.REDIS_ERRORS_KEY)
            return count or 0
        except Exception:
            logger.error("获取错误总数失败", exc_info=True)
            return 0
        finally:
            await client.aclose()

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
                engine = self._get_engine(source)
                items = engine.parse_sector_list(f)
                count = await self._bulk_upsert_sector_info(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块列表文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块列表文件处理失败: {exc}",
                    raw_data="",
                )
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
                    # DC: 流式处理 ZIP，逐个内部 CSV yield 解析结果
                    for batch in self.dc_engine.iter_constituents_zip(f):
                        if await self._check_stop_signal():
                            return total
                        count = await self._bulk_insert_constituents(batch)
                        total += count
                elif source == DataSource.TI:
                    # TI: 区分汇总 CSV 和散装 CSV
                    if "成分汇总" in f.name:
                        items = self.ti_engine.parse_constituents_summary(f)
                    else:
                        items = self.ti_engine.parse_constituents_per_sector(f)
                    count = await self._bulk_insert_constituents(items)
                    total += count
                else:
                    # TDX: 解析成分 ZIP
                    items = self.tdx_engine.parse_constituents_zip(f)
                    count = await self._bulk_insert_constituents(items)
                    total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块成分文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块成分文件处理失败: {exc}",
                    raw_data="",
                )
        return total

    async def _import_klines(self, data_sources: list[DataSource]) -> int:
        """扫描并导入板块行情文件，返回导入记录总数。

        对散装 CSV 逐文件处理：读取→解析→写入→释放内存。
        对 TDX 历史行情 ZIP 采用流式处理以节省内存。
        """
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
                if f.suffix.lower() == ".zip":
                    # TDX 历史行情 ZIP：流式处理
                    count = await self._import_kline_zip_streaming(source, f)
                else:
                    # 散装/增量 CSV：使用对应引擎解析
                    engine = self._get_engine(source)
                    items = engine.parse_kline_csv(f)
                    count = await self._bulk_insert_klines(items)
                    del items  # 释放内存
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块行情文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块行情文件处理失败: {exc}",
                    raw_data="",
                )
        return total

    async def _import_kline_zip_streaming(
        self, source: DataSource, zip_path: Path
    ) -> int:
        """流式处理板块行情 ZIP 文件。

        使用 TDX 引擎的 iter_kline_zip 逐个读取 ZIP 内部 CSV，
        解析后立即写入数据库，写入完成后释放该批数据的内存，避免 OOM。
        """
        count = 0
        for items in self.tdx_engine.iter_kline_zip(zip_path):
            if await self._check_stop_signal():
                return count
            inserted = await self._bulk_insert_klines(items)
            count += inserted
            # 定期更新进度，让前端能看到 ZIP 内部的处理进展
            await self.update_progress(imported_records=count)
        return count

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
                engine = self._get_engine(source)
                items = engine.parse_sector_list(f)
                count = await self._bulk_upsert_sector_info(items)
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块列表文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块列表文件处理失败: {exc}",
                    raw_data="",
                )
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
                    for batch in self.dc_engine.iter_constituents_zip(f):
                        if await self._check_stop_signal():
                            return total
                        count = await self._bulk_insert_constituents(batch)
                        total += count
                elif source == DataSource.TI:
                    if "成分汇总" in f.name:
                        items = self.ti_engine.parse_constituents_summary(f)
                    else:
                        items = self.ti_engine.parse_constituents_per_sector(f)
                    count = await self._bulk_insert_constituents(items)
                    total += count
                else:
                    items = self.tdx_engine.parse_constituents_zip(f)
                    count = await self._bulk_insert_constituents(items)
                    total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块成分文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块成分文件处理失败: {exc}",
                    raw_data="",
                )
        return total

    async def _import_klines_incremental(
        self, data_sources: list[DataSource],
    ) -> int:
        """增量扫描并导入板块行情文件，跳过已导入文件。

        对散装 CSV 逐文件处理，对 TDX 历史行情 ZIP 采用流式处理以节省内存。
        """
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
                if f.suffix.lower() == ".zip":
                    count = await self._import_kline_zip_streaming(source, f)
                else:
                    engine = self._get_engine(source)
                    items = engine.parse_kline_csv(f)
                    count = await self._bulk_insert_klines(items)
                    del items  # 释放内存
                total += count
                processed_files += 1
                await self.mark_imported(f)
                await self.update_progress(
                    processed_files=processed_files,
                    imported_records=total,
                )
            except Exception as exc:
                logger.error("板块行情文件处理失败: %s", f, exc_info=True)
                await self._record_error(
                    file=f.name,
                    line=0,
                    error_type="parse_error",
                    message=f"板块行情文件处理失败: {exc}",
                    raw_data="",
                )
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
        await self._clear_errors()

        await self.update_progress(
            status="running",
            stage="板块列表",
            processed_files=0,
            imported_records=0,
            error_count=0,
            failed_files=[],
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
        await self._clear_errors()

        await self.update_progress(
            status="running",
            stage="板块列表",
            processed_files=0,
            imported_records=0,
            error_count=0,
            failed_files=[],
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
