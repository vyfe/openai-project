<template>
  <!-- 聊天内容区域 -->
  <div class="chat-content">
    <ChatToolbar
      :form-data="formData"
      :font-size="fontSize"
      :formatted-context-tokens="formattedContextTokens"
      :is-context-window-high="isContextWindowHigh"
      :handoff-loading="handoffLoading"
      :can-trigger-handoff="canTriggerHandoff"
      :context-window-hint="contextWindowHint"
      :has-messages="messages.length > 0"
      :selected-count="selectedCount"
      :show-back-to-top="showBackToTop"
      :show-mobile-input="showMobileInput"
      @update-font-size="handleFontSizeChange"
      @update-dialog-title="updateDialogTitle"
      @handle-handoff="handleHandoff"
      @clear-session="clearCurrentSession"
      @export-selected="exportSelectedMessages"
      @delete-selected="deleteSelectedMessages"
      @toggle-mobile-input="toggleMobileInput"
      @scroll-to-top="scrollToTop"
    />
    <!-- 消息列表容器 - 关键滚动区域 -->
    <div class="messages-container" :class="'font-size-' + fontSize" ref="messagesContainer">
      <!-- 对话区域内嵌水印（用于长截图） -->
      <div class="conversation-title-wrap">
        <p v-if="formData.dialogTitle" class="conversation-title">{{ formData.dialogTitle }}</p>
      </div>
      <div v-for="(message, index) in messages" :key="index" :class="['message', message.type]">
        <div class="message-avatar">
          <el-icon v-if="message.type === 'user'">
            <UserFilled />
          </el-icon>
          <el-icon v-else>
            <Cpu />
          </el-icon>
        </div>
        <div class="message-content" :class="`message-content-${message.type}`">
          <div class="message-header">
            <span class="message-author">{{ message.type === 'user' ? authStore.user : t('chat.AI') + formData.modelValue}}</span>
            <span class="message-time">{{ message.time }}</span>
            <div class="message-actions">
              <el-checkbox
                :model-value="message.selected || false"
                @change="(val: boolean) => toggleMessageSelection(index, val)"
                class="message-checkbox"
              />
              <el-tooltip v-if="message.type === 'ai' && isLatestAiMessage(index)" :content="t('chat.retry')" placement="top">
                <el-button
                  :icon="RefreshLeft"
                  circle
                  size="small"
                  text
                  :disabled="!canRetryLastExchange()"
                  @click="retryLastExchange"
                />
              </el-tooltip>
              <el-button :icon="CopyDocument" circle size="small" text @click="copyMessageContent(getCopyText(message))" />
              <el-popconfirm :title="t('chat.deleteMessageConfirmation')" :confirm-button-text="t('chat.confirm')" :cancel-button-text="t('chat.cancel')"
                @confirm="deleteMessage(index)">
                <template #reference>
                  <el-button :icon="Delete" circle size="small" text />
                </template>
              </el-popconfirm>
            </div>
          </div>
          <div class="message-text" v-html="renderRichText(getTextContent(message.content))"></div>
          <div v-if="getToolResultParts(message.parts).length" class="tool-results">
            <div v-for="(part, partIndex) in getToolResultParts(message.parts)" :key="partIndex" class="tool-result-card">
              <div class="tool-result-header">
                <div class="tool-result-title">
                  <span class="tool-result-dot" aria-hidden="true"></span>
                  {{ t('chat.toolResultTitle') }}
                </div>
                <span v-if="getToolSources(part).length" class="tool-result-count">
                  {{ getToolSources(part).length }} {{ t('chat.toolResultSourceCount') }}
                </span>
              </div>
              <div v-if="getToolSources(part).length" class="tool-result-sources">
                <a
                  v-for="(source, sourceIndex) in getToolSources(part)"
                  :key="source.url"
                  :href="source.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="tool-result-source"
                  :title="source.url"
                >
                  <span class="tool-result-source-index" aria-hidden="true">{{ sourceIndex + 1 }}</span>
                  <span class="tool-result-source-label">{{ source.title || source.url }}</span>
                </a>
              </div>
              <details v-if="part.text" class="tool-result-details">
                <summary class="tool-result-summary">
                  <span class="tool-result-expand-label">{{ t('chat.toolResultExpand') }}</span>
                  <span class="tool-result-collapse-label">{{ t('chat.toolResultCollapse') }}</span>
                  <span class="tool-result-chevron" aria-hidden="true">⌄</span>
                </summary>
                <div class="tool-result-text">{{ part.text }}</div>
              </details>
            </div>
          </div>
          <!-- TODO(human): 验证中文引号粗体修复 - 测试包含中文引号的**"文本"**是否能正确显示为粗体 -->
          <!-- 已完成: 代码块和表格的移动端响应式布局优化 -->
          <!-- 图片预览 - 支持从消息url字段和内容中提取，避免重复显示 -->
          <div v-if="message.url || extractFileUrls(message.content).length > 0" class="message-attachments">
            <!-- 如果消息对象有url字段，优先显示且不再从内容中提取 -->
            <template v-if="message.url">
              <img v-if="isImageUrl(message.url)" :src="message.url" class="attachment-preview" @click="openImagePreview(message.url)" />
              <a v-else :href="message.url" target="_blank" class="attachment-link">
                <el-icon>
                  <Document />
                </el-icon>
                {{ message.url.split('/').pop() }}
              </a>
            </template>
            <!-- 只有当消息对象没有url字段时，才从内容中提取 -->
            <template v-else v-for="url in extractFileUrls(message.content)" :key="url">
              <img v-if="isImageUrl(url)" :src="url" class="attachment-preview" @click="openImagePreview(url)" />
              <a v-else :href="url" target="_blank" class="attachment-link">
                <el-icon>
                  <Document />
                </el-icon>
                {{ url.split('/').pop() }}
              </a>
            </template>
          </div>
          <!-- 流式内容的加载动画 -->
          <div v-if="message.type === 'ai' && isStreaming(index)" class="streaming-indicator">
            <hr class="divider" />
            <div v-if="message.content === ''" class="typing-initial">
              <div class="typing-placeholder">
                {{ t('chat.modelLoading') }}
              </div>
              <div class="typing">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
            <div v-else class="typing-continue">
              <div class="typing">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
          </div>
          <!-- 错误消息重试按钮 -->
          <div v-if="message.type === 'ai' && message.isError" class="error-actions">
            <el-button type="warning" size="small" @click="retryMessage(index)">
              <el-icon>
                <RefreshLeft />
              </el-icon>
              {{ t('chat.retry') }}
            </el-button>
          </div>
          <!-- 当回复为空时，提示用户重新发送 -->
          <div v-if="message.type === 'ai' && message.content === '' && !message.isError && !isStreaming(index)"
            class="empty-response-actions">
            <el-alert :closable="false" :title="t('chat.aiTemporarilyNoReply')" type="info" show-icon />
            <el-button type="success" size="small" @click="retryMessage(index)">
              <el-icon>
                <RefreshLeft />
              </el-icon>
              {{ t('chat.resend') }}
            </el-button>
          </div>
          <!-- 截断消息继续生成按钮 -->
          <div v-if="message.type === 'ai' && message.isTruncated && !message.isError && !isStreaming(index)"
            class="truncated-actions">
            <div class="truncated-indicator">
              <span class="ellipsis">...</span>
              <span class="truncated-hint">{{ t('chat.contentTruncated') }}</span>
            </div>
            <el-button type="success" size="small" @click="continueGeneration(index)" :disabled="formData.isLoading">
              <el-icon>
                <CaretRight />
              </el-icon>
              {{ t('chat.continueGenerate') }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="copyright-watermark-inline">
        <span>© 2026 vyfe | chat-h.cc</span>
      </div>

      <!-- 开源项目链接 -->
      <div class="github-link-inline">
        <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer">
          <el-icon>
            <Link />
          </el-icon> {{ t('login.githubLink') }}
        </a>
        <span class="wechat-info">
          <WeChatIcon size="sm" :label="t('login.contactLabel')" />
          pata_data_studio
        </span>
      </div>

      <!-- 回到顶部按钮 -->
      <div v-if="showBackToTop && !formData.isMobile" class="back-to-top-btn-normal" @click="scrollToTop">
        <el-icon>
          <Top />
        </el-icon>
      </div>
    </div>

    <!-- 输入区域 -->
    <InputArea
      v-if="!formData.isMobile || showMobileInput"
      v-model="inputMessage"
      :send-preference="formData.sendPreference"
      :is-loading="isLoading"
      :selected-model="formData.selectedModel"
      :selected-model-type="formData.selectedModelType"
      :selected-model-allow-net="formData.selectedModelAllowNet"
      :context-count="formData.contextCount"
      :enhanced-role-enabled="formData.enhancedRoleEnabled"
      :system-prompt="formData.systemPrompt"
      :active-enhanced-group="formData.activeEnhancedGroup"
      :selected-enhanced-role="formData.selectedEnhancedRole"
      :enhanced-role-groups="formData.enhancedRoleGroups"
      :stream-enabled="formData.streamEnabled"
      :max-response-chars="formData.maxResponseChars"
      :dialog-title="formData.dialogTitle"
      :current-dialog-id="formData.currentDialogId"
      :is-scrolled-to-bottom="formData.isScrolledToBottom"
      :is-mobile="formData.isMobile"
      :font-size="fontSize"
      :enabled-tools="formData.enabledTools"
      @send-message="handleSendMessage"
      @update:enabled-tools="formData.enabledTools = $event"
      @file-change="handleFileChange"
      @clear-file="clearFile"
      @stop-stream="handleStopStream"
    />

    <!-- TODO(human): 实现移动端输入框按钮的状态指示器，例如添加一个小标签显示当前状态（如"隐藏输入框"或"显示输入框"） -->
  </div>
  <!-- 图片预览弹窗 -->
  <el-dialog
  v-model="showImagePreview"
  width="80%"
  top="5vh"
  class="image-preview-dialog"
  :modal="true"
  :show-close="true"
  @close="showImagePreview = false"
>
  <img :src="previewImageUrl" style="width: 100%; height: auto;" />
</el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  UserFilled,
  Cpu,
  Document,
  Delete,
  CopyDocument,
  RefreshLeft,
  Top,
  Link,
  CaretRight,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { chatAPI } from '@/services/api'
import { FormData } from '@/utils/main'
import WeChatIcon from '@/components/common/WeChatIcon.vue'
import InputArea from './InputArea.vue'
import ChatToolbar from './ChatToolbar.vue'
import 'highlight.js/styles/github-dark.css'
import 'katex/dist/katex.min.css'
import { renderRichText } from '@/composables/chat/chatMarkdown'
import {
  extractFileUrls,
  getCopyText,
  getCurrentTime,
  getTextContent,
  getToolResultParts,
  getToolSources,
  isImageUrl,
} from '@/composables/chat/messageUtils'
import type { ChatMessage, RoleSetting } from '@/composables/chat/types'
import { useChatExport } from '@/composables/chat/useChatExport'
import { useChatMermaid } from '@/composables/chat/useChatMermaid'
import { useChatMessageActions } from '@/composables/chat/useChatMessageActions'
import { useChatScroll } from '@/composables/chat/useChatScroll'
import { useChatStream } from '@/composables/chat/useChatStream'

const props = defineProps<{
  modelValue: FormData
  sessionKey?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: FormData]
  'refresh-history': []
  'clear-session': []
  'loading-change': [payload: { sessionKey: string, loading: boolean }]
  'session-dialog-created': [payload: { sessionKey: string, dialogId: number }]
  'role-setting-loaded': [payload: { sessionKey: string, roleSetting: RoleSetting }]
  'handoff-created': [payload: { dialogId: number, dialogName: string, modelName: string, usage?: unknown }]
}>()

