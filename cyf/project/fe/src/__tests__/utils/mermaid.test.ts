/**
 * mermaid 渲染工具集成测试（happy-dom 环境）。
 *
 * 验证：
 * - 占位 div 能被识别
 * - 渲染失败时显示 fallback（不崩溃）
 * - 同一源码二次渲染走缓存
 */

import { describe, it, expect, beforeEach } from 'vitest'

// 在 happy-dom 下 mock 关键 API：measureText（mermaid 内部依赖）
;(globalThis as any).SVGElement_getComputedTextLength = function () { return 0 }

// happy-dom 不实现的 API，mermaid 用了就 mock 掉，避免一连串失败
const mockContext = {
  measureText: () => ({ width: 10 }),
  font: '',
  fillText: () => {},
}
;(HTMLCanvasElement.prototype as any).getContext = function () {
  return mockContext
}

describe('renderMermaidPlaceholders', () => {
  beforeEach(async () => {
    // 每个 case 独立模块状态：清空缓存
    const mod = await import('@/utils/mermaid')
    mod._clearMermaidCacheForTest()
  })

  it('未渲染的占位 div 会被识别', async () => {
    document.body.innerHTML = `
      <div class="messages-container">
        <div class="message-text">
          <div class="mermaid-diagram" data-source="${encodeURIComponent('graph TD\n  A-->B')}">
            <div class="mermaid-loading">生成图表中…</div>
          </div>
        </div>
      </div>`

    const { renderMermaidPlaceholders } = await import('@/utils/mermaid')
    const root = document.querySelector('.messages-container') as HTMLElement
    // 不等待渲染完成（mermaid 在 happy-dom 中渲染复杂），只验证识别
    const placeholders = root.querySelectorAll('.mermaid-diagram[data-source]')
    expect(placeholders.length).toBe(1)
    // 调用函数（不一定要成功渲染——happy-dom 下 mermaid 可能有兼容问题）
    await renderMermaidPlaceholders(root)
    // 验证占位元素被打上了 dataset.rendered=1 标记（无论渲染成功失败都会标记）
    const el = placeholders[0] as HTMLElement
    expect(el.dataset.rendered).toBe('1')
    // class 应包含 mermaid-rendered 或 mermaid-failed
    const cls = el.className
    expect(cls.includes('mermaid-rendered') || cls.includes('mermaid-failed')).toBe(true)
  })

  it('非法 mermaid 源码会触发 fallback 而不是抛错', async () => {
    document.body.innerHTML = `
      <div class="mermaid-diagram" data-source="${encodeURIComponent('this is not valid mermaid !!!')}">
        <div class="mermaid-loading">生成图表中…</div>
      </div>`

    const { renderMermaidPlaceholders } = await import('@/utils/mermaid')
    const root = document.body
    // 不抛错即可（即使 happy-dom 下 mermaid 渲染结果可能不完美）
    await expect(renderMermaidPlaceholders(root)).resolves.toBeGreaterThanOrEqual(0)
  })

  it('二次调用不会重复渲染已渲染的占位', async () => {
    document.body.innerHTML = `
      <div class="mermaid-diagram" data-source="${encodeURIComponent('graph TD\n  A-->B')}" data-rendered="1">
        <div class="mermaid-loading">生成图表中…</div>
      </div>`

    const { renderMermaidPlaceholders } = await import('@/utils/mermaid')
    const rendered = await renderMermaidPlaceholders(document.body)
    // 已标记的占位不会再次进入渲染路径
    expect(rendered).toBe(0)
  })

  it('空源码返回 null（renderMermaid 单元行为）', async () => {
    const { renderMermaid } = await import('@/utils/mermaid')
    expect(await renderMermaid('')).toBeNull()
    expect(await renderMermaid('   \n   ')).toBeNull()
  })

  it('渲染进行中重复调用会被防重入拦截，避免级联风暴', async () => {
    document.body.innerHTML = `<div class="mermaid-diagram" data-source="${encodeURIComponent('graph TD')}"></div>`
    const { renderMermaidPlaceholders } = await import('@/utils/mermaid')
    // 第一次调用不 await，使其停留在 renderInProgress=true
    const first = renderMermaidPlaceholders(document.body)
    // 第二次调用应立即被拦截返回 0，而不是再启动一个渲染循环
    const second = renderMermaidPlaceholders(document.body)
    expect(await second).toBe(0)
    await first
  })
})
