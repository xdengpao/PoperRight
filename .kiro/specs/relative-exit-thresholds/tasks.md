# 实现计划：平仓条件相对值阈值支持

## 概述

基于已确认的需求和设计文档，将相对值阈值功能分解为增量式编码任务。后端使用 Python（FastAPI + dataclass），前端使用 TypeScript（Vue 3 + Pinia）。每个任务构建在前一个任务之上，从数据模型扩展开始，经过核心解析引擎、评估器集成、回测引擎适配、API 验证，到前端 UI 扩展和系统内置模版，最终完成端到端集成。

## 任务列表

- [x] 1. 扩展数据模型（ExitCondition、HoldingContext、IndicatorCache）
  - [x] 1.1 在 `app/core/schemas.py` 中扩展 `ExitCondition` dataclass，新增 `threshold_mode`、`base_field`、`factor` 字段
    - 新增 `threshold_mode: str = "absolute"` 字段（取值 `"absolute"` 或 `"relative"`）
    - 新增 `base_field: str | None = None` 字段（相对值基准字段）
    - 新增 `factor: float | None = None` 字段（乘数因子）
    - 新增 `VALID_BASE_FIELDS` 常量集合，包含 12 种合法 base_field 取值
    - 更新 `to_dict()` 方法，序列化时包含 `threshold_mode`、`base_field`、`factor` 字段
    - 更新 `from_dict()` 方法，反序列化时还原新字段，`threshold_mode` 缺失时默认为 `"absolute"`
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8_

  - [x] 1.2 在 `app/core/schemas.py` 中新增 `HoldingContext` dataclass
    - 定义 `entry_price: float`（买入价）、`highest_price: float`（持仓最高收盘价）、`lowest_price: float`（持仓最低收盘价）、`entry_bar_index: int`（买入时 bar 索引）
    - _需求: 2.1, 2.4_

  - [x] 1.3 在 `app/services/backtest_engine.py` 的 `IndicatorCache` 中新增 `opens` 字段
    - 新增 `opens: list[float]` 字段，存储开盘价序列
    - 更新 `_precompute_indicators()` 函数，在构建 IndicatorCache 时填充 `opens`：`opens = [float(b.open) for b in bars]`
    - _需求: 3.9, 3.10_

  - [x] 1.4 编写 ExitCondition 序列化往返属性测试（Property 1）
    - **Property 1: ExitCondition round-trip serialization with relative threshold fields**
    - **验证: 需求 1.6, 1.7, 1.9**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成任意合法的 ExitCondition（包含 `threshold_mode="absolute"` 和 `"relative"` 两种模式），验证 `ExitCondition.from_dict(condition.to_dict())` 与原对象等价，新增字段在往返后完全保留

  - [x] 1.5 编写缺失 threshold_mode 向后兼容属性测试（Property 2）
    - **Property 2: Backward compatibility for missing threshold_mode**
    - **验证: 需求 1.8, 7.4, 8.3**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成不包含 `threshold_mode` 字段的旧版 ExitCondition 字典，验证 `from_dict()` 后 `threshold_mode` 为 `"absolute"`、`base_field` 为 `None`、`factor` 为 `None`

  - [x] 1.6 编写数据模型单元测试
    - 在 `tests/services/test_threshold_resolver.py` 中测试 ExitCondition 新字段的构造、默认值
    - 测试 HoldingContext 的构造和字段访问
    - 测试 IndicatorCache 新增 `opens` 字段
    - _需求: 1.1, 1.2, 1.3, 1.4, 2.4_

