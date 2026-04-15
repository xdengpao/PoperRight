# Implementation Plan: 前复权K线数据 (Forward-Adjusted K-line Data)

## Overview

本实现计划将前复权K线数据功能分解为增量编码步骤，从核心纯函数计算层开始，逐步扩展到数据访问层、服务集成层、API 层、前端 UI 和回测集成。每个步骤都在前一步基础上构建，确保无孤立代码。

## Tasks

- [x] 1. Implement ForwardAdjustmentCalculator core module
  - [x] 1.1 Create `app/services/data_engine/forward_adjustment.py` with `adjust_kline_bars` and `_find_factor_for_date` pure functions
    - Implement the forward-adjustment formula: `adjusted_price = raw_price × (daily_factor / latest_factor)`, rounded to 2 decimal places
    - Use `Decimal` for all price arithmetic to avoid floating-point errors
    - Build a `{trade_date: adj_factor}` lookup map from the factors list
    - Use `bisect` to find the nearest preceding factor when exact date match is missing
    - Return original bars unchanged when factors list is empty or latest_factor is zero, logging a warning
    - Only adjust OHLC fields; preserve volume, amount, turnover, vol_ratio, and all other fields
    - Return new `KlineBar` objects (no mutation of input data)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 1.2 Write property test: Formula correctness (Property 1)
    - **Property 1: 前复权公式正确性**
    - For any valid raw KlineBar and adjustment factor combination, each adjusted OHLC price must equal `round(raw_price × (daily_factor / latest_factor), 2)`
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 2.1, 2.3**

  - [x] 1.3 Write property test: Volume/amount invariance (Property 2)
    - **Property 2: 成交量和成交额不变性**
    - For any raw KlineBar and adjustment factor combination, volume and amount must remain identical after forward adjustment
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 2.2**

  - [x] 1.4 Write property test: Factor fallback lookup (Property 3)
    - **Property 3: 因子回退查找正确性**
    - When a KlineBar's trade date has no exact factor match, the calculator must use the nearest preceding factor
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 2.4**

  - [x] 1.5 Write property test: OHLC price ordering preservation (Property 4)
    - **Property 4: 前复权价格保序性**
    - For any valid raw KlineBar where `low ≤ open`, `low ≤ close`, `high ≥ open`, `high ≥ close`, the same ordering must hold after forward adjustment
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 2.6, 6.1, 7.8**

  - [x] 1.6 Write property test: Same-factor price direction consistency (Property 5)
    - **Property 5: 同因子价格变动方向一致性**
    - For any two consecutive KlineBars sharing the same adjustment factor, if `close[i+1] > close[i]` in raw data, then `adjusted_close[i+1] > adjusted_close[i]` (and vice versa)
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 6.2**

  - [x] 1.7 Write property test: Constant-factor identity (Property 6)
    - **Property 6: 恒定因子恒等性**
    - When all daily factors equal the latest factor (no ex-dividend events), adjusted OHLC prices must be identical to raw prices
    - Test file: `tests/properties/test_forward_adjustment_properties.py`
    - **Validates: Requirements 6.3**

  - [x] 1.8 Write unit tests for `adjust_kline_bars` edge cases
    - Test file: `tests/services/test_forward_adjustment.py`
    - Test empty factors list returns original bars
    - Test latest_factor = 0 returns original bars
    - Test single bar + single factor produces correct numeric result
    - Test multiple bars with partial date coverage verifies fallback logic
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2. Checkpoint — Ensure all core calculator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Extend AdjFactorRepository with query methods
  - [x] 3.1 Add `query_by_symbol`, `query_latest_factor`, and `query_batch` async methods to `app/services/data_engine/adj_factor_repository.py`
    - `query_by_symbol(symbol, adj_type, start, end)` → returns `list[AdjustmentFactor]` ordered by trade_date ascending
    - `query_latest_factor(symbol, adj_type)` → returns `Decimal | None` for the most recent trade_date's factor
    - `query_batch(symbols, adj_type, start, end)` → returns `dict[str, list[AdjustmentFactor]]` via a single SQL query to reduce DB round-trips
    - Reuse existing `_get_session_ctx` pattern for session management
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 3.2 Write unit tests for AdjFactorRepository query methods
    - Test file: `tests/services/test_adj_factor_repository.py`
    - Test `query_by_symbol` returns factors in ascending date order
    - Test `query_by_symbol` returns empty list when no data exists
    - Test `query_latest_factor` returns the most recent factor value
    - Test `query_batch` groups results by symbol correctly
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 4. Integrate forward adjustment into ScreenDataProvider
  - [x] 4.1 Modify `app/services/screener/screen_data_provider.py` to apply forward adjustment before indicator calculation
    - Import `AdjFactorRepository` and `adjust_kline_bars`
    - In `load_screen_data`, after loading valid stocks, call `adj_repo.query_batch(...)` to batch-fetch all forward-adjustment factors (adj_type=1)
    - For each stock, if factors exist, compute `latest_factor` from the last factor in the sorted list and call `adjust_kline_bars(bars, factors, latest)`
    - Pass the adjusted bars to `_build_factor_dict` so all downstream indicator modules (MA, MACD, BOLL, RSI, DMA, breakout) receive forward-adjusted prices
    - Add `raw_close` field to factor_dict preserving the original unadjusted close price
    - When a stock has no adjustment factors, use original bars and log a warning
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 4.2 Write unit tests for ScreenDataProvider forward-adjustment integration
    - Test file: `tests/services/test_screen_data_provider_adj.py`
    - Mock AdjFactorRepository and KlineRepository
    - Verify adjusted prices are passed to indicator calculation
    - Verify `raw_close` is preserved in factor_dict
    - Verify graceful fallback when no factors exist
    - _Requirements: 3.1, 3.3, 3.5_

