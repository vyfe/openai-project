import { createRouter, createWebHistory } from 'vue-router'
import VersionService from '@/services/version'
import { useAuthStore } from '@/stores/auth'
import { appForPath, registerKnownPaths } from '@/auth/destination'
import { syncCurrentRoles } from '@/auth/sync'
import type { AppRole } from '@/auth/permissions'

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
      meta: { requiresAuth: true, requiredRole: 'chat' }
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('@/views/Admin.vue'),
      meta: { requiresAuth: true, requiredRole: 'admin' }
    },
    {
      path: '/studio',
      name: 'Studio',
      component: () => import('@/views/studio/StudioLayout.vue'),
      redirect: '/studio/voice',
      meta: { requiresAuth: true, requiredRole: 'sound' },
      children: [
        {
          path: 'voice',
          name: 'StudioVoice',
          component: () => import('@/views/studio/pages/VoiceStudioPage.vue')
        },
        {
          path: 'music',
          name: 'StudioMusic',
          component: () => import('@/views/studio/pages/MusicStudioPage.vue')
        }
      ]
    },
    {
      path: '/quant',
      name: 'Quant',
      component: () => import('@/views/quant/QuantLayout.vue'),
      redirect: '/quant/overview',
      meta: { requiresAuth: true, requiredRole: 'quant' },
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
          path: 'industry',
          name: 'QuantIndustry',
          component: () => import('@/views/quant/pages/QuantIndustryPage.vue')
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
          // 以下子页本期保持管理员边界
          path: 'scheduler',
          name: 'QuantScheduler',
          component: () => import('@/views/quant/pages/QuantSchedulerPage.vue'),
          meta: { requiredRole: 'admin' }
        },
        {
          path: 'ai-memory',
          name: 'QuantAiMemory',
          component: () => import('@/views/quant/pages/QuantAiMemoryPage.vue'),
          meta: { requiredRole: 'admin' }
        },
        {
          path: 'im-positions',
          name: 'QuantImPositions',
          component: () => import('@/views/quant/pages/QuantImPositionsPage.vue'),
          meta: { requiredRole: 'admin' }
        }
      ]
    }
  ]
})

registerKnownPaths(router.getRoutes().filter((route) => router.resolve(route.path).meta.requiresAuth).map((route) => ({
  path: route.path, requiredRole: router.resolve(route.path).meta.requiredRole as AppRole
})))

// 路由守卫：统一按 requiredRole 判定，不再各处硬编码管理员路径。
router.beforeEach(async (to, _from, next) => {
  VersionService.checkAndHandleVersionChange()

  const authStore = useAuthStore()
  const requiredRole = to.meta.requiredRole as AppRole | undefined
  const authenticated = authStore.isAuthenticated()

  if (!to.meta.requiresAuth) {
    next()
    return
  }

  if (!authenticated) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  if (!await syncCurrentRoles()) {
    next({ path: '/login', query: { redirect: to.fullPath, authError: '1' } })
    return
  }

  if (requiredRole && !authStore.hasRole(requiredRole)) {
    // 权限不足：回到入口页展示权限引导，不重放原业务操作。
    next({ path: '/login', query: { app: appForPath(to.path), denied: '1', required: requiredRole } })
    return
  }

  next()
})

export default router
