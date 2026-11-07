// 独立托管时显式配置后端；本机和原有同源部署保持默认行为。
export const getApiBaseUrl = () => {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured) return configured.replace(/\/+$/, '')
  return import.meta.env.DEV ? 'http://localhost:39997' : window.location.origin
}

export const API_BASE_URL = getApiBaseUrl()

const configuredFileBase = import.meta.env.VITE_FILE_BASE_URL?.trim().replace(/\/+$/, '')
const fileBase = configuredFileBase || API_BASE_URL

/** 上传、历史附件和生成图片共用，外部供应商的绝对地址保持原样。 */
export const normalizeFileUrl = (value: string): string => {
  if (!value) return ''
  const legacyPath = value.match(/^:4567(\/download\/.*)$/)?.[1]
  if (legacyPath && configuredFileBase) return new URL(legacyPath, fileBase).href
  if (value.startsWith(':')) {
    const base = new URL(API_BASE_URL)
    return `${base.protocol}//${base.hostname}${value}`
  }
  if (/^https?:\/\//i.test(value)) {
    const url = new URL(value)
    // 已保存的旧附件使用 chat-h.cc:4567，切换 CDN 后迁到 HTTPS 文件入口。
    if (configuredFileBase && url.port === '4567' && url.pathname.startsWith('/download/') &&
        [new URL(API_BASE_URL).hostname, 'chat-h.cc'].includes(url.hostname)) {
      return new URL(url.pathname + url.search + url.hash, fileBase).href
    }
    return value
  }
  return new URL(value, `${fileBase}/`).href
}

// 请求上下文也要迁移旧附件，确保模型读取历史文件时不再访问 CDN 的旧端口。
export const normalizeFileMarkers = (content: string): string =>
  content.replace(/\[FILE_URL:([^\]]+)\]/g, (_, url: string) => `[FILE_URL:${normalizeFileUrl(url)}]`)

export const serializeChatDialog = (dialog: unknown): string => JSON.stringify(dialog, (key, value) => {
  if (typeof value !== 'string') return value
  if (key === 'url') return normalizeFileUrl(value)
  return key === 'content' || key === 'text' ? normalizeFileMarkers(value) : value
})
