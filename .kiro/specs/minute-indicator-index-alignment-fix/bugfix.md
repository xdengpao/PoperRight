# Bugfix Requirements Document

## Introduction

在回测引擎的自定义平仓条件评估中，当用户配置分钟频率（如 `"5min"`、`"15min"`）的平仓条件时，`ExitConditionEvaluator` 接收到的 `bar_index` 是基于**日K线**日期索引计算的（通过 `_get_bars_up_to(idx_info, trade_date)` 在 `_check_sell_conditions` 中得出）。然而，这个日K线 `bar_index` 被直接用于访问**分钟频率的指标缓存**，而分钟缓存的长度和索引含义与日K线完全不同。

例如：日K线有 60 根（60 个交易日），5 分钟K线有约 2880 根（60 天 × 48 根/天）。当 `bar_index = 20`（第 20 个交易日）时，评估器读取 `minute_cache["rsi_14"][20]`，这实际上是第 20 根 5 分钟K线（第 1 个交易日早盘），而非第 20 个交易日的任何分钟K线的 RSI 值。

这导致分钟频率的平仓条件评估使用了完全错误的指标值，使其实质上无法正常工作。

**影响范围**：所有使用分钟频率（`"1min"`、`"5min"`、`"15min"`、`"30min"`、`"60min"`）的自定义平仓条件均受影响。日K线频率（`"daily"`）的条件不受影响，因为日K线缓存与 `bar_index` 的索引语义一致。

**根因位置**：
1. `app/services/backtest_engine.py` — `_check_sell_conditions()` 从日K线日期索引计算 `bar_index` 并传递给评估器
2. `app/services/exit_condition_evaluator.py` — `evaluate()` 将同一个 `bar_index` 传递给 `_evaluate_single()`，不区分条件使用的是日频还是分钟频
3. `app/services/exit_condition_evaluator.py` — `_get_indicator_value()` 和 `_get_from_exit_cache()` 直接使用 `bar_index` 索引分钟频率缓存
4. `app/services/backtest_engine.py` — `_precompute_exit_indicators()` 按分钟K线原始长度构建缓存，未提供日期到分钟索引范围的映射

**修复语义**：对分钟频率条件，系统应遍历该交易日内的**每一根分钟 bar** 的指标值，只要任意一根分钟 bar 满足条件即触发平仓信号。这比仅取日终值更贴近真实交易——例如 5 分钟 RSI 在上午 10:30 超过 80 触发超买，即使收盘时回落到 60，也应视为条件满足。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户配置了分钟频率（如 `freq="5min"`）的平仓条件，且回测引擎在某个交易日评估该条件时，THEN 系统使用日K线的 `bar_index`（如第 20 个交易日对应 `bar_index=20`）直接索引分钟频率指标缓存（如 `exit_indicator_cache["5min"]["rsi_14"][20]`），读取到的是第 20 根 5 分钟K线的指标值（第 1 个交易日早盘），而非第 20 个交易日内任何分钟K线的指标值

1.2 WHEN `_precompute_exit_indicators()` 为分钟频率条件计算指标缓存时，THEN 系统按分钟K线的原始长度构建缓存（如 5 分钟K线 2880 根对应缓存长度 2880），未提供"交易日 → 该日分钟 bar 索引范围"的映射

1.3 WHEN 分钟频率平仓条件的 `bar_index`（日K线索引）超过分钟缓存长度时（如日K线有 200 个交易日但分钟缓存因数据缺失只有 100 根），THEN 系统因索引越界而跳过该条件评估，导致条件永远不触发

1.4 WHEN 用户同时配置了日频和分钟频的平仓条件（如 `freq="daily"` 的 RSI > 80 AND `freq="5min"` 的 MACD 死叉），THEN 分钟频条件因索引错位而评估了错误的指标值，导致组合条件的整体判断结果不正确

### Expected Behavior (Correct)

2.1 WHEN 用户配置了分钟频率（如 `freq="5min"`）的平仓条件，且回测引擎在某个交易日评估该条件时，THEN 系统 SHALL 遍历该交易日内**每一根分钟 bar** 对应的指标值，只要任意一根分钟 bar 的指标值满足条件即视为该条件在当日触发

2.2 WHEN `_precompute_exit_indicators()` 为分钟频率条件计算指标缓存时，THEN 系统 SHALL 同时构建"交易日 → 该日分钟 bar 索引范围"的映射（`minute_day_ranges`），格式为 `{symbol: {freq: [(start_idx, end_idx), ...]}}`，其中每个元组对应一个交易日在分钟缓存中的起止索引（闭区间）

2.3 WHEN `ExitConditionEvaluator` 评估分钟频率条件时，THEN 系统 SHALL 接收 `minute_day_ranges` 映射，根据日K线 `bar_index` 查找当日的分钟 bar 索引范围 `(start_idx, end_idx)`，遍历该范围内的每个分钟 bar 索引进行条件评估

