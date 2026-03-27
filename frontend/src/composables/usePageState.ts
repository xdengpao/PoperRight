import { reactive } from 'vue'

export interface PageState<T> {
  loading: boolean
  error: string | null
  data: T | null
}

export function usePageState<T>() {
  const state = reactive<PageState<T>>({ loading: false, error: null, data: null })

  async function execute(fn: () => Promise<T>): Promise<void> {
    state.loading = true
    state.error = null
    try {
      state.data = await fn()
    } catch (e) {
      state.error = e instanceof Error ? e.message : '请求失败，请重试'
    } finally {
      state.loading = false
    }
  }

  return { state, execute }
}
