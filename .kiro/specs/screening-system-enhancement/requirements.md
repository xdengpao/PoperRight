# 需求文档：智能选股系统增强

## 简介

本需求文档定义了对现有智能选股系统（`app/services/screener/`）的全面增强计划。增强分为两大部分：

**第一部分（需求 1-11）**：修复现有系统的断裂链路（资金流因子硬编码、Celery 任务空跑、板块因子未接入、风控未集成）、重构评分与信号体系、性能与架构优化。

**第二部分（需求 12-22）**：基于已全面集成的 tushare 数据源（122 个接口），扩展因子注册表（从 19 个扩展到 52 个），新增技术面专业因子、筹码分析因子、两融因子、增强资金流因子、打板专题因子、指数专题因子共 6 大类新因子；增强因子条件编辑器指标；重构板块面因子分类以适配 tushare 数据来源体系；更新现有策略示例以适配板块分类重构；提供优化选股组合方案及组合配置说明书。

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
- **FACTOR_REGISTRY**：因子元数据注册表，位于 `app/services/screener/factor_registry.py`，存储所有因子的元数据定义
- **FactorMeta**：因子元数据冻结数据类，包含因子名称、标签、类别、阈值类型、默认值等
- **FactorCategory**：因子类别枚举，当前包含 technical、money_flow、fundamental、sector 四类
- **DataSource**：板块数据来源枚举，位于 `app/models/sector.py`，当前包含 DC（东方财富）、TI（同花顺/申万）、TDX（通达信）、CI（中信行业）、THS（同花顺概念/行业）
- **SectorType**：板块类型枚举，位于 `app/models/sector.py`，当前包含 CONCEPT、INDUSTRY、REGION、STYLE 四类（将被重构为可选过滤参数）
- **SectorScreenConfig**：板块筛选配置数据类，位于 `app/core/schemas.py`，包含 `sector_data_source`、`sector_type`、`sector_period`、`sector_top_n` 字段
- **ThresholdType**：因子阈值类型枚举，包含 absolute、percentile、industry_relative、z_score、boolean、range 六种
- **stk_factor_pro**：tushare 股票技术面因子专业版接口，提供预计算的技术因子数据，存储于 `stk_factor` 表
- **cyq_perf**：tushare 每日筹码及胜率接口，提供筹码集中度和获利比例数据，存储于 `cyq_perf` 表
- **cyq_chips**：tushare 每日筹码分布接口，提供筹码分布详情，存储于 `cyq_chips` 表
- **margin_detail**：tushare 融资融券交易明细接口，提供个股两融数据，存储于 `margin_detail` 表
- **moneyflow_ths**：tushare 同花顺个股资金流向接口，提供多维度资金流数据，存储于 `moneyflow_ths` 表
- **moneyflow_dc**：tushare 东方财富个股资金流向接口，提供多维度资金流数据，存储于 `moneyflow_dc` 表
- **limit_list_d**：tushare 涨跌停和炸板数据接口，提供涨停板相关数据，存储于 `limit_list` 表
- **idx_factor_pro**：tushare 指数技术面因子专业版接口，提供指数技术因子数据，存储于 `index_tech` 表
- **StrategyExample**：策略示例数据类，位于 `app/services/screener/strategy_examples.py`，存储可直接加载的选股策略配置
- **Combination_Config_Doc**：组合配置说明书，描述每个推荐选股组合的因子构成、适用场景、参数配置和风险提示

## 需求

---

### 第一部分：现有系统修复与增强（需求 1-11）

---

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
4. WHEN 调用 SectorStrengthFilter 时，THE ScreenDataProvider SHALL 以 `sector_data_source` 为主维度查询板块数据（参见需求 22），不再依赖 `sector_type` 作为必选过滤参数

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


---

### 第二部分：基于 Tushare 数据源的因子扩展与选股优化（需求 12-22）

---

