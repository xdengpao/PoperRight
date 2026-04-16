/**
 * 频率标签提取属性测试（Vitest + fast-check）
 *
 * 验证 getTemplateFreqLabel() 对任意 ExitTemplate 输入返回正确的频率标签。
 *
 * **Validates: Requirements 5.1**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { getTemplateFreqLabel } from '@/stores/backtest'
import type { ExitTemplate } from '@/stores/backtest'

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const MINUTE_FREQS = ['1min', '5min', '15min', '30min', '60min'] as const
const ALL_FREQS = ['daily', ...MINUTE_FREQS] as const

const FREQ_LABEL_MAP: Record<string, string> = {
  '1min': '1分钟',
  '5min': '5分钟',
  '15min': '15分钟',
  '30min': '30分钟',
  '60min': '60分钟',
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成单个条件对象 */
function conditionArb(freqArb: fc.Arbitrary<string>) {
  return fc.record({
    freq: freqArb,
    indicator: fc.constantFrom('rsi', 'macd_dif', 'close', 'ma', 'boll_upper'),
    operator: fc.constantFrom('>', '<', 'cross_down', 'cross_up'),
    threshold: fc.oneof(fc.constant(null), fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true })),
    cross_target: fc.oneof(fc.constant(null), fc.constantFrom('ma', 'boll_middle', 'macd_dea')),
    params: fc.constant({} as Record<string, number>),
  })
}

/** 生成仅含 daily 频率条件的列表（至少 1 个） */
const dailyOnlyConditionsArb = fc.array(conditionArb(fc.constant('daily')), { minLength: 1, maxLength: 5 })

/** 生成含单一分钟频率条件的列表（至少 1 个，可混合 daily） */
function singleMinuteFreqConditionsArb(minuteFreq: string) {
  return fc.array(
    conditionArb(fc.constantFrom('daily', minuteFreq)),
    { minLength: 1, maxLength: 5 },
  ).filter(conditions => conditions.some(c => c.freq === minuteFreq))
}

/** 生成含多个不同分钟频率条件的列表 */
const multiMinuteFreqConditionsArb = fc
  .uniqueArray(fc.constantFrom(...MINUTE_FREQS), { minLength: 2, maxLength: 5 })
  .chain(freqs => {
    // Ensure at least one condition per selected minute freq
    const requiredConditions = freqs.map(f => conditionArb(fc.constant(f)))
    const extraConditions = fc.array(
      conditionArb(fc.constantFrom('daily', ...freqs)),
      { minLength: 0, maxLength: 3 },
    )
    return fc.tuple(fc.tuple(...requiredConditions), extraConditions).map(
      ([required, extra]) => [...required, ...extra],
    )
  })

/** 构建 ExitTemplate 壳 */
function makeTemplate(
  conditions: Array<{
    freq: string
    indicator: string
    operator: string
    threshold: number | null
    cross_target: string | null
    params: Record<string, number>
  }>,
  logic: 'AND' | 'OR' = 'AND',
): ExitTemplate {
  return {
    id: 'test-id',
    name: 'test',
    description: null,
    exit_conditions: { conditions, logic },
    is_system: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('频率标签提取属性测试: getTemplateFreqLabel()', () => {
  /**
   * 属性 1：无条件的模版返回 null
   * **Validates: Requirements 5.1**
   */
  it('无条件的模版返回 null', () => {
    fc.assert(
      fc.property(fc.constantFrom<'AND' | 'OR'>('AND', 'OR'), (logic) => {
        const template = makeTemplate([], logic)
        expect(getTemplateFreqLabel(template)).toBeNull()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 2：仅含 daily 频率条件的模版返回 null
   * **Validates: Requirements 5.1**
   */
  it('仅含 daily 频率条件的模版返回 null', () => {
    fc.assert(
      fc.property(dailyOnlyConditionsArb, (conditions) => {
        const template = makeTemplate(conditions)
        expect(getTemplateFreqLabel(template)).toBeNull()
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 3：含单一分钟频率的模版返回对应中文标签
   * **Validates: Requirements 5.1**
   */
  it('含单一分钟频率的模版返回对应中文标签', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...MINUTE_FREQS).chain(freq =>
          singleMinuteFreqConditionsArb(freq).map(conditions => ({ freq, conditions })),
        ),
        ({ freq, conditions }) => {
          const template = makeTemplate(conditions)
          const result = getTemplateFreqLabel(template)
          expect(result).toBe(FREQ_LABEL_MAP[freq])
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 4：含多个不同分钟频率的模版返回 '多频率'
   * **Validates: Requirements 5.1**
   */
  it('含多个不同分钟频率的模版返回 多频率', () => {
    fc.assert(
      fc.property(multiMinuteFreqConditionsArb, (conditions) => {
        const template = makeTemplate(conditions)
        expect(getTemplateFreqLabel(template)).toBe('多频率')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 5：混合 daily + 单一分钟频率条件返回分钟频率标签
   * **Validates: Requirements 5.1**
   */
  it('混合 daily + 单一分钟频率条件返回分钟频率标签', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...MINUTE_FREQS),
        fc.array(conditionArb(fc.constant('daily')), { minLength: 1, maxLength: 3 }),
        fc.array(conditionArb(fc.constant('placeholder')), { minLength: 1, maxLength: 3 }),
        (minuteFreq, dailyConditions, minuteConditionsRaw) => {
          // Replace placeholder freq with the actual minute freq
          const minuteConditions = minuteConditionsRaw.map(c => ({ ...c, freq: minuteFreq }))
          const allConditions = [...dailyConditions, ...minuteConditions]
          const template = makeTemplate(allConditions)
          expect(getTemplateFreqLabel(template)).toBe(FREQ_LABEL_MAP[minuteFreq])
        },
      ),
      { numRuns: 100 },
    )
  })
})
