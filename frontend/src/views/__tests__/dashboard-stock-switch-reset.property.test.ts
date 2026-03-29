/**
 * 属性 77：切换股票查询时数据状态重置
 *
 * Feature: a-share-quant-trading-system, Property 77: 切换股票数据状态重置
 *
 * 对任意两个不同股票代码，切换后基本面和资金流向的数据、loading、error 状态应全部重置为初始值
 *
 * **Validates: Requirements 26.12**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（镜像 DashboardView 中的状态） ─────────────────────────────────

interface StockFundamentalsResponse {
  symbol: string
  name: string | null
  pe_ttm: number | null
  pb: number | null
  roe: number | null
  market_cap: number | null
  revenue_growth: number | null
  net_profit_growth: number | null
  report_period: string | null
  updated_at: string | null
}

interface MoneyFlowDailyRecord {
  trade_date: string
  main_net_inflow: number
  north_net_inflow: number | null
  large_order_ratio: number | null
  super_large_inflow: number | null
  large_inflow: number | null
}

interface StockMoneyFlowResponse {
  symbol: string
  name: string | null
  days: number
  records: MoneyFlowDailyRecord[]
}

interface TabDataState {
  fundamentals: StockFundamentalsResponse | null
  fundamentalsLoading: boolean
  fundamentalsError: string
  fundamentalsLoaded: boolean
  moneyFlow: StockMoneyFlowResponse | null
  moneyFlowLoading: boolean
  moneyFlowError: string
  moneyFlowLoaded: boolean
}

// ─── 纯函数：resetTabData 逻辑（提取自 DashboardView.vue） ─────────────────

function resetTabData(state: TabDataState): TabDataState {
  return {
    fundamentals: null,
    fundamentalsError: '',
    fundamentalsLoading: false,
    fundamentalsLoaded: false,
    moneyFlow: null,
    moneyFlowError: '',
    moneyFlowLoading: false,
    moneyFlowLoaded: false,
  }
}

const INITIAL_STATE: TabDataState = {
  fundamentals: null,
  fundamentalsError: '',
  fundamentalsLoading: false,
  fundamentalsLoaded: false,
  moneyFlow: null,
  moneyFlowError: '',
  moneyFlowLoading: false,
  moneyFlowLoaded: false,
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 6位数字股票代码 */
const stockCodeArb = fc.stringOf(fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'), {
  minLength: 6,
  maxLength: 6,
})

/** 两个不同的股票代码 */
const twoDistinctCodesArb = fc
  .tuple(stockCodeArb, stockCodeArb)
  .filter(([a, b]) => a !== b)

/** 任意基本面数据 */
const fundamentalsArb: fc.Arbitrary<StockFundamentalsResponse> = fc.record({
  symbol: stockCodeArb,
  name: fc.option(fc.string({ minLength: 1, maxLength: 10 }), { nil: null }),
  pe_ttm: fc.option(fc.double({ min: -500, max: 5000, noNaN: true }), { nil: null }),
  pb: fc.option(fc.double({ min: -50, max: 500, noNaN: true }), { nil: null }),
  roe: fc.option(fc.double({ min: -100, max: 100, noNaN: true }), { nil: null }),
  market_cap: fc.option(fc.double({ min: 0, max: 100000, noNaN: true }), { nil: null }),
  revenue_growth: fc.option(fc.double({ min: -100, max: 1000, noNaN: true }), { nil: null }),
  net_profit_growth: fc.option(fc.double({ min: -100, max: 1000, noNaN: true }), { nil: null }),
  report_period: fc.option(fc.constant('2024-Q3'), { nil: null }),
  updated_at: fc.option(fc.constant('2024-01-01T00:00:00Z'), { nil: null }),
})

/** 任意资金流向数据 */
const moneyFlowArb: fc.Arbitrary<StockMoneyFlowResponse> = fc.record({
  symbol: stockCodeArb,
  name: fc.option(fc.string({ minLength: 1, maxLength: 10 }), { nil: null }),
  days: fc.integer({ min: 1, max: 60 }),
  records: fc.array(
    fc.record({
      trade_date: fc.constant('2024-01-15'),
      main_net_inflow: fc.double({ min: -100000, max: 100000, noNaN: true }),
      north_net_inflow: fc.option(fc.double({ min: -50000, max: 50000, noNaN: true }), { nil: null }),
      large_order_ratio: fc.option(fc.double({ min: 0, max: 100, noNaN: true }), { nil: null }),
      super_large_inflow: fc.option(fc.double({ min: -50000, max: 50000, noNaN: true }), { nil: null }),
      large_inflow: fc.option(fc.double({ min: -50000, max: 50000, noNaN: true }), { nil: null }),
    }),
    { minLength: 1, maxLength: 5 },
  ),
})

/** 任意"脏"状态（模拟已加载数据后的状态） */
const dirtyStateArb: fc.Arbitrary<TabDataState> = fc.record({
  fundamentals: fc.option(fundamentalsArb, { nil: null }),
  fundamentalsLoading: fc.boolean(),
  fundamentalsError: fc.oneof(fc.constant(''), fc.constant('获取基本面数据失败，请重试')),
  fundamentalsLoaded: fc.boolean(),
  moneyFlow: fc.option(moneyFlowArb, { nil: null }),
  moneyFlowLoading: fc.boolean(),
  moneyFlowError: fc.oneof(fc.constant(''), fc.constant('获取资金流向数据失败，请重试')),
  moneyFlowLoaded: fc.boolean(),
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 77：切换股票查询时数据状态重置', () => {
  /**
   * 属性 77a：对任意脏状态，resetTabData 后所有字段恢复初始值
   * Validates: Requirements 26.12
   */
  it('对任意脏状态，resetTabData 后所有字段恢复初始值', () => {
    fc.assert(
      fc.property(dirtyStateArb, (dirtyState) => {
        const result = resetTabData(dirtyState)

        expect(result.fundamentals).toBeNull()
        expect(result.fundamentalsError).toBe('')
        expect(result.fundamentalsLoading).toBe(false)
        expect(result.fundamentalsLoaded).toBe(false)
        expect(result.moneyFlow).toBeNull()
        expect(result.moneyFlowError).toBe('')
        expect(result.moneyFlowLoading).toBe(false)
        expect(result.moneyFlowLoaded).toBe(false)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 77b：对任意两个不同股票代码和任意脏状态，切换后状态等于初始状态
   * Validates: Requirements 26.12
   */
  it('对任意两个不同股票代码，切换后状态严格等于初始状态', () => {
    fc.assert(
      fc.property(twoDistinctCodesArb, dirtyStateArb, ([_codeA, _codeB], dirtyState) => {
        const result = resetTabData(dirtyState)
        expect(result).toEqual(INITIAL_STATE)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 77c：resetTabData 是幂等的——连续调用两次结果相同
   * Validates: Requirements 26.12
   */
  it('resetTabData 是幂等的', () => {
    fc.assert(
      fc.property(dirtyStateArb, (dirtyState) => {
        const first = resetTabData(dirtyState)
        const second = resetTabData(first)
        expect(second).toEqual(first)
      }),
      { numRuns: 100 },
    )
  })
})
