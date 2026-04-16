# 需求文档：平仓条件相对值阈值支持

## 简介

当前 `ExitCondition` 的 `threshold` 字段仅支持绝对值（固定 float），在实际量化交易中，许多平仓条件的阈值需要根据持仓上下文动态计算。例如"收盘价跌破买入价的 95%"无法在配置时确定一个固定价格值，因为不同股票的买入价不同。本功能引入"相对值阈值"机制，让阈值在回测运行时根据持仓上下文（买入价、最高价、均量等）动态解析为具体数值，从而支持止损比例、放量倍数、回撤幅度等常见量化策略场景。

## 术语表

- **Threshold_Resolver**：阈值解析器，负责在回测运行时将相对值阈值配置解析为具体的浮点数值
- **ExitCondition**：单条自定义平仓条件数据类，包含指标、运算符、阈值等字段
- **ExitConditionConfig**：自定义平仓条件配置，包含条件列表和逻辑运算符
- **ExitConditionEvaluator**：平仓条件评估器，负责在每个交易日对持仓标的评估平仓条件
- **Threshold_Mode**：阈值模式枚举，区分绝对值（`absolute`）和相对值（`relative`）两种模式
- **Base_Field**：基准字段，相对值阈值的计算基准来源，如 `entry_price`（买入价）、`highest_price`（持仓期间最高价）、`prev_close`（前一日收盘价）、`prev_bar_close`（上一根K线收盘价）、`ma_volume`（N日均量）等
- **Factor**：乘数因子，与基准字段相乘得到最终阈值的浮点数
- **Holding_Context**：持仓上下文，回测引擎在评估平仓条件时提供的持仓相关数据，包含买入价、持仓期间最高价、持仓天数等信息
- **BacktestEngine**：回测引擎，执行历史策略回放的核心服务

## 需求

### 需求 1：阈值模式数据模型扩展

**用户故事：** 作为量化策略开发者，我希望平仓条件支持绝对值和相对值两种阈值模式，以便在配置时选择适合的阈值类型。

#### 验收标准

1. THE ExitCondition SHALL 包含 `threshold_mode` 字段，取值为 `"absolute"` 或 `"relative"`，默认值为 `"absolute"`
2. WHEN `threshold_mode` 为 `"absolute"` 时，THE ExitCondition SHALL 保持现有行为，直接使用 `threshold` 字段的浮点数值进行比较
3. WHEN `threshold_mode` 为 `"relative"` 时，THE ExitCondition SHALL 包含 `base_field` 字段（字符串，指定计算基准来源）和 `factor` 字段（浮点数，乘数因子）
4. THE ExitCondition SHALL 支持以下 `base_field` 取值：
   - `entry_price`（买入价）
   - `highest_price`（持仓期间最高价）
   - `lowest_price`（持仓期间最低价）
   - `prev_close`（前一日收盘价）
   - `prev_high`（前一日最高价）
   - `prev_low`（前一日最低价）
   - `today_open`（今日开盘价）
   - `prev_bar_open`（上一根K线开盘价）
   - `prev_bar_high`（上一根K线最高价）
   - `prev_bar_low`（上一根K线最低价）
   - `prev_bar_close`（上一根K线收盘价）
   - `ma_volume`（N日均量，需配合 `params` 中的 `ma_volume_period` 参数）
5. WHEN `threshold_mode` 为 `"relative"` 且 `base_field` 为 `ma_volume` 时，THE ExitCondition SHALL 从 `params` 字段中读取 `ma_volume_period` 参数（整数，默认值 5）作为均量计算周期
6. THE ExitCondition 的 `to_dict()` 方法 SHALL 在序列化时包含 `threshold_mode`、`base_field`、`factor` 字段
7. THE ExitCondition 的 `from_dict()` 方法 SHALL 在反序列化时正确还原 `threshold_mode`、`base_field`、`factor` 字段
8. WHEN `threshold_mode` 字段缺失时，THE ExitCondition 的 `from_dict()` 方法 SHALL 默认设置 `threshold_mode` 为 `"absolute"`，保证与旧版数据的向后兼容
9. FOR ALL 合法的 ExitCondition 对象，`from_dict(condition.to_dict())` SHALL 产生与原对象等价的结果（序列化往返一致性）

