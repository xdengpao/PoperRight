# 需求文档：K线缺失时的指标计算处理机制

## 简介

在智能选股和策略回测过程中，K线数据缺失是常见场景——包括新股上市数据不足、停牌导致日K线中断、分钟K线部分或全天缺失等。当前系统已在各层实现了"NaN 填充 + 跳过无效值"的处理策略，但缺乏统一的文档化规范和系统性验证。本 spec 旨在将现有的缺失数据处理逻辑形式化为明确的需求和正确性属性，补充缺失的边界测试，并在必要时修补处理空隙，确保选股和回测在任何数据缺失场景下都能产生可靠、可解释的结果。

核心设计原则：**不插值、不猜测，数据不足就输出 NaN，NaN 等价于"无信号"，宁可漏选也不误选。**

## 术语表

- **K线 (KlineBar)**：单根K线的 OHLCV 数据记录，包含时间、开高低收、成交量等字段
- **NaN 前缀 (NaN Prefix)**：技术指标在数据不足时输出的 `float('nan')` 值区间，位于指标序列的前部
- **预热期 (Warmup Period)**：技术指标计算所需的、回测起始日期之前的历史数据时间窗口
- **安全系数 (Safety Factor)**：预热期计算中用于覆盖非交易日（周末、节假日、停牌）的乘数，当前为 1.5
- **指标缓存 (IndicatorCache)**：预计算的单只股票全部指标时间序列的数据结构，与K线序列等长
- **日期索引 (KlineDateIndex)**：将日期映射到K线列表索引位置的数据结构
- **分钟日内范围 (minute_day_ranges)**：将交易日映射到分钟K线缓存中起止索引的数据结构
- **哨兵值 (Sentinel Value)**：`(-1, -1)` 元组，表示某个交易日在分钟K线数据中无对应 bar
- **选股执行器 (ScreenExecutor)**：根据策略配置对股票数据执行多因子筛选的组件
- **平仓条件评估器 (ExitConditionEvaluator)**：在每个交易日对持仓标的评估自定义平仓条件的组件

## 需求

### 需求 1：底层指标函数的 NaN 填充规范

**用户故事：** 作为量化交易员，我希望所有技术指标在数据不足时返回 NaN 而非错误值，以便下游系统能安全地识别和跳过无效数据。

#### 验收标准

1. WHEN 输入收盘价序列长度小于 MA 周期 N 时，THE `calculate_ma(closes, N)` SHALL 返回全部为 NaN 的列表，长度等于输入序列长度
2. WHEN 输入收盘价序列长度 >= MA 周期 N 时，THE `calculate_ma(closes, N)` SHALL 返回前 N-1 个值为 NaN、从第 N 个值开始为有效浮点数的列表
3. WHEN 输入收盘价序列长度小于 EMA 周期 N 时，THE `_ema(data, N)` SHALL 返回全部为 NaN 的列表
4. WHEN 输入收盘价序列长度 >= EMA 周期 N 时，THE `_ema(data, N)` SHALL 返回前 N-1 个值为 NaN、从第 N-1 个索引开始为有效值的列表（用前 N 个值的 SMA 初始化）
5. WHEN 输入收盘价序列长度小于 `slow_period` 时，THE `calculate_macd(closes, fast, slow, signal)` SHALL 返回 DIF、DEA、MACD 柱全部为 NaN 的结果
6. WHEN 输入收盘价序列长度小于 `period + 1` 时，THE `calculate_rsi(closes, period)` SHALL 返回全部为 NaN 的值列表
7. WHEN 输入收盘价序列长度小于 BOLL 周期时，THE `calculate_boll(closes, period, std_dev)` SHALL 返回上轨、中轨、下轨全部为 NaN 的结果
8. WHEN 输入收盘价序列长度小于 DMA 长周期时，THE `calculate_dma(closes, short, long)` SHALL 返回 DMA 和 AMA 全部为 NaN 的结果
9. WHEN 输入序列为空列表时，ALL 指标计算函数 SHALL 返回空列表（而非抛出异常）
10. WHEN 周期参数 <= 0 时，THE `calculate_ma(closes, period)` 和 `_ema(data, period)` SHALL 返回全部为 NaN 的列表（而非抛出异常）

