# 需求文档：回测引擎因子对齐优化

## 简介

当前回测引擎（`BacktestEngine`）的买入信号生成方法（`_generate_buy_signals` 和 `_generate_buy_signals_optimized`）在构建因子字典时存在严重的数据缺失问题：

1. **基本面因子硬编码为 None**：`pe_ttm: None, pb: None, roe: None, market_cap: None`，未从 `StockInfo` 表加载实际数据（注：基本面数据并非所有用户都能获取，应作为可选项）
2. **资金面因子硬编码为 False**：`money_flow: False, large_order: False`，未从 `money_flow` 表查询主力资金和大单数据（注：资金面数据并非所有用户都能获取，应作为可选项）
3. **缺少百分位排名字段**：未计算 `_pctl` 后缀字段（如 `money_flow_pctl`、`roe_pctl`、`market_cap_pctl` 等）
4. **缺少行业相对值字段**：未计算 `_ind_rel` 后缀字段（如 `pe_ind_rel`、`pb_ind_rel`）
5. **缺少板块强势数据**：未加载 `SectorKline` / `SectorConstituent` 数据，`sector_rank` 和 `sector_trend` 字段缺失
6. **缺少利润增长率和营收增长率**：`profit_growth` 和 `revenue_growth` 字段未从外部数据源加载
7. **缺少 Tushare 导入的 33 个因子**：stk_factor 表因子（KDJ/CCI/WR/TRIX/BIAS）、筹码因子（cyq_perf）、两融因子（margin_detail）、增强资金流因子（moneyflow_ths/dc）、打板因子（limit_list/step/top_list）、指数因子（index_dailybasic/tech/weight）、本地计算因子（PSY/OBV）全部缺失
8. **缺少信号增强字段**：`macd_strength`、`macd_signal_type`、`boll_near_upper_band`、`boll_hold_days`、`rsi_current`、`rsi_consecutive_rising`、`daily_change_pct`、`change_pct_3d`、`breakout_list` 等字段缺失，导致信号质量元数据降级
9. **涨跌停价格计算错误**：创业板（300xxx）和科创板（688xxx）股票应使用 ±20% 涨跌停限制，当前统一使用 ±10%
10. **持仓天数计算偏差**：`buy_trade_day_index` 记录的是信号日而非实际买入日，导致持仓天数多算 1 天
11. **DANGER 风控行为不一致**：回测在 DANGER 状态下完全阻断买入，但实时选股允许 trend_score >= 95 的强势股通过
12. **优化路径趋势评分算法偏差（严重）**：`_precompute_indicators` 中的距离评分使用简单线性公式（`50 + pct_above * 10`），而 `score_ma_trend` 使用钟形曲线（`_bell_curve_distance_score`），两者在相同输入下产生显著不同的分数（如 pct_above=0% 时分别得 50 分和 100 分）
13. **优化路径斜率评分算法偏差（严重）**：`_precompute_indicators` 对所有均线周期使用等权平均且忽略 `slope_threshold`，而 `score_ma_trend` 对短期均线（5/10 日）使用 2 倍权重并支持 `slope_threshold` 过滤
14. **实时选股忽略策略自定义指标参数**：`ScreenDataProvider._build_factor_dict()` 调用 `detect_macd_signal(closes_float)` 等函数时使用默认参数，忽略策略配置中的自定义参数（如 `macd_fast=8`），导致实时选股与回测对非默认参数策略产生不同信号
15. **非优化路径缺少 slope_threshold 传递**：`_generate_buy_signals` 调用 `score_ma_trend(closes_f, ma_periods)` 时未传递 `slope_threshold` 参数

这导致 `factor-editor-optimization` 功能中定义的策略示例在回测时无法正确执行——52 个注册因子中仅有 7 个技术面因子（ma_trend/ma_support/macd/boll/rsi/dma/breakout）能在回测中获得正确数据，其余 45 个因子全部缺失或硬编码。更严重的是，生产环境使用的优化路径（`_generate_buy_signals_optimized`）的趋势评分算法与标准库函数 `score_ma_trend` 存在系统性偏差，导致回测结果与实时选股产生不可预期的差异。

