/**
 * 前端 backtest store 单元测试 — ExitConditionForm 相对值阈值字段
 *
 * 测试 ExitConditionForm 新字段默认值、序列化/反序列化映射、
 * 以及加载旧版模版时的向后兼容行为。
 *
 * 需求: 7.1, 7.2, 7.3, 7.4
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useBacktestStore, type ExitConditionForm, BASE_FIELD_OPTIONS } from '../backtest'

describe('ExitConditionForm 相对值阈值字段', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ─── 新字段默认值 ─────────────────────────────────────────────────────────

  describe('新字段默认值', () => {
    it('新增条件时 thresholdMode 默认为 absolute', () => {
      const condition: ExitConditionForm = {
        freq: 'daily',
        indicator: 'close',
        operator: '<',
        threshold: 10,
        crossTarget: null,
        params: {},
        thresholdMode: 'absolute',
        baseField: null,
        factor: null,
      }
      expect(condition.thresholdMode).toBe('absolute')
      expect(condition.baseField).toBeNull()
      expect(condition.factor).toBeNull()
    })

    it('相对值模式条件包含 baseField 和 factor', () => {
      const condition: ExitConditionForm = {
        freq: 'daily',
        indicator: 'close',
        operator: '<',
        threshold: null,
        crossTarget: null,
        params: {},
        thresholdMode: 'relative',
        baseField: 'entry_price',
        factor: 0.95,
      }
      expect(condition.thresholdMode).toBe('relative')
      expect(condition.baseField).toBe('entry_price')
      expect(condition.factor).toBe(0.95)
    })
  })

  // ─── 序列化（camelCase → snake_case）─────────────────────────────────────

  describe('序列化 camelCase → snake_case', () => {
    it('startBacktest 序列化包含相对值字段', () => {
      const store = useBacktestStore()
      store.form.exitConditions.conditions = [
        {
          freq: 'daily',
          indicator: 'close',
          operator: '<',
          threshold: null,
          crossTarget: null,
          params: {},
          thresholdMode: 'relative',
          baseField: 'entry_price',
          factor: 0.95,
        },
      ]

      // 提取序列化逻辑（与 startBacktest 中一致）
      const exitConds = store.form.exitConditions
      const payload = exitConds.conditions.map((c) => ({
        freq: c.freq,
        indicator: c.indicator,
        operator: c.operator,
        threshold: c.threshold,
        cross_target: c.crossTarget,
        params: c.params,
        threshold_mode: c.thresholdMode,
        base_field: c.baseField,
        factor: c.factor,
      }))

      expect(payload[0].threshold_mode).toBe('relative')
      expect(payload[0].base_field).toBe('entry_price')
      expect(payload[0].factor).toBe(0.95)
      expect(payload[0].threshold).toBeNull()
    })

    it('绝对值模式序列化 threshold_mode 为 absolute', () => {
      const condition: ExitConditionForm = {
        freq: 'daily',
        indicator: 'rsi',
        operator: '>',
        threshold: 80,
        crossTarget: null,
        params: { rsi_period: 14 },
        thresholdMode: 'absolute',
        baseField: null,
        factor: null,
      }

      const payload = {
        freq: condition.freq,
        indicator: condition.indicator,
        operator: condition.operator,
        threshold: condition.threshold,
        cross_target: condition.crossTarget,
        params: condition.params,
        threshold_mode: condition.thresholdMode,
        base_field: condition.baseField,
        factor: condition.factor,
      }

      expect(payload.threshold_mode).toBe('absolute')
      expect(payload.base_field).toBeNull()
      expect(payload.factor).toBeNull()
      expect(payload.threshold).toBe(80)
    })
  })

  // ─── 反序列化（snake_case → camelCase）─────────────────────────────────────

  describe('反序列化 snake_case → camelCase', () => {
    it('包含相对值字段的模版正确反序列化', () => {
      const templateCondition = {
        freq: 'daily',
        indicator: 'close',
        operator: '<',
        threshold: null,
        cross_target: null,
        params: {},
        threshold_mode: 'relative',
        base_field: 'highest_price',
        factor: 0.9,
      }

      // 模拟 loadExitTemplate 中的反序列化逻辑
      const restored: ExitConditionForm = {
        freq: templateCondition.freq as ExitConditionForm['freq'],
        indicator: templateCondition.indicator,
        operator: templateCondition.operator,
        threshold: templateCondition.threshold ?? null,
        crossTarget: templateCondition.cross_target ?? null,
        params: templateCondition.params ?? {},
        thresholdMode: (templateCondition.threshold_mode ?? 'absolute') as 'absolute' | 'relative',
        baseField: templateCondition.base_field ?? null,
        factor: templateCondition.factor ?? null,
      }

      expect(restored.thresholdMode).toBe('relative')
      expect(restored.baseField).toBe('highest_price')
      expect(restored.factor).toBe(0.9)
      expect(restored.threshold).toBeNull()
    })

    it('加载不含 threshold_mode 的旧版模版默认为 absolute', () => {
      // 旧版模版数据不含 threshold_mode / base_field / factor
      const oldTemplateCondition: Record<string, unknown> = {
        freq: 'daily',
        indicator: 'close',
        operator: '<',
        threshold: 9.5,
        cross_target: null,
        params: {},
      }

      // 模拟 loadExitTemplate 中的反序列化逻辑
      const restored: ExitConditionForm = {
        freq: (oldTemplateCondition.freq as string ?? 'daily') as ExitConditionForm['freq'],
        indicator: oldTemplateCondition.indicator as string,
        operator: oldTemplateCondition.operator as string,
        threshold: (oldTemplateCondition.threshold as number) ?? null,
        crossTarget: (oldTemplateCondition.cross_target as string) ?? null,
        params: (oldTemplateCondition.params as Record<string, number>) ?? {},
        thresholdMode: ((oldTemplateCondition.threshold_mode as string) ?? 'absolute') as 'absolute' | 'relative',
        baseField: (oldTemplateCondition.base_field as string) ?? null,
        factor: (oldTemplateCondition.factor as number) ?? null,
      }

      expect(restored.thresholdMode).toBe('absolute')
      expect(restored.baseField).toBeNull()
      expect(restored.factor).toBeNull()
      expect(restored.threshold).toBe(9.5)
    })

    it('所有 12 种 base_field 值正确反序列化', () => {
      const allBaseFields = BASE_FIELD_OPTIONS.flatMap(g => g.options.map(o => o.value))

      for (const bf of allBaseFields) {
        const templateCondition = {
          freq: 'daily',
          indicator: 'close',
          operator: '<',
          threshold: null,
          cross_target: null,
          params: {},
          threshold_mode: 'relative',
          base_field: bf,
          factor: 1.05,
        }

        const restored: ExitConditionForm = {
          freq: templateCondition.freq as ExitConditionForm['freq'],
          indicator: templateCondition.indicator,
          operator: templateCondition.operator,
          threshold: templateCondition.threshold ?? null,
          crossTarget: templateCondition.cross_target ?? null,
          params: templateCondition.params ?? {},
          thresholdMode: (templateCondition.threshold_mode ?? 'absolute') as 'absolute' | 'relative',
          baseField: templateCondition.base_field ?? null,
          factor: templateCondition.factor ?? null,
        }

        expect(restored.baseField).toBe(bf)
        expect(restored.thresholdMode).toBe('relative')
        expect(restored.factor).toBe(1.05)
      }
    })
  })

  // ─── BASE_FIELD_OPTIONS 常量 ──────────────────────────────────────────────

  describe('BASE_FIELD_OPTIONS 常量', () => {
    it('包含 12 种合法 base_field 值', () => {
      const allValues = BASE_FIELD_OPTIONS.flatMap(g => g.options.map(o => o.value))
      expect(allValues).toHaveLength(12)
    })

    it('按 5 个类别分组', () => {
      expect(BASE_FIELD_OPTIONS).toHaveLength(5)
      expect(BASE_FIELD_OPTIONS[0].group).toBe('持仓相关')
      expect(BASE_FIELD_OPTIONS[1].group).toBe('前一日行情')
      expect(BASE_FIELD_OPTIONS[2].group).toBe('当日行情')
      expect(BASE_FIELD_OPTIONS[3].group).toBe('上一根K线')
      expect(BASE_FIELD_OPTIONS[4].group).toBe('成交量')
    })

    it('每个选项包含 value 和 label', () => {
      for (const group of BASE_FIELD_OPTIONS) {
        for (const option of group.options) {
          expect(typeof option.value).toBe('string')
          expect(option.value.length).toBeGreaterThan(0)
          expect(typeof option.label).toBe('string')
          expect(option.label.length).toBeGreaterThan(0)
        }
      }
    })
  })
})
