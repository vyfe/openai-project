/**
 * mermaidExtract 单元测试：marked 输出 → 占位 div。
 *
 * 输入是 marked 渲染后的 HTML 片段（含 `<pre><code class="language-mermaid">`）。
 * 输出必须是可被 DOMPurify 接受的占位 div（带 data-source），
 * 后续由 renderMermaidPlaceholders 异步替换为 SVG。
 *
 * data-source 用 encodeURIComponent 编码：浏览器解析 HTML 属性值会把换行符
 * 规范化为空格，直接放多行源码会丢换行；编码后只含 [A-Za-z0-9%...]，可无损还原。
 */

import { describe, it, expect } from 'vitest'
import { extractMermaidBlocks } from '@/utils/mermaidExtract'

/** 从占位 div 提取 data-source 并解码还原为 mermaid 源码 */
const decodeSource = (html: string): string => {
  const encoded = html.match(/data-source="([^"]*)"/)?.[1]
  expect(encoded).toBeTruthy()
  return decodeURIComponent(encoded!)
}

describe('extractMermaidBlocks', () => {
  it('非 mermaid 代码块原样保留', () => {
    const input = '<pre><code class="language-javascript">const x = 1</code></pre>'
    expect(extractMermaidBlocks(input)).toBe(input)
  })

  it('空字符串/不含 mermaid 的输入原样返回', () => {
    expect(extractMermaidBlocks('')).toBe('')
    expect(extractMermaidBlocks('<p>hello</p>')).toBe('<p>hello</p>')
  })

  it('mermaid 代码块被替换为占位 div，源码可无损还原', () => {
    const source = 'graph TD\n  A-->B'
    const input = `<pre><code class="language-mermaid">${source}</code></pre>`
    const output = extractMermaidBlocks(input)
    expect(output).not.toContain('<pre><code')
    expect(output).toContain('class="mermaid-diagram"')
    expect(output).toContain('<div class="mermaid-loading">')
    expect(decodeSource(output)).toBe(source)
  })

  it('marked 输出的 mermaid 块带 language-mermaid class 也能识别', () => {
    const input = '<pre><code class="language-mermaid">sequenceDiagram\n  Alice->>Bob: Hi</code></pre>'
    const output = extractMermaidBlocks(input)
    expect(output).toContain('mermaid-diagram')
    expect(decodeSource(output)).toBe('sequenceDiagram\n  Alice->>Bob: Hi')
  })

  it('解码 marked 的 entity 编码后存储，源码无损还原且属性值无裸 < >', () => {
    // marked 会把源码里的 < > 编码成 &lt; &gt;。
    // 先 decodeEntities 得到 < >，再 encodeURIComponent 编码存储。
    const input = '<pre><code class="language-mermaid">graph LR\n  A--&gt;|label| B\n  A &lt;--&gt; B</code></pre>'
    const output = extractMermaidBlocks(input)
    const encoded = output.match(/data-source="([^"]*)"/)?.[1]!
    expect(decodeURIComponent(encoded)).toBe('graph LR\n  A-->|label| B\n  A <--> B')
    expect(encoded).not.toMatch(/[<>]/)
  })

  it('源码中含引号不破坏 HTML 属性，且源码无损还原', () => {
    const input = '<pre><code class="language-mermaid">graph TD\n  A--&quot;label&quot;--&gt;B</code></pre>'
    const output = extractMermaidBlocks(input)
    expect(output).toMatch(/<div class="mermaid-diagram"[^>]*data-source="/)
    expect(decodeSource(output)).toBe('graph TD\n  A--"label"-->B')
  })

  it('多行中文源码的换行符经编码后不落入属性值', () => {
    const source = 'sequenceDiagram\n    actor User as 开发者\n    User->>Kiro: 提出需求'
    const input = `<pre><code class="language-mermaid">${source}</code></pre>`
    const output = extractMermaidBlocks(input)
    const encoded = output.match(/data-source="([^"]*)"/)?.[1]!
    // 属性值里不能出现真实换行符（否则浏览器会规范化为空格）
    expect(encoded).not.toMatch(/\n/)
    expect(decodeURIComponent(encoded)).toBe(source)
  })

  it('多个 mermaid 块都正确处理', () => {
    const input = [
      '<p>intro</p>',
      '<pre><code class="language-mermaid">graph TD\n  A--&gt;B</code></pre>',
      '<p>middle</p>',
      '<pre><code class="language-mermaid">pie title X\n  "A" : 50</code></pre>',
      '<pre><code class="language-javascript">const x = 1</code></pre>'
    ].join('\n')
    const output = extractMermaidBlocks(input)
    expect((output.match(/mermaid-diagram/g) || []).length).toBe(2)
    expect(output).toContain('class="language-javascript"')
    expect(output).toContain('<p>intro</p>')
    expect(output).toContain('<p>middle</p>')
  })

  it('占位 div 包含 data-source-hash 用于调试', () => {
    const input = '<pre><code class="language-mermaid">graph TD</code></pre>'
    const output = extractMermaidBlocks(input)
    expect(output).toMatch(/data-source-hash="[a-z0-9]+"/)
  })
})