本功能将对回测引擎进行全面的因子数据对齐和算法一致性优化，使回测环境中的因子字典和评分算法与实时选股环境（`ScreenDataProvider`）保持完全一致。

## 术语表

- **BacktestEngine（回测引擎）**：历史策略回测核心服务，位于 `app/services/backtest_engine.py`，负责模拟历史交易并计算绩效指标
- **BacktestFactorProvider（回测因子数据提供器）**：本功能新增的服务模块，负责在回测环境中加载和计算完整的因子数据，对齐 ScreenDataProvider 的因子字典结构
- **ScreenDataProvider（选股数据提供服务）**：实时选股环境中的数据加载服务，已实现百分位排名、行业相对值和板块强势数据的计算逻辑
- **FactorEvaluator（因子评估器）**：根据因子的阈值类型（threshold_type）自动选择正确的比较字段进行因子条件评估
- **FACTOR_REGISTRY（因子元数据注册表）**：定义所有因子的阈值类型、默认值和取值范围的常量字典
- **StockInfo（股票基础信息）**：PostgreSQL 表，存储股票的 PE/PB/ROE/市值等基本面数据
- **MoneyFlow（资金流向）**：PostgreSQL 表 `money_flow`，存储个股每日主力资金净流入、大单成交占比等资金面数据
- **SectorKline（板块行情）**：TimescaleDB 表，存储板块指数日K线行情数据
- **SectorConstituent（板块成分）**：PostgreSQL 表，存储板块成分股每日快照数据
- **IndicatorCache（指标缓存）**：回测引擎中预计算的技术指标时间序列缓存，用于优化路径的快速查表
- **BacktestTask（回测任务）**：Celery 异步任务，使用同步数据库访问执行回测
- **PercentileRank（百分位排名）**：将因子原始值转换为 0-100 的排名值，用于 percentile 类型阈值比较
- **IndustryRelativeValue（行业相对值）**：将因子原始值除以行业中位数，用于 industry_relative 类型阈值比较
- **StkFactor（技术面因子表）**：Tushare 导入的 PostgreSQL 表 `stk_factor`，存储 KDJ/CCI/WR/TRIX/BIAS 等预计算技术因子，使用 `ts_code` 字段（带后缀格式如 `"000001.SZ"`）
- **CyqPerf（筹码数据表）**：Tushare 导入的 PostgreSQL 表 `cyq_perf`，存储筹码集中度和获利比例数据
- **MarginDetail（两融数据表）**：Tushare 导入的 PostgreSQL 表 `margin_detail`，存储融资融券交易明细
- **MoneyflowThs/MoneyflowDc（增强资金流表）**：Tushare 导入的 PostgreSQL 表，存储按订单大小分类的多维度资金流数据
- **LimitList/LimitStep/TopList（打板数据表）**：Tushare 导入的 PostgreSQL 表，存储涨跌停和龙虎榜数据
- **IndexDailybasic/IndexTech/IndexWeight（指数数据表）**：Tushare 导入的 PostgreSQL 表，存储指数每日指标、技术因子和成分权重
- **_strip_market_suffix**：代码格式转换辅助函数，将 Tushare `ts_code`（如 `"000001.SZ"`）转换为纯数字格式（`"000001"`），已在 `screener-data-alignment-fix` 中实现

## 需求

### 需求 1：回测环境基本面数据加载（可选）

**用户故事：** 作为量化交易员，由于不一定能获取到所有股票的基本面数据，我需要在回测参数中通过可选开关选择是否加载股票的基本面数据（PE/PB/ROE/市值/利润增长率/营收增长率），默认不加载，以便在数据可用时使用基本面因子的策略能获得正确的评估结果。

#### 验收标准

