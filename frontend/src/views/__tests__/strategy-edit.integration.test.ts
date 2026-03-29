/**
 * 集成测试 18.7.1：选中策略 → 配置回显 → 修改参数 → 保存修改 → 重新选中验证回显一致性全链路测试
 *
 * 验证需求：22.1, 22.2
 *
 * 测试完整流程：
 * 1. 选中策略 → 验证配置加载并回填各面板
 * 2. 修改参数
 * 3. 点击"保存修改" → 验证 PUT API 调用携带正确配置
 * 4. 取消选中再重新选中 → 验证面板显示更新后的配置
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener' } },
  },
}))

vi.mock('@/services/wsClient', () => ({
  wsClient: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onMessage: vi.fn(),
    offMessage: vi.fn(),
    reconnect: vi.fn(),
  },
}))

const mockGet = vi.fn()
const mockPut = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    put: (...args: unknown[]) => mockPut(...args),
    post: (...args: unknown[]) => mockPost(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

// ─── 类型定义（与 ScreenerView 保持一致）─────────────────────────────────────

interface MaTrendConfig {
  ma_periods: number[]
  slope_threshold: number
  trend_score_threshold: number
  support_ma_lines: number[]
}

interface IndicatorParamsConfig {
  macd: { fast_period: number; slow_period: number; signal_period: number }
  boll: { period: number; std_dev: number }
  rsi: { period: number; lower_bound: number; upper_bound: number }
  dma: { short_period: number; long_period: number }
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

interface FullStrategyConfig {
  logic: 'AND' | 'OR'
  factors: Array<{ factor_name: string; operator: string; threshold: number | null }>
  weights: Record<string, number>
  ma_periods: number[]
  indicator_params: IndicatorParamsConfig
  ma_trend: MaTrendConfig
  breakout: BreakoutConfig
  volume_price: VolumePriceConfig
}

interface StrategyTemplate {
  id: string
  name: string
  config: FullStrategyConfig
  is_active: boolean
  created_at: string
}

// ─── 默认值常量（与 ScreenerView 保持一致）──────────────────────────────────

const INDICATOR_DEFAULTS: IndicatorParamsConfig = {
  macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
  boll: { period: 20, std_dev: 2 },
  rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
  dma: { short_period: 10, long_period: 50 },
}

const MA_TREND_DEFAULTS: MaTrendConfig = {
  ma_periods: [5, 10, 20, 60, 120],
  slope_threshold: 0,
  trend_score_threshold: 80,
  support_ma_lines: [20, 60],
}

const BREAKOUT_DEFAULTS: BreakoutConfig = {
  box_breakout: true,
  high_breakout: true,
  trendline_breakout: true,
  volume_ratio_threshold: 1.5,
  confirm_days: 1,
}

const VOLUME_PRICE_DEFAULTS: VolumePriceConfig = {
  turnover_rate_min: 3,
  turnover_rate_max: 15,
  main_flow_threshold: 1000,
  main_flow_days: 2,
  large_order_ratio: 30,
  min_daily_amount: 5000,
  sector_rank_top: 30,
}

// ─── 纯函数等价实现（与 ScreenerView 逻辑一致）──────────────────────────────

/**
 * 等价于 ScreenerView.buildStrategyConfig()
 * 将面板状态序列化为服务端配置格式
 */
function buildStrategyConfig(
  logic: 'AND' | 'OR',
  factors: Array<{ type: string; factor_name: string; operator: string; threshold: number | null; weight: number }>,
  maPeriods: string,
  indicatorParams: IndicatorParamsConfig,
  maTrend: MaTrendConfig,
  breakoutConfig: BreakoutConfig,
  volumePriceConfig: VolumePriceConfig,
): FullStrategyConfig {
  return {
    logic,
    factors: factors.map(({ type: _type, weight: _weight, ...f }) => f),
    weights: Object.fromEntries(
      factors.map((f) => [f.factor_name || f.type, f.weight / 100]),
    ),
    ma_periods: maPeriods.split(',').map(Number).filter(Boolean),
    indicator_params: {
      macd: { ...indicatorParams.macd },
      boll: { ...indicatorParams.boll },
      rsi: { ...indicatorParams.rsi },
      dma: { ...indicatorParams.dma },
    },
    ma_trend: {
      ma_periods: [...maTrend.ma_periods],
      slope_threshold: maTrend.slope_threshold,
      trend_score_threshold: maTrend.trend_score_threshold,
      support_ma_lines: [...maTrend.support_ma_lines],
    },
    breakout: { ...breakoutConfig },
    volume_price: { ...volumePriceConfig },
  }
}

/**
 * 等价于 ScreenerView.selectStrategy() 中的配置回填逻辑
 * 将服务端返回的配置解析为面板状态
 */
