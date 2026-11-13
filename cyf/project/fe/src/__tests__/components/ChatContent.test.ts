import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import messages from '@/locales'
import type { FormData } from '@/utils/main'

const chatApiMock = vi.hoisted(() => ({
  sendChatStream: vi.fn(),
  sendChat: vi.fn(),
  sendImageGeneration: vi.fn(),
  cancelChatStream: vi.fn(async () => ({ success: true })),
  getDialogContent: vi.fn(),
  updateDialogTitle: vi.fn(),
  handoff: vi.fn(),
}))

vi.mock('@/services/api', () => ({ chatAPI: chatApiMock }))

import ChatContent from '@/components/chat/ChatContent.vue'

const i18n = createI18n({ legacy: false, locale: 'zh', messages: messages as never })
const welcomeText = (messages as { zh: { chat: { aiWelcomeMessage: string } } }).zh.chat.aiWelcomeMessage

function createFormData(overrides: Partial<FormData> = {}): FormData {
  return {
    isDarkTheme: false,
    currentDialogId: null,
    selectedModel: 'test-model',
    selectedModelType: 1,
    selectedModelAllowNet: true,
    enabledTools: [],
    contextCount: 10,
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

const stubs = {
  ChatToolbar: { name: 'ChatToolbar', template: '<div class="chat-toolbar-stub" />' },
  InputArea: {
    name: 'InputArea',
    props: ['modelValue'],
    emits: ['update:modelValue', 'send-message', 'file-change', 'clear-file', 'stop-stream'],
    template: '<div class="input-area-stub" />',
  },
  WeChatIcon: { name: 'WeChatIcon', template: '<span class="wechat-stub" />' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-checkbox': {
    props: ['modelValue'],
    emits: ['change'],
    template: '<input type="checkbox" />',
  },
  'el-button': { template: '<button><slot /></button>' },
  'el-tooltip': { template: '<span><slot /></span>' },
  'el-popconfirm': { template: '<span><slot /><slot name="reference" /></span>' },
  'el-alert': { template: '<div class="alert-stub"><slot /></div>' },
  'el-dialog': { template: '<div><slot /></div>' },
}

function mountContent(formData: FormData) {
  return mount(ChatContent, {
    props: { modelValue: formData, sessionKey: 'tab-1' },
    global: { plugins: [i18n, createPinia()], stubs },
  })
}

describe('ChatContent 重构后行为', () => {
  beforeEach(() => {
    chatApiMock.sendChatStream.mockReset()
    chatApiMock.sendChat.mockReset()
    chatApiMock.sendImageGeneration.mockReset()
  })

  it('初始渲染欢迎消息', () => {
    const wrapper = mountContent(createFormData())
    expect(wrapper.text()).toContain(welcomeText)
  })

  it('发送消息后走流式接口并把回复写入列表', async () => {
    chatApiMock.sendChatStream.mockImplementation(async (_model, _message, onChunk) => {
      onChunk('模型', false)
      onChunk('回答', true, 'stop', { usage: { total_tokens: 12 } })
    })

    const formData = createFormData()
    const wrapper = mountContent(formData)
    const inputArea = wrapper.findComponent({ name: 'InputArea' })
    inputArea.vm.$emit('send-message', '你好')

    await flushPromises()
    await flushPromises()

    expect(chatApiMock.sendChatStream).toHaveBeenCalledTimes(1)
    expect(chatApiMock.sendChatStream.mock.calls[0][0]).toBe('test-model')
    expect(chatApiMock.sendChatStream.mock.calls[0][1]).toBe('你好')
    expect(wrapper.text()).toContain('你好')
    expect(wrapper.text()).toContain('模型回答')
    expect(formData.contextTotalTokens).toBe(12)
  })

  it('关闭流式开关时走非流式接口', async () => {
    chatApiMock.sendChat.mockResolvedValue({ content: '非流式回答', usage: { total_tokens: 3 } })

    const formData = createFormData({ streamEnabled: false })
    const wrapper = mountContent(formData)
    wrapper.findComponent({ name: 'InputArea' }).vm.$emit('send-message', '问题')

    await flushPromises()
    await flushPromises()

    expect(chatApiMock.sendChat).toHaveBeenCalledTimes(1)
    expect(chatApiMock.sendChatStream).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('非流式回答')
  })

  it('没有选择模型时提示且不发请求', async () => {
    const wrapper = mountContent(createFormData({ selectedModel: '' }))
    wrapper.findComponent({ name: 'InputArea' }).vm.$emit('send-message', '你好')
    await flushPromises()
    expect(chatApiMock.sendChatStream).not.toHaveBeenCalled()
    expect(chatApiMock.sendChat).not.toHaveBeenCalled()
  })
})
