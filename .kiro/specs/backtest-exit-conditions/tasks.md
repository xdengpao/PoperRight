# 实现计划：回测自定义平仓条件

## 概述

基于已确认的需求和设计文档，将自定义平仓条件功能分解为增量式编码任务。后端使用 Python（FastAPI + dataclass），前端使用 TypeScript（Vue 3 + Pinia）。每个任务构建在前一个任务之上，最终完成端到端集成。

## 任务列表

- [x] 1. 实现平仓条件数据模型
  - [x] 1.1 在 `app/core/schemas.py` 中新增 `ExitCondition` 和 `ExitConditionConfig` 数据类
    - 新增 `VALID_INDICATORS` 和 `VALID_OPERATORS` 常量集合
    - 实现 `ExitCondition` dataclass，包含 `freq`、`indicator`、`operator`、`threshold`、`cross_target`、`params` 字段
    - 实现 `ExitConditionConfig` dataclass，包含 `conditions` 列表和 `logic` 字段（默认 "AND"）
    - 实现 `to_dict()` 和 `from_dict()` 序列化/反序列化方法
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x] 1.2 扩展 `BacktestConfig` 新增 `exit_conditions` 可选字段
    - 在 `BacktestConfig` dataclass 中新增 `exit_conditions: ExitConditionConfig | None = None`
    - _需求: 5.5_
  - [x] 1.3 扩展 `_TradeRecord` 和 `_SellSignal` 数据结构
    - 在 `app/services/backtest_engine.py` 的 `_TradeRecord` 中新增 `sell_reason: str = ""` 字段
    - 在 `_SellSignal` 的 reason 注释中补充 `"EXIT_CONDITION"` 类型
    - _需求: 7.1, 7.4_
  - [x] 1.4 编写 `ExitConditionConfig` 序列化往返属性测试
    - **Property 1: ExitConditionConfig round-trip serialization**
    - **验证: 需求 1.6, 1.7**
    - 在 `tests/properties/test_exit_condition_properties.py` 中使用 Hypothesis 生成任意合法的 `ExitConditionConfig`，验证 `from_dict(config.to_dict())` 与原对象等价
  - [x] 1.5 编写数据模型单元测试
    - 在 `tests/services/test_exit_condition.py` 中测试 `ExitCondition` 和 `ExitConditionConfig` 的构造、默认值、各种指标和运算符组合
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. 实现 ExitConditionEvaluator 评估引擎
  - [x] 2.1 创建 `app/services/exit_condition_evaluator.py`，实现核心评估逻辑
    - 实现 `ExitConditionEvaluator` 类
    - 实现 `evaluate()` 方法：接收 `ExitConditionConfig`、symbol、bar_index、indicator_cache、exit_indicator_cache，返回 `(triggered, reason)`
    - 实现 `_evaluate_single()` 方法：评估单条平仓条件
    - 实现 `_get_indicator_value()` 方法：从缓存获取指标值，支持自定义参数
    - 实现 `_check_cross()` 方法：检测 cross_up / cross_down 交叉信号
    - 实现 AND / OR 逻辑组合
    - 处理数据不足、NaN、无效指标等异常情况（跳过条件，记录日志）
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_
  - [x] 2.2 编写逻辑运算符评估正确性属性测试
    - **Property 2: Logic operator evaluation correctness**
    - **验证: 需求 2.2, 2.3**
    - 在 `tests/properties/test_exit_condition_properties.py` 中使用 Hypothesis 生成任意逻辑运算符和布尔值列表，验证 AND 等于 `all()`、OR 等于 `any()`
  - [x] 2.3 编写数值比较运算符正确性属性测试
    - **Property 3: Numeric comparison operator correctness**
    - **验证: 需求 2.4**
    - 使用 Hypothesis 生成任意浮点数和合法数值运算符，验证评估结果与 Python 原生比较一致
  - [x] 2.4 编写交叉检测正确性属性测试
    - **Property 4: Cross detection correctness**
    - **验证: 需求 2.5, 2.6**
    - 使用 Hypothesis 生成任意两组连续两日浮点数值对，验证 cross_up 和 cross_down 的判定逻辑
  - [x] 2.5 编写 ExitConditionEvaluator 单元测试
    - 在 `tests/services/test_exit_condition_evaluator.py` 中测试具体评估场景
    - 测试 RSI > 80、MACD_DIF cross_down MACD_DEA 等具体条件
    - 测试边界条件：空条件列表、单条件、数据不足、NaN 值
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.9_

