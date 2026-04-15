# 需求文档：前复权K线数据

## 简介

智能选股系统当前使用原始（不复权）K线数据进行技术指标计算和选股筛选。由于股票存在分红送股等除权除息事件，原始K线数据中的价格不连续，导致均线、MACD、BOLL、RSI 等技术指标计算结果失真，影响选股准确性。

本功能在数据加载层引入前复权因子实时计算，将原始K线价格通过 `复权价 = 原始价 × (当日复权因子 / 最新复权因子)` 公式转换为前复权价格，使价格序列连续可比，从而提升技术指标计算、选股筛选和策略回测的准确性。同时在前端分钟K线图和日K线图中分别增加原始K线与前复权K线的切换展示功能，并在策略回测流程中集成前复权数据，确保回测引擎与选股引擎使用一致的前复权价格数据。

## 术语表

- **Forward_Adjustment_Calculator（前复权计算器）**：负责将原始K线价格数据通过复权因子转换为前复权价格的服务模块
- **AdjFactorRepository（复权因子仓储）**：负责从 TimescaleDB adjustment_factor 表查询复权因子数据的数据访问层
- **ScreenDataProvider（选股数据提供服务）**：负责从数据库加载K线数据并计算技术因子的服务，是选股引擎的数据源
- **KlineChart（K线图组件）**：前端 ECharts 蜡烛图组件，展示K线行情数据
- **Raw_Kline（原始K线）**：未经复权处理的原始OHLCV价格数据
- **Forward_Adjusted_Kline（前复权K线）**：通过前复权因子调整后的价格连续K线数据
- **Adj_Factor（复权因子）**：存储在 adjustment_factor 表中的每日复权系数，adj_type=1 表示前复权因子
- **Latest_Factor（最新复权因子）**：查询日期范围内最新交易日对应的复权因子值，作为前复权计算的统一基准
- **OHLC**：开盘价（Open）、最高价（High）、最低价（Low）、收盘价（Close）四个价格字段的统称
- **BacktestEngine（回测引擎）**：负责执行历史策略回测的核心模块，支持信号驱动和策略驱动两种回测路径
- **BacktestTask（回测任务）**：Celery 异步任务，负责从数据库加载K线数据并调用回测引擎执行回测
- **DailyKlineChart（日K线图）**：选股结果页面中内嵌的日K线蜡烛图，展示每只股票最近一年的日K线行情数据，通过 `fetchKline` 函数加载并渲染在 ScreenerResultsView 中
- **ScreenerResultsView（选股结果页面）**：展示选股结果列表的前端页面，包含内嵌的日K线图（DailyKlineChart）和分钟K线图组件（MinuteKlineChart）

## 需求

### 需求 1：复权因子查询能力

**用户故事：** 作为选股系统，我需要从数据库查询指定股票的复权因子数据，以便在数据加载时实时计算前复权价格。

#### 验收标准

1. WHEN 指定股票代码、复权类型和日期范围时，THE AdjFactorRepository SHALL 返回该股票在指定日期范围内的全部复权因子记录，按交易日期升序排列
2. WHEN 指定股票代码和复权类型时，THE AdjFactorRepository SHALL 支持查询该股票最新交易日的复权因子值（Latest_Factor）
3. WHEN 查询的股票在指定日期范围内无复权因子记录时，THE AdjFactorRepository SHALL 返回空列表
4. THE AdjFactorRepository SHALL 支持批量查询多只股票的复权因子数据，减少数据库往返次数

### 需求 2：前复权价格实时计算

**用户故事：** 作为选股系统，我需要在加载K线数据时实时计算前复权价格，以便技术指标基于价格连续的数据进行计算。

#### 验收标准

