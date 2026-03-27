import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import LoginView from '../LoginView.vue'

// Mock the auth store's login method
const mockLogin = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    isAuthenticated: false,
    role: 'READONLY',
    token: null,
    user: null,
  }),
}))

function createTestRouter(initialRoute = '/login') {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'Login', component: LoginView },
      { path: '/dashboard', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/custom', name: 'Custom', component: { template: '<div>Custom</div>' } },
      { path: '/register', name: 'Register', component: { template: '<div>Register</div>' } },
    ],
  })
}

function mountLoginView(router: ReturnType<typeof createTestRouter>) {
  return mount(LoginView, {
    global: {
      plugins: [createPinia(), router],
    },
  })
}

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockLogin.mockReset()
  })

  it('渲染登录表单：用户名、密码输入框和登录按钮', () => {
    const router = createTestRouter()
    const wrapper = mountLoginView(router)

    expect(wrapper.find('#username').exists()).toBe(true)
    expect(wrapper.find('#password').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('A股量化选股系统')
  })

  it('登录按钮在用户名或密码为空时禁用', () => {
    const router = createTestRouter()
    const wrapper = mountLoginView(router)

    const button = wrapper.find('button[type="submit"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('登录成功后跳转至主页面', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    const wrapper = mountLoginView(router)

    await wrapper.find('#username').setValue('testuser')
    await wrapper.find('#password').setValue('TestPass1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockLogin).toHaveBeenCalledWith('testuser', 'TestPass1')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('登录成功后跳转至 redirect 参数指定的页面', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    const router = createTestRouter()
    await router.push('/login?redirect=/custom')
    await router.isReady()
    const wrapper = mountLoginView(router)

    await wrapper.find('#username').setValue('testuser')
    await wrapper.find('#password').setValue('TestPass1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/custom')
  })

  it('登录失败时显示错误提示信息', async () => {
    mockLogin.mockRejectedValueOnce(new Error('用户名或密码错误'))
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    const wrapper = mountLoginView(router)

    await wrapper.find('#username').setValue('baduser')
    await wrapper.find('#password').setValue('WrongPass1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(true)
    expect(wrapper.find('.error-message').text()).toBe('用户名或密码错误')
  })

  it('登录失败时清空密码输入框', async () => {
    mockLogin.mockRejectedValueOnce(new Error('用户名或密码错误'))
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    const wrapper = mountLoginView(router)

    await wrapper.find('#username').setValue('baduser')
    await wrapper.find('#password').setValue('WrongPass1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect((wrapper.find('#password').element as HTMLInputElement).value).toBe('')
  })

  it('包含注册页面链接', () => {
    const router = createTestRouter()
    const wrapper = mountLoginView(router)

    const link = wrapper.find('.register-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/register')
  })
})
