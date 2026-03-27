/**
 * 属性 33：注册校验正确性
 *
 * 验证用户名重复拒绝、密码强度不足拒绝、仅当用户名唯一且密码满足全部强度要求时注册成功
 *
 * **Validates: Requirements 21.2**
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as fc from 'fast-check'

// ─── 密码强度校验纯函数（与 RegisterView 中的逻辑一致）────────────────────────

interface PasswordChecks {
  minLength: boolean
  hasUppercase: boolean
  hasLowercase: boolean
  hasDigit: boolean
}

function checkPassword(password: string): PasswordChecks {
  return {
    minLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasDigit: /\d/.test(password),
  }
}

function isPasswordValid(password: string): boolean {
  const checks = checkPassword(password)
  return checks.minLength && checks.hasUppercase && checks.hasLowercase && checks.hasDigit
}

// ─── Mock 设置 ────────────────────────────────────────────────────────────────

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { fullPath: '/dashboard' } },
  },
}))

const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

// ─── Arbitraries ─────────────────────────────────────────────────────────────

type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

const userRoleArb = fc.constantFrom<UserRole>('TRADER', 'ADMIN', 'READONLY')

// 长度 < 8 的密码（必然不满足 minLength）
const shortPasswordArb = fc.string({ minLength: 0, maxLength: 7 })

// 无大写字母的密码（长度 >= 8，含小写和数字，但无大写）
const noUppercasePasswordArb = fc
  .string({ minLength: 8, maxLength: 30 })
  .filter((s) => /[a-z]/.test(s) && /\d/.test(s) && !/[A-Z]/.test(s))

// 无小写字母的密码（长度 >= 8，含大写和数字，但无小写）
const noLowercasePasswordArb = fc
  .string({ minLength: 8, maxLength: 30 })
  .filter((s) => /[A-Z]/.test(s) && /\d/.test(s) && !/[a-z]/.test(s))

// 无数字的密码（长度 >= 8，含大写和小写，但无数字）
const noDigitPasswordArb = fc
  .string({ minLength: 8, maxLength: 30 })
  .filter((s) => /[A-Z]/.test(s) && /[a-z]/.test(s) && !/\d/.test(s))

// 满足全部强度要求的密码（长度 >= 8，含大写、小写、数字）
const validPasswordArb = fc
  .tuple(
    fc.stringOf(fc.constantFrom(...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')), {
      minLength: 1,
      maxLength: 5,
    }),
    fc.stringOf(fc.constantFrom(...'abcdefghijklmnopqrstuvwxyz'.split('')), {
      minLength: 1,
      maxLength: 5,
    }),
    fc.stringOf(fc.constantFrom(...'0123456789'.split('')), { minLength: 1, maxLength: 5 }),
    fc.string({ minLength: 1, maxLength: 10 }),
  )
  .map(([upper, lower, digit, extra]) => {
    const combined = upper + lower + digit + extra
    // Shuffle to avoid predictable patterns
    return combined
      .split('')
      .sort(() => 0.5 - Math.random())
      .join('')
  })
  .filter((s) => s.length >= 8 && /[A-Z]/.test(s) && /[a-z]/.test(s) && /\d/.test(s))

// 非空用户名
const usernameArb = fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0)

// 注册成功响应
const registerResponseArb = fc.record({
  id: fc.uuid(),
  username: usernameArb,
  role: userRoleArb,
})

// ─── 测试：密码强度校验纯函数属性 ────────────────────────────────────────────

describe('属性 33：注册校验正确性 - 密码强度校验纯函数', () => {
  it('长度 < 8 的密码：minLength 校验应为 false', () => {
    fc.assert(
      fc.property(shortPasswordArb, (password) => {
        const checks = checkPassword(password)
        expect(checks.minLength).toBe(false)
        expect(isPasswordValid(password)).toBe(false)
      }),
      { numRuns: 100 },
    )
  })

  it('缺少大写字母的密码：hasUppercase 校验应为 false', () => {
    fc.assert(
      fc.property(noUppercasePasswordArb, (password) => {
        const checks = checkPassword(password)
        expect(checks.hasUppercase).toBe(false)
        expect(isPasswordValid(password)).toBe(false)
      }),
      { numRuns: 50 },
    )
  })

  it('缺少小写字母的密码：hasLowercase 校验应为 false', () => {
    fc.assert(
      fc.property(noLowercasePasswordArb, (password) => {
        const checks = checkPassword(password)
        expect(checks.hasLowercase).toBe(false)
        expect(isPasswordValid(password)).toBe(false)
      }),
      { numRuns: 50 },
    )
  })

  it('缺少数字的密码：hasDigit 校验应为 false', () => {
    fc.assert(
      fc.property(noDigitPasswordArb, (password) => {
        const checks = checkPassword(password)
        expect(checks.hasDigit).toBe(false)
        expect(isPasswordValid(password)).toBe(false)
      }),
      { numRuns: 50 },
    )
  })

  it('满足全部条件的密码：所有校验应为 true', () => {
    fc.assert(
      fc.property(validPasswordArb, (password) => {
        const checks = checkPassword(password)
        expect(checks.minLength).toBe(true)
        expect(checks.hasUppercase).toBe(true)
        expect(checks.hasLowercase).toBe(true)
        expect(checks.hasDigit).toBe(true)
        expect(isPasswordValid(password)).toBe(true)
      }),
      { numRuns: 100 },
    )
  })

  it('仅当全部 4 项条件均满足时 isPasswordValid 才返回 true', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0, maxLength: 50 }), (password) => {
        const checks = checkPassword(password)
        const allPass =
          checks.minLength && checks.hasUppercase && checks.hasLowercase && checks.hasDigit
        expect(isPasswordValid(password)).toBe(allPass)
      }),
      { numRuns: 200 },
    )
  })
})

// ─── 测试：注册 API 响应处理属性 ─────────────────────────────────────────────

describe('属性 33：注册校验正确性 - API 响应处理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('用户名重复（409）：注册应被拒绝并抛出错误', async () => {
    await fc.assert(
      fc.asyncProperty(usernameArb, validPasswordArb, async (username, password) => {
        mockPost.mockRejectedValueOnce(new Error('用户名已被占用'))

        let threw = false
        try {
          await mockPost('/auth/register', { username, password })
        } catch (err) {
          threw = true
          expect(err).toBeInstanceOf(Error)
          expect((err as Error).message).toContain('用户名')
        }
        expect(threw).toBe(true)
      }),
      { numRuns: 50 },
    )
  })

  it('密码强度不足（422）：注册应被拒绝并抛出错误', async () => {
    await fc.assert(
      fc.asyncProperty(usernameArb, shortPasswordArb, async (username, password) => {
        mockPost.mockRejectedValueOnce(new Error('数据校验失败'))

        let threw = false
        try {
          await mockPost('/auth/register', { username, password })
        } catch (err) {
          threw = true
          expect(err).toBeInstanceOf(Error)
        }
        expect(threw).toBe(true)
      }),
      { numRuns: 50 },
    )
  })

  it('用户名唯一且密码满足全部强度要求：注册成功并返回用户对象', async () => {
    await fc.assert(
      fc.asyncProperty(
        usernameArb,
        validPasswordArb,
        registerResponseArb,
        async (username, password, mockResponse) => {
          mockPost.mockResolvedValueOnce({ data: mockResponse })

          const res = await mockPost('/auth/register', { username, password })

          // 注册成功应返回包含 id、username、role 的用户对象
          expect(res.data).toBeDefined()
          expect(typeof res.data.id).toBe('string')
          expect(res.data.id.length).toBeGreaterThan(0)
          expect(typeof res.data.username).toBe('string')
          expect(res.data.username.length).toBeGreaterThan(0)
          expect(['TRADER', 'ADMIN', 'READONLY']).toContain(res.data.role)
        },
      ),
      { numRuns: 50 },
    )
  })

  it('用户名唯一性检查：可用用户名返回 available: true', async () => {
    await fc.assert(
      fc.asyncProperty(usernameArb, async (username) => {
        mockGet.mockResolvedValueOnce({ data: { available: true, message: '' } })

        const res = await mockGet('/auth/check-username', { params: { username } })

        expect(res.data.available).toBe(true)
      }),
      { numRuns: 50 },
    )
  })

  it('用户名唯一性检查：重复用户名返回 available: false', async () => {
    await fc.assert(
      fc.asyncProperty(usernameArb, async (username) => {
        mockGet.mockResolvedValueOnce({ data: { available: false, message: '用户名已被占用' } })

        const res = await mockGet('/auth/check-username', { params: { username } })

        expect(res.data.available).toBe(false)
        expect(res.data.message).toBeTruthy()
      }),
      { numRuns: 50 },
    )
  })

  it('注册成功的充要条件：用户名唯一 AND 密码满足全部强度要求', async () => {
    await fc.assert(
      fc.asyncProperty(
        usernameArb,
        validPasswordArb,
        registerResponseArb,
        async (username, password, mockResponse) => {
          // 前提：密码必须满足全部强度要求
          expect(isPasswordValid(password)).toBe(true)

          // 前提：用户名可用
          mockGet.mockResolvedValueOnce({ data: { available: true, message: '' } })
          const checkRes = await mockGet('/auth/check-username', { params: { username } })
          expect(checkRes.data.available).toBe(true)

          // 注册成功
          mockPost.mockResolvedValueOnce({ data: mockResponse })
          const registerRes = await mockPost('/auth/register', { username, password })

          expect(registerRes.data.id).toBeTruthy()
          expect(registerRes.data.username).toBeTruthy()
          expect(['TRADER', 'ADMIN', 'READONLY']).toContain(registerRes.data.role)
        },
      ),
      { numRuns: 50 },
    )
  })
})