1. WHEN 提供原始K线数据和对应的复权因子序列时，THE Forward_Adjustment_Calculator SHALL 按公式 `复权价 = 原始价 × (当日复权因子 / 最新复权因子)` 计算每根K线的前复权 OHLC 价格
2. THE Forward_Adjustment_Calculator SHALL 仅调整 OHLC 四个价格字段，成交量（volume）和成交额（amount）保持原始值不变
3. WHEN 计算前复权价格后，THE Forward_Adjustment_Calculator SHALL 将调整后的 OHLC 价格四舍五入保留两位小数
4. WHEN 某根K线对应的交易日期在复权因子记录中不存在时，THE Forward_Adjustment_Calculator SHALL 使用该日期之前最近一个交易日的复权因子进行计算
5. WHEN 复权因子序列为空或最新复权因子为零时，THE Forward_Adjustment_Calculator SHALL 返回原始K线数据不做调整，并记录警告日志
6. FOR ALL 有效的原始K线数据和复权因子组合，THE Forward_Adjustment_Calculator SHALL 保证调整后的价格关系不变：调整后的最低价 ≤ 调整后的开盘价、调整后的最低价 ≤ 调整后的收盘价、调整后的最高价 ≥ 调整后的开盘价、调整后的最高价 ≥ 调整后的收盘价（前复权价格保序性）

### 需求 3：选股数据提供服务集成前复权

**用户故事：** 作为量化交易员，我需要选股引擎使用前复权K线数据计算技术指标，以便获得更准确的选股结果。

#### 验收标准

1. THE ScreenDataProvider SHALL 在加载K线数据后、计算技术指标前，使用 Forward_Adjustment_Calculator 将原始K线价格转换为前复权价格
2. WHEN ScreenDataProvider 加载某只股票的K线数据时，THE ScreenDataProvider SHALL 同时查询该股票对应日期范围的前复权因子（adj_type=1）
3. WHEN 某只股票无前复权因子数据时，THE ScreenDataProvider SHALL 使用原始K线数据继续计算，并记录警告日志
4. THE ScreenDataProvider SHALL 将前复权后的价格序列（closes、highs、lows）传递给所有下游技术指标计算模块（MA趋势、MACD、BOLL、RSI、DMA、形态突破）
5. THE ScreenDataProvider SHALL 在因子字典中保留原始收盘价字段（raw_close），供需要原始价格的场景使用

### 需求 4：K线数据 API 支持前复权

**用户故事：** 作为前端K线图组件，我需要通过 API 获取前复权K线数据，以便在图表中展示前复权行情。

#### 验收标准

1. WHEN 请求 K 线数据 API 时传入 adj_type=1 参数，THE Data_API SHALL 返回经过前复权计算的K线数据
2. WHEN 请求 K 线数据 API 时传入 adj_type=0 或不传 adj_type 参数，THE Data_API SHALL 返回原始K线数据（保持向后兼容）
3. THE Data_API SHALL 在响应中包含 adj_type 字段，标识返回数据的复权类型

### 需求 5：前端K线图复权类型切换

**用户故事：** 作为量化交易员，我需要在选股结果的K线图中切换查看前复权K线和原始K线，以便对比分析除权除息对价格走势的影响。

#### 验收标准

1. THE KlineChart SHALL 在K线图面板中显示复权类型切换控件，提供"原始"和"前复权"两个选项
2. WHEN 用户选择"前复权"选项时，THE KlineChart SHALL 请求 adj_type=1 的K线数据并重新渲染图表
3. WHEN 用户选择"原始"选项时，THE KlineChart SHALL 请求 adj_type=0 的K线数据并重新渲染图表
4. THE KlineChart SHALL 默认显示原始K线数据（adj_type=0），保持与当前行为一致
5. WHEN 用户切换复权类型时，THE KlineChart SHALL 保持当前选中的日期和周期不变，仅切换数据源
6. THE KlineChart SHALL 在缓存键中包含复权类型参数，确保不同复权类型的数据独立缓存
7. WHEN K线数据加载中时，THE KlineChart SHALL 显示加载状态提示，切换操作期间禁用切换控件防止重复请求

### 需求 6：前复权计算的保序性验证

**用户故事：** 作为系统，我需要确保前复权计算不会破坏K线数据的内在价格关系，以保证技术指标计算的正确性。

#### 验收标准

