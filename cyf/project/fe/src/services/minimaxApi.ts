import { createApiClient } from '@/services/httpClient'

export type Reply<T> = { success: boolean; data: T; msg: string }

// 付费请求发出后不自动重放，只在请求前刷新登录态。
const client = createApiClient({ requireAuthByDefault: true, retryAuthOnFailure: false })

export async function unwrap<T>(request: Promise<Reply<T>>): Promise<T> {
  const reply = await request
  if (!reply.success) throw new Error(reply.msg || '操作失败')
  return reply.data
}

export function minimaxGet<T>(path: string) {
  return unwrap(client.get<never, Reply<T>>(path))
}

export function minimaxPost<T>(path: string, data?: unknown, timeout = 600000) {
  return unwrap(client.post<never, Reply<T>>(path, data ?? {}, { timeout }))
}

export function minimaxUpload<T>(path: string, data: FormData) {
  return unwrap(client.post<never, Reply<T>>(path, data,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 900000 }))
}

export async function minimaxBlob(path: string): Promise<Blob> {
  try {
    return await client.get<never, Blob>(path, { responseType: 'blob' })
  } catch (error: any) {
    if (error?.response?.data instanceof Blob) {
      const raw = await error.response.data.text()
      let message = ''
      try { message = JSON.parse(raw).msg || '' } catch { /* 非 JSON 错误保留原始异常。 */ }
      if (message) throw new Error(message)
    }
    throw error
  }
}
