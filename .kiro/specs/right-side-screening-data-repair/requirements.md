# 需求文档：右侧趋势突破选股数据消缺

## 简介

右侧趋势突破综合策略在手动选股中出现“筛选 5331 只、入选 0 只”的异常结果。日志和数据库排查显示，问题不是单一策略过严，而是多处数据与代码口径不一致叠加：

- `rsi` 在策略注册表中定义为 RANGE 数值因子，但选股数据层实际写入布尔信号，真正 RSI 数值保存在 `rsi_current`
- Tushare `daily` 写入 `kline` 时没有写入 `turnover`、`vol_ratio`、`limit_up`、`limit_down`
- `daily_basic` 与 `stk_limit` 已注册为独立 Tushare 接口，但其辅助行情字段没有回填或合并到 TimescaleDB `kline`
- `money_flow` 因子仍依赖旧 `money_flow` 表，而库内可用数据主要在 `moneyflow_ths` / `moneyflow_dc`
- `stk_factor` 仅按选股当天精确查询，最新交易日缺数据时直接匹配 0 只股票

本 spec 目标是在不改变既有策略配置语义的前提下，修正因子读取口径、补齐 K 线辅助字段、接入可用资金流数据，并让专业技术因子在最新数据缺失时安全降级到最近可用交易日，最终使右侧趋势突破类策略基于真实可用数据产生可解释结果。

## 术语表

- **右侧趋势突破综合策略**：内置策略模板，包含 `ma_trend`、`breakout`、`sector_rank`、`sector_trend`、`macd`、`turnover`、`money_flow`、`rsi` 等因子，使用 AND 逻辑。
- **FactorEvaluator**：`app/services/screener/strategy_engine.py` 中的单因子评估器，负责根据 `FactorCondition` 判定某个因子是否通过。
- **ScreenDataProvider**：`app/services/screener/screen_data_provider.py` 中的选股数据供给层，负责从 PostgreSQL 和 TimescaleDB 加载并构造 `{symbol: factor_dict}`。
- **Kline 辅助字段**：`kline.turnover`、`kline.vol_ratio`、`kline.limit_up`、`kline.limit_down`，用于换手、量比、涨跌停风控和选股。
- **Tushare daily**：Tushare 日线行情接口，提供 OHLCV 和成交额，但不提供换手率、量比、涨跌停价。
- **Tushare daily_basic**：Tushare 每日指标接口，提供 `turnover_rate`、`volume_ratio` 等每日指标。
- **Tushare stk_limit**：Tushare 每日涨跌停价格接口，提供 `up_limit`、`down_limit`。
- **增强资金流表**：`moneyflow_ths` / `moneyflow_dc`，当前库内已有较完整资金流数据，可用于生成 `money_flow`、`large_order` 和相关百分位因子。
- **最近可用交易日回退**：当目标选股日期无某类因子数据时，在限定回退窗口内选择不晚于目标日期的最近数据日期。

## 需求

### 需求 1：RSI RANGE 因子读取口径修正

**用户故事：** 作为量化交易员，我希望 RSI 区间条件使用真实 RSI 数值判断，而不是误用布尔信号，以便策略配置中的 `rsi BETWEEN 55 AND 80` 能按预期生效。

#### 验收标准

1. WHEN `FactorEvaluator` 评估 `factor_name="rsi"` 且阈值类型为 RANGE 时，THE 系统 SHALL 从 `stock_data["rsi_current"]` 读取数值进行区间判断
2. WHEN `stock_data["rsi_current"]` 缺失或为 `None` 时，THE `rsi` RANGE 条件 SHALL 判定为不通过
3. WHEN `stock_data["rsi_current"]` 在 `[threshold_low, threshold_high]` 区间内时，THE `rsi` RANGE 条件 SHALL 判定为通过
4. WHEN `stock_data["rsi"]` 为布尔值且 `stock_data["rsi_current"]` 存在时，THE RANGE 判断 SHALL 不使用布尔值
5. THE 修复 SHALL 保持布尔型 `rsi` 信号在指标共振、信号展示中的现有语义不变

### 需求 2：Kline 辅助字段来源与写入口径统一

**用户故事：** 作为量化交易员，我希望 `kline` 表中的换手率、量比、涨跌停价字段由 Tushare 辅助接口补齐，以便选股和回测能直接读取一致的 K 线行情字段。

#### 验收标准

