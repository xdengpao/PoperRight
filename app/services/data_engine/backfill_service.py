"""
历史数据批量回填编排服务

负责参数校验、默认值填充、并发保护和 Celery 任务分发。
支持 K 线行情、基本面、资金流向三种数据类型的批量回填。

需求：25.1, 25.2, 25.3, 25.12
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime

from app.core.config import settings
from app.core.redis_client import cache_delete, cache_get, cache_set

logger = logging.getLogger(__name__)

# 常量
BATCH_SIZE = 50
BATCH_DELAY = 1.0
REDIS_KEY = "backfill:progress"
STOP_SIGNAL_KEY = "backfill:stop_signal"
PROGRESS_TTL = 86400  # 24h

# Celery 任务名 → data_type 映射
_TASK_MAP = {
    "kline": "app.tasks.data_sync.sync_historical_kline",
    "fundamentals": "app.tasks.data_sync.sync_historical_fundamentals",
    "money_flow": "app.tasks.data_sync.sync_historical_money_flow",
}

ALL_DATA_TYPES = list(_TASK_MAP.keys())


class BackfillService:
    """历史数据批量回填编排服务"""

    async def start_backfill(
        self,
        data_types: list[str] | None = None,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        freq: str = "1d",
    ) -> dict:
        """
        启动回填任务。

        1. 检查是否有正在运行的回填任务（并发保护）
        2. 填充默认参数（symbols → 全市场，start_date → 10年前）
        3. 初始化 Redis 进度为 pending
        4. 按 data_types 分发对应 Celery 任务

        Returns:
            {"message": str, "task_ids": list[str]}

        Raises:
            RuntimeError: 已有回填任务正在执行
        """
        # ── 并发保护 & 清除残留任务 ──
        progress_raw = await cache_get(REDIS_KEY)
        if progress_raw:
            try:
                progress = json.loads(progress_raw)
                status = progress.get("status", "")
                if status == "running":
                    raise RuntimeError("已有回填任务正在执行，请等待完成后再试")
                # 清除非 running 的残留状态（pending/completed/failed/stopped/stopping 等）
                if status != "running":
                    old_task_ids = progress.get("task_ids", [])
                    if old_task_ids:
                        from app.core.celery_app import celery_app
                        for tid in old_task_ids:
                            try:
                                celery_app.control.revoke(tid, terminate=True)
                            except Exception:
                                pass
                        logger.info("已清除 %d 个残留 Celery 任务", len(old_task_ids))
                    await cache_delete(REDIS_KEY)
                    await cache_delete(STOP_SIGNAL_KEY)
                    logger.info("已清除 Redis 中的残留回填状态")
            except (json.JSONDecodeError, TypeError):
                await cache_delete(REDIS_KEY)

        # ── 填充默认参数 ──
        data_types = data_types or ALL_DATA_TYPES[:]
        symbols = await self._resolve_symbols(symbols)
        start_date = self._resolve_start_date(start_date)
        end_date = end_date or date.today()

        # ── 初始化 Redis 进度 ──
        # 清除上次的停止信号
        await cache_delete(STOP_SIGNAL_KEY)

        progress_data = {
            "total": len(symbols),
            "completed": 0,
            "failed": 0,
            "current_symbol": "",
            "status": "pending",
            "data_types": data_types,
            "started_at": datetime.now().isoformat(),
            "errors": [],
            "task_ids": [],
        }
        await cache_set(REDIS_KEY, json.dumps(progress_data), ex=PROGRESS_TTL)

        # ── 分发 Celery 任务 ──
        from app.core.celery_app import celery_app

        task_ids: list[str] = []
        for dt in data_types:
            task_name = _TASK_MAP.get(dt)
            if not task_name:
                logger.warning("未知数据类型: %s，跳过", dt)
                continue

            kwargs: dict = {
                "symbols": symbols,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            if dt == "kline":
                kwargs["freq"] = freq

            result = celery_app.send_task(
                task_name,
                kwargs=kwargs,
                queue="data_sync",
            )
            task_ids.append(result.id)
            logger.info("已分发回填任务 %s → %s", dt, result.id)

        # 将 task_ids 写回 Redis 进度，供 stop_backfill 撤销
        progress_data["task_ids"] = task_ids
        await cache_set(REDIS_KEY, json.dumps(progress_data), ex=PROGRESS_TTL)

        return {
            "message": f"已启动 {len(task_ids)} 个回填任务",
            "task_ids": task_ids,
        }

    async def stop_backfill(self) -> dict:
        """
        发送停止回填信号并撤销 Celery 任务。

        1. 设置独立停止信号键（不依赖 progress 的 status 字段）
        2. 读取 Redis 进度，若 status 为 running/pending 则设为 stopping
        3. 撤销已记录的 Celery 任务 ID

        Returns:
            {"message": str}

        需求：25.16
        """
        # 设置独立停止信号键，所有任务都会检查这个键
        await cache_set(STOP_SIGNAL_KEY, "1", ex=PROGRESS_TTL)

        raw = await cache_get(REDIS_KEY)
        if raw:
            try:
                progress = json.loads(raw)
                if progress.get("status") in ("running", "pending", "stopping"):
                    # 撤销已分发的 Celery 任务
                    task_ids = progress.get("task_ids", [])
                    if task_ids:
                        from app.core.celery_app import celery_app
                        for tid in task_ids:
                            try:
                                celery_app.control.revoke(tid, terminate=True)
                                logger.info("已撤销 Celery 任务 %s", tid)
                            except Exception as exc:
                                logger.warning("撤销任务 %s 失败: %s", tid, exc)

                    # 清除 Redis 中的进度和停止信号，彻底释放状态
                    await cache_delete(REDIS_KEY)
                    await cache_delete(STOP_SIGNAL_KEY)
                    logger.info("已清除 Redis 回填进度和停止信号")

                    return {"message": "已停止回填并清除任务状态"}
            except (json.JSONDecodeError, TypeError):
                pass

        # 即使没有活跃任务，也清除可能残留的 Redis 键
        await cache_delete(REDIS_KEY)
        await cache_delete(STOP_SIGNAL_KEY)
        return {"message": "当前没有正在执行的回填任务，已清除残留状态"}

    async def get_progress(self) -> dict:
        """从 Redis 读取回填进度，无数据时返回 idle 默认值。"""
        raw = await cache_get(REDIS_KEY)
        if not raw:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "current_symbol": "",
                "status": "idle",
                "data_types": [],
            }
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "current_symbol": "",
                "status": "idle",
                "data_types": [],
            }

    async def _resolve_symbols(self, symbols: list[str]) -> list[str]:
        """解析股票代码列表。

        - ["ALL"] → 从 Tushare 拉取全市场 A 股列表，写入 stock_info，返回完整列表
        - 其他 → 原样返回
        """
        if not symbols:
            symbols = ["ALL"]

        if symbols == ["ALL"]:
            logger.info("收到全市场回填请求，从 Tushare 拉取全市场 A 股列表...")
            stocks = await self._fetch_all_symbols_from_tushare()
            if not stocks:
                raise RuntimeError("从 Tushare 拉取全市场股票列表失败，无法执行全市场回填")
            logger.info("从 Tushare 获取到 %d 只股票，写入 stock_info", len(stocks))
            await self._bulk_insert_stock_info(stocks)
            return [s["symbol"] for s in stocks]

        return symbols

    async def _fetch_all_symbols_from_tushare(self) -> list[dict]:
        """从 Tushare stock_basic 接口拉取全市场 A 股列表。"""
        from app.services.data_engine.tushare_adapter import TushareAdapter

        adapter = TushareAdapter()
        try:
            data = await adapter._call_api(
                "stock_basic",
                exchange="",
                list_status="L",
            )
            fields = data.get("fields", [])
            items = data.get("items", [])
            rows = [dict(zip(fields, row)) for row in items]
            result = []
            for row in rows:
                ts_code = row.get("ts_code", "")
                # 保留 Tushare 代码格式（如 000001.SZ），用于 API 调用
                # 纯数字格式用于本地 DB 存储（在 KlineRepository 中处理）
                symbol = ts_code if ts_code else ""
                # stock_info 表存纯数字
                clean_symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                result.append({
                    "symbol": symbol,
                    "clean_symbol": clean_symbol,
                    "name": row.get("name", ""),
                    "market": row.get("market", ""),
                    "list_date": row.get("list_date"),
                    "is_st": "ST" in (row.get("name") or ""),
                })
            return result
        except Exception as exc:
            logger.error("从 Tushare 拉取股票列表失败: %s", exc)
            return []

    async def _bulk_insert_stock_info(self, stocks: list[dict]) -> None:
        """批量写入 stock_info 表（ON CONFLICT 跳过已有记录）。"""
        from datetime import datetime as dt_cls

        from sqlalchemy import text

        from app.core.database import AsyncSessionPG

        upsert_sql = text("""
            INSERT INTO stock_info (symbol, name, market, list_date, is_st, is_delisted, updated_at)
            VALUES (:symbol, :name, :market, :list_date, :is_st, FALSE, :updated_at)
            ON CONFLICT (symbol) DO UPDATE SET
                name = CASE WHEN EXCLUDED.name != '' THEN EXCLUDED.name ELSE stock_info.name END,
                market = EXCLUDED.market,
                is_st = EXCLUDED.is_st,
                updated_at = EXCLUDED.updated_at
        """)

        now = dt_cls.now()
        async with AsyncSessionPG() as session:
            for stock in stocks:
                list_date = None
                if stock.get("list_date"):
                    try:
                        list_date = date.fromisoformat(
                            str(stock["list_date"])[:4] + "-"
                            + str(stock["list_date"])[4:6] + "-"
                            + str(stock["list_date"])[6:8]
                        )
                    except (ValueError, IndexError):
                        pass
                await session.execute(upsert_sql, {
                    "symbol": stock.get("clean_symbol", stock["symbol"].split(".")[0]),
                    "name": stock.get("name", ""),
                    "market": stock.get("market", ""),
                    "list_date": list_date,
                    "is_st": stock.get("is_st", False),
                    "updated_at": now,
                })
            await session.commit()
        logger.info("批量写入 stock_info 完成，共 %d 条", len(stocks))

    def _resolve_start_date(self, start_date: date | None) -> date:
        """未传入时使用 today - settings.kline_history_years（默认 10 年）。"""
        if start_date is not None:
            return start_date
        today = date.today()
        return today.replace(year=today.year - settings.kline_history_years)
