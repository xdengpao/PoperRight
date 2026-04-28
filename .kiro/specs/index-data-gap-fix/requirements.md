# 需求文档：指数数据缺口评估与补全

## 简介

本需求文档定义了对 PoperRight 智能选股系统中指数数据缺口的评估结果和补全方案。

**背景：** 经调研，系统中所有 6 张指数相关数据表（`index_info`、`index_weight`、`index_dailybasic`、`index_tech`、`index_global`、`market_daily_info`）以及 kline 表中的指数 K 线数据（`000001.SH`、`000300.SH`、`000905.SH`、`399001.SZ`、`399006.SZ`）全部为空（0 行）。这导致以下核心功能失效：

| 受影响功能 | 依赖的指数数据 | 失效表现 |
|-----------|--------------|---------|
| 选股引擎 4 个指数因子 | `index_dailybasic` + `index_tech` + `index_weight` | `index_pe`/`index_turnover`/`index_ma_trend`/`index_vol_ratio` 全部降级为 None |
| 回测大盘风控模拟 | kline 表中的指数 K 线 | `_evaluate_market_risk` 返回 NORMAL，风控模拟失效 |
| 回测市场环境分类 | kline 表中的指数 K 线 | `MarketEnvironmentClassifier` 无法分段，分段回测不可用 |
| 选股评估超额收益 | kline 表中的指数 K 线 | 无法计算选股结果相对基准的超额收益 |
| 前端大盘概况 | kline 表中的指数 K 线 | DB 降级路径无数据，完全依赖 AkShare 实时接口 |
| 在线风控 | 指数收盘价序列 | `MarketRiskChecker` 无指数数据输入，大盘风控形同虚设 |

**Tushare 注册表现状：** 系统已在 `tushare_registry.py` 中注册了 13 个指数相关 API，ORM 模型和存储路径均已就绪，但从未执行过导入。

## 术语表

- **指数 K 线**：大盘指数（如沪深300、上证指数）的日/周/月 K 线数据，存储在 kline 表中，symbol 格式为 `{code}.{exchange}`（如 `000001.SH`）
- **指数基本面**：指数的 PE、PB、换手率、总市值等每日指标，存储在 `index_dailybasic` 表
- **指数技术因子**：指数的 MACD、KDJ、RSI、BOLL 等预计算技术指标，存储在 `index_tech` 表
- **指数成分权重**：指数包含哪些成分股及其权重，存储在 `index_weight` 表
- **核心指数集**：选股/回测/风控所需的最小指数集合——上证指数（000001.SH）、沪深300（000300.SH）、中证500（000905.SH）、深证成指（399001.SZ）、创业板指（399006.SZ）

## 需求

---

### 需求 1：指数基本信息导入

**用户故事：** 作为量化交易员，我需要系统导入指数基本信息（名称、发布方、基日、基点），以便指数数据有元数据基础。

#### 验收标准

1. THE 系统 SHALL 通过 Tushare `index_basic` API 导入核心指数集的基本信息到 `index_info` 表
2. WHEN 导入完成后，THE `index_info` 表 SHALL 至少包含核心指数集 5 个指数的记录
3. THE 导入 SHALL 支持通过前端 Tushare 导入页面手动触发

### 需求 2：指数日线 K 线导入

**用户故事：** 作为量化交易员，我需要系统导入指数日线 K 线数据到 kline 表，以便回测引擎能进行大盘风控模拟和市场环境分类，选股评估能计算超额收益。

#### 验收标准

1. THE 系统 SHALL 通过 Tushare `index_daily` API 导入核心指数集的日线 K 线到 kline 表（TimescaleDB）
2. WHEN 导入完成后，THE kline 表 SHALL 包含核心指数集 5 个指数至少 3 年（约 750 个交易日）的日线数据
3. THE 指数 K 线的 symbol 字段 SHALL 使用标准代码格式（如 `000001.SH`），与 Tushare 注册表中 `code_format=INDEX_CODE` 的配置一致
4. THE 导入 SHALL 支持增量更新——仅导入 kline 表中该指数最新日期之后的数据
5. IF 导入过程中 Tushare API 返回错误或超时，THEN THE 系统 SHALL 按现有重试策略自动重试

### 需求 3：指数每日基本面指标导入

**用户故事：** 作为量化交易员，我需要系统导入指数每日基本面指标（PE、PB、换手率、总市值），以便选股引擎的 `index_pe` 和 `index_turnover` 因子能正常工作。

#### 验收标准

1. THE 系统 SHALL 通过 Tushare `index_dailybasic` API 导入核心指数集的每日指标到 `index_dailybasic` 表
2. WHEN 导入完成后，THE `index_dailybasic` 表 SHALL 包含核心指数集至少 1 年的每日指标数据
3. THE 导入 SHALL 使用 `by_index` 分批策略（从 `index_info` 表读取指数代码列表逐个调用 API）
4. WHEN 选股引擎 `_enrich_index_factors` 查询 `index_dailybasic` 时，SHALL 能获取到当日或最近交易日的 PE 和换手率数据

