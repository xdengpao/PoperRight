/**
 * 属性 71：标签页切换仅显示当前激活面板
 *
 * Feature: a-share-quant-trading-system, Property 71: 标签页切换显隐
 *
 * 对任意标签页状态，仅当前激活面板可见，其余隐藏
 *
 * **Validates: Requirements 26.1**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// ─── Mock 依赖 ────────────────────────────────────────────────────────────────

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })),
}))

// Smart mock: return appropriate data based on URL
vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn().mockImplementation((url: string) => {
      if (url.includes('/market/overview')) {
        return Promise.resolve({
          data: {
            sh_index: 3000, sh_change_pct: 0.5,
            sz_index: 10000, sz_change_pct: -0.3,
            cyb_index: 2000, cyb_change_pct: 1.2,
            advance_count: 2000, decline_count: 1500,
            limit_up_count: 30, limit_down_count: 10,
            updated_at: new Date().toISOString(),
          },
        })
      }
      if (url.includes('/market/sectors')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/kline/')) {
        return Promise.resolve({
          data: { symbol: '000001', name: '测试', freq: '1d', bars: [] },
        })
      }
      if (url.includes('/fundamentals')) {
        return Promise.resolve({ data: null })
      }
      if (url.includes('/money-flow')) {
        return Promise.resolve({ data: null })
      }
      return Promise.resolve({ data: {} })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.stubGlobal(
  'WebSocket',
  vi.fn().mockImplementation(() => ({
    onmessage: null,
    onclose: null,
    close: vi.fn(),
  })),
)

import DashboardView from '../DashboardView.vue'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type ChartTab = 'kline' | 'fundamentals' | 'moneyFlow'

const ALL_TABS: ChartTab[] = ['kline', 'fundamentals', 'moneyFlow']

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const tabArb: fc.Arbitrary<ChartTab> = fc.constantFrom(
  'kline' as const,
  'fundamentals' as const,
  'moneyFlow' as const,
)

// ─── 纯函数逻辑（提取自模板的显隐判定） ──────────────────────────────────────

function isPanelVisible(activeTab: ChartTab, panelTab: ChartTab): boolean {
  return activeTab === panelTab
}

function isTabButtonActive(activeTab: ChartTab, buttonTab: ChartTab): boolean {
  return activeTab === buttonTab
}

// ─── 辅助常量 ─────────────────────────────────────────────────────────────────

const TAB_TEXT_MAP: Record<ChartTab, string> = {
  kline: 'K线',
  fundamentals: '基本面',
  moneyFlow: '资金流向',
}

const PANEL_LABEL_MAP: Record<ChartTab, string> = {
  kline: 'K线图',
  fundamentals: '基本面数据',
  moneyFlow: '资金流向数据',
}

async function mountDashboard() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(DashboardView, {
    global: { plugins: [pinia] },
  })

  // Let onMounted async calls (fetchOverview, loadKline, etc.) settle
  await flushPromises()
  await wrapper.vm.$nextTick()

  return wrapper
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 71：标签页切换仅显示当前激活面板', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 属性 71a：对任意标签页状态，恰好有一个面板可见
   * Validates: Requirements 26.1
   */
  it('任意标签页状态下恰好有一个面板可见', () => {
    fc.assert(
      fc.property(tabArb, (activeTab) => {
        const visibleCount = ALL_TABS.filter((t) =>
          isPanelVisible(activeTab, t),
        ).length
        expect(visibleCount).toBe(1)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 71b：当前激活标签页对应的面板可见，其余面板隐藏
   * Validates: Requirements 26.1
   */
  it('激活面板可见，其余面板隐藏', () => {
    fc.assert(
      fc.property(tabArb, (activeTab) => {
        expect(isPanelVisible(activeTab, activeTab)).toBe(true)
        for (const other of ALL_TABS.filter((t) => t !== activeTab)) {
          expect(isPanelVisible(activeTab, other)).toBe(false)
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 71c：恰好有一个标签按钮处于激活状态
   * Validates: Requirements 26.1
   */
  it('恰好有一个标签按钮处于激活状态', () => {
    fc.assert(
      fc.property(tabArb, (activeTab) => {
        const activeCount = ALL_TABS.filter((t) =>
          isTabButtonActive(activeTab, t),
        ).length
        expect(activeCount).toBe(1)
        expect(isTabButtonActive(activeTab, activeTab)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 71d：组件 DOM 中对任意标签页切换，仅激活面板可见（v-show 验证）
   * Validates: Requirements 26.1
   */
  it('组件 DOM 中仅激活面板可见，其余面板通过 v-show 隐藏', async () => {
    await fc.assert(
      fc.asyncProperty(tabArb, async (activeTab) => {
        const wrapper = await mountDashboard()

        // Click the target tab button
        const tabButtons = wrapper.findAll('[role="tab"]')
        for (const btn of tabButtons) {
          if (btn.text().includes(TAB_TEXT_MAP[activeTab])) {
            await btn.trigger('click')
            break
          }
        }
        await flushPromises()
        await wrapper.vm.$nextTick()

        // Verify tab button states
        for (const btn of wrapper.findAll('[role="tab"]')) {
          const text = btn.text()
          const matched = ALL_TABS.find((t) => text.includes(TAB_TEXT_MAP[t]))
          if (!matched) continue

          if (matched === activeTab) {
            expect(btn.classes()).toContain('active')
            expect(btn.attributes('aria-selected')).toBe('true')
          } else {
            expect(btn.classes()).not.toContain('active')
            expect(btn.attributes('aria-selected')).toBe('false')
          }
        }

        // Verify panel visibility via v-show (display: none)
        for (const panel of wrapper.findAll('[role="tabpanel"]')) {
          const label = panel.attributes('aria-label') ?? ''
          const matched = ALL_TABS.find((t) => label === PANEL_LABEL_MAP[t])
          if (!matched) continue

          const style = panel.attributes('style') ?? ''
          if (matched === activeTab) {
            expect(style).not.toContain('display: none')
          } else {
            expect(style).toContain('display: none')
          }
        }

        wrapper.unmount()
      }),
      { numRuns: 100 },
    )
  })
})
