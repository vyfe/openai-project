<template>
  <div class="chat-content">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button
          v-if="currentDialogId"
          @click="editDialogTitle"
          class="title-button"
        >
          <span class="dialog-title">{{ dialogTitle || t('chat.newChat') }}</span>
          <el-icon><EditPen /></el-icon>
        </el-button>
        <div v-else class="new-chat-title">
          {{ t('chat.newChat') }}
        </div>

        <!-- 字体设置按钮 -->
        <el-dropdown @command="handleFontChange" trigger="click">
          <el-button class="font-button">
            <el-icon><Reading /></el-icon>
            {{ t('chat.fontSize') }} {{ fontSize }}px
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="14">14px</el-dropdown-item>
              <el-dropdown-item command="16">16px</el-dropdown-item>
              <el-dropdown-item command="18">18px</el-dropdown-item>
              <el-dropdown-item command="20">20px</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div class="toolbar-right">
        <el-button @click="createNewDialog">
          {{ t('chat.newDialog') }}
        </el-button>
        <el-button @click="exportDialog">
          {{ t('chat.export') }}
        </el-button>
      </div>
    </div>

    <!-- 移动端工具栏抽屉 -->
    <el-drawer
      v-model="showMobileToolbar"
      :title="t('chat.toolbar')"
      direction="ltr"
      size="80%"
    >
      <div class="mobile-toolbar-content">
        <el-button @click="createNewDialog" style="width: 100%; margin-bottom: 10px;">
          {{ t('chat.newDialog') }}
        </el-button>
        <el-button @click="exportDialog" style="width: 100%; margin-bottom: 10px;">
          {{ t('chat.export') }}
        </el-button>
        <el-button @click="editDialogTitle" style="width: 100%;">
          {{ t('chat.editTitle') }}
        </el-button>
      </div>
    </el-drawer>

    <!-- 消息列表 -->
    <div ref="messagesContainer" class="messages-container">
      <div
        v-for="(message, index) in messages"
        :key="message.id || index"
        :class="['message', message.role]"
      >
        <div class="avatar">
          <el-avatar
            :icon="message.role === 'user' ? User : message.role === 'assistant' ? Message : Tickets"
            :size="32"
          />
        </div>
        <div class="content">
          <div
            v-if="message.content"
            class="message-text"
            :style="{ fontSize: fontSize + 'px' }"
            v-html="renderMarkdown(message.content)"
          ></div>
          <div v-if="message.imageUrls && message.imageUrls.length > 0" class="image-content">
            <el-image
              v-for="(imgUrl, imgIdx) in message.imageUrls"
              :key="imgIdx"
              :src="imgUrl"
              :preview-src-list="message.imageUrls"
              :initial-index="imgIdx"
              fit="contain"
              class="chat-image"
            />
          </div>
          <div v-if="message.loading" class="loading-indicator">
            <el-icon class="is-loading"><Loading /></el-icon>
            {{ t('chat.loading') }}
          </div>
          <div v-if="message.error" class="error-message">
            {{ t('chat.errorMessage') }}
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="file-upload-area" v-if="uploadedFiles.length > 0">
        <div class="file-list">
          <div
            v-for="(file, index) in uploadedFiles"
            :key="index"
            class="file-item"
          >
            <el-tag type="info" closable @close="removeFile(index)">
              {{ file.name }} ({{ formatFileSize(file.size) }})
            </el-tag>
          </div>
        </div>
      </div>

      <div class="input-controls">
        <el-upload
          class="upload-wrapper"
          drag
          :action="uploadUrl"
          :headers="authHeaders"
          :before-upload="beforeFileUpload"
          :on-success="handleFileUploadSuccess"
          :on-error="handleFileUploadError"
          :show-file-list="false"
          :accept="acceptedFileTypes"
        >
          <el-button type="primary" :icon="Upload">
            {{ t('chat.uploadFile') }}
          </el-button>
        </el-upload>

        <el-input
          v-model="inputMessage"
          :rows="inputRows"
          type="textarea"
          :placeholder="t('chat.inputPlaceholder')"
          :disabled="isLoading"
          @keydown.enter="handleEnterKey"
          class="message-input"
        />

        <el-button
          type="primary"
          :icon="Right"
          @click="sendMessageWrapper"
          :disabled="isLoading || !inputMessage.trim()"
          class="send-button"
        >
          {{ t('chat.send') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  EditPen,
  Reading,
  ArrowDown,
  User,
  Message,
  Tickets,
  Loading,
  Right,
  Upload
} from '@element-plus/icons-vue'
import { useChat } from '../../composables/useChat'
import { ChatContentProps, ChatContentEmits } from './types'

// 接收 props
const props = defineProps<ChatContentProps>()

// 定义 emits
const emit = defineEmits<ChatContentEmits>()

// 国际化
const { t } = useI18n()

// 使用聊天 composable
const {
  messages,
  inputMessage,
  isLoading,
  dialogTitle,
  currentDialogId: currentDialogIdFromComposable,
  addMessage,
  updateMessage,
  setLoading,
  setError,
  setDialogTitle,
  setCurrentDialogId,
  clearMessages,
  clearCurrentSession,
  sendMessage,
  loadDialogContent,
  renderMarkdown
} = useChat()

// 本地状态
const fontSize = ref(16)
const inputRows = ref(3)
const uploadedFiles = ref<File[]>([])
const showMobileToolbar = ref(false)
const messagesContainer = ref<HTMLDivElement | null>(null)

// 计算属性
const uploadUrl = computed(() => `${import.meta.env.VITE_API_BASE_URL}/upload`)
const authHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))
const acceptedFileTypes = computed(() => '.txt,.pdf,.png,.jpg,.jpeg,.gif,.ppt,.pptx')