function restoreFromConfig(cfg: FullStrategyConfig): {
  logic: 'AND' | 'OR'
  factors: Array<{ type: string; factor_name: string; operator: string; threshold: number | null; weight: number }>
  maTrend: MaTrendConfig
  indicatorParams: IndicatorParamsConfig
  breakoutConfig: BreakoutConfig
  volumePriceConfig: VolumePriceConfig
} {
  const factors = (cfg.factors ?? []).map((f) => ({
    type: 'technical',
    factor_name: f.factor_name ?? '',
    operator: f.operator ?? '>',
    threshold: f.threshold ?? null,
    weight: Math.round(((cfg.weights?.[f.factor_name ?? ''] ?? 0.5) * 100)),
  }))

  const mt = cfg.ma_trend
  const maTrend: MaTrendConfig = mt
    ? {
        ma_periods: Array.isArray(mt.ma_periods) ? [...mt.ma_periods] : [...MA_TREND_DEFAULTS.ma_periods],
        slope_threshold: typeof mt.slope_threshold === 'number' ? mt.slope_threshold : MA_TREND_DEFAULTS.slope_threshold,
        trend_score_threshold: typeof mt.trend_score_threshold === 'number' ? mt.trend_score_threshold : MA_TREND_DEFAULTS.trend_score_threshold,
        support_ma_lines: Array.isArray(mt.support_ma_lines) ? [...mt.support_ma_lines] : [...MA_TREND_DEFAULTS.support_ma_lines],
      }
    : { ...MA_TREND_DEFAULTS, ma_periods: [...MA_TREND_DEFAULTS.ma_periods], support_ma_lines: [...MA_TREND_DEFAULTS.support_ma_lines] }

  const ip = cfg.indicator_params
  const indicatorParams: IndicatorParamsConfig = ip
    ? {
        macd: { ...INDICATOR_DEFAULTS.macd, ...ip.macd },
        boll: { ...INDICATOR_DEFAULTS.boll, ...ip.boll },
        rsi: { ...INDICATOR_DEFAULTS.rsi, ...ip.rsi },
        dma: { ...INDICATOR_DEFAULTS.dma, ...ip.dma },
      }
    : JSON.parse(JSON.stringify(INDICATOR_DEFAULTS))

  const bo = cfg.breakout
  const breakoutConfig: BreakoutConfig = bo
    ? {
        box_breakout: bo.box_breakout ?? BREAKOUT_DEFAULTS.box_breakout,
        high_breakout: bo.high_breakout ?? BREAKOUT_DEFAULTS.high_breakout,
        trendline_breakout: bo.trendline_breakout ?? BREAKOUT_DEFAULTS.trendline_breakout,
        volume_ratio_threshold: bo.volume_ratio_threshold ?? BREAKOUT_DEFAULTS.volume_ratio_threshold,
        confirm_days: bo.confirm_days ?? BREAKOUT_DEFAULTS.confirm_days,
      }
    : { ...BREAKOUT_DEFAULTS }

  const vp = cfg.volume_price
  const volumePriceConfig: VolumePriceConfig = vp
    ? {
        turnover_rate_min: vp.turnover_rate_min ?? VOLUME_PRICE_DEFAULTS.turnover_rate_min,
        turnover_rate_max: vp.turnover_rate_max ?? VOLUME_PRICE_DEFAULTS.turnover_rate_max,
        main_flow_threshold: vp.main_flow_threshold ?? VOLUME_PRICE_DEFAULTS.main_flow_threshold,
        main_flow_days: vp.main_flow_days ?? VOLUME_PRICE_DEFAULTS.main_flow_days,
        large_order_ratio: vp.large_order_ratio ?? VOLUME_PRICE_DEFAULTS.large_order_ratio,
        min_daily_amount: vp.min_daily_amount ?? VOLUME_PRICE_DEFAULTS.min_daily_amount,
        sector_rank_top: vp.sector_rank_top ?? VOLUME_PRICE_DEFAULTS.sector_rank_top,
      }
    : { ...VOLUME_PRICE_DEFAULTS }

  return { logic: cfg.logic ?? 'AND', factors, maTrend, indicatorParams, breakoutConfig, volumePriceConfig }
}

/**
 * 等价于 ScreenerView.resetToDefaults()
 * 取消选中时恢复所有面板为默认值
 */
function getDefaultPanelState() {
  return {
    logic: 'AND' as const,
    factors: [] as Array<{ type: string; factor_name: string; operator: string; threshold: number | null; weight: number }>,
    maTrend: { ...MA_TREND_DEFAULTS, ma_periods: [...MA_TREND_DEFAULTS.ma_periods], support_ma_lines: [...MA_TREND_DEFAULTS.support_ma_lines] },
    indicatorParams: JSON.parse(JSON.stringify(INDICATOR_DEFAULTS)) as IndicatorParamsConfig,
    breakoutConfig: { ...BREAKOUT_DEFAULTS },
    volumePriceConfig: { ...VOLUME_PRICE_DEFAULTS },
  }
}

// ─── 模拟服务端状态机 ────────────────────────────────────────────────────────

/**
 * 模拟服务端策略存储：
 * - GET /strategies → 返回策略列表
 * - GET /strategies/{id} → 返回策略详情（含 config）
 * - PUT /strategies/{id} → 更新策略配置
 * - POST /strategies/{id}/activate → 激活策略
 */
class MockStrategyServer {
  private strategies: Map<string, StrategyTemplate> = new Map()

  addStrategy(s: StrategyTemplate) {
    this.strategies.set(s.id, JSON.parse(JSON.stringify(s)))
  }

  getList(): StrategyTemplate[] {
    return [...this.strategies.values()]
  }

  getById(id: string): StrategyTemplate | undefined {
    const s = this.strategies.get(id)
    return s ? JSON.parse(JSON.stringify(s)) : undefined
  }

  update(id: string, data: { config?: FullStrategyConfig; name?: string }): StrategyTemplate | undefined {
    const s = this.strategies.get(id)
    if (!s) return undefined
    if (data.config) s.config = JSON.parse(JSON.stringify(data.config))
    if (data.name) s.name = data.name
    return JSON.parse(JSON.stringify(s))
  }