1. THE BacktestConfig SHALL 新增 `enable_fundamental_data` 布尔字段，默认值为 False，用于控制是否在回测中加载基本面数据
2. WHEN `enable_fundamental_data` 为 True 时，THE BacktestTask SHALL 从 PostgreSQL `stock_info` 表批量查询所有回测股票的基本面数据（pe_ttm、pb、roe、market_cap），构建 symbol → 基本面数据 的映射字典
3. WHEN `enable_fundamental_data` 为 True 且回测引擎构建因子字典时，THE BacktestEngine SHALL 使用 StockInfo 映射字典填充 `pe_ttm`、`pb`、`roe`、`market_cap` 字段的实际值，替代当前硬编码的 None
4. WHEN `enable_fundamental_data` 为 False 时，THE BacktestEngine SHALL 保持当前行为，将基本面字段设为 None
5. IF `enable_fundamental_data` 为 True 但某只股票在 `stock_info` 表中不存在或基本面字段为空，THEN THE BacktestEngine SHALL 将对应因子字段设为 None，FactorEvaluator 将该因子视为不通过

### 需求 2：回测环境资金面数据加载（可选）

**用户故事：** 作为量化交易员，由于不一定能获取到所有股票的资金面数据，我需要在回测参数中通过可选开关选择是否加载股票的资金流向数据（主力资金净流入、大单成交占比），默认不加载，以便在数据可用时使用资金面因子的策略在回测中能获得正确的评估结果。

#### 验收标准

1. THE BacktestConfig SHALL 新增 `enable_money_flow_data` 布尔字段，默认值为 False，用于控制是否在回测中加载资金面数据
2. WHEN `enable_money_flow_data` 为 True 时，THE BacktestTask SHALL 从 PostgreSQL `money_flow` 表批量查询回测日期范围内所有股票的资金流向数据（main_net_inflow、large_order_ratio），构建 symbol → {trade_date → MoneyFlowRecord} 的嵌套映射字典
3. WHEN `enable_money_flow_data` 为 True 且回测引擎在某个交易日构建因子字典时，THE BacktestEngine SHALL 从资金流向映射字典中查询该股票在当日（或最近交易日）的 `main_net_inflow` 值填充 `money_flow` 字段，查询 `large_order_ratio` 值填充 `large_order` 字段
4. WHEN `enable_money_flow_data` 为 False 时，THE BacktestEngine SHALL 将 `money_flow` 设为 None、`large_order` 设为 None（而非当前硬编码的 False）
5. IF `enable_money_flow_data` 为 True 但某只股票在某个交易日无资金流向数据，THEN THE BacktestEngine SHALL 将 `money_flow` 设为 None、`large_order` 设为 None
6. THE BacktestEngine SHALL 同时计算日均成交额（`volume_price`）字段，基于因子字典中已有的 `amounts` 序列计算近 20 日日均成交额（volume_price 不依赖 money_flow 表，始终计算）

### 需求 3：回测环境百分位排名计算

**用户故事：** 作为量化交易员，我需要回测引擎在每个交易日计算全市场股票各因子的百分位排名，以便使用 percentile 类型阈值的策略在回测中能获得正确的评估结果。

#### 验收标准

1. WHEN 回测引擎在某个交易日完成所有股票的因子字典构建后，THE BacktestEngine SHALL 仅对源数据已启用且可用的 percentile 类型因子计算当日回测股票池内的百分位排名。具体而言：
   - `volume_price_pctl`：始终计算（volume_price 基于 K 线数据，不依赖可选数据源）
   - `money_flow_pctl`：仅当 `enable_money_flow_data` 为 True 时计算，否则设为 None
   - `roe_pctl`、`profit_growth_pctl`、`market_cap_pctl`、`revenue_growth_pctl`：仅当 `enable_fundamental_data` 为 True 时计算，否则设为 None
2. THE BacktestEngine SHALL 复用 ScreenDataProvider._compute_percentile_ranks 的纯函数逻辑进行百分位排名计算，确保回测环境与实时选股环境的计算结果一致
3. THE BacktestEngine SHALL 将百分位排名值写入因子字典的 `_pctl` 后缀字段（如 `money_flow_pctl`、`roe_pctl`），与 ScreenDataProvider 的字段命名保持一致
4. WHEN 计算百分位排名时，THE BacktestEngine SHALL 排除因子值为 None 的股票，仅对有效值进行排名，排名值保证在 [0, 100] 闭区间内
5. THE BacktestEngine SHALL 使用与 ScreenDataProvider 相同的升序百分位公式和平均排名（average tie-breaking）策略

### 需求 4：回测环境行业相对值计算

