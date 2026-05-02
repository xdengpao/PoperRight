# 任务清单：Tushare 日级全市场导入性能优化

## 阶段 1：Registry 标记与路由策略

- [x] 1.1 为目标接口增加日级全市场配置
  - 文件：`app/services/data_engine/tushare_registry.py`
  - 为 `stk_factor_pro`、`daily_basic`、`stk_limit` 增加 `extra_config.full_market_by_trade_date=True`
  - 配置 `date_param="trade_date"`
  - 配置 `max_rows` 和 `estimated_daily_rows`

- [x] 1.2 补齐 `stk_factor_pro` upsert 更新列
  - 文件：`app/services/data_engine/tushare_registry.py`
  - 将 `wr`、`dmi`、`trix`、`bias` 加入 `update_columns`
  - 保持已有字段映射不变

- [x] 1.3 新增 `by_trade_date` 分批策略判定
  - 文件：`app/tasks/tushare_import.py`
  - 在 `determine_batch_strategy()` 中优先识别 `full_market_by_trade_date`
  - 未传 `ts_code` 且有 `start_date/end_date` 时返回 `by_trade_date`
  - 显式传 `ts_code` 时保持原有兼容路径

- [x] 1.4 补充分批策略测试
  - 文件：新增或扩展 `tests/tasks/test_tushare_import_strategy.py`
  - 覆盖三个目标接口未传 `ts_code` 返回 `by_trade_date`
  - 覆盖显式传 `ts_code` 时不走 `by_trade_date`
  - 覆盖未配置接口不受影响

## 阶段 2：交易日解析

- [x] 2.1 实现交易日解析函数
  - 文件：`app/tasks/tushare_import.py`
  - 新增 `_resolve_trade_dates(start_date, end_date)`
  - 优先查询 PostgreSQL `trade_calendar`
  - 返回 `YYYYMMDD` 升序列表和 `used_calendar` 标记

- [x] 2.2 处理交易日历去重与兜底
  - 文件：`app/tasks/tushare_import.py`
  - SSE/SZSE 重复日期去重
  - 无日历数据时使用自然日兜底
  - 缺少交易日历时输出 warning

- [x] 2.3 补充交易日解析测试
  - 文件：新增 `tests/tasks/test_tushare_import_trade_dates.py`
  - 覆盖有日历时跳过非交易日
  - 覆盖多交易所重复日期去重
  - 覆盖无日历时自然日兜底
  - 覆盖日期升序和格式转换

## 阶段 3：按交易日全市场导入执行器

- [x] 3.1 在 `_process_import` 中接入 `by_trade_date`
  - 文件：`app/tasks/tushare_import.py`
  - 新增 strategy 分支
  - 调用 `_process_batched_by_trade_date()`

- [x] 3.2 实现 `_process_batched_by_trade_date`
  - 文件：`app/tasks/tushare_import.py`
  - 按交易日逐日调用 Tushare API
  - 单日参数使用 `trade_date`
  - 移除单日调用中的 `start_date/end_date`
  - 检查停止信号、更新 Redis 进度、遵守 rate delay

- [x] 3.3 实现 `by_trade_date` 统计与日志
  - 文件：`app/tasks/tushare_import.py`
  - 统计计划交易日数、成功交易日数、空数据交易日数、失败交易日数
  - 统计截断风险和失败日期
  - 任务开始日志输出 api、batch_mode、日期范围、计划请求数
  - `batch_stats` 写入 `tushare_import_log.extra_info`

- [x] 3.4 补充按交易日导入测试
  - 文件：新增 `tests/tasks/test_tushare_import_by_trade_date.py`
  - 覆盖 N 个交易日只调用 N 次 API
  - 覆盖每次调用参数为单日 `trade_date`
  - 覆盖空数据、API 异常、停止信号
  - 覆盖 Redis 进度 total 等于交易日数

## 阶段 4：写入策略与 Hook 兼容

- [x] 4.1 为 PostgreSQL 写入增加 hook 控制参数
  - 文件：`app/tasks/tushare_import.py`
  - `_write_to_postgresql(rows, entry, run_post_hooks=True)`
  - 默认行为保持兼容
  - 调整内部 `_run_post_write_hooks` 调用受该参数控制

