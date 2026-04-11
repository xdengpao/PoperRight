/**
 * BacktestView 前端模版管理单元测试
 *
 * 测试平仓条件模版管理相关的 UI 交互：
 * - "保存为模版"按钮状态（有条件时启用，无条件时禁用）
 * - 保存对话框弹出与提交
 * - 模版选择下拉框加载与选择
 * - 模版加载后替换当前配置
 * - 模版删除确认对话框
 *
 * 需求: 10.1, 10.2, 10.6, 10.7, 10.9, 10.10
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Pinia } from 'pinia'
import BacktestView from '../BacktestView.vue'
import { useBacktestStore } from '@/stores/backtest'
import type { ExitTemplate } from '@/stores/backtest'

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

// ─── 模版 mock 数据 ──────────────────────────────────────────────────────────

const MOCK_TEMPLATES: ExitTemplate[] = [
  {
    id: 'tpl-001',
    name: '高RSI止盈',
    description: 'RSI超过80时平仓',
    exit_conditions: {
      conditions: [
        { freq: 'daily', indicator: 'rsi', operator: '>', threshold: 80, cross_target: null, params: {} },
      ],
      logic: 'AND',
    },
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-02T00:00:00',
  },
  {
    id: 'tpl-002',
    name: 'MACD死叉',
    description: null,
    exit_conditions: {
      conditions: [
        { freq: 'daily', indicator: 'macd_dif', operator: 'cross_down', threshold: null, cross_target: 'macd_dea', params: {} },
      ],
      logic: 'AND',
    },
    created_at: '2024-01-03T00:00:00',
    updated_at: '2024-01-04T00:00:00',
  },
]

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

let pinia: Pinia

/**
 * 预填充 store 中的模版列表后再挂载组件。
 * 组件中 `const { exitTemplates } = store` 解构会在挂载时捕获 ref，
 * 因此需要在挂载前设置好数据，确保初始渲染就包含模版选项。
 */
function mountWithTemplates() {
  const store = useBacktestStore()
  store.exitTemplates = [...MOCK_TEMPLATES]
  return mount(BacktestView, {
    global: { plugins: [pinia] },
  })
}

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

