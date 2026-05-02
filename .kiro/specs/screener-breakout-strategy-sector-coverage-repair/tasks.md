# 右侧趋势突破策略分组与板块覆盖校验修复任务

## Phase 0：板块行情缺失修复归档与补强

- [x] 0.1 修复 `sector_kline` 写入代码字段映射。
  - 使用 `sector_code` 优先、`ts_code` 兜底写入板块代码。
  - 覆盖需求 5.5。

- [x] 0.2 修复 `sector_kline.time` 无时区列写入失败。
  - 保持普通 `kline` 使用 UTC aware datetime。
  - 对 `sector_kline` 单独转换为 UTC naive datetime。
  - 覆盖需求 5.6。

- [x] 0.3 修复每日快速和缺口补导的板块实表覆盖判断。
  - `dc_daily / ths_daily / tdx_daily / sw_daily / ci_daily` 均以 `sector_kline` 目标日覆盖为准。
  - 覆盖需求 4.1、4.2、4.3。

- [x] 0.4 修复 daily-fast/gap-repair 收尾完整性检查卡住问题。
  - 对每日快速和缺口补导使用轻量目标日覆盖检查。
  - 避免无边界扫描 `kline` 大表。
  - 覆盖需求 4.6。

- [x] 0.5 修复空缺口补导误回退 daily-fast 全链路问题。
  - `repair_plan.missing_steps=[]` 时直接完成轻量检查。
  - 覆盖需求 4.7。

- [x] 0.6 执行板块缺口补导并验证实表覆盖。
  - 已补导 `20260425` 至 `20260430`。
  - 已验证 `2026-04-30` 覆盖：`DC=1013`、`THS=1504`、`TDX=615`、`TI=439`、`CI=437`。

- [x] 0.7 补充板块修复相关自动化测试。
  - `tests/tasks/test_tushare_import_timezone.py`
  - `tests/services/data_engine/test_tushare_smart_import_workflow.py`
  - 已验证相关测试通过。

- [x] 0.8 增加板块导入完成后的实表反查。
  - `dc_daily / ths_daily / tdx_daily / sw_daily / ci_daily` 导入完成后反查 `sector_kline` 覆盖。
  - API 返回 `record_count > 0` 但目标日覆盖为 0 时标记失败或数据不完整。
  - 记录实际覆盖日期、目标覆盖数和缺失日期。
  - 覆盖需求 5.1、5.2、5.3、5.4。

- [x] 0.9 增加板块缺失诊断原因。
  - 区分导入日志误判、API 返回空、字段映射无有效代码/时间、TS 写入失败、目标日非交易日、部分覆盖。
  - 在完整性摘要和任务 `extra_info` 中输出可读诊断信息。
  - 覆盖需求 6.1、6.2、6.3、6.4、6.5。

- [x] 0.10 补充导入后反查和诊断测试。
  - 覆盖 API 返回非空但 `sector_kline` 目标日无覆盖。
  - 覆盖部分日期写入和缺失日期记录。
  - 覆盖完整性摘要展示诊断原因。
  - 覆盖需求 8.3、8.4、8.5。

## Phase 1：策略配置结构扩展

- [x] 1.1 在后端 schema 中新增因子角色和分组配置结构。
  - 新增 `FactorRole`、`GroupLogic`、`FactorGroupConfig`。
  - 扩展 `FactorCondition` 支持 `role`、`group_id`。
  - 扩展 `StrategyConfig` 支持 `factor_groups`、`confirmation_mode`。
  - 覆盖需求 1.1、1.2、2.1。

- [x] 1.2 保持旧策略配置向后兼容。
  - 旧 `factors + logic` 无 `factor_groups` 时保持原行为。
  - `to_dict()` 不丢失旧字段。
  - `from_dict()` 可读取新旧两种结构。
  - 覆盖需求 1.9、2.2、2.6。

- [x] 1.3 扩展 screen API 入参模型。
  - `FactorConditionIn` 增加 `role`、`group_id`。
  - `StrategyConfigIn` 增加 `factor_groups`、`confirmation_mode`。
  - 新增 `FactorGroupConfigIn`。
  - 覆盖需求 2.3。