const { t } = useI18n()
const authStore = useAuthStore()

const formData = (props.modelValue || {}) as FormData
const WELCOME_MESSAGE = t('chat.aiWelcomeMessage')

const buildRoleSetting = (): RoleSetting => ({
  enhanced_role_enabled: !!formData.enhancedRoleEnabled,
  system_prompt_id: formData.enhancedRoleEnabled ? (formData.systemPromptId || null) : null,
  active_enhanced_group: formData.enhancedRoleEnabled ? (formData.activeEnhancedGroup || '') : '',
  selected_enhanced_role: formData.enhancedRoleEnabled ? (formData.selectedEnhancedRole || '') : '',
  system_prompt: formData.enhancedRoleEnabled ? '' : (formData.systemPrompt || ''),
  active_role_id: formData.enhancedRoleEnabled ? '' : (formData.activeRoleId || 'default'),
})

const applyRoleSetting = (roleSetting: RoleSetting | null | undefined) => {
  if (!roleSetting || typeof roleSetting !== 'object') return
  formData.enhancedRoleEnabled = !!roleSetting.enhanced_role_enabled
  formData.systemPromptId = roleSetting.system_prompt_id ? Number(roleSetting.system_prompt_id) : undefined
  formData.activeEnhancedGroup = roleSetting.active_enhanced_group || ''
  formData.selectedEnhancedRole = roleSetting.selected_enhanced_role || ''
  formData.systemPrompt = roleSetting.system_prompt || ''
  formData.activeRoleId = roleSetting.active_role_id || 'default'
}

