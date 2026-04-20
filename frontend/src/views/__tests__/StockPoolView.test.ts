/**
 * StockPoolView 选股池管理页面单元测试
 *
 * 测试内容：
 * - 空状态渲染
 * - 选股池列表渲染
 * - 创建对话框交互
 * - 删除确认对话框
 * - 富化表格渲染（需求 7）
 * - 无选股结果数据占位符
 * - 详情面板展开/不展开
 * - 排序功能
 *
 * Requirements: 2.3, 2.5, 3.1, 3.8, 7.1, 7.2, 7.6, 7.8
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import StockPoolView from '../StockPoolView.vue'

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="mock-vchart"></div>', props: ['option', 'autoresize'] },
}))
vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/charts', () => ({ CandlestickChart: {}, BarChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  DataZoomComponent: {},
  MarkLineComponent: {},
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

vi.mock('@/components/MinuteKlineChart.vue', () => ({
  default: { name: 'MinuteKlineChart', template: '<div class="mock-minute-kline"></div>', props: ['symbol', 'selectedDate', 'latestTradeDate'] },
}))

// ─── 测试数据 ─────────────────────────────────────────────────────────────────

const MOCK_POOLS = [
  {
    id: 'pool-1',
    name: '趋势追踪池',
    stock_count: 5,
    created_at: '2024-06-01T10:00:00',
    updated_at: '2024-06-01T10:00:00',
  },
  {
    id: 'pool-2',
    name: '价值投资池',
    stock_count: 12,
    created_at: '2024-06-02T14:30:00',
    updated_at: '2024-06-02T14:30:00',
  },
]

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function mountView() {
  return mount(StockPoolView, {
    global: {
      plugins: [createPinia()],
    },
  })
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('StockPoolView - 空状态渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('无选股池时显示空状态提示', async () => {
    mockGet.mockResolvedValue({ data: [] })

    const wrapper = mountView()
    await flushPromises()

    const emptyState = wrapper.find('.empty-state')
    expect(emptyState.exists()).toBe(true)
    expect(emptyState.text()).toContain('暂无选股池，请点击"新建选股池"创建')

    wrapper.unmount()
  })

  it('空状态下不渲染选股池列表', async () => {
    mockGet.mockResolvedValue({ data: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.pool-list').exists()).toBe(false)
    expect(wrapper.findAll('.pool-card').length).toBe(0)

    wrapper.unmount()
  })
})

describe('StockPoolView - 列表渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('渲染选股池名称和股票数量', async () => {
    mockGet.mockResolvedValue({ data: MOCK_POOLS })

    const wrapper = mountView()
    await flushPromises()

    // 不应显示空状态
    expect(wrapper.find('.empty-state').exists()).toBe(false)

    // 应渲染两个选股池卡片
    const cards = wrapper.findAll('.pool-card')
    expect(cards.length).toBe(2)

    // 验证第一个选股池
    const firstCard = cards[0]
    expect(firstCard.find('.pool-name').text()).toBe('趋势追踪池')
    expect(firstCard.find('.pool-meta').text()).toContain('5 只股票')

    // 验证第二个选股池
    const secondCard = cards[1]
    expect(secondCard.find('.pool-name').text()).toBe('价值投资池')
    expect(secondCard.find('.pool-meta').text()).toContain('12 只股票')

    wrapper.unmount()
  })

  it('每个选股池显示删除和重命名按钮', async () => {
    mockGet.mockResolvedValue({ data: MOCK_POOLS })

    const wrapper = mountView()
    await flushPromises()

    const cards = wrapper.findAll('.pool-card')
    for (const card of cards) {
      const actions = card.find('.pool-actions')
      expect(actions.exists()).toBe(true)

      // 重命名按钮（✏️）和删除按钮（🗑️）
      const buttons = actions.findAll('.btn-icon')
      expect(buttons.length).toBe(2)
    }

    wrapper.unmount()
  })
})

describe('StockPoolView - 创建对话框', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('点击"新建选股池"按钮打开创建对话框', async () => {
    mockGet.mockResolvedValue({ data: [] })

    const wrapper = mountView()
    await flushPromises()

    // 对话框初始不可见
    expect(wrapper.find('#create-dialog-title').exists()).toBe(false)

    // 点击新建按钮
    const createBtn = wrapper.findAll('.btn.btn-primary').find(
      (btn) => btn.text().includes('新建选股池'),
    )
    expect(createBtn).toBeDefined()
    await createBtn!.trigger('click')

    // 对话框应可见
    expect(wrapper.find('#create-dialog-title').exists()).toBe(true)
    expect(wrapper.find('#create-dialog-title').text()).toBe('新建选股池')

    wrapper.unmount()
  })

  it('名称为空时显示校验错误', async () => {
    mockGet.mockResolvedValue({ data: [] })

    const wrapper = mountView()
    await flushPromises()

    // 打开创建对话框
    const createBtn = wrapper.findAll('.btn.btn-primary').find(
      (btn) => btn.text().includes('新建选股池'),
    )
    await createBtn!.trigger('click')

    // 不输入名称，直接点击创建
    const confirmBtn = wrapper.findAll('.dialog-footer .btn-primary').find(
      (btn) => btn.text().includes('创建'),
    )
    await confirmBtn!.trigger('click')

    // 应显示校验错误
    expect(wrapper.find('.field-error').exists()).toBe(true)
    expect(wrapper.find('.field-error').text()).toContain('选股池名称不能为空')

    // 不应调用 API
    expect(mockPost).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('输入合法名称后调用创建 API', async () => {
    mockGet.mockResolvedValue({ data: [] })
    mockPost.mockResolvedValue({
      data: { id: 'new-pool', name: '新池', stock_count: 0, created_at: '2024-06-03T00:00:00', updated_at: '2024-06-03T00:00:00' },
    })

    const wrapper = mountView()
    await flushPromises()

    // 打开创建对话框
    const createBtn = wrapper.findAll('.btn.btn-primary').find(
      (btn) => btn.text().includes('新建选股池'),
    )
    await createBtn!.trigger('click')

    // 输入名称
    const input = wrapper.find('.dialog-body .input')
    await input.setValue('新池')

    // 点击创建
    const confirmBtn = wrapper.findAll('.dialog-footer .btn-primary').find(
      (btn) => btn.text().includes('创建'),
    )
    await confirmBtn!.trigger('click')
    await flushPromises()

    // 应调用创建 API
    expect(mockPost).toHaveBeenCalledWith('/pools', { name: '新池' })

    wrapper.unmount()
  })
})

describe('StockPoolView - 删除确认对话框', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('点击删除按钮打开确认对话框，显示选股池名称和数量', async () => {
    mockGet.mockResolvedValue({ data: MOCK_POOLS })

    const wrapper = mountView()
    await flushPromises()

    // 删除确认对话框初始不可见
    expect(wrapper.find('#delete-dialog-title').exists()).toBe(false)

    // 点击第一个选股池的删除按钮（🗑️）
    const firstCard = wrapper.findAll('.pool-card')[0]
    const deleteBtn = firstCard.find('.btn-icon-danger')
    await deleteBtn.trigger('click')

    // 确认对话框应可见
    expect(wrapper.find('#delete-dialog-title').exists()).toBe(true)

    // 应显示选股池名称和股票数量
    const dialogBody = wrapper.find('.dialog-body')
    expect(dialogBody.text()).toContain('趋势追踪池')
    expect(dialogBody.text()).toContain('5')

    wrapper.unmount()
  })

  it('确认删除后调用删除 API', async () => {
    mockGet.mockResolvedValue({ data: MOCK_POOLS })
    mockDelete.mockResolvedValue({ data: {} })

    const wrapper = mountView()
    await flushPromises()

    // 点击第一个选股池的删除按钮
    const firstCard = wrapper.findAll('.pool-card')[0]
    const deleteBtn = firstCard.find('.btn-icon-danger')
    await deleteBtn.trigger('click')

    // 点击确认删除
    const confirmBtn = wrapper.findAll('.dialog-footer .btn-danger').find(
      (btn) => btn.text().includes('确认删除'),
    )
    await confirmBtn!.trigger('click')
    await flushPromises()

    // 应调用删除 API
    expect(mockDelete).toHaveBeenCalledWith('/pools/pool-1')

    wrapper.unmount()
  })
})

// ─── 富化展示测试数据（需求 7）──────────────────────────────────────────────

const MOCK_ENRICHED_STOCKS = [
  {
    symbol: '600000',
    stock_name: '浦发银行',
    added_at: '2024-06-01T10:00:00',
    ref_buy_price: 12.50,
    trend_score: 85,
    risk_level: 'LOW',
    signals: [{ category: 'MA_TREND', label: '均线多头排列', is_fake_breakout: false, strength: 'STRONG' }],
    screen_time: '2024-06-01T15:30:00',
    has_fake_breakout: false,
    sector_classifications: { eastmoney: ['银行'], tonghuashun: ['银行'], tongdaxin: ['银行'] },
  },
  {
    symbol: '000001',
    stock_name: '平安银行',
    added_at: '2024-06-01T10:01:00',
    ref_buy_price: null,
    trend_score: null,
    risk_level: null,
    signals: null,
    screen_time: null,
    has_fake_breakout: false,
    sector_classifications: null,
  },
  {
    symbol: '600036',
    stock_name: '招商银行',
    added_at: '2024-06-01T10:02:00',
    ref_buy_price: 35.00,
    trend_score: 60,
    risk_level: 'MEDIUM',
    signals: [{ category: 'BREAKOUT', label: '突破', is_fake_breakout: false }],
    screen_time: '2024-06-01T15:30:00',
    has_fake_breakout: false,
    sector_classifications: null,
  },
]

/**
 * Helper: mount the view, expand pool-1, and return the wrapper.
 * mockGet is set up to route /pools → MOCK_POOLS, /pools/pool-1/stocks → MOCK_ENRICHED_STOCKS.
 */
