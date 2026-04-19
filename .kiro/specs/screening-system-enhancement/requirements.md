# 需求文档：智能选股系统增强

## 简介

本需求文档定义了对现有智能选股系统（`app/services/screener/`）的全面增强计划。当前系统存在多处关键链路断裂（资金流因子硬编码、Celery 任务空跑、板块因子未接入、风控未集成）、评分逻辑缺陷（多模块 `max()` 竞争）、以及架构不合理（实时选股全量重算）等问题。增强分三个阶段推进：修复断裂链路、重构评分与信号体系、性能与架构优化。

## 术语表

- **ScreenExecutor**：选股执行器，位于 `app/services/screener/screen_executor.py`，封装盘后与盘中选股核心逻辑
- **ScreenDataProvider**：选股数据提供服务，位于 `app/services/screener/screen_data_provider.py`，负责从数据库加载股票数据并计算派生因子
- **StrategyEngine**：多因子策略引擎，位于 `app/services/screener/strategy_engine.py`，执行 AND/OR 逻辑评估与加权评分
- **RiskController**：风险控制模块，位于 `app/services/risk_controller.py`，包含大盘风控、个股风控、黑白名单管理
- **SectorStrengthFilter**：板块强势筛选器，位于 `app/services/screener/sector_strength.py`，计算板块排名与趋势
- **Factor_Dict**：因子字典，`ScreenDataProvider._build_factor_dict()` 为每只股票生成的 `{factor_name: value}` 字典
- **Celery_Task**：Celery 异步任务，位于 `app/tasks/screening.py`，包含盘后选股和盘中实时选股定时任务
- **Money_Flow_Table**：资金流数据表，数据库中已存在的 `money_flow` 表，存储主力资金净流入和大单成交数据
- **Trend_Score**：趋势强度评分，0-100 分，由多个选股模块综合计算得出
- **Signal_Strength**：信号强度等级，分为强信号、中等信号、弱信号三级
- **Signal_Freshness**：信号新鲜度标记，区分当日新出现的信号与持续存在的信号
- **Redis_Factor_Cache**：Redis 因子缓存，用于存储盘中增量计算的中间因子数据，避免全量重算
- **MarketRiskLevel**：大盘风险等级枚举，包含 NORMAL、CAUTION、DANGER 三个级别

## 需求

### 需求 1：资金流因子数据接入

**用户故事：** 作为量化交易者，我希望选股系统能够查询真实的资金流数据，以便资金面因子（主力资金净流入、大单成交占比）能够参与选股评估。

#### 验收标准

1. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 Money_Flow_Table 查询该股票最近 N 个交易日的主力资金净流入数据，并调用 `check_money_flow_signal()` 计算 `money_flow` 因子值
2. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 Money_Flow_Table 查询该股票当日的大单成交占比数据，并调用 `check_large_order_signal()` 计算 `large_order` 因子值
3. IF Money_Flow_Table 中该股票无数据记录，THEN THE ScreenDataProvider SHALL 将 `money_flow` 设为 False、`large_order` 设为 False，并记录 WARNING 级别日志
4. WHEN 资金流因子数据成功加载后，THE ScreenDataProvider SHALL 将 `money_flow` 和 `large_order` 的原始数值写入 Factor_Dict，以便百分位排名计算能够正确处理这两个因子

### 需求 2：Celery 选股任务接入数据管线

**用户故事：** 作为量化交易者，我希望盘后选股定时任务能够自动加载真实的市场数据和活跃策略配置，以便每日 15:30 的自动选股能够产出有效结果。

#### 验收标准

1. WHEN `run_eod_screening` 任务执行时，THE Celery_Task SHALL 通过 ScreenDataProvider 异步加载全市场股票因子数据，替代当前返回空字典的 `_load_market_data()` 占位实现
2. WHEN `run_eod_screening` 任务执行且未传入 `strategy_dict` 参数时，THE Celery_Task SHALL 从 PostgreSQL `strategy_template` 表查询当前用户的活跃策略模板（`is_active=True`），替代当前返回空配置的 `_load_active_strategy()` 占位实现
3. WHEN 盘后选股任务成功完成时，THE Celery_Task SHALL 将选股结果写入 Redis 缓存（key 格式 `screen:results:{strategy_id}`），并记录执行耗时和选出股票数量到 Redis（key `screen:eod:last_run`）
4. IF 数据库连接不可用或数据加载失败，THEN THE Celery_Task SHALL 记录 ERROR 级别日志并按 Celery 重试策略自动重试，重试次数上限为 3 次

### 需求 3：板块因子接入主选股管线

