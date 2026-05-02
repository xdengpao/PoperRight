# 智能选股 Tushare 一键数据导入工作流 Tasks

## Phase 1：工作流定义与状态服务

- [x] 1. 新增 `app/services/data_engine/tushare_smart_import_workflow.py`
  - 定义 `WorkflowStep`、`WorkflowStage`、`WorkflowDefinition`、`WorkflowRunState` 数据结构。
  - 实现默认智能选股工作流阶段和接口清单。
  - 支持 `include_moneyflow_ths`、`include_ths_sector`、`include_tdx_sector`、`include_ti_sector`、`include_ci_sector` 扩展选项。
  - 验证默认链路包含 `stock_basic`、`trade_cal`、`daily`、`adj_factor`、`daily_basic`、`stk_factor_pro`、`moneyflow_dc`、`dc_index`、`dc_member`、`dc_daily`、指数专题和扩展专题接口。

- [x] 2. 实现策略依赖扫描摘要
  - 从因子注册表和策略示例/内置模板扫描当前智能选股使用因子。
  - 输出已覆盖因子、未覆盖因子和兼容风险。
  - 将摘要纳入工作流定义响应和完整性检查结果。
  - 为后续新增策略或因子提供测试断言，避免静默遗漏。

- [x] 3. 实现工作流默认参数生成
  - 支持工作流请求传入 `date_range.start_date` 和 `date_range.end_date`。
  - 将日期范围同步到所有包含 `DATE_RANGE` 的导入步骤。
  - 不向无日期范围参数的导入步骤强行注入日期。
  - 未传日期范围时按 Asia/Shanghai 当前日期兜底为最近一天。
  - 支持 `initialize` 模式或近 1 年快捷范围。
  - 为 `index_weight` 生成核心指数集合参数。
  - 保持日期参数格式为 `YYYYMMDD`。

- [x] 4. 实现工作流状态读写
  - 使用 `tushare:workflow:{workflow_task_id}` 保存状态。
  - 使用 `tushare:workflow:running:smart-screening` 控制同一时刻只运行一个智能选股工作流。
  - 使用 `tushare:workflow:stop:{workflow_task_id}` 保存停止信号。
  - 状态 TTL 设为 24 小时。

- [x] 5. 实现 Token 和并发校验
  - 根据工作流定义汇总所需 Token tier。
  - Token 可用性判断与现有导入服务保持一致，分级 Token 缺失时允许回退到 `tushare_api_token`。
  - 缺失 Token 时返回明确的 `missing_token_tiers`。
  - 子接口执行前检查现有 `tushare:import:lock:{api_name}`，避免与手动导入冲突。

## Phase 2：导入核心复用与 Celery 工作流任务

- [x] 6. 重构 `app/tasks/tushare_import.py` 的导入核心
  - 确认 `_process_import` 可被工作流任务复用。
  - 如有必要，补充一个稳定的 async 包装函数用于“已创建日志后的单接口执行”。
  - 保持现有 `run_import` 行为和任务名不变。

- [x] 7. 新增 `app/tasks/tushare_workflow.py`
  - 注册 `app.tasks.tushare_workflow.run_smart_screening_import_workflow`。
  - 显式设置 `queue="data_sync"`、`soft_time_limit=28800`、`time_limit=32400`，避免继承全局短超时。
  - 校验 Celery Redis broker `visibility_timeout` 是否覆盖工作流任务上限，避免长任务重复投递。
  - 按阶段顺序执行工作流步骤。
  - 每个子接口创建独立 `tushare_import_log`。
  - 初始化并更新子接口原有 Redis 进度。
  - 执行中持续更新工作流 Redis 状态。

- [x] 8. 实现停止和失败处理
  - 工作流收到停止信号后停止后续步骤。
  - 工作流收到暂停信号后停止后续步骤，并进入可恢复的 `paused` 状态。
  - 当前子接口同步写入 `tushare:import:stop:{child_task_id}`。
  - 关键步骤失败时中止工作流。
  - 可选步骤失败时按 `continue_on_failure` 记录并继续。
  - 终态释放 running 键和子接口锁。

