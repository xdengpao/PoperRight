# Tushare 每日智能选股快速导入工作流 Tasks

## Phase 0：共用工作流基础能力

- [x] 1. 先完成 smart-screening 工作流运行中子接口实时进度展示
  - 对应 `.kiro/specs/tushare-smart-screening-import-workflow/tasks.md` 的任务 25。
  - 后端状态接口合并运行中子任务的 `tushare:import:{child_task_id}` 进度到 `child_tasks[].progress`。
  - 前端运行中显示 `completed / total`、失败数和当前处理对象，完成后显示最终 `record_count`。
  - 保持现有单接口导入状态接口和历史记录展示兼容。
  - 补充服务层/API/前端测试。

- [x] 2. 先完成 smart-screening 工作流超时失败落账和恢复能力
  - 对应 `.kiro/specs/tushare-smart-screening-import-workflow/tasks.md` 的任务 26。
  - 捕获 `SoftTimeLimitExceeded` 和硬超时，将 workflow 标记为 `failed`。
  - 对 worker 异常退出这类无法在任务内捕获的场景，提供 stale running 检测与修复能力。
  - 将当前运行中的 child task 和对应 `tushare_import_log` 标记为失败或 `stale_failed`。
  - 释放 `tushare:workflow:running:smart-screening` 和当前子接口锁。
  - 前端展示超时失败原因、最后接口、已完成步骤，并允许恢复。
  - 补充服务层/API/任务测试。

## Phase 1：计划模型与模式扩展

- [x] 3. 定义一键导入链路模式枚举和请求结构
  - 新增或扩展 `TushareImportPlanMode`：`daily_fast`、`gap_repair`、`weekly_maintenance`、`full_initialize`。
  - 扩展工作流启动请求，支持 `mode`、`target_date`、`strategy_scope`、`repair_source_workflow_id`、`options`。
  - 保持现有完整工作流请求兼容，未传新模式时可映射为 `full_initialize` 或现有默认行为。

- [x] 4. 实现导入计划数据结构
  - 定义 `execute_steps`、`skip_steps`、`maintenance_suggestions`、`estimated_cost`、`next_actions`。
  - 每个 step 包含 `api_name`、`params`、`reason`、`priority`、`estimated_rows`、`estimated_duration`、`skip_reason`。
  - 计划响应能同时服务确认面板、工作流执行和测试断言。

- [x] 5. 新增或扩展 Tushare 智能导入计划生成器
  - 在服务层按 `api -> service -> task` 分层实现，避免前端拼接单接口任务。
  - 每日快速、缺口补导、周维护、完整初始化共用同一计划生成入口。
  - 计划生成器复用 Tushare registry、Token tier、参数校验和依赖检查。

## Phase 2：每日快速链路

- [x] 6. 实现每日快速默认执行步骤
  - 默认包含 `daily`、`adj_factor`、`daily_basic`、`stk_factor_pro`、`moneyflow_dc`、`dc_daily`。
  - 默认包含核心指数集合的 `index_daily`、`index_dailybasic`、`idx_factor_pro`。
  - 默认不把 `trade_cal` 作为导入步骤执行，只本地读取或必要时提示维护。
  - 默认跳过 `stock_basic`、`index_basic`、`dc_index`、`dc_member`、`ths_member`、`tdx_member`、`index_member_all`、`ci_index_member`。
  - 默认只使用 DC 资金流和 DC 板块行情，不启用 THS/TDX/TI/CI 扩展链路。

- [x] 7. 实现每日快速目标交易日解析
  - 页面默认日期仍为最近一天；服务端按 Asia/Shanghai 解析目标交易日。
  - 每日快速链路默认按 18:00 后的当天或最近交易日执行。
  - 若 18:00 前导入当天数据，确认面板提示数据可能尚未完整。
  - 休市日自动回退到最近交易日，并在计划中说明回退原因。

- [x] 8. 实现策略感知依赖推导
  - 复用或扩展 `derive_strategy_dependency_summary()`。
  - 默认策略集保守覆盖右侧趋势突破综合策略和现有智能选股默认策略。
  - 策略未使用筹码、两融、打板、龙虎榜因子时，跳过 `cyq_perf`、`margin_detail`、`limit_list_d`、`limit_step`、`top_list`。
  - 策略使用 THS/TDX/TI/CI 板块源时，仅追加对应行情接口，并通过维护建议提示成分刷新。

- [x] 9. 实现核心指数最小化参数
  - 默认核心指数集合为 `000001.SH`、`399001.SZ`、`399006.SZ`、`000300.SH`、`000905.SH`、`000852.SH`。
  - 指数接口按核心集合生成参数，不默认执行全量指数。
  - 用户或策略需要全量指数时，允许通过扩展选项切换。

## Phase 3：新鲜度检查与缺口补导

- [x] 10. 实现数据新鲜度检查服务
  - 检查 K 线/日频表最近 `trade_date/time` 是否覆盖目标交易日。
  - 检查资金流、板块行情、技术专题和核心指数最近可用日期。
  - 检查基础表、板块成分和指数成分的最近成功导入日志或 `updated_at` 是否在 TTL 内。
  - 输出缺失接口、缺失日期范围、覆盖数量和跳过原因。

- [x] 11. 实现每日快速跳过已覆盖接口
  - 当接口已覆盖目标交易日时，计划中标记为 `skip_steps`。
  - 跳过原因展示为“今日已覆盖”“静态数据未过期”“当前策略未使用”等。
  - 保证跳过不影响完整性检查和最终摘要。

