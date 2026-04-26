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

import warnings

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.data_engine.date_batch_splitter import DateBatchSplitter
from app.services.data_engine.tushare_adapter import TushareAdapter, TushareAPIError
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    ParamType,
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

# 频率限制（秒）：按 RateLimitGroup 分组，从配置读取
def _build_rate_limit_map() -> dict[RateLimitGroup, float]:
    """从 settings 构建频率限制映射，支持运行时通过环境变量调整。"""
    return {
        RateLimitGroup.KLINE: settings.rate_limit_kline,
        RateLimitGroup.FUNDAMENTALS: settings.rate_limit_fundamentals,
        RateLimitGroup.MONEY_FLOW: settings.rate_limit_money_flow,
        RateLimitGroup.LIMIT_UP: settings.rate_limit_limit_up,
        RateLimitGroup.TIER_80: settings.rate_limit_tier_80,
        RateLimitGroup.TIER_60: settings.rate_limit_tier_60,
        RateLimitGroup.TIER_20: settings.rate_limit_tier_20,
        RateLimitGroup.TIER_10: settings.rate_limit_tier_10,
        RateLimitGroup.TIER_2: settings.rate_limit_tier_2,
    }


_RATE_LIMIT_MAP: dict[RateLimitGroup, float] = _build_rate_limit_map()

# Redis 键前缀和 TTL
_PROGRESS_KEY_PREFIX = "tushare:import:"
_STOP_KEY_PREFIX = "tushare:import:stop:"
_LOCK_KEY_PREFIX = "tushare:import:lock:"
_PROGRESS_TTL = 86400  # 24h

# 网络超时重试配置
_MAX_NETWORK_RETRIES = 3
_RATE_LIMIT_WAIT = 60  # 频率限制等待秒数


# ---------------------------------------------------------------------------
# 截断检测辅助函数
# ---------------------------------------------------------------------------

# 连续截断告警阈值
_CONSECUTIVE_TRUNCATION_THRESHOLD = 3

# 截断重试最大递归深度（防止无限拆分）
_MAX_TRUNCATION_RETRY_DEPTH = 3


def check_chunk_config(
    date_chunk_days: int,
    max_rows: int,
    estimated_daily_rows: int | None,
    api_name: str,
) -> bool:
    """预检查步长配置合理性。

    根据接口的 date_chunk_days 和 max_rows 配置，验证步长是否可能导致数据截断。
    如果 estimated_daily_rows 可用，检查 date_chunk_days * estimated_daily_rows 是否超过 max_rows。

    Args:
        date_chunk_days: 日期分批步长（天数）
        max_rows: 单次 API 返回行数上限
        estimated_daily_rows: 预估每日行数（从 extra_config 读取，可能为 None）
        api_name: 接口名称（用于日志）

    Returns:
        True 表示配置合理，False 表示步长可能过大

    对应需求：6.1
    """
    if estimated_daily_rows is None or estimated_daily_rows <= 0:
        # 无预估数据，无法判断，视为合理
        return True

    estimated_total = date_chunk_days * estimated_daily_rows
    if estimated_total >= max_rows:
        logger.warning(
            "接口 %s 步长配置可能过大：date_chunk_days=%d × estimated_daily_rows=%d = %d >= max_rows=%d，"
            "建议减小 date_chunk_days",
            api_name, date_chunk_days, estimated_daily_rows, estimated_total, max_rows,
        )
        return False

    return True