2.4 WHEN 分钟频率条件使用交叉运算符（`cross_up` / `cross_down`）时，THEN 系统 SHALL 在该交易日的分钟 bar 索引范围内逐 bar 检测交叉信号，任意相邻两根分钟 bar 之间发生交叉即视为条件满足

2.5 WHEN 用户同时配置了日频和分钟频的平仓条件时，THEN 系统 SHALL 对日频条件使用日K线 `bar_index` 直接评估，对分钟频条件使用日内分钟 bar 遍历评估，两者的评估结果按配置的逻辑运算符（AND/OR）组合

2.6 WHEN 某个交易日在分钟K线数据中无对应 bar（如该日停牌或数据缺失）时，THEN 系统 SHALL 跳过该分钟频率条件的评估，视为条件未满足，并记录 WARNING 日志

2.7 WHEN 分钟频率条件在日内遍历中触发时，THEN 系统 SHALL 在卖出原因描述中包含触发的具体条件（如 `"EXIT_CONDITION: RSI > 80"`），与日频条件的描述格式一致

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户仅配置了日频（`freq="daily"`）的平仓条件时，THEN 系统 SHALL CONTINUE TO 使用日K线的 `bar_index` 直接索引日频指标缓存，评估结果与修复前完全一致

3.2 WHEN 用户未配置任何自定义平仓条件时（`exit_conditions` 为 None），THEN 系统 SHALL CONTINUE TO 保持与现有行为完全一致，不产生任何 `EXIT_CONDITION` 类型的卖出信号

3.3 WHEN `_precompute_exit_indicators()` 处理日频（`freq="daily"`）指标时，THEN 系统 SHALL CONTINUE TO 从 `existing_cache` 复用已有的日K线 closes 序列计算指标，缓存结构和长度不变

3.4 WHEN 分钟K线数据不可用时，THEN 系统 SHALL CONTINUE TO 回退到日K线数据进行评估，并记录 INFO 日志

3.5 WHEN 现有风控条件（止损、趋势破位、移动止盈、持仓超期）已触发某只持仓的卖出信号时，THEN 系统 SHALL CONTINUE TO 跳过该持仓的自定义平仓条件评估

3.6 WHEN 指标数据不足（如K线数量少于指标最小周期）或指标值为 NaN 时，THEN 系统 SHALL CONTINUE TO 跳过该条件评估并记录警告日志

3.7 WHEN 自定义平仓条件触发卖出信号时，THEN 系统 SHALL CONTINUE TO 生成优先级为 5 的卖出信号，卖出以 T+1 开盘价执行，遵守 A 股 T+1 交易规则

---

## Bug Condition (Formal)

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type ExitConditionEvaluation
    -- X.condition: ExitCondition (contains freq field)
    -- X.bar_index: int (daily K-line index)
    -- X.exit_indicator_cache: dict (per-freq indicator caches)
  OUTPUT: boolean

  resolved_freq ← resolve_freq(X.condition.freq)

  // Bug triggers when the condition uses a minute frequency
  // and bar_index (daily index) is used to directly index minute cache
  RETURN resolved_freq ∈ {"1min", "5min", "15min", "30min", "60min"}
END FUNCTION
```

### Property Specification — Fix Checking

```pascal
// Property: Fix Checking — Minute-frequency conditions scan all intra-day bars
FOR ALL X WHERE isBugCondition(X) DO
  resolved_freq ← resolve_freq(X.condition.freq)
  minute_cache ← X.exit_indicator_cache[resolved_freq]
  day_range ← X.minute_day_ranges[resolved_freq][X.bar_index]
    // day_range = (start_idx, end_idx) for this trading day

  // The evaluator checks every minute bar in the day range
  FOR bar_idx FROM day_range.start TO day_range.end DO
    value ← minute_cache[cache_key][bar_idx]
    // value is the indicator at this specific minute bar
  END FOR

  // Condition triggers if ANY minute bar in the range satisfies it
  triggered ← EXISTS bar_idx IN [day_range.start..day_range.end]
    SUCH THAT evaluate_single(X.condition, bar_idx, minute_cache) = TRUE

  // For cross operators, check consecutive pairs within the range
  IF X.condition.operator ∈ {"cross_up", "cross_down"} THEN
    triggered ← EXISTS bar_idx IN [day_range.start+1..day_range.end]
      SUCH THAT check_cross(bar_idx-1, bar_idx, minute_cache) = TRUE
  END IF
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking — Daily-frequency behavior unchanged
FOR ALL X WHERE NOT isBugCondition(X) DO
  // X uses freq="daily", bar_index indexes daily cache directly
  // Single-value evaluation, no intra-day scan
  ASSERT F(X) = F'(X)
  // Daily indicator cache structure, length, and values are identical
END FOR
```