1. THE 系统 SHALL 明确 `kline.turnover` 来源为 `daily_basic.turnover_rate`
2. THE 系统 SHALL 明确 `kline.vol_ratio` 来源为 `daily_basic.volume_ratio`
3. THE 系统 SHALL 明确 `kline.limit_up` 来源为 `stk_limit.up_limit`
4. THE 系统 SHALL 明确 `kline.limit_down` 来源为 `stk_limit.down_limit`
5. WHEN Tushare `daily` 写入 `kline` 时，THE 写入逻辑 SHALL 保持 OHLCV 字段的现有行为，不伪造 `turnover`、`vol_ratio`、`limit_up`、`limit_down`
6. WHEN 辅助接口数据不可用时，THE `kline` 对应辅助字段 SHALL 保持 `NULL`，不得写入 `0` 伪装为有效值
7. THE `adj_type=0` SHALL 继续表示不复权原始 K 线，不作为缺失字段处理

### 需求 3：Tushare daily_basic 数据入库与回填

**用户故事：** 作为系统运维人员，我希望导入 `daily_basic` 后能把换手率和量比合并到 `kline`，以便选股换手率条件不再因字段缺失全部失败。

#### 验收标准

1. WHEN `daily_basic` 导入完成并包含 `ts_code`、`trade_date`、`turnover_rate`、`volume_ratio` 时，THE 系统 SHALL 将对应值回填到 `kline.turnover` 和 `kline.vol_ratio`
2. THE 回填 SHALL 按 `(symbol, trade_date, freq='1d', adj_type=0)` 匹配 `kline` 行
3. IF 对应 `kline` 行不存在，THEN THE 系统 SHALL 跳过该行并记录可观测统计，不创建无 OHLCV 的空 K 线
4. WHEN 新值为 `NULL` 时，THE 回填 SHALL 不覆盖 `kline` 中已有非空值
5. THE 回填 SHALL 支持批量执行，避免逐行提交导致大范围历史补齐性能不可接受
6. THE 回填 SHALL 可由 Tushare 导入任务自动触发，也 SHALL 可通过服务函数或脚本对历史数据手动补跑

### 需求 4：Tushare stk_limit 数据入库与回填

**用户故事：** 作为量化交易员，我希望涨跌停价能进入 `kline`，以便风险过滤和结果展示使用真实涨跌停价格。

#### 验收标准

1. WHEN `stk_limit` 导入完成并包含 `ts_code`、`trade_date`、`up_limit`、`down_limit` 时，THE 系统 SHALL 将对应值回填到 `kline.limit_up` 和 `kline.limit_down`
2. THE 回填 SHALL 按 `(symbol, trade_date, freq='1d', adj_type=0)` 匹配 `kline` 行
3. IF 对应 `kline` 行不存在，THEN THE 系统 SHALL 跳过该行并记录可观测统计
4. WHEN 新值为 `NULL` 时，THE 回填 SHALL 不覆盖 `kline` 中已有非空值
5. THE 回填 SHALL 支持对历史 `stk_limit` 表数据进行一次性补齐

### 需求 5：资金流因子支持用户选择数据源

**用户故事：** 作为量化交易员，我希望在策略中通过下拉框选择 `money_flow` 因子使用的数据源（`money_flow` / `moneyflow_ths` / `moneyflow_dc` 三选一），以便根据数据覆盖和策略偏好决定资金流口径。

#### 验收标准

1. THE 策略配置 SHALL 支持资金流数据源字段，取值为 `money_flow`、`moneyflow_ths`、`moneyflow_dc` 三者之一
2. THE 前端策略配置 SHALL 通过下拉框展示资金流数据源选项，且只能单选
3. WHEN 用户选择 `money_flow` 时，THE 系统 SHALL 使用旧 `money_flow` 表生成 `money_flow`、`large_order`、`main_net_inflow`、`large_order_ratio` 等因子
4. WHEN 用户选择 `moneyflow_ths` 时，THE 系统 SHALL 使用 `moneyflow_ths` 表生成可比较的资金流原始值、`money_flow` 布尔信号和百分位字段
5. WHEN 用户选择 `moneyflow_dc` 时，THE 系统 SHALL 使用 `moneyflow_dc` 表生成可比较的资金流原始值、`money_flow` 布尔信号和百分位字段
6. THE 系统 SHALL 不在三个资金流数据源之间自动回退；所选数据源缺失时，THE `money_flow` 因子 SHALL 降级为 False，相关数值字段 SHALL 置为 `None`
7. WHEN 策略配置缺失资金流数据源字段时，THE 系统 SHALL 默认使用 `money_flow`，保证旧策略向后兼容
8. THE 实现 SHALL 保持已有 `money_flow_strength`、`large_net_inflow`、`super_large_net_inflow` 等增强资金流字段的语义兼容