- [x] 3. 检查点 - 确保数据模型和评估器测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 扩展指标缓存与 BacktestEngine 集成
  - [x] 4.1 在 `app/services/backtest_engine.py` 中实现 `_precompute_exit_indicators()` 函数
    - 检查 `ExitConditionConfig` 中引用的指标参数组合
    - 对非默认参数的指标补充计算并缓存
    - 返回 `{symbol: {cache_key: values}}` 格式的补充缓存
    - cache_key 格式如 `"ma_10"`, `"rsi_7"`, `"macd_dif_8_21_5"` 等
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 4.2 在 `_check_sell_conditions()` 方法末尾集成自定义平仓条件评估
    - 在现有四种卖出条件检测之后追加自定义条件评估
    - 当风控已触发卖出信号时跳过自定义条件
    - 自定义条件触发时生成 priority=5 的 `_SellSignal`，reason 为 `"EXIT_CONDITION"`
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [x] 4.3 在 `_run_backtest_strategy_driven()` 中传递 exit_conditions 配置和补充缓存
    - 在预计算阶段调用 `_precompute_exit_indicators()`
    - 将 `exit_indicator_cache` 传递给 `_check_sell_conditions()`
    - 在交易记录序列化中包含 `sell_reason` 字段
    - 确保所有 SELL 记录都包含非空 `sell_reason`（现有四种卖出也需补充）
    - _需求: 3.1, 3.4, 3.5, 4.2, 7.1, 7.2, 7.4_
  - [x] 4.4 编写无自定义条件时向后兼容属性测试
    - **Property 5: Backward compatibility without exit conditions**
    - **验证: 需求 3.5**
    - 使用 Hypothesis 生成 `exit_conditions=None` 的 `BacktestConfig`，验证不产生 `EXIT_CONDITION` 类型卖出信号
  - [x] 4.5 编写所有卖出记录包含平仓原因属性测试
    - **Property 6: All sell records contain sell_reason**
    - **验证: 需求 7.1, 7.4**
    - 验证所有 SELL 记录的 `sell_reason` 非空且属于合法集合
  - [x] 4.6 编写 BacktestEngine 集成单元测试
    - 在 `tests/services/test_exit_condition_integration.py` 中测试：
    - 自定义条件在风控之后执行
    - 风控已触发时跳过自定义条件
    - 卖出记录包含正确的 sell_reason
    - 无自定义条件时行为不变
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 7.1_

- [x] 5. 检查点 - 确保后端核心逻辑测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 6. 扩展回测 API
  - [x] 6.1 在 `app/api/v1/backtest.py` 中扩展请求模型和路由
    - 新增 `ExitConditionSchema` 和 `ExitConditionsSchema` Pydantic 模型，包含 `model_validator` 验证逻辑
    - 在 `BacktestRunRequest` 中新增可选字段 `exit_conditions: ExitConditionsSchema | None = None`
    - 在 `run_backtest` 路由中将 `exit_conditions` 传递给 Celery 任务
    - _需求: 5.1, 5.2, 5.3, 5.4_
  - [x] 6.2 在 `app/tasks/backtest.py` 中传递 exit_conditions 参数到 BacktestConfig
    - 将 API 传入的 exit_conditions JSON 反序列化为 `ExitConditionConfig`
    - 设置到 `BacktestConfig.exit_conditions` 字段
    - _需求: 5.4, 5.5_
  - [x] 6.3 编写 API 验证单元测试
    - 测试有效和无效的 exit_conditions 请求
    - 测试无效指标名称返回 422
    - 测试无效运算符返回 422
    - 测试 cross_up/cross_down 缺少 cross_target 返回 422
    - _需求: 5.1, 5.2, 5.3_

