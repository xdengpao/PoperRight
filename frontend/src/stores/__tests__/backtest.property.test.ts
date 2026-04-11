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
