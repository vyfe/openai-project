import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL } from './backendUrl'
export { API_BASE_URL, getApiBaseUrl } from './backendUrl'

const TOKEN_EXPIRE_AHEAD_SECONDS = 30

let refreshPromise: { token: string; promise: Promise<string> } | null = null

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

  const session = authStore.sessionVersion
  const refreshToken = credentials.refreshToken
  if (!refreshPromise || refreshPromise.token !== refreshToken) {
    const promise = axios.post(`${API_BASE_URL}/never_guess_my_usage/token/refresh`, {
      refresh_token: credentials.refreshToken
    }, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000
    }).then((res) => {
      const data = res.data?.data || {}
      if (!res.data?.success || !data.access_token) {
        throw new Error(res.data?.msg || '刷新 token 失败')
      }
      if (authStore.sessionVersion !== session) throw new Error('登录账号已变更')
      authStore.applySnapshot({ ...data, refresh_token: data.refresh_token ?? refreshToken, refresh_token_expires_at: data.refresh_token_expires_at ?? credentials.refreshTokenExpiresAt }, true)
      return data.access_token as string
    }).finally(() => {
      if (refreshPromise?.promise === promise) refreshPromise = null
    })
    refreshPromise = { token: refreshToken, promise }
  }

  return refreshPromise.promise
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
  retryAuthOnFailure?: boolean
}

const isPublicPath = (path: string, publicPathPrefixes: string[]) => {
  return publicPathPrefixes.some((prefix) => path.includes(prefix))
}

/** 403：已认证但缺少权限——不刷新 token、不重放业务请求。 */
type PermissionDeniedDetail = {
  path: string
  status: number
  msg: string
  requiredRole?: string
}

const permissionDeniedHandlers = new Set<(detail: PermissionDeniedDetail) => void>()

/** 订阅 403 事件：前端据此同步角色并展示权限引导。 */
export const onPermissionDenied = (handler: (detail: PermissionDeniedDetail) => void) => {
  permissionDeniedHandlers.add(handler)
  return () => permissionDeniedHandlers.delete(handler)
}

const emitPermissionDenied = (detail: PermissionDeniedDetail) => {
  permissionDeniedHandlers.forEach((handler) => {
    try {
      handler(detail)
    } catch (error) {
      console.error('permission denied handler failed:', error)
    }
  })
}

/** 401：凭据失效——调用方据此清理登录态。 */
type UnauthenticatedDetail = { path: string; status: number; msg: string }

const unauthenticatedHandlers = new Set<(detail: UnauthenticatedDetail) => void>()

export const onUnauthenticated = (handler: (detail: UnauthenticatedDetail) => void) => {
  unauthenticatedHandlers.add(handler)
  return () => unauthenticatedHandlers.delete(handler)
}

const emitUnauthenticated = (detail: UnauthenticatedDetail) => {
  unauthenticatedHandlers.forEach((handler) => {
    try {
      handler(detail)
    } catch (error) {
      console.error('unauthenticated handler failed:', error)
    }
  })
}

export const createApiClient = ({
  requireAuthByDefault = true,
  publicPathPrefixes = [],
  retryAuthOnFailure = true
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
        ;(config as InternalAxiosRequestConfig & { _session?: number })._session = useAuthStore().sessionVersion
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
      const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean; _session?: number }) | undefined
      const status = error.response?.status
      const responseBody = (error.response?.data as any) || {}
      const responseMsg = responseBody.msg || ''
      const path = originalRequest?.url || ''

      if (originalRequest?._session !== undefined && originalRequest._session !== authStore.sessionVersion) return Promise.reject(error)

      // 403：权限不足。不刷新 token，也不重放业务请求；通知上层同步授权。
      if (status === 403) {
        emitPermissionDenied({
          path,
          status,
          msg: responseMsg || '',
          requiredRole: responseBody.required_role
        })
        return Promise.reject(error)
      }

      const isAuthError = status === 401 || String(responseMsg).includes('令牌')

      if (!retryAuthOnFailure || !originalRequest || originalRequest._retry || !isAuthError) {
        if (status === 401) {
          emitUnauthenticated({ path, status, msg: responseMsg || '' })
        }
        return Promise.reject(error)
      }

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
      } catch (retryErr) {
        emitUnauthenticated({ path, status: 401, msg: '登录已失效，请重新登录' })
        authStore.logout()
        return Promise.reject(retryErr)
      }
      return client.request(originalRequest)
    }
  )

  return client
}
