/**
 * 基本面指标颜色编码纯函数
 *
 * 根据指标类型和数值返回对应的 CSS 颜色类名：
 * - PE TTM: < 20 → green (低估), > 40 → red (高估), 20–40 → 无色
 * - ROE: > 15% → green (优质), < 8% → red (较差), 8%–15% → 无色
 * - 营收/净利润增长率: > 0 → red (增长), < 0 → green (下降), = 0 → 无色
 *
 * @param metric - 指标名称: 'pe_ttm' | 'pb' | 'roe' | 'revenue_growth' | 'net_profit_growth'
 * @param value - 指标数值，null 时返回空字符串
 * @returns CSS 类名: 'color-green' | 'color-red' | ''
 */
export function getFundamentalColorClass(metric: string, value: number | null): string {
  if (value === null || value === undefined) return ''

  switch (metric) {
    case 'pe_ttm':
      if (value < 20) return 'color-green'
      if (value > 40) return 'color-red'
      return ''

    case 'roe':
      if (value > 15) return 'color-green'
      if (value < 8) return 'color-red'
      return ''

    case 'revenue_growth':
    case 'net_profit_growth':
      if (value > 0) return 'color-red'
      if (value < 0) return 'color-green'
      return ''

    default:
      return ''
  }
}

/**
 * 格式化基本面指标数值
 *
 * @param metric - 指标名称
 * @param value - 指标数值
 * @returns 格式化后的字符串
 */
export function formatFundamentalValue(metric: string, value: number | null): string {
  if (value === null || value === undefined) return '--'

  switch (metric) {
    case 'pe_ttm':
    case 'pb':
      return value.toFixed(2)

    case 'roe':
    case 'revenue_growth':
    case 'net_profit_growth':
      return value.toFixed(2) + '%'

    case 'market_cap':
      return value.toFixed(2) + ' 亿'

    default:
      return String(value)
  }
}
