// 聊天消息相关的纯函数工具。
// 这些函数不依赖组件状态，便于单测，也避免 ChatContent 继续膨胀。
import { normalizeFileUrl } from '@/services/backendUrl'
import type { ChatMessage, MessagePart } from './types'

/** 当前时间的 HH:mm 展示值。 */
export function getCurrentTime(): string {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 当前时间的 YYYY-MM-DD HH:mm:ss 展示值。 */
export function getCurrentDateTime(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

/** 从消息内容中提取文件 URL 列表（兼容新旧格式）。 */
export function extractFileUrls(content: string): string[] {
  if (!content) return []

  const urls: string[] = []
  const patterns = [
    { regex: /\[FILE_URL:(https?:\/\/[^\]]+)\]/g }, // 新格式: [FILE_URL:http://xxx]
    { regex: /\[FILE_URL:((?!https?:\/\/)[^\]]+)\]/g }, // 新格式相对路径
    { regex: /文件已上传:\s*(https?:\/\/[^\s]+)/g }, // 旧格式绝对地址
    { regex: /文件已上传:\s*((?!https?:\/\/)[^\s]+)/g }, // 旧格式相对路径
  ]

  patterns.forEach(({ regex }) => {
    let match: RegExpExecArray | null
    while ((match = regex.exec(content)) !== null) {
      urls.push(normalizeFileUrl(match[1]))
    }
  })

  return urls
}

/** 获取纯文本内容（移除文件标记）。 */
export function getTextContent(content: string): string {
  if (content === null || content === undefined) {
    return ''
  }
  return String(content)
    .replace(/\[FILE_URL:[^\]]+\]/g, '')
    .replace(/\[文件已上传:[^\]]+\]/g, '')
    .replace(/文件已上传:\s*(https?:\/\/[^\s]+|[^\s]+)/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** 用整段文本生成对话标题。 */
export function sanitizeDialogTitle(content: string): string {
  return getTextContent(content).replace(/\s+/g, ' ').trim() || '对话'
}

/** 判断 URL 是否指向图片。 */
export function isImageUrl(url: string): boolean {
  return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url)
}

/** 从消息对象提取可复制文本：优先用 parts 中的 text 部分，回退到 content。 */
export function getCopyText(msg: Pick<ChatMessage, 'parts' | 'content'>): string {
  const textParts = (msg.parts || [])
    .filter((part): part is Extract<MessagePart, { type: 'text' }> => part.type === 'text' && !!(part as { text?: string }).text)
  if (textParts.length > 0) {
    return textParts.map((part) => part.text).join('\n')
  }
  return msg.content || ''
}

/** 提取 tool_result 部件。 */
export function getToolResultParts(parts?: MessagePart[]): Extract<MessagePart, { type: 'tool_result' }>[] {
  return (parts || []).filter(
    (part): part is Extract<MessagePart, { type: 'tool_result' }> => part?.type === 'tool_result',
  )
}

/** 提取 tool_result 部件里的搜索来源。 */
export function getToolSources(part: MessagePart): Array<{ url: string; title?: string }> {
  if (part.type !== 'tool_result') return []
  const sources = (part.data as { sources?: unknown } | undefined)?.sources
  return Array.isArray(sources) ? (sources as Array<{ url: string; title?: string }>) : []
}