### 需求 4：指数技术面因子导入

**用户故事：** 作为量化交易员，我需要系统导入指数技术面因子（MACD、KDJ、RSI、BOLL），以便选股引擎的 `index_ma_trend` 因子能正常工作。

#### 验收标准

1. THE 系统 SHALL 通过 Tushare `idx_factor_pro` API 导入核心指数集的技术因子到 `index_tech` 表
2. WHEN 导入完成后，THE `index_tech` 表 SHALL 包含核心指数集至少 1 年的技术因子数据
3. THE 导入 SHALL 使用注册表中已配置的 `batch_by_date(1天)` 分批策略
4. WHEN 选股引擎 `_enrich_index_factors` 查询 `index_tech` 时，SHALL 能获取到当日或最近交易日的 MACD 数据

### 需求 5：指数成分权重导入

**用户故事：** 作为量化交易员，我需要系统导入指数成分股权重数据，以便选股引擎能正确判断每只股票所属的指数，从而匹配对应的指数因子。

#### 验收标准

1. THE 系统 SHALL 通过 Tushare `index_weight` API 导入沪深300（000300.SH）和中证500（000905.SH）的成分权重到 `index_weight` 表
2. WHEN 导入完成后，THE `index_weight` 表 SHALL 包含最近一个月的成分权重数据
3. WHEN 选股引擎 `_enrich_index_factors` 查询 `index_weight` 时，SHALL 能正确将股票映射到所属指数

### 需求 6：指数 K 线查询适配

**用户故事：** 作为量化交易员，我需要确保回测引擎、风控模块和选股评估能正确从 kline 表查询指数 K 线数据，不因 symbol 格式问题导致查询失败。

#### 验收标准

1. WHEN 回测引擎调用 `KlineRepository.query(symbol="000001.SH", freq="1d", ...)` 时，SHALL 能正确返回上证指数的日线数据
2. WHEN 选股评估脚本需要指数 K 线计算超额收益时，SHALL 使用标准代码格式（如 `000300.SH`）查询 kline 表
3. THE `HistoricalDataPreparer.load_index_data()` 方法 SHALL 使用沪深300（`000300.SH`）作为默认基准指数，IF 沪深300无数据 THEN 回退到上证指数（`000001.SH`）
4. THE 选股评估脚本 SHALL 在指数数据不可用时输出明确的警告信息，而非静默降级

### 需求 7：指数数据导入自动化

**用户故事：** 作为量化交易员，我需要指数数据能随日常数据同步自动更新，而非每次手动导入。

#### 验收标准

1. THE Celery Beat 调度 SHALL 新增一个指数数据同步任务，在每个交易日 16:00 自动执行
2. THE 指数同步任务 SHALL 按顺序导入：指数日线 K 线 → 指数每日基本面 → 指数技术因子
3. THE 指数同步任务 SHALL 仅导入增量数据（从各表最新日期到当天）
4. IF 任一步骤失败，THEN THE 任务 SHALL 记录 ERROR 日志并继续执行下一步骤，不阻塞整体流程
5. THE 指数成分权重 SHALL 每月 1 日自动更新一次（成分股调整频率较低）

---

### 第三部分：智能选股系统性评价对指数数据的依赖（需求 8-12）

---

### 需求 8：选股评估超额收益计算所需的指数基准

**用户故事：** 作为量化交易员，我需要选股评估系统能基于沪深300指数计算选股结果的超额收益（Alpha），以便客观衡量选股策略是否跑赢大盘。

**依赖分析：** 评估模块 `ForwardReturnCalculator` 在计算每只选股的未来收益时，同步计算同期指数收益并求差得到超额收益。`HistoricalDataPreparer.load_index_data()` 从 kline 表查询指数日线。当前 kline 表中指数数据为空，导致 `excess_return` 全部为 0，评估报告中的超额收益指标无意义。

#### 验收标准

1. WHEN 指数日线 K 线（需求 2）导入完成后，THE `ForwardReturnCalculator` SHALL 能从 kline 表查询到沪深300（`000300.SH`）的日线数据，正确计算每个持有期（T+1/3/5/10/20）的指数同期收益
2. THE `HistoricalDataPreparer.load_index_data()` SHALL 使用沪深300（`000300.SH`）作为默认基准指数
3. IF 沪深300数据不可用，THEN SHALL 回退到上证指数（`000001.SH`），并记录 WARNING 日志
4. THE 评估报告中的 `excess_return` 指标 SHALL 反映选股结果相对基准指数的真实超额收益，而非全零

### 需求 9：策略对比评价的市场环境分类所需的指数数据

**用户故事：** 作为量化交易员，我需要选股评估系统能基于指数数据将评估期划分为上涨市/震荡市/下跌市，以便按市场环境分组对比 22 个策略模板的表现。

**依赖分析：** 评估模块 `StrategyMetricsCalculator._classify_market_env()` 需要指数的 MA20、MA60 和近 20 日涨跌幅来判断市场环境。这些数据由 `HistoricalDataPreparer.load_index_data()` 从 kline 表计算得出。当前指数 K 线为空，所有交易日都被分类为"震荡市"，策略的市场环境分组评价完全失效。

