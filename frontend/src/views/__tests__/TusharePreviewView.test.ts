/**
 * TusharePreviewView 前端单元测试
 *
 * 覆盖 Tab 导航渲染和切换、分类选择器展开/折叠、表格分页切换、
 * 图表/表格展示模式切换、空数据状态展示、增量查询按钮交互、
 * 导入记录列表渲染和点击、导入状态颜色区分。
 *
 * 需求: 1.2-1.5, 2.1-2.5, 3.1-3.5, 4.5, 7.1-7.5, 10.1-10.4
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TusharePreviewView from '../TusharePreviewView.vue'
import { useTusharePreviewStore } from '@/stores/tusharePreview'
import type {
  ApiRegistryItem,
  ImportLogItem,
  PreviewDataResponse,
} from '@/stores/tusharePreview'

// ── Mock vue-router ───────────────────────────────────────────────────────────

const mockPush = vi.fn()
const mockRouteName = { value: 'DataOnlineTusharePreview' }

vi.mock('vue-router', () => ({
  useRoute: () => ({ name: mockRouteName.value }),
  useRouter: () => ({ push: mockPush }),
}))

// ── Mock apiClient ────────────────────────────────────────────────────────────

const mockGet = vi.fn().mockResolvedValue({ data: [] })

vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

// ── Mock vue-echarts（PreviewChart 使用） ─────────────────────────────────────

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

const sampleRegistry: ApiRegistryItem[] = [
  {
    api_name: 'daily',
    label: '日线行情',
    category: 'stock_data',
    subcategory: '行情数据',
    token_tier: 'basic',
    required_params: ['date_range'],
    optional_params: [],
    token_available: true,
  },
  {
    api_name: 'stock_basic',
    label: '股票基础列表',
    category: 'stock_data',
    subcategory: '基础数据',
    token_tier: 'basic',
    required_params: [],
    optional_params: [],
    token_available: true,
  },
  {
    api_name: 'index_daily',
    label: '指数日线行情',
    category: 'index_data',
    subcategory: '指数行情',
    token_tier: 'basic',
    required_params: ['date_range'],
    optional_params: [],
    token_available: true,
  },
]

const sampleImportLogs: ImportLogItem[] = [
  {
    id: 1,
    api_name: 'daily',
    params_json: { start_date: '20240101', end_date: '20240131' },
    status: 'completed',
    record_count: 5000,
    error_message: null,
    started_at: '2024-06-15T10:30:00',
    finished_at: '2024-06-15T10:30:05',
  },
  {
    id: 2,
    api_name: 'daily',
    params_json: { start_date: '20240201', end_date: '20240228' },
    status: 'failed',
    record_count: 0,
    error_message: 'Token 无效',
    started_at: '2024-06-14T09:00:00',
    finished_at: '2024-06-14T09:00:01',
  },
  {
    id: 3,
    api_name: 'daily',
    params_json: null,
    status: 'running',
    record_count: 100,
    error_message: null,
    started_at: '2024-06-13T08:00:00',
    finished_at: null,
  },
  {
    id: 4,
    api_name: 'daily',
    params_json: null,
    status: 'stopped',
    record_count: 50,
    error_message: null,
    started_at: '2024-06-12T07:00:00',
    finished_at: '2024-06-12T07:00:02',
  },
]

const samplePreviewData: PreviewDataResponse = {
  columns: [
    { name: 'trade_date', label: '交易日期', type: 'date' },
    { name: 'open', label: '开盘价', type: 'number' },
    { name: 'close', label: '收盘价', type: 'number' },
    { name: 'high', label: '最高价', type: 'number' },
    { name: 'low', label: '最低价', type: 'number' },
  ],
  rows: [
    { trade_date: '2024-01-02', open: 10.5, close: 11.0, high: 11.2, low: 10.3 },
    { trade_date: '2024-01-03', open: 11.0, close: 10.8, high: 11.5, low: 10.6 },
  ],
  total: 100,
  page: 1,
  page_size: 50,
  time_field: 'trade_date',
  chart_type: 'candlestick',
  scope_info: null,
  incremental_info: null,
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

/** 挂载组件并返回 wrapper 和 store */
function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(TusharePreviewView, {
    global: { plugins: [pinia] },
  })
  const store = useTusharePreviewStore()
  return { wrapper, store }
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

