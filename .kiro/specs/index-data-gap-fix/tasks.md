# 任务文档：指数数据缺口评估与补全

## 阶段一：代码修改

- [x] 1.1 修复 `app/services/data_engine/tushare_registry.py` 中 `index_daily` 注册条目——删除 `batch_by_code=True`（使用默认值 False），使 `determine_batch_strategy()` 路由到 `by_index` 策略（从 `index_info` 表读取指数代码列表），而非当前错误地走 `by_code` 策略（从 `stock_info` 读取股票代码）
- [x] 1.2 在 `app/tasks/data_sync.py` 中新增 `sync_index_data` 和 `sync_index_weight` 两个 Celery 任务。`sync_index_data` 通过 `TushareImportService.start_import` 分发 `index_daily` → `index_dailybasic` → `idx_factor_pro` 三个导入任务（写入不同表，无数据依赖，可并行）。`sync_index_weight` 导入 `index_weight`
- [x] 1.3 在 `app/core/celery_app.py` 的 `_beat_schedule` 中新增两个条目：`index-data-sync-1600`（每个交易日 16:00 执行 `sync_index_data`）和 `index-weight-sync-monthly`（每月 1 日 08:00 执行 `sync_index_weight`）
- [x] 1.4 修复 `app/services/screener/screen_data_provider.py` 中 `_enrich_index_factors` 方法的 `index_vol_ratio` 计算——新增 `_compute_index_vol_ratios` 方法从 kline 表查询指数最近 6 日成交量，计算量比（当日成交量 / 近 5 日平均成交量），替代当前硬编码的 None
- [x] 1.5 修改 `app/services/screener/evaluation/historical_data_preparer.py` 的 `load_index_data` 方法——调整签名为 `(self, start_date, end_date, index_code="000300.SH", fallback_code="000001.SH")`，增加回退逻辑，拆分为 `load_index_data` + `_load_index_kline` 两个方法
- [x] 1.6 修改 `scripts/evaluate_screener.py`——调用改为 `preparer.load_index_data(start_date, end_date)`（使用默认基准沪深300），新增 `_check_index_data_completeness` 函数检查指数数据覆盖率，在评估报告 summary 中增加 `index_data_status` 字段

## 阶段二：首次全量数据导入

- [x] 2.1 通过前端 Tushare 导入页面手动导入 `index_basic`（指数基本信息）到 `index_info` 表，确认核心指数集 5 个指数（000001.SH、000300.SH、000905.SH、399001.SZ、399006.SZ）已入库
- [x] 2.2 手动导入 `index_daily`（指数日线 K 线）到 kline 表，参数设置起始日期为 3 年前，确认核心指数集在 kline 表中有至少 750 个交易日的日线数据
- [x] 2.3 手动导入 `index_dailybasic`（指数每日基本面指标）到 `index_dailybasic` 表，确认核心指数集有至少 1 年的 PE/换手率数据
- [x] 2.4 手动导入 `idx_factor_pro`（指数技术面因子）到 `index_tech` 表，确认核心指数集有至少 1 年的 MACD/KDJ 数据
- [x] 2.5 手动导入 `index_weight`（指数成分权重）到 `index_weight` 表，确认沪深300和中证500有最近一个月的成分权重数据

## 阶段三：端到端验证

- [x] 3.1 运行选股评估脚本 `python scripts/evaluate_screener.py --start-date 2025-04-14 --end-date 2025-04-25 --strategies "强势多头趋势追踪"`，验证：指数 K 线覆盖率 100%、市场环境分类正常工作、风控规则评估有数据、评估报告 summary 包含 `index_data_status`、JSON 和 Markdown 报告正确生成
- [x] 3.2 验证 Celery Beat 两个指数同步任务（每日 + 每月）能正常触发和执行增量导入
