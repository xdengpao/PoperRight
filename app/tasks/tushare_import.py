"""
Tushare 数据在线导入 Celery 异步任务

执行实际的 Tushare API 调用、数据转换（字段映射 + 代码格式转换）和数据库写入。
继承 DataSyncTask 基类，注册到 data_sync 队列。

核心流程：
1. 从 API_Registry 获取接口元数据
2. 创建 TushareAdapter（使用指定 Token）
3. 按 batch_by_code 决定是否分批处理
4. 每批：检查停止信号 → 调用 API → 字段映射 → 代码转换 → 写入 DB → 更新进度
5. 完成后更新 tushare_import_log

对应需求：3.2, 4.4, 4.5, 4.8, 12.3, 20.2, 21.3, 26.1, 26.2
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

from app.core.celery_app import celery_app
from app.services.data_engine.tushare_adapter import TushareAdapter, TushareAPIError
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    RateLimitGroup,
    StorageEngine,
    get_entry,
)
from app.tasks.base import DataSyncTask

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

BATCH_SIZE = 50

# 频率限制（秒）：按 RateLimitGroup 分组
_RATE_LIMIT_MAP: dict[RateLimitGroup, float] = {
    RateLimitGroup.KLINE: 0.18,
    RateLimitGroup.FUNDAMENTALS: 0.40,
    RateLimitGroup.MONEY_FLOW: 0.30,
}

# Redis 键前缀和 TTL
_PROGRESS_KEY_PREFIX = "tushare:import:"
_STOP_KEY_PREFIX = "tushare:import:stop:"
_LOCK_KEY_PREFIX = "tushare:import:lock:"
_PROGRESS_TTL = 86400  # 24h

# 网络超时重试配置
_MAX_NETWORK_RETRIES = 3
_RATE_LIMIT_WAIT = 60  # 频率限制等待秒数


# ---------------------------------------------------------------------------
# 辅助：在同步 Celery worker 中运行异步协程
# ---------------------------------------------------------------------------

def _run_async(coro):
    """在同步 Celery worker 中运行异步协程。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Redis 辅助（同步包装异步 Redis）
# ---------------------------------------------------------------------------

async def _redis_get(key: str) -> str | None:
    """异步获取 Redis 键值。"""
    from app.core.redis_client import cache_get
    return await cache_get(key)


async def _redis_set(key: str, value: str, ex: int | None = None) -> None:
    """异步设置 Redis 键值。"""
    from app.core.redis_client import cache_set
    await cache_set(key, value, ex=ex)


async def _redis_delete(key: str) -> None:
    """异步删除 Redis 键。"""
    from app.core.redis_client import cache_delete
    await cache_delete(key)


# ---------------------------------------------------------------------------
# Celery 任务定义
# ---------------------------------------------------------------------------

@celery_app.task(
    base=DataSyncTask,
    name="app.tasks.tushare_import.run_import",
    bind=True,
    queue="data_sync",
    soft_time_limit=7200,
    time_limit=10800,
)
def run_import(
    self,
    api_name: str,
    params: dict,
    token: str,
    log_id: int,
    task_id: str,
) -> dict:
    """
    执行 Tushare 数据导入（Celery 任务入口）。

    薄包装层，将参数传递给 _process_import 异步核心逻辑。

    Args:
        api_name: Tushare 接口名称
        params: 导入参数字典
        token: API Token
        log_id: tushare_import_log 记录 ID
        task_id: 任务唯一标识
    """
    return _run_async(_process_import(api_name, params, token, log_id, task_id))


# ---------------------------------------------------------------------------
# 核心处理逻辑
# ---------------------------------------------------------------------------

