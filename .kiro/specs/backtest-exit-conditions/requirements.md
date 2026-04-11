# 需求文档：回测自定义平仓条件

## 简介

在现有策略回测系统中，平仓（卖出）条件仅依赖风控模块的固定止损、移动止盈、趋势破位均线和最大持仓天数四种方式。本功能扩展回测引擎，允许用户在回测参数配置页面中定义基于技术指标的自定义平仓条件。这些条件可使用系统已支持的多种分钟K线（1分钟、5分钟、15分钟、30分钟、60分钟）和日K线数据及其衍生指标（MA、MACD、BOLL、RSI、DMA、量价等），与现有风控止损止盈条件并行生效，为量化交易员提供更灵活的回测平仓策略。此外，用户可将配置好的自定义平仓条件保存为命名模版，在后续回测中直接加载复用，避免重复配置。

## 术语表

- **Backtest_Engine**: 历史回测核心引擎，负责逐交易日模拟买卖执行和绩效计算
- **Exit_Condition_Evaluator**: 自定义平仓条件评估器，负责在每个交易日对持仓标的逐一评估用户配置的平仓条件
- **Exit_Condition**: 单条自定义平仓条件，由数据源频率（日K线或具体分钟K线类型）、指标名称、比较运算符、阈值或交叉目标组成
- **Minute_Kline_Type**: 分钟K线类型，系统支持五种分钟级别K线："1min"、"5min"、"15min"、"30min"、"60min"
- **VALID_FREQS**: 合法的数据源频率集合，包含 "daily"、"1min"、"5min"、"15min"、"30min"、"60min"
- **Exit_Condition_Config**: 用户配置的平仓条件集合，包含条件列表和条件间逻辑关系
- **Indicator_Cache**: 预计算指标缓存，存储每只股票各项技术指标的完整时间序列
- **KlineBar**: K线数据传输对象，包含时间、开高低收、成交量、成交额、换手率等字段
- **Risk_Controller**: 现有风控模块，提供固定止损、移动止盈、趋势破位止损等功能
- **BacktestConfig**: 回测配置数据类，包含策略配置、起止日期、资金参数和风控参数
- **Backtest_API**: 回测 REST API 端点，接收前端提交的回测参数并启动回测任务
- **Backtest_View**: 前端回测页面组件，提供回测参数配置表单和结果展示
- **Exit_Condition_Template**: 平仓条件模版，用户保存的一组命名的 Exit_Condition_Config 配置，可在后续回测中加载复用
- **Exit_Template_API**: 平仓条件模版 REST API 端点，提供模版的增删改查操作
- **ExitConditionTemplate**: 平仓条件模版 ORM 模型，存储于 PostgreSQL，包含模版名称、描述、平仓条件配置 JSON 和用户归属

## 需求

### 需求 1：平仓条件数据模型定义

**用户故事：** 作为量化交易员，我希望系统提供结构化的平仓条件数据模型，以便我能以统一格式配置各类基于技术指标的平仓规则。

#### 验收标准

1. THE Exit_Condition SHALL 包含以下字段：数据源频率（"daily"、"1min"、"5min"、"15min"、"30min"、"60min" 之一）、指标名称、比较运算符、阈值或交叉目标、指标参数
2. THE Exit_Condition SHALL 支持以下指标名称："ma"、"macd_dif"、"macd_dea"、"macd_histogram"、"boll_upper"、"boll_middle"、"boll_lower"、"rsi"、"dma"、"ama"、"close"、"volume"、"turnover"
3. THE Exit_Condition SHALL 支持以下比较运算符：">"、"<"、">="、"<="、"cross_up"、"cross_down"
4. WHEN 比较运算符为 "cross_up" 或 "cross_down" 时，THE Exit_Condition SHALL 使用交叉目标字段指定被交叉的指标名称，而非数值阈值
5. THE Exit_Condition_Config SHALL 包含平仓条件列表和条件间逻辑运算符（"AND" 或 "OR"），默认为 "AND"
6. THE Exit_Condition_Config SHALL 支持序列化为 JSON 字典和从 JSON 字典反序列化
7. FOR ALL 有效的 Exit_Condition_Config 对象，序列化后再反序列化 SHALL 产生与原对象等价的结果（往返一致性）

