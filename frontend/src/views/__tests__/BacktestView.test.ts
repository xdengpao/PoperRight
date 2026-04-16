/**
 * BacktestView 前端组件单元测试
 *
 * 测试自定义平仓条件面板的交互行为：
 * - 条件面板的展开/折叠
 * - 添加/删除条件行
 * - 运算符切换时输入框变化
 * - 频率标签显示（分钟级模版 vs 日K线模版）
 * - 模版描述 tooltip 显示
 *
 * 需求: 5.1, 5.3, 6.1, 6.2, 6.3, 6.4, 6.7
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BacktestView from '../BacktestView.vue'

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

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  })),
  graphic: {
    LinearGradient: vi.fn(),
  },
}))

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function mountBacktestView() {
  return mount(BacktestView, {
    global: {
      plugins: [createPinia()],
    },
  })
}

describe('BacktestView - 自定义平仓条件面板', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    // 默认 mock：策略列表和风控配置
    mockGet.mockResolvedValue({ data: [] })
  })

  // ─── 需求 6.1: 面板默认折叠 ──────────────────────────────────────────────

  it('条件面板默认折叠，exit-conditions-content 不可见', () => {
    const wrapper = mountBacktestView()

    expect(wrapper.find('#exit-conditions-content').exists()).toBe(false)
    expect(wrapper.find('.panel-toggle').exists()).toBe(true)
    expect(wrapper.find('.panel-toggle').text()).toContain('自定义平仓条件')
  })

  // ─── 需求 6.1: 点击展开面板 ──────────────────────────────────────────────

  it('点击 toggle 按钮展开面板', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')

    expect(wrapper.find('#exit-conditions-content').exists()).toBe(true)
  })

  // ─── 需求 6.1: 再次点击折叠面板 ──────────────────────────────────────────

  it('再次点击 toggle 按钮折叠面板', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    expect(wrapper.find('#exit-conditions-content').exists()).toBe(true)

    await wrapper.find('.panel-toggle').trigger('click')
    expect(wrapper.find('#exit-conditions-content').exists()).toBe(false)
  })

  // ─── 需求 6.2, 6.3: 添加条件行 ──────────────────────────────────────────

  it('点击"添加条件"按钮新增一行条件', async () => {
    const wrapper = mountBacktestView()

    // 先展开面板
    await wrapper.find('.panel-toggle').trigger('click')

    // 点击添加条件
    const addBtn = wrapper.find('[aria-label="添加平仓条件"]')
    expect(addBtn.exists()).toBe(true)
    await addBtn.trigger('click')

    // 应出现一行条件
    const rows = wrapper.findAll('.condition-row')
    expect(rows.length).toBe(1)

    // 条件行应包含频率、指标、运算符、阈值模式选择框和阈值输入框
    const fields = rows[0].find('.condition-fields')
    const selects = fields.findAll('select')
    expect(selects.length).toBe(4) // freq, indicator, operator, thresholdMode
    const inputs = fields.findAll('input[type="number"]')
    expect(inputs.length).toBe(1) // threshold
  })

  // ─── 需求 6.7: 删除条件行 ────────────────────────────────────────────────

  it('点击删除按钮移除条件行', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')

    // 添加两个条件
    const addBtn = wrapper.find('[aria-label="添加平仓条件"]')
    await addBtn.trigger('click')
    await addBtn.trigger('click')
    expect(wrapper.findAll('.condition-row').length).toBe(2)

    // 删除第一个条件
    const deleteBtn = wrapper.find('[aria-label="删除条件1"]')
    expect(deleteBtn.exists()).toBe(true)
    await deleteBtn.trigger('click')

    expect(wrapper.findAll('.condition-row').length).toBe(1)
  })

  // ─── 需求 6.4: 运算符切换为 cross_up 时显示交叉目标下拉框 ────────────────

  it('运算符切换为 cross_up 时显示 crossTarget 下拉框而非阈值输入框', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 默认运算符为 ">"，应显示阈值输入框
    expect(wrapper.find('[aria-label="条件1阈值"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="条件1交叉目标"]').exists()).toBe(false)

    // 切换运算符为 cross_up
    const operatorSelect = wrapper.find('[aria-label="条件1运算符"]')
    await operatorSelect.setValue('cross_up')

    // 应显示交叉目标下拉框，隐藏阈值输入框
    expect(wrapper.find('[aria-label="条件1交叉目标"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="条件1阈值"]').exists()).toBe(false)
  })

  // ─── 需求 6.4: 运算符从 cross 切回数值运算符时恢复阈值输入框 ─────────────

  it('运算符从 cross_up 切回 ">" 时恢复阈值输入框', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 先切到 cross_up
    const operatorSelect = wrapper.find('[aria-label="条件1运算符"]')
    await operatorSelect.setValue('cross_up')
    expect(wrapper.find('[aria-label="条件1交叉目标"]').exists()).toBe(true)

    // 切回 ">"
    await operatorSelect.setValue('>')

    // 应恢复阈值输入框
    expect(wrapper.find('[aria-label="条件1阈值"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="条件1交叉目标"]').exists()).toBe(false)
  })
})

// ─── 需求 5.1, 5.3: 频率标签与 tooltip 显示 ──────────────────────────────────

describe('BacktestView - 模版频率标签与 tooltip 显示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    mockGet.mockResolvedValue({ data: [] })
  })

  /** 构造一个系统模版对象 */
  function makeSystemTemplate(overrides: Partial<{
    id: string
    name: string
    description: string | null
    freq: string
    is_system: boolean
  }> = {}) {
    return {
      id: overrides.id ?? 'tpl-1',
      name: overrides.name ?? '5分钟RSI超买平仓',
      description: overrides.description ?? '5分钟RSI超过80时触发',
      exit_conditions: {
        conditions: [
          {
            freq: overrides.freq ?? '5min',
            indicator: 'rsi',
            operator: '>',
            threshold: 80,
            cross_target: null,
            params: {},
          },
        ],
        logic: 'AND' as const,
      },
      is_system: overrides.is_system ?? true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    }
  }

  // ─── 需求 5.1: 分钟级系统模版显示频率标签 ────────────────────────────────

  it('分钟级系统模版选项显示 [系统·5分钟] 频率标签', async () => {
    const minuteTemplate = makeSystemTemplate({
      id: 'tpl-5min',
      name: '5分钟RSI超买平仓',
      freq: '5min',
    })

    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: [minuteTemplate] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountBacktestView()
    await wrapper.find('.panel-toggle').trigger('click')
    await flushPromises()

    const systemOptions = wrapper.findAll('.system-template-option')
    expect(systemOptions.length).toBe(1)
    expect(systemOptions[0].text()).toContain('[系统·5分钟]')
    expect(systemOptions[0].text()).toContain('5分钟RSI超买平仓')
  })

  // ─── 需求 5.1: 日K线系统模版显示 [系统] 无频率标签 ────────────────────────

  it('日K线系统模版选项显示 [系统] 无频率标签', async () => {
    const dailyTemplate = makeSystemTemplate({
      id: 'tpl-daily',
      name: 'RSI超买平仓',
      freq: 'daily',
    })

    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: [dailyTemplate] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountBacktestView()
    await wrapper.find('.panel-toggle').trigger('click')
    await flushPromises()

    const systemOptions = wrapper.findAll('.system-template-option')
    expect(systemOptions.length).toBe(1)
    expect(systemOptions[0].text()).toContain('[系统]')
    expect(systemOptions[0].text()).not.toContain('·')
    expect(systemOptions[0].text()).toContain('RSI超买平仓')
  })

  // ─── 需求 5.3: 模版描述作为 tooltip 显示 ─────────────────────────────────

  it('系统模版选项的 title 属性显示模版描述', async () => {
    const template = makeSystemTemplate({
      id: 'tpl-tooltip',
      name: '15分钟MACD死叉平仓',
      description: '15分钟MACD快线下穿慢线，中短线趋势转弱',
      freq: '15min',
    })

    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: [template] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountBacktestView()
    await wrapper.find('.panel-toggle').trigger('click')
    await flushPromises()

    const systemOptions = wrapper.findAll('.system-template-option')
    expect(systemOptions.length).toBe(1)
    expect(systemOptions[0].attributes('title')).toBe('15分钟MACD快线下穿慢线，中短线趋势转弱')
  })
})