- [x] 5. Add adj_type support to K-line Data API
  - [x] 5.1 Modify `app/api/v1/data.py` `get_kline` endpoint to apply forward adjustment when `adj_type=1`
    - After fetching raw bars from TimescaleDB, if `adj_type == 1` and bars exist, query adjustment factors via `AdjFactorRepository` and apply `adjust_kline_bars`
    - Ensure `adj_type` field is included in the response (already present in current code)
    - When `adj_type=0` or not provided, return raw bars unchanged (backward compatible)
    - When factor query fails, return raw bars and log a warning
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.2 Write unit tests for K-line API adj_type parameter
    - Test file: `tests/api/test_kline_adj.py`
    - Test `adj_type=0` returns raw data
    - Test `adj_type=1` returns forward-adjusted data
    - Test default (no adj_type) returns raw data
    - Test response includes `adj_type` field
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement frontend adj_type toggle UI
  - [x] 7.1 Update `frontend/src/components/minuteKlineUtils.ts` to support adj_type
    - Add `AdjType` type alias: `export type AdjType = 0 | 1`
    - Update `buildCacheKey` signature to accept optional `adjType: AdjType = 0` parameter, appending it to the cache key string
    - Update `buildRequestParams` signature to accept optional `adjType: AdjType = 0` parameter, including `adj_type` in the returned params object
    - Maintain backward compatibility: existing callers without adjType still work (defaults to 0)
    - _Requirements: 5.6_

  - [x] 7.2 Write property test: Cache key adj_type differentiation (Property 7)
    - **Property 7: 缓存键复权类型区分性**
    - For any symbol, date, freq, and adjType combination, different adjType values must produce different cache keys; same parameters must produce identical keys
    - Test file: `frontend/src/components/__tests__/minuteKlineUtils.property.test.ts`
    - Use fast-check for property-based testing
    - **Validates: Requirements 5.6**

  - [x] 7.3 Update `frontend/src/components/MinuteKlineChart.vue` to add adj_type toggle
    - Add `ADJ_OPTIONS` constant array with `{ value: 0, label: '原始' }` and `{ value: 1, label: '前复权' }` options
    - Add `adjType` ref with default value `0`
    - Add adj-selector button group in template between freq-selector and chart-area, with `role="group"` and `aria-label="复权类型选择"`
    - Disable toggle buttons while `loading` is true to prevent duplicate requests
    - Update `buildCacheKey` and `buildRequestParams` calls to pass `adjType.value`
    - Add `adjType` to the watch array so changing adj type triggers `loadMinuteKline()`
    - Add CSS styles for `.adj-selector` and `.adj-btn` matching existing `.freq-selector` / `.freq-btn` patterns
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7_

  - [x] 7.4 Write unit tests for MinuteKlineChart adj_type toggle
    - Test file: `frontend/src/components/__tests__/MinuteKlineChart.test.ts`
    - Test default adjType is 0
    - Test clicking "前复权" button triggers API request with adj_type=1
    - Test toggle buttons are disabled during loading
    - Test switching adj_type preserves selected date and freq
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.7_

