import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useScreenerStore } from '../screener'

const mockPost = vi.fn()
const mockGet = vi.fn()

vi.mock('@/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

describe('useScreenerStore factor stats', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('runScreen 完成后保存因子筛选统计', async () => {
    const factorStats = [
      {
        factor_name: 'ma_trend',
        label: 'MA趋势打分',
        role: 'primary',
        group_id: 'primary_core',
        evaluated_count: 3,
        passed_count: 2,
        failed_count: 1,
        missing_count: 0,
      },
    ]
    mockPost.mockResolvedValueOnce({ data: { task_id: 'task-1', status: 'pending' } })
    mockGet.mockImplementation((url: string) => {
      if (url === '/screen/run/status/task-1') {
        return Promise.resolve({
          data: {
            task_id: 'task-1',
            status: 'completed',
            strategy_id: 'strategy-1',
            factor_stats: factorStats,
          },
        })
      }
      if (url === '/screen/results') {
        return Promise.resolve({
          data: {
            strategy_id: 'strategy-1',
            items: [],
            factor_stats: factorStats,
          },
        })
      }
      return Promise.resolve({ data: {} })
    })

    const store = useScreenerStore()
    const result = await store.runScreen({ strategyId: 'strategy-1' })

    expect(result.success).toBe(true)
    expect(store.lastFactorStats).toEqual(factorStats)
    expect(store.lastFactorStatsStrategyKey).toBe('strategy-1')
  })

  it('fetchResults 可从结果缓存恢复因子筛选统计', async () => {
    mockGet.mockResolvedValueOnce({
      data: {
        strategy_id: 'latest-strategy',
        items: [],
        factor_stats: [
          {
            factor_name: 'money_flow',
            label: '主力资金净流入',
            role: 'confirmation',
            group_id: 'confirmation',
            evaluated_count: 3,
            passed_count: 1,
            failed_count: 1,
            missing_count: 1,
          },
        ],
      },
    })

    const store = useScreenerStore()
    await store.fetchResults()

    expect(store.lastFactorStats).toHaveLength(1)
    expect(store.lastFactorStats[0].factor_name).toBe('money_flow')
    expect(store.lastFactorStatsStrategyKey).toBe('latest-strategy')
  })
})