#### 验收标准

1. WHEN 指数日线 K 线（需求 2）导入完成后，THE `HistoricalDataPreparer.load_index_data()` SHALL 返回包含 `close`、`ma20`、`ma60`、`change_pct_20d` 的指数数据字典
2. THE `StrategyMetricsCalculator._classify_market_env()` SHALL 能基于真实指数数据正确分类市场环境：
   - 上涨市：MA20 > MA60 且近 20 日涨幅 > 5%
   - 下跌市：MA20 < MA60 且近 20 日跌幅 > 5%
   - 震荡市：其他
3. THE 评估报告中的 `by_market_env` 分组 SHALL 包含至少 2 种不同的市场环境（而非全部为"震荡市"）

### 需求 10：选股模拟中大盘风控所需的指数收盘价序列

**用户故事：** 作为量化交易员，我需要选股模拟器在历史回放时能正确模拟大盘风控逻辑，以便评估风控规则对选股结果的实际影响。

**依赖分析：** 评估模块 `ScreeningSimulator._extract_index_closes()` 从指数数据中提取最近 60 日收盘价序列，传递给 `ScreenExecutor.run_eod_screen()` 的 `index_closes` 参数。`ScreenExecutor` 内部调用 `MarketRiskChecker` 判断大盘风险等级（NORMAL/CAUTION/DANGER）。当前指数数据为空，`index_closes` 为 None，大盘风控在模拟中完全跳过，评估结果无法反映风控对选股质量的真实影响。

#### 验收标准

1. WHEN 指数日线 K 线（需求 2）导入完成后，THE `ScreeningSimulator._extract_index_closes()` SHALL 能提取截至每个评估日的最近 60 日指数收盘价序列
2. THE `ScreenExecutor.run_eod_screen()` SHALL 接收到有效的 `index_closes` 参数，使大盘风控逻辑在模拟中正常生效
3. THE 评估报告中的风控有效性分析 SHALL 能区分 NORMAL/CAUTION/DANGER 三种大盘状态下的选股表现差异

### 需求 11：选股引擎指数因子评估所需的完整数据链

**用户故事：** 作为量化交易员，我需要选股引擎的 4 个指数因子（`index_pe`、`index_turnover`、`index_ma_trend`、`index_vol_ratio`）在评估期内有真实数据，以便因子预测力评估（IC/IR）能覆盖这些因子。

**依赖分析：** 评估模块 `FactorMetricsCalculator` 对所有 52 个注册因子计算 IC/IR。当前 4 个指数因子在 factor_dict 中全部为 None（因 `index_dailybasic`、`index_tech`、`index_weight` 三张表为空），导致这 4 个因子的 IC 无法计算，被自动归类为"无效因子"——但这是数据缺失导致的误判，而非因子本身无效。

#### 验收标准

1. WHEN 指数基本面（需求 3）、指数技术因子（需求 4）、指数成分权重（需求 5）导入完成后，THE 选股引擎 `_enrich_index_factors` SHALL 能为每只股票填充 `index_pe`、`index_turnover`、`index_ma_trend` 的真实值
2. THE 评估模块 `FactorMetricsCalculator` SHALL 能对 `index_pe`、`index_turnover`、`index_ma_trend` 计算有效的 IC/IR 值（而非因数据全 None 而跳过）
3. THE `index_vol_ratio` 因子当前代码中硬编码为 None（`screen_data_provider.py` 中注释说明 vol_ratio 不在 index_dailybasic 中），SHALL 在本次修复中补全其计算逻辑——从指数日线 K 线计算量比（当日成交量 / 近 5 日平均成交量）

### 需求 12：评估报告指数数据完整性检查

**用户故事：** 作为量化交易员，我需要评估脚本在运行前自动检查指数数据的完整性，在数据不足时给出明确提示而非产出误导性的评估结果。

#### 验收标准

1. THE 评估脚本 SHALL 在数据准备阶段检查以下指数数据的可用性：
   - kline 表中基准指数（`000300.SH` 或 `000001.SH`）在评估期内的日线数据覆盖率
   - `index_dailybasic` 表中核心指数在评估期内的数据覆盖率
   - `index_tech` 表中核心指数在评估期内的数据覆盖率
   - `index_weight` 表中沪深300/中证500的最新成分权重日期
2. IF 基准指数 K 线覆盖率 < 80%，THEN THE 评估脚本 SHALL 输出 ERROR 级别警告：`"基准指数数据不足（覆盖率 XX%），超额收益和市场环境分类将不准确。请先导入指数数据：python scripts/evaluate_screener.py --help"`
3. IF `index_dailybasic` 或 `index_tech` 覆盖率 < 50%，THEN THE 评估脚本 SHALL 输出 WARNING：`"指数因子数据不足，index_pe/index_turnover/index_ma_trend 的 IC 评估将不完整"`
4. THE 评估报告的 `summary` 章节 SHALL 包含 `index_data_status` 字段，标明各项指数数据的覆盖率和可用状态
