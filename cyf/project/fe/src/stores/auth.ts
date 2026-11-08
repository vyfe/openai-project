import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  APP_ORDER,
  type AppKey
} from '@/auth/apps'
import {
  hasRole as rolesHave,
  isAdminRoles,
  normalizeRoles,
  toCompatRole,
  type AppRole
} from '@/auth/permissions'

type NullableString = string | null

type TokenBundle = {
  accessToken: NullableString
  accessTokenExpiresAt: number | null
  refreshToken: NullableString
  refreshTokenExpiresAt: number | null
}

/** 后端账号快照（login / refresh / auth/me 共用） */
export type AccountSnapshot = {
  user_id?: number | null
  username?: string
  roles?: unknown
  role?: string
  access_token?: string
  access_token_expires_at?: number
  refresh_token?: string
  refresh_token_expires_at?: number
}

const TTL_DAYS = 7

/** 每个账号上次使用的入口；账号切换时清理上一账号的偏好。 */
const LAST_APP_KEY = 'last_app'

export const useAuthStore = defineStore('auth', () => {
  const getStoredValue = (key: string) => {
    try {
      const item = localStorage.getItem(key)
      if (!item) return null

      const parsedItem = JSON.parse(item)
      const now = Date.now()
      if (parsedItem.expiry && now > parsedItem.expiry) {
        localStorage.removeItem(key)
        return null
      }
      return parsedItem.value
    } catch (e) {
      console.error('Error parsing stored value:', e)
      return null
    }
  }

  const setStoredValue = (key: string, value: any) => {
    const expiryTime = Date.now() + TTL_DAYS * 24 * 60 * 60 * 1000
    localStorage.setItem(key, JSON.stringify({ value, expiry: expiryTime }))
  }

  const removeStoredValue = (key: string) => {
    localStorage.removeItem(key)
  }

  const user = ref<NullableString>(getStoredValue('user'))
  const userId = ref<number | null>(getStoredValue('user_id'))
  // 本地 roles 只是恢复线索，真实授权一律以服务端快照为准。
  const roles = ref<AppRole[]>(normalizeRoles(getStoredValue('roles')))
  const role = ref<NullableString>(getStoredValue('role'))
  const accessToken = ref<NullableString>(getStoredValue('access_token'))
  const accessTokenExpiresAt = ref<number | null>(getStoredValue('access_token_expires_at'))
  const refreshToken = ref<NullableString>(getStoredValue('refresh_token'))
  const refreshTokenExpiresAt = ref<number | null>(getStoredValue('refresh_token_expires_at'))
  const lastApp = ref<AppKey | null>(getStoredValue(LAST_APP_KEY))
  /** 服务端已确认的授权快照；false 表示尚未与服务端核对。 */
  const rolesConfirmed = ref(false)
  const sessionVersion = ref(0)

  const isTokenExpired = (expiresAt: number | null) => {
    if (!expiresAt) return true
    return Date.now() >= Number(expiresAt) * 1000
  }

  const setTokens = (bundle: TokenBundle) => {
    accessToken.value = bundle.accessToken
    accessTokenExpiresAt.value = bundle.accessTokenExpiresAt
    refreshToken.value = bundle.refreshToken
    refreshTokenExpiresAt.value = bundle.refreshTokenExpiresAt

    if (bundle.accessToken) setStoredValue('access_token', bundle.accessToken)
    else removeStoredValue('access_token')

    if (bundle.accessTokenExpiresAt) setStoredValue('access_token_expires_at', bundle.accessTokenExpiresAt)
    else removeStoredValue('access_token_expires_at')

    if (bundle.refreshToken) setStoredValue('refresh_token', bundle.refreshToken)
    else removeStoredValue('refresh_token')

    if (bundle.refreshTokenExpiresAt) setStoredValue('refresh_token_expires_at', bundle.refreshTokenExpiresAt)
    else removeStoredValue('refresh_token_expires_at')
  }

  const clearLegacyPassword = () => {
    removeStoredValue('password')
  }

  /** 应用服务端返回的账号快照（角色 + 可选 token）。 */
  const applySnapshot = (snapshot: AccountSnapshot, withTokens = false) => {
    const normalized = normalizeRoles(snapshot.roles)
    if (snapshot.username) {
      // 账号切换：清理上一账号的目的地偏好与业务缓存。
      if (user.value && user.value !== snapshot.username) {
        clearAccountScopedState()
      }
      user.value = snapshot.username
      setStoredValue('user', user.value)
    }
    if (typeof snapshot.user_id === 'number') {
      userId.value = snapshot.user_id
      setStoredValue('user_id', userId.value)
    }
    roles.value = normalized
    role.value = toCompatRole(normalized)
    setStoredValue('roles', normalized)
    setStoredValue('role', role.value)
    rolesConfirmed.value = true
    removeStoredValue('roles_confirmed')

    if (withTokens) {
      setTokens({
        accessToken: snapshot.access_token ?? null,
        accessTokenExpiresAt: snapshot.access_token_expires_at ?? null,
        refreshToken: snapshot.refresh_token ?? null,
        refreshTokenExpiresAt: snapshot.refresh_token_expires_at ?? null
      })
    }
  }

  const login = (userData: AccountSnapshot) => {
    sessionVersion.value++
    applySnapshot(userData, true)
    clearLegacyPassword()
  }

  const updateAccessToken = (nextAccessToken: string, expiresAt: number, nextRefreshToken?: string, nextRefreshExpiresAt?: number) => {
    setTokens({
      accessToken: nextAccessToken,
      accessTokenExpiresAt: expiresAt,
      refreshToken: nextRefreshToken ?? refreshToken.value,
      refreshTokenExpiresAt: nextRefreshExpiresAt ?? refreshTokenExpiresAt.value
    })
  }

  /** 清理与单个账号绑定的偏好（切换账号时调用）。 */
  const clearAccountScopedState = () => {
    lastApp.value = null
    removeStoredValue(LAST_APP_KEY)
  }

  const logout = () => {
    sessionVersion.value++
    user.value = null
    userId.value = null
    roles.value = []
    role.value = null
    rolesConfirmed.value = false
    setTokens({
      accessToken: null,
      accessTokenExpiresAt: null,
      refreshToken: null,
      refreshTokenExpiresAt: null
    })
    removeStoredValue('user')
    removeStoredValue('user_id')
    removeStoredValue('role')
    removeStoredValue('roles')
    removeStoredValue('roles_confirmed')
    clearAccountScopedState()
    clearLegacyPassword()
  }

  const isAuthenticated = () => {
    const storedUser = getStoredValue('user')
    const storedRefreshToken = getStoredValue('refresh_token')
    const storedRefreshExpiresAt = getStoredValue('refresh_token_expires_at')
    const legacyPassword = getStoredValue('password')

    // 兼容旧会话（有密码但没 token），让用户重新登录
    if (legacyPassword && !storedRefreshToken) {
      logout()
      return false
    }

    if (!storedUser || !storedRefreshToken || isTokenExpired(storedRefreshExpiresAt ? Number(storedRefreshExpiresAt) : null)) {
      logout()
      return false
    }

    // 同一标签页内授权只接受服务端快照；其它标签页更换会话时重新确认。
    if (storedUser !== user.value || storedRefreshToken !== refreshToken.value) {
      sessionVersion.value++
      rolesConfirmed.value = false
      roles.value = []
      role.value = null
      user.value = storedUser
      userId.value = getStoredValue('user_id')
      refreshToken.value = storedRefreshToken
      refreshTokenExpiresAt.value = Number(storedRefreshExpiresAt)
      accessToken.value = getStoredValue('access_token')
      accessTokenExpiresAt.value = getStoredValue('access_token_expires_at')
      clearAccountScopedState()
    }

    return true
  }

  const isAdmin = () => isAdminRoles(roles.value)

  const hasRole = (target: AppRole): boolean => rolesHave(roles.value, target)

  /** 能否进入某个功能入口。 */
  const canAccessApp = (app: AppKey) => {
    if (app === 'admin') return isAdminRoles(roles.value)
    return hasRole(app as AppRole)
  }

  /** 当前账号可用的功能入口（顶栏与登录页共用）。 */
  const availableApps = computed<AppKey[]>(() =>
    APP_ORDER.filter((app) => canAccessApp(app))
  )

  const setLastApp = (app: AppKey | null) => {
    lastApp.value = app
    if (app) setStoredValue(LAST_APP_KEY, app)
    else removeStoredValue(LAST_APP_KEY)
  }

  const getCredentials = () => {
    if (!isAuthenticated()) {
      return {
        user: null,
        userId: null,
        roles: [] as AppRole[],
        role: null,
        accessToken: null,
        accessTokenExpiresAt: null,
        refreshToken: null,
        refreshTokenExpiresAt: null
      }
    }
    return {
      user: user.value,
      userId: userId.value,
      roles: roles.value,
      role: role.value,
      accessToken: accessToken.value,
      accessTokenExpiresAt: accessTokenExpiresAt.value,
      refreshToken: refreshToken.value,
      refreshTokenExpiresAt: refreshTokenExpiresAt.value
    }
  }

  return {
    user,
    userId,
    roles,
    role,
    accessToken,
    accessTokenExpiresAt,
    refreshToken,
    refreshTokenExpiresAt,
    lastApp,
    rolesConfirmed,
    sessionVersion,
    availableApps,
    login,
    logout,
    isAuthenticated,
    isAdmin,
    hasRole,
    canAccessApp,
    setLastApp,
    applySnapshot,
    getCredentials,
    updateAccessToken
  }
})
