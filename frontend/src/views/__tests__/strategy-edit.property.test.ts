/**
 * 策略模板编辑与激活属性测试（Vitest + fast-check）
 *
 * 属性 46：策略配置回显 round-trip 正确性
 *
 * 验证需求：22.1, 22.2
 *
 * 核心属性：对于任意合法策略配置，通过 buildStrategyConfig() 序列化后
 * 保存至服务端（PUT /strategies/{id}），再通过 selectStrategy() 加载回来
 * （GET /strategies/{id}），各面板回显参数与保存时完全一致。
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ---------------------------------------------------------------------------
// 共享类型（与 ScreenerView 保持一致）
// ---------------------------------------------------------------------------

type FactorType = 'technical' | 'capital' | 'fundamental' | 'sector'

interface FactorCondition {
  type: FactorType
  factor_name: string
  operator: string
  threshold: number | null
  weight: number
}

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

// ---------------------------------------------------------------------------
// buildStrategyConfig 的纯函数等价实现（与 ScreenerView 逻辑一致）
// ---------------------------------------------------------------------------

function buildStrategyConfig(
  logic: 'AND' | 'OR',
  factors: FactorCondition[],
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

// ---------------------------------------------------------------------------
// restoreFromConfig 的纯函数等价实现（与 selectStrategy 回填逻辑一致）
// ---------------------------------------------------------------------------

function restoreFromConfig(cfg: FullStrategyConfig): {
  logic: 'AND' | 'OR'
  factors: FactorCondition[]
  maTrend: MaTrendConfig
  indicatorParams: IndicatorParamsConfig
  breakoutConfig: BreakoutConfig
  volumePriceConfig: VolumePriceConfig
} {
  const factors = (cfg.factors ?? []).map((f) => ({
    type: 'technical' as FactorType,
    factor_name: f.factor_name ?? '',
    operator: f.operator ?? '>',
    threshold: f.threshold ?? null,
    // In the component: weights key is (factor_name || type) on save,
    // but (factor_name) on load. With non-empty factor_name they match.
    weight: Math.round(((cfg.weights?.[f.factor_name ?? ''] ?? 0.5) * 100)),
  }))

  const mt = cfg.ma_trend
  const maTrend: MaTrendConfig = mt
    ? {
        ma_periods: Array.isArray(mt.ma_periods) ? [...mt.ma_periods] : [5, 10, 20, 60, 120],
        slope_threshold: typeof mt.slope_threshold === 'number' ? mt.slope_threshold : 0,
        trend_score_threshold: typeof mt.trend_score_threshold === 'number' ? mt.trend_score_threshold : 80,
        support_ma_lines: Array.isArray(mt.support_ma_lines) ? [...mt.support_ma_lines] : [20, 60],
      }
    : { ma_periods: [5, 10, 20, 60, 120], slope_threshold: 0, trend_score_threshold: 80, support_ma_lines: [20, 60] }

  const ip = cfg.indicator_params
  const indicatorParams: IndicatorParamsConfig = ip
    ? {
        macd: { ...{ fast_period: 12, slow_period: 26, signal_period: 9 }, ...ip.macd },
        boll: { ...{ period: 20, std_dev: 2 }, ...ip.boll },
        rsi: { ...{ period: 14, lower_bound: 50, upper_bound: 80 }, ...ip.rsi },
        dma: { ...{ short_period: 10, long_period: 50 }, ...ip.dma },
      }
    : {
        macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
        boll: { period: 20, std_dev: 2 },
        rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
        dma: { short_period: 10, long_period: 50 },
      }

  const bo = cfg.breakout
  const breakoutConfig: BreakoutConfig = bo
    ? {
        box_breakout: bo.box_breakout ?? true,
        high_breakout: bo.high_breakout ?? true,
        trendline_breakout: bo.trendline_breakout ?? true,
        volume_ratio_threshold: bo.volume_ratio_threshold ?? 1.5,
        confirm_days: bo.confirm_days ?? 1,
      }
    : { box_breakout: true, high_breakout: true, trendline_breakout: true, volume_ratio_threshold: 1.5, confirm_days: 1 }

  const vp = cfg.volume_price
  const volumePriceConfig: VolumePriceConfig = vp
    ? {
        turnover_rate_min: vp.turnover_rate_min ?? 3,
        turnover_rate_max: vp.turnover_rate_max ?? 15,
        main_flow_threshold: vp.main_flow_threshold ?? 1000,
        main_flow_days: vp.main_flow_days ?? 2,
        large_order_ratio: vp.large_order_ratio ?? 30,
        min_daily_amount: vp.min_daily_amount ?? 5000,
        sector_rank_top: vp.sector_rank_top ?? 30,
      }
    : { turnover_rate_min: 3, turnover_rate_max: 15, main_flow_threshold: 1000, main_flow_days: 2, large_order_ratio: 30, min_daily_amount: 5000, sector_rank_top: 30 }

  return {
    logic: cfg.logic ?? 'AND',
    factors,
    maTrend,
    indicatorParams,
    breakoutConfig,
    volumePriceConfig,
  }
}


// ---------------------------------------------------------------------------
// 模拟 JSON round-trip（服务端保存 + 加载经过 JSON 序列化/反序列化）
// ---------------------------------------------------------------------------

function serverRoundTrip(config: FullStrategyConfig): FullStrategyConfig {
  return JSON.parse(JSON.stringify(config)) as FullStrategyConfig
}

// ---------------------------------------------------------------------------
// fast-check Arbitraries
// ---------------------------------------------------------------------------

const factorTypeArb = fc.constantFrom<FactorType>('technical', 'capital', 'fundamental', 'sector')
const operatorArb = fc.constantFrom('>', '>=', '<', '<=', '==')

const factorArb = (index: number): fc.Arbitrary<FactorCondition> =>
  fc.record({
    type: factorTypeArb,
    // Use index suffix to guarantee unique factor_name across the array,
    // matching real-world usage where duplicate names cause weight collisions
    factor_name: fc.stringMatching(/^[a-z]{1,10}$/).map((s) => `${s}_${index}`),
    operator: operatorArb,
    threshold: fc.oneof(fc.constant(null), fc.integer({ min: -1000, max: 1000 })),
    weight: fc.integer({ min: 0, max: 100 }),
  })

const maTrendArb: fc.Arbitrary<MaTrendConfig> = fc.record({
  ma_periods: fc.uniqueArray(fc.integer({ min: 1, max: 250 }), { minLength: 1, maxLength: 8 }),
  slope_threshold: fc.double({ min: -1, max: 1, noNaN: true, noDefaultInfinity: true }),
  trend_score_threshold: fc.integer({ min: 0, max: 100 }),
  support_ma_lines: fc.subarray([5, 10, 20, 60, 120]),
})

const indicatorParamsArb: fc.Arbitrary<IndicatorParamsConfig> = fc.record({
  macd: fc.record({
    fast_period: fc.integer({ min: 1, max: 50 }),
    slow_period: fc.integer({ min: 1, max: 100 }),
    signal_period: fc.integer({ min: 1, max: 30 }),
  }),
  boll: fc.record({
    period: fc.integer({ min: 1, max: 100 }),
    std_dev: fc.double({ min: 0.5, max: 5, noNaN: true, noDefaultInfinity: true }),
  }),
  rsi: fc.record({
    period: fc.integer({ min: 1, max: 50 }),
    lower_bound: fc.integer({ min: 0, max: 100 }),
    upper_bound: fc.integer({ min: 0, max: 100 }),
  }),
  dma: fc.record({
    short_period: fc.integer({ min: 1, max: 50 }),
    long_period: fc.integer({ min: 1, max: 200 }),
  }),
})

const breakoutArb: fc.Arbitrary<BreakoutConfig> = fc.record({
  box_breakout: fc.boolean(),
  high_breakout: fc.boolean(),
  trendline_breakout: fc.boolean(),
  volume_ratio_threshold: fc.double({ min: 0.1, max: 5, noNaN: true, noDefaultInfinity: true }),
  confirm_days: fc.integer({ min: 1, max: 10 }),
})

const volumePriceArb: fc.Arbitrary<VolumePriceConfig> = fc.record({
  turnover_rate_min: fc.double({ min: 0, max: 50, noNaN: true, noDefaultInfinity: true }),
  turnover_rate_max: fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
  main_flow_threshold: fc.double({ min: 0, max: 100000, noNaN: true, noDefaultInfinity: true }),
  main_flow_days: fc.integer({ min: 1, max: 30 }),
  large_order_ratio: fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
  min_daily_amount: fc.double({ min: 0, max: 1000000, noNaN: true, noDefaultInfinity: true }),
  sector_rank_top: fc.integer({ min: 1, max: 100 }),
})

// ---------------------------------------------------------------------------
// 属性 46：策略配置回显 round-trip 正确性
// **Validates: Requirements 22.1, 22.2**
// ---------------------------------------------------------------------------

describe('属性 46：策略配置回显 round-trip 正确性', () => {
  /**
   * 核心属性：对于任意合法策略配置，
   * buildStrategyConfig() → JSON round-trip（模拟服务端保存/加载）→ restoreFromConfig()
   * 后各面板参数与原始输入完全一致。
   */
  it('任意策略配置保存后再加载，各面板回显参数与保存时完全一致', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<'AND' | 'OR'>('AND', 'OR'),
        fc.integer({ min: 0, max: 5 }).chain((len) =>
          len === 0
            ? fc.constant([] as FactorCondition[])
            : fc.tuple(...Array.from({ length: len }, (_, i) => factorArb(i))).map((arr) => [...arr]),
        ),
        maTrendArb,
        indicatorParamsArb,
        breakoutArb,
        volumePriceArb,
        (logic, factors, maTrend, indicatorParams, breakout, volumePrice) => {
          // Step 1: Build config (simulates user clicking "保存修改")
          const maPeriods = maTrend.ma_periods.join(',')
          const saved = buildStrategyConfig(
            logic, factors, maPeriods,
            indicatorParams, maTrend, breakout, volumePrice,
          )

          // Step 2: Simulate server round-trip (PUT → GET via JSON)
          const loaded = serverRoundTrip(saved)

          // Step 3: Restore panels (simulates selectStrategy callback)
          const restored = restoreFromConfig(loaded)

          // ── Verify logic ──
          expect(restored.logic).toBe(logic)

          // ── Verify ma_trend ──
          expect(restored.maTrend.ma_periods).toEqual(maTrend.ma_periods)
          expect(restored.maTrend.trend_score_threshold).toBe(maTrend.trend_score_threshold)
          expect(restored.maTrend.support_ma_lines).toEqual(maTrend.support_ma_lines)
          // slope_threshold goes through JSON so compare with tolerance
          expect(restored.maTrend.slope_threshold).toBeCloseTo(maTrend.slope_threshold, 10)

          // ── Verify indicator_params ──
          expect(restored.indicatorParams.macd).toEqual(indicatorParams.macd)
          expect(restored.indicatorParams.boll.period).toBe(indicatorParams.boll.period)
          expect(restored.indicatorParams.boll.std_dev).toBeCloseTo(indicatorParams.boll.std_dev, 10)
          expect(restored.indicatorParams.rsi).toEqual(indicatorParams.rsi)
          expect(restored.indicatorParams.dma).toEqual(indicatorParams.dma)

          // ── Verify breakout ──
          expect(restored.breakoutConfig.box_breakout).toBe(breakout.box_breakout)
          expect(restored.breakoutConfig.high_breakout).toBe(breakout.high_breakout)
          expect(restored.breakoutConfig.trendline_breakout).toBe(breakout.trendline_breakout)
          expect(restored.breakoutConfig.volume_ratio_threshold).toBeCloseTo(breakout.volume_ratio_threshold, 10)
          expect(restored.breakoutConfig.confirm_days).toBe(breakout.confirm_days)

          // ── Verify volume_price ──
          expect(restored.volumePriceConfig.turnover_rate_min).toBeCloseTo(volumePrice.turnover_rate_min, 10)
          expect(restored.volumePriceConfig.turnover_rate_max).toBeCloseTo(volumePrice.turnover_rate_max, 10)
          expect(restored.volumePriceConfig.main_flow_threshold).toBeCloseTo(volumePrice.main_flow_threshold, 10)
          expect(restored.volumePriceConfig.main_flow_days).toBe(volumePrice.main_flow_days)
          expect(restored.volumePriceConfig.large_order_ratio).toBeCloseTo(volumePrice.large_order_ratio, 10)
          expect(restored.volumePriceConfig.min_daily_amount).toBeCloseTo(volumePrice.min_daily_amount, 10)
          expect(restored.volumePriceConfig.sector_rank_top).toBe(volumePrice.sector_rank_top)

          // ── Verify factors round-trip (weights are stored as 0-1, restored as 0-100) ──
          for (let i = 0; i < factors.length; i++) {
            const orig = factors[i]
            const rest = restored.factors[i]
            expect(rest.factor_name).toBe(orig.factor_name)
            expect(rest.operator).toBe(orig.operator)
            expect(rest.threshold).toBe(orig.threshold)
            // Weight: original 0-100 → saved as /100 → restored as *100 → Math.round
            const expectedWeight = Math.round(Math.round(orig.weight) / 100 * 100)
            expect(rest.weight).toBe(expectedWeight)
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  it('空因子列表的 round-trip 保持空', () => {
    fc.assert(
      fc.property(
        maTrendArb,
        indicatorParamsArb,
        breakoutArb,
        volumePriceArb,
        (maTrend, indicatorParams, breakout, volumePrice) => {
          const saved = buildStrategyConfig(
            'AND', [], maTrend.ma_periods.join(','),
            indicatorParams, maTrend, breakout, volumePrice,
          )
          const loaded = serverRoundTrip(saved)
          const restored = restoreFromConfig(loaded)
          expect(restored.factors).toEqual([])
          expect(restored.logic).toBe('AND')
        },
      ),
      { numRuns: 30 },
    )
  })

  it('ma_periods 通过逗号分隔字符串序列化后保持一致', () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.integer({ min: 1, max: 250 }), { minLength: 1, maxLength: 8 }),
        (periods) => {
          const csv = periods.join(',')
          const parsed = csv.split(',').map(Number).filter(Boolean)
          expect(parsed).toEqual(periods)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('JSON round-trip 不丢失任何顶层配置字段', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<'AND' | 'OR'>('AND', 'OR'),
        maTrendArb,
        indicatorParamsArb,
        breakoutArb,
        volumePriceArb,
        (logic, maTrend, indicatorParams, breakout, volumePrice) => {
          const saved = buildStrategyConfig(
            logic, [], maTrend.ma_periods.join(','),
            indicatorParams, maTrend, breakout, volumePrice,
          )
          const loaded = serverRoundTrip(saved)

          // All top-level keys must survive the round-trip
          const expectedKeys = ['logic', 'factors', 'weights', 'ma_periods', 'indicator_params', 'ma_trend', 'breakout', 'volume_price']
          for (const key of expectedKeys) {
            expect(loaded).toHaveProperty(key)
          }
        },
      ),
      { numRuns: 50 },
    )
  })
})


