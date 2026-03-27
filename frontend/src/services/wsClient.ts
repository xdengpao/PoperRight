/**
 * WebSocket 客户端 - 支持自动重连（指数退避）
 * 需求 21.16
 */

export interface WsMessage {
  type: 'alert' | 'market_overview' | 'position_update' | 'connected'
  data: Record<string, unknown>
}

type MessageHandler = (msg: WsMessage) => void

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000/api/v1/ws'

/** 指数退避参数 */
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30_000

export class WsClient {
  private ws: WebSocket | null = null
  private handlers: MessageHandler[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private userId: string | null = null
  private token: string | null = null
  private manualDisconnect = false

  /** 建立 WebSocket 连接 */
  connect(userId: string, token: string): void {
    this.userId = userId
    this.token = token
    this.manualDisconnect = false
    this._openSocket()
  }

  /** 主动断开连接（不触发重连） */
  disconnect(): void {
    this.manualDisconnect = true
    this._clearReconnectTimer()
    this.reconnectAttempts = 0
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /** 注册消息处理器 */
  onMessage(handler: MessageHandler): void {
    this.handlers.push(handler)
  }

  /** 移除消息处理器 */
  offMessage(handler: MessageHandler): void {
    this.handlers = this.handlers.filter((h) => h !== handler)
  }

  /** 手动触发重连 */
  reconnect(): void {
    this.disconnect()
    this.manualDisconnect = false
    if (this.userId && this.token) {
      this._openSocket()
    }
  }

  private _openSocket(): void {
    if (!this.userId || !this.token) return

    const url = `${WS_BASE_URL}/${this.userId}?token=${encodeURIComponent(this.token)}`
    try {
      this.ws = new WebSocket(url)
    } catch {
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data as string)
        this.handlers.forEach((h) => h(msg))
      } catch {
        // 忽略非 JSON 消息
      }
    }

    this.ws.onclose = (event: CloseEvent) => {
      this.ws = null
      // 4001 = 认证失败，不重连
      if (this.manualDisconnect || event.code === 4001) return
      this._scheduleReconnect()
    }

    this.ws.onerror = () => {
      // onerror 后会触发 onclose，由 onclose 处理重连
    }
  }

  /** 指数退避重连调度：1s → 2s → 4s → 8s → 最大 30s */
  private _scheduleReconnect(): void {
    this._clearReconnectTimer()
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.reconnectAttempts, RECONNECT_MAX_MS)
    this.reconnectAttempts++
    this.reconnectTimer = setTimeout(() => {
      if (!this.manualDisconnect && this.userId && this.token) {
        this._openSocket()
      }
    }, delay)
  }

  private _clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }
}

/** 全局单例 */
export const wsClient = new WsClient()