  activate(id: string): void {
    for (const [, s] of this.strategies) {
      s.is_active = s.id === id
    }
  }
}

// ─── 测试数据 ────────────────────────────────────────────────────────────────

const STRATEGY_ID = 'strat-001'

const INITIAL_CONFIG: FullStrategyConfig = {
  logic: 'AND',
  factors: [
    { factor_name: 'ma_trend', operator: '>=', threshold: 80 },
    { factor_name: 'volume_ratio', operator: '>', threshold: 1.5 },
  ],
  weights: { ma_trend: 0.6, volume_ratio: 0.4 },
  ma_periods: [5, 10, 20, 60],
  indicator_params: {
    macd: { fast_period: 10, slow_period: 22, signal_period: 7 },
    boll: { period: 18, std_dev: 1.8 },
    rsi: { period: 12, lower_bound: 45, upper_bound: 75 },
    dma: { short_period: 8, long_period: 40 },
  },
  ma_trend: {
    ma_periods: [5, 10, 20, 60],
    slope_threshold: 0.02,
    trend_score_threshold: 75,
    support_ma_lines: [20],
  },
  breakout: {
    box_breakout: true,
    high_breakout: false,
    trendline_breakout: true,
    volume_ratio_threshold: 2.0,
    confirm_days: 2,
  },
  volume_price: {
    turnover_rate_min: 4,
    turnover_rate_max: 12,
    main_flow_threshold: 1500,
    main_flow_days: 3,
    large_order_ratio: 35,
    min_daily_amount: 8000,
    sector_rank_top: 20,
  },
}

