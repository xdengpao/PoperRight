/**
 * 属性 73：基本面指标颜色编码正确性
 *
 * Feature: a-share-quant-trading-system, Property 73: 基本面指标颜色编码
 *
 * 对任意 PE/ROE/增长率值，getFundamentalColorClass 返回值应符合颜色规则
 *
 * **Validates: Requirements 26.5**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { getFundamentalColorClass } from '@/views/fundamentalUtils'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成有限浮点数（排除 NaN / Infinity） */
const finiteFloat = fc.double({ min: -1e6, max: 1e6, noNaN: true })

/** 生成正浮点数（严格 > 0） */
const positiveFloat = fc.double({ min: 0.001, max: 1e6, noNaN: true })

/** 生成负浮点数（严格 < 0） */
const negativeFloat = fc.double({ min: -1e6, max: -0.001, noNaN: true })

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 73：基本面指标颜色编码正确性', () => {
  /**
   * 属性 73a：PE TTM 颜色编码规则
   * < 20 → 'color-green', > 40 → 'color-red', 20-40 → ''
   * Validates: Requirements 26.5
   */
  it('PE TTM: < 20 → green, > 40 → red, 20-40 → 无色', () => {
    fc.assert(
      fc.property(finiteFloat, (value) => {
        const result = getFundamentalColorClass('pe_ttm', value)
        if (value < 20) {
          expect(result).toBe('color-green')
        } else if (value > 40) {
          expect(result).toBe('color-red')
        } else {
          expect(result).toBe('')
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 73b：ROE 颜色编码规则
   * > 15 → 'color-green', < 8 → 'color-red', 8-15 → ''
   * Validates: Requirements 26.5
   */
  it('ROE: > 15 → green, < 8 → red, 8-15 → 无色', () => {
    fc.assert(
      fc.property(finiteFloat, (value) => {
        const result = getFundamentalColorClass('roe', value)
        if (value > 15) {
          expect(result).toBe('color-green')
        } else if (value < 8) {
          expect(result).toBe('color-red')
        } else {
          expect(result).toBe('')
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 73c：营收增长率颜色编码规则
   * > 0 → 'color-red', < 0 → 'color-green', = 0 → ''
   * Validates: Requirements 26.5
   */
  it('revenue_growth: > 0 → red, < 0 → green, = 0 → 无色', () => {
    fc.assert(
      fc.property(finiteFloat, (value) => {
        const result = getFundamentalColorClass('revenue_growth', value)
        if (value > 0) {
          expect(result).toBe('color-red')
        } else if (value < 0) {
          expect(result).toBe('color-green')
        } else {
          expect(result).toBe('')
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 73d：净利润增长率颜色编码规则
   * > 0 → 'color-red', < 0 → 'color-green', = 0 → ''
   * Validates: Requirements 26.5
   */
  it('net_profit_growth: > 0 → red, < 0 → green, = 0 → 无色', () => {
    fc.assert(
      fc.property(finiteFloat, (value) => {
        const result = getFundamentalColorClass('net_profit_growth', value)
        if (value > 0) {
          expect(result).toBe('color-red')
        } else if (value < 0) {
          expect(result).toBe('color-green')
        } else {
          expect(result).toBe('')
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 73e：null 值始终返回空字符串
   * Validates: Requirements 26.5
   */
  it('任意指标传入 null 值均返回空字符串', () => {
    const metrics = ['pe_ttm', 'roe', 'revenue_growth', 'net_profit_growth']
    fc.assert(
      fc.property(fc.constantFrom(...metrics), (metric) => {
        expect(getFundamentalColorClass(metric, null)).toBe('')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 73f：返回值始终为合法颜色类名之一
   * Validates: Requirements 26.5
   */
  it('返回值始终为 color-green、color-red 或空字符串之一', () => {
    const metrics = ['pe_ttm', 'roe', 'revenue_growth', 'net_profit_growth']
    const validResults = new Set(['color-green', 'color-red', ''])
    fc.assert(
      fc.property(
        fc.constantFrom(...metrics),
        fc.oneof(finiteFloat, fc.constant(null as number | null)),
        (metric, value) => {
          const result = getFundamentalColorClass(metric, value)
          expect(validResults.has(result)).toBe(true)
        },
      ),
      { numRuns: 200 },
    )
  })
})
