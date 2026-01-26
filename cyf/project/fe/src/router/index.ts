import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'
import Chat from '@/views/Chat.vue'
import VersionService from '@/services/version'

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
    }
  ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const user = localStorage.getItem('user')
  const password = localStorage.getItem('password')

  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();

  if (to.meta.requiresAuth && (!user || !password)) {
    next('/login')
  } else if (to.path === '/login' && user && password) {
    next('/chat')
  } else {
    next()
  }
})

export default router