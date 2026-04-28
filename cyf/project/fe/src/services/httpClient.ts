import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

const TOKEN_EXPIRE_AHEAD_SECONDS = 30

export const getApiBaseUrl = () => {
  if (import.meta.env.DEV) {
    return 'http://localhost:39997'
  }
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  return `${protocol}//${window.location.hostname}`
}

export const API_BASE_URL = getApiBaseUrl()

let refreshPromise: Promise<string> | null = null

const ensureJsonBody = (config: InternalAxiosRequestConfig) => {
  if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
    if (config.headers['Content-Type'] === 'application/json') {
      config.data = JSON.stringify(config.data)
    }
  }
}

const attachBearer = (config: InternalAxiosRequestConfig, token: string) => {
  config.headers = config.headers || {}
  config.headers.Authorization = `Bearer ${token}`
}

const isExpiredSoon = (expiresAt: number | null | undefined) => {
  if (!expiresAt) return true
  const nowSeconds = Math.floor(Date.now() / 1000)
  return nowSeconds >= expiresAt - TOKEN_EXPIRE_AHEAD_SECONDS
}

const refreshAccessToken = async (): Promise<string> => {
  const authStore = useAuthStore()
  const credentials = authStore.getCredentials()
  if (!credentials.refreshToken) {
    throw new Error('登录已失效，请重新登录')
  }

  if (!refreshPromise) {
    refreshPromise = axios.post(`${API_BASE_URL}/never_guess_my_usage/token/refresh`, {
      refresh_token: credentials.refreshToken
    }, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000
    }).then((res) => {
      const data = res.data?.data || {}
      if (!res.data?.success || !data.access_token) {
        throw new Error(res.data?.msg || '刷新 token 失败')
      }
      authStore.updateAccessToken(
        data.access_token,
        data.access_token_expires_at,
        data.refresh_token,
        data.refresh_token_expires_at
      )
      return data.access_token as string
    }).finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

export const getValidAccessToken = async (forceRefresh = false): Promise<string | null> => {
  const authStore = useAuthStore()
  const credentials = authStore.getCredentials()

  if (!credentials.refreshToken) {
    return null
  }

  if (!forceRefresh && credentials.accessToken && !isExpiredSoon(credentials.accessTokenExpiresAt)) {
    return credentials.accessToken
  }

  return refreshAccessToken()
}

type ClientOptions = {
  requireAuthByDefault?: boolean
  publicPathPrefixes?: string[]
}

const isPublicPath = (path: string, publicPathPrefixes: string[]) => {
  return publicPathPrefixes.some((prefix) => path.includes(prefix))
}

export const createApiClient = ({
  requireAuthByDefault = true,
  publicPathPrefixes = []
}: ClientOptions = {}): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 300000,
    headers: {
      'Content-Type': 'application/json'
    },
    maxBodyLength: Infinity,
    maxContentLength: Infinity
  })

  client.interceptors.request.use(
    async (config) => {
      const path = config.url || ''
      const shouldAuth = requireAuthByDefault && !isPublicPath(path, publicPathPrefixes)
      if (shouldAuth) {
        const token = await getValidAccessToken()
        if (token) {
          attachBearer(config, token)
        }
      }
      ensureJsonBody(config)
      return config
    },
    (error) => Promise.reject(error)
  )

  client.interceptors.response.use(
    (response) => response.data,
    async (error: AxiosError) => {
      const authStore = useAuthStore()
      const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
      const status = error.response?.status
      const responseMsg = (error.response?.data as any)?.msg || ''
      const isAuthError = status === 401 || String(responseMsg).includes('令牌')

      if (!originalRequest || originalRequest._retry || !isAuthError) {
        return Promise.reject(error)
      }

      const path = originalRequest.url || ''
      if (!requireAuthByDefault || isPublicPath(path, publicPathPrefixes)) {
        return Promise.reject(error)
      }

      originalRequest._retry = true
      try {
        const nextToken = await getValidAccessToken(true)
        if (!nextToken) {
          throw new Error('登录已失效，请重新登录')
        }
        attachBearer(originalRequest, nextToken)
        return await client.request(originalRequest)
      } catch (retryErr) {
        authStore.logout()
        return Promise.reject(retryErr)
      }
    }
  )

  return client
}
