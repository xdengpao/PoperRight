/**
 * Feature: minute-kline-chart, Property 1: 日K线点击提取正确日期
 *
 * For any 有效的日K线 bars 数组和任意有效索引 i，
 * extractDateFromClick(dates, i) 应返回 dates[i]。
 * 对于越界索引，应返回 null。
 *
 * **Validates: Requirements 3.1**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { extractDateFromClick } from '@/components/minuteKlineUtils'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成有效的 YYYY-MM-DD 日期字符串 */
const dateStringArb = fc
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

/** 生成非空日期数组（1~50 个日期） */
const datesArrayArb = fc.array(dateStringArb, { minLength: 1, maxLength: 50 })

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: minute-kline-chart, Property 1: 日K线点击提取正确日期', () => {
  /**
   * Property 1a: 有效索引返回对应日期
   * For any non-empty dates array and valid index i (0 <= i < dates.length),
   * extractDateFromClick(dates, i) === dates[i]
   *
   * Validates: Requirements 3.1
   */
  it('有效索引 i 时，extractDateFromClick 返回 dates[i]', () => {
    fc.assert(
      fc.property(datesArrayArb, (dates) => {
        // 从有效范围内随机选一个索引
        const index = Math.floor(Math.random() * dates.length)
        const result = extractDateFromClick(dates, index)
        expect(result).toBe(dates[index])
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 1b: 有效索引（使用 fast-check 生成索引）返回对应日期
   * Validates: Requirements 3.1
   */
  it('fast-check 生成的有效索引返回 dates[index]', () => {
    fc.assert(
      fc.property(
        datesArrayArb.chain((dates) =>
          fc.integer({ min: 0, max: dates.length - 1 }).map((idx) => ({ dates, idx })),
        ),
        ({ dates, idx }) => {
          const result = extractDateFromClick(dates, idx)
          expect(result).toBe(dates[idx])
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * Property 1c: 负数索引返回 null
   * Validates: Requirements 3.1
   */
  it('负数索引返回 null', () => {
    fc.assert(
      fc.property(datesArrayArb, fc.integer({ min: -1000, max: -1 }), (dates, negIndex) => {
        const result = extractDateFromClick(dates, negIndex)
        expect(result).toBeNull()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 1d: 超出上界的索引返回 null
   * Validates: Requirements 3.1
   */
  it('超出上界的索引返回 null', () => {
    fc.assert(
      fc.property(datesArrayArb, fc.integer({ min: 0, max: 500 }), (dates, offset) => {
        const outOfBoundsIndex = dates.length + offset
        const result = extractDateFromClick(dates, outOfBoundsIndex)
        expect(result).toBeNull()
      }),
      { numRuns: 100 },
    )
  })
})
