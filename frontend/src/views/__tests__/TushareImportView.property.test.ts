/**
 * TushareImportView 前端属性测试
 *
 * Feature: tushare-data-import
 *
 * 使用 fast-check 对 TushareImportView 的核心渲染逻辑进行属性测试，
 * 验证动态表单参数渲染、必填参数校验、Token 禁用、注册表驱动列表渲染
 * 和导入历史字段完整性。
 *
 * **Validates: Requirements 23.1-23.4, 22a.6, 2.5, 2.6, 24.2**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { mount, flushPromises } from '@vue/test-utils'
import TushareImportView from '../TushareImportView.vue'
import type { ApiItem, ImportLog } from '../TushareImportView.vue'

// ── Mock apiClient ────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

// ── 参数类型常量 ──────────────────────────────────────────────────────────────

const ALL_PARAM_TYPES = [
  'date_range', 'stock_code', 'index_code', 'market',
  'report_period', 'freq', 'hs_type', 'sector_code',
] as const

// ── 生成器 ────────────────────────────────────────────────────────────────────

/** 生成合法的参数类型子集 */
const paramSubsetArb = fc.subarray([...ALL_PARAM_TYPES], { minLength: 0 })

/** 生成合法的 token_tier */
const tokenTierArb = fc.constantFrom('basic', 'advanced', 'special')

/** 生成安全的 ASCII 标签（避免 HTML 转义问题） */
const safeLabelArb = fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/)

/** 生成合法的 ApiItem */
function apiItemArb(overrides?: Partial<ApiItem>): fc.Arbitrary<ApiItem> {
  return fc.record({
    api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
    label: safeLabelArb,
    category: fc.constantFrom('stock_data', 'index_data'),
    subcategory: fc.constant('测试分类'),
    token_tier: tokenTierArb,
    required_params: paramSubsetArb,
    optional_params: paramSubsetArb,
    token_available: fc.boolean(),
  }).map((item) => ({ ...item, ...overrides }))
}

/** 生成合法的 ImportLog */
const importLogArb: fc.Arbitrary<ImportLog> = fc.record({
  id: fc.integer({ min: 1, max: 100000 }),
  api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
  status: fc.constantFrom('completed', 'failed', 'stopped', 'running'),
  record_count: fc.integer({ min: 0, max: 1000000 }),
  error_message: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: null }),
  started_at: fc.constant('2024-06-15T10:30:00'),
  finished_at: fc.option(fc.constant('2024-06-15T10:35:00'), { nil: null }),
})

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

