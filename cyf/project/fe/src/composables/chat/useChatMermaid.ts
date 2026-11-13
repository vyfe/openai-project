// mermaid 渲染与 MutationObserver 兜底。
// 依赖消息容器与消息列表，负责在 DOM 重渲染后重新渲染占位符。
import { nextTick, onBeforeUnmount, onMounted, watch, type Ref } from 'vue'
import { renderMermaidPlaceholders } from '@/utils/mermaid'
import type { ChatMessage } from './types'

export function useChatMermaid(
  messagesContainer: Ref<HTMLElement | undefined>,
  messages: ChatMessage[],
) {
  let observer: MutationObserver | null = null

  /** 触发 mermaid 占位符渲染（统一 nextTick + 错误捕获）。 */
  const triggerMermaidRender = () => {
    nextTick(() => {
      if (!messagesContainer.value) return
      renderMermaidPlaceholders(messagesContainer.value).catch((err: unknown) => {
        console.warn('[mermaid] 渲染占位符失败', err)
      })
    })
  }

  /**
   * v-html 重渲染会产生新的 .mermaid-diagram 占位 div，watch(messages) 覆盖不到
   * 整个 message-text 被替换的场景，因此用 MutationObserver 兜底。
   * 只监听 childList，避免渲染完成后的 class/innerHTML 变更再次触发渲染。
   */
  const setupMermaidObserver = () => {
    const container = messagesContainer.value
    if (!container) return
    if (observer) return
    observer = new MutationObserver((mutations) => {
      const hasNewPlaceholder = mutations.some((mutation) =>
        Array.from(mutation.addedNodes).some((node) => {
          if (!(node instanceof HTMLElement)) return false
          return node.classList?.contains('mermaid-diagram') || node.querySelector?.('.mermaid-diagram') != null
        }),
      )
      if (hasNewPlaceholder) {
        triggerMermaidRender()
      }
    })
    observer.observe(container, { childList: true, subtree: true })
  }

  // 内容变化但 length 不变（如流式追加）也需要重渲染
  watch(messages, () => triggerMermaidRender(), { deep: true })

  onMounted(() => {
    triggerMermaidRender()
    nextTick(() => setupMermaidObserver())
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return { triggerMermaidRender, setupMermaidObserver }
}
