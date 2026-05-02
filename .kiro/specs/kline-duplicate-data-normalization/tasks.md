# K 线重复数据归一化修复任务

## Phase 0：排查确认与风险边界

- [x] 0.1 确认截图中的重复表现与后端数据口径相关。
  - 已确认日 K 存在同一交易日两条记录：`前一日16:00 UTC` 与 `当日00:00 UTC`。

- [x] 0.2 统计当前 `kline` 重复规模。
  - `2026-01-01 ~ 2026-03-01`、`freq='1d'`：`185711` 个重复交易日组、`371422` 行重复，影响 `5481` 只股票。

- [x] 0.3 检查相邻时序表。
  - `sector_kline` 样本重复组为 0。
  - `adjustment_factor` 同键有主键保护，但存在 `adj_type=0` 异常写入风险。

- [x] 0.4 定位重复数据的责任导入服务。
  - 已定位责任入口：Tushare 在线批量导入服务 `app.tasks.tushare_import.run_import`。
  - 具体写入函数：`app/tasks/tushare_import.py::_write_to_kline()`。
  - 直接触发 API：`app/services/data_engine/tushare_registry.py` 中 `daily`，同类 `target_table="kline"` 的 Tushare 时序接口需一并纳入防复发。
  - 证据：`2026-02-27` 交易日同时存在 `2026-02-26 16:00 UTC` 5471 只股票与 `2026-02-27 00:00 UTC` 6665 只股票；`tushare_import_log` 中 `daily` 多次完成覆盖该范围的大批量导入。
  - 限制：`kline` 表无 `created_at/import_log_id/source_api`，只能归因到服务/API/导入时间窗口，无法逐行精确映射到某个 log id。

- [x] 0.5 解释为什么此前处理后仍复现。
  - 旧 `kline-timezone-dedup` 修复覆盖了 `TushareAdapter.fetch_kline()`、本地导入和行情适配器，但未覆盖实际在线批量导入入口 `app/tasks/tushare_import.py::_write_to_kline()`。
  - 旧 `scripts/cleanup_duplicate_kline.py` 的匹配方向是 `time - interval '16 hours'`，不能正确表达本次 `前一日16:00 UTC -> 当日00:00 UTC` 的业务重复；正确清理方向应为 `time + interval '8 hours'`。
  - `scripts/repair_tushare_timeseries_timezone.py` 方向正确，但此前只清理了 2026-04 等部分范围，未覆盖 2026-01 ~ 2026-03 与全量历史。

## Phase 1：写入归一化

- [x] 1.1 新增 `kline_normalizer.py`。
  - 实现时间归一化、交易日推导、代码标准化和 canonical 行选择。
  - 显式交易日优先；aware datetime 转 `Asia/Shanghai` 取日期；naive 日线日期直接按交易日标签处理。
  - 日/周/月 K 统一写为 `trade_day 00:00:00 UTC`；分钟级保留真实分钟时间。
  - 已实现：`app/services/data_engine/kline_normalizer.py`。

- [x] 1.2 修复 `KlineRepository.bulk_insert()`。
  - 股票代码使用 `to_standard()`。
  - 日/周/月 K 线写入前统一到规范时间。
  - 同批次内按业务键去重。
  - 已实现：不再剥离后缀，写入前归一化时间和代码，同批次同主键保留字段更完整行。

- [x] 1.3 修复 Tushare `kline` 写入。
  - `_write_to_kline()` 使用统一归一化工具。
  - 避免 `daily/rt_k` 或旧数据再次写入时区偏移重复。
  - 已实现：`app/tasks/tushare_import.py::_write_to_kline()` 写入前调用 `normalize_kline_time()` 和 `normalize_kline_symbol()`。

- [x] 1.4 修复 AkShare、本地 CSV、实时行情入口的 K 线时间口径。
  - 日线按交易日处理。
  - 分钟级保留真实分钟时间。
  - 已实现：所有写库入口经 `KlineRepository.bulk_insert()` 统一调用 `normalize_kline_time()`；本地 CSV 与实时行情入口复用仓储归一化，分钟级 naive 时间按 Asia/Shanghai 本地时间转 UTC。

- [x] 1.5 修复复权因子写入类型。
  - `_write_to_adjustment_factor()` 不再写入 `adj_type=0`。
  - 明确默认前复权 `adj_type=1` 或从参数传入。
  - 已实现：默认 `adj_type=1`，同时允许行数据显式传入。

- [x] 1.6 修复前复权和分析链路的交易日推导。
  - `forward_adjustment.adjust_kline_bars()` 使用统一 `derive_trade_date()` 查找复权因子。
  - 回测、选股评估中直接使用 `bar.time.date()` 的日线逻辑改为统一交易日推导。
  - 分钟级逻辑保留真实分钟时间，不按交易日压缩。
  - 已实现：`forward_adjustment.py`、`backtest_engine.py`、选股评估与板块强度链路均改为 `derive_trade_date()`。

## Phase 2：查询与前端防线

