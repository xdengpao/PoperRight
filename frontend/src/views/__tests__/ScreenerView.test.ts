/**
 * ScreenerView 前端组件单元测试
 *
 * 测试因子条件编辑器优化功能的 UI 行为：
 * - factor-registry API 集成与数据绑定
 * - boolean 因子 toggle 渲染
 * - range 因子双输入框渲染
 * - 因子 tooltip 显示
 * - 恢复默认按钮功能
 * - 板块面选择器渲染
 * - 策略示例加载器
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 14.2
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ScreenerView from '../ScreenerView.vue'
import type { FactorMeta, StrategyExample } from '@/stores/screener'

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

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/screener' } },
  }),
}))

// ─── 测试数据 ─────────────────────────────────────────────────────────────────

const MOCK_FACTOR_REGISTRY: Record<string, FactorMeta[]> = {
  technical: [
    {
      factor_name: 'ma_trend',
      label: 'MA趋势打分',
      category: 'technical',
      threshold_type: 'absolute',
      default_threshold: 80,
      value_min: 0,
      value_max: 100,
      unit: '分',
      description: '基于均线排列程度、斜率和价格距离的综合打分',
      examples: [{ operator: '>=', threshold: 80 }],
      default_range: null,
    },
    {
      factor_name: 'ma_support',
      label: '均线支撑信号',
      category: 'technical',
      threshold_type: 'boolean',
      default_threshold: null,
      value_min: null,
      value_max: null,
      unit: '',
      description: '价格回调至均线附近后企稳反弹的信号',
      examples: [],
      default_range: null,
    },
    {
      factor_name: 'rsi',
      label: 'RSI强势信号',
      category: 'technical',
      threshold_type: 'range',
      default_threshold: null,
      value_min: 0,
      value_max: 100,
      unit: '',
      description: 'RSI 处于强势区间且无超买背离',
      examples: [],
      default_range: [50, 80],
    },
  ],
  money_flow: [
    {
      factor_name: 'money_flow',
      label: '主力资金净流入',
      category: 'money_flow',
      threshold_type: 'percentile',
      default_threshold: 80,
      value_min: 0,
      value_max: 100,
      unit: '',
      description: '主力资金净流入的全市场百分位排名',
      examples: [],
      default_range: null,
      data_source_config: {
        kind: 'money_flow',
        config_path: 'volume_price.money_flow_source',
        scope: 'strategy',
        options: [
          { value: 'moneyflow_dc', label: '东方财富资金流', description: '覆盖较完整，推荐默认使用', recommended: true, legacy: false },
          { value: 'moneyflow_ths', label: '同花顺资金流', description: '覆盖较完整，可作为备选资金流源', recommended: false, legacy: false },
          { value: 'money_flow', label: '旧资金流表', description: '历史旧表，当前覆盖不足', recommended: false, legacy: true },
        ],
      },
    },
  ],
  fundamental: [
    {
      factor_name: 'pe',
      label: '市盈率 TTM',
      category: 'fundamental',
      threshold_type: 'industry_relative',
      default_threshold: 1.0,
      value_min: 0,
      value_max: 5.0,
      unit: '',
      description: '市盈率的行业相对值',
      examples: [],
      default_range: null,
    },
  ],
  sector: [
    {
      factor_name: 'sector_rank',
      label: '板块涨幅排名',
      category: 'sector',
      threshold_type: 'absolute',
      default_threshold: 30,
      value_min: 1,
      value_max: 300,
      unit: '',
      description: '股票所属板块在全市场板块涨幅排名中的位次',
      examples: [],
      default_range: null,
      data_source_config: {
        kind: 'sector',
        config_path: 'sector_config.sector_data_source',
        scope: 'strategy',
        options: [
          { value: 'DC', label: '东方财富 DC', description: '', recommended: false, legacy: false },
          { value: 'THS', label: '同花顺 THS', description: '', recommended: false, legacy: false },
          { value: 'TDX', label: '通达信 TDX', description: '', recommended: false, legacy: false },
          { value: 'TI', label: '申万行业 TI', description: '', recommended: false, legacy: false },
          { value: 'CI', label: '中信行业 CI', description: '', recommended: false, legacy: false },
        ],
      },
    },
    {
      factor_name: 'sector_trend',
      label: '板块趋势',
      category: 'sector',
      threshold_type: 'boolean',
      default_threshold: null,
      value_min: null,
      value_max: null,
      unit: '',
      description: '股票所属板块是否处于多头趋势',
      examples: [],
      default_range: null,
      data_source_config: {
        kind: 'sector',
        config_path: 'sector_config.sector_data_source',
        scope: 'strategy',
        options: [
          { value: 'DC', label: '东方财富 DC', description: '', recommended: false, legacy: false },
          { value: 'THS', label: '同花顺 THS', description: '', recommended: false, legacy: false },
          { value: 'TDX', label: '通达信 TDX', description: '', recommended: false, legacy: false },
          { value: 'TI', label: '申万行业 TI', description: '', recommended: false, legacy: false },
          { value: 'CI', label: '中信行业 CI', description: '', recommended: false, legacy: false },
        ],
      },
    },
    {
      factor_name: 'index_pe',
      label: '指数市盈率',
      category: 'sector',
      threshold_type: 'range',
      default_threshold: null,
      value_min: null,
      value_max: null,
      unit: '',
      description: '所属指数的市盈率',
      examples: [],
      default_range: [10, 25],
    },
  ],
}

const MOCK_STRATEGY_EXAMPLES: StrategyExample[] = [
  {
    name: '强势多头趋势追踪',
    description: '捕捉处于强势上升趋势中的个股',
    factors: [
      { factor_name: 'ma_trend', operator: '>=', threshold: 85, params: {} },
      { factor_name: 'ma_support', operator: '==', threshold: null, params: {} },
    ],
    logic: 'AND',
    weights: { ma_trend: 0.6, ma_support: 0.4 },
    enabled_modules: ['factor_editor', 'ma_trend'],
    sector_config: null,
    config_doc: '',
  },
  {
    name: '概念板块热点龙头',
    description: '追踪概念板块轮动热点',
    factors: [
      { factor_name: 'sector_rank', operator: '<=', threshold: 15, params: {} },
      { factor_name: 'sector_trend', operator: '==', threshold: null, params: {} },
    ],
    logic: 'AND',
    weights: { sector_rank: 0.5, sector_trend: 0.5 },
    enabled_modules: ['factor_editor', 'ma_trend'],
    sector_config: { sector_data_source: 'DC', sector_period: 3, sector_top_n: 15 },
    config_doc: '',
  },
]

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function setupDefaultMocks() {
  mockGet.mockImplementation((url: string) => {
    if (url === '/screen/factor-registry') {
      return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
    }
    if (url === '/screen/strategy-examples') {
      return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
    }
    if (url === '/strategies') {
      return Promise.resolve({ data: [] })
    }
    if (url === '/screen/schedule') {
      return Promise.resolve({ data: null })
    }
    return Promise.resolve({ data: [] })
  })
}

function mountScreenerView() {
  return mount(ScreenerView, {
    global: {
      plugins: [createPinia()],
    },
  })
}

/**
 * Mount ScreenerView with factor_editor module enabled and factor registry loaded.
 * Simulates selecting a strategy that has factor_editor enabled.
 */
