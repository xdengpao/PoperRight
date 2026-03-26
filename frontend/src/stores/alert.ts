import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface AlertMessage {
  id: string
  symbol: string
  message: string
  level: 'INFO' | 'WARNING' | 'DANGER'
  created_at: string
  read: boolean
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref<AlertMessage[]>([])
  const unreadCount = ref(0)

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

  return { alerts, unreadCount, addAlert, markRead, clearAll }
})