- [x] 8. Integrate forward adjustment into BacktestTask
  - [x] 8.1 Modify `app/tasks/backtest.py` to load adjustment factors and apply forward adjustment
    - Import `adjust_kline_bars` from `app.services.data_engine.forward_adjustment` and `AdjustmentFactor` model
    - After loading K-line data from TimescaleDB, add a new section to batch-query all forward-adjustment factors (adj_type=1) for the warmup_date to end_date range
    - Query latest factors per symbol using `DISTINCT ON (symbol) ... ORDER BY symbol, trade_date DESC`
    - Construct `AdjustmentFactor` objects from raw SQL rows
    - For each symbol in `kline_data`, apply `adjust_kline_bars(bars, factors, latest)` if factors and latest_factor exist
    - Log a warning for symbols without adjustment factor data and continue with raw bars
    - Ensure BacktestEngine receives forward-adjusted prices for indicator pre-calculation, signal generation, and equity curve computation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 8.2 Write unit tests for BacktestTask forward-adjustment integration
    - Test file: `tests/tasks/test_backtest_adj.py`
    - Mock TimescaleDB session to return known K-line and adjustment factor data
    - Verify `adjust_kline_bars` is called with correct arguments
    - Verify symbols without factors use raw bars and log a warning
    - _Requirements: 7.1, 7.2, 7.6_

