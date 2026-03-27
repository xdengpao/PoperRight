/**
 * 属性 36：角色菜单动态渲染正确性
 *
 * 验证 READONLY 不含交易/持仓菜单，TRADER 不含系统管理菜单，ADMIN 包含全部菜单
 *
 * **Validates: Requirements 21.14**
 */
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: UserRole[]  // 为空表示所有角色可见
  group: '数据' | '选股' | '风控' | '交易' | '分析' | '系统'
}

// ─── 菜单定义（与 MainLayout 保持一致）────────────────────────────────────────

const menuGroups: Record<string, NavItem[]> = {
  '数据': [
    { path: '/dashboard', label: '大盘概况', icon: '📊', group: '数据' },
    { path: '/data', label: '数据管理', icon: '💾', group: '数据' },
  ],
  '选股': [
    { path: '/screener', label: '智能选股', icon: '🔍', group: '选股' },
    { path: '/screener/results', label: '选股结果', icon: '📋', group: '选股' },
  ],
  '风控': [
    { path: '/risk', label: '风险控制', icon: '🛡️', group: '风控' },
  ],
  '交易': [
    { path: '/trade', label: '交易执行', icon: '💹', roles: ['TRADER', 'ADMIN'], group: '交易' },
    { path: '/positions', label: '持仓管理', icon: '💰', roles: ['TRADER', 'ADMIN'], group: '交易' },
  ],
  '分析': [
    { path: '/backtest', label: '策略回测', icon: '📈', group: '分析' },
    { path: '/review', label: '复盘分析', icon: '📝', group: '分析' },
  ],
  '系统': [
    { path: '/admin', label: '系统管理', icon: '⚙️', roles: ['ADMIN'], group: '系统' },
  ],
}

// ─── 被测函数：按角色过滤菜单项 ───────────────────────────────────────────────

/**
 * 根据用户角色过滤菜单项。
 * 没有 roles 限制的菜单项对所有角色可见；
 * 有 roles 限制的菜单项仅对 roles 中包含的角色可见。
 */
function filterMenuByRole(role: UserRole): NavItem[] {
  const allItems = Object.values(menuGroups).flat()
  return allItems.filter((item) => !item.roles || item.roles.includes(role))
}

// ─── 常量：路径分类 ───────────────────────────────────────────────────────────

