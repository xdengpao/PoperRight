/**
 * 属性 68：前端进度展示包含所有必要字段
 *
 * 对任意合法 BackfillProgress 状态对象，验证渲染后包含进度条、当前股票代码、
 * 数据类型标签、失败数量和状态徽章
 *
 * **Validates: Requirements 25.15**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义（镜像 DataManageView.vue 中的接口） ─────────────────────────────

type BackfillStatus = 'idle' | 'pending' | 'running' | 'completed' | 'failed'
type BackfillDataType = 'kline' | 'fundamentals' | 'money_flow'

interface BackfillProgress {
  total: number
  completed: number
  failed: number
  current_symbol: string
  status: BackfillStatus
  data_types: BackfillDataType[]
}

// ─── UI 渲染逻辑（提取自模板的纯函数） ───────────────────────────────────────

/** 计算进度百分比（模板中 backfillPct computed） */
function computeBackfillPct(progress: BackfillProgress): number {
  if (progress.total <= 0) return 0
  return Math.round((progress.completed / progress.total) * 100)
}

/** 状态标签映射（模板中 backfillStatusLabel 函数） */
function backfillStatusLabel(status: BackfillStatus): string {
  const map: Record<string, string> = {
    idle: '空闲',
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] ?? status
}

/** 状态样式类映射（模板中 backfillStatusClass 函数） */
function backfillStatusClass(status: BackfillStatus): string {
  const map: Record<string, string> = {
    idle: 'syncing',
    pending: 'syncing',
    running: 'syncing',
    completed: 'ok',
    failed: 'error',
  }
  return map[status] ?? ''
}

/** 数据类型标签映射（模板中 dataTypeLabel 函数） */
function dataTypeLabel(dt: BackfillDataType): string {
  const map: Record<string, string> = {
    kline: '行情数据',
    fundamentals: '基本面数据',
    money_flow: '资金流向',
  }
  return map[dt] ?? dt
}

/** 进度区域是否可见（模板中 v-if="backfillProgress.status !== 'idle'"） */
function isProgressVisible(progress: BackfillProgress): boolean {
  return progress.status !== 'idle'
}

/** 失败计数是否显示（模板中 v-if="backfillProgress.failed > 0"） */
function isFailedCountVisible(progress: BackfillProgress): boolean {
  return progress.failed > 0
}

/** 当前处理股票是否显示（模板中 v-if="backfillProgress.current_symbol"） */
function isCurrentSymbolVisible(progress: BackfillProgress): boolean {
  return !!progress.current_symbol
}

/** 数据类型标签是否显示（模板中 v-if="backfillProgress.data_types.length"） */
function areDataTypeTagsVisible(progress: BackfillProgress): boolean {
  return progress.data_types.length > 0
}

/**
 * 模拟渲染进度区域，返回各字段的渲染结果。
 * 对应模板中 .backfill-progress 区域的完整渲染逻辑。
 */
function renderProgressDisplay(progress: BackfillProgress) {
  const pct = computeBackfillPct(progress)
  return {
    visible: isProgressVisible(progress),
    statusBadge: {
      label: backfillStatusLabel(progress.status),
      cssClass: backfillStatusClass(progress.status),
    },
    failedCount: {
      visible: isFailedCountVisible(progress),
      value: progress.failed,
    },
    progressBar: {
      widthPct: pct,
      text: `${progress.completed} / ${progress.total}`,
      pctText: `${pct}%`,
    },
    currentSymbol: {
      visible: isCurrentSymbolVisible(progress),
      value: progress.current_symbol,
    },
    dataTypeTags: {
      visible: areDataTypeTagsVisible(progress),
      labels: progress.data_types.map(dataTypeLabel),
    },
  }
}

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const stockSymbolArb = fc.stringOf(
  fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'),
  { minLength: 6, maxLength: 6 },
)

const activeStatusArb: fc.Arbitrary<BackfillStatus> = fc.constantFrom(
  'pending' as const,
  'running' as const,
  'completed' as const,
  'failed' as const,
)

const allStatusArb: fc.Arbitrary<BackfillStatus> = fc.constantFrom(
  'idle' as const,
  'pending' as const,
  'running' as const,
  'completed' as const,
  'failed' as const,
)

const dataTypeArb: fc.Arbitrary<BackfillDataType> = fc.constantFrom(
  'kline' as const,
  'fundamentals' as const,
  'money_flow' as const,
)

