/**
 * Mermaid 图表渲染工具（单例 lazy-loaded）。
 *
 * 关键点：
 * - mermaid 包体 ~600KB，使用动态 import 按需加载
 * - 单例避免重复 initialize
 * - 同一图表源码缓存渲染结果（debounce 同一会话反复出现的同一图）
 */

import type mermaidType from 'mermaid'

let mermaidInstance: typeof mermaidType | null = null
let initializePromise: Promise<void> | null = null
const renderCache = new Map<string, string>()  // source -> svg
let renderInProgress = false  // 渲染中标志：打断 MutationObserver 级联触发

/**
 * 懒加载 mermaid 包。第一次调用时下载 + initialize，之后复用单例。
 */
export async function getMermaid(): Promise<typeof mermaidType> {
  if (mermaidInstance) return mermaidInstance
  if (!initializePromise) {
    initializePromise = (async () => {
      const mod = await import('mermaid')
      const m = mod.default
      m.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'strict',
        fontFamily: 'inherit',
        // 语法错误时抛异常而非渲染内置"错误图"（含 "Syntax error in text"），
        // 这样 renderMermaid 的 try-catch 能兜住并回退显示源码。
        suppressErrorRendering: true
      })
      mermaidInstance = m
    })()
  }
  await initializePromise
  return mermaidInstance!
}

/**
 * 渲染单个 mermaid 源码为 SVG 字符串。失败时返回 null（调用方应回退显示源码）。
 */
export async function renderMermaid(source: string): Promise<string | null> {
  const trimmed = source.trim()
  if (!trimmed) return null
  const cached = renderCache.get(trimmed)
  if (cached !== undefined) return cached

  try {
    const m = await getMermaid()
    const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`
    const result = await m.render(id, trimmed)
    const svg = result?.svg ?? ''
    // mermaid v11 在缺少 DOM 测量 API 的环境（如 happy-dom、部分 SSR 框架）
    // 不会抛错但返回空字符串。空 svg 必须视为失败，避免静默"成功"
    if (!svg || svg.length < 10) {
      console.warn('[mermaid] 渲染返回空 svg', { id, sourceLen: trimmed.length })
      return null
    }
    renderCache.set(trimmed, svg)
    return svg
  } catch (error) {
    console.warn('[mermaid] 渲染失败', error)
    return null
  }
}

/**
 * 在容器中找到所有 class 包含 mermaid-diagram 的占位 div 并渲染。
 * 返回成功渲染的数量（用于测试断言）。
 */
export async function renderMermaidPlaceholders(root: HTMLElement | Document): Promise<number> {
  // 防重入：本函数内部对每个占位执行 classList.add，会触发监听 class 的 MutationObserver，
  // observer 又回调本函数，形成 O(n²) 级联渲染风暴（大量消息时卡死主线程）。
  // 渲染中直接返回，剩余占位由当前正在运行的循环兜底完成。
  if (renderInProgress) return 0
  renderInProgress = true
  try {
    const placeholders = root.querySelectorAll<HTMLElement>('.mermaid-diagram[data-source]')
    let rendered = 0
    // 串行渲染避免 DOM 竞态（mermaid.render 需要唯一 id）
    for (const el of Array.from(placeholders)) {
      if (el.dataset.rendered === '1') continue
      const source = decodeURIComponent(el.dataset.source ?? '')
      const svg = await renderMermaid(source)
      if (svg) {
        // 用 DOM 操作避免触发 v-html 重渲染
        el.innerHTML = svg
        el.dataset.rendered = '1'
        el.classList.add('mermaid-rendered')
        rendered++
      } else {
        // 渲染失败：显示原始源码在 <pre><code>
        el.innerHTML = `<pre class="mermaid-fallback"><code>${escapeHtml(source)}</code></pre>`
        el.dataset.rendered = '1'
        el.classList.add('mermaid-failed')
      }
    }
    return rendered
  } finally {
    renderInProgress = false
  }
}

/** HTML escape（用于 fallback 显示） */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 单元测试辅助：清空渲染缓存与渲染标志 */
export function _clearMermaidCacheForTest(): void {
  renderCache.clear()
  renderInProgress = false
}
