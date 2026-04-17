# 实现计划：K线缺失时的指标计算处理机制

## 概述

基于已确认的需求和设计文档，将K线缺失处理机制的验证和补强分解为增量式任务。本 spec 的核心目标是对现有处理逻辑进行形式化验证、补充边界测试、修补处理空隙。任务从底层指标函数的属性验证开始，逐层向上覆盖预热期、预计算缓存、日期索引、分钟K线处理、选股过滤，最终完成端到端集成测试。

## 任务列表

- [x] 1. 底层指标函数 NaN 填充属性验证
  - [x] 1.1 编写 MA NaN 前缀长度属性测试（Property 1）
    - **Property 1: MA NaN prefix length**
    - **验证: 需求 1.1, 1.2**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意非空收盘价序列和正整数周期 N，验证 `calculate_ma(closes, N)` 返回列表的前 `min(N-1, len(closes))` 个值为 NaN，若 `len(closes) >= N` 则从索引 `N-1` 开始为有效浮点数

  - [x] 1.2 编写 EMA NaN 前缀长度属性测试（Property 2）
    - **Property 2: EMA NaN prefix length**
    - **验证: 需求 1.3, 1.4**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意非空数值序列和正整数周期 N，验证 `_ema(data, N)` 返回列表的前 `min(N-1, len(data))` 个值为 NaN，若 `len(data) >= N` 则索引 `N-1` 处为有效浮点数

  - [x] 1.3 编写 MACD NaN 传播属性测试（Property 3）
    - **Property 3: MACD NaN propagation**
    - **验证: 需求 1.5**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意非空收盘价序列和合法 MACD 参数 (fast, slow, signal)，验证 `calculate_macd` 返回的 DIF 序列前 `slow-1` 个值为 NaN，若 `len(closes) < slow` 则 DIF 全部为 NaN

  - [x] 1.4 编写 RSI NaN 前缀长度属性测试（Property 4）
    - **Property 4: RSI NaN prefix length**
    - **验证: 需求 1.6**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意非空收盘价序列和正整数周期 period，验证 `calculate_rsi(closes, period)` 返回的值列表前 `min(period, len(closes))` 个值为 NaN，若 `len(closes) < period + 1` 则全部为 NaN

  - [x] 1.5 编写空输入安全性属性测试（Property 5）
    - **Property 5: Empty input safety**
    - **验证: 需求 1.9**
    - 在 `tests/properties/test_missing_kline_properties.py` 中验证所有指标计算函数（`calculate_ma`、`_ema`、`calculate_macd`、`calculate_boll`、`calculate_rsi`、`calculate_dma`）在输入空列表时返回空结果，不抛出异常

  - [x] 1.6 编写指标函数边界条件单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - `calculate_ma` 周期为 0、负数、1 的行为
    - `_ema` 周期为 0、负数的行为
    - 各指标函数输入单元素列表的行为
    - 各指标函数输入恰好等于周期长度的列表的行为
    - BOLL 和 DMA 在数据不足时返回全 NaN 的行为
    - _需求: 1.1 ~ 1.10_

- [x] 2. 检查点 - 确保底层指标属性测试通过
  - 运行 `pytest tests/properties/test_missing_kline_properties.py tests/services/test_missing_kline_handling.py -v`
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 3. 预热期充分性验证
  - [x] 3.1 编写预热期充分性属性测试（Property 6）
    - **Property 6: Warmup period sufficiency**
    - **验证: 需求 2.1, 2.2, 2.3**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意有效 start_date、strategy_config（含不同 ma_periods 和指标参数组合）和 buffer_days，验证 `calculate_warmup_start_date` 返回的日期满足所有后置条件
    - 注意：若 `tests/properties/test_warmup_start_date_properties.py` 已有类似测试，可在此文件中补充覆盖 MACD/RSI/BOLL/DMA 各指标的预热需求验证

  - [x] 3.2 编写预热期覆盖各指标的单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - 仅配置 MA120 时，预热天数 >= 120 × 1.5 = 180
    - 配置 MACD(12,26,9) 时，预热天数 >= 35 × 1.5 = 52.5
    - 配置 RSI(14) 时，预热天数 >= 15 × 1.5 = 22.5
    - 配置 BOLL(20) 时，预热天数 >= 20 × 1.5 = 30
    - 配置 DMA(10,50) 时，预热天数 >= 50 × 1.5 = 75
    - 同时配置多个指标时，取最大值
    - buffer_days=250 时，预热天数 >= 250 × 1.5 = 375
    - _需求: 2.1 ~ 2.8_