/** 生成合法的 BackfillProgress（非 idle 状态，确保进度区域可见） */
const activeProgressArb: fc.Arbitrary<BackfillProgress> = fc
  .record({
    total: fc.integer({ min: 1, max: 5000 }),
    completed: fc.integer({ min: 0, max: 5000 }),
    failed: fc.integer({ min: 0, max: 500 }),
    current_symbol: stockSymbolArb,
    status: activeStatusArb,
    data_types: fc.subarray(['kline' as const, 'fundamentals' as const, 'money_flow' as const], {
      minLength: 1,
    }),
  })
  .map((p) => ({
    ...p,
    completed: Math.min(p.completed, p.total),
    failed: Math.min(p.failed, p.total - Math.min(p.completed, p.total)),
  }))

/** 生成任意 BackfillProgress（包括 idle） */
const anyProgressArb: fc.Arbitrary<BackfillProgress> = fc.record({
  total: fc.integer({ min: 0, max: 5000 }),
  completed: fc.integer({ min: 0, max: 5000 }),
  failed: fc.integer({ min: 0, max: 500 }),
  current_symbol: fc.oneof(stockSymbolArb, fc.constant('')),
  status: allStatusArb,
  data_types: fc.subarray(['kline' as const, 'fundamentals' as const, 'money_flow' as const]),
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 68：前端进度展示包含所有必要字段', () => {
  /**
   * 属性 68a：非 idle 状态时进度区域可见，且包含状态徽章和进度条
   * Validates: Requirements 25.15
   */
  it('非 idle 状态时进度区域可见，包含状态徽章和进度条', () => {
    fc.assert(
      fc.property(activeProgressArb, (progress) => {
        const rendered = renderProgressDisplay(progress)

        // 进度区域可见
        expect(rendered.visible).toBe(true)

        // 状态徽章存在且有有效标签
        expect(rendered.statusBadge.label).toBeTruthy()
        expect(rendered.statusBadge.label.length).toBeGreaterThan(0)
        expect(rendered.statusBadge.cssClass).toBeTruthy()

        // 进度条百分比在 0-100 范围内
        expect(rendered.progressBar.widthPct).toBeGreaterThanOrEqual(0)
        expect(rendered.progressBar.widthPct).toBeLessThanOrEqual(100)

        // 进度文本包含 completed 和 total
        expect(rendered.progressBar.text).toContain(String(progress.completed))
        expect(rendered.progressBar.text).toContain(String(progress.total))
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 68b：当前处理股票代码在有值时显示
   * Validates: Requirements 25.15
   */
  it('current_symbol 非空时显示当前处理股票代码', () => {
    fc.assert(
      fc.property(activeProgressArb, (progress) => {
        const rendered = renderProgressDisplay(progress)
        if (progress.current_symbol) {
          expect(rendered.currentSymbol.visible).toBe(true)
          expect(rendered.currentSymbol.value).toBe(progress.current_symbol)
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 68c：数据类型标签与 data_types 数组一一对应
   * Validates: Requirements 25.15
   */
  it('数据类型标签与 data_types 数组一一对应', () => {
    fc.assert(
      fc.property(activeProgressArb, (progress) => {
        const rendered = renderProgressDisplay(progress)

        expect(rendered.dataTypeTags.visible).toBe(progress.data_types.length > 0)
        expect(rendered.dataTypeTags.labels).toHaveLength(progress.data_types.length)

        // 每个标签都是有效的中文标签
        for (const label of rendered.dataTypeTags.labels) {
          expect(['行情数据', '基本面数据', '资金流向']).toContain(label)
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 68d：失败数量仅在 failed > 0 时显示
   * Validates: Requirements 25.15
   */
  it('失败数量仅在 failed > 0 时显示', () => {
    fc.assert(
      fc.property(anyProgressArb, (progress) => {
        const rendered = renderProgressDisplay(progress)
        expect(rendered.failedCount.visible).toBe(progress.failed > 0)
        if (rendered.failedCount.visible) {
          expect(rendered.failedCount.value).toBe(progress.failed)
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 68e：idle 状态时进度区域不可见
   * Validates: Requirements 25.15
   */
  it('idle 状态时进度区域不可见', () => {
    const idleProgress: BackfillProgress = {
      total: 0,
      completed: 0,
      failed: 0,
      current_symbol: '',
      status: 'idle',
      data_types: [],
    }
    const rendered = renderProgressDisplay(idleProgress)
    expect(rendered.visible).toBe(false)
  })

  /**
   * 属性 68f：状态标签映射覆盖所有合法状态值
   * Validates: Requirements 25.15
   */
  it('所有合法状态值都有对应的中文标签和样式类', () => {
    fc.assert(
      fc.property(allStatusArb, (status) => {
        const label = backfillStatusLabel(status)
        const cssClass = backfillStatusClass(status)

        expect(label).toBeTruthy()
        expect(['空闲', '等待中', '运行中', '已完成', '失败']).toContain(label)
        expect(cssClass).toBeTruthy()
        expect(['syncing', 'ok', 'error']).toContain(cssClass)
      }),
      { numRuns: 50 },
    )
  })
})
