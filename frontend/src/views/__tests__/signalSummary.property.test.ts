/**
 * Feature: signal-detail-enhancement, Property 4: Signal summary strong count
 *
 * For any list of SignalDetail objects with varying strength values,
 * the signal summary string SHALL include the count of STRONG signals
 * if and only if at least one signal has strength === 'STRONG'.
 * When no signals are STRONG, the summary SHALL contain only the total
 * signal count without a strong count annotation.
 *
 * **Validates: Requirements 7.1, 7.2**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（与 ScreenerResultsView.vue 保持一致）─────────────────────────

type SignalCategory =
  | 'MA_TREND' | 'MACD' | 'BOLL' | 'RSI' | 'DMA'
  | 'BREAKOUT' | 'CAPITAL_INFLOW' | 'LARGE_ORDER'
  | 'MA_SUPPORT' | 'SECTOR_STRONG'

interface SignalDetail {
  category: SignalCategory
  label: string
  is_fake_breakout: boolean
  strength?: 'STRONG' | 'MEDIUM' | 'WEAK'
  freshness?: 'NEW' | 'CONTINUING'
  description?: string
}

// ─── 常量（与 ScreenerResultsView.vue 保持一致）─────────────────────────────

const SIGNAL_CATEGORY_LABEL: Record<string, string> = {
  MA_TREND: '均线趋势',
  MACD: 'MACD',
  BOLL: '布林带',
  RSI: 'RSI',
  DMA: 'DMA',
  BREAKOUT: '形态突破',
  CAPITAL_INFLOW: '资金流入',
  LARGE_ORDER: '大单活跃',
  MA_SUPPORT: '均线支撑',
  SECTOR_STRONG: '板块强势',
}

// ─── 被测函数（从 ScreenerResultsView.vue 复制，因未导出）────────────────────

function signalSummary(signals: SignalDetail[]): string {
  if (!signals.length) return '无信号'
  const strongCount = signals.filter(s => s.strength === 'STRONG').length
  const base = strongCount > 0
    ? `${signals.length} 个信号（${strongCount} 强）`
    : `${signals.length} 个信号`
  const cats = [...new Set(signals.map((s) => SIGNAL_CATEGORY_LABEL[s.category] ?? s.category))]
  return `${base}：${cats.slice(0, 3).join(' / ')}${cats.length > 3 ? ' …' : ''}`
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const SIGNAL_CATEGORIES: SignalCategory[] = [
  'MA_TREND', 'MACD', 'BOLL', 'RSI', 'DMA',
  'BREAKOUT', 'CAPITAL_INFLOW', 'LARGE_ORDER',
  'MA_SUPPORT', 'SECTOR_STRONG',
]

const STRENGTHS: Array<'STRONG' | 'MEDIUM' | 'WEAK'> = ['STRONG', 'MEDIUM', 'WEAK']

/** 生成任意 SignalDetail 对象 */
const signalDetailArb: fc.Arbitrary<SignalDetail> = fc.record({
  category: fc.constantFrom(...SIGNAL_CATEGORIES),
  label: fc.string({ minLength: 1, maxLength: 20 }),
  is_fake_breakout: fc.boolean(),
  strength: fc.constantFrom<'STRONG' | 'MEDIUM' | 'WEAK'>(...STRENGTHS),
  freshness: fc.constantFrom<'NEW' | 'CONTINUING'>('NEW', 'CONTINUING'),
  description: fc.option(fc.string({ minLength: 0, maxLength: 50 }), { nil: undefined }),
})

/** 生成非空信号列表（1~20 个信号） */
const nonEmptySignalsArb = fc.array(signalDetailArb, { minLength: 1, maxLength: 20 })

/** 生成至少包含一个 STRONG 信号的列表 */
const signalsWithAtLeastOneStrongArb = fc
  .tuple(
    fc.array(signalDetailArb, { minLength: 0, maxLength: 19 }),
    signalDetailArb.map(s => ({ ...s, strength: 'STRONG' as const })),
  )
  .chain(([others, strong]) =>
    fc.shuffledSubarray([...others, strong], { minLength: others.length + 1, maxLength: others.length + 1 })
      .map(() => {
        // 将 strong 信号插入随机位置
        const arr = [...others]
        const pos = Math.floor(Math.random() * (arr.length + 1))
        arr.splice(pos, 0, strong)
        return arr
      }),
  )

/** 生成不包含任何 STRONG 信号的非空列表 */
const signalsWithNoStrongArb = fc.array(
  signalDetailArb.map(s => ({
    ...s,
    strength: (Math.random() < 0.5 ? 'MEDIUM' : 'WEAK') as 'MEDIUM' | 'WEAK',
  })),
  { minLength: 1, maxLength: 20 },
)

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: signal-detail-enhancement, Property 4: Signal summary strong count', () => {
  /**
   * Property 4a: 空信号列表返回"无信号"
   * Validates: Requirements 7.1, 7.2
   */
  it('空信号列表返回"无信号"', () => {
    const result = signalSummary([])
    expect(result).toBe('无信号')
  })

  /**
   * Property 4b: 当至少一个信号为 STRONG 时，摘要包含"（M 强）"
   * Validates: Requirements 7.1
   */
  it('至少一个 STRONG 信号时，摘要包含强信号数量标注', () => {
    fc.assert(
      fc.property(signalsWithAtLeastOneStrongArb, (signals) => {
        const result = signalSummary(signals)
        const strongCount = signals.filter(s => s.strength === 'STRONG').length
        expect(strongCount).toBeGreaterThan(0)
        expect(result).toContain(`（${strongCount} 强）`)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 4c: 当没有 STRONG 信号时，摘要不包含"强）"
   * Validates: Requirements 7.2
   */
  it('无 STRONG 信号时，摘要不包含"强）"', () => {
    fc.assert(
      fc.property(signalsWithNoStrongArb, (signals) => {
        const result = signalSummary(signals)
        expect(result).not.toContain('强）')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * Property 4d: 摘要包含"（M 强）"当且仅当至少一个信号为 STRONG（双向验证）
   * Validates: Requirements 7.1, 7.2
   */
  it('摘要包含强信号标注 ⟺ 至少一个信号为 STRONG', () => {
    fc.assert(
      fc.property(nonEmptySignalsArb, (signals) => {
        const result = signalSummary(signals)
        const strongCount = signals.filter(s => s.strength === 'STRONG').length
        const hasStrongAnnotation = /（\d+ 强）/.test(result)

        if (strongCount > 0) {
          // 有 STRONG 信号 → 摘要必须包含强信号标注
          expect(hasStrongAnnotation).toBe(true)
          expect(result).toContain(`（${strongCount} 强）`)
        } else {
          // 无 STRONG 信号 → 摘要不包含强信号标注
          expect(hasStrongAnnotation).toBe(false)
        }
      }),
      { numRuns: 100 },
    )
  })
})
