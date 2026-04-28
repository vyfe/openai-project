import { defineStore } from 'pinia'
import { ref } from 'vue'

type NullableString = string | null

type TokenBundle = {
  accessToken: NullableString
  accessTokenExpiresAt: number | null
  refreshToken: NullableString
  refreshTokenExpiresAt: number | null
}

const TTL_DAYS = 7

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
  const role = ref<NullableString>(getStoredValue('role'))
  const accessToken = ref<NullableString>(getStoredValue('access_token'))
  const accessTokenExpiresAt = ref<number | null>(getStoredValue('access_token_expires_at'))
  const refreshToken = ref<NullableString>(getStoredValue('refresh_token'))
  const refreshTokenExpiresAt = ref<number | null>(getStoredValue('refresh_token_expires_at'))

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

  const login = (userData: {
    username: string
    role?: string
    accessToken?: string
    accessTokenExpiresAt?: number
    refreshToken?: string
    refreshTokenExpiresAt?: number
  }) => {
    user.value = userData.username
    role.value = userData.role || 'user'
    setStoredValue('user', user.value)
    setStoredValue('role', role.value)
    setTokens({
      accessToken: userData.accessToken || null,
      accessTokenExpiresAt: userData.accessTokenExpiresAt || null,
      refreshToken: userData.refreshToken || null,
      refreshTokenExpiresAt: userData.refreshTokenExpiresAt || null
    })
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

  const logout = () => {
    user.value = null
    role.value = null
    setTokens({
      accessToken: null,
      accessTokenExpiresAt: null,
      refreshToken: null,
      refreshTokenExpiresAt: null
    })
    removeStoredValue('user')
    removeStoredValue('role')
    clearLegacyPassword()
  }

  const isAuthenticated = () => {
    const storedUser = getStoredValue('user')
    const storedRole = getStoredValue('role')
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

    user.value = storedUser
    role.value = storedRole
    refreshToken.value = storedRefreshToken
    refreshTokenExpiresAt.value = storedRefreshExpiresAt ? Number(storedRefreshExpiresAt) : null

    const storedAccessToken = getStoredValue('access_token')
    const storedAccessExpiresAt = getStoredValue('access_token_expires_at')
    accessToken.value = storedAccessToken
    accessTokenExpiresAt.value = storedAccessExpiresAt ? Number(storedAccessExpiresAt) : null

    return true
  }

  const isAdmin = () => role.value === 'admin'

  const getCredentials = () => {
    if (!isAuthenticated()) {
      return {
        user: null,
        role: null,
        accessToken: null,
        accessTokenExpiresAt: null,
        refreshToken: null,
        refreshTokenExpiresAt: null
      }
    }
    return {
      user: user.value,
      role: role.value,
      accessToken: accessToken.value,
      accessTokenExpiresAt: accessTokenExpiresAt.value,
      refreshToken: refreshToken.value,
      refreshTokenExpiresAt: refreshTokenExpiresAt.value
    }
  }

  return {
    user,
    role,
    accessToken,
    accessTokenExpiresAt,
    refreshToken,
    refreshTokenExpiresAt,
    login,
    logout,
    isAuthenticated,
    isAdmin,
    getCredentials,
    updateAccessToken
  }
})