### 需求 2：持仓上下文数据传递

**用户故事：** 作为回测引擎开发者，我希望评估平仓条件时能获取当前持仓的上下文数据，以便相对值阈值能根据持仓状态动态计算。

#### 验收标准

1. THE BacktestEngine SHALL 在调用 ExitConditionEvaluator 时传递 Holding_Context 数据，包含以下字段：`entry_price`（买入价，浮点数）、`highest_price`（买入后至当前交易日的最高收盘价，浮点数）、`lowest_price`（买入后至当前交易日的最低收盘价，浮点数）、`entry_bar_index`（买入时的 bar 索引，整数）
2. THE BacktestEngine SHALL 在每个交易日更新持仓的 `highest_price` 和 `lowest_price`，确保反映买入后至当前交易日的极值
3. WHEN Holding_Context 未提供时，THE ExitConditionEvaluator SHALL 跳过所有 `threshold_mode` 为 `"relative"` 的条件，并记录 WARNING 日志
4. THE Holding_Context SHALL 作为独立的数据类定义在 `app/core/schemas.py` 中

### 需求 3：阈值动态解析引擎

**用户故事：** 作为量化策略开发者，我希望相对值阈值在回测运行时能根据持仓上下文自动计算为具体数值，以便实现基于买入价比例的止损等策略。

#### 验收标准

1. THE Threshold_Resolver SHALL 接收 ExitCondition、Holding_Context、IndicatorCache 和当前 bar_index，返回解析后的浮点数阈值
2. WHEN `threshold_mode` 为 `"absolute"` 时，THE Threshold_Resolver SHALL 直接返回 `threshold` 字段的值
3. WHEN `base_field` 为 `entry_price` 时，THE Threshold_Resolver SHALL 计算 `Holding_Context.entry_price × factor` 作为阈值
4. WHEN `base_field` 为 `highest_price` 时，THE Threshold_Resolver SHALL 计算 `Holding_Context.highest_price × factor` 作为阈值
5. WHEN `base_field` 为 `lowest_price` 时，THE Threshold_Resolver SHALL 计算 `Holding_Context.lowest_price × factor` 作为阈值
6. WHEN `base_field` 为 `prev_close` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的收盘价，再乘以 `factor` 作为阈值
7. WHEN `base_field` 为 `prev_high` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的最高价，再乘以 `factor` 作为阈值
8. WHEN `base_field` 为 `prev_low` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的最低价，再乘以 `factor` 作为阈值
9. WHEN `base_field` 为 `today_open` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取当前 `bar_index` 处的开盘价，再乘以 `factor` 作为阈值
10. WHEN `base_field` 为 `prev_bar_open` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的开盘价，再乘以 `factor` 作为阈值
11. WHEN `base_field` 为 `prev_bar_high` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的最高价，再乘以 `factor` 作为阈值
12. WHEN `base_field` 为 `prev_bar_low` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的最低价，再乘以 `factor` 作为阈值
13. WHEN `base_field` 为 `prev_bar_close` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中获取 `bar_index - 1` 处的收盘价，再乘以 `factor` 作为阈值
14. WHEN `base_field` 为 `ma_volume` 时，THE Threshold_Resolver SHALL 从 IndicatorCache 中计算过去 N 日（由 `params.ma_volume_period` 指定，默认 5）的平均成交量，再乘以 `factor` 作为阈值
15. IF `base_field` 的值不在合法取值范围内，THEN THE Threshold_Resolver SHALL 返回 None 并记录 ERROR 日志
16. IF 基准值为 None 或 NaN（如 bar_index 为 0 时无法获取前一日数据），THEN THE Threshold_Resolver SHALL 返回 None 并记录 WARNING 日志
17. IF `factor` 为 None 或非正数，THEN THE Threshold_Resolver SHALL 返回 None 并记录 WARNING 日志

