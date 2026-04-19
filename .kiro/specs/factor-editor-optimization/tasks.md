# Implementation Plan: 智能选股因子条件编辑器优化

## Overview

本实现计划将因子条件编辑器优化功能分解为增量式编码任务。从后端核心数据结构和注册表开始，逐步扩展到计算服务、评估器适配、API 端点，最后完成前端 UI 增强。每个任务构建在前一个任务的基础上，确保无孤立代码。

## Tasks

- [x] 1. Create factor registry module with ThresholdType, FactorMeta, and FACTOR_REGISTRY
  - [x] 1.1 Create `app/services/screener/factor_registry.py` with ThresholdType enum, FactorCategory enum, and FactorMeta frozen dataclass
    - Define `ThresholdType(str, Enum)` with values: ABSOLUTE, PERCENTILE, INDUSTRY_RELATIVE, Z_SCORE, BOOLEAN, RANGE
    - Define `FactorCategory(str, Enum)` with values: TECHNICAL, MONEY_FLOW, FUNDAMENTAL, SECTOR
    - Define `FactorMeta` frozen dataclass with fields: factor_name, label, category, threshold_type, default_threshold, value_min, value_max, unit, description, examples, default_range
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Populate FACTOR_REGISTRY constant with all factor definitions
    - Add 7 technical factors (ma_trend, ma_support, macd, boll, rsi, dma, breakout) per design spec
    - Add 4 money_flow factors (turnover, money_flow, large_order, volume_price) with correct threshold types
    - Add 6 fundamental factors (pe, pb, roe, profit_growth, market_cap, revenue_growth) with correct threshold types
    - Add 2 sector factors (sector_rank, sector_trend) with examples including data source info
    - Implement `get_factor_meta(factor_name)` and `get_factors_by_category(category)` helper functions
    - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3_

  - [x] 1.3 Write property test for FACTOR_REGISTRY structure integrity
    - **Property 1: FACTOR_REGISTRY 结构完整性**
    - Verify all entries have required fields with valid types, threshold_type is valid ThresholdType enum member
    - **Validates: Requirements 1.2, 1.3**

  - [x] 1.4 Write unit tests for factor registry module
    - Test ma_trend metadata definition (Req 2.1)
    - Test all boolean factors metadata (Req 2.2-2.4, 2.6-2.7)
    - Test rsi range metadata (Req 2.5)
    - Test money_flow percentile metadata (Req 3.2)
    - Test pe industry_relative metadata (Req 4.1)
    - Test sector_rank metadata (Req 6.1)
    - Test get_factor_meta and get_factors_by_category helpers
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.2, 4.1, 6.1_

