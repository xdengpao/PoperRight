/**
 * PreviewTable 增强功能单元测试
 *
 * 测试数值精度规则和格式化函数：
 * - 价格字段 2 位小数
 * - 成交量字段整数显示
 * - 大数值千分位分隔符
 * - 整数值不添加小数位
 * - 未知字段默认 4 位小数
 *
 * 需求: 6.1-6.8, 7.2-7.3
 */
import { describe, it, expect } from 'vitest'
import {
  formatCell,
  getFieldPrecision,
  PRECISION_RULES,
  DEFAULT_PRECISION,
} from '@/components/PreviewTable.vue'

describe('PreviewTable 增强功能', () => {
  // ── test_format_cell_price_precision ─────────────────────────────────────

  /**
   * 价格字段 2 位小数
   * Validates: Requirements 6.1
   */
  describe('test_format_cell_price_precision', () => {
    it('open 字段浮点数显示 2 位小数', () => {
      expect(formatCell(10.5678, 'number', 'open')).toBe('10.57')
    })

    it('close 字段浮点数显示 2 位小数', () => {
      expect(formatCell(25.1, 'number', 'close')).toBe('25.10')
    })

    it('high 字段浮点数显示 2 位小数', () => {
      expect(formatCell(99.999, 'number', 'high')).toBe('100.00')
    })

    it('low 字段浮点数显示 2 位小数', () => {
      expect(formatCell(3.14159, 'number', 'low')).toBe('3.14')
    })

    it('price 字段浮点数显示 2 位小数', () => {
      expect(formatCell(50.123, 'number', 'price')).toBe('50.12')
    })

    it('avg_price 字段浮点数显示 2 位小数', () => {
      expect(formatCell(88.8888, 'number', 'avg_price')).toBe('88.89')
    })

    it('amount 字段浮点数显示 2 位小数', () => {
      expect(formatCell(1234.567, 'number', 'amount')).toBe('1234.57')
    })

    it('getFieldPrecision 对价格类字段返回 2', () => {
      expect(getFieldPrecision('open')).toBe(2)
      expect(getFieldPrecision('close')).toBe(2)
      expect(getFieldPrecision('high')).toBe(2)
      expect(getFieldPrecision('low')).toBe(2)
      expect(getFieldPrecision('price')).toBe(2)
      expect(getFieldPrecision('avg_price')).toBe(2)
    })
  })

  // ── test_format_cell_volume_integer ──────────────────────────────────────

  /**
   * 成交量字段整数显示
   * Validates: Requirements 6.4
   */
  describe('test_format_cell_volume_integer', () => {
    it('vol 字段整数值直接显示为整数', () => {
      expect(formatCell(5000, 'number', 'vol')).toBe('5000')
    })

    it('volume 字段整数值直接显示为整数', () => {
      expect(formatCell(123456, 'number', 'volume')).toBe('123,456')
    })

    it('vol 字段浮点数显示 0 位小数', () => {
      expect(formatCell(5000.789, 'number', 'vol')).toBe('5001')
    })

    it('volume 字段浮点数显示 0 位小数', () => {
      expect(formatCell(999.5, 'number', 'volume')).toBe('1000')
    })

    it('getFieldPrecision 对成交量字段返回 0', () => {
      expect(getFieldPrecision('vol')).toBe(0)
      expect(getFieldPrecision('volume')).toBe(0)
    })
  })

  // ── test_format_cell_large_number_with_commas ───────────────────────────

  /**
   * 大数值千分位分隔符
   * Validates: Requirements 7.3
   */
  describe('test_format_cell_large_number_with_commas', () => {
    it('整数 >= 10000 添加千分位分隔符', () => {
      expect(formatCell(10000, 'number', 'some_field')).toBe('10,000')
    })

    it('整数 1000000 添加千分位分隔符', () => {
      expect(formatCell(1000000, 'number', 'some_field')).toBe('1,000,000')
    })

    it('浮点数 >= 10000 添加千分位分隔符', () => {
      const result = formatCell(12345.6789, 'number', 'some_field')
      expect(result).toContain(',')
      // 默认精度 4 位小数
      expect(result).toBe('12,345.6789')
    })

    it('负数大数值也添加千分位分隔符', () => {
      const result = formatCell(-50000, 'number', 'some_field')
      expect(result).toContain(',')
    })

    it('价格类大数值添加千分位分隔符', () => {
      const result = formatCell(12345.67, 'number', 'amount')
      expect(result).toContain(',')
      expect(result).toBe('12,345.67')
    })

    it('小数值 (< 10000) 不添加千分位分隔符', () => {
      const result = formatCell(9999.1234, 'number', 'some_field')
      expect(result).not.toContain(',')
    })
  })

  // ── test_format_cell_integer_no_decimals ────────────────────────────────

  /**
   * 整数值不添加小数位
   * Validates: Requirements 6.8
   */
  describe('test_format_cell_integer_no_decimals', () => {
    it('小整数直接显示为整数', () => {
      expect(formatCell(42, 'number', 'some_field')).toBe('42')
    })

    it('整数 0 直接显示', () => {
      expect(formatCell(0, 'number', 'some_field')).toBe('0')
    })

    it('负整数直接显示', () => {
      expect(formatCell(-100, 'number', 'some_field')).toBe('-100')
    })

    it('整数 1 直接显示', () => {
      expect(formatCell(1, 'number', 'some_field')).toBe('1')
    })

    it('整数不会被添加 .0000 后缀', () => {
      const result = formatCell(500, 'number', 'some_field')
      expect(result).not.toContain('.')
    })

    it('大整数显示千分位但无小数', () => {
      const result = formatCell(100000, 'number', 'some_field')
      expect(result).toBe('100,000')
      expect(result).not.toContain('.')
    })
  })

  // ── test_format_cell_default_precision ──────────────────────────────────

  /**
   * 未知字段 4 位小数
   * Validates: Requirements 6.7
   */
  describe('test_format_cell_default_precision', () => {
    it('未知字段浮点数显示 4 位小数', () => {
      expect(formatCell(3.14159265, 'number', 'ts_code_ratio')).toBe('3.1416')
    })

    it('未知字段名 trade_date_val 使用默认精度', () => {
      expect(formatCell(1.1, 'number', 'some_unknown_metric')).toBe('1.1000')
    })

    it('未知字段名 industry_score 使用默认精度', () => {
      expect(formatCell(0.123456, 'number', 'industry_score')).toBe('0.1235')
    })

    it('getFieldPrecision 对未知字段返回 DEFAULT_PRECISION (4)', () => {
      expect(getFieldPrecision('ts_code')).toBe(DEFAULT_PRECISION)
      expect(getFieldPrecision('trade_date')).toBe(DEFAULT_PRECISION)
      expect(getFieldPrecision('name')).toBe(DEFAULT_PRECISION)
      expect(getFieldPrecision('industry')).toBe(DEFAULT_PRECISION)
    })

    it('DEFAULT_PRECISION 常量值为 4', () => {
      expect(DEFAULT_PRECISION).toBe(4)
    })
  })

  // ── 边界情况 ────────────────────────────────────────────────────────────

  describe('formatCell 边界情况', () => {
    it('null 值显示为 —', () => {
      expect(formatCell(null, 'number', 'open')).toBe('—')
    })

    it('undefined 值显示为 —', () => {
      expect(formatCell(undefined, 'number', 'open')).toBe('—')
    })

    it('字符串类型直接转为字符串', () => {
      expect(formatCell('hello', 'string', 'name')).toBe('hello')
    })

    it('非 number 类型的数值不做精度格式化', () => {
      expect(formatCell(42, 'string', 'open')).toBe('42')
    })
  })
})
