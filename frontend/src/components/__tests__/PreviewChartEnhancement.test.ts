/**
 * PreviewChart 增强功能单元测试
 *
 * 测试列选择器的显示/隐藏逻辑和交互行为：
 * - 折线图显示列选择器
 * - K 线图不显示列选择器
 * - 默认选中前 3 列
 * - 切换列更新图表
 *
 * 需求: 11.1-11.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PreviewChart from '@/components/PreviewChart.vue'
import type { ColumnInfo } from '@/stores/tusharePreview'

// ── Mock ECharts 依赖 ─────────────────────────────────────────────────────────

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="mock-echart"></div>',
    props: ['option', 'autoresize'],
  },
}))

vi.mock('echarts/core', () => ({
  use: vi.fn(),
}))

vi.mock('echarts/charts', () => ({
  CandlestickChart: {},
  LineChart: {},
  BarChart: {},
}))

vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  DataZoomComponent: {},
  LegendComponent: {},
}))

vi.mock('echarts/renderers', () => ({
  CanvasRenderer: {},
}))

// ── 测试数据 ──────────────────────────────────────────────────────────────────

const numericColumns: ColumnInfo[] = [
  { name: 'open', label: '开盘价', type: 'number' },
  { name: 'high', label: '最高价', type: 'number' },
  { name: 'low', label: '最低价', type: 'number' },
  { name: 'close', label: '收盘价', type: 'number' },
  { name: 'vol', label: '成交量', type: 'number' },
]

const lineColumns: ColumnInfo[] = [
  { name: 'trade_date', label: '交易日期', type: 'date' },
  { name: 'buy_sm_amount', label: '小单买入金额', type: 'number' },
  { name: 'sell_sm_amount', label: '小单卖出金额', type: 'number' },
  { name: 'buy_md_amount', label: '中单买入金额', type: 'number' },
  { name: 'sell_md_amount', label: '中单卖出金额', type: 'number' },
  { name: 'buy_lg_amount', label: '大单买入金额', type: 'number' },
]

const candlestickColumns: ColumnInfo[] = [
  { name: 'trade_date', label: '交易日期', type: 'date' },
  { name: 'open', label: '开盘价', type: 'number' },
  { name: 'high', label: '最高价', type: 'number' },
  { name: 'low', label: '最低价', type: 'number' },
  { name: 'close', label: '收盘价', type: 'number' },
  { name: 'vol', label: '成交量', type: 'number' },
]

/** 生成足够的行数据（至少 2 行才会显示图表） */
function generateRows(count: number, timeField: string): Record<string, unknown>[] {
  return Array.from({ length: count }, (_, i) => ({
    [timeField]: `2024-01-${String(i + 1).padStart(2, '0')}`,
    open: 10 + i,
    high: 12 + i,
    low: 9 + i,
    close: 11 + i,
    vol: 10000 + i * 100,
    buy_sm_amount: 100 + i,
    sell_sm_amount: 90 + i,
    buy_md_amount: 200 + i,
    sell_md_amount: 180 + i,
    buy_lg_amount: 500 + i,
  }))
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

function mountChart(props: {
  chartType: 'candlestick' | 'line' | 'bar' | null
  rows: Record<string, unknown>[]
  timeField: string | null
  columns: ColumnInfo[]
  selectedColumns?: string[]
}) {
  return mount(PreviewChart, {
    props,
  })
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

describe('PreviewChart 增强功能', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── test_column_selector_shown_for_line_chart ───────────────────────────

  /**
   * 折线图显示列选择器
   * Validates: Requirements 11.1
   */
  describe('test_column_selector_shown_for_line_chart', () => {
    it('chartType 为 line 时显示列选择器', () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const selector = wrapper.find('.column-selector')
      expect(selector.exists()).toBe(true)

      wrapper.unmount()
    })

    it('列选择器显示「展示列：」标签', () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const label = wrapper.find('.column-selector-label')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('展示列：')

      wrapper.unmount()
    })

    it('列选择器列出所有数值列的中文标签', () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const items = wrapper.findAll('.column-selector-item')
      // lineColumns 中除 trade_date 外有 5 个数值列
      expect(items).toHaveLength(5)

      const labels = items.map((item) => item.find('.column-selector-text').text())
      expect(labels).toContain('小单买入金额')
      expect(labels).toContain('小单卖出金额')
      expect(labels).toContain('中单买入金额')
      expect(labels).toContain('中单卖出金额')
      expect(labels).toContain('大单买入金额')

      wrapper.unmount()
    })

    it('chartType 为 bar 时也显示列选择器', () => {
      const wrapper = mountChart({
        chartType: 'bar',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const selector = wrapper.find('.column-selector')
      expect(selector.exists()).toBe(true)

      wrapper.unmount()
    })
  })

  // ── test_column_selector_hidden_for_candlestick ─────────────────────────

  /**
   * K 线图不显示列选择器
   * Validates: Requirements 11.5
   */
  describe('test_column_selector_hidden_for_candlestick', () => {
    it('chartType 为 candlestick 时不显示列选择器', () => {
      const wrapper = mountChart({
        chartType: 'candlestick',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: candlestickColumns,
      })

      const selector = wrapper.find('.column-selector')
      expect(selector.exists()).toBe(false)

      wrapper.unmount()
    })

    it('chartType 为 null 时不渲染组件', () => {
      const wrapper = mountChart({
        chartType: null,
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const chart = wrapper.find('.preview-chart')
      expect(chart.exists()).toBe(false)

      wrapper.unmount()
    })
  })

  // ── test_default_selected_columns_max_3 ─────────────────────────────────

  /**
   * 默认选中前 3 列
   * Validates: Requirements 11.2
   */
  describe('test_default_selected_columns_max_3', () => {
    it('折线图默认选中前 3 个数值列', () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      const checkboxes = wrapper.findAll('.column-selector-item input[type="checkbox"]')
      const checkedBoxes = checkboxes.filter((cb) => (cb.element as HTMLInputElement).checked)

      // 默认选中前 3 个
      expect(checkedBoxes).toHaveLength(3)

      wrapper.unmount()
    })

    it('数值列不足 3 个时全部选中', () => {
      const twoNumericColumns: ColumnInfo[] = [
        { name: 'trade_date', label: '交易日期', type: 'date' },
        { name: 'value1', label: '指标1', type: 'number' },
        { name: 'value2', label: '指标2', type: 'number' },
      ]

      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: twoNumericColumns,
      })

      const checkboxes = wrapper.findAll('.column-selector-item input[type="checkbox"]')
      const checkedBoxes = checkboxes.filter((cb) => (cb.element as HTMLInputElement).checked)

      expect(checkedBoxes).toHaveLength(2)

      wrapper.unmount()
    })

    it('传入 selectedColumns 时使用指定列', () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
        selectedColumns: ['buy_lg_amount', 'sell_md_amount'],
      })

      const checkboxes = wrapper.findAll('.column-selector-item input[type="checkbox"]')
      const checkedBoxes = checkboxes.filter((cb) => (cb.element as HTMLInputElement).checked)

      expect(checkedBoxes).toHaveLength(2)

      wrapper.unmount()
    })
  })

  // ── test_column_toggle_updates_chart ────────────────────────────────────

  /**
   * 切换列更新图表
   * Validates: Requirements 11.3
   */
  describe('test_column_toggle_updates_chart', () => {
    it('取消勾选一列触发 update:selectedColumns 事件', async () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      // 找到第一个已选中的 checkbox 并取消勾选
      const checkboxes = wrapper.findAll('.column-selector-item input[type="checkbox"]')
      const firstChecked = checkboxes.find((cb) => (cb.element as HTMLInputElement).checked)
      expect(firstChecked).toBeDefined()

      await firstChecked!.setValue(false)
      await flushPromises()

      // 验证触发了 update:selectedColumns 事件
      const emitted = wrapper.emitted('update:selectedColumns')
      expect(emitted).toBeTruthy()
      expect(emitted!.length).toBeGreaterThan(0)

      wrapper.unmount()
    })

    it('勾选新列触发 update:selectedColumns 事件', async () => {
      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: lineColumns,
      })

      // 找到一个未选中的 checkbox 并勾选
      const checkboxes = wrapper.findAll('.column-selector-item input[type="checkbox"]')
      const unchecked = checkboxes.find((cb) => !(cb.element as HTMLInputElement).checked)
      expect(unchecked).toBeDefined()

      await unchecked!.setValue(true)
      await flushPromises()

      // 验证触发了 update:selectedColumns 事件
      const emitted = wrapper.emitted('update:selectedColumns')
      expect(emitted).toBeTruthy()

      // 新选中的列应该在事件数据中
      const lastEmit = emitted![emitted!.length - 1][0] as string[]
      expect(lastEmit.length).toBeGreaterThan(3) // 原来 3 个 + 新增 1 个

      wrapper.unmount()
    })

    it('取消勾选时至少保留一列', async () => {
      // 只有一个数值列的情况
      const singleNumericColumns: ColumnInfo[] = [
        { name: 'trade_date', label: '交易日期', type: 'date' },
        { name: 'value1', label: '指标1', type: 'number' },
      ]

      const wrapper = mountChart({
        chartType: 'line',
        rows: generateRows(5, 'trade_date'),
        timeField: 'trade_date',
        columns: singleNumericColumns,
        selectedColumns: ['value1'],
      })

      // 尝试取消唯一选中的列
      const checkbox = wrapper.find('.column-selector-item input[type="checkbox"]')
      await checkbox.setValue(false)
      await flushPromises()

      // 事件中应仍保留至少一列
      const emitted = wrapper.emitted('update:selectedColumns')
      if (emitted && emitted.length > 0) {
        const lastEmit = emitted[emitted.length - 1][0] as string[]
        expect(lastEmit.length).toBeGreaterThanOrEqual(1)
      }

      wrapper.unmount()
    })
  })
})
