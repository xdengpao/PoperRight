# 实现计划：回测引擎性能与正确性优化

## 概述

按 P1→P2→P3→P4 优先级分层实施回测引擎优化。P1 修复预热期数据加载（正确性），P2 实现因子按需计算（性能），P3 预计算指标缓存（性能），P4 K线数据预索引（性能）。最后将所有优化组件集成到回测主循环中，替换原有的逐日重算和线性扫描逻辑。

## Tasks

- [x] 1. 实现预热期数据加载（P1 - 正确性修复）
  - [x] 1.1 在 `app/tasks/backtest.py` 中实现 `calculate_warmup_start_date` 函数
    - 分析 `StrategyConfig` 中 `ma_periods`、`indicator_params`（MACD/BOLL/RSI/DMA）的最大回看窗口
    - 取 `max(buffer_days, max_lookback)`，乘以 1.5 倍安全系数，计算预热起始日期
    - 确保返回值严格早于 `start_date`，且自然日数 >= `max(ma_periods)` 和 `buffer_days`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 编写 `calculate_warmup_start_date` 的属性测试
    - **Property 1: 预热期充分性**
    - **Validates: Requirements 1.2, 1.3, 1.5**

  - [x] 1.3 修改 `run_backtest_task` 中的 K 线 SQL 查询，使用预热起始日期替换 `start_date`
    - 调用 `calculate_warmup_start_date(sd, strategy_config)` 获取预热日期
    - 将 SQL 中 `time >= :start` 改为 `time >= :warmup_start`
    - _Requirements: 1.1_

- [x] 2. 检查点 - 确保预热期加载正确
  - 确保所有测试通过，如有疑问请询问用户。

- [x] 3. 实现因子按需计算（P2 - 性能优化）
  - [x] 3.1 在 `app/services/backtest_engine.py` 中实现 `_extract_required_factors` 函数
    - 定义 `FACTOR_TO_COMPUTE` 映射字典（含 `ma_support` → `{"ma_trend", "ma_support"}` 依赖关系）
    - 空 `factors` 列表返回全部 7 个因子（向后兼容）
    - 未知因子名称记录 WARNING 日志并忽略
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.2_

  - [x] 3.2 编写 `_extract_required_factors` 的属性测试
    - **Property 2: 因子提取完备性**
    - **Validates: Requirements 2.1, 2.3**

  - [x] 3.3 编写 `_extract_required_factors` 的属性测试（向后兼容）
    - **Property 3: 因子提取向后兼容**
    - **Validates: Requirement 2.2**

- [x] 4. 实现 K 线数据预索引（P4 - 性能优化）
  - [x] 4.1 在 `app/services/backtest_engine.py` 中定义 `KlineDateIndex` 数据类并实现 `_build_date_index` 函数
    - `KlineDateIndex` 包含 `date_to_idx: dict[date, int]` 和 `sorted_dates: list[date]`
    - 遍历每只股票的 bars 构建映射，重复日期使用后出现的记录覆盖
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.3_

  - [x] 4.2 实现 `_get_bars_up_to` 二分查找函数
    - 使用 `bisect_right` 实现 O(log N) 查找 `<= trade_date` 的最后一个索引
    - 无匹配时返回 -1
    - _Requirements: 4.5, 4.6, 4.7_

  - [x] 4.3 编写日期索引结构的属性测试
    - **Property 7: 日期索引结构不变量**
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [x] 4.4 编写日期索引查找正确性的属性测试
    - **Property 8: 日期索引查找正确性**
    - **Validates: Requirement 4.4**

  - [x] 4.5 编写二分查找等价性的属性测试
    - **Property 9: 二分查找等价性**
    - **Validates: Requirements 4.5, 4.6**

- [x] 5. 检查点 - 确保因子提取和日期索引正确
  - 确保所有测试通过，如有疑问请询问用户。

