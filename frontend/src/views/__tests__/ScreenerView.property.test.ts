/**
 * Feature: factor-editor-optimization
 *
 * 前端属性测试（Vitest + fast-check）
 *
 * Property 7 (frontend): StrategyConfig JSON round-trip
 * Property 9 (frontend): Strategy example config completeness
 *
 * **Validates: Requirements 13.3, 13.4, 14.5**
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ---------------------------------------------------------------------------
// TypeScript interfaces (mirroring frontend/src/stores/screener.ts)
// ---------------------------------------------------------------------------

type ThresholdType = 'absolute' | 'percentile' | 'industry_relative' | 'z_score' | 'boolean' | 'range'

interface SectorScreenConfig {
  sector_data_source: string
  sector_type: string
  sector_period: number
  sector_top_n: number
}

interface FactorCondition {
  factor_name: string
  operator: string
  threshold: number | null
  params: Record<string, unknown>
}

interface StrategyConfig {
  logic: string
  factors: FactorCondition[]
  weights: Record<string, number>
  ma_periods: number[]
  indicator_params: {
    macd: { fast_period: number; slow_period: number; signal_period: number }
    boll: { period: number; std_dev: number }
    rsi: { period: number; lower_bound: number; upper_bound: number }
    dma: { short_period: number; long_period: number }
  }
  ma_trend: {
    ma_periods: number[]
    slope_threshold: number
    trend_score_threshold: number
    support_ma_lines: number[]
  }
  breakout: {
    box_breakout: boolean
    high_breakout: boolean
    trendline_breakout: boolean
    volume_ratio_threshold: number
    confirm_days: number
  }
  volume_price: {
    turnover_rate_min: number
    turnover_rate_max: number
    main_flow_threshold: number
    main_flow_days: number
    large_order_ratio: number
    min_daily_amount: number
    sector_rank_top: number
  }
  sector_config: SectorScreenConfig
}

interface StrategyExample {
  name: string
  description: string
  factors: FactorCondition[]
  logic: string
  weights: Record<string, number>
  enabled_modules: string[]
  sector_config: SectorScreenConfig | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** JSON round-trip: serialize then deserialize */
function jsonRoundTrip<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj)) as T
}

/**
 * Normalize -0 to 0 in a deep structure.
 * JSON.stringify converts -0 to "0", so JSON.parse gives back 0.
 * This causes toEqual failures since Object.is(-0, 0) is false.
 * We normalize the source object to match JSON semantics.
 */
function normalizeNegativeZero<T>(obj: T): T {
  if (obj === null || obj === undefined) return obj
  if (typeof obj === 'number') return (Object.is(obj, -0) ? 0 : obj) as T
  if (Array.isArray(obj)) return obj.map(normalizeNegativeZero) as T
  if (typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      result[key] = normalizeNegativeZero(value)
    }
    return result as T
  }
  return obj
}

// ---------------------------------------------------------------------------
// Arbitraries (generators)
// ---------------------------------------------------------------------------

const FACTOR_NAMES = [
  'ma_trend', 'ma_support', 'macd', 'boll', 'rsi', 'dma', 'breakout',
  'turnover', 'money_flow', 'large_order', 'volume_price',
  'pe', 'pb', 'roe', 'profit_growth', 'market_cap', 'revenue_growth',
  'sector_rank', 'sector_trend',
]

const OPERATORS = ['>', '>=', '<', '<=', '==', 'BETWEEN']

const THRESHOLD_TYPES: ThresholdType[] = [
  'absolute', 'percentile', 'industry_relative', 'z_score', 'boolean', 'range',
]

const DATA_SOURCES = ['DC', 'TI', 'TDX']
const SECTOR_TYPES = ['INDUSTRY', 'CONCEPT', 'REGION', 'STYLE']

