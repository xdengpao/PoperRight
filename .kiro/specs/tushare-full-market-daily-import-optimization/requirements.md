# 需求文档：Tushare 日级全市场导入性能优化

## 简介

近期排查显示，`stk_factor_pro`、`daily_basic`、`stk_limit` 在未传 `ts_code` 且传入日期范围时，被通用 Tushare 导入路由误判为 `by_code_and_date`。在当前全市场约 5531 只股票、`20260101~20260429` 约 119 个自然日的场景下，请求量会膨胀到约 65.8 万次 API 调用，导致导入长时间无法完成，并进一步影响 `stk_factor`、`kline.turnover`、`kline.vol_ratio`、`kline.limit_up`、`kline.limit_down` 等选股关键数据的补齐。

本 spec 目标是在不破坏现有 Tushare 注册表驱动架构的前提下，为支持按交易日返回全市场数据的日级接口建立“未传 `ts_code` 时按交易日全市场导入”的专用路径；同时使用交易日历跳过非交易日，并重新梳理 `daily_basic` 历史数据的落库语义，使其既能高效回填 K 线辅助字段，又不持续污染 `stock_info` 的当前指标语义。

## 术语表

- **日级全市场接口**：支持通过 `trade_date` 或单日 `start_date/end_date` 一次返回全市场数据的 Tushare 接口，例如 `stk_factor_pro`、`daily_basic`、`stk_limit`。
- **按交易日全市场导入**：未传 `ts_code` 时，按交易日列表逐日调用 API，每次请求不附带股票代码，导入当天全市场数据。
- **交易日历**：`trade_calendar` 表中 `is_open=1` 的 A 股交易日；用于跳过周末和节假日。
- **当前指标表**：`stock_info` 当前承担股票基础信息和最新指标字段，例如 `pe_ttm`、`pb`、`market_cap`。
- **历史每日指标**：按 `(ts_code, trade_date)` 存储的 `daily_basic` 历史明细，用于回填 K 线辅助字段和未来可能的回测/预览。
- **Kline 辅助字段**：TimescaleDB `kline` 中的 `turnover`、`vol_ratio`、`limit_up`、`limit_down`。

## 需求

### 需求 1：日级全市场接口按交易日导入

**用户故事：** 作为系统运维人员，我希望 `stk_factor_pro`、`daily_basic`、`stk_limit` 在未指定股票代码时按交易日全市场导入，以便大范围历史补齐能在可接受时间内完成。

#### 验收标准

1. WHEN 用户启动 `stk_factor_pro` 且参数包含 `start_date/end_date` 但不包含 `ts_code` 时，THE 系统 SHALL 使用按交易日全市场导入路径，而不是 `by_code_and_date`
2. WHEN 用户启动 `daily_basic` 且参数包含 `start_date/end_date` 但不包含 `ts_code` 时，THE 系统 SHALL 使用按交易日全市场导入路径，而不是 `by_code_and_date`
3. WHEN 用户启动 `stk_limit` 且参数包含 `start_date/end_date` 但不包含 `ts_code` 时，THE 系统 SHALL 使用按交易日全市场导入路径，而不是 `by_code_and_date`
4. WHEN 用户显式传入 `ts_code` 时，THE 系统 SHALL 保持按指定股票代码导入的兼容行为
5. THE 导入进度 SHALL 显示新的 `batch_mode`，例如 `by_trade_date` 或等价名称，以便前端和日志能区分该路径
6. THE 实现 SHALL 保持其他 Tushare 接口的既有分批策略不变，除非接口被明确配置为日级全市场接口

### 需求 2：分片日期使用交易日历

**用户故事：** 作为系统运维人员，我希望日级全市场导入跳过周末和节假日，以减少空请求和无效等待。

#### 验收标准

1. WHEN `trade_calendar` 表存在目标范围内的 `is_open=1` 日期时，THE 系统 SHALL 只对这些交易日发起日级全市场 API 请求
2. WHEN `trade_calendar` 在目标范围内无可用数据时，THE 系统 SHALL 使用保守兜底策略生成日期列表，并在日志中记录缺少交易日历的 warning
3. THE 交易日解析 SHALL 支持 `YYYYMMDD` 入参和数据库中已有日期格式
4. THE 交易日列表 SHALL 按日期升序执行，便于进度观察和断点分析
5. THE 进度 total SHALL 等于实际计划请求的交易日数量，而不是自然日数量
6. THE 导入结果统计 SHALL 包含计划交易日数、成功交易日数、空数据交易日数、失败交易日数

