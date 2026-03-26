import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAlertStore, type AlertMessage } from '../alert'

function makeAlert(overrides: Partial<AlertMessage> = {}): AlertMessage {
  return {
    id: Math.random().toString(36).slice(2),
    symbol: '000001',
    message: '测试预警',
    level: 'INFO',
    created_at: new Date().toISOString(),
    read: false,
    ...overrides,
  }
}

describe('useAlertStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('addAlert 增加未读计数', () => {
    const store = useAlertStore()
    store.addAlert(makeAlert())
    expect(store.unreadCount).toBe(1)
    expect(store.alerts).toHaveLength(1)
  })

  it('addAlert 已读消息不增加未读计数', () => {
    const store = useAlertStore()
    store.addAlert(makeAlert({ read: true }))
    expect(store.unreadCount).toBe(0)
  })

  it('markRead 将消息标记为已读并减少未读计数', () => {
    const store = useAlertStore()
    const alert = makeAlert()
    store.addAlert(alert)
    store.markRead(alert.id)
    expect(store.unreadCount).toBe(0)
    expect(store.alerts[0].read).toBe(true)
  })

  it('clearAll 清空所有消息和未读计数', () => {
    const store = useAlertStore()
    store.addAlert(makeAlert())
    store.addAlert(makeAlert())
    store.clearAll()
    expect(store.alerts).toHaveLength(0)
    expect(store.unreadCount).toBe(0)
  })

  it('新消息插入到列表头部', () => {
    const store = useAlertStore()
    const first = makeAlert({ symbol: '000001' })
    const second = makeAlert({ symbol: '600000' })
    store.addAlert(first)
    store.addAlert(second)
    expect(store.alerts[0].symbol).toBe('600000')
  })
})
