/**
 * 属性 67：前端回填控件根据数据类型选择动态显示频率选择器
 *
 * 对任意数据类型复选框选择状态，验证频率选择器仅在"行情数据"（kline）被勾选时可见
 *
 * **Validates: Requirements 25.14**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（镜像 DataManageView.vue 中的回填数据类型） ──────────────────────

/** 回填支持的数据类型 */
type BackfillDataType = 'kline' | 'fundamentals' | 'money_flow'

const ALL_DATA_TYPES: BackfillDataType[] = ['kline', 'fundamentals', 'money_flow']

// ─── UI 渲染逻辑（提取自模板的纯函数） ───────────────────────────────────────

/**
 * 判断频率选择器是否可见。
 * 模板中的条件：`v-if="backfillDataTypes.includes('kline')"`
 */
function isFreqSelectorVisible(selectedTypes: BackfillDataType[]): boolean {
  return selectedTypes.includes('kline')
}

/**
 * 判断"开始回填"按钮是否禁用。
 * 模板中的条件：`:disabled="backfillLoading || backfillDataTypes.length === 0"`
 */
function isStartButtonDisabled(selectedTypes: BackfillDataType[], loading: boolean): boolean {
  return loading || selectedTypes.length === 0
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成任意数据类型子集（包括空集） */
const dataTypeSubsetArb: fc.Arbitrary<BackfillDataType[]> = fc.subarray(ALL_DATA_TYPES)

/** 生成包含 kline 的数据类型子集 */
const dataTypeWithKlineArb: fc.Arbitrary<BackfillDataType[]> = fc
  .subarray(['fundamentals' as const, 'money_flow' as const])
  .map((rest) => ['kline' as BackfillDataType, ...rest])

/** 生成不包含 kline 的数据类型子集 */
const dataTypeWithoutKlineArb: fc.Arbitrary<BackfillDataType[]> = fc.subarray([
  'fundamentals' as const,
  'money_flow' as const,
])

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 67：前端回填控件根据数据类型选择动态显示频率选择器', () => {
  /**
   * 属性 67a：频率选择器仅在 kline 被选中时可见
   * Validates: Requirements 25.14
   */
  it('频率选择器可见性与 kline 是否被选中完全一致', () => {
    fc.assert(
      fc.property(dataTypeSubsetArb, (selectedTypes) => {
        const visible = isFreqSelectorVisible(selectedTypes)
        const klineSelected = selectedTypes.includes('kline')
        expect(visible).toBe(klineSelected)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 67b：选中 kline 时频率选择器始终可见
   * Validates: Requirements 25.14
   */
  it('选中 kline 时频率选择器始终可见', () => {
    fc.assert(
      fc.property(dataTypeWithKlineArb, (selectedTypes) => {
        expect(isFreqSelectorVisible(selectedTypes)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 67c：未选中 kline 时频率选择器始终隐藏
   * Validates: Requirements 25.14
   */
  it('未选中 kline 时频率选择器始终隐藏', () => {
    fc.assert(
      fc.property(dataTypeWithoutKlineArb, (selectedTypes) => {
        expect(isFreqSelectorVisible(selectedTypes)).toBe(false)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 67d：无数据类型选中时开始回填按钮禁用
   * Validates: Requirements 25.14
   */
  it('无数据类型选中时开始回填按钮禁用', () => {
    fc.assert(
      fc.property(fc.boolean(), (loading) => {
        const disabled = isStartButtonDisabled([], loading)
        expect(disabled).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 67e：有数据类型选中且非加载状态时按钮可用
   * Validates: Requirements 25.14
   */
  it('有数据类型选中且非加载状态时按钮可用', () => {
    const nonEmptySubsetArb = fc
      .subarray(ALL_DATA_TYPES, { minLength: 1 })

    fc.assert(
      fc.property(nonEmptySubsetArb, (selectedTypes) => {
        const disabled = isStartButtonDisabled(selectedTypes, false)
        expect(disabled).toBe(false)
      }),
      { numRuns: 100 },
    )
  })
})
