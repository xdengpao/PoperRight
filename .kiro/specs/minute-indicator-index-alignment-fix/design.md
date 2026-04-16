# Minute Indicator Index Alignment Fix — Bugfix Design

## Overview

回测引擎中，分钟频率平仓条件评估使用了日K线的 `bar_index` 直接索引分钟指标缓存，导致读取到完全错误的指标值。修复方案采用**日内扫描（intra-day scanning）**：为每个交易日建立分钟 bar 索引范围映射（`minute_day_ranges`），评估分钟频率条件时遍历该日所有分钟 bar，任意一根满足条件即触发。日频条件保持原有的单 `bar_index` 评估逻辑不变。

## Glossary

- **Bug_Condition (C)**: 平仓条件的 `freq` 为分钟频率（`"1min"`, `"5min"`, `"15min"`, `"30min"`, `"60min"`），此时日K线 `bar_index` 与分钟缓存索引语义不匹配
- **Property (P)**: 对分钟频率条件，系统应遍历该交易日内每一根分钟 bar 的指标值，任意一根满足条件即触发
- **Preservation**: 日频条件（`freq="daily"`）的评估逻辑、缓存结构、风控优先级、T+1 规则等均不受修复影响
- **`bar_index`**: 日K线序列中的索引，由 `_get_bars_up_to(idx_info, trade_date)` 计算得出
- **`minute_day_ranges`**: 新增映射 `{symbol: {freq: [(start_idx, end_idx), ...]}}`，将每个交易日映射到其在分钟缓存中的起止索引（闭区间）
- **`exit_indicator_cache`**: 现有缓存结构 `{symbol: {freq: {cache_key: values}}}`，分钟频率的 `values` 按分钟 bar 原始顺序存储
- **`ExitConditionEvaluator`**: `app/services/exit_condition_evaluator.py` 中的平仓条件评估器

## Bug Details

### Bug Condition

当用户配置分钟频率的平仓条件时，`_check_sell_conditions()` 从日K线日期索引计算 `bar_index`（如第 20 个交易日 → `bar_index=20`），然后将此值直接传递给 `ExitConditionEvaluator.evaluate()`。评估器内部的 `_get_indicator_value()` 和 `_get_from_exit_cache()` 使用同一个 `bar_index` 索引分钟频率缓存，但分钟缓存的索引含义完全不同（如 5 分钟K线每天约 48 根，`bar_index=20` 对应的是第 1 个交易日早盘的第 20 根 5 分钟 bar）。

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ExitConditionEvaluation
    -- input.condition.freq: string (condition frequency)
    -- input.bar_index: int (daily K-line index)
    -- input.exit_indicator_cache: dict (per-freq indicator caches)
  OUTPUT: boolean

  resolved_freq ← resolve_freq(input.condition.freq)

  RETURN resolved_freq IN {"1min", "5min", "15min", "30min", "60min"}