- [x] 9. 实现恢复执行能力
  - 支持从失败或停止的步骤继续。
  - 跳过已完成步骤。
  - 保留原工作流的子任务历史和失败信息。

## Phase 3：完整性检查

- [x] 10. 实现智能选股数据完整性检查
  - 检查日线 K 线最近日期和覆盖股票数。
  - 检查复权因子最近日期和覆盖股票数。
  - 检查 `daily_basic` 最近日期、覆盖股票数和 K 线辅助字段情况。
  - 检查 `moneyflow_dc` 最近可用日期和覆盖股票数，允许最近 10 天内回退。
  - 检查 `stk_factor` 最近日期和覆盖股票数。
  - 检查 DC 板块基础信息、成分和行情覆盖情况。
  - 检查指数专题核心数据最近日期。
  - 检查筹码、两融、打板、龙虎榜扩展专题最近日期。

- [x] 11. 输出完整性建议
  - 对关键数据缺失给出对应接口和建议重新导入阶段。
  - 对 `pe_ttm` 等旧策略字段输出兼容风险提示。
  - 将完整性摘要写入工作流终态。

## Phase 4：后端 API

- [x] 12. 扩展 `app/api/v1/tushare.py`
  - 新增 `GET /data/tushare/workflows/smart-screening`。
  - 新增 `POST /data/tushare/workflows/smart-screening/start`。
  - 新增 `GET /data/tushare/workflows/status/{workflow_task_id}`。
  - 新增 `POST /data/tushare/workflows/pause/{workflow_task_id}`。
  - 新增 `POST /data/tushare/workflows/stop/{workflow_task_id}`。
  - 新增 `GET /data/tushare/workflows/running`。
  - 新增 `POST /data/tushare/workflows/resume/{workflow_task_id}`。

- [x] 13. 统一 API 错误响应
  - Token 缺失返回 400 和 `missing_token_tiers`。
  - 已有工作流运行返回 409。
  - 子接口锁冲突返回工作流状态中的失败阶段和接口。
  - 未知工作流返回 404 或 `status=unknown`。

## Phase 5：前端入口与进度展示

- [x] 14. 修改 `frontend/src/views/TushareImportView.vue` 连接状态栏
  - 在“一键导入”按钮左侧增加数据起始日期和结束日期控件。
  - 增加一键导入、一键暂停、一键恢复、一键停止四个小按钮，上下两排各两个。
  - 日期范围默认最近一天，即起始日期和结束日期均为当前日期。
  - 当前时间早于 18:00 且结束日期为当前日期时，在确认面板展示当天数据可能未完整提示。
  - 在“重新检测”旁增加“一键导入”按钮。
  - 根据连接状态和 Token 状态控制禁用。
  - 起始日期晚于结束日期时禁用“一键导入”并提示。
  - 按钮保持紧凑，不改变现有单接口导入布局。

- [x] 15. 增加工作流确认面板
  - 点击“一键导入”后加载并展示工作流定义。
  - 展示阶段、接口数量、Token 要求和用户选择的数据范围。
  - 支持选择 `incremental` 或 `initialize` 模式，选择初始化时可快捷设置近 1 年范围。
  - 支持可选扩展数据源开关。

- [x] 16. 增加工作流进度区
  - 展示整体状态、当前阶段、当前接口、完成数和失败数。
  - 展示子接口任务列表和错误信息。
  - 支持停止和继续执行。
  - 完成后展示完整性检查摘要。

- [x] 17. 实现前端状态恢复
  - 页面加载时请求 `/data/tushare/workflows/running`。
  - 有运行中工作流时恢复进度区和轮询。
  - 工作流进入终态后停止轮询并刷新导入历史。

## Phase 6：测试与验证