- [x] 1.4 补充 schema/API 序列化测试。
  - 验证新结构可 round-trip。
  - 验证旧结构行为不变。
  - 覆盖需求 8.1、8.2。

## Phase 2：策略引擎支持主条件和确认因子分组

- [x] 2.1 实现分组评估入口。
  - `factor_groups` 为空时走旧路径。
  - `factor_groups` 非空时按分组路径评估。
  - 覆盖需求 1.1、1.3、1.4。

- [x] 2.2 实现组内逻辑。
  - 支持 `AND`、`OR`、`AT_LEAST_N`、`SCORE_ONLY`。
  - 支持 `min_pass_count`。
  - 覆盖需求 1.3、1.4。

- [x] 2.3 实现组间放行规则。
  - `primary + blocking` 必须通过。
  - `confirmation + blocking` 按配置决定是否拦截。
  - `score_only` 仅影响评分和信号。
  - 覆盖需求 1.4、1.7。

- [x] 2.4 在评分和信号中保留因子角色信息。
  - `FactorResult` 或等价结果对象记录 `role`、`group_id`。
  - 结果评分保留现有权重兼容逻辑。
  - 覆盖需求 1.8。

- [x] 2.4.1 输出策略分组执行日志。
  - 执行策略时记录主条件通过数、确认因子通过数、最终入选数。
  - 日志应能定位具体策略和任务 ID。
  - 覆盖需求 3.3。

- [x] 2.5 更新内置“右侧趋势突破综合策略”推荐配置。
  - 写入可编辑的 `primary_core` 和 `confirmation` 分组。
  - 推荐配置不作为引擎硬编码规则。
  - 覆盖需求 1.5、1.6、3.1。

- [x] 2.6 处理数据库中旧版内置策略配置。
  - 提供启动同步或读取时兼容修正。
  - 不覆盖交易员复制或已编辑的策略。
  - 覆盖需求 3.2、3.4。

- [x] 2.7 补充策略引擎分组测试。
  - 主条件 AND + 确认因子 OR 通过场景。
  - 主条件通过但确认因子阻塞失败场景。
  - 确认因子仅加分不拦截场景。
  - 旧平铺策略回归。
  - 覆盖需求 8.1、8.2。

## Phase 3：后端因子筛选统计

- [x] 3.1 新增因子筛选统计数据结构。
  - 新增 `FactorConditionStats`。
  - `ScreenResult` 增加 `factor_stats` 和可选 `group_stats`。
  - 覆盖需求 7.1、7.6。

- [x] 3.2 扩展因子统计生成逻辑。
  - 新增 `summarize_factor_condition_stats()` 返回列表结构。
  - 保留 `summarize_factor_failures()` 旧 dict 结构作为兼容包装，避免破坏现有日志和测试。
  - 基于当前策略每个启用条件因子统计 `passed_count`、`failed_count`、`missing_count`、`evaluated_count`。
  - 保留 `role`、`group_id`。
  - 覆盖需求 7.1、7.2、7.6。

- [x] 3.3 将因子统计挂载到选股结果。
  - `ScreenExecutor._execute()` 返回 `ScreenResult.factor_stats`。
  - 选股结果缓存写入统计字段。
  - 覆盖需求 7.7。

- [x] 3.4 在异步任务状态中返回因子统计。
  - `screen:task:{task_id}` completed 状态附加 `factor_stats`。
  - `/screen/run/status/{task_id}` 返回 `factor_stats`。
  - 覆盖需求 7.3、7.7。

- [x] 3.5 在 `/screen/results` 返回最近结果统计。
  - 刷新页面后前端仍可恢复最近一次统计。
  - 覆盖需求 7.7、7.8。

- [x] 3.6 补充后端统计测试。
  - 验证通过数、失败数、缺失数。
  - 验证分组角色信息。
  - 验证 API 返回统计字段。
  - 覆盖需求 8.8。

## Phase 4：前端策略编辑器支持因子角色

