import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { apiClient } from '@/api'

// ─── 接口定义 ─────────────────────────────────────────────────────────────────

export interface ImportParams {
  markets: string[] | null
  freqs: string[] | null
  start_date: string | null
  end_date: string | null
  force: boolean
}

export interface AdjFactorImportParams {
  adj_factors: string[]
}

/** 缓存在 Redis 中的导入页面参数 */
export interface CachedImportParams {
  markets: string[] | null
  freqs: string[] | null
  start_date: string | null
  end_date: string | null
  force: boolean
  adj_factors: string[] | null
}

export interface ImportProgress {
  status: string
  total_files: number
  processed_files: number
  success_files: number
  failed_files: number
  skipped_files: number
  total_parsed: number
  total_inserted: number
  total_skipped: number
  elapsed_seconds: number
  failed_details: Array<{ path: string; error: string }>
}

export interface ImportResult {
  status: string
  total_files: number
  processed_files: number
  success_files: number
  failed_files: number
  skipped_files: number
  total_parsed: number
  total_inserted: number
  total_skipped: number
  elapsed_seconds: number
  failed_details: Array<{ path: string; error: string }>
}

export interface AdjFactorResult {
  status: string
  adj_factor_stats: Record<string, { status: string; parsed: number; inserted: number; skipped: number; error?: string }>
  elapsed_seconds: number
  error: string
  total_types: number
  completed_types: number
  current_type: string
  current_step: string
}

// ─── 默认值工厂 ───────────────────────────────────────────────────────────────

function defaultProgress(): ImportProgress {
  return {
    status: 'idle',
    total_files: 0,
    processed_files: 0,
    success_files: 0,
    failed_files: 0,
    skipped_files: 0,
    total_parsed: 0,
    total_inserted: 0,
    total_skipped: 0,
    elapsed_seconds: 0,
    failed_details: [],
  }
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useLocalImportStore = defineStore('localImport', () => {
  // 状态
  const taskId = ref<string | null>(null)
  const progress = reactive<ImportProgress>(defaultProgress())
  const result = reactive<ImportResult>(defaultProgress())
  const loading = ref(false)
  const polling = ref(false)
  const error = ref('')

  // 复权因子导入状态
  const adjLoading = ref(false)
  const adjResult = reactive<AdjFactorResult>({ status: 'idle', adj_factor_stats: {}, elapsed_seconds: 0, error: '', total_types: 0, completed_types: 0, current_type: '', current_step: '' })
  const adjError = ref('')
  const adjPolling = ref(false)

  let pollingTimer: ReturnType<typeof setInterval> | null = null
  let adjPollingTimer: ReturnType<typeof setInterval> | null = null

  // ── 动作 ──────────────────────────────────────────────────────────────────

  /** 触发本地K线导入任务 */
  async function startImport(params: ImportParams): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.post<{ task_id: string; message: string }>(
        '/data/import/local-kline',
        params,
      )
      taskId.value = res.data.task_id
      // 重置进度和结果，准备展示新任务
      Object.assign(progress, defaultProgress())
      Object.assign(result, defaultProgress())
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes('已有导入任务正在运行')) {
        error.value = '已有导入任务正在运行'
      } else if (err instanceof Error) {
        error.value = err.message
      } else {
        error.value = '触发导入失败'
      }
    } finally {
      loading.value = false
    }
  }

  /** 获取导入进度/结果 */
  async function fetchStatus(): Promise<void> {
    try {
      const res = await apiClient.get<ImportProgress>('/data/import/local-kline/status')
      Object.assign(progress, res.data)

      // pending / running / idle 继续轮询；终态时停止
      if (
        res.data.status === 'completed' ||
        res.data.status === 'failed' ||
        res.data.status === 'stopped'
      ) {
        stopPolling()
        Object.assign(result, res.data)
      }
    } catch {
      // 轮询请求失败时静默忽略，下次轮询继续尝试
    }
  }

  /** 启动 3 秒间隔轮询 */
  function startPolling(): void {
    // 防重入：先清理已有 timer
    if (pollingTimer !== null) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
    polling.value = true
    fetchStatus()
    pollingTimer = setInterval(fetchStatus, 3000)
  }

  /** 停止轮询 */
  function stopPolling(): void {
    if (pollingTimer !== null) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
    polling.value = false
  }

  /** 请求停止K线导入 */
  async function requestStopImport(): Promise<void> {
    try {
      await apiClient.post('/data/import/local-kline/stop')
    } catch {
      // 静默忽略
    }
  }

  /** 触发复权因子独立导入 */
  async function startAdjImport(params: AdjFactorImportParams): Promise<void> {
    adjLoading.value = true
    adjError.value = ''
    // 重置结果
    Object.assign(adjResult, { status: 'idle', adj_factor_stats: {}, elapsed_seconds: 0, error: '', total_types: 0, completed_types: 0, current_type: '', current_step: '' })
    try {
      await apiClient.post('/data/import/adj-factors', params)
      startAdjPolling()
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes('已有复权因子导入任务正在运行')) {
        adjError.value = '已有复权因子导入任务正在运行'
      } else if (err instanceof Error) {
        adjError.value = err.message
      } else {
        adjError.value = '触发复权因子导入失败'
      }
    } finally {
      adjLoading.value = false
    }
  }

  /** 获取复权因子导入状态 */
  async function fetchAdjStatus(): Promise<void> {
    try {
      const res = await apiClient.get<AdjFactorResult>('/data/import/adj-factors/status')
      Object.assign(adjResult, res.data)
      // 终态时停止轮询
      if (res.data.status === 'completed' || res.data.status === 'failed' || res.data.status === 'stopped') {
        stopAdjPolling()
      }
    } catch {
      // 静默忽略
    }
  }

  /** 启动复权因子导入轮询 */
  function startAdjPolling(): void {
    adjPolling.value = true
    fetchAdjStatus()
    adjPollingTimer = setInterval(fetchAdjStatus, 2000)
  }

  /** 停止复权因子导入轮询 */
  function stopAdjPolling(): void {
    if (adjPollingTimer !== null) {
      clearInterval(adjPollingTimer)
      adjPollingTimer = null
    }
    adjPolling.value = false
  }

  /** 请求停止复权因子导入 */
  async function requestStopAdjImport(): Promise<void> {
    try {
      await apiClient.post('/data/import/adj-factors/stop')
    } catch {
      // 静默忽略
    }
  }

  /** 保存导入参数到 Redis */
  async function saveParams(params: CachedImportParams): Promise<void> {
    try {
      await apiClient.put('/data/import/params', params)
    } catch {
      // 静默忽略，参数缓存失败不影响主流程
    }
  }

  /** 从 Redis 加载上次导入参数 */
  async function loadParams(): Promise<CachedImportParams | null> {
    try {
      const res = await apiClient.get<CachedImportParams>('/data/import/params')
      return res.data
    } catch {
      return null
    }
  }

  return {
    taskId,
    progress,
    result,
    loading,
    polling,
    error,
    adjLoading,
    adjResult,
    adjError,
    adjPolling,
    startImport,
    fetchStatus,
    startPolling,
    stopPolling,
    requestStopImport,
    startAdjImport,
    fetchAdjStatus,
    startAdjPolling,
    stopAdjPolling,
    requestStopAdjImport,
    saveParams,
    loadParams,
  }
})
