import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore, parseTokenExp, isTokenValid } from '../auth'

// 模拟 apiClient，避免真实 HTTP 请求
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

// 模拟 wsClient，避免真实 WebSocket 连接
const mockWsClient = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  onMessage: vi.fn(),
  offMessage: vi.fn(),
  reconnect: vi.fn(),
}
vi.mock('@/services/wsClient', () => ({
  wsClient: mockWsClient,
}))

// ─── 辅助：构造 JWT token ──────────────────────────────────────────────────

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const sig = 'fakesig'
  return `${header}.${body}.${sig}`
}

describe('parseTokenExp', () => {
  it('从有效 JWT 中解析 exp', () => {
    const exp = Math.floor(Date.now() / 1000) + 3600
    const token = makeJwt({ sub: '1', exp })
    expect(parseTokenExp(token)).toBe(exp)
  })

  it('token 格式无效时返回 null', () => {
    expect(parseTokenExp('not-a-jwt')).toBeNull()
    expect(parseTokenExp('')).toBeNull()
  })

  it('payload 缺少 exp 时返回 null', () => {
    const token = makeJwt({ sub: '1' })
    expect(parseTokenExp(token)).toBeNull()
  })
})

describe('isTokenValid', () => {
  it('null token 返回 false', () => {
    expect(isTokenValid(null)).toBe(false)
  })

  it('未过期 token 返回 true', () => {
    const exp = Math.floor(Date.now() / 1000) + 3600
    expect(isTokenValid(makeJwt({ sub: '1', exp }))).toBe(true)
  })

  it('已过期 token 返回 false', () => {
    const exp = Math.floor(Date.now() / 1000) - 60
    expect(isTokenValid(makeJwt({ sub: '1', exp }))).toBe(false)
  })
})

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    vi.clearAllMocks()
  })

  it('初始状态：未认证', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.role).toBe('READONLY')
  })

  it('持有有效 token 时 isAuthenticated 为 true', () => {
    const exp = Math.floor(Date.now() / 1000) + 3600
    const validToken = makeJwt({ sub: '1', exp })
    const store = useAuthStore()
    store.token = validToken
    expect(store.isAuthenticated).toBe(true)
  })

  it('持有过期 token 时 isAuthenticated 为 false', () => {
    const exp = Math.floor(Date.now() / 1000) - 60
    const expiredToken = makeJwt({ sub: '1', exp })
    const store = useAuthStore()
    store.token = expiredToken
    expect(store.isAuthenticated).toBe(false)
  })

  it('logout 后清除 token 和用户信息', () => {
    const store = useAuthStore()
    store.token = 'test-token'
    store.user = { id: '1', username: 'trader', role: 'TRADER' }

    store.logout()

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('role 计算属性根据 user.role 返回正确角色', () => {
    const store = useAuthStore()
    store.user = { id: '1', username: 'admin', role: 'ADMIN' }
    expect(store.role).toBe('ADMIN')
  })

  it('logout 时调用 wsClient.disconnect', () => {
    const store = useAuthStore()
    store.token = 'test-token'
    store.user = { id: '1', username: 'trader', role: 'TRADER' }
    store.logout()
    expect(mockWsClient.disconnect).toHaveBeenCalledOnce()
  })
})