async function mountWithFactorEditor() {
  const wrapper = mountScreenerView()
  await flushPromises()

  // The factor editor section is only visible when factor_editor module is enabled.
  // We need to create a strategy and select it, or directly manipulate the component state.
  // Since the component uses currentEnabledModules ref, we can trigger the "新建策略" flow
  // or use the strategy examples loader which sets enabled_modules.

  return wrapper
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('ScreenerView - factor-registry API integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 1.4, 7.1: factor-registry API 调用与数据绑定 ────────────────────

  it('fetches factor registry on mount', async () => {
    mountScreenerView()
    await flushPromises()

    // Verify the factor-registry API was called
    const factorRegistryCalls = mockGet.mock.calls.filter(
      (call: unknown[]) => call[0] === '/screen/factor-registry'
    )
    expect(factorRegistryCalls.length).toBe(1)
  })

  it('fetches strategy examples on mount', async () => {
    mountScreenerView()
    await flushPromises()

    const exampleCalls = mockGet.mock.calls.filter(
      (call: unknown[]) => call[0] === '/screen/strategy-examples'
    )
    expect(exampleCalls.length).toBe(1)
  })

  it('binds factor registry data to the store', async () => {
    const wrapper = mountScreenerView()
    await flushPromises()

    const { useScreenerStore } = await import('@/stores/screener')
    const store = useScreenerStore()

    expect(Object.keys(store.factorRegistry).length).toBeGreaterThan(0)
    expect(store.factorRegistry.technical).toBeDefined()
    expect(store.factorRegistry.technical.length).toBe(3)
    expect(store.factorRegistry.technical[0].factor_name).toBe('ma_trend')

    wrapper.unmount()
  })
})


