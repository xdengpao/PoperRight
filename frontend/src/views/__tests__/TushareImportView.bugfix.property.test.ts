/**
 * TushareImportView Bug Condition 探索性属性测试
 *
 * Feature: tushare-import-optimization (bugfix)
 *
 * 使用 fast-check 验证 5 项 UX 缺陷的存在。
 * 这些测试编码了期望行为——在未修复代码上运行时应失败（确认缺陷存在），
 * 修复后运行应通过（确认修复正确性）。
 *
 * **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
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

/** 生成可导入的 API（canImport 条件满足：connected=true, token_available=true, 无需手动输入的必填参数） */
function importableApiArb(overrides?: Partial<ApiItem>): fc.Arbitrary<ApiItem> {
  return fc.record({
    api_name: fc.stringMatching(/^[a-z][a-z0-9_]{2,15}$/),
    label: fc.stringMatching(/^[a-zA-Z0-9\u4e00-\u9fff]{1,10}$/),
    category: fc.constantFrom('stock_data', 'index_data'),
    subcategory: fc.constant('测试分类'),
    token_tier: tokenTierArb,
    required_params: fc.constant([] as string[]),
    optional_params: fc.constant(['date_range'] as string[]),
    token_available: fc.constant(true),
  }).map((item) => ({ ...item, ...overrides }))
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

/** 设置默认 mock 返回值（connected=true） */
function setupDefaultMocks(registryData: ApiItem[] = []) {
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
      return Promise.resolve({ data: [] })
    }
    return Promise.resolve({ data: {} })
  })
}

// ── Bug Condition 探索性测试 ──────────────────────────────────────────────────

describe('Bug Condition: Bug 1 — Loading 状态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Bug 1: 对任意 api where canImport(api)=true，模拟点击"开始导入"按钮，
   * 断言按钮立即进入 loading 状态（disabled=true, 文字变为"导入中..."）。
   *
   * isBugCondition: action=="click_import" AND canImport(api)==true AND button.loading==false
   *
   * 在未修复代码上：按钮点击后无 loading 状态，文字保持"开始导入"，此测试应失败。
   *
   * **Validates: Requirements 1.1**
   */
  it('点击导入按钮后应进入 loading 状态（disabled=true, text="导入中..."）', async () => {
    await fc.assert(
      fc.asyncProperty(
        importableApiArb({ category: 'stock_data', subcategory: '测试分类' }),
        async (api) => {
          setupDefaultMocks([api])

          // 让 POST 请求挂起（模拟网络延迟），这样可以检查 loading 中间状态
          let resolvePost: (value: unknown) => void
          mockPost.mockReturnValue(new Promise((resolve) => { resolvePost = resolve }))

          const wrapper = mount(TushareImportView)
          await flushPromises()

          // 展开子分类
          const headers = wrapper.findAll('.subcategory-header')
          if (headers.length > 0) {
            await headers[0].trigger('click')
            await flushPromises()
          }

          // 找到导入按钮并点击
          const importBtn = wrapper.find('.btn-import')
          expect(importBtn.exists()).toBe(true)

          // 点击前按钮应该是可用的
          expect(importBtn.attributes('disabled')).toBeUndefined()

          await importBtn.trigger('click')
          await flushPromises()

          // 点击后按钮应进入 loading 状态
          const btnAfterClick = wrapper.find('.btn-import')
          expect(btnAfterClick.text()).toBe('导入中...')
          expect(btnAfterClick.attributes('disabled')).toBeDefined()

          // 清理：resolve 挂起的请求
          resolvePost!({ data: { task_id: 'test-task', log_id: 1, status: 'pending' } })
          await flushPromises()

          wrapper.unmount()
        },
      ),
      { numRuns: 10 },
    )
  })
})

describe('Bug Condition: Bug 2 — 日期默认值', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Bug 2: 对任意 api where date_range in required_params or optional_params，
   * 展开子分类后断言 start_date 输入框的值为一年前日期，而非空字符串。
   *
   * isBugCondition: getParam(api.api_name, 'start_date') == ""
   *
   * 在未修复代码上：start_date 输入框 value 为空，此测试应失败。
   *
   * **Validates: Requirements 1.2**
   */
  it('date_range 参数的 start_date 应默认为一年前日期', async () => {
    const oneYearAgo = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10)

    await fc.assert(
      fc.asyncProperty(
        importableApiArb({
          category: 'stock_data',
          subcategory: '测试分类',
          required_params: ['date_range'],
          optional_params: [],
        }),
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

          // 找到 start_date 输入框（第一个 date input，aria-label="开始日期"）
          const startDateInput = wrapper.find('input[aria-label="开始日期"]')
          expect(startDateInput.exists()).toBe(true)

          // start_date 应有默认值（一年前日期），而非空字符串
          const value = (startDateInput.element as HTMLInputElement).value
          expect(value).toBe(oneYearAgo)

          wrapper.unmount()
        },
      ),
      { numRuns: 10 },
    )
  })
})

describe('Bug Condition: Bug 3 — Stock Code 可选', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Bug 3: 构造 required_params 包含 stock_code 的 API，留空 stock_code，
   * 断言"开始导入"按钮不被禁用（requiredParamsFilled(api) 应返回 true）。
   *
   * isBugCondition: "stock_code" IN required_params AND stock_code_value=="" AND requiredParamsFilled(api)==false
   *
   * 在未修复代码上：requiredParamsFilled() 对 stock_code 为空时返回 false，按钮被禁用，此测试应失败。
   *
   * **Validates: Requirements 1.3**
   */
  it('stock_code 在 required_params 中但留空时，导入按钮不应被禁用', async () => {
    await fc.assert(
      fc.asyncProperty(
        importableApiArb({
          category: 'stock_data',
          subcategory: '测试分类',
          required_params: ['stock_code'],
          optional_params: ['date_range'],
        }),
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

          // stock_code 输入框留空（默认就是空）
          const stockCodeInput = wrapper.find('input[placeholder*="留空表示全市场"]')
          expect(stockCodeInput.exists()).toBe(true)
          expect((stockCodeInput.element as HTMLInputElement).value).toBe('')

          // 导入按钮应该不被禁用（stock_code 留空应视为可选）
          const importBtn = wrapper.find('.btn-import')
          expect(importBtn.exists()).toBe(true)
          expect(importBtn.attributes('disabled')).toBeUndefined()

          wrapper.unmount()
        },
      ),
      { numRuns: 10 },
    )
  })
})

describe('Bug Condition: Bug 4 — 批量选择', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Bug 4: 检查子分类中是否存在 checkbox 和"批量导入已选"按钮。
   *
   * isBugCondition: selectedApis.length > 1 AND NO batchImport mechanism exists
   *
   * 在未修复代码上：无 checkbox 元素，无"批量导入已选"按钮，此测试应失败。
   *
   * **Validates: Requirements 1.4**
   */
  it('子分类中应存在 checkbox 和批量导入按钮', async () => {
    // 生成同一子分类下 2-4 个 API
    const apisArb = fc.array(
      importableApiArb({ category: 'stock_data', subcategory: '测试分类' }),
      { minLength: 2, maxLength: 4 },
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

        // 应存在 checkbox（每个 API 一个）
        const checkboxes = wrapper.findAll('input[type="checkbox"]')
        expect(checkboxes.length).toBeGreaterThanOrEqual(apis.length)

        // 应存在"批量导入"相关按钮
        const html = wrapper.text()
        expect(html).toContain('批量导入')

        wrapper.unmount()
      }),
      { numRuns: 10 },
    )
  })
})