**用户故事：** 作为量化交易员，我需要回测引擎在基本面数据可用时计算基本面因子的行业相对值，以便使用 industry_relative 类型阈值的策略在回测中能获得正确的评估结果。

#### 验收标准

1. WHEN 回测任务启动且 `enable_fundamental_data` 为 True 时，THE BacktestTask SHALL 从 SectorConstituent 表查询行业板块（sector_type = INDUSTRY）的成分股数据，构建 symbol → 行业板块代码 的映射字典
2. WHEN `enable_fundamental_data` 为 True 且回测引擎在某个交易日完成因子字典构建后，THE BacktestEngine SHALL 对所有 industry_relative 类型因子（pe、pb）计算行业相对值（个股值 / 行业中位数）
3. WHEN `enable_fundamental_data` 为 False 时，THE BacktestEngine SHALL 将 `pe_ind_rel` 和 `pb_ind_rel` 设为 None，跳过行业相对值计算
4. THE BacktestEngine SHALL 复用 ScreenDataProvider._compute_industry_relative_values 的纯函数逻辑进行行业相对值计算，确保回测环境与实时选股环境的计算结果一致
5. THE BacktestEngine SHALL 将行业相对值写入因子字典的 `_ind_rel` 后缀字段（如 `pe_ind_rel`、`pb_ind_rel`），与 ScreenDataProvider 的字段命名保持一致
6. IF 某只股票未找到所属行业板块或行业中位数为零，THEN THE BacktestEngine SHALL 将该股票的行业相对值设为 None

### 需求 5：回测环境板块强势数据加载

**用户故事：** 作为量化交易员，我需要回测引擎在每个交易日加载板块强势数据（板块涨幅排名、板块趋势），以便使用板块面因子的策略在回测中能获得正确的评估结果。

#### 验收标准

1. WHEN 回测任务启动时，THE BacktestTask SHALL 从 TimescaleDB `sector_kline` 表批量查询回测日期范围内指定数据来源和板块类型的板块行情数据
2. WHEN 回测任务启动时，THE BacktestTask SHALL 从 PostgreSQL `sector_constituent` 表查询板块成分股数据，构建 symbol → [sector_code] 映射
3. WHEN 回测引擎在某个交易日构建因子字典时，THE BacktestEngine SHALL 使用 SectorStrengthFilter 的纯函数方法计算当日的板块涨跌幅排名和多头趋势标志
4. THE BacktestEngine SHALL 将板块排名和趋势信息写入因子字典的 `sector_rank`（int | None）和 `sector_trend`（bool）字段
5. THE BacktestEngine SHALL 从 BacktestConfig.strategy_config.sector_config 读取板块筛选配置（sector_data_source、sector_type、sector_period、sector_top_n），使用与实时选股相同的配置参数
6. IF 板块行情数据不可用（未导入或查询失败），THEN THE BacktestEngine SHALL 记录警告日志并跳过板块强势数据加载，将 `sector_rank` 设为 None、`sector_trend` 设为 False，不阻塞回测执行

### 需求 6：因子字典完整性对齐

**用户故事：** 作为量化交易员，我需要回测引擎构建的因子字典与实时选股环境（ScreenDataProvider）的因子字典结构完全一致，以便所有策略在回测和实时选股中产生一致的评估结果。

#### 验收标准

1. THE BacktestEngine 构建的因子字典 SHALL 包含以下所有字段，与 ScreenDataProvider._build_factor_dict 的输出结构对齐：
   - 基本面原始值：`pe_ttm`、`pb`、`roe`、`market_cap`（当 `enable_fundamental_data` 为 False 时全部为 None）
   - 资金面原始值：`money_flow`（主力资金净流入金额）、`large_order`（大单成交占比百分比）（当 `enable_money_flow_data` 为 False 时全部为 None）、`volume_price`（近 20 日日均成交额，始终计算）
   - 百分位排名：`money_flow_pctl`、`volume_price_pctl`、`roe_pctl`、`profit_growth_pctl`、`market_cap_pctl`、`revenue_growth_pctl`（仅对源数据已启用的因子计算，未启用的设为 None）
   - 行业相对值：`pe_ind_rel`、`pb_ind_rel`（仅当 `enable_fundamental_data` 为 True 时计算，否则为 None）
   - 板块强势：`sector_rank`、`sector_trend`