describe('ScreenerView - boolean factor toggle rendering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 7.4: boolean 因子显示 toggle 控件 ───────────────────────────────

  it('renders toggle switch for boolean-type factors instead of threshold input', async () => {
    // Create a strategy with factor_editor enabled and a boolean factor
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-1',
            name: 'Test Strategy',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_support', operator: '==', threshold: null, params: {} },
              ],
              weights: { ma_support: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-1',
            name: 'Test Strategy',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_support', operator: '==', threshold: null, params: {} },
              ],
              weights: { ma_support: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()

    // The component auto-selects the active strategy, which loads the factor_editor module
    // Wait for the strategy selection to complete
    await flushPromises()

    // Find the factor row with the boolean factor
    const factorRows = wrapper.findAll('.factor-row')
    expect(factorRows.length).toBeGreaterThanOrEqual(1)

    // Boolean factor should have a toggle switch
    const toggleSwitch = wrapper.find('.factor-toggle')
    expect(toggleSwitch.exists()).toBe(true)

    // Boolean factor should NOT have a regular threshold input
    const thresholdInputs = factorRows[0].findAll('input.factor-threshold')
    expect(thresholdInputs.length).toBe(0)

    // Boolean factor should NOT have an operator select
    const operatorSelects = factorRows[0].findAll('.factor-op')
    expect(operatorSelects.length).toBe(0)

    wrapper.unmount()
  })
})

describe('ScreenerView - range factor dual-input rendering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 7.5: range 因子显示双输入框 ─────────────────────────────────────

  it('renders dual inputs (lower/upper) for range-type factors', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-2',
            name: 'Range Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 50, threshold_high: 80 } },
              ],
              weights: { rsi: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-2',
            name: 'Range Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 50, threshold_high: 80 } },
              ],
              weights: { rsi: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Find the range inputs container
    const rangeInputs = wrapper.find('.range-inputs')
    expect(rangeInputs.exists()).toBe(true)

    // Should have two half-width inputs
    const halfInputs = rangeInputs.findAll('.factor-threshold-half')
    expect(halfInputs.length).toBe(2)

    // Should have a range separator
    const sep = rangeInputs.find('.range-sep')
    expect(sep.exists()).toBe(true)
    expect(sep.text()).toBe('–')

    wrapper.unmount()
  })
})


describe('ScreenerView - factor tooltip display', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 7.3: 因子名称 hover 显示 tooltip ────────────────────────────────

  it('displays tooltip with factor description on factor name wrapper', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-3',
            name: 'Tooltip Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-3',
            name: 'Tooltip Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // The factor-name-wrapper should have a title attribute with the description
    const nameWrapper = wrapper.find('.factor-name-wrapper')
    expect(nameWrapper.exists()).toBe(true)
    expect(nameWrapper.attributes('title')).toContain('基于均线排列程度')

    wrapper.unmount()
  })
})