- [x] 2. Create strategy examples module
  - [x] 2.1 Create `app/services/screener/strategy_examples.py` with StrategyExample dataclass and STRATEGY_EXAMPLES constant
    - Define `StrategyExample` dataclass with fields: name, description, factors, logic, weights, enabled_modules, sector_config
    - Populate STRATEGY_EXAMPLES with all 12 strategy examples from requirements (Req 14.4)
    - Each example must use FACTOR_REGISTRY-compatible threshold types and value ranges
    - _Requirements: 14.1, 14.4, 14.5, 14.6, 14.8_

  - [x] 2.2 Write property test for strategy examples consistency
    - **Property 9: 策略示例一致性**
    - Verify all examples have required fields, all factor_names exist in FACTOR_REGISTRY, threshold values within defined ranges
    - **Validates: Requirements 14.5, 14.8**

  - [x] 2.3 Write unit tests for strategy examples
    - Test at least 12 examples exist (Req 14.1)
    - Test each example has all required fields (Req 14.5)
    - _Requirements: 14.1, 14.5_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Extend StrategyConfig with SectorScreenConfig and serialization updates
  - [x] 4.1 Add SectorScreenConfig dataclass to `app/core/schemas.py`
    - Define `SectorScreenConfig` with fields: sector_data_source (default "DC"), sector_type (default "CONCEPT"), sector_period (default 5), sector_top_n (default 30)
    - Implement `to_dict()` and `from_dict()` methods
    - _Requirements: 5.1, 13.2_

  - [x] 4.2 Add sector_config field to StrategyConfig and update serialization
    - Add `sector_config: SectorScreenConfig = field(default_factory=SectorScreenConfig)` to StrategyConfig
    - Update `StrategyConfig.to_dict()` to include sector_config serialization
    - Update `StrategyConfig.from_dict()` to deserialize sector_config with backward-compatible defaults
    - _Requirements: 5.1, 13.2, 13.3, 13.4_

  - [x] 4.3 Write property test for StrategyConfig round-trip serialization
    - **Property 7: StrategyConfig 序列化往返**
    - Generate random StrategyConfig instances (including sector_config), verify to_dict() then from_dict() produces equivalent values
    - **Validates: Requirements 5.1, 13.3, 13.4**

  - [x] 4.4 Write property test for backward-compatible default values
    - **Property 8: 向后兼容默认值**
    - Generate legacy config dicts without threshold_type or sector_config, verify deserialization produces valid defaults
    - **Validates: Requirements 13.1, 13.2**

  - [x] 4.5 Write unit tests for SectorScreenConfig and StrategyConfig backward compatibility
    - Test SectorScreenConfig to_dict/from_dict
    - Test StrategyConfig.from_dict with legacy config missing sector_config
    - Test StrategyConfig.to_dict includes sector_config
    - _Requirements: 5.1, 13.1, 13.2, 13.3, 13.4_

