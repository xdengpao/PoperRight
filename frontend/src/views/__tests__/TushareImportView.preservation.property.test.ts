/**
 * TushareImportView Preservation 属性测试
 *
 * Feature: tushare-import-optimization (bugfix)
 *
 * Property 2: Preservation — 非 Bug 输入行为保持不变
 *
 * 这些测试在未修复代码上运行并通过，建立基线行为。
 * 修复后重新运行以确认无回归。
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { mount, flushPromises } from '@vue/test-utils'
import TushareImportView from '../TushareImportView.vue'
import type { ApiItem } from '../TushareImportView.vue'

// ── Mock apiClient ────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

// ── 生成器 ────────────────────────────────────────────────────────────────────

/** 生成合法的 token_tier */
const tokenTierArb = fc.constantFrom('basic', 'advanced', 'special')

/** 非 stock_code 的需要用户手动输入的必填参数 */
const nonStockCodeRequiredParams = ['hs_type', 'sector_code', 'index_code'] as const

/** 生成至少包含一个非 stock_code 必填参数的 API */
function apiWithNonStockCodeRequiredArb(): fc.Arbitrary<{ api: ApiItem; emptyParam: string }> {
  return fc.constantFrom(...nonStockCodeRequiredParams).chain((param) =>
    fc.record({
      api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
      label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
      category: fc.constantFrom('stock_data', 'index_data') as fc.Arbitrary<string>,
      subcategory: fc.constant('测试分类'),
      token_tier: tokenTierArb,
      required_params: fc.constant([param] as string[]),
      optional_params: fc.constant([] as string[]),
      token_available: fc.constant(true),
    }).map((item) => ({ api: item, emptyParam: param })),
  )
}

/** 生成 canImport 条件不满足的 API（connected=false 或 token_available=false） */
function nonImportableApiArb(): fc.Arbitrary<ApiItem> {
  return fc.record({
    api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
    label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
    category: fc.constant('stock_data' as string),
    subcategory: fc.constant('测试分类'),
    token_tier: tokenTierArb,
    required_params: fc.constant([] as string[]),
    optional_params: fc.constant([] as string[]),
    token_available: fc.boolean(),
  })
}

/** 生成包含 date_range 参数的 API */
function apiWithDateRangeArb(): fc.Arbitrary<ApiItem> {
  return fc.record({
    api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
    label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
    category: fc.constant('stock_data' as string),
    subcategory: fc.constant('测试分类'),
    token_tier: tokenTierArb,
    required_params: fc.constant([] as string[]),
    optional_params: fc.constant(['date_range'] as string[]),
    token_available: fc.constant(true),
  })
}

/** 生成包含 report_period 和/或 freq 参数的 API */
function apiWithNonDateParamsArb(): fc.Arbitrary<ApiItem> {
  return fc.record({
    api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
    label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
    category: fc.constant('stock_data' as string),
    subcategory: fc.constant('测试分类'),
    token_tier: tokenTierArb,
    required_params: fc.constant([] as string[]),
    optional_params: fc.constantFrom(
      ['report_period'],
      ['freq'],
      ['report_period', 'freq'],
    ) as fc.Arbitrary<string[]>,
    token_available: fc.constant(true),
  })
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

/** 设置 mock 返回值 */
function setupMocks(
  registryData: ApiItem[] = [],
  options?: { connected?: boolean },
) {
  const connected = options?.connected ?? true
  mockGet.mockImplementation((url: string) => {
    if (url === '/data/tushare/health') {
      return Promise.resolve({
        data: {
          connected,
          tokens: {
            basic: { configured: true },
            advanced: { configured: true },
            special: { configured: true },
          },
        },
      })
    }
    if (url === '/data/tushare/registry') {
      return Promise.resolve({ data: registryData })
    }
    if (url.startsWith('/data/tushare/import/history')) {
      return Promise.resolve({ data: [] })
    }
    return Promise.resolve({ data: {} })
  })
}

// ── Preservation 属性测试 ────────────────────────────────────────────────────

describe('Preservation: 非 stock_code 必填参数校验保持', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 API 和任意非 stock_code 必填参数（hs_type, sector_code, index_code）为空时，
   * requiredParamsFilled(api) 返回 false，导入按钮保持禁用。
   *
   * 此行为在修复前后都应保持不变。
   *
   * **Validates: Requirements 3.1, 3.2**
   */
  it('非 stock_code 必填参数为空时导入按钮禁用', async () => {
    await fc.assert(
      fc.asyncProperty(apiWithNonStockCodeRequiredArb(), async ({ api, emptyParam }) => {
        setupMocks([api])
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        // 不填写任何参数（emptyParam 保持空值）
        // 导入按钮应被禁用
        const importBtn = wrapper.find('.btn-import')
        expect(importBtn.exists()).toBe(true)
        expect(importBtn.attributes('disabled')).toBeDefined()

        wrapper.unmount()
      }),
      { numRuns: 20 },
    )
  })
})