- [x] 2. 实现 ThresholdResolver 模块
  - [x] 2.1 创建 `app/services/threshold_resolver.py`，实现 `resolve_threshold()` 纯函数
    - 实现 `resolve_threshold(condition, holding_context, indicator_cache, bar_index) -> float | None`
    - `threshold_mode="absolute"` 时直接返回 `condition.threshold`
    - `threshold_mode="relative"` 时根据 `base_field` 从 HoldingContext 或 IndicatorCache 获取基准值，乘以 `factor` 返回
    - 支持 12 种 `base_field`：`entry_price`、`highest_price`、`lowest_price`、`prev_close`、`prev_high`、`prev_low`、`today_open`、`prev_bar_open`、`prev_bar_high`、`prev_bar_low`、`prev_bar_close`、`ma_volume`
    - `ma_volume` 从 IndicatorCache.volumes 计算过去 N 日均量（N 由 `params.ma_volume_period` 指定，默认 5）
    - 错误处理：无效 `base_field` 返回 None + ERROR 日志；基准值为 None/NaN 返回 None + WARNING 日志；`factor` 为 None 或非正数返回 None + WARNING 日志
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16, 3.17_

  - [x] 2.2 编写绝对值模式向后兼容属性测试（Property 3）
    - **Property 3: Absolute mode backward compatibility**
    - **验证: 需求 1.2, 3.2, 4.4**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成任意 `threshold_mode="absolute"` 的 ExitCondition 和任意 `holding_context`（包括 None），验证 ThresholdResolver 直接返回 `condition.threshold`

  - [x] 2.3 编写 HoldingContext 基准字段解析属性测试（Property 4）
    - **Property 4: HoldingContext base field resolution**
    - **验证: 需求 3.3, 3.4, 3.5**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成任意合法 HoldingContext 和正数 factor，当 `base_field` 为 `entry_price`/`highest_price`/`lowest_price` 时，验证返回值等于 `getattr(ctx, base_field) * factor`

  - [x] 2.4 编写 IndicatorCache 基准字段解析属性测试（Property 5）
    - **Property 5: IndicatorCache base field resolution**
    - **验证: 需求 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成合法 IndicatorCache（序列长度 ≥ 2）、合法 bar_index（≥ 1）和正数 factor，验证 `prev_close`/`prev_high`/`prev_low`/`today_open`/`prev_bar_open`/`prev_bar_high`/`prev_bar_low`/`prev_bar_close` 返回正确索引处的值乘以 factor

  - [x] 2.5 编写 ma_volume 基准字段解析属性测试（Property 6）
    - **Property 6: ma_volume base field resolution**
    - **验证: 需求 3.14**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成合法 IndicatorCache（volumes 长度 ≥ N）、合法 bar_index（≥ N-1）、正整数 N 和正数 factor，验证返回 `mean(volumes[bar_index-N+1:bar_index+1]) × factor`

  - [x] 2.6 编写 ThresholdResolver 单元测试
    - 在 `tests/services/test_threshold_resolver.py` 中测试各 base_field 的具体计算
    - 测试边界条件：bar_index=0 时 prev_close 返回 None、NaN 基准值、无效 base_field、factor=0、factor=None
    - 测试 ma_volume 数据不足时返回 None
    - 测试 holding_context=None 且 base_field 需要 HoldingContext 时返回 None
    - _需求: 3.1 ~ 3.17_