### 需求 4：评估器集成相对值阈值

**用户故事：** 作为量化策略开发者，我希望 ExitConditionEvaluator 在评估数值比较条件时能自动处理相对值阈值，以便无需修改评估流程即可使用相对值条件。

#### 验收标准

1. THE ExitConditionEvaluator 的 `evaluate()` 方法 SHALL 接受可选的 `holding_context` 参数（Holding_Context 类型）
2. WHEN 评估数值比较条件（`>`, `<`, `>=`, `<=`）时，THE ExitConditionEvaluator SHALL 调用 Threshold_Resolver 解析阈值，而非直接使用 `condition.threshold`
3. WHEN Threshold_Resolver 返回 None 时，THE ExitConditionEvaluator SHALL 跳过该条件并记录 WARNING 日志
4. WHEN `threshold_mode` 为 `"absolute"` 且 `holding_context` 未提供时，THE ExitConditionEvaluator SHALL 保持现有行为，直接使用 `condition.threshold` 进行比较
5. THE ExitConditionEvaluator 的触发原因描述 SHALL 包含解析后的实际阈值数值，格式为 `"{INDICATOR} {operator} {resolved_threshold}（{base_field}×{factor}）"`
6. THE ExitConditionEvaluator 对交叉条件（`cross_up`, `cross_down`）的评估 SHALL 不受相对值阈值影响，保持现有行为

### 需求 5：API 验证扩展

**用户故事：** 作为系统管理员，我希望 API 层对相对值阈值配置进行严格验证，以便拒绝无效的配置请求。

#### 验收标准

1. THE ExitConditionSchema SHALL 新增可选字段 `threshold_mode`（默认 `"absolute"`）、`base_field`（字符串，可选）、`factor`（浮点数，可选）
2. WHEN `threshold_mode` 为 `"relative"` 时，THE ExitConditionSchema SHALL 验证 `base_field` 非空且属于合法取值集合，否则返回 422 错误
3. WHEN `threshold_mode` 为 `"relative"` 时，THE ExitConditionSchema SHALL 验证 `factor` 非空且为正数，否则返回 422 错误
4. WHEN `threshold_mode` 为 `"relative"` 时，THE ExitConditionSchema SHALL 允许 `threshold` 为 None（因为阈值由 `base_field × factor` 动态计算）
5. WHEN `threshold_mode` 为 `"absolute"` 且运算符为数值比较时，THE ExitConditionSchema SHALL 保持现有验证逻辑，要求 `threshold` 非空
6. WHEN `threshold_mode` 字段缺失时，THE ExitConditionSchema SHALL 默认为 `"absolute"`，保证与旧版 API 请求的向后兼容

### 需求 6：前端配置面板扩展

**用户故事：** 作为量化策略开发者，我希望在前端配置面板中能选择阈值模式并配置相对值参数，以便直观地创建基于比例的平仓条件。

#### 验收标准

1. WHEN 用户选择数值比较运算符（`>`, `<`, `>=`, `<=`）时，THE 配置面板 SHALL 显示阈值模式切换控件，提供"绝对值"和"相对值"两个选项
2. WHEN 用户选择"绝对值"模式时，THE 配置面板 SHALL 显示现有的阈值数值输入框
3. WHEN 用户选择"相对值"模式时，THE 配置面板 SHALL 隐藏阈值数值输入框，改为显示基准字段下拉框和乘数因子输入框
4. THE 基准字段下拉框 SHALL 包含以下选项，按类别分组展示：
   - 持仓相关：买入价（`entry_price`）、持仓最高价（`highest_price`）、持仓最低价（`lowest_price`）
   - 前一日行情：前一日收盘价（`prev_close`）、前一日最高价（`prev_high`）、前一日最低价（`prev_low`）
   - 当日行情：今日开盘价（`today_open`）
   - 上一根K线：上一根K线开盘价（`prev_bar_open`）、上一根K线最高价（`prev_bar_high`）、上一根K线最低价（`prev_bar_low`）、上一根K线收盘价（`prev_bar_close`）
   - 成交量：N日均量（`ma_volume`）