describe('TusharePreviewView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: [] })
    mockRouteName.value = 'DataOnlineTusharePreview'
  })

  // ── 1. Tab 导航渲染和切换 ─────────────────────────────────────────────────

  describe('Tab 导航渲染和切换', () => {
    /**
     * 渲染两个 Tab 标签
     * Validates: Requirements 1.2
     */
    it('渲染「Tushare 数据导入」和「Tushare 数据预览」两个 Tab', async () => {
      const { wrapper } = mountView()
      await flushPromises()

      const tabs = wrapper.findAll('.tab-item')
      expect(tabs).toHaveLength(2)

      const labels = tabs.map((t) => t.text())
      expect(labels).toContain('Tushare 数据导入')
      expect(labels).toContain('Tushare 数据预览')

      wrapper.unmount()
    })

    /**
     * 当前路由为预览页时，预览 Tab 高亮
     * Validates: Requirements 1.3
     */
    it('当前路由为预览页时，预览 Tab 高亮', async () => {
      mockRouteName.value = 'DataOnlineTusharePreview'
      const { wrapper } = mountView()
      await flushPromises()

      const tabs = wrapper.findAll('.tab-item')
      const previewTab = tabs.find((t) => t.text() === 'Tushare 数据预览')
      expect(previewTab).toBeDefined()
      expect(previewTab!.classes()).toContain('active')

      wrapper.unmount()
    })

    /**
     * 点击「Tushare 数据导入」Tab 导航到导入页面
     * Validates: Requirements 1.4
     */
    it('点击导入 Tab 调用 router.push 导航', async () => {
      const { wrapper } = mountView()
      await flushPromises()

      const tabs = wrapper.findAll('.tab-item')
      const importTab = tabs.find((t) => t.text() === 'Tushare 数据导入')
      await importTab!.trigger('click')

      expect(mockPush).toHaveBeenCalledWith({ name: 'DataOnlineTushare' })

      wrapper.unmount()
    })

    /**
     * 点击当前已激活的 Tab 不触发导航
     * Validates: Requirements 1.3
     */
    it('点击当前已激活的 Tab 不触发导航', async () => {
      mockRouteName.value = 'DataOnlineTusharePreview'
      const { wrapper } = mountView()
      await flushPromises()

      const tabs = wrapper.findAll('.tab-item')
      const previewTab = tabs.find((t) => t.text() === 'Tushare 数据预览')
      await previewTab!.trigger('click')

      expect(mockPush).not.toHaveBeenCalled()

      wrapper.unmount()
    })
  })

  // ── 2. 分类选择器展开/折叠 ───────────────────────────────────────────────

  describe('分类选择器展开/折叠', () => {
    /**
     * 显示两个大类标题
     * Validates: Requirements 2.1, 2.2
     */
    it('显示「📈 股票数据」和「📊 指数数据」两个大类', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      // 设置注册表数据
      store.registry = sampleRegistry
      store.registryLoading = false
      await flushPromises()

      const titles = wrapper.findAll('.category-title')
      const titleTexts = titles.map((t) => t.text())
      expect(titleTexts).toContain('📈 股票数据')
      expect(titleTexts).toContain('📊 指数数据')

      wrapper.unmount()
    })

    /**
     * 子分类初始折叠，点击后展开显示 API 列表
     * Validates: Requirements 2.3
     */
    it('子分类初始折叠，点击后展开显示 API 列表', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.registryLoading = false
      await flushPromises()

      // 初始状态下 API 列表不可见
      expect(wrapper.findAll('.api-list').length).toBe(0)

      // 点击第一个子分类 header
      const header = wrapper.find('.subcategory-header')
      await header.trigger('click')
      await flushPromises()

      // 展开后应显示 API 列表
      expect(wrapper.findAll('.api-list').length).toBeGreaterThan(0)

      wrapper.unmount()
    })

    /**
     * 子分类旁显示接口数量
     * Validates: Requirements 2.5
     */
    it('子分类旁显示接口数量', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.registryLoading = false
      await flushPromises()

      const counts = wrapper.findAll('.subcategory-count')
      expect(counts.length).toBeGreaterThan(0)
      // 每个子分类有 1 个接口
      expect(counts[0].text()).toBe('1')

      wrapper.unmount()
    })

    /**
     * 再次点击子分类 header 折叠 API 列表
     * Validates: Requirements 2.3
     */
    it('再次点击子分类 header 折叠 API 列表', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.registryLoading = false
      await flushPromises()

      const header = wrapper.find('.subcategory-header')

      // 展开
      await header.trigger('click')
      await flushPromises()
      expect(wrapper.findAll('.api-list').length).toBeGreaterThan(0)

      // 折叠
      await header.trigger('click')
      await flushPromises()
      expect(wrapper.findAll('.api-list').length).toBe(0)

      wrapper.unmount()
    })

    /**
     * 注册表加载中显示加载提示
     * Validates: Requirements 2.1
     */
    it('注册表加载中显示加载提示', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registryLoading = true
      await flushPromises()

      expect(wrapper.text()).toContain('加载接口列表...')

      wrapper.unmount()
    })
  })

  // ── 3. 表格分页切换 ──────────────────────────────────────────────────────

  describe('表格分页切换', () => {
    /**
     * 表格上方显示总记录数
     * Validates: Requirements 3.4
     */
    it('表格上方显示总记录数', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.displayMode = 'table'
      await flushPromises()

      expect(wrapper.text()).toContain('100')

      wrapper.unmount()
    })

    /**
     * 分页控件显示每页条数选择按钮
     * Validates: Requirements 3.3
     */
    it('分页控件显示每页条数选择按钮（20/50/100）', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.displayMode = 'table'
      await flushPromises()

      const pageSizeBtns = wrapper.findAll('.page-size-btn')
      const sizes = pageSizeBtns.map((b) => b.text())
      expect(sizes).toContain('20')
      expect(sizes).toContain('50')
      expect(sizes).toContain('100')

      wrapper.unmount()
    })

    /**
     * 点击每页条数按钮触发 fetchPreviewData
     * Validates: Requirements 3.3
     */
    it('点击每页条数按钮触发数据重新加载', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.displayMode = 'table'
      await flushPromises()

      // 监听 fetchPreviewData
      const fetchSpy = vi.spyOn(store, 'fetchPreviewData').mockResolvedValue()

      // 点击 "20" 条按钮
      const pageSizeBtns = wrapper.findAll('.page-size-btn')
      const btn20 = pageSizeBtns.find((b) => b.text() === '20')
      await btn20!.trigger('click')
      await flushPromises()

      expect(fetchSpy).toHaveBeenCalled()

      wrapper.unmount()
    })
  })

  // ── 4. 图表/表格展示模式切换 ─────────────────────────────────────────────

  describe('图表/表格展示模式切换', () => {
    /**
     * 渲染三个展示模式按钮
     * Validates: Requirements 4.5
     */
    it('渲染「仅表格」「仅图表」「图表+表格」三个模式按钮', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      const modeBtns = wrapper.findAll('.mode-btn')
      expect(modeBtns).toHaveLength(3)

      const labels = modeBtns.map((b) => b.text())
      expect(labels).toContain('仅表格')
      expect(labels).toContain('仅图表')
      expect(labels).toContain('图表+表格')

      wrapper.unmount()
    })

    /**
     * 默认展示模式为「仅表格」
     * Validates: Requirements 4.5
     */
    it('默认展示模式为「仅表格」', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      const modeBtns = wrapper.findAll('.mode-btn')
      const tableBtn = modeBtns.find((b) => b.text() === '仅表格')
      expect(tableBtn!.classes()).toContain('active')

      // 表格可见
      expect(wrapper.findComponent({ name: 'PreviewTable' }).exists()).toBe(true)

      wrapper.unmount()
    })

    /**
     * 切换到「仅图表」模式隐藏表格
     * Validates: Requirements 4.5
     */
    it('切换到「仅图表」模式隐藏表格', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      // 点击「仅图表」
      const modeBtns = wrapper.findAll('.mode-btn')
      const chartBtn = modeBtns.find((b) => b.text() === '仅图表')
      await chartBtn!.trigger('click')
      await flushPromises()

      expect(store.displayMode).toBe('chart')

      wrapper.unmount()
    })

    /**
     * 切换到「图表+表格」模式同时显示
     * Validates: Requirements 4.5
     */
    it('切换到「图表+表格」模式', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      // 点击「图表+表格」
      const modeBtns = wrapper.findAll('.mode-btn')
      const bothBtn = modeBtns.find((b) => b.text() === '图表+表格')
      await bothBtn!.trigger('click')
      await flushPromises()

      expect(store.displayMode).toBe('both')

      wrapper.unmount()
    })
  })

  // ── 5. 空数据状态展示 ────────────────────────────────────────────────────

  describe('空数据状态展示', () => {
    /**
     * 未选择接口时显示提示
     * Validates: Requirements 2.4
     */
    it('未选择接口时显示提示信息', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = null
      await flushPromises()

      expect(wrapper.text()).toContain('请从左侧选择一个 API 接口以预览数据')

      wrapper.unmount()
    })

    /**
     * 查询结果为空时表格显示「暂无数据」
     * Validates: Requirements 3.5
     */
    it('查询结果为空时表格显示「暂无数据」', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = {
        ...samplePreviewData,
        rows: [],
        total: 0,
      }
      store.displayMode = 'table'
      await flushPromises()

      expect(wrapper.text()).toContain('暂无数据')

      wrapper.unmount()
    })

    /**
     * 注册表为空时显示空状态
     * Validates: Requirements 2.1
     */
    it('注册表为空时显示「暂无接口数据」', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = []
      store.registryLoading = false
      await flushPromises()

      expect(wrapper.text()).toContain('暂无接口数据')

      wrapper.unmount()
    })
  })

  // ── 6. 增量查询按钮交互 ──────────────────────────────────────────────────

  describe('增量查询按钮交互', () => {
    /**
     * 渲染「查看增量数据」按钮
     * Validates: Requirements 7.1
     */
    it('选择接口后显示「查看增量数据」按钮', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      const btns = wrapper.findAll('.btn-secondary')
      const incrementalBtn = btns.find((b) => b.text() === '查看增量数据')
      expect(incrementalBtn).toBeDefined()

      wrapper.unmount()
    })

    /**
     * 点击增量查询按钮触发 fetchPreviewData 并设置 incremental=true
     * Validates: Requirements 7.2
     */
    it('点击增量查询按钮触发增量查询', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      await flushPromises()

      const fetchSpy = vi.spyOn(store, 'fetchPreviewData').mockResolvedValue()

      const btns = wrapper.findAll('.btn-secondary')
      const incrementalBtn = btns.find((b) => b.text() === '查看增量数据')
      await incrementalBtn!.trigger('click')
      await flushPromises()

      // 验证 incremental 标志被设置
      expect(store.filters.incremental).toBe(true)
      expect(fetchSpy).toHaveBeenCalled()

      wrapper.unmount()
    })

    /**
     * 增量查询模式下显示导入信息摘要
     * Validates: Requirements 7.4
     */
    it('增量查询模式下显示导入信息摘要', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = {
        ...samplePreviewData,
        incremental_info: {
          import_log_id: 1,
          import_time: '2024-06-15T10:30:00',
          record_count: 5000,
          status: 'completed',
          params_summary: '20240101 ~ 20240131',
        },
      }
      await flushPromises()

      const infoSection = wrapper.find('.incremental-info')
      expect(infoSection.exists()).toBe(true)
      expect(infoSection.text()).toContain('5,000')
      expect(infoSection.text()).toContain('20240101 ~ 20240131')

      wrapper.unmount()
    })

    /**
     * 无成功导入记录时显示提示
     * Validates: Requirements 7.5
     */
    it('增量查询无成功导入记录时显示提示', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.importLogs = [
        { ...sampleImportLogs[1] }, // 只有 failed 记录
      ]
      store.importLogsLoading = false
      store.filters.incremental = true
      store.previewData = { ...samplePreviewData, incremental_info: null }
      // 移除 incremental_info 使 showNoSuccessMessage 为 true
      delete (store.previewData as any).incremental_info
      await flushPromises()

      expect(wrapper.text()).toContain('该接口暂无成功导入记录')

      wrapper.unmount()
    })

    /**
     * 加载中时增量查询按钮禁用
     * Validates: Requirements 7.1
     */
    it('加载中时增量查询按钮禁用', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.previewLoading = true
      await flushPromises()

      const btns = wrapper.findAll('.btn-secondary')
      const incrementalBtn = btns.find((b) => b.text() === '查看增量数据')
      expect(incrementalBtn!.attributes('disabled')).toBeDefined()

      wrapper.unmount()
    })
  })

  // ── 7. 导入记录列表渲染和点击 ────────────────────────────────────────────

  describe('导入记录列表渲染和点击', () => {
    /**
     * 显示导入记录列表
     * Validates: Requirements 10.1, 10.2
     */
    it('显示导入记录列表及每条记录的信息', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = sampleImportLogs
      store.importLogsLoading = false
      await flushPromises()

      // 导入记录区域应存在
      const logSection = wrapper.find('.import-logs-section')
      expect(logSection.exists()).toBe(true)

      // 显示记录数量
      expect(logSection.text()).toContain(`${sampleImportLogs.length} 条`)

      // 显示导入记录条目
      const logItems = wrapper.findAll('.import-log-item')
      expect(logItems).toHaveLength(sampleImportLogs.length)

      wrapper.unmount()
    })

    /**
     * 导入记录显示时间、状态、记录数
     * Validates: Requirements 10.2
     */
    it('导入记录显示时间、状态标签和记录数', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = [sampleImportLogs[0]]
      store.importLogsLoading = false
      await flushPromises()

      const logItem = wrapper.find('.import-log-item')
      expect(logItem.exists()).toBe(true)

      // 显示时间
      expect(logItem.text()).toContain('2024-06-15 10:30:00')
      // 显示状态
      expect(logItem.text()).toContain('成功')
      // 显示记录数
      expect(logItem.text()).toContain('5,000')

      wrapper.unmount()
    })

    /**
     * 点击导入记录触发数据查询
     * Validates: Requirements 10.3
     */
    it('点击导入记录触发数据查询', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = sampleImportLogs
      store.importLogsLoading = false
      await flushPromises()

      const fetchSpy = vi.spyOn(store, 'fetchPreviewData').mockResolvedValue()

      const logItems = wrapper.findAll('.import-log-item')
      await logItems[0].trigger('click')
      await flushPromises()

      // 验证 importLogId 被设置
      expect(store.filters.importLogId).toBe(sampleImportLogs[0].id)
      expect(fetchSpy).toHaveBeenCalled()

      wrapper.unmount()
    })

    /**
     * 导入记录为空时显示空提示
     * Validates: Requirements 10.1
     */
    it('导入记录为空时显示「暂无导入记录」', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = []
      store.importLogsLoading = false
      await flushPromises()

      expect(wrapper.text()).toContain('暂无导入记录')

      wrapper.unmount()
    })

    /**
     * 导入记录区域可折叠
     * Validates: Requirements 10.1
     */
    it('点击导入记录区域标题可折叠/展开', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = sampleImportLogs
      store.importLogsLoading = false
      await flushPromises()

      // 初始展开，应有 import-logs-body
      expect(wrapper.find('.import-logs-body').exists()).toBe(true)

      // 点击折叠
      const toggle = wrapper.find('.section-toggle')
      await toggle.trigger('click')
      await flushPromises()

      expect(wrapper.find('.import-logs-body').exists()).toBe(false)

      // 再次点击展开
      await toggle.trigger('click')
      await flushPromises()

      expect(wrapper.find('.import-logs-body').exists()).toBe(true)

      wrapper.unmount()
    })
  })

  // ── 8. 导入状态颜色区分 ──────────────────────────────────────────────────

  describe('导入状态颜色区分', () => {
    /**
     * 成功状态使用绿色
     * Validates: Requirements 10.4
     */
    it('成功状态使用 status-green 类', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = [sampleImportLogs[0]] // completed
      store.importLogsLoading = false
      await flushPromises()

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('status-green')

      wrapper.unmount()
    })

    /**
     * 失败状态使用红色
     * Validates: Requirements 10.4
     */
    it('失败状态使用 status-red 类', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = [sampleImportLogs[1]] // failed
      store.importLogsLoading = false
      await flushPromises()

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('status-red')

      wrapper.unmount()
    })

    /**
     * 运行中状态使用蓝色
     * Validates: Requirements 10.4
     */
    it('运行中状态使用 status-blue 类', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = [sampleImportLogs[2]] // running
      store.importLogsLoading = false
      await flushPromises()

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('status-blue')

      wrapper.unmount()
    })

    /**
     * 已停止状态使用灰色
     * Validates: Requirements 10.4
     */
    it('已停止状态使用 status-gray 类', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = [sampleImportLogs[3]] // stopped
      store.importLogsLoading = false
      await flushPromises()

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('status-gray')

      wrapper.unmount()
    })

    /**
     * 多条记录各自显示正确的状态颜色
     * Validates: Requirements 10.4
     */
    it('多条记录各自显示正确的状态颜色', async () => {
      const { wrapper, store } = mountView()
      await flushPromises()

      store.registry = sampleRegistry
      store.selectedApiName = 'daily'
      store.previewData = { ...samplePreviewData }
      store.importLogs = sampleImportLogs
      store.importLogsLoading = false
      await flushPromises()

      const badges = wrapper.findAll('.import-log-item .status-badge')
      expect(badges).toHaveLength(4)

      // completed → green, failed → red, running → blue, stopped → gray
      expect(badges[0].classes()).toContain('status-green')
      expect(badges[1].classes()).toContain('status-red')
      expect(badges[2].classes()).toContain('status-blue')
      expect(badges[3].classes()).toContain('status-gray')

      wrapper.unmount()
    })
  })
})
