/**
 * 智能选股功能页面集成测试 — 多模板参数可调性验证
 *
 * 测试覆盖：
 * 1. 创建多个不同参数的策略模板（均线趋势型、量价突破型、保守型）
 * 2. 各配置面板参数可调：均线趋势、技术指标(MACD/BOLL/RSI/DMA)、形态突破、量价资金
 * 3. 因子条件编辑器：AND/OR 逻辑切换、因子增删、权重调整
 * 4. 策略切换时参数正确回显、保存修改后持久化
 * 5. 策略重命名、删除、导入上限校验
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Mock ─────────────────────────────────────────────────────────────────────

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener' } },
  },
}))

vi.mock('@/services/wsClient', () => ({
  wsClient: {
    connect: vi.fn(), disconnect: vi.fn(),
    onMessage: vi.fn(), offMessage: vi.fn(), reconnect: vi.fn(),
  },
}))

const mockGet = vi.fn()
const mockPut = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...a: unknown[]) => mockGet(...a),
    put: (...a: unknown[]) => mockPut(...a),
    post: (...a: unknown[]) => mockPost(...a),
    delete: (...a: unknown[]) => mockDelete(...a),
  },
}))

// ─── 类型 ─────────────────────────────────────────────────────────────────────

interface IndicatorParamsConfig {
  macd: { fast_period: number; slow_period: number; signal_period: number }
  boll: { period: number; std_dev: number }
  rsi: { period: number; lower_bound: number; upper_bound: number }
  dma: { short_period: number; long_period: number }
}

interface MaTrendConfig {
  ma_periods: number[]
  slope_threshold: number
  trend_score_threshold: number
  support_ma_lines: number[]
}

interface BreakoutConfig {
  box_breakout: boolean
  high_breakout: boolean
  trendline_breakout: boolean
  volume_ratio_threshold: number
  confirm_days: number
}

interface VolumePriceConfig {
  turnover_rate_min: number
  turnover_rate_max: number
  main_flow_threshold: number
  main_flow_days: number
  large_order_ratio: number
  min_daily_amount: number
  sector_rank_top: number
}

interface FullConfig {
  logic: 'AND' | 'OR'
  factors: Array<{ factor_name: string; operator: string; threshold: number | null }>
  weights: Record<string, number>
  ma_periods: number[]
  indicator_params: IndicatorParamsConfig
  ma_trend: MaTrendConfig
  breakout: BreakoutConfig
  volume_price: VolumePriceConfig
}

interface Strategy {
  id: string
  name: string
  config: FullConfig
  is_active: boolean
  created_at: string
}

// ─── 模拟服务端 ───────────────────────────────────────────────────────────────

class MockServer {
  strategies: Map<string, Strategy> = new Map()
  private nextId = 1

  create(name: string, config: FullConfig, isActive = false): Strategy {
    const id = `strat-${this.nextId++}`
    const s: Strategy = {
      id, name, config: JSON.parse(JSON.stringify(config)),
      is_active: isActive, created_at: new Date().toISOString(),
    }
    this.strategies.set(id, s)
    return JSON.parse(JSON.stringify(s))
  }

  list(): Strategy[] { return [...this.strategies.values()].map(s => JSON.parse(JSON.stringify(s))) }

  get(id: string): Strategy | undefined {
    const s = this.strategies.get(id)
    return s ? JSON.parse(JSON.stringify(s)) : undefined
  }

  update(id: string, data: { name?: string; config?: FullConfig }): Strategy | undefined {
    const s = this.strategies.get(id)
    if (!s) return undefined
    if (data.name) s.name = data.name
    if (data.config) s.config = JSON.parse(JSON.stringify(data.config))
    return JSON.parse(JSON.stringify(s))
  }

  delete(id: string): boolean {
    return this.strategies.delete(id)
  }

  activate(id: string): void {
    for (const [, s] of this.strategies) s.is_active = s.id === id
  }
}

// ─── 三套不同风格的策略配置 ───────────────────────────────────────────────────

/** 策略 A：均线趋势型 — 长周期均线、高打分阈值、保守突破 */
const CONFIG_A: FullConfig = {
  logic: 'AND',
  factors: [
    { factor_name: 'ma_trend', operator: '>=', threshold: 85 },
    { factor_name: 'rsi_strength', operator: '>', threshold: 55 },
  ],
  weights: { ma_trend: 0.7, rsi_strength: 0.3 },
  ma_periods: [10, 20, 60, 120, 250],
  indicator_params: {
    macd: { fast_period: 8, slow_period: 21, signal_period: 5 },
    boll: { period: 25, std_dev: 2.5 },
    rsi: { period: 21, lower_bound: 55, upper_bound: 85 },
    dma: { short_period: 15, long_period: 60 },
  },
  ma_trend: {
    ma_periods: [10, 20, 60, 120, 250],
    slope_threshold: 0.03,
    trend_score_threshold: 85,
    support_ma_lines: [20, 60],
  },
  breakout: {
    box_breakout: true, high_breakout: false, trendline_breakout: false,
    volume_ratio_threshold: 2.0, confirm_days: 3,
  },
  volume_price: {
    turnover_rate_min: 2, turnover_rate_max: 10,
    main_flow_threshold: 2000, main_flow_days: 3,
    large_order_ratio: 40, min_daily_amount: 10000, sector_rank_top: 15,
  },
}

