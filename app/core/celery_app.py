"""
Celery 应用实例配置
包含 Celery + Redis Broker 配置和 Celery Beat 定时任务调度计划
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# 创建 Celery 应用实例
celery_app = Celery(
    "a_share_quant",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.data_sync",
        "app.tasks.screening",
        "app.tasks.backtest",
        "app.tasks.review",
        "app.tasks.sector_sync",
    ],
)

# Celery 基础配置
celery_app.conf.update(
    # 序列化配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务路由：按队列分发
    task_routes={
        "app.tasks.data_sync.*": {"queue": "data_sync"},
        "app.tasks.sector_sync.*": {"queue": "data_sync"},
        "app.tasks.screening.*": {"queue": "screening"},
        "app.tasks.backtest.*": {"queue": "backtest"},
        "app.tasks.review.*": {"queue": "review"},
    },

    # 任务队列定义
    task_queues={
        "data_sync": {"exchange": "data_sync", "routing_key": "data_sync"},
        "screening": {"exchange": "screening", "routing_key": "screening"},
        "backtest": {"exchange": "backtest", "routing_key": "backtest"},
        "review": {"exchange": "review", "routing_key": "review"},
    },
    task_default_queue="data_sync",

    # 重试配置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,

    # Redis broker 可见性超时（秒）
    # 必须大于最长任务的执行时间，否则 Redis 会重新投递任务导致重复执行
    broker_transport_options={"visibility_timeout": 14400},  # 4 小时

    # 结果过期时间（24小时）
    result_expires=86400,

    # Worker 并发配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # 任务软/硬超时（秒）
    task_soft_time_limit=1800,
    task_time_limit=3600,
)

# Celery Beat 定时任务调度计划
celery_app.conf.beat_schedule = {
    # 盘后选股：每个交易日 15:30 自动执行（需求 7.4）
    "eod-screening-1530": {
        "task": "app.tasks.screening.run_eod_screening",
        "schedule": crontab(hour=15, minute=30, day_of_week="1-5"),
        "options": {"queue": "screening"},
    },

    # 盘后复盘：每个交易日 15:45 自动执行（需求 16.1）
    "daily-review-1545": {
        "task": "app.tasks.review.generate_daily_review",
        "schedule": crontab(hour=15, minute=45, day_of_week="1-5"),
        "options": {"queue": "review"},
    },

    # 基本面数据日更：每日 18:00 执行（需求 1.3）
    "fundamentals-sync-1800": {
        "task": "app.tasks.data_sync.sync_fundamentals",
        "schedule": crontab(hour=18, minute=0, day_of_week="1-5"),
        "options": {"queue": "data_sync"},
    },

    # 资金数据日更：每个交易日 15:30 执行（需求 1.4/1.5）
    "money-flow-sync-1530": {
        "task": "app.tasks.data_sync.sync_money_flow",
        "schedule": crontab(hour=15, minute=30, day_of_week="1-5"),
        "options": {"queue": "data_sync"},
    },

    # 盘中实时行情同步：交易时段每 10 秒执行（需求 7.5）
    "realtime-market-sync": {
        "task": "app.tasks.data_sync.sync_realtime_market",
        "schedule": 10.0,  # 每 10 秒
        "options": {"queue": "data_sync"},
    },

    # 每日增量 K 线同步：每个交易日 16:00 执行（需求 25.13）
    "daily-kline-sync-1600": {
        "task": "app.tasks.data_sync.sync_daily_kline",
        "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
        "options": {"queue": "data_sync"},
    },
}