const getSessionKey = () => props.sessionKey || 'default'

const messages = reactive<ChatMessage[]>([
  {
    type: 'ai',
    content: WELCOME_MESSAGE,
    time: getCurrentTime(),
  },
])

const sessionMessageStore = ref<Record<string, ChatMessage[]>>({})
const sessionLoadingStore = ref<Record<string, boolean>>({})
const sessionAbortControllers = ref<Record<string, AbortController | null>>({})
const sessionRequestIds = ref<Record<string, string | null>>({})
const sessionAiIndexes = ref<Record<string, number | null>>({})
const sessionWaitingTimers = ref<Record<string, number | null>>({})
const sessionWaitingShown = ref<Record<string, boolean>>({})

const isLoading = ref(false)
const inputMessage = ref('')
const uploadRef = ref()
const uploadedFile = ref<File | null>(null)
const handoffLoading = ref(false)
const CONTEXT_HANDOFF_THRESHOLD = 100000

const saveMessagesToSession = (sessionKey: string) => {
  sessionMessageStore.value[sessionKey] = messages.map((msg) => ({ ...msg }))
}

const getSessionMessages = (sessionKey: string): ChatMessage[] => {
  if (sessionKey === getSessionKey()) return messages
  if (!Array.isArray(sessionMessageStore.value[sessionKey])) {
    sessionMessageStore.value[sessionKey] = [{
      type: 'ai',
      content: WELCOME_MESSAGE,
      time: getCurrentTime(),
    }]
  }
  return sessionMessageStore.value[sessionKey]
}

