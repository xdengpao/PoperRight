/**
 * SectorBrowserPanel 组件测试
 *
 * 测试板块数据浏览面板的标签页渲染、表格列、分页控件、加载/空状态和涨跌幅样式
 *
 * Validates: Requirements 9.4, 9.5, 9.6, 11.5, 11.6, 12.6, 12.7, 13.6, 13.7, 13.8
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SectorBrowserPanel from '../SectorBrowserPanel.vue'
import { useSectorStore } from '@/stores/sector'

// ─── Mock 依赖 ────────────────────────────────────────────────────────────────

vi.mock('@/api', () => ({
  apiClient: { get: vi.fn() },
}))

// ─── Helper ───────────────────────────────────────────────────────────────────

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(SectorBrowserPanel, {
    global: { plugins: [pinia] },
  })
  const store = useSectorStore()
  return { wrapper, store }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('SectorBrowserPanel 组件', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * 测试 3 个标签页按钮渲染和默认选中
   * Validates: Requirements 9.4, 9.5
   */
  it('渲染 3 个标签页按钮，默认选中"板块数据"', () => {
    const { wrapper } = mountPanel()

    const tabButtons = wrapper.findAll('[role="tab"]')
    expect(tabButtons).toHaveLength(3)

    const labels = tabButtons.map(btn => btn.text())
    expect(labels).toContain('板块数据')
    expect(labels).toContain('板块成分')
    expect(labels).toContain('板块行情')

    // 默认选中"板块数据"
    const infoTab = tabButtons.find(btn => btn.text() === '板块数据')
    expect(infoTab).toBeDefined()
    expect(infoTab!.attributes('aria-selected')).toBe('true')
    expect(infoTab!.classes()).toContain('active')

    wrapper.unmount()
  })

  /**
   * 测试标签页 ARIA 属性
   * Validates: Requirements 9.6
   */
  it('所有标签页按钮具有正确的 ARIA 属性', () => {
    const { wrapper } = mountPanel()

    const tablist = wrapper.find('[role="tablist"]')
    expect(tablist.exists()).toBe(true)
    expect(tablist.attributes('aria-label')).toBe('板块数据浏览')

    const tabButtons = wrapper.findAll('[role="tab"]')
    expect(tabButtons).toHaveLength(3)

    for (const btn of tabButtons) {
      expect(btn.attributes('role')).toBe('tab')
      expect(btn.attributes('aria-selected')).toBeDefined()
    }

    // 非选中标签页 aria-selected 为 false
    const otherTabs = tabButtons.filter(btn => btn.text() !== '板块数据')
    for (const tab of otherTabs) {
      expect(tab.attributes('aria-selected')).toBe('false')
    }

    wrapper.unmount()
  })

  /**
   * 测试板块数据表格 6 列表头
   * Validates: Requirements 11.5
   */
  it('板块数据标签页渲染 6 列表头', async () => {
    const { wrapper, store } = mountPanel()

    // 设置 infoBrowse 数据使表格渲染
    store.infoBrowse.items = [
      {
        sector_code: 'BK0001',
        name: '测试板块',
        sector_type: 'INDUSTRY',
        data_source: 'DC',
        list_date: '2024-01-01',
        constituent_count: 50,
      },
    ]
    await wrapper.vm.$nextTick()

    // 板块数据标签页的表格
    const infoTable = wrapper.find('table[aria-label="板块数据表"]')
    expect(infoTable.exists()).toBe(true)

    const headers = infoTable.findAll('th')
    expect(headers).toHaveLength(6)

    const headerTexts = headers.map(h => h.text())
    expect(headerTexts).toEqual(['板块代码', '板块名称', '板块类型', '数据来源', '上市日期', '成分股数量'])

    // 验证 scope="col"
    for (const th of headers) {
      expect(th.attributes('scope')).toBe('col')
    }

    wrapper.unmount()
  })

  /**
   * 测试板块成分表格 5 列表头
   * Validates: Requirements 12.6
   */
  it('板块成分标签页渲染 5 列表头', async () => {
    const { wrapper, store } = mountPanel()

    // 切换到成分标签页
    store.setBrowserTab('constituent')
    // 设置 constituentBrowse 数据使表格渲染
    store.constituentBrowse.items = [
      {
        trade_date: '2024-01-15',
        sector_code: 'BK0001',
        data_source: 'DC',
        symbol: '600000',
        stock_name: '浦发银行',
      },
    ]
    await wrapper.vm.$nextTick()

    const constituentTable = wrapper.find('table[aria-label="板块成分表"]')
    expect(constituentTable.exists()).toBe(true)

    const headers = constituentTable.findAll('th')
    expect(headers).toHaveLength(5)

    const headerTexts = headers.map(h => h.text())
    expect(headerTexts).toEqual(['交易日期', '板块代码', '数据来源', '股票代码', '股票名称'])

    wrapper.unmount()
  })

  /**
   * 测试板块行情表格 9 列表头
   * Validates: Requirements 13.6
   */
  it('板块行情标签页渲染 9 列表头', async () => {
    const { wrapper, store } = mountPanel()

    // 切换到行情标签页
    store.setBrowserTab('kline')
    // 设置 klineBrowse 数据使表格渲染
    store.klineBrowse.items = [
      {
        time: '2024-01-15',
        sector_code: 'BK0001',
        data_source: 'DC',
        freq: '1d',
        open: 100.0,
        high: 105.0,
        low: 99.0,
        close: 103.0,
        volume: 1000000,
        amount: 103000000.0,
        change_pct: 3.0,
      },
    ]
    await wrapper.vm.$nextTick()

    const klineTable = wrapper.find('table[aria-label="板块行情表"]')
    expect(klineTable.exists()).toBe(true)

    const headers = klineTable.findAll('th')
    expect(headers).toHaveLength(9)

    const headerTexts = headers.map(h => h.text())
    expect(headerTexts).toEqual(['时间', '板块代码', '开盘', '最高', '最低', '收盘', '成交量', '成交额', '涨跌幅'])

    wrapper.unmount()
  })

  /**
   * 测试分页控件渲染
   * Validates: Requirements 11.6
   */
  it('分页控件渲染上一页和下一页按钮', async () => {
    const { wrapper, store } = mountPanel()

    // 设置 infoBrowse 有数据和 total > 0
    store.infoBrowse.items = [
      {
        sector_code: 'BK0001',
        name: '测试板块',
        sector_type: 'INDUSTRY',
        data_source: 'DC',
        list_date: '2024-01-01',
        constituent_count: 50,
      },
    ]
    store.infoBrowse.total = 100
    await wrapper.vm.$nextTick()

    const pagination = wrapper.find('.pagination')
    expect(pagination.exists()).toBe(true)

    const paginationButtons = pagination.findAll('button')
    const buttonTexts = paginationButtons.map(b => b.text())
    expect(buttonTexts).toContain('上一页')
    expect(buttonTexts).toContain('下一页')

    wrapper.unmount()
  })

  /**
   * 测试加载状态
   * Validates: Requirements 12.7
   */
  it('加载状态显示"加载中..."', async () => {
    const { wrapper, store } = mountPanel()

    store.infoBrowse.loading = true
    await wrapper.vm.$nextTick()

    const loadingText = wrapper.find('.loading-text')
    expect(loadingText.exists()).toBe(true)
    expect(loadingText.text()).toContain('加载中...')

    wrapper.unmount()
  })

  /**
   * 测试空数据提示
   * Validates: Requirements 12.7
   */
  it('空数据显示"暂无数据"提示', async () => {
    const { wrapper, store } = mountPanel()

    store.infoBrowse.items = []
    store.infoBrowse.loading = false
    store.infoBrowse.error = ''
    await wrapper.vm.$nextTick()

    // 板块数据标签页的空数据提示
    const emptyElements = wrapper.findAll('.empty')
    const infoEmpty = emptyElements.find(el => el.text().includes('暂无数据'))
    expect(infoEmpty).toBeDefined()
    expect(infoEmpty!.text()).toContain('暂无数据')

    wrapper.unmount()
  })

  /**
   * 测试行情标签页 change_pct 红涨绿跌
   * Validates: Requirements 13.7, 13.8
   */
  it('行情标签页 change_pct 正值红色(up)、负值绿色(down)', async () => {
    const { wrapper, store } = mountPanel()

    // 切换到行情标签页
    store.setBrowserTab('kline')
    // 设置包含正值和负值 change_pct 的数据
    store.klineBrowse.items = [
      {
        time: '2024-01-15',
        sector_code: 'BK0001',
        data_source: 'DC',
        freq: '1d',
        open: 100.0,
        high: 105.0,
        low: 99.0,
        close: 103.0,
        volume: 1000000,
        amount: 103000000.0,
        change_pct: 3.5,
      },
      {
        time: '2024-01-14',
        sector_code: 'BK0002',
        data_source: 'DC',
        freq: '1d',
        open: 100.0,
        high: 101.0,
        low: 95.0,
        close: 97.0,
        volume: 800000,
        amount: 78000000.0,
        change_pct: -2.1,
      },
    ]
    await wrapper.vm.$nextTick()

    const klineTable = wrapper.find('table[aria-label="板块行情表"]')
    expect(klineTable.exists()).toBe(true)

    const rows = klineTable.findAll('tbody tr')
    expect(rows).toHaveLength(2)

    // 第一行：change_pct = 3.5（正值，应有 .up 类）
    const firstRowCells = rows[0].findAll('td')
    const firstChangePctCell = firstRowCells[firstRowCells.length - 1] // 最后一列是涨跌幅
    expect(firstChangePctCell.classes()).toContain('up')
    expect(firstChangePctCell.text()).toContain('+3.50%')

    // 第二行：change_pct = -2.1（负值，应有 .down 类）
    const secondRowCells = rows[1].findAll('td')
    const secondChangePctCell = secondRowCells[secondRowCells.length - 1]
    expect(secondChangePctCell.classes()).toContain('down')
    expect(secondChangePctCell.text()).toContain('-2.10%')

    wrapper.unmount()
  })
})