2. THE BacktestEngine 的 `_generate_buy_signals` 方法和 `_generate_buy_signals_optimized` 方法 SHALL 同时更新，确保两条路径产生一致的因子字典
3. WHEN FactorEvaluator 评估回测环境中的因子条件时，THE FactorEvaluator SHALL 能够从因子字典中正确读取 `_pctl`、`_ind_rel` 和板块字段，与实时选股环境的行为一致

### 需求 7：优化路径因子数据缓存

**用户故事：** 作为量化交易员，我需要回测引擎的优化路径（`_generate_buy_signals_optimized`）能够高效地缓存和查询新增因子数据，以便长时间跨度的回测不会因为新增因子计算而显著降低性能。

#### 验收标准

1. THE BacktestEngine SHALL 在回测初始化阶段根据 BacktestConfig 的可选开关一次性加载对应的数据到内存中（`enable_fundamental_data` 为 True 时加载基本面数据，`enable_money_flow_data` 为 True 时加载资金流向数据，板块数据始终加载），避免在每个交易日重复查询数据库
2. WHEN 使用优化路径时，THE BacktestEngine SHALL 从预加载的内存数据中按交易日和股票代码查询因子值，时间复杂度为 O(1) 的字典查表
3. THE BacktestEngine SHALL 在每个交易日构建完所有股票的因子字典后，批量计算百分位排名和行业相对值，而非逐只股票计算
4. WHEN 回测跨度超过 1 年（约 250 个交易日）且股票池超过 3000 只时，THE BacktestEngine 的单个交易日因子构建耗时 SHALL 保持在合理范围内（不超过原有技术指标计算耗时的 50%）

### 需求 8：回测任务数据加载扩展

**用户故事：** 作为量化交易员，我需要回测 Celery 任务在启动时加载新增的因子数据源，以便回测引擎能够获得完整的因子数据。

#### 验收标准

1. THE BacktestTask SHALL 在加载 K 线数据后，根据 BacktestConfig 中的可选开关增加以下数据加载步骤：
   - 当 `enable_fundamental_data` 为 True 时：从 `stock_info` 表查询所有回测股票的基本面数据
   - 当 `enable_money_flow_data` 为 True 时：从 `money_flow` 表查询回测日期范围内的资金流向数据
   - 从 `sector_kline` 表查询回测日期范围内的板块行情数据（板块数据始终加载，不受上述开关控制）
   - 从 `sector_constituent` 表查询板块成分股数据
   - 当 `enable_fundamental_data` 为 True 时：从 `sector_info` 表查询板块元数据（用于行业映射）
2. THE BacktestTask SHALL 将加载的数据以字典形式传递给 BacktestEngine.run_backtest 方法，通过新增参数传入
3. IF 任何新增数据源加载失败，THEN THE BacktestTask SHALL 记录警告日志并继续执行回测，使用空字典作为默认值，确保回测不会因数据加载失败而中断
4. THE BacktestTask SHALL 使用同步数据库访问（与现有 K 线加载一致），通过 SQLAlchemy 同步 Session 查询 PostgreSQL 和 TimescaleDB

### 需求 9：向后兼容性保障

**用户故事：** 作为量化交易员，我需要已有的回测配置和不使用新因子类型的策略在优化后仍能正常运行，以便不影响现有的回测工作流。

#### 验收标准

1. WHEN 回测配置中的策略不包含 percentile、industry_relative 或 sector 类型因子时，THE BacktestEngine SHALL 保持与优化前完全一致的回测结果
2. WHEN BacktestEngine.run_backtest 方法未收到新增的数据参数（基本面数据、资金流向数据、板块数据）时，THE BacktestEngine SHALL 回退到当前行为（基本面为 None、资金面为 None），不报错
3. THE BacktestEngine.run_backtest 方法的新增参数 SHALL 全部使用默认值 None，确保现有调用方无需修改
4. WHEN 加载不包含 sector_config 字段的旧版 StrategyConfig 时，THE BacktestEngine SHALL 使用默认的 SectorScreenConfig（sector_data_source="DC", sector_type="CONCEPT", sector_period=5, sector_top_n=30）
5. WHEN 加载不包含 `enable_fundamental_data` 或 `enable_money_flow_data` 字段的旧版 BacktestConfig 时，THE BacktestConfig SHALL 使用默认值 False，保持与优化前一致的行为

