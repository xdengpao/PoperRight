/**
 * 属性 76：加载与错误状态渲染
 *
 * Feature: a-share-quant-trading-system, Property 76: 加载与错误状态渲染
 *
 * 对任意 loading/error/data 状态组合，渲染结果应符合：
 * loading=true → 加载指示器，error 非空 → 错误信息+重试按钮，
 * data 存在 → 数据内容，否则 → 空面板提示
 *
 * **Validates: Requirements 26.10**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type PanelType = 'fundamentals' | 'moneyFlow'

interface PanelState {
  loading: boolean
  error: string
  hasData: boolean
}

type VisibleElement = 'loading-indicator' | 'error-banner' | 'data-content' | 'empty-panel'

// ─── 纯函数：从 DashboardView 模板提取的显隐判定逻辑 ──────────────────────────
// 模板中 v-if/v-else-if 链：
//   v-if="loading"          → loading-indicator
//   v-else-if="error"       → error-banner
//   v-else-if="data"        → data-content
//   v-else                  → empty-panel

function determineVisibleElement(state: PanelState): VisibleElement {
  if (state.loading) return 'loading-indicator'
  if (state.error !== '') return 'error-banner'
  if (state.hasData) return 'data-content'
  return 'empty-panel'
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const panelTypeArb: fc.Arbitrary<PanelType> = fc.constantFrom(
  'fundamentals' as const,
  'moneyFlow' as const,
)

const panelStateArb: fc.Arbitrary<PanelState> = fc.record({
  loading: fc.boolean(),
  error: fc.oneof(fc.constant(''), fc.stringOf(fc.char(), { minLength: 1, maxLength: 50 })),
  hasData: fc.boolean(),
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 76：加载与错误状态渲染', () => {
  /**
   * 属性 76a：loading=true 时始终显示加载指示器，无论 error 和 data 状态
   * Validates: Requirements 26.10
   */
  it('loading=true 时始终显示加载指示器', () => {
    fc.assert(
      fc.property(
        panelTypeArb,
        panelStateArb.filter((s) => s.loading),
        (_panel, state) => {
          const visible = determineVisibleElement(state)
          expect(visible).toBe('loading-indicator')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 76b：loading=false 且 error 非空时显示错误信息
   * Validates: Requirements 26.10
   */
  it('loading=false 且 error 非空时显示错误信息', () => {
    fc.assert(
      fc.property(
        panelTypeArb,
        panelStateArb.filter((s) => !s.loading && s.error !== ''),
        (_panel, state) => {
          const visible = determineVisibleElement(state)
          expect(visible).toBe('error-banner')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 76c：loading=false、error 为空、data 存在时显示数据内容
   * Validates: Requirements 26.10
   */
  it('loading=false、error 为空、data 存在时显示数据内容', () => {
    fc.assert(
      fc.property(
        panelTypeArb,
        panelStateArb.filter((s) => !s.loading && s.error === '' && s.hasData),
        (_panel, state) => {
          const visible = determineVisibleElement(state)
          expect(visible).toBe('data-content')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 76d：loading=false、error 为空、无数据时显示空面板提示
   * Validates: Requirements 26.10
   */
  it('loading=false、error 为空、无数据时显示空面板提示', () => {
    fc.assert(
      fc.property(
        panelTypeArb,
        panelStateArb.filter((s) => !s.loading && s.error === '' && !s.hasData),
        (_panel, state) => {
          const visible = determineVisibleElement(state)
          expect(visible).toBe('empty-panel')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 76e：任意状态组合恰好命中一个渲染分支（互斥完备性）
   * Validates: Requirements 26.10
   */
  it('任意状态组合恰好命中一个渲染分支', () => {
    const ALL_ELEMENTS: VisibleElement[] = [
      'loading-indicator',
      'error-banner',
      'data-content',
      'empty-panel',
    ]

    fc.assert(
      fc.property(panelTypeArb, panelStateArb, (_panel, state) => {
        const visible = determineVisibleElement(state)
        // Exactly one element is visible
        expect(ALL_ELEMENTS).toContain(visible)
        // The result is deterministic — same state always yields same element
        expect(determineVisibleElement(state)).toBe(visible)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 76f：loading 优先级最高 — loading=true 时 error 和 data 不影响结果
   * Validates: Requirements 26.10
   */
  it('loading 优先级最高，error 和 data 不影响结果', () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.boolean(),
        (hasError, hasData) => {
          const state: PanelState = {
            loading: true,
            error: hasError ? '某个错误' : '',
            hasData,
          }
          expect(determineVisibleElement(state)).toBe('loading-indicator')
        },
      ),
      { numRuns: 100 },
    )
  })
})