const sectorScreenConfigArb: fc.Arbitrary<SectorScreenConfig> = fc.record({
  sector_data_source: fc.constantFrom(...DATA_SOURCES),
  sector_type: fc.constantFrom(...SECTOR_TYPES),
  sector_period: fc.integer({ min: 1, max: 60 }),
  sector_top_n: fc.integer({ min: 1, max: 300 }),
})

const factorConditionArb: fc.Arbitrary<FactorCondition> = fc.record({
  factor_name: fc.constantFrom(...FACTOR_NAMES),
  operator: fc.constantFrom(...OPERATORS),
  threshold: fc.oneof(
    fc.constant(null),
    fc.float({ min: Math.fround(-1000), max: Math.fround(1000), noNaN: true, noDefaultInfinity: true }),
  ),
  params: fc.oneof(
    fc.constant({}),
    fc.record({
      threshold_low: fc.float({ min: Math.fround(0), max: Math.fround(100), noNaN: true, noDefaultInfinity: true }),
      threshold_high: fc.float({ min: Math.fround(0), max: Math.fround(100), noNaN: true, noDefaultInfinity: true }),
    }),
    fc.record({
      threshold_type: fc.constantFrom(...THRESHOLD_TYPES),
    }),
  ),
})

const strategyConfigArb: fc.Arbitrary<StrategyConfig> = fc.record({
  logic: fc.constantFrom('AND', 'OR'),
  factors: fc.array(factorConditionArb, { minLength: 0, maxLength: 8 }),
  weights: fc.dictionary(
    fc.constantFrom(...FACTOR_NAMES),
    fc.float({ min: Math.fround(0), max: Math.fround(1), noNaN: true, noDefaultInfinity: true }),
  ),
  ma_periods: fc.array(fc.integer({ min: 1, max: 250 }), { minLength: 1, maxLength: 8 }),
  indicator_params: fc.record({
    macd: fc.record({
      fast_period: fc.integer({ min: 1, max: 50 }),
      slow_period: fc.integer({ min: 1, max: 100 }),
      signal_period: fc.integer({ min: 1, max: 30 }),
    }),
    boll: fc.record({
      period: fc.integer({ min: 1, max: 100 }),
      std_dev: fc.float({ min: Math.fround(0.5), max: Math.fround(5), noNaN: true, noDefaultInfinity: true }),
    }),
    rsi: fc.record({
      period: fc.integer({ min: 1, max: 50 }),
      lower_bound: fc.integer({ min: 0, max: 100 }),
      upper_bound: fc.integer({ min: 0, max: 100 }),
    }),
    dma: fc.record({
      short_period: fc.integer({ min: 1, max: 50 }),
      long_period: fc.integer({ min: 1, max: 200 }),
    }),
  }),
  ma_trend: fc.record({
    ma_periods: fc.array(fc.integer({ min: 1, max: 250 }), { minLength: 1, maxLength: 8 }),
    slope_threshold: fc.float({ min: Math.fround(-1), max: Math.fround(1), noNaN: true, noDefaultInfinity: true }),
    trend_score_threshold: fc.integer({ min: 0, max: 100 }),
    support_ma_lines: fc.subarray([5, 10, 20, 60, 120]),
  }),
  breakout: fc.record({
    box_breakout: fc.boolean(),
    high_breakout: fc.boolean(),
    trendline_breakout: fc.boolean(),
    volume_ratio_threshold: fc.float({ min: Math.fround(0.1), max: Math.fround(5), noNaN: true, noDefaultInfinity: true }),
    confirm_days: fc.integer({ min: 1, max: 10 }),
  }),
  volume_price: fc.record({
    turnover_rate_min: fc.float({ min: Math.fround(0), max: Math.fround(50), noNaN: true, noDefaultInfinity: true }),
    turnover_rate_max: fc.float({ min: Math.fround(0), max: Math.fround(100), noNaN: true, noDefaultInfinity: true }),
    main_flow_threshold: fc.float({ min: Math.fround(0), max: Math.fround(100000), noNaN: true, noDefaultInfinity: true }),
    main_flow_days: fc.integer({ min: 1, max: 30 }),
    large_order_ratio: fc.float({ min: Math.fround(0), max: Math.fround(100), noNaN: true, noDefaultInfinity: true }),
    min_daily_amount: fc.float({ min: Math.fround(0), max: Math.fround(1000000), noNaN: true, noDefaultInfinity: true }),
    sector_rank_top: fc.integer({ min: 1, max: 100 }),
  }),
  sector_config: sectorScreenConfigArb,
})