### 需求 2：平仓条件评估引擎

**用户故事：** 作为量化交易员，我希望回测引擎能在每个交易日自动评估我配置的平仓条件，以便在满足条件时自动触发平仓操作。

#### 验收标准

1. WHEN 回测进入每个交易日的卖出条件检测阶段时，THE Exit_Condition_Evaluator SHALL 对每只持仓标的逐一评估用户配置的所有自定义平仓条件
2. WHEN Exit_Condition_Config 的逻辑运算符为 "AND" 时，THE Exit_Condition_Evaluator SHALL 在所有条件均满足时才触发平仓信号
3. WHEN Exit_Condition_Config 的逻辑运算符为 "OR" 时，THE Exit_Condition_Evaluator SHALL 在任一条件满足时即触发平仓信号
4. WHEN 比较运算符为 ">"、"<"、">="、"<=" 时，THE Exit_Condition_Evaluator SHALL 将指标当前值与数值阈值进行比较
5. WHEN 比较运算符为 "cross_up" 时，THE Exit_Condition_Evaluator SHALL 检测指标值从前一交易日低于或等于目标指标值变为当日高于目标指标值
6. WHEN 比较运算符为 "cross_down" 时，THE Exit_Condition_Evaluator SHALL 检测指标值从前一交易日高于或等于目标指标值变为当日低于目标指标值
7. WHEN 数据源频率为 "daily" 时，THE Exit_Condition_Evaluator SHALL 使用日K线数据及其衍生指标进行评估
8. WHEN 数据源频率为 "1min"、"5min"、"15min"、"30min" 或 "60min" 时，THE Exit_Condition_Evaluator SHALL 使用对应周期的分钟K线数据及其衍生指标进行评估，在对应周期的分钟K线数据不可用时回退到日K线数据
9. IF 指标数据不足以计算（如K线数量少于指标所需最小周期）时，THEN THE Exit_Condition_Evaluator SHALL 跳过该条件评估并记录警告日志

### 需求 3：自定义平仓条件与现有风控的集成

**用户故事：** 作为量化交易员，我希望自定义平仓条件与现有的止损止盈机制协同工作，以便两套规则能同时生效且不互相冲突。

#### 验收标准

1. THE Backtest_Engine SHALL 在现有卖出条件检测（固定止损、趋势破位、移动止盈、持仓超期）之后执行自定义平仓条件评估
2. WHEN 现有风控条件已触发某只持仓的卖出信号时，THE Backtest_Engine SHALL 跳过该持仓的自定义平仓条件评估
3. WHEN 自定义平仓条件触发卖出信号时，THE Backtest_Engine SHALL 生成优先级为 5 的卖出信号（低于现有四种卖出信号的优先级 1-4）
4. THE Backtest_Engine SHALL 在交易记录中标注卖出原因为 "EXIT_CONDITION"，以区分自定义平仓条件触发的卖出
5. WHEN 用户未配置任何自定义平仓条件时，THE Backtest_Engine SHALL 保持与现有行为完全一致

### 需求 4：指标计算与缓存扩展

**用户故事：** 作为量化交易员，我希望自定义平仓条件所需的指标能被高效计算和缓存，以便回测性能不因新增平仓条件而显著下降。

#### 验收标准

1. THE Indicator_Cache SHALL 复用现有预计算指标缓存中已有的指标数据（MA、MACD、BOLL、RSI、DMA）
2. WHEN 自定义平仓条件引用了 Indicator_Cache 中尚未缓存的指标参数组合时，THE Backtest_Engine SHALL 在预计算阶段补充计算并缓存该指标
3. THE Exit_Condition_Evaluator SHALL 通过索引直接从 Indicator_Cache 查表获取指标值，避免逐日重复计算
4. WHEN 平仓条件使用 "ma" 指标时，THE Exit_Condition_Evaluator SHALL 支持用户自定义均线周期参数（如 MA5、MA10、MA20、MA60）
5. WHEN 平仓条件使用 MACD 相关指标时，THE Exit_Condition_Evaluator SHALL 支持用户自定义快线、慢线、信号线周期参数

### 需求 5：回测 API 扩展

**用户故事：** 作为量化交易员，我希望通过回测 API 提交自定义平仓条件配置，以便前端页面能将我的配置传递给回测引擎。

