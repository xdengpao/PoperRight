import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      // 大盘概况
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '大盘概况' },
      },
      // 数据管理（父路由，重定向到在线数据）
      {
        path: 'data',
        redirect: '/data/online',
      },
      // 在线数据（原数据管理）
      {
        path: 'data/online',
        name: 'DataOnline',
        component: () => import('@/views/DataManageView.vue'),
        meta: { title: '在线数据' },
      },
      // Tushare 数据导入
      {
        path: 'data/online/tushare',
        name: 'DataOnlineTushare',
        component: () => import('@/views/TushareImportView.vue'),
        meta: { title: 'Tushare 数据导入' },
      },
      // Tushare 数据预览
      {
        path: 'data/online/tushare-preview',
        name: 'DataOnlineTusharePreview',
        component: () => import('@/views/TusharePreviewView.vue'),
        meta: { title: 'Tushare 数据预览' },
      },
      // 本地数据（原本地数据导入）
      {
        path: 'data/local',
        name: 'DataLocal',
        component: () => import('@/views/LocalImportView.vue'),
        meta: { title: '本地数据' },
      },
      // 选股功能（需求 3-7）
      {
        path: 'screener',
        name: 'Screener',
        component: () => import('@/views/ScreenerView.vue'),
        meta: { title: '智能选股' },
      },
      // 选股结果标的池
      {
        path: 'screener/results',
        name: 'ScreenerResults',
        component: () => import('@/views/ScreenerResultsView.vue'),
        meta: { title: '选股结果' },
      },
      // 选股池管理
      {
        path: 'stock-pool',
        name: 'StockPool',
        component: () => import('@/views/StockPoolView.vue'),
        meta: { title: '选股池' },
      },
      // 风控配置（需求 9-11）
      {
        path: 'risk',
        name: 'Risk',
        component: () => import('@/views/RiskView.vue'),
        meta: { title: '风险控制' },
      },
      // 策略回测（需求 12-13）
      {
        path: 'backtest',
        name: 'Backtest',
        component: () => import('@/views/BacktestView.vue'),
        meta: { title: '策略回测' },
      },
      // 交易执行（需求 14-15）
      {
        path: 'trade',
        name: 'Trade',
        component: () => import('@/views/TradeView.vue'),
        meta: { title: '交易执行', roles: ['TRADER', 'ADMIN'] },
      },
      // 持仓管理
      {
        path: 'positions',
        name: 'Positions',
        component: () => import('@/views/PositionsView.vue'),
        meta: { title: '持仓管理', roles: ['TRADER', 'ADMIN'] },
      },
      // 复盘分析（需求 16）
      {
        path: 'review',
        name: 'Review',
        component: () => import('@/views/ReviewView.vue'),
        meta: { title: '复盘分析' },
      },
      // 系统管理（需求 17，仅 ADMIN 可见）
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/AdminView.vue'),
        meta: { title: '系统管理', roles: ['ADMIN'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 全局导航守卫：JWT 认证 + 角色权限（需求 19.4）
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth === false) {
    return next()
  }

  if (!authStore.isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  const requiredRoles = to.meta.roles as string[] | undefined
  if (requiredRoles && !requiredRoles.includes(authStore.role)) {
    return next({ name: 'Dashboard' })
  }

  next()
})

export default router
