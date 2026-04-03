/**
 * Feature: local-kline-import, Property: 进度百分比计算
 *
 * 对任意合法的 processed_files 和 total_files 组合，验证进度百分比始终在 [0, 100] 范围内。
 *
 * **Validates: Requirements 11.10**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 纯函数（提取自 LocalImportView.vue 的 progressPct computed） ─────────────

/** 计算导入进度百分比 */
function computeProgressPct(processedFiles: number, totalFiles: number): number {
  if (totalFiles === 0) return 0
  return Math.round((processedFiles / totalFiles) * 100)
}

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('Feature: local-kline-import — 进度百分比计算', () => {
  /**
   * 属性: 进度百分比始终在 [0, 100] 范围内
   * 对任意 processed_files ∈ [0, total_files]，total_files ≥ 0，
   * computeProgressPct 返回值 ∈ [0, 100]。
   * Validates: Requirements 11.10
   */
  it('进度百分比始终在 [0, 100] 范围内', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 100000 }).chain((total) =>
          fc.tuple(
            fc.constant(total),
            fc.integer({ min: 0, max: Math.max(total, 1) }),
          ),
        ),
        ([totalFiles, processedFiles]) => {
          const pct = computeProgressPct(processedFiles, totalFiles)
          expect(pct).toBeGreaterThanOrEqual(0)
          expect(pct).toBeLessThanOrEqual(100)
        },
      ),
      { numRuns: 200 },
    )
  })

  /**
   * 属性: total_files 为 0 时百分比为 0
   * Validates: Requirements 11.10
   */
  it('total_files 为 0 时百分比为 0', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 100000 }), (processedFiles) => {
        expect(computeProgressPct(processedFiles, 0)).toBe(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性: 全部处理完成时百分比为 100
   * Validates: Requirements 11.10
   */
  it('processed_files 等于 total_files 时百分比为 100', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 100000 }), (n) => {
        expect(computeProgressPct(n, n)).toBe(100)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性: 百分比单调递增
   * 对任意 a < b ≤ total，computeProgressPct(a, total) ≤ computeProgressPct(b, total)
   * Validates: Requirements 11.10
   */
  it('百分比随 processed_files 单调递增', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 100000 }).chain((total) =>
          fc.tuple(
            fc.constant(total),
            fc.integer({ min: 0, max: total - 1 }),
            fc.integer({ min: 1, max: total }),
          ),
        ),
        ([total, a, b]) => {
          // ensure a < b
          const lo = Math.min(a, b)
          const hi = Math.max(a, b)
          expect(computeProgressPct(lo, total)).toBeLessThanOrEqual(
            computeProgressPct(hi, total),
          )
        },
      ),
      { numRuns: 200 },
    )
  })

  /**
   * 属性: 百分比始终为整数（Math.round）
   * Validates: Requirements 11.10
   */
  it('百分比始终为整数', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 100000 }).chain((total) =>
          fc.tuple(
            fc.constant(total),
            fc.integer({ min: 0, max: Math.max(total, 1) }),
          ),
        ),
        ([totalFiles, processedFiles]) => {
          const pct = computeProgressPct(processedFiles, totalFiles)
          expect(Number.isInteger(pct)).toBe(true)
        },
      ),
      { numRuns: 100 },
    )
  })
})