describe('ScreenerView - threshold type badge display', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 7.1: 阈值类型标签显示 ──────────────────────────────────────────

  it('displays threshold type badge for each factor', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-badge',
            name: 'Badge Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
                { factor_name: 'money_flow', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 0.5, money_flow: 0.5 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-badge',
            name: 'Badge Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
                { factor_name: 'money_flow', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 0.5, money_flow: 0.5 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Find threshold type badges
    const badges = wrapper.findAll('.threshold-type-badge')
    expect(badges.length).toBe(2)

    // First factor (ma_trend) should show '绝对值'
    expect(badges[0].text()).toBe('绝对值')

    // Second factor (money_flow) should show '百分位'
    expect(badges[1].text()).toBe('百分位')
    expect(badges[1].classes()).toContain('percentile')

    wrapper.unmount()
  })

  // ─── Req 7.2: 单位和取值范围提示 ────────────────────────────────────────

  it('displays unit and value range hint next to threshold input', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-unit',
            name: 'Unit Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-unit',
            name: 'Unit Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 80, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // ma_trend has unit '分' and range 0-100
    const unitSpan = wrapper.find('.factor-unit')
    expect(unitSpan.exists()).toBe(true)
    expect(unitSpan.text()).toBe('分')

    const rangeHint = wrapper.find('.factor-range-hint')
    expect(rangeHint.exists()).toBe(true)
    expect(rangeHint.text()).toContain('0')
    expect(rangeHint.text()).toContain('100')

    wrapper.unmount()
  })
})


describe('ScreenerView - reset-default button functionality', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 7.6: 恢复默认按钮 ──────────────────────────────────────────────

  it('reset-default button restores FACTOR_REGISTRY default values', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-reset',
            name: 'Reset Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 50, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-reset',
            name: 'Reset Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 50, params: {} },
              ],
              weights: { ma_trend: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Verify the factor has a non-default threshold (50 instead of 80)
    const thresholdInput = wrapper.find('.factor-threshold')
    expect(thresholdInput.exists()).toBe(true)

    // Find and click the reset-default button (↺)
    const resetBtn = wrapper.find('[aria-label="恢复默认"]')
    expect(resetBtn.exists()).toBe(true)
    await resetBtn.trigger('click')

    // After reset, the threshold should be restored to the FACTOR_REGISTRY default (80)
    const updatedInput = wrapper.find('.factor-threshold')
    expect((updatedInput.element as HTMLInputElement).value).toBe('80')

    wrapper.unmount()
  })

  it('reset-default button restores range factor defaults', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-reset-range',
            name: 'Reset Range Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 10, threshold_high: 90 } },
              ],
              weights: { rsi: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-reset-range',
            name: 'Reset Range Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'rsi', operator: 'BETWEEN', threshold: null, params: { threshold_low: 10, threshold_high: 90 } },
              ],
              weights: { rsi: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Verify range inputs exist with non-default values
    const halfInputs = wrapper.findAll('.factor-threshold-half')
    expect(halfInputs.length).toBe(2)

    // Click reset-default button
    const resetBtn = wrapper.find('[aria-label="恢复默认"]')
    expect(resetBtn.exists()).toBe(true)
    await resetBtn.trigger('click')

    // After reset, range should be restored to default [50, 80]
    const updatedInputs = wrapper.findAll('.factor-threshold-half')
    expect((updatedInputs[0].element as HTMLInputElement).value).toBe('50')
    expect((updatedInputs[1].element as HTMLInputElement).value).toBe('80')

    wrapper.unmount()
  })
})

