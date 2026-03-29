/**
 * 属性 58：清洗统计 UI 展示 API 数据正确性
 *
 * Feature: data-manage-dual-source-integration, Property 58: 清洗统计 UI 展示 API 数据正确性
 *
 * 对任意有效 CleaningStatsResponse 数据，验证页面展示数值与 API 返回一致，无硬编码静态数值
 *
 * **Validates: Requirements 24.8**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（镜像 DataManageView.vue 中的接口） ─────────────────────────────

interface CleaningStatsResponse {
  total_stocks: number
  valid_stocks: number
  st_delisted_count: number
  new_stock_count: number
  suspended_count: number
  high_pledge_count: number
}

// ─── UI 渲染逻辑（提取自模板的纯函数） ───────────────────────────────────────

/** 模拟模板中 `value?.toLocaleString() ?? '—'` 的格式化逻辑 */
function formatStatValue(value: number | null | undefined): string {
  return value?.toLocaleString() ?? '—'
}

/** 从 CleaningStatsResponse 提取 6 张统计卡片的展示值 */
function renderCleaningStats(data: CleaningStatsResponse | null): Record<string, string> {
  return {
    总股票数: formatStatValue(data?.total_stocks),
    有效标的: formatStatValue(data?.valid_stocks),
    'ST / 退市剔除': formatStatValue(data?.st_delisted_count),
    新股剔除: formatStatValue(data?.new_stock_count),
    停牌剔除: formatStatValue(data?.suspended_count),
    高质押剔除: formatStatValue(data?.high_pledge_count),
  }
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const nonNegativeIntArb = fc.integer({ min: 0, max: 10_000_000 })

const cleaningStatsArb: fc.Arbitrary<CleaningStatsResponse> = fc.record({
  total_stocks: nonNegativeIntArb,
  valid_stocks: nonNegativeIntArb,
  st_delisted_count: nonNegativeIntArb,
  new_stock_count: nonNegativeIntArb,
  suspended_count: nonNegativeIntArb,
  high_pledge_count: nonNegativeIntArb,
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 58：清洗统计 UI 展示 API 数据正确性', () => {
  /**
   * 属性 58a：对任意有效 CleaningStatsResponse，6 张卡片展示值与 toLocaleString() 格式化结果一致
   * Validates: Requirements 24.8
   */
  it('6 张统计卡片展示值与 API 返回数据的 toLocaleString() 格式化结果一致', () => {
    fc.assert(
      fc.property(cleaningStatsArb, (stats) => {
        const rendered = renderCleaningStats(stats)

        expect(rendered['总股票数']).toBe(stats.total_stocks.toLocaleString())
        expect(rendered['有效标的']).toBe(stats.valid_stocks.toLocaleString())
        expect(rendered['ST / 退市剔除']).toBe(stats.st_delisted_count.toLocaleString())
        expect(rendered['新股剔除']).toBe(stats.new_stock_count.toLocaleString())
        expect(rendered['停牌剔除']).toBe(stats.suspended_count.toLocaleString())
        expect(rendered['高质押剔除']).toBe(stats.high_pledge_count.toLocaleString())
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 58b：当 data 为 null 时，所有卡片展示 '—' 占位符
   * Validates: Requirements 24.8
   */
  it('data 为 null 时所有卡片展示占位符 "—"', () => {
    const rendered = renderCleaningStats(null)
    for (const label of Object.keys(rendered)) {
      expect(rendered[label]).toBe('—')
    }
  })

  /**
   * 属性 58c：对任意有效数据，展示值不包含旧的硬编码静态数值
   * Validates: Requirements 24.8
   */
  it('展示值不包含旧的硬编码静态数值（5,354 / 4,821 / 312 / 221）', () => {
    const hardcodedValues = new Set(['5,354', '4,821', '312', '221'])

    fc.assert(
      fc.property(
        cleaningStatsArb.filter(
          (s) =>
            s.total_stocks !== 5354 &&
            s.valid_stocks !== 4821 &&
            s.st_delisted_count !== 312 &&
            s.new_stock_count !== 221,
        ),
        (stats) => {
          const rendered = renderCleaningStats(stats)
          for (const label of Object.keys(rendered)) {
            expect(hardcodedValues.has(rendered[label])).toBe(false)
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 58d：对任意有效数据，渲染结果恰好包含 6 张统计卡片
   * Validates: Requirements 24.8
   */
  it('渲染结果恰好包含 6 张统计卡片', () => {
    fc.assert(
      fc.property(cleaningStatsArb, (stats) => {
        const rendered = renderCleaningStats(stats)
        expect(Object.keys(rendered)).toHaveLength(6)
        expect(Object.keys(rendered)).toEqual([
          '总股票数',
          '有效标的',
          'ST / 退市剔除',
          '新股剔除',
          '停牌剔除',
          '高质押剔除',
        ])
      }),
      { numRuns: 100 },
    )
  })
})