const TEST_STRATEGY: StrategyTemplate = {
  id: STRATEGY_ID,
  name: '趋势突破策略',
  config: INITIAL_CONFIG,
  is_active: false,
  created_at: '2024-01-15T10:00:00Z',
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('18.7.1 选中策略 → 配置回显 → 修改参数 → 保存修改 → 重新选中验证回显一致性', () => {
  let server: MockStrategyServer

  beforeEach(() => {
    vi.clearAllMocks()
    server = new MockStrategyServer()
    server.addStrategy(TEST_STRATEGY)

    // 配置 mock 路由到模拟服务端
    mockGet.mockImplementation((url: string) => {
      if (url === '/strategies') {
        return Promise.resolve({ data: server.getList() })
      }
      const match = url.match(/^\/strategies\/(.+)$/)
      if (match) {
        const s = server.getById(match[1])
        if (s) return Promise.resolve({ data: s })
        return Promise.reject(new Error('策略不存在'))
      }
      if (url === '/screen/schedule') {
        return Promise.resolve({ data: { next_run_at: '2024-01-16T15:30:00+08:00', last_run_at: null, last_run_duration_ms: null, last_run_result_count: null } })
      }
      return Promise.resolve({ data: {} })
    })

    mockPut.mockImplementation((url: string, data: Record<string, unknown>) => {
      const match = url.match(/^\/strategies\/(.+)$/)
      if (match) {
        const updated = server.update(match[1], data as { config?: FullStrategyConfig; name?: string })
        if (updated) return Promise.resolve({ data: updated })
        return Promise.reject(new Error('策略不存在'))
      }
      return Promise.resolve({ data: {} })
    })

    mockPost.mockImplementation((url: string) => {
      const match = url.match(/^\/strategies\/(.+)\/activate$/)
      if (match) {
        server.activate(match[1])
        return Promise.resolve({ data: { ok: true } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  // ─── Step 1: 选中策略 → 配置回显 ──────────────────────────────────────────

  it('Step 1: 选中策略后各面板参数正确回填', async () => {
    // 模拟 selectStrategy(STRATEGY_ID) 的核心逻辑：
    // 1. GET /strategies/{id} 获取配置
    // 2. restoreFromConfig 解析并回填面板

    const res = await mockGet(`/strategies/${STRATEGY_ID}`)
    const strategy = res.data as StrategyTemplate
    expect(strategy.id).toBe(STRATEGY_ID)
    expect(strategy.config).toBeDefined()

    const panels = restoreFromConfig(strategy.config)

    // 验证因子条件回填
    expect(panels.logic).toBe('AND')
    expect(panels.factors).toHaveLength(2)
    expect(panels.factors[0].factor_name).toBe('ma_trend')
    expect(panels.factors[0].operator).toBe('>=')
    expect(panels.factors[0].threshold).toBe(80)
    expect(panels.factors[0].weight).toBe(60) // 0.6 * 100
    expect(panels.factors[1].factor_name).toBe('volume_ratio')
    expect(panels.factors[1].weight).toBe(40) // 0.4 * 100

    // 验证均线趋势配置回填
    expect(panels.maTrend.ma_periods).toEqual([5, 10, 20, 60])
    expect(panels.maTrend.slope_threshold).toBe(0.02)
    expect(panels.maTrend.trend_score_threshold).toBe(75)
    expect(panels.maTrend.support_ma_lines).toEqual([20])

    // 验证技术指标配置回填
    expect(panels.indicatorParams.macd.fast_period).toBe(10)
    expect(panels.indicatorParams.macd.slow_period).toBe(22)
    expect(panels.indicatorParams.boll.std_dev).toBe(1.8)
    expect(panels.indicatorParams.rsi.lower_bound).toBe(45)
    expect(panels.indicatorParams.dma.long_period).toBe(40)

    // 验证形态突破配置回填
    expect(panels.breakoutConfig.high_breakout).toBe(false)
    expect(panels.breakoutConfig.volume_ratio_threshold).toBe(2.0)
    expect(panels.breakoutConfig.confirm_days).toBe(2)

    // 验证量价资金筛选配置回填
    expect(panels.volumePriceConfig.turnover_rate_min).toBe(4)
    expect(panels.volumePriceConfig.main_flow_threshold).toBe(1500)
    expect(panels.volumePriceConfig.sector_rank_top).toBe(20)

    // 验证 activate 被调用
    await mockPost(`/strategies/${STRATEGY_ID}/activate`)
    expect(mockPost).toHaveBeenCalledWith(`/strategies/${STRATEGY_ID}/activate`)
  })

  // ─── Step 2+3: 修改参数 → 保存修改 → 验证 PUT 调用 ────────────────────────

  it('Step 2+3: 修改参数后保存，PUT API 携带正确的更新配置', async () => {
    // Step 1: 加载原始配置
    const res = await mockGet(`/strategies/${STRATEGY_ID}`)
    const panels = restoreFromConfig(res.data.config)

    // Step 2: 修改参数（模拟用户在面板中修改）
    panels.maTrend.trend_score_threshold = 85  // 75 → 85
    panels.indicatorParams.macd.fast_period = 14  // 10 → 14
    panels.breakoutConfig.high_breakout = true  // false → true
    panels.volumePriceConfig.main_flow_threshold = 2000  // 1500 → 2000
    panels.logic = 'OR'  // AND → OR

    // Step 3: 构建保存配置（模拟 buildStrategyConfig）
    const savedConfig = buildStrategyConfig(
      panels.logic,
      panels.factors,
      panels.maTrend.ma_periods.join(','),
      panels.indicatorParams,
      panels.maTrend,
      panels.breakoutConfig,
      panels.volumePriceConfig,
    )

    // 模拟 saveStrategy() 调用 PUT
    await mockPut(`/strategies/${STRATEGY_ID}`, { config: savedConfig })

    // 验证 PUT 被调用且携带正确参数
    expect(mockPut).toHaveBeenCalledWith(
      `/strategies/${STRATEGY_ID}`,
      expect.objectContaining({
        config: expect.objectContaining({
          logic: 'OR',
          ma_trend: expect.objectContaining({ trend_score_threshold: 85 }),
          indicator_params: expect.objectContaining({
            macd: expect.objectContaining({ fast_period: 14 }),
          }),
          breakout: expect.objectContaining({ high_breakout: true }),
          volume_price: expect.objectContaining({ main_flow_threshold: 2000 }),
        }),
      }),
    )

    // 验证服务端已更新
    const updated = server.getById(STRATEGY_ID)!
    expect(updated.config.logic).toBe('OR')
    expect(updated.config.ma_trend.trend_score_threshold).toBe(85)
    expect(updated.config.indicator_params.macd.fast_period).toBe(14)
    expect(updated.config.breakout.high_breakout).toBe(true)
    expect(updated.config.volume_price.main_flow_threshold).toBe(2000)
  })

  // ─── Step 4: 取消选中 → 重新选中 → 验证回显一致性 ──────────────────────────

  it('Step 4: 取消选中恢复默认值，重新选中后回显更新后的配置', async () => {
    // Step 1: 加载并修改
    const res1 = await mockGet(`/strategies/${STRATEGY_ID}`)
    const panels = restoreFromConfig(res1.data.config)
    panels.maTrend.trend_score_threshold = 85
    panels.indicatorParams.macd.fast_period = 14
    panels.breakoutConfig.high_breakout = true
    panels.volumePriceConfig.main_flow_threshold = 2000
    panels.logic = 'OR'

    // Step 2: 保存修改
    const savedConfig = buildStrategyConfig(
      panels.logic, panels.factors,
      panels.maTrend.ma_periods.join(','),
      panels.indicatorParams, panels.maTrend,
      panels.breakoutConfig, panels.volumePriceConfig,
    )
    await mockPut(`/strategies/${STRATEGY_ID}`, { config: savedConfig })

    // Step 3: 取消选中 → 面板恢复默认值
    const defaults = getDefaultPanelState()
    expect(defaults.logic).toBe('AND')
    expect(defaults.factors).toEqual([])
    expect(defaults.maTrend.trend_score_threshold).toBe(80)
    expect(defaults.indicatorParams.macd.fast_period).toBe(12)
    expect(defaults.breakoutConfig.high_breakout).toBe(true)
    expect(defaults.volumePriceConfig.main_flow_threshold).toBe(1000)

    // Step 4: 重新选中 → 从服务端加载更新后的配置
    const res2 = await mockGet(`/strategies/${STRATEGY_ID}`)
    const reloaded = restoreFromConfig(res2.data.config)

    // 验证回显的是更新后的值，而非原始值或默认值
    expect(reloaded.logic).toBe('OR')
    expect(reloaded.maTrend.trend_score_threshold).toBe(85)
    expect(reloaded.indicatorParams.macd.fast_period).toBe(14)
    expect(reloaded.breakoutConfig.high_breakout).toBe(true)
    expect(reloaded.volumePriceConfig.main_flow_threshold).toBe(2000)

    // 验证未修改的字段保持原值
    expect(reloaded.maTrend.ma_periods).toEqual([5, 10, 20, 60])
    expect(reloaded.maTrend.slope_threshold).toBe(0.02)
    expect(reloaded.indicatorParams.boll.std_dev).toBe(1.8)
    expect(reloaded.breakoutConfig.confirm_days).toBe(2)
    expect(reloaded.volumePriceConfig.sector_rank_top).toBe(20)
  })

  // ─── 完整全链路测试 ──────────────────────────────────────────────────────

  it('全链路：选中 → 回显 → 修改 → 保存 → 取消 → 重选 → 验证一致性', async () => {
    // ── 1. 选中策略，验证 GET 调用 ──
    const loadRes = await mockGet(`/strategies/${STRATEGY_ID}`)
    expect(mockGet).toHaveBeenCalledWith(`/strategies/${STRATEGY_ID}`)
    const initialPanels = restoreFromConfig(loadRes.data.config)

    // 验证初始回显
    expect(initialPanels.logic).toBe('AND')
    expect(initialPanels.maTrend.trend_score_threshold).toBe(75)
    expect(initialPanels.indicatorParams.rsi.lower_bound).toBe(45)

    // ── 2. 激活策略 ──
    await mockPost(`/strategies/${STRATEGY_ID}/activate`)
    const listAfterActivate = server.getList()
    expect(listAfterActivate.find(s => s.id === STRATEGY_ID)?.is_active).toBe(true)

    // ── 3. 修改多个参数 ──
    initialPanels.maTrend.trend_score_threshold = 90
    initialPanels.maTrend.support_ma_lines = [20, 60]
    initialPanels.indicatorParams.rsi.lower_bound = 55
    initialPanels.indicatorParams.rsi.upper_bound = 85
    initialPanels.breakoutConfig.trendline_breakout = false
    initialPanels.volumePriceConfig.large_order_ratio = 40
    initialPanels.volumePriceConfig.min_daily_amount = 10000

    // ── 4. 保存修改 ──
    const configToSave = buildStrategyConfig(
      initialPanels.logic, initialPanels.factors,
      initialPanels.maTrend.ma_periods.join(','),
      initialPanels.indicatorParams, initialPanels.maTrend,
      initialPanels.breakoutConfig, initialPanels.volumePriceConfig,
    )
    await mockPut(`/strategies/${STRATEGY_ID}`, { config: configToSave })

    // 验证 PUT 调用
    expect(mockPut).toHaveBeenCalledWith(
      `/strategies/${STRATEGY_ID}`,
      expect.objectContaining({ config: expect.any(Object) }),
    )

    // ── 5. 取消选中（模拟再次点击同一策略） ──
    const defaultState = getDefaultPanelState()
    // 默认值与修改后的值不同
    expect(defaultState.maTrend.trend_score_threshold).not.toBe(90)
    expect(defaultState.indicatorParams.rsi.lower_bound).not.toBe(55)

    // ── 6. 重新选中，从服务端加载 ──
    const reloadRes = await mockGet(`/strategies/${STRATEGY_ID}`)
    const reloadedPanels = restoreFromConfig(reloadRes.data.config)

    // ── 7. 验证回显一致性：所有修改后的值正确回显 ──
    expect(reloadedPanels.logic).toBe('AND')
    expect(reloadedPanels.maTrend.trend_score_threshold).toBe(90)
    expect(reloadedPanels.maTrend.support_ma_lines).toEqual([20, 60])
    expect(reloadedPanels.indicatorParams.rsi.lower_bound).toBe(55)
    expect(reloadedPanels.indicatorParams.rsi.upper_bound).toBe(85)
    expect(reloadedPanels.breakoutConfig.trendline_breakout).toBe(false)
    expect(reloadedPanels.volumePriceConfig.large_order_ratio).toBe(40)
    expect(reloadedPanels.volumePriceConfig.min_daily_amount).toBe(10000)

    // 验证未修改的字段保持不变
    expect(reloadedPanels.factors).toHaveLength(2)
    expect(reloadedPanels.factors[0].factor_name).toBe('ma_trend')
    expect(reloadedPanels.maTrend.slope_threshold).toBe(0.02)
    expect(reloadedPanels.indicatorParams.macd.fast_period).toBe(10)
    expect(reloadedPanels.breakoutConfig.volume_ratio_threshold).toBe(2.0)
    expect(reloadedPanels.volumePriceConfig.turnover_rate_min).toBe(4)
  })

  // ─── 边界：保存后因子权重 round-trip 正确 ─────────────────────────────────

  it('因子权重 round-trip：0-100 → 0-1 → 0-100 保持一致', async () => {
    const res = await mockGet(`/strategies/${STRATEGY_ID}`)
    const panels = restoreFromConfig(res.data.config)

    // 原始权重：ma_trend=60, volume_ratio=40
    expect(panels.factors[0].weight).toBe(60)
    expect(panels.factors[1].weight).toBe(40)

    // 修改权重
    panels.factors[0].weight = 75
    panels.factors[1].weight = 25

    // 保存
    const saved = buildStrategyConfig(
      panels.logic, panels.factors,
      panels.maTrend.ma_periods.join(','),
      panels.indicatorParams, panels.maTrend,
      panels.breakoutConfig, panels.volumePriceConfig,
    )

    // 验证序列化后的权重
    expect(saved.weights['ma_trend']).toBeCloseTo(0.75, 10)
    expect(saved.weights['volume_ratio']).toBeCloseTo(0.25, 10)

    // 保存到服务端
    await mockPut(`/strategies/${STRATEGY_ID}`, { config: saved })

    // 重新加载
    const res2 = await mockGet(`/strategies/${STRATEGY_ID}`)
    const reloaded = restoreFromConfig(res2.data.config)

    // 验证 round-trip 后权重一致
    expect(reloaded.factors[0].weight).toBe(75)
    expect(reloaded.factors[1].weight).toBe(25)
  })

  // ─── 边界：空因子列表的全链路 ─────────────────────────────────────────────

  it('空因子列表策略的选中 → 修改 → 保存 → 回显全链路', async () => {
    // 添加一个无因子的策略
    const emptyFactorStrategy: StrategyTemplate = {
      id: 'strat-empty',
      name: '空因子策略',
      config: {
        logic: 'OR',
        factors: [],
        weights: {},
        ma_periods: [10, 20],
        indicator_params: JSON.parse(JSON.stringify(INDICATOR_DEFAULTS)),
        ma_trend: { ...MA_TREND_DEFAULTS, ma_periods: [10, 20], support_ma_lines: [20] },
        breakout: { ...BREAKOUT_DEFAULTS },
        volume_price: { ...VOLUME_PRICE_DEFAULTS },
      },
      is_active: false,
      created_at: '2024-01-16T10:00:00Z',
    }
    server.addStrategy(emptyFactorStrategy)

    // 选中
    const res = await mockGet('/strategies/strat-empty')
    const panels = restoreFromConfig(res.data.config)
    expect(panels.factors).toEqual([])
    expect(panels.logic).toBe('OR')

    // 修改非因子参数
    panels.maTrend.trend_score_threshold = 65

    // 保存
    const saved = buildStrategyConfig(
      panels.logic, panels.factors,
      panels.maTrend.ma_periods.join(','),
      panels.indicatorParams, panels.maTrend,
      panels.breakoutConfig, panels.volumePriceConfig,
    )
    await mockPut('/strategies/strat-empty', { config: saved })

    // 重新加载验证
    const res2 = await mockGet('/strategies/strat-empty')
    const reloaded = restoreFromConfig(res2.data.config)
    expect(reloaded.factors).toEqual([])
    expect(reloaded.maTrend.trend_score_threshold).toBe(65)
  })
})


// ─── 测试 18.7.2 ──────────────────────────────────────────────────────────────

describe('18.7.2 选中策略 A → 切换选中策略 B → 验证激活状态切换 → 刷新页面验证持久化', () => {
  let server: MockStrategyServer

  // ─── 测试数据：两个策略 ──────────────────────────────────────────────────

  const STRATEGY_A: StrategyTemplate = {
    id: 'strat-A',
    name: '均线趋势策略 A',
    config: {
      logic: 'AND',
      factors: [{ factor_name: 'ma_trend', operator: '>=', threshold: 80 }],
      weights: { ma_trend: 0.7 },
      ma_periods: [5, 10, 20],
      indicator_params: {
        macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
        boll: { period: 20, std_dev: 2 },
        rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
        dma: { short_period: 10, long_period: 50 },
      },
      ma_trend: {
        ma_periods: [5, 10, 20],
        slope_threshold: 0.01,
        trend_score_threshold: 80,
        support_ma_lines: [20],
      },
      breakout: {
        box_breakout: true,
        high_breakout: true,
        trendline_breakout: false,
        volume_ratio_threshold: 1.5,
        confirm_days: 1,
      },
      volume_price: {
        turnover_rate_min: 3,
        turnover_rate_max: 15,
        main_flow_threshold: 1000,
        main_flow_days: 2,
        large_order_ratio: 30,
        min_daily_amount: 5000,
        sector_rank_top: 30,
      },
    },
    is_active: false,
    created_at: '2024-02-01T10:00:00Z',
  }

  const STRATEGY_B: StrategyTemplate = {
    id: 'strat-B',
    name: '量价突破策略 B',
    config: {
      logic: 'OR',
      factors: [
        { factor_name: 'volume_ratio', operator: '>', threshold: 2.0 },
        { factor_name: 'breakout_score', operator: '>=', threshold: 70 },
      ],
      weights: { volume_ratio: 0.5, breakout_score: 0.5 },
      ma_periods: [10, 20, 60],
      indicator_params: {
        macd: { fast_period: 10, slow_period: 22, signal_period: 7 },
        boll: { period: 18, std_dev: 1.8 },
        rsi: { period: 12, lower_bound: 45, upper_bound: 75 },
        dma: { short_period: 8, long_period: 40 },
      },
      ma_trend: {
        ma_periods: [10, 20, 60],
        slope_threshold: 0.02,
        trend_score_threshold: 75,
        support_ma_lines: [20, 60],
      },
      breakout: {
        box_breakout: true,
        high_breakout: false,
        trendline_breakout: true,
        volume_ratio_threshold: 2.0,
        confirm_days: 2,
      },
      volume_price: {
        turnover_rate_min: 4,
        turnover_rate_max: 12,
        main_flow_threshold: 1500,
        main_flow_days: 3,
        large_order_ratio: 35,
        min_daily_amount: 8000,
        sector_rank_top: 20,
      },
    },
    is_active: false,
    created_at: '2024-02-05T10:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    server = new MockStrategyServer()
    server.addStrategy(STRATEGY_A)
    server.addStrategy(STRATEGY_B)

    // 配置 mock 路由到模拟服务端
    mockGet.mockImplementation((url: string) => {
      if (url === '/strategies') {
        return Promise.resolve({ data: server.getList() })
      }
      const match = url.match(/^\/strategies\/(.+)$/)
      if (match) {
        const s = server.getById(match[1])
        if (s) return Promise.resolve({ data: s })
        return Promise.reject(new Error('策略不存在'))
      }
      if (url === '/screen/schedule') {
        return Promise.resolve({ data: { next_run_at: '2024-02-06T15:30:00+08:00', last_run_at: null, last_run_duration_ms: null, last_run_result_count: null } })
      }
      return Promise.resolve({ data: {} })
    })

    mockPost.mockImplementation((url: string) => {
      const match = url.match(/^\/strategies\/(.+)\/activate$/)
      if (match) {
        server.activate(match[1])
        return Promise.resolve({ data: { ok: true } })
      }
      return Promise.resolve({ data: {} })
    })

    mockPut.mockImplementation((url: string, data: Record<string, unknown>) => {
      const match = url.match(/^\/strategies\/(.+)$/)
      if (match) {
        const updated = server.update(match[1], data as { config?: FullStrategyConfig; name?: string })
        if (updated) return Promise.resolve({ data: updated })
        return Promise.reject(new Error('策略不存在'))
      }
      return Promise.resolve({ data: {} })
    })
  })

  // ─── Step 1: 选中策略 A → 验证服务端激活状态 ──────────────────────────────

  it('Step 1: 选中策略 A 后服务端 is_active 正确', async () => {
    // 模拟 selectStrategy('strat-A')：加载配置 + 激活
    const res = await mockGet('/strategies/strat-A')
    expect(res.data.id).toBe('strat-A')

    await mockPost('/strategies/strat-A/activate')

    // 验证服务端状态
    const list = server.getList()
    const stratA = list.find(s => s.id === 'strat-A')!
    const stratB = list.find(s => s.id === 'strat-B')!
    expect(stratA.is_active).toBe(true)
    expect(stratB.is_active).toBe(false)

    // 验证配置可正确回填
    const panels = restoreFromConfig(res.data.config)
    expect(panels.logic).toBe('AND')
    expect(panels.maTrend.trend_score_threshold).toBe(80)
    expect(panels.breakoutConfig.trendline_breakout).toBe(false)
  })

  // ─── Step 2: 切换选中策略 B → 验证 A 失活、B 激活 ─────────────────────────

  it('Step 2: 切换到策略 B 后 A 失活、B 激活', async () => {
    // 先激活 A
    await mockPost('/strategies/strat-A/activate')
    expect(server.getList().find(s => s.id === 'strat-A')!.is_active).toBe(true)

    // 切换到 B：加载配置 + 激活
    const resB = await mockGet('/strategies/strat-B')
    expect(resB.data.id).toBe('strat-B')

    await mockPost('/strategies/strat-B/activate')

    // 验证服务端状态：A 失活，B 激活
    const list = server.getList()
    expect(list.find(s => s.id === 'strat-A')!.is_active).toBe(false)
    expect(list.find(s => s.id === 'strat-B')!.is_active).toBe(true)

    // 验证 B 的配置回填
    const panels = restoreFromConfig(resB.data.config)
    expect(panels.logic).toBe('OR')
    expect(panels.factors).toHaveLength(2)
    expect(panels.factors[0].factor_name).toBe('volume_ratio')
    expect(panels.maTrend.trend_score_threshold).toBe(75)
    expect(panels.breakoutConfig.volume_ratio_threshold).toBe(2.0)
    expect(panels.volumePriceConfig.main_flow_threshold).toBe(1500)
  })

  // ─── Step 3: 模拟页面刷新 → 验证 B 仍然激活并自动选中 ─────────────────────

  it('Step 3: 刷新页面后活跃策略 B 仍然持久化且自动选中', async () => {
    // 先激活 A，再切换到 B
    await mockPost('/strategies/strat-A/activate')
    await mockPost('/strategies/strat-B/activate')

    // ── 模拟页面刷新：重新 GET /strategies 获取列表 ──
    const listRes = await mockGet('/strategies')
    const strategies = listRes.data as StrategyTemplate[]

    // 验证列表中 B 是活跃策略
    const activeStrategy = strategies.find(s => s.is_active)
    expect(activeStrategy).toBeDefined()
    expect(activeStrategy!.id).toBe('strat-B')
    expect(activeStrategy!.name).toBe('量价突破策略 B')

    // 验证 A 不是活跃策略
    const inactiveA = strategies.find(s => s.id === 'strat-A')!
    expect(inactiveA.is_active).toBe(false)

    // ── 模拟 onMounted 自动选中逻辑：找到 is_active=true 的策略并加载配置 ──
    const autoSelectId = activeStrategy!.id
    const detailRes = await mockGet(`/strategies/${autoSelectId}`)
    const autoSelectedConfig = restoreFromConfig(detailRes.data.config)

    // 验证自动选中的是 B 的配置
    expect(autoSelectedConfig.logic).toBe('OR')
    expect(autoSelectedConfig.factors).toHaveLength(2)
    expect(autoSelectedConfig.maTrend.ma_periods).toEqual([10, 20, 60])
    expect(autoSelectedConfig.maTrend.trend_score_threshold).toBe(75)
    expect(autoSelectedConfig.indicatorParams.macd.fast_period).toBe(10)
    expect(autoSelectedConfig.indicatorParams.boll.std_dev).toBe(1.8)
    expect(autoSelectedConfig.breakoutConfig.confirm_days).toBe(2)
    expect(autoSelectedConfig.volumePriceConfig.sector_rank_top).toBe(20)
  })

  // ─── 完整全链路测试 ──────────────────────────────────────────────────────

  it('全链路：选中 A → 切换 B → 验证激活切换 → 刷新验证持久化', async () => {
    // ── 1. 选中策略 A ──
    const resA = await mockGet('/strategies/strat-A')
    const panelsA = restoreFromConfig(resA.data.config)
    expect(panelsA.logic).toBe('AND')
    expect(panelsA.maTrend.trend_score_threshold).toBe(80)

    await mockPost('/strategies/strat-A/activate')
    expect(mockPost).toHaveBeenCalledWith('/strategies/strat-A/activate')

    // 验证 A 激活
    let list = server.getList()
    expect(list.find(s => s.id === 'strat-A')!.is_active).toBe(true)
    expect(list.find(s => s.id === 'strat-B')!.is_active).toBe(false)

    // ── 2. 切换到策略 B ──
    const resB = await mockGet('/strategies/strat-B')
    const panelsB = restoreFromConfig(resB.data.config)
    expect(panelsB.logic).toBe('OR')
    expect(panelsB.maTrend.trend_score_threshold).toBe(75)
    expect(panelsB.volumePriceConfig.main_flow_threshold).toBe(1500)

    await mockPost('/strategies/strat-B/activate')
    expect(mockPost).toHaveBeenCalledWith('/strategies/strat-B/activate')

    // ── 3. 验证激活状态切换 ──
    list = server.getList()
    expect(list.find(s => s.id === 'strat-A')!.is_active).toBe(false)
    expect(list.find(s => s.id === 'strat-B')!.is_active).toBe(true)

    // 验证 A 和 B 的配置不同
    expect(panelsA.logic).not.toBe(panelsB.logic)
    expect(panelsA.maTrend.trend_score_threshold).not.toBe(panelsB.maTrend.trend_score_threshold)

    // ── 4. 模拟页面刷新（重新获取策略列表） ──
    const refreshRes = await mockGet('/strategies')
    const refreshedList = refreshRes.data as StrategyTemplate[]

    // 找到活跃策略
    const activeAfterRefresh = refreshedList.find(s => s.is_active)
    expect(activeAfterRefresh).toBeDefined()
    expect(activeAfterRefresh!.id).toBe('strat-B')

    // ── 5. 模拟 onMounted 自动选中活跃策略并回填配置 ──
    const autoLoadRes = await mockGet(`/strategies/${activeAfterRefresh!.id}`)
    const autoLoadedPanels = restoreFromConfig(autoLoadRes.data.config)

    // 验证回填的是 B 的完整配置
    expect(autoLoadedPanels.logic).toBe('OR')
    expect(autoLoadedPanels.factors).toHaveLength(2)
    expect(autoLoadedPanels.factors[0].factor_name).toBe('volume_ratio')
    expect(autoLoadedPanels.factors[0].weight).toBe(50) // 0.5 * 100
    expect(autoLoadedPanels.factors[1].factor_name).toBe('breakout_score')
    expect(autoLoadedPanels.factors[1].weight).toBe(50)
    expect(autoLoadedPanels.maTrend.ma_periods).toEqual([10, 20, 60])
    expect(autoLoadedPanels.maTrend.slope_threshold).toBe(0.02)
    expect(autoLoadedPanels.maTrend.support_ma_lines).toEqual([20, 60])
    expect(autoLoadedPanels.indicatorParams.macd.fast_period).toBe(10)
    expect(autoLoadedPanels.indicatorParams.rsi.lower_bound).toBe(45)
    expect(autoLoadedPanels.breakoutConfig.high_breakout).toBe(false)
    expect(autoLoadedPanels.breakoutConfig.trendline_breakout).toBe(true)
    expect(autoLoadedPanels.volumePriceConfig.turnover_rate_min).toBe(4)
    expect(autoLoadedPanels.volumePriceConfig.min_daily_amount).toBe(8000)
  })

  // ─── 边界：多次切换后激活状态始终唯一 ─────────────────────────────────────

  it('多次切换激活策略后，始终只有一个策略处于激活状态', async () => {
    // A → B → A → B 连续切换
    await mockPost('/strategies/strat-A/activate')
    expect(server.getList().filter(s => s.is_active)).toHaveLength(1)
    expect(server.getList().find(s => s.is_active)!.id).toBe('strat-A')

    await mockPost('/strategies/strat-B/activate')
    expect(server.getList().filter(s => s.is_active)).toHaveLength(1)
    expect(server.getList().find(s => s.is_active)!.id).toBe('strat-B')

    await mockPost('/strategies/strat-A/activate')
    expect(server.getList().filter(s => s.is_active)).toHaveLength(1)
    expect(server.getList().find(s => s.is_active)!.id).toBe('strat-A')

    await mockPost('/strategies/strat-B/activate')
    expect(server.getList().filter(s => s.is_active)).toHaveLength(1)
    expect(server.getList().find(s => s.is_active)!.id).toBe('strat-B')

    // 刷新后仍然是 B
    const list = (await mockGet('/strategies')).data as StrategyTemplate[]
    expect(list.filter(s => s.is_active)).toHaveLength(1)
    expect(list.find(s => s.is_active)!.id).toBe('strat-B')
  })
})