def check_truncation(
    row_count: int,
    max_rows: int,
    api_name: str,
    chunk_start: str,
    chunk_end: str,
) -> bool:
    """检测单个子区间是否被截断。

    当 API 返回行数达到或超过 max_rows 阈值时，判定为数据可能被截断。

    Args:
        row_count: 实际返回行数
        max_rows: 单次 API 返回行数上限
        api_name: 接口名称（用于日志）
        chunk_start: 子区间起始日期 YYYYMMDD
        chunk_end: 子区间结束日期 YYYYMMDD

    Returns:
        True 表示检测到截断

    对应需求：6.2
    """
    if row_count >= max_rows:
        logger.warning(
            "子区间 %s~%s 返回 %d 行（达到上限，数据可能被截断），api=%s, max_rows=%d",
            chunk_start, chunk_end, row_count, api_name, max_rows,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# 辅助：在同步 Celery worker 中运行异步协程
# ---------------------------------------------------------------------------

def _run_async(coro):
    """在同步 Celery worker 中运行异步协程。

    使用每个 worker 进程独立的持久 event loop，避免 asyncio.run() 每次
    创建/销毁 loop 导致 SQLAlchemy 异步引擎的连接池绑定失效
    （'Event loop is closed' 错误）。
    """
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


def _get_worker_loop():
    """获取当前 worker 进程的持久 event loop（线程局部单例）。"""
    import threading
    if not hasattr(_get_worker_loop, "_local"):
        _get_worker_loop._local = threading.local()
    local = _get_worker_loop._local
    loop = getattr(local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        local.loop = loop
    return loop


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
    soft_time_limit=28800,  # 8 小时，支持 batch_by_sector 模式的大量板块遍历
    time_limit=32400,      # 9 小时（硬限制）
    autoretry_for=(),  # 禁用自动重试，_process_import 内部已有完整的错误处理
    max_retries=0,
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
# 分批策略路由（纯函数，可独立测试）
# ---------------------------------------------------------------------------

def determine_batch_strategy(
    entry: ApiEntry,
    params: dict,
) -> str:
    """根据注册表配置和用户参数，确定分批策略。

    纯函数，不依赖外部状态，便于属性测试验证路由优先级。

    优先级路由：
    0. batch_by_sector → "by_sector"（按板块代码遍历，优先级最高）
    1. batch_by_code → "by_code"（若同时 batch_by_date 且有日期范围 → "by_code_and_date"）
    2. INDEX_CODE 且未指定 ts_code → "by_index"
    3. batch_by_date 且有日期范围 → "by_date"
    4. 兜底：未声明 batch_by_date 但运行时检测到 DATE_RANGE 参数且有日期范围 → "by_date_fallback"
    5. 以上均不满足 → "single"

    Args:
        entry: 接口注册信息
        params: 用户传入的导入参数

    Returns:
        策略标识字符串：
        "by_sector", "by_code", "by_code_and_date", "by_index", "by_date", "by_date_fallback", "single"

    对应需求：4.1, 4.2, sector-member-batch-import 需求 1.1
    """
    has_date_params = bool(params.get("start_date") and params.get("end_date"))
    has_ts_code = bool(params.get("ts_code"))

    # 优先级 0（新增）：batch_by_sector — 按板块代码遍历，优先级高于所有其他策略
    if entry.batch_by_sector:
        return "by_sector"

    # 优先级 1：batch_by_code
    use_batch_code = entry.batch_by_code
    if not use_batch_code and not has_ts_code:
        # 接口支持 stock_code 参数但用户未传 ts_code → 自动按全市场分批
        has_stock_param = (
            ParamType.STOCK_CODE in entry.required_params
            or ParamType.STOCK_CODE in entry.optional_params
        )
        if has_stock_param:
            use_batch_code = True

    if use_batch_code:
        # 双重分批：同时 batch_by_date 且有日期范围
        if entry.batch_by_date and has_date_params:
            return "by_code_and_date"
        return "by_code"

    # 优先级 2：INDEX_CODE 且未指定 ts_code
    if not has_ts_code:
        has_index_param = (
            ParamType.INDEX_CODE in entry.required_params
            or ParamType.INDEX_CODE in entry.optional_params
        )
        if has_index_param:
            return "by_index"

    # 优先级 3：batch_by_date 声明 + 有日期范围
    if entry.batch_by_date and has_date_params:
        return "by_date"

    # 优先级 4：兜底 — 未声明 batch_by_date 但运行时检测到 DATE_RANGE 参数且有日期范围
    if not entry.batch_by_date and has_date_params:
        has_date_range = (
            ParamType.DATE_RANGE in entry.required_params
            or ParamType.DATE_RANGE in entry.optional_params
        )
        if has_date_range:
            return "by_date_fallback"

    # 优先级 5：单次调用
    return "single"


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
    3. 通过 determine_batch_strategy() 确定分批策略
    4. 每批：检查停止信号 → 调用 API → 字段映射 → 代码转换 → 写入 DB → 更新进度
    5. 完成后更新 tushare_import_log

    对应需求：4.1, 4.2, 5.3
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
        # 使用纯函数确定分批策略
        strategy = determine_batch_strategy(entry, params)

        if strategy == "by_code" or strategy == "by_code_and_date":
            result = await _process_batched(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        elif strategy == "by_index":
            result = await _process_batched_index(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        elif strategy == "by_sector":
            result = await _process_batched_by_sector(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        elif strategy == "by_date":
            result = await _process_batched_by_date(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        elif strategy == "by_date_fallback":
            # 兜底：未声明 batch_by_date 但运行时检测到 DATE_RANGE + 日期参数
            logger.warning(
                "接口 %s 未声明 batch_by_date=True 但检测到 DATE_RANGE 参数和日期范围，"
                "使用默认步长 %d 天进行兜底日期分批。建议在注册表中显式配置 batch_by_date。",
                api_name, _DATE_BATCH_DAYS,
            )
            result = await _process_batched_by_date(
                entry, adapter, params, task_id, log_id, rate_delay,
            )
        else:
            # strategy == "single"
            result = await _process_single(
                entry, adapter, params, task_id, log_id, rate_delay,
            )

        total_records = result.get("record_count", 0)
        status = result.get("status", "completed")
        batch_stats = result.get("batch_stats")

        if status == "stopped":
            await _finalize_log(log_id, "stopped", total_records, batch_stats=batch_stats)
            await _update_progress(task_id, status="stopped",
                                   total=total_records, completed=total_records)
        else:
            await _finalize_log(log_id, "completed", total_records, batch_stats=batch_stats)
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
                           current_item=entry.api_name, batch_mode="single")

    # 支持 extra_config 中的 tushare_api_name（实际 Tushare 接口名）和 default_params（默认参数）
    actual_api_name = entry.extra_config.get("tushare_api_name", entry.api_name)
    call_params = {**entry.extra_config.get("default_params", {}), **params}

    # 某些 Tushare 接口只接受 trade_date 而非 start_date/end_date（如 top_list、top_inst）
    # 将 start_date 转为 trade_date
    if entry.extra_config.get("use_trade_date_loop"):
        if "start_date" in call_params and "trade_date" not in call_params:
            call_params["trade_date"] = call_params.pop("start_date")
        call_params.pop("end_date", None)

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
                           total=1, batch_mode="single")

    return {"status": "completed", "record_count": len(converted_rows)}


# ---------------------------------------------------------------------------
# 按日期分批处理
# ---------------------------------------------------------------------------

# Tushare 单次返回行数上限（超过此数量说明数据被截断）
_TUSHARE_MAX_ROWS = 3000

# 日期分批默认步长（天）
_DATE_BATCH_DAYS = 30


def _generate_date_chunks(
    start_date: str, end_date: str, chunk_days: int = _DATE_BATCH_DAYS,
) -> list[tuple[str, str]]:
    """将日期范围拆分为多个子区间（YYYYMMDD 格式）。

    .. deprecated::
        请使用 ``DateBatchSplitter.split()`` 替代。本函数保留仅为向后兼容，
        内部已委托给 DateBatchSplitter。

    Args:
        start_date: 起始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        chunk_days: 每个子区间的天数

    Returns:
        [(chunk_start, chunk_end), ...] 列表
    """
    warnings.warn(
        "_generate_date_chunks 已弃用，请使用 DateBatchSplitter.split() 替代",
        DeprecationWarning,
        stacklevel=2,
    )
    return DateBatchSplitter.split(start_date, end_date, chunk_days)


async def _process_chunk_with_retry(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    chunk_start: str,
    chunk_end: str,
    max_rows: int,
    rate_delay: float,
    actual_api_name: str,
    default_params: dict,
    inject_fields: dict | None,
    use_trade_date_loop: bool,
    depth: int = 0,
) -> dict:
    """处理单个日期子区间，支持截断自动重试（递归拆分）。

    当检测到数据截断（返回行数 >= max_rows）时，自动将当前子区间拆分为两个更小的
    子区间（步长减半），递归处理每个子区间。通过 depth 参数限制最大递归深度，
    防止无限拆分。

    Args:
        entry: 接口注册信息
        adapter: Tushare API 适配器
        params: 用户传入的导入参数
        task_id: 任务唯一标识
        chunk_start: 子区间起始日期 YYYYMMDD
        chunk_end: 子区间结束日期 YYYYMMDD
        max_rows: 单次 API 返回行数上限
        rate_delay: 频率限制延迟（秒）
        actual_api_name: 实际 Tushare 接口名
        default_params: 默认参数
        inject_fields: 注入字段（可选）
        use_trade_date_loop: 是否使用 trade_date 循环模式
        depth: 当前递归深度（0 = 首次调用）

    Returns:
        {"records": int, "truncated": bool, "retried": bool, "retry_details": list}
        - records: 本次处理写入的记录数
        - truncated: 是否检测到截断（最终状态）
        - retried: 是否执行了重试
        - retry_details: 重试详情列表

    对应需求：2.4, 2.5
    """
    # 构建本次 API 调用参数
    call_params = {**default_params, **params}
    call_params["start_date"] = chunk_start
    call_params["end_date"] = chunk_end

    # 处理 use_trade_date_loop 模式
    if use_trade_date_loop:
        call_params["trade_date"] = chunk_start
        call_params.pop("start_date", None)
        call_params.pop("end_date", None)

    data = await _call_api_with_retry(
        adapter, actual_api_name, call_params, entry,
    )
    rows = TushareAdapter._rows_from_data(data)

    if not rows:
        return {"records": 0, "truncated": False, "retried": False, "retry_details": []}

    # 检测截断
    truncated = check_truncation(
        len(rows), max_rows, entry.api_name, chunk_start, chunk_end,
    )

    if truncated:
        # 达到最大重试深度，记录 ERROR 并写入已获取的（可能不完整的）数据
        if depth >= _MAX_TRUNCATION_RETRY_DEPTH:
            logger.error(
                "截断重试达到最大深度 %d，无法进一步拆分子区间 %s~%s，"
                "数据可能不完整。api=%s, rows=%d, max_rows=%d",
                _MAX_TRUNCATION_RETRY_DEPTH, chunk_start, chunk_end,
                entry.api_name, len(rows), max_rows,
            )
            # 写入已获取的数据（尽管可能不完整）
            records = await _write_chunk_rows(rows, entry, inject_fields)
            return {
                "records": records,
                "truncated": True,
                "retried": True,
                "retry_details": [{
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "depth": depth,
                    "action": "max_depth_reached",
                    "rows": len(rows),
                }],
            }

        # 丢弃当前截断数据，拆分子区间重新请求
        logger.info(
            "截断自动重试：拆分子区间 %s~%s（depth=%d），api=%s, rows=%d >= max_rows=%d",
            chunk_start, chunk_end, depth + 1, entry.api_name, len(rows), max_rows,
        )

        # 使用 DateBatchSplitter 将当前子区间拆分为两半
        from datetime import datetime as _dt
        start_dt = _dt.strptime(chunk_start, "%Y%m%d").date()
        end_dt = _dt.strptime(chunk_end, "%Y%m%d").date()
        total_days = (end_dt - start_dt).days + 1

        # 如果只有 1 天，无法再拆分
        if total_days <= 1:
            logger.error(
                "截断重试：子区间 %s~%s 仅 %d 天，无法进一步拆分，"
                "数据可能不完整。api=%s, rows=%d",
                chunk_start, chunk_end, total_days, entry.api_name, len(rows),
            )
            records = await _write_chunk_rows(rows, entry, inject_fields)
            return {
                "records": records,
                "truncated": True,
                "retried": True,
                "retry_details": [{
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "depth": depth,
                    "action": "cannot_split_further",
                    "rows": len(rows),
                }],
            }

        # 拆分为两半
        half_days = max(total_days // 2, 1)
        sub_chunks = DateBatchSplitter.split(chunk_start, chunk_end, half_days)

        total_records = 0
        still_truncated = False
        retry_details: list[dict] = []

        for sub_start, sub_end in sub_chunks:
            # 检查停止信号
            if await _check_stop_signal(task_id):
                return {
                    "records": total_records,
                    "truncated": still_truncated,
                    "retried": True,
                    "retry_details": retry_details,
                    "stopped": True,
                }

            sub_result = await _process_chunk_with_retry(
                entry=entry,
                adapter=adapter,
                params=params,
                task_id=task_id,
                chunk_start=sub_start,
                chunk_end=sub_end,
                max_rows=max_rows,
                rate_delay=rate_delay,
                actual_api_name=actual_api_name,
                default_params=default_params,
                inject_fields=inject_fields,
                use_trade_date_loop=use_trade_date_loop,
                depth=depth + 1,
            )

            total_records += sub_result["records"]
            if sub_result["truncated"]:
                still_truncated = True
            retry_details.extend(sub_result.get("retry_details", []))

            # 子区间处理后检查停止信号
            if sub_result.get("stopped"):
                return {
                    "records": total_records,
                    "truncated": still_truncated,
                    "retried": True,
                    "retry_details": retry_details,
                    "stopped": True,
                }

            # 频率限制
            time.sleep(rate_delay)

        return {
            "records": total_records,
            "truncated": still_truncated,
            "retried": True,
            "retry_details": [{
                "chunk_start": chunk_start,
                "chunk_end": chunk_end,
                "depth": depth,
                "action": "split_and_retry",
                "sub_chunks": len(sub_chunks),
                "total_records": total_records,
            }] + retry_details,
        }

    # 未截断，正常写入数据
    records = await _write_chunk_rows(rows, entry, inject_fields)
    return {"records": records, "truncated": False, "retried": False, "retry_details": []}


async def _write_chunk_rows(
    rows: list[dict],
    entry: ApiEntry,
    inject_fields: dict | None,
) -> int:
    """将行数据写入数据库（字段映射 + 代码转换 + 写入）。

    Args:
        rows: API 返回的原始行数据
        entry: 接口注册信息
        inject_fields: 注入字段（可选）

    Returns:
        成功写入的记录数
    """
    if inject_fields:
        for row in rows:
            row.update(inject_fields)

    mapped_rows = _apply_field_mappings(rows, entry)
    converted_rows = _convert_codes(mapped_rows, entry)

    if entry.storage_engine == StorageEngine.TS:
        await _write_to_timescaledb(converted_rows, entry)
    else:
        await _write_to_postgresql(converted_rows, entry)

    return len(converted_rows)


async def _process_batched_by_date(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """按日期分批模式：将大日期范围拆分为小区间逐批调用 API。

    使用 DateBatchSplitter 进行日期拆分，步长取自注册表 entry.date_chunk_days。
    截断阈值取自 entry.extra_config.get("max_rows", 3000)。

    当检测到截断时，自动将子区间拆分为更小的子区间重新请求（最多 3 层递归）。
    当连续截断计数达到阈值（3 次）时，自动将后续所有子区间的步长减半。

    适用于带 DATE_RANGE 参数且单次调用可能超过 Tushare 行数上限的接口
    （如 dc_daily、ths_daily、tdx_daily、top_list 等）。

    对应需求：2.4, 2.5, 3.1, 3.2, 4.3, 4.4
    """
    start_date = params.get("start_date", "")
    end_date = params.get("end_date", "")
    if not start_date or not end_date:
        # 没有日期范围，退回单次调用
        return await _process_single(
            entry, adapter, params, task_id, log_id, rate_delay,
        )

    # 使用注册表配置的步长（兜底策略使用默认值 30）
    chunk_days = entry.date_chunk_days if entry.date_chunk_days > 0 else _DATE_BATCH_DAYS
    chunks = DateBatchSplitter.split(start_date, end_date, chunk_days)

    # 使用注册表配置的 max_rows 阈值（默认 3000）
    max_rows = entry.extra_config.get("max_rows", _TUSHARE_MAX_ROWS)

    # 预检查步长配置合理性（对应需求 6.1）
    estimated_daily_rows = entry.extra_config.get("estimated_daily_rows")
    check_chunk_config(chunk_days, max_rows, estimated_daily_rows, entry.api_name)

    total = len(chunks)
    completed = 0
    total_records = 0
    success_chunks = 0
    consecutive_truncation_count = 0
    truncation_warnings: list[dict] = []
    needs_smaller_chunk = False
    # 截断自动恢复记录（对应需求 2.5）
    truncation_recoveries: list[dict] = []

    await _update_progress(
        task_id, status="running", total=total, completed=0,
        current_item=f"{start_date}-{end_date}",
        batch_mode="by_date",
    )

    actual_api_name = entry.extra_config.get("tushare_api_name", entry.api_name)
    default_params = entry.extra_config.get("default_params", {})
    inject_fields = entry.extra_config.get("inject_fields")
    use_trade_date_loop = entry.extra_config.get("use_trade_date_loop", False)

    # 当前生效的 chunk 列表（连续截断时可能重新拆分剩余区间）
    remaining_chunks = list(chunks)
    chunk_index = 0

    while chunk_index < len(remaining_chunks):
        chunk_start, chunk_end = remaining_chunks[chunk_index]

        # 检查停止信号
        if await _check_stop_signal(task_id):
            logger.info("Tushare 导入收到停止信号 task_id=%s", task_id)
            # 构建已完成部分的分批统计
            batch_stats = _build_batch_stats(
                total, success_chunks, truncation_warnings, truncation_recoveries,
                needs_smaller_chunk,
            )
            return {"status": "stopped", "record_count": total_records, "batch_stats": batch_stats}

        try:
            result = await _process_chunk_with_retry(
                entry=entry,
                adapter=adapter,
                params=params,
                task_id=task_id,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                max_rows=max_rows,
                rate_delay=rate_delay,
                actual_api_name=actual_api_name,
                default_params=default_params,
                inject_fields=inject_fields,
                use_trade_date_loop=use_trade_date_loop,
                depth=0,
            )

            # 处理停止信号（从递归重试中传播）
            if result.get("stopped"):
                batch_stats = _build_batch_stats(
                    total, success_chunks, truncation_warnings, truncation_recoveries,
                    needs_smaller_chunk,
                )
                return {
                    "status": "stopped",
                    "record_count": total_records + result["records"],
                    "batch_stats": batch_stats,
                }

            total_records += result["records"]

            if result["truncated"]:
                consecutive_truncation_count += 1
                # 记录截断警告
                truncation_warnings.append({
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "row_count": result["records"],
                    "max_rows": max_rows,
                    "retried": result["retried"],
                })

                # 记录截断恢复详情
                if result["retried"]:
                    truncation_recoveries.append({
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                        "retry_details": result.get("retry_details", []),
                        "recovered_records": result["records"],
                    })

                # 连续截断自动缩小后续步长（对应需求 2.5）
                if (
                    consecutive_truncation_count >= _CONSECUTIVE_TRUNCATION_THRESHOLD
                    and not needs_smaller_chunk
                ):
                    needs_smaller_chunk = True
                    new_chunk_days = max(chunk_days // 2, 1)
                    logger.warning(
                        "接口 %s 连续 %d 个子区间数据被截断，自动将后续步长从 %d 天缩小到 %d 天",
                        entry.api_name, consecutive_truncation_count,
                        chunk_days, new_chunk_days,
                    )

                    # 重新拆分剩余未处理的子区间
                    remaining_after = remaining_chunks[chunk_index + 1:]
                    if remaining_after:
                        # 取剩余区间的整体范围，用新步长重新拆分
                        remaining_start = remaining_after[0][0]
                        remaining_end = remaining_after[-1][1]
                        new_chunks = DateBatchSplitter.split(
                            remaining_start, remaining_end, new_chunk_days,
                        )
                        remaining_chunks = remaining_chunks[:chunk_index + 1] + new_chunks
                        total = len(remaining_chunks)

                        # 记录步长缩小恢复信息
                        truncation_recoveries.append({
                            "action": "auto_shrink_step",
                            "old_chunk_days": chunk_days,
                            "new_chunk_days": new_chunk_days,
                            "remaining_chunks_resplit": len(new_chunks),
                            "consecutive_truncation_count": consecutive_truncation_count,
                        })

                    chunk_days = new_chunk_days

                if result["records"] > 0:
                    success_chunks += 1
            else:
                # 未截断，重置连续截断计数
                consecutive_truncation_count = 0
                if result["records"] > 0:
                    success_chunks += 1
                elif result["records"] == 0:
                    # 无数据返回也算成功处理
                    success_chunks += 1

        except TushareAPIError as api_exc:
            if api_exc.code and api_exc.code == -2001:
                raise
            logger.error(
                "API 调用失败 api=%s chunk=%s~%s: %s",
                entry.api_name, chunk_start, chunk_end, api_exc,
            )
        except Exception as exc:
            logger.error(
                "处理失败 api=%s chunk=%s~%s: %s",
                entry.api_name, chunk_start, chunk_end, exc,
            )

        completed += 1
        await _update_progress(
            task_id, status="running",
            total=total, completed=completed,
            current_item=f"{chunk_start}-{chunk_end}",
            batch_mode="by_date",
            truncation_warnings=truncation_warnings,
            needs_smaller_chunk=needs_smaller_chunk,
        )

        # 频率限制
        time.sleep(rate_delay)

        chunk_index += 1

    # 构建分批统计信息（对应需求 8.1, 8.2）
    batch_stats = _build_batch_stats(
        total, success_chunks, truncation_warnings, truncation_recoveries,
        needs_smaller_chunk,
    )

    return {"status": "completed", "record_count": total_records, "batch_stats": batch_stats}


def _build_batch_stats(
    total_chunks: int,
    success_chunks: int,
    truncation_warnings: list[dict],
    truncation_recoveries: list[dict],
    needs_smaller_chunk: bool,
) -> dict:
    """构建分批统计信息字典。

    Args:
        total_chunks: 总子区间数
        success_chunks: 成功处理的子区间数
        truncation_warnings: 截断警告列表
        truncation_recoveries: 截断自动恢复详情列表
        needs_smaller_chunk: 是否触发了步长自动缩小

    Returns:
        分批统计字典，包含截断恢复详情

    对应需求：8.1, 8.2
    """
    stats: dict = {
        "batch_mode": "by_date",
        "total_chunks": total_chunks,
        "success_chunks": success_chunks,
        "truncation_count": len(truncation_warnings),
        "truncation_details": [
            {
                "chunk": f"{w['chunk_start']}-{w['chunk_end']}",
                "rows": w.get("row_count", 0),
                "max_rows": w.get("max_rows", 0),
                "retried": w.get("retried", False),
            }
            for w in truncation_warnings[:10]
        ],
    }

    # 截断自动恢复详情（对应需求 2.5）
    if truncation_recoveries:
        stats["truncation_recoveries"] = truncation_recoveries[:10]

    if needs_smaller_chunk:
        stats["auto_shrink_applied"] = True

    return stats


# ---------------------------------------------------------------------------
# 按代码分批处理
# ---------------------------------------------------------------------------

async def _process_batched(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """分批模式：按股票代码列表分批调用 API。

    支持双重分批：当接口同时标记 batch_by_date=True 且用户提供了日期范围参数时，
    在每个 ts_code 的调用中额外按日期子区间逐批调用，避免单只股票长日期范围数据截断。

    对应需求：1.8, 4.1
    """
    # 获取股票列表
    stock_codes = await _get_stock_list()
    if not stock_codes:
        return {"status": "completed", "record_count": 0}

    # 判断是否需要双重分批：batch_by_date=True 且用户提供了 start_date + end_date
    has_date_params = bool(params.get("start_date") and params.get("end_date"))
    dual_batch = entry.batch_by_date and has_date_params

    # 双重分批时，预先拆分日期区间
    date_chunks: list[tuple[str, str]] = []
    if dual_batch:
        chunk_days = entry.date_chunk_days if entry.date_chunk_days > 0 else _DATE_BATCH_DAYS
        date_chunks = DateBatchSplitter.split(
            params["start_date"], params["end_date"], chunk_days,
        )

    # 计算总进度：双重分批时 total = 股票数 × 日期子区间数，否则 total = 股票数
    num_codes = len(stock_codes)
    num_date_chunks = len(date_chunks) if dual_batch else 1
    total = num_codes * num_date_chunks
    completed = 0
    total_records = 0

    # 截断检测阈值（双重分批时使用）
    max_rows = entry.extra_config.get("max_rows", _TUSHARE_MAX_ROWS)

    # 确定 batch_mode 标识（对应需求 7.4）
    batch_mode = "by_code_and_date" if dual_batch else "by_code"

    await _update_progress(task_id, status="running", total=total, completed=0,
                           batch_mode=batch_mode)

    inject_fields = entry.extra_config.get("inject_fields")

    # 按 BATCH_SIZE 分批
    for batch_start in range(0, num_codes, BATCH_SIZE):
        batch = stock_codes[batch_start: batch_start + BATCH_SIZE]

        for ts_code in batch:
            if dual_batch:
                # 双重分批：对当前 ts_code 按日期子区间逐批调用
                for chunk_start, chunk_end in date_chunks:
                    # 检查停止信号
                    if await _check_stop_signal(task_id):
                        logger.info("Tushare 导入收到停止信号 task_id=%s", task_id)
                        return {"status": "stopped", "record_count": total_records}

                    # 构建本次 API 调用参数（ts_code + 日期子区间）
                    call_params = {**params, "ts_code": ts_code,
                                   "start_date": chunk_start, "end_date": chunk_end}

                    try:
                        data = await _call_api_with_retry(
                            adapter, entry.api_name, call_params, entry,
                        )
                        rows = TushareAdapter._rows_from_data(data)

                        if rows:
                            if inject_fields:
                                for row in rows:
                                    row.update(inject_fields)

                            mapped_rows = _apply_field_mappings(rows, entry)
                            converted_rows = _convert_codes(mapped_rows, entry)

                            try:
                                if entry.storage_engine == StorageEngine.TS:
                                    await _write_to_timescaledb(converted_rows, entry)
                                else:
                                    await _write_to_postgresql(converted_rows, entry)
                                total_records += len(converted_rows)
                            except Exception as db_exc:
                                logger.error(
                                    "DB 写入失败 api=%s ts_code=%s chunk=%s~%s: %s",
                                    entry.api_name, ts_code, chunk_start, chunk_end, db_exc,
                                )

                            # 截断检测：单个子区间返回行数达到上限
                            if len(rows) >= max_rows:
                                logger.warning(
                                    "双重分批子区间 ts_code=%s %s~%s 返回 %d 行（可能被截断），"
                                    "api=%s, max_rows=%d",
                                    ts_code, chunk_start, chunk_end, len(rows),
                                    entry.api_name, max_rows,
                                )

                    except TushareAPIError as api_exc:
                        if api_exc.code and api_exc.code == -2001:
                            raise  # Token 无效，终止整个任务
                        logger.error(
                            "API 调用失败 api=%s ts_code=%s chunk=%s~%s: %s",
                            entry.api_name, ts_code, chunk_start, chunk_end, api_exc,
                        )
                    except Exception as exc:
                        logger.error(
                            "处理失败 api=%s ts_code=%s chunk=%s~%s: %s",
                            entry.api_name, ts_code, chunk_start, chunk_end, exc,
                        )

                    completed += 1
                    await _update_progress(
                        task_id, status="running",
                        total=total, completed=completed,
                        current_item=f"{ts_code}:{chunk_start}-{chunk_end}",
                        batch_mode=batch_mode,
                    )

                    # 频率限制
                    time.sleep(rate_delay)
            else:
                # 原有逻辑：单次调用（非双重分批）
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
                        if inject_fields:
                            for row in rows:
                                row.update(inject_fields)

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
                    batch_mode=batch_mode,
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


async def _get_index_list() -> list[str]:
    """从 index_info 表获取全部指数的 ts_code 列表。"""
    from sqlalchemy import select

    from app.core.database import AsyncSessionPG
    from app.models.tushare_import import IndexInfo

    async with AsyncSessionPG() as session:
        stmt = select(IndexInfo.ts_code).order_by(IndexInfo.ts_code)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _process_batched_index(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """按指数代码列表分批调用 API（用于 index_weekly/index_monthly 等）。"""
    index_codes = await _get_index_list()
    if not index_codes:
        return {"status": "completed", "record_count": 0}

    total = len(index_codes)
    completed = 0
    total_records = 0

    await _update_progress(task_id, status="running", total=total, completed=0,
                           batch_mode="by_index")

    for ts_code in index_codes:
        if await _check_stop_signal(task_id):
            return {"status": "stopped", "record_count": total_records}

        # 根据接口要求选择参数名：index_weight 用 index_code，其他用 ts_code
        code_param_name = "index_code" if entry.api_name == "index_weight" else "ts_code"
        call_params = {**params, code_param_name: ts_code}
        # 仅在 use_trade_date_loop 模式下移除 start_date/end_date
        if entry.extra_config.get("use_trade_date_loop"):
            call_params.pop("start_date", None)
            call_params.pop("end_date", None)

        try:
            data = await _call_api_with_retry(adapter, entry.api_name, call_params, entry)
            rows = TushareAdapter._rows_from_data(data)

            if rows:
                inject_fields = entry.extra_config.get("inject_fields")
                if inject_fields:
                    for row in rows:
                        row.update(inject_fields)

                mapped_rows = _apply_field_mappings(rows, entry)
                converted_rows = _convert_codes(mapped_rows, entry)

                try:
                    if entry.storage_engine == StorageEngine.TS:
                        await _write_to_timescaledb(converted_rows, entry)
                    else:
                        await _write_to_postgresql(converted_rows, entry)
                    total_records += len(converted_rows)
                except Exception as db_exc:
                    logger.error("DB 写入失败 api=%s ts_code=%s: %s", entry.api_name, ts_code, db_exc)

        except TushareAPIError as api_exc:
            if api_exc.code and api_exc.code == -2001:
                raise
            logger.error("API 调用失败 api=%s ts_code=%s: %s", entry.api_name, ts_code, api_exc)
        except Exception as exc:
            logger.error("处理失败 api=%s ts_code=%s: %s", entry.api_name, ts_code, exc)

        completed += 1
        await _update_progress(task_id, status="running", total=total, completed=completed,
                               current_item=ts_code, batch_mode="by_index")
        time.sleep(rate_delay)

    return {"status": "completed", "record_count": total_records}


async def _process_batched_by_sector(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    """按板块代码遍历模式：从 sector_info 获取所有板块代码，逐个调用 API。

    流程：
    1. 从 inject_fields 获取 data_source
    2. 查询 sector_info WHERE data_source=:ds，获取 (sector_code, name) 列表
    3. 遍历每个板块代码：
       a. 检查停止信号
       b. 调用 Tushare API（ts_code=sector_code）
       c. inject_fields + 字段映射 + _convert_codes + 写入 DB
       d. 更新进度（含板块名称）
       e. 频率限制延迟
    4. 汇总结果（成功/失败/空数据计数）

    对应需求：sector-member-batch-import 需求 1.2-1.7, 6.1-6.4
    """
    from sqlalchemy import select

    from app.core.database import AsyncSessionPG
    from app.models.sector import SectorInfo

    # 从 inject_fields 获取 data_source
    inject_fields = entry.extra_config.get("inject_fields", {})
    ds = inject_fields.get("data_source")
    if not ds:
        logger.error("batch_by_sector 模式缺少 inject_fields.data_source, api=%s", entry.api_name)
        await _finalize_log(log_id, "failed", 0, "batch_by_sector 模式缺少 inject_fields.data_source")
        return {"status": "failed", "error": "缺少 data_source", "record_count": 0}

    # 查询 sector_info 获取板块代码列表
    async with AsyncSessionPG() as session:
        stmt = (
            select(SectorInfo.sector_code, SectorInfo.name)
            .where(SectorInfo.data_source == ds)
            .order_by(SectorInfo.sector_code)
        )
        result = await session.execute(stmt)
        sector_codes = [(r.sector_code, r.name) for r in result.all()]

    # 空列表检查（前置依赖提示）
    if not sector_codes:
        logger.warning(
            "batch_by_sector 模式下 sector_info 表中无 data_source=%s 的板块，"
            "请先导入板块信息（如 ths_index/dc_index/tdx_index），api=%s",
            ds, entry.api_name,
        )
        return {"status": "completed", "record_count": 0, "batch_stats": {
            "total_sectors": 0, "success_sectors": 0, "failed_sectors": 0, "empty_sectors": 0,
        }}

    total = len(sector_codes)
    completed_count = 0
    total_records = 0
    success_count = 0
    failed_count = 0
    empty_count = 0

    # 截断检测阈值
    max_rows = entry.extra_config.get("max_rows", _TUSHARE_MAX_ROWS)

    await _update_progress(task_id, status="running", total=total, completed=0,
                           batch_mode="by_sector")

    for idx, (sector_code, sector_name) in enumerate(sector_codes):
        # 检查停止信号
        if await _check_stop_signal(task_id):
            logger.info("Tushare 导入收到停止信号 task_id=%s, 已完成 %d/%d 板块", task_id, idx, total)
            return {
                "status": "stopped",
                "record_count": total_records,
                "batch_stats": {
                    "total_sectors": total,
                    "success_sectors": success_count,
                    "failed_sectors": failed_count,
                    "empty_sectors": empty_count,
                },
            }

        # 构建 API 调用参数
        call_params = {**params, "ts_code": sector_code}

        try:
            data = await _call_api_with_retry(adapter, entry.api_name, call_params, entry)
            rows = TushareAdapter._rows_from_data(data)

            if not rows:
                # API 返回空数据，跳过，不计为失败
                empty_count += 1
                logger.debug("板块 %s (%s) 无成分股数据，跳过", sector_code, sector_name)
            else:
                # 截断检测
                if len(rows) >= max_rows:
                    logger.warning(
                        "板块 %s (%s) 返回 %d 行（可能被截断），api=%s, max_rows=%d",
                        sector_code, sector_name, len(rows), entry.api_name, max_rows,
                    )

                # inject_fields
                if inject_fields:
                    for row in rows:
                        row.update(inject_fields)

                # 动态注入 trade_date（针对 ths_member 等 API 不返回日期的接口）
                # 条件：字段映射中没有 trade_date，且 inject_fields 中也没有
                has_trade_date_in_mapping = any(
                    fm.target == "trade_date" for fm in entry.field_mappings
                )
                if not has_trade_date_in_mapping and "trade_date" not in inject_fields:
                    from datetime import date
                    current_date = date.today().strftime("%Y%m%d")
                    for row in rows:
                        row["trade_date"] = current_date

                # 字段映射 + 代码转换
                mapped_rows = _apply_field_mappings(rows, entry)
                converted_rows = _convert_codes(mapped_rows, entry)

                try:
                    if entry.storage_engine == StorageEngine.TS:
                        await _write_to_timescaledb(converted_rows, entry)
                    else:
                        await _write_to_postgresql(converted_rows, entry)
                    total_records += len(converted_rows)
                    success_count += 1
                except Exception as db_exc:
                    logger.error(
                        "DB 写入失败 api=%s sector=%s (%s): %s",
                        entry.api_name, sector_code, sector_name, db_exc,
                    )
                    failed_count += 1

        except TushareAPIError as api_exc:
            # Token 无效，终止整个任务
            if api_exc.code and api_exc.code == -2001:
                raise
            # 其他 API 错误，记录并继续
            logger.warning(
                "API 调用失败 api=%s sector=%s (%s): %s",
                entry.api_name, sector_code, sector_name, api_exc,
            )
            failed_count += 1
        except Exception as exc:
            logger.error(
                "处理失败 api=%s sector=%s (%s): %s",
                entry.api_name, sector_code, sector_name, exc,
            )
            failed_count += 1

        completed_count += 1
        await _update_progress(
            task_id,
            status="running",
            total=total,
            completed=completed_count,
            failed=failed_count,
            current_item=f"{sector_code} ({sector_name})",
            batch_mode="by_sector",
        )

        # 频率限制
        time.sleep(rate_delay)

    logger.info(
        "batch_by_sector 完成 api=%s data_source=%s: 总板块=%d, 成功=%d, 失败=%d, 空数据=%d, 总记录=%d",
        entry.api_name, ds, total, success_count, failed_count, empty_count, total_records,
    )

    return {
        "status": "completed",
        "record_count": total_records,
        "batch_stats": {
            "total_sectors": total,
            "success_sectors": success_count,
            "failed_sectors": failed_count,
            "empty_sectors": empty_count,
        },
    }


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
    batch_mode: str = "",
    truncation_warnings: list[dict] | None = None,
    needs_smaller_chunk: bool = False,
) -> None:
    """更新 Redis 中的导入进度。

    Args:
        task_id: 任务唯一标识
        status: 任务状态（running/completed/failed/stopped）
        total: 总步数
        completed: 已完成步数（单调递增）
        failed: 失败步数
        current_item: 当前处理项标识
        error_message: 错误信息
        batch_mode: 当前分批策略（by_date/by_code/by_code_and_date/by_index/single）
        truncation_warnings: 截断警告列表，每项包含 chunk_start/chunk_end/row_count/max_rows
        needs_smaller_chunk: 连续截断检测标志，建议用户减小步长

    对应需求：7.1, 7.2, 7.3, 7.4, 7.5
    """
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

    # 分批模式标识（对应需求 7.4）
    if batch_mode:
        progress["batch_mode"] = batch_mode

    # 截断警告列表（对应需求 7.3）
    if truncation_warnings is not None:
        progress["truncation_warnings"] = truncation_warnings

    # 连续截断标志（对应需求 7.5）
    if needs_smaller_chunk:
        progress["needs_smaller_chunk"] = True

    await _redis_set(progress_key, json.dumps(progress), ex=_PROGRESS_TTL)


# ---------------------------------------------------------------------------
# 更新 tushare_import_log 记录
# ---------------------------------------------------------------------------

async def _finalize_log(
    log_id: int,
    status: str,
    record_count: int,
    error_message: str | None = None,
    batch_stats: dict | None = None,
) -> None:
    """更新 tushare_import_log 记录的终态。

    Args:
        log_id: 导入日志记录 ID
        status: 终态状态（completed/failed/stopped）
        record_count: 总导入记录数
        error_message: 错误信息（可选）
        batch_stats: 分批统计信息（可选），序列化为 JSON 存入 extra_info 列。
            结构示例：{"batch_mode": "by_date", "total_chunks": 12,
            "success_chunks": 11, "truncation_count": 1,
            "truncation_details": [...]}

    对应需求：8.1, 8.2
    """
    from sqlalchemy import update

    from app.core.database import AsyncSessionPG
    from app.models.tushare_import import TushareImportLog

    try:
        # 序列化 batch_stats 为 JSON 字符串（存入 extra_info 列）
        extra_info_str: str | None = None
        if batch_stats is not None:
            try:
                extra_info_str = json.dumps(batch_stats, ensure_ascii=False)
                # extra_info 列最大 2000 字符，超长时截断
                if len(extra_info_str) > 2000:
                    extra_info_str = extra_info_str[:2000]
            except (TypeError, ValueError) as json_exc:
                logger.warning("序列化 batch_stats 失败 log_id=%d: %s", log_id, json_exc)
                extra_info_str = None

        # 处理截断警告：追加到 error_message（对应需求 8.2）
        final_error_message = error_message
        if batch_stats and batch_stats.get("truncation_count", 0) > 0:
            truncation_details = batch_stats.get("truncation_details", [])
            # 最多记录前 10 个截断子区间
            limited_details = truncation_details[:10]
            truncation_summary = "; ".join(
                f"{d.get('chunk', '?')}({d.get('rows', '?')}行)"
                for d in limited_details
            )
            truncation_msg = f"截断警告({batch_stats['truncation_count']}个子区间): {truncation_summary}"

            if final_error_message:
                final_error_message = f"{final_error_message}; {truncation_msg}"
            else:
                final_error_message = truncation_msg

        async with AsyncSessionPG() as session:
            stmt = (
                update(TushareImportLog)
                .where(TushareImportLog.id == log_id)
                .values(
                    status=status,
                    record_count=record_count,
                    error_message=final_error_message[:500] if final_error_message else None,
                    finished_at=datetime.now(),
                    extra_info=extra_info_str,
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

    from sqlalchemy import Boolean, Date, DateTime, Numeric, String
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
    string_columns: set[str] = set()
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
            elif isinstance(col.type, String):
                string_columns.add(col.name)
    else:
        logger.warning(
            "目标表 %s 未在 ORM metadata 中找到，跳过列过滤和类型转换",
            entry.target_table,
        )

    # 收集所有列名（取第一行的键），过滤掉目标表中不存在的列
    raw_columns = list(rows[0].keys())

    # JSONB 打包：将非固定列的字段打包成 JSON 存入指定 JSONB 列
    jsonb_pack_col = entry.extra_config.get("jsonb_pack_column")
    jsonb_fixed_cols = set(entry.extra_config.get("jsonb_fixed_columns", []))
    if jsonb_pack_col:
        import json as _json
        packed_rows = []
        for row in rows:
            new_row = {}
            json_data = {}
            for k, v in row.items():
                if k in jsonb_fixed_cols:
                    new_row[k] = v
                else:
                    json_data[k] = v
            new_row[jsonb_pack_col] = _json.dumps(json_data, ensure_ascii=False) if json_data else "{}"
            packed_rows.append(new_row)
        rows = packed_rows
        raw_columns = list(rows[0].keys()) if rows else raw_columns

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
        - String 列：int/float → str（Tushare 有时返回数字类型给字符串列）
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
            # String 列：int/float/date/datetime → str
            # 特殊处理：日期类型值写入 VARCHAR 日期列时，规范化为 YYYYMMDD 格式
            elif k in string_columns and not isinstance(v, str):
                if isinstance(v, datetime_type):
                    v = v.strftime("%Y%m%d")
                elif isinstance(v, date_type):
                    v = v.strftime("%Y%m%d")
                else:
                    v = str(v)
            elif k in string_columns and isinstance(v, str):
                # 字符串值但格式为 "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD"，
                # 且目标列长度 <= 8（VARCHAR(8) 日期列），规范化为 YYYYMMDD
                col_obj = table_obj.columns.get(k) if table_obj is not None else None
                if col_obj is not None and hasattr(col_obj.type, "length") and col_obj.type.length and col_obj.type.length <= 8:
                    if len(v) >= 10 and "-" in v:
                        v = v[:10].replace("-", "")
            result[k] = v
        return result

    filtered_rows = [_coerce_row(row) for row in rows]

    # 过滤掉冲突列值为 NULL 或缺失的行（NULL 值无法参与唯一约束匹配）
    # 只检查 ON CONFLICT 冲突列，其他 NOT NULL 列交给数据库约束处理
    must_not_null: set[str] = set()
    if entry.conflict_columns:
        must_not_null = set(entry.conflict_columns)
    if must_not_null:
        before_count = len(filtered_rows)
        filtered_rows = [
            row for row in filtered_rows
            if all(row.get(c) is not None for c in must_not_null)
        ]
        skipped = before_count - len(filtered_rows)
        if skipped:
            logger.debug(
                "跳过 %d 行（冲突列含 NULL 或缺失），表=%s 检查列=%s",
                skipped, entry.target_table, must_not_null,
            )

    if not filtered_rows:
        return

    # 构建 INSERT 语句（列名加双引号避免 SQL 保留字冲突，如 limit）
    col_list = ", ".join(f'"{col}"' for col in columns)
    val_placeholders = ", ".join(f":{col}" for col in columns)

    if entry.conflict_columns and entry.conflict_action == "do_nothing":
        conflict_cols = ", ".join(f'"{c}"' for c in entry.conflict_columns)
        sql = (
            f"INSERT INTO {entry.target_table} ({col_list}) "
            f"VALUES ({val_placeholders}) "
            f"ON CONFLICT ({conflict_cols}) DO NOTHING"
        )
    elif entry.conflict_columns and entry.conflict_action == "do_update":
        conflict_cols = ", ".join(f'"{c}"' for c in entry.conflict_columns)
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
                    set_parts.append('"updated_at" = NOW()')
                elif col in columns_set:
                    set_parts.append(f'"{col}" = EXCLUDED."{col}"')
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

    # 死锁重试：多个 worker 并发写同一张表时可能触发 PostgreSQL 死锁
    max_retries = 3
    for attempt in range(max_retries):
        async with AsyncSessionPG() as session:
            try:
                for row in filtered_rows:
                    await session.execute(stmt, row)
                await session.commit()
                return
            except Exception as exc:
                await session.rollback()
                # 检测死锁错误，重试
                exc_str = str(exc)
                if "deadlock" in exc_str.lower() and attempt < max_retries - 1:
                    import time as _time
                    wait = 0.5 * (attempt + 1)
                    logger.warning(
                        "死锁检测，%0.1fs 后重试 (attempt %d/%d)，表=%s",
                        wait, attempt + 1, max_retries, entry.target_table,
                    )
                    _time.sleep(wait)
                    continue
                raise


# ---------------------------------------------------------------------------
# TimescaleDB 写入
# ---------------------------------------------------------------------------

async def _write_to_timescaledb(rows: list[dict], entry: ApiEntry) -> None:
    """写入 TimescaleDB 超表（kline 或 sector_kline）。

    根据 entry.target_table 决定写入目标：
    - kline：股票/指数行情数据
    - sector_kline：板块行情数据（ths_daily/dc_daily/sw_daily/ci_daily/tdx_daily）

    使用 ON CONFLICT DO NOTHING 去重。事务保证单批原子性。
    """
    if not rows:
        return

    from sqlalchemy import text

    from app.core.database import AsyncSessionTS

    # 从 entry.extra_config 获取 freq 和 data_source 配置
    freq = entry.extra_config.get("freq", "1d")
    data_source = entry.extra_config.get("data_source", "")

    # 根据 target_table 选择写入目标
    if entry.target_table == "sector_kline":
        await _write_to_sector_kline(rows, entry, freq, data_source)
    elif entry.target_table == "adjustment_factor":
        await _write_to_adjustment_factor(rows, entry)
    else:
        await _write_to_kline(rows, entry, freq)


async def _write_to_kline(rows: list[dict], entry: ApiEntry, freq: str) -> None:
    """写入 kline 超表（股票/指数行情）。"""
    from sqlalchemy import text
    from app.core.database import AsyncSessionTS

    sql = text("""
        INSERT INTO kline ("time", "symbol", "freq", "open", "high", "low", "close", "volume", "amount", "adj_type")
        VALUES (:time, :symbol, :freq, :open, :high, :low, :close, :volume, :amount, :adj_type)
        ON CONFLICT ("time", "symbol", "freq", "adj_type")
        DO UPDATE SET
            "open" = COALESCE(EXCLUDED."open", kline."open"),
            "high" = COALESCE(EXCLUDED."high", kline."high"),
            "low" = COALESCE(EXCLUDED."low", kline."low"),
            "close" = COALESCE(EXCLUDED."close", kline."close"),
            "volume" = COALESCE(EXCLUDED."volume", kline."volume"),
            "amount" = COALESCE(EXCLUDED."amount", kline."amount")
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


async def _write_to_adjustment_factor(rows: list[dict], entry: ApiEntry) -> None:
    """写入 adjustment_factor 表（复权因子）。"""
    from datetime import date as date_type

    from sqlalchemy import text

    from app.core.database import AsyncSessionTS

    sql = text("""
        INSERT INTO adjustment_factor ("symbol", "trade_date", "adj_type", "adj_factor")
        VALUES (:symbol, :trade_date, :adj_type, :adj_factor)
        ON CONFLICT ("symbol", "trade_date", "adj_type") DO NOTHING
    """)

    async with AsyncSessionTS() as session:
        try:
            for row in rows:
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

                # trade_date → date 对象
                trade_date_str = str(row.get("trade_date", ""))
                if len(trade_date_str) == 8 and trade_date_str.isdigit():
                    trade_date = date_type(
                        int(trade_date_str[:4]),
                        int(trade_date_str[4:6]),
                        int(trade_date_str[6:8]),
                    )
                else:
                    continue

                await session.execute(sql, {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "adj_type": 0,
                    "adj_factor": row.get("adj_factor"),
                })
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _write_to_sector_kline(
    rows: list[dict], entry: ApiEntry, freq: str, data_source: str,
) -> None:
    """写入 sector_kline 超表（板块行情）。"""
    from sqlalchemy import text
    from app.core.database import AsyncSessionTS

    sql = text("""
        INSERT INTO sector_kline ("time", "sector_code", "data_source", "freq", "open", "high", "low", "close", "volume", "amount", "turnover", "change_pct")
        VALUES (:time, :sector_code, :data_source, :freq, :open, :high, :low, :close, :volume, :amount, :turnover, :change_pct)
        ON CONFLICT ("time", "sector_code", "data_source", "freq")
        DO UPDATE SET
            "open" = COALESCE(EXCLUDED."open", sector_kline."open"),
            "high" = COALESCE(EXCLUDED."high", sector_kline."high"),
            "low" = COALESCE(EXCLUDED."low", sector_kline."low"),
            "close" = COALESCE(EXCLUDED."close", sector_kline."close"),
            "volume" = COALESCE(EXCLUDED."volume", sector_kline."volume"),
            "amount" = COALESCE(EXCLUDED."amount", sector_kline."amount"),
            "turnover" = COALESCE(EXCLUDED."turnover", sector_kline."turnover"),
            "change_pct" = COALESCE(EXCLUDED."change_pct", sector_kline."change_pct")
    """)

    async with AsyncSessionTS() as session:
        try:
            for row in rows:
                trade_date_str = row.get("trade_date", "")
                if trade_date_str and len(str(trade_date_str)) == 8:
                    try:
                        ts = datetime.strptime(str(trade_date_str), "%Y%m%d")
                    except ValueError:
                        continue
                else:
                    continue

                sector_code = row.get("ts_code", "")
                if not sector_code:
                    continue

                await session.execute(sql, {
                    "time": ts,
                    "sector_code": str(sector_code),
                    "data_source": data_source,
                    "freq": freq,
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("vol") or row.get("volume") or 0,
                    "amount": row.get("amount"),
                    "turnover": row.get("turnover_rate") or row.get("turnover"),
                    "change_pct": row.get("pct_change") or row.get("change_pct"),
                })
            await session.commit()
        except Exception:
            await session.rollback()
            raise