const TRADE_PATHS = ['/trade', '/positions']
const ADMIN_PATHS = ['/admin']
const PUBLIC_PATHS = ['/dashboard', '/data', '/screener', '/screener/results', '/risk', '/backtest', '/review']
const ALL_PATHS = [...PUBLIC_PATHS, ...TRADE_PATHS, ...ADMIN_PATHS]

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const userRoleArb = fc.constantFrom<UserRole>('TRADER', 'ADMIN', 'READONLY')

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 36：角色菜单动态渲染正确性', () => {
  /**
   * 属性 36a：READONLY 角色不含交易执行和持仓管理入口
   * Validates: Requirements 21.14
   */
  it('READONLY：菜单中不包含 /trade 和 /positions', () => {
    fc.assert(
      fc.property(fc.constant<UserRole>('READONLY'), (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        expect(paths).not.toContain('/trade')
        expect(paths).not.toContain('/positions')
      }),
      { numRuns: 10 },
    )
  })

  /**
   * 属性 36b：TRADER 角色不含系统管理入口
   * Validates: Requirements 21.14
   */
  it('TRADER：菜单中不包含 /admin', () => {
    fc.assert(
      fc.property(fc.constant<UserRole>('TRADER'), (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        expect(paths).not.toContain('/admin')
      }),
      { numRuns: 10 },
    )
  })

  /**
   * 属性 36c：ADMIN 角色包含全部菜单项
   * Validates: Requirements 21.14
   */
  it('ADMIN：菜单包含全部路径（含 /trade、/positions、/admin）', () => {
    fc.assert(
      fc.property(fc.constant<UserRole>('ADMIN'), (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        for (const path of ALL_PATHS) {
          expect(paths).toContain(path)
        }
      }),
      { numRuns: 10 },
    )
  })

  /**
   * 属性 36d：任意角色均可见公共菜单项（无 roles 限制的菜单项）
   * Validates: Requirements 21.14
   */
  it('任意角色：公共菜单项始终可见', () => {
    fc.assert(
      fc.property(userRoleArb, (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        for (const path of PUBLIC_PATHS) {
          expect(paths).toContain(path)
        }
      }),
      { numRuns: 50 },
    )
  })

  /**
   * 属性 36e：有 roles 限制的菜单项仅对匹配角色可见
   * 验证过滤函数的核心逻辑：roles 字段为空则全部可见，否则仅匹配角色可见
   * Validates: Requirements 21.14
   */
  it('有 roles 限制的菜单项仅对匹配角色可见', () => {
    const allItems = Object.values(menuGroups).flat()
    const restrictedItems = allItems.filter((item) => item.roles && item.roles.length > 0)

    fc.assert(
      fc.property(userRoleArb, (role) => {
        const visibleItems = filterMenuByRole(role)
        const visiblePaths = new Set(visibleItems.map((item) => item.path))

        for (const item of restrictedItems) {
          if (item.roles!.includes(role)) {
            // 角色在允许列表中 → 应可见
            expect(visiblePaths.has(item.path)).toBe(true)
          } else {
            // 角色不在允许列表中 → 不应可见
            expect(visiblePaths.has(item.path)).toBe(false)
          }
        }
      }),
      { numRuns: 50 },
    )
  })

  /**
   * 属性 36f：无 roles 限制的菜单项对所有角色均可见
   * Validates: Requirements 21.14
   */
  it('无 roles 限制的菜单项对所有角色均可见', () => {
    const allItems = Object.values(menuGroups).flat()
    const publicItems = allItems.filter((item) => !item.roles || item.roles.length === 0)

    fc.assert(
      fc.property(userRoleArb, (role) => {
        const visibleItems = filterMenuByRole(role)
        const visiblePaths = new Set(visibleItems.map((item) => item.path))

        for (const item of publicItems) {
          expect(visiblePaths.has(item.path)).toBe(true)
        }
      }),
      { numRuns: 50 },
    )
  })

  /**
   * 属性 36g：READONLY 可见公共菜单但不可见受限菜单（交易/持仓/系统管理）
   * Validates: Requirements 21.14
   */
  it('READONLY：仅可见公共菜单，不可见任何受限菜单', () => {
    fc.assert(
      fc.property(fc.constant<UserRole>('READONLY'), (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        // 公共路径全部可见
        for (const path of PUBLIC_PATHS) {
          expect(paths).toContain(path)
        }

        // 受限路径均不可见
        for (const path of [...TRADE_PATHS, ...ADMIN_PATHS]) {
          expect(paths).not.toContain(path)
        }
      }),
      { numRuns: 10 },
    )
  })

  /**
   * 属性 36h：TRADER 可见公共菜单和交易菜单，但不可见系统管理
   * Validates: Requirements 21.14
   */
  it('TRADER：可见公共菜单和交易菜单，不可见系统管理', () => {
    fc.assert(
      fc.property(fc.constant<UserRole>('TRADER'), (role) => {
        const items = filterMenuByRole(role)
        const paths = items.map((item) => item.path)

        // 公共路径全部可见
        for (const path of PUBLIC_PATHS) {
          expect(paths).toContain(path)
        }

        // 交易路径可见
        for (const path of TRADE_PATHS) {
          expect(paths).toContain(path)
        }

        // 系统管理不可见
        for (const path of ADMIN_PATHS) {
          expect(paths).not.toContain(path)
        }
      }),
      { numRuns: 10 },
    )
  })
})
