/**
 * 把 marked 渲染后的 HTML 中 ```mermaid 代码块替换为占位 div，供 mermaid 异步渲染。
 *
 * 处理顺序：在 marked → protectCodeBlocks → DOMPurify 之间调用。
 *
 * 输入 HTML 形如：
 *   <pre><code class="language-mermaid">graph TD\n  A-->B</code></pre>
 *
 * 输出（占位符）：
 *   <div class="mermaid-diagram" data-source="..." data-source-hash="..."><div class="mermaid-loading"></div></div>
 *
 * 这样 DOMPurify sanitize 之后 mermaid 仍然能在前端异步渲染。
 *
 * 不匹配非 mermaid 代码块，原样返回。
 */

const MERMAID_BLOCK_RE = /<pre>\s*<code[^>]*class="[^"]*\blanguage-mermaid\b[^"]*"[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/g

/** 解码 marked 转义（marked 把 `>` 等做了 entity encode） */
function decodeEntities(s: string): string {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

/** 简单 hash，用于 data-source-hash 调试（不用于安全） */
function shortHash(s: string): string {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  return (h >>> 0).toString(36)
}

/** 把 mermaid 块转为占位 div */
export function extractMermaidBlocks(html: string): string {
  if (!html || !html.includes('language-mermaid')) return html
  return html.replace(MERMAID_BLOCK_RE, (_match, rawSource: string) => {
    const source = decodeEntities(rawSource)
    const hash = shortHash(source)
    // 用 encodeURIComponent 编码：浏览器解析 HTML 属性值时会把手动换行符规范化为空格，
    // 直接把多行源码放进 data-source 会导致源码变单行、mermaid 渲染失败。
    // 编码后只剩 [A-Za-z0-9%...]，无换行/<>/&，可安全穿过 DOMPurify 与 v-html。
    return `<div class="mermaid-diagram" data-source="${encodeURIComponent(source)}" data-source-hash="${hash}"><div class="mermaid-loading"></div></div>`
  })
}