### 需求 10：回测性能优化

**用户故事：** 作为量化交易员，我需要新增因子数据的加载和计算不会显著增加回测的总执行时间，以便长时间跨度的回测仍然可以在合理时间内完成。

#### 验收标准

1. THE BacktestTask SHALL 使用批量 SQL 查询加载数据（当 `enable_fundamental_data` 为 True 时单次查询加载所有股票的基本面数据、当 `enable_money_flow_data` 为 True 时单次查询加载日期范围内的资金流向数据），避免逐只股票查询
2. THE BacktestEngine SHALL 将资金流向数据组织为 {symbol: {trade_date_str: record}} 的嵌套字典结构，支持 O(1) 的按日期查询
3. THE BacktestEngine SHALL 将板块行情数据按交易日分组预处理，避免在每个交易日重复计算板块排名
4. WHEN 百分位排名计算涉及排序操作时，THE BacktestEngine SHALL 对每个因子仅执行一次排序（O(N log N)），而非对每只股票逐一计算排名

### 需求 11：Tushare 导入因子数据加载（可选）

**用户故事：** 作为量化交易员，我希望回测引擎能加载已导入的 Tushare 因子数据（技术面专业因子、筹码、两融、增强资金流、打板、指数），以便使用这些因子的策略在回测中能获得正确的评估结果。

#### 验收标准

1. THE BacktestConfig SHALL 新增 `enable_tushare_factors` 布尔字段，默认值为 False，用于控制是否在回测中加载 Tushare 导入的因子数据
2. WHEN `enable_tushare_factors` 为 True 时，THE BacktestTask SHALL 从以下 PostgreSQL 表批量查询回测日期范围内的数据：
   - `stk_factor` 表：KDJ（kdj_k/kdj_d/kdj_j）、CCI、WR、TRIX、BIAS
   - `cyq_perf` 表：chip_winner_rate、chip_cost_5pct/15pct/50pct、chip_weight_avg
   - `margin_detail` 表：rzye_change、rqye_ratio、rzrq_balance_trend、margin_net_buy
   - `moneyflow_ths`/`moneyflow_dc` 表：super_large_net_inflow、large_net_inflow、small_net_outflow、money_flow_strength、net_inflow_rate
   - `limit_list`/`limit_step`/`top_list` 表：limit_up_count、limit_up_streak、limit_up_open_pct、dragon_tiger_net_buy、first_limit_up
   - `index_dailybasic`/`index_tech`/`index_weight` 表：index_pe、index_turnover、index_ma_trend、index_vol_ratio
3. THE BacktestTask SHALL 在构建 Tushare 因子数据映射时，使用 `_strip_market_suffix()` 将 `ts_code` 转换为纯数字格式，确保与回测引擎的 symbol 格式一致
4. WHEN `enable_tushare_factors` 为 False 时，THE BacktestEngine SHALL 将所有 Tushare 因子字段设为 None
5. THE BacktestFactorProvider SHALL 新增 `_fill_tushare_factor_fields()` 方法，从预加载的数据映射中按交易日和股票代码填充因子字典
6. THE BacktestFactorProvider SHALL 同时计算 PSY 和 OBV 因子（基于 K 线数据本地计算，不依赖 Tushare 数据），复用 `indicators.py` 中的 `calculate_psy()` 和 `calculate_obv_signal()` 函数

### 需求 12：信号增强字段补全

**用户故事：** 作为量化交易员，我希望回测引擎构建的因子字典包含与实时选股一致的信号增强字段，以便回测中的信号质量评估、趋势评分计算和信号描述与实时选股保持一致。

#### 验收标准