- [x] 4.2 新增统一写入策略入口
  - 文件：`app/tasks/tushare_import.py`
  - 新增 `WriteContext` 或等价结构
  - 新增 `_write_rows_with_policy(raw_rows, entry, context)`
  - 复用字段映射、行展开、代码转换和存储路由

- [x] 4.3 实现 `daily_basic` 当前指标保护
  - 文件：`app/tasks/tushare_import.py`
  - `daily_basic` 历史交易日不写 `stock_info`
  - 仅市场最近可用交易日允许写 `stock_info`
  - 用户显式传入 `update_current_snapshot=true` 时允许写 `stock_info`
  - 历史交易日仍调用 `backfill_daily_basic_rows`
  - 不影响 `stk_factor_pro` 和 `stk_limit` 主表写入

- [x] 4.4 保持 `stk_limit` Kline 回填 hook
  - 文件：`app/tasks/tushare_import.py`
  - `by_trade_date` 路径写入 `stk_limit` 后继续触发 `backfill_stk_limit_rows`
  - hook 失败记录 warning，不回滚主表导入
  - `extra_info` 合并 hook 统计或错误摘要

- [x] 4.5 补充写入策略测试
  - 文件：新增 `tests/tasks/test_tushare_import_daily_basic_policy.py`
  - 覆盖 `daily_basic` 历史交易日不写主表但执行 hook
  - 覆盖市场最近可用交易日写主表并执行 hook
  - 覆盖旧区间最后一天不写主表
  - 覆盖显式 `update_current_snapshot=true` 时允许写主表
  - 覆盖 hook 失败不影响主流程
  - 覆盖 `stk_limit` 仍写主表并触发 hook

- [x] 4.6 明确导入统计口径
  - 文件：`app/tasks/tushare_import.py`
  - `record_count` / `api_rows` 表示 Tushare 返回有效 rows
  - `primary_written_rows` 表示实际写入主表 rows
  - `kline_aux_backfill` 继续表示 Kline 回填统计
  - `daily_basic` 历史日期回填 Kline 但未写主表时，统计应能区分两者

## 阶段 5：截断检测与配置验证

- [x] 5.1 在 `by_trade_date` 中使用接口级 `max_rows`
  - 文件：`app/tasks/tushare_import.py`
  - 使用 `entry.extra_config.get("max_rows", _TUSHARE_MAX_ROWS)`
  - 返回行数达到上限时记录截断 warning
  - 不自动退回按股票拆分

- [x] 5.2 补充截断检测测试
  - 文件：扩展 `tests/tasks/test_truncation_detection.py` 或新增测试
  - 覆盖 `stk_factor_pro` 使用 10000 上限
  - 覆盖单日返回达到上限时 batch_stats 记录 warning

## 阶段 6：真实库验证与小范围试跑

- [x] 6.1 执行定向后端测试
  - 命令：
    - `pytest tests/tasks/test_tushare_import_strategy.py`
    - `pytest tests/tasks/test_tushare_import_trade_dates.py`
    - `pytest tests/tasks/test_tushare_import_by_trade_date.py`
    - `pytest tests/tasks/test_tushare_import_daily_basic_policy.py`
  - 同时运行受影响的既有 hook 测试

- [x] 6.2 执行小日期范围 dry-run 或真实导入验证
  - 范围：最近 2-3 个交易日
  - 接口：`stk_factor_pro`、`daily_basic`、`stk_limit`
  - 验证计划请求数等于交易日数
  - 验证不再出现 `5531 × 日期数` 的 total

- [x] 6.3 执行数据库覆盖率验证
  - 查询最近交易日 `stk_factor` 行数
  - 查询最近交易日 `kline.turnover`、`vol_ratio`、`limit_up`、`limit_down` 非空覆盖率
  - 记录关键输出到最终说明

## 阶段 7：质量审查与文档同步

- [x] 7.1 运行代码质量自审
  - 按 `.kiro/hooks/code-quality-review.kiro.hook` 检查
  - 重点检查导入路径复杂度、重复逻辑、hook 幂等性、异常吞噬

- [x] 7.2 更新任务状态与风险说明
  - 完成项标记 `[x]`
  - 无法完成项标记 `[!]` 并说明原因
  - 最终报告包含测试命令、验证结果、剩余风险