### 需求 3：Tushare 返回行数上限与截断检测配置化

**用户故事：** 作为开发者，我希望 `stk_factor_pro`、`daily_basic`、`stk_limit` 使用符合接口真实上限的截断判断，避免误报或错误拆分。

#### 验收标准

1. THE `stk_factor_pro` 注册信息 SHALL 明确配置单次返回行数上限，默认按 Tushare 文档使用 `10000`
2. THE `daily_basic` 注册信息 SHALL 明确配置合理的单次返回行数上限和预估每日行数
3. THE `stk_limit` 注册信息 SHALL 明确配置合理的单次返回行数上限和预估每日行数
4. WHEN 单个交易日返回行数达到接口上限时，THE 系统 SHALL 记录截断风险，并把该交易日纳入导入统计
5. IF 接口支持通过交易所或其他参数进一步拆分，THEN 后续设计 SHALL 允许对单个交易日执行二级拆分；本需求不要求立即实现所有拆分策略

### 需求 4：`stk_factor_pro` 导入保持 `stk_factor` 语义完整

**用户故事：** 作为量化交易员，我希望 `stk_factor_pro` 全市场导入后能完整更新专业技术因子字段，以便选股中的 RSI/KDJ/CCI/WR/TRIX/BIAS 等因子可用。

#### 验收标准

1. WHEN `stk_factor_pro` 导入某交易日数据时，THE 系统 SHALL 按 `(ts_code, trade_date)` 写入或更新 `stk_factor`
2. THE 字段映射 SHALL 继续支持 `macd_dif`、`macd_dea`、`macd`、`kdj_k`、`kdj_d`、`kdj_j`、`rsi_6`、`rsi_12`、`rsi_24`、`boll_upper`、`boll_mid`、`boll_lower`、`cci`
3. THE upsert 更新列 SHALL 包含当前已映射的 `wr`、`dmi`、`trix`、`bias`，避免补导时这些字段仍不更新
4. WHEN 单个交易日部分股票无返回数据时，THE 系统 SHALL 不伪造缺失行
5. THE 导入完成后 SHALL 能通过数据库统计看到最近交易日 `stk_factor` 覆盖股票数明显接近 Tushare 返回行数

### 需求 5：`stk_limit` 导入继续回填 Kline 涨跌停字段

**用户故事：** 作为量化交易员，我希望优化后的 `stk_limit` 全市场导入仍然触发已有 Kline 辅助字段回填，以便 `limit_up/limit_down` 在 K 线中可用。

#### 验收标准

1. WHEN `stk_limit` 通过按交易日全市场路径导入 rows 时，THE 系统 SHALL 继续调用现有 `backfill_stk_limit_rows`
2. THE 回填 SHALL 继续按 `(symbol, trade_date, freq='1d', adj_type=0)` 匹配 `kline`
3. WHEN 回填 hook 失败时，THE 主表导入 SHALL 不回滚，但导入结果 SHALL 记录可观测的 hook 错误摘要
4. THE 导入统计 SHALL 区分主表写入行数和 Kline 回填统计

### 需求 6：`daily_basic` 短期回填与长期历史表设计

**用户故事：** 作为量化交易员，我希望 `daily_basic` 历史导入既能高效回填 `kline.turnover/vol_ratio`，又不会把历史每日指标反复覆盖到 `stock_info` 的当前字段。

#### 验收标准

1. 短期实现 SHALL 保持现有 `daily_basic` 导入后置 hook，使用 API rows 回填 `kline.turnover` 和 `kline.vol_ratio`
2. WHEN `daily_basic` 按交易日全市场路径导入历史日期时，THE 系统 SHALL 避免用旧日期指标覆盖 `stock_info` 中代表当前状态的 `pe_ttm`、`pb`、`market_cap`
3. WHEN 导入日期为市场最近可用交易日或用户明确选择更新当前指标时，THE 系统 MAY 更新 `stock_info` 当前指标
4. 长期设计 SHALL 支持新增独立历史表，例如 `daily_basic_history` 或等价表，按 `(ts_code, trade_date)` 存储每日指标明细
5. IF 本次实施新增历史表，THEN 表结构 SHALL 至少包含 `ts_code`、`trade_date`、`turnover_rate`、`volume_ratio`、`pe_ttm`、`pb`、`total_mv`/`market_cap`，并建立唯一约束 `(ts_code, trade_date)`
6. IF 本次实施暂不新增历史表，THEN 设计文档 SHALL 明确 `daily_basic` 历史补跑的临时语义和后续迁移方案