- [x] 3. 检查点 - 确保数据模型和 ThresholdResolver 测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. ExitConditionEvaluator 集成 ThresholdResolver
  - [x] 4.1 修改 `app/services/exit_condition_evaluator.py` 的 `evaluate()` 方法，新增可选 `holding_context` 参数
    - 在 `evaluate()` 签名中新增 `holding_context: HoldingContext | None = None`
    - 将 `holding_context` 传递给 `_evaluate_single()` 和 `_evaluate_single_minute_scanning()`
    - _需求: 4.1_

  - [x] 4.2 修改 `_evaluate_single()` 方法，在数值比较前调用 ThresholdResolver
    - 导入并调用 `resolve_threshold(condition, holding_context, indicator_cache, bar_index)`
    - 使用解析后的阈值替代 `condition.threshold` 进行数值比较
    - ThresholdResolver 返回 None 时跳过该条件并记录 WARNING 日志
    - `threshold_mode="absolute"` 且 `holding_context=None` 时保持现有行为
    - 构建触发原因字符串：relative 模式格式为 `"{INDICATOR} {operator} {resolved_threshold}（{base_field}×{factor}）"`
    - _需求: 4.2, 4.3, 4.4, 4.5_

  - [x] 4.3 修改 `_evaluate_single_minute_scanning()` 方法，同样集成 ThresholdResolver
    - 在分钟频率日内扫描的数值比较中调用 ThresholdResolver
    - 使用解析后的阈值替代 `condition.threshold`
    - 触发原因格式与日频一致
    - _需求: 4.2, 4.5_

  - [x] 4.4 确保交叉条件（cross_up/cross_down）不受相对值阈值影响
    - 验证 `_evaluate_cross()` 和交叉扫描逻辑不调用 ThresholdResolver
    - _需求: 4.6_

  - [x] 4.5 编写评估器使用解析后阈值属性测试（Property 7）
    - **Property 7: Evaluator uses resolved threshold**
    - **验证: 需求 4.2**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成 `threshold_mode="relative"` 的数值比较条件、合法 HoldingContext 和 IndicatorCache，验证评估结果等价于使用 ThresholdResolver 解析后的阈值进行 Python 原生比较

  - [x] 4.6 编写交叉条件不受影响属性测试（Property 8）
    - **Property 8: Cross conditions unaffected by relative threshold**
    - **验证: 需求 4.6**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成 cross_up/cross_down 条件，无论 `threshold_mode` 设为 `"absolute"` 还是 `"relative"`，验证评估结果完全相同

  - [x] 4.7 编写触发原因格式属性测试（Property 9）
    - **Property 9: Trigger reason format includes resolution info**
    - **验证: 需求 4.5, 9.1**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成被触发的 `threshold_mode="relative"` 条件，验证触发原因字符串包含解析后的实际阈值和 `（{base_field}×{factor}）` 格式信息

  - [x] 4.8 编写评估器集成单元测试
    - 在 `tests/services/test_exit_condition_evaluator.py` 中新增测试：
    - 测试 relative 条件评估（如 close < entry_price × 0.95）
    - 测试 holding_context 传递和使用
    - 测试 ThresholdResolver 返回 None 时跳过条件
    - 测试 reason 格式包含解析信息
    - 测试 absolute 模式在有/无 holding_context 时行为不变
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 5. 检查点 - 确保评估器集成测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 6. BacktestEngine 持仓上下文传递
  - [x] 6.1 在 `app/services/backtest_engine.py` 的 `_BacktestPosition` 中新增 `lowest_close` 字段
    - 新增 `lowest_close: Decimal = Decimal("999999999")` 字段
    - 在创建 `_BacktestPosition` 时初始化 `lowest_close` 为买入价（与 `highest_close` 对称）
    - _需求: 2.2_

  - [x] 6.2 在 `_check_sell_conditions()` 中更新 `lowest_close` 并构建 HoldingContext
    - 在更新 `highest_close` 的逻辑附近，新增 `lowest_close` 更新逻辑：`if close < position.lowest_close: position.lowest_close = close`
    - 构建 `HoldingContext(entry_price=float(position.cost_price), highest_price=float(position.highest_close), lowest_price=float(position.lowest_close), entry_bar_index=position.buy_trade_day_index)`
    - 将 `holding_context` 传递给 `evaluator.evaluate()` 调用
    - _需求: 2.1, 2.2, 2.3_

  - [x] 6.3 编写持仓上下文极值跟踪不变量属性测试（Property 10）
    - **Property 10: Position extrema tracking invariant**
    - **验证: 需求 2.2**
    - 在 `tests/properties/test_relative_threshold_properties.py` 中使用 Hypothesis 生成任意收盘价序列，模拟 BacktestEngine 的每日更新逻辑，验证 `highest_close` 始终等于序列最大值、`lowest_close` 始终等于序列最小值

  - [x] 6.4 编写 BacktestEngine 集成单元测试
    - 在 `tests/services/test_exit_condition_integration.py` 中新增测试：
    - 测试 `lowest_close` 正确跟踪持仓期间最低收盘价
    - 测试 HoldingContext 正确构建并传递给 evaluator
    - 测试相对值条件在回测中正确触发（如 close < entry_price × 0.95 触发卖出）
    - 测试交易流水 sell_reason 包含相对值解析信息
    - _需求: 2.1, 2.2, 9.1_