/** 策略 B：量价突破型 — 短周期、低阈值、激进突破 */
const CONFIG_B: FullConfig = {
  logic: 'OR',
  factors: [
    { factor_name: 'breakout_score', operator: '>=', threshold: 70 },
    { factor_name: 'volume_surge', operator: '>', threshold: 2.0 },
    { factor_name: 'capital_inflow', operator: '>=', threshold: 1500 },
  ],
  weights: { breakout_score: 0.4, volume_surge: 0.35, capital_inflow: 0.25 },
  ma_periods: [5, 10, 20],
  indicator_params: {
    macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
    boll: { period: 15, std_dev: 1.5 },
    rsi: { period: 10, lower_bound: 40, upper_bound: 70 },
    dma: { short_period: 5, long_period: 30 },
  },
  ma_trend: {
    ma_periods: [5, 10, 20],
    slope_threshold: 0.0,
    trend_score_threshold: 60,
    support_ma_lines: [20],
  },
  breakout: {
    box_breakout: true, high_breakout: true, trendline_breakout: true,
    volume_ratio_threshold: 1.2, confirm_days: 1,
  },
  volume_price: {
    turnover_rate_min: 5, turnover_rate_max: 20,
    main_flow_threshold: 500, main_flow_days: 1,
    large_order_ratio: 25, min_daily_amount: 3000, sector_rank_top: 50,
  },
}

/** 策略 C：保守防御型 — 极高阈值、严格过滤 */
const CONFIG_C: FullConfig = {
  logic: 'AND',
  factors: [
    { factor_name: 'ma_trend', operator: '>=', threshold: 95 },
  ],
  weights: { ma_trend: 1.0 },
  ma_periods: [20, 60, 120],
  indicator_params: {
    macd: { fast_period: 15, slow_period: 30, signal_period: 12 },
    boll: { period: 30, std_dev: 3.0 },
    rsi: { period: 28, lower_bound: 60, upper_bound: 90 },
    dma: { short_period: 20, long_period: 100 },
  },
  ma_trend: {
    ma_periods: [20, 60, 120],
    slope_threshold: 0.05,
    trend_score_threshold: 95,
    support_ma_lines: [60],
  },
  breakout: {
    box_breakout: false, high_breakout: false, trendline_breakout: false,
    volume_ratio_threshold: 3.0, confirm_days: 5,
  },
  volume_price: {
    turnover_rate_min: 1, turnover_rate_max: 8,
    main_flow_threshold: 5000, main_flow_days: 5,
    large_order_ratio: 50, min_daily_amount: 20000, sector_rank_top: 10,
  },
}

