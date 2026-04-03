import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { apiClient } from '@/api'

// ─── 接口定义 ─────────────────────────────────────────────────────────────────

export interface ImportParams {
  freqs: string[] | null
  sub_dir: string | null
  force: boolean
}

export interface ImportProgress {
  status: string
  total_files: number
  processed_files: number
  success_files: number
  failed_files: number
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
  total_parsed: number
  total_inserted: number
  total_skipped: number
  elapsed_seconds: number
  failed_details: Array<{ path: string; error: string }>
}

// ─── 默认值工厂 ───────────────────────────────────────────────────────────────

function defaultProgress(): ImportProgress {
  return {
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

  let pollingTimer: ReturnType<typeof setInterval> | null = null

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

      // 只有当前有 taskId 且状态为终态时才停止轮询
      // 避免新任务刚触发时读到上次的 completed 状态就停止
      if (
        (res.data.status === 'completed' || res.data.status === 'failed') &&
        progress.processed_files > 0
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

  return {
    taskId,
    progress,
    result,
    loading,
    polling,
    error,
    startImport,
    fetchStatus,
    startPolling,
    stopPolling,
  }
})