- [x] 7. 实现前端平仓条件配置面板
  - [x] 7.1 在 `frontend/src/stores/backtest.ts` 中扩展 form 状态
    - 新增 `ExitConditionForm` 接口定义
    - 在 form 中新增 `exitConditions` 字段，包含 `conditions` 数组和 `logic` 字段
    - 在 `startBacktest()` 中将 exitConditions 序列化并包含在请求中
    - _需求: 6.8_
  - [x] 7.2 在 `frontend/src/views/BacktestView.vue` 中新增自定义平仓条件配置面板
    - 新增可折叠的"自定义平仓条件"面板，默认折叠
    - 实现条件列表渲染和"添加条件"按钮
    - 每行条件包含：数据源频率下拉框、指标名称下拉框、比较运算符下拉框、阈值输入框或交叉目标下拉框
    - 选择 cross_up/cross_down 时将阈值输入框替换为交叉目标下拉框
    - 选择 ma 指标时显示均线周期参数输入框
    - 实现条件间逻辑运算符选择（AND/OR）
    - 实现条件行删除功能
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
  - [x] 7.3 在交易流水表格中新增"平仓原因"列
    - 在 `BacktestView.vue` 的交易流水表格中展示 `sell_reason` 字段
    - 对 sell_reason 值进行中文友好展示（如 STOP_LOSS → 固定止损）
    - _需求: 7.3_
  - [x] 7.4 编写前端 ExitConditionConfig JSON 序列化往返属性测试
    - 在 `frontend/src/stores/__tests__/backtest.property.test.ts` 中使用 fast-check 生成任意合法配置
    - 验证序列化为 JSON 后再解析回来与原对象一致
    - _需求: 1.6, 1.7_
  - [x] 7.5 编写前端组件单元测试
    - 测试条件面板的展开/折叠
    - 测试添加/删除条件行
    - 测试运算符切换时输入框变化
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.7_

- [x] 8. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

---

## 增量任务：扩展 freq 字段支持多种分钟K线频率

以下任务覆盖将 `freq` 从 `"daily" | "minute"` 扩展为 `"daily" | "1min" | "5min" | "15min" | "30min" | "60min"` 所需的增量变更，并确保旧版 `"minute"` 值的向后兼容。

- [x] 9. 后端数据模型与评估器 freq 扩展
  - [x] 9.1 在 `app/core/schemas.py` 中新增 `VALID_FREQS` 常量并更新 `ExitCondition.from_dict()`
    - 新增 `VALID_FREQS = {"daily", "1min", "5min", "15min", "30min", "60min"}` 常量
    - 在 `ExitCondition.from_dict()` 中添加 `"minute"` → `"1min"` 的向后兼容映射逻辑
    - 更新 `ExitCondition` 的 `freq` 字段注释，说明支持的6种频率值
    - _需求: 1.1, 8.3_

  - [x] 9.2 在 `app/services/exit_condition_evaluator.py` 中新增 `_resolve_freq()` 方法和按频率分组的缓存支持
    - 新增模块级常量 `VALID_FREQS` 和 `_FREQ_MIGRATION = {"minute": "1min"}`
    - 新增 `_resolve_freq(freq: str) -> str` 方法，将 `"minute"` 映射为 `"1min"`
    - 修改 `evaluate()` 方法签名：`exit_indicator_cache` 类型从 `dict[str, list[float]]` 改为 `dict[str, dict[str, list[float]]]`（按频率分组）
    - 在 `evaluate()` 中对每条条件调用 `_resolve_freq()` 标准化频率，根据频率从 `exit_indicator_cache[freq]` 获取对应缓存
    - 分钟K线缓存不可用时回退到 `"daily"` 频率缓存，记录 INFO 日志
    - _需求: 2.7, 2.8, 8.1_

  - [x] 9.3 更新 `app/services/backtest_engine.py` 中 `_precompute_exit_indicators()` 支持按频率分组
    - 修改函数签名接收 `kline_data: dict[str, dict[str, list[KlineBar]]]`（按频率和股票代码组织）
    - 遍历 `exit_config.conditions` 收集所有 `(freq, indicator, params)` 组合，将 `"minute"` 映射为 `"1min"`
    - 对每个频率加载对应K线数据并计算所需指标，日K线优先从 `existing_cache` 复用
    - 返回 `{symbol: {freq: {cache_key: values}}}` 格式的按频率分组补充缓存
    - 更新 `_check_sell_conditions()` 和 `_run_backtest_strategy_driven()` 中传递按频率分组的缓存
    - _需求: 4.1, 4.2, 4.3_

