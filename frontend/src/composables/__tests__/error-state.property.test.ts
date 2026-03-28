/**
 * 属性 38：API 错误状态管理正确性
 *
 * 验证失败请求后 loading→error 状态转换、error 包含非空提示、重试后重新进入 loading
 *
 * **Validates: Requirements 21.17**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { usePageState } from '@/composables/usePageState'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 非空错误消息（去除纯空白） */
const errorMessageArb = fc.string({ minLength: 1, maxLength: 200 }).filter(
  (s) => s.trim().length > 0,
)

/** 任意非 Error 类型的 throw 值 */
const nonErrorThrowArb = fc.oneof(
  fc.integer(),
  fc.boolean(),
  fc.constant(null),
  fc.constant(undefined),
)

/** 任意成功返回值 */
const successDataArb = fc.oneof(
  fc.string(),
  fc.integer(),
  fc.record({ id: fc.integer(), name: fc.string() }),
  fc.array(fc.integer()),
)

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 38：API 错误状态管理正确性', () => {
  /**
   * 属性 38a：失败的 API 请求后，状态应为 loading=false, error=非空字符串, data=null
   * Validates: Requirements 21.17
   */
  it('失败请求后状态转为 error，error 包含非空提示信息', async () => {
    await fc.assert(
      fc.asyncProperty(errorMessageArb, async (msg) => {
        const { state, execute } = usePageState<string>()

        await execute(() => Promise.reject(new Error(msg)))

        expect(state.loading).toBe(false)
        expect(state.error).not.toBeNull()
        expect(typeof state.error).toBe('string')
        expect(state.error!.length).toBeGreaterThan(0)
        expect(state.data).toBeNull()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 38b：成功的 API 请求后，状态应为 loading=false, error=null, data=结果
   * Validates: Requirements 21.17
   */
  it('成功请求后状态转为 data，error 为 null', async () => {
    await fc.assert(
      fc.asyncProperty(successDataArb, async (data) => {
        const { state, execute } = usePageState<unknown>()

        await execute(() => Promise.resolve(data))

        expect(state.loading).toBe(false)
        expect(state.error).toBeNull()
        expect(state.data).toEqual(data)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 38c：重试（再次调用 execute）后状态重新进入 loading
   * Validates: Requirements 21.17
   */
  it('重试后状态重新进入 loading', async () => {
    await fc.assert(
      fc.asyncProperty(errorMessageArb, async (msg) => {
        const { state, execute } = usePageState<string>()

        // 第一次请求失败
        await execute(() => Promise.reject(new Error(msg)))
        expect(state.loading).toBe(false)
        expect(state.error).not.toBeNull()

        // 重试：在 execute 内部 loading 应为 true
        let loadingDuringRetry = false
        await execute(() => {
          // 在异步函数执行时捕获 loading 状态
          loadingDuringRetry = state.loading
          return Promise.resolve('success')
        })

        expect(loadingDuringRetry).toBe(true)
        expect(state.loading).toBe(false)
        expect(state.error).toBeNull()
        expect(state.data).toBe('success')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 38d：Error 实例的 message 被保留到 state.error
   * Validates: Requirements 21.17
   */
  it('Error 实例的 message 被保留到 state.error', async () => {
    await fc.assert(
      fc.asyncProperty(errorMessageArb, async (msg) => {
        const { state, execute } = usePageState<string>()

        await execute(() => Promise.reject(new Error(msg)))

        expect(state.error).toBe(msg)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 38e：非 Error 类型的 throw 产生回退消息 '请求失败，请重试'
   * Validates: Requirements 21.17
   */
  it('非 Error 类型的 throw 产生回退消息', async () => {
    await fc.assert(
      fc.asyncProperty(nonErrorThrowArb, async (throwValue) => {
        const { state, execute } = usePageState<string>()

        await execute(() => Promise.reject(throwValue))

        expect(state.error).toBe('请求失败，请重试')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 38f：execute 调用期间 error 被重置为 null
   * Validates: Requirements 21.17
   */
  it('重试时 error 被重置为 null（在新请求开始时）', async () => {
    await fc.assert(
      fc.asyncProperty(errorMessageArb, async (msg) => {
        const { state, execute } = usePageState<string>()

        // 第一次请求失败
        await execute(() => Promise.reject(new Error(msg)))
        expect(state.error).not.toBeNull()

        // 重试时检查 error 是否被重置
        let errorDuringRetry: string | null = 'NOT_CHECKED'
        await execute(() => {
          errorDuringRetry = state.error
          return Promise.resolve('ok')
        })

        expect(errorDuringRetry).toBeNull()
      }),
      { numRuns: 100 },
    )
  })
})