### 需求 2：预热期数据加载保障

**用户故事：** 作为量化交易员，我希望回测引擎在回测起始日就能获得准确的技术指标值，即使存在节假日和停牌导致的数据缺失。

#### 验收标准

1. THE `calculate_warmup_start_date(start_date, strategy_config, buffer_days)` SHALL 返回一个严格早于 `start_date` 的日期
2. THE 预热起始日期距 `start_date` 的自然日数 SHALL 不小于 `max(strategy_config.ma_periods)` 的 1.5 倍
3. THE 预热起始日期距 `start_date` 的自然日数 SHALL 不小于 `buffer_days`（默认 250）的 1.5 倍
4. WHEN 策略配置包含 MACD 指标时，THE 预热天数 SHALL 覆盖 `(macd_slow + macd_signal) × 1.5` 个自然日
5. WHEN 策略配置包含 RSI 指标时，THE 预热天数 SHALL 覆盖 `(rsi_period + 1) × 1.5` 个自然日
6. WHEN 策略配置包含 BOLL 指标时，THE 预热天数 SHALL 覆盖 `boll_period × 1.5` 个自然日
7. WHEN 策略配置包含 DMA 指标时，THE 预热天数 SHALL 覆盖 `dma_long × 1.5` 个自然日
8. THE 回测任务 SHALL 使用预热起始日期（而非回测起始日期）作为 SQL 查询的 `time >= :warmup_start` 条件

### 需求 3：日K线缺失时的回测引擎处理

**用户故事：** 作为量化交易员，我希望回测引擎在遇到停牌或数据缺失的股票时能优雅处理，不中断回测也不产生错误信号。

#### 验收标准

1. WHEN 某只股票在某个交易日没有K线数据（停牌）时，THE `_get_bars_up_to(index, trade_date)` SHALL 返回该股票在 `trade_date` 之前最近一个有效交易日的K线索引
2. WHEN 某只股票在所有交易日之前都没有K线数据时，THE `_get_bars_up_to(index, trade_date)` SHALL 返回 -1
3. WHEN `_get_bars_up_to` 返回 -1 时，THE 回测引擎 SHALL 跳过该股票在该交易日的信号生成和卖出检查
4. WHEN 某只新股的K线数据不足以计算所有指标时，THE 预计算指标缓存 SHALL 在数据不足的位置填充 NaN 或 False，该股票在这些交易日不产生买入信号
5. WHEN 预计算指标缓存中某只股票的 `ma_trend_scores[idx]` 基于不足数据计算时，THE 值 SHALL 为 0.0（而非 NaN），因为 MA 趋势评分函数在数据不足时返回 0 分
6. WHEN 预计算指标缓存中某只股票的 `macd_signals[idx]` 基于不足数据计算时，THE 值 SHALL 为 False
7. WHEN 预计算指标缓存中某只股票的 `boll_signals[idx]` 基于不足数据计算时，THE 值 SHALL 为 False
8. WHEN 预计算指标缓存中某只股票的 `rsi_signals[idx]` 基于不足数据计算时，THE 值 SHALL 为 False

### 需求 4：分钟K线缺失时的平仓条件处理

**用户故事：** 作为量化交易员，我希望分钟频率的平仓条件在分钟K线缺失时能安全降级，不会因数据缺失而产生错误的平仓信号。

#### 验收标准

