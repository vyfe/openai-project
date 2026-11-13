import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { useChatScroll } from '@/composables/chat/useChatScroll'
import { useChatMessageActions } from '@/composables/chat/useChatMessageActions'
import type { ChatMessage } from '@/composables/chat/types'
import type { FormData } from '@/utils/main'

function createFormData(overrides: Partial<FormData> = {}): FormData {
  return {
    isScrolledToBottom: true,
    ...overrides,
  } as FormData
}

function createScroller(scrollHeight = 1000, clientHeight = 200) {
  const el = document.createElement('div')
  Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true })
  Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true })
  el.scrollTop = 0
  return el
}

describe('useChatScroll', () => {
  it('滚到底部时按 scrollHeight - clientHeight 计算', () => {
    const el = createScroller()
    const formData = createFormData()
    const scroll = useChatScroll(ref(el), formData)
    scroll.scrollToBottom()
    expect(el.scrollTop).toBe(800)
  })

  it('用户不在底部时不强制滚动', () => {
    const el = createScroller()
    const formData = createFormData({ isScrolledToBottom: false })
    const scroll = useChatScroll(ref(el), formData)
    scroll.scrollToBottom()
    expect(el.scrollTop).toBe(0)
  })

  it('滚动位置同步回 showBackToTop 与 isScrolledToBottom', () => {
    const el = createScroller()
    const formData = createFormData()
    const scroll = useChatScroll(ref(el), formData)

    el.scrollTop = 500
    scroll.handleScroll()
    expect(scroll.showBackToTop.value).toBe(true)
    expect(formData.isScrolledToBottom).toBe(false)

    el.scrollTop = 800
    scroll.handleScroll()
    expect(scroll.showBackToTop.value).toBe(true)
    expect(formData.isScrolledToBottom).toBe(true)
  })

  it('async scrollToBottomOnNewMessage 在下一帧生效', async () => {
    const el = createScroller()
    const formData = createFormData()
    const scroll = useChatScroll(ref(el), formData)
    scroll.scrollToBottomOnNewMessage()
    await nextTick()
    expect(el.scrollTop).toBe(800)
  })
})

describe('useChatMessageActions', () => {
  const t = ((key: string) => key) as never

  it('选中计数与删除单条消息', () => {
    const messages: ChatMessage[] = [
      { type: 'ai', content: '欢迎', time: '00:00' },
      { type: 'user', content: '你好', time: '00:01' },
    ]
    const actions = useChatMessageActions(messages, t)
    actions.toggleMessageSelection(1, true)
    expect(actions.selectedCount.value).toBe(1)

    actions.deleteMessage(1)
    expect(messages).toHaveLength(1)
  })

  it('欢迎消息不可删除', () => {
    const messages: ChatMessage[] = [{ type: 'ai', content: 'chat.aiWelcomeMessage', time: '00:00' }]
    const actions = useChatMessageActions(messages, t)
    actions.deleteMessage(0)
    expect(messages).toHaveLength(1)
  })

  it('批量删除跳过欢迎消息并清理选中态', async () => {
    const messages: ChatMessage[] = [
      { type: 'ai', content: 'chat.aiWelcomeMessage', time: '00:00', selected: true },
      { type: 'user', content: '你好', time: '00:01', selected: true },
    ]
    const actions = useChatMessageActions(messages, t)
    await actions.deleteSelectedMessages()
    expect(messages).toHaveLength(1)
    expect(messages[0].content).toBe('chat.aiWelcomeMessage')
    expect(messages[0].selected).toBe(false)
  })
})
