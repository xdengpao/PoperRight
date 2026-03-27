import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api'

export type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface AuthUser {
  id: string
  username: string
  role: UserRole
}

/**
 * 解析 JWT payload 中的 exp 字段（秒级 Unix 时间戳）。
 * 返回 null 表示 token 格式无效或缺少 exp。
 */
export function parseTokenExp(token: string): number | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    // base64url → base64 → JSON
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const decoded = JSON.parse(atob(payload))
    if (typeof decoded.exp === 'number') return decoded.exp
    return null
  } catch {
    return null
  }
}

/**
 * 判断 token 是否仍然有效（存在且未过期）。
 */
export function isTokenValid(token: string | null): boolean {
  if (!token) return false
  const exp = parseTokenExp(token)
  if (exp === null) return false
  // 当前时间（秒）与 exp 比较
  return exp > Date.now() / 1000
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => isTokenValid(token.value))
  const role = computed<UserRole>(() => user.value?.role ?? 'READONLY')

  async function login(username: string, password: string) {
    const res = await apiClient.post<{ access_token: string; user: AuthUser }>(
      '/auth/login',
      { username, password },
    )
    token.value = res.data.access_token
    user.value = res.data.user
    localStorage.setItem('access_token', res.data.access_token)
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  async function fetchCurrentUser() {
    if (!token.value) return
    const res = await apiClient.get<AuthUser>('/auth/me')
    user.value = res.data
  }

  return { token, user, isAuthenticated, role, login, logout, fetchCurrentUser }
})
