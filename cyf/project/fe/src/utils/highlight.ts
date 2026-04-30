import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import cpp from 'highlight.js/lib/languages/cpp'
import csharp from 'highlight.js/lib/languages/csharp'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

const LANGUAGE_REGISTRY: Record<string, (hljs: typeof import('highlight.js/lib/core')) => void> = {
  bash,
  shell: bash,
  sh: bash,
  zsh: bash,
  c: cpp,
  cpp,
  cxx: cpp,
  cc: cpp,
  csharp,
  cs: csharp,
  css,
  go,
  golang: go,
  html: xml,
  xml,
  java,
  javascript,
  js: javascript,
  json,
  markdown,
  md: markdown,
  php,
  python,
  py: python,
  rust,
  rs: rust,
  sql,
  typescript,
  ts: typescript,
  tsx: typescript,
  vue: xml,
  yml: yaml,
  yaml,
}

for (const [name, language] of Object.entries(LANGUAGE_REGISTRY)) {
  hljs.registerLanguage(name, language)
}

const AUTO_DETECT_LANGUAGES = ['bash', 'cpp', 'css', 'go', 'java', 'javascript', 'json', 'markdown', 'php', 'python', 'rust', 'sql', 'typescript', 'xml', 'yaml']

const escapeHtml = (code: string): string => code
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

export const highlightCode = (html: string): string => {
  if (!html) return html

  return html.replace(/<pre><code(?:\s+class="([^"]*)")?>([\s\S]*?)<\/code><\/pre>/g, (_match, classStr, code) => {
    const decodedCode = code
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")

    const langMatch = classStr?.match(/language-([\w-]+)/)
    const language = langMatch?.[1]?.toLowerCase() || ''

    let highlightedCode = escapeHtml(decodedCode)
    try {
      if (language && hljs.getLanguage(language)) {
        highlightedCode = hljs.highlight(decodedCode, { language }).value
      } else {
        highlightedCode = hljs.highlightAuto(decodedCode, AUTO_DETECT_LANGUAGES).value
      }
    } catch {
      highlightedCode = escapeHtml(decodedCode)
    }

    return `<pre><code class="hljs ${classStr || ''}">${highlightedCode}</code></pre>`
  })
}

export const initHighlight = () => {
  // 目前仅保留兼容导出，实际不需要额外初始化
}
