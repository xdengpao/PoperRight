/**
 * WsClient 单元测试
 * 需求 21.16
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { WsClient, type WsMessage } from '../wsClient'

// ─── Mock WebSocket ────────────────────────────────────────────────────────

class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: ((e: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  readyState = 0

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close() {
    this.onclose?.({ code: 1000 })
  }

  /** 模拟服务端发送消息 */
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  /** 模拟连接成功 */
  simulateOpen() {
    this.readyState = 1
    this.onopen?.()
  }

  /** 模拟连接关闭 */
  simulateClose(code = 1006) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('WsClient', () => {
  let client: WsClient

  beforeEach(() => {
    MockWebSocket.instances = []
    vi.useFakeTimers()
    client = new WsClient()
  })

  afterEach(() => {
    client.disconnect()
    vi.useRealTimers()
  })

  it('connect 创建 WebSocket 并使用正确 URL', () => {
    client.connect('user1', 'tok123')
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toContain('/user1')
    expect(MockWebSocket.instances[0].url).toContain('token=tok123')
  })

  it('onMessage 处理器接收到消息', () => {
    const handler = vi.fn()
    client.onMessage(handler)
    client.connect('user1', 'tok')

    const ws = MockWebSocket.instances[0]
    const msg: WsMessage = { type: 'connected', data: {} }
    ws.simulateMessage(msg)

    expect(handler).toHaveBeenCalledWith(msg)
  })

  it('disconnect 后不触发重连', () => {
    client.connect('user1', 'tok')
    const ws = MockWebSocket.instances[0]
    ws.simulateOpen()

    client.disconnect()
    ws.simulateClose(1006)

    vi.advanceTimersByTime(5000)
    // 只有初始连接，没有重连
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('连接断开后自动重连（指数退避）', () => {
    client.connect('user1', 'tok')
    const ws = MockWebSocket.instances[0]
    ws.simulateOpen()
    ws.simulateClose(1006)

    // 第一次重连：1s 后
    expect(MockWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it('指数退避：第二次重连延迟为 2s', () => {
    client.connect('user1', 'tok')
    MockWebSocket.instances[0].simulateOpen()
    MockWebSocket.instances[0].simulateClose(1006)

    vi.advanceTimersByTime(1000) // 第一次重连
    expect(MockWebSocket.instances).toHaveLength(2)

    MockWebSocket.instances[1].simulateClose(1006)
    vi.advanceTimersByTime(1000) // 不够 2s
    expect(MockWebSocket.instances).toHaveLength(2)

    vi.advanceTimersByTime(1000) // 共 2s
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('认证失败（code 4001）不触发重连', () => {
    client.connect('user1', 'tok')
    MockWebSocket.instances[0].simulateOpen()
    MockWebSocket.instances[0].simulateClose(4001)

    vi.advanceTimersByTime(10000)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('连接成功后重置重连计数', () => {
    client.connect('user1', 'tok')
    MockWebSocket.instances[0].simulateOpen()
    MockWebSocket.instances[0].simulateClose(1006)

    vi.advanceTimersByTime(1000) // 第一次重连
    MockWebSocket.instances[1].simulateOpen() // 重连成功，重置计数

    MockWebSocket.instances[1].simulateClose(1006)
    vi.advanceTimersByTime(1000) // 重置后第一次重连仍是 1s
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('offMessage 移除处理器后不再接收消息', () => {
    const handler = vi.fn()
    client.onMessage(handler)
    client.offMessage(handler)
    client.connect('user1', 'tok')

    MockWebSocket.instances[0].simulateMessage({ type: 'connected', data: {} })
    expect(handler).not.toHaveBeenCalled()
  })

  it('非 JSON 消息不抛出异常', () => {
    const handler = vi.fn()
    client.onMessage(handler)
    client.connect('user1', 'tok')

    expect(() => {
      MockWebSocket.instances[0].onmessage?.({ data: 'not-json' })
    }).not.toThrow()
    expect(handler).not.toHaveBeenCalled()
  })
})