### 需求 12：技术面专业因子扩展（基于 stk_factor_pro）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare `stk_factor_pro` 接口提供的预计算技术因子数据，新增专业级技术面因子到因子条件编辑器，以便使用更丰富的技术分析维度进行选股。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 新增以下技术面因子，类别为 `FactorCategory.TECHNICAL`：
   - `kdj_k`（KDJ-K值）：阈值类型 RANGE，默认区间 [20, 80]，取值范围 [0, 100]
   - `kdj_d`（KDJ-D值）：阈值类型 RANGE，默认区间 [20, 80]，取值范围 [0, 100]
   - `kdj_j`（KDJ-J值）：阈值类型 RANGE，默认区间 [0, 100]，取值范围 [-50, 150]
   - `cci`（CCI顺势指标）：阈值类型 ABSOLUTE，默认阈值 100，取值范围 [-300, 300]
   - `wr`（威廉指标）：阈值类型 RANGE，默认区间 [0, 20]，取值范围 [0, 100]，说明"WR 越低表示越超买"
   - `trix`（TRIX三重指数平滑）：阈值类型 BOOLEAN，说明"TRIX 上穿信号线为多头信号"
   - `bias`（乖离率）：阈值类型 RANGE，默认区间 [-5, 5]，单位 %
   - `psy`（心理线指标）：阈值类型 RANGE，默认区间 [40, 75]，取值范围 [0, 100]，单位 %
   - `obv_signal`（OBV能量潮信号）：阈值类型 BOOLEAN，说明"OBV 趋势向上为多头信号"
2. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 `stk_factor` 表查询该股票最新的技术因子数据，将上述因子值写入 Factor_Dict
3. IF `stk_factor` 表中该股票无数据记录，THEN THE ScreenDataProvider SHALL 将所有 stk_factor_pro 相关因子设为 None，选股流程继续执行不中断
4. THE FactorEvaluator SHALL 能够正确评估上述新增因子的条件，包括 RANGE 类型的区间判断和 BOOLEAN 类型的布尔判断

### 需求 13：筹码分析因子扩展（基于 cyq_perf / cyq_chips）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare 筹码数据（`cyq_perf` 每日筹码及胜率、`cyq_chips` 每日筹码分布），新增筹码分析因子到因子条件编辑器，以便从筹码集中度和获利盘比例维度筛选个股。

#### 验收标准

1. THE FactorCategory SHALL 新增 `CHIP` 类别（筹码面），用于归类所有筹码分析因子
2. THE FACTOR_REGISTRY SHALL 新增以下筹码面因子，类别为 `FactorCategory.CHIP`：
   - `chip_winner_rate`（获利比例）：阈值类型 PERCENTILE，默认阈值 50，取值范围 [0, 100]，单位 %，说明"当前价格下的获利筹码占比"，数据来源 `cyq_perf.winner_rate`
   - `chip_cost_5pct`（5%成本集中度）：阈值类型 ABSOLUTE，默认阈值 10，单位 %，说明"5%筹码集中度，值越小表示筹码越集中"，数据来源 `cyq_perf.cost_5pct`
   - `chip_cost_15pct`（15%成本集中度）：阈值类型 ABSOLUTE，默认阈值 20，单位 %，说明"15%筹码集中度"，数据来源 `cyq_perf.cost_15pct`
   - `chip_cost_50pct`（50%成本集中度）：阈值类型 ABSOLUTE，默认阈值 30，单位 %，说明"50%筹码集中度"，数据来源 `cyq_perf.cost_50pct`
   - `chip_weight_avg`（筹码加权平均成本）：阈值类型 INDUSTRY_RELATIVE，默认阈值 1.0，说明"加权平均成本与当前价格的比值，< 1 表示当前价格低于平均成本"，数据来源 `cyq_perf.weight_avg`
   - `chip_concentration`（筹码集中度综合评分）：阈值类型 PERCENTILE，默认阈值 70，取值范围 [0, 100]，说明"基于 cost_5pct/cost_15pct/cost_50pct 综合计算的筹码集中度评分，值越高表示筹码越集中"
3. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 `cyq_perf` 表查询该股票最新的筹码数据，将上述因子值写入 Factor_Dict
4. WHEN 计算 `chip_concentration` 综合评分时，THE ScreenDataProvider SHALL 使用公式：`score = 100 - (cost_5pct × 0.5 + cost_15pct × 0.3 + cost_50pct × 0.2)`，确保评分在 [0, 100] 区间内
5. IF `cyq_perf` 表中该股票无数据记录，THEN THE ScreenDataProvider SHALL 将所有筹码因子设为 None，选股流程继续执行不中断

### 需求 14：两融数据因子扩展（基于 margin_detail / margin）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare 两融数据（`margin_detail` 融资融券交易明细、`margin` 融资融券交易汇总），新增两融因子到因子条件编辑器，以便从融资融券维度判断市场情绪和资金动向。

#### 验收标准

1. THE FactorCategory SHALL 新增 `MARGIN` 类别（两融面），用于归类所有两融因子
2. THE FACTOR_REGISTRY SHALL 新增以下两融面因子，类别为 `FactorCategory.MARGIN`：
   - `rzye_change`（融资余额变化率）：阈值类型 PERCENTILE，默认阈值 70，取值范围 [0, 100]，说明"融资余额日环比变化率的全市场百分位排名，值越高表示融资买入意愿越强"，数据来源 `margin_detail`
   - `rqye_ratio`（融券余额占比）：阈值类型 ABSOLUTE，默认阈值 5，单位 %，说明"融券余额占流通市值的比例，过高表示做空压力大"，数据来源 `margin_detail`
   - `rzrq_balance_trend`（两融余额趋势）：阈值类型 BOOLEAN，说明"近 5 日融资余额连续增加为 True，表示资金持续流入"，数据来源 `margin_detail`
   - `margin_net_buy`（融资净买入额）：阈值类型 PERCENTILE，默认阈值 75，取值范围 [0, 100]，说明"当日融资净买入额的全市场百分位排名"，数据来源 `margin_detail.rzjme`
3. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 `margin_detail` 表查询该股票最近 5 个交易日的两融数据，计算上述因子值并写入 Factor_Dict
4. WHEN 计算 `rzrq_balance_trend` 因子时，THE ScreenDataProvider SHALL 检查最近 5 个交易日的融资余额是否严格递增（每日 > 前一日）
5. IF `margin_detail` 表中该股票无数据记录，THEN THE ScreenDataProvider SHALL 将所有两融因子设为 None，选股流程继续执行不中断

### 需求 15：增强资金流因子扩展（基于 moneyflow_ths / moneyflow_dc）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare 多源资金流数据（同花顺 `moneyflow_ths`、东方财富 `moneyflow_dc`），新增更细粒度的资金流因子到因子条件编辑器，以便从超大单、大单、中单、小单多维度分析资金动向。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 新增以下资金面因子，类别为 `FactorCategory.MONEY_FLOW`：
   - `super_large_net_inflow`（超大单净流入）：阈值类型 PERCENTILE，默认阈值 80，取值范围 [0, 100]，说明"超大单（≥100万）净流入额的全市场百分位排名"，数据来源 `moneyflow_ths` 或 `moneyflow_dc`
   - `large_net_inflow`（大单净流入）：阈值类型 PERCENTILE，默认阈值 75，取值范围 [0, 100]，说明"大单（20-100万）净流入额的全市场百分位排名"
   - `small_net_outflow`（小单净流出）：阈值类型 BOOLEAN，说明"小单净流出为 True 时表示散户在卖出、主力在吸筹"
   - `money_flow_strength`（资金流强度综合评分）：阈值类型 ABSOLUTE，默认阈值 70，取值范围 [0, 100]，单位"分"，说明"基于超大单、大单、中单、小单净流入的综合评分"
   - `net_inflow_rate`（净流入占比）：阈值类型 ABSOLUTE，默认阈值 5，单位 %，说明"主力净流入额占当日总成交额的比例"
2. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 优先从 `moneyflow_ths` 表查询数据，IF `moneyflow_ths` 无数据，THEN 回退到 `moneyflow_dc` 表
3. WHEN 计算 `money_flow_strength` 综合评分时，THE ScreenDataProvider SHALL 使用公式：`score = super_large_weight × 0.4 + large_weight × 0.3 + mid_weight × 0.2 + small_outflow_weight × 0.1`，其中各分项根据净流入额的正负和大小映射到 [0, 100] 区间
4. IF `moneyflow_ths` 和 `moneyflow_dc` 表中该股票均无数据记录，THEN THE ScreenDataProvider SHALL 将所有增强资金流因子设为 None，选股流程继续执行不中断

### 需求 16：打板专题因子扩展（基于 limit_list_d / limit_step / top_list）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare 打板专题数据（涨跌停数据、连板天梯、龙虎榜），新增打板相关因子到因子条件编辑器，以便从涨停板强度和龙虎榜维度筛选短线强势股。

#### 验收标准

1. THE FactorCategory SHALL 新增 `BOARD_HIT` 类别（打板面），用于归类所有打板专题因子
2. THE FACTOR_REGISTRY SHALL 新增以下打板面因子，类别为 `FactorCategory.BOARD_HIT`：
   - `limit_up_count`（近期涨停次数）：阈值类型 ABSOLUTE，默认阈值 1，取值范围 [0, 20]，说明"近 10 个交易日内涨停次数"，数据来源 `limit_list_d`
   - `limit_up_streak`（连板天数）：阈值类型 ABSOLUTE，默认阈值 2，取值范围 [0, 15]，说明"当前连续涨停天数，0 表示非连板"，数据来源 `limit_step`
   - `limit_up_open_pct`（涨停封板率）：阈值类型 ABSOLUTE，默认阈值 80，取值范围 [0, 100]，单位 %，说明"涨停后封板时间占比，越高表示封板越坚决"，数据来源 `limit_list_d`
   - `dragon_tiger_net_buy`（龙虎榜净买入）：阈值类型 BOOLEAN，说明"近 3 日出现在龙虎榜且机构净买入为正"，数据来源 `top_list` + `top_inst`
   - `first_limit_up`（首板涨停标记）：阈值类型 BOOLEAN，说明"当日为首次涨停（非连板），适合打首板策略"，数据来源 `limit_list_d`
3. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 从 `limit_list` 表查询该股票近 10 个交易日的涨跌停数据，从 `limit_step` 表查询连板数据，从 `top_list` 表查询龙虎榜数据，计算上述因子值并写入 Factor_Dict
4. WHEN 计算 `limit_up_count` 因子时，THE ScreenDataProvider SHALL 统计 `limit_list` 表中 `limit_type` 为涨停的记录数
5. IF 相关打板数据表中该股票无数据记录，THEN THE ScreenDataProvider SHALL 将所有打板因子设为默认值（数值型为 0，布尔型为 False），选股流程继续执行不中断

### 需求 17：指数专题因子扩展（基于 idx_factor_pro / index_dailybasic）

**用户故事：** 作为量化交易者，我希望选股系统能够利用 tushare 指数专题数据（`idx_factor_pro` 指数技术面因子、`index_dailybasic` 大盘指数每日指标），新增指数维度因子到因子条件编辑器，以便从大盘环境和指数技术面维度辅助选股决策。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 新增以下板块面因子，类别为 `FactorCategory.SECTOR`：
   - `index_pe`（指数市盈率）：阈值类型 RANGE，默认区间 [10, 25]，说明"所属指数的市盈率，用于判断市场估值水平"，数据来源 `index_dailybasic.pe`
   - `index_turnover`（指数换手率）：阈值类型 RANGE，默认区间 [0.5, 3.0]，单位 %，说明"所属指数的换手率，反映市场活跃度"，数据来源 `index_dailybasic.turnover_rate`
   - `index_ma_trend`（指数均线趋势）：阈值类型 BOOLEAN，说明"所属指数短期均线在长期均线上方为 True"，数据来源 `idx_factor_pro` 或指数日线计算
   - `index_vol_ratio`（指数量比）：阈值类型 ABSOLUTE，默认阈值 1.0，说明"所属指数的量比，> 1 表示放量"，数据来源 `index_dailybasic.vol_ratio` 或指数日线计算
