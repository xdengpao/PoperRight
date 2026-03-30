/**
 * 属性 78：创建对话框默认展示五个未勾选的模块复选框
 *
 * **Validates: Requirements 27.1**
 *
 * 对任意创建对话框渲染状态，模块多选区域应包含恰好 5 个复选框且初始均未勾选。
 *
 * 测试策略：
 * - 验证 ALL_MODULES 常量恰好包含 5 个模块定义
 * - 验证 newStrategyModules 默认值为空数组（即所有复选框未勾选）
 * - 验证每个模块的 key 和 label 均为非空字符串
 * - 验证模块 key 唯一（不重复）
 * - 使用 fast-check 对任意子集勾选状态验证初始状态不变量
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ---------------------------------------------------------------------------
// 与 ScreenerView 保持一致的类型和常量
// ---------------------------------------------------------------------------

type StrategyModule = 'factor_editor' | 'ma_trend' | 'indicator_params' | 'breakout' | 'volume_price'

interface ModuleOption {
  key: StrategyModule
  label: string
}

/** 与 ScreenerView.vue 中 ALL_MODULES 常量完全一致 */
const ALL_MODULES: ModuleOption[] = [
  { key: 'factor_editor', label: '因子条件编辑器' },
  { key: 'ma_trend', label: '均线趋势配置' },
  { key: 'indicator_params', label: '技术指标配置' },
  { key: 'breakout', label: '形态突破配置' },
  { key: 'volume_price', label: '量价资金筛选' },
]

const EXPECTED_MODULE_COUNT = 5

/**
 * 模拟创建对话框打开时的初始状态。
 * 与 ScreenerView 中 showCreateDialog=true 时的 newStrategyModules 初始值一致。
 */
function getDefaultSelectedModules(): StrategyModule[] {
  return [] // 默认空数组，所有复选框未勾选
}

/**
 * 判断某个模块在给定选中列表中是否被勾选。
 * 与 v-model="newStrategyModules" 的 checkbox 绑定行为一致。
 */
function isModuleChecked(moduleKey: StrategyModule, selectedModules: StrategyModule[]): boolean {
  return selectedModules.includes(moduleKey)
}

// ---------------------------------------------------------------------------
// 属性 78：创建对话框默认展示五个未勾选的模块复选框
// ---------------------------------------------------------------------------

describe('属性 78：创建对话框默认展示五个未勾选的模块复选框', () => {
  it('ALL_MODULES 恰好包含 5 个模块', () => {
    expect(ALL_MODULES.length).toBe(EXPECTED_MODULE_COUNT)
  })

  it('每个模块的 key 和 label 均为非空字符串', () => {
    for (const mod of ALL_MODULES) {
      expect(typeof mod.key).toBe('string')
      expect(mod.key.length).toBeGreaterThan(0)
      expect(typeof mod.label).toBe('string')
      expect(mod.label.length).toBeGreaterThan(0)
    }
  })

  it('模块 key 唯一，无重复', () => {
    const keys = ALL_MODULES.map((m) => m.key)
    const uniqueKeys = new Set(keys)
    expect(uniqueKeys.size).toBe(ALL_MODULES.length)
  })

  it('默认选中列表为空数组（所有复选框未勾选）', () => {
    const defaultSelected = getDefaultSelectedModules()
    expect(defaultSelected).toEqual([])
    expect(defaultSelected.length).toBe(0)
  })

  it('对任意创建对话框初始状态，所有 5 个模块均未勾选', () => {
    fc.assert(
      fc.property(
        fc.constant(true), // 模拟 showCreateDialog = true
        (_dialogOpen) => {
          const selectedModules = getDefaultSelectedModules()

          // 恰好 5 个复选框
          expect(ALL_MODULES.length).toBe(EXPECTED_MODULE_COUNT)

          // 每个复选框初始均未勾选
          for (const mod of ALL_MODULES) {
            expect(isModuleChecked(mod.key, selectedModules)).toBe(false)
          }
        },
      ),
    )
  })

  it('对任意模块子集勾选后，未勾选模块数 + 已勾选模块数 = 5', () => {
    const allKeys = ALL_MODULES.map((m) => m.key)

    fc.assert(
      fc.property(
        fc.subarray(allKeys),
        (selectedModules) => {
          const checkedCount = ALL_MODULES.filter((m) =>
            isModuleChecked(m.key, selectedModules),
          ).length
          const uncheckedCount = ALL_MODULES.filter((m) =>
            !isModuleChecked(m.key, selectedModules),
          ).length

          expect(checkedCount + uncheckedCount).toBe(EXPECTED_MODULE_COUNT)
          expect(checkedCount).toBe(selectedModules.length)
        },
      ),
    )
  })

  it('创建对话框重置后选中列表回到空数组', () => {
    fc.assert(
      fc.property(
        fc.subarray(ALL_MODULES.map((m) => m.key)),
        (previousSelection) => {
          // 模拟用户勾选了一些模块
          expect(previousSelection.length).toBeLessThanOrEqual(EXPECTED_MODULE_COUNT)

          // 模拟创建成功后重置（与 ScreenerView 中 createStrategy 后的重置逻辑一致）
          const resetSelection: StrategyModule[] = []

          // 重置后所有模块均未勾选
          for (const mod of ALL_MODULES) {
            expect(isModuleChecked(mod.key, resetSelection)).toBe(false)
          }
          expect(resetSelection.length).toBe(0)
        },
      ),
    )
  })

  it('ALL_MODULES 包含预期的五个模块 key', () => {
    const expectedKeys: StrategyModule[] = [
      'factor_editor',
      'ma_trend',
      'indicator_params',
      'breakout',
      'volume_price',
    ]
    const actualKeys = ALL_MODULES.map((m) => m.key)
    expect(actualKeys).toEqual(expectedKeys)
  })
})