- [x] 7. 检查点 - 确保后端核心逻辑测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 8. API 验证扩展
  - [x] 8.1 在 `app/api/v1/backtest.py` 的 `ExitConditionSchema` 中新增字段和验证
    - 新增 `threshold_mode: str = "absolute"` 字段
    - 新增 `base_field: str | None = None` 字段
    - 新增 `factor: float | None = None` 字段
    - 在 `validate_condition` 中新增相对值模式验证：`threshold_mode="relative"` 时验证 `base_field` 非空且属于 `VALID_BASE_FIELDS`，`factor` 非空且为正数
    - `threshold_mode="relative"` 时允许 `threshold` 为 None
    - `threshold_mode="absolute"` 时保持现有验证逻辑
    - 无效 `threshold_mode` 返回 422
    - 缺失 `threshold_mode` 时默认为 `"absolute"`（向后兼容）
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 8.2 编写 API 验证单元测试
    - 在 `tests/api/test_backtest_api.py` 中新增测试：
    - 测试 `threshold_mode="relative"` + 有效 `base_field` + 正数 `factor` 通过验证
    - 测试 `threshold_mode="relative"` 缺少 `base_field` 返回 422
    - 测试 `threshold_mode="relative"` 无效 `base_field` 返回 422
    - 测试 `threshold_mode="relative"` 缺少 `factor` 或 `factor <= 0` 返回 422
    - 测试 `threshold_mode="relative"` 允许 `threshold=None`
    - 测试 `threshold_mode="absolute"` 保持现有验证行为
    - 测试缺失 `threshold_mode` 字段默认为 `"absolute"`
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 9. 检查点 - 确保 API 验证测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 10. 前端状态与序列化扩展
  - [x] 10.1 在 `frontend/src/stores/backtest.ts` 中扩展 `ExitConditionForm` 接口和序列化逻辑
    - 在 `ExitConditionForm` 接口中新增 `thresholdMode: 'absolute' | 'relative'`（默认 `'absolute'`）、`baseField: string | null`、`factor: number | null`
    - 新增 `BASE_FIELD_OPTIONS` 常量数组，按类别分组（持仓相关、前一日行情、当日行情、上一根K线、成交量）
    - 更新 `startBacktest()` 中序列化逻辑：`thresholdMode` → `threshold_mode`、`baseField` → `base_field`（camelCase → snake_case）
    - 更新 `loadExitTemplate()` 中反序列化逻辑：`threshold_mode` → `thresholdMode`、`base_field` → `baseField`（snake_case → camelCase），缺失时默认 `'absolute'`
    - 更新 `createExitTemplate()` 中序列化逻辑，包含新字段
    - _需求: 7.1, 7.2, 7.3, 7.4_

  - [x] 10.2 编写前端 ExitConditionForm 序列化往返属性测试（Property 11）
    - **Property 11: Frontend ExitConditionForm round-trip serialization**
    - **验证: 需求 7.2, 7.3, 7.4, 7.5**
    - 在 `frontend/src/stores/__tests__/backtest.property.test.ts` 中使用 fast-check 生成任意合法 ExitConditionForm（包含 `thresholdMode`、`baseField`、`factor`），验证序列化为 snake_case JSON 后再反序列化回 camelCase 与原对象等价，缺失 `threshold_mode` 的旧版数据默认为 `'absolute'`

  - [x] 10.3 编写前端状态单元测试
    - 在 `frontend/src/stores/__tests__/backtest.test.ts` 中测试：
    - 测试 `ExitConditionForm` 新字段默认值
    - 测试序列化/反序列化新字段的正确映射
    - 测试加载不含 `threshold_mode` 的旧版模版时默认为 `'absolute'`
    - _需求: 7.1, 7.2, 7.3, 7.4_