- [x] 4. 日K线缺失处理验证（日期索引与停牌）
  - [x] 4.1 编写 bisect 查找等价性属性测试（Property 7）
    - **Property 7: bisect lookup equivalence**
    - **验证: 需求 3.1, 3.2**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意K线序列（含随机日期间隔模拟停牌）和任意 trade_date，验证 `_get_bars_up_to(index, trade_date)` 与朴素线性扫描结果一致
    - 注意：若 `tests/properties/test_warmup_start_date_properties.py` 已有类似测试，可在此文件中补充停牌场景的覆盖

  - [x] 4.2 编写停牌场景单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - 连续停牌 5 天后查询停牌期间的日期，应返回停牌前最后一个交易日的索引
    - 首日即停牌（trade_date 早于所有K线日期），应返回 -1
    - 末日停牌（trade_date 等于最后一根K线日期），应返回最后一个索引
    - 单根K线的股票，查询该日期返回 0，查询更早日期返回 -1
    - _需求: 3.1, 3.2, 3.3_

  - [x] 4.3 编写预计算缓存信号安全性属性测试（Property 8）
    - **Property 8: Precomputed cache signal safety**
    - **验证: 需求 3.5, 3.6, 3.7, 3.8**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成任意长度的K线序列（包括极短序列模拟新股），构建 IndicatorCache 后验证：
    - `macd_signals` 中所有值为 bool 类型
    - `boll_signals` 中所有值为 bool 类型
    - `rsi_signals` 中所有值为 bool 类型
    - `ma_trend_scores` 中所有值为 float 且在 [0.0, 100.0] 范围内

  - [x] 4.4 编写新股数据不足单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - 构造仅有 10 根K线的股票，验证 IndicatorCache 中 MA120 相关的 ma_trend_scores 全部为 0.0
    - 构造仅有 20 根K线的股票，验证 MACD 信号在前 34 个位置为 False
    - 构造仅有 5 根K线的股票，验证所有指标信号均为 False/0.0/None
    - _需求: 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 5. 检查点 - 确保日K线缺失处理测试通过
  - 运行 `pytest tests/properties/test_missing_kline_properties.py tests/services/test_missing_kline_handling.py -v`
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 6. 分钟K线缺失处理验证
  - [x] 6.1 编写分钟日内范围哨兵值属性测试（Property 9）
    - **Property 9: Minute day ranges sentinel value**
    - **验证: 需求 4.1**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成日K线和分钟K线数据（部分交易日无分钟数据），验证 `_build_minute_day_ranges()` 对无分钟数据的交易日返回 `(-1, -1)`

  - [x] 6.2 编写分钟 NaN 跳过安全性属性测试（Property 10）
    - **Property 10: Minute NaN skip safety**
    - **验证: 需求 4.4**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成含 NaN 值的分钟指标缓存和数值比较条件，验证 `_evaluate_single_minute_scanning()` 在遇到 NaN 时跳过该 bar 而非触发条件

  - [x] 6.3 编写分钟K线缺失场景单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - `_build_minute_day_ranges`：3 个交易日中第 2 日无分钟数据，验证第 2 日为 `(-1, -1)`
    - `ExitConditionEvaluator`：day_range 为 `(-1, -1)` 时跳过条件，返回 `(False, "")`
    - `ExitConditionEvaluator`：分钟缓存不可用时回退到日频缓存
    - `ExitConditionEvaluator`：bar_index 超出 minute_day_ranges 长度时跳过条件
    - `_evaluate_single_minute_scanning`：日内扫描中 NaN 值被跳过
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7. 选股引擎缺失数据过滤验证
  - [x] 7.1 编写选股无信号过滤属性测试（Property 11）
    - **Property 11: Screen no-signal filter**
    - **验证: 需求 5.1, 5.2, 5.3, 5.4**
    - 在 `tests/properties/test_missing_kline_properties.py` 中使用 Hypothesis 生成所有指标信号均为 False/0.0/None 的 stocks_data，验证 `ScreenExecutor._execute()` 返回的 `ScreenResult.items` 为空列表

  - [x] 7.2 编写选股缺失数据单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - 构造 ma_trend=0.0、macd=False、boll=False、rsi=False、breakout=None 的股票数据，验证不纳入选股结果
    - 构造部分指标有效（如 macd=True）但其他为 False 的股票数据，验证仅有效信号被纳入
    - 验证选股引擎不对缺失数据进行插值
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. 检查点 - 确保分钟K线和选股过滤测试通过
  - 运行 `pytest tests/properties/test_missing_kline_properties.py tests/services/test_missing_kline_handling.py -v`
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 9. 平仓条件指标预计算缺失数据验证
  - [x] 9.1 编写指标计算函数共享一致性属性测试（Property 12）
    - **Property 12: Indicator function sharing consistency**
    - **验证: 需求 6.5**
    - 在 `tests/properties/test_missing_kline_properties.py` 中验证 `_precompute_exit_indicators()` 中导入的指标计算函数（`calculate_ma`、`calculate_macd`、`calculate_rsi`、`calculate_boll`、`calculate_dma`）与 `app/services/screener/indicators.py` 和 `app/services/screener/ma_trend.py` 中的函数是同一对象（`is` 比较）

  - [x] 9.2 编写平仓条件预计算缺失数据单元测试
    - 在 `tests/services/test_missing_kline_handling.py` 中测试：
    - 日频条件：复用 existing_cache 的 closes 序列，验证指标值与直接调用计算函数一致
    - 分钟频条件：某只股票无分钟K线数据时，该股票在该频率下无缓存条目
    - 分钟频条件：K线数据不足时，缓存中保留 NaN 值
    - _需求: 6.1, 6.2, 6.3, 6.4_