describe('BacktestView - 模版管理', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    mockGet.mockReset()
    mockPost.mockReset()
    mockPut.mockReset()
    mockDelete.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: MOCK_TEMPLATES })
      }
      return Promise.resolve({ data: [] })
    })
  })

  // ─── 需求 10.10: 无条件时禁用"保存为模版"按钮 ──────────────────────────

  it('无平仓条件时"保存为模版"按钮禁用', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)

    const saveBtn = wrapper.find('[aria-label="保存为模版"]')
    expect(saveBtn.exists()).toBe(true)
    expect((saveBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  // ─── 需求 10.1, 10.10: 有条件时启用"保存为模版"按钮 ─────────────────────

  it('有平仓条件时"保存为模版"按钮启用', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    const saveBtn = wrapper.find('[aria-label="保存为模版"]')
    expect((saveBtn.element as HTMLButtonElement).disabled).toBe(false)
  })

  // ─── 需求 10.2: 点击"保存为模版"弹出对话框 ────────────────────────────────

  it('点击"保存为模版"弹出保存对话框', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    await wrapper.find('[aria-label="保存为模版"]').trigger('click')

    const dialog = wrapper.find('[role="dialog"][aria-label="保存为模版"]')
    expect(dialog.exists()).toBe(true)
    expect(wrapper.find('#tpl-name').exists()).toBe(true)
    expect(wrapper.find('#tpl-desc').exists()).toBe(true)
  })

  // ─── 需求 10.2: 保存对话框提交 ───────────────────────────────────────────

  it('填写名称后确认保存调用 createExitTemplate', async () => {
    mockPost.mockResolvedValue({
      data: { id: 'new-tpl', name: '测试模版', exit_conditions: {}, created_at: '', updated_at: '' },
    })

    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    await wrapper.find('[aria-label="保存为模版"]').trigger('click')
    await wrapper.find('#tpl-name').setValue('测试模版')

    const confirmBtn = wrapper.findAll('.dialog-actions .btn-primary').find(
      (b) => b.text().includes('确认保存')
    )
    expect(confirmBtn).toBeDefined()
    expect((confirmBtn!.element as HTMLButtonElement).disabled).toBe(false)

    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith(
      '/backtest/exit-templates',
      expect.objectContaining({ name: '测试模版' }),
    )
  })

  // ─── 需求 10.2: 名称为空时确认保存按钮禁用 ────────────────────────────────

  it('名称为空时确认保存按钮禁用', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)
    await addCondition(wrapper)

    await wrapper.find('[aria-label="保存为模版"]').trigger('click')

    const confirmBtn = wrapper.findAll('.dialog-actions .btn-primary').find(
      (b) => b.text().includes('确认保存')
    )
    expect(confirmBtn).toBeDefined()
    expect((confirmBtn!.element as HTMLButtonElement).disabled).toBe(true)
  })

  // ─── 需求 10.6: 模版选择下拉框加载模版列表 ────────────────────────────────

  it('展开面板后模版下拉框显示模版列表', async () => {
    // 预填充模版数据后挂载，确保初始渲染包含模版选项
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    const templateSelect = wrapper.find('#exit-template')
    expect(templateSelect.exists()).toBe(true)

    const options = templateSelect.findAll('option')
    expect(options.length).toBe(3) // "无" + 2 templates
    expect(options[1].text()).toBe('高RSI止盈')
    expect(options[2].text()).toBe('MACD死叉')
  })

  // ─── 需求 10.6: 展开面板触发 fetchExitTemplates ───────────────────────────

  it('展开面板时调用 fetchExitTemplates 加载模版', async () => {
    const wrapper = mountBacktestView()
    await openExitPanel(wrapper)

    expect(mockGet).toHaveBeenCalledWith('/backtest/exit-templates')
  })

  // ─── 需求 10.7: 选择模版后加载配置 ────────────────────────────────────────

  it('选择模版后调用 loadExitTemplate', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: MOCK_TEMPLATES })
      }
      if (url === '/backtest/exit-templates/tpl-001') {
        return Promise.resolve({ data: MOCK_TEMPLATES[0] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountWithTemplates()
    const store = useBacktestStore()
    await openExitPanel(wrapper)

    await store.loadExitTemplate('tpl-001')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/backtest/exit-templates/tpl-001')
  })

  // ─── 需求 10.7: 模版加载后替换当前条件配置 ────────────────────────────────

  it('模版加载后当前条件配置被替换', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: MOCK_TEMPLATES })
      }
      if (url === '/backtest/exit-templates/tpl-001') {
        return Promise.resolve({ data: MOCK_TEMPLATES[0] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountBacktestView()
    const store = useBacktestStore()
    await openExitPanel(wrapper)

    await addCondition(wrapper)
    expect(store.form.exitConditions.conditions.length).toBe(1)

    await store.loadExitTemplate('tpl-001')
    await flushPromises()

    expect(store.form.exitConditions.conditions.length).toBe(1)
    expect(store.form.exitConditions.conditions[0].indicator).toBe('rsi')
    expect(store.form.exitConditions.conditions[0].operator).toBe('>')
    expect(store.form.exitConditions.conditions[0].threshold).toBe(80)
  })

  // ─── 需求 10.9: 删除模版确认对话框 ────────────────────────────────────────

  it('点击删除模版按钮弹出确认对话框', async () => {
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    const manageBtn = wrapper.find('[aria-label="管理模版"]')
    expect(manageBtn.exists()).toBe(true)
    await manageBtn.trigger('click')

    expect(wrapper.find('.manage-panel').exists()).toBe(true)

    const deleteBtns = wrapper.findAll('[aria-label="删除模版"]')
    expect(deleteBtns.length).toBeGreaterThan(0)
    await deleteBtns[0].trigger('click')

    const deleteDialog = wrapper.find('[role="dialog"][aria-label="确认删除模版"]')
    expect(deleteDialog.exists()).toBe(true)
    expect(deleteDialog.text()).toContain('高RSI止盈')
  })

  // ─── 需求 10.9: 确认删除调用 deleteExitTemplate ───────────────────────────

  it('确认删除后调用 DELETE API', async () => {
    mockDelete.mockResolvedValue({ data: { id: 'tpl-001', deleted: true } })

    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    await wrapper.find('[aria-label="管理模版"]').trigger('click')
    const deleteBtns = wrapper.findAll('[aria-label="删除模版"]')
    expect(deleteBtns.length).toBeGreaterThan(0)
    await deleteBtns[0].trigger('click')

    const confirmDeleteBtn = wrapper.findAll('.dialog-actions .btn-danger').find(
      (b) => b.text().includes('确认删除')
    )
    expect(confirmDeleteBtn).toBeDefined()
    await confirmDeleteBtn!.trigger('click')
    await flushPromises()

    expect(mockDelete).toHaveBeenCalledWith('/backtest/exit-templates/tpl-001')
  })

  // ─── 需求 10.9: 取消删除关闭对话框 ────────────────────────────────────────

  it('取消删除关闭确认对话框', async () => {
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    await wrapper.find('[aria-label="管理模版"]').trigger('click')
    const deleteBtns = wrapper.findAll('[aria-label="删除模版"]')
    expect(deleteBtns.length).toBeGreaterThan(0)
    await deleteBtns[0].trigger('click')

    expect(wrapper.find('[role="dialog"][aria-label="确认删除模版"]').exists()).toBe(true)

    const cancelBtn = wrapper.findAll('.dialog-actions .btn-outline').find(
      (b) => b.text().includes('取消')
    )
    await cancelBtn!.trigger('click')

    expect(wrapper.find('[role="dialog"][aria-label="确认删除模版"]').exists()).toBe(false)
  })
})
