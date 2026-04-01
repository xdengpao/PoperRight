# 需求文档

## 简介

本文档定义回测引擎性能与正确性优化的需求。当前回测引擎在策略驱动路径中存在两类问题：（1）正确性缺陷——K线数据查询未包含技术指标预热期，导致 MA120、EMA26 等长周期指标在回测初期产生 NaN 值；（2）性能瓶颈——每个交易日对全市场股票从头计算全部技术指标，且使用线性扫描过滤K线数据。优化方案按 P1（预热期数据加载）、P2（因子按需计算）、P3（预计算指标缓存）、P4（K线数据预索引）四个优先级分层实施。

## 术语表

- **回测引擎 (BacktestEngine)**：执行历史策略回测的核心服务，位于 `app/services/backtest_engine.py`
- **回测任务 (BacktestTask)**：Celery 异步任务，负责加载数据并调用回测引擎，位于 `app/tasks/backtest.py`
- **预热期 (Warmup Period)**：技术指标计算所需的、回测起始日期之前的历史数据时间窗口
- **策略配置 (StrategyConfig)**：定义选股因子、逻辑运算、均线周期、指标参数等的配置数据类
- **因子 (Factor)**：策略中配置的技术指标筛选条件，如 ma_trend、macd、boll、rsi、dma、breakout
- **指标缓存 (IndicatorCache)**：预计算的单只股票全部指标时间序列的数据结构
- **日期索引 (KlineDateIndex)**：将日期映射到K线列表索引位置的数据结构，支持 O(1) 精确查找和 O(log N) 范围查找
- **K线数据 (KlineBar)**：单根K线的 OHLCV 数据记录
- **选股执行器 (ScreenExecutor)**：根据策略配置对股票数据执行多因子筛选的组件

## 需求

### 需求 1：预热期数据加载

**用户故事：** 作为量化交易员，我希望回测引擎在回测起始日就能获得准确的技术指标值，以便回测结果从第一天起就可靠。

#### 验收标准

1. WHEN 回测任务加载K线数据时，THE 回测任务 SHALL 根据策略配置中所有指标的最大回看窗口计算预热起始日期，并从该日期开始加载K线数据
2. THE 预热期计算函数 SHALL 返回一个严格早于回测起始日期的日期，且该日期距回测起始日期的自然日数不小于策略配置中最大均线周期（max(ma_periods)）
3. THE 预热期计算函数 SHALL 返回一个距回测起始日期的自然日数不小于 buffer_days 参数值（默认 250）的日期
4. WHEN 策略配置包含 MACD 指标时，THE 预热期计算函数 SHALL 确保预热天数覆盖 MACD 慢线周期加信号线周期的总和
5. THE 预热期计算函数 SHALL 对计算出的交易日需求乘以 1.5 倍安全系数，以覆盖节假日和停牌等非交易日

### 需求 2：因子按需计算

**用户故事：** 作为量化交易员，我希望回测引擎只计算策略中实际配置的技术指标，以便减少不必要的计算开销。

#### 验收标准

1. WHEN 策略配置的 factors 列表非空时，THE 因子提取函数 SHALL 仅返回 factors 列表中出现的因子名称对应的计算模块集合
2. WHEN 策略配置的 factors 列表为空时，THE 因子提取函数 SHALL 返回全部七个因子（ma_trend、ma_support、macd、boll、rsi、dma、breakout），以保持向后兼容
3. THE 因子提取函数 SHALL 返回 {"ma_trend", "ma_support", "macd", "boll", "rsi", "dma", "breakout"} 的子集
4. WHEN 策略配置的 factors 列表包含 "ma_support" 因子时，THE 因子提取函数 SHALL 同时包含 "ma_trend" 计算模块，因为均线支撑依赖均线趋势计算

### 需求 3：预计算指标缓存

**用户故事：** 作为量化交易员，我希望回测引擎在主循环开始前一次性预计算所有指标，以便交易日循环中只做查表操作，大幅提升回测速度。

#### 验收标准

1. WHEN 预计算指标函数执行时，THE 预计算指标函数 SHALL 为 kline_data 中的每只股票生成一个 IndicatorCache 实例，返回字典的键集合与 kline_data 的键集合相同
2. THE IndicatorCache 中的 closes、highs、lows、volumes 列表长度 SHALL 等于该股票的 KlineBar 列表长度
3. WHEN required_factors 包含某个因子名称时，THE 预计算指标函数 SHALL 填充 IndicatorCache 中对应的指标字段为非 None 的时间序列
4. WHEN required_factors 不包含某个因子名称时，THE 预计算指标函数 SHALL 将 IndicatorCache 中对应的指标字段保持为 None
5. THE 预计算指标函数生成的指标值 SHALL 与对同一股票同一索引位置使用 bars[:idx+1] 从头计算的指标值数值一致

### 需求 4：K线数据预索引

**用户故事：** 作为量化交易员，我希望回测引擎使用预建索引替代线性扫描来定位K线数据，以便每个交易日的数据查找从 O(N) 降至 O(log N) 或 O(1)。

#### 验收标准

1. WHEN 日期索引构建函数执行时，THE 日期索引构建函数 SHALL 为 kline_data 中的每只股票生成一个 KlineDateIndex 实例，返回字典的键集合与 kline_data 的键集合相同
2. THE KlineDateIndex 中的 sorted_dates 列表 SHALL 严格递增
3. THE KlineDateIndex 中的 date_to_idx 字典的长度 SHALL 等于对应股票的 KlineBar 列表长度
4. WHEN 通过 date_to_idx 查找日期 d 时，THE KlineDateIndex SHALL 满足 bars[date_to_idx[d]].time.date() == d
5. WHEN 使用二分查找函数查找 trade_date 时，THE 二分查找函数 SHALL 返回 bars 中日期 <= trade_date 的最后一条K线的索引位置
6. WHEN 所有K线的日期均晚于 trade_date 时，THE 二分查找函数 SHALL 返回 -1
7. THE 二分查找函数的时间复杂度 SHALL 为 O(log N)，替代原有的 O(N) 线性扫描

### 需求 5：优化后信号生成等价性

**用户故事：** 作为量化交易员，我希望优化后的回测结果与优化前完全一致，以便确认优化没有引入计算偏差。

#### 验收标准

1. WHEN 使用相同的 config 和 kline_data 执行回测时，THE 优化后的信号生成函数 SHALL 对每个交易日产生与优化前 _generate_buy_signals 相同的 ScreenItem 列表（按 symbol 排序后比较）
2. WHEN 使用相同的输入执行完整回测时，THE 优化后的回测引擎 SHALL 产生与优化前相同的 BacktestResult 九项绩效指标值

### 需求 6：错误处理

**用户故事：** 作为量化交易员，我希望回测引擎在遇到异常数据时能够优雅处理，以便回测不会因个别股票的数据问题而中断。

#### 验收标准

1. WHEN 某只股票在预热起始日期之前没有足够的K线数据时，THE 回测引擎 SHALL 正常处理该股票，在数据不足的交易日不产生有效信号
2. WHEN 策略配置的 factors 列表包含未知因子名称时，THE 因子提取函数 SHALL 忽略未知因子并记录 WARNING 日志，仅计算已知因子
3. WHEN 同一股票在同一日期存在多条K线记录时，THE 日期索引构建函数 SHALL 使用后出现的记录覆盖先出现的记录，进行防御性处理