- [x] 5. Implement SectorStrengthFilter module
  - [x] 5.1 Create `app/services/screener/sector_strength.py` with SectorStrengthFilter class
    - Define `SectorRankResult` dataclass with fields: sector_code, sector_name, rank, change_pct, is_bullish
    - Implement `compute_sector_ranks()` method: query SectorKline for specified data_source and sector_type, compute cumulative change over sector_period, rank in descending order
    - Implement `map_stocks_to_sectors()` method: query SectorConstituent for latest trade_date, build symbol → [sector_code] mapping
    - Implement `filter_by_sector_strength()` method: write sector_rank, sector_trend, sector_name into stock_data dicts
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

  - [x] 5.2 Write property test for sector rank ordering
    - **Property 6: 板块涨跌幅排名有序性**
    - Generate sector kline data with cumulative changes, verify ranks are in descending order of change, verify stock-to-sector mapping consistency
    - **Validates: Requirements 5.4, 5.5**

  - [x] 5.3 Write unit tests for SectorStrengthFilter
    - Test sector data unavailable graceful degradation (Req 5.6)
    - Test rank computation with sample data
    - Test stock-to-sector mapping
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 6. Enhance ScreenDataProvider with percentile ranking and industry-relative values
  - [x] 6.1 Implement percentile ranking computation in ScreenDataProvider
    - Add `_compute_percentile_ranks(stocks_data, factor_names)` method
    - Use ascending percentile formula: percentile = (rank_position / total_valid) × 100
    - Exclude None values from ranking; write results to `{factor}_pctl` fields
    - Handle edge cases: all None values (skip), single stock (percentile = 100)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6_

  - [x] 6.2 Implement industry-relative value computation in ScreenDataProvider
    - Add `_compute_industry_relative_values(stocks_data, factor_names, industry_map)` method
    - Add `_build_industry_map()` method to query SectorConstituent for INDUSTRY type mapping
    - Compute industry median, calculate (stock_value / industry_median) as relative value
    - Write results to `{factor}_ind_rel` fields; handle missing industry or zero median (set to None)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

  - [x] 6.3 Integrate sector strength data loading into ScreenDataProvider.load_screen_data()
    - Add `_load_sector_strength_data(sector_config)` method using SectorStrengthFilter
    - Call percentile ranking, industry-relative, and sector strength computations after building factor dicts
    - Handle database errors gracefully: log WARNING, skip sector data, don't block other factors
    - _Requirements: 5.2, 5.3, 5.6, 9.1, 10.1_

  - [x] 6.4 Write property test for percentile ranking invariants
    - **Property 2: 百分位排名不变量**
    - Generate random float/None lists, verify: all ranks in [0, 100], None stocks get no rank, max value gets highest rank, min value gets lowest rank, monotonicity preserved
    - **Validates: Requirements 3.3, 3.6, 9.1, 9.2, 9.3, 9.6**

  - [x] 6.5 Write property test for industry-relative value correctness
    - **Property 3: 行业相对值计算正确性**
    - Generate stocks grouped by industry with positive values, verify relative value = stock_value / industry_median, stock at median gets 1.0
    - **Validates: Requirements 4.7, 10.1, 10.3**

  - [x] 6.6 Write unit tests for ScreenDataProvider enhancements
    - Test percentile with all None values (edge case)
    - Test percentile with single stock (edge case)
    - Test industry-relative with missing industry (edge case)
    - Test industry-relative with zero median (edge case)
    - Test sector data unavailable degradation (Req 5.6)
    - _Requirements: 9.1, 9.2, 9.6, 10.3, 10.6, 5.6_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Adapt FactorEvaluator for threshold type awareness
  - [x] 8.1 Modify FactorEvaluator.evaluate() in `app/services/screener/strategy_engine.py`
    - Import FACTOR_REGISTRY and get_factor_meta from factor_registry module
    - Query FACTOR_REGISTRY for threshold_type; fallback to ABSOLUTE if factor not found
    - For PERCENTILE type: read `{factor_name}_pctl` field from stock_data
    - For INDUSTRY_RELATIVE type: read `{factor_name}_ind_rel` field from stock_data
    - For RANGE type: check value in [threshold_low, threshold_high] from condition.params
    - For BOOLEAN and ABSOLUTE: preserve existing behavior
    - Support `threshold_type` override in FactorCondition.params for backward compatibility
    - If resolved field is missing or None, set passed=False
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1_

  - [x] 8.2 Write property test for FactorEvaluator threshold type field resolution
    - **Property 4: FactorEvaluator 阈值类型字段解析**
    - Generate FactorConditions with various threshold types and stock_data, verify correct field is read and comparison result is consistent
    - **Validates: Requirements 9.5, 10.5, 12.1, 12.2, 12.3, 12.4**

  - [x] 8.3 Write property test for range type evaluation
    - **Property 5: Range 类型区间评估**
    - Generate random values and range bounds, verify passed iff low ≤ value ≤ high
    - **Validates: Requirements 12.5**

  - [x] 8.4 Write unit tests for enhanced FactorEvaluator
    - Test percentile factor evaluation
    - Test industry_relative factor evaluation
    - Test range factor evaluation
    - Test boolean factor evaluation (unchanged behavior)
    - Test missing _pctl field handling
    - Test legacy factor condition backward compatibility (Req 13.1)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1_