const restoreMessagesFromSession = (sessionKey: string) => {
  const saved = sessionMessageStore.value[sessionKey]
  messages.splice(0, messages.length)
  if (Array.isArray(saved) && saved.length > 0) {
    saved.forEach((msg) => messages.push({ ...msg }))
    return
  }
  messages.push({
    type: 'ai',
    content: WELCOME_MESSAGE,
    time: getCurrentTime(),
  })
}

const mutateSessionMessages = (sessionKey: string, mutator: (target: ChatMessage[]) => void) => {
  const target = getSessionMessages(sessionKey)
  mutator(target)
  if (sessionKey === getSessionKey()) {
    saveMessagesToSession(sessionKey)
  } else {
    sessionMessageStore.value[sessionKey] = target.map((item) => ({ ...item }))
  }
}

const setSessionLoading = (sessionKey: string, loading: boolean) => {
  sessionLoadingStore.value[sessionKey] = loading
  emit('loading-change', { sessionKey, loading })
  if (sessionKey === getSessionKey()) {
    isLoading.value = loading
  }
}

const contextTotalTokens = computed(() => Number(formData.contextTotalTokens || 0))
const formattedContextTokens = computed(() => contextTotalTokens.value > 0 ? contextTotalTokens.value.toLocaleString() : '--')
const isContextWindowHigh = computed(() => !!formData.currentDialogId && contextTotalTokens.value >= CONTEXT_HANDOFF_THRESHOLD)
const canTriggerHandoff = computed(() => isContextWindowHigh.value && !isLoading.value && !handoffLoading.value)
const contextWindowHint = computed(() => {
  if (!formData.currentDialogId) return '当前会话保存后可统计上下文窗口'
  if (!contextTotalTokens.value) return '等待模型返回 token 统计'
  if (isContextWindowHigh.value) return '上下文已超过 100k，可点击压缩并创建交接新会话'
  return '上下文未超过 100k，暂不需要压缩'
})

const setContextUsage = (usage?: { total_tokens?: number }) => {
  formData.contextTotalTokens = Number(usage?.total_tokens || 0)
}

const filterSystemMessages = (list: Array<{ role?: string }>) => list.filter((msg) => msg.role !== 'system')

