import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import MainLayout from '../MainLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { useAlertStore } from '@/stores/alert'

// Stub router-link and router-view
const DummyComponent = { template: '<div>page</div>' }

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/dashboard', component: DummyComponent },
      { path: '/data', component: DummyComponent },
      { path: '/screener', component: DummyComponent },
      { path: '/screener/results', component: DummyComponent },
      { path: '/risk', component: DummyComponent },
      { path: '/backtest', component: DummyComponent },
      { path: '/trade', component: DummyComponent },
      { path: '/positions', component: DummyComponent },
      { path: '/review', component: DummyComponent },
      { path: '/admin', component: DummyComponent },
      { path: '/login', component: DummyComponent },
    ],
  })
}

async function mountLayout(role: 'ADMIN' | 'TRADER' | 'READONLY' = 'ADMIN', path = '/dashboard') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  router.push(path)
  await router.isReady()

  const wrapper = mount(MainLayout, {
    global: {
      plugins: [pinia, router],
    },
  })

  const authStore = useAuthStore()
  authStore.user = { id: '1', username: 'testuser', role }

  await wrapper.vm.$nextTick()
  return { wrapper, authStore, alertStore: useAlertStore(), router }
}

describe('MainLayout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('顶部导航栏', () => {
    it('显示系统名称', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.system-name').text()).toBe('A股右侧量化选股系统')
    })

    it('显示用户名', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.user-info').text()).toBe('testuser')
    })

    it('显示用户角色标签 - ADMIN', async () => {
      const { wrapper } = await mountLayout('ADMIN')
      expect(wrapper.find('.user-role-badge').text()).toBe('管理员')
    })

    it('显示用户角色标签 - TRADER', async () => {
      const { wrapper } = await mountLayout('TRADER')
      expect(wrapper.find('.user-role-badge').text()).toBe('交易员')
    })

    it('显示用户角色标签 - READONLY', async () => {
      const { wrapper } = await mountLayout('READONLY')
      expect(wrapper.find('.user-role-badge').text()).toBe('观察员')
    })

    it('显示退出按钮', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.logout-btn').exists()).toBe(true)
    })

    it('显示通知铃铛', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.notification-bell').exists()).toBe(true)
    })
  })

  describe('预警通知铃铛', () => {
    it('无未读时不显示 badge', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.badge').exists()).toBe(false)
    })

    it('有未读时显示 badge 数字', async () => {
      const { wrapper, alertStore } = await mountLayout()
      alertStore.addAlert({
        id: '1', symbol: '000001', message: '测试', level: 'INFO',
        created_at: new Date().toISOString(), read: false,
      })
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.badge').exists()).toBe(true)
      expect(wrapper.find('.badge').text()).toBe('1')
    })

    it('超过99显示99+', async () => {
      const { wrapper, alertStore } = await mountLayout()
      for (let i = 0; i < 100; i++) {
        alertStore.addAlert({
          id: String(i), symbol: '000001', message: '测试', level: 'INFO',
          created_at: new Date().toISOString(), read: false,
        })
      }
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.badge').text()).toBe('99+')
    })

    it('点击铃铛展开通知面板', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.notification-panel').exists()).toBe(false)
      await wrapper.find('.notification-bell').trigger('click')
      expect(wrapper.find('.notification-panel').exists()).toBe(true)
    })

    it('无消息时显示空状态', async () => {
      const { wrapper } = await mountLayout()
      await wrapper.find('.notification-bell').trigger('click')
      expect(wrapper.find('.notification-empty').text()).toBe('暂无预警消息')
    })

    it('有消息时显示预警列表', async () => {
      const { wrapper, alertStore } = await mountLayout()
      alertStore.addAlert({
        id: '1', symbol: '600000', message: '趋势突破', level: 'WARNING',
        created_at: new Date().toISOString(), read: false,
      })
      await wrapper.find('.notification-bell').trigger('click')
      await wrapper.vm.$nextTick()
      const items = wrapper.findAll('.notification-item')
      expect(items.length).toBe(1)
      expect(wrapper.find('.notification-symbol').text()).toBe('600000')
      expect(wrapper.find('.notification-message').text()).toBe('趋势突破')
    })

    it('点击预警项标记为已读', async () => {
      const { wrapper, alertStore } = await mountLayout()
      alertStore.addAlert({
        id: 'a1', symbol: '000001', message: '测试', level: 'INFO',
        created_at: new Date().toISOString(), read: false,
      })
      await wrapper.find('.notification-bell').trigger('click')
      await wrapper.vm.$nextTick()
      await wrapper.find('.notification-item').trigger('click')
      expect(alertStore.alerts[0].read).toBe(true)
      expect(alertStore.unreadCount).toBe(0)
    })
  })

  describe('侧边菜单分组', () => {
    it('ADMIN 角色显示所有分组', async () => {
      const { wrapper } = await mountLayout('ADMIN')
      const groups = wrapper.findAll('.nav-group-label')
      const labels = groups.map((g) => g.text())
      expect(labels).toEqual(['数据', '选股', '风控', '交易', '分析', '系统'])
    })

    it('TRADER 角色不显示系统分组', async () => {
      const { wrapper } = await mountLayout('TRADER')
      const groups = wrapper.findAll('.nav-group-label')
      const labels = groups.map((g) => g.text())
      expect(labels).toContain('交易')
      expect(labels).not.toContain('系统')
    })

    it('READONLY 角色不显示交易和系统分组', async () => {
      const { wrapper } = await mountLayout('READONLY')
      const groups = wrapper.findAll('.nav-group-label')
      const labels = groups.map((g) => g.text())
      expect(labels).not.toContain('交易')
      expect(labels).not.toContain('系统')
      expect(labels).toContain('数据')
      expect(labels).toContain('选股')
      expect(labels).toContain('风控')
      expect(labels).toContain('分析')
    })
  })

  describe('菜单项角色过滤', () => {
    it('ADMIN 看到全部菜单项', async () => {
      const { wrapper } = await mountLayout('ADMIN')
      const links = wrapper.findAll('.nav-link')
      const paths = links.map((l) => l.attributes('href'))
      expect(paths).toContain('/trade')
      expect(paths).toContain('/positions')
      expect(paths).toContain('/admin')
    })

    it('TRADER 看不到系统管理', async () => {
      const { wrapper } = await mountLayout('TRADER')
      const links = wrapper.findAll('.nav-link')
      const paths = links.map((l) => l.attributes('href'))
      expect(paths).toContain('/trade')
      expect(paths).toContain('/positions')
      expect(paths).not.toContain('/admin')
    })

    it('READONLY 看不到交易/持仓/系统管理', async () => {
      const { wrapper } = await mountLayout('READONLY')
      const links = wrapper.findAll('.nav-link')
      const paths = links.map((l) => l.attributes('href'))
      expect(paths).not.toContain('/trade')
      expect(paths).not.toContain('/positions')
      expect(paths).not.toContain('/admin')
    })
  })

  describe('路由高亮', () => {
    it('当前路由对应菜单项高亮', async () => {
      const { wrapper } = await mountLayout('ADMIN', '/dashboard')
      const activeLinks = wrapper.findAll('.nav-link.active')
      expect(activeLinks.length).toBe(1)
      expect(activeLinks[0].attributes('href')).toBe('/dashboard')
    })
  })

  describe('退出登录', () => {
    it('点击退出按钮调用 logout 并跳转登录页', async () => {
      const { wrapper, authStore, router } = await mountLayout()
      const logoutSpy = vi.spyOn(authStore, 'logout')
      const pushSpy = vi.spyOn(router, 'push')
      await wrapper.find('.logout-btn').trigger('click')
      expect(logoutSpy).toHaveBeenCalled()
      expect(pushSpy).toHaveBeenCalledWith('/login')
    })
  })

  describe('主内容区域', () => {
    it('包含 router-view 渲染区域', async () => {
      const { wrapper } = await mountLayout()
      expect(wrapper.find('.content').exists()).toBe(true)
    })
  })
})