**用户故事：** 作为量化交易者，我希望板块排名和板块趋势因子能够在选股评估中生效，以便我能够筛选处于强势板块中的个股。

#### 验收标准

1. WHEN ScreenDataProvider 完成 Factor_Dict 构建后，THE ScreenDataProvider SHALL 确保 `sector_rank` 和 `sector_trend` 字段已写入每只股票的 Factor_Dict 中，而非仅写入 `stocks_data` 的顶层
2. WHEN `SectorStrengthFilter.filter_by_sector_strength()` 执行完毕后，THE ScreenDataProvider SHALL 验证 Factor_Dict 中 `sector_rank` 为整数类型（或 None）、`sector_trend` 为布尔类型
3. IF 板块数据加载失败或数据库会话不可用，THEN THE ScreenDataProvider SHALL 将 `sector_rank` 设为 None、`sector_trend` 设为 False，选股流程继续执行不中断

### 需求 4：风控集成到选股执行器

**用户故事：** 作为量化交易者，我希望选股结果经过风控过滤，以便单日涨幅过大、黑名单中的股票、以及大盘危险状态下的所有股票不会出现在选股结果中。

#### 验收标准

1. WHEN ScreenExecutor 执行选股时，THE ScreenExecutor SHALL 调用 `MarketRiskChecker.check_market_risk()` 检查大盘风险等级
2. WHILE 大盘风险等级为 DANGER 时，THE ScreenExecutor SHALL 返回空的选股结果列表，并在结果中标注大盘风险暂停买入
3. WHILE 大盘风险等级为 CAUTION 时，THE ScreenExecutor SHALL 将趋势打分阈值从 80 提升至 90，仅保留 Trend_Score >= 90 的股票
4. WHEN ScreenExecutor 生成候选股票列表后，THE ScreenExecutor SHALL 调用 `StockRiskFilter.check_daily_gain()` 剔除单日涨幅超过 9% 的股票
5. WHEN ScreenExecutor 生成候选股票列表后，THE ScreenExecutor SHALL 调用 `BlackWhiteListManager.is_blacklisted()` 剔除黑名单中的股票
6. THE ScreenExecutor SHALL 在选股结果的每个 ScreenItem 中记录应用的风控过滤信息，包括大盘风险等级和被剔除的原因

### 需求 5：重构趋势评分为加权求和

**用户故事：** 作为量化交易者，我希望多个选股模块的评分能够按权重加权求和，而非取最大值，以便综合评分能够真实反映多因子共振的强度。

#### 验收标准

1. THE ScreenExecutor SHALL 使用加权求和公式计算 Trend_Score：`Trend_Score = Σ(module_score × module_weight) / Σ(module_weight)`，替代当前的 `max()` 竞争逻辑
2. WHEN 计算 Trend_Score 时，THE ScreenExecutor SHALL 为每个启用的模块分配可配置的权重，默认权重为：`factor_editor=0.30`、`ma_trend=0.25`、`indicator_params=0.20`、`breakout=0.15`、`volume_price=0.10`
3. WHEN 某个模块未启用或该模块评分为 0 时，THE ScreenExecutor SHALL 将该模块从加权求和中排除（不计入分母），避免拉低综合评分
4. THE ScreenExecutor SHALL 确保最终 Trend_Score 在 [0, 100] 闭区间内

### 需求 6：支持多重突破信号并发

**用户故事：** 作为量化交易者，我希望一只股票能够同时报告多种突破类型（箱体突破、前高突破、趋势线突破），以便我能够评估突破信号的共振强度。

#### 验收标准

1. WHEN ScreenDataProvider 检测突破信号时，THE ScreenDataProvider SHALL 对所有启用的突破类型（箱体突破、前高突破、趋势线突破）逐一检测，而非在检测到第一个突破后停止
2. WHEN 一只股票同时满足多种突破条件时，THE ScreenDataProvider SHALL 将所有检测到的突破信号存储为列表格式写入 Factor_Dict 的 `breakout` 字段
3. WHEN ScreenExecutor 处理突破信号时，THE ScreenExecutor SHALL 为每种有效突破类型生成独立的 SignalDetail，并在 ScreenItem 的 signals 列表中包含所有突破信号
4. THE ScreenDataProvider SHALL 保持向后兼容：当 `breakout` 字段为单个字典（旧格式）时，ScreenExecutor 仍能正确处理

### 需求 7：信号强度分级

**用户故事：** 作为量化交易者，我希望每个选股信号标注强度等级（强/中/弱），以便我能够优先关注强信号股票。

#### 验收标准