1. THE BacktestEngine 构建的因子字典 SHALL 包含以下信号增强字段：
   - `macd_strength`：MACD 信号强度（SignalStrength 枚举），从 `detect_macd_signal()` 返回的 `MACDSignalResult.strength` 获取
   - `macd_signal_type`：MACD 信号类型（`"above_zero"` / `"below_zero_second"` / `"none"`），从 `MACDSignalResult.signal_type` 获取
   - `boll_near_upper_band`：布林带接近上轨风险标志（bool），从 `detect_boll_signal()` 返回的 `BOLLSignalResult.near_upper_band` 获取
   - `boll_hold_days`：布林带连续站稳中轨天数（int），从 `BOLLSignalResult.hold_days` 获取
   - `rsi_current`：当前 RSI 数值（float），从 `detect_rsi_signal()` 返回的 `RSISignalResult.current_rsi` 获取
   - `rsi_consecutive_rising`：RSI 连续上升天数（int），从 `RSISignalResult.consecutive_rising` 获取
2. THE BacktestEngine 构建的因子字典 SHALL 包含 `daily_change_pct` 和 `change_pct_3d` 字段，计算逻辑与 `ScreenDataProvider._build_factor_dict()` 一致
3. THE BacktestEngine 构建的因子字典 SHALL 包含 `breakout_list` 字段（所有突破信号列表），使用与 `ScreenDataProvider._detect_all_breakouts()` 相同的数据窗口前移方式进行假突破检测
4. THE `_generate_buy_signals` 和 `_generate_buy_signals_optimized` 两条路径 SHALL 同时更新，确保信号增强字段一致

### 需求 13：涨跌停价格计算修正

**用户故事：** 作为量化交易员，我希望回测引擎能正确计算创业板和科创板股票的涨跌停价格，以便回测中的买入跳过和卖出延迟逻辑对这些股票产生正确的判断。

#### 验收标准

1. THE BacktestEngine `_calc_limit_prices()` 方法 SHALL 接受 `symbol` 参数，根据股票代码前缀判断涨跌停幅度：
   - 创业板（symbol 以 `"300"` 开头）：±20%
   - 科创板（symbol 以 `"688"` 开头）：±20%
   - 北交所（symbol 以 `"8"` 或 `"4"` 开头）：±30%
   - 其他（主板）：±10%
2. WHEN 判断买入是否因涨停而跳过时（`open_price >= limit_up`），THE BacktestEngine SHALL 使用正确的涨跌停幅度
3. WHEN 判断卖出是否因跌停而延迟时（`open_price <= limit_down`），THE BacktestEngine SHALL 使用正确的涨跌停幅度
4. WHEN 跟踪持仓最高收盘价时（`close < limit_up` 条件），THE BacktestEngine SHALL 使用正确的涨跌停幅度

### 需求 14：持仓天数计算修正

**用户故事：** 作为量化交易员，我希望回测引擎的持仓天数计算从实际买入执行日开始计算，以便最大持仓天数限制与预期一致。

#### 验收标准

1. THE BacktestEngine SHALL 将 `_BacktestPosition.buy_trade_day_index` 设置为实际买入执行日的交易日序号（即信号日的下一个交易日），而非信号生成日的序号
2. WHEN 检查最大持仓天数时（`state_trade_day_index - position.buy_trade_day_index > config.max_holding_days`），THE BacktestEngine SHALL 基于实际买入日计算持仓天数，确保持仓恰好 `max_holding_days` 个交易日后触发强制卖出
3. THE BacktestEngine SHALL 同步修正 `HoldingContext.entry_bar_index` 的赋值，使用实际买入执行日的序号

### 需求 15：DANGER 风控行为对齐

**用户故事：** 作为量化交易员，我希望回测引擎在 DANGER 大盘风控状态下的行为与实时选股一致，以便回测结果能准确反映实盘表现。

#### 验收标准

1. WHEN 大盘风险等级为 DANGER 时，THE BacktestEngine SHALL 不再完全阻断买入信号，而是将信号传递给 ScreenExecutor，由 ScreenExecutor 的 `_apply_risk_filters_pure()` 方法按 `trend_score >= 95` 的阈值过滤
2. THE BacktestEngine SHALL 将 `index_closes` 参数传递给 `ScreenExecutor.run_eod_screen()`，使 ScreenExecutor 内部的大盘风控逻辑能正确执行
3. THE BacktestEngine SHALL 移除 `_generate_buy_signals` 和 `_generate_buy_signals_optimized` 方法开头的 `if market_risk_state == "DANGER": return []` 逻辑，改为在 ScreenExecutor 内部统一处理

