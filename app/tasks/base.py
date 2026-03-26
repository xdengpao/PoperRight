"""
任务基类
提供统一的重试逻辑、错误处理和日志记录
"""
import logging
from typing import Any

from celery import Task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """
    所有业务任务的基类。

    提供：
    - 统一的 on_failure / on_retry / on_success 钩子
    - 指数退避自动重试（最多 3 次）
    - 结构化日志记录
    """

    # 默认重试配置
    max_retries: int = 3
    default_retry_delay: int = 60  # 秒，首次重试等待时间
    autoretry_for: tuple = (Exception,)
    retry_backoff: bool = True       # 指数退避
    retry_backoff_max: int = 600     # 最大退避时间（秒）
    retry_jitter: bool = True        # 随机抖动，避免惊群

    # 子类可覆盖，标识任务所属业务模块
    task_module: str = "base"

    # ------------------------------------------------------------------ #
    # 生命周期钩子
    # ------------------------------------------------------------------ #

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """任务成功完成时调用。"""
        logger.info(
            "[%s] task_id=%s succeeded | args=%s kwargs=%s retval=%s",
            self.name,
            task_id,
            args,
            kwargs,
            retval,
        )

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """任务最终失败（超过最大重试次数或不可重试异常）时调用。"""
        logger.error(
            "[%s] task_id=%s FAILED | args=%s kwargs=%s | error=%s",
            self.name,
            task_id,
            args,
            kwargs,
            exc,
            exc_info=einfo,
        )

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """任务即将重试时调用。"""
        logger.warning(
            "[%s] task_id=%s retrying (attempt %d/%d) | error=%s",
            self.name,
            task_id,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )

    # ------------------------------------------------------------------ #
    # 辅助方法
    # ------------------------------------------------------------------ #

    def retry_with_backoff(self, exc: Exception, **kwargs: Any) -> None:
        """
        以指数退避策略重试任务。
        若已超过最大重试次数，则将异常向上抛出。
        """
        retry_count = self.request.retries
        countdown = min(
            self.default_retry_delay * (2 ** retry_count),
            self.retry_backoff_max,
        )
        logger.warning(
            "[%s] scheduling retry %d/%d in %ds | error=%s",
            self.name,
            retry_count + 1,
            self.max_retries,
            countdown,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=countdown, **kwargs)
        except MaxRetriesExceededError:
            logger.error(
                "[%s] max retries (%d) exceeded | error=%s",
                self.name,
                self.max_retries,
                exc,
            )
            raise exc


class DataSyncTask(BaseTask):
    """数据同步任务基类（data_sync 队列）。"""

    task_module = "data_sync"
    # 数据同步任务允许更长的超时时间
    soft_time_limit = 120
    time_limit = 300


class ScreeningTask(BaseTask):
    """选股任务基类（screening 队列）。"""

    task_module = "screening"
    # 盘后全市场选股需在 3 秒内完成（需求 18.1），设置较短超时
    soft_time_limit = 10
    time_limit = 30


class BacktestTask(BaseTask):
    """回测任务基类（backtest 队列）。"""

    task_module = "backtest"
    # 回测/参数优化耗时较长
    soft_time_limit = 1800
    time_limit = 3600
    # 回测任务不自动重试，失败需人工介入
    max_retries = 0
    autoretry_for = ()


class ReviewTask(BaseTask):
    """复盘任务基类（review 队列）。"""

    task_module = "review"
    soft_time_limit = 300
    time_limit = 600