#### 验收标准

1. THE Backtest_API 的回测启动请求模型 SHALL 新增可选字段 exit_conditions，类型为平仓条件配置的 JSON 对象
2. WHEN exit_conditions 字段为空或未提供时，THE Backtest_API SHALL 以无自定义平仓条件的方式启动回测
3. WHEN exit_conditions 字段包含无效的指标名称、运算符或数据源频率时，THE Backtest_API SHALL 返回 HTTP 422 状态码和描述性错误信息
4. WHEN exit_conditions 字段中的 freq 值不属于 VALID_FREQS 集合时，THE Backtest_API SHALL 返回 HTTP 422 状态码，错误信息中列出合法的频率值
5. THE Backtest_API SHALL 将 exit_conditions 配置传递给 BacktestConfig 数据类，并最终传递给 Backtest_Engine
6. THE BacktestConfig 数据类 SHALL 新增可选字段 exit_conditions，默认值为 None

### 需求 6：前端回测页面平仓条件配置

**用户故事：** 作为量化交易员，我希望在回测参数配置页面中通过可视化表单添加和管理自定义平仓条件，以便我无需手动编写 JSON 即可配置复杂的平仓规则。

#### 验收标准

1. THE Backtest_View SHALL 在回测参数区域新增"自定义平仓条件"配置面板，默认折叠
2. WHEN 用户展开平仓条件面板时，THE Backtest_View SHALL 显示条件列表和"添加条件"按钮
3. WHEN 用户点击"添加条件"按钮时，THE Backtest_View SHALL 新增一行条件配置，包含数据源频率下拉框（选项为"日K"、"1分钟"、"5分钟"、"15分钟"、"30分钟"、"60分钟"）、指标名称下拉框、比较运算符下拉框、阈值输入框或交叉目标下拉框
4. WHEN 用户选择比较运算符为 "cross_up" 或 "cross_down" 时，THE Backtest_View SHALL 将阈值输入框替换为交叉目标指标下拉框
5. WHEN 用户选择 "ma" 指标时，THE Backtest_View SHALL 显示均线周期参数输入框
6. THE Backtest_View SHALL 提供条件间逻辑运算符选择（"AND" / "OR"），默认为 "AND"
7. WHEN 用户点击条件行的删除按钮时，THE Backtest_View SHALL 移除该条件
8. THE Backtest_View SHALL 在提交回测时将平仓条件配置序列化为 JSON 并包含在请求中

### 需求 7：回测结果中的平仓原因展示

**用户故事：** 作为量化交易员，我希望在回测结果的交易流水中看到每笔卖出的平仓原因，以便我能分析自定义平仓条件的实际触发效果。

#### 验收标准

1. THE Backtest_Engine SHALL 在每笔卖出交易记录中包含 sell_reason 字段，标注触发卖出的具体原因
2. WHEN 卖出由自定义平仓条件触发时，THE sell_reason SHALL 包含触发的具体条件描述（如 "RSI > 80" 或 "MACD_DIF cross_down MACD_DEA"）
3. THE Backtest_View 的交易流水表格 SHALL 新增"平仓原因"列，展示每笔卖出交易的 sell_reason
4. WHEN 卖出由现有风控条件触发时，THE sell_reason SHALL 标注对应的风控类型（"STOP_LOSS"、"TREND_BREAK"、"TRAILING_STOP"、"MAX_HOLDING_DAYS"）

### 需求 8：分钟K线频率向后兼容

**用户故事：** 作为量化交易员，我希望系统在扩展分钟K线类型后仍能兼容旧版配置中的 "minute" 频率值，以便已保存的回测配置不会因升级而失效。

#### 验收标准

1. WHEN Exit_Condition 的 freq 字段值为 "minute" 时，THE Exit_Condition_Evaluator SHALL 将其视为 "1min" 进行评估（向后兼容）
2. THE Backtest_API SHALL 接受 "minute" 作为 freq 的合法值，并在内部将其映射为 "1min"
3. THE Exit_Condition_Config 的 from_dict 方法 SHALL 在反序列化时将 freq 值 "minute" 自动转换为 "1min"

### 需求 9：平仓条件模版后端存储与 API

