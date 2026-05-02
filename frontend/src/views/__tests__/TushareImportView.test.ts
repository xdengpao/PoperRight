/**
 * TushareImportView 前端单元测试
 *
 * 覆盖组件渲染、连接状态检查、接口列表展示、参数表单交互、
 * 导入启动/停止、进度更新、历史记录显示。
 *
 * 需求: 2.1-2.7, 20.3, 21.1, 22.1-22.4, 23.1-23.4, 24.1-24.2
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TushareImportView from '../TushareImportView.vue'

// ── Mock apiClient ────────────────────────────────────────────────────────────

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ name: 'DataOnlineTushare' }),
  useRouter: () => ({ push: vi.fn() }),
}))

// ── 测试数据 ──────────────────────────────────────────────────────────────────

const healthConnected = {
  connected: true,
  tokens: {
    basic: { configured: true },
    advanced: { configured: true },
    premium: { configured: false },
    special: { configured: false },
  },
}

const healthDisconnected = {
  connected: false,
  tokens: {
    basic: { configured: false },
    advanced: { configured: false },
    premium: { configured: false },
    special: { configured: false },
  },
}

const sampleRegistry = [
  {
    api_name: 'stock_basic',
    label: '股票基础列表',
    category: 'stock_data',
    subcategory: '基础数据',
    token_tier: 'basic',
    required_params: [],
    optional_params: [],
    token_available: true,
  },
  {
    api_name: 'daily',
    label: '日线行情',
    category: 'stock_data',
    subcategory: '行情数据（低频：日K/周K/月K）',
    token_tier: 'basic',
    required_params: ['date_range'],
    optional_params: ['stock_code'],
    token_available: true,
  },
  {
    api_name: 'index_daily',
    label: '指数日线行情',
    category: 'index_data',
    subcategory: '指数行情数据（低频：日线/周线/月线）',
    token_tier: 'basic',
    required_params: ['date_range'],
    optional_params: ['index_code'],
    token_available: true,
  },
  {
    api_name: 'index_tech',
    label: '指数技术面因子',
    category: 'index_data',
    subcategory: '指数技术面因子',
    token_tier: 'special',
    required_params: ['date_range'],
    optional_params: ['index_code'],
    token_available: false,
  },
]

const sampleHistory = [
  {
    id: 1,
    api_name: 'stock_basic',
    status: 'completed',
    record_count: 5200,
    error_message: null,
    started_at: '2024-06-15T10:30:00',
    finished_at: '2024-06-15T10:30:03',
  },
  {
    id: 2,
    api_name: 'daily',
    status: 'failed',
    record_count: 0,
    error_message: 'Token 无效',
    started_at: '2024-06-15T10:25:00',
    finished_at: '2024-06-15T10:25:01',
  },
]

const sampleWorkflowDefinition = {
  workflow_key: 'smart-screening',
  label: '智能选股数据一键导入',
  mode: 'daily_fast',
  stages: [
    {
      key: 'foundation',
      label: '基础数据',
      description: '股票基础信息和交易日历',
      steps: [
        {
          api_name: 'stock_basic',
          label: '股票基础列表',
          factor_groups: [],
          required_token_tier: 'basic',
          optional: false,
        },
      ],
    },
  ],
  required_token_tiers: ['basic'],
}

const sampleWorkflowPlan = {
  mode: 'daily_fast',
  target_trade_date: '20260430',
  execute_steps: [
    {
      api_name: 'daily',
      label: '日线行情',
      params: { start_date: '20260430', end_date: '20260430' },
      reason: '每日选股核心依赖',
      priority: 1,
      estimated_duration: '快：按目标交易日',
    },
  ],
  skip_steps: [
    { api_name: 'stock_basic', reason: '静态基础表不在每日快速默认链路中', skip_reason: '静态基础表不在每日快速默认链路中' },
  ],
  maintenance_suggestions: [
    { api_name: 'dc_member', reason: '板块成分超过 TTL 时执行周维护' },
  ],
  estimated_cost: { step_count: 1, slow_step_count: 0, label: '预计较快' },
  next_actions: [],
}

const runningWorkflowStatus = {
  workflow_task_id: 'workflow-1',
  workflow_key: 'smart-screening',
  status: 'running',
  mode: 'daily_fast',
  date_range: { start_date: '20260410', end_date: '20260430' },
  options: {
    include_moneyflow_ths: true,
    include_ths_sector: true,
    include_tdx_sector: true,
    include_ti_sector: true,
    include_ci_sector: true,
  },
  current_stage_key: 'kline',
  current_stage_label: '股票日线主行情和复权',
  current_api_name: 'daily',
  completed_steps: 2,
  failed_steps: 0,
  total_steps: 32,
  child_tasks: [],
  readiness: null,
  error_message: null,
  skip_steps: [
    { api_name: 'stock_basic', skip_reason: '静态基础表不在每日快速默认链路中' },
  ],
  maintenance_suggestions: [
    { api_name: 'dc_member', reason: '板块成分超过 TTL 时执行周维护' },
  ],
  next_actions: [
    { mode: 'gap_repair', label: '补齐缺口', enabled: true },
  ],
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

function setupMocks(
  health = healthConnected,
  registry = sampleRegistry,
  history = sampleHistory,
) {
  mockGet.mockImplementation((url: string) => {
    if (url === '/data/tushare/health') {
      return Promise.resolve({ data: health })
    }
    if (url === '/data/tushare/registry') {
      return Promise.resolve({ data: registry })
    }
    if (url.startsWith('/data/tushare/import/history')) {
      return Promise.resolve({ data: history })
    }
    if (url === '/data/tushare/import/last-times') {
      return Promise.resolve({ data: {} })
    }
    if (url === '/data/tushare/import/running') {
      return Promise.resolve({ data: [] })
    }
    if (url.startsWith('/data/tushare/import/status/')) {
      return Promise.resolve({
        data: {
          task_id: 'task-1',
          api_name: 'daily',
          status: 'running',
          total: 100,
          completed: 50,
          failed: 2,
          current_item: '600000',
        },
      })
    }
    if (url === '/data/tushare/workflows/running') {
      return Promise.resolve({ data: null })
    }
    if (url.startsWith('/data/tushare/workflows/status/')) {
      return Promise.resolve({ data: runningWorkflowStatus })
    }
    if (url === '/data/tushare/workflows/smart-screening') {
      return Promise.resolve({ data: sampleWorkflowDefinition })
    }
    return Promise.resolve({ data: {} })
  })
  mockPost.mockImplementation((url: string) => {
    if (url === '/data/tushare/workflows/smart-screening/plan') {
      return Promise.resolve({ data: sampleWorkflowPlan })
    }
    if (url === '/data/tushare/workflows/smart-screening/start') {
      return Promise.resolve({ data: { workflow_task_id: 'workflow-1', status: 'pending' } })
    }
    return Promise.resolve({ data: { status: 'ok' } })
  })
}

function getButton(wrapper: ReturnType<typeof mount>, ariaLabel: string) {
  return wrapper.find(`button[aria-label="${ariaLabel}"]`)
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

describe('TushareImportView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 30, 17, 0, 0))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ── 1. 组件渲染 ──────────────────────────────────────────────────────────

  it('渲染页面标题', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.find('.page-title').text()).toBe('Tushare 数据导入')
    wrapper.unmount()
  })

  // ── 2. 连接状态检查 ──────────────────────────────────────────────────────

  it('页面加载时自动检查连接状态', async () => {
    setupMocks()
    mount(TushareImportView)
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/data/tushare/health')
  })

  it('连接成功时显示"已连接"状态', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.find('.connection-status.connected').exists()).toBe(true)
    expect(wrapper.text()).toContain('已连接')
    wrapper.unmount()
  })

  it('连接失败时显示"未连接"状态', async () => {
    setupMocks(healthDisconnected)
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.find('.connection-status.disconnected').exists()).toBe(true)
    expect(wrapper.text()).toContain('未连接')
    wrapper.unmount()
  })

  it('显示三级 Token 配置状态', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const text = wrapper.text()
    // basic 和 advanced 已配置，special 未配置
    expect(text).toContain('基础✅')
    expect(text).toContain('高级✅')
    expect(text).toContain('特殊❌')
    wrapper.unmount()
  })

  it('点击"重新检测"按钮触发健康检查', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    mockGet.mockClear()
    const btn = wrapper.find('button[aria-label="重新检测 Tushare 连接"]')
    await btn.trigger('click')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/data/tushare/health')
    wrapper.unmount()
  })

  // ── 3. 接口列表展示 ──────────────────────────────────────────────────────

  it('显示"股票数据"和"指数专题"两个分类区域', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const sections = wrapper.findAll('.section-title')
    const titles = sections.map((s) => s.text())
    expect(titles).toContain('📈 股票数据')
    expect(titles).toContain('📊 指数专题')
    wrapper.unmount()
  })

  it('按子分类分组显示可折叠的接口列表', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 应有子分类 header
    const headers = wrapper.findAll('.subcategory-header')
    expect(headers.length).toBeGreaterThan(0)

    // 初始状态下 API 列表不可见
    expect(wrapper.findAll('.api-list').length).toBe(0)
    wrapper.unmount()
  })

  it('展开子分类后显示 API 接口列表', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 点击第一个子分类 header
    const header = wrapper.find('.subcategory-header')
    await header.trigger('click')
    await flushPromises()

    // 应显示 API 列表
    expect(wrapper.findAll('.api-item').length).toBeGreaterThan(0)

    // 显示 api_name 和 label
    expect(wrapper.text()).toContain('stock_basic')
    expect(wrapper.text()).toContain('股票基础列表')
    wrapper.unmount()
  })

  it('显示 Token 权限标签', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 展开第一个子分类
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()

    // 应有权限标签
    const badges = wrapper.findAll('.tier-badge')
    expect(badges.length).toBeGreaterThan(0)
    wrapper.unmount()
  })

  it('子分类 header 显示接口数量', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const counts = wrapper.findAll('.subcategory-count')
    expect(counts.length).toBeGreaterThan(0)
    // "基础数据" 子分类有 1 个接口
    expect(counts[0].text()).toContain('个接口')
    wrapper.unmount()
  })

  // ── 4. 参数表单交互 ──────────────────────────────────────────────────────

  it('日期范围参数渲染起止日期选择器', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 展开"行情数据"子分类（daily 接口有 date_range 参数）
    const headers = wrapper.findAll('.subcategory-header')
    // 找到包含 daily 的子分类
    for (const h of headers) {
      if (h.text().includes('行情数据')) {
        await h.trigger('click')
        break
      }
    }
    await flushPromises()

    // 应有日期输入框
    const dateInputs = wrapper.findAll('input[type="date"]')
    expect(dateInputs.length).toBeGreaterThanOrEqual(2)
    wrapper.unmount()
  })

  it('Token 未配置时导入按钮禁用并显示提示', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 展开指数技术面因子子分类（token_available=false）
    const headers = wrapper.findAll('.subcategory-header')
    for (const h of headers) {
      if (h.text().includes('指数技术面因子')) {
        await h.trigger('click')
        break
      }
    }
    await flushPromises()

    // 找到 index_tech 的导入按钮
    const importBtns = wrapper.findAll('.btn-import')
    if (importBtns.length > 0) {
      const btn = importBtns[importBtns.length - 1]
      expect(btn.attributes('disabled')).toBeDefined()
      expect(btn.attributes('title')).toContain('需配置对应权限 Token')
    }
    wrapper.unmount()
  })

  // ── 5. 导入启动/停止 ────────────────────────────────────────────────────

  it('点击"开始导入"调用 POST /import', async () => {
    setupMocks()
    mockPost.mockResolvedValue({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 展开"基础数据"子分类
    const header = wrapper.find('.subcategory-header')
    await header.trigger('click')
    await flushPromises()

    // 点击导入按钮（stock_basic 无必填参数）
    const importBtn = wrapper.find('.btn-import')
    await importBtn.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith(
      '/data/tushare/import',
      expect.objectContaining({ api_name: 'stock_basic' }),
    )
    wrapper.unmount()
  })

  // ── 6. 智能选股一键导入工作流 ───────────────────────────────────────────

  it('显示智能选股工作流日期控件和四个快捷按钮', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.find('[aria-label="智能选股导入日期范围"]').exists()).toBe(true)
    expect(wrapper.find('select[aria-label="智能选股导入链路模式"]').exists()).toBe(true)
    expect((wrapper.find('select[aria-label="智能选股导入链路模式"]').element as HTMLSelectElement).value).toBe('daily_fast')
    expect(getButton(wrapper, '智能选股一键导入').text()).toBe('一键导入')
    expect(getButton(wrapper, '暂停智能选股一键导入').text()).toBe('一键暂停')
    expect(getButton(wrapper, '恢复智能选股一键导入').text()).toBe('一键恢复')
    expect(getButton(wrapper, '停止智能选股一键导入').text()).toBe('一键停止')

    wrapper.unmount()
  })

  it('切换链路后按新模式加载工作流定义和计划', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    await wrapper.find('select[aria-label="智能选股导入链路模式"]').setValue('weekly_maintenance')
    await getButton(wrapper, '智能选股一键导入').trigger('click')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith(
      '/data/tushare/workflows/smart-screening',
      expect.objectContaining({ params: { mode: 'weekly_maintenance' } }),
    )
    expect(mockPost).toHaveBeenCalledWith(
      '/data/tushare/workflows/smart-screening/plan',
      expect.objectContaining({ mode: 'weekly_maintenance' }),
    )

    wrapper.unmount()
  })

  it('智能选股导入日期默认最近一天', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const startInput = wrapper.find<HTMLInputElement>('input[aria-label="智能选股导入起始日期"]')
    const endInput = wrapper.find<HTMLInputElement>('input[aria-label="智能选股导入结束日期"]')
    expect(startInput.element.value).toBe('2026-04-30')
    expect(endInput.element.value).toBe('2026-04-30')

    wrapper.unmount()
  })

  it('智能选股日期范围不合法时禁用一键导入', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    await wrapper.find('input[aria-label="智能选股导入起始日期"]').setValue('2026-04-30')
    await wrapper.find('input[aria-label="智能选股导入结束日期"]').setValue('2026-04-10')
    await flushPromises()

    const importButton = getButton(wrapper, '智能选股一键导入')
    expect((importButton.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('起始日期不能晚于结束日期')

    wrapper.unmount()
  })

  it('Tushare 未连接时禁用智能选股一键导入', async () => {
    setupMocks(healthDisconnected)
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const importButton = getButton(wrapper, '智能选股一键导入')
    expect((importButton.element as HTMLButtonElement).disabled).toBe(true)
    expect(importButton.attributes('title')).toBe('Tushare 未连接')

    wrapper.unmount()
  })

  it('确认智能选股一键导入时提交所选日期范围', async () => {
    setupMocks()
    mockPost.mockImplementation((url: string) => {
      if (url === '/data/tushare/workflows/smart-screening/plan') {
        return Promise.resolve({ data: sampleWorkflowPlan })
      }
      if (url === '/data/tushare/workflows/smart-screening/start') {
        return Promise.resolve({ data: { workflow_task_id: 'workflow-1', status: 'pending' } })
      }
      return Promise.resolve({ data: { status: 'ok' } })
    })
    const wrapper = mount(TushareImportView)
    await flushPromises()

    await wrapper.find('input[aria-label="智能选股导入起始日期"]').setValue('2026-04-10')
    await wrapper.find('input[aria-label="智能选股导入结束日期"]').setValue('2026-04-30')
    await getButton(wrapper, '智能选股一键导入').trigger('click')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith(
      '/data/tushare/workflows/smart-screening',
      expect.objectContaining({ params: { mode: 'daily_fast' } }),
    )
    expect(wrapper.text()).toContain('基础数据')
    expect(wrapper.text()).toContain('stock_basic')
    expect(wrapper.text()).toContain('本次执行')
    expect(wrapper.text()).toContain('本次跳过')

    await wrapper.find('.workflow-actions .btn-primary').trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith(
      '/data/tushare/workflows/smart-screening/start',
      expect.objectContaining({
        mode: 'daily_fast',
        date_range: { start_date: '20260410', end_date: '20260430' },
      }),
    )

    wrapper.unmount()
  })

  it('运行中工作流启用暂停和停止并调用对应接口', async () => {
    setupMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/data/tushare/workflows/running') return Promise.resolve({ data: runningWorkflowStatus })
      if (url.startsWith('/data/tushare/workflows/status/')) return Promise.resolve({ data: runningWorkflowStatus })
      if (url === '/data/tushare/health') return Promise.resolve({ data: healthConnected })
      if (url === '/data/tushare/registry') return Promise.resolve({ data: sampleRegistry })
      if (url.startsWith('/data/tushare/import/history')) return Promise.resolve({ data: sampleHistory })
      if (url === '/data/tushare/import/last-times') return Promise.resolve({ data: {} })
      if (url === '/data/tushare/import/running') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })
    mockPost.mockResolvedValue({ data: { status: 'ok' } })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    const pauseButton = getButton(wrapper, '暂停智能选股一键导入')
    const resumeButton = getButton(wrapper, '恢复智能选股一键导入')
    const stopButton = getButton(wrapper, '停止智能选股一键导入')
    expect((pauseButton.element as HTMLButtonElement).disabled).toBe(false)
    expect((resumeButton.element as HTMLButtonElement).disabled).toBe(true)
    expect((stopButton.element as HTMLButtonElement).disabled).toBe(false)

    await pauseButton.trigger('click')
    await stopButton.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/data/tushare/workflows/pause/workflow-1')
    expect(mockPost).toHaveBeenCalledWith('/data/tushare/workflows/stop/workflow-1')

    wrapper.unmount()
  })

  it('工作流子接口运行中显示 Redis 进度而不是 0 行', async () => {
    const statusWithChildProgress = {
      ...runningWorkflowStatus,
      child_tasks: [
        {
          task_id: 'child-1',
          api_name: 'daily',
          status: 'running',
          record_count: 0,
          progress: {
            total: 100,
            completed: 42,
            failed: 1,
            current_item: '600000.SH',
          },
        },
      ],
    }
    setupMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/data/tushare/workflows/running') return Promise.resolve({ data: statusWithChildProgress })
      if (url.startsWith('/data/tushare/workflows/status/')) return Promise.resolve({ data: statusWithChildProgress })
      if (url === '/data/tushare/health') return Promise.resolve({ data: healthConnected })
      if (url === '/data/tushare/registry') return Promise.resolve({ data: sampleRegistry })
      if (url.startsWith('/data/tushare/import/history')) return Promise.resolve({ data: sampleHistory })
      if (url === '/data/tushare/import/last-times') return Promise.resolve({ data: {} })
      if (url === '/data/tushare/import/running') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.text()).toContain('42 / 100')
    expect(wrapper.text()).toContain('当前 600000.SH')
    expect(wrapper.text()).not.toContain('daily运行中0 行')

    wrapper.unmount()
  })

  it('工作流进度区展示跳过接口维护建议和下一步动作', async () => {
    setupMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/data/tushare/workflows/running') return Promise.resolve({ data: runningWorkflowStatus })
      if (url.startsWith('/data/tushare/workflows/status/')) return Promise.resolve({ data: runningWorkflowStatus })
      if (url === '/data/tushare/health') return Promise.resolve({ data: healthConnected })
      if (url === '/data/tushare/registry') return Promise.resolve({ data: sampleRegistry })
      if (url.startsWith('/data/tushare/import/history')) return Promise.resolve({ data: sampleHistory })
      if (url === '/data/tushare/import/last-times') return Promise.resolve({ data: {} })
      if (url === '/data/tushare/import/running') return Promise.resolve({ data: [] })
      if (url === '/data/tushare/workflows/smart-screening') return Promise.resolve({ data: sampleWorkflowDefinition })
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.text()).toContain('已跳过')
    expect(wrapper.text()).toContain('stock_basic')
    expect(wrapper.text()).toContain('维护建议')
    expect(wrapper.text()).toContain('dc_member')
    expect(wrapper.text()).toContain('补齐缺口')

    wrapper.unmount()
  })

  it('已暂停工作流启用恢复并调用恢复接口', async () => {
    const pausedWorkflowStatus = { ...runningWorkflowStatus, status: 'paused' }
    setupMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/data/tushare/workflows/running') return Promise.resolve({ data: pausedWorkflowStatus })
      if (url.startsWith('/data/tushare/workflows/status/')) return Promise.resolve({ data: pausedWorkflowStatus })
      if (url === '/data/tushare/health') return Promise.resolve({ data: healthConnected })
      if (url === '/data/tushare/registry') return Promise.resolve({ data: sampleRegistry })
      if (url.startsWith('/data/tushare/import/history')) return Promise.resolve({ data: sampleHistory })
      if (url === '/data/tushare/import/last-times') return Promise.resolve({ data: {} })
      if (url === '/data/tushare/import/running') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })
    mockPost.mockResolvedValue({ data: { status: 'running' } })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    const pauseButton = getButton(wrapper, '暂停智能选股一键导入')
    const resumeButton = getButton(wrapper, '恢复智能选股一键导入')
    const stopButton = getButton(wrapper, '停止智能选股一键导入')
    expect((pauseButton.element as HTMLButtonElement).disabled).toBe(true)
    expect((resumeButton.element as HTMLButtonElement).disabled).toBe(false)
    expect((stopButton.element as HTMLButtonElement).disabled).toBe(false)

    await resumeButton.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/data/tushare/workflows/resume/workflow-1')

    wrapper.unmount()
  })

  it('导入启动后显示活跃任务区域', async () => {
    setupMocks()
    mockPost.mockResolvedValue({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 展开并点击导入
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()
    await wrapper.find('.btn-import').trigger('click')
    await flushPromises()

    // 应显示活跃任务
    expect(wrapper.find('.active-task').exists()).toBe(true)
    expect(wrapper.text()).toContain('stock_basic')
    wrapper.unmount()
  })

  it('活跃任务显示"停止导入"按钮', async () => {
    setupMocks()
    mockPost.mockResolvedValue({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 启动导入
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()
    await wrapper.find('.btn-import').trigger('click')
    await flushPromises()

    // 应有停止按钮
    const stopBtn = wrapper.find('.active-task .btn-danger')
    expect(stopBtn.exists()).toBe(true)
    expect(stopBtn.text()).toContain('停止导入')
    wrapper.unmount()
  })

  it('点击"停止导入"调用 POST /import/stop', async () => {
    setupMocks()
    mockPost.mockResolvedValueOnce({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })
    mockPost.mockResolvedValueOnce({
      data: { message: '已发送停止信号' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 启动导入
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()
    await wrapper.find('.btn-import').trigger('click')
    await flushPromises()

    // 点击停止
    const stopBtn = wrapper.find('.active-task .btn-danger')
    await stopBtn.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/data/tushare/import/stop/task-1')
    wrapper.unmount()
  })

  // ── 7. 进度更新 ─────────────────────────────────────────────────────────

  it('每 3 秒轮询进度接口', async () => {
    setupMocks()
    mockPost.mockResolvedValue({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 启动导入
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()
    await wrapper.find('.btn-import').trigger('click')
    await flushPromises()

    // 清除之前的调用记录
    const callsBefore = mockGet.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/import/status/'),
    ).length

    // 推进 3 秒
    vi.advanceTimersByTime(3000)
    await flushPromises()

    const callsAfter = mockGet.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/import/status/'),
    ).length

    expect(callsAfter).toBeGreaterThan(callsBefore)
    wrapper.unmount()
  })

  it('进度更新后显示百分比和完成数量', async () => {
    setupMocks()
    mockPost.mockResolvedValue({
      data: { task_id: 'task-1', log_id: 1, status: 'pending' },
    })

    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 启动导入
    await wrapper.find('.subcategory-header').trigger('click')
    await flushPromises()
    await wrapper.find('.btn-import').trigger('click')
    await flushPromises()

    // 推进轮询
    vi.advanceTimersByTime(3000)
    await flushPromises()

    // 进度数据应显示（50/100 = 50%）
    const text = wrapper.text()
    expect(text).toContain('50%')
    expect(text).toContain('50')
    wrapper.unmount()
  })

  // ── 8. 历史记录显示 ─────────────────────────────────────────────────────

  it('页面加载时获取导入历史', async () => {
    setupMocks()
    mount(TushareImportView)
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith(
      '/data/tushare/import/history',
      expect.objectContaining({ params: { limit: 20 } }),
    )
  })

  it('显示历史记录表格', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 应有表格
    expect(wrapper.find('.data-table').exists()).toBe(true)

    // 表头
    const text = wrapper.text()
    expect(text).toContain('接口名称')
    expect(text).toContain('导入时间')
    expect(text).toContain('数据量')
    expect(text).toContain('状态')
    expect(text).toContain('耗时')
    wrapper.unmount()
  })

  it('历史记录显示接口名称和数据量', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('stock_basic')
    expect(text).toContain('5,200')
    expect(text).toContain('daily')
    wrapper.unmount()
  })

  it('历史记录显示状态标签', async () => {
    setupMocks()
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 应有状态标签
    const badges = wrapper.findAll('.status-badge')
    expect(badges.length).toBeGreaterThanOrEqual(2)

    const text = wrapper.text()
    expect(text).toContain('成功')
    expect(text).toContain('失败')
    wrapper.unmount()
  })

  it('无历史记录时显示空状态', async () => {
    setupMocks(healthConnected, sampleRegistry, [])
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.text()).toContain('暂无导入记录')
    wrapper.unmount()
  })

  // ── 边界情况 ─────────────────────────────────────────────────────────────

  it('API 调用失败时优雅降级', async () => {
    mockGet.mockRejectedValue(new Error('网络错误'))
    const wrapper = mount(TushareImportView)
    await flushPromises()

    // 不应崩溃，应显示未连接状态
    expect(wrapper.find('.connection-status.disconnected').exists()).toBe(true)
    wrapper.unmount()
  })

  it('注册表为空时显示空状态', async () => {
    setupMocks(healthConnected, [])
    const wrapper = mount(TushareImportView)
    await flushPromises()

    expect(wrapper.text()).toContain('暂无股票数据接口')
    expect(wrapper.text()).toContain('暂无指数专题接口')
    wrapper.unmount()
  })
})