- [x] 9. Add API endpoints for factor registry and strategy examples
  - [x] 9.1 Add GET /screen/factor-registry endpoint to `app/api/v1/screen.py`
    - Import FACTOR_REGISTRY and get_factors_by_category from factor_registry module
    - Return factor metadata grouped by category (technical, money_flow, fundamental, sector)
    - Support optional `category` query parameter for filtering; return empty list for invalid category
    - Serialize FactorMeta dataclass fields to JSON-compatible dict
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 9.2 Add GET /screen/strategy-examples endpoint to `app/api/v1/screen.py`
    - Import STRATEGY_EXAMPLES from strategy_examples module
    - Return list of strategy example dicts with all fields
    - Return empty list if no examples available
    - _Requirements: 14.6_

  - [x] 9.3 Add SectorScreenConfigIn Pydantic model and update StrategyConfigIn
    - Add `SectorScreenConfigIn` Pydantic model with sector_data_source, sector_type, sector_period, sector_top_n fields
    - Add `sector_config: SectorScreenConfigIn` field to `StrategyConfigIn` with default factory
    - Update `ScreenRunRequest` handling to pass sector_config through to ScreenDataProvider
    - _Requirements: 5.1, 8.4_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Enhance frontend screener store with factor registry and strategy examples
  - [x] 11.1 Update `frontend/src/stores/screener.ts` with new state and fetch methods
    - Add `factorRegistry` ref to store factor metadata grouped by category
    - Add `strategyExamples` ref to store strategy example list
    - Add `fetchFactorRegistry()` method calling GET /screen/factor-registry
    - Add `fetchStrategyExamples()` method calling GET /screen/strategy-examples
    - Add TypeScript interfaces: `FactorMeta`, `ThresholdType`, `StrategyExample`, `SectorScreenConfig`
    - _Requirements: 1.4, 14.2_

- [x] 12. Enhance frontend factor editor UI
  - [x] 12.1 Add threshold type labels and tooltips to factor editor in ScreenerView.vue
    - Display threshold type badge (百分位/行业相对/绝对值/布尔/区间) on each factor row
    - Display unit and value range hint next to threshold input
    - Show tooltip on factor name hover with description and examples from factorRegistry
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 12.2 Implement boolean toggle and range dual-input controls
    - Replace threshold input with toggle switch for boolean-type factors; hide operator selector
    - Replace single threshold input with dual inputs (lower/upper) for range-type factors; auto-set operator to "BETWEEN"
    - Add "reset to default" button per factor row, restoring FACTOR_REGISTRY default values on click
    - _Requirements: 7.4, 7.5, 7.6_

  - [x] 12.3 Implement sector data source and type selectors
    - Add data source dropdown (DC/TI/TDX) for sector-category factors
    - Add sector type dropdown (INDUSTRY/CONCEPT/REGION/STYLE) for sector-category factors
    - Add sector period input (1-60 days, default 5) for sector-category factors
    - Save selections to StrategyConfig.sector_config; restore on template load
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 12.4 Implement strategy examples loader UI
    - Add "加载示例策略" button to factor editor toolbar
    - Show strategy example selection dialog with name, description, and factor category tags
    - On selection, load full StrategyConfig (factors, logic, weights, enabled_modules, sector_config) into editor
    - Auto-enable required modules from example's enabled_modules list
    - _Requirements: 14.2, 14.3, 14.7_

  - [x] 12.5 Write frontend property tests
    - **Property 7 (frontend): StrategyConfig JSON round-trip** — serialize/deserialize StrategyConfig with sector_config, verify equivalence using fast-check
    - **Property 9 (frontend): Strategy example config completeness** — verify loaded examples have all required fields using fast-check
    - _Requirements: 13.3, 13.4, 14.5_

  - [x] 12.6 Write frontend unit tests
    - Test factor-registry API integration and data binding
    - Test boolean factor toggle rendering
    - Test range factor dual-input rendering
    - Test factor tooltip display
    - Test reset-default button functionality
    - Test sector selector rendering
    - Test strategy example loader
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 14.2_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement SectorStrengthFilter change_pct fallback (Requirement 15)
  - [x] 14.1 Modify `_aggregate_change_pct()` in `app/services/screener/sector_strength.py` to add close-price fallback
    - When all change_pct are NULL for a sector, compute from close prices: `(latest_close - earliest_close) / earliest_close * 100`
    - Prioritize change_pct when any valid records exist (> 0 non-NULL); only fallback when ALL are NULL
    - If fewer than 2 valid close prices, set change to 0.0
    - Add division-by-zero protection when earliest close is 0.0
    - Return type remains float for both paths
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 14.2 Write property test for change_pct fallback correctness
    - **Property 10: change_pct fallback 正确性**
    - Create test in `tests/properties/test_factor_editor_properties.py`
    - Generate random kline data with mixed NULL/non-NULL change_pct and close values using Hypothesis
    - Verify: when all change_pct NULL → close price formula used; when any change_pct non-NULL → sum of change_pct used; when < 2 valid closes → 0.0
    - Minimum 100 iterations
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4**

  - [x] 14.3 Write unit tests for change_pct fallback edge cases
    - Create test file `tests/services/test_sector_strength_fallback.py`
    - Test all change_pct NULL with valid close prices (Req 15.1)
    - Test partial change_pct NULL uses change_pct sum (Req 15.3)
    - Test fewer than 2 valid close prices returns 0.0 (Req 15.2)
    - Test earliest close = 0.0 returns 0.0 (division-by-zero protection)
    - Test all close also NULL returns 0.0
    - Test return type is always float (Req 15.4)
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 15. Implement sector coverage API endpoint (Requirement 16)
  - [x] 15.1 Add GET /api/v1/sector/coverage endpoint to `app/api/v1/sector.py`
    - Add `CoverageSourceStats` and `CoverageResponse` Pydantic models
    - Query SectorInfo for total sector count per data source (DC/TI/TDX)
    - Query SectorConstituent for sectors with constituent data and distinct stock count (latest trade_date)
    - Compute coverage_ratio = sectors_with_constituents / total_sectors
    - Handle empty data sources gracefully (return zero values)
    - _Requirements: 16.2_

  - [x] 15.2 Write unit/integration tests for sector coverage endpoint
    - Create test file `tests/api/test_sector_coverage.py`
    - Test endpoint returns all three data sources (DC/TI/TDX)
    - Test response structure contains required fields
    - Test empty data source returns zero values
    - _Requirements: 16.2_