async def _process_import(
    api_name: str,
    params: dict,
    token: str,
    log_id: int,
    task_id: str,
) -> dict:
    """导入核心处理逻辑。

    1. 从 API_Registry 获取接口元数据
    2. 创建 TushareAdapter
    3. 如果 batch_by_code=True，按代码分批处理
    4. 每批：检查停止信号 → 调用 API → 字段映射 → 代码转换 → 写入 DB → 更新进度
    5. 完成后更新 tushare_import_log
    """
    entry = get_entry(api_name)
    if entry is None:
        await _finalize_log(log_id, "failed", 0, f"未知接口: {api_name}")
        return {"status": "failed", "error": f"未知接口: {api_name}"}

    adapter = TushareAdapter(api_token=token)
    rate_delay = _RATE_LIMIT_MAP.get(entry.rate_limit_group, 0.18)

    # 更新 Redis 进度为 running
    await _update_progress(task_id, status="running")

    total_records = 0

    try:
        # 判断是否需要分批处理：
        # 1. 注册表明确标记 batch_by_code=True
        # 2. 接口支持 stock_code 参数但用户未传 ts_code → 自动按全市场分批
        use_batch = entry.batch_by_code
        if not use_batch and not params.get("ts_code"):
            from app.services.data_engine.tushare_registry import ParamType
            has_stock_param = (
                ParamType.STOCK_CODE in entry.required_params
                or ParamType.STOCK_CODE in entry.optional_params
            )
            if has_stock_param:
                use_batch = True

        if use_batch:
            result = await _process_batched(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        else:
            result = await _process_single(
                entry, adapter, params, task_id, log_id, rate_delay,
            )

        total_records = result.get("record_count", 0)
        status = result.get("status", "completed")

        if status == "stopped":
            await _finalize_log(log_id, "stopped", total_records)
            await _update_progress(task_id, status="stopped",
                                   total=total_records, completed=total_records)
        else:
            await _finalize_log(log_id, "completed", total_records)
            await _update_progress(task_id, status="completed",
                                   total=total_records, completed=total_records)

        return result

    except Exception as exc:
        error_msg = str(exc)[:500]
        logger.error("Tushare 导入失败 api=%s: %s", api_name, exc, exc_info=True)
        await _finalize_log(log_id, "failed", total_records, error_msg)
        await _update_progress(task_id, status="failed", error_message=error_msg)
        return {"status": "failed", "error": error_msg, "record_count": total_records}

    finally:
        # 释放并发锁
        lock_key = f"{_LOCK_KEY_PREFIX}{api_name}"
        await _redis_delete(lock_key)


# ---------------------------------------------------------------------------
# 单次处理（非分批）
# ---------------------------------------------------------------------------

async def _process_single(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """非分批模式：一次 API 调用获取全部数据。"""
    # 设置初始进度（单次调用视为 1 步）
    await _update_progress(task_id, status="running", total=1, completed=0,
                           current_item=entry.api_name)

    # 支持 extra_config 中的 tushare_api_name（实际 Tushare 接口名）和 default_params（默认参数）
    actual_api_name = entry.extra_config.get("tushare_api_name", entry.api_name)
    call_params = {**entry.extra_config.get("default_params", {}), **params}

    data = await _call_api_with_retry(adapter, actual_api_name, call_params, entry)
    rows = TushareAdapter._rows_from_data(data)

    if not rows:
        return {"status": "completed", "record_count": 0}

    # 支持 extra_config.inject_fields：向每行注入固定字段值
    inject_fields = entry.extra_config.get("inject_fields")
    if inject_fields:
        for row in rows:
            row.update(inject_fields)

    mapped_rows = _apply_field_mappings(rows, entry)
    converted_rows = _convert_codes(mapped_rows, entry)

    # 写入数据库
    if entry.storage_engine == StorageEngine.TS:
        await _write_to_timescaledb(converted_rows, entry)
    else:
        await _write_to_postgresql(converted_rows, entry)

    await _update_progress(task_id, status="running", completed=1,
                           total=1)

    return {"status": "completed", "record_count": len(converted_rows)}


# ---------------------------------------------------------------------------
# 分批处理
# ---------------------------------------------------------------------------

async def _process_batched(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """分批模式：按股票代码列表分批调用 API。"""
    # 获取股票列表
    stock_codes = await _get_stock_list()
    if not stock_codes:
        return {"status": "completed", "record_count": 0}

    total = len(stock_codes)
    completed = 0
    total_records = 0

    await _update_progress(task_id, status="running", total=total, completed=0)

    # 按 BATCH_SIZE 分批
    for batch_start in range(0, total, BATCH_SIZE):
        batch = stock_codes[batch_start: batch_start + BATCH_SIZE]

        for ts_code in batch:
            # 检查停止信号
            if await _check_stop_signal(task_id):
                logger.info("Tushare 导入收到停止信号 task_id=%s", task_id)
                return {"status": "stopped", "record_count": total_records}

            # 构建本次 API 调用参数
            call_params = {**params, "ts_code": ts_code}

            try:
                data = await _call_api_with_retry(
                    adapter, entry.api_name, call_params, entry,
                )
                rows = TushareAdapter._rows_from_data(data)

                if rows:
                    mapped_rows = _apply_field_mappings(rows, entry)
                    converted_rows = _convert_codes(mapped_rows, entry)

                    try:
                        if entry.storage_engine == StorageEngine.TS:
                            await _write_to_timescaledb(converted_rows, entry)
                        else:
                            await _write_to_postgresql(converted_rows, entry)
                        total_records += len(converted_rows)
                    except Exception as db_exc:
                        # 数据库写入失败：回滚当前批次，继续下一批
                        logger.error(
                            "DB 写入失败 api=%s ts_code=%s: %s",
                            entry.api_name, ts_code, db_exc,
                        )

            except TushareAPIError as api_exc:
                # Token 无效不重试，其他 API 错误记录后继续
                if api_exc.code and api_exc.code == -2001:
                    raise  # Token 无效，终止整个任务
                logger.error(
                    "API 调用失败 api=%s ts_code=%s: %s",
                    entry.api_name, ts_code, api_exc,
                )
            except Exception as exc:
                logger.error(
                    "处理失败 api=%s ts_code=%s: %s",
                    entry.api_name, ts_code, exc,
                )

            completed += 1
            await _update_progress(
                task_id, status="running",
                total=total, completed=completed,
                current_item=ts_code,
            )

            # 频率限制
            time.sleep(rate_delay)

    return {"status": "completed", "record_count": total_records}


# ---------------------------------------------------------------------------
# API 调用（带重试）
# ---------------------------------------------------------------------------

async def _call_api_with_retry(
    adapter: TushareAdapter,
    api_name: str,
    params: dict,
    entry: ApiEntry,
) -> dict[str, Any]:
    """调用 Tushare API，带网络超时重试和频率限制等待。

    - 网络超时：重试最多 3 次
    - Token 无效（code=-2001）：不重试，直接抛出
    - 频率限制（code=-2002）：等待 60s 后重试
    - HTTP 错误：记录日志，抛出
    """
    import httpx

    last_exc: Exception | None = None

    for attempt in range(_MAX_NETWORK_RETRIES):
        try:
            data = await adapter._call_api(api_name, **params)
            return data

        except TushareAPIError as exc:
            # Token 无效 → 不重试
            if exc.code == -2001:
                logger.error("Token 无效 api=%s: %s", api_name, exc)
                raise

            # 频率限制 → 等待后重试
            if exc.code == -2002:
                logger.warning(
                    "频率限制 api=%s，等待 %ds 后重试 (attempt %d/%d)",
                    api_name, _RATE_LIMIT_WAIT, attempt + 1, _MAX_NETWORK_RETRIES,
                )
                time.sleep(_RATE_LIMIT_WAIT)
                last_exc = exc
                continue

            # 其他 API 错误 → 记录并抛出
            logger.error("API 错误 api=%s code=%s: %s", api_name, exc.code, exc)
            raise

        except httpx.TimeoutException as exc:
            logger.warning(
                "网络超时 api=%s (attempt %d/%d): %s",
                api_name, attempt + 1, _MAX_NETWORK_RETRIES, exc,
            )
            last_exc = exc
            if attempt < _MAX_NETWORK_RETRIES - 1:
                time.sleep(2 * (attempt + 1))  # 简单退避
            continue

        except httpx.HTTPStatusError as exc:
            logger.error("HTTP 错误 api=%s: %s", api_name, exc)
            raise TushareAPIError(
                f"HTTP {exc.response.status_code}",
                api_name=api_name,
                code=exc.response.status_code,
            ) from exc

    # 所有重试耗尽
    if last_exc:
        raise TushareAPIError(
            f"重试 {_MAX_NETWORK_RETRIES} 次后仍失败: {last_exc}",
            api_name=api_name,
        ) from last_exc

    raise TushareAPIError("API 调用失败（未知原因）", api_name=api_name)


# ---------------------------------------------------------------------------
# 字段映射
# ---------------------------------------------------------------------------

def _apply_field_mappings(rows: list[dict], entry: ApiEntry) -> list[dict]:
    """应用字段映射，将 Tushare 字段名转换为目标表字段名。

    如果 entry.field_mappings 为空，则原样返回（pass-through）。
    """
    if not entry.field_mappings:
        return rows

    # 构建映射字典：source → target
    mapping = {fm.source: fm.target for fm in entry.field_mappings}

    result = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            target_key = mapping.get(key, key)
            new_row[target_key] = value
        result.append(new_row)

    return result


# ---------------------------------------------------------------------------
# 代码格式转换
# ---------------------------------------------------------------------------

def _convert_codes(rows: list[dict], entry: ApiEntry) -> list[dict]:
    """根据 code_format 转换代码格式。

    - STOCK_SYMBOL: ts_code 去后缀（600000.SH → 600000），存入 symbol 字段
    - INDEX_CODE: 保留 ts_code 原样
    - NONE: 不做任何转换
    """
    if entry.code_format == CodeFormat.NONE:
        return rows

    if entry.code_format == CodeFormat.STOCK_SYMBOL:
        for row in rows:
            ts_code = row.get("ts_code", "")
            if ts_code and "." in str(ts_code):
                row["symbol"] = str(ts_code).split(".")[0]
            elif ts_code:
                row["symbol"] = str(ts_code)
        return rows

    if entry.code_format == CodeFormat.INDEX_CODE:
        # 保留 ts_code 原样，不做转换
        return rows

    return rows


# ---------------------------------------------------------------------------
# 停止信号检测
# ---------------------------------------------------------------------------

async def _check_stop_signal(task_id: str) -> bool:
    """检查 Redis 停止信号。"""
    stop_key = f"{_STOP_KEY_PREFIX}{task_id}"
    signal = await _redis_get(stop_key)
    return signal is not None


# ---------------------------------------------------------------------------
# 获取股票列表（用于分批处理）
# ---------------------------------------------------------------------------

async def _get_stock_list() -> list[str]:
    """从 stock_info 表获取全市场有效股票的 ts_code 列表。

    返回 Tushare 格式的代码（如 600000.SH），用于分批 API 调用。
    """
    from sqlalchemy import select

    from app.core.database import AsyncSessionPG
    from app.models.stock import StockInfo

    async with AsyncSessionPG() as session:
        stmt = (
            select(StockInfo.symbol)
            .where(StockInfo.is_delisted == False)  # noqa: E712
            .order_by(StockInfo.symbol)
        )
        result = await session.execute(stmt)
        symbols = list(result.scalars().all())

    # 将纯 6 位 symbol 转为 Tushare ts_code 格式
    ts_codes = []
    for sym in symbols:
        sym = str(sym)
        if sym.startswith("6"):
            ts_codes.append(f"{sym}.SH")
        elif sym.startswith("0") or sym.startswith("3"):
            ts_codes.append(f"{sym}.SZ")
        elif sym.startswith("4") or sym.startswith("8"):
            ts_codes.append(f"{sym}.BJ")
        else:
            ts_codes.append(f"{sym}.SZ")

    return ts_codes


# ---------------------------------------------------------------------------
# Redis 进度更新
# ---------------------------------------------------------------------------

async def _update_progress(
    task_id: str,
    status: str = "running",
    total: int | None = None,
    completed: int | None = None,
    failed: int | None = None,
    current_item: str = "",
    error_message: str = "",
) -> None:
    """更新 Redis 中的导入进度。"""
    progress_key = f"{_PROGRESS_KEY_PREFIX}{task_id}"

    # 读取现有进度
    raw = await _redis_get(progress_key)
    if raw:
        try:
            progress = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            progress = {}
    else:
        progress = {}

    # 更新字段（completed 单调递增）
    progress["status"] = status
    if total is not None:
        progress["total"] = total
    if completed is not None:
        current_completed = progress.get("completed", 0)
        progress["completed"] = max(current_completed, completed)
    if failed is not None:
        progress["failed"] = failed
    progress["current_item"] = current_item
    if error_message:
        progress["error_message"] = error_message

    await _redis_set(progress_key, json.dumps(progress), ex=_PROGRESS_TTL)


# ---------------------------------------------------------------------------
# 更新 tushare_import_log 记录
# ---------------------------------------------------------------------------

async def _finalize_log(
    log_id: int,
    status: str,
    record_count: int,
    error_message: str | None = None,
) -> None:
    """更新 tushare_import_log 记录的终态。"""
    from sqlalchemy import update

    from app.core.database import AsyncSessionPG
    from app.models.tushare_import import TushareImportLog

    try:
        async with AsyncSessionPG() as session:
            stmt = (
                update(TushareImportLog)
                .where(TushareImportLog.id == log_id)
                .values(
                    status=status,
                    record_count=record_count,
                    error_message=error_message[:500] if error_message else None,
                    finished_at=datetime.now(),
                )
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:
        logger.error("更新导入日志失败 log_id=%d: %s", log_id, exc)


# ---------------------------------------------------------------------------
# PostgreSQL 写入
# ---------------------------------------------------------------------------

async def _write_to_postgresql(rows: list[dict], entry: ApiEntry) -> None:
    """写入 PostgreSQL，根据 ApiEntry 的 conflict_columns 和 conflict_action 构建 SQL。

    - conflict_action="do_nothing" + conflict_columns 非空:
        INSERT ... ON CONFLICT (cols) DO NOTHING
    - conflict_action="do_update" + conflict_columns 非空:
        INSERT ... ON CONFLICT (cols) DO UPDATE SET col=EXCLUDED.col
    - conflict_columns 为空:
        简单 INSERT（无 ON CONFLICT）

    使用 AsyncSessionPG，事务保证单批原子性。
    自动过滤掉目标表中不存在的列，避免 Tushare 原始字段名与 DB 列名不匹配导致的错误。
    自动将 Tushare 日期字符串（YYYYMMDD）转换为 Python date 对象。
    """
    if not rows:
        return

    from datetime import date as date_type
    from datetime import datetime as datetime_type
    from decimal import Decimal, InvalidOperation

    from sqlalchemy import Boolean, Date, DateTime, Numeric
    from sqlalchemy import text

    from app.core.database import AsyncSessionPG, PGBase

    # 确保所有 ORM 模型已注册到 PGBase.metadata（Celery worker 中可能未自动导入）
    import app.models.stock  # noqa: F401
    import app.models.tushare_import  # noqa: F401
    import app.models.sector  # noqa: F401

    # 获取目标表的实际列名集合和列类型信息
    table_columns: set[str] | None = None
    date_columns: set[str] = set()
    bool_columns: set[str] = set()
    numeric_columns: set[str] = set()
    table_obj = PGBase.metadata.tables.get(entry.target_table)
    if table_obj is not None:
        table_columns = {col.name for col in table_obj.columns}
        for col in table_obj.columns:
            if isinstance(col.type, (Date, DateTime)):
                date_columns.add(col.name)
            elif isinstance(col.type, Boolean):
                bool_columns.add(col.name)
            elif isinstance(col.type, Numeric):
                numeric_columns.add(col.name)
    else:
        logger.warning(
            "目标表 %s 未在 ORM metadata 中找到，跳过列过滤和类型转换",
            entry.target_table,
        )

    # 收集所有列名（取第一行的键），过滤掉目标表中不存在的列
    raw_columns = list(rows[0].keys())
    if table_columns is not None:
        columns = [c for c in raw_columns if c in table_columns]
    else:
        columns = raw_columns

    if not columns:
        return

    # 过滤行数据，只保留有效列，并自动转换类型
    def _coerce_row(row: dict) -> dict:
        """过滤列并将 Tushare 原始值转换为 asyncpg 兼容的 Python 类型。

        - Date 列：YYYYMMDD / YYYY-MM-DD 字符串 → date 对象
        - Boolean 列：int (0/1) → bool
        - Numeric 列：str → Decimal
        """
        result = {}
        for k, v in row.items():
            if table_columns is not None and k not in table_columns:
                continue
            if v is None:
                result[k] = v
                continue
            # Date/DateTime 列：字符串 → date
            if k in date_columns and isinstance(v, str):
                try:
                    if len(v) == 8 and v.isdigit():
                        v = date_type(int(v[:4]), int(v[4:6]), int(v[6:8]))
                    elif len(v) == 10 and "-" in v:
                        v = date_type.fromisoformat(v)
                    else:
                        v = None
                except (ValueError, TypeError):
                    v = None
            # Boolean 列：int → bool
            elif k in bool_columns and not isinstance(v, bool):
                v = bool(v)
            # Numeric 列：str → Decimal
            elif k in numeric_columns and isinstance(v, str):
                try:
                    v = Decimal(v) if v else None
                except (InvalidOperation, ValueError):
                    v = None
            result[k] = v
        return result

    filtered_rows = [_coerce_row(row) for row in rows]

    # 构建 INSERT 语句
    col_list = ", ".join(columns)
    val_placeholders = ", ".join(f":{col}" for col in columns)

    if entry.conflict_columns and entry.conflict_action == "do_nothing":
        conflict_cols = ", ".join(entry.conflict_columns)
        sql = (
            f"INSERT INTO {entry.target_table} ({col_list}) "
            f"VALUES ({val_placeholders}) "
            f"ON CONFLICT ({conflict_cols}) DO NOTHING"
        )
    elif entry.conflict_columns and entry.conflict_action == "do_update":
        conflict_cols = ", ".join(entry.conflict_columns)
        # 更新 update_columns 中指定的列，如果未指定则更新所有非冲突列
        update_cols = entry.update_columns or [
            c for c in columns if c not in entry.conflict_columns
        ]
        if update_cols:
            # 只更新 INSERT 列表中存在的列（用 EXCLUDED 引用），
            # updated_at 特殊处理为 NOW()，不在 INSERT 中的列跳过
            set_parts = []
            columns_set = set(columns)
            for col in update_cols:
                if col == "updated_at":
                    set_parts.append("updated_at = NOW()")
                elif col in columns_set:
                    set_parts.append(f"{col} = EXCLUDED.{col}")
            set_clause = ", ".join(set_parts) if set_parts else ""
            if set_clause:
                sql = (
                    f"INSERT INTO {entry.target_table} ({col_list}) "
                    f"VALUES ({val_placeholders}) "
                    f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {set_clause}"
                )
            else:
                sql = (
                    f"INSERT INTO {entry.target_table} ({col_list}) "
                    f"VALUES ({val_placeholders}) "
                    f"ON CONFLICT ({conflict_cols}) DO NOTHING"
                )
        else:
            # 没有可更新的列，退化为 DO NOTHING
            sql = (
                f"INSERT INTO {entry.target_table} ({col_list}) "
                f"VALUES ({val_placeholders}) "
                f"ON CONFLICT ({conflict_cols}) DO NOTHING"
            )
    else:
        # 无冲突策略，简单 INSERT
        sql = (
            f"INSERT INTO {entry.target_table} ({col_list}) "
            f"VALUES ({val_placeholders})"
        )

    stmt = text(sql)

    async with AsyncSessionPG() as session:
        try:
            for row in filtered_rows:
                await session.execute(stmt, row)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# TimescaleDB 写入
# ---------------------------------------------------------------------------

async def _write_to_timescaledb(rows: list[dict], entry: ApiEntry) -> None:
    """写入 TimescaleDB kline 超表。

    将 Tushare 行情数据映射到 kline 表列：
    time, symbol, freq, open, high, low, close, volume, amount, adj_type

    使用 ON CONFLICT (time, symbol, freq, adj_type) DO NOTHING 去重。
    事务保证单批原子性。
    """
    if not rows:
        return

    from sqlalchemy import text

    from app.core.database import AsyncSessionTS

    # 从 entry.extra_config 获取 freq 配置
    freq = entry.extra_config.get("freq", "1d")

    sql = text("""
        INSERT INTO kline (time, symbol, freq, open, high, low, close, volume, amount, adj_type)
        VALUES (:time, :symbol, :freq, :open, :high, :low, :close, :volume, :amount, :adj_type)
        ON CONFLICT (time, symbol, freq, adj_type) DO NOTHING
    """)

    async with AsyncSessionTS() as session:
        try:
            for row in rows:
                # 解析 trade_date → datetime
                trade_date_str = row.get("trade_date", "")
                if trade_date_str and len(str(trade_date_str)) == 8:
                    try:
                        ts = datetime.strptime(str(trade_date_str), "%Y%m%d")
                    except ValueError:
                        continue
                else:
                    continue

                # symbol：优先使用已转换的 symbol 字段，否则从 ts_code 提取
                symbol = row.get("symbol", "")
                if not symbol:
                    ts_code = row.get("ts_code", "")
                    if "." in str(ts_code):
                        symbol = str(ts_code).split(".")[0]
                    else:
                        symbol = str(ts_code)

                if not symbol:
                    continue

                await session.execute(sql, {
                    "time": ts,
                    "symbol": symbol,
                    "freq": freq,
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("vol") or row.get("volume") or 0,
                    "amount": row.get("amount"),
                    "adj_type": 0,
                })
            await session.commit()
        except Exception:
            await session.rollback()
            raise
