import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// 模拟 apiClient，避免真实 HTTP 请求
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态：未认证', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.role).toBe('READONLY')
  })

  it('logout 后清除 token 和用户信息', () => {
    const store = useAuthStore()
    // 手动设置状态模拟已登录
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
})