// 添加加载对话内容的方法
const loadDialogContent = async (dialogId: number, sessionKeyOverride?: string) => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  const targetSessionKey = sessionKeyOverride || getSessionKey()

  try {
    const response: any = await chatAPI.getDialogContent(dialogId)
    // 若请求期间已切换到其他会话，直接丢弃结果，避免覆盖当前 tab
    if (targetSessionKey !== getSessionKey()) {
      return
    }
    if (response?.content) {
      const roleSetting = response.content.role_setting as RoleSetting | undefined
      if (roleSetting) {
        applyRoleSetting(roleSetting)
        emit('role-setting-loaded', { sessionKey: targetSessionKey, roleSetting })
      }
      setContextUsage(response.content.usage)
      const context = response.content.context
      const toMessage = (msg: any): ChatMessage => ({
        type: msg.role === 'user' ? 'user' : 'ai',
        content: msg.content || msg.desc || '',
        url: msg.url,
        parts: msg.parts,
        time: msg.time || getCurrentTime(),
      })

      let loadedMessages: ChatMessage[] = []
      if (Array.isArray(context)) {
        loadedMessages = filterSystemMessages(context).map(toMessage)
      } else if (typeof context === 'string') {
        try {
          const contentObj = JSON.parse(context)
          if (Array.isArray(contentObj)) {
            loadedMessages = filterSystemMessages(contentObj).map(toMessage)
          }
        } catch {
          // 非 JSON 时把整段内容当成单条 AI 消息
          loadedMessages = [{ type: 'ai', content: response.content, time: getCurrentTime() }]
        }
      }
      // 一次性替换，避免逐条 push 触发多次响应式更新与 mermaid 重渲染
      messages.splice(0, messages.length, ...loadedMessages)
      ElMessage.success('对话内容已同步')
    }
  } catch (error: any) {
    console.error('加载对话内容错误:', error)
    ElMessage.error('加载对话内容失败')
  }
}

defineExpose({ loadDialogContent })

// 字体大小
const fontSize = computed({
  get() {
    return formData.fontSize || 'medium'
  },
  set(value: string) {
    formData.fontSize = value
    localStorage.setItem('fontSize', value)
  },
})

const updateGlobalFontSizeClass = (size: string) => {
  document.body.classList.remove('font-size-small', 'font-size-medium', 'font-size-large')
  document.body.classList.add(`font-size-${size}`)
}

const updateFontSizeSelectorTheme = () => {
  const selector = document.querySelector('.font-size-selector')
  if (!selector) return
  if (formData.isDarkTheme) {
    selector.classList.add('dark-theme')
    selector.classList.remove('light-theme')
  } else {
    selector.classList.add('light-theme')
    selector.classList.remove('dark-theme')
  }
}

const setupThemeWatcher = () => {
  watch(() => formData.isDarkTheme, (newVal) => {
    document.body.classList.toggle('dark-theme', newVal)
    document.body.classList.toggle('dark', newVal)
    document.documentElement.classList.toggle('dark', newVal)
    updateFontSizeSelectorTheme()
  }, { immediate: true })
}

const initializeSettings = () => {
  const savedFontSize = localStorage.getItem('fontSize')
  if (savedFontSize && ['small', 'medium', 'large'].includes(savedFontSize)) {
    formData.fontSize = savedFontSize
    updateGlobalFontSizeClass(savedFontSize)
  }

  const savedTheme = localStorage.getItem('isDarkTheme')
  if (savedTheme !== null) {
    formData.isDarkTheme = savedTheme === 'true'
  }
}

const handleFontSizeChange = (size: string) => {
  formData.fontSize = size
  localStorage.setItem('fontSize', size)
  updateGlobalFontSizeClass(size)
  updateFontSizeSelectorTheme()
}

const clearCurrentSession = () => {
  // 统一交由父组件处理新建会话 tab 逻辑，避免子组件直接改 currentDialogId 导致 tab 行为不一致
  emit('clear-session')
}

const updateDialogTitle = async () => {
  if (!formData.currentDialogId) {
    ElMessage.warning('当前没有打开的对话，无法更新标题')
    return
  }
  if (!formData.dialogTitle.trim()) {
    ElMessage.warning('对话标题不能为空')
    return
  }

  try {
    const response: any = await chatAPI.updateDialogTitle(formData.currentDialogId, formData.dialogTitle.trim())
    if (response?.success) {
      ElMessage.success('对话标题更新成功')
      const dialogItem = formData.dialogHistory.find((d: any) => d.id === formData.currentDialogId)
      if (dialogItem) {
        dialogItem.dialog_name = formData.dialogTitle.trim()
      }
    } else {
      ElMessage.error(response?.msg || '更新对话标题失败')
    }
  } catch (error: any) {
    console.error('更新对话标题错误:', error)
    ElMessage.error('更新对话标题失败')
  }
}

