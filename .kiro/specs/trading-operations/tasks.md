# 任务文档：实操模块（Trading Operations）

## 阶段 1：数据模型与数据库迁移

- [x] 1.1 在 `app/core/schemas.py` 中新增枚举类型：`PlanStatus`、`CandidateStatus`、`PositionStatus`、`ChecklistLevel`
- [x] 1.2 在 `app/core/schemas.py` 中新增配置 dataclass：`CandidateFilterConfig`、`StageStopConfig`、`PositionControlConfig`、`MarketProfileConfig`，均实现 `to_dict()` / `from_dict()`
- [x] 1.3 新建 `app/models/operations.py`，定义 6 个 ORM 模型：`TradingPlan`、`CandidateStock`、`BuyRecord`、`PlanPosition`、`DailyChecklist`、`MarketProfileLog`
- [x] 1.4 生成 Alembic 迁移脚本，创建 6 张表及索引、外键、联合唯一约束

## 阶段 2：服务层核心逻辑

- [x] 2.1 新建 `app/services/operations_service.py`，实现 `OperationsService` 类骨架（方法签名 + docstring）
- [x] 2.2 实现交易计划 CRUD 方法：`create_plan`、`update_plan`、`archive_plan`、`delete_plan`、`list_plans`（含概览统计查询）
- [x] 2.3 实现盘后选股与候选筛选：`run_post_market_screening`（调用 ScreenExecutor）、`filter_candidates`（复用 MarketRiskChecker + StockRiskFilter + BlackWhiteListManager 风控检查）、`get_candidates`、`skip_candidate`
- [x] 2.4 实现买入操作：`validate_position_control`（仓位校验）、`execute_buy`（创建 BuyRecord + PlanPosition + 设置初始止损）、`manual_buy`（补录模式）
- [x] 2.5 实现分阶段止损状态机：`evaluate_stop_stage` 纯函数（五阶段转换逻辑）、`run_stop_loss_evaluation`（批量评估所有持仓）、`confirm_sell`、`adjust_stop`
- [x] 2.6 实现每日复盘清单：`run_daily_checklist`（生成 7 维度检查项）、`get_checklist`、`get_checklist_history`、`run_weekly_health_check`（策略健康度评估）
- [x] 2.7 实现市场环境适配：`get_market_profile`、`update_market_profile`、`check_and_switch_market_level`（自动切换 + 记录日志）

## 阶段 3：API 层

- [x] 3.1 新建 `app/api/v1/operations.py`，定义 Pydantic 请求/响应模型
- [x] 3.2 实现交易计划 CRUD 端点：GET/POST `/plans`、GET/PUT/DELETE `/plans/{id}`、PATCH `/plans/{id}/status`
- [x] 3.3 实现候选股端点：GET `/plans/{id}/candidates`、DELETE `/plans/{id}/candidates/{cid}`
- [x] 3.4 实现买入端点：POST `/plans/{id}/buy`、POST `/plans/{id}/buy/manual`
- [x] 3.5 实现持仓端点：GET `/plans/{id}/positions`、POST `/plans/{id}/positions/{pid}/sell`、PATCH `/plans/{id}/positions/{pid}/stop`
- [x] 3.6 实现复盘与市场环境端点：GET `/plans/{id}/checklist`、GET `/plans/{id}/buy-records`、GET/PUT `/plans/{id}/market-profile`
- [x] 3.7 在 `app/api/v1/__init__.py` 中注册 operations_router

## 阶段 4：Celery 定时任务

- [x] 4.1 新建 `app/tasks/operations.py`，定义 `OperationsTask` 基类
- [x] 4.2 实现 4 个定时任务：`post_market_screening`（15:35）、`stop_loss_evaluation`（15:40）、`daily_checklist`（16:00）、`weekly_health_check`（周五 17:00）
- [x] 4.3 在 `app/core/celery_app.py` 中注册 `operations` 队列、任务路由和 Beat 调度

## 阶段 5：前端实现

- [x] 5.1 新建 `frontend/src/stores/operations.ts`，定义接口类型和 Pinia store（state + actions）
- [x] 5.2 新建 `frontend/src/views/OperationsView.vue`，实现交易计划概览卡片列表 + 新建计划对话框
- [x] 5.3 新建 `frontend/src/views/OperationDetailView.vue`，实现 Tab 页框架（候选股/持仓/买入记录/复盘/设置）
- [x] 5.4 实现候选股 Tab：候选股列表展示 + 风控状态标注 + 一键买入确认面板
- [x] 5.5 实现持仓 Tab：持仓列表 + 止损阶段颜色编码 + 卖出信号标记 + 一键卖出
- [x] 5.6 实现买入记录 Tab：历史买入记录表格（含信号快照、盈亏统计）
- [x] 5.7 实现复盘 Tab：复盘清单详情 + 策略健康度卡片
- [x] 5.8 实现设置 Tab：计划配置 JSON 预览（后续迭代为表单）
- [x] 5.9 在 `router/index.ts` 中注册 `/operations` 和 `/operations/:planId` 路由
- [x] 5.10 在 `MainLayout.vue` 的 `menuGroups` 中新增「实操」导航分组

## 阶段 6：集成验证

- [x] 6.1 后端代码安全审查：检查所有新增代码的代码异味、设计模式、最佳实践、可读性、可维护性、性能
- [x] 6.2 向后兼容性验证：确认现有 `trade_order`/`position` 表未修改、`/trade`/`/positions` API 正常、现有 Celery 队列未受影响、TradeView/PositionsView 页面功能正常
- [x] 6.3 验证完整工作流：创建交易计划 → 盘后选股 → 候选筛选 → 买入 → 持仓止损评估 → 复盘清单生成 → 市场环境切换
- [x] 6.4 验证前端页面：交易计划概览 → 计划详情各 Tab 页功能 → 买入/卖出操作流程 → 复盘日历视图