2. WHEN ScreenDataProvider 构建 Factor_Dict 时，THE ScreenDataProvider SHALL 根据股票所属指数（沪深300、中证500等），从 `index_dailybasic` 和 `index_tech` 表查询指数因子数据，写入 Factor_Dict
3. IF 指数因子数据不可用，THEN THE ScreenDataProvider SHALL 将所有指数因子设为 None，选股流程继续执行不中断

### 需求 18：因子条件编辑器增强

**用户故事：** 作为量化交易者，我希望因子条件编辑器能够支持所有新增因子类别（筹码面、两融面、打板面），并提供分类浏览、参数提示和配置示例，以便我能够方便地构建多维度选股策略。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 支持按新增类别（CHIP、MARGIN、BOARD_HIT）查询因子列表，`get_factors_by_category()` 函数能够正确返回各类别下的所有因子
2. THE FactorMeta SHALL 为每个新增因子提供至少一个 `examples` 配置示例，包含 `operator`、`threshold`（或 `threshold_low`/`threshold_high`）和中文说明
3. WHEN 前端请求因子列表时，THE Screen_API SHALL 返回按类别分组的因子元数据，包含 `factor_name`、`label`、`category`、`threshold_type`、`default_threshold`（或 `default_range`）、`value_min`、`value_max`、`unit`、`description`、`examples`
4. THE FactorEvaluator SHALL 能够正确评估所有新增因子类别的条件，包括 CHIP 类别的百分位排名比较、MARGIN 类别的布尔和百分位判断、BOARD_HIT 类别的绝对值和布尔判断
5. THE StrategyConfig 的 `to_dict()` 和 `from_dict()` 方法 SHALL 能够正确序列化和反序列化包含新增因子的策略配置（round-trip 属性）

### 需求 19：优化选股组合方案

**用户故事：** 作为量化交易者，我希望系统提供经过优化的预设选股组合方案，覆盖趋势追踪、价值成长、资金驱动、板块轮动、短线打板、筹码博弈等多种交易风格，以便我能够快速选择适合自己交易风格的策略组合。

#### 验收标准

1. THE STRATEGY_EXAMPLES SHALL 新增以下优化选股组合方案（在现有 12 个示例基础上扩展）：
   - `筹码集中突破型`：组合筹码集中度（chip_concentration >= 70）+ 形态突破（breakout）+ 换手率区间（turnover 5%-15%），适用于中线波段
   - `两融资金驱动型`：组合融资净买入（margin_net_buy >= 75 百分位）+ 融资余额趋势（rzrq_balance_trend = True）+ 主力资金流入（money_flow >= 80 百分位）+ MA趋势（ma_trend >= 70），适用于中短线
   - `多维资金共振型`：组合超大单净流入（super_large_net_inflow >= 85 百分位）+ 大单净流入（large_net_inflow >= 80 百分位）+ 小单净流出（small_net_outflow = True）+ 资金流强度（money_flow_strength >= 75），适用于短线
   - `首板打板策略`：组合首板涨停（first_limit_up = True）+ 涨停封板率（limit_up_open_pct >= 80）+ 换手率（turnover 5%-20%）+ 龙虎榜净买入（dragon_tiger_net_buy = True，OR 逻辑），适用于超短线
   - `价值成长筹码型`：组合 ROE（roe >= 70 百分位）+ 利润增长（profit_growth >= 70 百分位）+ PE 行业相对值（pe <= 1.0）+ 筹码集中度（chip_concentration >= 60）+ MA趋势（ma_trend >= 65），适用于中长线
   - `指数增强型`：组合指数均线趋势（index_ma_trend = True）+ 板块排名（sector_rank <= 20）+ 技术指标共振（macd + rsi [55,75]）+ 资金流强度（money_flow_strength >= 70），适用于跟随大盘趋势
   - `连板接力型`：组合连板天数（limit_up_streak >= 2）+ 涨停封板率（limit_up_open_pct >= 85）+ 龙虎榜净买入（dragon_tiger_net_buy = True）+ 超大单净流入（super_large_net_inflow >= 85 百分位）+ 换手率（turnover 8%-25%），适用于超短线连板接力
   - `主力吸筹型`：组合筹码集中度（chip_concentration >= 65）+ 小单净流出（small_net_outflow = True）+ 融资余额趋势（rzrq_balance_trend = True）+ 获利比例低位（chip_winner_rate <= 30 百分位）+ MA趋势（ma_trend >= 60），适用于中短线底部吸筹
   - `技术共振型`：组合 KDJ 金叉区间（kdj_k [20,50] + kdj_d [20,50]）+ MACD 金叉（macd = True）+ RSI 强势（rsi [50,70]）+ 布林带突破（boll = True）+ 资金流强度（money_flow_strength >= 65），适用于短线波段
   - `行业轮动增强型`：组合板块排名（sector_rank <= 15，数据来源 TI 申万行业）+ 指数均线趋势（index_ma_trend = True）+ ROE（roe >= 65 百分位）+ 融资净买入（margin_net_buy >= 70 百分位）+ 形态突破（breakout = True），适用于中线行业轮动