- [x] 16. Add frontend sector coverage display and warning (Requirement 16)
  - [x] 16.1 Update `frontend/src/stores/screener.ts` with coverage state and fetch method
    - Add `CoverageSourceStats` interface
    - Add `sectorCoverage` ref and `fetchSectorCoverage()` method calling GET /sector/coverage
    - _Requirements: 16.1, 16.2_

  - [x] 16.2 Update `frontend/src/views/ScreenerView.vue` sector data source selector
    - Display coverage summary in data source dropdown options: "数据源名称（板块数 / 成分股覆盖数）"
    - Show warning when selecting a data source with coverage_ratio < 0.5 (e.g., TI)
    - Warning text: "该数据源成分股数据不完整，可能影响板块筛选效果，建议使用东方财富（DC）或通达信（TDX）"
    - Call `fetchSectorCoverage()` on component mount
    - _Requirements: 16.1, 16.3_

  - [x] 16.3 Write frontend unit tests for coverage display
    - Add tests to `frontend/src/views/__tests__/ScreenerView.test.ts`
    - Test data source dropdown displays coverage info (Req 16.1)
    - Test low-coverage warning appears for TI (Req 16.3)
    - Test no warning for DC and TDX
    - _Requirements: 16.1, 16.3_

- [x] 17. Checkpoint - Ensure all new tests pass
  - Run backend tests: `pytest tests/properties/test_factor_editor_properties.py tests/services/test_sector_strength_fallback.py tests/api/test_sector_coverage.py`
  - Run frontend tests: `npm test` in frontend/
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (10 properties from design document, using Hypothesis for backend and fast-check for frontend)
- Unit tests validate specific examples, edge cases, and error handling
- Backend uses Python 3.11+; frontend uses TypeScript with Vue 3 Composition API
- All new backend modules follow existing project structure under `app/services/screener/`
- All new tests follow existing conventions: `tests/properties/` for Hypothesis, `tests/services/` for unit tests, `frontend/src/views/__tests__/` for frontend tests
- Tasks 1-13 cover requirements 1-14 (original scope)
- Tasks 14-17 cover requirements 15-16 (change_pct fallback and coverage API/UI)
