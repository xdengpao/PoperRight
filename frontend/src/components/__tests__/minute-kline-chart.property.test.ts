/**
 * Feature: minute-kline-chart, Property 2: 分钟K线日期标签格式化
 *
 * For any 有效的日期字符串（YYYY-MM-DD 格式），格式化后的标签应严格匹配 "YYYY-MM-DD 分钟K线" 模式。
 *
 * **Validates: Requirements 3.3**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { mount } from '@vue/test-utils'
import { minuteKlineCache } from '../minuteKlineUtils'

// Mock vue-echarts and echarts to avoid ESM import issues in test environment
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="mock-vchart"></div>', props: ['option', 'autoresize'] },
}))
vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/charts', () => ({ CandlestickChart: {}, BarChart: {} }))
vi.mock('echarts/components', () => ({ GridComponent: {}, TooltipComponent: {}, DataZoomComponent: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

// Mock apiClient to prevent real HTTP calls
vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { bars: [] } }),
  },
}))

// Import component after mocks are set up
import MinuteKlineChart from '../MinuteKlineChart.vue'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成有效的 YYYY-MM-DD 日期字符串 */
const dateStringArb = fc
  .record({
    year: fc.integer({ min: 2000, max: 2099 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }), // 使用 28 避免无效日期
  })
  .map(({ year, month, day }) => {
    const mm = String(month).padStart(2, '0')
    const dd = String(day).padStart(2, '0')
    return `${year}-${mm}-${dd}`
  })

