/**
 * SectorStore 单元测试
 *
 * 测试 useSectorStore 的初始状态、fetchRanking 成功/失败、setSectorType 行为。
 * Requirements: 5.1, 5.2, 5.3, 5.4
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSectorStore, type SectorRankingItem } from '../sector'

// Mock apiClient
vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/api'

const mockedGet = vi.mocked(apiClient.get)

// ─── 辅助：构造板块排行数据 ─────────────────────────────────────────────────

function makeSectorItem(overrides: Partial<SectorRankingItem> = {}): SectorRankingItem {
  return {
    sector_code: 'BK0001',
    name: '测试板块',
    sector_type: 'INDUSTRY',
    change_pct: 2.35,
    close: 1234.56,
    volume: 100000,
    amount: 5000000000,
    turnover: 3.21,
    ...overrides,
  }
}

describe('useSectorStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ─── 初始状态 ─────────────────────────────────────────────────────────────

  describe('初始状态', () => {
    it('rankings 为空列表、currentType 为空字符串、loading 为 false、error 为空字符串', () => {
      const store = useSectorStore()
      expect(store.rankings).toEqual([])
      expect(store.currentType).toBe('')
      expect(store.loading).toBe(false)
      expect(store.error).toBe('')
    })
  })

  // ─── fetchRanking 成功 ────────────────────────────────────────────────────

  describe('fetchRanking 成功', () => {
    it('成功获取数据后更新 rankings', async () => {
      const mockData = [
        makeSectorItem({ sector_code: 'BK0001', name: '半导体', change_pct: 5.12 }),
        makeSectorItem({ sector_code: 'BK0002', name: '新能源', change_pct: 3.45 }),
      ]
      mockedGet.mockResolvedValueOnce({ data: mockData })

      const store = useSectorStore()
      await store.fetchRanking()

      expect(store.rankings).toEqual(mockData)
      expect(store.loading).toBe(false)
      expect(store.error).toBe('')
    })

    it('传入 sectorType 时请求携带 sector_type 参数', async () => {
      mockedGet.mockResolvedValueOnce({ data: [] })

      const store = useSectorStore()
      await store.fetchRanking('CONCEPT')

      expect(mockedGet).toHaveBeenCalledWith('/sector/ranking', {
        params: { sector_type: 'CONCEPT' },
      })
    })

    it('不传 sectorType 时请求不携带 sector_type 参数', async () => {
      mockedGet.mockResolvedValueOnce({ data: [] })

      const store = useSectorStore()
      await store.fetchRanking()

      expect(mockedGet).toHaveBeenCalledWith('/sector/ranking', {
        params: {},
      })
    })
  })

  // ─── fetchRanking 失败 ────────────────────────────────────────────────────

  describe('fetchRanking 失败', () => {
    it('请求失败时设置 error 状态', async () => {
      mockedGet.mockRejectedValueOnce(new Error('网络连接失败'))

      const store = useSectorStore()
      await store.fetchRanking()

      expect(store.error).toBe('获取板块排行数据失败')
      expect(store.loading).toBe(false)
    })

    it('请求失败时保留上一次成功数据', async () => {
      const previousData = [
        makeSectorItem({ sector_code: 'BK0001', name: '半导体' }),
      ]
      mockedGet.mockResolvedValueOnce({ data: previousData })

      const store = useSectorStore()
      await store.fetchRanking()
      expect(store.rankings).toEqual(previousData)

      // 第二次请求失败
      mockedGet.mockRejectedValueOnce(new Error('服务器错误'))
      await store.fetchRanking()

      // 数据保留
      expect(store.rankings).toEqual(previousData)
      expect(store.error).toBe('获取板块排行数据失败')
    })
  })

  // ─── setSectorType ────────────────────────────────────────────────────────

  describe('setSectorType', () => {
    it('更新 currentType 并触发 fetchRanking', async () => {
      mockedGet.mockResolvedValue({ data: [] })

      const store = useSectorStore()
      store.setSectorType('CONCEPT')

      expect(store.currentType).toBe('CONCEPT')
      expect(mockedGet).toHaveBeenCalledWith('/sector/ranking', {
        params: { sector_type: 'CONCEPT' },
      })
    })

    it('设置空字符串类型时不传 sector_type 参数', async () => {
      mockedGet.mockResolvedValue({ data: [] })

      const store = useSectorStore()
      store.setSectorType('')

      expect(store.currentType).toBe('')
      expect(mockedGet).toHaveBeenCalledWith('/sector/ranking', {
        params: {},
      })
    })
  })

  // ─── toggleSectorKline ────────────────────────────────────────────────────

  describe('toggleSectorKline', () => {
    const mockKlineData = [
      { time: '2025-04-01', open: 100, high: 110, low: 95, close: 105, volume: 50000 },
      { time: '2025-04-02', open: 105, high: 115, low: 100, close: 112, volume: 60000 },
    ]

    it('展开板块：expandedSectorCode 设置正确，触发 API 调用', async () => {
      mockedGet.mockResolvedValueOnce({ data: mockKlineData })

      const store = useSectorStore()
      expect(store.expandedSectorCode).toBeNull()

      await store.toggleSectorKline('BK0001')

      expect(store.expandedSectorCode).toBe('BK0001')
      expect(store.expandedKlineData).toEqual(mockKlineData)
      expect(store.expandedKlineLoading).toBe(false)
      expect(store.expandedKlineError).toBe('')

      // 验证 API 调用参数
      expect(mockedGet).toHaveBeenCalledWith(
        '/sector/BK0001/kline',
        expect.objectContaining({
          params: expect.objectContaining({
            data_source: 'DC',
            freq: '1d',
          }),
        }),
      )
      // 验证 start/end 参数存在
      const callParams = mockedGet.mock.calls[0][1]?.params as Record<string, string>
      expect(callParams.start).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(callParams.end).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('收起板块：再次点击同一板块，expandedSectorCode 变为 null', async () => {
      mockedGet.mockResolvedValueOnce({ data: mockKlineData })

      const store = useSectorStore()
      await store.toggleSectorKline('BK0001')
      expect(store.expandedSectorCode).toBe('BK0001')

      // 再次点击同一板块 → 收起
      await store.toggleSectorKline('BK0001')
      expect(store.expandedSectorCode).toBeNull()
      expect(store.expandedKlineData).toEqual([])
      expect(store.expandedKlineError).toBe('')
    })

    it('切换板块：点击不同板块，expandedSectorCode 更新', async () => {
      const klineDataA = [
        { time: '2025-04-01', open: 100, high: 110, low: 95, close: 105, volume: 50000 },
      ]
      const klineDataB = [
        { time: '2025-04-01', open: 200, high: 220, low: 190, close: 210, volume: 80000 },
      ]
      mockedGet.mockResolvedValueOnce({ data: klineDataA })

      const store = useSectorStore()
      await store.toggleSectorKline('BK0001')
      expect(store.expandedSectorCode).toBe('BK0001')
      expect(store.expandedKlineData).toEqual(klineDataA)

      // 点击不同板块 → 切换
      mockedGet.mockResolvedValueOnce({ data: klineDataB })
      await store.toggleSectorKline('BK0002')
      expect(store.expandedSectorCode).toBe('BK0002')
      expect(store.expandedKlineData).toEqual(klineDataB)
    })

    it('K线加载失败时 expandedKlineError 设置正确', async () => {
      mockedGet.mockRejectedValueOnce(new Error('网络超时'))

      const store = useSectorStore()
      await store.toggleSectorKline('BK0001')

      expect(store.expandedSectorCode).toBe('BK0001')
      expect(store.expandedKlineError).toBe('获取板块K线数据失败')
      expect(store.expandedKlineData).toEqual([])
      expect(store.expandedKlineLoading).toBe(false)
    })

    it('展开时传入自定义 dataSource', async () => {
      mockedGet.mockResolvedValueOnce({ data: [] })

      const store = useSectorStore()
      await store.toggleSectorKline('BK0001', 'TI')

      const callParams = mockedGet.mock.calls[0][1]?.params as Record<string, string>
      expect(callParams.data_source).toBe('TI')
    })

    it('展开时使用 store 当前 dataSource', async () => {
      mockedGet.mockResolvedValueOnce({ data: [] })

      const store = useSectorStore()
      store.currentDataSource = 'TDX'
      await store.toggleSectorKline('BK0001')

      const callParams = mockedGet.mock.calls[0][1]?.params as Record<string, string>
      expect(callParams.data_source).toBe('TDX')
    })

    it('展开期间 loading 状态正确', async () => {
      let resolvePromise: (value: unknown) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockedGet.mockReturnValueOnce(pendingPromise as ReturnType<typeof mockedGet>)

      const store = useSectorStore()
      const togglePromise = store.toggleSectorKline('BK0001')

      // 请求进行中
      expect(store.expandedKlineLoading).toBe(true)

      resolvePromise!({ data: mockKlineData })
      await togglePromise

      // 请求完成
      expect(store.expandedKlineLoading).toBe(false)
    })
  })
})
