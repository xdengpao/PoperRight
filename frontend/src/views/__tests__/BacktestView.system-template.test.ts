/**
 * BacktestView 前端系统模版视觉区分单元测试
 *
 * 测试系统内置模版与用户自定义模版的视觉区分：
 * - 模版下拉框中系统模版带 `[系统]` 标签
 * - 系统模版排在用户模版之前
 * - 系统模版不显示重命名和删除操作
 * - 选择系统模版后可加载到配置面板
 *
 * 需求: 12.3, 12.4, 12.5
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

// ─── 模版 mock 数据（系统 + 用户） ──────────────────────────────────────────

const MOCK_TEMPLATES: ExitTemplate[] = [
  {
    id: 'sys-1',
    name: 'RSI 超买平仓',
    is_system: true,
    description: null,
    exit_conditions: {
      conditions: [
        { freq: 'daily', indicator: 'rsi', operator: '>', threshold: 80, cross_target: null, params: {} },
      ],
      logic: 'AND',
    },
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
  {
    id: 'sys-2',
    name: 'MACD 死叉平仓',
    is_system: true,
    description: null,
    exit_conditions: {
      conditions: [
        { freq: 'daily', indicator: 'macd_dif', operator: 'cross_down', threshold: null, cross_target: 'macd_dea', params: {} },
      ],
      logic: 'AND',
    },
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  },
  {
    id: 'user-1',
    name: '我的模版',
    is_system: false,
    description: null,
    exit_conditions: {
      conditions: [
        { freq: 'daily', indicator: 'close', operator: '>', threshold: 100, cross_target: null, params: {} },
      ],
      logic: 'AND',
    },
    created_at: '2024-01-02',
    updated_at: '2024-01-02',
  },
]

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

let pinia: Pinia

function mountWithTemplates() {
  const store = useBacktestStore()
  store.exitTemplates = [...MOCK_TEMPLATES]
  return mount(BacktestView, {
    global: { plugins: [pinia] },
  })
}

async function openExitPanel(wrapper: ReturnType<typeof mount>) {
  await wrapper.find('.panel-toggle').trigger('click')
  await flushPromises()
}

describe('BacktestView - 系统模版视觉区分', () => {
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

  // ─── 需求 12.4: 模版下拉框中系统模版带 [系统] 标签 ────────────────────────

  it('模版下拉框中系统模版选项带 [系统] 前缀标签', async () => {
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    const systemOptions = wrapper.findAll('.system-template-option')
    expect(systemOptions.length).toBe(2)
    expect(systemOptions[0].text()).toContain('[系统]')
    expect(systemOptions[0].text()).toContain('RSI 超买平仓')
    expect(systemOptions[1].text()).toContain('[系统]')
    expect(systemOptions[1].text()).toContain('MACD 死叉平仓')
  })

  // ─── 需求 12.3: 系统模版排在用户模版之前 ──────────────────────────────────

  it('系统模版在下拉框中排在用户模版之前', async () => {
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    const templateSelect = wrapper.find('#exit-template')
    const allOptions = templateSelect.findAll('option')

    // 收集系统模版选项和用户模版选项（排除"无"和分隔线）
    const systemOptions = allOptions.filter((o) => o.classes().includes('system-template-option'))
    const userOptions = allOptions.filter(
      (o) => o.attributes('value') && o.attributes('value') !== '' && !o.classes().includes('system-template-option') && !o.classes().includes('template-separator')
    )

    expect(systemOptions.length).toBe(2)
    expect(userOptions.length).toBe(1)

    // 系统模版的索引应小于用户模版的索引
    const firstSystemIdx = allOptions.indexOf(systemOptions[0])
    const lastSystemIdx = allOptions.indexOf(systemOptions[systemOptions.length - 1])
    const firstUserIdx = allOptions.indexOf(userOptions[0])
    expect(lastSystemIdx).toBeLessThan(firstUserIdx)

    // 验证内容
    expect(systemOptions[0].text()).toContain('[系统]')
    expect(systemOptions[1].text()).toContain('[系统]')
    expect(userOptions[0].text()).toBe('我的模版')
  })

  // ─── 需求 12.5: 系统模版不显示重命名和删除操作 ────────────────────────────

  it('管理面板中系统模版不显示重命名和删除按钮', async () => {
    const wrapper = mountWithTemplates()
    await openExitPanel(wrapper)

    // 打开管理面板
    await wrapper.find('[aria-label="管理模版"]').trigger('click')
    expect(wrapper.find('.manage-panel').exists()).toBe(true)

    const manageItems = wrapper.findAll('.manage-item')
    expect(manageItems.length).toBe(3) // 2 system + 1 user

    // 系统模版应显示 [系统] 标签
    const systemTags = wrapper.findAll('.system-tag')
    expect(systemTags.length).toBe(2)
    expect(systemTags[0].text()).toBe('[系统]')

    // 系统模版不应有操作按钮（重命名/删除）
    // 前两个 manage-item 是系统模版，不应有 .manage-item-actions
    const firstItem = manageItems[0]
    const secondItem = manageItems[1]
    expect(firstItem.find('.manage-item-actions').exists()).toBe(false)
    expect(secondItem.find('.manage-item-actions').exists()).toBe(false)

    // 用户模版应有操作按钮
    const userItem = manageItems[2]
    expect(userItem.find('.manage-item-actions').exists()).toBe(true)
    expect(userItem.find('[aria-label="重命名模版"]').exists()).toBe(true)
    expect(userItem.find('[aria-label="删除模版"]').exists()).toBe(true)
  })

  // ─── 需求 12.5: 选择系统模版后可加载到配置面板 ────────────────────────────

  it('选择系统模版后加载其平仓条件到配置面板', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/backtest/exit-templates') {
        return Promise.resolve({ data: MOCK_TEMPLATES })
      }
      if (url === '/backtest/exit-templates/sys-1') {
        return Promise.resolve({ data: MOCK_TEMPLATES[0] })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountWithTemplates()
    const store = useBacktestStore()
    await openExitPanel(wrapper)

    // 加载系统模版
    await store.loadExitTemplate('sys-1')
    await flushPromises()

    // 验证 API 调用
    expect(mockGet).toHaveBeenCalledWith('/backtest/exit-templates/sys-1')

    // 验证条件已加载到 store
    expect(store.form.exitConditions.conditions.length).toBe(1)
    expect(store.form.exitConditions.conditions[0].indicator).toBe('rsi')
    expect(store.form.exitConditions.conditions[0].operator).toBe('>')
    expect(store.form.exitConditions.conditions[0].threshold).toBe(80)
    expect(store.selectedTemplateId).toBe('sys-1')
  })
})