1. WHEN 某个交易日在分钟K线数据中无对应 bar 时，THE `_build_minute_day_ranges()` SHALL 为该交易日生成 `(-1, -1)` 哨兵值
2. WHEN `minute_day_ranges` 中某个交易日的范围为 `(-1, -1)` 时，THE `ExitConditionEvaluator` SHALL 跳过该分钟频率条件的评估，视为条件未满足，并记录 WARNING 日志
3. WHEN 分钟频率的指标缓存不可用时，THE `ExitConditionEvaluator` SHALL 回退到日K线频率的指标缓存进行评估，并记录 INFO 日志
4. WHEN 分钟频率日内扫描中某根 bar 的指标值为 NaN 时，THE `ExitConditionEvaluator` SHALL 跳过该 bar 继续扫描下一根，不将 NaN 视为条件满足
5. WHEN `bar_index` 超出 `minute_day_ranges` 的长度时，THE `ExitConditionEvaluator` SHALL 跳过该条件并记录 WARNING 日志

### 需求 5：选股引擎中的缺失数据过滤

**用户故事：** 作为量化交易员，我希望选股引擎在指标数据不足时不将该股票纳入选股结果，避免基于无效数据做出选股决策。

#### 验收标准

1. WHEN 某只股票的 MA 趋势评分为 0.0（数据不足）时，THE 选股引擎 SHALL 不将该股票视为 MA 趋势信号通过
2. WHEN 某只股票的 MACD/BOLL/RSI 信号为 False（数据不足或指标值为 NaN）时，THE 选股引擎 SHALL 不将该股票视为对应信号通过
3. WHEN 某只股票的突破检测结果为 None（数据不足）时，THE 选股引擎 SHALL 不将该股票视为突破信号通过
4. WHEN 某只股票无任何有效信号时，THE `ScreenExecutor` SHALL 不将该股票纳入选股结果列表
5. THE 选股引擎 SHALL 不对缺失数据进行插值或补全，仅基于实际可用的K线数据计算指标

### 需求 6：平仓条件指标预计算中的缺失数据处理

**用户故事：** 作为量化交易员，我希望自定义平仓条件的指标预计算在K线数据不足时产生 NaN 值，以便评估器能安全跳过无效数据。

#### 验收标准

1. WHEN 日K线频率的平仓条件指标预计算时，THE `_precompute_exit_indicators()` SHALL 复用 `existing_cache` 中已基于前复权数据计算的 closes 序列，保证指标计算一致性
2. WHEN 分钟K线频率的平仓条件指标预计算时，THE `_precompute_exit_indicators()` SHALL 使用 `kline_data[freq]` 中已前复权的K线数据
3. WHEN 某只股票在某个分钟频率下没有K线数据时，THE `_precompute_exit_indicators()` SHALL 跳过该股票在该频率下的指标计算
4. WHEN 指标计算函数（`calculate_ma`、`calculate_macd`、`calculate_rsi`、`calculate_boll`、`calculate_dma`）在数据不足时产生 NaN 值，THE `_precompute_exit_indicators()` SHALL 保留这些 NaN 值在缓存中，不进行替换或插值
5. THE `_precompute_exit_indicators()` 使用的指标计算函数 SHALL 与选股引擎（`ScreenDataProvider`）共享同一实现，保证回测信号与选股信号的一致性

### 需求 7：数据完整性日志与可观测性

**用户故事：** 作为系统运维人员，我希望系统在遇到数据缺失时记录清晰的日志，以便排查数据质量问题。

#### 验收标准

1. WHEN 分钟K线缓存不可用并回退到日K线时，THE 系统 SHALL 记录 INFO 级别日志，包含频率、股票代码信息
2. WHEN 某个交易日无分钟数据（哨兵值 `(-1, -1)`）时，THE 系统 SHALL 记录 WARNING 级别日志，包含 bar_index、频率、股票代码信息
3. WHEN `bar_index` 超出 `minute_day_ranges` 范围时，THE 系统 SHALL 记录 WARNING 级别日志
4. WHEN 某只股票在预热期内数据不足导致指标全部为 NaN 时，THE 系统 SHALL 正常处理（不记录额外日志，因为这是预期行为）