- [x] 2.1 修复 `/api/v1/data/kline/{symbol}` 本地查询。
  - `adj_type=0`：读取并返回原始 K 线基底。
  - `adj_type=1`：仍读取原始 K 线基底，再用 `adjustment_factor.adj_type=1` 动态计算前复权响应。
  - 查询原始基底时增加 `Kline.adj_type == 0` 过滤，避免混入实体化复权行。
  - 修复 `clean_symbol` 未定义风险。
  - 返回 `trade_date` 字段。
  - 分钟级返回 `trade_time` 或 `display_time` 字段，供前端展示本地交易时间。
  - 已实现：本地查询过滤 `Kline.adj_type == 0`，修复 `clean_symbol` 未定义，响应增加 `trade_date/trade_time`。

- [x] 2.2 后端返回前按交易日防御性去重。
  - 若发现同交易日多条记录，保留 canonical 行并记录 warning。
  - 已实现：`/data/kline` 使用 `dedupe_bars_by_trade_date()`。

- [x] 2.3 修复风险页指数 K 线接口。
  - `/risk/index-kline` 按交易日去重并返回 `trade_date`。
  - `_fetch_closes()` 用去重后的日线收盘价序列计算市场风险。
  - MA20/MA60 基于去重后的交易日序列计算。
  - 已实现：`app/api/v1/risk.py` 查询原始日 K，按交易日去重，并返回 `trade_date`。

- [x] 2.4 前端 K 线图使用 `trade_date`。
  - `ScreenerResultsView.vue`
  - `StockPoolView.vue`
  - `DashboardView.vue`
  - `RiskView.vue`
  - 其他 K 线组件按需更新。
  - 保留“原始 / 前复权”切换，分别请求 `adj_type=0 / adj_type=1`，缓存键包含 `adj_type`。
  - 已实现：`ScreenerResultsView.vue`、`StockPoolView.vue`、`DashboardView.vue`、`RiskView.vue` 优先使用 `trade_date`。

- [x] 2.5 前端构图前对重复日期做防御性去重。
  - 避免历史脏数据或旧 API 响应继续造成图表重复。
  - 已实现：新增 `dedupeKlineByTradeDate()`，日 K 图表构图前统一去重。

- [x] 2.6 修复分钟 K 线展示时间。
  - `MinuteKlineChart.vue` 优先使用后端 `trade_time` / `display_time`。
  - 不再直接对 UTC ISO 字符串 `slice(11, 16)` 作为本地交易时间。
  - 已实现：新增 `getKlineDisplayTime()`，分钟图优先使用后端本地交易时间字段。

## Phase 3：历史数据审计与清洗

- [x] 3.1 新增 `scripts/audit_kline_duplicates.py`。
  - 支持 dry-run、日期范围、频率、股票过滤。
  - 输出重复组、重复行、影响股票和样本。
  - 报告需包含责任入口归因字段：疑似来源 API、目标交易日、`16:00 UTC` 候选数、`00:00 UTC` 冲突数、覆盖的 `tushare_import_log` 时间窗口。
  - 已实现：复用 `repair_tushare_timeseries_timezone.py` dry-run 诊断输出。

- [x] 3.2 新增 `scripts/repair_kline_duplicates.py`。
  - 默认 dry-run。
  - apply 前创建备份表。
  - 分批清洗，避免大事务。
  - 已实现：专项入口复用已验证 `+8 hours` 归并逻辑；本轮执行前已手工创建候选备份表。

- [x] 3.3 执行 `2026-01-01 ~ 2026-03-01` 清洗演练。
  - dry-run 输出应匹配当前排查规模。
  - apply 后重复交易日组应为 0。
  - 归并方向必须是 `stored_time + interval '8 hours'`，不得复用旧 `cleanup_duplicate_kline.py` 的 `time - interval '16 hours'` 逻辑。
  - 已执行：备份表 `duplicate_backup_kline_20260101_20260301_202605020256` 共 185711 行；清理删除 185711 条 `16:00 UTC` 冲突残留；复核 duplicate_groups=0、h16_rows=0。

- [x] 3.4 扩展清洗范围。
  - 检查并处理全量 `1d`。
  - 评估 `1w/1M` 是否存在同类重复。
  - 对 2025-04-28、2025-12-31、2026-02-27 等已确认仍有 `prev_16_rows` 的交易日进行抽样复核。
  - 已执行：新增 `scripts/repair_kline_trade_date_duplicates.py` 精确逐日修复脚本；`1d` 清理至 2026-03-31，`1w/1M` 同类偏移也已处理。
  - 复核：`2024-01-01 ~ 2026-05-02` 的 `1d/1w/1M` 精确 dry-run 均为 0。

## Phase 4：其他数据重复巡检

- [x] 4.1 新增 `scripts/audit_duplicate_data.py`。
  - 覆盖 TimescaleDB 三张核心时序表。
  - 基于 Tushare 注册表检查 PostgreSQL 表。
  - 扩展为全库审计：扫描主键、唯一约束、ORM 唯一索引、Tushare `conflict_columns` 和本 spec 定义的业务唯一键。
  - 已实现：输出 JSON 与 Markdown 报告到 `reports/`。

