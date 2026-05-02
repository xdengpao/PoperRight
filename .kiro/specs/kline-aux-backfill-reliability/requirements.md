# K 线辅助字段回填可靠性修复需求

## 背景

`daily_basic`、`stk_limit` 已按交易日全市场导入并写入源数据，但导入后置 hook 在并发更新 TimescaleDB `kline` 表时出现 `DeadlockDetectedError`。结果表现为：

- `stk_factor_pro` 已正常写入 `stk_factor`，不属于本次修复范围。
- `stk_limit` 源表存在 `up_limit/down_limit`，但部分交易日未完整回填到 `kline.limit_up/limit_down`。
- `daily_basic` 不保留独立历史表，历史导入 rows 只在导入过程内通过 hook 回填 `kline.turnover/vol_ratio`，hook 失败会造成当日辅助字段缺失。
- `kline` 最新日期可能只有指数行，指数行本来无法匹配个股 `daily_basic/stk_limit`，这类空值不应被误判为回填失败。

## 方案评估

第 4 点“给 `kline_aux_field_backfill` 加串行锁或死锁重试”的推荐落地方案如下：

1. 仅加死锁重试：实现简单，但两个 Celery worker 同时更新 `kline` 时仍可能反复冲突，尤其 `daily_basic` 和 `stk_limit` 同时按交易日跑。
2. 仅靠人工顺序导入：短期可缓解，但不可靠，无法防止后续调度或多人操作再次并发。
3. 串行化回填 + 死锁重试：推荐。通过数据库级 advisory lock 或等效锁保证同一时刻只有一个 K 线辅助字段回填在写 `kline`，同时保留小批次死锁/连接异常重试，兼顾可靠性和可恢复性。
4. 新增完整 `daily_basic` 历史表：能提升可补偿能力，但超出当前“只修复回填可靠性”的范围，后续可单独设计。

本 Spec 采用方案 3。

## 术语

- K 线辅助字段：`kline.turnover`、`kline.vol_ratio`、`kline.limit_up`、`kline.limit_down`。
- 回填 hook：Tushare 导入任务写入 PostgreSQL 主表后，立即调用 `KlineAuxFieldBackfillService` 更新 TimescaleDB `kline` 的逻辑。
- 串行化回填：同一时间只允许一个辅助字段回填事务写入 `kline`，避免不同导入任务互相死锁。
- 可补偿回填：导入完成后可再次执行的回填能力，当前 `stk_limit` 可从历史表补跑，`daily_basic` 需要重新导入对应日期才能补偿。

## 需求

### 1. 回填写入必须避免并发死锁

**用户故事：** 作为数据维护者，我希望 `daily_basic` 与 `stk_limit` 可以并发导入，但它们对 `kline` 的辅助字段回填不会互相死锁，从而减少人工重跑。

**验收标准：**

1. WHEN `daily_basic` 和 `stk_limit` 的回填 hook 在不同 Celery worker 中同时触发 THEN 系统 SHALL 对写入 `kline` 的回填事务进行串行化。
2. WHEN 一个回填事务正在更新 `kline` THEN 另一个回填事务 SHALL 等待锁释放，而不是直接并发更新同一批 `kline` 行。
3. IF 回填锁获取或释放发生异常 THEN 系统 SHALL 记录清晰日志并不得破坏主导入任务的状态一致性。

### 2. 回填批次必须具备可重试能力

**用户故事：** 作为数据维护者，我希望偶发死锁、连接中断或事务冲突时系统能自动重试，而不是直接留下整日空值。

**验收标准：**

1. WHEN 单个回填批次遇到 `DeadlockDetectedError` 或可识别的瞬时数据库异常 THEN 系统 SHALL 使用有限次数退避重试。
2. WHEN 重试成功 THEN 回填统计 SHALL 反映最终的 `matched_rows` 与 `updated_rows`。
3. WHEN 超过最大重试次数仍失败 THEN 系统 SHALL 记录失败原因，并让导入日志包含该回填失败摘要。
4. 系统 SHALL 避免无限重试，默认重试次数和等待时间应可在代码中集中调整。

### 3. 回填统计必须可观测且不被长日志吞没

**用户故事：** 作为数据维护者，我希望导入日志能快速判断哪些日期回填成功、哪些日期失败，而不需要翻完整 Celery 堆栈。

**验收标准：**

1. WHEN 回填完成 THEN `tushare_import_log.extra_info` SHALL 包含紧凑的回填摘要，包括源接口、日期范围、源行数、匹配行数、更新行数、跳过行数、失败次数。
2. WHEN 某个交易日回填失败 THEN 摘要 SHALL 保留失败日期和错误类型。
3. 系统 SHALL 避免把完整 SQL 或超长异常堆栈写入 `extra_info`，以降低字段截断风险。
4. Celery 日志 SHALL 继续保留足够的异常上下文用于排查。

### 4. 回填逻辑必须保持幂等

**用户故事：** 作为数据维护者，我希望重复导入或补跑回填不会破坏已有正确数据。

**验收标准：**

1. WHEN 同一批 `daily_basic` rows 被重复回填 THEN `kline.turnover/vol_ratio` SHALL 保持一致，已相同的数据不应重复更新。
2. WHEN 同一批 `stk_limit` rows 被重复回填 THEN `kline.limit_up/limit_down` SHALL 保持一致，已相同的数据不应重复更新。
3. IF 某个字段源值为空 THEN 系统 SHALL 保留 `kline` 现有值，不应写入空值覆盖。

### 5. 回填范围必须只针对个股日 K 辅助字段

**用户故事：** 作为数据维护者，我希望指数 K 线的辅助字段为空时不会被误判为导入失败。

**验收标准：**

1. WHEN 回填 `daily_basic` 或 `stk_limit` THEN 系统 SHALL 仅匹配标准个股代码与 `freq='1d'`、`adj_type=0` 的 K 线。
2. WHEN `kline` 行是指数、板块或其他非个股代码 THEN 系统 SHALL 不要求其具备 `daily_basic/stk_limit` 辅助字段。
3. 回填统计中的 `skipped_rows` SHALL 能反映源数据与可匹配 K 线之间的差异。

### 6. 测试必须覆盖并发保护与失败退化

**用户故事：** 作为开发者，我希望此次修复有单元测试保护，避免后续导入优化再次引入死锁或不可观测失败。

**验收标准：**

1. SHALL 为 `KlineAuxFieldBackfillService` 增加死锁重试测试。
2. SHALL 为回填锁或串行化机制增加测试，验证回填 SQL 在锁保护下执行。
3. SHALL 为 `_run_post_write_hooks` 增加测试，验证失败摘要被紧凑记录且不抛出到主导入任务。
4. SHALL 保留现有回填幂等测试并确保通过。

## 非目标

- 本次不新增独立 `daily_basic` 历史表。
- 本次不改变 `stk_factor_pro` 写入 `stk_factor` 的表设计。
- 本次不把指数 K 线强行补齐 `turnover/vol_ratio/limit_up/limit_down`。
- 本次不重构 Tushare 导入 UI。