1. FOR ALL 经过前复权计算的K线数据，THE Forward_Adjustment_Calculator SHALL 保证同一根K线内 low ≤ open、low ≤ close、high ≥ open、high ≥ close 的关系成立
2. FOR ALL 使用相同复权因子的连续K线序列，THE Forward_Adjustment_Calculator SHALL 保证前复权后的价格变动方向与原始价格变动方向一致（即若原始收盘价上涨，前复权收盘价也上涨）
3. WHEN 复权因子在查询期间内保持不变时（无除权除息事件），THE Forward_Adjustment_Calculator SHALL 产生与原始K线完全相同的价格数据（因为 daily_factor / latest_factor = 1）

### 需求 7：策略回测集成前复权K线数据

**用户故事：** 作为量化交易员，我需要策略回测功能使用与智能选股相同的前复权K线数据进行回测，以保证回测结果的准确性和与选股信号的一致性。

#### 验收标准

1. WHEN BacktestTask 从 TimescaleDB 加载K线数据时，THE BacktestTask SHALL 同时查询所有相关股票在回测日期范围内的前复权因子（adj_type=1）
2. WHEN BacktestTask 完成K线数据加载后，THE BacktestTask SHALL 使用 Forward_Adjustment_Calculator 将原始K线 OHLC 价格转换为前复权价格，再传递给 BacktestEngine
3. THE BacktestTask SHALL 使用与 ScreenDataProvider 相同的 Forward_Adjustment_Calculator 实例化方式和计算逻辑，确保回测数据与选股数据的前复权结果一致
4. WHEN BacktestEngine 执行策略驱动回测时，THE BacktestEngine SHALL 基于前复权价格进行指标预计算、买卖信号生成和限价委托价格计算
5. WHEN BacktestEngine 计算权益曲线和交易记录时，THE BacktestEngine SHALL 使用前复权价格计算持仓市值和盈亏
6. WHEN 某只股票在回测期间内无前复权因子数据时，THE BacktestTask SHALL 使用该股票的原始K线数据继续回测，并记录警告日志
7. THE BacktestTask SHALL 在回测结果的交易记录中保留前复权后的成交价格，供回测报告展示使用
8. FOR ALL 经过前复权处理的回测K线数据，THE BacktestTask SHALL 保证前复权后的价格满足同一根K线内 low ≤ open、low ≤ close、high ≥ open、high ≥ close 的保序性约束

### 需求 8：日K线图复权类型切换

**用户故事：** 作为量化交易员，我需要在选股结果页面的日K线图中切换查看前复权K线和原始K线，以便在日线级别对比分析除权除息对价格走势的影响。

#### 验收标准

1. THE DailyKlineChart SHALL 在日K线图面板中显示复权类型切换控件，提供"原始"和"前复权"两个选项，与分钟K线图的复权切换控件保持一致的交互风格
2. WHEN 用户选择"前复权"选项时，THE DailyKlineChart SHALL 请求 adj_type=1 的日K线数据并重新渲染蜡烛图和成交量柱状图
3. WHEN 用户选择"原始"选项时，THE DailyKlineChart SHALL 请求 adj_type=0 的日K线数据并重新渲染蜡烛图和成交量柱状图
4. THE DailyKlineChart SHALL 默认显示原始K线数据（adj_type=0），保持与当前行为一致
5. WHEN 用户切换复权类型时，THE DailyKlineChart SHALL 保持当前的数据缩放范围（dataZoom）和已选中的日期高亮标记（markLine）不变，仅切换数据源
6. WHEN 日K线数据加载中时，THE DailyKlineChart SHALL 显示加载状态提示，切换操作期间禁用切换控件防止重复请求
7. WHEN 用户切换日K线复权类型后点击日K线图选择某个交易日时，THE ScreenerResultsView SHALL 将选中的日期正确传递给分钟K线图组件，分钟K线图的复权类型选择保持独立不受日K线复权类型影响
8. THE DailyKlineChart SHALL 对不同复权类型的日K线数据独立缓存，避免切换时重复请求已加载的数据
