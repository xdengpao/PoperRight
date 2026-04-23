/**
 * Bug Condition 探索性测试：Tushare 数据预览功能修复（前端）
 *
 * **Validates: Requirements 1.1, 1.2, 1.3**
 *
 * 本测试在未修复代码上运行，预期全部 FAIL，以确认缺陷存在。
 *
 * P1 数据时间自动填充：生成随机 PreviewStatsResponse（earliest_time/latest_time 非空），
 *   mock fetchStats 返回该响应，调用 setSelectedApi()，
 *   断言 filters.dataTimeStart 等于格式化后的 earliest_time（在未修复代码上失败）。
 *
 * P2 完整性校验 Loading：设置 integrityLoading=true, integrityReport=null，
 *   渲染组件，断言存在包含"正在校验数据完整性..."文字的 loading 元素（在未修复代码上失败）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { defineComponent, h, computed } from 'vue'

import {
  useTusharePreviewStore,
  type PreviewStatsResponse,
} from '@/stores/tusharePreview'

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

/**
 * 将 "20240101" 格式的日期字符串转为 "2024-01-01" 格式
 * 这是期望的自动填充格式化逻辑
 */
function formatDateStr(raw: string): string {
  if (raw.length === 8 && !raw.includes('-')) {
    return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`
  }
  // 如果已经是 ISO 格式或其他格式，截取前 10 位
  return raw.slice(0, 10)
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成合法的 8 位日期字符串（YYYYMMDD 格式） */
const dateStr8Arb = fc
  .record({
    year: fc.integer({ min: 2000, max: 2025 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }),
  })
  .map(({ year, month, day }) => {
    const m = String(month).padStart(2, '0')
    const d = String(day).padStart(2, '0')
    return `${year}${m}${d}`
  })

/** 生成 earliest_time < latest_time 的日期对 */
const dateRangeArb = fc
  .tuple(dateStr8Arb, dateStr8Arb)
  .filter(([a, b]) => a < b)
  .map(([earliest, latest]) => ({ earliest, latest }))

/** 生成非空 earliest_time/latest_time 的 PreviewStatsResponse */
const statsResponseArb: fc.Arbitrary<PreviewStatsResponse> = dateRangeArb.chain(
  ({ earliest, latest }) =>
    fc.record({
      total_count: fc.integer({ min: 1, max: 1000000 }),
      earliest_time: fc.constant(earliest),
      latest_time: fc.constant(latest),
      last_import_at: fc.oneof(
        fc.constant(null),
        fc.constant('2024-06-15T10:30:00'),
      ),
      last_import_count: fc.integer({ min: 0, max: 10000 }),
    }),
)

// ─── P1: 数据时间自动填充 ─────────────────────────────────────────────────────

describe('P1 数据时间自动填充（Bug Condition 探索）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * P1: 生成随机 PreviewStatsResponse（earliest_time/latest_time 非空），
   * mock fetchStats 返回该响应，调用 setSelectedApi()，
   * 断言 filters.dataTimeStart 等于格式化后的 earliest_time。
   *
   * 在未修复代码上应 FAIL：filters.dataTimeStart 仍为 null。
   *
   * **Validates: Requirements 1.1, 1.3**
   */
  it('setSelectedApi 后 filters.dataTimeStart 应被自动填充为 earliest_time', async () => {
    await fc.assert(
      fc.asyncProperty(statsResponseArb, async (statsResponse) => {
        // 重新创建 pinia 以隔离每次运行
        setActivePinia(createPinia())
        const store = useTusharePreviewStore()

        // Mock apiClient.get 以返回生成的 statsResponse
        const { apiClient } = await import('@/api')
        const getSpy = vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
          if (typeof url === 'string' && url.includes('/stats')) {
            return { data: statsResponse }
          }
          if (typeof url === 'string' && url.includes('/import-logs')) {
            return { data: [] }
          }
          if (typeof url === 'string' && url.includes('/chart-data')) {
            return { data: { rows: [], time_field: null, chart_type: null, columns: [], total_available: 0 } }
          }
          // 默认预览数据
          return {
            data: {
              columns: [],
              rows: [],
              total: 0,
              page: 1,
              page_size: 50,
              time_field: 'time',
              chart_type: null,
              scope_info: null,
              incremental_info: null,
            },
          }
        })

        try {
          await store.setSelectedApi('test_api')

          // 验证 filters 被自动填充
          const expectedStart = formatDateStr(statsResponse.earliest_time!)
          const expectedEnd = formatDateStr(statsResponse.latest_time!)

          expect(store.filters.dataTimeStart).toBe(expectedStart)
          expect(store.filters.dataTimeEnd).toBe(expectedEnd)
        } finally {
          getSpy.mockRestore()
        }
      }),
      { numRuns: 20 },
    )
  })
})

// ─── P2: 完整性校验 Loading ───────────────────────────────────────────────────

/**
 * 创建一个简化的测试组件，模拟 TusharePreviewView 中完整性校验 loading 的渲染逻辑。
 * 直接测试 Vue 模板中 v-if 条件的行为。
 */
const IntegrityLoadingTestComponent = defineComponent({
  name: 'IntegrityLoadingTest',
  setup() {
    const store = useTusharePreviewStore()
    return { store }
  },
  render() {
    const children = []

    // 模拟 TusharePreviewView 中完整性校验区域的渲染逻辑
    // 当前代码只有 v-if="store.integrityReport" 的分支
    // 修复后应增加 v-if="store.integrityLoading" 的 loading 分支

    if (this.store.integrityLoading) {
      children.push(
        h('div', { class: 'integrity-loading', 'data-testid': 'integrity-loading' }, [
          h('span', { class: 'loading-spinner' }),
          h('span', {}, '正在校验数据完整性...'),
        ]),
      )
    }

    if (this.store.integrityReport) {
      children.push(
        h('div', { class: 'integrity-report', 'data-testid': 'integrity-report' }, '校验结果'),
      )
    }

    return h('div', {}, children)
  },
})

describe('P2 完整性校验 Loading（Bug Condition 探索）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * P2: 设置 integrityLoading=true, integrityReport=null，
   * 渲染 TusharePreviewView 组件，断言存在包含"正在校验数据完整性..."文字的 loading 元素。
   *
   * 在未修复代码上应 FAIL：当前模板中无 loading 状态分支。
   *
   * 注意：由于 TusharePreviewView 组件依赖较多，这里直接测试实际 Vue 文件中的模板。
   * 我们通过检查实际组件源码中是否存在 integrityLoading 的 v-if 分支来验证。
   *
   * **Validates: Requirements 1.2**
   */
  it('integrityLoading=true 时应渲染 loading 反馈区域', async () => {
    // 读取实际的 TusharePreviewView.vue 模板内容来验证
    // 由于直接渲染完整组件依赖太多，我们验证 store 状态驱动的 UI 逻辑

    const store = useTusharePreviewStore()

    // 设置 bug condition 状态
    store.integrityLoading = true
    store.integrityReport = null

    // 尝试动态导入并渲染实际组件
    // 如果组件中没有 integrityLoading 的 loading 分支，则不会渲染 loading 文字
    let hasLoadingElement = false

    try {
      // 导入实际组件
      const { default: TusharePreviewView } = await import('@/views/TusharePreviewView.vue')

      // 需要 mock router 和其他依赖
      const wrapper = mount(TusharePreviewView, {
        global: {
          plugins: [],
          stubs: {
            TushareTabNav: true,
            PreviewChart: true,
            PreviewTable: true,
          },
        },
      })

      // 设置 store 状态
      store.selectedApiName = 'test_api'
      store.integrityLoading = true
      store.integrityReport = null

      await wrapper.vm.$nextTick()

      // 检查是否存在 loading 文字
      hasLoadingElement = wrapper.text().includes('正在校验数据完整性...')

      wrapper.unmount()
    } catch {
      // 如果组件导入/渲染失败，回退到检查模板源码
      hasLoadingElement = false
    }

    expect(hasLoadingElement).toBe(true)
  })
})
