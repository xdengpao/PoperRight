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
      params: { freq: '5m', start: '2024-06-15', end: '2024-06-15', adj_type: 0 },
    })
  })

  it('selectedDate 有值时使用 selectedDate 发起请求', async () => {
    mount(MinuteKlineChart, {
      props: { ...defaultProps, selectedDate: '2024-03-20' },
    })
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '5m', start: '2024-03-20', end: '2024-03-20', adj_type: 0 },
    })
  })

  it('缓存命中时不发起重复请求', async () => {
    const fakeBars = [{ time: '2024-06-15T09:35:00', open: '10', high: '11', low: '9', close: '10.5', volume: 100, amount: '1000', turnover: '0.1', vol_ratio: '1.0' }]
    minuteKlineCache.set('600000-2024-06-15-5m-0', fakeBars)

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
      params: { freq: '15m', start: '2024-06-15', end: '2024-06-15', adj_type: 0 },
    })
  })
})

describe('MinuteKlineChart 复权类型切换', () => {
  beforeEach(() => {
    minuteKlineCache.clear()
    vi.mocked(apiClient.get).mockReset()
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bars: [] } })
  })

  /** Validates: Requirements 5.1, 5.4 */
  it('默认 adjType 为 0，"原始"按钮高亮', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()

    const adjButtons = wrapper.findAll('.adj-btn')
    expect(adjButtons).toHaveLength(2)
    expect(adjButtons[0].text()).toBe('原始')
    expect(adjButtons[1].text()).toBe('前复权')

    // "原始" should be active
    expect(adjButtons[0].classes()).toContain('active')
    expect(adjButtons[1].classes()).not.toContain('active')

    // aria-pressed reflects default state
    expect(adjButtons[0].attributes('aria-pressed')).toBe('true')
    expect(adjButtons[1].attributes('aria-pressed')).toBe('false')
  })

  /** Validates: Requirements 5.2 */
  it('点击"前复权"按钮发起 adj_type=1 的 API 请求', async () => {
    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    await flushPromises()
    vi.mocked(apiClient.get).mockClear()

    // Click "前复权"
    const adjButtons = wrapper.findAll('.adj-btn')
    await adjButtons[1].trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '5m', start: '2024-06-15', end: '2024-06-15', adj_type: 1 },
    })

    // "前复权" should now be active
    expect(adjButtons[1].classes()).toContain('active')
    expect(adjButtons[0].classes()).not.toContain('active')
  })

  /** Validates: Requirements 5.7 */
  it('加载中时复权切换按钮被禁用', async () => {
    // Make API hang so loading stays true
    let resolveApi!: (value: any) => void
    vi.mocked(apiClient.get).mockImplementation(
      () => new Promise((resolve) => { resolveApi = resolve }),
    )

    const wrapper = mount(MinuteKlineChart, { props: defaultProps })
    // Allow the watch to fire and start loading
    await flushPromises()

    const adjButtons = wrapper.findAll('.adj-btn')
    expect(adjButtons[0].attributes('disabled')).toBeDefined()
    expect(adjButtons[1].attributes('disabled')).toBeDefined()

    // Resolve the API call and verify buttons are re-enabled
    resolveApi({ data: { bars: [] } })
    await flushPromises()

    expect(adjButtons[0].attributes('disabled')).toBeUndefined()
    expect(adjButtons[1].attributes('disabled')).toBeUndefined()
  })

  /** Validates: Requirements 5.5 */
  it('切换 adjType 保持当前日期和周期不变', async () => {
    const wrapper = mount(MinuteKlineChart, {
      props: { ...defaultProps, selectedDate: '2024-03-20' },
    })
    await flushPromises()

    // Switch freq to 15m first
    const freqButtons = wrapper.findAll('.freq-btn')
    await freqButtons[2].trigger('click')
    await flushPromises()
    vi.mocked(apiClient.get).mockClear()

    // Now switch to 前复权
    const adjButtons = wrapper.findAll('.adj-btn')
    await adjButtons[1].trigger('click')
    await flushPromises()

    // Should request with same date (2024-03-20) and freq (15m), only adj_type changed
    expect(apiClient.get).toHaveBeenCalledWith('/data/kline/600000', {
      params: { freq: '15m', start: '2024-03-20', end: '2024-03-20', adj_type: 1 },
    })

    // Freq and date label should remain unchanged
    expect(freqButtons[2].classes()).toContain('active')
    expect(wrapper.find('.date-label').text()).toBe('2024-03-20 分钟K线')
  })
})