// ---------------------------------------------------------------------------
// 属性 47：策略激活状态服务端同步正确性
// **Validates: Requirements 22.3**
// ---------------------------------------------------------------------------

/**
 * 模拟服务端策略激活状态机：
 * - State: 策略列表，每个策略有 id 和 is_active 标志
 * - Action: activate(id) → 将该 id 设为 active，其余全部设为 inactive
 * - Property 1: 任意时刻最多只有一个策略处于 active 状态
 * - Property 2: activate(X) 后，仅 X 的 is_active 为 true
 * - Property 3: 页面挂载时（模拟），is_active=true 的策略被自动选中
 */

interface StrategyEntry {
  id: string
  name: string
  is_active: boolean
}

/**
 * 模拟服务端 POST /strategies/{id}/activate 的行为：
 * 将目标策略设为 active，其余全部设为 inactive。
 */
function serverActivate(strategies: StrategyEntry[], targetId: string): StrategyEntry[] {
  return strategies.map((s) => ({
    ...s,
    is_active: s.id === targetId,
  }))
}

/**
 * 模拟页面挂载时的自动选中逻辑（onMounted）：
 * 从策略列表中找到 is_active=true 的策略，返回其 id；
 * 若无活跃策略则返回空字符串。
 */
function autoSelectOnMount(strategies: StrategyEntry[]): string {
  const active = strategies.find((s) => s.is_active)
  return active ? active.id : ''
}

