import type { Router } from 'vue-router'
import { onPermissionDenied, onUnauthenticated } from '@/services/httpClient'
import { useAuthStore } from '@/stores/auth'
import { syncCurrentRoles } from './sync'
import type { AppRole } from './permissions'
import { appForPath } from './destination'

/** 服务端撤权、标签页恢复与账号切换共用同一条同步路径。 */
export const installAuthLifecycle = (router: Router) => {
  let pending: Promise<void> | null = null
  const check = () => {
    if (pending) return pending
    pending = (async () => {
      const store = useAuthStore()
      if (!store.isAuthenticated()) return
      const snapshot = await syncCurrentRoles()
      const route = router.currentRoute.value
      if (!route.meta.requiresAuth) return
      const required = route.meta.requiredRole as AppRole
      if (!snapshot || !store.hasRole(required)) {
        await router.replace({ path: '/login', query: snapshot
          ? { app: appForPath(route.path), denied: '1', required }
          : { redirect: route.fullPath, authError: '1' } })
      }
    })().finally(() => { pending = null })
    return pending
  }
  onPermissionDenied(({ path }) => { if (!path.endsWith('/auth/me')) void check() })
  onUnauthenticated(() => {
    const route = router.currentRoute.value
    useAuthStore().logout()
    if (route.meta.requiresAuth) void router.replace({ path: '/login', query: { redirect: route.fullPath } })
  })
  window.addEventListener('focus', () => { void check() })
  window.addEventListener('storage', () => { void check() })
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void check() })
}
