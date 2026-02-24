import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const ADMIN_API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:39997'
  : `${window.location.protocol}//${window.location.hostname}`

// 创建独立的 admin API 实例
const adminApi = axios.create({
  baseURL: ADMIN_API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  },
  maxBodyLength: Infinity,
  maxContentLength: Infinity,
})

// Admin API 请求拦截器
adminApi.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    const credentials = authStore.getCredentials()

    // 将认证信息注入到请求参数中
    if (config.method?.toLowerCase() === 'post' && config.headers['Content-Type'] === 'application/json') {
      if (!config.data) {
        config.data = {}
      }
      if (credentials.user) {
        (config.data as any).user = credentials.user
      }
      if (credentials.password) {
        (config.data as any).password = credentials.password
      }
    } else {
      // GET请求或其他类型，认证信息加入URL参数
      if (!config.params) {
        config.params = {}
      }
      if (credentials.user) {
        config.params.user = credentials.user
      }
      if (credentials.password) {
        config.params.password = credentials.password
      }
    }

    // 如果是普通对象数据且不是FormData，将其转换为JSON格式
    if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
      if (config.headers['Content-Type'] === 'application/json') {
        config.data = JSON.stringify(config.data)
      }
    }
    return config
  },
  (error) => {
    console.error('Admin API Error:', error)
    return Promise.reject(error)
  }
)

adminApi.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('Admin API Error:', error)
    return Promise.reject(error)
  }
)

interface AdminResponse<T = any> {
  success: boolean
  data?: T
  msg: string
}

// ModelMeta APIs
export const modelMetaAPI = {
  list: (params?: { recommend?: boolean; status_valid?: boolean }) =>
    adminApi.get('/never_guess_my_usage/model_meta/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/model_meta/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/model_meta/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/model_meta/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/model_meta/delete', { id })
}

// SystemPrompt APIs
export const systemPromptAPI = {
  list: (params?: { role_group?: string; status_valid?: boolean }) =>
    adminApi.get('/never_guess_my_usage/system_prompt/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/system_prompt/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/system_prompt/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/system_prompt/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/system_prompt/delete', { id })
}

// User APIs
export const userAPI = {
  list: () => adminApi.get('/never_guess_my_usage/user/list'),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/user/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/user/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/user/update', data),
  delete: (id: number, hardDelete?: boolean) =>
    adminApi.post('/never_guess_my_usage/user/delete', { id, hard_delete: hardDelete })
}

// Notification APIs
export const notificationAPI = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    adminApi.get('/never_guess_my_usage/notification/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/notification/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/notification/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/notification/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/notification/delete', { id })
}

// TestLimit APIs
export const testLimitAPI = {
  list: () => adminApi.get('/never_guess_my_usage/test_limit/list'),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/test_limit/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/test_limit/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/test_limit/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/test_limit/delete', { id }),
  reset: (data: { id?: number; user_ip?: string; reset_all?: boolean }) =>
    adminApi.post('/never_guess_my_usage/test_limit/reset', data)
}

// SQL Execute API
export const sqlAPI = {
  execute: (sql: string, params?: any[]) =>
    adminApi.post('/never_guess_my_usage/sql_execute', { sql, params })
}
