"""
Tushare 数据导入编排服务

负责参数校验、四级 Token 路由（basic/advanced/premium/special）、
Celery 任务分发、进度管理和导入历史查询。
设计模式参考现有 BackfillService，通过 API_Registry 注册表驱动导入流程。

对应需求：20.1, 20.4, 21.2, 21.3, 22.1, 22a.3, 22a.4, 23.4, 24.3-24.6
"""

from __future__ import annotations

import json
import logging
import re
from uuid import uuid4

from app.core.config import settings
from app.core.redis_client import cache_delete, cache_get, cache_set, get_redis_client
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    ParamType,
    TokenTier,
    get_entry,
)

logger = logging.getLogger(__name__)

# Redis 键前缀和 TTL 常量
_PROGRESS_KEY_PREFIX = "tushare:import:"
_STOP_KEY_PREFIX = "tushare:import:stop:"
_LOCK_KEY_PREFIX = "tushare:import:lock:"
_PROGRESS_TTL = 86400       # 进度数据 24h 过期
_STOP_SIGNAL_TTL = 3600     # 停止信号 1h 过期
_LOCK_TTL = 7200            # 并发锁 2h 过期

# 日期格式正则（YYYYMMDD）
_DATE_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")

# 股票代码格式正则（6 位数字，可选 .SH/.SZ/.BJ 后缀）
_CODE_RE = re.compile(r"^\d{6}(\.[A-Z]{2})?$")