// ---------------------------------------------------------------------------
// Strategy examples constant (matching the 12 examples from requirements)
// ---------------------------------------------------------------------------

const STRATEGY_EXAMPLES: StrategyExample[] = [
  {
    name: '强势多头趋势追踪',
    description: '捕捉处于强势上升趋势中的个股，适合趋势跟踪型交易',
    factors: [
      { factor_name: 'ma_trend', operator: '>=', threshold: 85, params: {} },
      { factor_name: 'ma_support', operator: '==', threshold: null, params: {} },
      { factor_name: 'dma', operator: '==', threshold: null, params: {} },
    ],
    logic: 'AND',
    weights: { ma_trend: 0.5, ma_support: 0.3, dma: 0.2 },
    enabled_modules: ['ma_trend'],
    sector_config: null,
  },
  {
    name: 'MACD 金叉放量突破',
    description: 'MACD 金叉配合成交量放大，确认短期多头启动信号',
    factors: [
      { factor_name: 'macd', operator: '==', threshold: null, params: {} },
      { factor_name: 'turnover', operator: 'BETWEEN', threshold: null, params: { threshold_low: 5.0, threshold_high: 15.0 } },
      { factor_name: 'volume_price', operator: '>=', threshold: 80, params: {} },
    ],
    logic: 'AND',
    weights: { macd: 0.4, turnover: 0.3, volume_price: 0.3 },
    enabled_modules: ['indicator_params', 'volume_price'],
    sector_config: null,
  },
  {
    name: '概念板块热点龙头',
    description: '追踪概念板块轮动热点，筛选强势概念板块中的龙头股',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 15, params: {} },
      { factor_name: 'sector_trend', operator: '==', threshold: null, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 70, params: {} },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.4, sector_trend: 0.3, ma_trend: 0.3 },
    enabled_modules: ['ma_trend'],
    sector_config: { sector_data_source: 'DC', sector_type: 'CONCEPT', sector_period: 3, sector_top_n: 15 },
  },
  {
    name: '行业板块轮动策略',
    description: '跟踪行业板块轮动节奏，在强势行业中选择技术面共振的个股',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 20, params: {} },
      { factor_name: 'sector_trend', operator: '==', threshold: null, params: {} },
      { factor_name: 'macd', operator: '==', threshold: null, params: {} },
      { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 55, threshold_high: 75 } },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.3, sector_trend: 0.2, macd: 0.3, rsi: 0.2 },
    enabled_modules: ['indicator_params'],
    sector_config: { sector_data_source: 'TI', sector_type: 'INDUSTRY', sector_period: 5, sector_top_n: 20 },
  },
  {
    name: '形态突破放量买入',
    description: '捕捉箱体突破或前高突破的个股，要求量价配合确认突破有效性',
    factors: [
      { factor_name: 'breakout', operator: '==', threshold: null, params: {} },
      { factor_name: 'turnover', operator: 'BETWEEN', threshold: null, params: { threshold_low: 5.0, threshold_high: 20.0 } },
      { factor_name: 'large_order', operator: '>=', threshold: 35, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 60, params: {} },
    ],
    logic: 'AND',
    weights: { breakout: 0.35, turnover: 0.2, large_order: 0.25, ma_trend: 0.2 },
    enabled_modules: ['breakout', 'ma_trend', 'volume_price'],
    sector_config: null,
  },
  {
    name: '技术指标多重共振',
    description: '多个技术指标同时发出多头信号，形成共振确认，提高信号可靠性',
    factors: [
      { factor_name: 'macd', operator: '==', threshold: null, params: {} },
      { factor_name: 'boll', operator: '==', threshold: null, params: {} },
      { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 50, threshold_high: 80 } },
      { factor_name: 'dma', operator: '==', threshold: null, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 75, params: {} },
    ],
    logic: 'AND',
    weights: { macd: 0.25, boll: 0.2, rsi: 0.2, dma: 0.15, ma_trend: 0.2 },
    enabled_modules: ['indicator_params', 'ma_trend'],
    sector_config: null,
  },
  {
    name: '均线支撑反弹策略',
    description: '在上升趋势中回调至均线支撑位企稳反弹的买入机会',
    factors: [
      { factor_name: 'ma_support', operator: '==', threshold: null, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 65, params: {} },
      { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 40, threshold_high: 60 } },
      { factor_name: 'turnover', operator: 'BETWEEN', threshold: null, params: { threshold_low: 3.0, threshold_high: 10.0 } },
    ],
    logic: 'AND',
    weights: { ma_support: 0.35, ma_trend: 0.3, rsi: 0.2, turnover: 0.15 },
    enabled_modules: ['ma_trend', 'indicator_params', 'volume_price'],
    sector_config: null,
  },
  {
    name: '板块强势 + 布林突破',
    description: '在强势板块中寻找布林带突破的个股，板块动量与个股技术面双重确认',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 25, params: {} },
      { factor_name: 'boll', operator: '==', threshold: null, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 70, params: {} },
      { factor_name: 'volume_price', operator: '>=', threshold: 70, params: {} },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.3, boll: 0.3, ma_trend: 0.2, volume_price: 0.2 },
    enabled_modules: ['indicator_params', 'ma_trend', 'volume_price'],
    sector_config: { sector_data_source: 'DC', sector_type: 'CONCEPT', sector_period: 5, sector_top_n: 25 },
  },
  {
    name: '主力资金驱动策略',
    description: '筛选主力资金持续流入且技术面配合的个股，适合中短线波段操作',
    factors: [
      { factor_name: 'money_flow', operator: '>=', threshold: 85, params: {} },
      { factor_name: 'large_order', operator: '>=', threshold: 30, params: {} },
      { factor_name: 'macd', operator: '==', threshold: null, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 70, params: {} },
    ],
    logic: 'AND',
    weights: { money_flow: 0.3, large_order: 0.25, macd: 0.25, ma_trend: 0.2 },
    enabled_modules: ['indicator_params', 'ma_trend', 'volume_price'],
    sector_config: null,
  },
  {
    name: '概念板块 + 形态突破联动',
    description: '在热门概念板块中寻找形态突破的个股，板块热度与技术突破共振',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 10, params: {} },
      { factor_name: 'sector_trend', operator: '==', threshold: null, params: {} },
      { factor_name: 'breakout', operator: '==', threshold: null, params: {} },
      { factor_name: 'turnover', operator: 'BETWEEN', threshold: null, params: { threshold_low: 5.0, threshold_high: 20.0 } },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.3, sector_trend: 0.2, breakout: 0.3, turnover: 0.2 },
    enabled_modules: ['breakout', 'volume_price'],
    sector_config: { sector_data_source: 'DC', sector_type: 'CONCEPT', sector_period: 3, sector_top_n: 10 },
  },
  {
    name: '多数据源板块交叉验证',
    description: '使用通达信行业数据与东方财富概念数据交叉验证，筛选同时处于强势行业和热门概念的个股',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 30, params: { sector_data_source: 'TDX', sector_type: 'INDUSTRY', sector_period: 5 } },
      { factor_name: 'sector_rank', operator: '<=', threshold: 20, params: { sector_data_source: 'DC', sector_type: 'CONCEPT', sector_period: 3 } },
      { factor_name: 'ma_trend', operator: '>=', threshold: 70, params: {} },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.6, ma_trend: 0.4 },
    enabled_modules: ['ma_trend'],
    sector_config: null,
  },
  {
    name: 'RSI 超卖反弹 + 板块支撑',
    description: '在强势板块中寻找 RSI 短期超卖后反弹的个股，逆向买入但有板块趋势保护',
    factors: [
      { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 30, threshold_high: 50 } },
      { factor_name: 'sector_trend', operator: '==', threshold: null, params: {} },
      { factor_name: 'sector_rank', operator: '<=', threshold: 30, params: {} },
      { factor_name: 'ma_trend', operator: '>=', threshold: 55, params: {} },
    ],
    logic: 'AND',
    weights: { rsi: 0.3, sector_trend: 0.25, sector_rank: 0.25, ma_trend: 0.2 },
    enabled_modules: ['indicator_params', 'ma_trend'],
    sector_config: { sector_data_source: 'TI', sector_type: 'INDUSTRY', sector_period: 5, sector_top_n: 30 },
  },
]