- [x] 10. 端到端集成测试
  - [x] 10.1 编写含停牌股票的端到端回测集成测试
    - 在 `tests/integration/test_missing_kline_integration.py` 中：
    - 构造 3 只股票的K线数据，其中 1 只在回测中间停牌 5 天
    - 执行完整回测，验证：回测不中断、停牌股票在停牌期间不产生新买入信号、已持有的停牌股票在停牌期间不触发卖出（因为无新K线数据）、复牌后正常恢复信号生成
    - _需求: 3.1, 3.3, 3.4_

  - [x] 10.2 编写新股数据不足的端到端回测集成测试
    - 在 `tests/integration/test_missing_kline_integration.py` 中：
    - 构造 1 只仅有 30 根K线的新股（上市不足 120 个交易日）
    - 执行完整回测，验证：该新股在整个回测期间不产生买入信号、回测正常完成不报错
    - _需求: 3.4, 5.1, 5.4_

  - [x] 10.3 编写分钟K线缺失的平仓条件集成测试
    - 在 `tests/integration/test_missing_kline_integration.py` 中：
    - 构造 1 只股票的日K线和 5 分钟K线数据，其中 2 个交易日无分钟数据
    - 配置分钟频率平仓条件（如 5min RSI > 80）
    - 执行回测，验证：有分钟数据的交易日正常评估、无分钟数据的交易日跳过分钟条件（不触发错误平仓）、日志中包含 WARNING 信息
    - _需求: 4.1, 4.2, 4.3, 4.4_

- [x] 11. 最终检查点 - 确保所有测试通过
  - 运行完整测试套件：
    ```bash
    pytest tests/properties/test_missing_kline_properties.py tests/services/test_missing_kline_handling.py tests/integration/test_missing_kline_integration.py -v
    ```
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 本 spec 主要是验证和补强现有逻辑，不引入新的业务功能
- 大部分代码逻辑已在 backtest-engine-optimization 和 minute-indicator-index-alignment-fix 两个 spec 中实现
- 属性测试使用 Hypothesis 库，与项目现有的属性测试风格一致
- 若 `tests/properties/test_warmup_start_date_properties.py` 已覆盖部分属性（如 Property 6、7），可在新测试文件中引用或扩展，避免重复
- 集成测试需要构造完整的 KlineBar 数据结构，可参考 `tests/tasks/test_backtest_warmup.py` 中的测试数据构造方式
- 检查点确保增量验证，每个阶段完成后运行测试
