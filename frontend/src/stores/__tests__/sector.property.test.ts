/**
 * 板块排行项显示格式化属性测试
 *
 * Feature: sector-ranking-display, Property 5: Ranking item display formatting
 *
 * 对任意 SectorRankingItem 数据，验证涨跌幅、成交额、换手率、收盘价的
 * 格式化输出和 CSS class 分配符合需求规范。
 *
 * **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import type { SectorRankingItem } from '@/stores/sector'

// ─── 格式化纯函数（提取自 DashboardView.vue 模板内联逻辑）─────────────────────

/**
 * 格式化涨跌幅：正值 "+" 前缀、两位小数、"%" 后缀；null 返回 "--"
 */
function formatChangePct(change_pct: number | null): string {
  if (change_pct == null) return '--'
  return (change_pct >= 0 ? '+' : '') + change_pct.toFixed(2) + '%'
}

/**
 * 获取涨跌幅 CSS class：>= 0 为 'up'，< 0 为 'down'；null 视为 0 → 'up'
 */
function getChangePctClass(change_pct: number | null): 'up' | 'down' {
  return (change_pct ?? 0) >= 0 ? 'up' : 'down'
}

/**
 * 格式化成交额：以亿为单位（amount / 1e8），两位小数；null 返回 "--"
 */
function formatAmount(amount: number | null): string {
  if (amount == null) return '--'
  return (amount / 1e8).toFixed(2)
}

/**
 * 格式化换手率：两位小数 + "%" 后缀；null 返回 "--"
 */
function formatTurnover(turnover: number | null): string {
  if (turnover == null) return '--'
  return turnover.toFixed(2) + '%'
}

/**
 * 格式化收盘价：两位小数；null 返回 "--"
 */
function formatClose(close: number | null): string {
  if (close == null) return '--'
  return close.toFixed(2)
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成 JSON 安全的 double（排除 NaN、Infinity） */
const safeDouble = fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true })

/** 生成可空的 double */
const nullableDouble = fc.option(safeDouble, { nil: null })

