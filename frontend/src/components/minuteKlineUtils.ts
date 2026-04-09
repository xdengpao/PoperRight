// ─── 分钟K线图工具函数与类型 ──────────────────────────────────────────────────

export interface KlineBar {
  time: string
  open: string
  high: string
  low: string
  close: string
  volume: number
  amount: string
  turnover: string
  vol_ratio: string
}

/** 模块级缓存（跨组件实例持久化） */
export const minuteKlineCache = new Map<string, KlineBar[]>()

// 开发环境下 HMR 时自动清空缓存，避免脏数据残留
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    minuteKlineCache.clear()
  })
}

/** 构造缓存 key: `${symbol}-${date}-${freq}` */
export function buildCacheKey(symbol: string, date: string, freq: string): string {
  return `${symbol}-${date}-${freq}`
}

/** 构造 API 请求参数 */
export function buildRequestParams(freq: string, date: string) {
  return { freq, start: date, end: date }
}

/** 从日K线点击事件中提取日期（纯函数，便于测试） */
export function extractDateFromClick(dates: string[], dataIndex: number): string | null {
  if (dataIndex >= 0 && dataIndex < dates.length) {
    return dates[dataIndex]
  }
  return null
}