### 需求 6：stk_factor 最近可用日期回退

**用户故事：** 作为量化交易员，我希望专业技术因子在当天数据尚未导入时能使用最近可用交易日数据，而不是直接匹配 0 只股票。

#### 验收标准

1. WHEN `_enrich_stk_factor_factors` 查询目标 `screen_date` 没有任何 `stk_factor` 数据时，THE 系统 SHALL 在限定回退窗口内查找不晚于 `screen_date` 的最近可用 `trade_date`
2. THE 默认回退窗口 SHALL 不超过 10 个自然日或 5 个交易日，避免使用过旧因子
3. IF 找到最近可用日期，THEN THE 系统 SHALL 使用该日期的 `stk_factor` 数据补充 KDJ、CCI、WR、TRIX、BIAS 等字段
4. IF 未找到最近可用日期，THEN THE 系统 SHALL 保持现有安全降级行为，将相关因子置为 `None`
5. THE 日志 SHALL 记录目标日期、实际使用日期、匹配股票数和回退天数

### 需求 7：右侧趋势突破综合策略可解释性

**用户故事：** 作为量化交易员，我希望当策略仍然选不出股票时，系统能告诉我是哪些因子限制了结果，而不是只返回 0。

#### 验收标准

1. WHEN 手动选股完成且入选数量为 0 时，THE 系统 SHALL 在日志中输出每个策略因子的通过数量或缺失数量
2. THE 统计 SHALL 至少包含 `ma_trend`、`breakout`、`sector_rank`、`sector_trend`、`macd`、`turnover`、`money_flow`、`rsi`
3. THE 统计 SHALL 区分“值缺失导致不通过”和“有值但条件不满足”
4. THE 统计 SHALL 不改变 API 响应结构，除非后续设计明确需要前端展示

### 需求 8：历史数据补齐与幂等性

**用户故事：** 作为系统运维人员，我希望能对已有 Tushare 导入数据执行一次性补齐，并且重复执行不会破坏已有 K 线数据。

#### 验收标准

1. THE 系统 SHALL 提供批量/历史回填入口，用于将导入过程中获得的 `daily_basic` rows、可用的 `daily_basic` 历史明细来源（如后续新增表或重新导入结果）以及已有 `stk_limit` 表数据补齐到 `kline`
2. THE 历史表或重新导入补跑入口 SHALL 支持按日期范围执行；导入后置 hook 可按当前批次 rows 执行
3. THE 回填 SHALL 是幂等的，重复执行不改变已正确写入的数据
4. THE 回填 SHALL 不覆盖 OHLCV 字段
5. THE 回填 SHALL 输出处理行数、匹配行数、更新行数、跳过行数
6. IF 回填过程中发生单批失败，THEN THE 系统 SHALL 回滚该批并报告错误，不留下部分提交的不可追踪状态

### 需求 9：测试与验证

**用户故事：** 作为开发者，我希望这些修复有针对性的自动化测试和数据库验证查询，以便后续导入链路调整不会再次造成全市场 0 命中。

#### 验收标准

1. THE 测试 SHALL 覆盖 `rsi` RANGE 使用 `rsi_current` 而非布尔 `rsi`
2. THE 测试 SHALL 覆盖 `daily_basic` 回填 `turnover`、`vol_ratio` 到 `kline`
3. THE 测试 SHALL 覆盖 `stk_limit` 回填 `limit_up`、`limit_down` 到 `kline`
4. THE 测试 SHALL 覆盖 `money_flow` / `moneyflow_ths` / `moneyflow_dc` 三种用户选择数据源生成可评估因子，且 THS/DC 之间不自动回退
5. THE 测试 SHALL 覆盖 `stk_factor` 目标日期缺失时的最近可用日期回退
6. THE 验证 SHALL 包含一次真实库统计查询，确认最近交易日 `kline.turnover`、`kline.vol_ratio`、`kline.limit_up`、`kline.limit_down` 的非空覆盖率
7. THE 验证 SHALL 包含一次右侧趋势突破综合策略手动选股或等价服务级运行，确认不再由数据字段缺失或 RSI 口径错误导致必然 0 入选

## 非目标

1. 本 spec 不要求引入物化前复权 K 线；`adj_type=1/2` 的存储策略保持不变
2. 本 spec 仅要求在现有量价资金配置 UI 中新增资金流数据源下拉框，不要求重做策略配置页面或结果展示 UI
3. 本 spec 不要求自动放宽右侧趋势突破综合策略阈值
4. 本 spec 不要求补齐所有 Tushare 接口的历史导入成功率，只聚焦影响本次选股的字段和因子