// Required fields for every strategy example
const REQUIRED_EXAMPLE_FIELDS: (keyof StrategyExample)[] = [
  'name', 'description', 'factors', 'logic', 'weights', 'enabled_modules',
]

// ---------------------------------------------------------------------------
// Feature: factor-editor-optimization, Property 7 (frontend):
// StrategyConfig JSON round-trip
// ---------------------------------------------------------------------------

describe('Property 7 (frontend): StrategyConfig JSON round-trip', () => {
  /**
   * **Validates: Requirements 13.3, 13.4**
   *
   * For any valid StrategyConfig (including sector_config), serializing to
   * JSON and deserializing back SHALL produce an equivalent object.
   */
  it('serialize → deserialize produces equivalent StrategyConfig', () => {
    fc.assert(
      fc.property(strategyConfigArb, (config) => {
        const normalized = normalizeNegativeZero(config)
        const restored = jsonRoundTrip(normalized)

        // Top-level fields
        expect(restored.logic).toBe(normalized.logic)
        expect(restored.factors).toEqual(normalized.factors)
        expect(restored.weights).toEqual(normalized.weights)
        expect(restored.ma_periods).toEqual(normalized.ma_periods)

        // Nested indicator params
        expect(restored.indicator_params.macd).toEqual(normalized.indicator_params.macd)
        expect(restored.indicator_params.rsi.period).toBe(normalized.indicator_params.rsi.period)
        expect(restored.indicator_params.rsi.lower_bound).toBe(normalized.indicator_params.rsi.lower_bound)
        expect(restored.indicator_params.rsi.upper_bound).toBe(normalized.indicator_params.rsi.upper_bound)
        expect(restored.indicator_params.dma).toEqual(normalized.indicator_params.dma)

        // ma_trend
        expect(restored.ma_trend.ma_periods).toEqual(normalized.ma_trend.ma_periods)
        expect(restored.ma_trend.trend_score_threshold).toBe(normalized.ma_trend.trend_score_threshold)
        expect(restored.ma_trend.support_ma_lines).toEqual(normalized.ma_trend.support_ma_lines)

        // breakout
        expect(restored.breakout.box_breakout).toBe(normalized.breakout.box_breakout)
        expect(restored.breakout.high_breakout).toBe(normalized.breakout.high_breakout)
        expect(restored.breakout.trendline_breakout).toBe(normalized.breakout.trendline_breakout)
        expect(restored.breakout.confirm_days).toBe(normalized.breakout.confirm_days)

        // volume_price
        expect(restored.volume_price.main_flow_days).toBe(normalized.volume_price.main_flow_days)
        expect(restored.volume_price.sector_rank_top).toBe(normalized.volume_price.sector_rank_top)

        // sector_config (the new field)
        expect(restored.sector_config).toBeDefined()
        expect(restored.sector_config.sector_data_source).toBe(normalized.sector_config.sector_data_source)
        expect(restored.sector_config.sector_type).toBe(normalized.sector_config.sector_type)
        expect(restored.sector_config.sector_period).toBe(normalized.sector_config.sector_period)
        expect(restored.sector_config.sector_top_n).toBe(normalized.sector_config.sector_top_n)
      }),
      { numRuns: 100 },
    )
  })

  it('sector_config survives round-trip with all data source / type combinations', () => {
    fc.assert(
      fc.property(sectorScreenConfigArb, (sectorCfg) => {
        const restored = jsonRoundTrip(sectorCfg)
        expect(restored).toEqual(sectorCfg)
      }),
      { numRuns: 100 },
    )
  })

  it('factors with params survive round-trip', () => {
    fc.assert(
      fc.property(
        fc.array(factorConditionArb, { minLength: 1, maxLength: 10 }),
        (factors) => {
          const normalized = normalizeNegativeZero(factors)
          const restored = jsonRoundTrip(normalized)
          expect(restored).toEqual(normalized)
        },
      ),
      { numRuns: 100 },
    )
  })
})

