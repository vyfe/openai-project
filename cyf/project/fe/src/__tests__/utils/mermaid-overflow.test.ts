/**
 * v-html 重渲染覆盖场景的回归测试。
 *
 * 触发链路：
 * 1. renderMermaidPlaceholders 把 SVG 注入占位 div
 * 2. Vue 响应式数据变化 → v-html 重渲染 → 新占位 div 替换原占位 div → SVG 被覆盖
 * 3. 此时 watch(messages) 不触发（messages 数组引用未变）
 * 4. MutationObserver 必须检测到新的占位 div 并立即重新渲染
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { renderMermaidPlaceholders } from '@/utils/mermaid'
import { extractMermaidBlocks } from '@/utils/mermaidExtract'

describe('v-html 重渲染覆盖场景', () => {
  beforeEach(async () => {
    const mod = await import('@/utils/mermaid')
    mod._clearMermaidCacheForTest()
    document.body.innerHTML = ''
  })

  it('新插入的占位 div 应被 MutationObserver 捕获并重新渲染', async () => {
    document.body.innerHTML = `<div class="messages-container"></div>`
    const container = document.querySelector('.messages-container') as HTMLElement

    // 模拟 ChatContent.vue 的 MutationObserver 兜底逻辑
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of Array.from(mutation.addedNodes)) {
          if (node.nodeType === 1 && (node as Element).classList?.contains('mermaid-diagram')) {
            renderMermaidPlaceholders(container).catch(() => {})
            return
          }
        }
      }
    })
    observer.observe(container, { childList: true, subtree: true })

    // 1. 第一次插入占位 div（模拟 v-html 渲染）
    const html1 = extractMermaidBlocks('<pre><code class="language-mermaid">graph TD\n  A-->B</code></pre>')
    container.innerHTML = html1

    // 等 observer + renderMermaidPlaceholders 跑完
    await new Promise(r => setTimeout(r, 200))

    const first = container.querySelector('.mermaid-diagram') as HTMLElement
    // mermaid 在 happy-dom 下渲染会失败回退到 mermaid-failed —— 但占位已被标记为 rendered
    expect(first.dataset.rendered).toBe('1')

    // 2. 模拟 v-html 重渲染：覆盖整个 innerHTML
    const html2 = extractMermaidBlocks('<pre><code class="language-mermaid">graph LR\n  X--&gt;Y</code></pre>')
    container.innerHTML = html2

    // 等 observer 触发 + renderMermaidPlaceholders 跑完
    await new Promise(r => setTimeout(r, 200))

    const second = container.querySelector('.mermaid-diagram') as HTMLElement
    // 新占位 div 也应该被标记（说明 renderMermaidPlaceholders 被调用）
    expect(second.dataset.rendered).toBe('1')
    expect(second.classList.contains('mermaid-rendered') || second.classList.contains('mermaid-failed')).toBe(true)

    observer.disconnect()
  })

  it('observer 不应在非占位 div 节点上触发', async () => {
    document.body.innerHTML = `<div class="messages-container"></div>`
    const container = document.querySelector('.messages-container') as HTMLElement

    const renderSpy = vi.fn()
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of Array.from(mutation.addedNodes)) {
          if (node.nodeType === 1 && (node as Element).classList?.contains('mermaid-diagram')) {
            renderSpy()
          }
        }
      }
    })
    observer.observe(container, { childList: true, subtree: true })

    // 插入非 mermaid 节点
    container.innerHTML = '<p>普通文本</p>'
    await new Promise(r => setTimeout(r, 50))
    expect(renderSpy).not.toHaveBeenCalled()

    // 插入 mermaid 占位
    const html = extractMermaidBlocks('<pre><code class="language-mermaid">graph TD</code></pre>')
    container.innerHTML = html
    await new Promise(r => setTimeout(r, 50))
    expect(renderSpy).toHaveBeenCalledTimes(1)

    observer.disconnect()
  })
})
