/**
 * 前端 ExitConditionConfig JSON 序列化往返属性测试
 *
 * Feature: backtest-exit-conditions, Property 1 (frontend): ExitConditionConfig round-trip serialization
 *
 * 对任意合法的 ExitConditionForm 数组和逻辑运算符，
 * 序列化为 snake_case JSON（匹配 API payload）后再解析回 camelCase，
 * 应与原对象完全一致。
 *
 * **Validates: Requirements 1.6, 1.7**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { INDICATOR_DESCRIPTIONS } from '@/stores/backtest'

// ─── 类型定义（与 backtest.ts 中 ExitConditionForm 一致）────────────────────

interface ExitConditionForm {
  freq: 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'
  indicator: string
  operator: string
  threshold: number | null
  crossTarget: string | null
  params: Record<string, number>
}

interface ExitConditionsConfig {
  conditions: ExitConditionForm[]
  logic: 'AND' | 'OR'
}

// ─── snake_case API payload 类型 ──────────────────────────────────────────────

interface ExitConditionPayload {
  freq: string
  indicator: string
  operator: string
  threshold: number | null
  cross_target: string | null
  params: Record<string, number>
}

interface ExitConditionsPayload {
  conditions: ExitConditionPayload[]
  logic: string
}

// ─── 序列化 / 反序列化（提取自 startBacktest 中的逻辑）──────────────────────

function serializeToPayload(config: ExitConditionsConfig): ExitConditionsPayload {
  return {
    conditions: config.conditions.map((c) => ({
      freq: c.freq,
      indicator: c.indicator,
      operator: c.operator,
      threshold: c.threshold,
      cross_target: c.crossTarget,
      params: c.params,
    })),
    logic: config.logic,
  }
}

function deserializeFromPayload(payload: ExitConditionsPayload): ExitConditionsConfig {
  return {
    conditions: payload.conditions.map((c) => ({
      freq: c.freq as ExitConditionForm['freq'],
      indicator: c.indicator,
      operator: c.operator,
      threshold: c.threshold,
      crossTarget: c.cross_target,
      params: c.params,
    })),
    logic: payload.logic as 'AND' | 'OR',
  }
}

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const VALID_INDICATORS = [
  'ma', 'macd_dif', 'macd_dea', 'macd_histogram',
  'boll_upper', 'boll_middle', 'boll_lower',
  'rsi', 'dma', 'ama', 'close', 'volume', 'turnover',
] as const

const NUMERIC_OPERATORS = ['>', '<', '>=', '<='] as const
const CROSS_OPERATORS = ['cross_up', 'cross_down'] as const

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const freqArb = fc.constantFrom('daily' as const, '1min' as const, '5min' as const, '15min' as const, '30min' as const, '60min' as const)
const indicatorArb = fc.constantFrom(...VALID_INDICATORS)
const logicArb = fc.constantFrom('AND' as const, 'OR' as const)

/** 生成合法的指标参数 */
const paramsArb: fc.Arbitrary<Record<string, number>> = fc.oneof(
  fc.constant({} as Record<string, number>),
  fc.record({ period: fc.integer({ min: 1, max: 250 }) }),
  fc.record({
    fast_period: fc.integer({ min: 1, max: 50 }),
    slow_period: fc.integer({ min: 1, max: 100 }),
    signal_period: fc.integer({ min: 1, max: 50 }),
  }),
)

/** 生成使用数值运算符的条件 */
const numericConditionArb: fc.Arbitrary<ExitConditionForm> = fc.record({
  freq: freqArb,
  indicator: indicatorArb,
  operator: fc.constantFrom(...NUMERIC_OPERATORS) as fc.Arbitrary<string>,
  threshold: fc.double({ min: -1e6, max: 1e6, noNaN: true }) as fc.Arbitrary<number | null>,
  crossTarget: fc.constant(null) as fc.Arbitrary<string | null>,
  params: paramsArb,
})

/** 生成使用交叉运算符的条件 */
const crossConditionArb: fc.Arbitrary<ExitConditionForm> = fc.record({
  freq: freqArb,
  indicator: indicatorArb,
  operator: fc.constantFrom(...CROSS_OPERATORS) as fc.Arbitrary<string>,
  threshold: fc.constant(null) as fc.Arbitrary<number | null>,
  crossTarget: fc.constantFrom(...VALID_INDICATORS) as fc.Arbitrary<string | null>,
  params: paramsArb,
})

/** 生成任意合法条件 */
const conditionArb = fc.oneof(numericConditionArb, crossConditionArb)

