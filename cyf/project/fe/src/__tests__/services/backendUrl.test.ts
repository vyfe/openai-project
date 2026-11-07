import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

const loadUrls = async (api = '', files = '') => {
  vi.stubEnv('VITE_API_BASE_URL', api)
  vi.stubEnv('VITE_FILE_BASE_URL', files)
  return import('@/services/backendUrl')
}

describe('前后端独立部署地址', () => {
  it('独立 API 配置覆盖开发默认地址，并去掉尾部斜杠', async () => {
    const { getApiBaseUrl } = await loadUrls('https://api.chat-h.cc/')
    expect(getApiBaseUrl()).toBe('https://api.chat-h.cc')
  })

  it('未配置时保留本机开发和同源生产部署', async () => {
    vi.stubEnv('DEV', true)
    const { getApiBaseUrl } = await loadUrls()
    expect(getApiBaseUrl()).toBe('http://localhost:39997')
    vi.stubEnv('DEV', false)
    expect(getApiBaseUrl()).toBe(window.location.origin)
  })

  it('将新旧附件统一迁到 HTTPS 后端，同时保留外部生成图片地址', async () => {
    const { normalizeFileUrl } = await loadUrls('https://api.chat-h.cc', 'https://api.chat-h.cc')
    for (const value of [':4567/download/test.pdf', '/download/test.pdf', 'download/test.pdf',
      'https://chat-h.cc:4567/download/test.pdf', 'http://api.chat-h.cc:4567/download/test.pdf']) {
      expect(normalizeFileUrl(value)).toBe('https://api.chat-h.cc/download/test.pdf')
    }
    expect(normalizeFileUrl('https://cdn.example.com/image.png?token=a')).toBe('https://cdn.example.com/image.png?token=a')
    expect(normalizeFileUrl('')).toBe('')
  })

  it('原部署未启用新文件入口时，旧端口仍属于后端主机', async () => {
    const { normalizeFileUrl } = await loadUrls('http://localhost:39997')
    expect(normalizeFileUrl(':4567/download/test.pdf')).toBe('http://localhost:4567/download/test.pdf')
  })

  it('历史上下文和多模态部件发给模型前改用文件入口，且不修改原始记录', async () => {
    const { normalizeFileMarkers, serializeChatDialog } = await loadUrls('https://api.chat-h.cc', 'https://api.chat-h.cc')
    const content = '分析附件 [FILE_URL:https://chat-h.cc:4567/download/test.pdf]'
    const dialog = [{ role: 'user', content, time: '2026-11-07',
      parts: [{ type: 'file', url: ':4567/download/test.pdf', name: 'test.pdf' }] }]
    const result = JSON.parse(serializeChatDialog(dialog))
    expect(result[0].content).toBe(normalizeFileMarkers(content))
    expect(result[0].content).toContain('https://api.chat-h.cc/download/test.pdf')
    expect(result[0].parts[0].url).toBe('https://api.chat-h.cc/download/test.pdf')
    expect(result[0].time).toBe('2026-11-07')
    expect(dialog[0].content).toBe(content)
  })
})
