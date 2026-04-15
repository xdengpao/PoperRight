/**
 * BacktestView 前端指标使用说明单元测试
 *
 * 测试自定义平仓条件面板中指标使用说明卡片的展示行为：
 * - 选择指标后展示使用说明卡片
 * - 使用说明包含中文名称、计算逻辑、参数说明、典型场景
 * - 切换指标时说明卡片内容更新
 * - 无参数指标不显示参数区域
 *
 * 需求: 11.1, 11.2, 11.3, 11.4, 11.5
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Pinia } from 'pinia'
import BacktestView from '../BacktestView.vue'
import { useBacktestStore, INDICATOR_DESCRIPTIONS } from '@/stores/backtest'

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: vi.fn(),
    delete: vi.fn(),
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

let pinia: Pinia

function mountBacktestView() {
  return mount(BacktestView, {
    global: { plugins: [pinia] },
  })
}

/** 展开平仓条件面板 */
async function openExitPanel(wrapper: ReturnType<typeof mount>) {
  await wrapper.find('.panel-toggle').trigger('click')
  await flushPromises()
}

/** 添加一个条件行 */
async function addCondition(wrapper: ReturnType<typeof mount>) {
  await wrapper.find('[aria-label="添加平仓条件"]').trigger('click')
}

describe('BacktestView - 指标使用说明卡片', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    mockGet.mockReset()
    mockPost.mockReset()
    mockGet.mockResolvedValue({ data: [] })
  })

  // ─── 需求 11.2: 选择指标后展示使用说明卡片 ────────────────────────────────

  it('添加条件后展示对应指标的使用说明卡片', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 默认指标为 rsi，应展示说明卡片
    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)
  })

  // ─── 需求 11.1, 11.3, 11.4, 11.5: 使用说明包含中文名称、计算逻辑、参数说明、典型场景 ──

  it('RSI 指标说明卡片包含中文名称、计算逻辑、参数说明、典型场景', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 默认指标为 rsi
    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)

    // 中文名称
    const nameEl = descCard.find('.indicator-desc-name')
    expect(nameEl.exists()).toBe(true)
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.rsi.chineseName)

    // 计算逻辑
    const calcEl = descCard.find('.indicator-desc-calc')
    expect(calcEl.exists()).toBe(true)
    expect(calcEl.text()).toBe(INDICATOR_DESCRIPTIONS.rsi.calculationSummary)

    // 参数说明（RSI 有参数）
    const paramsEl = descCard.find('.indicator-desc-params')
    expect(paramsEl.exists()).toBe(true)
    expect(paramsEl.text()).toContain('RSI周期')

    // 典型场景
    const usageEl = descCard.find('.indicator-desc-usage')
    expect(usageEl.exists()).toBe(true)
    expect(usageEl.text()).toContain(INDICATOR_DESCRIPTIONS.rsi.typicalUsage)
  })

  // ─── 需求 11.2: 切换指标时说明卡片内容更新 ────────────────────────────────

  it('切换指标时说明卡片内容更新为新指标的说明', async () => {
    const wrapper = mountBacktestView()
    const store = useBacktestStore()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 默认指标为 rsi，验证初始状态
    let nameEl = wrapper.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.rsi.chineseName)

    // 切换指标为 ma
    const indicatorSelect = wrapper.find('[aria-label="条件1指标"]')
    await indicatorSelect.setValue('ma')

    // 说明卡片应更新为 MA 的说明
    nameEl = wrapper.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.ma.chineseName)

    const calcEl = wrapper.find('.indicator-desc-calc')
    expect(calcEl.text()).toBe(INDICATOR_DESCRIPTIONS.ma.calculationSummary)

    const usageEl = wrapper.find('.indicator-desc-usage')
    expect(usageEl.text()).toContain(INDICATOR_DESCRIPTIONS.ma.typicalUsage)
  })

  // ─── 需求 11.4: 无参数指标不显示参数区域 ──────────────────────────────────

  it('无参数指标（close）不显示参数区域', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 切换指标为 close（无参数指标）
    const indicatorSelect = wrapper.find('[aria-label="条件1指标"]')
    await indicatorSelect.setValue('close')

    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)

    // 中文名称应为收盘价
    const nameEl = descCard.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.close.chineseName)

    // 参数区域不应显示
    const paramsEl = descCard.find('.indicator-desc-params')
    expect(paramsEl.exists()).toBe(false)
  })

  // ─── 需求 11.4: 无参数指标 volume 不显示参数区域 ──────────────────────────

  it('无参数指标（volume）不显示参数区域', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 切换指标为 volume
    const indicatorSelect = wrapper.find('[aria-label="条件1指标"]')
    await indicatorSelect.setValue('volume')

    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)

    const nameEl = descCard.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.volume.chineseName)

    const paramsEl = descCard.find('.indicator-desc-params')
    expect(paramsEl.exists()).toBe(false)
  })

  // ─── 需求 11.4: 有参数指标 MACD 显示参数区域 ─────────────────────────────

  it('有参数指标（macd_dif）显示参数区域，包含多个参数说明', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 切换指标为 macd_dif
    const indicatorSelect = wrapper.find('[aria-label="条件1指标"]')
    await indicatorSelect.setValue('macd_dif')

    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)

    // 中文名称
    const nameEl = descCard.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.macd_dif.chineseName)

    // 参数区域应显示
    const paramsEl = descCard.find('.indicator-desc-params')
    expect(paramsEl.exists()).toBe(true)

    // MACD 有 3 个参数
    const paramItems = paramsEl.findAll('.indicator-desc-param')
    expect(paramItems.length).toBe(3)
    expect(paramsEl.text()).toContain('快线周期')
    expect(paramsEl.text()).toContain('慢线周期')
    expect(paramsEl.text()).toContain('信号线周期')
  })

  // ─── 需求 11.2: 切换到另一个无参数指标 turnover ───────────────────────────

  it('从有参数指标切换到无参数指标 turnover 时参数区域消失', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    // 默认 rsi 有参数
    expect(wrapper.find('.indicator-desc-params').exists()).toBe(true)

    // 切换到 turnover（无参数）
    const indicatorSelect = wrapper.find('[aria-label="条件1指标"]')
    await indicatorSelect.setValue('turnover')

    const descCard = wrapper.find('.indicator-desc-card')
    expect(descCard.exists()).toBe(true)

    const nameEl = descCard.find('.indicator-desc-name')
    expect(nameEl.text()).toBe(INDICATOR_DESCRIPTIONS.turnover.chineseName)

    expect(wrapper.find('.indicator-desc-params').exists()).toBe(false)
  })
})
