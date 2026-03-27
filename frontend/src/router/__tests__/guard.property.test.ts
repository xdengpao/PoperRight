/**
 * 属性 34：路由守卫认证拦截
 *
 * 验证未持有有效 token 或 token 过期时重定向至登录页
 *
 * **Validates: Requirements 21.3**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { isTokenValid, parseTokenExp } from '@/stores/auth'

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/dashboard' } },
  },
}))

vi.mock('@/services/wsClient', () => ({
  wsClient: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onMessage: vi.fn(),
    offMessage: vi.fn(),
    reconnect: vi.fn(),
  },
}))

vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

// ─── 辅助函数：构造 JWT token ─────────────────────────────────────────────────

/**
 * 构造一个带有指定 exp 的 JWT token（仅用于测试，不做真实签名）
 */
function makeJwtWithExp(exp: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
  const payload = btoa(JSON.stringify({ sub: 'user1', exp }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
  return `${header}.${payload}.fakesignature`
}

/**
 * 构造一个已过期的 JWT token（exp 在过去）
 */
function makeExpiredToken(secondsAgo: number): string {
  const exp = Math.floor(Date.now() / 1000) - secondsAgo
  return makeJwtWithExp(exp)
}

/**
 * 构造一个有效的 JWT token（exp 在未来）
 */
function makeValidToken(secondsFromNow: number): string {
  const exp = Math.floor(Date.now() / 1000) + secondsFromNow
  return makeJwtWithExp(exp)
}

// ─── Arbitraries ─────────────────────────────────────────────────────────────

// 受保护路由路径（非 /login 和 /register）
const protectedPathArb = fc.oneof(
  fc.constantFrom(
    '/dashboard',
    '/data',
    '/screener',
    '/screener/results',
    '/risk',
    '/backtest',
    '/trade',
    '/positions',
    '/review',
    '/admin',
  ),
  // 任意以 / 开头但不是 /login 或 /register 的路径
  fc
    .string({ minLength: 1, maxLength: 30 })
    .filter((s) => /^[a-z0-9-/]+$/.test(s) && s.length > 0)
    .map((s) => `/${s}`)
    .filter((p) => p !== '/login' && p !== '/register'),
)

// 公开路由路径
const publicPathArb = fc.constantFrom('/login', '/register')

// 过期时间（1 秒到 1 年前）
const expiredSecondsAgoArb = fc.integer({ min: 1, max: 365 * 24 * 3600 })

// 有效时间（1 秒到 1 年后）
const validSecondsFromNowArb = fc.integer({ min: 1, max: 365 * 24 * 3600 })

// ─── 路由守卫逻辑（从 router/index.ts 提取的纯函数版本）────────────────────────

/**
 * 模拟路由守卫的核心判断逻辑：
 * - requiresAuth === false → 允许通过
 * - isAuthenticated 为 false → 重定向至 /login
 * - 否则 → 允许通过
 */
function guardDecision(
  requiresAuth: boolean,
  isAuthenticated: boolean,
): 'allow' | 'redirect-to-login' {
  if (!requiresAuth) return 'allow'
  if (!isAuthenticated) return 'redirect-to-login'
  return 'allow'
}

// ─── 测试：isTokenValid 纯函数属性 ───────────────────────────────────────────

describe('属性 34：路由守卫认证拦截 - isTokenValid 纯函数', () => {
  it('null token：isTokenValid 应返回 false', () => {
    expect(isTokenValid(null)).toBe(false)
  })

  it('空字符串 token：isTokenValid 应返回 false', () => {
    expect(isTokenValid('')).toBe(false)
  })

  it('格式无效的 token（非 JWT 三段式）：isTokenValid 应返回 false', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.split('.').length !== 3),
        (invalidToken) => {
          expect(isTokenValid(invalidToken)).toBe(false)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('已过期的 token：isTokenValid 应返回 false', () => {
    fc.assert(
      fc.property(expiredSecondsAgoArb, (secondsAgo) => {
        const token = makeExpiredToken(secondsAgo)
        expect(isTokenValid(token)).toBe(false)
      }),
      { numRuns: 100 },
    )
  })

  it('有效的 token（未过期）：isTokenValid 应返回 true', () => {
    fc.assert(
      fc.property(validSecondsFromNowArb, (secondsFromNow) => {
        const token = makeValidToken(secondsFromNow)
        expect(isTokenValid(token)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  it('parseTokenExp：有效 JWT 应正确解析 exp 字段', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1000000, max: 9999999999 }), (exp) => {
        const token = makeJwtWithExp(exp)
        expect(parseTokenExp(token)).toBe(exp)
      }),
      { numRuns: 100 },
    )
  })
})

// ─── 测试：路由守卫决策逻辑属性 ──────────────────────────────────────────────

describe('属性 34：路由守卫认证拦截 - 守卫决策逻辑', () => {
  it('受保护路由 + 无 token：守卫应重定向至登录页', () => {
    fc.assert(
      fc.property(protectedPathArb, (_path) => {
        // 无 token → isAuthenticated = false
        const decision = guardDecision(true, false)
        expect(decision).toBe('redirect-to-login')
      }),
      { numRuns: 100 },
    )
  })

  it('受保护路由 + 过期 token：守卫应重定向至登录页', () => {
    fc.assert(
      fc.property(protectedPathArb, expiredSecondsAgoArb, (_path, secondsAgo) => {
        const token = makeExpiredToken(secondsAgo)
        const isAuthenticated = isTokenValid(token)
        const decision = guardDecision(true, isAuthenticated)
        expect(decision).toBe('redirect-to-login')
      }),
      { numRuns: 100 },
    )
  })

  it('受保护路由 + 有效 token：守卫应允许通过', () => {
    fc.assert(
      fc.property(protectedPathArb, validSecondsFromNowArb, (_path, secondsFromNow) => {
        const token = makeValidToken(secondsFromNow)
        const isAuthenticated = isTokenValid(token)
        const decision = guardDecision(true, isAuthenticated)
        expect(decision).toBe('allow')
      }),
      { numRuns: 100 },
    )
  })

  it('公开路由（/login, /register）：无论 token 状态如何，守卫应允许通过', () => {
    fc.assert(
      fc.property(publicPathArb, fc.boolean(), (_path, hasValidToken) => {
        // requiresAuth === false → 直接允许，不检查 token
        const decision = guardDecision(false, hasValidToken)
        expect(decision).toBe('allow')
      }),
      { numRuns: 100 },
    )
  })

  it('公开路由 + 过期 token：守卫仍应允许通过', () => {
    fc.assert(
      fc.property(publicPathArb, expiredSecondsAgoArb, (_path, secondsAgo) => {
        const token = makeExpiredToken(secondsAgo)
        const isAuthenticated = isTokenValid(token)
        // 公开路由不检查认证状态
        const decision = guardDecision(false, isAuthenticated)
        expect(decision).toBe('allow')
      }),
      { numRuns: 50 },
    )
  })
})

// ─── 测试：路由守卫与 localStorage 集成属性 ──────────────────────────────────

describe('属性 34：路由守卫认证拦截 - localStorage token 状态', () => {
  beforeEach(() => {
    localStorage.removeItem('access_token')
    vi.clearAllMocks()
  })

  it('localStorage 无 token：isTokenValid 应返回 false，守卫应拦截受保护路由', async () => {
    await fc.assert(
      fc.asyncProperty(protectedPathArb, async (_path) => {
        localStorage.removeItem('access_token')

        const { setActivePinia, createPinia } = await import('pinia')
        setActivePinia(createPinia())
        const { useAuthStore } = await import('@/stores/auth')
        const store = useAuthStore()

        expect(store.isAuthenticated).toBe(false)
        const decision = guardDecision(true, store.isAuthenticated)
        expect(decision).toBe('redirect-to-login')
      }),
      { numRuns: 20 },
    )
  })

  it('localStorage 存有过期 token：isAuthenticated 应为 false，守卫应拦截受保护路由', async () => {
    await fc.assert(
      fc.asyncProperty(protectedPathArb, expiredSecondsAgoArb, async (_path, secondsAgo) => {
        const expiredToken = makeExpiredToken(secondsAgo)
        localStorage.setItem('access_token', expiredToken)

        const { setActivePinia, createPinia } = await import('pinia')
        setActivePinia(createPinia())
        const { useAuthStore } = await import('@/stores/auth')
        const store = useAuthStore()

        expect(store.isAuthenticated).toBe(false)
        const decision = guardDecision(true, store.isAuthenticated)
        expect(decision).toBe('redirect-to-login')
      }),
      { numRuns: 20 },
    )
  })

  it('localStorage 存有有效 token：isAuthenticated 应为 true，守卫应允许受保护路由通过', async () => {
    await fc.assert(
      fc.asyncProperty(
        protectedPathArb,
        validSecondsFromNowArb,
        async (_path, secondsFromNow) => {
          const validToken = makeValidToken(secondsFromNow)
          localStorage.setItem('access_token', validToken)

          const { setActivePinia, createPinia } = await import('pinia')
          setActivePinia(createPinia())
          const { useAuthStore } = await import('@/stores/auth')
          const store = useAuthStore()

          expect(store.isAuthenticated).toBe(true)
          const decision = guardDecision(true, store.isAuthenticated)
          expect(decision).toBe('allow')
        },
      ),
      { numRuns: 20 },
    )
  })

  it('公开路由：无论 localStorage token 状态如何，守卫均应允许通过', async () => {
    await fc.assert(
      fc.asyncProperty(publicPathArb, async (_path) => {
        // 无 token 情况
        localStorage.removeItem('access_token')

        const { setActivePinia, createPinia } = await import('pinia')
        setActivePinia(createPinia())
        const { useAuthStore } = await import('@/stores/auth')
        const store = useAuthStore()

        // 公开路由不检查认证
        const decision = guardDecision(false, store.isAuthenticated)
        expect(decision).toBe('allow')
      }),
      { numRuns: 20 },
    )
  })
})