END FUNCTION
```

### Examples

- **Example 1**: 日K线有 60 根（60 个交易日），5 分钟K线有 2880 根。`bar_index=20` 时，评估器读取 `cache["5min"]["rsi_14"][20]`（第 1 天早盘第 20 根 5 分钟 bar 的 RSI），而非第 20 个交易日内任何 5 分钟 bar 的 RSI。**Expected**: 应遍历第 20 个交易日对应的 5 分钟 bar 范围（如 index 912~959），任意一根 RSI > 80 即触发。
- **Example 2**: `bar_index=200`（第 200 个交易日），但 5 分钟缓存因数据缺失只有 100 根。`_safe_index` 返回 None，条件永远不触发。**Expected**: 应通过 `minute_day_ranges` 查找第 200 天的分钟范围，若无数据则跳过并记录警告。
- **Example 3**: 用户配置 `freq="5min"` 的 MACD 死叉条件。`bar_index=10` 时，评估器检查 `cache["5min"]["macd_dif"][9]` 和 `cache["5min"]["macd_dif"][10]` 的交叉，这两根 bar 都在第 1 个交易日内，与第 10 个交易日无关。**Expected**: 应在第 10 个交易日的分钟 bar 范围内逐对检测交叉。
- **Edge case**: 日频和分钟频条件混合使用 AND 逻辑时，日频条件正确评估但分钟频条件因索引错位返回错误结果，导致 AND 组合判断不正确。

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 日频（`freq="daily"`）平仓条件使用 `bar_index` 直接索引日频缓存，评估结果与修复前完全一致
- 未配置自定义平仓条件时（`exit_conditions=None`），不产生任何 `EXIT_CONDITION` 卖出信号
- `_precompute_exit_indicators()` 处理日频指标时，从 `existing_cache` 复用日K线 closes，缓存结构和长度不变
- 分钟K线数据不可用时，回退到日K线数据评估并记录 INFO 日志
- 风控条件（止损/趋势破位/移动止盈/持仓超期）优先级高于自定义平仓条件
- 指标值为 NaN 或数据不足时跳过条件评估并记录警告
- 自定义平仓条件触发优先级为 5 的卖出信号，T+1 开盘价执行

**Scope:**
所有 `freq="daily"` 的条件评估路径完全不受影响。修复仅改变分钟频率条件的索引解析方式（从直接使用 `bar_index` 改为通过 `minute_day_ranges` 查找日内范围并遍历）。

## Hypothesized Root Cause

Based on the bug description, the root cause is a **frequency-index mismatch** in the evaluation pipeline:

1. **Single bar_index for all frequencies**: `_check_sell_conditions()` 计算一个基于日K线的 `bar_index` 并传递给 `ExitConditionEvaluator.evaluate()`。评估器对所有条件（无论日频还是分钟频）使用同一个 `bar_index`，未区分频率。

2. **Missing day-to-minute index mapping**: `_precompute_exit_indicators()` 按分钟K线原始长度构建缓存，但未提供"交易日 → 该日分钟 bar 索引范围"的映射。评估器无法将日K线 `bar_index` 转换为分钟缓存中的正确索引范围。

3. **Evaluator lacks frequency-aware indexing**: `_evaluate_single()` 和 `_evaluate_cross()` 直接将 `bar_index` 传递给 `_get_indicator_value()` → `_get_from_exit_cache()`，后者使用 `bar_index` 作为列表索引，不考虑缓存的频率语义。

4. **No intra-day scanning logic**: 即使索引正确，当前设计也只检查单个 bar 的指标值，而分钟频率条件的正确语义是"该交易日内任意一根分钟 bar 满足条件即触发"。

## Correctness Properties

Property 1: Bug Condition - Minute-frequency intra-day scanning triggers correctly

_For any_ minute-frequency exit condition (where `isBugCondition` returns true) and a trading day with known minute bar indicator values, the fixed evaluator SHALL scan all minute bars within that day's range and trigger the condition if ANY single minute bar satisfies the numeric threshold (for `>`, `<`, `>=`, `<=` operators), or if ANY consecutive pair of minute bars within the day shows a crossover (for `cross_up`, `cross_down` operators).

**Validates: Requirements 2.1, 2.3, 2.4**

Property 2: Preservation - Daily-frequency evaluation unchanged

_For any_ daily-frequency exit condition (where `isBugCondition` returns false), the fixed evaluator SHALL produce exactly the same `(triggered, reason)` result as the original evaluator when given the same `bar_index`, `indicator_cache`, and `exit_indicator_cache`, preserving single-bar evaluation semantics.

**Validates: Requirements 3.1, 3.2, 3.3**

Property 3: Bug Condition - minute_day_ranges mapping correctness

_For any_ set of minute kline bars grouped by symbol and frequency, the `minute_day_ranges` mapping SHALL correctly map each trading day index to a contiguous `(start_idx, end_idx)` range in the minute cache, where: (a) ranges are non-overlapping, (b) ranges cover all minute bars, (c) `start_idx <= end_idx`, and (d) the number of day ranges equals the number of distinct trading days in the minute data.

**Validates: Requirements 2.2**

Property 4: Preservation - Mixed daily/minute conditions combine correctly

_For any_ `ExitConditionConfig` containing both daily-frequency and minute-frequency conditions with AND/OR logic, the fixed evaluator SHALL evaluate daily conditions using single `bar_index` lookup and minute conditions using intra-day scanning, then combine results using the configured logic operator, producing the same combination semantics as the original AND/OR logic.

**Validates: Requirements 2.5, 3.1**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `app/services/backtest_engine.py`

**Function**: `_precompute_exit_indicators()`

**Specific Changes**:
1. **Build `minute_day_ranges` mapping**: After computing minute-frequency indicator caches, iterate through minute kline bars to build a `{symbol: {freq: [(start_idx, end_idx), ...]}}` mapping. Each tuple maps a trading day (by its position in the daily sorted_dates list) to the start and end indices in the minute cache. Group consecutive minute bars by their `time.date()` to determine day boundaries.

2. **Return `minute_day_ranges` alongside cache**: Modify the return type or add a separate builder function to produce the `minute_day_ranges` mapping. The mapping is built from the minute kline data's date grouping.

**Function**: `_check_sell_conditions()`

**Specific Changes**:
3. **Pass `minute_day_ranges` to evaluator**: When calling `evaluator.evaluate()`, pass the symbol's `minute_day_ranges` so the evaluator can resolve daily `bar_index` to minute bar ranges.

4. **Pass daily `sorted_dates` for day-index alignment**: The evaluator needs to know which trading day corresponds to `bar_index` so it can look up the correct minute range. Pass the daily `KlineDateIndex` or the trade_date directly.

**File**: `app/services/exit_condition_evaluator.py`

**Function**: `evaluate()`

**Specific Changes**:
5. **Accept `minute_day_ranges` parameter**: Add an optional `minute_day_ranges: dict[str, list[tuple[int, int]]] | None` parameter (keyed by resolved freq).

6. **Route minute-frequency conditions to intra-day scanning**: In the per-condition loop, after resolving `freq`, check if `freq != "daily"` and `minute_day_ranges` is available. If so, call a new `_evaluate_single_minute_scanning()` method instead of `_evaluate_single()`.

**Function**: `_evaluate_single_minute_scanning()` (new)

**Specific Changes**:
7. **Implement intra-day scanning for numeric conditions**: For `>`, `<`, `>=`, `<=` operators, iterate through `range(start_idx, end_idx + 1)` and return `(True, reason)` if any bar satisfies the condition.

8. **Implement intra-day scanning for cross conditions**: For `cross_up` / `cross_down`, iterate through `range(start_idx + 1, end_idx + 1)` and check each consecutive pair `(bar_idx - 1, bar_idx)` for crossover. Return `(True, reason)` if any pair shows a cross.

9. **Handle missing day range gracefully**: If `bar_index` is out of range for `minute_day_ranges`, log a WARNING and return `(False, "")`.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that configure minute-frequency exit conditions with known indicator values and verify that the evaluator reads from the correct minute bar indices. Run these tests on the UNFIXED code to observe failures.

**Test Cases**:
1. **5min RSI numeric condition**: Configure `freq="5min"`, `rsi > 80`. Provide minute cache where day 5's minute bars (indices 240-287) have RSI=85, but index 5 has RSI=50. On unfixed code, evaluator reads index 5 (RSI=50) → not triggered. Expected: should scan indices 240-287 and trigger (will fail on unfixed code).
2. **1min MACD cross_down condition**: Configure `freq="1min"`, MACD DIF cross_down DEA. Provide minute cache where day 3's bars show a crossover at indices 720-721, but indices 2-3 show no crossover. On unfixed code, evaluator checks indices 2-3 → not triggered (will fail on unfixed code).
3. **Mixed daily + minute AND condition**: Configure daily RSI > 80 AND 5min close < 95. Daily RSI at bar_index=10 is 85 (satisfied). 5min close at index 10 is 100 (not satisfied), but day 10's minute bars include close=90 (satisfied). On unfixed code, AND fails because minute condition reads wrong index (will fail on unfixed code).
4. **Out-of-range bar_index**: `bar_index=200` but minute cache has only 100 entries. On unfixed code, returns None/skips. Expected: should use minute_day_ranges to find correct range or skip gracefully (may fail on unfixed code).

**Expected Counterexamples**:
- Minute-frequency conditions evaluate wrong indicator values because `bar_index` (daily index) is used directly as minute cache index
- Possible causes: missing day-to-minute index mapping, no intra-day scanning logic

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  resolved_freq ← resolve_freq(input.condition.freq)
  day_range ← minute_day_ranges[resolved_freq][input.bar_index]
  // day_range = (start_idx, end_idx)

  IF input.condition.operator IN {">", "<", ">=", "<="} THEN
    result := evaluate_minute_scanning(input.condition, day_range, minute_cache)
    expected := EXISTS idx IN [day_range.start..day_range.end]
      SUCH THAT op(minute_cache[cache_key][idx], threshold) = TRUE
    ASSERT result.triggered = expected
  END IF

  IF input.condition.operator IN {"cross_up", "cross_down"} THEN
    result := evaluate_minute_scanning(input.condition, day_range, minute_cache)
    expected := EXISTS idx IN [day_range.start+1..day_range.end]
      SUCH THAT check_cross(idx-1, idx, minute_cache) = TRUE
    ASSERT result.triggered = expected
  END IF
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT evaluate_original(input) = evaluate_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (arbitrary daily indicator values, thresholds, operators)
- It catches edge cases that manual unit tests might miss (NaN values, boundary thresholds, empty conditions)
- It provides strong guarantees that daily-frequency behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for daily-frequency conditions, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Daily numeric condition preservation**: Generate random daily indicator values and thresholds, verify fixed evaluator produces same result as original for `freq="daily"` conditions
2. **Daily cross condition preservation**: Generate random consecutive daily indicator/target pairs, verify cross detection unchanged for `freq="daily"`
3. **Empty conditions preservation**: Verify `ExitConditionConfig(conditions=[])` still returns `(False, None)`
4. **AND/OR logic preservation for daily-only configs**: Generate random daily-only condition configs with AND/OR logic, verify identical results

### Unit Tests

- Test `minute_day_ranges` construction from minute kline data with varying bars per day
- Test `_evaluate_single_minute_scanning()` for numeric conditions with known day ranges
- Test `_evaluate_single_minute_scanning()` for cross conditions with known day ranges
- Test edge cases: empty day range, single-bar day range, NaN values in minute cache
- Test `_check_sell_conditions()` passes `minute_day_ranges` correctly to evaluator
- Test missing minute data for a trading day (should skip and log warning)

### Property-Based Tests

- Generate random minute indicator values for a day range and verify intra-day scanning triggers correctly for numeric conditions (Property 1)
- Generate random daily indicator values and verify daily-frequency evaluation is unchanged (Property 2)
- Generate random minute kline bar sequences and verify `minute_day_ranges` mapping properties: contiguous, non-overlapping, complete coverage (Property 3)
- Generate mixed daily/minute condition configs and verify AND/OR combination correctness (Property 4)

### Integration Tests

- Test full `_check_sell_conditions()` flow with minute-frequency conditions and real-shaped minute kline data
- Test that risk conditions (stop-loss, trend break) still take priority over minute-frequency exit conditions
- Test T+1 rule is preserved when minute-frequency conditions trigger sell signals
- Test backward compatibility: existing daily-only exit condition tests continue to pass without modification
