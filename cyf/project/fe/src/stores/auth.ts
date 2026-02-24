import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // 获取带过期时间的存储值
  const getStoredValue = (key: string) => {
    try {
      const item = localStorage.getItem(key)
      if (!item) return null

      const parsedItem = JSON.parse(item)
      const now = new Date().getTime()

      // 检查是否过期
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

  // 设置带过期时间的存储值（7天有效期）
  const setStoredValue = (key: string, value: string) => {
    const expiryTime = new Date().getTime() + 7 * 24 * 60 * 60 * 1000 // 7天后过期
    const item = {
      value: value,
      expiry: expiryTime
    }
    localStorage.setItem(key, JSON.stringify(item))
  }

  const user = ref<string | null>(getStoredValue('user'))
  const password = ref<string | null>(getStoredValue('password'))
  const role = ref<string | null>(getStoredValue('role'))

  const login = (userData: { username: string; password: string; role?: string }) => {
    user.value = userData.username
    password.value = userData.password
    role.value = userData.role || 'user'
    setStoredValue('user', userData.username)
    setStoredValue('password', userData.password)
    setStoredValue('role', role.value)
  }

  const logout = () => {
    user.value = null
    password.value = null
    role.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('password')
    localStorage.removeItem('role')
  }

  const isAuthenticated = () => {
    // 检查是否已过期，如果过期则更新ref值
    const storedUser = getStoredValue('user')
    const storedPassword = getStoredValue('password')
    const storedRole = getStoredValue('role')

    if (!storedUser || !storedPassword) {
      user.value = null
      password.value = null
      role.value = null
      return false
    }

    // 如果store中的值与存储中的值不一致，则更新store
    if (user.value !== storedUser) {
      user.value = storedUser
    }
    if (password.value !== storedPassword) {
      password.value = storedPassword
    }
    if (role.value !== storedRole) {
      role.value = storedRole
    }

    return !!user.value && !!password.value
  }

  const isAdmin = () => {
    return role.value === 'admin'
  }

  const getCredentials = () => {
    // 确保返回的数据没有过期
    const storedUser = getStoredValue('user')
    const storedPassword = getStoredValue('password')
    const storedRole = getStoredValue('role')

    if (!storedUser || !storedPassword) {
      user.value = null
      password.value = null
      role.value = null
      return {
        user: null,
        password: null,
        role: null
      }
    }

    return {
      user: storedUser,
      password: storedPassword,
      role: storedRole
    }
  }

  return {
    user,
    password,
    role,
    login,
    logout,
    isAuthenticated,
    isAdmin,
    getCredentials
  }
})