# Tushare 时序数据日期时区修复 Requirements

## 背景

当前 Tushare 导入任务在写入 TimescaleDB 时序表时，将 `YYYYMMDD` 交易日期解析为 naive `datetime`。在 TimescaleDB `TIMESTAMPTZ` 或会话时区参与转换时，日线数据会从目标交易日 `00:00:00` 偏移到前一日 `16:00:00+00`。这导致：

- `daily` 接口已从 Tushare 返回 2026-04-29 个股行情，但本地 `kline` 按 `time::date='2026-04-29'` 查不到个股日 K；
- `daily_basic/stk_limit` 已导入 2026-04-29 辅助字段，但回填 `kline` 时 `matched_rows=0`；
- 同一交易日可能同时存在 `00:00:00+00` 与 `16:00:00+00` 两种时间戳，形成重复或错日展示；
- 已有历史 spec `.kiro/specs/kline-timezone-dedup/` 提到 K 线时区重复问题，但当前 Tushare 写入函数仍有同类风险，且未覆盖 `sector_kline`。

本次需求按用户要求统一检查并修复 Tushare 时序导入中的同类问题。初步代码扫描结论：

- 受影响：`kline` 写入函数 `_write_to_kline`，覆盖 `daily/weekly/monthly/stk_weekly_monthly/bak_daily/rt_k/rt_min/rt_min_daily/index_daily/index_weekly/index_monthly/rt_idx_k/rt_idx_min/rt_idx_min_daily/idx_mins` 等目标表为 `kline` 的 Tushare 接口；
- 受影响：`sector_kline` 写入函数 `_write_to_sector_kline`，覆盖 `ths_daily/dc_daily/tdx_daily/sw_daily/rt_sw_k/ci_daily` 等板块行情接口；
- 额外发现：`stk_mins/rt_min/idx_mins` 等分钟接口的 `freq` 可由用户参数传入，当前写入入口只读取 `entry.extra_config.freq`，需要在本次修复中把运行时 `freq` 传递到 TimescaleDB 写入层，否则分钟数据可能被默认写成 `1d`；
- 不受同类 TIMESTAMPTZ 偏移影响：`adjustment_factor` 使用 `DATE` 类型；PostgreSQL Tushare 业务表多数使用 `DATE` 或字符串交易日期，非时序主键的 `created_at/updated_at` 属系统时间，不属于 Tushare 交易日解析。

## 术语

- 交易日：Tushare 返回的 `trade_date`，格式通常为 `YYYYMMDD`。
- 日级时序数据：`freq` 为 `1d/1w/1M` 或业务语义为日线/周线/月线的 K 线、板块 K 线。
- 分钟级时序数据：`freq` 为 `1m/5m/15m/30m/60m` 等包含盘中时间的数据。
- 规范时间戳：日级交易日期统一存储为 `YYYY-MM-DD 00:00:00+00`，分钟级保留实际分钟时间并明确时区。
- 偏移记录：日级数据被存为 `YYYY-MM-DD 16:00:00+00`，实际代表下一自然交易日的记录。

## Requirements

### Requirement 1：统一 Tushare 时序日期解析

**User Story:** 作为量化系统维护者，我希望 Tushare 所有时序行情写入都使用明确的时区规则，这样日线、周线、月线不会因运行环境时区不同而错日。

#### Acceptance Criteria

1. WHEN `_write_to_kline` 处理 `trade_date=YYYYMMDD` THEN 系统 SHALL 将其解析为 timezone-aware UTC datetime，时间为 `00:00:00+00`。
2. WHEN `_write_to_sector_kline` 处理 `trade_date=YYYYMMDD` THEN 系统 SHALL 使用同一套 timezone-aware UTC 日期解析逻辑。
3. WHEN Tushare 返回分钟级或带具体时间字段的数据 THEN 系统 SHALL 使用运行时 `freq` 判断分钟语义，优先解析具体时间字段并显式设置或转换为 UTC，避免 naive datetime 写入 TimescaleDB。
4. IF `trade_date` 格式无效 THEN 系统 SHALL 跳过该行并保持现有导入任务不中断行为。