- [x] 10. 后端 API freq 验证扩展
  - [x] 10.1 在 `app/api/v1/backtest.py` 的 `ExitConditionSchema` 中新增 freq 验证
    - 导入 `VALID_FREQS` 常量（从 `app/core/schemas.py`）
    - 在 `validate_condition` 中添加 `"minute"` → `"1min"` 映射逻辑
    - 在 `validate_condition` 中添加 `freq not in VALID_FREQS` 的验证，返回 422 错误信息：`"无效的数据源频率: {freq}，支持: daily, 1min, 5min, 15min, 30min, 60min"`
    - _需求: 5.3, 5.4, 8.2_

  - [x] 10.2 编写 API freq 验证单元测试
    - 在 `tests/api/` 中测试 `ExitConditionSchema` 对6种合法频率值的接受
    - 测试 `"minute"` 被接受并映射为 `"1min"`
    - 测试无效频率值（如 `"hourly"`、`"2min"`）返回 422
    - _需求: 5.3, 5.4, 8.2_

- [x] 11. 检查点 - 确保后端 freq 扩展测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 12. 前端 freq 扩展
  - [x] 12.1 更新 `frontend/src/stores/backtest.ts` 中 `ExitConditionForm.freq` 类型
    - 将 `freq` 类型从 `'daily' | 'minute'` 改为 `'daily' | '1min' | '5min' | '15min' | '30min' | '60min'`
    - 新增 `FREQ_OPTIONS` 常量数组，包含6种频率的 `{ value, label }` 映射（`daily` → `日K`、`1min` → `1分钟`、`5min` → `5分钟`、`15min` → `15分钟`、`30min` → `30分钟`、`60min` → `60分钟`）
    - _需求: 6.3, 6.8_

  - [x] 12.2 更新 `frontend/src/views/BacktestView.vue` 中频率下拉框
    - 将 `freqOptions` 替换为从 store 导入的 `FREQ_OPTIONS` 常量（或直接更新为6种选项）
    - 确保新增条件时默认 `freq` 为 `'daily'`
    - _需求: 6.3_

- [x] 13. 更新属性测试覆盖新 freq 值
  - [x] 13.1 更新后端 Property 1 的 freq 生成策略
    - 在 `tests/properties/test_exit_condition_properties.py` 中将 `_freq_strategy` 从 `st.sampled_from(["daily", "minute"])` 改为 `st.sampled_from(["daily", "1min", "5min", "15min", "30min", "60min"])`
    - 确保 round-trip 测试覆盖所有6种新频率值
    - _需求: 1.1, 1.7_

  - [x] 13.2 新增后端 Property 7：旧版 "minute" 频率向后兼容映射属性测试
    - **Property 7: Legacy minute freq backward compatibility mapping**
    - **验证: 需求 8.1, 8.3**
    - 在 `tests/properties/test_exit_condition_properties.py` 中新增测试
    - 使用 Hypothesis 生成 `freq="minute"` 的 `ExitCondition` 字典，验证 `from_dict()` 后 `freq` 等于 `"1min"`
    - 验证包含 `freq="minute"` 条件的 `ExitConditionConfig` 经 `from_dict()` → `to_dict()` 后对应条件的 `freq` 为 `"1min"`

  - [x] 13.3 更新前端属性测试的 freq 生成器
    - 在 `frontend/src/stores/__tests__/backtest.property.test.ts` 中将 `freqArb` 从 `fc.constantFrom('daily', 'minute')` 改为 `fc.constantFrom('daily', '1min', '5min', '15min', '30min', '60min')`
    - 更新 `ExitConditionForm` 接口的 `freq` 类型定义
    - _需求: 1.1, 1.7_

  - [x] 13.4 更新后端评估器相关单元测试
    - 在 `tests/services/test_exit_condition_evaluator.py` 中新增测试用例：验证不同分钟频率条件使用对应频率缓存
    - 测试 `_resolve_freq("minute")` 返回 `"1min"`
    - 测试分钟K线缓存不可用时回退到日K线缓存
    - _需求: 2.7, 2.8, 8.1_