- [x] 12. 实现缺口补导计划生成
  - 根据最近成功日期和目标交易日集合生成最小日期范围。
  - 支持从每日快速完整性检查结果自动带入缺失接口和日期。
  - 支持用户手动日期范围，只补该范围内缺失交易日。
  - 缺口补导完成后再次执行完整性检查。

## Phase 4：周维护与完整初始化

- [x] 13. 实现周维护计划
  - 默认包含 `stock_basic`、`trade_cal`、`index_basic`、`dc_index`、`dc_member`。
  - 按选项追加 `ths_index`、`ths_member`、`tdx_index`、`tdx_member`、`index_classify`、`index_member_all`、`ci_index_member`。
  - 根据 TTL 和完整性结果提示是否需要执行周维护。
  - 当每日快速启用静态强制刷新选项时，可将必要低频接口追加到本次计划，并在确认面板提示耗时增加。

- [x] 14. 保留并映射完整初始化链路
  - `full_initialize` 复用现有 smart-screening 完整工作流阶段。
  - 历史大范围补数、首次初始化和大型修复继续走完整链路。
  - 用户选择长日期范围时提示预计耗时，并建议缺口补导或完整初始化。

## Phase 5：后端 API 与 Celery 执行

- [x] 15. 新增或扩展计划 API
  - 新增 `POST /data/tushare/workflows/smart-screening/plan` 或等价接口。
  - 返回执行、跳过、建议维护、预计耗时和下一步动作。
  - 覆盖 Token 缺失、模式非法、日期非法和无可执行步骤场景。

- [x] 16. 扩展工作流启动 API
  - `POST /data/tushare/workflows/smart-screening/start` 支持四种 `mode`。
  - 启动时使用已生成计划作为执行来源，避免确认面板和实际执行不一致。
  - 已有工作流运行时继续返回 409，并展示当前运行工作流摘要。

- [x] 17. 扩展 Celery 工作流执行
  - 任务按计划中的 `execute_steps` 顺序执行。
  - `skip_steps` 不创建导入日志，但进入工作流摘要。
  - 子接口继续复用现有 `_process_import` 或稳定服务层包装。
  - 工作流终态写入实际耗时、接口耗时排名、完整性摘要和下一步建议。

## Phase 6：前端交互

- [x] 18. 在一键导入控制区增加链路模式下拉框
  - 下拉框选项包含“每日快速”“缺口补导”“周维护”“完整初始化”。
  - 默认选择“每日快速”。
  - 放在日期范围和一键导入按钮附近，保持按钮上下两排各两个的小尺寸布局。

- [x] 19. 扩展确认面板展示导入计划
  - 展示本次执行接口、日期范围、原因和预计耗时。
  - 展示本次跳过接口和跳过原因。
  - 展示建议维护项和风险提示。
  - 将现有确认面板中的 16:00 口径改为 18:00；18:00 前导入当天数据时提示 Tushare 当日数据可能未完整。

- [x] 20. 实现每日快速后的补导闭环入口
  - 完整性通过时展示“每日选股数据已就绪”。
  - 完整性不通过时展示缺失接口、缺失日期范围和建议链路。
  - 用户从结果进入缺口补导时，自动带入上一轮缺口范围和接口集合。
  - 缺失属于低频静态或成分过期时，建议“周维护”而不是“缺口补导”。

- [x] 21. 扩展前端工作流状态和历史展示
  - 状态区展示执行、跳过、建议维护和实际耗时。
  - 展示接口耗时排名和可优化建议。
  - 对超时失败、stale running、可恢复状态给出明确文案和恢复入口。

## Phase 7：测试与验证

- [x] 22. 新增计划生成服务测试
  - 覆盖四种链路模式。
  - 覆盖每日快速默认接口和默认跳过接口。
  - 覆盖核心指数集合、18:00 前提示、休市日回退。
  - 覆盖策略感知扩展专题启停。

- [x] 23. 新增新鲜度和缺口补导测试
  - 覆盖已覆盖目标交易日时跳过。
  - 覆盖最近成功日期早于目标交易日时生成缺口范围。
  - 覆盖低频数据 TTL 过期时建议周维护。
  - 覆盖每日快速失败后带入缺口补导。

- [x] 24. 新增 API 和 Celery 任务测试
  - 覆盖计划 API、启动 API、状态 API 和恢复 API。
  - 覆盖四种模式下执行步骤和跳过步骤的一致性。
  - 覆盖超时失败落账、锁释放和恢复执行。

- [x] 25. 新增或扩展前端测试
  - 验证链路下拉框默认“每日快速”。
  - 验证切换链路后重新生成计划。
  - 验证确认面板展示执行、跳过和建议维护列表。
  - 验证完整性失败后可以进入缺口补导并自动带入缺口。
  - 验证超时失败和 stale running 的展示与恢复入口。

- [x] 26. 运行验证命令
  - 运行相关后端服务测试。
  - 运行相关 API 测试。
  - 运行相关 Celery 任务测试。
  - 运行相关前端测试或类型检查。
  - 手工验证四种链路的确认面板、进度展示、暂停、恢复和停止。

## Phase 8：代码质量与交付

- [x] 27. 执行代码质量自查
  - 检查是否遵守 `api -> service -> task` 分层。
  - 检查是否未破坏现有单接口导入、批量导入、完整工作流和历史记录。
  - 检查 Redis 键、状态枚举、模式枚举和错误信息命名一致。
  - 检查中文 UI 文案、日志和注释符合项目约定。

- [x] 28. 更新任务状态和交付说明
  - 按实际完成情况更新本文件复选框。
  - 同步更新 smart-screening 工作流任务 25、26 的完成状态。
  - 总结实现文件、验证结果、剩余风险和后续优化建议。