- [x] 4.1 扩展前端策略配置类型。
  - `FactorCondition` 增加 `role`、`group_id`。
  - 新增 `FactorGroupConfig` 类型。
  - 覆盖需求 2.5。

- [x] 4.2 在因子编辑器行中增加角色选择。
  - 支持主条件、确认因子、仅加分、禁用。
  - 使用紧凑控件，避免扩大表单高度过多。
  - 覆盖需求 1.2、2.5。

- [x] 4.3 增加分组规则配置区域。
  - 支持主条件组和确认组的组合逻辑。
  - 支持确认因子是否拦截。
  - 覆盖需求 1.3、1.4、2.5。

- [x] 4.4 更新策略配置构建和回填。
  - `buildStrategyConfig()` 输出 `factor_groups`、`role`、`group_id`。
  - `selectStrategy()` / 配置恢复逻辑可读取新旧结构。
  - 覆盖需求 2.1、2.2、2.3、2.4。

- [x] 4.5 处理统计 stale 状态。
  - 切换策略、修改因子、修改分组后清空或标记旧统计。
  - 覆盖需求 7.5、7.8。

- [x] 4.6 补充前端策略编辑测试。
  - 验证角色选择。
  - 验证新结构保存和恢复。
  - 验证旧配置恢复不报错。
  - 覆盖需求 8.8。

## Phase 5：前端展示因子筛选统计

- [x] 5.1 扩展 screener store 状态。
  - 新增 `lastFactorStats`、`lastFactorStatsStrategyKey`。
  - `runScreen()` completed 后保存 `factor_stats`。
  - `fetchResults()` 同步恢复 `factor_stats`。
  - 覆盖需求 7.3、7.7。

- [x] 5.2 在当前策略区域新增统计展示。
  - 在“一键执行选股”按钮左侧展示。
  - 格式示例：`ma_trend 通过 265 只`、`money_flow 通过 1334 只，缺失 1 只`。
  - 覆盖需求 7.2、7.3。

- [x] 5.3 实现紧凑响应式样式。
  - 横向滚动或折叠展示。
  - 不遮挡当前策略名称和按钮。
  - 覆盖需求 7.4。

- [x] 5.4 增加角色视觉区分。
  - 主条件、确认因子、仅加分使用不同但克制的标签样式。
  - tooltip 展示完整统计。
  - 覆盖需求 7.6。

- [x] 5.5 处理空状态和失败状态。
  - 未执行过选股不展示过期统计。
  - 任务失败时显示失败原因或清空统计。
  - 覆盖需求 7.8。

- [x] 5.6 补充前端展示测试。
  - 验证按钮左侧展示位置。
  - 验证缺失数量文案。
  - 验证策略变更后 stale/清空。
  - 覆盖需求 8.8。

## Phase 6：联调与回归

- [x] 6.1 执行后端目标测试。
  - 策略 schema 测试。
  - 策略引擎分组测试。
  - 因子统计测试。
  - screen API 测试。
  - Tushare 板块写入和工作流测试。

- [x] 6.2 执行前端目标测试。
  - `ScreenerView` 相关单元测试。
  - 策略编辑集成测试。
  - 必要的 property 测试。

- [x] 6.3 手动执行右侧趋势突破综合策略验证。
  - 验证不再因 `breakout AND macd` 同级硬 AND 长期为空。
  - 验证当前策略栏展示每因子统计。
  - 验证统计与后端返回一致。

- [x] 6.4 验证板块覆盖仍正常。
  - 重新执行 gap_repair plan。
  - 确认 `dc_daily / ths_daily / tdx_daily / sw_daily / ci_daily` 均以 `sector_kline` 实表覆盖跳过。

- [x] 6.5 重启受影响服务。
  - 后端 schema、API、Celery 任务、前端变更完成后重启开发服务。
  - 确认 API 健康检查和 Celery 无残留任务。

- [x] 6.6 更新任务完成状态和最终记录。
  - 执行过程中逐项勾选本任务文件。
  - 记录测试命令、手动验证结果和剩余风险。

