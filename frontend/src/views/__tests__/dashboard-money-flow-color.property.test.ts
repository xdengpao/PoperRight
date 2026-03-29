/**
 * 属性 74：资金流向柱状图颜色映射
 *
 * Feature: a-share-quant-trading-system, Property 74: 资金流向柱状图颜色映射
 *
 * 对任意每日记录列表，main_net_inflow ≥ 0 → '#f85149'，< 0 → '#3fb950'
 *
 * **Validates: Requirements 26.4**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { getMoneyFlowBarColor } from '@/views/moneyFlowUtils'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成有限浮点数（排除 NaN / Infinity） */
const finiteFloat = fc.double({ min: -1e9, max: 1e9, noNaN: true })

/** 生成非负浮点数（≥ 0） */
const nonNegativeFloat = fc.double({ min: 0, max: 1e9, noNaN: true })

/** 生成负浮点数（< 0） */
const negativeFloat = fc.double({ min: -1e9, max: -Number.MIN_VALUE, noNaN: true })

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 74：资金流向柱状图颜色映射', () => {
  /**
   * 属性 74a：非负净流入 → 红色 (#f85149)
   * Validates: Requirements 26.4
   */
  it('main_net_inflow ≥ 0 → #f85149（红色）', () => {
    fc.assert(
      fc.property(nonNegativeFloat, (value) => {
        expect(getMoneyFlowBarColor(value)).toBe('#f85149')
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 74b：负净流入 → 绿色 (#3fb950)
   * Validates: Requirements 26.4
   */
  it('main_net_inflow < 0 → #3fb950（绿色）', () => {
    fc.assert(
      fc.property(negativeFloat, (value) => {
        expect(getMoneyFlowBarColor(value)).toBe('#3fb950')
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 74c：对任意每日记录列表，颜色映射始终正确
   * Validates: Requirements 26.4
   */
  it('任意每日记录列表的颜色映射均符合规则', () => {
    fc.assert(
      fc.property(fc.array(finiteFloat, { minLength: 1, maxLength: 30 }), (records) => {
        for (const value of records) {
          const color = getMoneyFlowBarColor(value)
          if (value >= 0) {
            expect(color).toBe('#f85149')
          } else {
            expect(color).toBe('#3fb950')
          }
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 74d：返回值始终为合法颜色之一
   * Validates: Requirements 26.4
   */
  it('返回值始终为 #f85149 或 #3fb950 之一', () => {
    const validColors = new Set(['#f85149', '#3fb950'])
    fc.assert(
      fc.property(finiteFloat, (value) => {
        expect(validColors.has(getMoneyFlowBarColor(value))).toBe(true)
      }),
      { numRuns: 200 },
    )
  })
})