- [x] 14. 最终检查点 - 确保所有 freq 扩展测试通过
  - 确保所有测试通过，如有问题请向用户确认。

---

## 增量任务：平仓条件模版管理功能

以下任务覆盖需求 9（后端模版存储与 API）和需求 10（前端模版管理）所需的增量变更，构建在已完成的任务 1-14 之上。

- [x] 15. 后端模版 ORM 模型与数据库迁移
  - [x] 15.1 在 `app/models/backtest.py` 中新增 `ExitConditionTemplate` ORM 模型
    - 遵循 `StrategyTemplate`（`app/models/strategy.py`）的设计模式：`PGBase` 基类、UUID 主键、JSONB 配置字段、时间戳字段
    - 字段：`id`（UUID 主键，`gen_random_uuid()`）、`user_id`（UUID，非空）、`name`（String(100)，非空）、`description`（String(500)，可空）、`exit_conditions`（JSONB，非空，存储 `ExitConditionConfig.to_dict()` 结果）、`created_at`（TIMESTAMPTZ）、`updated_at`（TIMESTAMPTZ）
    - _需求: 9.1, 9.2, 9.9_
  - [x] 15.2 创建 Alembic 迁移文件 `alembic/versions/004_create_exit_condition_template.py`
    - 创建 `exit_condition_template` 表
    - 添加 `idx_exit_condition_template_user_id` 索引（按 `user_id` 查询）
    - 添加 `idx_exit_condition_template_user_name` 唯一索引（`user_id, name` 组合，保证同一用户下名称唯一）
    - _需求: 9.1, 9.5_

- [x] 16. 后端模版 CRUD API
  - [x] 16.1 在 `app/api/v1/backtest.py` 中新增模版 Pydantic 请求/响应模型
    - 新增 `ExitTemplateCreateRequest`：`name`（str，1-100 字符，必填）、`description`（str，最长 500 字符，可选）、`exit_conditions`（`ExitConditionsSchema`，必填，复用现有验证逻辑）
    - 新增 `ExitTemplateUpdateRequest`：`name`（str，1-100 字符，可选）、`description`（str，最长 500 字符，可选）、`exit_conditions`（`ExitConditionsSchema`，可选）
    - 新增 `ExitTemplateResponse`：`id`、`name`、`description`、`exit_conditions`、`created_at`、`updated_at`
    - _需求: 9.3, 9.4_
  - [x] 16.2 实现 5 个 REST 端点
    - `POST /api/v1/backtest/exit-templates`：创建模版，含名称唯一性校验（409）和数量上限校验（50 个，409）
    - `GET /api/v1/backtest/exit-templates`：列出当前用户所有模版，按 `updated_at` 降序
    - `GET /api/v1/backtest/exit-templates/{id}`：获取指定模版，不存在返回 404
    - `PUT /api/v1/backtest/exit-templates/{id}`：更新模版，含所有权校验（非本人返回 403）、不存在返回 404；若更新 name 需校验唯一性（409）
    - `DELETE /api/v1/backtest/exit-templates/{id}`：删除模版，含所有权校验（403）、不存在返回 404
    - 新增辅助函数 `_exit_template_to_dict()` 和 `_get_template_or_404()`
    - _需求: 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_
  - [x] 16.3 编写模版 CRUD API 单元测试
    - 在 `tests/api/test_exit_template_api.py` 中测试：
    - 创建模版：有效数据返回 201、名称重复返回 409、数量超限返回 409、无效 exit_conditions 返回 422、名称为空或超长返回 422
    - 列出模版：返回当前用户所有模版
    - 获取模版：存在的 ID 返回 200、不存在的 ID 返回 404
    - 更新模版：本人模版返回 200、非本人模版返回 403、不存在的 ID 返回 404
    - 删除模版：本人模版返回 200、非本人模版返回 403、不存在的 ID 返回 404
    - _需求: 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

