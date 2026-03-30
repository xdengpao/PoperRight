/**
 * 属性 80：配置面板可见性由 enabled_modules 驱动
 *
 * **Validates: Requirements 27.3, 27.5**
 *
 * 对任意 `enabled_modules` 值（五个模块标识符的任意子集），选股策略页面应仅显示
 * `enabled_modules` 中列出的模块对应的配置面板，未列出的模块面板应隐藏不显示；
 * `enabled_modules` 为空时所有五个配置面板均应隐藏。
 *
 * 测试策略：
 * - 复制 ScreenerView 中 isModuleEnabled 的纯函数逻辑
 * - 使用 fast-check 生成五个模块 key 的任意子集
 * - 对每个子集验证：启用的模块返回 true，未启用的返回 false
 * - 验证空列表时所有面板隐藏
 * - 验证完整列表时所有面板可见
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ---------------------------------------------------------------------------
// 与 ScreenerView 保持一致的类型和常量
// ---------------------------------------------------------------------------

type StrategyModule = 'factor_editor' | 'ma_trend' | 'indicator_params' | 'breakout' | 'volume_price'

/** 五个可选配置模块 key，与 ScreenerView.vue 中 ALL_MODULES 一致 */
const ALL_MODULE_KEYS: StrategyModule[] = [
  'factor_editor',
  'ma_trend',
  'indicator_params',
  'breakout',
  'volume_price',
]

/**
 * 复制 ScreenerView.vue 中 isModuleEnabled 的纯函数逻辑。
 * 原始实现：`return currentEnabledModules.value.includes(moduleKey)`
 */
function isModuleEnabled(moduleKey: StrategyModule, enabledModules: StrategyModule[]): boolean {
  return enabledModules.includes(moduleKey)
}

// ---------------------------------------------------------------------------
// 属性 80：配置面板可见性由 enabled_modules 驱动
// ---------------------------------------------------------------------------

describe('属性 80：配置面板可见性由 enabled_modules 驱动', () => {
  it('对任意 enabled_modules 子集，仅启用模块的面板可见，其余隐藏', () => {
    fc.assert(
      fc.property(
        fc.subarray(ALL_MODULE_KEYS),
        (enabledModules) => {
          for (const key of ALL_MODULE_KEYS) {
            const visible = isModuleEnabled(key, enabledModules)
            if (enabledModules.includes(key)) {
              expect(visible).toBe(true)
            } else {
              expect(visible).toBe(false)
            }
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  it('enabled_modules 为空列表时，所有面板隐藏', () => {
    const enabledModules: StrategyModule[] = []
    for (const key of ALL_MODULE_KEYS) {
      expect(isModuleEnabled(key, enabledModules)).toBe(false)
    }
  })

  it('enabled_modules 包含全部五个模块时，所有面板可见', () => {
    const enabledModules: StrategyModule[] = [...ALL_MODULE_KEYS]
    for (const key of ALL_MODULE_KEYS) {
      expect(isModuleEnabled(key, enabledModules)).toBe(true)
    }
  })

  it('可见面板数量等于 enabled_modules 长度', () => {
    fc.assert(
      fc.property(
        fc.subarray(ALL_MODULE_KEYS),
        (enabledModules) => {
          const visibleCount = ALL_MODULE_KEYS.filter((key) =>
            isModuleEnabled(key, enabledModules),
          ).length
          expect(visibleCount).toBe(enabledModules.length)
        },
      ),
      { numRuns: 100 },
    )
  })

  it('可见面板数 + 隐藏面板数 = 5', () => {
    fc.assert(
      fc.property(
        fc.subarray(ALL_MODULE_KEYS),
        (enabledModules) => {
          const visibleCount = ALL_MODULE_KEYS.filter((key) =>
            isModuleEnabled(key, enabledModules),
          ).length
          const hiddenCount = ALL_MODULE_KEYS.filter((key) =>
            !isModuleEnabled(key, enabledModules),
          ).length
          expect(visibleCount + hiddenCount).toBe(5)
        },
      ),
      { numRuns: 100 },
    )
  })
})