describe('Preservation: canImport 在连接/Token 不可用时返回 false', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 API，当 health.connected=false 时，canImport(api) 返回 false，
   * 导入按钮保持禁用。
   *
   * **Validates: Requirements 3.1**
   */
  it('health.connected=false 时导入按钮禁用', async () => {
    await fc.assert(
      fc.asyncProperty(nonImportableApiArb(), async (api) => {
        setupMocks([api], { connected: false })
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        // 导入按钮应被禁用
        const importBtn = wrapper.find('.btn-import')
        expect(importBtn.exists()).toBe(true)
        expect(importBtn.attributes('disabled')).toBeDefined()

        wrapper.unmount()
      }),
      { numRuns: 15 },
    )
  })

  /**
   * 对任意 API where token_available=false，canImport(api) 返回 false，
   * 导入按钮保持禁用。
   *
   * **Validates: Requirements 3.1**
   */
  it('token_available=false 时导入按钮禁用', async () => {
    const tokenUnavailableApiArb = fc.record({
      api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
      label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
      category: fc.constant('stock_data' as string),
      subcategory: fc.constant('测试分类'),
      token_tier: tokenTierArb,
      required_params: fc.constant([] as string[]),
      optional_params: fc.constant([] as string[]),
      token_available: fc.constant(false),
    })

    await fc.assert(
      fc.asyncProperty(tokenUnavailableApiArb, async (api) => {
        setupMocks([api], { connected: true })
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        // 导入按钮应被禁用
        const importBtn = wrapper.find('.btn-import')
        expect(importBtn.exists()).toBe(true)
        expect(importBtn.attributes('disabled')).toBeDefined()

        wrapper.unmount()
      }),
      { numRuns: 15 },
    )
  })
})

describe('Preservation: end_date 默认值为今天', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意包含 date_range 参数的 API，end_date 输入框默认值为今天日期。
   *
   * **Validates: Requirements 3.7**
   */
  it('end_date 默认值为 todayStr', async () => {
    const todayStr = new Date().toISOString().slice(0, 10)

    await fc.assert(
      fc.asyncProperty(apiWithDateRangeArb(), async (api) => {
        setupMocks([api])
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        // 找到 end_date 输入框（aria-label="结束日期"）
        const endDateInput = wrapper.find('input[aria-label="结束日期"]')
        expect(endDateInput.exists()).toBe(true)

        const value = (endDateInput.element as HTMLInputElement).value
        expect(value).toBe(todayStr)

        wrapper.unmount()
      }),
      { numRuns: 15 },
    )
  })
})

describe('Preservation: buildImportParams 非 date_range 参数默认值', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意包含 report_period 参数的 API，report_year 默认为当前年份，
   * report_quarter 默认为 '1'。
   * 对任意包含 freq 参数的 API，freq 默认为 '1min'。
   *
   * 通过检查 select 元素的默认值来验证 buildImportParams 的行为。
   *
   * **Validates: Requirements 3.3, 3.4, 3.5**
   */
  it('report_period 默认 year=currentYear/quarter="1"，freq 默认 "1min"', async () => {
    const currentYear = new Date().getFullYear().toString()

    await fc.assert(
      fc.asyncProperty(apiWithNonDateParamsArb(), async (api) => {
        setupMocks([api])
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        const allParams = [...api.required_params, ...api.optional_params]

        if (allParams.includes('report_period')) {
          // 检查报告期 select 的默认值
          const selects = wrapper.findAll('.report-period-inputs select')
          expect(selects.length).toBe(2)

          // 年份 select 默认值
          const yearSelect = selects[0].element as HTMLSelectElement
          expect(yearSelect.value).toBe(currentYear)

          // 季度 select 默认值
          const quarterSelect = selects[1].element as HTMLSelectElement
          expect(quarterSelect.value).toBe('1')
        }

        if (allParams.includes('freq')) {
          // 检查频率 select 的默认值
          const freqSelects = wrapper.findAll('.param-field select')
          // 找到频率 select（通过检查 option 值）
          let freqSelect: HTMLSelectElement | null = null
          for (const sel of freqSelects) {
            const options = (sel.element as HTMLSelectElement).options
            for (let i = 0; i < options.length; i++) {
              if (options[i].value === '1min') {
                freqSelect = sel.element as HTMLSelectElement
                break
              }
            }
            if (freqSelect) break
          }
          expect(freqSelect).not.toBeNull()
          expect(freqSelect!.value).toBe('1min')
        }

        wrapper.unmount()
      }),
      { numRuns: 15 },
    )
  })
})