- [x] 9. Checkpoint — Ensure all existing tests pass before daily K-line toggle
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement daily K-line adj_type toggle in ScreenerResultsView
  - [x] 10.1 Add daily K-line reactive state and cache infrastructure in `frontend/src/views/ScreenerResultsView.vue`
    - Import `AdjType` from `@/components/minuteKlineUtils`
    - Add `dailyAdjType` reactive state (`reactive<Record<string, AdjType>>({})`) to track per-symbol daily K-line adj type
    - Add `dailyKlineCache` as a `Map<string, any[]>()` for caching daily K-line bars by adj_type
    - Add `DAILY_ADJ_OPTIONS` constant array: `[{ value: 0, label: '原始' }, { value: 1, label: '前复权' }]`
    - Add `buildDailyKlineCacheKey(symbol: string, adjType: AdjType): string` helper returning `daily-${symbol}-${adjType}`
    - _Requirements: 8.4, 8.8_

  - [x] 10.2 Modify `fetchKline` to accept `adjType` parameter and use daily K-line cache
    - Change signature to `fetchKline(symbol: string, adjType: AdjType = 0)`
    - Compute cache key via `buildDailyKlineCacheKey(symbol, adjType)`
    - On cache hit, call `rebuildKlineOptions(symbol, cachedBars, adjType)` and return early
    - On cache miss, include `adj_type: adjType` in the API request params
    - Store fetched bars in `dailyKlineCache` under the computed cache key
    - Call `rebuildKlineOptions(symbol, bars, adjType)` after successful fetch
    - Remove the early-return guard `if (klineOptions[symbol] || klineLoading[symbol]) return` — replace with cache-based logic
    - _Requirements: 8.2, 8.3, 8.4, 8.8_

  - [x] 10.3 Extract `rebuildKlineOptions` function that preserves dataZoom and markLine
    - Extract chart-building logic from `fetchKline` into `rebuildKlineOptions(symbol: string, bars: any[], adjType: AdjType)`
    - Before building new options, read current `klineOptions[symbol]` to capture existing `dataZoom[0].start/end` and `series[0].markLine`
    - Apply preserved `dataZoom` start/end values (fallback to `60`/`100` if no previous options)
    - Restore `markLine` data from previous options if it existed
    - Update `latestTradeDates[symbol]` and `klineDateArrays[symbol]` from the new bars
    - _Requirements: 8.5_

  - [x] 10.4 Add toggle buttons and `onDailyAdjTypeChange` handler in the detail-row template
    - Add `.adj-selector` button group above the daily K-line chart `<v-chart>` in the detail-row template
    - Use `v-for="opt in DAILY_ADJ_OPTIONS"` with `:class="['adj-btn', (dailyAdjType[row.symbol] ?? 0) === opt.value && 'active']"`
    - Disable buttons when `klineLoading[row.symbol]` is true
    - Add `role="group"` and `aria-label="日K线复权类型选择"` for accessibility
    - Implement `onDailyAdjTypeChange(symbol: string, adjType: AdjType)` that sets `dailyAdjType[symbol] = adjType` and calls `fetchKline(symbol, adjType)`
    - Update `toggleExpand` to call `fetchKline(symbol, dailyAdjType[symbol] ?? 0)` instead of `fetchKline(symbol)`
    - _Requirements: 8.1, 8.2, 8.3, 8.6_

  - [x] 10.5 Add `.adj-selector` and `.adj-btn` CSS styles to ScreenerResultsView
    - Add scoped CSS for `.adj-selector` (flex container with gap) and `.adj-btn` (styled toggle button with active state)
    - Match the styling patterns from MinuteKlineChart's `.adj-selector` / `.adj-btn` for visual consistency
    - _Requirements: 8.1_

  - [x] 10.6 Verify daily K-line click interaction still works after refactor
    - Ensure `onDailyKlineClick` correctly updates `selectedDates[symbol]` and markLine after the `rebuildKlineOptions` extraction
    - Ensure clicking a daily K-line date passes the selected date to MinuteKlineChart, and minute K-line adj_type remains independent
    - _Requirements: 8.7_

  - [ ]* 10.7 Write unit tests for daily K-line adj_type toggle
    - Test file: `frontend/src/views/__tests__/ScreenerResultsView.dailyAdj.test.ts`
    - Test default `dailyAdjType` is `0` (original K-line)
    - Test clicking "前复权" button triggers API request with `adj_type=1`
    - Test toggle buttons are disabled during loading
    - Test switching adj_type preserves dataZoom range and markLine
    - Test daily K-line adj_type and minute K-line adj_type are independent
    - Test different adj_type values produce independent cache entries
    - _Requirements: 8.1, 8.2, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 10.8 Write property test: dataZoom and markLine preservation on daily K-line toggle (Property 8)
    - **Property 8: 日K线图切换复权类型时 dataZoom 和 markLine 保持不变**
    - For any dataZoom start/end percentages (0–100) and any selected markLine date, after calling `rebuildKlineOptions` with new bars, the resulting chart options must preserve the same dataZoom start/end and markLine data
    - Test file: `frontend/src/views/__tests__/ScreenerResultsView.dailyAdj.property.test.ts`
    - Use fast-check for property-based testing
    - **Validates: Requirements 8.5**

  - [ ]* 10.9 Write property test: Daily K-line cache key adj_type differentiation (Property 9)
    - **Property 9: 日K线缓存键复权类型区分性**
    - For any symbol, `buildDailyKlineCacheKey(symbol, 0)` and `buildDailyKlineCacheKey(symbol, 1)` must produce different cache keys; same symbol and adjType must produce identical keys
    - Test file: `frontend/src/views/__tests__/ScreenerResultsView.dailyAdj.property.test.ts`
    - Use fast-check for property-based testing
    - **Validates: Requirements 8.8**

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (9 properties)
- Unit tests validate specific examples and edge cases
- Backend uses Python (Hypothesis for property tests, pytest for unit tests)
- Frontend uses TypeScript (fast-check for property tests, Vitest for unit tests)
- The `ForwardAdjustmentCalculator` is implemented as pure functions (not a class) since the computation is stateless
- Task 10 implements Requirement 8 (日K线图复权类型切换) with Properties 8 and 9 from the design document