- [x] 6. 实现预计算指标缓存（P3 - 性能优化）
  - [x] 6.1 在 `app/services/backtest_engine.py` 中定义 `IndicatorCache` 数据类
    - 包含 `closes`、`highs`、`lows`、`volumes`、`amounts`、`turnovers` 基础序列
    - 包含 `ma_trend_scores`、`ma_support_flags`、`macd_signals`、`boll_signals`、`rsi_signals`、`dma_values`、`breakout_results` 可选指标字段
    - _Requirements: 3.1, 3.2_

  - [x] 6.2 实现 `_precompute_indicators` 函数
    - 遍历 `kline_data` 中每只股票，提取 OHLCV 序列
    - 根据 `required_factors` 按需调用 `score_ma_trend`、`detect_ma_support`、`detect_macd_signal`、`detect_boll_signal`、`detect_rsi_signal`、`calculate_dma`、突破检测函数
    - 使用滑动窗口 `closes[:i+1]` 逐日计算，生成与 bars 等长的指标时间序列
    - 未激活因子的字段保持 None
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1_

  - [x] 6.3 编写指标缓存结构不变量的属性测试
    - **Property 4: 指标缓存结构不变量**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 6.4 编写条件因子计算的属性测试
    - **Property 5: 条件因子计算**
    - **Validates: Requirements 3.3, 3.4**

  - [x] 6.5 编写预计算一致性的属性测试
    - **Property 6: 预计算一致性**
    - **Validates: Requirement 3.5**

- [x] 7. 检查点 - 确保预计算指标缓存正确
  - 确保所有测试通过，如有疑问请询问用户。

- [x] 8. 集成优化组件到回测主循环
  - [x] 8.1 重构 `_run_backtest_strategy_driven` 方法，在主循环前添加预计算阶段
    - 调用 `_extract_required_factors` 获取激活因子集合
    - 调用 `_build_date_index` 构建日期索引
    - 调用 `_precompute_indicators` 预计算指标缓存
    - _Requirements: 2.1, 3.1, 4.1_

  - [x] 8.2 实现 `_generate_buy_signals_optimized` 方法，替换原有的 `_generate_buy_signals`
    - 使用 `_get_bars_up_to` 替代线性扫描 `[b for b in bars if b.time.date() <= trade_date]`
    - 从 `IndicatorCache` 按索引直接读取预计算指标值，不再逐日重算
    - 仅填充 `required_factors` 中激活的指标字段
    - 保持 `ScreenExecutor` 调用逻辑不变
    - _Requirements: 2.1, 3.3, 4.5, 5.1_

  - [x] 8.3 重构 `_check_sell_conditions`、`_execute_buys`、`_execute_sells` 和净值快照计算，使用日期索引替代线性扫描
    - 将所有 `[b for b in bars if b.time.date() <= trade_date]` 替换为 `_get_bars_up_to` 调用
    - 将所有 `[b for b in bars if b.time.date() > trade_date]` 替换为基于索引的查找
    - _Requirements: 4.5, 4.7_

  - [x] 8.4 重构 `_evaluate_market_risk` 方法，使用日期索引替代线性扫描
    - 将指数 K 线的线性过滤替换为 `_get_bars_up_to` 调用
    - _Requirements: 4.5, 4.7_

- [x] 9. 检查点 - 确保集成后回测功能正常
  - 确保所有测试通过，如有疑问请询问用户。

- [x] 10. 优化前后等价性验证
  - [x] 10.1 编写优化前后信号生成等价性的集成测试
    - **Property 10: 优化前后信号生成等价性**
    - 使用固定测试数据，对比 `_generate_buy_signals` 和 `_generate_buy_signals_optimized` 的输出
    - **Validates: Requirements 5.1, 5.2**

- [x] 11. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有疑问请询问用户。

## Notes

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 属性测试使用 Hypothesis 库，放置在 `tests/properties/` 目录下
- 检查点确保增量验证，避免问题累积
- 设计文档使用 Python 代码，实现语言为 Python
