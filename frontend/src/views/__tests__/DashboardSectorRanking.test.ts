/**
 * DashboardView 板块排行组件测试
 *
 * 测试板块涨幅排行模块的渲染、交互和无障碍属性
 *
 * Validates: Requirements 3.1, 3.2, 3.4, 3.6, 4.1, 4.7, 4.8, 5.5, 6.2
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import type { SectorRankingItem, SectorTypeFilter } from '@/stores/sector'

// ─── Mock 依赖 ────────────────────────────────────────────────────────────────

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })),
}))

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
      if (url.includes('/sector/ranking')) {
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

vi.mock('../fundamentalUtils', () => ({
  getFundamentalColorClass: vi.fn(() => ''),
  formatFundamentalValue: vi.fn(() => '--'),
}))

vi.mock('../moneyFlowUtils', () => ({
  getMoneyFlowBarColor: vi.fn(() => '#f85149'),
}))

vi.stubGlobal(
  'WebSocket',
  vi.fn().mockImplementation(() => ({
    onmessage: null,
    onclose: null,
    close: vi.fn(),
  })),
)

// ─── Mock sector store with controllable reactive state ───────────────────────

const mockFetchRanking = vi.fn()
const mockSetSectorType = vi.fn()

// Pinia stores return reactive objects (refs are auto-unwrapped), so we use reactive()
const mockStoreState = reactive({
  rankings: [] as SectorRankingItem[],
  currentType: '' as SectorTypeFilter,
  currentDataSource: '' as string,
  loading: false,
  error: '',
  fetchRanking: mockFetchRanking,
  setSectorType: mockSetSectorType,
  setDataSource: vi.fn(),
  expandedSectorCode: null as string | null,
  expandedKlineData: [] as any[],
  expandedKlineLoading: false,
  expandedKlineError: '',
  toggleSectorKline: vi.fn(),
  // Browse panel state needed by SectorBrowserPanel
  browserActiveTab: 'info' as string,
  setBrowserTab: vi.fn(),
  infoBrowse: {
    items: [], total: 0, page: 1, pageSize: 50,
    loading: false, error: '',
    filters: { data_source: 'DC', sector_type: '', keyword: '' },
  },
  constituentBrowse: {
    items: [], total: 0, page: 1, pageSize: 50,
    loading: false, error: '',
    filters: { data_source: 'DC', sector_code: '', trade_date: '', keyword: '' },
  },
  klineBrowse: {
    items: [], total: 0, page: 1, pageSize: 50,
    loading: false, error: '',
    filters: { data_source: 'DC', sector_code: '', freq: '1d', start: '', end: '' },
  },
  updateInfoFilters: vi.fn(),
  updateConstituentFilters: vi.fn(),
  updateKlineFilters: vi.fn(),
  fetchSectorInfoBrowse: vi.fn(),
  fetchConstituentBrowse: vi.fn(),
  fetchKlineBrowse: vi.fn(),
})

vi.mock('@/stores/sector', () => ({
  useSectorStore: vi.fn(() => mockStoreState),
}))

import DashboardView from '../DashboardView.vue'
import * as fs from 'fs'
import * as path from 'path'

// ─── Helper ───────────────────────────────────────────────────────────────────

async function mountDashboard() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(DashboardView, {
    global: { plugins: [pinia] },
  })

  await flushPromises()
  await wrapper.vm.$nextTick()

  return wrapper
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('DashboardView 板块排行模块', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStoreState.rankings = []
    mockStoreState.currentType = ''
    mockStoreState.loading = false
    mockStoreState.error = ''
  })

  /**
   * 测试 5 个标签页按钮渲染
   * Validates: Requirements 3.1
   */
  it('渲染 5 个板块类型标签页按钮', async () => {
    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const sectorTabs = sectorSection.find('.sector-tabs')
    const tabButtons = sectorTabs.findAll('[role="tab"]')

    expect(tabButtons).toHaveLength(5)

    const labels = tabButtons.map(btn => btn.text())
    expect(labels).toContain('全部')
    expect(labels).toContain('行业板块')
    expect(labels).toContain('概念板块')
    expect(labels).toContain('地区板块')
    expect(labels).toContain('风格板块')

    wrapper.unmount()
  })

  /**
   * 测试"全部"标签页默认选中
   * Validates: Requirements 3.2
   */
  it('"全部"标签页默认选中', async () => {
    mockStoreState.currentType = ''

    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const tabButtons = sectorSection.findAll('.sector-tabs [role="tab"]')

    const allTab = tabButtons.find(btn => btn.text() === '全部')
    expect(allTab).toBeDefined()
    expect(allTab!.classes()).toContain('active')
    expect(allTab!.attributes('aria-selected')).toBe('true')

    // Other tabs should not be active
    const otherTabs = tabButtons.filter(btn => btn.text() !== '全部')
    for (const tab of otherTabs) {
      expect(tab.attributes('aria-selected')).toBe('false')
    }

    wrapper.unmount()
  })

  /**
   * 测试点击标签页触发 setSectorType
   * Validates: Requirements 3.4, 5.5
   */
  it('点击标签页触发 setSectorType', async () => {
    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const tabButtons = sectorSection.findAll('.sector-tabs [role="tab"]')

    // Click "行业板块" tab
    const industryTab = tabButtons.find(btn => btn.text() === '行业板块')
    expect(industryTab).toBeDefined()
    await industryTab!.trigger('click')

    expect(mockSetSectorType).toHaveBeenCalledWith('INDUSTRY')

    // Click "概念板块" tab
    const conceptTab = tabButtons.find(btn => btn.text() === '概念板块')
    await conceptTab!.trigger('click')

    expect(mockSetSectorType).toHaveBeenCalledWith('CONCEPT')

    wrapper.unmount()
  })

  /**
   * 测试 6 列表头渲染
   * Validates: Requirements 4.1, 4.7
   */
  it('渲染 6 列表头', async () => {
    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const table = sectorSection.find('table.data-table')
    const headers = table.findAll('th[scope="col"]')

    expect(headers).toHaveLength(6)

    const headerTexts = headers.map(h => h.text())
    expect(headerTexts).toEqual(['排名', '板块名称', '涨跌幅', '收盘价', '成交额(亿)', '换手率'])

    wrapper.unmount()
  })

  /**
   * 测试加载状态提示文字
   * Validates: Requirements 3.4
   */
  it('加载状态显示提示文字', async () => {
    mockStoreState.loading = true

    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const loadingText = sectorSection.find('.loading-text')

    expect(loadingText.exists()).toBe(true)
    expect(loadingText.text()).toContain('加载板块数据中')

    wrapper.unmount()
  })

  /**
   * 测试错误状态和重试按钮
   * Validates: Requirements 5.5
   */
  it('错误状态显示错误信息和重试按钮', async () => {
    mockStoreState.loading = false
    mockStoreState.error = '获取板块排行数据失败'

    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const errorBanner = sectorSection.find('.error-banner-inline')

    expect(errorBanner.exists()).toBe(true)
    expect(errorBanner.text()).toContain('获取板块排行数据失败')

    const retryBtn = errorBanner.find('.retry-btn')
    expect(retryBtn.exists()).toBe(true)

    await retryBtn.trigger('click')
    expect(mockFetchRanking).toHaveBeenCalled()

    wrapper.unmount()
  })

  /**
   * 测试空数据"暂无数据"提示
   * Validates: Requirements 4.8
   */
  it('空数据显示"暂无数据"提示', async () => {
    mockStoreState.rankings = []
    mockStoreState.loading = false
    mockStoreState.error = ''

    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')
    const emptyCell = sectorSection.find('.empty')

    expect(emptyCell.exists()).toBe(true)
    expect(emptyCell.text()).toContain('暂无数据')

    wrapper.unmount()
  })

  /**
   * 测试 ARIA 属性
   * Validates: Requirements 3.6, 4.7, 6.2
   */
  it('ARIA 属性正确设置', async () => {
    const wrapper = await mountDashboard()

    const sectorSection = wrapper.find('.sector-section')

    // Tablist has aria-label
    const tablist = sectorSection.find('[role="tablist"]')
    expect(tablist.exists()).toBe(true)
    expect(tablist.attributes('aria-label')).toBe('板块类型切换')

    // All tab buttons have role="tab" and aria-selected
    const tabButtons = sectorSection.findAll('.sector-tabs [role="tab"]')
    expect(tabButtons.length).toBe(5)
    for (const btn of tabButtons) {
      expect(btn.attributes('role')).toBe('tab')
      expect(btn.attributes('aria-selected')).toBeDefined()
    }

    // Table has aria-label
    const table = sectorSection.find('table.data-table')
    expect(table.attributes('aria-label')).toBe('板块涨幅排行表')

    // Column headers have scope="col"
    const headers = table.findAll('th')
    for (const th of headers) {
      expect(th.attributes('scope')).toBe('col')
    }

    wrapper.unmount()
  })

  /**
   * 验证 loadSectors 和 SectorData 不再存在于 DashboardView 源码中
   * Validates: Requirements 6.2
   */
  it('DashboardView 源码中不再包含 loadSectors 和 SectorData', () => {
    const filePath = path.resolve(__dirname, '../DashboardView.vue')
    const source = fs.readFileSync(filePath, 'utf-8')

    expect(source).not.toContain('loadSectors')
    expect(source).not.toContain('SectorData')
  })
})
