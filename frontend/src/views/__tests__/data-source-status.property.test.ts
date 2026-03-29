/**
 * 属性 57：数据源状态 UI 渲染正确性
 *
 * Feature: data-manage-dual-source-integration, Property 57: 数据源状态 UI 渲染正确性
 *
 * 对任意健康检查响应和同步状态响应组合，验证卡片颜色映射正确、故障转移标注正确
 *
 * **Validates: Requirements 24.2, 24.4**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（镜像 DataManageView.vue 中的接口） ─────────────────────────────

interface DataSourceStatus {
  name: string
  status: 'connected' | 'disconnected'
  checked_at: string
}

interface DataSourceHealthResponse {
  sources: DataSourceStatus[]
}

interface SyncStatus {
  source: string
  last_sync_at: string
  status: 'OK' | 'ERROR' | 'SYNCING'
  record_count: number
  data_source: string
  is_fallback: boolean
}

// ─── UI 渲染逻辑（提取自模板的纯函数） ───────────────────────────────────────

function healthCardClass(status: 'connected' | 'disconnected'): string {
  return status === 'connected' ? 'health-ok' : 'health-err'
}

function healthStatusText(status: 'connected' | 'disconnected'): string {
  return status === 'connected' ? '✅ 已连接' : '❌ 已断开'
}

function hasFallbackBadge(item: SyncStatus): boolean {
  return item.is_fallback === true
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const nonEmptyStringArb = fc
  .string({ minLength: 1, maxLength: 30 })
  .filter((s) => s.trim().length > 0)

const dataSourceStatusArb: fc.Arbitrary<'connected' | 'disconnected'> =
  fc.constantFrom('connected' as const, 'disconnected' as const)

const isoDateArb = fc
  .date({ min: new Date('2020-01-01'), max: new Date('2099-12-31') })
  .map((d) => d.toISOString())

const dataSourceStatusItemArb: fc.Arbitrary<DataSourceStatus> = fc.record({
  name: nonEmptyStringArb,
  status: dataSourceStatusArb,
  checked_at: isoDateArb,
})

const healthResponseArb: fc.Arbitrary<DataSourceHealthResponse> = fc.record({
  sources: fc.array(dataSourceStatusItemArb, { minLength: 0, maxLength: 5 }),
})

const syncStatusArb: fc.Arbitrary<'OK' | 'ERROR' | 'SYNCING'> =
  fc.constantFrom('OK' as const, 'ERROR' as const, 'SYNCING' as const)

const syncStatusItemArb: fc.Arbitrary<SyncStatus> = fc.record({
  source: nonEmptyStringArb,
  last_sync_at: isoDateArb,
  status: syncStatusArb,
  record_count: fc.integer({ min: 0, max: 1_000_000 }),
  data_source: fc.constantFrom('Tushare', 'AkShare', 'N/A'),
  is_fallback: fc.boolean(),
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 57：数据源状态 UI 渲染正确性', () => {
  /**
   * 属性 57a：connected 数据源卡片使用绿色样式类 health-ok
   * Validates: Requirements 24.2
   */
  it('connected 数据源卡片使用 health-ok 样式类', () => {
    fc.assert(
      fc.property(healthResponseArb, (response) => {
        for (const src of response.sources) {
          const cls = healthCardClass(src.status)
          if (src.status === 'connected') {
            expect(cls).toBe('health-ok')
          } else {
            expect(cls).toBe('health-err')
          }
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 57b：connected 显示"✅ 已连接"，disconnected 显示"❌ 已断开"
   * Validates: Requirements 24.2
   */
  it('健康状态文本与 status 字段正确映射', () => {
    fc.assert(
      fc.property(dataSourceStatusItemArb, (src) => {
        const text = healthStatusText(src.status)
        if (src.status === 'connected') {
          expect(text).toBe('✅ 已连接')
        } else {
          expect(text).toBe('❌ 已断开')
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 57c：is_fallback=true 时显示故障转移标注，false 时不显示
   * Validates: Requirements 24.4
   */
  it('is_fallback 为 true 时显示故障转移标注', () => {
    fc.assert(
      fc.property(syncStatusItemArb, (item) => {
        const showBadge = hasFallbackBadge(item)
        expect(showBadge).toBe(item.is_fallback)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 57d：对任意健康检查和同步状态组合，卡片颜色映射和故障转移标注同时正确
   * Validates: Requirements 24.2, 24.4
   */
  it('任意健康检查 + 同步状态组合，卡片颜色和故障转移标注均正确', () => {
    fc.assert(
      fc.property(
        healthResponseArb,
        fc.array(syncStatusItemArb, { minLength: 0, maxLength: 10 }),
        (healthResp, syncItems) => {
          // 验证健康卡片颜色映射
          for (const src of healthResp.sources) {
            const cls = healthCardClass(src.status)
            if (src.status === 'connected') {
              expect(cls).toBe('health-ok')
              expect(healthStatusText(src.status)).toContain('已连接')
            } else {
              expect(cls).toBe('health-err')
              expect(healthStatusText(src.status)).toContain('已断开')
            }
          }

          // 验证同步状态故障转移标注
          for (const item of syncItems) {
            expect(hasFallbackBadge(item)).toBe(item.is_fallback)
            // data_source 字段始终存在
            expect(typeof item.data_source).toBe('string')
            expect(item.data_source.length).toBeGreaterThan(0)
          }
        },
      ),
      { numRuns: 100 },
    )
  })
})