async function mountAndExpandPool() {
  mockGet.mockImplementation((url: string, config?: any) => {
    if (url === '/pools') {
      return Promise.resolve({ data: MOCK_POOLS })
    }
    if (url.startsWith('/pools/pool-1/stocks')) {
      return Promise.resolve({ data: MOCK_ENRICHED_STOCKS })
    }
    return Promise.resolve({ data: [] })
  })

  const wrapper = mountView()
  await flushPromises()

  // Click pool header to expand
  const poolHeader = wrapper.findAll('.pool-header')[0]
  await poolHeader.trigger('click')
  await flushPromises()

  return wrapper
}

// ─── 富化展示测试（需求 7）──────────────────────────────────────────────────

describe('StockPoolView - 富化表格渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('(a) 展示买入参考价、趋势评分进度条、风险等级徽章、信号摘要、选股时间', async () => {
    const wrapper = await mountAndExpandPool()

    const rows = wrapper.findAll('.stock-row')
    expect(rows.length).toBe(3)

    // ── 第一行：600000 浦发银行（完整富化数据）──
    const row1 = rows[0]

    // 买入参考价 ¥12.50
    expect(row1.find('.price-cell').text()).toContain('¥12.50')

    // 趋势评分进度条
    const scoreBar = row1.find('.score-bar')
    expect(scoreBar.exists()).toBe(true)
    expect(scoreBar.attributes('aria-valuenow')).toBe('85')

    // 风险等级徽章
    const riskBadge = row1.find('.risk-badge')
    expect(riskBadge.exists()).toBe(true)
    expect(riskBadge.classes()).toContain('risk-low')
    expect(riskBadge.text()).toContain('低风险')

    // 信号摘要
    const signalCount = row1.find('.signal-count')
    expect(signalCount.exists()).toBe(true)
    expect(signalCount.text()).toContain('1 个信号')

    // 选股时间
    expect(row1.find('.time-cell').text()).toContain('2024-06-01')

    // ── 第二行：600036 招商银行（MEDIUM 风险，sorted by trend_score desc）──
    const row2 = rows[1]
    expect(row2.find('.price-cell').text()).toContain('¥35.00')
    const riskBadge2 = row2.find('.risk-badge')
    expect(riskBadge2.exists()).toBe(true)
    expect(riskBadge2.classes()).toContain('risk-medium')

    wrapper.unmount()
  })

  it('(b) 无选股结果数据的股票行显示占位符「—」', async () => {
    const wrapper = await mountAndExpandPool()

    const rows = wrapper.findAll('.stock-row')
    // Default sort is trend_score desc → 600000(85), 600036(60), 000001(null → -1)
    // Third row: 000001 平安银行（signals === null）
    const row2 = rows[2]

    // 买入参考价应为 —
    expect(row2.find('.price-cell').text()).toBe('—')

    // 趋势评分应为 — (no score-bar)
    expect(row2.find('.score-bar').exists()).toBe(false)
    expect(row2.find('.score-cell').text()).toBe('—')

    // 风险等级应为 — (no risk-badge)
    expect(row2.find('.risk-badge').exists()).toBe(false)

    // 信号摘要应为 — (no signal-count)
    expect(row2.find('.signal-count').exists()).toBe(false)
    expect(row2.find('.signals-cell').text()).toBe('—')

    // 选股时间应为 —
    expect(row2.find('.time-cell').text()).toBe('—')

    wrapper.unmount()
  })

  it('(c) 点击有选股结果的股票行展开详情面板', async () => {
    const wrapper = await mountAndExpandPool()

    // 详情面板初始不存在
    expect(wrapper.find('.detail-panel').exists()).toBe(false)

    // 点击第一行（600000，signals !== null）
    const rows = wrapper.findAll('.stock-row')
    await rows[0].trigger('click')
    await flushPromises()

    // 详情面板应出现
    expect(wrapper.find('.detail-panel').exists()).toBe(true)

    wrapper.unmount()
  })

  it('(d) 点击无选股结果的股票行不展开详情面板', async () => {
    const wrapper = await mountAndExpandPool()

    // Click third row (000001, signals === null — sorted last by trend_score desc)
    const rows = wrapper.findAll('.stock-row')
    await rows[2].trigger('click')
    await flushPromises()

    // 详情面板不应出现
    expect(wrapper.find('.detail-panel').exists()).toBe(false)

    wrapper.unmount()
  })

  it('(e) 点击趋势评分排序按钮后表格行顺序变化', async () => {
    const wrapper = await mountAndExpandPool()

    // 默认排序是 trend_score desc → 600000(85), 600036(60), 000001(null → -1)
    let rows = wrapper.findAll('.stock-row')
    expect(rows[0].find('.symbol-code').text()).toBe('600000')
    expect(rows[1].find('.symbol-code').text()).toBe('600036')
    expect(rows[2].find('.symbol-code').text()).toBe('000001')

    // 点击趋势评分排序按钮 → 切换为 asc
    const sortBtns = wrapper.findAll('.sort-btn')
    const trendSortBtn = sortBtns.find((btn) => btn.text().includes('趋势评分'))
    expect(trendSortBtn).toBeDefined()
    await trendSortBtn!.trigger('click')
    await flushPromises()

    // 排序后应为 asc → 000001(null → -1), 600036(60), 600000(85)
    rows = wrapper.findAll('.stock-row')
    expect(rows[0].find('.symbol-code').text()).toBe('000001')
    expect(rows[1].find('.symbol-code').text()).toBe('600036')
    expect(rows[2].find('.symbol-code').text()).toBe('600000')

    wrapper.unmount()
  })
})
