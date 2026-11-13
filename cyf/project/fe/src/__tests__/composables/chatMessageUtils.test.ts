import { describe, expect, it } from 'vitest'
import {
  extractFileUrls,
  getCopyText,
  getTextContent,
  getToolResultParts,
  getToolSources,
  isImageUrl,
  sanitizeDialogTitle,
} from '@/composables/chat/messageUtils'
import type { MessagePart } from '@/composables/chat/types'

describe('聊天消息工具函数', () => {
  it('提取新旧两种附件标记', () => {
    const urls = extractFileUrls(
      '正文 [FILE_URL:https://cdn.example.com/a.pdf] 和 文件已上传: https://cdn.example.com/b.png',
    )
    expect(urls).toEqual(['https://cdn.example.com/a.pdf', 'https://cdn.example.com/b.png'])
  })

  it('忽略空内容与无标记内容', () => {
    expect(extractFileUrls('')).toEqual([])
    expect(extractFileUrls('普通文本')).toEqual([])
  })

  it('getTextContent 移除附件标记与多余空行', () => {
    const text = getTextContent('第一行\n\n\n[FILE_URL:https://x/a.png]\n第二行')
    expect(text).toBe('第一行\n\n第二行')
  })

  it('标题压缩空白并兜底', () => {
    expect(sanitizeDialogTitle('  你好   世界  ')).toBe('你好 世界')
    expect(sanitizeDialogTitle('[FILE_URL:https://x/a.png]')).toBe('对话')
  })

  it('识别图片扩展名（含查询串）', () => {
    expect(isImageUrl('https://x/a.PNG?x=1')).toBe(true)
    expect(isImageUrl('https://x/a.pdf')).toBe(false)
  })

  it('复制文本优先使用 text parts', () => {
    const parts: MessagePart[] = [
      { type: 'text', text: '第一段' },
      { type: 'image', url: 'https://x/a.png' },
      { type: 'text', text: '第二段' },
    ]
    expect(getCopyText({ content: '原始内容', parts })).toBe('第一段\n第二段')
    expect(getCopyText({ content: '原始内容' })).toBe('原始内容')
  })

  it('提取工具结果与来源', () => {
    const parts: MessagePart[] = [
      {
        type: 'tool_result',
        text: '结果',
        data: { sources: [{ url: 'https://a', title: 'A' }] },
      },
      { type: 'text', text: '普通文本' },
    ]
    const toolParts = getToolResultParts(parts)
    expect(toolParts).toHaveLength(1)
    expect(getToolSources(toolParts[0])).toEqual([{ url: 'https://a', title: 'A' }])
    expect(getToolSources(parts[1])).toEqual([])
  })
})