const handleHandoff = async () => {
  if (!formData.currentDialogId) {
    ElMessage.warning('当前没有可压缩的对话')
    return
  }
  if (!isContextWindowHigh.value) {
    ElMessage.info('上下文未超过 100k，暂不需要压缩')
    return
  }
  if (isLoading.value) {
    ElMessage.warning('当前会话正在生成回复，稍后再压缩')
    return
  }

  handoffLoading.value = true
  try {
    const response: any = await chatAPI.handoff(Number(formData.currentDialogId), formData.selectedModel)
    if (!response?.success) {
      ElMessage.error(response?.msg || '上下文压缩失败')
      return
    }
    const data = response.data || {}
    const newDialogId = Number(data.dialog_id)
    if (!Number.isFinite(newDialogId) || newDialogId <= 0) {
      ElMessage.error('上下文压缩已返回，但缺少新对话 ID')
      return
    }
    emit('handoff-created', {
      dialogId: newDialogId,
      dialogName: data.dialog_name || `对话 ${newDialogId}`,
      modelName: data.modelname || formData.selectedModel,
      usage: data.usage,
    })
    ElMessage.success('上下文压缩完成，已打开交接新会话')
  } catch (error: any) {
    console.error('handoff 上下文压缩失败:', error)
    ElMessage.error(error?.message || '上下文压缩失败')
  } finally {
    handoffLoading.value = false
  }
}

// 移动端 / 图片预览
const showMobileInput = ref(true)
const isMobile = ref(false)
const previousIsMobile = ref(false)
const messagesContainer = ref<HTMLElement>()
const previewImageUrl = ref('')
const showImagePreview = ref(false)

const toggleMobileInput = () => {
  showMobileInput.value = !showMobileInput.value
}

const checkIsMobile = () => {
  const currentIsMobile = window.innerWidth < 768
  previousIsMobile.value = currentIsMobile
  isMobile.value = currentIsMobile
}

const openImagePreview = (url: string) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

const handleFileChange = (file: any) => {
  try {
    if (file) {
      uploadedFile.value = file
    }
  } catch (error: any) {
    console.error('处理文件变更错误:', error)
    ElMessage.error('处理文件失败')
  }
}

