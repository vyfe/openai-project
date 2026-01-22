import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<string | null>(localStorage.getItem('user'))
  const password = ref<string | null>(localStorage.getItem('password'))

  const login = (userData: { username: string; password: string }) => {
    user.value = userData.username
    password.value = userData.password
    localStorage.setItem('user', userData.username)
    localStorage.setItem('password', userData.password)
  }

  const logout = () => {
    user.value = null
    password.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('password')
  }

  const isAuthenticated = () => {
    return !!user.value && !!password.value
  }

  const getCredentials = () => {
    return {
      user: user.value,
      password: password.value
    }
  }

  return {
    user,
    password,
    login,
    logout,
    isAuthenticated,
    getCredentials
  }
})