/** 生成随机 SectorRankingItem */
const sectorRankingItemArb: fc.Arbitrary<SectorRankingItem> = fc.record({
  sector_code: fc.string({ minLength: 1, maxLength: 10 }),
  name: fc.string({ minLength: 1, maxLength: 20 }),
  sector_type: fc.constantFrom('CONCEPT', 'INDUSTRY', 'REGION', 'STYLE'),
  change_pct: nullableDouble,
  close: nullableDouble,
  volume: fc.option(fc.integer({ min: 0, max: 1e9 }), { nil: null }),
  amount: nullableDouble,
  turnover: nullableDouble,
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: sector-ranking-display, Property 5: Ranking item display formatting', () => {
  /**
   * 涨跌幅格式化：正值有 "+" 前缀、两位小数、"%" 后缀
   * Validates: Requirements 4.2, 4.3
   */
  it('非空 change_pct 格式化包含正确前缀、两位小数和 % 后缀', () => {
    fc.assert(
      fc.property(safeDouble, (changePct) => {
        const formatted = formatChangePct(changePct)

        // 必须以 % 结尾
        expect(formatted.endsWith('%')).toBe(true)

        // 正值必须有 + 前缀
        if (changePct >= 0) {
          expect(formatted.startsWith('+')).toBe(true)
        } else {
          expect(formatted.startsWith('-')).toBe(true)
        }

        // 两位小数：去掉 % 后缀，解析数值应与原值两位小数一致
        const numericPart = formatted.slice(0, -1) // 去掉 %
        const parsed = parseFloat(numericPart)
        expect(parsed).toBeCloseTo(changePct, 2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 涨跌幅 CSS class：>= 0 为 'up'，< 0 为 'down'
   * Validates: Requirements 4.2
   */
  it('change_pct CSS class 正确分配 up/down', () => {
    fc.assert(
      fc.property(nullableDouble, (changePct) => {
        const cssClass = getChangePctClass(changePct)

        if (changePct == null || changePct >= 0) {
          expect(cssClass).toBe('up')
        } else {
          expect(cssClass).toBe('down')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 成交额亿元转换：amount / 1e8，两位小数
   * Validates: Requirements 4.4
   */
  it('非空 amount 正确转换为亿元并保留两位小数', () => {
    fc.assert(
      fc.property(safeDouble, (amount) => {
        const formatted = formatAmount(amount)
        const expected = (amount / 1e8).toFixed(2)
        expect(formatted).toBe(expected)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 换手率格式化：两位小数 + "%" 后缀
   * Validates: Requirements 4.5
   */
  it('非空 turnover 格式化为两位小数加 % 后缀', () => {
    fc.assert(
      fc.property(safeDouble, (turnover) => {
        const formatted = formatTurnover(turnover)

        expect(formatted.endsWith('%')).toBe(true)

        const numericPart = formatted.slice(0, -1)
        const parsed = parseFloat(numericPart)
        expect(parsed).toBeCloseTo(turnover, 2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 空值占位符：null 字段显示 "--"
   * Validates: Requirements 4.6
   */
  it('null 字段统一显示 "--" 占位符', () => {
    fc.assert(
      fc.property(sectorRankingItemArb, (item) => {
        if (item.change_pct == null) {
          expect(formatChangePct(item.change_pct)).toBe('--')
        }
        if (item.close == null) {
          expect(formatClose(item.close)).toBe('--')
        }
        if (item.amount == null) {
          expect(formatAmount(item.amount)).toBe('--')
        }
        if (item.turnover == null) {
          expect(formatTurnover(item.turnover)).toBe('--')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 收盘价格式化：两位小数；null 返回 "--"
   * Validates: Requirements 4.6
   */
  it('非空 close 格式化为两位小数', () => {
    fc.assert(
      fc.property(safeDouble, (close) => {
        const formatted = formatClose(close)
        const expected = close.toFixed(2)
        expect(formatted).toBe(expected)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 综合验证：对任意 SectorRankingItem，所有格式化函数输出类型一致
   * Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6
   */
  it('任意 SectorRankingItem 的所有字段格式化输出均为字符串', () => {
    fc.assert(
      fc.property(sectorRankingItemArb, (item) => {
        expect(typeof formatChangePct(item.change_pct)).toBe('string')
        expect(typeof getChangePctClass(item.change_pct)).toBe('string')
        expect(typeof formatClose(item.close)).toBe('string')
        expect(typeof formatAmount(item.amount)).toBe('string')
        expect(typeof formatTurnover(item.turnover)).toBe('string')
      }),
      { numRuns: 100 },
    )
  })
})


// ─── Property 10: Browser tab state isolation ─────────────────────────────────

/**
 * 浏览面板标签页状态隔离属性测试
 *
 * Feature: sector-ranking-display, Property 10: Browser tab state isolation
 *
 * 对任意标签页切换序列，验证 setBrowserTab 仅修改 browserActiveTab，
 * 不影响任何标签页的 items、total、page、filters、loading、error 状态。
 *
 * **Validates: Requirements 14.2, 14.3**
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach } from 'vitest'
import { useSectorStore, type BrowserTab } from '@/stores/sector'

describe('Feature: sector-ranking-display, Property 10: Browser tab state isolation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * 随机标签页切换序列不影响任何标签页的数据状态
   * Validates: Requirements 14.2, 14.3
   */
  it('setBrowserTab 仅修改 browserActiveTab，不影响各标签页的 items/total/page/filters/loading/error', () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom<BrowserTab>('info', 'constituent', 'kline'), { minLength: 1, maxLength: 20 }),
        (tabSequence) => {
          // 每次迭代创建新的 pinia 实例以隔离状态
          setActivePinia(createPinia())
          const store = useSectorStore()

          // 设置各标签页的初始状态（模拟已有数据）
          store.infoBrowse.items = [
            { sector_code: 'BK0001', name: '测试板块', sector_type: 'CONCEPT', data_source: 'DC', list_date: '2024-01-01', constituent_count: 10 },
          ]
          store.infoBrowse.total = 100
          store.infoBrowse.page = 3
          store.infoBrowse.loading = false
          store.infoBrowse.error = '测试错误'
          store.infoBrowse.filters = { data_source: 'TI', sector_type: 'INDUSTRY', keyword: '银行' }

          store.constituentBrowse.items = [
            { trade_date: '2024-06-01', sector_code: 'BK0002', data_source: 'DC', symbol: '600000', stock_name: '浦发银行' },
          ]
          store.constituentBrowse.total = 200
          store.constituentBrowse.page = 5
          store.constituentBrowse.loading = false
          store.constituentBrowse.error = ''
          store.constituentBrowse.filters = { data_source: 'DC', sector_code: 'BK0002', trade_date: '2024-06-01', keyword: '' }

          store.klineBrowse.items = [
            { time: '2024-06-01', sector_code: 'BK0003', data_source: 'TDX', freq: '1d', open: 100, high: 110, low: 95, close: 105, volume: 1000, amount: 50000, change_pct: 2.5 },
          ]
          store.klineBrowse.total = 300
          store.klineBrowse.page = 7
          store.klineBrowse.loading = false
          store.klineBrowse.error = 'K线错误'
          store.klineBrowse.filters = { data_source: 'TDX', sector_code: 'BK0003', freq: '1w', start: '2024-01-01', end: '2024-06-30' }

          // 快照各标签页状态
          const infoSnapshot = {
            items: JSON.parse(JSON.stringify(store.infoBrowse.items)),
            total: store.infoBrowse.total,
            page: store.infoBrowse.page,
            loading: store.infoBrowse.loading,
            error: store.infoBrowse.error,
            filters: { ...store.infoBrowse.filters },
          }
          const constituentSnapshot = {
            items: JSON.parse(JSON.stringify(store.constituentBrowse.items)),
            total: store.constituentBrowse.total,
            page: store.constituentBrowse.page,
            loading: store.constituentBrowse.loading,
            error: store.constituentBrowse.error,
            filters: { ...store.constituentBrowse.filters },
          }
          const klineSnapshot = {
            items: JSON.parse(JSON.stringify(store.klineBrowse.items)),
            total: store.klineBrowse.total,
            page: store.klineBrowse.page,
            loading: store.klineBrowse.loading,
            error: store.klineBrowse.error,
            filters: { ...store.klineBrowse.filters },
          }

          // 执行随机标签页切换序列
          for (const tab of tabSequence) {
            store.setBrowserTab(tab)
          }

          // 验证最终 browserActiveTab 等于序列中最后一个标签页
          expect(store.browserActiveTab).toBe(tabSequence[tabSequence.length - 1])

          // 验证各标签页状态未被修改
          expect(JSON.parse(JSON.stringify(store.infoBrowse.items))).toEqual(infoSnapshot.items)
          expect(store.infoBrowse.total).toBe(infoSnapshot.total)
          expect(store.infoBrowse.page).toBe(infoSnapshot.page)
          expect(store.infoBrowse.loading).toBe(infoSnapshot.loading)
          expect(store.infoBrowse.error).toBe(infoSnapshot.error)
          expect({ ...store.infoBrowse.filters }).toEqual(infoSnapshot.filters)

          expect(JSON.parse(JSON.stringify(store.constituentBrowse.items))).toEqual(constituentSnapshot.items)
          expect(store.constituentBrowse.total).toBe(constituentSnapshot.total)
          expect(store.constituentBrowse.page).toBe(constituentSnapshot.page)
          expect(store.constituentBrowse.loading).toBe(constituentSnapshot.loading)
          expect(store.constituentBrowse.error).toBe(constituentSnapshot.error)
          expect({ ...store.constituentBrowse.filters }).toEqual(constituentSnapshot.filters)

          expect(JSON.parse(JSON.stringify(store.klineBrowse.items))).toEqual(klineSnapshot.items)
          expect(store.klineBrowse.total).toBe(klineSnapshot.total)
          expect(store.klineBrowse.page).toBe(klineSnapshot.page)
          expect(store.klineBrowse.loading).toBe(klineSnapshot.loading)
          expect(store.klineBrowse.error).toBe(klineSnapshot.error)
          expect({ ...store.klineBrowse.filters }).toEqual(klineSnapshot.filters)
        },
      ),
      { numRuns: 100 },
    )
  })
})