1. THE ScreenExecutor SHALL 为每个 SignalDetail 计算并标注 Signal_Strength 等级：STRONG（强）、MEDIUM（中）、WEAK（弱）
2. WHEN 计算均线趋势信号强度时，THE ScreenExecutor SHALL 根据 `ma_trend` 评分划分：>= 90 为 STRONG、>= 70 为 MEDIUM、其余为 WEAK
3. WHEN 计算突破信号强度时，THE ScreenExecutor SHALL 根据量比划分：量比 >= 2.0 为 STRONG、量比 >= 1.5 为 MEDIUM、其余为 WEAK
4. WHEN 计算技术指标信号强度时，THE ScreenExecutor SHALL 根据同时触发的指标数量划分：>= 3 个为 STRONG、2 个为 MEDIUM、1 个为 WEAK

### 需求 8：信号新鲜度标记

**用户故事：** 作为量化交易者，我希望选股结果能够区分当日新出现的信号和持续存在的信号，以便我能够及时发现新的交易机会。

#### 验收标准

1. WHEN ScreenExecutor 生成选股结果时，THE ScreenExecutor SHALL 为每个 SignalDetail 标注 Signal_Freshness：NEW（当日新出现）或 CONTINUING（持续存在）
2. WHEN 判断信号新鲜度时，THE ScreenExecutor SHALL 从 Redis 缓存读取前一次选股结果，比较同一股票的信号列表变化
3. IF 前一次选股结果不存在（首次运行或缓存过期），THEN THE ScreenExecutor SHALL 将所有信号标记为 NEW
4. THE ScreenItem SHALL 包含一个 `has_new_signal` 布尔字段，标识该股票是否包含至少一个 NEW 信号

### 需求 9：实时选股增量计算架构

**用户故事：** 作为量化交易者，我希望盘中实时选股能够在 10 秒内完成一轮筛选，以便我能够及时捕捉盘中交易机会。

#### 验收标准

1. WHEN 盘中实时选股任务启动时，THE Celery_Task SHALL 采用增量计算模式：仅获取最新一根实时 K 线数据，与 Redis_Factor_Cache 中缓存的历史因子数据合并计算
2. WHEN 每个交易日首次执行实时选股时，THE Celery_Task SHALL 执行一次全量因子预热，将全市场股票的历史因子数据写入 Redis_Factor_Cache，缓存有效期至当日收盘后
3. WHEN 增量计算更新因子时，THE Celery_Task SHALL 仅重新计算受实时数据影响的因子（收盘价相关的均线、技术指标），基本面因子和板块因子使用缓存值
4. THE Celery_Task SHALL 在每轮实时选股完成后记录执行耗时，IF 单轮执行耗时超过 8 秒，THEN THE Celery_Task SHALL 记录 WARNING 级别日志

### 需求 10：选股结果去重与变化检测

**用户故事：** 作为量化交易者，我希望连续多轮实时选股的结果能够去重，仅推送新增和变化的股票，以便减少信息噪音。

#### 验收标准

1. WHEN 实时选股完成一轮筛选后，THE ScreenExecutor SHALL 将本轮结果与 Redis 中缓存的上一轮结果进行比对
2. WHEN 检测到新增股票（本轮有、上轮无）时，THE ScreenExecutor SHALL 将该股票标记为 `change_type=NEW`
3. WHEN 检测到信号变化（同一股票的信号列表发生变化）时，THE ScreenExecutor SHALL 将该股票标记为 `change_type=UPDATED`
4. WHEN 检测到股票移出（上轮有、本轮无）时，THE ScreenExecutor SHALL 将该股票标记为 `change_type=REMOVED`
5. THE ScreenResult SHALL 包含 `changes` 字段，仅包含发生变化的股票列表，供前端增量更新使用

### 需求 11：选股结果到回测的闭环验证

**用户故事：** 作为量化交易者，我希望能够将选股结果一键发送到回测引擎进行历史验证，以便评估选股策略的有效性。

#### 验收标准

1. WHEN 用户通过 API 请求对选股结果执行回测验证时，THE Screen_API SHALL 接受选股结果 ID 和回测参数，构造 BacktestConfig 并提交回测任务
2. WHEN 构造回测配置时，THE Screen_API SHALL 从选股结果中提取策略配置（StrategyConfig）、选出的股票列表、以及选股时间作为回测起始日期
3. THE Screen_API SHALL 返回回测任务 ID，用户可通过回测 API 查询回测进度和结果
4. IF 选股结果 ID 不存在或已过期，THEN THE Screen_API SHALL 返回 404 错误并附带描述性错误信息
