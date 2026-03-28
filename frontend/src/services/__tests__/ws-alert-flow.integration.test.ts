/**
 * 集成测试：WebSocket 连接 → 预警推送 → 通知弹窗 → 跳转详情 全链路
 *
 * 验证完整的 WebSocket 预警推送流程：
 * 1. 用户登录 → WebSocket 连接建立（wsClient.connect 被调用）
 * 2. WebSocket 收到 alert 消息 → auth store 的 _handleWsMessage 处理
 * 3. AlertStore 新增预警（alerts 数组、unreadCount 递增）
 * 4. Toast 通知推送至 AlertStore（toasts 数组）
 * 5. Toast 包含正确的 type、symbol、message、level、link_to 字段
 * 6. 收到 position_update 消息 → PositionsStore 更新持仓
 * 7. 用户登出 → WebSocket 断开（wsClient.disconnect 被调用）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { WsMessage } from '@/services/wsClient'

// ─── 捕获 onMessage handler ──────────────────────────────────────────────────

let capturedHandler: ((msg: WsMessage) => void) | null = null

vi.mock('@/services/wsClient', () => ({
  wsClient: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onMessage: vi.fn((handler: (msg: WsMessage) => void) => {
      capturedHandler = handler
    }),
    offMessage: vi.fn(),
    reconnect: vi.fn(),
  },
}))

const mockPost = vi.fn()
const mockGet = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function makeValidToken(secondsFromNow = 3600): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const payload = btoa(JSON.stringify({ sub: 'user1', exp: Math.floor(Date.now() / 1000) + secondsFromNow }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${payload}.fakesignature`
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('集成测试：WebSocket 连接 → 预警推送 → 通知弹窗 → 跳转详情', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('access_token')
    capturedHandler = null
    vi.clearAllMocks()
  })

  it('登录后建立 WebSocket 连接，收到 alert 消息后 AlertStore 新增预警和 toast', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { useAlertStore } = await import('@/stores/alert')
    const { wsClient } = await import('@/services/wsClient')

    const authStore = useAuthStore()
    const alertStore = useAlertStore()

    // 初始状态
    expect(alertStore.alerts).toHaveLength(0)
    expect(alertStore.unreadCount).toBe(0)
    expect(alertStore.toasts).toHaveLength(0)

    // 模拟登录
    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'password123')

    // 验证 WebSocket 连接已建立
    expect(wsClient.connect).toHaveBeenCalledWith('u1', validToken)
    expect(wsClient.onMessage).toHaveBeenCalled()
    expect(capturedHandler).not.toBeNull()

    // 模拟 WebSocket 收到 alert 消息
    const alertData = {
      id: 'alert-001',
      type: 'SCREEN',
      symbol: '600519',
      message: '贵州茅台趋势打分突破90分',
      level: 'WARNING',
      created_at: '2024-01-15T10:30:00Z',
      link_to: '/screener/results',
    }
    capturedHandler!({ type: 'alert', data: alertData })

    // 验证 AlertStore 新增了预警
    expect(alertStore.alerts).toHaveLength(1)
    expect(alertStore.alerts[0].id).toBe('alert-001')
    expect(alertStore.alerts[0].symbol).toBe('600519')
    expect(alertStore.alerts[0].message).toBe('贵州茅台趋势打分突破90分')
    expect(alertStore.alerts[0].level).toBe('WARNING')
    expect(alertStore.alerts[0].read).toBe(false)

    // 验证 unreadCount 递增
    expect(alertStore.unreadCount).toBe(1)

    // 验证 toast 通知已推送
    expect(alertStore.toasts).toHaveLength(1)
    const toast = alertStore.toasts[0]
    expect(toast.id).toBe('alert-001')
    expect(toast.type).toBe('SCREEN')
    expect(toast.symbol).toBe('600519')
    expect(toast.message).toBe('贵州茅台趋势打分突破90分')
    expect(toast.level).toBe('WARNING')
    expect(toast.link_to).toBe('/screener/results')
  })

  it('收到多条 alert 消息后 unreadCount 正确累加', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { useAlertStore } = await import('@/stores/alert')

    const authStore = useAuthStore()
    const alertStore = useAlertStore()

    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'pass')

    // 发送两条 alert
    capturedHandler!({
      type: 'alert',
      data: { id: 'a1', type: 'RISK', symbol: '000001', message: '风控预警', level: 'DANGER', link_to: '/risk' },
    })
    capturedHandler!({
      type: 'alert',
      data: { id: 'a2', type: 'TRADE', symbol: '000002', message: '交易预警', level: 'INFO', link_to: '/trade' },
    })

    expect(alertStore.alerts).toHaveLength(2)
    expect(alertStore.unreadCount).toBe(2)
    expect(alertStore.toasts).toHaveLength(2)
  })

  it('收到 position_update 消息后 PositionsStore 更新持仓', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { usePositionsStore } = await import('@/stores/positions')

    const authStore = useAuthStore()
    const positionsStore = usePositionsStore()

    expect(positionsStore.positions).toHaveLength(0)

    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'pass')

    // 模拟 position_update 消息
    const positionData = {
      symbol: '600519',
      name: '贵州茅台',
      quantity: 100,
      available_quantity: 100,
      cost_price: 1800.0,
      current_price: 1850.5,
      market_value: 185050.0,
      profit_loss: 5050.0,
      profit_loss_ratio: 0.028,
    }
    capturedHandler!({ type: 'position_update', data: positionData })

    // 验证持仓已更新
    expect(positionsStore.positions).toHaveLength(1)
    expect(positionsStore.positions[0].symbol).toBe('600519')
    expect(positionsStore.positions[0].quantity).toBe(100)
    expect(positionsStore.positions[0].current_price).toBe(1850.5)
    expect(positionsStore.positions[0].profit_loss).toBe(5050.0)
  })

  it('position_update 更新已有持仓而非新增', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { usePositionsStore } = await import('@/stores/positions')

    const authStore = useAuthStore()
    const positionsStore = usePositionsStore()

    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'pass')

    // 先推送一条持仓
    capturedHandler!({
      type: 'position_update',
      data: { symbol: '600519', quantity: 100, available_quantity: 100, cost_price: 1800, current_price: 1800, market_value: 180000, profit_loss: 0, profit_loss_ratio: 0 },
    })
    expect(positionsStore.positions).toHaveLength(1)

    // 再推送同一股票的更新
    capturedHandler!({
      type: 'position_update',
      data: { symbol: '600519', quantity: 100, available_quantity: 100, cost_price: 1800, current_price: 1900, market_value: 190000, profit_loss: 10000, profit_loss_ratio: 0.0556 },
    })

    // 应更新而非新增
    expect(positionsStore.positions).toHaveLength(1)
    expect(positionsStore.positions[0].current_price).toBe(1900)
    expect(positionsStore.positions[0].profit_loss).toBe(10000)
  })

  it('登出后 WebSocket 断开连接', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { wsClient } = await import('@/services/wsClient')

    const authStore = useAuthStore()

    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'pass')
    expect(wsClient.connect).toHaveBeenCalledTimes(1)

    // 登出
    authStore.logout()

    // 验证 WebSocket 已断开
    expect(wsClient.disconnect).toHaveBeenCalledTimes(1)
    expect(authStore.isAuthenticated).toBe(false)
    expect(authStore.token).toBeNull()
  })

  it('alert 消息缺少可选字段时使用默认值', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const { useAlertStore } = await import('@/stores/alert')

    const authStore = useAuthStore()
    const alertStore = useAlertStore()

    const validToken = makeValidToken()
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: validToken,
        user: { id: 'u1', username: 'trader1', role: 'TRADER' },
      },
    })
    await authStore.login('trader1', 'pass')

    // 发送缺少部分字段的 alert（无 symbol、无 link_to）
    capturedHandler!({
      type: 'alert',
      data: { id: 'a-minimal', message: '系统通知', level: 'INFO' },
    })

    expect(alertStore.alerts).toHaveLength(1)
    expect(alertStore.alerts[0].symbol).toBe('')
    expect(alertStore.alerts[0].level).toBe('INFO')
    expect(alertStore.alerts[0].read).toBe(false)

    // toast 的 link_to 应为空字符串（默认值）
    expect(alertStore.toasts).toHaveLength(1)
    expect(alertStore.toasts[0].link_to).toBe('')
    // toast 的 type 应为 'SYSTEM'（默认值，因为 alert.type 为 undefined）
    expect(alertStore.toasts[0].type).toBe('SYSTEM')
  })
})
