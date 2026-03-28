/**
 * 集成测试：登录 → 路由守卫 → 角色菜单渲染 → 页面访问 全链路
 *
 * 验证完整的认证与授权流程：
 * 1. 登录流程：API 返回 token + user → auth store 存储 → isAuthenticated 变为 true
 * 2. 路由守卫：未认证用户重定向至 /login；已认证用户可访问受保护路由
 * 3. 角色菜单过滤：登录后菜单按角色过滤
 * 4. 角色路由访问：不同角色对受限路由的访问控制
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

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

const mockPost = vi.fn()
const mockGet = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: UserRole[]
  group: '数据' | '选股' | '风控' | '交易' | '分析' | '系统'
}

// ─── 菜单定义（与 MainLayout / design.md 保持一致）─────────────────────────────

const menuGroups: Record<string, NavItem[]> = {
  '数据': [
    { path: '/dashboard', label: '大盘概况', icon: '📊', group: '数据' },
    { path: '/data', label: '数据管理', icon: '💾', group: '数据' },
  ],
  '选股': [
    { path: '/screener', label: '智能选股', icon: '🔍', group: '选股' },
    { path: '/screener/results', label: '选股结果', icon: '📋', group: '选股' },
  ],
  '风控': [
    { path: '/risk', label: '风险控制', icon: '🛡️', group: '风控' },
  ],
  '交易': [
    { path: '/trade', label: '交易执行', icon: '💹', roles: ['TRADER', 'ADMIN'], group: '交易' },
    { path: '/positions', label: '持仓管理', icon: '💰', roles: ['TRADER', 'ADMIN'], group: '交易' },
  ],
  '分析': [
    { path: '/backtest', label: '策略回测', icon: '📈', group: '分析' },
    { path: '/review', label: '复盘分析', icon: '📝', group: '分析' },
  ],
  '系统': [
    { path: '/admin', label: '系统管理', icon: '⚙️', roles: ['ADMIN'], group: '系统' },
  ],
}

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

/** 构造带有指定 exp 的 JWT token（仅用于测试） */
function makeJwtWithExp(exp: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const payload = btoa(JSON.stringify({ sub: 'user1', exp }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${payload}.fakesignature`
}

/** 构造一个有效的 JWT token（exp 在未来） */
function makeValidToken(secondsFromNow = 3600): string {
  return makeJwtWithExp(Math.floor(Date.now() / 1000) + secondsFromNow)
}

/** 按角色过滤菜单项 */
function filterMenuByRole(role: UserRole): NavItem[] {
  const allItems = Object.values(menuGroups).flat()
  return allItems.filter((item) => !item.roles || item.roles.includes(role))
}

/** 路由守卫决策逻辑（纯函数版本，含角色检查） */
function guardDecision(
  requiresAuth: boolean,
  isAuthenticated: boolean,
  requiredRoles?: string[],
  userRole?: string,
): 'allow' | 'redirect-to-login' | 'redirect-to-dashboard' {
  if (!requiresAuth) return 'allow'
  if (!isAuthenticated) return 'redirect-to-login'
  if (requiredRoles && userRole && !requiredRoles.includes(userRole)) return 'redirect-to-dashboard'
  return 'allow'
}

// ─── 路由元数据（与 router/index.ts 保持一致）──────────────────────────────────

const routeMeta: Record<string, { requiresAuth: boolean; roles?: string[] }> = {
  '/login': { requiresAuth: false },
  '/register': { requiresAuth: false },
  '/dashboard': { requiresAuth: true },
  '/data': { requiresAuth: true },
  '/screener': { requiresAuth: true },
  '/screener/results': { requiresAuth: true },
  '/risk': { requiresAuth: true },
  '/backtest': { requiresAuth: true },
  '/trade': { requiresAuth: true, roles: ['TRADER', 'ADMIN'] },
  '/positions': { requiresAuth: true, roles: ['TRADER', 'ADMIN'] },
  '/review': { requiresAuth: true },
  '/admin': { requiresAuth: true, roles: ['ADMIN'] },
}

const PUBLIC_PATHS = ['/dashboard', '/data', '/screener', '/screener/results', '/risk', '/backtest', '/review']
const TRADE_PATHS = ['/trade', '/positions']
const ADMIN_PATHS = ['/admin']

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('集成测试：认证 → 路由守卫 → 菜单渲染 → 页面访问 全链路', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    vi.clearAllMocks()
  })

  // ─── 1. 未认证 → 登录 → 已认证 ──────────────────────────────────────────

  describe('1. 登录流程：未认证 → 登录 → token 存储 → isAuthenticated 变为 true', () => {
    it('登录前 isAuthenticated 为 false，登录后为 true 且 token/user 已存储', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      // 登录前：未认证
      expect(store.isAuthenticated).toBe(false)
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()

      // 模拟登录 API 返回
      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u1', username: 'admin_user', role: 'ADMIN' as UserRole },
        },
      })

      await store.login('admin_user', 'password123')

      // 登录后：已认证
      expect(store.isAuthenticated).toBe(true)
      expect(store.token).toBe(validToken)
      expect(store.user).toEqual({ id: 'u1', username: 'admin_user', role: 'ADMIN' })
      expect(localStorage.getItem('access_token')).toBe(validToken)
    })

    it('登录失败时 token 和 user 保持为空', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      mockPost.mockRejectedValueOnce(new Error('用户名或密码错误'))

      await expect(store.login('bad', 'creds')).rejects.toThrow()

      expect(store.isAuthenticated).toBe(false)
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorage.getItem('access_token')).toBeNull()
    })
  })

  // ─── 2. ADMIN 全链路 ──────────────────────────────────────────────────────

  describe('2. ADMIN 登录 → 可访问所有路由，菜单包含全部项', () => {
    it('ADMIN 登录后路由守卫允许访问所有受保护路由', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u1', username: 'admin', role: 'ADMIN' as UserRole },
        },
      })
      await store.login('admin', 'pass')

      // 所有路由均应允许通过
      const allProtectedPaths = [...PUBLIC_PATHS, ...TRADE_PATHS, ...ADMIN_PATHS]
      for (const path of allProtectedPaths) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('allow')
      }
    })

    it('ADMIN 菜单包含全部菜单项（含 /trade、/positions、/admin）', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u1', username: 'admin', role: 'ADMIN' as UserRole },
        },
      })
      await store.login('admin', 'pass')

      const menuItems = filterMenuByRole(store.role)
      const paths = menuItems.map((item) => item.path)

      const allPaths = [...PUBLIC_PATHS, ...TRADE_PATHS, ...ADMIN_PATHS]
      for (const p of allPaths) {
        expect(paths).toContain(p)
      }
    })
  })

  // ─── 3. TRADER 全链路 ─────────────────────────────────────────────────────

  describe('3. TRADER 登录 → 可访问交易路由，不可访问 /admin', () => {
    it('TRADER 登录后可访问公共路由和交易路由，/admin 重定向至 dashboard', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u2', username: 'trader', role: 'TRADER' as UserRole },
        },
      })
      await store.login('trader', 'pass')

      // 公共路由：允许
      for (const path of PUBLIC_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('allow')
      }

      // 交易路由：允许
      for (const path of TRADE_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('allow')
      }

      // /admin：重定向至 dashboard
      for (const path of ADMIN_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('redirect-to-dashboard')
      }
    })

    it('TRADER 菜单包含交易项但不包含 /admin', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u2', username: 'trader', role: 'TRADER' as UserRole },
        },
      })
      await store.login('trader', 'pass')

      const menuItems = filterMenuByRole(store.role)
      const paths = menuItems.map((item) => item.path)

      // 公共 + 交易路由可见
      for (const p of [...PUBLIC_PATHS, ...TRADE_PATHS]) {
        expect(paths).toContain(p)
      }
      // /admin 不可见
      expect(paths).not.toContain('/admin')
    })
  })

  // ─── 4. READONLY 全链路 ───────────────────────────────────────────────────

  describe('4. READONLY 登录 → 仅可访问公共路由，不可访问交易和管理路由', () => {
    it('READONLY 登录后公共路由允许，交易和管理路由重定向', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u3', username: 'viewer', role: 'READONLY' as UserRole },
        },
      })
      await store.login('viewer', 'pass')

      // 公共路由：允许
      for (const path of PUBLIC_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('allow')
      }

      // 交易路由：重定向
      for (const path of TRADE_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('redirect-to-dashboard')
      }

      // 管理路由：重定向
      for (const path of ADMIN_PATHS) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('redirect-to-dashboard')
      }
    })

    it('READONLY 菜单仅包含公共项，不包含交易和管理项', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u3', username: 'viewer', role: 'READONLY' as UserRole },
        },
      })
      await store.login('viewer', 'pass')

      const menuItems = filterMenuByRole(store.role)
      const paths = menuItems.map((item) => item.path)

      // 公共路由可见
      for (const p of PUBLIC_PATHS) {
        expect(paths).toContain(p)
      }
      // 交易和管理路由不可见
      for (const p of [...TRADE_PATHS, ...ADMIN_PATHS]) {
        expect(paths).not.toContain(p)
      }
    })
  })

  // ─── 5. 登出 → 清除 → 重定向 ─────────────────────────────────────────────

  describe('5. 登出后 token 清除，受保护路由重定向至登录页', () => {
    it('登出后 isAuthenticated 为 false，守卫拦截所有受保护路由', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      // 先登录
      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u1', username: 'admin', role: 'ADMIN' as UserRole },
        },
      })
      await store.login('admin', 'pass')
      expect(store.isAuthenticated).toBe(true)

      // 登出
      store.logout()

      expect(store.isAuthenticated).toBe(false)
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorage.getItem('access_token')).toBeNull()

      // 所有受保护路由应重定向至登录页
      const allProtectedPaths = [...PUBLIC_PATHS, ...TRADE_PATHS, ...ADMIN_PATHS]
      for (const path of allProtectedPaths) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated, meta.roles, store.role)
        expect(decision).toBe('redirect-to-login')
      }
    })

    it('登出后公开路由（/login, /register）仍可访问', async () => {
      const { useAuthStore } = await import('@/stores/auth')
      const store = useAuthStore()

      // 登录后登出
      const validToken = makeValidToken()
      mockPost.mockResolvedValueOnce({
        data: {
          access_token: validToken,
          user: { id: 'u1', username: 'admin', role: 'ADMIN' as UserRole },
        },
      })
      await store.login('admin', 'pass')
      store.logout()

      // 公开路由仍可访问
      for (const path of ['/login', '/register']) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, store.isAuthenticated)
        expect(decision).toBe('allow')
      }
    })
  })

  // ─── 6. 未认证用户路由守卫拦截 ───────────────────────────────────────────

  describe('6. 未认证用户访问受保护路由被重定向至登录页', () => {
    it('未登录时所有受保护路由重定向至 /login', () => {
      const allProtectedPaths = [...PUBLIC_PATHS, ...TRADE_PATHS, ...ADMIN_PATHS]
      for (const path of allProtectedPaths) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, false)
        expect(decision).toBe('redirect-to-login')
      }
    })

    it('未登录时公开路由（/login, /register）允许访问', () => {
      for (const path of ['/login', '/register']) {
        const meta = routeMeta[path]
        const decision = guardDecision(meta.requiresAuth, false)
        expect(decision).toBe('allow')
      }
    })
  })
})
