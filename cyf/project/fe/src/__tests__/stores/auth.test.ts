import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

describe('auth store 角色快照', () => {
  it('登录后保存角色与兼容 role', () => {
    const store = useAuthStore()
    store.login({
      username: 'researcher',
      user_id: 42,
      roles: ['quant', 'chat'],
      role: 'user',
      access_token: 'at',
      access_token_expires_at: 9999999999,
      refresh_token: 'rt',
      refresh_token_expires_at: 9999999999
    })
    expect(store.roles).toEqual(['chat', 'quant'])
    expect(store.role).toBe('user')
    expect(store.userId).toBe(42)
    expect(store.isAuthenticated()).toBe(true)
  })

  it('hasRole / canAccessApp 按角色判定', () => {
    const store = useAuthStore()
    store.login({ username: 'u', roles: ['quant'], access_token: 'at', refresh_token: 'rt' })
    expect(store.hasRole('quant')).toBe(true)
    expect(store.hasRole('chat')).toBe(false)
    expect(store.canAccessApp('quant')).toBe(true)
    expect(store.canAccessApp('chat')).toBe(false)
    expect(store.canAccessApp('admin')).toBe(false)
    expect(store.isAdmin()).toBe(false)
  })

  it('管理员具备全部入口', () => {
    const store = useAuthStore()
    store.login({ username: 'root', roles: ['admin'], access_token: 'at', refresh_token: 'rt' })
    expect(store.isAdmin()).toBe(true)
    expect(store.availableApps).toEqual(['chat', 'quant', 'sound', 'admin'])
  })

  it('applySnapshot 只更新角色，不动 token', () => {
    const store = useAuthStore()
    store.login({ username: 'u', roles: ['chat'], access_token: 'at', refresh_token: 'rt' })
    store.applySnapshot({ username: 'u', roles: ['sound'] })
    expect(store.roles).toEqual(['sound'])
    expect(store.accessToken).toBe('at')
    expect(store.refreshToken).toBe('rt')
  })

  it('账号切换清理上一账号的目的地偏好', () => {
    const store = useAuthStore()
    store.login({ username: 'a', roles: ['chat'], access_token: 'at', refresh_token: 'rt' })
    store.setLastApp('chat')
    expect(store.lastApp).toBe('chat')
    store.applySnapshot({ username: 'b', roles: ['quant'] })
    expect(store.lastApp).toBeNull()
  })

  it('退出登录清理全部账号状态', () => {
    const store = useAuthStore()
    store.login({ username: 'u', roles: ['chat'], access_token: 'at', refresh_token: 'rt' })
    store.setLastApp('chat')
    store.logout()
    expect(store.user).toBeNull()
    expect(store.roles).toEqual([])
    expect(store.accessToken).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.lastApp).toBeNull()
    expect(store.isAuthenticated()).toBe(false)
  })

  it('本地 roles 只是恢复线索，服务端确认后标记已确认', () => {
    const store = useAuthStore()
    store.login({ username: 'u', roles: ['chat'], access_token: 'at', refresh_token: 'rt' })
    expect(store.rolesConfirmed).toBe(true)
  })
})
