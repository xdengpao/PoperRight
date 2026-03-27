import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// 模拟 router
const pushMock = vi.fn()
vi.mock('@/router', () => ({
  default: {
    push: (...args: unknown[]) => pushMock(...args),
    currentRoute: { value: { fullPath: '/dashboard' } },
  },
}))

describe('Axios 401 拦截器', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    pushMock.mockClear()
  })

  it('401 响应时清除 token 并跳转登录页', async () => {
    // 设置初始 token
    localStorage.setItem('access_token', 'old-token')

    // 动态导入以获取新的模块实例
    const { apiClient } = await import('@/api')
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    authStore.token = 'old-token'

    // 模拟 401 响应
    try {
      // 触发响应拦截器的错误处理
      const errorHandler = apiClient.interceptors.response as unknown as {
        handlers: Array<{ rejected: (error: unknown) => unknown }>
      }
      const handler = errorHandler.handlers.find((h) => h.rejected)
      if (handler) {
        await handler.rejected({ response: { status: 401, data: {} } })
      }
    } catch (e) {
      // 预期会抛出错误
      expect((e as Error).message).toBe('登录已过期，请重新登录')
    }

    // 验证 token 被清除
    expect(localStorage.getItem('access_token')).toBeNull()
    // 验证跳转到登录页
    expect(pushMock).toHaveBeenCalledWith({
      name: 'Login',
      query: { redirect: '/dashboard' },
    })
  })
})