- [x] 18. 新增工作流定义服务测试
  - 覆盖默认接口清单。
  - 覆盖阶段顺序。
  - 覆盖扩展选项。
  - 覆盖默认参数生成。
  - 覆盖日期范围仅同步到需要 `DATE_RANGE` 的步骤。
  - 覆盖 Token tier 汇总。

- [x] 19. 新增 Celery 工作流任务测试
  - mock 单接口导入核心，验证执行顺序。
  - 验证关键步骤失败中止。
  - 验证可选步骤失败继续。
  - 验证停止信号。
  - 验证子接口日志创建。

- [x] 20. 新增 API 测试
  - 覆盖工作流定义、启动、状态、停止、running、resume。
  - 覆盖 Token 缺失、并发冲突和未知任务。

- [x] 21. 新增或扩展前端测试
  - 验证“一键导入 / 一键暂停 / 一键恢复 / 一键停止”按钮展示。
  - 验证起始日期和结束日期控件展示并默认最近一天。
  - 验证日期范围不合法时禁用一键导入。
  - 验证连接或 Token 不满足时禁用。
  - 验证确认面板展示工作流阶段。
  - 验证确认后调用启动接口并携带所选日期范围。
  - 验证暂停、恢复、停止按钮按状态启禁并调用对应接口。
  - 验证 running workflow 恢复轮询。

- [x] 22. 运行验证命令
  - 运行相关后端单元测试。
  - 运行相关 API 测试。
  - 运行相关前端测试或类型检查。
  - 手工启动开发服务验证按钮、确认面板和工作流状态展示。

## Phase 7：代码质量与收尾

- [x] 23. 执行代码质量自查
  - 检查是否遵守 `api -> service -> task` 分层。
  - 检查是否未破坏现有单接口导入、批量导入和历史记录。
  - 检查 Redis 键、状态枚举和错误信息命名一致。
  - 检查中文 UI 文案和注释符合项目约定。

- [x] 24. 更新任务状态和交付说明
  - 按实际完成情况更新本文件复选框。
  - 总结实现文件、验证结果和残余风险。

## Phase 8：后续优化观察池

- [x] 25. 优化工作流运行中子接口实时进度展示
  - 共用前置任务：该能力也是 `.kiro/specs/tushare-daily-fast-import-workflow/tasks.md` Phase 0 的任务 1，需先完成再实现每日快速、缺口补导等新链路。
  - 问题记录：`daily` 等长耗时子接口运行中，单接口进度 Redis 已有 `completed / total`，但工作流卡片只展示 `child.record_count`，因此显示 `0 行`。
  - 后端状态接口合并运行中子任务的 `tushare:import:{child_task_id}` 进度到 `child_tasks[].progress`。
  - 前端对子接口按状态展示：运行中显示 `completed / total`、失败数和当前处理对象；完成后显示最终 `record_count`。
  - 保持现有单接口导入状态接口和历史记录展示兼容。
  - 补充服务层/API/前端测试。
  - 后续如观察到其他一键导入可观测性问题，可一并纳入本阶段处理。

- [x] 26. 优化超时后的失败落账和恢复能力
  - 共用前置任务：该能力也是 `.kiro/specs/tushare-daily-fast-import-workflow/tasks.md` Phase 0 的任务 2，需先完成再实现每日快速、缺口补导等新链路。
  - 问题记录：完整工作流触发 `SoftTimeLimitExceeded` 后，Celery 任务已失败，但 Redis workflow 与当前 child task 仍显示 `running`。
  - 捕获 `SoftTimeLimitExceeded`、硬超时和 worker 异常退出，将 workflow 状态标记为 `failed`，写入错误原因。
  - 将当前运行中的 child task 和对应 `tushare_import_log` 标记为失败或 stale failed，避免前端误判仍在导入。
  - 释放 `tushare:workflow:running:smart-screening` 和当前子接口锁，避免后续导入被假运行阻塞。
  - 前端展示超时失败原因、最后接口、已完成步骤，并允许点击恢复从未完成步骤继续。
  - 补充服务层/API/任务测试，覆盖超时失败、stale running 修复和恢复执行。
