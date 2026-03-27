import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createWebHistory, type Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { defineComponent } from 'vue'

// 模拟 apiClient
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

const Stub = defineComponent({ template: '<div />' })

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${body}.fakesig`
}

function buildRouter(): Router {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/login', name: 'Login', component: Stub, meta: { requiresAuth: false } },
      { path: '/register', name: 'Register', component: Stub, meta: { requiresAuth: false } },
      {
        path: '/',
        component: Stub,
        meta: { requiresAuth: true },
        children: [
          { path: '', redirect: '/dashboard' },
          { path: 'dashboard', name: 'Dashboard', component: Stub },
          { path: 'admin', name: 'Admin', component: Stub, meta: { roles: ['ADMIN'] } },
        ],
      },
    ],
  })

  // 复制生产环境的守卫逻辑
  router.beforeEach((to, _from, next) => {
    const authStore = useAuthStore()
    if (to.meta.requiresAuth === false) return next()
    if (!authStore.isAuthenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }
    const requiredRoles = to.meta.roles as string[] | undefined
    if (requiredRoles && !requiredRoles.includes(authStore.role)) {
      return next({ name: 'Dashboard' })
    }
    next()
  })

  return router
}

describe('路由守卫', () => {
  let router: Router

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    router = buildRouter()
  })

  it('未认证用户访问受保护路由时重定向至登录页', async () => {
    await router.push('/dashboard')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Login')
    expect(router.currentRoute.value.query.redirect).toBe('/dashboard')
  })

  it('持有过期 token 的用户被重定向至登录页', async () => {
    const authStore = useAuthStore()
    const expiredToken = makeJwt({ sub: '1', exp: Math.floor(Date.now() / 1000) - 60 })
    authStore.token = expiredToken

    await router.push('/dashboard')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Login')
  })

  it('持有有效 token 的用户可以访问受保护路由', async () => {
    const authStore = useAuthStore()
    const validToken = makeJwt({ sub: '1', exp: Math.floor(Date.now() / 1000) + 3600 })
    authStore.token = validToken

    await router.push('/dashboard')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })

  it('未认证用户可以访问登录页', async () => {
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Login')
  })

  it('未认证用户可以访问注册页', async () => {
    await router.push('/register')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Register')
  })

  it('角色不匹配时重定向至 Dashboard', async () => {
    const authStore = useAuthStore()
    const validToken = makeJwt({ sub: '1', exp: Math.floor(Date.now() / 1000) + 3600 })
    authStore.token = validToken
    authStore.user = { id: '1', username: 'trader', role: 'TRADER' }

    await router.push('/admin')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })
})
