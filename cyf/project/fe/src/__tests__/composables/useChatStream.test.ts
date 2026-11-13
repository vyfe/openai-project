import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useChatStream } from '@/composables/chat/useChatStream'
import type { ChatMessage } from '@/composables/chat/types'
import type { FormData } from '@/utils/main'

function createFormData(overrides: Partial<FormData> = {}): FormData {
  return {
    isDarkTheme: false,
    currentDialogId: null,
    selectedModel: 'test-model',
    selectedModelType: 1,
    selectedModelAllowNet: true,
    enabledTools: [],
    contextCount: 2,
    sidebarCollapsed: false,
    maxResponseChars: 4000,
    isMobile: false,
    streamEnabled: true,
    systemPrompt: '',
    sendPreference: 'enter',
    dialogTitle: '',
    dialogHistory: [],
    loadingHistory: false,
    historyDaysRange: null,
    isLoading: false,
    contextTotalTokens: 0,
    models: [],
    groupedModels: {},
    providers: [],
    providerValue: '',
    modelValue: '',
    currentModelDesc: '',
    enhancedRoleEnabled: false,
    enhancedRoleGroups: {},
    activeEnhancedGroup: '',
    selectedEnhancedRole: '',
    rolePresets: [],
    activeRoleId: 'default',
    fontSize: 'medium',
    isScrolledToBottom: true,
    ...overrides,
  } as FormData
}

function createStream(messages: ChatMessage[], formData: FormData) {
  return useChatStream({
    messages,
    formData,
    isLoading: ref(false),
    inputMessage: ref(''),
    getSessionKey: () => 'tab-1',
    sessionAbortControllers: ref({}),
    sessionRequestIds: ref({}),
    sessionAiIndexes: ref({}),
    sessionWaitingTimers: ref({}),
    sessionWaitingShown: ref({}),
    sessionLoadingStore: ref({}),
    setSessionLoading: vi.fn(),
    mutateSessionMessages: (_key, mutator) => mutator(messages),
    buildRoleSetting: () => ({}),
    setContextUsage: vi.fn(),
    scrollToBottom: vi.fn(),
    scrollToBottomOnNewMessage: vi.fn(),
    onDialogCreated: vi.fn(),
    onRefreshHistory: vi.fn(),
    t: ((key: string) => key) as never,
    welcomeMessage: '欢迎',
  })
}

describe('useChatStream', () => {
  it('按 contextCount 截取上下文并追加当前问题', () => {
    const messages: ChatMessage[] = [
      { type: 'ai', content: '欢迎', time: '00:00' },
      { type: 'user', content: '问题1', time: '00:01' },
      { type: 'ai', content: '回答1', time: '00:02' },
      { type: 'user', content: '问题2', time: '00:03' },
      { type: 'ai', content: '回答2', time: '00:04' },
    ]
    const stream = createStream(messages, createFormData({ contextCount: 2 }))
    const dialog = stream.buildDialogArrayFromSnapshot(messages, '问题3', '00:05')
    expect(dialog).toEqual([
      { role: 'user', content: '问题2', url: '', time: '00:03' },
      { role: 'assistant', content: '回答2', url: '', time: '00:04' },
      { role: 'user', content: '问题3', time: '00:05' },
    ])
  })

  it('contextCount 为 0 时只发送当前消息', () => {
    const messages: ChatMessage[] = [{ type: 'ai', content: '欢迎', time: '00:00' }]
    const stream = createStream(messages, createFormData({ contextCount: 0 }))
    expect(stream.buildDialogArrayFromSnapshot(messages, '你好', '00:01')).toEqual([
      { role: 'user', content: '你好', time: '00:01' },
    ])
  })

  it('未启用增强角色时带上本地 systemPrompt，启用后交给后端', () => {
    const messages: ChatMessage[] = [{ type: 'ai', content: '欢迎', time: '00:00' }]
    const plain = createStream(messages, createFormData({ systemPrompt: '你是助手' }))
    expect(plain.buildDialogArrayFromSnapshot(messages, 'hi', '00:01')[0]).toEqual({
      role: 'system',
      content: '你是助手',
    })

    const enhanced = createStream(
      messages,
      createFormData({ systemPrompt: '本地提示词', enhancedRoleEnabled: true }),
    )
    expect(enhanced.buildDialogArrayFromSnapshot(messages, 'hi', '00:01')).toEqual([
      { role: 'user', content: 'hi', time: '00:01' },
    ])
  })

  it('透传多模态 parts', () => {
    const messages: ChatMessage[] = [
      {
        type: 'user',
        content: '看图',
        time: '00:01',
        parts: [{ type: 'image', url: 'https://x/a.png' }],
      },
    ]
    const stream = createStream(messages, createFormData({ contextCount: 5 }))
    const dialog = stream.buildDialogArrayFromSnapshot(messages, '继续', '00:02')
    expect(dialog[0].parts).toEqual([{ type: 'image', url: 'https://x/a.png' }])
  })

  it('isStreaming 只对最后一条 AI 消息且加载中返回 true', () => {
    const messages: ChatMessage[] = [
      { type: 'user', content: 'hi', time: '00:00' },
      { type: 'ai', content: '回答', time: '00:01' },
    ]
    const stream = createStream(messages, createFormData())
    expect(stream.isStreaming(1)).toBe(false)
  })

  it('isLatestAiMessage 与 canRetryLastExchange 识别最后一轮问答', () => {
    const messages: ChatMessage[] = [
      { type: 'user', content: 'hi', time: '00:00' },
      { type: 'ai', content: '回答', time: '00:01' },
    ]
    const stream = createStream(messages, createFormData())
    expect(stream.isLatestAiMessage(1)).toBe(true)
    expect(stream.isLatestAiMessage(0)).toBe(false)
    expect(stream.canRetryLastExchange()).toBe(true)
  })
})