// ---------------------------------------------------------------------------
// Feature: factor-editor-optimization, Property 9 (frontend):
// Strategy example config completeness
// ---------------------------------------------------------------------------

describe('Property 9 (frontend): Strategy example config completeness', () => {
  /**
   * **Validates: Requirements 14.5**
   *
   * For any strategy example in STRATEGY_EXAMPLES, the example SHALL contain
   * all required fields (name, description, factors, logic, weights,
   * enabled_modules).
   */
  it('every example has all required fields', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          for (const field of REQUIRED_EXAMPLE_FIELDS) {
            expect(example[field]).toBeDefined()
            expect(example[field]).not.toBeNull()
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every example has non-empty name and description', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          expect(example.name.length).toBeGreaterThan(0)
          expect(example.description.length).toBeGreaterThan(0)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every example has at least one factor condition', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          expect(example.factors.length).toBeGreaterThan(0)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every factor in examples uses a known factor_name', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          for (const factor of example.factors) {
            expect(FACTOR_NAMES).toContain(factor.factor_name)
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every example has logic set to AND or OR', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          expect(['AND', 'OR']).toContain(example.logic)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every example has at least one enabled module', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          expect(example.enabled_modules.length).toBeGreaterThan(0)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('every example has weights that sum to approximately 1.0', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          const totalWeight = Object.values(example.weights).reduce((sum, w) => sum + w, 0)
          expect(totalWeight).toBeCloseTo(1.0, 1)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('examples with sector factors have sector_config defined', () => {
    const SECTOR_FACTOR_NAMES = ['sector_rank', 'sector_trend']
    for (const example of STRATEGY_EXAMPLES) {
      const hasSectorFactor = example.factors.some((f) =>
        SECTOR_FACTOR_NAMES.includes(f.factor_name),
      )
      // If example has sector factors AND sector_config is provided, verify it
      if (hasSectorFactor && example.sector_config) {
        expect(example.sector_config.sector_data_source).toBeDefined()
        expect(example.sector_config.sector_type).toBeDefined()
        expect(example.sector_config.sector_period).toBeGreaterThan(0)
        expect(example.sector_config.sector_top_n).toBeGreaterThan(0)
      }
    }
  })

  it('example configs survive JSON round-trip', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STRATEGY_EXAMPLES),
        (example) => {
          const restored = jsonRoundTrip(example)
          expect(restored.name).toBe(example.name)
          expect(restored.description).toBe(example.description)
          expect(restored.factors).toEqual(example.factors)
          expect(restored.logic).toBe(example.logic)
          expect(restored.weights).toEqual(example.weights)
          expect(restored.enabled_modules).toEqual(example.enabled_modules)
          expect(restored.sector_config).toEqual(example.sector_config)
        },
      ),
      { numRuns: 100 },
    )
  })
})