- [x] 11. 前端 UI 配置面板扩展
  - [x] 11.1 在 `frontend/src/views/BacktestView.vue` 中扩展条件行 UI
    - 当运算符为数值比较（非 cross）时，在阈值输入框前显示阈值模式切换控件（"绝对值"/"相对值"两个选项）
    - 绝对值模式：显示现有阈值数值输入框
    - 相对值模式：隐藏阈值输入框，显示基准字段下拉框（按类别分组）和乘数因子输入框（步长 0.01，默认 1.0）
    - 选择 `ma_volume` 基准字段时额外显示均量周期输入框（默认 5，最小 1）
    - 切换模式时清空对立字段（切换到绝对值清空 `baseField`/`factor`，切换到相对值清空 `threshold`）
    - 交叉运算符时隐藏阈值模式切换控件
    - 新增条件时默认 `thresholdMode` 为 `'absolute'`
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 11.2 更新交易流水 `formatSellReason()` 函数，正确解析包含相对值信息的平仓原因
    - 确保 `EXIT_CONDITION: CLOSE < 9.5000（entry_price×0.95）` 格式的 sell_reason 正确展示
    - _需求: 9.2_

  - [x] 11.3 编写前端模式切换清空对立字段属性测试（Property 12）
    - **Property 12: Mode switch clears opposing fields**
    - **验证: 需求 6.7**
    - 在 `frontend/src/stores/__tests__/backtest.property.test.ts` 中使用 fast-check 生成任意 ExitConditionForm 状态，验证切换 `thresholdMode` 时对立字段被正确清空

  - [x] 11.4 编写前端 UI 单元测试
    - 在 `frontend/src/views/__tests__/BacktestView.test.ts` 中新增测试：
    - 测试数值比较运算符时显示阈值模式切换控件
    - 测试交叉运算符时隐藏阈值模式切换控件
    - 测试切换到相对值模式时显示基准字段下拉框和乘数因子输入框
    - 测试选择 `ma_volume` 时显示均量周期输入框
    - 测试模式切换时清空对立字段
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 12. 检查点 - 确保前端扩展测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 13. 系统内置模版新增
  - [x] 13.1 创建 Alembic 数据迁移文件，seed 2 个包含相对值阈值条件的系统内置模版
    - 模版 1：**买入价比例止损**（收盘价 < 买入价 × 0.95），`threshold_mode="relative"`, `base_field="entry_price"`, `factor=0.95`
    - 模版 2：**回撤止损**（收盘价 < 最高价 × 0.90），`threshold_mode="relative"`, `base_field="highest_price"`, `factor=0.90`
    - 使用固定系统用户 UUID `00000000-0000-0000-0000-000000000000`，`is_system=True`
    - 使用 `ON CONFLICT DO NOTHING` 保证幂等性
    - _需求: 8.4_

  - [x] 13.2 编写系统内置模版单元测试
    - 在 `tests/api/test_exit_template_api.py` 中新增测试：
    - 验证新增的 2 个相对值模版存在且 `is_system=True`
    - 验证模版的 `exit_conditions` 包含 `threshold_mode="relative"` 条件
    - 验证模版可通过 `ExitConditionConfig.from_dict()` 正确反序列化
    - _需求: 8.1, 8.2, 8.4_

  - [x] 13.3 验证模版保存/加载往返一致性
    - 测试包含相对值条件的模版创建 API 正确保存 `exit_conditions` 到 JSONB
    - 测试模版加载 API 正确还原包含相对值条件的 `exit_conditions`
    - 测试加载不含 `threshold_mode` 的旧版模版时默认为 `"absolute"`
    - _需求: 8.1, 8.2, 8.3_

- [x] 14. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证设计文档中定义的 12 个正确性属性
- 后端属性测试使用 Hypothesis（`tests/properties/test_relative_threshold_properties.py`），前端使用 fast-check（`frontend/src/stores/__tests__/backtest.property.test.ts`）
- 检查点确保增量验证，每个阶段完成后运行测试
- 任务构建在已完成的 backtest-exit-conditions spec（任务 1-29）之上