### Requirement 2：覆盖所有受影响的 Tushare 时序接口

**User Story:** 作为数据使用者，我希望股票、指数和板块行情的日期都一致，这样跨表回填、预览、选股和回测不会被错日数据干扰。

#### Acceptance Criteria

1. WHEN 导入目标表为 `kline` 的任一 Tushare 接口写入数据 THEN 系统 SHALL 使用统一的时序日期规范化函数。
2. WHEN 导入目标表为 `sector_kline` 的任一 Tushare 接口写入数据 THEN 系统 SHALL 使用统一的时序日期规范化函数。
3. WHEN 导入 `adjustment_factor` THEN 系统 SHALL 继续使用 `DATE` 存储，不引入不必要的 datetime 转换。
4. WHEN 导入 PostgreSQL Tushare 业务表 THEN 系统 SHALL 保持现有 `DATE`/字符串字段语义，不将非时序交易日改为 `TIMESTAMPTZ`。

### Requirement 3：修复历史错日与重复数据

**User Story:** 作为策略使用者，我希望历史库中已导入的数据也被校正，这样 2026-04-29 这类交易日能按交易日查到完整个股 K 线并完成辅助字段回填。

#### Acceptance Criteria

1. WHEN 检测到 `kline` 日级数据存在 `16:00:00+00` 偏移记录 THEN 系统 SHALL 提供可重复执行的数据校正方案，将其归并到正确交易日的 `00:00:00+00`。
2. WHEN 同一 `symbol/freq/adj_type/目标交易日` 同时存在偏移记录和规范记录 THEN 系统 SHALL 保留目标规范记录已有非空字段，仅用偏移记录的非空字段补齐目标空值，并避免违反唯一索引。
3. WHEN 校正 `kline` 后 THEN 系统 SHALL 能重新执行 `daily_basic/stk_limit` 回填，使 2026-04-29 个股日 K 的 `turnover/vol_ratio/limit_up/limit_down` 正常命中。
4. WHEN `sector_kline` 存在同类偏移记录 THEN 系统 SHALL 提供同类校正方案，并保留 `sector_code/data_source/freq/time` 唯一性。
5. IF 校正前检测到异常冲突或疑似分钟数据被误判为日级偏移 THEN 系统 SHALL 停止自动校正并输出待人工确认的诊断结果。

### Requirement 4：防止辅助字段回填继续受时区影响

**User Story:** 作为数据维护者，我希望辅助字段回填按交易日稳定匹配 K 线，这样导入 `daily_basic/stk_limit` 后不需要手工排查错日。

#### Acceptance Criteria

1. WHEN `daily_basic/stk_limit` 回填按 `trade_date` 匹配 `kline` THEN 系统 SHALL 在规范化后的 `00:00:00+00` 日级 K 线上命中目标交易日。
2. WHEN 回填统计中某交易日 `source_rows > 0` 且 `matched_rows = 0` THEN 系统 SHALL 能通过日志或诊断 SQL 判断是 K 线缺失还是时间偏移。
3. WHEN 修复完成后验证 2026-04-29 THEN 系统 SHALL 显示个股 `daily` K 线存在，且辅助字段覆盖率与 2026-04-28 同量级。

### Requirement 5：测试与诊断覆盖

**User Story:** 作为开发者，我希望通过自动化测试锁住这个问题，避免后续导入函数再次引入 naive datetime。

#### Acceptance Criteria

1. WHEN 单元测试覆盖 `_write_to_kline` 日期解析 THEN 测试 SHALL 断言 `20260429` 写入参数为 timezone-aware `2026-04-29T00:00:00+00:00`。
2. WHEN 单元测试覆盖 `_write_to_sector_kline` 日期解析 THEN 测试 SHALL 断言其与 `kline` 使用同一 UTC 日期规范。
3. WHEN 测试覆盖 `adjustment_factor` THEN 测试 SHALL 断言其仍写入 `date` 对象而非 datetime。
4. WHEN 运行诊断 SQL THEN 系统 SHALL 能统计 `kline/sector_kline` 在指定日期范围内 `00:00:00+00` 与 `16:00:00+00` 的分布。
5. WHEN 执行代码质量检查 THEN 系统 SHALL 不存在重复日期解析逻辑或隐藏的 naive datetime 写入路径。