- [x] 17. 检查点 - 确保后端模版功能测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 18. 前端模版管理功能
  - [x] 18.1 在 `frontend/src/stores/backtest.ts` 中扩展模版状态和 CRUD 方法
    - 新增 `ExitTemplate` 接口定义（`id`、`name`、`description`、`exit_conditions`、`created_at`、`updated_at`）
    - 新增状态：`exitTemplates`（模版列表）、`selectedTemplateId`（当前选中模版 ID）、`templateLoading`（加载状态）
    - 实现 `fetchExitTemplates()`：调用 `GET /backtest/exit-templates` 获取模版列表
    - 实现 `createExitTemplate(name, description?)`：调用 `POST /backtest/exit-templates`，将当前 `exitConditions` 序列化为请求体
    - 实现 `loadExitTemplate(templateId)`：调用 `GET /backtest/exit-templates/{id}`，将模版配置加载到当前 `exitConditions`（snake_case → camelCase 转换）
    - 实现 `updateExitTemplate(templateId, data)`：调用 `PUT /backtest/exit-templates/{id}`
    - 实现 `deleteExitTemplate(templateId)`：调用 `DELETE /backtest/exit-templates/{id}`，删除后刷新列表
    - 在 store 返回值中导出新增状态和方法
    - _需求: 10.3, 10.4, 10.7, 10.8, 10.9_
  - [x] 18.2 在 `frontend/src/views/BacktestView.vue` 中新增模版选择下拉框
    - 在平仓条件面板顶部新增模版选择下拉框，列出当前用户所有已保存模版（按 `updated_at` 降序）
    - 选择模版后调用 `loadExitTemplate()` 加载配置，替换当前 `exitConditions`
    - 面板展开时自动调用 `fetchExitTemplates()` 加载模版列表
    - _需求: 10.6, 10.7_
  - [x] 18.3 在 `frontend/src/views/BacktestView.vue` 中新增"保存为模版"按钮和对话框
    - 在平仓条件面板中新增"保存为模版"按钮，当 `exitConditions.conditions` 为空时禁用
    - 点击后弹出对话框，包含名称输入框（必填）和描述输入框（可选）
    - 确认保存时调用 `createExitTemplate()`，成功后显示提示并刷新模版列表
    - 保存失败时显示对应错误提示（名称重复 → "模版名称已存在"，数量超限 → "模版数量已达上限"）
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5, 10.10_
  - [x] 18.4 在 `frontend/src/views/BacktestView.vue` 中新增模版管理功能（重命名、删除）
    - 在模版选择下拉框旁提供管理入口，支持重命名（调用 `updateExitTemplate()`）和删除（弹出确认对话框后调用 `deleteExitTemplate()`）
    - _需求: 10.8, 10.9_
  - [x] 18.5 编写前端模版管理单元测试
    - 测试"保存为模版"按钮状态（有条件时启用，无条件时禁用）
    - 测试保存对话框弹出与提交
    - 测试模版选择下拉框加载与选择
    - 测试模版加载后替换当前配置
    - 测试模版删除确认对话框
    - _需求: 10.1, 10.2, 10.6, 10.7, 10.9, 10.10_

- [x] 19. 模版属性测试
  - [x] 19.1 编写模版 exit_conditions 往返一致性属性测试
    - **Property 8: Template exit_conditions round-trip consistency**
    - **验证: 需求 9.4, 9.9, 9.10**
    - 在 `tests/properties/test_exit_condition_properties.py` 中新增测试
    - 使用 Hypothesis 生成任意有效的 `ExitConditionConfig`，验证 `to_dict()` 序列化后经 `ExitConditionConfig.from_dict()` 反序列化所得对象与原对象等价（模拟 JSONB 存取往返）
  - [x] 19.2 编写同一用户下模版名称唯一性属性测试
    - **Property 9: Template name uniqueness per user**
    - **验证: 需求 9.5**
    - 在 `tests/properties/test_exit_condition_properties.py` 中新增测试
    - 使用 Hypothesis 生成任意有效的模版名称（非空，长度 ≤ 100），验证同一用户创建两个同名模版时第二次返回 409，且数据库中该用户下该名称的模版数量始终为 1

- [x] 20. 最终检查点 - 确保所有模版功能测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证设计文档中定义的正确性属性
- 后端属性测试使用 Hypothesis（`tests/properties/`），前端使用 fast-check
- 任务 9-14 为 freq 扩展增量任务，构建在已完成的任务 1-8 之上
- 任务 15-20 为模版管理增量任务，构建在已完成的任务 1-14 之上
