import axios, { AxiosError } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApiClient } from '@/services/httpClient'

const auth = vi.hoisted(() => ({ getCredentials: vi.fn(), updateAccessToken: vi.fn(), logout: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))

beforeEach(() => {
  vi.clearAllMocks()
  auth.getCredentials.mockReturnValue({ refreshToken: 'test-refresh', accessToken: 'test-access',
    accessTokenExpiresAt: Math.floor(Date.now() / 1000) + 3600 })
})
afterEach(() => vi.restoreAllMocks())

describe('语音付费请求的认证行为', () => {
  it('服务端返回 401 后不刷新令牌或重复发送合成请求', async () => {
    const refresh = vi.spyOn(axios, 'post')
    const client = createApiClient({ retryAuthOnFailure: false })
    const adapter = vi.fn(async config => {
      throw new AxiosError('令牌失效', 'ERR_BAD_REQUEST', config, undefined,
        { status: 401, statusText: 'Unauthorized', data: { msg: '令牌失效' }, headers: {}, config })
    })
    client.defaults.adapter = adapter
    await expect(client.post('/never_guess_my_usage/voice/synthesize', { text: '晚安' })).rejects.toThrow('令牌失效')
    expect(adapter).toHaveBeenCalledTimes(1)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('请求前令牌过期仍先刷新，再发送一次合成请求', async () => {
    auth.getCredentials.mockReturnValue({ refreshToken: 'test-refresh', accessToken: 'old-access', accessTokenExpiresAt: 1 })
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { success: true,
      data: { access_token: 'new-access', access_token_expires_at: Math.floor(Date.now() / 1000) + 3600 } } })
    const client = createApiClient({ retryAuthOnFailure: false })
    const adapter = vi.fn(async config => ({ data: { success: true }, status: 200, statusText: 'OK', headers: {}, config }))
    client.defaults.adapter = adapter
    await expect(client.post('/never_guess_my_usage/voice/synthesize', { text: '晚安' })).resolves.toEqual({ success: true })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(adapter).toHaveBeenCalledTimes(1)
    expect(adapter.mock.calls[0][0].headers.Authorization).toBe('Bearer new-access')
  })
})
