// Markdown / 数学公式渲染链路。
// 从 ChatContent.vue 拆出：纯函数、无组件状态，便于单测。
import katex from 'katex'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { highlightCode } from '@/utils/highlight'
import { extractMermaidBlocks } from '@/utils/mermaidExtract'

// 配置 marked 启用 GFM（GitHub Flavored Markdown）支持
marked.use({
  gfm: true,
  breaks: true,
})

const mathRenderer = {
  inlineMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: false,
      })
    } catch (error) {
      console.warn('KaTeX rendering error:', error)
      return `$${math}$`
    }
  },
  displayMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: true,
      })
    } catch (error) {
      console.warn('KaTeX rendering error:', error)
      return `$$${math}$$`
    }
  },
}

const decodeMathEntities = (text: string) =>
  text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")

const renderMathInPlainTextSegment = (text: string) => {
  const decodedText = decodeMathEntities(text)
  let processedText = decodedText.replace(/\$\$\s*([\s\S]*?)\s*\$\$/g, (_, math) =>
    mathRenderer.displayMath(String(math || '').trim()),
  )

  processedText = processedText.replace(/\$([^{][^$]*?)\$/g, (_, math) => {
    const mathText = String(math || '')
    if (mathText.includes('katex') || mathText.includes('class="katex')) {
      return `$${mathText}$`
    }
    // 价格文本不按数学公式渲染
    const pricePattern = /^\s*\d+(\.\d{1,2})?\s*$/
    if (pricePattern.test(mathText)) {
      return `$${mathText}$`
    }
    return mathRenderer.inlineMath(mathText.trim())
  })

  return processedText
}

/** 只对 HTML 标签之外的文本渲染数学公式，避免破坏标签属性。 */
export const renderMathOutsideHtmlTags = (html: string) => {
  const htmlTagRegex = /<(\/?[a-zA-Z][a-zA-Z0-9-]*(?:\s[^>]*)?)>|<!--[\s\S]*?-->/g
  const parts: Array<{ content: string; isHtml: boolean }> = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = htmlTagRegex.exec(html)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ content: html.substring(lastIndex, match.index), isHtml: false })
    }
    parts.push({ content: match[0], isHtml: true })
    lastIndex = htmlTagRegex.lastIndex
  }

  if (lastIndex < html.length) {
    parts.push({ content: html.substring(lastIndex), isHtml: false })
  }

  return parts.map((part) => (part.isHtml ? part.content : renderMathInPlainTextSegment(part.content))).join('')
}

const patchOrderedListStart = (html: string) => {
  return html.replace(
    /<ol(\s+(?:[^>]*?\s+)?start\s*=\s*["']?(\d+)["']?(?:\s+[^>]*)?|\s+[^>]*?)>/gi,
    (match, attributes, startNum) => {
      if (!startNum) return match
      const num = parseInt(startNum, 10)
      const cssCounterValue = num - 1
      const cleanedAttributes = String(attributes || '').replace(/\s*start\s*=\s*["']?\d+["']?\s*/i, '').trim()
      return `<ol${cleanedAttributes} start="${num}" style="--ol-start: ${cssCounterValue};" class="ordered-list-with-start">`
    },
  )
}

const parseMarkdownToHtml = (content: string) => {
  const preprocessedContent = (content || '').replace(/\*\*“([^”]*?)”\*\*/g, '**$1**')
  try {
    const parsed = marked.parse(preprocessedContent)
    if (parsed instanceof Promise) {
      return preprocessedContent
    }
    return typeof parsed === 'string' ? parsed.trim() : String(parsed)
  } catch (error) {
    console.error('Markdown parsing error:', error)
    return preprocessedContent
  }
}

const protectCodeBlocks = (html: string) => {
  const protectedBlocks: string[] = []
  const protectedHtml = html.replace(
    /<pre><code[^>]*>[\s\S]*?<\/code><\/pre>|<code[^>]*>[\s\S]*?<\/code>/g,
    (match) => {
      protectedBlocks.push(match)
      return `__CODE_BLOCK_PLACEHOLDER_${protectedBlocks.length - 1}__`
    },
  )
  return { protectedHtml, protectedBlocks }
}

const restoreCodeBlocks = (html: string, protectedBlocks: string[]) => {
  let restoredHtml = html
  for (let i = 0; i < protectedBlocks.length; i++) {
    restoredHtml = restoredHtml.replace(`__CODE_BLOCK_PLACEHOLDER_${i}__`, protectedBlocks[i])
  }
  return restoredHtml
}

const sanitizeRichHtml = (html: string) => {
  return DOMPurify.sanitize(html, {
    ADD_ATTR: [
      'target',
      'rel',
      'class',
      'style',
      'start',
      'aria-hidden',
      'data-code',
      'type',
      'data-source',
      'data-source-hash',
      'data-rendered',
    ],
  })
}

/** 把 ASCII 图（含制表符 / 多个空格）从段落提升为 pre，避免被折叠。 */
export const normalizeAsciiDiagramBlocks = (html: string) => {
  if (!html) return html
  return html.replace(/<p>([\s\S]*?)<\/p>/g, (match, inner) => {
    const text = String(inner || '')
    if (!text.includes('\t') && text.indexOf('  ') === -1) {
      return match
    }
    const normalized = text
      .replace(/\t/g, '    ')
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/&nbsp;/g, ' ')
      .trim()
    const lines = normalized.split('\n')
    const looksLikeDiagram = lines.length >= 2 && lines.some((line) => /[+\-|│┌┐└┘├┤┬┴┼]/.test(line))
    if (!looksLikeDiagram) {
      return match
    }
    return `<pre class="ascii-diagram"><code>${normalized}</code></pre>`
  })
}

/** 完整渲染链路：Markdown → mermaid 占位 → 数学公式 → ASCII 图 → 代码高亮 → 消毒。 */
export const renderRichText = (content: string) => {
  if (!content) return ''

  let html = parseMarkdownToHtml(content)
  html = patchOrderedListStart(html)

  // 把 ```mermaid 代码块转为占位 div，供 mermaid 异步渲染
  html = extractMermaidBlocks(html)

  const { protectedHtml, protectedBlocks } = protectCodeBlocks(html)
  let rendered = renderMathOutsideHtmlTags(protectedHtml)
  rendered = restoreCodeBlocks(rendered, protectedBlocks)
  rendered = normalizeAsciiDiagramBlocks(rendered)

  // 为 Markdown 图片追加预览样式
  rendered = rendered.replace(/<img\s+([^>]*?)>/gi, '<img $1 class="attachment-preview" />')
  rendered = highlightCode(rendered)

  return sanitizeRichHtml(rendered)
}
