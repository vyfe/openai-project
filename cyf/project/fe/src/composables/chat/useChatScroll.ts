// 聊天消息区的滚动行为：回到底部、回到顶部、滚动位置同步。
import { nextTick, ref, type Ref } from 'vue'
import type { FormData } from '@/utils/main'

function debounce<T extends (...args: never[]) => void>(func: T, wait: number) {
  let timeout: number | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = window.setTimeout(() => func(...args), wait)
  }
}

export function useChatScroll(
  messagesContainer: Ref<HTMLElement | undefined>,
  formData: FormData,
) {
  const showBackToTop = ref(false)

  const scrollToTop = () => {
    messagesContainer.value?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  /** 智能滚动到底部；force=true 时忽略用户是否正在查看历史。 */
  const scrollToBottom = (force = false) => {
    const container = messagesContainer.value
    if (!container) return
    if (!force && !formData.isScrolledToBottom) return
    container.scrollTop = container.scrollHeight - container.clientHeight
  }

  const handleScroll = () => {
    const container = messagesContainer.value
    if (!container) return
    const { scrollTop, scrollHeight, clientHeight } = container

    // 滚动超过一屏时显示回到顶部按钮
    showBackToTop.value = scrollTop > clientHeight

    const threshold = 10
    formData.isScrolledToBottom = scrollHeight - scrollTop - clientHeight < threshold
  }

  const debouncedHandleScroll = debounce(handleScroll, 100)

  /** 新消息的滚动：等 DOM 更新后再滚，避免高度未计算完。 */
  const scrollToBottomOnNewMessage = () => {
    if (!messagesContainer.value) return
    if (!formData.isScrolledToBottom) return
    nextTick(() => {
      const container = messagesContainer.value
      if (!container) return
      container.scrollTop = container.scrollHeight - container.clientHeight
    })
  }

  return {
    showBackToTop,
    scrollToTop,
    scrollToBottom,
    scrollToBottomOnNewMessage,
    handleScroll,
    debouncedHandleScroll,
  }
}
