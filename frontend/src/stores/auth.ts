import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api'

export type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface AuthUser {
  id: string
  username: string
  role: UserRole
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => !!token.value)
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