describe('ScreenerView - sector selector rendering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 8.1, 8.2: 板块面因子显示数据来源和板块类型选择器 ────────────────

  it('renders sector data source and type selectors for sector-category factors', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-sector',
            name: 'Sector Test',
            config: {
              logic: 'AND',
              factors: [
                { type: 'sector', factor_name: 'sector_rank', operator: '<=', threshold: 30, params: {} },
              ],
              weights: { sector_rank: 1.0 },
              sector_config: { sector_data_source: 'DC', sector_period: 5, sector_top_n: 30 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-sector',
            name: 'Sector Test',
            config: {
              logic: 'AND',
              factors: [
                { type: 'sector', factor_name: 'sector_rank', operator: '<=', threshold: 30, params: {} },
              ],
              weights: { sector_rank: 1.0 },
              sector_config: { sector_data_source: 'DC', sector_period: 5, sector_top_n: 30 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Sector selectors should be visible for sector-type factors
    const sectorSelectors = wrapper.find('.sector-selectors')
    expect(sectorSelectors.exists()).toBe(true)

    // Data source selector with 5 options: DC, THS, TDX, TI, CI
    const dataSourceSelect = wrapper.find('[aria-label="数据来源"]')
    expect(dataSourceSelect.exists()).toBe(true)
    const dsOptions = dataSourceSelect.findAll('option')
    expect(dsOptions.length).toBe(5)

    // Sector type selector should be visible for sector source factors.
    const sectorTypeSelect = wrapper.find('[aria-label="板块类型"]')
    expect(sectorTypeSelect.exists()).toBe(true)

    // Period input
    const periodInput = wrapper.find('[aria-label="涨幅周期"]')
    expect(periodInput.exists()).toBe(true)

    wrapper.unmount()
  })
})

describe('ScreenerView - factor data source selector', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  it('renders money-flow source selector and saves selected source', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      if (url === '/screen/strategy-examples') return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-money-flow',
            name: 'Money Flow Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'money_flow', operator: '>=', threshold: 75, params: {} },
              ],
              weights: { money_flow: 1.0 },
              volume_price: { money_flow_source: 'moneyflow_dc' },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-money-flow',
            name: 'Money Flow Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'money_flow', operator: '>=', threshold: 75, params: {} },
              ],
              weights: { money_flow: 1.0 },
              volume_price: { money_flow_source: 'moneyflow_dc' },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })
    mockPut.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    const sourceSelect = wrapper.find('[aria-label="资金流数据源"]')
    expect(sourceSelect.exists()).toBe(true)
    expect(sourceSelect.findAll('option').map((o) => o.element.value)).toEqual([
      'moneyflow_dc',
      'moneyflow_ths',
      'money_flow',
    ])

    await sourceSelect.setValue('moneyflow_ths')
    await wrapper.find('.btn-save').trigger('click')
    await flushPromises()

    expect(mockPut).toHaveBeenCalled()
    const payload = mockPut.mock.calls[0][1] as { config: { volume_price: { money_flow_source: string } } }
    expect(payload.config.volume_price.money_flow_source).toBe('moneyflow_ths')

    wrapper.unmount()
  })

  it('does not render sector source selector for index topic factors', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      if (url === '/screen/strategy-examples') return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-index',
            name: 'Index Factor Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'index_pe', operator: 'BETWEEN', threshold: null, params: { threshold_low: 10, threshold_high: 25 } },
              ],
              weights: { index_pe: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-index',
            name: 'Index Factor Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'index_pe', operator: 'BETWEEN', threshold: null, params: { threshold_low: 10, threshold_high: 25 } },
              ],
              weights: { index_pe: 1.0 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('.sector-selectors').exists()).toBe(false)
    expect(wrapper.find('[aria-label="数据来源"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="板块类型"]').exists()).toBe(false)

    wrapper.unmount()
  })
})

describe('ScreenerView - factor role selector', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('renders role selector for factor rows', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      if (url === '/screen/strategy-examples') return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'role-test',
            name: 'Role Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 75, params: {}, role: 'primary', group_id: 'primary_core' },
              ],
              weights: { ma_trend: 1 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'role-test',
            name: 'Role Test',
            config: {
              logic: 'AND',
              factors: [
                { factor_name: 'ma_trend', operator: '>=', threshold: 75, params: {}, role: 'primary', group_id: 'primary_core' },
              ],
              weights: { ma_trend: 1 },
            },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    const roleSelect = wrapper.find('.factor-role-select')
    expect(roleSelect.exists()).toBe(true)
    expect(roleSelect.text()).toContain('主条件')
    expect(roleSelect.text()).toContain('确认')

    wrapper.unmount()
  })
})

