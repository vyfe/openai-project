import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'
import Chat from '@/views/Chat-New.vue'
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
      component: Login
    },
    {
      path: '/chat',
      name: 'Chat',
      component: Chat,
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('@/views/Admin.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const user = localStorage.getItem('user')
  const password = localStorage.getItem('password')

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

  if (to.meta.requiresAuth && (!user || !password)) {
    next('/login')
  } else if (to.path === '/login' && user && password) {
    next('/chat')
  } else {
    next()
  }
})

export default router