// 监听当前对话ID变化
watch(
  () => props.currentDialogId,
  (newId) => {
    if (newId !== currentDialogIdFromComposable.value) {
      setCurrentDialogId(newId)
      if (newId) {
        loadDialogContent(newId)
      } else {
        clearMessages()
        setDialogTitle('')
      }
    }
  },
  { immediate: true }
)

// 发送消息包装器
const sendMessageWrapper = async () => {
  if (!inputMessage.value.trim()) return

  try {
    // 准备设置对象
    const settings = {
      contextCount: props.contextCount,
      maxResponseChars: props.maxResponseChars,
      streamEnabled: props.streamEnabled,
      systemPrompt: props.systemPrompt,
      sendPreference: props.sendPreference
    }

    await sendMessage(inputMessage.value, props.selectedModel, settings)

    // 清空输入框
    inputMessage.value = ''

    // 如果是新对话，发出对话创建事件
    if (!currentDialogIdFromComposable.value) {
      // 模拟新对话创建，这里应该是实际的API返回的ID
      emit('dialog-created', Date.now())
    }

    // 滚动到底部
    scrollToBottom()
  } catch (error) {
    console.error('发送消息失败:', error)
    ElMessage.error(t('chat.sendMessageFailed'))
  }
}

// 处理回车键
const handleEnterKey = (event: KeyboardEvent) => {
  const isShiftPressed = event.shiftKey
  const isCtrlPressed = event.ctrlKey || event.metaKey

  if (props.sendPreference === 'enter' && !isShiftPressed && !isCtrlPressed) {
    event.preventDefault()
    sendMessageWrapper()
  } else if (props.sendPreference === 'ctrl_enter' && isCtrlPressed && !isShiftPressed) {
    event.preventDefault()
    sendMessageWrapper()
  }
}

// 文件上传相关方法
const beforeFileUpload = (file: File) => {
  const isValidType = /\.(txt|pdf|png|jpg|jpeg|gif|ppt|pptx)$/i.test(file.name)
  if (!isValidType) {
    ElMessage.error(t('chat.invalidFileType'))
    return false
  }

  const maxSize = 10 * 1024 * 1024 // 10MB
  if (file.size > maxSize) {
    ElMessage.error(t('chat.fileTooLarge'))
    return false
  }

  uploadedFiles.value.push(file)
  return true
}

