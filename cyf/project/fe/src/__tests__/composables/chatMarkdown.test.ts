import { describe, expect, it } from 'vitest'
import { normalizeAsciiDiagramBlocks, renderMathOutsideHtmlTags, renderRichText } from '@/composables/chat/chatMarkdown'

describe('chatMarkdown', () => {
  it('渲染 GFM 粗体与代码块高亮', () => {
    const html = renderRichText('**粗体**\n\n```js\nconst a = 1\n```')
    expect(html).toContain('<strong>粗体</strong>')
    expect(html).toContain('hljs-keyword')
    expect(html).toContain('hljs-number')
  })

  it('把 mermaid 代码块转成占位节点', () => {
    const html = renderRichText('```mermaid\ngraph TD;A-->B\n```')
    expect(html).toContain('mermaid')
    expect(html).not.toContain('graph TD')
  })

  it('渲染行内与块级数学公式', () => {
    const inline = renderRichText('价格 $x^2$ 与公式')
    expect(inline).toContain('katex')
    const block = renderRichText('$$a^2+b^2=c^2$$')
    expect(block).toContain('katex-display')
  })

  it('价格文本不会被当成公式', () => {
    const html = renderMathOutsideHtmlTags('这是 12.50 元')
    expect(html).toBe('这是 12.50 元')
  })

  it('HTML 标签内的 $ 不会被公式替换', () => {
    const html = renderMathOutsideHtmlTags('<a href="/a$b">链接</a>')
    expect(html).toBe('<a href="/a$b">链接</a>')
  })

  it('带制表符的多行文本提升为 ASCII 图', () => {
    const html = normalizeAsciiDiagramBlocks('<p>+--+<br>|  |</p>')
    expect(html).toContain('ascii-diagram')
  })

  it('普通段落不受 ASCII 图规则影响', () => {
    const html = normalizeAsciiDiagramBlocks('<p>普通段落</p>')
    expect(html).toBe('<p>普通段落</p>')
  })
})
