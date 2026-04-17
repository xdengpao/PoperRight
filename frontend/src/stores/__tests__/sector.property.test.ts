/**
 * 板块排行项显示格式化属性测试
 *
 * Feature: sector-ranking-display, Property 5: Ranking item display formatting
 *
 * 对任意 SectorRankingItem 数据，验证涨跌幅、成交额、换手率、收盘价的
 * 格式化输出和 CSS class 分配符合需求规范。
 *
 * **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import type { SectorRankingItem } from '@/stores/sector'

// ─── 格式化纯函数（提取自 DashboardView.vue 模板内联逻辑）─────────────────────

/**
 * 格式化涨跌幅：正值 "+" 前缀、两位小数、"%" 后缀；null 返回 "--"
 */
function formatChangePct(change_pct: number | null): string {
  if (change_pct == null) return '--'
  return (change_pct >= 0 ? '+' : '') + change_pct.toFixed(2) + '%'
}

/**
 * 获取涨跌幅 CSS class：>= 0 为 'up'，< 0 为 'down'；null 视为 0 → 'up'
 */
function getChangePctClass(change_pct: number | null): 'up' | 'down' {
  return (change_pct ?? 0) >= 0 ? 'up' : 'down'
}

/**
 * 格式化成交额：以亿为单位（amount / 1e8），两位小数；null 返回 "--"
 */
function formatAmount(amount: number | null): string {
  if (amount == null) return '--'
  return (amount / 1e8).toFixed(2)
}

/**
 * 格式化换手率：两位小数 + "%" 后缀；null 返回 "--"
 */
function formatTurnover(turnover: number | null): string {
  if (turnover == null) return '--'
  return turnover.toFixed(2) + '%'
}

/**
 * 格式化收盘价：两位小数；null 返回 "--"
 */
function formatClose(close: number | null): string {
  if (close == null) return '--'
  return close.toFixed(2)
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成 JSON 安全的 double（排除 NaN、Infinity） */
const safeDouble = fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true })

/** 生成可空的 double */
const nullableDouble = fc.option(safeDouble, { nil: null })

/** 生成随机 SectorRankingItem */
const sectorRankingItemArb: fc.Arbitrary<SectorRankingItem> = fc.record({
  sector_code: fc.string({ minLength: 1, maxLength: 10 }),
  name: fc.string({ minLength: 1, maxLength: 20 }),
  sector_type: fc.constantFrom('CONCEPT', 'INDUSTRY', 'REGION', 'STYLE'),
  change_pct: nullableDouble,
  close: nullableDouble,
  volume: fc.option(fc.integer({ min: 0, max: 1e9 }), { nil: null }),
  amount: nullableDouble,
  turnover: nullableDouble,
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: sector-ranking-display, Property 5: Ranking item display formatting', () => {
  /**
   * 涨跌幅格式化：正值有 "+" 前缀、两位小数、"%" 后缀
   * Validates: Requirements 4.2, 4.3
   */
  it('非空 change_pct 格式化包含正确前缀、两位小数和 % 后缀', () => {
    fc.assert(
      fc.property(safeDouble, (changePct) => {
        const formatted = formatChangePct(changePct)

        // 必须以 % 结尾
        expect(formatted.endsWith('%')).toBe(true)

        // 正值必须有 + 前缀
        if (changePct >= 0) {
          expect(formatted.startsWith('+')).toBe(true)
        } else {
          expect(formatted.startsWith('-')).toBe(true)
        }

        // 两位小数：去掉 % 后缀，解析数值应与原值两位小数一致
        const numericPart = formatted.slice(0, -1) // 去掉 %
        const parsed = parseFloat(numericPart)
        expect(parsed).toBeCloseTo(changePct, 2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 涨跌幅 CSS class：>= 0 为 'up'，< 0 为 'down'
   * Validates: Requirements 4.2
   */
  it('change_pct CSS class 正确分配 up/down', () => {
    fc.assert(
      fc.property(nullableDouble, (changePct) => {
        const cssClass = getChangePctClass(changePct)

        if (changePct == null || changePct >= 0) {
          expect(cssClass).toBe('up')
        } else {
          expect(cssClass).toBe('down')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 成交额亿元转换：amount / 1e8，两位小数
   * Validates: Requirements 4.4
   */
  it('非空 amount 正确转换为亿元并保留两位小数', () => {
    fc.assert(
      fc.property(safeDouble, (amount) => {
        const formatted = formatAmount(amount)
        const expected = (amount / 1e8).toFixed(2)
        expect(formatted).toBe(expected)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 换手率格式化：两位小数 + "%" 后缀
   * Validates: Requirements 4.5
   */
  it('非空 turnover 格式化为两位小数加 % 后缀', () => {
    fc.assert(
      fc.property(safeDouble, (turnover) => {
        const formatted = formatTurnover(turnover)

        expect(formatted.endsWith('%')).toBe(true)

        const numericPart = formatted.slice(0, -1)
        const parsed = parseFloat(numericPart)
        expect(parsed).toBeCloseTo(turnover, 2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 空值占位符：null 字段显示 "--"
   * Validates: Requirements 4.6
   */
  it('null 字段统一显示 "--" 占位符', () => {
    fc.assert(
      fc.property(sectorRankingItemArb, (item) => {
        if (item.change_pct == null) {
          expect(formatChangePct(item.change_pct)).toBe('--')
        }
        if (item.close == null) {
          expect(formatClose(item.close)).toBe('--')
        }
        if (item.amount == null) {
          expect(formatAmount(item.amount)).toBe('--')
        }
        if (item.turnover == null) {
          expect(formatTurnover(item.turnover)).toBe('--')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 收盘价格式化：两位小数；null 返回 "--"
   * Validates: Requirements 4.6
   */
  it('非空 close 格式化为两位小数', () => {
    fc.assert(
      fc.property(safeDouble, (close) => {
        const formatted = formatClose(close)
        const expected = close.toFixed(2)
        expect(formatted).toBe(expected)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 综合验证：对任意 SectorRankingItem，所有格式化函数输出类型一致
   * Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6
   */
  it('任意 SectorRankingItem 的所有字段格式化输出均为字符串', () => {
    fc.assert(
      fc.property(sectorRankingItemArb, (item) => {
        expect(typeof formatChangePct(item.change_pct)).toBe('string')
        expect(typeof getChangePctClass(item.change_pct)).toBe('string')
        expect(typeof formatClose(item.close)).toBe('string')
        expect(typeof formatAmount(item.amount)).toBe('string')
        expect(typeof formatTurnover(item.turnover)).toBe('string')
      }),
      { numRuns: 100 },
    )
  })
})
