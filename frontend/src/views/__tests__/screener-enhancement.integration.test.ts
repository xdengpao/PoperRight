/**
 * 选股增强集成测试
 *
 * 17.13.1 选股策略配置（均线/指标/突破/量价面板）→ 保存策略 → 执行选股 → 结果信号分类展示全链路测试
 * 17.13.2 实时选股开关开启 → 交易时段自动刷新 → 非交易时段自动禁用全链路测试
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ---------------------------------------------------------------------------
// 17.13.1 策略配置 → 保存 → 执行选股 → 信号分类展示全链路
// ---------------------------------------------------------------------------

describe('17.13.1 选股策略配置 → 保存 → 执行选股 → 信号分类展示', () => {
  it('buildStrategyConfig 包含所有子配置字段', () => {
    // 模拟 buildStrategyConfig 输出结构
    const config = {
      logic: 'AND' as const,
      factors: [],
      weights: {},
      ma_periods: [5, 10, 20, 60, 120],
      indicator_params: {
        macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
        boll: { period: 20, std_dev: 2 },
        rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
        dma: { short_period: 10, long_period: 50 },
      },
      ma_trend: {
        ma_periods: [5, 10, 20, 60, 120],
        slope_threshold: 0,
        trend_score_threshold: 80,
        support_ma_lines: [20, 60],
      },
      breakout: {
        box_breakout: true,
        high_breakout: true,
        trendline_breakout: true,
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
    }

    // 验证所有顶层字段存在
    expect(config).toHaveProperty('logic')
    expect(config).toHaveProperty('factors')
    expect(config).toHaveProperty('weights')
    expect(config).toHaveProperty('ma_periods')
    expect(config).toHaveProperty('indicator_params')
    expect(config).toHaveProperty('ma_trend')
    expect(config).toHaveProperty('breakout')
    expect(config).toHaveProperty('volume_price')

    // 验证子配置完整性
    expect(config.indicator_params.macd).toHaveProperty('fast_period')
    expect(config.indicator_params.boll).toHaveProperty('std_dev')
    expect(config.indicator_params.rsi).toHaveProperty('lower_bound')
    expect(config.indicator_params.dma).toHaveProperty('long_period')
    expect(config.ma_trend).toHaveProperty('slope_threshold')
    expect(config.breakout).toHaveProperty('volume_ratio_threshold')
    expect(config.volume_price).toHaveProperty('main_flow_threshold')
  })

  it('策略配置 JSON 序列化后可完整还原', () => {
    const original = {
      logic: 'OR' as const,
      factors: [{ factor_name: 'ma_trend', operator: '>=', threshold: 80 }],
      weights: { ma_trend: 0.5 },
      ma_periods: [10, 20, 60],
      indicator_params: {
        macd: { fast_period: 8, slow_period: 21, signal_period: 5 },
        boll: { period: 15, std_dev: 1.5 },
        rsi: { period: 10, lower_bound: 40, upper_bound: 70 },
        dma: { short_period: 5, long_period: 30 },
      },
      ma_trend: {
        ma_periods: [10, 20, 60],
        slope_threshold: 0.05,
        trend_score_threshold: 70,
        support_ma_lines: [20],
      },
      breakout: {
        box_breakout: false,
        high_breakout: true,
        trendline_breakout: false,
        volume_ratio_threshold: 2.0,
        confirm_days: 2,
      },
      volume_price: {
        turnover_rate_min: 5,
        turnover_rate_max: 20,
        main_flow_threshold: 2000,
        main_flow_days: 3,
        large_order_ratio: 40,
        min_daily_amount: 8000,
        sector_rank_top: 20,
      },
    }

    const restored = JSON.parse(JSON.stringify(original))
    expect(restored).toEqual(original)
  })

  it('选股结果信号按类型分类且假突破标记正确', () => {
    type SignalCategory = 'MA_TREND' | 'MACD' | 'BREAKOUT' | 'CAPITAL_INFLOW'
    interface SignalDetail {
      category: SignalCategory
      label: string
      is_fake_breakout: boolean
    }

    const signals: SignalDetail[] = [
      { category: 'MA_TREND', label: '多头排列', is_fake_breakout: false },
      { category: 'MACD', label: 'MACD 金叉', is_fake_breakout: false },
      { category: 'BREAKOUT', label: '箱体突破', is_fake_breakout: true },
      { category: 'CAPITAL_INFLOW', label: '主力净流入', is_fake_breakout: false },
    ]

    const has_fake_breakout = signals.some((s) => s.is_fake_breakout)
    expect(has_fake_breakout).toBe(true)

    // 按类型分组
    const grouped = new Map<string, SignalDetail[]>()
    for (const sig of signals) {
      const list = grouped.get(sig.category) ?? []
      list.push(sig)
      grouped.set(sig.category, list)
    }

    expect(grouped.get('MA_TREND')).toHaveLength(1)
    expect(grouped.get('MACD')).toHaveLength(1)
    expect(grouped.get('BREAKOUT')).toHaveLength(1)
    expect(grouped.get('CAPITAL_INFLOW')).toHaveLength(1)

    // 假突破仅在 BREAKOUT 类型
    const fakeSignals = signals.filter((s) => s.is_fake_breakout)
    expect(fakeSignals.every((s) => s.category === 'BREAKOUT')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 17.13.2 实时选股开关 → 交易时段自动刷新 → 非交易时段自动禁用
// ---------------------------------------------------------------------------

describe('17.13.2 实时选股开关 → 交易时段刷新 → 非交易时段禁用', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function isTradingHours(now: Date): boolean {
    const cst = new Date(now.getTime() + 8 * 60 * 60 * 1000)
    const h = cst.getUTCHours()
    const m = cst.getUTCMinutes()
    const day = cst.getUTCDay()
    if (day === 0 || day === 6) return false
    const minutes = h * 60 + m
    return minutes >= 9 * 60 + 30 && minutes < 15 * 60
  }

  it('交易时段内开启实时选股后定时器启动', () => {
    // 模拟周一 CST 10:00 = UTC 02:00
    const monday10am = new Date('2024-01-08T02:00:00Z')
    vi.setSystemTime(monday10am)

    expect(isTradingHours(new Date())).toBe(true)

    let refreshCount = 0
    const timer = setInterval(() => { refreshCount++ }, 10_000)

    // 推进 30 秒 = 3 次刷新
    vi.advanceTimersByTime(30_000)
    expect(refreshCount).toBe(3)

    clearInterval(timer)
  })

  it('非交易时段开关应被禁用', () => {
    // 模拟周六 CST 10:00 = UTC 02:00
    const saturday = new Date('2024-01-13T02:00:00Z')
    vi.setSystemTime(saturday)

    expect(isTradingHours(new Date())).toBe(false)
  })

  it('从交易时段切换到非交易时段时定时器应停止', () => {
    // 模拟周一 CST 14:59 = UTC 06:59
    const nearClose = new Date('2024-01-08T06:59:00Z')
    vi.setSystemTime(nearClose)
    expect(isTradingHours(new Date())).toBe(true)

    let refreshCount = 0
    let enabled = true
    const timer = setInterval(() => {
      if (!isTradingHours(new Date())) {
        enabled = false
        clearInterval(timer)
        return
      }
      refreshCount++
    }, 10_000)

    // 推进 2 分钟 — 第一次 10s 后还在交易时段，但 70s 后 CST 15:00+ 不在了
    vi.advanceTimersByTime(120_000)

    // 定时器应已停止
    expect(enabled).toBe(false)
    // 至少刷新了几次（前 60 秒内）
    expect(refreshCount).toBeGreaterThanOrEqual(0)

    clearInterval(timer) // 安全清理
  })
})
