import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api'
import { wsClient, type WsMessage } from '@/services/wsClient'
import { useAlertStore, type AlertMessage, type AlertToast } from '@/stores/alert'
import { usePositionsStore, type Position } from '@/stores/positions'

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

    // 登录成功后建立 WebSocket 连接
    _setupWsHandlers()
    wsClient.connect(res.data.user.id, res.data.access_token)
  }

  function logout() {
    wsClient.disconnect()
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  /** 注册 WebSocket 消息处理器 */
  function _setupWsHandlers() {
    wsClient.onMessage(_handleWsMessage)
  }

  function _handleWsMessage(msg: WsMessage) {
    if (msg.type === 'alert') {
      const alertStore = useAlertStore()
      const d = msg.data as Record<string, unknown>
      const alert: AlertMessage = {
        id: (d.id as string) ?? crypto.randomUUID(),
        type: d.type as AlertMessage['type'],
        symbol: (d.symbol as string) ?? '',
        message: (d.message as string) ?? '',
        level: (d.level as AlertMessage['level']) ?? 'INFO',
        created_at: (d.created_at as string) ?? new Date().toISOString(),
        read: false,
        link_to: d.link_to as string | undefined,
      }
      alertStore.addAlert(alert)
      alertStore.pushToast({
        id: alert.id,
        type: alert.type ?? 'SYSTEM',
        symbol: alert.symbol,
        message: alert.message,
        level: alert.level,
        created_at: alert.created_at,
        link_to: alert.link_to ?? '',
      } as AlertToast)
    } else if (msg.type === 'position_update') {
      const positionsStore = usePositionsStore()
      positionsStore.updatePosition(msg.data as unknown as Position)
    }
  }

  async function fetchCurrentUser() {
    if (!token.value) return
    const res = await apiClient.get<AuthUser>('/auth/me')
    user.value = res.data
  }

  return { token, user, isAuthenticated, role, login, logout, fetchCurrentUser }
})