**用户故事：** 作为量化交易员，我希望将配置好的自定义平仓条件保存为命名模版并通过 API 管理，以便我在后续回测中能快速加载已保存的平仓条件配置，避免重复配置。

#### 验收标准

1. THE ExitConditionTemplate SHALL 包含以下字段：UUID 主键（id）、用户标识（user_id）、模版名称（name，最长 100 字符）、模版描述（description，可选，最长 500 字符）、平仓条件配置（exit_conditions，JSONB 类型，存储 ExitConditionConfig 序列化结果）、创建时间（created_at）、更新时间（updated_at）
2. THE ExitConditionTemplate SHALL 存储于 PostgreSQL 数据库，使用 PGBase 作为 ORM 基类，遵循现有 StrategyTemplate 模型的设计模式（UUID 主键、JSONB 配置字段、时间戳字段）
3. THE Exit_Template_API SHALL 提供以下 REST 端点：POST /api/v1/backtest/exit-templates（保存新模版）、GET /api/v1/backtest/exit-templates（列出当前用户所有模版）、GET /api/v1/backtest/exit-templates/{id}（获取指定模版）、PUT /api/v1/backtest/exit-templates/{id}（更新指定模版）、DELETE /api/v1/backtest/exit-templates/{id}（删除指定模版）
4. WHEN 用户创建模版时，THE Exit_Template_API SHALL 验证 exit_conditions 字段包含有效的 ExitConditionConfig 数据（指标名称、运算符、频率均合法）
5. IF 用户创建模版时提供的模版名称与该用户已有模版名称重复，THEN THE Exit_Template_API SHALL 返回 HTTP 409 状态码和描述性错误信息
6. IF 用户的模版数量已达到上限（50 个），THEN THE Exit_Template_API SHALL 返回 HTTP 409 状态码，错误信息提示已达到模版数量上限
7. WHEN 用户更新或删除模版时，THE Exit_Template_API SHALL 验证该模版属于当前用户，非本人模版返回 HTTP 403 状态码
8. WHEN 用户请求获取指定模版但该模版不存在时，THE Exit_Template_API SHALL 返回 HTTP 404 状态码
9. THE ExitConditionTemplate 的 exit_conditions 字段 SHALL 支持序列化为 JSON 和从 JSON 反序列化，且与 ExitConditionConfig 的 to_dict/from_dict 格式一致
10. FOR ALL 有效的 ExitConditionTemplate 对象，其 exit_conditions 字段经 ExitConditionConfig.from_dict() 反序列化后 SHALL 产生有效的 ExitConditionConfig 对象

### 需求 10：前端平仓条件模版管理

**用户故事：** 作为量化交易员，我希望在回测页面的平仓条件配置面板中保存和加载模版，以便我能将常用的平仓条件组合保存下来并在后续回测中一键加载复用。

#### 验收标准

1. THE Backtest_View SHALL 在平仓条件面板中新增"保存为模版"按钮
2. WHEN 用户点击"保存为模版"按钮时，THE Backtest_View SHALL 弹出模版名称输入对话框，包含名称输入框（必填）和描述输入框（可选）
3. WHEN 用户确认保存模版时，THE Backtest_View SHALL 将当前平仓条件配置序列化并调用 POST /api/v1/backtest/exit-templates 接口保存
4. IF 模版保存成功，THEN THE Backtest_View SHALL 显示保存成功提示并刷新模版列表
5. IF 模版保存失败（名称重复或数量超限），THEN THE Backtest_View SHALL 显示对应的错误提示信息
6. THE Backtest_View SHALL 在平仓条件面板中新增模版选择下拉框，列出当前用户所有已保存的模版
7. WHEN 用户从模版选择下拉框中选择一个模版时，THE Backtest_View SHALL 调用 GET /api/v1/backtest/exit-templates/{id} 获取模版详情，并将当前平仓条件配置替换为模版中的条件配置
8. THE Backtest_View SHALL 在模版选择下拉框旁提供模版管理功能，支持重命名和删除已保存的模版
9. WHEN 用户删除模版时，THE Backtest_View SHALL 弹出确认对话框，确认后调用 DELETE /api/v1/backtest/exit-templates/{id} 接口删除
10. WHEN 用户未配置任何平仓条件时，THE Backtest_View SHALL 禁用"保存为模版"按钮
