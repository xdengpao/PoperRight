/**
 * BacktestView 前端组件单元测试
 *
 * 测试自定义平仓条件面板的交互行为：
 * - 条件面板的展开/折叠
 * - 添加/删除条件行
 * - 运算符切换时输入框变化
 *
 * 需求: 6.1, 6.2, 6.3, 6.4, 6.7
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BacktestView from '../BacktestView.vue'

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
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

    // 条件行应包含频率、指标、运算符选择框和阈值输入框
    const fields = rows[0].find('.condition-fields')
    const selects = fields.findAll('select')
    expect(selects.length).toBe(3) // freq, indicator, operator
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