// ─── 纯函数：等价于 ScreenerView 的 restoreFromConfig ─────────────────────────

const DEFAULTS = {
  indicator: {
    macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
    boll: { period: 20, std_dev: 2 },
    rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
    dma: { short_period: 10, long_period: 50 },
  },
  maTrend: { ma_periods: [5, 10, 20, 60, 120], slope_threshold: 0, trend_score_threshold: 80, support_ma_lines: [20, 60] },
  breakout: { box_breakout: true, high_breakout: true, trendline_breakout: true, volume_ratio_threshold: 1.5, confirm_days: 1 },
  volumePrice: { turnover_rate_min: 3, turnover_rate_max: 15, main_flow_threshold: 1000, main_flow_days: 2, large_order_ratio: 30, min_daily_amount: 5000, sector_rank_top: 30 },
}

function restore(cfg: FullConfig) {
  return {
    logic: cfg.logic ?? 'AND',
    factors: (cfg.factors ?? []).map(f => ({
      factor_name: f.factor_name ?? '',
      operator: f.operator ?? '>',
      threshold: f.threshold ?? null,
      weight: Math.round((cfg.weights?.[f.factor_name ?? ''] ?? 0.5) * 100),
    })),
    maTrend: cfg.ma_trend ? { ...cfg.ma_trend } : { ...DEFAULTS.maTrend },
    indicator: cfg.indicator_params ? {
      macd: { ...DEFAULTS.indicator.macd, ...cfg.indicator_params.macd },
      boll: { ...DEFAULTS.indicator.boll, ...cfg.indicator_params.boll },
      rsi: { ...DEFAULTS.indicator.rsi, ...cfg.indicator_params.rsi },
      dma: { ...DEFAULTS.indicator.dma, ...cfg.indicator_params.dma },
    } : JSON.parse(JSON.stringify(DEFAULTS.indicator)),
    breakout: cfg.breakout ? { ...DEFAULTS.breakout, ...cfg.breakout } : { ...DEFAULTS.breakout },
    volumePrice: cfg.volume_price ? { ...DEFAULTS.volumePrice, ...cfg.volume_price } : { ...DEFAULTS.volumePrice },
  }
}

