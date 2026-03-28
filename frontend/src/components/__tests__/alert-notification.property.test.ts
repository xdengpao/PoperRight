/**
 * 属性 37：预警通知渲染完整性
 *
 * 验证通知卡片包含预警类型、股票代码、触发原因且均不为空，携带正确跳转链接
 *
 * **Validates: Requirements 21.16**
 */
import { describe, it, expect, beforeEach } from 'vitest'
import * as fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'
import { useAlertStore, type AlertToast, type AlertType, type AlertLevel } from '@/stores/alert'

// ─── 类型常量 ─────────────────────────────────────────────────────────────────

const ALERT_TYPES: AlertType[] = ['SCREEN', 'RISK', 'TRADE', 'SYSTEM']
const ALERT_LEVELS: AlertLevel[] = ['INFO', 'WARNING', 'DANGER']

// 有效的跳转路径前缀（与路由结构一致）
const VALID_LINK_PREFIXES = [
  '/risk',
  '/trade',
  '/positions',
  '/screener',
  '/screener/results',
  '/dashboard',
  '/data',
  '/backtest',
  '/review',
  '/admin',
]

// ─── 生成器 ───────────────────────────────────────────────────────────────────

const alertTypeArb = fc.constantFrom<AlertType>(...ALERT_TYPES)
const alertLevelArb = fc.constantFrom<AlertLevel>(...ALERT_LEVELS)

/** 非空字符串（去除纯空白） */
const nonEmptyStringArb = fc.string({ minLength: 1, maxLength: 100 }).filter(
  (s) => s.trim().length > 0,
)

/** 股票代码生成器（6位数字） */
const symbolArb = fc.stringOf(fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'), {
  minLength: 6,
  maxLength: 6,
})

/** 以 '/' 开头的有效路由路径 */
const linkToArb = fc.constantFrom(...VALID_LINK_PREFIXES)

/** 生成完整的 AlertToast 对象 */
const alertToastArb: fc.Arbitrary<AlertToast> = fc.record({
  id: fc.uuid(),
  type: alertTypeArb,
  symbol: symbolArb,
  message: nonEmptyStringArb,
  level: alertLevelArb,
  created_at: fc.date().map((d) => d.toISOString()),
  link_to: linkToArb,
})

// ─── 测试 ─────────────────────────────────────────────────────────────────────

describe('属性 37：预警通知渲染完整性', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  /**
   * 属性 37a：预警类型（type）为有效的 AlertType 且非空
   * Validates: Requirements 21.16
   */
  it('通知卡片的 type 字段为有效的 AlertType 且非空', () => {
    fc.assert(
      fc.property(alertToastArb, (toast) => {
        const store = useAlertStore()
        store.pushToast(toast)

        const stored = store.toasts[0]
        expect(stored.type).toBeTruthy()
        expect(stored.type.length).toBeGreaterThan(0)
        expect(ALERT_TYPES).toContain(stored.type)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 37b：股票代码（symbol）为非空字符串
   * Validates: Requirements 21.16
   */
  it('通知卡片的 symbol 字段为非空字符串', () => {
    fc.assert(
      fc.property(alertToastArb, (toast) => {
        const store = useAlertStore()
        store.pushToast(toast)

        const stored = store.toasts[0]
        expect(typeof stored.symbol).toBe('string')
        expect(stored.symbol.length).toBeGreaterThan(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 37c：触发原因（message）为非空字符串
   * Validates: Requirements 21.16
   */
  it('通知卡片的 message 字段为非空字符串', () => {
    fc.assert(
      fc.property(alertToastArb, (toast) => {
        const store = useAlertStore()
        store.pushToast(toast)

        const stored = store.toasts[0]
        expect(typeof stored.message).toBe('string')
        expect(stored.message.trim().length).toBeGreaterThan(0)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 37d：跳转链接（link_to）为非空字符串且以 '/' 开头
   * Validates: Requirements 21.16
   */
  it('通知卡片的 link_to 字段为非空字符串且以 / 开头', () => {
    fc.assert(
      fc.property(alertToastArb, (toast) => {
        const store = useAlertStore()
        store.pushToast(toast)

        const stored = store.toasts[0]
        expect(typeof stored.link_to).toBe('string')
        expect(stored.link_to.length).toBeGreaterThan(0)
        expect(stored.link_to.startsWith('/')).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 37e：pushToast 后 store 中保留所有字段且值与输入一致
   * Validates: Requirements 21.16
   */
  it('pushToast 存储的 toast 保留全部字段且值与输入一致', () => {
    fc.assert(
      fc.property(alertToastArb, (toast) => {
        const store = useAlertStore()
        store.pushToast(toast)

        expect(store.toasts).toHaveLength(1)
        const stored = store.toasts[0]
        expect(stored.id).toBe(toast.id)
        expect(stored.type).toBe(toast.type)
        expect(stored.symbol).toBe(toast.symbol)
        expect(stored.message).toBe(toast.message)
        expect(stored.level).toBe(toast.level)
        expect(stored.created_at).toBe(toast.created_at)
        expect(stored.link_to).toBe(toast.link_to)
      }),
      { numRuns: 100 },
    )
  })

  /**
   * 属性 37f：removeToast 正确移除指定 id 的 toast
   * Validates: Requirements 21.16
   */
  it('removeToast 正确移除指定 id 的 toast', () => {
    fc.assert(
      fc.property(
        fc.array(alertToastArb, { minLength: 1, maxLength: 10 }),
        (toasts) => {
          const store = useAlertStore()

          // 确保 id 唯一
          const uniqueToasts = toasts.reduce<AlertToast[]>((acc, t, i) => {
            acc.push({ ...t, id: `${t.id}-${i}` })
            return acc
          }, [])

          for (const t of uniqueToasts) {
            store.pushToast(t)
          }
          expect(store.toasts).toHaveLength(uniqueToasts.length)

          // 移除第一个 toast
          const removeId = uniqueToasts[0].id
          store.removeToast(removeId)

          expect(store.toasts).toHaveLength(uniqueToasts.length - 1)
          expect(store.toasts.find((t) => t.id === removeId)).toBeUndefined()

          // 其余 toast 仍然存在
          for (let i = 1; i < uniqueToasts.length; i++) {
            expect(store.toasts.find((t) => t.id === uniqueToasts[i].id)).toBeDefined()
          }
        },
      ),
      { numRuns: 50 },
    )
  })
})
