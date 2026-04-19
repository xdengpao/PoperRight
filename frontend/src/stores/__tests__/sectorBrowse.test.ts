/**
 * SectorStore 浏览面板状态单元测试
 *
 * 测试 useSectorStore 中浏览面板相关的状态管理：
 * browserActiveTab、setBrowserTab、fetchSectorInfoBrowse、
 * fetchConstituentBrowse、fetchKlineBrowse、标签页状态隔离、筛选条件重置。
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  useSectorStore,
  type SectorInfoBrowseItem,
  type ConstituentBrowseItem,
  type KlineBrowseItem,
} from '../sector'

// Mock apiClient
vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/api'

const mockedGet = vi.mocked(apiClient.get)

// ─── 辅助：构造浏览面板数据 ─────────────────────────────────────────────────

function makeSectorInfoItem(overrides: Partial<SectorInfoBrowseItem> = {}): SectorInfoBrowseItem {
  return {
    sector_code: 'BK0001',
    name: '测试板块',
    sector_type: 'INDUSTRY',
    data_source: 'DC',
    list_date: '2020-01-01',
    constituent_count: 50,
    ...overrides,
  }
}

function makeConstituentItem(overrides: Partial<ConstituentBrowseItem> = {}): ConstituentBrowseItem {
  return {
    trade_date: '2025-04-01',
    sector_code: 'BK0001',
    data_source: 'DC',
    symbol: '600000',
    stock_name: '浦发银行',
    ...overrides,
  }
}

function makeKlineItem(overrides: Partial<KlineBrowseItem> = {}): KlineBrowseItem {
  return {
    time: '2025-04-01',
    sector_code: 'BK0001',
    data_source: 'DC',
    freq: '1d',
    open: 100,
    high: 110,
    low: 95,
    close: 105,
    volume: 50000,
    amount: 5000000,
    change_pct: 2.35,
    ...overrides,
  }
}

describe('useSectorStore 浏览面板状态', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ─── browserActiveTab 初始状态 ────────────────────────────────────────────

  describe('browserActiveTab 初始状态', () => {
    it('默认值为 info', () => {
      const store = useSectorStore()
      expect(store.browserActiveTab).toBe('info')
    })
  })

  // ─── setBrowserTab ────────────────────────────────────────────────────────

  describe('setBrowserTab', () => {
    it('切换到 constituent 标签页', () => {
      const store = useSectorStore()
      store.setBrowserTab('constituent')
      expect(store.browserActiveTab).toBe('constituent')
    })

    it('切换到 kline 标签页', () => {
      const store = useSectorStore()
      store.setBrowserTab('kline')
      expect(store.browserActiveTab).toBe('kline')
    })

    it('切换回 info 标签页', () => {
      const store = useSectorStore()
      store.setBrowserTab('kline')
      store.setBrowserTab('info')
      expect(store.browserActiveTab).toBe('info')
    })
  })

  // ─── fetchSectorInfoBrowse 成功 ───────────────────────────────────────────

  describe('fetchSectorInfoBrowse 成功', () => {
    it('成功获取数据后更新 infoBrowse 的 items、total、page', async () => {
      const mockItems = [
        makeSectorInfoItem({ sector_code: 'BK0001', name: '半导体' }),
        makeSectorInfoItem({ sector_code: 'BK0002', name: '新能源' }),
      ]
      mockedGet.mockResolvedValueOnce({
        data: { total: 10, page: 1, page_size: 50, items: mockItems },
      })

      const store = useSectorStore()
      await store.fetchSectorInfoBrowse()

      expect(store.infoBrowse.items).toEqual(mockItems)
      expect(store.infoBrowse.total).toBe(10)
      expect(store.infoBrowse.page).toBe(1)
      expect(store.infoBrowse.loading).toBe(false)
      expect(store.infoBrowse.error).toBe('')
    })

    it('传入 page 参数时请求对应页码', async () => {
      mockedGet.mockResolvedValueOnce({
        data: { total: 100, page: 3, page_size: 50, items: [] },
      })

      const store = useSectorStore()
      await store.fetchSectorInfoBrowse(3)

      expect(store.infoBrowse.page).toBe(3)
      expect(mockedGet).toHaveBeenCalledWith('/sector/info/browse', {
        params: expect.objectContaining({ page: '3', page_size: '50' }),
      })
    })

    it('请求携带筛选条件参数', async () => {
      mockedGet.mockResolvedValueOnce({
        data: { total: 0, page: 1, page_size: 50, items: [] },
      })

      const store = useSectorStore()
      // 默认 filters 中 data_source='DC'，其他为空字符串
      await store.fetchSectorInfoBrowse()

      // 空字符串的 filter 不应传递
      const callParams = mockedGet.mock.calls[0][1]?.params as Record<string, string>
      expect(callParams.data_source).toBe('DC')
      expect(callParams).not.toHaveProperty('sector_type')
      expect(callParams).not.toHaveProperty('keyword')
    })
  })

  // ─── fetchSectorInfoBrowse 失败 ───────────────────────────────────────────

  describe('fetchSectorInfoBrowse 失败', () => {
    it('请求失败时设置 error 状态', async () => {
      mockedGet.mockRejectedValueOnce(new Error('网络连接失败'))

      const store = useSectorStore()
      await store.fetchSectorInfoBrowse()

      expect(store.infoBrowse.error).toBe('获取板块数据失败')
      expect(store.infoBrowse.loading).toBe(false)
    })

    it('请求失败时保留上一次成功数据', async () => {
      const previousItems = [makeSectorInfoItem({ sector_code: 'BK0001' })]
      mockedGet.mockResolvedValueOnce({
        data: { total: 1, page: 1, page_size: 50, items: previousItems },
      })

      const store = useSectorStore()
      await store.fetchSectorInfoBrowse()
      expect(store.infoBrowse.items).toEqual(previousItems)

      // 第二次请求失败
      mockedGet.mockRejectedValueOnce(new Error('服务器错误'))
      await store.fetchSectorInfoBrowse()

      // 数据保留
      expect(store.infoBrowse.items).toEqual(previousItems)
      expect(store.infoBrowse.error).toBe('获取板块数据失败')
    })
  })

  // ─── fetchConstituentBrowse 成功 ──────────────────────────────────────────

  describe('fetchConstituentBrowse 成功', () => {
    it('成功获取数据后更新 constituentBrowse 状态', async () => {
      const mockItems = [
        makeConstituentItem({ symbol: '600000', stock_name: '浦发银行' }),
        makeConstituentItem({ symbol: '601398', stock_name: '工商银行' }),
      ]
      mockedGet.mockResolvedValueOnce({
        data: { total: 20, page: 1, page_size: 50, items: mockItems },
      })

      const store = useSectorStore()
      await store.fetchConstituentBrowse()

      expect(store.constituentBrowse.items).toEqual(mockItems)
      expect(store.constituentBrowse.total).toBe(20)
      expect(store.constituentBrowse.page).toBe(1)
      expect(store.constituentBrowse.loading).toBe(false)
      expect(store.constituentBrowse.error).toBe('')
    })
  })

  // ─── fetchKlineBrowse 成功 ────────────────────────────────────────────────

  describe('fetchKlineBrowse 成功', () => {
    it('成功获取数据后更新 klineBrowse 状态', async () => {
      const mockItems = [
        makeKlineItem({ time: '2025-04-01', close: 105, change_pct: 2.35 }),
        makeKlineItem({ time: '2025-04-02', close: 108, change_pct: 2.86 }),
      ]
      mockedGet.mockResolvedValueOnce({
        data: { total: 50, page: 1, page_size: 50, items: mockItems },
      })

      const store = useSectorStore()
      await store.fetchKlineBrowse()

      expect(store.klineBrowse.items).toEqual(mockItems)
      expect(store.klineBrowse.total).toBe(50)
      expect(store.klineBrowse.page).toBe(1)
      expect(store.klineBrowse.loading).toBe(false)
      expect(store.klineBrowse.error).toBe('')
    })
  })

  // ─── 标签页状态隔离 ──────────────────────────────────────────────────────

  describe('标签页状态隔离', () => {
    it('修改 infoBrowse 不影响 constituentBrowse 和 klineBrowse', async () => {
      const infoItems = [makeSectorInfoItem({ sector_code: 'BK0001' })]
      mockedGet.mockResolvedValueOnce({
        data: { total: 5, page: 1, page_size: 50, items: infoItems },
      })

      const store = useSectorStore()

      // 记录 constituentBrowse 和 klineBrowse 初始状态
      const constituentBefore = { ...store.constituentBrowse }
      const klineBefore = { ...store.klineBrowse }

      // 修改 infoBrowse
      await store.fetchSectorInfoBrowse()

      // infoBrowse 已更新
      expect(store.infoBrowse.items).toEqual(infoItems)
      expect(store.infoBrowse.total).toBe(5)

      // constituentBrowse 和 klineBrowse 不受影响
      expect(store.constituentBrowse.items).toEqual(constituentBefore.items)
      expect(store.constituentBrowse.total).toBe(constituentBefore.total)
      expect(store.constituentBrowse.page).toBe(constituentBefore.page)
      expect(store.constituentBrowse.loading).toBe(constituentBefore.loading)
      expect(store.constituentBrowse.error).toBe(constituentBefore.error)

      expect(store.klineBrowse.items).toEqual(klineBefore.items)
      expect(store.klineBrowse.total).toBe(klineBefore.total)
      expect(store.klineBrowse.page).toBe(klineBefore.page)
      expect(store.klineBrowse.loading).toBe(klineBefore.loading)
      expect(store.klineBrowse.error).toBe(klineBefore.error)
    })

    it('切换标签页不清空其他标签页的数据', async () => {
      const infoItems = [makeSectorInfoItem({ sector_code: 'BK0001' })]
      mockedGet.mockResolvedValueOnce({
        data: { total: 5, page: 1, page_size: 50, items: infoItems },
      })

      const store = useSectorStore()
      await store.fetchSectorInfoBrowse()

      // 切换到 constituent 标签页
      store.setBrowserTab('constituent')
      expect(store.browserActiveTab).toBe('constituent')

      // infoBrowse 数据仍然保留
      expect(store.infoBrowse.items).toEqual(infoItems)
      expect(store.infoBrowse.total).toBe(5)
    })
  })

  // ─── 筛选条件变更时 page 重置为 1 ────────────────────────────────────────

  describe('筛选条件变更时 page 重置为 1', () => {
    it('updateInfoFilters 重置 page 为 1', async () => {
      mockedGet.mockResolvedValue({
        data: { total: 0, page: 1, page_size: 50, items: [] },
      })

      const store = useSectorStore()
      // 先设置 page 为 5
      store.infoBrowse.page = 5
      expect(store.infoBrowse.page).toBe(5)

      // 调用 updateInfoFilters
      store.updateInfoFilters({ sector_type: 'CONCEPT' })

      // page 重置为 1
      expect(store.infoBrowse.page).toBe(1)
      // 筛选条件已更新
      expect(store.infoBrowse.filters.sector_type).toBe('CONCEPT')
    })

    it('updateConstituentFilters 重置 page 为 1', async () => {
      mockedGet.mockResolvedValue({
        data: { total: 0, page: 1, page_size: 50, items: [] },
      })

      const store = useSectorStore()
      store.constituentBrowse.page = 3
      store.updateConstituentFilters({ sector_code: 'BK0001' })

      expect(store.constituentBrowse.page).toBe(1)
      expect(store.constituentBrowse.filters.sector_code).toBe('BK0001')
    })

    it('updateKlineFilters 重置 page 为 1', async () => {
      mockedGet.mockResolvedValue({
        data: { total: 0, page: 1, page_size: 50, items: [] },
      })

      const store = useSectorStore()
      store.klineBrowse.page = 4
      store.updateKlineFilters({ freq: '1w' })

      expect(store.klineBrowse.page).toBe(1)
      expect(store.klineBrowse.filters.freq).toBe('1w')
    })
  })
})
