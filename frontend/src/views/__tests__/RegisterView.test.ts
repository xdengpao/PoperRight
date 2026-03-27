import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import RegisterView from '../RegisterView.vue'

// Mock apiClient
const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/register', name: 'Register', component: RegisterView },
      { path: '/login', name: 'Login', component: { template: '<div>Login</div>' } },
    ],
  })
}

function mountRegisterView(router: ReturnType<typeof createTestRouter>) {
  return mount(RegisterView, {
    global: {
      plugins: [createPinia(), router],
    },
  })
}

describe('RegisterView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
    mockPost.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('渲染注册表单：用户名、密码输入框和注册按钮', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    expect(wrapper.find('#reg-username').exists()).toBe(true)
    expect(wrapper.find('#reg-password').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('创建账号')
  })

  it('显示4条密码强度校验规则', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    const rules = wrapper.findAll('.password-rules li')
    expect(rules.length).toBe(4)
    expect(wrapper.text()).toContain('≥8 位字符')
    expect(wrapper.text()).toContain('包含大写字母')
    expect(wrapper.text()).toContain('包含小写字母')
    expect(wrapper.text()).toContain('包含数字')
  })

  it('密码为空时所有规则显示 ✗', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    const failRules = wrapper.findAll('.rule-fail')
    expect(failRules.length).toBe(4)
  })

  it('密码满足所有条件时所有规则显示 ✓', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    await wrapper.find('#reg-password').setValue('StrongPass1')
    const passRules = wrapper.findAll('.rule-pass')
    expect(passRules.length).toBe(4)
  })

  it('密码部分满足条件时正确显示 ✓ 和 ✗', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    // Only lowercase, no uppercase, no digit, length < 8
    await wrapper.find('#reg-password').setValue('short')
    const passRules = wrapper.findAll('.rule-pass')
    const failRules = wrapper.findAll('.rule-fail')
    // Only hasLowercase should pass
    expect(passRules.length).toBe(1)
    expect(failRules.length).toBe(3)
  })

  it('用户名输入后防抖调用 check-username 接口', async () => {
    mockGet.mockResolvedValue({ data: { available: true, message: '' } })
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    await wrapper.find('#reg-username').setValue('newuser')
    // Trigger input event
    await wrapper.find('#reg-username').trigger('input')

    // Before debounce fires, API should not be called
    expect(mockGet).not.toHaveBeenCalled()

    // Advance timer past debounce (400ms)
    vi.advanceTimersByTime(400)
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/auth/check-username', {
      params: { username: 'newuser' },
    })
  })

  it('用户名可用时显示 ✓', async () => {
    mockGet.mockResolvedValue({ data: { available: true, message: '' } })
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    await wrapper.find('#reg-username').setValue('available_user')
    await wrapper.find('#reg-username').trigger('input')
    vi.advanceTimersByTime(400)
    await flushPromises()

    expect(wrapper.find('.input-status.valid').exists()).toBe(true)
    expect(wrapper.find('.input-status.valid').text()).toBe('✓')
  })

  it('用户名已占用时显示 ✗ 和错误信息', async () => {
    mockGet.mockResolvedValue({ data: { available: false, message: '用户名已被占用' } })
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    await wrapper.find('#reg-username').setValue('taken_user')
    await wrapper.find('#reg-username').trigger('input')
    vi.advanceTimersByTime(400)
    await flushPromises()

    expect(wrapper.find('.input-status.invalid').exists()).toBe(true)
    expect(wrapper.find('.input-status.invalid').text()).toBe('✗')
    expect(wrapper.find('.field-error').text()).toBe('用户名已被占用')
  })

  it('注册按钮在条件不满足时禁用', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    const button = wrapper.find('button[type="submit"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('注册成功后跳转至登录页', async () => {
    mockGet.mockResolvedValue({ data: { available: true, message: '' } })
    mockPost.mockResolvedValue({ data: { id: '1', username: 'newuser', role: 'TRADER' } })
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    // Set username and trigger check
    await wrapper.find('#reg-username').setValue('newuser')
    await wrapper.find('#reg-username').trigger('input')
    vi.advanceTimersByTime(400)
    await flushPromises()

    // Set valid password
    await wrapper.find('#reg-password').setValue('StrongPass1')

    // Submit
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/auth/register', {
      username: 'newuser',
      password: 'StrongPass1',
    })
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('注册失败时显示错误信息', async () => {
    mockGet.mockResolvedValue({ data: { available: true, message: '' } })
    mockPost.mockRejectedValue(new Error('用户名已被占用'))
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    // Set username and trigger check
    await wrapper.find('#reg-username').setValue('newuser')
    await wrapper.find('#reg-username').trigger('input')
    vi.advanceTimersByTime(400)
    await flushPromises()

    // Set valid password
    await wrapper.find('#reg-password').setValue('StrongPass1')

    // Submit
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(true)
    expect(wrapper.find('.error-message').text()).toBe('用户名已被占用')
  })

  it('包含登录页面链接', async () => {
    const router = createTestRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mountRegisterView(router)

    const link = wrapper.find('.login-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/login')
  })
})
