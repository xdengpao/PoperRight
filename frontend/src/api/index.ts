import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

// ─── 常量 ────────────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const REQUEST_TIMEOUT = 15_000 // 15s

// ─── Axios 实例 ───────────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// ─── 请求拦截器：注入 JWT Token（需求 19） ────────────────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error: unknown) => Promise.reject(error),
)

// ─── 响应拦截器：统一错误处理（需求 21.3） ────────────────────────────────────

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: { response?: { status: number; data: { detail?: string } } }) => {
    if (!error.response) {
      // 网络错误 / 超时
      return Promise.reject(new Error('网络连接失败，请检查网络设置'))
    }

    const { status, data } = error.response

    switch (status) {
      case 400:
        return Promise.reject(new Error(data?.detail ?? '请求参数错误'))
      case 401: {
        // Token 过期或无效，清除 auth 状态并跳转登录页（需求 21.3）
        const authStore = useAuthStore()
        authStore.logout()
        const currentPath = router.currentRoute.value.fullPath
        if (currentPath !== '/login') {
          router.push({ name: 'Login', query: { redirect: currentPath } })
        }
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
      case 403:
        return Promise.reject(new Error('权限不足，无法执行此操作'))
      case 404:
        return Promise.reject(new Error('请求的资源不存在'))
      case 422:
        return Promise.reject(new Error(data?.detail ?? '数据校验失败'))
      case 429:
        return Promise.reject(new Error('请求过于频繁，请稍后再试'))
      case 500:
        return Promise.reject(new Error('服务器内部错误，请联系管理员'))
      default:
        return Promise.reject(new Error(data?.detail ?? `请求失败（${status}）`))
    }
  },
)

// ─── 便捷方法 ─────────────────────────────────────────────────────────────────

export default apiClient
