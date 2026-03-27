/**
 * 属性 32：登录响应正确性
 *
 * 验证有效凭证返回 token 和用户对象，无效凭证返回错误且不返回 token
 *
 * **Validates: Requirements 21.1**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'

// 模拟 router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/dashboard' } },
  },
}))

// 模拟 wsClient
vi.mock('@/services/wsClient', () => ({
  wsClient: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onMessage: vi.fn(),
    offMessage: vi.fn(),
    reconnect: vi.fn(),
  },
}))

// 模拟 apiClient
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: vi.fn(),
  },
}))

type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface LoginResponse {
  access_token: string
  user: { id: string; username: string; role: UserRole }
}

// 生成有效的 UserRole
const userRoleArb = fc.constantFrom<UserRole>('TRADER', 'ADMIN', 'READONLY')

// 生成非空字符串（用于 username/password）
const nonEmptyStringArb = fc.string({ minLength: 1, maxLength: 50 }).filter(
  (s) => s.trim().length > 0,
)

// 生成有效的 LoginResponse
const loginResponseArb: fc.Arbitrary<LoginResponse> = fc.record({
  access_token: fc.string({ minLength: 1, maxLength: 256 }).filter((s) => s.trim().length > 0),
  user: fc.record({
    id: fc.uuid(),
    username: nonEmptyStringArb,
    role: userRoleArb,
  }),
})

describe('属性 32：登录响应正确性', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    vi.clearAllMocks()
  })

  it('有效凭证：返回的 access_token 为非空字符串', async () => {
    await fc.assert(
      fc.asyncProperty(
        nonEmptyStringArb,
        nonEmptyStringArb,
        loginResponseArb,
        async (username, password, mockResponse) => {
          mockPost.mockResolvedValueOnce({ data: mockResponse })

          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()
          await store.login(username, password)

          // access_token 应为非空字符串
          expect(typeof store.token).toBe('string')
          expect((store.token as string).length).toBeGreaterThan(0)
        },
      ),
      { numRuns: 50 },
    )
  })

  it('有效凭证：返回的用户对象包含 id、username、role 字段', async () => {
    await fc.assert(
      fc.asyncProperty(
        nonEmptyStringArb,
        nonEmptyStringArb,
        loginResponseArb,
        async (username, password, mockResponse) => {
          mockPost.mockResolvedValueOnce({ data: mockResponse })

          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()
          await store.login(username, password)

          // user 对象应存在且包含必要字段
          expect(store.user).not.toBeNull()
          expect(typeof store.user!.id).toBe('string')
          expect(store.user!.id.length).toBeGreaterThan(0)
          expect(typeof store.user!.username).toBe('string')
          expect(store.user!.username.length).toBeGreaterThan(0)
          expect(['TRADER', 'ADMIN', 'READONLY']).toContain(store.user!.role)
        },
      ),
      { numRuns: 50 },
    )
  })

  it('有效凭证：token 与响应中的 access_token 一致', async () => {
    await fc.assert(
      fc.asyncProperty(
        nonEmptyStringArb,
        nonEmptyStringArb,
        loginResponseArb,
        async (username, password, mockResponse) => {
          mockPost.mockResolvedValueOnce({ data: mockResponse })

          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()
          await store.login(username, password)

          expect(store.token).toBe(mockResponse.access_token)
          expect(store.user).toEqual(mockResponse.user)
        },
      ),
      { numRuns: 50 },
    )
  })

  it('无效凭证（401）：抛出错误且不存储 token', async () => {
    await fc.assert(
      fc.asyncProperty(
        nonEmptyStringArb,
        nonEmptyStringArb,
        async (username, password) => {
          mockPost.mockRejectedValueOnce(new Error('登录已过期，请重新登录'))

          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()

          await expect(store.login(username, password)).rejects.toThrow()

          // 登录失败时不应存储 token
          expect(store.token).toBeNull()
          expect(store.user).toBeNull()
          expect(localStorage.getItem('access_token')).toBeNull()
        },
      ),
      { numRuns: 50 },
    )
  })

  it('无效凭证：isAuthenticated 应为 false', async () => {
    await fc.assert(
      fc.asyncProperty(
        nonEmptyStringArb,
        nonEmptyStringArb,
        async (username, password) => {
          mockPost.mockRejectedValueOnce(new Error('用户名或密码错误'))

          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()

          try {
            await store.login(username, password)
          } catch {
            // 预期抛出错误
          }

          expect(store.isAuthenticated).toBe(false)
        },
      ),
      { numRuns: 50 },
    )
  })
})
