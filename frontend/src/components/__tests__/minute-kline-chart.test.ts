import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { minuteKlineCache } from '../minuteKlineUtils'

// Mock vue-echarts and echarts to avoid ESM import issues in test environment
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="mock-vchart"></div>', props: ['option', 'autoresize'] },
}))
vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/charts', () => ({ CandlestickChart: {}, BarChart: {} }))
vi.mock('echarts/components', () => ({ GridComponent: {}, TooltipComponent: {}, DataZoomComponent: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

// Mock apiClient
vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { bars: [] } }),
  },
}))

// Import component and mocked modules after mocks are set up
import MinuteKlineChart from '../MinuteKlineChart.vue'
import { apiClient } from '@/api'

const defaultProps = {
  symbol: '600000',
  selectedDate: null,
  latestTradeDate: '2024-06-15',
}

describe('MinuteKlineChart 组件骨架', () => {
  beforeEach(() => {
    minuteKlineCache.clear()
  })

  it('渲染五个周期按钮（1m/5m/15m/30m/60m）', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    const buttons = wrapper.findAll('.freq-btn')
    expect(buttons).toHaveLength(5)
    expect(buttons.map((b) => b.text())).toEqual(['1m', '5m', '15m', '30m', '60m'])
  })

  it('默认高亮 5m 按钮', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    const activeBtn = wrapper.find('.freq-btn.active')
    expect(activeBtn.exists()).toBe(true)
    expect(activeBtn.text()).toBe('5m')
  })

  it('点击周期按钮切换高亮', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    const buttons = wrapper.findAll('.freq-btn')

    // 点击 15m
    await buttons[2].trigger('click')
    await flushPromises()
    expect(buttons[2].classes()).toContain('active')
    // 5m 不再高亮
    expect(buttons[1].classes()).not.toContain('active')
  })

  it('selectedDate 为 null 时使用 latestTradeDate 显示日期标签', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    expect(wrapper.find('.date-label').text()).toBe('2024-06-15 分钟K线')
  })

  it('selectedDate 有值时使用 selectedDate 显示日期标签', async () => {
    const wrapper = mount(MinuteKlineChart, {
      props: { ...defaultProps, selectedDate: '2024-03-20' },
    })
    await flushPromises()
    expect(wrapper.find('.date-label').text()).toBe('2024-03-20 分钟K线')
  })

  it('周期按钮具有正确的 aria-pressed 属性', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    const buttons = wrapper.findAll('.freq-btn')
    // 5m (index 1) should be pressed
    expect(buttons[1].attributes('aria-pressed')).toBe('true')
    // others should not
    expect(buttons[0].attributes('aria-pressed')).toBe('false')
    expect(buttons[2].attributes('aria-pressed')).toBe('false')
  })
})

describe('MinuteKlineChart 数据加载与缓存', () => {
  beforeEach(() => {
    minuteKlineCache.clear()
    vi.mocked(apiClient.get).mockReset()
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bars: [] } })
  })

  it('挂载时使用 latestTradeDate 发起 API 请求（selectedDate 为 null）', async () => {
    mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '5m', start: '2024-06-15', end: '2024-06-15' },
    })
  })

  it('selectedDate 有值时使用 selectedDate 发起请求', async () => {
    mount(MinuteKlineChart, {
      props: { ...defaultProps, selectedDate: '2024-03-20' },
    })
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '5m', start: '2024-03-20', end: '2024-03-20' },
    })
  })

  it('缓存命中时不发起重复请求', async () => {
    const fakeBars = [{ time: '2024-06-15T09:35:00', open: '10', high: '11', low: '9', close: '10.5', volume: 100, amount: '1000', turnover: '0.1', vol_ratio: '1.0' }]
    minuteKlineCache.set('600000-2024-06-15-5m', fakeBars)

    mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    expect(apiClient.get).not.toHaveBeenCalled()
  })

  it('API 请求失败时显示错误信息', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    expect(wrapper.find('.chart-error').text()).toBe('加载分钟K线失败')
  })

  it('API 返回空 bars 时显示空数据提示', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bars: [] } })

    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    expect(wrapper.find('.chart-placeholder').text()).toBe('该交易日暂无分钟K线数据')
  })

  it('emit loading 事件', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    const events = wrapper.emitted('loading') ?? []
    expect(events).toContainEqual([true])
    expect(events).toContainEqual([false])
  })

  it('切换 freq 后发起新请求', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    vi.mocked(apiClient.get).mockClear()

    // 点击 15m
    const buttons = wrapper.findAll('.freq-btn')
    await buttons[2].trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '15m', start: '2024-06-15', end: '2024-06-15' },
    })
  })
})