class TushareImportService:
    """Tushare 数据导入编排服务"""

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _resolve_token(self, tier: TokenTier) -> str:
        """根据权限级别选择 Token。

        优先使用对应级别 Token，未配置则回退到 tushare_api_token。
        两者均为空时抛出 ValueError。

        Args:
            tier: Token 权限级别（basic/advanced/premium/special）

        Returns:
            选中的 API Token 字符串

        Raises:
            ValueError: 对应级别和默认 Token 均未配置
        """
        tier_token_map = {
            TokenTier.BASIC: settings.tushare_token_basic,
            TokenTier.ADVANCED: settings.tushare_token_advanced,
            TokenTier.PREMIUM: settings.tushare_token_premium,
            TokenTier.SPECIAL: settings.tushare_token_special,
        }

        tier_token = tier_token_map.get(tier, "")
        if tier_token:
            return tier_token

        # 回退到默认 Token
        if settings.tushare_api_token:
            return settings.tushare_api_token

        raise ValueError(
            f"Token 未配置：{tier.value} 级别 Token 和默认 tushare_api_token 均为空"
        )

    def _validate_params(self, entry: ApiEntry, params: dict) -> dict:
        """校验并规范化导入参数。

        检查必填参数是否存在、日期格式（YYYYMMDD）、代码格式。

        Args:
            entry: API 注册表条目
            params: 用户传入的参数字典

        Returns:
            校验通过的参数字典（原样返回）

        Raises:
            ValueError: 参数校验失败
        """
        # 检查必填参数
        for param_type in entry.required_params:
            if param_type == ParamType.DATE_RANGE:
                if not params.get("start_date") and not params.get("trade_date"):
                    raise ValueError("必填参数缺失：需要提供 start_date 或 trade_date")
            elif param_type == ParamType.STOCK_CODE:
                pass  # 留空表示全市场，无需校验
            elif param_type == ParamType.INDEX_CODE:
                pass  # 留空表示全部指数，无需校验
            elif param_type == ParamType.MARKET:
                if not params.get("market"):
                    raise ValueError("必填参数缺失：需要提供 market（市场）")
            elif param_type == ParamType.HS_TYPE:
                if not params.get("hs_type"):
                    raise ValueError("必填参数缺失：需要提供 hs_type（SH/SZ）")
            elif param_type == ParamType.FREQ:
                if not params.get("freq"):
                    raise ValueError("必填参数缺失：需要提供 freq（频率）")
            elif param_type == ParamType.MONTH_RANGE:
                if not params.get("month"):
                    raise ValueError("必填参数缺失：需要提供 month（月份，格式 YYYYMM）")
            elif param_type == ParamType.SECTOR_CODE:
                if not params.get("ts_code") and not params.get("sector_code"):
                    raise ValueError("必填参数缺失：需要提供板块代码")

        # 转换 report_year + report_quarter → Tushare period 格式（YYYYMMDD 季末日期）
        if params.get("report_year") and params.get("report_quarter"):
            year = params.pop("report_year")
            quarter = params.pop("report_quarter")
            quarter_end = {"1": "0331", "2": "0630", "3": "0930", "4": "1231"}
            end_date = quarter_end.get(str(quarter), "1231")
            params["period"] = f"{year}{end_date}"

        # 校验日期格式（YYYYMMDD），自动转换 YYYY-MM-DD → YYYYMMDD
        for date_key in ("start_date", "end_date", "trade_date"):
            date_val = params.get(date_key)
            if date_val:
                date_str = str(date_val)
                # 自动转换 YYYY-MM-DD → YYYYMMDD
                if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
                    date_str = date_str.replace("-", "")
                    params[date_key] = date_str
                if not _DATE_RE.match(date_str):
                    raise ValueError(
                        f"日期格式错误：{date_key}={date_val}，应为 YYYYMMDD 格式"
                    )

        # 校验代码格式
        if entry.code_format == CodeFormat.STOCK_SYMBOL:
            ts_code = params.get("ts_code", "")
            if ts_code:
                # 支持逗号分隔的多个代码
                codes = [c.strip() for c in str(ts_code).split(",") if c.strip()]
                for code in codes:
                    if not _CODE_RE.match(code):
                        raise ValueError(
                            f"股票代码格式错误：{code}，应为 6 位数字或 XXXXXX.XX 格式"
                        )

        return params

    # ------------------------------------------------------------------
    # 公开接口：健康检查
    # ------------------------------------------------------------------

    async def check_health(self) -> dict:
        """检查 Tushare 连通性和四级 Token 配置状态。

        Returns:
            {
                "connected": bool,
                "tokens": {
                    "basic": {"configured": bool},
                    "advanced": {"configured": bool},
                    "premium": {"configured": bool},
                    "special": {"configured": bool},
                }
            }
        """
        from app.services.data_engine.tushare_adapter import TushareAdapter

        # 使用任意可用 Token 检查连通性
        token = ""
        for t in (
            settings.tushare_token_basic,
            settings.tushare_token_advanced,
            settings.tushare_token_premium,
            settings.tushare_token_special,
            settings.tushare_api_token,
        ):
            if t:
                token = t
                break

        connected = False
        if token:
            adapter = TushareAdapter(api_token=token)
            try:
                connected = await adapter.health_check()
            except Exception as exc:
                logger.warning("Tushare 连通性检查失败: %s", exc)

        return {
            "connected": connected,
            "tokens": {
                "basic": {"configured": bool(settings.tushare_token_basic)},
                "advanced": {"configured": bool(settings.tushare_token_advanced)},
                "premium": {"configured": bool(settings.tushare_token_premium)},
                "special": {"configured": bool(settings.tushare_token_special)},
            },
        }

    # ------------------------------------------------------------------
    # 公开接口：导入任务启动
    # ------------------------------------------------------------------

    async def start_import(self, api_name: str, params: dict) -> dict:
        """启动导入任务。

        1. 从 API_Registry 获取接口元数据（不存在则抛出 ValueError）
        2. 校验必填参数
        3. 根据 token_tier 选择 Token
        4. 并发保护：同一 api_name 同时只允许一个导入任务运行
        5. 在 tushare_import_log 中创建记录（status="running"）
        6. 初始化 Redis 进度
        7. 分发 Celery 任务到 data_sync 队列
        8. 返回 {task_id, log_id, status: "pending"}

        Args:
            api_name: Tushare 接口名称
            params: 导入参数字典

        Returns:
            {"task_id": str, "log_id": int, "status": "pending"}

        Raises:
            ValueError: 接口不存在、参数校验失败、Token 未配置
            RuntimeError: 同一接口已有任务在运行
        """
        # 1. 获取注册表条目
        entry = get_entry(api_name)
        if entry is None:
            raise ValueError(f"未知的 Tushare 接口：{api_name}")

        # 2. 参数校验
        self._validate_params(entry, params)

        # 3. Token 路由
        token = self._resolve_token(entry.token_tier)

        # 4. 并发保护：检查 Redis 锁
        lock_key = f"{_LOCK_KEY_PREFIX}{api_name}"
        redis = get_redis_client()
        try:
            lock_exists = await redis.exists(lock_key)
            if lock_exists:
                raise RuntimeError(
                    f"接口 {api_name} 已有导入任务在运行，请等待完成后再试"
                )
        finally:
            await redis.aclose()

        # 生成 task_id
        task_id = str(uuid4())

        # 5. 创建 tushare_import_log 记录
        log_id = await self._create_import_log(
            api_name=api_name,
            params=params,
            celery_task_id=task_id,
        )

        # 设置并发锁
        await cache_set(lock_key, task_id, ex=_LOCK_TTL)

        # 6. 初始化 Redis 进度
        progress_key = f"{_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "status": "pending",
            "current_item": "",
        }
        await cache_set(progress_key, json.dumps(progress_data), ex=_PROGRESS_TTL)

        # 7. 分发 Celery 任务
        from app.core.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.tushare_import.run_import",
            kwargs={
                "api_name": api_name,
                "params": params,
                "token": token,
                "log_id": log_id,
                "task_id": task_id,
            },
            queue="data_sync",
            task_id=task_id,
        )
        logger.info(
            "已分发 Tushare 导入任务 api=%s task_id=%s log_id=%d",
            api_name, task_id, log_id,
        )

        # 8. 返回结果
        return {
            "task_id": task_id,
            "log_id": log_id,
            "status": "pending",
        }

    # ------------------------------------------------------------------
    # 公开接口：停止导入
    # ------------------------------------------------------------------

    async def stop_import(self, task_id: str) -> dict:
        """停止导入任务。

        1. 在 Redis 设置停止信号
        2. 更新 Redis 进度状态为 "stopped"
        3. 撤销 Celery 任务
        4. 更新数据库 tushare_import_log 状态为 "stopped"
        5. 释放 Redis 并发锁
        """
        # 1. 设置停止信号
        stop_key = f"{_STOP_KEY_PREFIX}{task_id}"
        await cache_set(stop_key, "1", ex=_STOP_SIGNAL_TTL)

        # 2. 更新 Redis 进度状态
        progress_key = f"{_PROGRESS_KEY_PREFIX}{task_id}"
        raw = await cache_get(progress_key)
        if raw:
            try:
                progress = json.loads(raw)
                progress["status"] = "stopped"
                await cache_set(
                    progress_key, json.dumps(progress), ex=_PROGRESS_TTL
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # 3. 撤销 Celery 任务
        from app.core.celery_app import celery_app

        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info("已撤销 Celery 任务 %s", task_id)
        except Exception as exc:
            logger.warning("撤销 Celery 任务 %s 失败: %s", task_id, exc)

        # 4. 更新数据库状态并释放并发锁
        try:
            from datetime import datetime

            from sqlalchemy import select, update

            from app.core.database import AsyncSessionPG
            from app.models.tushare_import import TushareImportLog

            async with AsyncSessionPG() as session:
                # 查找该任务的 api_name
                result = await session.execute(
                    select(TushareImportLog).where(
                        TushareImportLog.celery_task_id == task_id
                    )
                )
                log = result.scalar_one_or_none()
                if log:
                    api_name = log.api_name
                    # 更新状态为 stopped
                    if log.status in ("running", "pending"):
                        await session.execute(
                            update(TushareImportLog)
                            .where(TushareImportLog.id == log.id)
                            .values(
                                status="stopped",
                                error_message="用户手动停止",
                                finished_at=datetime.utcnow(),
                            )
                        )
                        await session.commit()

                    # 5. 释放并发锁
                    try:
                        await cache_delete(f"{_LOCK_KEY_PREFIX}{api_name}")
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("停止任务后清理失败 task_id=%s: %s", task_id, exc)

        return {"message": "停止信号已发送"}

    # ------------------------------------------------------------------
    # 公开接口：查询进度
    # ------------------------------------------------------------------

    async def get_import_status(self, task_id: str) -> dict:
        """获取导入任务进度。

        从 Redis 读取 tushare:import:{task_id} 键。

        Args:
            task_id: 导入任务 ID

        Returns:
            {total, completed, failed, status, current_item}
            若键不存在返回 {status: "unknown"}
        """
        progress_key = f"{_PROGRESS_KEY_PREFIX}{task_id}"
        raw = await cache_get(progress_key)
        if not raw:
            return {"status": "unknown"}

        try:
            progress = json.loads(raw)
            return {
                "total": progress.get("total", 0),
                "completed": progress.get("completed", 0),
                "failed": progress.get("failed", 0),
                "status": progress.get("status", "unknown"),
                "current_item": progress.get("current_item", ""),
                "error_message": progress.get("error_message", ""),
            }
        except (json.JSONDecodeError, TypeError):
            return {"status": "unknown"}

    # ------------------------------------------------------------------
    # 公开接口：导入历史
    # ------------------------------------------------------------------

    async def get_last_import_times(self) -> dict[str, str]:
        """获取每个 API 接口的最近成功导入时间。

        从 tushare_import_log 表查询每个 api_name 的最新 finished_at（status='completed'）。

        Returns:
            {api_name: finished_at_iso_string} 字典
        """
        from sqlalchemy import func, select

        from app.core.database import AsyncSessionPG
        from app.models.tushare_import import TushareImportLog

        async with AsyncSessionPG() as session:
            stmt = (
                select(
                    TushareImportLog.api_name,
                    func.max(TushareImportLog.finished_at).label("last_time"),
                )
                .where(TushareImportLog.status == "completed")
                .group_by(TushareImportLog.api_name)
            )
            result = await session.execute(stmt)
            rows = result.all()

        return {
            row.api_name: row.last_time.isoformat() if row.last_time else None
            for row in rows
            if row.last_time is not None
        }

    async def get_import_history(self, limit: int = 20) -> list[dict]:
        """获取最近导入历史记录。

        从 tushare_import_log 表查询最近 N 条记录，按 started_at 降序排列。
        extra_info 列存储 JSON 格式的分批统计信息，解析后作为 dict 返回。

        Args:
            limit: 返回记录数上限，默认 20

        Returns:
            包含 id, api_name, params_json, status, record_count,
            error_message, extra_info, started_at, finished_at 的字典列表
        """
        from sqlalchemy import select

        from app.core.database import AsyncSessionPG
        from app.models.tushare_import import TushareImportLog

        async with AsyncSessionPG() as session:
            stmt = (
                select(TushareImportLog)
                .order_by(TushareImportLog.started_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()

        return [
            {
                "id": log.id,
                "api_name": log.api_name,
                "params_json": log.params_json,
                "status": log.status,
                "record_count": log.record_count,
                "error_message": log.error_message,
                "celery_task_id": log.celery_task_id,
                "extra_info": self._parse_extra_info(log.extra_info),
                "started_at": (
                    log.started_at.isoformat() if log.started_at else None
                ),
                "finished_at": (
                    log.finished_at.isoformat() if log.finished_at else None
                ),
            }
            for log in logs
        ]

    async def get_running_tasks(self) -> list[dict]:
        """获取所有 running 状态的导入任务。

        不受 limit 限制，返回 tushare_import_log 中所有 status='running' 的记录。
        用于前端页面加载时恢复活跃任务列表。

        Returns:
            running 状态的导入记录列表
        """
        from sqlalchemy import select

        from app.core.database import AsyncSessionPG
        from app.models.tushare_import import TushareImportLog

        async with AsyncSessionPG() as session:
            stmt = (
                select(TushareImportLog)
                .where(TushareImportLog.status == "running")
                .order_by(TushareImportLog.started_at.desc())
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()

        return [
            {
                "id": log.id,
                "api_name": log.api_name,
                "params_json": log.params_json,
                "status": log.status,
                "record_count": log.record_count,
                "error_message": log.error_message,
                "celery_task_id": log.celery_task_id,
                "extra_info": self._parse_extra_info(log.extra_info),
                "started_at": (
                    log.started_at.isoformat() if log.started_at else None
                ),
                "finished_at": (
                    log.finished_at.isoformat() if log.finished_at else None
                ),
            }
            for log in logs
        ]

    @staticmethod
    def _parse_extra_info(raw: str | None) -> dict | None:
        """解析 extra_info JSON 字符串为字典。

        Args:
            raw: JSON 格式字符串或 None

        Returns:
            解析后的字典，若为 None/空字符串/解析失败则返回 None
        """
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("extra_info JSON 解析失败: %s", raw)
            return None

    # ------------------------------------------------------------------
    # 内部辅助：创建导入日志记录
    # ------------------------------------------------------------------

    async def _create_import_log(
        self,
        api_name: str,
        params: dict,
        celery_task_id: str,
    ) -> int:
        """在 tushare_import_log 表中创建导入记录。

        Args:
            api_name: Tushare 接口名称
            params: 导入参数
            celery_task_id: Celery 任务 ID

        Returns:
            新创建记录的 id
        """
        from app.core.database import AsyncSessionPG
        from app.models.tushare_import import TushareImportLog

        log = TushareImportLog(
            api_name=api_name,
            params_json=params,
            status="running",
            celery_task_id=celery_task_id,
        )

        async with AsyncSessionPG() as session:
            session.add(log)
            await session.flush()
            log_id = log.id
            await session.commit()

        logger.info(
            "创建导入日志 id=%d api=%s task_id=%s",
            log_id, api_name, celery_task_id,
        )
        return log_id