2. WHEN 新增策略示例时，THE StrategyExample SHALL 包含完整的 `factors`、`logic`、`weights`、`enabled_modules` 和 `sector_config`（如适用）配置
3. THE STRATEGY_EXAMPLES 中每个新增组合 SHALL 使用已在 FACTOR_REGISTRY 中注册的因子名称，确保因子名称与注册表一致

### 需求 20：选股组合配置说明书

**用户故事：** 作为量化交易者，我希望每个推荐的选股组合方案都附带详细的配置说明书，包括因子构成说明、适用市场环境、参数调优建议和风险提示，以便我能够理解每个组合的设计逻辑并根据实际情况调整参数。

#### 验收标准

1. THE STRATEGY_EXAMPLES 中每个策略示例 SHALL 包含 `config_doc` 字段（字符串类型），提供该组合的配置说明书内容
2. WHEN 生成配置说明书时，THE config_doc SHALL 包含以下章节：
   - **策略概述**：一句话描述策略核心逻辑
   - **因子构成**：列出每个因子的名称、作用、默认参数和调整范围
   - **适用场景**：描述适合的市场环境（牛市/震荡/熊市）、适合的交易周期（超短线/短线/中线/中长线）、适合的标的类型
   - **参数调优建议**：针对不同市场环境给出参数调整方向（如震荡市收紧阈值、牛市放宽阈值）
   - **风险提示**：列出该策略的主要风险点和注意事项
   - **回测建议**：建议的回测时间段和评估指标
3. WHEN 前端请求策略示例列表时，THE Screen_API SHALL 返回包含 `config_doc` 字段的完整策略示例数据
4. THE config_doc 内容 SHALL 使用中文编写，格式为 Markdown 文本

### 需求 21：架构一致性保障

**用户故事：** 作为量化交易者，我希望所有新增因子和选股组合的技术实现与现有架构保持一致，以便系统的可维护性和扩展性不受影响。

#### 验收标准

1. THE 新增因子 SHALL 遵循现有 `FactorMeta` 冻结数据类模式注册到 `FACTOR_REGISTRY` 字典中，包含完整的 `factor_name`、`label`、`category`、`threshold_type`、`default_threshold`（或 `default_range`）、`description`、`examples` 字段
2. THE 新增因子的数据加载 SHALL 在 `ScreenDataProvider._build_factor_dict()` 或独立的 `_enrich_*_factors()` 异步方法中实现，遵循现有的降级容错模式（数据缺失时设默认值、记录 WARNING 日志、不中断选股流程）
3. THE 新增因子的条件评估 SHALL 通过现有 `FactorEvaluator.evaluate()` 方法处理，利用 `ThresholdType` 自动选择正确的比较逻辑，无需为新因子编写特殊评估代码
4. THE 新增 `FactorCategory` 枚举值（CHIP、MARGIN、BOARD_HIT）SHALL 在 `strategy_engine.py` 的 `FACTOR_CATEGORIES` 映射字典中注册，确保因子类别查询功能正常
5. THE 新增因子的百分位排名计算 SHALL 复用 `ScreenDataProvider._compute_percentile_ranks()` 方法，将新增的 PERCENTILE 类型因子名称加入 `percentile_factors` 列表
6. THE StrategyConfig 的序列化/反序列化 SHALL 保持向后兼容：不包含新因子的旧配置能够正常加载，包含新因子的新配置能够正确序列化为 JSONB 存储；旧配置中包含 `sector_type` 字段时反序列化不报错（参见需求 22）
7. THE 所有新增代码的注释和文档字符串 SHALL 使用中文编写，并标注对应的需求编号（如"需求 12.1"）