const handleFileUploadSuccess = (response: any) => {
  ElMessage.success(t('chat.fileUploadSuccess'))
  // 处理上传成功的逻辑
}

const handleFileUploadError = () => {
  ElMessage.error(t('chat.fileUploadFailed'))
  // 移除最后添加的文件
  uploadedFiles.value.pop()
}

const removeFile = (index: number) => {
  uploadedFiles.value.splice(index, 1)
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  else return (bytes / 1048576).toFixed(1) + ' MB'
}

// 工具栏相关方法
const handleFontChange = (fontSizeValue: string) => {
  fontSize.value = parseInt(fontSizeValue)
}

const editDialogTitle = async () => {
  if (!currentDialogIdFromComposable.value) {
    ElMessage.warning(t('chat.noActiveDialog'))
    return
  }

  try {
    const { value } = await ElMessageBox.prompt(
      t('chat.enterDialogTitle'),
      t('chat.editDialogTitle'),
      {
        confirmButtonText: t('chat.confirm'),
        cancelButtonText: t('chat.cancel'),
        inputValue: dialogTitle.value
      }
    )

    setDialogTitle(value)
    // 这里应该是实际的API调用来更新对话标题
  } catch {
    // 用户取消操作
  }
}

const createNewDialog = () => {
  clearCurrentSession()
  emit('update:currentDialogId', null)
}

const exportDialog = () => {
  // 导出对话逻辑
  alert(t('chat.exportFeatureComingSoon'))
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(messages, () => {
  if (!isLoading.value) {
    nextTick(() => {
      scrollToBottom()
    })
  }
}, { deep: true })

// 处理移动端工具栏显示
const toggleMobileToolbar = () => {
  if (props.isMobile) {
    showMobileToolbar.value = true
  }
}

// 组件挂载时初始化
onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-button {
  padding: 6px 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dialog-title {
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.new-chat-title {
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.font-button {
  padding: 6px 12px;
}

.toolbar-right {
  display: flex;
  gap: 12px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  display: flex;
  align-items: flex-start;
}

.content {
  flex: 1;
  max-width: calc(100% - 44px);
}

.message-text {
  padding: 12px 16px;
  background: var(--el-bg-color-page);
  border-radius: 8px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-text :deep(p) {
  margin: 0 0 16px 0;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4),
.message-text :deep(h5),
.message-text :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
}

.message-text :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  margin: 8px 0;
  white-space: pre-wrap;
}

.message-text :deep(code) {
  max-width: 100%;
  overflow-x: auto;
}

.message-text :deep(blockquote) {
  margin: 0;
  padding-left: 16px;
  border-left: 4px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
}

.message-text :deep(ul),
.message-text :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text :deep(li) {
  margin-bottom: 4px;
}

.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  table-layout: fixed;
}

.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 8px;
  text-align: left;
  word-break: break-word;
}

.image-content {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chat-image {
  width: 120px;
  height: 120px;
  border-radius: 4px;
  cursor: pointer;
}

.loading-indicator {
  padding: 8px 12px;
  color: var(--el-text-color-secondary);
  font-style: italic;
}

.error-message {
  padding: 8px 12px;
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-radius: 4px;
}

.input-area {
  padding: 20px;
  border-top: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.file-upload-area {
  margin-bottom: 16px;
}

.file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.input-controls {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.upload-wrapper {
  display: flex;
  align-items: center;
}

.message-input {
  flex: 1;
}

.send-button {
  height: 42px;
}

.mobile-toolbar-content {
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .toolbar {
    padding: 8px 12px;
  }

  .toolbar-left {
    gap: 8px;
  }

  .title-button {
    max-width: 150px;
  }

  .dialog-title {
    max-width: 120px;
  }

  .messages-container {
    padding: 12px;
    gap: 16px;
  }

  .message {
    gap: 8px;
  }

  .content {
    max-width: calc(100% - 36px);
  }

  .input-area {
    padding: 12px;
  }
}
</style>
