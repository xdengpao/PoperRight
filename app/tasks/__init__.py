"""
任务模块入口

任务队列划分：
- data_sync：数据同步任务（行情、基本面、资金数据）
- screening：选股任务（盘后选股、实时选股）
- backtest：回测任务（历史回测、参数优化）
- review：复盘任务（每日复盘报告、策略绩效报表）
"""
from app.core.celery_app import celery_app

__all__ = ["celery_app"]
