import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AlertType = 'SCREEN' | 'RISK' | 'TRADE' | 'SYSTEM'
export type AlertLevel = 'INFO' | 'WARNING' | 'DANGER'

export interface AlertMessage {
  id: string
  type?: AlertType
  symbol: string
  message: string
  level: AlertLevel
  created_at: string
  read: boolean
  link_to?: string
}

/** Toast 通知（弹出卡片），与历史列表分开管理 */
export interface AlertToast {
  id: string
  type: AlertType
  symbol: string
  message: string
  level: AlertLevel
  created_at: string
  link_to: string
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref<AlertMessage[]>([])
  const unreadCount = ref(0)
  const toasts = ref<AlertToast[]>([])

  function addAlert(alert: AlertMessage) {
    alerts.value.unshift(alert)
    if (!alert.read) unreadCount.value++
  }

  function markRead(id: string) {
    const item = alerts.value.find((a) => a.id === id)
    if (item && !item.read) {
      item.read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  }

  function clearAll() {
    alerts.value = []
    unreadCount.value = 0
  }

  /** 推送一条 toast 弹出通知 */
  function pushToast(toast: AlertToast) {
    toasts.value.push(toast)
  }

  /** 移除指定 toast */
  function removeToast(id: string) {
    const idx = toasts.value.findIndex((t) => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  return { alerts, unreadCount, toasts, addAlert, markRead, clearAll, pushToast, removeToast }
})
