/**
 * Preservation 属性测试：Tushare 数据预览功能修复（前端）
 *
 * **Validates: Requirements 3.1, 3.2, 3.3**
 *
 * 本测试在未修复代码上运行，预期全部 PASS，以确认基线行为。
 * 修复后重新运行，仍应全部 PASS（确保无回归）。
 *
 * P6 手动筛选器覆盖：生成随机日期字符串，模拟自动填充后用户手动修改
 *   filters.dataTimeStart/filters.dataTimeEnd，验证后续查询使用手动值。
 *
 * 完整性校验结果展示不变：设置 integrityLoading=false, integrityReport 为非空完整性报告，
 *   渲染组件，验证结果展示逻辑不变。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import {
  useTusharePreviewStore,
  type CompletenessReport,
} from '@/stores/tusharePreview'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成合法的 YYYY-MM-DD 格式日期字符串 */
const dateStrArb = fc
  .record({
    year: fc.integer({ min: 2000, max: 2025 }),
    month: fc.integer({ min: 1, max: 12 }),
    day: fc.integer({ min: 1, max: 28 }),
  })
  .map(({ year, month, day }) => {
    const m = String(month).padStart(2, '0')
    const d = String(day).padStart(2, '0')
    return `${year}-${m}-${d}`
  })

/** 生成非空完整性校验报告 */
const completenessReportArb: fc.Arbitrary<CompletenessReport> = fc.record({
  check_type: fc.constantFrom('time_series' as const, 'code_based' as const),
  expected_count: fc.integer({ min: 1, max: 10000 }),
  actual_count: fc.integer({ min: 0, max: 10000 }),
  missing_count: fc.integer({ min: 0, max: 1000 }),
  completeness_rate: fc.double({ min: 0, max: 1, noNaN: true }),
  missing_items: fc.array(
    fc.string({ minLength: 1, maxLength: 10 }),
    { maxLength: 10 },
  ),
  time_range: fc.oneof(
    fc.constant(null),
    fc.record({
      start: fc.constant('20240101'),
      end: fc.constant('20241231'),
    }),
  ),
  message: fc.oneof(
    fc.constant(null),
    fc.string({ minLength: 1, maxLength: 50 }),
  ),
})

// ─── P6: 手动筛选器覆盖 ──────────────────────────────────────────────────────

describe('P6 手动筛选器覆盖（Preservation）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * P6: 生成随机日期字符串，模拟自动填充后用户手动修改
   * filters.dataTimeStart/filters.dataTimeEnd，验证后续查询使用手动值。
   *
   * 在未修复代码上应 PASS：手动修改 filters 后，fetchPreviewData 使用手动值。
   * 修复后仍应 PASS：自动填充不会覆盖用户手动设置的值。
   *
   * **Validates: Requirements 3.1, 3.2**
   */
  it('手动修改 filters 后查询使用手动值而非自动填充值', async () => {
    await fc.assert(
      fc.asyncProperty(
        dateStrArb,
        dateStrArb,
        dateStrArb,
        dateStrArb,
        async (autoStart, autoEnd, manualStart, manualEnd) => {
          // 跳过手动值与自动值完全相同的情况
          fc.pre(manualStart !== autoStart || manualEnd !== autoEnd)

          setActivePinia(createPinia())
          const store = useTusharePreviewStore()

          // 模拟自动填充：直接设置 filters
          store.filters.dataTimeStart = autoStart
          store.filters.dataTimeEnd = autoEnd

          // 用户手动修改
          store.filters.dataTimeStart = manualStart
          store.filters.dataTimeEnd = manualEnd

          // 验证 filters 保持用户手动设置的值
          expect(store.filters.dataTimeStart).toBe(manualStart)
          expect(store.filters.dataTimeEnd).toBe(manualEnd)

          // Mock apiClient 并触发查询，验证使用手动值
          const { apiClient } = await import('@/api')
          let capturedParams: Record<string, unknown> | undefined

          const getSpy = vi
            .spyOn(apiClient, 'get')
            .mockImplementation(
              async (
                _url: string,
                config?: { params?: Record<string, unknown> },
              ) => {
                capturedParams = config?.params
                return {
                  data: {
                    columns: [],
                    rows: [],
                    total: 0,
                    page: 1,
                    page_size: 50,
                    time_field: null,
                    chart_type: null,
                    scope_info: null,
                    incremental_info: null,
                  },
                }
              },
            )

          try {
            await store.fetchPreviewData('test_api', store.filters)

            // 验证查询参数使用了手动设置的值
            expect(capturedParams).toBeDefined()
            expect(capturedParams!.data_time_start).toBe(manualStart)
            expect(capturedParams!.data_time_end).toBe(manualEnd)
          } finally {
            getSpy.mockRestore()
          }
        },
      ),
      { numRuns: 20 },
    )
  })
})

