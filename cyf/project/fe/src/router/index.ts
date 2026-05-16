import { createRouter, createWebHistory } from 'vue-router'
import VersionService from '@/services/version'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue')
    },
    {
      path: '/chat',
      name: 'Chat',
      component: () => import('@/views/Chat-New.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('@/views/Admin.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/quant',
      name: 'Quant',
      component: () => import('@/views/quant/QuantLayout.vue'),
      redirect: '/quant/overview',
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        {
          path: 'overview',
          name: 'QuantOverview',
          component: () => import('@/views/quant/pages/QuantOverviewPage.vue')
        },
        {
          path: 'data',
          name: 'QuantData',
          component: () => import('@/views/quant/pages/QuantDataPage.vue')
        },
        {
          path: 'strategy',
          name: 'QuantStrategy',
          component: () => import('@/views/quant/pages/QuantStrategyPage.vue')
        },
        {
          path: 'runs',
          name: 'QuantRuns',
          component: () => import('@/views/quant/pages/QuantRunsPage.vue')
        },
        {
          path: 'operations',
          name: 'QuantOperations',
          component: () => import('@/views/quant/pages/QuantOperationsPage.vue')
        },
        {
          path: 'backtest',
          name: 'QuantBacktest',
          component: () => import('@/views/quant/pages/QuantBacktestPage.vue')
        },
        {
          path: 'scheduler',
          name: 'QuantScheduler',
          component: () => import('@/views/quant/pages/QuantSchedulerPage.vue')
        },
        {
          path: 'ai-memory',
          name: 'QuantAiMemory',
          component: () => import('@/views/quant/pages/QuantAiMemoryPage.vue')
        },
        {
          path: 'im-positions',
          name: 'QuantImPositions',
          component: () => import('@/views/quant/pages/QuantImPositionsPage.vue')
        }
      ]
    }
  ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const user = localStorage.getItem('user')
  const refreshToken = localStorage.getItem('refresh_token')

  // 解析 role（存储的是 JSON 字符串）
  let role = null
  const roleStr = localStorage.getItem('role')
  if (roleStr) {
    try {
      const parsedRole = JSON.parse(roleStr)
      role = parsedRole.value
    } catch (e) {
      console.error('Failed to parse role from localStorage:', e)
    }
  }

  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();

  // 检查admin权限
  if (to.meta.requiresAdmin && role !== 'admin') {
    next('/chat')
    return
  }

  if (to.meta.requiresAuth && (!user || !refreshToken)) {
    next('/login')
  } else if (to.path === '/login' && user && refreshToken) {
    next('/chat')
  } else {
    next()
  }
})

export default router
