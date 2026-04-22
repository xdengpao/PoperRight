/**
 * Tushare 数据预览前端属性测试
 *
 * 测试 tusharePreview Store 中导出的纯函数：
 * - groupRegistryByCategory：注册表分组逻辑
 * - inferChartType：图表类型推断
 * - getStatusColor：导入状态颜色映射
 *
 * 使用 fast-check 进行属性测试，每个属性 100 次迭代。
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import {
  groupRegistryByCategory,
  inferChartType,
  getStatusColor,
  CHART_TYPE_MAP,
  type ApiRegistryItem,
} from '@/stores/tusharePreview'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成随机 ApiRegistryItem */
const apiRegistryItemArb: fc.Arbitrary<ApiRegistryItem> = fc.record({
  api_name: fc.string({ minLength: 1, maxLength: 30 }),
  label: fc.string({ minLength: 1, maxLength: 30 }),
  category: fc.string({ minLength: 1, maxLength: 20 }),
  subcategory: fc.string({ minLength: 1, maxLength: 20 }),
  token_tier: fc.constantFrom('basic', 'vip', 'super_vip'),
  required_params: fc.array(fc.string({ minLength: 1, maxLength: 10 }), { maxLength: 5 }),
  optional_params: fc.array(fc.string({ minLength: 1, maxLength: 10 }), { maxLength: 5 }),
  token_available: fc.boolean(),
  vip_variant: fc.option(fc.string({ minLength: 1, maxLength: 20 }), { nil: null }),
})

/** 生成随机注册表条目列表 */
const registryListArb = fc.array(apiRegistryItemArb, { minLength: 0, maxLength: 50 })

/** 生成随机 targetTable 字符串 */
const targetTableArb = fc.string({ minLength: 1, maxLength: 30 })

/** 生成随机 subcategory 字符串 */
const subcategoryArb = fc.string({ minLength: 1, maxLength: 30 })

/** 生成随机 timeField（string | null） */
const timeFieldArb = fc.option(fc.string({ minLength: 1, maxLength: 20 }), { nil: null })

/** 已知状态集合 */
const knownStatuses = ['completed', 'failed', 'running', 'pending', 'stopped'] as const

/** 生成已知状态 */
const knownStatusArb = fc.constantFrom(...knownStatuses)

/** 生成任意状态字符串（包含未知状态） */
const arbitraryStatusArb = fc.oneof(
  knownStatusArb,
  fc.string({ minLength: 0, maxLength: 20 }),
)

// ─── Property 1: Registry grouping preserves all entries with correct counts ──