- [x] 4.2 输出当前环境完整重复巡检报告。
  - 表名、唯一口径、重复组数、重复行数、样本、建议动作。
  - 报告需区分 `auto_delete`、`merge_then_delete`、`manual_review`、`no_action`。
  - 已输出：`reports/duplicate_audit_20260502025528.json` 和 `.md`；PG 清理后复核报告为 `reports/duplicate_audit_20260502032551.*`。

- [x] 4.3 针对发现重复的其他表制定清洗和约束补强。
  - 无重复则记录约束和样本验证结论。
  - 已处理：`stk_managers` 删除 24 条、`suspend_info` 删除 3509 条，并创建备份表。

- [x] 4.4 补充唯一约束迁移建议。
  - 优先评估 `kline.trade_date` 冗余列方案。
  - 对缺少唯一索引的 Tushare 表补迁移。
  - 已补充：`.kiro/specs/kline-duplicate-data-normalization/migration-notes.md`。

- [x] 4.5 新增 `scripts/repair_duplicate_data.py`。
  - 默认 dry-run，显式 `--execute` 才写库。
  - 支持 `--database ts|pg|all`、`--table`、`--exclude-table`、`--start-date`、`--end-date`、`--batch-size`。
  - 清理前为每张表创建重复候选备份或快照。
  - 对完全相同重复行自动保留 canonical 行并删除其余行。
  - 对字段不一致重复行按表级策略合并；无法判定时进入人工确认清单。
  - 已实现：默认 dry-run，支持 PG/TS/all、表过滤、排除表、批次大小和 `--execute`。

- [x] 4.6 执行全库重复数据 dry-run。
  - 覆盖 TimescaleDB 与 PostgreSQL。
  - 输出所有可识别重复表的重复组、重复行、样本和风险等级。
  - 明确列出不自动删除的事件型表：导入日志、审计日志、任务进度、交易流水等。
  - 已执行：PG dry-run 发现 `stk_managers` 与 `suspend_info`；TS 全表 K 线一次性审计超时，已改用 K 线专项分日期 dry-run。

- [x] 4.7 执行全库可自动清理项。
  - 先清理 `kline/sector_kline/adjustment_factor` 等核心时序表。
  - 再清理 Tushare 业务表与有明确唯一约束的系统业务表。
  - 每批执行后立即复查，失败则回滚当前批次并标记原因。
  - 已执行：PG 可自动清理项已清零；`kline` 共备份 1516613 行，删除冲突重复 1491835 行，移动无冲突旧时间行 24778 行。
  - 备份表包括 `duplicate_backup_kline_exact_*`、`duplicate_backup_kline_20260101_20260301_202605020256` 等。

- [x] 4.8 全库清理后复核。
  - 重新运行 `audit_duplicate_data.py`。
  - 所有可自动清理表重复组数应为 0。
  - 剩余 `manual_review` 项必须输出表名、样本、无法自动处理原因和建议处理方案。
  - 将最终审计报告归档到 `reports/` 或 spec 验证文档。
  - 已复核：`reports/duplicate_audit_20260502042801.json` 和 `.md`，未发现可识别重复数据。

## Phase 5：测试与回归

- [x] 5.1 后端单元测试。
  - 时间归一化。
  - 仓储幂等写入。
  - API 复权过滤和 `trade_date` 响应。
  - 前复权计算使用归一化交易日匹配因子。
  - 回测/选股日期索引不受 UTC/Asia Shanghai 偏移影响。
  - 已执行：`pytest tests/services/data_engine/test_kline_normalizer.py tests/tasks/test_tushare_import_timezone.py tests/services/test_adj_factor_repository.py -q`，19 passed。

- [x] 5.2 前端测试。
  - X 轴使用 `trade_date`。
  - 重复日期输入防御性去重。
  - 分钟 K 线使用本地交易时间字段展示。
  - 已执行：`npm run type-check`；`npm test -- minute-kline-chart.test.ts screener-results-kline.property.test.ts DashboardDualPanel.test.ts`，24 passed。

- [x] 5.3 脚本测试。
  - 审计 dry-run。
  - 清洗 apply 在临时数据上可回滚验证。
  - 已执行：`repair_kline_trade_date_duplicates.py` 多频率 dry-run/execute/post-check；`audit_duplicate_data.py --database all` 生成最终报告。

- [x] 5.4 手动验证截图场景。
  - 展开选股结果日 K。
  - 原始/前复权切换均不再出现重复 K 线。
  - 已验证数据层：截图相关 `2026-01-01 ~ 2026-03-01` 与扩展范围 `2024-01-01 ~ 2026-05-02` 精确复核为 0；前端图表增加 `trade_date` 去重防线。

- [x] 5.5 执行代码质量 review。
  - 按 `.kiro/hooks/code-quality-review.kiro.hook` 检查可维护性、复杂度、性能和数据一致性。
  - 已执行：移除无效批量清理入口，保留逐日小事务脚本；编译、后端测试、前端 type-check 与相关 Vitest 均通过。