### 需求 7：任务排队与并发可观测性

**用户故事：** 作为系统运维人员，我希望大范围 Tushare 导入不会让任务看起来“卡住”，并能判断任务是在排队、运行还是被前置长任务阻塞。

#### 验收标准

1. WHEN Tushare 导入任务已创建但 Celery worker 尚未开始执行时，THE 进度 SHALL 保持 `pending`，并可通过运行任务列表看到该任务
2. WHEN Celery worker 开始执行任务时，THE 进度 SHALL 更新为 `running`，并设置 batch mode 与 total
3. THE 前端或 API SHALL 能展示 `pending/running/completed/failed/stopped` 的差异，不要求本 spec 重做 UI
4. THE 日志 SHALL 在任务开始时输出 api_name、batch_mode、计划请求数和日期范围
5. THE 系统 SHALL 保持同一 api_name 并发锁，避免重复启动同一接口导入

### 需求 8：测试与验证

**用户故事：** 作为开发者，我希望通过单元测试和真实库验证确认请求量已从“股票 × 日期”降到“交易日”，且数据字段被正确补齐。

#### 验收标准

1. THE 测试 SHALL 覆盖 `determine_batch_strategy` 或等价路由逻辑：三个目标接口未传 `ts_code` 时不再返回 `by_code_and_date`
2. THE 测试 SHALL 覆盖显式传入 `ts_code` 时的兼容路径
3. THE 测试 SHALL 覆盖交易日历解析：有交易日历时跳过非交易日，无交易日历时使用兜底并记录 warning
4. THE 测试 SHALL 覆盖按交易日全市场导入时每个交易日只调用一次 API
5. THE 测试 SHALL 覆盖 `stk_factor_pro` 的 `wr/dmi/trix/bias` upsert 更新列
6. THE 测试 SHALL 覆盖 `daily_basic` 历史日期不覆盖 `stock_info` 当前指标的规则
7. THE 验证 SHALL 包含一次小日期范围真实导入或 dry-run 统计，确认计划请求数等于交易日数
8. THE 验证 SHALL 包含数据库覆盖率查询：最近交易日 `stk_factor` 行数、`kline.turnover/vol_ratio/limit_up/limit_down` 非空覆盖率

### 需求 9：导入统计口径清晰

**用户故事：** 作为系统运维人员，我希望导入统计能区分 API 拉取行数、主表写入行数和 Kline 回填结果，以便判断 `daily_basic` 历史导入虽未写 `stock_info` 但是否完成了 Kline 回填。

#### 验收标准

1. THE `by_trade_date` 导入结果 SHALL 使用 `record_count` 或 `api_rows` 表示 Tushare 返回的有效 rows 数
2. THE `by_trade_date` 导入结果 SHALL 使用 `primary_written_rows` 表示实际写入主表的 rows 数
3. THE `daily_basic` 历史日期只回填 Kline 而不写 `stock_info` 时，THE 统计 SHALL 体现 `api_rows > primary_written_rows`
4. THE Kline 回填统计 SHALL 继续通过 `kline_aux_backfill` 或等价字段记录，并与主表写入行数分开

## 非目标

1. 本 spec 不要求优化所有 Tushare 接口，仅聚焦 `stk_factor_pro`、`daily_basic`、`stk_limit`
2. 本 spec 不要求突破 Tushare 官方频率限制或绕过 Token 权限
3. 本 spec 不要求重做 Tushare 导入前端页面，只要求后端进度和日志可区分新路径
4. 本 spec 不要求立即完成全量历史数据补跑，实施完成后可先用小范围验证
5. 本 spec 不改变 K 线 OHLCV 的主导入来源和复权存储策略