describe('ScreenerView - strategy example loader', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    setupDefaultMocks()
  })

  // ─── Req 14.2: 加载示例策略按钮和对话框 ─────────────────────────────────

  it('shows "加载示例策略" button in factor editor toolbar', async () => {
    // Need factor_editor module enabled to see the button
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-example',
            name: 'Example Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-example',
            name: 'Example Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Find the "加载示例策略" button
    const exampleBtn = wrapper.findAll('.btn.btn-outline.btn-sm').find(
      btn => btn.text().includes('加载示例策略')
    )
    expect(exampleBtn).toBeDefined()

    wrapper.unmount()
  })

  it('opens strategy example dialog when button is clicked', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-dialog',
            name: 'Dialog Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-dialog',
            name: 'Dialog Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Dialog should not be visible initially
    expect(wrapper.find('[aria-label="加载示例策略"]').exists()).toBe(false)

    // Click the "加载示例策略" button
    const exampleBtn = wrapper.findAll('.btn.btn-outline.btn-sm').find(
      btn => btn.text().includes('加载示例策略')
    )
    expect(exampleBtn).toBeDefined()
    await exampleBtn!.trigger('click')

    // Dialog should now be visible
    const dialog = wrapper.find('[aria-label="加载示例策略"]')
    expect(dialog.exists()).toBe(true)

    // Dialog should show strategy examples
    const exampleItems = wrapper.findAll('.example-item')
    expect(exampleItems.length).toBe(2) // Our mock has 2 examples

    // Each example should show name and description
    expect(exampleItems[0].find('.example-name').text()).toBe('强势多头趋势追踪')
    expect(exampleItems[0].find('.example-desc').text()).toContain('捕捉处于强势上升趋势中的个股')

    expect(exampleItems[1].find('.example-name').text()).toBe('概念板块热点龙头')

    wrapper.unmount()
  })

  it('loads strategy example config into editor when example is clicked', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/factor-registry') {
        return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      }
      if (url === '/screen/strategy-examples') {
        return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      }
      if (url === '/strategies') {
        return Promise.resolve({
          data: [{
            id: 'test-load',
            name: 'Load Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          }],
        })
      }
      if (typeof url === 'string' && url.startsWith('/strategies/')) {
        return Promise.resolve({
          data: {
            id: 'test-load',
            name: 'Load Test',
            config: { logic: 'AND', factors: [], weights: {} },
            is_active: true,
            created_at: '2024-01-01',
            enabled_modules: ['factor_editor'],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // Initially no factors
    expect(wrapper.findAll('.factor-row').length).toBe(0)

    // Open the examples dialog
    const exampleBtn = wrapper.findAll('.btn.btn-outline.btn-sm').find(
      btn => btn.text().includes('加载示例策略')
    )
    await exampleBtn!.trigger('click')
    await flushPromises()

    // Click the first example
    const exampleItems = wrapper.findAll('.example-item')
    await exampleItems[0].trigger('click')
    await flushPromises()

    // Dialog should close
    expect(wrapper.find('[aria-label="加载示例策略"]').exists()).toBe(false)

    // Factors should be loaded from the example
    const factorRows = wrapper.findAll('.factor-row')
    expect(factorRows.length).toBe(2) // The first example has 2 factors

    wrapper.unmount()
  })
})

// ─── 板块数据源覆盖率显示测试 ─────────────────────────────────────────────────

const MOCK_COVERAGE_DATA = {
  sources: [
    {
      data_source: 'DC',
      total_sectors: 1030,
      sectors_with_constituents: 1030,
      total_stocks: 5882,
      coverage_ratio: 1.0,
    },
    {
      data_source: 'TI',
      total_sectors: 1724,
      sectors_with_constituents: 90,
      total_stocks: 5755,
      coverage_ratio: 0.0522,
    },
    {
      data_source: 'TDX',
      total_sectors: 615,
      sectors_with_constituents: 615,
      total_stocks: 7122,
      coverage_ratio: 1.0,
    },
  ],
}

/**
 * Helper: set up mocks for a sector-factor strategy with coverage data.
 * Returns a mockGet implementation that serves factor registry, strategy examples,
 * strategies with a sector factor, and sector coverage data.
 */
function setupSectorCoverageMocks(selectedSource = 'DC') {
  mockGet.mockImplementation((url: string) => {
    if (url === '/screen/factor-registry') {
      return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
    }
    if (url === '/screen/strategy-examples') {
      return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
    }
    if (url === '/sector/coverage') {
      return Promise.resolve({ data: MOCK_COVERAGE_DATA })
    }
    if (url === '/strategies') {
      return Promise.resolve({
        data: [{
          id: 'test-coverage',
          name: 'Coverage Test',
          config: {
            logic: 'AND',
            factors: [
              { type: 'sector', factor_name: 'sector_rank', operator: '<=', threshold: 30, params: {} },
            ],
            weights: { sector_rank: 1.0 },
            sector_config: {
              sector_data_source: selectedSource,
              sector_period: 5,
              sector_top_n: 30,
            },
          },
          is_active: true,
          created_at: '2024-01-01',
          enabled_modules: ['factor_editor'],
        }],
      })
    }
    if (typeof url === 'string' && url.startsWith('/strategies/')) {
      return Promise.resolve({
        data: {
          id: 'test-coverage',
          name: 'Coverage Test',
          config: {
            logic: 'AND',
            factors: [
              { type: 'sector', factor_name: 'sector_rank', operator: '<=', threshold: 30, params: {} },
            ],
            weights: { sector_rank: 1.0 },
            sector_config: {
              sector_data_source: selectedSource,
              sector_period: 5,
              sector_top_n: 30,
            },
          },
          is_active: true,
          created_at: '2024-01-01',
          enabled_modules: ['factor_editor'],
        },
      })
    }
    return Promise.resolve({ data: [] })
  })
  mockPost.mockResolvedValue({ data: {} })
}

describe('ScreenerView - 板块数据源覆盖率显示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  // ─── Req 16.1: 数据源下拉选项显示覆盖率摘要 ─────────────────────────────

  it('数据源下拉选项显示板块数和股票数覆盖信息', async () => {
    setupSectorCoverageMocks('DC')

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // 数据来源选择器应存在
    const dataSourceSelect = wrapper.find('[aria-label="数据来源"]')
    expect(dataSourceSelect.exists()).toBe(true)

    // 获取所有选项
    const options = dataSourceSelect.findAll('option')
    expect(options.length).toBe(5)

    // DC 选项应包含板块数和股票数
    const dcOption = options.find(o => o.element.value === 'DC')
    expect(dcOption).toBeDefined()
    expect(dcOption!.text()).toContain('1030')
    expect(dcOption!.text()).toContain('5882')
    expect(dcOption!.text()).toContain('板块')
    expect(dcOption!.text()).toContain('股票')

    // TI 选项应包含总板块、股票数和警告标记
    const tiOption = options.find(o => o.element.value === 'TI')
    expect(tiOption).toBeDefined()
    expect(tiOption!.text()).toContain('1724')
    expect(tiOption!.text()).toContain('5755')
    expect(tiOption!.text()).toContain('⚠️')

    // TDX 选项应包含覆盖率信息，无警告标记
    const tdxOption = options.find(o => o.element.value === 'TDX')
    expect(tdxOption).toBeDefined()
    expect(tdxOption!.text()).toContain('615')
    expect(tdxOption!.text()).toContain('7122')
    expect(tdxOption!.text()).not.toContain('⚠️')

    wrapper.unmount()
  })

  // ─── Req 16.3: 低覆盖率数据源显示警告 ───────────────────────────────────

  it('选择 TI 数据源时显示低覆盖率警告', async () => {
    setupSectorCoverageMocks('TI')

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // TI 的 coverage_ratio = 0.0522 < 0.5，应显示警告
    const warning = wrapper.find('.sector-coverage-warning')
    expect(warning.exists()).toBe(true)
    expect(warning.attributes('role')).toBe('alert')
    expect(warning.text()).toContain('仅 90/1724 个板块有成分股映射')
    expect(warning.text()).toContain('板块涨幅排名和板块趋势因子将无法生效')
    expect(warning.text()).toContain('90')
    expect(warning.text()).toContain('1724')

    wrapper.unmount()
  })

  // ─── Req 16.3: DC 数据源不显示警告 ──────────────────────────────────────

  it('选择 DC 数据源时不显示低覆盖率警告', async () => {
    setupSectorCoverageMocks('DC')

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // DC 的 coverage_ratio = 1.0 >= 0.5，不应显示警告
    const warning = wrapper.find('.sector-coverage-warning')
    expect(warning.exists()).toBe(false)

    wrapper.unmount()
  })

  // ─── Req 16.3: TDX 数据源不显示警告 ─────────────────────────────────────

  it('选择 TDX 数据源时不显示低覆盖率警告', async () => {
    setupSectorCoverageMocks('TDX')

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    // TDX 的 coverage_ratio = 1.0 >= 0.5，不应显示警告
    const warning = wrapper.find('.sector-coverage-warning')
    expect(warning.exists()).toBe(false)

    wrapper.unmount()
  })
})

describe('ScreenerView - 因子筛选统计展示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
  })

  it('页面恢复最近一次选股统计，并在一键执行选股按钮左侧展示通过数和缺失数', async () => {
    const strategy = {
      id: 'strategy-1',
      name: '右侧趋势突破综合策略',
      config: {
        factors: [
          {
            factor_name: 'money_flow',
            operator: '>=',
            threshold: 75,
            params: {},
            role: 'confirmation',
            group_id: 'confirmation',
          },
        ],
        logic: 'AND',
        factor_groups: [
          {
            group_id: 'confirmation',
            label: '确认因子',
            role: 'confirmation',
            logic: 'OR',
            factor_names: ['money_flow'],
            blocking: true,
          },
        ],
        weights: { money_flow: 0.12 },
        volume_price: { money_flow_source: 'moneyflow_dc' },
      },
      is_active: true,
      created_at: '2026-05-02',
      enabled_modules: ['factor_editor', 'volume_price'],
    }
    const factorStats = [
      {
        factor_name: 'money_flow',
        label: '主力资金净流入',
        role: 'confirmation',
        group_id: 'confirmation',
        evaluated_count: 5335,
        passed_count: 1334,
        failed_count: 4000,
        missing_count: 1,
      },
    ]

    mockGet.mockImplementation((url: string) => {
      if (url === '/strategies') return Promise.resolve({ data: [strategy] })
      if (url === '/strategies/strategy-1') return Promise.resolve({ data: strategy })
      if (url === '/screen/factor-registry') return Promise.resolve({ data: MOCK_FACTOR_REGISTRY })
      if (url === '/screen/strategy-examples') return Promise.resolve({ data: MOCK_STRATEGY_EXAMPLES })
      if (url === '/sector/coverage') return Promise.resolve({ data: { sources: [] } })
      if (url === '/sector/types') return Promise.resolve({ data: [] })
      if (url === '/screen/results') {
        return Promise.resolve({
          data: {
            strategy_id: 'strategy-1',
            items: [],
            factor_stats: factorStats,
          },
        })
      }
      if (url === '/screen/schedule') return Promise.resolve({ data: null })
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: {} })

    const wrapper = mountScreenerView()
    await flushPromises()
    await flushPromises()

    const runRow = wrapper.find('.run-row')
    const statsStrip = runRow.find('.factor-stats-strip')
    const runButton = runRow.find('button[aria-label="执行选股"]')

    expect(statsStrip.exists()).toBe(true)
    expect(statsStrip.text()).toContain('主力资金净流入 通过 1334 只，缺失 1 只')
    expect(runButton.exists()).toBe(true)
    expect(
      statsStrip.element.compareDocumentPosition(runButton.element)
        & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    wrapper.unmount()
  })
})
