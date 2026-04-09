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
  - [ ]* 1.4 编写 `ExitConditionConfig` 序列化往返属性测试
    - **Property 1: ExitConditionConfig round-trip serialization**
    - **验证: 需求 1.6, 1.7**
    - 在 `tests/properties/test_exit_condition_properties.py` 中使用 Hypothesis 生成任意合法的 `ExitConditionConfig`，验证 `from_dict(config.to_dict())` 与原对象等价
  - [ ]* 1.5 编写数据模型单元测试
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
  - [ ]* 2.2 编写逻辑运算符评估正确性属性测试
    - **Property 2: Logic operator evaluation correctness**
    - **验证: 需求 2.2, 2.3**
    - 在 `tests/properties/test_exit_condition_properties.py` 中使用 Hypothesis 生成任意逻辑运算符和布尔值列表，验证 AND 等于 `all()`、OR 等于 `any()`
  - [ ]* 2.3 编写数值比较运算符正确性属性测试
    - **Property 3: Numeric comparison operator correctness**
    - **验证: 需求 2.4**
    - 使用 Hypothesis 生成任意浮点数和合法数值运算符，验证评估结果与 Python 原生比较一致
  - [ ]* 2.4 编写交叉检测正确性属性测试
    - **Property 4: Cross detection correctness**
    - **验证: 需求 2.5, 2.6**
    - 使用 Hypothesis 生成任意两组连续两日浮点数值对，验证 cross_up 和 cross_down 的判定逻辑
  - [ ]* 2.5 编写 ExitConditionEvaluator 单元测试
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
  - [ ]* 4.4 编写无自定义条件时向后兼容属性测试
    - **Property 5: Backward compatibility without exit conditions**
    - **验证: 需求 3.5**
    - 使用 Hypothesis 生成 `exit_conditions=None` 的 `BacktestConfig`，验证不产生 `EXIT_CONDITION` 类型卖出信号
  - [ ]* 4.5 编写所有卖出记录包含平仓原因属性测试
    - **Property 6: All sell records contain sell_reason**
    - **验证: 需求 7.1, 7.4**
    - 验证所有 SELL 记录的 `sell_reason` 非空且属于合法集合
  - [ ]* 4.6 编写 BacktestEngine 集成单元测试
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
  - [ ]* 6.3 编写 API 验证单元测试
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
  - [ ]* 7.4 编写前端 ExitConditionConfig JSON 序列化往返属性测试
    - 在 `frontend/src/stores/__tests__/backtest.property.test.ts` 中使用 fast-check 生成任意合法配置
    - 验证序列化为 JSON 后再解析回来与原对象一致
    - _需求: 1.6, 1.7_
  - [ ]* 7.5 编写前端组件单元测试
    - 测试条件面板的展开/折叠
    - 测试添加/删除条件行
    - 测试运算符切换时输入框变化
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.7_

- [x] 8. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证设计文档中定义的正确性属性
- 后端属性测试使用 Hypothesis（`tests/properties/`），前端使用 fast-check