### 2026-05-02 执行记录

- 已重启后端 API、Celery worker、Celery beat、Vite 前端，健康检查 `GET /health` 返回 `{"status":"ok","env":"development"}`。
- 已确认内置策略 `00000000-0000-0000-0000-000000000006` 配置包含 `primary_core`、`confirmation`、`score_only` 三组。
- 手动执行右侧趋势突破综合策略任务 `edf32a9d-e2fc-4498-adfd-7b5f7e5d752c`：加载 5335 只，入选 75 只，耗时 154.195 秒。
- 本轮因子统计：`ma_trend` 通过 265 只；`breakout` 通过 1333 只、缺失 4002 只；`sector_rank` 通过 2996 只；`sector_trend` 通过 5222 只；`macd` 通过 273 只；`turnover` 通过 2112 只；`money_flow` 通过 1334 只、缺失 1 只；`rsi` 通过 2117 只。
- 已执行测试：`python -m py_compile app/core/schemas.py app/services/screener/strategy_engine.py app/services/screener/screen_executor.py app/tasks/screening.py app/api/v1/screen.py`；`/Users/poper/ContestTrade/yes/bin/python -m pytest tests/services/screener/test_strategy_engine.py tests/services/test_screening_factor_summary.py`；`npm run type-check`；`npx vitest run src/stores/__tests__/screener-factor-stats.test.ts src/views/__tests__/ScreenerView.test.ts`。

### 2026-05-02 剩余任务执行记录

- 已在 `app/tasks/tushare_import.py` 增加板块日行情导入后 `sector_kline` 实表反查：记录 `target_trade_date`、`target_coverage_count`、`actual_dates`、`missing_dates`、`coverage_by_date`，并在 API 返回行数但目标日覆盖为 0 或部分缺失时将导入结果标记为失败。
- 已增加写入预处理诊断摘要：统计字段映射后缺失时间、无效时间、缺失板块代码和逐行写入失败数，并合并到 `extra_info.sector_kline_postcheck`。
- 已增强 daily-fast/gap-repair 完整性摘要诊断：当导入日志显示成功但 `sector_kline` 未覆盖时输出 `import_log_mismatch` 和补导建议。
- 已执行后端测试：`/Users/poper/ContestTrade/yes/bin/python -m py_compile app/tasks/tushare_import.py app/services/data_engine/tushare_smart_import_workflow.py`；`/Users/poper/ContestTrade/yes/bin/python -m pytest tests/tasks/test_tushare_import_timezone.py tests/services/data_engine/test_tushare_smart_import_workflow.py -q`，30 passed；`/Users/poper/ContestTrade/yes/bin/python -m pytest tests/services/screener/test_strategy_engine.py tests/services/test_screening_factor_summary.py tests/tasks/test_tushare_import_timezone.py tests/services/data_engine/test_tushare_smart_import_workflow.py -q`，77 passed。
- 已执行前端测试：`npm run type-check`；`npx vitest run src/stores/__tests__/screener-factor-stats.test.ts src/views/__tests__/ScreenerView.test.ts`，24 passed。
- 已验证 `20260430` 缺口补导计划：`dc_daily / ths_daily / tdx_daily / sw_daily / ci_daily` 均因 `sector_kline` 实表覆盖跳过，覆盖数分别为 `1013 / 1504 / 615 / 439 / 437`。
- 2026-05-02 复查需求 7：确认后端 `factor_stats` 已实现，但前端选股页重新挂载时会因策略回填 watcher 清空统计，导致按钮左侧看不到最近统计；已修复为策略回填期间不清空、挂载后从 `/screen/results` 恢复，并仅在统计属于当前策略时展示。新增前端回归测试覆盖按钮左侧展示位置和缺失数量文案。
- 2026-05-02 修正 `breakout` 因子统计口径：`breakout=None` 表示“未触发形态突破”，不再计为数据缺失；后续统计计入 `failed_count`。已同步修正当前 Redis 结果缓存，API 反查为 `breakout passed=1422 failed=3913 missing=0`。
