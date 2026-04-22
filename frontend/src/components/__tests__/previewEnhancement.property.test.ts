/**
 * Tushare 数据预览增强 — 前端属性测试
 *
 * 测试增强功能中导出的纯函数：
 * - getFieldPrecision：字段精度规则匹配
 * - formatCell：数值格式化（千分位分隔符）
 * - inferChartType：扩展图表类型推断
 * - getDefaultSelectedColumns：默认图表列选择
 *
 * 使用 fast-check 进行属性测试，每个属性 100 次迭代。
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import {
  getFieldPrecision,
  formatCell,
  PRECISION_RULES,
  DEFAULT_PRECISION,
} from '@/components/PreviewTable.vue'
import {
  inferChartType,
  CHART_TYPE_MAP,
  getDefaultSelectedColumns,
} from '@/stores/tusharePreview'

// ─── 生成器 ───────────────────────────────────────────────────────────────────

/** 生成任意字段名字符串 */
const fieldNameArb = fc.string({ minLength: 0, maxLength: 40 })

/** 已知成交量字段名（匹配 /^(vol|volume)$/i） */
const volumeFieldArb = fc.constantFrom('vol', 'volume', 'Vol', 'Volume', 'VOL', 'VOLUME')

/** 已知价格类字段名（匹配 /(open|high|low|close|price|avg_price|amount)/i） */
const priceFieldArb = fc.constantFrom(
  'open', 'high', 'low', 'close', 'price', 'avg_price', 'amount',
  'pre_close', 'open_price', 'high_price', 'avg_amount',
)

/** 已知涨跌幅类字段名（匹配 /(pct_chg|change)/i） */
const changeFieldArb = fc.constantFrom('pct_chg', 'change', 'pct_chg_rate', 'price_change')

/** 已知换手率类字段名（匹配 /turnover_rate/i） */
const turnoverFieldArb = fc.constantFrom('turnover_rate', 'turnover_rate_f', 'Turnover_Rate')

/** 已知市值类字段名（匹配 /(total_mv|circ_mv|market_cap)/i） */
const marketCapFieldArb = fc.constantFrom('total_mv', 'circ_mv', 'market_cap', 'total_mv_usd')

/** 已知 PE/PB 类字段名（匹配 /^(pe|pb|pe_ttm|ps|ps_ttm)(_|$)/i） */
const pePbFieldArb = fc.constantFrom('pe', 'pb', 'pe_ttm', 'ps', 'ps_ttm', 'pe_', 'pb_ratio')

/** 生成不匹配任何精度规则的字段名 */
const unmatchedFieldArb = fc.constantFrom(
  'ts_code', 'trade_date', 'ann_date', 'name', 'industry',
  'list_date', 'symbol', 'area', 'fullname', 'is_hs',
)

/** 生成随机 targetTable 字符串 */
const targetTableArb = fc.string({ minLength: 1, maxLength: 30 })

/** 生成随机 subcategory 字符串 */
const subcategoryArb = fc.string({ minLength: 1, maxLength: 30 })

/** 生成随机 timeField（string | null） */
const timeFieldArb = fc.option(fc.string({ minLength: 1, maxLength: 20 }), { nil: null })

/** 生成随机字符串数组（用于列名列表） */
const columnListArb = fc.array(fc.string({ minLength: 1, maxLength: 20 }), {
  minLength: 0,
  maxLength: 20,
})

// ─── Property 5: Field precision rule matching ───────────────────────────────