/** 生成任意合法配置 */
const exitConditionsConfigArb: fc.Arbitrary<ExitConditionsConfig> = fc.record({
  conditions: fc.array(conditionArb, { minLength: 0, maxLength: 10 }),
  logic: logicArb,
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('ExitConditionConfig JSON 序列化往返属性测试', () => {
  /**
   * 序列化为 snake_case JSON 后再解析回 camelCase 应与原对象一致
   * Validates: Requirements 1.6, 1.7
   */
  it('serialize → JSON.stringify → JSON.parse → deserialize 往返一致', () => {
    fc.assert(
      fc.property(exitConditionsConfigArb, (config) => {
        // 1. camelCase → snake_case payload
        const payload = serializeToPayload(config)

        // 2. 模拟网络传输：JSON 序列化 + 反序列化
        const json = JSON.stringify(payload)
        const parsed: ExitConditionsPayload = JSON.parse(json)

        // 3. snake_case → camelCase
        const restored = deserializeFromPayload(parsed)

        // 4. 验证等价性
        expect(restored.logic).toBe(config.logic)
        expect(restored.conditions.length).toBe(config.conditions.length)

        for (let i = 0; i < config.conditions.length; i++) {
          const original = config.conditions[i]
          const round = restored.conditions[i]
          expect(round.freq).toBe(original.freq)
          expect(round.indicator).toBe(original.indicator)
          expect(round.operator).toBe(original.operator)
          expect(round.threshold).toBe(original.threshold)
          expect(round.crossTarget).toBe(original.crossTarget)
          expect(round.params).toEqual(original.params)
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 空条件列表的往返一致性
   * Validates: Requirements 1.6, 1.7
   */
  it('空条件列表序列化往返一致', () => {
    fc.assert(
      fc.property(logicArb, (logic) => {
        const config: ExitConditionsConfig = { conditions: [], logic }
        const payload = serializeToPayload(config)
        const json = JSON.stringify(payload)
        const parsed: ExitConditionsPayload = JSON.parse(json)
        const restored = deserializeFromPayload(parsed)

        expect(restored).toEqual(config)
      }),
      { numRuns: 100 },
    )
  })
})


// ─── Property 10: 指标使用说明注册表完整性 ─────────────────────────────────────

/**
 * Feature: backtest-exit-conditions, Property 10: Indicator description registry completeness
 *
 * 对任意合法指标名称（从 VALID_INDICATORS 13 个指标中采样），
 * 验证 INDICATOR_DESCRIPTIONS 中存在对应条目，且条目包含完整的说明信息。
 *
 * **Validates: Requirements 11.1, 11.3, 11.4, 11.5**
 */
describe('指标使用说明注册表完整性属性测试', () => {
  const INDICATORS_WITH_PARAMS = [
    'ma', 'macd_dif', 'macd_dea', 'macd_histogram',
    'boll_upper', 'boll_middle', 'boll_lower',
    'rsi', 'dma', 'ama',
  ] as const

  const INDICATORS_WITHOUT_PARAMS = ['close', 'volume', 'turnover'] as const

  const allIndicatorArb = fc.constantFrom(...VALID_INDICATORS)
  const paramIndicatorArb = fc.constantFrom(...INDICATORS_WITH_PARAMS)

  /**
   * 对任意合法指标名称，INDICATOR_DESCRIPTIONS 中存在对应条目，
   * 且包含非空的 chineseName、calculationSummary、typicalUsage
   * Validates: Requirements 11.1, 11.3, 11.5
   */
  it('任意合法指标名称在 INDICATOR_DESCRIPTIONS 中存在且包含完整基本信息', () => {
    fc.assert(
      fc.property(allIndicatorArb, (indicator) => {
        const desc = INDICATOR_DESCRIPTIONS[indicator]

        // 条目存在
        expect(desc).toBeDefined()

        // chineseName 非空
        expect(desc.chineseName).toBeDefined()
        expect(typeof desc.chineseName).toBe('string')
        expect(desc.chineseName.length).toBeGreaterThan(0)

        // calculationSummary 非空
        expect(desc.calculationSummary).toBeDefined()
        expect(typeof desc.calculationSummary).toBe('string')
        expect(desc.calculationSummary.length).toBeGreaterThan(0)

        // typicalUsage 非空
        expect(desc.typicalUsage).toBeDefined()
        expect(typeof desc.typicalUsage).toBe('string')
        expect(desc.typicalUsage.length).toBeGreaterThan(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 对包含可配置参数的指标，params 数组非空，
   * 且每个参数包含 name、defaultValue、suggestedRange
   * Validates: Requirements 11.4
   */
  it('可配置参数指标的 params 数组非空且每个参数包含必要字段', () => {
    fc.assert(
      fc.property(paramIndicatorArb, (indicator) => {
        const desc = INDICATOR_DESCRIPTIONS[indicator]

        expect(desc).toBeDefined()
        expect(Array.isArray(desc.params)).toBe(true)
        expect(desc.params.length).toBeGreaterThan(0)

        for (const param of desc.params) {
          // name 非空
          expect(param.name).toBeDefined()
          expect(typeof param.name).toBe('string')
          expect(param.name.length).toBeGreaterThan(0)

          // defaultValue 存在且为数值
          expect(param.defaultValue).toBeDefined()
          expect(typeof param.defaultValue).toBe('number')

          // suggestedRange 存在且为包含两个数值的数组
          expect(param.suggestedRange).toBeDefined()
          expect(Array.isArray(param.suggestedRange)).toBe(true)
          expect(param.suggestedRange).toHaveLength(2)
          expect(typeof param.suggestedRange[0]).toBe('number')
          expect(typeof param.suggestedRange[1]).toBe('number')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 无参数指标（close、volume、turnover）的 params 数组为空
   * Validates: Requirements 11.3
   */
  it('无参数指标的 params 数组为空', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...INDICATORS_WITHOUT_PARAMS),
        (indicator) => {
          const desc = INDICATOR_DESCRIPTIONS[indicator]

          expect(desc).toBeDefined()
          expect(Array.isArray(desc.params)).toBe(true)
          expect(desc.params.length).toBe(0)
        },
      ),
      { numRuns: 100 },
    )
  })
})


// ─── Property 11: 前端 ExitConditionForm 序列化往返一致性（含相对值阈值字段）──

/**
 * Feature: relative-exit-thresholds, Property 11: frontend round-trip
 *
 * 对任意合法的 ExitConditionForm 对象（包含 thresholdMode、baseField、factor），
 * 序列化为 snake_case JSON 后再反序列化回 camelCase 应与原对象等价。
 * 缺失 threshold_mode 的旧版数据应默认为 'absolute'。
 *
 * **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
 */

import { BASE_FIELD_OPTIONS } from '@/stores/backtest'

// ─── 扩展类型（含相对值阈值字段）──────────────────────────────────────────────

interface ExitConditionFormFull {
  freq: 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'
  indicator: string
  operator: string
  threshold: number | null
  crossTarget: string | null
  params: Record<string, number>
  thresholdMode: 'absolute' | 'relative'
  baseField: string | null
  factor: number | null
}

interface ExitConditionPayloadFull {
  freq: string
  indicator: string
  operator: string
  threshold: number | null
  cross_target: string | null
  params: Record<string, number>
  threshold_mode: string
  base_field: string | null
  factor: number | null
}

// ─── 序列化 / 反序列化（匹配 startBacktest / loadExitTemplate 逻辑）─────────

function serializeConditionFull(c: ExitConditionFormFull): ExitConditionPayloadFull {
  return {
    freq: c.freq,
    indicator: c.indicator,
    operator: c.operator,
    threshold: c.threshold,
    cross_target: c.crossTarget,
    params: c.params,
    threshold_mode: c.thresholdMode,
    base_field: c.baseField,
    factor: c.factor,
  }
}

function deserializeConditionFull(c: Partial<ExitConditionPayloadFull>): ExitConditionFormFull {
  return {
    freq: (c.freq ?? 'daily') as ExitConditionFormFull['freq'],
    indicator: c.indicator ?? '',
    operator: c.operator ?? '',
    threshold: c.threshold ?? null,
    crossTarget: c.cross_target ?? null,
    params: c.params ?? {},
    thresholdMode: ((c as Record<string, unknown>).threshold_mode ?? 'absolute') as 'absolute' | 'relative',
    baseField: c.base_field ?? null,
    factor: c.factor ?? null,
  }
}

// ─── 合法 base_field 值 ───────────────────────────────────────────────────────

const VALID_BASE_FIELDS = BASE_FIELD_OPTIONS.flatMap(g => g.options.map(o => o.value))

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const freqArbFull = fc.constantFrom('daily' as const, '1min' as const, '5min' as const, '15min' as const, '30min' as const, '60min' as const)
const indicatorArbFull = fc.constantFrom(...VALID_INDICATORS)
const baseFieldArb = fc.constantFrom(...VALID_BASE_FIELDS)

const paramsArbFull: fc.Arbitrary<Record<string, number>> = fc.oneof(
  fc.constant({} as Record<string, number>),
  fc.record({ period: fc.integer({ min: 1, max: 250 }) }),
  fc.record({ ma_volume_period: fc.integer({ min: 1, max: 60 }) }),
)

/** 生成 JSON 安全的 double（排除 -0，因为 JSON.parse(JSON.stringify(-0)) === 0） */
const jsonSafeDouble = (opts: { min: number; max: number }) =>
  fc.double({ ...opts, noNaN: true }).map(v => (Object.is(v, -0) ? 0 : v))

/** 生成绝对值模式条件 */
const absoluteConditionFullArb: fc.Arbitrary<ExitConditionFormFull> = fc.record({
  freq: freqArbFull,
  indicator: indicatorArbFull,
  operator: fc.constantFrom('>', '<', '>=', '<=') as fc.Arbitrary<string>,
  threshold: jsonSafeDouble({ min: -1e6, max: 1e6 }) as fc.Arbitrary<number | null>,
  crossTarget: fc.constant(null) as fc.Arbitrary<string | null>,
  params: paramsArbFull,
  thresholdMode: fc.constant('absolute' as const),
  baseField: fc.constant(null) as fc.Arbitrary<string | null>,
  factor: fc.constant(null) as fc.Arbitrary<number | null>,
})

/** 生成相对值模式条件 */
const relativeConditionFullArb: fc.Arbitrary<ExitConditionFormFull> = fc.record({
  freq: freqArbFull,
  indicator: indicatorArbFull,
  operator: fc.constantFrom('>', '<', '>=', '<=') as fc.Arbitrary<string>,
  threshold: fc.constant(null) as fc.Arbitrary<number | null>,
  crossTarget: fc.constant(null) as fc.Arbitrary<string | null>,
  params: paramsArbFull,
  thresholdMode: fc.constant('relative' as const),
  baseField: baseFieldArb as fc.Arbitrary<string | null>,
  factor: jsonSafeDouble({ min: 0.01, max: 100 }) as fc.Arbitrary<number | null>,
})

/** 生成交叉条件（含新字段默认值） */
const crossConditionFullArb: fc.Arbitrary<ExitConditionFormFull> = fc.record({
  freq: freqArbFull,
  indicator: indicatorArbFull,
  operator: fc.constantFrom('cross_up', 'cross_down') as fc.Arbitrary<string>,
  threshold: fc.constant(null) as fc.Arbitrary<number | null>,
  crossTarget: fc.constantFrom(...VALID_INDICATORS) as fc.Arbitrary<string | null>,
  params: paramsArbFull,
  thresholdMode: fc.constant('absolute' as const),
  baseField: fc.constant(null) as fc.Arbitrary<string | null>,
  factor: fc.constant(null) as fc.Arbitrary<number | null>,
})

/** 生成任意合法条件（含相对值字段） */
const conditionFullArb = fc.oneof(absoluteConditionFullArb, relativeConditionFullArb, crossConditionFullArb)

describe('Feature: relative-exit-thresholds, Property 11: frontend round-trip', () => {
  /**
   * 序列化为 snake_case → JSON → 反序列化回 camelCase 应与原对象等价
   * Validates: Requirements 7.2, 7.3, 7.5
   */
  it('ExitConditionForm 含相对值字段的序列化往返一致', () => {
    fc.assert(
      fc.property(conditionFullArb, (condition) => {
        // 1. camelCase → snake_case
        const payload = serializeConditionFull(condition)

        // 2. 模拟网络传输
        const json = JSON.stringify(payload)
        const parsed: ExitConditionPayloadFull = JSON.parse(json)

        // 3. snake_case → camelCase
        const restored = deserializeConditionFull(parsed)

        // 4. 验证等价性
        expect(restored.freq).toBe(condition.freq)
        expect(restored.indicator).toBe(condition.indicator)
        expect(restored.operator).toBe(condition.operator)
        expect(restored.threshold).toBe(condition.threshold)
        expect(restored.crossTarget).toBe(condition.crossTarget)
        expect(restored.params).toEqual(condition.params)
        expect(restored.thresholdMode).toBe(condition.thresholdMode)
        expect(restored.baseField).toBe(condition.baseField)
        expect(restored.factor).toBe(condition.factor)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 缺失 threshold_mode 的旧版数据反序列化后默认为 'absolute'
   * Validates: Requirements 7.4
   */
  it('缺失 threshold_mode 的旧版数据默认为 absolute', () => {
    fc.assert(
      fc.property(
        freqArbFull,
        indicatorArbFull,
        fc.constantFrom('>', '<', '>=', '<='),
        fc.double({ min: -1e6, max: 1e6, noNaN: true }),
        paramsArbFull,
        (freq, indicator, operator, threshold, params) => {
          // 模拟旧版 API 返回（不含 threshold_mode / base_field / factor）
          const oldPayload = {
            freq,
            indicator,
            operator,
            threshold,
            cross_target: null,
            params,
          }

          const json = JSON.stringify(oldPayload)
          const parsed = JSON.parse(json)

          // 反序列化应默认 thresholdMode 为 'absolute'
          const restored = deserializeConditionFull(parsed)

          expect(restored.thresholdMode).toBe('absolute')
          expect(restored.baseField).toBeNull()
          expect(restored.factor).toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })
})


// ─── Property 12: 前端模式切换清空对立字段 ─────────────────────────────────────

/**
 * Feature: relative-exit-thresholds, Property 12: mode switch clears fields
 *
 * 对任意前端 ExitConditionForm 状态，当 thresholdMode 切换时：
 * - 切换到 'absolute': baseField → null, factor → null
 * - 切换到 'relative': threshold → null
 *
 * 提取自 BacktestView.vue 的 onThresholdModeChange() 逻辑为纯函数进行测试。
 *
 * **Validates: Requirements 6.7**
 */

describe('Feature: relative-exit-thresholds, Property 12: mode switch clears fields', () => {
  /**
   * 纯函数提取自 BacktestView.vue 的 onThresholdModeChange()
   * 模拟模式切换时清空对立字段的逻辑
   */
  function applyThresholdModeChange(cond: ExitConditionFormFull): ExitConditionFormFull {
    const result = { ...cond }
    if (result.thresholdMode === 'absolute') {
      // Switched to absolute: clear relative fields
      result.baseField = null
      result.factor = null
    } else {
      // Switched to relative: clear absolute field
      result.threshold = null
    }
    return result
  }

  /** 生成任意 ExitConditionForm 状态（可能包含不一致的字段组合） */
  const arbitraryConditionState: fc.Arbitrary<ExitConditionFormFull> = fc.record({
    freq: freqArbFull,
    indicator: indicatorArbFull,
    operator: fc.constantFrom('>', '<', '>=', '<=') as fc.Arbitrary<string>,
    threshold: fc.oneof(
      fc.constant(null),
      fc.double({ min: -1e6, max: 1e6, noNaN: true }),
    ) as fc.Arbitrary<number | null>,
    crossTarget: fc.constant(null) as fc.Arbitrary<string | null>,
    params: paramsArbFull,
    thresholdMode: fc.constantFrom('absolute' as const, 'relative' as const),
    baseField: fc.oneof(
      fc.constant(null),
      baseFieldArb,
    ) as fc.Arbitrary<string | null>,
    factor: fc.oneof(
      fc.constant(null),
      fc.double({ min: 0.01, max: 100, noNaN: true }),
    ) as fc.Arbitrary<number | null>,
  })

  /**
   * 切换到 'absolute' 模式时，baseField 和 factor 应被清空为 null
   * Validates: Requirements 6.7
   */
  it('切换到 absolute 模式时清空 baseField 和 factor', () => {
    fc.assert(
      fc.property(arbitraryConditionState, (cond) => {
        const withAbsolute: ExitConditionFormFull = { ...cond, thresholdMode: 'absolute' }
        const result = applyThresholdModeChange(withAbsolute)

        expect(result.baseField).toBeNull()
        expect(result.factor).toBeNull()
        // threshold 应保持不变
        expect(result.threshold).toBe(withAbsolute.threshold)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 切换到 'relative' 模式时，threshold 应被清空为 null
   * Validates: Requirements 6.7
   */
  it('切换到 relative 模式时清空 threshold', () => {
    fc.assert(
      fc.property(arbitraryConditionState, (cond) => {
        const withRelative: ExitConditionFormFull = { ...cond, thresholdMode: 'relative' }
        const result = applyThresholdModeChange(withRelative)

        expect(result.threshold).toBeNull()
        // baseField 和 factor 应保持不变
        expect(result.baseField).toBe(withRelative.baseField)
        expect(result.factor).toBe(withRelative.factor)
      }),
      { numRuns: 100 },
    )
  })
})
