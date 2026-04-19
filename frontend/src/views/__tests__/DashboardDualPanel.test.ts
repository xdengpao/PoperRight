/**
 * DashboardView 双面板布局测试
 *
 * 测试板块区域的左右双面板布局结构和 SectorBrowserPanel 组件渲染
 *
 * Validates: Requirements 9.1
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

// ─── Mock sector store ────────────────────────────────────────────────────────

const mockStoreState = reactive({
  rankings: [] as SectorRankingItem[],
  currentType: '' as SectorTypeFilter,
  currentDataSource: '' as string,
  loading: false,
  error: '',
  fetchRanking: vi.fn(),
  setSectorType: vi.fn(),
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

describe('DashboardView 双面板布局', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStoreState.rankings = []
    mockStoreState.currentType = ''
    mockStoreState.loading = false
    mockStoreState.error = ''
    mockStoreState.browserActiveTab = 'info'
  })

  /**
   * 测试 .sector-panel-left 容器存在于 .sector-panels 内
   * Validates: Requirements 9.1
   */
  it('.sector-panel-left 容器存在于 .sector-panels 内', async () => {
    const wrapper = await mountDashboard()

    const sectorPanels = wrapper.find('.sector-panels')
    expect(sectorPanels.exists()).toBe(true)

    const leftPanel = sectorPanels.find('.sector-panel-left')
    expect(leftPanel.exists()).toBe(true)

    wrapper.unmount()
  })

  /**
   * 测试 .sector-panel-right 容器存在于 .sector-panels 内
   * Validates: Requirements 9.1
   */
  it('.sector-panel-right 容器存在于 .sector-panels 内', async () => {
    const wrapper = await mountDashboard()

    const sectorPanels = wrapper.find('.sector-panels')
    expect(sectorPanels.exists()).toBe(true)

    const rightPanel = sectorPanels.find('.sector-panel-right')
    expect(rightPanel.exists()).toBe(true)

    wrapper.unmount()
  })

  /**
   * 测试 SectorBrowserPanel 组件被渲染在右侧面板中
   * Validates: Requirements 9.1
   */
  it('SectorBrowserPanel 组件被渲染在右侧面板中', async () => {
    const wrapper = await mountDashboard()

    const rightPanel = wrapper.find('.sector-panel-right')
    expect(rightPanel.exists()).toBe(true)

    // SectorBrowserPanel 渲染了 .browser-tabs tablist
    const browserTabs = rightPanel.find('[role="tablist"][aria-label="板块数据浏览"]')
    expect(browserTabs.exists()).toBe(true)

    // 验证浏览面板的根元素存在
    const browserPanel = rightPanel.find('.sector-browser-panel')
    expect(browserPanel.exists()).toBe(true)

    wrapper.unmount()
  })
})