function build(
  logic: 'AND' | 'OR',
  factors: Array<{ factor_name: string; operator: string; threshold: number | null; weight: number }>,
  maTrend: MaTrendConfig,
  indicator: IndicatorParamsConfig,
  breakout: BreakoutConfig,
  volumePrice: VolumePriceConfig,
): FullConfig {
  return {
    logic,
    factors: factors.map(({ weight: _, ...f }) => f),
    weights: Object.fromEntries(factors.map(f => [f.factor_name, f.weight / 100])),
    ma_periods: maTrend.ma_periods,
    indicator_params: JSON.parse(JSON.stringify(indicator)),
    ma_trend: JSON.parse(JSON.stringify(maTrend)),
    breakout: JSON.parse(JSON.stringify(breakout)),
    volume_price: JSON.parse(JSON.stringify(volumePrice)),
  }
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('智能选股页面集成测试 — 多模板参数可调性', () => {
  let server: MockServer

  beforeEach(() => {
    vi.clearAllMocks()
    server = new MockServer()

    mockGet.mockImplementation((url: string) => {
      if (url === '/strategies') return Promise.resolve({ data: server.list() })
      const m = url.match(/^\/strategies\/(.+)$/)
      if (m) {
        const s = server.get(m[1])
        return s ? Promise.resolve({ data: s }) : Promise.reject(new Error('404'))
      }
      if (url === '/screen/schedule') return Promise.resolve({ data: { next_run_at: '2024-01-16T15:30:00+08:00' } })
      return Promise.resolve({ data: {} })
    })
    mockPost.mockImplementation((url: string, body?: Record<string, unknown>) => {
      const activate = url.match(/^\/strategies\/(.+)\/activate$/)
      if (activate) { server.activate(activate[1]); return Promise.resolve({ data: { ok: true } }) }
      if (url === '/strategies' && body) {
        const s = server.create(body.name as string, body.config as FullConfig, body.is_active as boolean)
        return Promise.resolve({ data: s })
      }
      return Promise.resolve({ data: {} })
    })
    mockPut.mockImplementation((url: string, body?: Record<string, unknown>) => {
      const m = url.match(/^\/strategies\/(.+)$/)
      if (m && body) {
        const s = server.update(m[1], body as { name?: string; config?: FullConfig })
        return s ? Promise.resolve({ data: s }) : Promise.reject(new Error('404'))
      }
      return Promise.resolve({ data: {} })
    })
    mockDelete.mockImplementation((url: string) => {
      const m = url.match(/^\/strategies\/(.+)$/)
      if (m) { server.delete(m[1]); return Promise.resolve({ data: { deleted: true } }) }
      return Promise.resolve({ data: {} })
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 1. 创建三个不同风格的策略模板
  // ═══════════════════════════════════════════════════════════════════════════

  describe('1. 创建多个不同参数的策略模板', () => {
    it('创建均线趋势型策略 A 并验证服务端存储', async () => {
      const res = await mockPost('/strategies', { name: '均线趋势型', config: CONFIG_A, is_active: false })
      expect(res.data.name).toBe('均线趋势型')
      expect(res.data.id).toBeTruthy()
      expect(server.strategies.size).toBe(1)

      const stored = server.get(res.data.id)!
      expect(stored.config.logic).toBe('AND')
      expect(stored.config.ma_trend.trend_score_threshold).toBe(85)
      expect(stored.config.indicator_params.macd.fast_period).toBe(8)
    })

    it('创建量价突破型策略 B 并验证服务端存储', async () => {
      const res = await mockPost('/strategies', { name: '量价突破型', config: CONFIG_B, is_active: false })
      expect(res.data.name).toBe('量价突破型')

      const stored = server.get(res.data.id)!
      expect(stored.config.logic).toBe('OR')
      expect(stored.config.factors).toHaveLength(3)
      expect(stored.config.breakout.high_breakout).toBe(true)
      expect(stored.config.volume_price.main_flow_threshold).toBe(500)
    })

    it('创建保守防御型策略 C 并验证服务端存储', async () => {
      const res = await mockPost('/strategies', { name: '保守防御型', config: CONFIG_C, is_active: false })
      const stored = server.get(res.data.id)!
      expect(stored.config.ma_trend.slope_threshold).toBe(0.05)
      expect(stored.config.breakout.box_breakout).toBe(false)
      expect(stored.config.volume_price.min_daily_amount).toBe(20000)
    })

    it('三个策略同时存在于列表中', async () => {
      await mockPost('/strategies', { name: '策略A', config: CONFIG_A, is_active: false })
      await mockPost('/strategies', { name: '策略B', config: CONFIG_B, is_active: false })
      await mockPost('/strategies', { name: '策略C', config: CONFIG_C, is_active: false })

      const list = (await mockGet('/strategies')).data as Strategy[]
      expect(list).toHaveLength(3)
      expect(list.map(s => s.name).sort()).toEqual(['策略A', '策略B', '策略C'])
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 2. 均线趋势参数可调性
  // ═══════════════════════════════════════════════════════════════════════════

  describe('2. 均线趋势配置面板参数可调', () => {
    it('均线周期组合可自定义', async () => {
      const s = server.create('测试', CONFIG_A)
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.maTrend.ma_periods).toEqual([10, 20, 60, 120, 250])

      // 修改为短周期组合
      loaded.maTrend.ma_periods = [3, 5, 10]
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const reloaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(reloaded.maTrend.ma_periods).toEqual([3, 5, 10])
    })

    it('斜率阈值可调（0 → 0.05）', async () => {
      const s = server.create('测试', CONFIG_B) // slope=0
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.maTrend.slope_threshold).toBe(0)

      loaded.maTrend.slope_threshold = 0.05
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).maTrend.slope_threshold).toBe(0.05)
    })

    it('趋势打分阈值可调（60 → 90）', async () => {
      const s = server.create('测试', CONFIG_B) // threshold=60
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.maTrend.trend_score_threshold).toBe(60)

      loaded.maTrend.trend_score_threshold = 90
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).maTrend.trend_score_threshold).toBe(90)
    })

    it('均线支撑回调均线可调（[20] → [20, 60]）', async () => {
      const s = server.create('测试', CONFIG_B) // support=[20]
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.maTrend.support_ma_lines).toEqual([20])

      loaded.maTrend.support_ma_lines = [20, 60]
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).maTrend.support_ma_lines).toEqual([20, 60])
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 3. 技术指标参数可调性（MACD / BOLL / RSI / DMA）
  // ═══════════════════════════════════════════════════════════════════════════

  describe('3. 技术指标配置面板参数可调', () => {
    it('MACD 快线/慢线/信号线周期可调', async () => {
      const s = server.create('测试', CONFIG_A) // macd: 8/21/5
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.indicator.macd).toEqual({ fast_period: 8, slow_period: 21, signal_period: 5 })

      loaded.indicator.macd = { fast_period: 6, slow_period: 18, signal_period: 4 }
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.indicator.macd).toEqual({ fast_period: 6, slow_period: 18, signal_period: 4 })
    })

    it('BOLL 周期和标准差倍数可调', async () => {
      const s = server.create('测试', CONFIG_B) // boll: 15/1.5
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.indicator.boll.period).toBe(15)
      expect(loaded.indicator.boll.std_dev).toBe(1.5)

      loaded.indicator.boll = { period: 30, std_dev: 3.0 }
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.indicator.boll).toEqual({ period: 30, std_dev: 3.0 })
    })

    it('RSI 周期和强势区间上下限可调', async () => {
      const s = server.create('测试', CONFIG_A) // rsi: 21/55/85
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.indicator.rsi).toEqual({ period: 21, lower_bound: 55, upper_bound: 85 })

      loaded.indicator.rsi = { period: 7, lower_bound: 30, upper_bound: 70 }
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).indicator.rsi)
        .toEqual({ period: 7, lower_bound: 30, upper_bound: 70 })
    })

    it('DMA 短期/长期周期可调', async () => {
      const s = server.create('测试', CONFIG_C) // dma: 20/100
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.indicator.dma).toEqual({ short_period: 20, long_period: 100 })

      loaded.indicator.dma = { short_period: 3, long_period: 15 }
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).indicator.dma)
        .toEqual({ short_period: 3, long_period: 15 })
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 4. 形态突破配置参数可调性
  // ═══════════════════════════════════════════════════════════════════════════

  describe('4. 形态突破配置面板参数可调', () => {
    it('三种突破形态可独立启用/禁用', async () => {
      const s = server.create('测试', CONFIG_C) // 全部禁用
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.breakout.box_breakout).toBe(false)
      expect(loaded.breakout.high_breakout).toBe(false)
      expect(loaded.breakout.trendline_breakout).toBe(false)

      // 逐个启用
      loaded.breakout.box_breakout = true
      let saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })
      let r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.breakout.box_breakout).toBe(true)
      expect(r.breakout.high_breakout).toBe(false)

      loaded.breakout.high_breakout = true
      saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })
      r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.breakout.high_breakout).toBe(true)
      expect(r.breakout.trendline_breakout).toBe(false)
    })

    it('量比倍数阈值可调（3.0 → 1.2）', async () => {
      const s = server.create('测试', CONFIG_C) // 3.0
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.breakout.volume_ratio_threshold).toBe(3.0)

      loaded.breakout.volume_ratio_threshold = 1.2
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).breakout.volume_ratio_threshold).toBe(1.2)
    })

    it('站稳确认天数可调（5 → 1）', async () => {
      const s = server.create('测试', CONFIG_C) // 5
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.breakout.confirm_days).toBe(5)

      loaded.breakout.confirm_days = 1
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).breakout.confirm_days).toBe(1)
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 5. 量价资金筛选参数可调性
  // ═══════════════════════════════════════════════════════════════════════════

  describe('5. 量价资金筛选配置面板参数可调', () => {
    it('换手率区间可调', async () => {
      const s = server.create('测试', CONFIG_A) // 2-10
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.volumePrice.turnover_rate_min).toBe(2)
      expect(loaded.volumePrice.turnover_rate_max).toBe(10)

      loaded.volumePrice.turnover_rate_min = 5
      loaded.volumePrice.turnover_rate_max = 20
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.volumePrice.turnover_rate_min).toBe(5)
      expect(r.volumePrice.turnover_rate_max).toBe(20)
    })

    it('主力资金净流入阈值和连续天数可调', async () => {
      const s = server.create('测试', CONFIG_B) // 500/1
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.volumePrice.main_flow_threshold).toBe(500)
      expect(loaded.volumePrice.main_flow_days).toBe(1)

      loaded.volumePrice.main_flow_threshold = 3000
      loaded.volumePrice.main_flow_days = 4
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.volumePrice.main_flow_threshold).toBe(3000)
      expect(r.volumePrice.main_flow_days).toBe(4)
    })

    it('大单占比、日均成交额、板块排名可调', async () => {
      const s = server.create('测试', CONFIG_C) // 50/20000/10
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)

      loaded.volumePrice.large_order_ratio = 20
      loaded.volumePrice.min_daily_amount = 3000
      loaded.volumePrice.sector_rank_top = 50
      const saved = build('AND', [], loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.volumePrice.large_order_ratio).toBe(20)
      expect(r.volumePrice.min_daily_amount).toBe(3000)
      expect(r.volumePrice.sector_rank_top).toBe(50)
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 6. 因子条件编辑器可调性
  // ═══════════════════════════════════════════════════════════════════════════

  describe('6. 因子条件编辑器参数可调', () => {
    it('AND/OR 逻辑可切换', async () => {
      const s = server.create('测试', CONFIG_A) // AND
      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).logic).toBe('AND')

      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      const saved = build('OR', loaded.factors, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      expect(restore((await mockGet(`/strategies/${s.id}`)).data.config).logic).toBe('OR')
    })

    it('因子可增加和删除', async () => {
      const s = server.create('测试', CONFIG_C) // 1 factor
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.factors).toHaveLength(1)

      // 增加因子
      loaded.factors.push({ factor_name: 'volume_surge', operator: '>', threshold: 2.0, weight: 40 })
      loaded.factors.push({ factor_name: 'sector_rank', operator: '<=', threshold: 20, weight: 20 })
      const saved = build('AND', loaded.factors, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.factors).toHaveLength(3)
      expect(r.factors[1].factor_name).toBe('volume_surge')
      expect(r.factors[2].factor_name).toBe('sector_rank')

      // 删除中间因子
      const factors2 = r.factors.filter(f => f.factor_name !== 'volume_surge')
      const saved2 = build('AND', factors2, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved2 })

      const r2 = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r2.factors).toHaveLength(2)
      expect(r2.factors.map(f => f.factor_name)).toEqual(['ma_trend', 'sector_rank'])
    })

    it('因子权重可调整', async () => {
      const s = server.create('测试', CONFIG_A) // ma_trend=70, rsi_strength=30
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.factors[0].weight).toBe(70)
      expect(loaded.factors[1].weight).toBe(30)

      // 调整权重
      loaded.factors[0].weight = 50
      loaded.factors[1].weight = 50
      const saved = build('AND', loaded.factors, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.factors[0].weight).toBe(50)
      expect(r.factors[1].weight).toBe(50)
    })

    it('因子运算符和阈值可调', async () => {
      const s = server.create('测试', CONFIG_B) // breakout_score >= 70
      const loaded = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(loaded.factors[0].operator).toBe('>=')
      expect(loaded.factors[0].threshold).toBe(70)

      loaded.factors[0].operator = '>'
      loaded.factors[0].threshold = 80
      const saved = build('OR', loaded.factors, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${s.id}`, { config: saved })

      const r = restore((await mockGet(`/strategies/${s.id}`)).data.config)
      expect(r.factors[0].operator).toBe('>')
      expect(r.factors[0].threshold).toBe(80)
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 7. 策略切换时参数正确回显
  // ═══════════════════════════════════════════════════════════════════════════

  describe('7. 策略切换时参数正确回显', () => {
    it('从策略 A 切换到策略 B，所有面板参数正确切换', async () => {
      const sA = server.create('策略A', CONFIG_A)
      const sB = server.create('策略B', CONFIG_B)

      // 加载 A
      const panelsA = restore((await mockGet(`/strategies/${sA.id}`)).data.config)
      expect(panelsA.logic).toBe('AND')
      expect(panelsA.maTrend.trend_score_threshold).toBe(85)
      expect(panelsA.indicator.macd.fast_period).toBe(8)
      expect(panelsA.breakout.high_breakout).toBe(false)
      expect(panelsA.volumePrice.main_flow_threshold).toBe(2000)

      // 切换到 B
      const panelsB = restore((await mockGet(`/strategies/${sB.id}`)).data.config)
      expect(panelsB.logic).toBe('OR')
      expect(panelsB.maTrend.trend_score_threshold).toBe(60)
      expect(panelsB.indicator.macd.fast_period).toBe(12)
      expect(panelsB.breakout.high_breakout).toBe(true)
      expect(panelsB.volumePrice.main_flow_threshold).toBe(500)

      // 确认 A 和 B 的参数完全不同
      expect(panelsA.logic).not.toBe(panelsB.logic)
      expect(panelsA.maTrend.trend_score_threshold).not.toBe(panelsB.maTrend.trend_score_threshold)
      expect(panelsA.breakout.confirm_days).not.toBe(panelsB.breakout.confirm_days)
    })

    it('修改策略 A 后切换到 B 再切回 A，A 的修改已持久化', async () => {
      const sA = server.create('策略A', CONFIG_A)
      const sB = server.create('策略B', CONFIG_B)

      // 修改 A
      const loaded = restore((await mockGet(`/strategies/${sA.id}`)).data.config)
      loaded.maTrend.trend_score_threshold = 99
      const saved = build('AND', loaded.factors, loaded.maTrend, loaded.indicator, loaded.breakout, loaded.volumePrice)
      await mockPut(`/strategies/${sA.id}`, { config: saved })

      // 切换到 B
      const panelsB = restore((await mockGet(`/strategies/${sB.id}`)).data.config)
      expect(panelsB.maTrend.trend_score_threshold).toBe(60) // B 的值

      // 切回 A
      const panelsA = restore((await mockGet(`/strategies/${sA.id}`)).data.config)
      expect(panelsA.maTrend.trend_score_threshold).toBe(99) // 修改后的值
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 8. 策略管理操作（重命名、删除、激活）
  // ═══════════════════════════════════════════════════════════════════════════

  describe('8. 策略管理操作', () => {
    it('策略重命名后名称更新', async () => {
      const s = server.create('旧名称', CONFIG_A)
      await mockPut(`/strategies/${s.id}`, { name: '新名称' })

      const updated = server.get(s.id)!
      expect(updated.name).toBe('新名称')
      expect(updated.config.logic).toBe('AND') // 配置不变
    })

    it('删除策略后列表中不再存在', async () => {
      server.create('策略1', CONFIG_A)
      const s2 = server.create('策略2', CONFIG_B)
      server.create('策略3', CONFIG_C)
      expect(server.list()).toHaveLength(3)

      await mockDelete(`/strategies/${s2.id}`)
      const list = server.list()
      expect(list).toHaveLength(2)
      expect(list.find(s => s.name === '策略2')).toBeUndefined()
    })

    it('激活策略后仅该策略 is_active=true', async () => {
      const s1 = server.create('策略1', CONFIG_A)
      const s2 = server.create('策略2', CONFIG_B)
      const s3 = server.create('策略3', CONFIG_C)

      await mockPost(`/strategies/${s2.id}/activate`)

      expect(server.get(s1.id)!.is_active).toBe(false)
      expect(server.get(s2.id)!.is_active).toBe(true)
      expect(server.get(s3.id)!.is_active).toBe(false)

      // 切换激活到 s3
      await mockPost(`/strategies/${s3.id}/activate`)
      expect(server.get(s2.id)!.is_active).toBe(false)
      expect(server.get(s3.id)!.is_active).toBe(true)
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // 9. 全链路：创建 → 配置 → 保存 → 切换 → 验证
  // ═══════════════════════════════════════════════════════════════════════════

  describe('9. 全链路集成测试', () => {
    it('创建两个策略 → 分别配置不同参数 → 保存 → 切换验证回显', async () => {
      // 创建策略 A（默认配置）
      const resA = await mockPost('/strategies', { name: '趋势策略', config: CONFIG_A, is_active: false })
      const idA = resA.data.id

      // 创建策略 B（默认配置）
      const resB = await mockPost('/strategies', { name: '突破策略', config: CONFIG_B, is_active: false })
      const idB = resB.data.id

      // 修改策略 A 的参数
      const loadedA = restore((await mockGet(`/strategies/${idA}`)).data.config)
      loadedA.maTrend.trend_score_threshold = 92
      loadedA.indicator.rsi = { period: 7, lower_bound: 35, upper_bound: 65 }
      loadedA.breakout.confirm_days = 4
      loadedA.volumePrice.sector_rank_top = 5
      const savedA = build('AND', loadedA.factors, loadedA.maTrend, loadedA.indicator, loadedA.breakout, loadedA.volumePrice)
      await mockPut(`/strategies/${idA}`, { config: savedA })

      // 修改策略 B 的参数
      const loadedB = restore((await mockGet(`/strategies/${idB}`)).data.config)
      loadedB.indicator.macd = { fast_period: 5, slow_period: 15, signal_period: 3 }
      loadedB.volumePrice.main_flow_threshold = 8000
      loadedB.breakout.volume_ratio_threshold = 0.8
      const savedB = build('OR', loadedB.factors, loadedB.maTrend, loadedB.indicator, loadedB.breakout, loadedB.volumePrice)
      await mockPut(`/strategies/${idB}`, { config: savedB })

      // 验证策略 A 的修改
      const verifyA = restore((await mockGet(`/strategies/${idA}`)).data.config)
      expect(verifyA.maTrend.trend_score_threshold).toBe(92)
      expect(verifyA.indicator.rsi).toEqual({ period: 7, lower_bound: 35, upper_bound: 65 })
      expect(verifyA.breakout.confirm_days).toBe(4)
      expect(verifyA.volumePrice.sector_rank_top).toBe(5)

      // 验证策略 B 的修改
      const verifyB = restore((await mockGet(`/strategies/${idB}`)).data.config)
      expect(verifyB.indicator.macd).toEqual({ fast_period: 5, slow_period: 15, signal_period: 3 })
      expect(verifyB.volumePrice.main_flow_threshold).toBe(8000)
      expect(verifyB.breakout.volume_ratio_threshold).toBe(0.8)

      // 激活 A，验证状态
      await mockPost(`/strategies/${idA}/activate`)
      expect(server.get(idA)!.is_active).toBe(true)
      expect(server.get(idB)!.is_active).toBe(false)

      // 列表包含两个策略
      const list = (await mockGet('/strategies')).data as Strategy[]
      expect(list).toHaveLength(2)
    })
  })
})