### 需求 22：板块面因子分类重构（适配 Tushare 数据来源体系）

**用户故事：** 作为量化交易者，我希望板块面因子的分类方式从"板块类型"（行业/概念/地区/风格）改为"数据来源"（DC/THS/TDX/TI/CI），以便板块筛选能够正确匹配 tushare 导入的板块数据，解决当前板块类型过滤匹配不上实际数据的问题。

**背景说明：** 当前系统使用 `SectorType`（INDUSTRY/CONCEPT/REGION/STYLE）作为板块筛选的必选参数，但 tushare 各数据源导入的板块数据有自己的分类体系，`sector_type` 字段值由 tushare 接口的 `type` 字段直接映射，并非系统预定义的四种类型。这导致前端因子编辑器中选择"行业板块"等类型时，无法正确匹配到 tushare 导入的板块数据（如截图所示：同花顺 TI 显示 0 板块/0 股票）。

#### 验收标准

1. THE `SectorScreenConfig` SHALL 移除 `sector_type` 必选字段，改为以 `sector_data_source` 为主维度进行板块筛选。`sector_data_source` 的可选值扩展为：`DC`（东方财富概念板块）、`THS`（同花顺行业/概念板块）、`TDX`（通达信板块）、`TI`（申万行业分类）、`CI`（中信行业分类）
2. THE `SectorStrengthFilter.compute_sector_ranks()` 方法的 `sector_type` 参数 SHALL 改为可选参数（默认值 `None`），WHEN `sector_type` 为 `None` 时，SHALL 查询该 `data_source` 下所有板块，不按板块类型过滤
3. THE `SectorStrengthFilter.map_stocks_to_sectors()` 方法的 `sector_type` 参数 SHALL 改为可选参数（默认值 `None`），WHEN `sector_type` 为 `None` 时，SHALL 查询该 `data_source` 下所有成分股映射
4. THE `DataSource` 枚举 SHALL 确保包含 `CI`（中信行业）值，支持 5 个数据来源的完整覆盖
5. THE 前端因子编辑器中板块面因子的"板块类型"下拉 SHALL 替换为"数据来源"下拉，选项为：
   - 东方财富 DC（概念板块）
   - 同花顺 THS（行业/概念板块）
   - 通达信 TDX（板块）
   - 申万行业 TI（行业分类）
   - 中信行业 CI（行业分类）
6. THE `SectorScreenConfig.from_dict()` SHALL 保持向后兼容：旧配置中包含 `sector_type` 字段时，反序列化时忽略该字段，不影响加载；默认 `sector_data_source` 从 `"DC"` 保持不变
7. THE `SectorScreenConfig.to_dict()` SHALL 不再输出 `sector_type` 字段，仅输出 `sector_data_source`、`sector_period`、`sector_top_n`
8. THE `SectorType` 枚举 SHALL 保留（不删除），但不再作为选股筛选的必选参数，仅在数据导入和板块浏览等场景中使用
9. THE 现有 12 个策略示例（STRATEGY_EXAMPLES）中包含 `sector_config.sector_type` 字段的示例（示例 3、4、8、10、11、12）SHALL 移除 `sector_type` 字段，仅保留 `sector_data_source`、`sector_period`、`sector_top_n`，确保与新的 `SectorScreenConfig.to_dict()` 输出格式一致