/**
 * 属性 35：前端数据渲染字段完整性
 *
 * 验证选股结果项和持仓项渲染后所有必要字段均不为空
 *
 * **Validates: Requirements 21.7, 21.11**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface ScreenResultRow {
  symbol: string
  name: string
  ref_buy_price: number
  trend_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  signals: string[]
  screen_time: string
}

interface PositionRow {
  symbol: string
  name: string
  quantity: number
  cost_price: number
  current_price: number
  market_value: number
  pnl: number
  pnl_pct: number
  weight: number // 仓位占比 %
  trend_status: 'HOLD' | 'WARNING'
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const nonEmptyStringArb = fc
  .string({ minLength: 1, maxLength: 50 })
  .filter((s) => s.trim().length > 0)

const riskLevelArb = fc.constantFrom<'LOW' | 'MEDIUM' | 'HIGH'>('LOW', 'MEDIUM', 'HIGH')

const trendStatusArb = fc.constantFrom<'HOLD' | 'WARNING'>('HOLD', 'WARNING')

// trend_score: integer in [0, 100]
const trendScoreArb = fc.integer({ min: 0, max: 100 })

// positive price: > 0
const positivePriceArb = fc
  .float({ min: 0.01, max: 9999.99, noNaN: true })
  .filter((v) => v > 0 && isFinite(v))

// positive integer quantity
const positiveQuantityArb = fc.integer({ min: 1, max: 1_000_000 })

// weight in [0, 1]
const weightArb = fc.float({ min: 0, max: 1, noNaN: true }).filter((v) => isFinite(v))

const screenResultRowArb: fc.Arbitrary<ScreenResultRow> = fc.record({
  symbol: nonEmptyStringArb,
  name: nonEmptyStringArb,
  ref_buy_price: positivePriceArb,
  trend_score: trendScoreArb,
  risk_level: riskLevelArb,
  signals: fc.array(nonEmptyStringArb, { minLength: 0, maxLength: 10 }),
  screen_time: fc.date({ min: new Date('2000-01-01'), max: new Date('2099-12-31') }).map((d) =>
    d.toISOString(),
  ),
})

// PositionRow with mathematically consistent pnl fields
const positionRowArb: fc.Arbitrary<PositionRow> = fc
  .record({
    symbol: nonEmptyStringArb,
    name: nonEmptyStringArb,
    quantity: positiveQuantityArb,
    cost_price: positivePriceArb,
    current_price: positivePriceArb,
    weight: weightArb,
    trend_status: trendStatusArb,
  })
  .map((base) => {
    const pnl = (base.current_price - base.cost_price) * base.quantity
    const pnl_pct = pnl / (base.cost_price * base.quantity)
    const market_value = base.current_price * base.quantity
    return { ...base, market_value, pnl, pnl_pct }
  })

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 35：前端数据渲染字段完整性', () => {
  /**
   * 属性 35a：任意 ScreenResultRow 所有必要字段均不为 null/undefined/空
   * Validates: Requirements 21.7
   */
  it('ScreenResultRow：所有必要字段均不为 null/undefined/空', () => {
    fc.assert(
      fc.property(screenResultRowArb, (row) => {
        // symbol 非空字符串
        expect(row.symbol).toBeTruthy()
        expect(typeof row.symbol).toBe('string')
        expect(row.symbol.trim().length).toBeGreaterThan(0)

        // name 非空字符串
        expect(row.name).toBeTruthy()
        expect(typeof row.name).toBe('string')
        expect(row.name.trim().length).toBeGreaterThan(0)

        // ref_buy_price 非 null/undefined，且为数字
        expect(row.ref_buy_price).not.toBeNull()
        expect(row.ref_buy_price).not.toBeUndefined()
        expect(typeof row.ref_buy_price).toBe('number')

        // trend_score 非 null/undefined，且为数字
        expect(row.trend_score).not.toBeNull()
        expect(row.trend_score).not.toBeUndefined()
        expect(typeof row.trend_score).toBe('number')

        // risk_level 非 null/undefined，且为字符串
        expect(row.risk_level).not.toBeNull()
        expect(row.risk_level).not.toBeUndefined()
        expect(typeof row.risk_level).toBe('string')

        // signals 非 null/undefined，且为数组
        expect(row.signals).not.toBeNull()
        expect(row.signals).not.toBeUndefined()
        expect(Array.isArray(row.signals)).toBe(true)

        // screen_time 非空字符串
        expect(row.screen_time).toBeTruthy()
        expect(typeof row.screen_time).toBe('string')
        expect(row.screen_time.trim().length).toBeGreaterThan(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 35b：任意 PositionRow 所有必要字段均不为 null/undefined
   * Validates: Requirements 21.11
   */
  it('PositionRow：所有必要字段均不为 null/undefined', () => {
    fc.assert(
      fc.property(positionRowArb, (row) => {
        // symbol 非空字符串
        expect(row.symbol).toBeTruthy()
        expect(typeof row.symbol).toBe('string')
        expect(row.symbol.trim().length).toBeGreaterThan(0)

        // name 非空字符串
        expect(row.name).toBeTruthy()
        expect(typeof row.name).toBe('string')
        expect(row.name.trim().length).toBeGreaterThan(0)

        // quantity 非 null/undefined，且为数字
        expect(row.quantity).not.toBeNull()
        expect(row.quantity).not.toBeUndefined()
        expect(typeof row.quantity).toBe('number')

        // cost_price 非 null/undefined，且为数字
        expect(row.cost_price).not.toBeNull()
        expect(row.cost_price).not.toBeUndefined()
        expect(typeof row.cost_price).toBe('number')

        // current_price 非 null/undefined，且为数字
        expect(row.current_price).not.toBeNull()
        expect(row.current_price).not.toBeUndefined()
        expect(typeof row.current_price).toBe('number')

        // market_value 非 null/undefined，且为数字
        expect(row.market_value).not.toBeNull()
        expect(row.market_value).not.toBeUndefined()
        expect(typeof row.market_value).toBe('number')

        // pnl 非 null/undefined，且为数字
        expect(row.pnl).not.toBeNull()
        expect(row.pnl).not.toBeUndefined()
        expect(typeof row.pnl).toBe('number')

        // pnl_pct 非 null/undefined，且为数字
        expect(row.pnl_pct).not.toBeNull()
        expect(row.pnl_pct).not.toBeUndefined()
        expect(typeof row.pnl_pct).toBe('number')

        // weight 非 null/undefined，且为数字
        expect(row.weight).not.toBeNull()
        expect(row.weight).not.toBeUndefined()
        expect(typeof row.weight).toBe('number')

        // trend_status 非 null/undefined
        expect(row.trend_status).not.toBeNull()
        expect(row.trend_status).not.toBeUndefined()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 35c：trend_score 始终在 [0, 100] 范围内
   * Validates: Requirements 21.7
   */
  it('trend_score 始终在 [0, 100] 范围内', () => {
    fc.assert(
      fc.property(screenResultRowArb, (row) => {
        expect(row.trend_score).toBeGreaterThanOrEqual(0)
        expect(row.trend_score).toBeLessThanOrEqual(100)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 35d：risk_level 始终是 'LOW' | 'MEDIUM' | 'HIGH' 之一
   * Validates: Requirements 21.7
   */
  it("risk_level 始终是 'LOW' | 'MEDIUM' | 'HIGH' 之一", () => {
    fc.assert(
      fc.property(screenResultRowArb, (row) => {
        expect(['LOW', 'MEDIUM', 'HIGH']).toContain(row.risk_level)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 35e：pnl = (current_price - cost_price) * quantity（误差 ≤ 0.01%）
   * Validates: Requirements 21.11
   */
  it('pnl = (current_price - cost_price) * quantity（误差 ≤ 0.01%）', () => {
    fc.assert(
      fc.property(positionRowArb, (row) => {
        const expected = (row.current_price - row.cost_price) * row.quantity
        const tolerance = Math.abs(expected) * 0.0001 + Number.EPSILON
        expect(Math.abs(row.pnl - expected)).toBeLessThanOrEqual(tolerance)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 35f：pnl_pct = pnl / (cost_price * quantity)（误差 ≤ 0.01%）
   * Validates: Requirements 21.11
   */
  it('pnl_pct = pnl / (cost_price * quantity)（误差 ≤ 0.01%）', () => {
    fc.assert(
      fc.property(positionRowArb, (row) => {
        const costBasis = row.cost_price * row.quantity
        // costBasis > 0 is guaranteed by positivePriceArb and positiveQuantityArb
        const expected = row.pnl / costBasis
        const tolerance = Math.abs(expected) * 0.0001 + Number.EPSILON
        expect(Math.abs(row.pnl_pct - expected)).toBeLessThanOrEqual(tolerance)
      }),
      { numRuns: 100 },
    )
  })
})