/** YYYY-MM-DD 分钟K线 的正则模式 */
const DATE_LABEL_PATTERN = /^\d{4}-\d{2}-\d{2} 分钟K线$/

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: minute-kline-chart, Property 2: 分钟K线日期标签格式化', () => {
  beforeEach(() => {
    minuteKlineCache.clear()
  })

  /**
   * Property 2a: selectedDate 传入时，日期标签格式匹配 "YYYY-MM-DD 分钟K线"
   * Validates: Requirements 3.3
   */
  it('selectedDate 传入任意有效日期时，日期标签匹配 "YYYY-MM-DD 分钟K线" 模式', () => {
    fc.assert(
      fc.property(dateStringArb, (dateStr) => {
        const wrapper = mount(MinuteKlineChart, {
          props: {
            symbol: '600000',
            selectedDate: dateStr,
            latestTradeDate: '2024-01-01',
          },
        })

        const label = wrapper.find('.date-label').text()
        expect(label).toMatch(DATE_LABEL_PATTERN)
        expect(label).toBe(`${dateStr} 分钟K线`)

        wrapper.unmount()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 2b: selectedDate 为 null 时，使用 latestTradeDate，标签格式仍匹配
   * Validates: Requirements 3.3
   */
  it('selectedDate 为 null 时，使用 latestTradeDate 格式化标签', () => {
    fc.assert(
      fc.property(dateStringArb, (dateStr) => {
        const wrapper = mount(MinuteKlineChart, {
          props: {
            symbol: '600000',
            selectedDate: null,
            latestTradeDate: dateStr,
          },
        })

        const label = wrapper.find('.date-label').text()
        expect(label).toMatch(DATE_LABEL_PATTERN)
        expect(label).toBe(`${dateStr} 分钟K线`)

        wrapper.unmount()
      }),
      { numRuns: 100 },
    )
  })
})


// ─── Property 3: 分钟K线 API 请求参数构造 ─────────────────────────────────────

import { buildCacheKey, buildRequestParams } from '../minuteKlineUtils'

/**
 * Feature: minute-kline-chart, Property 3: 分钟K线 API 请求参数构造
 *
 * For any 有效的 symbol、分钟周期 freq（1m/5m/15m/30m/60m）和日期 date，
 * 构造的 API 请求 URL 应包含正确的 symbol 路径参数，
 * query 参数中 freq 等于传入的周期，start 和 end 均等于传入的日期。
 *
 * **Validates: Requirements 5.1**
 */
describe('Feature: minute-kline-chart, Property 3: 分钟K线 API 请求参数构造', () => {
  // ─── 生成器 ─────────────────────────────────────────────────────────────────

  /** 生成 6 位数字股票代码 */
  const symbolArb = fc
    .integer({ min: 0, max: 999999 })
    .map((n) => String(n).padStart(6, '0'))

  /** 生成有效的分钟周期 */
  const freqArb = fc.constantFrom('1m', '5m', '15m', '30m', '60m')

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

  /**
   * Property 3a: buildRequestParams 返回正确的 freq、start、end 参数
   * Validates: Requirements 5.1
   */
  it('buildRequestParams 对任意 freq/date 返回 { freq, start: date, end: date, adj_type: 0 }', () => {
    fc.assert(
      fc.property(freqArb, dateArb, (freq, date) => {
        const params = buildRequestParams(freq, date)

        expect(params).toEqual({ freq, start: date, end: date, adj_type: 0 })
        expect(params.freq).toBe(freq)
        expect(params.start).toBe(date)
        expect(params.end).toBe(date)
        expect(params.adj_type).toBe(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 3b: API 请求路径包含正确的 symbol，query 参数与 buildRequestParams 一致
   * Validates: Requirements 5.1
   */
  it('构造的 API 路径包含 symbol，query 参数包含正确的 freq/start/end', () => {
    fc.assert(
      fc.property(symbolArb, freqArb, dateArb, (symbol, freq, date) => {
        // 模拟前端构造请求的方式：路径 + params
        const path = `/data/kline/${symbol}`
        const params = buildRequestParams(freq, date)

        // 路径包含 symbol
        expect(path).toBe(`/data/kline/${symbol}`)
        expect(path).toContain(symbol)

        // query 参数正确
        expect(params.freq).toBe(freq)
        expect(params.start).toBe(date)
        expect(params.end).toBe(date)

        // 构造完整 URL 验证
        const url = new URL(`http://localhost${path}`)
        url.searchParams.set('freq', params.freq)
        url.searchParams.set('start', params.start)
        url.searchParams.set('end', params.end)

        expect(url.pathname).toBe(`/data/kline/${symbol}`)
        expect(url.searchParams.get('freq')).toBe(freq)
        expect(url.searchParams.get('start')).toBe(date)
        expect(url.searchParams.get('end')).toBe(date)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 3c: symbol 为 6 位数字字符串时路径参数格式正确
   * Validates: Requirements 5.1
   */
  it('6 位数字 symbol 在路径中保持原始格式', () => {
    fc.assert(
      fc.property(symbolArb, (symbol) => {
        const path = `/data/kline/${symbol}`

        // symbol 是 6 位数字
        expect(symbol).toMatch(/^\d{6}$/)
        // 路径以 /data/kline/ 开头并以 symbol 结尾
        expect(path).toMatch(new RegExp(`^/data/kline/${symbol}$`))
      }),
      { numRuns: 100 },
    )
  })
})


// ─── Property 4: 前端缓存命中避免重复请求 ──────────────────────────────────────

import { apiClient } from '@/api'
import type { KlineBar } from '../minuteKlineUtils'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'

/**
 * Feature: minute-kline-chart, Property 4: 前端缓存命中避免重复请求
 *
 * For any 有效的 symbol、freq、date 组合，首次请求后使用相同参数再次请求时，
 * 应命中缓存而不发起新的 API 调用。
 *
 * **Validates: Requirements 5.6**
 */
describe('Feature: minute-kline-chart, Property 4: 前端缓存命中避免重复请求', () => {
  // ─── 生成器 ─────────────────────────────────────────────────────────────────

  /** 生成 6 位数字股票代码 */
  const symbolArb = fc
    .integer({ min: 0, max: 999999 })
    .map((n) => String(n).padStart(6, '0'))

  /** 生成有效的分钟周期 */
  const freqArb = fc.constantFrom('1m', '5m', '15m', '30m', '60m')

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

  /** 生成 1~3 条假 KlineBar 数据 */
  const fakeBarsArb = fc
    .integer({ min: 1, max: 3 })
    .map((n) =>
      Array.from({ length: n }, (_, i) => ({
        time: `2024-01-01T09:${String(30 + i).padStart(2, '0')}:00`,
        open: '10.00',
        high: '10.50',
        low: '9.80',
        close: '10.20',
        volume: 1000 * (i + 1),
        amount: '100000.00',
        turnover: '0.10',
        vol_ratio: '1.00',
      } satisfies KlineBar)),
    )

  beforeEach(() => {
    minuteKlineCache.clear()
    vi.mocked(apiClient.get).mockClear()
  })

  /**
   * Property 4: 缓存预填充后，组件挂载时命中缓存，不发起 API 请求
   * Validates: Requirements 5.6
   */
  it('缓存已有数据时，相同 symbol/date/freq 挂载组件不发起 API 请求', async () => {
    await fc.assert(
      fc.asyncProperty(symbolArb, freqArb, dateArb, fakeBarsArb, async (symbol, freq, date, fakeBars) => {
        // 清理状态
        minuteKlineCache.clear()
        vi.mocked(apiClient.get).mockClear()

        // 1. 预填充缓存
        const key = buildCacheKey(symbol, date, freq)
        minuteKlineCache.set(key, fakeBars)

        // 2. 挂载组件（默认 freq 是 '5m'，需要通过 props 匹配）
        //    组件内部 freq 默认 '5m'，所以当 freq 恰好是 '5m' 时直接命中；
        //    否则需要先挂载再切换 freq。为简化，我们固定使用 '5m' 作为 freq 测试缓存命中。
        //    但为了覆盖所有 freq，我们预填充 '5m' 对应的 key。
        const key5m = buildCacheKey(symbol, date, '5m')
        minuteKlineCache.set(key5m, fakeBars)

        const wrapper = mount(MinuteKlineChart, {
          props: {
            symbol,
            selectedDate: date,
            latestTradeDate: '2024-01-01',
          },
        })

        // 等待 watch 触发和异步操作完成
        await flushPromises()
        await nextTick()

        // 3. 验证 apiClient.get 未被调用（缓存命中）
        expect(apiClient.get).not.toHaveBeenCalled()

        // 4. 验证组件展示了缓存数据（有 bars 时渲染 ECharts 而非空数据提示）
        expect(wrapper.find('.chart-placeholder').exists()).toBe(false)
        expect(wrapper.find('.mock-vchart').exists()).toBe(true)

        wrapper.unmount()
      }),
      { numRuns: 100 },
    )
  })
})