5. WHEN 用户选择 `ma_volume` 基准字段时，THE 配置面板 SHALL 额外显示均量周期输入框（默认值 5，最小值 1）
6. THE 乘数因子输入框 SHALL 接受正浮点数，步长为 0.01，默认值为 1.0
7. WHEN 用户切换阈值模式时，THE 配置面板 SHALL 清空另一模式的字段值（切换到绝对值时清空 `base_field` 和 `factor`，切换到相对值时清空 `threshold`）
8. WHEN 用户选择交叉运算符（`cross_up`, `cross_down`）时，THE 配置面板 SHALL 隐藏阈值模式切换控件，保持现有的交叉目标下拉框

### 需求 7：前端状态与序列化

**用户故事：** 作为前端开发者，我希望 ExitConditionForm 接口和序列化逻辑能正确处理相对值阈值字段，以便前后端数据一致。

#### 验收标准

1. THE ExitConditionForm 接口 SHALL 新增 `thresholdMode`（`'absolute' | 'relative'`，默认 `'absolute'`）、`baseField`（字符串或 null）、`factor`（数值或 null）字段
2. THE `startBacktest()` 方法 SHALL 在序列化时将 `thresholdMode` 映射为 `threshold_mode`、`baseField` 映射为 `base_field`（camelCase → snake_case）
3. THE `loadExitTemplate()` 方法 SHALL 在反序列化时将 `threshold_mode` 映射为 `thresholdMode`、`base_field` 映射为 `baseField`（snake_case → camelCase）
4. WHEN `threshold_mode` 字段缺失时，THE `loadExitTemplate()` 方法 SHALL 默认设置 `thresholdMode` 为 `'absolute'`，保证加载旧版模版的向后兼容
5. FOR ALL 合法的 ExitConditionForm 对象，序列化为 JSON 后再解析回来 SHALL 产生与原对象等价的结果（前端序列化往返一致性）

### 需求 8：模版与系统内置模版兼容

**用户故事：** 作为量化策略开发者，我希望相对值阈值能在模版中正确保存和加载，并且系统内置模版能包含相对值条件示例。

#### 验收标准

1. THE 模版创建 API SHALL 正确保存包含相对值阈值条件的 `exit_conditions` 到 JSONB 字段
2. THE 模版加载 API SHALL 正确还原包含相对值阈值条件的 `exit_conditions`
3. WHEN 加载不包含 `threshold_mode` 字段的旧版模版时，THE 系统 SHALL 默认将所有条件的 `threshold_mode` 设为 `"absolute"`
4. THE 系统 SHALL 新增至少 2 个包含相对值阈值条件的系统内置模版，示例场景包括：买入价比例止损（收盘价 < 买入价 × 0.95）和回撤止损（收盘价 < 最高价 × 0.90）

### 需求 9：交易流水展示

**用户故事：** 作为量化策略开发者，我希望交易流水中的平仓原因能清晰展示相对值阈值的触发详情，以便回顾和分析策略表现。

#### 验收标准

1. WHEN 相对值阈值条件触发平仓时，THE 交易流水的 `sell_reason` 字段 SHALL 包含解析后的实际阈值和基准信息，格式为 `"EXIT_CONDITION: {INDICATOR} {operator} {resolved_value}（{base_field}×{factor}）"`
2. THE 前端交易流水表格 SHALL 正确解析并展示包含相对值信息的平仓原因