### Requirement 6：运行安全与可回滚

**User Story:** 作为系统管理员，我希望历史修复脚本可以先演练再执行，避免误改大量行情数据。

#### Acceptance Criteria

1. WHEN 执行历史校正 THEN 系统 SHALL 支持 dry-run 模式，输出受影响行数、冲突行数、样例记录和预计更新范围。
2. WHEN dry-run 结果确认后 THEN 系统 SHALL 支持按表、日期范围、频率分批执行校正。
3. WHEN 校正执行失败 THEN 系统 SHALL 使用事务回滚当前批次，不留下半批次更新。
4. WHEN 校正完成 THEN 系统 SHALL 输出校正前后覆盖率 SQL 与推荐的补跑导入/回填顺序。

### Requirement 7：补充修复 16:00 UTC 残留重复日线

**User Story:** 作为策略使用者，我希望清理 `2026-04-27 16:00:00+00` 这类错误日线记录，这样同一股票同一交易日不会同时存在 `16:00 UTC` 与 `00:00 UTC` 两条日线，突破/均线等指标不会被重复交易日扭曲。

#### 背景与来源分析

已确认当前库中存在同一股票同一本地交易日两条日线的情况，例如 `000001.SZ`：

- `2026-04-27 16:00:00+00`，按 Asia/Shanghai 展示为 `2026-04-28 00:00:00`；
- `2026-04-28 00:00:00+00`，当前入口修复后的规范 UTC 零点记录。

`2026-04-27 16:00:00+00` 的来源不是新的 UTC 规范化入口，而是旧导入路径将 Tushare `trade_date=20260428` 解析成 naive `2026-04-28 00:00:00`，再由 `TIMESTAMPTZ`/会话时区按 Asia/Shanghai 转换后落库为 UTC `2026-04-27 16:00:00+00`。后续入口修复生效后，同一交易日又写入了规范 `2026-04-28 00:00:00+00`，于是形成残留重复。

现有历史校正工具已具备 `time + interval '8 hours'` 的归并方向，但此前仅对部分日期执行过校正，且最终验证没有覆盖全量交易日重复分布。因此本补充需求要求重新按日期范围全量诊断并去重。

#### Acceptance Criteria

1. WHEN 诊断 `kline` 日线数据 THEN 系统 SHALL 按 `target_time = stored_time + interval '8 hours'` 识别 `16:00 UTC` 残留记录，并按目标交易日输出候选、冲突、可移动数量。
2. WHEN 同一 `symbol/freq/adj_type/target_time` 已存在规范 `00:00 UTC` 记录 THEN 系统 SHALL 将 `16:00 UTC` 记录的非空辅助字段补齐到目标记录的空字段，然后删除 `16:00 UTC` 残留记录。
3. WHEN 目标规范记录不存在 THEN 系统 SHALL 将 `16:00 UTC` 记录移动到 `target_time`，而不是删除。
4. WHEN 执行去重 THEN 系统 SHALL 仅处理日级频率 `1d/1w/1M`，不得误处理分钟级盘中数据。
5. WHEN 去重完成 THEN 系统 SHALL 验证指定日期范围内不存在同一 `symbol/freq/adj_type/local_trade_date` 多条日线记录。
6. WHEN 去重完成 THEN 系统 SHALL 重新抽样运行“趋势 + 突破”诊断，确认 `breakout_any` 不再因重复交易日被压低到异常水平。
7. IF dry-run 发现目标冲突中 OHLCV 值不一致 THEN 系统 SHALL 在报告中输出样例和差异计数；自动修复仍保留目标规范记录的 OHLCV，只用残留记录补齐目标空值，避免覆盖新导入的规范行情。