const clearFile = () => {
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

// ===== 拆出的 composables =====
const {
  showBackToTop,
  scrollToTop,
  scrollToBottom,
  scrollToBottomOnNewMessage,
  debouncedHandleScroll,
} = useChatScroll(messagesContainer, formData)

const {
  selectedCount,
  toggleMessageSelection,
  copyMessageContent,
  handleMessageContainerClick,
  deleteMessage,
  deleteSelectedMessages,
} = useChatMessageActions(messages, t)

const { exportSelectedMessages } = useChatExport(messages, messagesContainer, formData)

useChatMermaid(messagesContainer, messages)

const {
  handleSendMessage,
  handleStopStream,
  retryMessage,
  continueGeneration,
  retryLastExchange,
  canRetryLastExchange,
  isStreaming,
  isLatestAiMessage,
} = useChatStream({
  messages,
  formData,
  isLoading,
  inputMessage,
  getSessionKey,
  sessionAbortControllers,
  sessionRequestIds,
  sessionAiIndexes,
  sessionWaitingTimers,
  sessionWaitingShown,
  sessionLoadingStore,
  setSessionLoading,
  mutateSessionMessages,
  buildRoleSetting,
  setContextUsage,
  scrollToBottom,
  scrollToBottomOnNewMessage,
  onDialogCreated: (sessionKey, dialogId) => emit('session-dialog-created', { sessionKey, dialogId }),
  onRefreshHistory: () => emit('refresh-history'),
  t,
  welcomeMessage: WELCOME_MESSAGE,
})

onMounted(() => {
  initializeSettings()
  checkIsMobile()
  window.addEventListener('resize', checkIsMobile)

  document.body.classList.toggle('dark-theme', formData.isDarkTheme)
  document.body.classList.toggle('dark', formData.isDarkTheme)
  document.documentElement.classList.toggle('dark', formData.isDarkTheme)
  setupThemeWatcher()

  const container = messagesContainer.value
  if (container) {
    container.addEventListener('scroll', debouncedHandleScroll)
    container.addEventListener('click', handleMessageContainerClick)
  }

  nextTick(() => {
    scrollToBottom()
    const current = messagesContainer.value
    if (current) {
      const { scrollTop, scrollHeight, clientHeight } = current
      formData.isScrolledToBottom = scrollHeight - scrollTop - clientHeight < 10
    }
  })
  restoreMessagesFromSession(getSessionKey())
})

onUnmounted(() => {
  window.removeEventListener('resize', checkIsMobile)
  const container = messagesContainer.value
  if (container) {
    container.removeEventListener('scroll', debouncedHandleScroll)
    container.removeEventListener('click', handleMessageContainerClick)
  }
})

// 消息数量变化时保存会话并跟随滚动
watch(() => messages.length, () => {
  saveMessagesToSession(getSessionKey())
  nextTick(() => {
    if (formData.isScrolledToBottom) {
      scrollToBottomOnNewMessage()
    }
  })
})

// 对话 ID 变化时加载内容
watch(() => formData.currentDialogId, async (newDialogId) => {
  if (newDialogId !== null && newDialogId !== undefined) {
    const currentSessionKey = getSessionKey()
    await loadDialogContent(newDialogId, currentSessionKey)
    saveMessagesToSession(getSessionKey())
  }
})

// 切换会话 tab 时保存 / 恢复消息
watch(() => props.sessionKey, (newKey, oldKey) => {
  if (oldKey) {
    saveMessagesToSession(oldKey)
  }
  const currentSessionKey = newKey || 'default'
  restoreMessagesFromSession(currentSessionKey)
  if (formData.currentDialogId !== null && formData.currentDialogId !== undefined) {
    loadDialogContent(formData.currentDialogId, currentSessionKey)
  }
  isLoading.value = !!sessionLoadingStore.value[currentSessionKey]
})

// 监听暗色主题变化
watch(() => formData.isDarkTheme, (newVal) => {
  document.body.classList.toggle('dark-theme', newVal)
  document.body.classList.toggle('dark', newVal)
  document.documentElement.classList.toggle('dark', newVal)
}, { immediate: true })
</script>

<style scoped>
@import '@/styles/chat-content.css';
@import '@/styles/global-font-sizes.css';
@import '@/styles/message-container-fix.css';
/* 消息区的响应式 / 暗色覆盖：放在最后，保证与基础样式特异性相同时由它胜出 */
@import '@/styles/chat-message-content.css';

.tool-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.tool-result-card {
  overflow: hidden;
  border: 1px solid var(--line-1);
  border-radius: var(--r-sm);
  background: var(--bg-1);
  color: var(--text-1);
  font-size: 0.9em;
}

.tool-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px 8px;
}

.tool-result-title {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-weight: 600;
}

.tool-result-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: var(--accent-1);
  box-shadow: 0 0 0 3px var(--accent-1-soft);
}

.tool-result-count {
  flex: 0 0 auto;
  color: var(--text-2);
  font-size: 0.88em;
}

.tool-result-sources {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 0 12px 9px;
}

.tool-result-source {
  display: flex;
  align-items: baseline;
  min-width: 0;
  gap: 7px;
  padding: 3px 0;
  color: var(--accent-1);
  line-height: 1.35;
  text-decoration: none;
}

.tool-result-source:hover {
  color: var(--el-color-primary-dark-2);
  text-decoration: underline;
}

.tool-result-source-index {
  flex: 0 0 auto;
  min-width: 1.2em;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.tool-result-source-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-result-details {
  border-top: 1px solid var(--line-1);
  background: var(--bg-0);
}

.tool-result-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 12px;
  color: var(--text-2);
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.tool-result-summary::-webkit-details-marker {
  display: none;
}

.tool-result-summary:hover {
  color: var(--text-1);
  background: var(--bg-2);
}

.tool-result-chevron {
  color: var(--accent-1);
  font-size: 1.15em;
  line-height: 1;
  transform: translateY(-2px);
  transition: transform var(--dur-fast) var(--ease-standard);
}

.tool-result-details[open] .tool-result-chevron {
  transform: rotate(180deg) translateY(2px);
}

.tool-result-collapse-label {
  display: none;
}

.tool-result-details[open] .tool-result-expand-label {
  display: none;
}

.tool-result-details[open] .tool-result-collapse-label {
  display: inline;
}

.tool-result-text {
  max-height: 320px;
  padding: 0 12px 12px;
  overflow: auto;
  color: var(--text-2);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