/** 设置默认 mock 返回值 */
function setupDefaultMocks(registryData: ApiItem[] = [], historyData: ImportLog[] = []) {
  mockGet.mockImplementation((url: string) => {
    if (url === '/data/tushare/health') {
      return Promise.resolve({
        data: {
          connected: true,
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
      return Promise.resolve({ data: historyData })
    }
    return Promise.resolve({ data: {} })
  })
}

// ── 属性测试 ──────────────────────────────────────────────────────────────────

describe('Feature: tushare-data-import, Property 9: 动态表单参数渲染', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 required_params/optional_params 组合，展开子分类后
   * 应渲染对应的 UI 控件。
   *
   * **Validates: Requirements 23.1, 23.2, 23.3**
   */
  it('根据 required_params 和 optional_params 渲染对应 UI 控件', async () => {
    await fc.assert(
      fc.asyncProperty(
        apiItemArb({ category: 'stock_data', subcategory: '测试分类', token_available: true }),
        async (api) => {
          setupDefaultMocks([api])
          const wrapper = mount(TushareImportView)
          await flushPromises()

          // 展开子分类
          const headers = wrapper.findAll('.subcategory-header')
          if (headers.length > 0) {
            await headers[0].trigger('click')
            await flushPromises()
          }

          const html = wrapper.html()
          const allParams = [...new Set([...api.required_params, ...api.optional_params])]

          for (const p of allParams) {
            switch (p) {
              case 'date_range':
                expect(wrapper.findAll('input[type="date"]').length).toBeGreaterThanOrEqual(2)
                break
              case 'stock_code':
                expect(html).toContain('股票代码')
                break
              case 'index_code':
                expect(html).toContain('指数代码')
                break
              case 'market':
                expect(html).toContain('市场')
                break
              case 'report_period':
                expect(html).toContain('报告期')
                break
              case 'freq':
                expect(html).toContain('频率')
                break
              case 'hs_type':
                expect(html).toContain('类型')
                break
              case 'sector_code':
                expect(html).toContain('板块代码')
                break
            }
          }

          wrapper.unmount()
        },
      ),
      { numRuns: 30 },
    )
  })
})

describe('Feature: tushare-data-import, Property 10: 必填参数校验', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 required_params 列表（含需要用户输入的参数），
   * 若用户未填写，导入按钮应处于禁用状态。
   *
   * **Validates: Requirements 23.4**
   */
  it('必填参数未填写时导入按钮禁用', async () => {
    // 只测试需要用户手动输入的必填参数类型
    const userInputParams = ['stock_code', 'index_code', 'hs_type', 'sector_code'] as const
    const requiredParamArb = fc.subarray([...userInputParams], { minLength: 1 })

    await fc.assert(
      fc.asyncProperty(requiredParamArb, async (requiredParams) => {
        const api: ApiItem = {
          api_name: 'test_api',
          label: '测试接口',
          category: 'stock_data',
          subcategory: '测试分类',
          token_tier: 'basic',
          required_params: requiredParams as string[],
          optional_params: [],
          token_available: true,
        }

        setupDefaultMocks([api])
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        // 未填写任何参数时，导入按钮应禁用
        const importBtn = wrapper.find('.btn-import')
        expect(importBtn.exists()).toBe(true)
        expect(importBtn.attributes('disabled')).toBeDefined()

        wrapper.unmount()
      }),
      { numRuns: 20 },
    )
  })
})

describe('Feature: tushare-data-import, Property 11: Token 不可用时禁用导入', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 ApiItem，若 token_available=false，导入按钮应禁用。
   *
   * **Validates: Requirements 22a.6**
   */
  it('token_available=false 时导入按钮禁用', async () => {
    await fc.assert(
      fc.asyncProperty(
        apiItemArb({ token_available: false, category: 'stock_data', subcategory: '测试分类' }),
        async (api) => {
          setupDefaultMocks([api])
          const wrapper = mount(TushareImportView)
          await flushPromises()

          // 展开子分类
          const headers = wrapper.findAll('.subcategory-header')
          if (headers.length > 0) {
            await headers[0].trigger('click')
            await flushPromises()
          }

          // 导入按钮应禁用
          const importBtn = wrapper.find('.btn-import')
          expect(importBtn.exists()).toBe(true)
          expect(importBtn.attributes('disabled')).toBeDefined()

          wrapper.unmount()
        },
      ),
      { numRuns: 20 },
    )
  })
})

describe('Feature: tushare-data-import, Property 12: 注册表驱动的接口列表渲染', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 registry 响应，展开子分类后显示的 API 列表应与数据一致，
   * 每个条目同时显示 api_name 和 label。
   *
   * **Validates: Requirements 2.5, 2.6**
   */
  it('子分类展开后显示正确的 API 列表', async () => {
    // 生成同一子分类下 1-5 个 API（使用安全标签）
    const apisArb = fc.array(
      apiItemArb({ category: 'stock_data', subcategory: '属性测试分类' }),
      { minLength: 1, maxLength: 5 },
    )

    await fc.assert(
      fc.asyncProperty(apisArb, async (apis) => {
        setupDefaultMocks(apis)
        const wrapper = mount(TushareImportView)
        await flushPromises()

        // 展开子分类
        const headers = wrapper.findAll('.subcategory-header')
        if (headers.length > 0) {
          await headers[0].trigger('click')
          await flushPromises()
        }

        const text = wrapper.text()

        // 验证每个 API 的 api_name 和 label 都显示
        for (const api of apis) {
          expect(text).toContain(api.api_name)
          expect(text).toContain(api.label)
        }

        wrapper.unmount()
      }),
      { numRuns: 20 },
    )
  })
})

describe('Feature: tushare-data-import, Property 13: 导入历史记录字段完整性', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 对任意 ImportLog 记录，渲染的历史行应包含 api_name、started_at（格式化后）、
   * record_count、status 对应的状态标签。
   *
   * **Validates: Requirements 24.2**
   */
  it('历史记录行包含所有必要字段', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(importLogArb, { minLength: 1, maxLength: 5 }),
        async (logs) => {
          setupDefaultMocks([], logs)
          const wrapper = mount(TushareImportView)
          await flushPromises()

          const text = wrapper.text()

          for (const log of logs) {
            // api_name 显示
            expect(text).toContain(log.api_name)
            // record_count 显示（toLocaleString 格式）
            expect(text).toContain(String(log.record_count.toLocaleString()))
            // 状态标签存在
            expect(wrapper.findAll('.status-badge').length).toBeGreaterThanOrEqual(1)
          }

          // 表头包含必要列
          expect(text).toContain('接口名称')
          expect(text).toContain('导入时间')
          expect(text).toContain('数据量')
          expect(text).toContain('状态')
          expect(text).toContain('耗时')

          wrapper.unmount()
        },
      ),
      { numRuns: 20 },
    )
  })
})