/**
 * ScreenerResultsView 信号标签增强单元测试
 *
 * 测试信号标签的描述文本显示、强度颜色编码、新鲜度徽章和图例组件。
 *
 * Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.5, 5.4, 6.1, 6.2, 6.3
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// ─── Mock 依赖 ────────────────────────────────────────────────────────────────

const mockGet = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener/results' } },
  }),
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

vi.mock('@/components/LoadingSpinner.vue', () => ({
  default: { name: 'LoadingSpinner', template: '<div class="mock-loading"></div>', props: ['text'] },
}))

vi.mock('@/components/ErrorBanner.vue', () => ({
  default: { name: 'ErrorBanner', template: '<div class="mock-error"></div>', props: ['message', 'retryFn'] },
}))

import ScreenerResultsView from '../ScreenerResultsView.vue'

// ─── 测试数据工厂 ─────────────────────────────────────────────────────────────

interface MockSignal {
  category: string
  label: string
  is_fake_breakout: boolean
  strength?: string
  freshness?: string
  description?: string
  dimension?: string
}

interface MockSectorClassifications {
  eastmoney: string[]
  tonghuashun: string[]
  tongdaxin: string[]
}

interface MockRow {
  symbol: string
  name: string
  ref_buy_price: number
  trend_score: number
  risk_level: string
  signals: MockSignal[]
  screen_time: string
  has_fake_breakout: boolean
  sector_classifications?: MockSectorClassifications
}

function makeRow(overrides: Partial<MockRow> & { signals: MockSignal[] }): MockRow {
  return {
    symbol: '600000',
    name: '测试股票',
    ref_buy_price: 10.5,
    trend_score: 75,
    risk_level: 'LOW',
    screen_time: '2024-01-15T10:30:00',
    has_fake_breakout: false,
    ...overrides,
  }
}

function setupMockApi(rows: MockRow[]) {
  mockGet.mockImplementation((url: string) => {
    if (url === '/screen/results') {
      return Promise.resolve({ data: rows })
    }
    // K线数据请求返回空
    if (typeof url === 'string' && url.includes('/data/kline/')) {
      return Promise.resolve({ data: { bars: [] } })
    }
    return Promise.resolve({ data: [] })
  })
}

async function mountAndExpand(rows: MockRow[]) {
  setupMockApi(rows)
  const wrapper = mount(ScreenerResultsView, {
    global: { plugins: [createPinia()] },
  })
  await flushPromises()

  // 点击第一行展开详情
  const firstRow = wrapper.find('.result-row')
  if (firstRow.exists()) {
    await firstRow.trigger('click')
    await flushPromises()
  }

  return wrapper
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('ScreenerResultsView - 信号标签增强', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
  })

  // ─── Req 3.1, 3.2: 描述文本显示 ──────────────────────────────────────────

  describe('描述文本显示与回退逻辑', () => {
    it('信号有 description 时，标签显示"分类名：描述文本"格式', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'MA_TREND',
            label: 'ma_trend',
            is_fake_breakout: false,
            strength: 'STRONG',
            freshness: 'NEW',
            description: '5日/10日/20日均线多头排列, 趋势评分 85',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.exists()).toBe(true)
      expect(tag.text()).toContain('均线趋势')
      expect(tag.text()).toContain('5日/10日/20日均线多头排列, 趋势评分 85')
      // 不应显示原始 label
      expect(tag.text()).not.toContain('ma_trend')

      wrapper.unmount()
    })

    it('信号 description 为空时，标签回退显示"分类名：label"格式', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'MACD',
            label: 'macd_golden_cross',
            is_fake_breakout: false,
            strength: 'MEDIUM',
            description: '',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.exists()).toBe(true)
      expect(tag.text()).toContain('MACD')
      expect(tag.text()).toContain('macd_golden_cross')

      wrapper.unmount()
    })

    it('信号无 description 字段时，标签回退显示 label', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'RSI',
            label: 'rsi_strong',
            is_fake_breakout: false,
            strength: 'WEAK',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.exists()).toBe(true)
      expect(tag.text()).toContain('RSI')
      expect(tag.text()).toContain('rsi_strong')

      wrapper.unmount()
    })
  })

  // ─── Req 4.1, 4.2, 4.3, 4.5: 强度颜色编码 CSS 类 ────────────────────────

  describe('强度颜色编码 CSS 类映射', () => {
    it('strength 为 STRONG 时，标签包含 sig-strong 类', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'MA_TREND',
            label: 'ma_trend',
            is_fake_breakout: false,
            strength: 'STRONG',
            description: '均线多头排列',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.classes()).toContain('sig-strong')

      wrapper.unmount()
    })

    it('strength 为 MEDIUM 时，标签包含 sig-medium 类', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'MACD',
            label: 'macd',
            is_fake_breakout: false,
            strength: 'MEDIUM',
            description: 'MACD 金叉',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.classes()).toContain('sig-medium')

      wrapper.unmount()
    })

    it('strength 为 WEAK 时，标签包含 sig-weak 类', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'BOLL',
            label: 'boll',
            is_fake_breakout: false,
            strength: 'WEAK',
            description: '布林带信号',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.classes()).toContain('sig-weak')

      wrapper.unmount()
    })

    it('strength 缺失时，标签默认使用 sig-medium 类', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'DMA',
            label: 'dma',
            is_fake_breakout: false,
            // strength 未设置
            description: 'DMA 信号',
          }],
        }),
      ])

      const tag = wrapper.find('.signal-tag')
      expect(tag.classes()).toContain('sig-medium')

      wrapper.unmount()
    })

    it('标签内显示强度文字标注"强"/"中"/"弱"', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [
            { category: 'MA_TREND', label: 'a', is_fake_breakout: false, strength: 'STRONG', description: '信号A' },
            { category: 'MACD', label: 'b', is_fake_breakout: false, strength: 'MEDIUM', description: '信号B' },
            { category: 'BOLL', label: 'c', is_fake_breakout: false, strength: 'WEAK', description: '信号C' },
          ],
        }),
      ])

      const strengthLabels = wrapper.findAll('.strength-label')
      expect(strengthLabels.length).toBe(3)
      expect(strengthLabels[0].text()).toBe('强')
      expect(strengthLabels[1].text()).toBe('中')
      expect(strengthLabels[2].text()).toBe('弱')

      wrapper.unmount()
    })
  })

  // ─── Req 6.1, 6.2, 6.3: 新鲜度徽章 ──────────────────────────────────────

  describe('新鲜度徽章显示/隐藏逻辑', () => {
    it('freshness 为 NEW 时，显示"新"徽章', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'BREAKOUT',
            label: 'breakout',
            is_fake_breakout: false,
            strength: 'STRONG',
            freshness: 'NEW',
            description: '箱体突破',
          }],
        }),
      ])

      const badge = wrapper.find('.freshness-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('新')

      wrapper.unmount()
    })

    it('freshness 为 CONTINUING 时，不显示新鲜度徽章', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'CAPITAL_INFLOW',
            label: 'capital',
            is_fake_breakout: false,
            strength: 'MEDIUM',
            freshness: 'CONTINUING',
            description: '主力资金净流入',
          }],
        }),
      ])

      const badge = wrapper.find('.freshness-badge')
      expect(badge.exists()).toBe(false)

      wrapper.unmount()
    })

    it('freshness 缺失时，不显示新鲜度徽章', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'LARGE_ORDER',
            label: 'large_order',
            is_fake_breakout: false,
            strength: 'WEAK',
            // freshness 未设置
            description: '大单成交活跃',
          }],
        }),
      ])

      const badge = wrapper.find('.freshness-badge')
      expect(badge.exists()).toBe(false)

      wrapper.unmount()
    })
  })

  // ─── Req 5.4: 图例组件条件渲染 ───────────────────────────────────────────

  describe('图例组件条件渲染', () => {
    it('有选股结果时，展开详情后显示信号强度图例', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{
            category: 'MA_TREND',
            label: 'ma_trend',
            is_fake_breakout: false,
            strength: 'STRONG',
            description: '均线多头排列',
          }],
        }),
      ])

      const legend = wrapper.find('.signal-strength-legend')
      expect(legend.exists()).toBe(true)
      expect(legend.text()).toContain('强：多个因子共振确认')
      expect(legend.text()).toContain('中：部分因子确认')
      expect(legend.text()).toContain('弱：单一因子触发')

      wrapper.unmount()
    })

    it('选股结果为空时，不显示信号强度图例', async () => {
      setupMockApi([])
      const wrapper = mount(ScreenerResultsView, {
        global: { plugins: [createPinia()] },
      })
      await flushPromises()

      // 空结果时不会有展开行，也不会有图例
      const legend = wrapper.find('.signal-strength-legend')
      expect(legend.exists()).toBe(false)

      wrapper.unmount()
    })
  })

  // ─── Req 9.4, 9.5, 9.6: 板块分类渲染 ────────────────────────────────────

  describe('板块分类渲染', () => {
    it('三列布局渲染正确（三个数据源均有数据）', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{ category: 'MA_TREND', label: 'ma_trend', is_fake_breakout: false, strength: 'STRONG', description: '均线多头排列' }],
          sector_classifications: {
            eastmoney: ['半导体', '芯片概念'],
            tonghuashun: ['半导体及元件'],
            tongdaxin: ['半导体', '电子信息'],
          },
        }),
      ])

      const sectorArea = wrapper.find('.sector-classifications')
      expect(sectorArea.exists()).toBe(true)

      const columns = wrapper.findAll('.sector-column')
      expect(columns.length).toBe(3)

      // 东方财富列
      const eastmoneyTags = columns[0].findAll('.sector-tag')
      expect(eastmoneyTags.length).toBe(2)
      expect(eastmoneyTags[0].text()).toBe('半导体')
      expect(eastmoneyTags[1].text()).toBe('芯片概念')

      // 同花顺列
      const thsTags = columns[1].findAll('.sector-tag')
      expect(thsTags.length).toBe(1)
      expect(thsTags[0].text()).toBe('半导体及元件')

      // 通达信列
      const tdxTags = columns[2].findAll('.sector-tag')
      expect(tdxTags.length).toBe(2)
      expect(tdxTags[0].text()).toBe('半导体')
      expect(tdxTags[1].text()).toBe('电子信息')

      wrapper.unmount()
    })

    it('数据源中文标题正确显示（"东方财富"、"同花顺"、"通达信"）', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{ category: 'MACD', label: 'macd', is_fake_breakout: false, strength: 'MEDIUM', description: 'MACD 金叉' }],
          sector_classifications: {
            eastmoney: ['银行'],
            tonghuashun: ['银行'],
            tongdaxin: ['银行'],
          },
        }),
      ])

      const titles = wrapper.findAll('.sector-source-title')
      expect(titles.length).toBe(3)
      expect(titles[0].text()).toBe('东方财富')
      expect(titles[1].text()).toBe('同花顺')
      expect(titles[2].text()).toBe('通达信')

      wrapper.unmount()
    })

    it('某数据源板块列表为空时显示"暂无数据"占位文本', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{ category: 'RSI', label: 'rsi', is_fake_breakout: false, strength: 'WEAK', description: 'RSI 信号' }],
          sector_classifications: {
            eastmoney: ['新能源'],
            tonghuashun: [],
            tongdaxin: [],
          },
        }),
      ])

      const columns = wrapper.findAll('.sector-column')
      expect(columns.length).toBe(3)

      // 东方财富有数据，不显示占位文本
      expect(columns[0].find('.sector-empty').exists()).toBe(false)
      expect(columns[0].findAll('.sector-tag').length).toBe(1)

      // 同花顺为空，显示"暂无数据"
      expect(columns[1].find('.sector-empty').exists()).toBe(true)
      expect(columns[1].find('.sector-empty').text()).toBe('暂无数据')

      // 通达信为空，显示"暂无数据"
      expect(columns[2].find('.sector-empty').exists()).toBe(true)
      expect(columns[2].find('.sector-empty').text()).toBe('暂无数据')

      wrapper.unmount()
    })

    it('sector_classifications 字段缺失时不渲染板块分类区域', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [{ category: 'BOLL', label: 'boll', is_fake_breakout: false, strength: 'MEDIUM', description: '布林带信号' }],
          // sector_classifications 未设置
        }),
      ])

      const sectorArea = wrapper.find('.sector-classifications')
      expect(sectorArea.exists()).toBe(false)

      wrapper.unmount()
    })
  })

  // ─── Req 10.3, 10.4, 10.5: 信号维度分组渲染 ─────────────────────────────

  describe('信号维度分组渲染', () => {
    it('信号按维度分组展示，每组有维度标题', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [
            { category: 'MA_TREND', label: 'ma_trend', is_fake_breakout: false, strength: 'STRONG', description: '均线多头排列', dimension: '技术面' },
            { category: 'CAPITAL_INFLOW', label: 'capital', is_fake_breakout: false, strength: 'MEDIUM', description: '主力资金净流入', dimension: '资金面' },
          ],
        }),
      ])

      const headers = wrapper.findAll('.dimension-header')
      expect(headers.length).toBe(2)
      expect(headers[0].text()).toBe('技术面')
      expect(headers[1].text()).toBe('资金面')

      // 每组下有对应的信号标签
      const tags = wrapper.findAll('.signal-tag')
      expect(tags.length).toBe(2)
      expect(tags[0].text()).toContain('均线趋势')
      expect(tags[1].text()).toContain('资金流入')

      wrapper.unmount()
    })

    it('维度分组按固定顺序（技术面 → 板块面 → 资金面 → 基本面）', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [
            { category: 'CAPITAL_INFLOW', label: 'capital', is_fake_breakout: false, strength: 'MEDIUM', description: '主力资金净流入', dimension: '资金面' },
            { category: 'SECTOR_STRONG', label: 'sector', is_fake_breakout: false, strength: 'STRONG', description: '板块强势', dimension: '板块面' },
            { category: 'MA_TREND', label: 'ma_trend', is_fake_breakout: false, strength: 'STRONG', description: '均线多头排列', dimension: '技术面' },
          ],
        }),
      ])

      const headers = wrapper.findAll('.dimension-header')
      expect(headers.length).toBe(3)
      // 固定顺序：技术面 → 板块面 → 资金面
      expect(headers[0].text()).toBe('技术面')
      expect(headers[1].text()).toBe('板块面')
      expect(headers[2].text()).toBe('资金面')

      wrapper.unmount()
    })

    it('无信号的维度分组被跳过', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [
            { category: 'MA_TREND', label: 'ma_trend', is_fake_breakout: false, strength: 'STRONG', description: '均线多头排列', dimension: '技术面' },
            { category: 'MACD', label: 'macd', is_fake_breakout: false, strength: 'MEDIUM', description: 'MACD 金叉', dimension: '技术面' },
          ],
        }),
      ])

      const headers = wrapper.findAll('.dimension-header')
      // 只有技术面有信号，其他维度被跳过
      expect(headers.length).toBe(1)
      expect(headers[0].text()).toBe('技术面')

      // 技术面下有两个信号标签
      const tags = wrapper.findAll('.signal-tag')
      expect(tags.length).toBe(2)

      wrapper.unmount()
    })

    it('dimension 缺失时信号归入"其他"分组', async () => {
      const wrapper = await mountAndExpand([
        makeRow({
          signals: [
            { category: 'MA_TREND', label: 'ma_trend', is_fake_breakout: false, strength: 'STRONG', description: '均线多头排列', dimension: '技术面' },
            { category: 'RSI', label: 'rsi', is_fake_breakout: false, strength: 'WEAK', description: 'RSI 信号' },
          ],
        }),
      ])

      const headers = wrapper.findAll('.dimension-header')
      expect(headers.length).toBe(2)
      expect(headers[0].text()).toBe('技术面')
      expect(headers[1].text()).toBe('其他')

      wrapper.unmount()
    })
  })
})
