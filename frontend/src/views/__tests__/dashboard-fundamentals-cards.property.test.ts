/**
 * 属性 72：基本面数据卡片渲染全部指标及元数据
 *
 * Feature: a-share-quant-trading-system, Property 72: 基本面数据卡片渲染完整性
 *
 * For any 合法的 StockFundamentalsResponse（数值字段非 null），
 * 渲染应包含六个指标值及报告期和更新时间
 *
 * **Validates: Requirements 26.2, 26.11**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { formatFundamentalValue } from '../fundamentalUtils'

// ─── Mock 依赖 ────────────────────────────────────────────────────────────────

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })),
}))

// Will be configured per-test via mockApiGet
const mockApiGet = vi.fn()

vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.stubGlobal(
  'WebSocket',
  vi.fn().mockImplementation(() => ({
    onmessage: null,
    onclose: null,
    close: vi.fn(),
  })),
)

import DashboardView from '../DashboardView.vue'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface StockFundamentalsResponse {
  symbol: string
  name: string | null
  pe_ttm: number | null
  pb: number | null
  roe: number | null
  market_cap: number | null
  revenue_growth: number | null
  net_profit_growth: number | null
  report_period: string | null
  updated_at: string | null
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** Generate a valid StockFundamentalsResponse with all numeric fields non-null */
const fundamentalsArb: fc.Arbitrary<StockFundamentalsResponse> = fc.record({
  symbol: fc.stringMatching(/^[0-9]{6}$/),
  name: fc.string({ minLength: 1, maxLength: 10 }),
  pe_ttm: fc.double({ min: -500, max: 2000, noNaN: true, noDefaultInfinity: true }),
  pb: fc.double({ min: -100, max: 500, noNaN: true, noDefaultInfinity: true }),
  roe: fc.double({ min: -100, max: 100, noNaN: true, noDefaultInfinity: true }),
  market_cap: fc.double({ min: 0.01, max: 100000, noNaN: true, noDefaultInfinity: true }),
  revenue_growth: fc.double({ min: -100, max: 1000, noNaN: true, noDefaultInfinity: true }),
  net_profit_growth: fc.double({ min: -100, max: 1000, noNaN: true, noDefaultInfinity: true }),
  report_period: fc.stringMatching(/^20[0-9]{2}-(0[1-9]|1[0-2])-[0-3][0-9]$/),
  updated_at: fc.stringMatching(/^20[0-9]{2}-(0[1-9]|1[0-2])-[0-3][0-9] [0-2][0-9]:[0-5][0-9]$/),
})

// ─── 六个指标的 key 和对应 formatFundamentalValue 的预期 ─────────────────────

const METRIC_KEYS = ['pe_ttm', 'pb', 'roe', 'market_cap', 'revenue_growth', 'net_profit_growth'] as const

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 72：基本面数据卡片渲染全部指标及元数据', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 属性 72a：对任意非 null 基本面数据，formatFundamentalValue 为六个指标均产生非 "--" 的格式化值
   * Validates: Requirements 26.2
   */
  it('formatFundamentalValue 为六个非 null 指标均产生有效格式化值', () => {
    fc.assert(
      fc.property(fundamentalsArb, (data) => {
        for (const key of METRIC_KEYS) {
          const value = data[key]
          const formatted = formatFundamentalValue(key, value)
          // Non-null values should never produce '--'
          expect(formatted).not.toBe('--')
          // Should be a non-empty string
          expect(formatted.length).toBeGreaterThan(0)
        }
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 72b：对任意非 null 基本面数据，六个指标的格式化值符合各自的格式规则
   * Validates: Requirements 26.2
   */
  it('六个指标的格式化值符合各自的格式规则', () => {
    fc.assert(
      fc.property(fundamentalsArb, (data) => {
        // pe_ttm and pb: should end with no suffix, just a decimal number
        expect(formatFundamentalValue('pe_ttm', data.pe_ttm)).toMatch(/^-?\d+\.\d{2}$/)
        expect(formatFundamentalValue('pb', data.pb)).toMatch(/^-?\d+\.\d{2}$/)

        // roe, revenue_growth, net_profit_growth: should end with '%'
        expect(formatFundamentalValue('roe', data.roe)).toMatch(/^-?\d+\.\d{2}%$/)
        expect(formatFundamentalValue('revenue_growth', data.revenue_growth)).toMatch(/^-?\d+\.\d{2}%$/)
        expect(formatFundamentalValue('net_profit_growth', data.net_profit_growth)).toMatch(/^-?\d+\.\d{2}%$/)

        // market_cap: should end with ' 亿'
        expect(formatFundamentalValue('market_cap', data.market_cap)).toMatch(/^-?\d+\.\d{2} 亿$/)
      }),
      { numRuns: 200 },
    )
  })

  /**
   * 属性 72c：组件 DOM 中对任意基本面数据，渲染包含六个指标值及报告期和更新时间
   * Validates: Requirements 26.2, 26.11
   */
  it('组件渲染包含六个指标格式化值及报告期和更新时间', async () => {
    await fc.assert(
      fc.asyncProperty(fundamentalsArb, async (data) => {
        // Configure mock API to return generated fundamentals data
        mockApiGet.mockImplementation((url: string) => {
          if (url.includes('/market/overview')) {
            return Promise.resolve({
              data: {
                sh_index: 3000, sh_change_pct: 0.5,
                sz_index: 10000, sz_change_pct: -0.3,
                cyb_index: 2000, cyb_change_pct: 1.2,
                advance_count: 2000, decline_count: 1500,
                limit_up_count: 30, limit_down_count: 10,
                updated_at: new Date().toISOString(),
              },
            })
          }
          if (url.includes('/market/sectors')) {
            return Promise.resolve({ data: [] })
          }
          if (url.includes('/kline/')) {
            return Promise.resolve({
              data: { symbol: '000001', name: '测试', freq: '1d', bars: [] },
            })
          }
          if (url.includes('/fundamentals')) {
            return Promise.resolve({ data: data })
          }
          if (url.includes('/money-flow')) {
            return Promise.resolve({ data: null })
          }
          return Promise.resolve({ data: {} })
        })

        const pinia = createPinia()
        setActivePinia(pinia)

        const wrapper = mount(DashboardView, {
          global: { plugins: [pinia] },
        })

        await flushPromises()
        await wrapper.vm.$nextTick()

        // Click the "基本面" tab
        const tabButtons = wrapper.findAll('[role="tab"]')
        for (const btn of tabButtons) {
          if (btn.text().includes('基本面')) {
            await btn.trigger('click')
            break
          }
        }
        await flushPromises()
        await wrapper.vm.$nextTick()

        const html = wrapper.html()

        // Verify all 6 metric formatted values are present in the rendered output
        for (const key of METRIC_KEYS) {
          const formatted = formatFundamentalValue(key, data[key])
          expect(html).toContain(formatted)
        }

        // Verify report_period and updated_at metadata are rendered (需求 26.11)
        expect(html).toContain(data.report_period!)
        expect(html).toContain(data.updated_at!)

        wrapper.unmount()
      }),
      { numRuns: 20 },
    )
  })
})
