import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LocalImportView from '../LocalImportView.vue'

// Mock apiClient
const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

function idleStatus() {
  return {
    data: {
      status: 'idle',
      total_files: 0,
      processed_files: 0,
      success_files: 0,
      failed_files: 0,
      total_parsed: 0,
      total_inserted: 0,
      total_skipped: 0,
      elapsed_seconds: 0,
      failed_details: [],
    },
  }
}

function mountView() {
  return mount(LocalImportView, {
    global: { plugins: [createPinia()] },
  })
}

describe('LocalImportView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    vi.useFakeTimers()
    // Default: onMounted fetchStatus returns idle
    mockGet.mockResolvedValue(idleStatus())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ── 组件挂载和渲染 (需求 11.2) ──

  it('渲染页面标题和导入配置区域', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('本地数据导入')
    expect(wrapper.text()).toContain('导入配置')
    expect(wrapper.text()).toContain('频率选择')
    expect(wrapper.find('button[aria-label="开始导入"]').exists()).toBe(true)
  })

  it('渲染五种频率的复选框', async () => {
    const wrapper = mountView()
    await flushPromises()

    const checkboxes = wrapper.findAll('.checkbox-group input[type="checkbox"]')
    // 5 freq checkboxes + 1 force import checkbox
    const freqCheckboxes = checkboxes.filter((cb) => {
      const label = cb.element.parentElement?.textContent?.trim() ?? ''
      return ['1m', '5m', '15m', '30m', '60m'].includes(label)
    })
    expect(freqCheckboxes.length).toBe(5)
  })

  it('渲染子目录输入框', async () => {
    const wrapper = mountView()
    await flushPromises()

    const input = wrapper.find('#sub-dir')
    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toContain('000001')
  })

  it('渲染定时任务配置区域', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('定时任务配置')
    expect(wrapper.find('#sched-hour').exists()).toBe(true)
    expect(wrapper.find('#sched-minute').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="保存定时配置"]').exists()).toBe(true)
  })

  // ── 频率多选控件交互 (需求 11.2) ──

  it('频率复选框默认全选', async () => {
    const wrapper = mountView()
    await flushPromises()

    const checkboxes = wrapper.findAll('.checkbox-group input[type="checkbox"]')
    const freqCheckboxes = checkboxes.filter((cb) => {
      const label = cb.element.parentElement?.textContent?.trim() ?? ''
      return ['1m', '5m', '15m', '30m', '60m'].includes(label)
    })
    for (const cb of freqCheckboxes) {
      expect((cb.element as HTMLInputElement).checked).toBe(true)
    }
  })

  it('取消勾选频率后再勾选恢复', async () => {
    const wrapper = mountView()
    await flushPromises()

    const checkboxes = wrapper.findAll('.checkbox-group input[type="checkbox"]')
    const firstFreq = checkboxes.find((cb) => {
      return cb.element.parentElement?.textContent?.trim() === '1m'
    })!
    expect(firstFreq).toBeDefined()

    // Uncheck
    await firstFreq.setValue(false)
    expect((firstFreq.element as HTMLInputElement).checked).toBe(false)

    // Re-check
    await firstFreq.setValue(true)
    expect((firstFreq.element as HTMLInputElement).checked).toBe(true)
  })

  // ── 开始导入按钮禁用/启用状态 (需求 11.5) ──

  it('默认状态下开始导入按钮可用', async () => {
    const wrapper = mountView()
    await flushPromises()

    const btn = wrapper.find('button[aria-label="开始导入"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('导入请求期间按钮禁用', async () => {
    // Make post hang (never resolve during test)
    let resolvePost: (v: unknown) => void
    mockPost.mockReturnValue(new Promise((r) => { resolvePost = r }))

    const wrapper = mountView()
    await flushPromises()

    const btn = wrapper.find('button[aria-label="开始导入"]')
    await btn.trigger('click')
    await flushPromises()

    // loading is true → button disabled
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    expect(btn.text()).toBe('提交中...')

    // Resolve to clean up
    resolvePost!({ data: { task_id: 'test-123', message: 'ok' } })
    await flushPromises()
  })

  it('导入成功后按钮恢复可用并显示任务ID', async () => {
    mockPost.mockResolvedValue({ data: { task_id: 'task-abc', message: '已触发' } })

    const wrapper = mountView()
    await flushPromises()

    const btn = wrapper.find('button[aria-label="开始导入"]')
    await btn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('task-abc')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  // ── 409 错误提示展示 (需求 11.7) ──

  it('后端返回409时显示已有任务运行提示', async () => {
    mockPost.mockRejectedValue(new Error('已有导入任务正在运行'))

    const wrapper = mountView()
    await flushPromises()

    const btn = wrapper.find('button[aria-label="开始导入"]')
    await btn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已有导入任务正在运行')
    const errorMsg = wrapper.find('.sync-msg.error')
    expect(errorMsg.exists()).toBe(true)
  })

  it('409错误后按钮恢复可用', async () => {
    mockPost.mockRejectedValue(new Error('已有导入任务正在运行'))

    const wrapper = mountView()
    await flushPromises()

    const btn = wrapper.find('button[aria-label="开始导入"]')
    await btn.trigger('click')
    await flushPromises()

    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  // ── 进度轮询启动/停止 (需求 11.9) ──

  it('导入成功后启动轮询', async () => {
    mockPost.mockResolvedValue({ data: { task_id: 'task-poll', message: 'ok' } })
    mockGet.mockResolvedValue({
      data: {
        status: 'running',
        total_files: 10,
        processed_files: 3,
        success_files: 3,
        failed_files: 0,
        total_parsed: 3000,
        total_inserted: 2900,
        total_skipped: 100,
        elapsed_seconds: 5.2,
        failed_details: [],
      },
    })

    const wrapper = mountView()
    await flushPromises()

    // Trigger import
    await wrapper.find('button[aria-label="开始导入"]').trigger('click')
    await flushPromises()

    // Advance past one polling interval (3s)
    vi.advanceTimersByTime(3000)
    await flushPromises()

    // fetchStatus should have been called multiple times (onMounted + startPolling immediate + interval)
    expect(mockGet).toHaveBeenCalled()
    expect(wrapper.text()).toContain('运行中')
  })

  it('任务完成后停止轮询', async () => {
    mockPost.mockResolvedValue({ data: { task_id: 'task-done', message: 'ok' } })

    const wrapper = mountView()
    await flushPromises()

    // Trigger import
    await wrapper.find('button[aria-label="开始导入"]').trigger('click')
    await flushPromises()

    // First poll returns running
    mockGet.mockResolvedValue({
      data: {
        status: 'running',
        total_files: 5,
        processed_files: 2,
        success_files: 2,
        failed_files: 0,
        total_parsed: 2000,
        total_inserted: 1900,
        total_skipped: 100,
        elapsed_seconds: 3.0,
        failed_details: [],
      },
    })
    vi.advanceTimersByTime(3000)
    await flushPromises()

    // Second poll returns completed → should stop polling
    mockGet.mockResolvedValue({
      data: {
        status: 'completed',
        total_files: 5,
        processed_files: 5,
        success_files: 5,
        failed_files: 0,
        total_parsed: 5000,
        total_inserted: 4800,
        total_skipped: 200,
        elapsed_seconds: 10.5,
        failed_details: [],
      },
    })
    vi.advanceTimersByTime(3000)
    await flushPromises()

    const callCountAfterComplete = mockGet.mock.calls.length

    // Advance more time — no additional calls should happen
    vi.advanceTimersByTime(9000)
    await flushPromises()

    expect(mockGet.mock.calls.length).toBe(callCountAfterComplete)
    expect(wrapper.text()).toContain('结果摘要')
  })

  it('页面挂载时检测到运行中任务自动恢复轮询', async () => {
    mockGet.mockResolvedValue({
      data: {
        status: 'running',
        total_files: 20,
        processed_files: 8,
        success_files: 8,
        failed_files: 0,
        total_parsed: 8000,
        total_inserted: 7500,
        total_skipped: 500,
        elapsed_seconds: 15.0,
        failed_details: [],
      },
    })

    const wrapper = mountView()
    await flushPromises()

    // onMounted fetches status and sees running → starts polling
    expect(wrapper.text()).toContain('运行中')

    // Advance to trigger another poll
    vi.advanceTimersByTime(3000)
    await flushPromises()

    // Should have polled at least twice (onMounted + interval)
    expect(mockGet.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('组件卸载时停止轮询', async () => {
    mockGet.mockResolvedValue({
      data: {
        status: 'running',
        total_files: 10,
        processed_files: 2,
        success_files: 2,
        failed_files: 0,
        total_parsed: 2000,
        total_inserted: 1800,
        total_skipped: 200,
        elapsed_seconds: 4.0,
        failed_details: [],
      },
    })

    const wrapper = mountView()
    await flushPromises()

    const callsBefore = mockGet.mock.calls.length

    wrapper.unmount()

    vi.advanceTimersByTime(9000)
    await flushPromises()

    // No additional calls after unmount
    expect(mockGet.mock.calls.length).toBe(callsBefore)
  })
})
