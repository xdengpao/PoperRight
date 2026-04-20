/**
 * 属性 1：Bug Condition — Store 缺少 `running` 状态导致导航后为 undefined
 *
 * 验证 screener store 暴露 `running`、`runError` 状态和 `runScreen` action。
 * 对于任意非空 strategyId，调用 `runScreen` 后 `running` 应为 `true`（boolean，非 undefined）。
 *
 * 在未修复代码上：store 没有 `running` 字段，`runScreen` 不存在，测试将失败 — 这证实了 bug 的存在。
 *
 * **Validates: Requirements 1.1, 1.2, 2.1, 2.2**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'

// Mock router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener' } },
  },
}))

// Mock apiClient — post 返回延迟 promise，以便在飞行中观察 running 状态
const mockPost = vi.fn()
const mockGet = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

describe('属性 1：Bug Condition — running 状态在 store 中缺失', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('对于任意 strategyId，runScreen 应存在且调用后 running 为 true', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
        async (strategyId) => {
          // 每次迭代创建隔离的 pinia 实例
          setActivePinia(createPinia())

          // Mock apiClient.post 返回一个延迟 promise，使 running 可在飞行中被观察
          let resolvePost!: (value: unknown) => void
          mockPost.mockReturnValueOnce(
            new Promise((resolve) => {
              resolvePost = resolve
            }),
          )

          const { useScreenerStore } = await import('@/stores/screener')
          const screenerStore = useScreenerStore()

          // 断言 runScreen action 存在（非 undefined）
          expect(typeof screenerStore.runScreen).toBe('function')

          // 调用 runScreen（不 await，因为我们要观察飞行中的状态）
          const runPromise = screenerStore.runScreen({ strategyId })

          // 断言 running 状态为 true（boolean，非 undefined）
          expect(screenerStore.running).toBe(true)

          // 清理：resolve promise 以避免悬挂
          resolvePost({ data: { success: true } })
          await runPromise.catch(() => {})
        },
      ),
      { numRuns: 20 },
    )
  })

  it('store 初始状态应包含 running（boolean）和 runError（string）', async () => {
    const { useScreenerStore } = await import('@/stores/screener')
    const screenerStore = useScreenerStore()

    // running 应为 boolean false，而非 undefined
    expect(screenerStore.running).not.toBeUndefined()
    expect(typeof screenerStore.running).toBe('boolean')
    expect(screenerStore.running).toBe(false)

    // runError 应为 string ''，而非 undefined
    expect(screenerStore.runError).not.toBeUndefined()
    expect(typeof screenerStore.runError).toBe('string')
    expect(screenerStore.runError).toBe('')
  })
})