// Feature: tushare-data-preview-enhancement, Property 5: Field precision rule matching
describe('Feature: tushare-data-preview-enhancement, Property 5: Field precision rule matching', () => {
  /**
   * 成交量字段返回 0 位小数
   * **Validates: Requirements 6.4**
   */
  it('成交量字段（vol, volume）返回 0 位小数', () => {
    fc.assert(
      fc.property(volumeFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 价格类字段返回 2 位小数
   * **Validates: Requirements 6.1**
   */
  it('价格类字段返回 2 位小数', () => {
    fc.assert(
      fc.property(priceFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 涨跌幅类字段返回 2 位小数
   * **Validates: Requirements 6.2**
   */
  it('涨跌幅类字段返回 2 位小数', () => {
    fc.assert(
      fc.property(changeFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 换手率类字段返回 2 位小数
   * **Validates: Requirements 6.3**
   */
  it('换手率类字段返回 2 位小数', () => {
    fc.assert(
      fc.property(turnoverFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 市值类字段返回 2 位小数
   * **Validates: Requirements 6.5**
   */
  it('市值类字段返回 2 位小数', () => {
    fc.assert(
      fc.property(marketCapFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * PE/PB 类字段返回 2 位小数
   * **Validates: Requirements 6.6**
   */
  it('PE/PB 类字段返回 2 位小数', () => {
    fc.assert(
      fc.property(pePbFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(2)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 未匹配任何规则的字段返回默认精度 4
   * **Validates: Requirements 6.7**
   */
  it('未匹配任何规则的字段返回默认精度 DEFAULT_PRECISION (4)', () => {
    fc.assert(
      fc.property(unmatchedFieldArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(DEFAULT_PRECISION)
        expect(getFieldPrecision(fieldName)).toBe(4)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 对任意字段名，返回值始终是 PRECISION_RULES 中某个 decimals 或 DEFAULT_PRECISION
   * **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
   */
  it('对任意字段名，返回值始终是已知精度值之一', () => {
    const validDecimals = new Set(PRECISION_RULES.map((r) => r.decimals))
    validDecimals.add(DEFAULT_PRECISION)

    fc.assert(
      fc.property(fieldNameArb, (fieldName) => {
        const precision = getFieldPrecision(fieldName)
        expect(validDecimals.has(precision)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 函数是确定性的：相同输入始终返回相同输出
   * **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
   */
  it('相同字段名始终返回相同精度（确定性）', () => {
    fc.assert(
      fc.property(fieldNameArb, (fieldName) => {
        expect(getFieldPrecision(fieldName)).toBe(getFieldPrecision(fieldName))
      }),
      { numRuns: 100 },
    )
  })
})

// ─── Property 6: Large number formatting includes thousand separators ────────

// Feature: tushare-data-preview-enhancement, Property 6: Large number formatting includes thousand separators
describe('Feature: tushare-data-preview-enhancement, Property 6: Large number formatting includes thousand separators', () => {
  /**
   * |value| >= 10000 的浮点数格式化结果包含逗号（千分位分隔符）
   * **Validates: Requirements 7.3**
   */
  it('|value| >= 10000 的浮点数格式化结果包含逗号', () => {
    // 生成绝对值 >= 10000 的浮点数（非整数）
    const largeFloatArb = fc.oneof(
      fc.double({ min: 10000.01, max: 1e12, noNaN: true, noDefaultInfinity: true }),
      fc.double({ min: -1e12, max: -10000.01, noNaN: true, noDefaultInfinity: true }),
    )

    fc.assert(
      fc.property(largeFloatArb, (value) => {
        // 使用不匹配任何精度规则的字段名，type='number'
        const result = formatCell(value, 'number', 'some_unknown_field')
        expect(result).toContain(',')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * |value| >= 10000 的整数格式化结果包含逗号（千分位分隔符）
   * **Validates: Requirements 7.3**
   */
  it('|value| >= 10000 的整数格式化结果包含逗号', () => {
    const largeIntArb = fc.oneof(
      fc.integer({ min: 10000, max: 1_000_000_000 }),
      fc.integer({ min: -1_000_000_000, max: -10000 }),
    )

    fc.assert(
      fc.property(largeIntArb, (value) => {
        const result = formatCell(value, 'number', 'some_unknown_field')
        expect(result).toContain(',')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * |value| < 10000 的浮点数格式化结果不包含逗号
   * **Validates: Requirements 7.3**
   */
  it('|value| < 10000 的浮点数格式化结果不包含逗号', () => {
    const smallFloatArb = fc.double({
      min: -9999.99,
      max: 9999.99,
      noNaN: true,
      noDefaultInfinity: true,
    }).filter((v) => !Number.isInteger(v) && Number.isFinite(v))

    fc.assert(
      fc.property(smallFloatArb, (value) => {
        const result = formatCell(value, 'number', 'some_unknown_field')
        expect(result).not.toContain(',')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * |value| < 10000 的整数格式化结果不包含逗号
   * **Validates: Requirements 7.3**
   */
  it('|value| < 10000 的整数格式化结果不包含逗号', () => {
    const smallIntArb = fc.integer({ min: -9999, max: 9999 })

    fc.assert(
      fc.property(smallIntArb, (value) => {
        const result = formatCell(value, 'number', 'some_unknown_field')
        expect(result).not.toContain(',')
      }),
      { numRuns: 100 },
    )
  })
})

// ─── Property 7: Expanded chart type inference follows priority rules ────────

// Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules
describe('Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules', () => {
  const chartTypeMapKeys = [...CHART_TYPE_MAP.keys()]
  const chartTypeMapKeysSet = new Set(chartTypeMapKeys)

  /**
   * 优先级 1：KLINE_TABLES 中的表始终返回 candlestick
   * **Validates: Requirements 9.1**
   */
  it('targetTable 为 kline/sector_kline 时始终返回 candlestick（最高优先级）', () => {
    const klineTableArb = fc.constantFrom('kline', 'sector_kline')

    fc.assert(
      fc.property(klineTableArb, subcategoryArb, timeFieldArb, (targetTable, subcategory, timeField) => {
        expect(inferChartType(targetTable, subcategory, timeField)).toBe('candlestick')
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 优先级 2：非 K 线表 + subcategory 在 CHART_TYPE_MAP 中 → 对应映射类型
   * **Validates: Requirements 9.3**
   */
  it('非 K 线表且 subcategory 在 CHART_TYPE_MAP 中时返回映射类型', () => {
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        fc.constantFrom(...chartTypeMapKeys),
        timeFieldArb,
        (targetTable, subcategory, timeField) => {
          const expected = CHART_TYPE_MAP.get(subcategory)
          expect(inferChartType(targetTable, subcategory, timeField)).toBe(expected)
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 优先级 3：非 K 线表 + subcategory 不在 CHART_TYPE_MAP + timeField 非 null → line
   * **Validates: Requirements 9.3**
   */
  it('非 K 线表且 subcategory 不在 CHART_TYPE_MAP 但有 timeField 时返回 line', () => {
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        subcategoryArb.filter((s) => !chartTypeMapKeysSet.has(s)),
        fc.string({ minLength: 1, maxLength: 20 }),
        (targetTable, subcategory, timeField) => {
          expect(inferChartType(targetTable, subcategory, timeField)).toBe('line')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 优先级 4：非 K 线表 + subcategory 不在 CHART_TYPE_MAP + timeField 为 null → null
   * **Validates: Requirements 9.4**
   */
  it('非 K 线表且 subcategory 不在 CHART_TYPE_MAP 且 timeField 为 null 时返回 null', () => {
    fc.assert(
      fc.property(
        targetTableArb.filter((t) => t !== 'kline' && t !== 'sector_kline'),
        subcategoryArb.filter((s) => !chartTypeMapKeysSet.has(s)),
        (targetTable, subcategory) => {
          expect(inferChartType(targetTable, subcategory, null)).toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * K 线表优先级高于 CHART_TYPE_MAP：kline + 任意 CHART_TYPE_MAP subcategory → candlestick
   * **Validates: Requirements 9.1**
   */
  it('K 线表优先级高于 CHART_TYPE_MAP subcategory', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('kline', 'sector_kline'),
        fc.constantFrom(...chartTypeMapKeys),
        timeFieldArb,
        (targetTable, subcategory, timeField) => {
          expect(inferChartType(targetTable, subcategory, timeField)).toBe('candlestick')
        },
      ),
      { numRuns: 100 },
    )
  })

  /**
   * 结果完全由三个输入决定（确定性）
   * **Validates: Requirements 9.1, 9.3, 9.4**
   */
  it('相同输入始终产生相同输出（确定性）', () => {
    fc.assert(
      fc.property(targetTableArb, subcategoryArb, timeFieldArb, (targetTable, subcategory, timeField) => {
        const result1 = inferChartType(targetTable, subcategory, timeField)
        const result2 = inferChartType(targetTable, subcategory, timeField)
        expect(result1).toBe(result2)
      }),
      { numRuns: 100 },
    )
  })
})

// ─── Property 9: Default chart column selection ──────────────────────────────

// Feature: tushare-data-preview-enhancement, Property 9: Default chart column selection
describe('Feature: tushare-data-preview-enhancement, Property 9: Default chart column selection', () => {
  /**
   * 返回前 min(3, N) 个元素
   * **Validates: Requirements 11.2**
   */
  it('返回前 min(3, N) 个列名', () => {
    fc.assert(
      fc.property(columnListArb, (columns) => {
        const result = getDefaultSelectedColumns(columns)
        const expectedLength = Math.min(3, columns.length)
        expect(result).toHaveLength(expectedLength)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 返回的元素保持原始顺序（是输入的前缀）
   * **Validates: Requirements 11.2**
   */
  it('返回的元素保持原始顺序', () => {
    fc.assert(
      fc.property(columnListArb, (columns) => {
        const result = getDefaultSelectedColumns(columns)
        for (let i = 0; i < result.length; i++) {
          expect(result[i]).toBe(columns[i])
        }
      }),
      { numRuns: 100 },
    )
  })

  /**
   * N >= 3 时恰好选中 3 个列
   * **Validates: Requirements 11.2**
   */
  it('N >= 3 时恰好选中 3 个列', () => {
    const atLeast3Arb = fc.array(fc.string({ minLength: 1, maxLength: 20 }), {
      minLength: 3,
      maxLength: 20,
    })

    fc.assert(
      fc.property(atLeast3Arb, (columns) => {
        const result = getDefaultSelectedColumns(columns)
        expect(result).toHaveLength(3)
        expect(result).toEqual(columns.slice(0, 3))
      }),
      { numRuns: 100 },
    )
  })

  /**
   * N < 3 时选中全部 N 个列
   * **Validates: Requirements 11.2**
   */
  it('N < 3 时选中全部 N 个列', () => {
    const lessThan3Arb = fc.array(fc.string({ minLength: 1, maxLength: 20 }), {
      minLength: 0,
      maxLength: 2,
    })

    fc.assert(
      fc.property(lessThan3Arb, (columns) => {
        const result = getDefaultSelectedColumns(columns)
        expect(result).toHaveLength(columns.length)
        expect(result).toEqual(columns)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 空输入产生空输出
   * **Validates: Requirements 11.2**
   */
  it('空输入产生空输出', () => {
    const result = getDefaultSelectedColumns([])
    expect(result).toEqual([])
    expect(result).toHaveLength(0)
  })
})