// Feature: tushare-data-preview, Property 1: Registry grouping preserves all entries with correct counts
describe('Feature: tushare-data-preview, Property 1: Registry grouping preserves all entries with correct counts', () => {
  /**
   * 分组后所有条目恰好出现一次：输出条目总数等于输入条目总数
   * **Validates: Requirements 2.1, 2.5**
   */
  it('分组后条目总数等于输入条目总数', () => {
    fc.assert(
      fc.property(registryListArb, (entries) => {
        const groups = groupRegistryByCategory(entries)

        // 统计输出中的条目总数
        let totalOutput = 0
        for (const group of groups) {
          for (const subGroup of group.subcategories) {
            totalOutput += subGroup.apis.length
          }
        }

        expect(totalOutput).toBe(entries.length)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 每个条目被放置在正确的 category 和 subcategory 下
   * **Validates: Requirements 2.1, 2.5**
   */
  it('每个条目被放置在正确的 category 和 subcategory 下', () => {
    fc.assert(
      fc.property(registryListArb, (entries) => {
        const groups = groupRegistryByCategory(entries)

        for (const group of groups) {
          for (const subGroup of group.subcategories) {
            for (const api of subGroup.apis) {
              expect(api.category).toBe(group.category)
              expect(api.subcategory).toBe(subGroup.subcategory)
            }
          }
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 子分类计数等于该组内条目数
   * **Validates: Requirements 2.1, 2.5**
   */
  it('子分类的 apis.length 等于该子分类下的实际条目数', () => {
    fc.assert(
      fc.property(registryListArb, (entries) => {
        const groups = groupRegistryByCategory(entries)

        // 构建期望的计数映射：category+subcategory → count
        const expectedCounts = new Map<string, number>()
        for (const entry of entries) {
          const key = `${entry.category}::${entry.subcategory}`
          expectedCounts.set(key, (expectedCounts.get(key) ?? 0) + 1)
        }

        for (const group of groups) {
          for (const subGroup of group.subcategories) {
            const key = `${group.category}::${subGroup.subcategory}`
            expect(subGroup.apis.length).toBe(expectedCounts.get(key))
          }
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 空输入产生空输出
   * **Validates: Requirements 2.1, 2.5**
   */
  it('空输入产生空分组', () => {
    const groups = groupRegistryByCategory([])
    expect(groups).toEqual([])
  })
})

// ─── Property 3: Chart type inference follows deterministic rules ─────────────

// Feature: tushare-data-preview, Property 3: Chart type inference follows deterministic rules
describe('Feature: tushare-data-preview, Property 3: Chart type inference follows deterministic rules', () => {
  /**
   * kline 表返回 'candlestick'（无论 subcategory 和 timeField）
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('targetTable 为 kline 时返回 candlestick', () => {
    fc.assert(
      fc.property(subcategoryArb, timeFieldArb, (subcategory, timeField) => {
        expect(inferChartType('kline', subcategory, timeField)).toBe('candlestick')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * sector_kline 表返回 'candlestick'（无论 subcategory 和 timeField）
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('targetTable 为 sector_kline 时返回 candlestick', () => {
    fc.assert(
      fc.property(subcategoryArb, timeFieldArb, (subcategory, timeField) => {
        expect(inferChartType('sector_kline', subcategory, timeField)).toBe('candlestick')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * subcategory 在 CHART_TYPE_MAP 中且非 K 线表时返回对应映射类型
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('subcategory 在 CHART_TYPE_MAP 中且非 K 线表时返回映射类型', () => {
    const chartTypeMapKeys = [...CHART_TYPE_MAP.keys()]
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        fc.constantFrom(...chartTypeMapKeys),
        timeFieldArb,
        (targetTable, subcategory, timeField) => {
          expect(inferChartType(targetTable, subcategory, timeField)).toBe(CHART_TYPE_MAP.get(subcategory))
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * K 线表优先级高于 CHART_TYPE_MAP subcategory：kline + 资金流向数据 → candlestick
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('K 线表优先级高于 CHART_TYPE_MAP subcategory', () => {
    expect(inferChartType('kline', '资金流向数据', null)).toBe('candlestick')
    expect(inferChartType('sector_kline', '资金流向数据', null)).toBe('candlestick')
    expect(inferChartType('kline', '打板专题数据', 'trade_date')).toBe('candlestick')
  })

  /**
   * 非 K 线表、非 CHART_TYPE_MAP subcategory、有 timeField 时返回 line
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('非 K 线表且非 CHART_TYPE_MAP subcategory 但有 timeField 时返回 line', () => {
    const chartTypeMapKeys = new Set(CHART_TYPE_MAP.keys())
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        subcategoryArb.filter((s) => !chartTypeMapKeys.has(s)),
        fc.string({ minLength: 1, maxLength: 20 }),
        (targetTable, subcategory, timeField) => {
          expect(inferChartType(targetTable, subcategory, timeField)).toBe('line')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 非 K 线表、非 CHART_TYPE_MAP subcategory、timeField 为 null 时返回 null
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('非 K 线表且非 CHART_TYPE_MAP subcategory 且 timeField 为 null 时返回 null', () => {
    const chartTypeMapKeys = new Set(CHART_TYPE_MAP.keys())
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        subcategoryArb.filter((s) => !chartTypeMapKeys.has(s)),
        (targetTable, subcategory) => {
          expect(inferChartType(targetTable, subcategory, null)).toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 结果完全由 targetTable、subcategory 和 timeField 决定（确定性）
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
   */
  it('相同输入始终产生相同输出（确定性）', () => {
    fc.assert(
      fc.property(targetTableArb, subcategoryArb, timeFieldArb, (targetTable, subcategory, timeField) => {
        const result1 = inferChartType(targetTable, subcategory, timeField)
        const result2 = inferChartType(targetTable, subcategory, timeField)
        expect(result1).toBe(result2)
      }),
      { numRuns: 100 },
    )
  })
})

// ─── Property 8: Import status color mapping ─────────────────────────────────

// Feature: tushare-data-preview, Property 8: Import status color mapping
describe('Feature: tushare-data-preview, Property 8: Import status color mapping', () => {
  /**
   * 已知状态返回确定的颜色映射
   * **Validates: Requirements 10.4**
   */
  it('已知状态返回正确的 CSS 类', () => {
    fc.assert(
      fc.property(knownStatusArb, (status) => {
        const color = getStatusColor(status)

        switch (status) {
          case 'completed':
            expect(color).toBe('status-green')
            break
          case 'failed':
            expect(color).toBe('status-red')
            break
          case 'running':
          case 'pending':
            expect(color).toBe('status-blue')
            break
          case 'stopped':
            expect(color).toBe('status-gray')
            break
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 未知状态返回默认颜色
   * **Validates: Requirements 10.4**
   */
  it('未知状态返回 status-default', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 0, maxLength: 20 }).filter(
          (s) => !['completed', 'failed', 'running', 'pending', 'stopped'].includes(s),
        ),
        (unknownStatus) => {
          expect(getStatusColor(unknownStatus)).toBe('status-default')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 对任意状态字符串，返回值始终是已知 CSS 类之一
   * **Validates: Requirements 10.4**
   */
  it('对任意状态字符串，返回值始终是有效的 CSS 类', () => {
    const validClasses = new Set([
      'status-green',
      'status-red',
      'status-blue',
      'status-gray',
      'status-default',
    ])

    fc.assert(
      fc.property(arbitraryStatusArb, (status) => {
        const color = getStatusColor(status)
        expect(validClasses.has(color)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 相同状态始终返回相同颜色（确定性）
   * **Validates: Requirements 10.4**
   */
  it('相同状态始终返回相同颜色（确定性）', () => {
    fc.assert(
      fc.property(arbitraryStatusArb, (status) => {
        const result1 = getStatusColor(status)
        const result2 = getStatusColor(status)
        expect(result1).toBe(result2)
      }),
      { numRuns: 100 },
    )
  })
})