### 需求 16：优化路径趋势评分算法修正（严重）

**用户故事：** 作为量化交易员，我希望回测引擎的优化路径（`_precompute_indicators`）使用与标准库函数 `score_ma_trend` 完全一致的评分算法，以便回测结果与实时选股产生一致的趋势评分。

#### 验收标准

1. THE BacktestEngine `_precompute_indicators` 方法的距离评分计算 SHALL 使用 `ma_trend.py` 中的 `_bell_curve_distance_score()` 函数替代当前的线性公式（`50 + pct_above * 10`），确保距离评分与 `score_ma_trend` 完全一致
2. THE BacktestEngine `_precompute_indicators` 方法的斜率评分计算 SHALL 使用与 `score_ma_trend` 相同的加权策略：短期均线（5 日、10 日）使用 `_SHORT_TERM_SLOPE_WEIGHT = 2.0` 权重，长期均线使用 `_LONG_TERM_SLOPE_WEIGHT = 1.0` 权重，替代当前的等权平均
3. THE BacktestEngine `_precompute_indicators` 方法 SHALL 支持 `slope_threshold` 参数，从 `StrategyConfig.ma_trend.slope_threshold` 读取，低于阈值的斜率在评分中视为 0，与 `score_ma_trend` 的行为一致
4. WHEN 优化路径和非优化路径使用相同的 K 线数据和策略配置时，两条路径生成的 `ma_trend` 评分 SHALL 完全一致（数值误差不超过 0.01）
5. THE BacktestEngine 优化路径 SHALL 直接调用 `score_ma_trend` 函数进行逐日评分（通过预计算 MA 序列后逐日切片调用），而非内联重新实现评分逻辑，从根本上消除算法偏差的可能性

### 需求 17：实时选股指标参数一致性修复

**用户故事：** 作为量化交易员，我希望实时选股和回测在计算技术指标时使用相同的参数来源（策略配置中的自定义参数），以便策略参数调优在两个环境中产生一致的效果。

#### 验收标准

1. THE ScreenDataProvider `_build_factor_dict()` 方法 SHALL 从 `strategy_config` 中读取 `indicator_params` 配置，将自定义参数传递给 `detect_macd_signal()`、`detect_boll_signal()`、`detect_rsi_signal()` 和 `calculate_dma()` 函数，替代当前使用默认参数的行为
2. WHEN 策略配置中 `indicator_params.macd_fast = 8` 时，THE ScreenDataProvider SHALL 调用 `detect_macd_signal(closes_float, fast_period=8, ...)`，而非 `detect_macd_signal(closes_float)`
3. THE BacktestEngine `_generate_buy_signals` 方法 SHALL 保持现有的自定义参数传递行为不变（已正确实现）
4. THE BacktestEngine `_generate_buy_signals` 方法 SHALL 将 `slope_threshold` 参数从 `config.strategy_config.ma_trend.slope_threshold` 传递给 `score_ma_trend()` 函数

### 需求 18：回测 API 层扩展

**用户故事：** 作为量化交易员，我希望通过回测 API 和前端界面控制是否加载基本面、资金面和 Tushare 因子数据，以便灵活选择回测的数据丰富度。

#### 验收标准

1. THE `BacktestRunRequest` Pydantic 模型 SHALL 新增三个可选布尔字段：`enable_fundamental_data`（默认 False）、`enable_money_flow_data`（默认 False）、`enable_tushare_factors`（默认 False）
2. THE `POST /api/v1/backtest/run` 接口 SHALL 将这三个字段传递给 Celery 任务参数
3. THE BacktestView.vue SHALL 在回测参数配置区域新增"数据源选项"折叠面板，包含三个开关控件：基本面数据、资金流向数据、Tushare 因子数据，默认关闭
4. THE BacktestView.vue SHALL 在开关旁显示提示文本说明各数据源的用途和对回测速度的影响