// ─── 需求 6.1~6.8: 相对值阈值 UI 配置面板 ─────────────────────────────────────

describe('BacktestView - 相对值阈值 UI 配置', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    mockGet.mockResolvedValue({ data: [] })
  })

  // ─── 需求 6.1: 数值比较运算符显示阈值模式切换控件 ────────────────────────

  it('数值比较运算符时显示阈值模式切换控件', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 默认运算符为 ">"（数值比较），应显示阈值模式选择框
    const modeSelect = wrapper.find('[aria-label="条件1阈值模式"]')
    expect(modeSelect.exists()).toBe(true)

    // 应有 "绝对值" 和 "相对值" 两个选项
    const options = modeSelect.findAll('option')
    expect(options.length).toBe(2)
    expect(options[0].text()).toBe('绝对值')
    expect(options[1].text()).toBe('相对值')
  })

  // ─── 需求 6.8: 交叉运算符隐藏阈值模式切换控件 ────────────────────────────

  it('交叉运算符时隐藏阈值模式切换控件', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 切换到 cross_up
    const operatorSelect = wrapper.find('[aria-label="条件1运算符"]')
    await operatorSelect.setValue('cross_up')

    // 阈值模式选择框应不存在
    expect(wrapper.find('[aria-label="条件1阈值模式"]').exists()).toBe(false)
  })

  // ─── 需求 6.3: 切换到相对值模式显示基准字段下拉框和乘数因子输入框 ────────

  it('切换到相对值模式时显示基准字段下拉框和乘数因子输入框', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 默认为绝对值模式，应显示阈值输入框
    expect(wrapper.find('[aria-label="条件1阈值"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="条件1基准字段"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="条件1乘数因子"]').exists()).toBe(false)

    // 切换到相对值模式
    const modeSelect = wrapper.find('[aria-label="条件1阈值模式"]')
    await modeSelect.setValue('relative')

    // 应隐藏阈值输入框，显示基准字段下拉框和乘数因子输入框
    expect(wrapper.find('[aria-label="条件1阈值"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="条件1基准字段"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="条件1乘数因子"]').exists()).toBe(true)
  })

  // ─── 需求 6.5: 选择 ma_volume 时显示均量周期输入框 ────────────────────────

  it('选择 ma_volume 基准字段时显示均量周期输入框', async () => {
    const wrapper = mountBacktestView()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    // 切换到相对值模式
    const modeSelect = wrapper.find('[aria-label="条件1阈值模式"]')
    await modeSelect.setValue('relative')

    // 默认不显示均量周期输入框
    expect(wrapper.find('#ma-vol-period-0').exists()).toBe(false)

    // 选择 ma_volume 基准字段
    const baseFieldSelect = wrapper.find('[aria-label="条件1基准字段"]')
    await baseFieldSelect.setValue('ma_volume')

    // 应显示均量周期输入框
    expect(wrapper.find('#ma-vol-period-0').exists()).toBe(true)
  })

  // ─── 需求 6.7: 模式切换清空对立字段 ──────────────────────────────────────

  it('模式切换时清空对立字段', async () => {
    const wrapper = mountBacktestView()
    const { useBacktestStore } = await import('@/stores/backtest')
    const store = useBacktestStore()

    await wrapper.find('.panel-toggle').trigger('click')
    await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')

    const cond = store.form.exitConditions.conditions[0]

    // 设置绝对值模式的阈值
    cond.threshold = 42

    // 切换到相对值模式
    const modeSelect = wrapper.find('[aria-label="条件1阈值模式"]')
    await modeSelect.setValue('relative')

    // threshold 应被清空
    expect(cond.threshold).toBeNull()

    // 设置相对值模式的字段
    cond.baseField = 'entry_price'
    cond.factor = 0.95

    // 切换回绝对值模式
    await modeSelect.setValue('absolute')

    // baseField 和 factor 应被清空
    expect(cond.baseField).toBeNull()
    expect(cond.factor).toBeNull()
  })
})