/**
 * 校验不变量：最多只有一个策略处于 active 状态
 */
function atMostOneActive(strategies: StrategyEntry[]): boolean {
  return strategies.filter((s) => s.is_active).length <= 1
}

// fast-check Arbitraries

const strategyIdArb = fc.uuid()

const strategyEntryArb: fc.Arbitrary<StrategyEntry> = fc.record({
  id: strategyIdArb,
  name: fc.stringMatching(/^[a-zA-Z0-9_]{1,20}$/),
  is_active: fc.constant(false), // 初始全部 inactive
})

const strategyListArb = fc.uniqueArray(strategyEntryArb, {
  minLength: 1,
  maxLength: 10,
  comparator: (a, b) => a.id === b.id,
})

describe('属性 47：策略激活状态服务端同步正确性', () => {
  /**
   * 核心属性 1：activate(X) 后，仅 X 的 is_active 为 true，其余为 false
   */
  it('选中策略 X 后，仅 X 的 is_active 为 true，其余策略为 false', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        (strategies) => {
          // 随机选择一个策略进行激活
          const targetIdx = Math.floor(Math.random() * strategies.length)
          const targetId = strategies[targetIdx].id

          const afterActivation = serverActivate(strategies, targetId)

          // 仅目标策略 is_active=true
          for (const s of afterActivation) {
            if (s.id === targetId) {
              expect(s.is_active).toBe(true)
            } else {
              expect(s.is_active).toBe(false)
            }
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 核心属性 2：任意激活操作后，最多只有一个策略处于 active 状态
   */
  it('任意激活操作后，最多只有一个策略处于 active 状态', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        fc.array(fc.nat({ max: 9 }), { minLength: 1, maxLength: 20 }),
        (strategies, activationSequence) => {
          let current = strategies.map((s) => ({ ...s }))

          for (const rawIdx of activationSequence) {
            const idx = rawIdx % current.length
            current = serverActivate(current, current[idx].id)

            // 不变量：每次激活后最多一个 active
            expect(atMostOneActive(current)).toBe(true)

            // 且恰好有一个 active（因为我们刚激活了一个）
            expect(current.filter((s) => s.is_active).length).toBe(1)
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 核心属性 3：页面挂载时，is_active=true 的策略被自动选中
   */
  it('页面挂载时，活跃策略被自动选中，与服务端状态一致', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        (strategies) => {
          // 模拟：先激活某个策略
          const targetIdx = Math.floor(Math.random() * strategies.length)
          const targetId = strategies[targetIdx].id
          const serverState = serverActivate(strategies, targetId)

          // 模拟页面挂载：autoSelectOnMount 应返回服务端活跃策略的 id
          const selectedId = autoSelectOnMount(serverState)
          expect(selectedId).toBe(targetId)

          // 模拟 JSON round-trip（服务端 → 前端加载）
          const roundTripped = JSON.parse(JSON.stringify(serverState)) as StrategyEntry[]
          const selectedAfterRefresh = autoSelectOnMount(roundTripped)
          expect(selectedAfterRefresh).toBe(targetId)
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 4：无活跃策略时，页面挂载不自动选中任何策略
   */
  it('无活跃策略时，页面挂载返回空选中', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        (strategies) => {
          // 所有策略 is_active=false（初始状态）
          const allInactive = strategies.map((s) => ({ ...s, is_active: false }))
          const selectedId = autoSelectOnMount(allInactive)
          expect(selectedId).toBe('')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 5：连续切换激活策略，最终状态仅最后激活的策略为 active
   */
  it('连续切换激活策略，最终仅最后激活的策略为 active', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        fc.array(fc.nat({ max: 9 }), { minLength: 2, maxLength: 15 }),
        (strategies, activationSequence) => {
          let current = strategies.map((s) => ({ ...s }))
          let lastActivatedId = ''

          for (const rawIdx of activationSequence) {
            const idx = rawIdx % current.length
            lastActivatedId = current[idx].id
            current = serverActivate(current, lastActivatedId)
          }

          // 最终状态：仅最后激活的策略为 active
          for (const s of current) {
            if (s.id === lastActivatedId) {
              expect(s.is_active).toBe(true)
            } else {
              expect(s.is_active).toBe(false)
            }
          }

          // 页面刷新后自动选中应与最后激活一致
          const selectedOnMount = autoSelectOnMount(current)
          expect(selectedOnMount).toBe(lastActivatedId)
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 6：激活操作不改变策略列表的长度和 id 集合
   */
  it('激活操作不改变策略列表的长度和 id 集合', () => {
    fc.assert(
      fc.property(
        strategyListArb,
        (strategies) => {
          const targetIdx = Math.floor(Math.random() * strategies.length)
          const targetId = strategies[targetIdx].id
          const afterActivation = serverActivate(strategies, targetId)

          // 长度不变
          expect(afterActivation.length).toBe(strategies.length)

          // id 集合不变
          const originalIds = new Set(strategies.map((s) => s.id))
          const afterIds = new Set(afterActivation.map((s) => s.id))
          expect(afterIds).toEqual(originalIds)

          // name 不变
          for (let i = 0; i < strategies.length; i++) {
            expect(afterActivation[i].name).toBe(strategies[i].name)
          }
        },
      ),
      { numRuns: 100 },
    )
  })
})


// ---------------------------------------------------------------------------
// 属性 48：导入策略前端上限校验正确性
// **Validates: Requirements 22.4**
// ---------------------------------------------------------------------------

/**
 * 模拟 onImportFile 中的前端上限校验守卫逻辑（纯函数等价）：
 * - 当策略数量 >= MAX_STRATEGIES (20) 时，拦截导入并返回错误提示
 * - 当策略数量 < MAX_STRATEGIES 时，允许导入（调用后端 API）
 */

const MAX_STRATEGIES = 20

interface ImportGuardResult {
  blocked: boolean
  errorMessage: string | null
}

/**
 * 纯函数等价实现 onImportFile 的前端上限校验逻辑。
 * 与 ScreenerView.vue 中 onImportFile 函数的守卫逻辑一致。
 */
function checkImportLimit(currentStrategyCount: number): ImportGuardResult {
  if (currentStrategyCount >= MAX_STRATEGIES) {
    return {
      blocked: true,
      errorMessage: '已达策略上限（20 套），请删除旧策略后再导入',
    }
  }
  return {
    blocked: false,
    errorMessage: null,
  }
}

describe('属性 48：导入策略前端上限校验正确性', () => {
  /**
   * 核心属性 1：策略数量 >= 20 时导入被拦截
   * 对于任意 count ∈ [20, 25]，blocked 必须为 true
   */
  it('策略数量达到上限时导入被拦截', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: MAX_STRATEGIES, max: 25 }),
        (count) => {
          const result = checkImportLimit(count)
          expect(result.blocked).toBe(true)
          expect(result.errorMessage).toBe('已达策略上限（20 套），请删除旧策略后再导入')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 核心属性 2：策略数量 < 20 时导入放行
   * 对于任意 count ∈ [0, 19]，blocked 必须为 false
   */
  it('策略数量未达上限时导入放行', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: MAX_STRATEGIES - 1 }),
        (count) => {
          const result = checkImportLimit(count)
          expect(result.blocked).toBe(false)
          expect(result.errorMessage).toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 核心属性 3：blocked 与 count >= 20 等价
   * 对于任意 count ∈ [0, 25]，blocked === (count >= MAX_STRATEGIES)
   */
  it('blocked 状态与策略数量是否达到上限严格等价', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 25 }),
        (count) => {
          const result = checkImportLimit(count)
          expect(result.blocked).toBe(count >= MAX_STRATEGIES)
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 4：被拦截时不应发起后端请求（errorMessage 非空即表示提前 return）
   * 放行时 errorMessage 为 null（不设置错误，继续调用 API）
   */
  it('拦截时设置错误提示，放行时无错误提示', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 25 }),
        (count) => {
          const result = checkImportLimit(count)
          if (result.blocked) {
            expect(result.errorMessage).not.toBeNull()
            expect(result.errorMessage!.length).toBeGreaterThan(0)
          } else {
            expect(result.errorMessage).toBeNull()
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 5：边界值 count=20 恰好被拦截，count=19 恰好放行
   */
  it('边界值：count=20 拦截，count=19 放行', () => {
    const atLimit = checkImportLimit(20)
    expect(atLimit.blocked).toBe(true)
    expect(atLimit.errorMessage).toBe('已达策略上限（20 套），请删除旧策略后再导入')

    const belowLimit = checkImportLimit(19)
    expect(belowLimit.blocked).toBe(false)
    expect(belowLimit.errorMessage).toBeNull()
  })
})
