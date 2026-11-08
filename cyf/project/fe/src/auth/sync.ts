import { authAPI } from '@/services/api'
import { useAuthStore, type AccountSnapshot } from '@/stores/auth'

let inflight: { session: number; store: ReturnType<typeof useAuthStore>; promise: Promise<AccountSnapshot | null> } | null = null

/** 每次受保护导航都确认当前授权，失败时由调用者阻止进入。 */
export const syncCurrentRoles = (): Promise<AccountSnapshot | null> => {
  const store = useAuthStore()
  if (!store.isAuthenticated()) return Promise.resolve(null)
  const session = store.sessionVersion
  if (inflight?.session === session && inflight.store === store) return inflight.promise
  const promise = (async () => {
    try {
      const response: any = await authAPI.me()
      if (session !== store.sessionVersion) return null
      if (response?.success && response.data) {
        store.applySnapshot(response.data)
        return response.data as AccountSnapshot
      }
    } catch {
      // 401 由 HTTP 生命周期统一清理；网络失败保留凭据供重试。
    }
    if (session === store.sessionVersion) store.rolesConfirmed = false
    return null
  })()
  inflight = { session, store, promise }
  void promise.finally(() => { if (inflight?.promise === promise) inflight = null })
  return promise
}

export const hasConfirmedRoles = (): boolean => useAuthStore().rolesConfirmed
