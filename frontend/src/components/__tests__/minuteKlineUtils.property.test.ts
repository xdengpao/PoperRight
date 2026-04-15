/**
 * # Feature: forward-adjusted-kline, Property 7: 缓存键复权类型区分性
 *
 * For any symbol, date, freq, and adjType combination, different adjType values
 * must produce different cache keys; same parameters must produce identical keys.
 *
 * **Validates: Requirements 5.6**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { buildCacheKey } from '../minuteKlineUtils'
import type { AdjType } from '../minuteKlineUtils'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成 6 位数字股票代码 */
const symbolArb = fc
  .integer({ min: 0, max: 999999 })
  .map((n) => String(n).padStart(6, '0'))

/** 生成有效的 YYYY-MM-DD 日期字符串 */
const dateArb = fc
  .record({
    year: fc.integer({ min: 2000, max: 2099 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }),
  })
  .map(({ year, month, day }) => {
    const mm = String(month).padStart(2, '0')
    const dd = String(day).padStart(2, '0')
    return `${year}-${mm}-${dd}`
  })

/** 生成有效的分钟周期 */
const freqArb = fc.constantFrom('1m', '5m', '15m', '30m', '60m')

/** 生成复权类型 */
const adjTypeArb = fc.constantFrom<AdjType>(0, 1)

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: forward-adjusted-kline, Property 7: 缓存键复权类型区分性', () => {
  /**
   * Property 7a: 不同 adjType 值产生不同的缓存键
   *
   * For any symbol, date, freq combination, buildCacheKey with adjType=0
   * must produce a different key than buildCacheKey with adjType=1.
   *
   * Validates: Requirements 5.6
   */
  it('不同 adjType 值（0 vs 1）对相同 symbol/date/freq 产生不同缓存键', () => {
    fc.assert(
      fc.property(symbolArb, dateArb, freqArb, (symbol, date, freq) => {
        const key0 = buildCacheKey(symbol, date, freq, 0)
        const key1 = buildCacheKey(symbol, date, freq, 1)

        expect(key0).not.toBe(key1)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 7b: 相同参数产生相同的缓存键（确定性）
   *
   * For any symbol, date, freq, adjType combination, calling buildCacheKey
   * twice with identical parameters must return identical keys.
   *
   * Validates: Requirements 5.6
   */
  it('相同参数多次调用 buildCacheKey 产生相同缓存键（确定性）', () => {
    fc.assert(
      fc.property(symbolArb, dateArb, freqArb, adjTypeArb, (symbol, date, freq, adjType) => {
        const key1 = buildCacheKey(symbol, date, freq, adjType)
        const key2 = buildCacheKey(symbol, date, freq, adjType)

        expect(key1).toBe(key2)
      }),
      { numRuns: 100 },
    )
  })
})
