/**
 * Feature: stock-pool-management
 *
 * 前端属性测试（Vitest + fast-check）
 *
 * Property 3: 选股池名称校验拒绝无效输入
 * Property 7: 非法股票代码拒绝
 *
 * **Validates: Requirements 3.3, 3.9, 5.3**
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { validatePoolName, validateStockSymbol } from '@/stores/stockPool'

// ---------------------------------------------------------------------------
// Property 3: 选股池名称校验
// ---------------------------------------------------------------------------

describe('Property 3: 选股池名称前端校验', () => {
  /**
   * **Validates: Requirements 3.3**
   *
   * 对于任意仅由空白字符组成的字符串，validatePoolName 应返回 { valid: false }。
   */
  it('纯空白字符串应被拒绝', () => {
    const whitespaceOnlyArb = fc.stringOf(
      fc.constantFrom(' ', '\t', '\n', '\r', '\u3000'),
      { minLength: 0, maxLength: 60 },
    )

    fc.assert(
      fc.property(whitespaceOnlyArb, (name) => {
        const result = validatePoolName(name)
        expect(result.valid).toBe(false)
        expect(result.error).toBeDefined()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * **Validates: Requirements 3.9**
   *
   * 对于任意 trim 后长度超过 50 个字符的字符串，validatePoolName 应返回 { valid: false }。
   */
  it('trim 后超过 50 字符的字符串应被拒绝', () => {
    // 生成 trim 后长度 > 50 的字符串
    const longNameArb = fc.string({ minLength: 51, maxLength: 100 }).filter(
      (s) => s.trim().length > 50,
    )

    fc.assert(
      fc.property(longNameArb, (name) => {
        const result = validatePoolName(name)
        expect(result.valid).toBe(false)
        expect(result.error).toBeDefined()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * **Validates: Requirements 3.3, 3.9**
   *
   * 对于任意非空且 trim 后长度在 1-50 之间的字符串，validatePoolName 应返回 { valid: true }。
   */
  it('trim 后长度 1-50 的非空字符串应被接受', () => {
    // 生成至少包含一个非空白字符、trim 后长度 1-50 的字符串
    const validNameArb = fc
      .tuple(
        fc.string({ minLength: 0, maxLength: 10 }),
        fc.stringOf(fc.char().filter((c) => c.trim().length > 0), { minLength: 1, maxLength: 50 }),
        fc.string({ minLength: 0, maxLength: 10 }),
      )
      .map(([prefix, core, suffix]) => {
        // 确保 trim 后长度 ≤ 50
        const trimmed = (prefix + core + suffix).trim()
        return trimmed.length > 50 ? trimmed.slice(0, 50) : prefix + core + suffix
      })
      .filter((s) => {
        const t = s.trim()
        return t.length >= 1 && t.length <= 50
      })

    fc.assert(
      fc.property(validNameArb, (name) => {
        const result = validatePoolName(name)
        expect(result.valid).toBe(true)
        expect(result.error).toBeUndefined()
      }),
      { numRuns: 100 },
    )
  })
})

// ---------------------------------------------------------------------------
// Property 7: 股票代码校验
// ---------------------------------------------------------------------------

describe('Property 7: 股票代码前端校验', () => {
  /**
   * **Validates: Requirements 5.3**
   *
   * 对于任意不匹配 /^\d{6}$/ 的字符串，validateStockSymbol 应返回 { valid: false }。
   */
  it('非 6 位数字字符串应被拒绝', () => {
    const invalidSymbolArb = fc.string({ minLength: 0, maxLength: 20 }).filter(
      (s) => !/^\d{6}$/.test(s),
    )

    fc.assert(
      fc.property(invalidSymbolArb, (symbol) => {
        const result = validateStockSymbol(symbol)
        expect(result.valid).toBe(false)
        expect(result.error).toBeDefined()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * **Validates: Requirements 5.3**
   *
   * 对于任意恰好 6 位数字的字符串，validateStockSymbol 应返回 { valid: true }。
   */
  it('恰好 6 位数字的字符串应被接受', () => {
    const validSymbolArb = fc
      .tuple(
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
        fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
      )
      .map((digits) => digits.join(''))

    fc.assert(
      fc.property(validSymbolArb, (symbol) => {
        const result = validateStockSymbol(symbol)
        expect(result.valid).toBe(true)
        expect(result.error).toBeUndefined()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * **Validates: Requirements 5.3**
   *
   * 长度不为 6 的纯数字字符串也应被拒绝。
   */
  it('长度不为 6 的纯数字字符串应被拒绝', () => {
    const wrongLengthDigitsArb = fc
      .stringOf(fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'), {
        minLength: 0,
        maxLength: 20,
      })
      .filter((s) => s.length !== 6)

    fc.assert(
      fc.property(wrongLengthDigitsArb, (symbol) => {
        const result = validateStockSymbol(symbol)
        expect(result.valid).toBe(false)
      }),
      { numRuns: 100 },
    )
  })
})