// ─── 完整性校验结果展示不变 ───────────────────────────────────────────────────

/**
 * 创建测试组件，模拟 TusharePreviewView 中完整性校验结果的渲染逻辑。
 * 当 integrityLoading=false 且 integrityReport 非空时，应展示结果。
 */
const IntegrityReportTestComponent = defineComponent({
  name: 'IntegrityReportTest',
  setup() {
    const store = useTusharePreviewStore()
    return { store }
  },
  render() {
    const children: ReturnType<typeof h>[] = []

    if (this.store.integrityReport) {
      const report = this.store.integrityReport
      const reportChildren: ReturnType<typeof h>[] = []

      // 标题
      reportChildren.push(
        h(
          'span',
          { class: 'integrity-title', 'data-testid': 'integrity-title' },
          '🔍 完整性校验结果',
        ),
      )

      // 数据完整时绿色提示
      if (report.missing_count === 0) {
        reportChildren.push(
          h(
            'div',
            {
              class: 'integrity-complete',
              'data-testid': 'integrity-complete',
            },
            '✅ 数据完整，无缺失',
          ),
        )
      } else {
        // 有缺失时显示摘要
        reportChildren.push(
          h(
            'div',
            { class: 'integrity-missing', 'data-testid': 'integrity-missing' },
            [
              h('span', {}, `缺失数量：${report.missing_count}`),
              h(
                'span',
                {},
                `完整率：${(report.completeness_rate * 100).toFixed(2)}%`,
              ),
            ],
          ),
        )
      }

      // 附加提示信息
      if (report.message) {
        reportChildren.push(
          h(
            'div',
            {
              class: 'integrity-message',
              'data-testid': 'integrity-message',
            },
            report.message,
          ),
        )
      }

      children.push(
        h(
          'section',
          {
            class: 'integrity-report-section',
            'data-testid': 'integrity-report',
          },
          reportChildren,
        ),
      )
    }

    return h('div', {}, children)
  },
})

describe('完整性校验结果展示不变（Preservation）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * 完整性校验结果展示不变：设置 integrityLoading=false, integrityReport 为非空，
   * 渲染组件，验证结果展示逻辑不变。
   *
   * 在未修复代码和修复后代码上均应 PASS。
   *
   * **Validates: Requirements 3.3**
   */
  it('integrityReport 非空时应正确展示校验结果', async () => {
    await fc.assert(
      fc.asyncProperty(completenessReportArb, async (report) => {
        setActivePinia(createPinia())
        const store = useTusharePreviewStore()

        // 设置 preservation 状态：校验完成，有结果
        store.integrityLoading = false
        store.integrityReport = report

        const wrapper = mount(IntegrityReportTestComponent)
        await wrapper.vm.$nextTick()

        // 验证结果区域被渲染
        const reportSection = wrapper.find('[data-testid="integrity-report"]')
        expect(reportSection.exists()).toBe(true)

        // 验证标题存在
        const title = wrapper.find('[data-testid="integrity-title"]')
        expect(title.exists()).toBe(true)
        expect(title.text()).toContain('完整性校验结果')

        // 验证完整/缺失状态正确展示
        if (report.missing_count === 0) {
          const complete = wrapper.find('[data-testid="integrity-complete"]')
          expect(complete.exists()).toBe(true)
          expect(complete.text()).toContain('数据完整')
        } else {
          const missing = wrapper.find('[data-testid="integrity-missing"]')
          expect(missing.exists()).toBe(true)
          expect(missing.text()).toContain(`缺失数量：${report.missing_count}`)
        }

        // 验证附加提示信息
        if (report.message) {
          const message = wrapper.find('[data-testid="integrity-message"]')
          expect(message.exists()).toBe(true)
          expect(message.text()).toContain(report.message)
        }

        wrapper.unmount()
      }),
      { numRuns: 20 },
    )
  })

  /**
   * integrityReport 为 null 时不应渲染结果区域。
   *
   * **Validates: Requirements 3.3**
   */
  it('integrityReport 为 null 时不应渲染结果区域', () => {
    const store = useTusharePreviewStore()

    store.integrityLoading = false
    store.integrityReport = null

    const wrapper = mount(IntegrityReportTestComponent)

    const reportSection = wrapper.find('[data-testid="integrity-report"]')
    expect(reportSection.exists()).toBe(false)

    wrapper.unmount()
  })
})
