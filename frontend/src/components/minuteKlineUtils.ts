// ─── 分钟K线图工具函数与类型 ──────────────────────────────────────────────────

export interface KlineBar {
  time: string
  trade_date?: string
  trade_time?: string | null
  display_time?: string | null
  open: string
  high: string
  low: string
  close: string
  volume: number
  amount: string
  turnover: string
  vol_ratio: string
}

/** 复权类型: 0=不复权, 1=前复权 */
export type AdjType = 0 | 1

/** 模块级缓存（跨组件实例持久化） */
export const minuteKlineCache = new Map<string, KlineBar[]>()

// 开发环境下 HMR 时自动清空缓存，避免脏数据残留
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    minuteKlineCache.clear()
  })
}

/** 构造缓存 key: `${symbol}-${date}-${freq}-${adjType}` */
export function buildCacheKey(symbol: string, date: string, freq: string, adjType: AdjType = 0): string {
  return `${symbol}-${date}-${freq}-${adjType}`
}

/** 构造 API 请求参数 */
export function buildRequestParams(freq: string, date: string, adjType: AdjType = 0) {
  return { freq, start: date, end: date, adj_type: adjType }
}

/** 获取日 K 展示日期：优先使用后端归一化交易日。 */
export function getKlineTradeDate(bar: Pick<KlineBar, 'time' | 'trade_date'>): string {
  return bar.trade_date || bar.time.slice(0, 10)
}

/** 获取分钟 K 展示时间：优先使用后端返回的本地交易时间。 */
export function getKlineDisplayTime(
  bar: Pick<KlineBar, 'time' | 'trade_time' | 'display_time'>,
): string {
  return bar.trade_time || bar.display_time || bar.time.slice(11, 16)
}

/** 按交易日防御性去重，保留后出现的 canonical 行。 */
export function dedupeKlineByTradeDate<T extends Pick<KlineBar, 'time' | 'trade_date'>>(bars: T[]): T[] {
  const byDate = new Map<string, T>()
  for (const bar of bars) {
    byDate.set(getKlineTradeDate(bar), bar)
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, bar]) => bar)
}

/** 从日K线点击事件中提取日期（纯函数，便于测试） */
export function extractDateFromClick(dates: string[], dataIndex: number): string | null {
  if (dataIndex >= 0 && dataIndex < dates.length) {
    return dates[dataIndex]
  }
  return null
}
