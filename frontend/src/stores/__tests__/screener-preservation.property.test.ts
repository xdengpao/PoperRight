/**
 * 属性 2：Preservation — 非 running 功能的现有 store 行为保持不变
 *
 * 在未修复代码上验证 screener store 的基线行为，确保后续修复不会引入回归。
 *
 * - P2a: 对于任意 ScreenItem 数组，fetchResults() 将其存入 results 并设置 lastUpdated 为 Date
 * - P2b: 对于任意 StrategyTemplate 数组，fetchStrategies() 将其存入 strategies
 * - P2c: 新建 store 的初始状态始终为 results=[], strategies=[], loading=false, lastUpdated=null
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'
import type { ScreenItem, StrategyTemplate } from '@/stores/screener'

// Mock router（apiClient 响应拦截器中引用了 router）
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener' } },
  },
}))

// Mock apiClient
const mockGet = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn(),
  },
}))

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const riskLevelArb = fc.constantFrom('LOW' as const, 'MEDIUM' as const, 'HIGH' as const)

/** 生成合法的 ScreenItem 对象 */
const screenItemArb: fc.Arbitrary<ScreenItem> = fc.record({
  symbol: fc.stringMatching(/^[0-9]{6}$/),
  name: fc.string({ minLength: 1, maxLength: 20 }),
  ref_buy_price: fc.double({ min: 0.01, max: 10000, noNaN: true, noDefaultInfinity: true }),
  trend_score: fc.double({ min: -100, max: 100, noNaN: true, noDefaultInfinity: true }),
  risk_level: riskLevelArb,
  signals: fc.dictionary(
    fc.string({ minLength: 1, maxLength: 10 }),
    fc.oneof(fc.boolean(), fc.integer(), fc.string({ maxLength: 20 })),
  ) as fc.Arbitrary<Record<string, unknown>>,
})

/** 生成合法的 StrategyTemplate 对象 */
const strategyTemplateArb: fc.Arbitrary<StrategyTemplate> = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  config: fc.dictionary(
    fc.string({ minLength: 1, maxLength: 10 }),
    fc.oneof(fc.boolean(), fc.integer(), fc.string({ maxLength: 20 })),
  ) as fc.Arbitrary<Record<string, unknown>>,
  is_active: fc.boolean(),
  created_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-01-01') })
    .map((d) => d.toISOString()),
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 2：Preservation — 现有 store 行为保持不变', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  /**
   * P2a: 对于任意 ScreenItem 数组，fetchResults() 将其存入 results 并设置 lastUpdated 为 Date
   * Validates: Requirements 3.1, 3.5
   */
  it('P2a: fetchResults() 将任意 ScreenItem 数组存入 results 并设置 lastUpdated', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(screenItemArb, { minLength: 0, maxLength: 20 }),
        async (items) => {
          // 每次迭代创建隔离的 pinia 实例
          setActivePinia(createPinia())

          mockGet.mockResolvedValueOnce({ data: items })

          const { useScreenerStore } = await import('@/stores/screener')
          const store = useScreenerStore()

          const beforeFetch = new Date()
          await store.fetchResults()
          const afterFetch = new Date()

          // results 应与 API 返回的数据一致
          expect(store.results).toEqual(items)
          expect(store.results.length).toBe(items.length)

          // lastUpdated 应为 Date 实例，且在 fetchResults 调用前后的时间范围内
          expect(store.lastUpdated).toBeInstanceOf(Date)
          expect(store.lastUpdated!.getTime()).toBeGreaterThanOrEqual(beforeFetch.getTime())
          expect(store.lastUpdated!.getTime()).toBeLessThanOrEqual(afterFetch.getTime())

          // loading 应在完成后恢复为 false
          expect(store.loading).toBe(false)

          // 验证 apiClient.get 被正确调用
          expect(mockGet).toHaveBeenCalledWith('/screen/results')
        },
      ),
      { numRuns: 50 },
    )
  })

  /**
   * P2b: 对于任意 StrategyTemplate 数组，fetchStrategies() 将其存入 strategies
   * Validates: Requirements 3.2, 3.5
   */
  it('P2b: fetchStrategies() 将任意 StrategyTemplate 数组存入 strategies', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(strategyTemplateArb, { minLength: 0, maxLength: 20 }),
        async (templates) => {
          // 每次迭代创建隔离的 pinia 实例
          setActivePinia(createPinia())

          mockGet.mockResolvedValueOnce({ data: templates })

          const { useScreenerStore } = await import('@/stores/screener')
          const store = useScreenerStore()

          await store.fetchStrategies()

          // strategies 应与 API 返回的数据一致
          expect(store.strategies).toEqual(templates)
          expect(store.strategies.length).toBe(templates.length)

          // 验证 apiClient.get 被正确调用
          expect(mockGet).toHaveBeenCalledWith('/strategies')
        },
      ),
      { numRuns: 50 },
    )
  })

  /**
   * P2c: 新建 store 的初始状态始终为 results=[], strategies=[], loading=false, lastUpdated=null
   * Validates: Requirements 3.3, 3.5
   */
  it('P2c: 新建 store 初始状态为 results=[], strategies=[], loading=false, lastUpdated=null', async () => {
    // 此属性无需生成输入，但我们多次创建 store 实例以验证不变量
    for (let i = 0; i < 20; i++) {
      setActivePinia(createPinia())

      const { useScreenerStore } = await import('@/stores/screener')
      const store = useScreenerStore()

      expect(store.results).toEqual([])
      expect(store.strategies).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.lastUpdated).toBeNull()
    }
  })
})
