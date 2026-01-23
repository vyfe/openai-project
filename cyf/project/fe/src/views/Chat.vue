<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left">
        <el-button
          class="sidebar-toggle-btn"
          :icon="sidebarCollapsed ? Expand : Fold"
          circle size="small"
          @click="sidebarCollapsed = !sidebarCollapsed"
        />
        <h2>智能对话</h2>
        <span class="user-info">用户：{{ authStore.user }}</span>
      </div>
      <div class="header-right">
        <el-button
          type="danger"
          size="small"
          :icon="SwitchButton"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </div>

    <!-- 聊天主体区域 -->
    <div class="chat-main">
      <!-- 侧边栏 -->
      <transition name="sidebar-slide">
        <div v-show="!sidebarCollapsed" class="chat-sidebar" :class="{ 'sidebar-mobile': isMobile }">
          <el-button v-if="isMobile" class="sidebar-close-btn" :icon="Close" circle @click="sidebarCollapsed = true"/>
          <div class="model-selector" @click.stop>
            <h3>选择模型</h3>
            <el-select v-model="selectedModel" placeholder="请输入关键字搜索模型" size="small" filterable clearable @click.stop>
              <el-option
                v-for="model in models"
                :key="model.value"
                :label="model.label"
                :value="model.value"
              />
            </el-select>
          </div>

          <div class="dialog-history-section">
            <h3>对话历史</h3>
            <el-button
              type="primary"
              size="small"
              @click="loadDialogHistory"
              :loading="loadingHistory"
              style="margin-bottom: 10px;"
            >
              <el-icon><Refresh /></el-icon>
              刷新历史
            </el-button>
            <div class="dialog-list">
              <div
                v-for="dialog in dialogHistory"
                :key="dialog.id"
                class="dialog-item"
                @click="loadDialogContent(dialog.id)"
              >
                <div class="dialog-title">{{ dialog.dialog_name }}</div>
                <div class="dialog-date">{{ dialog.start_date }}</div>
              </div>
              <div v-if="dialogHistory.length === 0" class="no-dialogs">
                暂无历史对话
              </div>
            </div>
          </div>

          <!-- 上下文设置部分 -->
          <div class="context-settings-section">
            <h3>上下文设置</h3>
            <div class="context-slider-wrapper">
              <div class="context-label">
                <span>携带历史消息</span>
                <el-tag size="small" type="info">{{ contextCount }} 条</el-tag>
              </div>
              <el-slider v-model="contextCount" :min="0" :max="20" :step="1"
                :marks="{ 0: '0', 10: '10', 20: '20' }" show-stops />
              <div class="context-hint">设为0时仅发送当前消息</div>
            </div>
          </div>
        </div>
      </transition>
      <div v-if="isMobile && !sidebarCollapsed" class="sidebar-overlay" @click="sidebarCollapsed = true"/>

      <!-- 聊天内容区域 -->
      <div class="chat-content">
        <div class="chat-toolbar">
          <el-button
            type="warning"
            size="small"
            @click="clearCurrentSession"
          >
            <el-icon><Delete /></el-icon>
            清空当前会话
          </el-button>
        </div>
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.type]"
          >
            <div class="message-avatar">
              <el-icon v-if="message.type === 'user'"><UserFilled /></el-icon>
              <el-icon v-else><Cpu /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-header">
                <span class="message-author">{{ message.type === 'user' ? '用户' : 'AI助手' }}</span>
                <span class="message-time">{{ message.time }}</span>
              </div>
              <div class="message-text" v-html="renderMarkdown(message.content)"></div>
              <!-- 流式内容的加载动画 -->
              <div v-if="message.type === 'ai' && isStreaming(index)" class="streaming-indicator">
                <hr class="divider" />
                <div v-if="message.content === ''" class="typing-initial">
                  <div class="typing-placeholder">
                    答案马上就到
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
              <div v-if="message.file" class="message-file">
                <el-icon><Document /></el-icon>
                <span>{{ message.file.name }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-container">
            <!-- 新增：文件上传弹窗按钮 -->
            <el-popover placement="top-start" :width="280" trigger="click" v-model:visible="showUploadPopover">
              <template #reference>
                <el-button class="upload-trigger-btn" :icon="Plus" circle size="large"/>
              </template>
              <div class="upload-popover-content">
                <div class="upload-popover-header">
                  <span>上传文件</span>
                  <el-button v-if="uploadedFile" type="danger" size="small" text @click="clearFile">清除</el-button>
                </div>
                <el-upload ref="uploadRef" drag :auto-upload="false" :on-change="handleFileChange"
                  accept=".txt,.pdf,.png,.jpg,.jpeg,.gif,.ppt,.pptx">
                  <el-icon><upload-filled /></el-icon>
                  <div class="el-upload__text">拖拽或点击上传</div>
                </el-upload>
              </div>
            </el-popover>

            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="请输入您的问题... (回车换行，Ctrl+回车发送)"
              class="message-input"
              @keydown="handleKeydown"
            />
            <div class="input-actions">
              <el-button
                type="primary"
                :icon="Position"
                :disabled="!inputMessage.trim() || isLoading"
                @click="sendMessage"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  SwitchButton,
  UploadFilled,
  UserFilled,
  Cpu,
  Document,
  Position,
  Refresh,
  Delete,
  Plus,
  Expand,
  Fold,
  Close
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { chatAPI, fileAPI } from '@/services/api'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const router = useRouter()
const authStore = useAuthStore()
const messagesContainer = ref<HTMLElement>()
const uploadRef = ref()
const isLoading = ref(false)
const loadingHistory = ref(false)
const inputMessage = ref('')
const uploadedFile = ref<File | null>(null)
const showUploadPopover = ref(false)

const selectedModel = ref(localStorage.getItem('selectedModel') || '')

// 添加上下文数量状态变量
const contextCount = ref(parseInt(localStorage.getItem('contextCount') || '10'))

// 添加侧边栏折叠状态
const sidebarCollapsed = ref(JSON.parse(localStorage.getItem('sidebarCollapsed') || 'false'))
const isMobile = ref(false)

const models = ref<Array<{ label: string, value: string }>>([])

// 对话历史数据
const dialogHistory = ref<any[]>([])

// 监听contextCount变化并持久化
watch(contextCount, (newVal) => {
  localStorage.setItem('contextCount', newVal.toString())
})

// 监听sidebarCollapsed变化并持久化
watch(sidebarCollapsed, (newVal) => {
  localStorage.setItem('sidebarCollapsed', JSON.stringify(newVal))
})

// 监听selectedModel变化并持久化
watch(selectedModel, (newVal) => {
  localStorage.setItem('selectedModel', newVal)
})

const messages = reactive<Array<{
  type: 'user' | 'ai'
  content: string
  time: string
  file?: File
}>>([
  {
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  }
])

const renderMarkdown = (content: string) => marked.parse(content || '')

function getCurrentTime() {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleFileChange = async (file: any) => {
  try {
    // 上传文件到服务器
    const response = await fileAPI.upload(file.raw)
    if (response && response.content) {
      // 文件上传成功，将URL添加到当前消息中
      uploadedFile.value = file.raw
      // 在输入框中插入文件URL
      inputMessage.value += `\n文件已上传: ${response.content}`
      ElMessage.success(`文件 "${file.name}" 已上传`)
    } else {
      throw new Error(response.msg || '文件上传失败')
    }
  } catch (error: any) {
    console.error('文件上传错误:', error)
    let errorMessage = '文件上传失败'
    if (error.response?.data?.msg) {
      errorMessage = error.response.data.msg
    }
    ElMessage.error(errorMessage)
  }
}

const clearFile = () => {
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  if (!selectedModel.value) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  // 检查是否是图像生成模型
  const isImageModel = ['图像生成(dall-e)', '图像生成(gpt-4o)'].includes(selectedModel.value)

  const userMessage = {
    type: 'user' as const,
    content: inputMessage.value,
    time: getCurrentTime(),
    file: uploadedFile.value || undefined
  }

  // 在构建对话数组之前先保存当前的上下文消息
  const contextSnapshot = [...messages]; // 创建当前消息快照用于构建上下文

  // 添加用户消息到数组
  messages.push(userMessage)
  inputMessage.value = ''
  const currentFile = uploadedFile.value
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }

  isLoading.value = true

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  try {
    // 根据模型类型调用相应的API
    if (isImageModel) {
      // 图像生成模型仍使用普通API
      const aiResponse = await chatAPI.sendImageGeneration(selectedModel.value, userMessage.content)

      // 处理响应
      let responseContent = ''
      if (typeof aiResponse === 'object' && aiResponse.desc) {
        responseContent = aiResponse.desc
        // 如果是图片生成，添加图片URL
        if (aiResponse.url) {
          responseContent += `\n图片链接: ${window.location.origin}${aiResponse.url}`
        }
      } else {
        responseContent = JSON.stringify(aiResponse)
      }

      messages.push({
        type: 'ai',
        content: responseContent,
        time: getCurrentTime()
      })
    } else {
      // 文本聊天使用流式API
      const aiMessageIndex = messages.length
      messages.push({
        type: 'ai',
        content: '',  // 初始内容为空
        time: getCurrentTime()
      })

      // 使用之前保存的上下文快照构建对话数组，避免因异步操作造成的混乱
      const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content)

      await chatAPI.sendChatStream(
        selectedModel.value,
        userMessage.content,
        (content, done) => {
          messages[aiMessageIndex].content += content
          if (done) {
            isLoading.value = false
          }
          nextTick(() => scrollToBottom())
        },
        contextCount.value > 0 ? 'multi' : 'single',
        dialogArray
      )
    }
  } catch (error: any) {
    console.error('API Error:', error)
    let errorMessage = '获取AI回复失败，请重试'
    if (error.response) {
      errorMessage = `错误: ${error.response.data?.msg || error.response.statusText}`
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行'
    }
    ElMessage.error(errorMessage)
    messages.push({
      type: 'ai',
      content: errorMessage,
      time: getCurrentTime()
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()

    // 刷新对话历史记录
    await loadDialogHistory()
  }
}

// 加载对话历史
const loadDialogHistory = async () => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  loadingHistory.value = true
  try {
    const response = await chatAPI.getDialogHistory(selectedModel.value)
    if (response && response.content) {
      dialogHistory.value = response.content
      ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
    } else {
      dialogHistory.value = []
      ElMessage.info('暂无历史对话')
    }
  } catch (error: any) {
    console.error('加载对话历史错误:', error)
    ElMessage.error('加载对话历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 清空当前会话
const clearCurrentSession = () => {
  messages.splice(0, messages.length)
  messages.push({
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  })
  ElMessage.success('当前会话已清空')
}

// 加载特定对话内容
const loadDialogContent = async (dialogId: number) => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  try {
    const response = await chatAPI.getDialogContent(dialogId)
    if (response && response.content) {
      // 清空当前消息并加载对话内容
      messages.splice(0, messages.length)

      // 根据对话类型确定如何解析内容
      const context = response.content.context
      if (Array.isArray(context)) {
        context.forEach((item: any) => {
          if (item.role === 'user') {
            messages.push({
              type: 'user',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          } else {
            messages.push({
              type: 'ai',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          }
        })
      }

      ElMessage.success('对话加载成功')
    }
  } catch (error: any) {
    console.error('加载对话内容错误:', error)
    ElMessage.error('加载对话内容失败')
  }
}

// 构建对话数组函数
const buildDialogArray = (currentMessage: string): Array<{role: string, content: string}> => {
  if (contextCount.value === 0) {
    return [{ role: 'user', content: currentMessage }]
  }

  const dialogArray: Array<{role: string, content: string}> = []
  // 获取有效消息（user 和 ai 类型），但排除初始欢迎消息和当前消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const validMessages = messages.filter(msg => (msg.type === 'user' || msg.type === 'ai') && msg.content !== welcomeMessage)

  // 获取要包含的上下文消息（排除当前用户消息）
  const contextMessages = validMessages.slice(0, -1) // 排除最后一条（当前用户消息）
  const messagesToInclude = contextMessages.slice(-contextCount.value) // 只取最新的几条

  for (const msg of messagesToInclude) {
    dialogArray.push({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    })
  }
  dialogArray.push({ role: 'user', content: currentMessage })
  return dialogArray
}

// 从消息快照构建对话数组函数
const buildDialogArrayFromSnapshot = (snapshot: any[], currentMessage: string): Array<{role: string, content: string}> => {
  if (contextCount.value === 0) {
    return [{ role: 'user', content: currentMessage }]
  }

  const dialogArray: Array<{role: string, content: string}> = []
  // 获取快照中的有效消息（user 和 ai 类型），但排除初始欢迎消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const validMessages = snapshot.filter((msg: any) => (msg.type === 'user' || msg.type === 'ai') && msg.content !== welcomeMessage)

  // 获取要包含的上下文消息
  const messagesToInclude = validMessages.slice(-contextCount.value) // 只取最新的几条

  for (const msg of messagesToInclude) {
    dialogArray.push({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    })
  }
  dialogArray.push({ role: 'user', content: currentMessage })
  return dialogArray
}

// 检测移动设备
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) sidebarCollapsed.value = true
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 处理键盘事件：Ctrl+Enter 发送，Enter 换行
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    sendMessage()
  }
  // 普通回车不阻止默认行为，允许换行
}

// 检查当前消息是否正在流式接收中
const isStreaming = (index: number) => {
  // 如果是AI消息并且是当前正在加载的那条消息
  const message = messages[index];
  if (message.type === 'ai') {
    // 检查是否是最新的AI消息且当前处于加载状态
    const lastAiMessageIndex = messages.reduce((lastIndex, msg, idx) => {
      if (msg.type === 'ai') {
        return idx; // 返回最后一个AI消息的索引
      }
      return lastIndex;
    }, -1);
    return index === lastAiMessageIndex && isLoading.value;
  }
  return false;
}

// TODO(human): 考虑是否需要在某些情况下延迟刷新对话历史，以避免过于频繁的API请求
// 可以在这里添加防抖机制或根据响应时间决定是否立即刷新

const handleLogout = () => {
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 组件挂载时加载模型列表
onMounted(async () => {
  try {
    const response = await chatAPI.getModels()
    if (response && response.success && response.models) {
      models.value = response.models.map((model: any) => ({
        label: model.label,
        value: model.id
      }))
      // 不再设置默认选中模型
    } else {
      console.error('获取模型列表失败:', response.msg)
      // 设置默认模型列表作为备选
      models.value = [
        { label: 'GPT-4o mini', value: 'gpt-4o-mini' },
        { label: 'GPT-4o', value: 'gpt-4o' },
        { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo' }
      ]
    }
  } catch (error) {
    console.error('加载模型列表时出错:', error)
    // 设置默认模型列表作为备选
    models.value = [
      { label: 'GPT-4o mini', value: 'gpt-4o-mini' },
      { label: 'GPT-4o', value: 'gpt-4o' },
      { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo' }
    ]
  }

  // 自动加载历史会话
  await loadDialogHistory()

  // 添加移动端检测和事件监听
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.chat-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #f9f7f0 0%, #e8f5e8 100%);
}

.chat-header {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(144, 238, 144, 0.3);
  box-shadow: 0 2px 10px rgba(144, 238, 144, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  color: #5a8a5a;
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.user-info {
  color: #7a9c7a;
  font-size: 14px;
}

.chat-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-sidebar {
  width: 300px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  padding: 20px;
  border-right: 1px solid rgba(144, 238, 144, 0.3);
  overflow-y: auto;
}

.model-selector {
  margin-bottom: 30px;
}

.model-selector h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

.dialog-history-section {
  margin-bottom: 30px;
}

.dialog-history-section h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

.dialog-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #dcdcdc;
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.7);
}

.dialog-item {
  padding: 8px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  background: rgba(232, 245, 232, 0.5);
  transition: background-color 0.2s;
}

.dialog-item:hover {
  background: rgba(144, 238, 144, 0.3);
}

.dialog-item:last-child {
  margin-bottom: 0;
}

.dialog-title {
  font-weight: 500;
  color: #5a8a5a;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dialog-date {
  font-size: 12px;
  color: #9caf9c;
  margin-top: 4px;
}

.no-dialogs {
  padding: 10px;
  color: #9caf9c;
  font-style: italic;
  text-align: center;
}

.file-upload-section h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

.upload-demo {
  border: 2px dashed #c0e0c0;
  border-radius: 8px;
  background: rgba(232, 245, 232, 0.3);
}

.upload-demo:hover {
  border-color: #90ee90;
  background: rgba(232, 245, 232, 0.5);
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.7);
}

.chat-toolbar {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid rgba(144, 238, 144, 0.3);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #9acd32 0%, #7dd87d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #87ceeb 0%, #5f9ea0 100%);
}

.message-content {
  max-width: 70%;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.message-author {
  font-weight: 500;
  color: #5a8a5a;
  font-size: 14px;
}

.message-time {
  color: #9caf9c;
  font-size: 12px;
}

.message-text {
  background: rgba(255, 255, 255, 0.9);
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(144, 238, 144, 0.3);
  color: #333;
  line-height: 1.5;
  white-space: pre-wrap;
}

/* Markdown 内容的特殊样式 */
.message-text :deep(p) {
  margin: 0 0 1em 0;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4),
.message-text :deep(h5),
.message-text :deep(h6) {
  margin: 0.5em 0;
}

.message-text :deep(pre) {
  background: #2d2d2d !important;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  font-family: 'Courier New', monospace;
  line-height: 1.4;
}

.message-text :deep(code) {
  font-family: 'Courier New', monospace;
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

.message-text :deep(pre code) {
  background: none !important;
  padding: 0 !important;
  font-size: 0.9em;
}

.message-text :deep(blockquote) {
  border-left: 3px solid #90ee90;
  padding-left: 12px;
  margin: 10px 0;
  color: #666;
}

.message-text :deep(ul),
.message-text :deep(ol) {
  padding-left: 20px;
  margin: 10px 0;
}

.message-text :deep(li) {
  margin: 5px 0;
}

.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
}

.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid #ccc;
  padding: 8px;
  text-align: left;
}

.message.user .message-text {
  background: rgba(144, 238, 144, 0.2);
  border-color: rgba(144, 238, 144, 0.5);
}

.message-file {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(232, 245, 232, 0.5);
  border-radius: 8px;
  font-size: 14px;
  color: #5a8a5a;
}

.typing {
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing-dot {
  width: 8px;
  height: 8px;
  background: #7a9c7a;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(1) { animation-delay: -0.32s; }
.typing-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  padding: 20px;
  background: rgba(255, 255, 255, 0.9);
  border-top: 1px solid rgba(144, 238, 144, 0.3);
}

.input-container {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.message-input {
  flex: 1;
}

.message-input textarea {
  background: rgba(232, 245, 232, 0.3);
  border: 1px solid #c0e0c0;
  border-radius: 12px;
  resize: none;
}

.message-input textarea:focus {
  border-color: #90ee90;
  box-shadow: 0 0 0 2px rgba(144, 238, 144, 0.2);
}

.input-actions {
  display: flex;
  gap: 8px;
  flex-direction: column;
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: rgba(232, 245, 232, 0.3);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: rgba(144, 238, 144, 0.5);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: rgba(144, 238, 144, 0.7);
}

/* 对话历史滚动条样式 */
.dialog-list::-webkit-scrollbar {
  width: 6px;
}

.dialog-list::-webkit-scrollbar-track {
  background: rgba(232, 245, 232, 0.3);
  border-radius: 3px;
}

.dialog-list::-webkit-scrollbar-thumb {
  background: rgba(144, 238, 144, 0.5);
  border-radius: 3px;
}

.dialog-list::-webkit-scrollbar-thumb:hover {
  background: rgba(144, 238, 144, 0.7);
}

.divider {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, rgba(144, 238, 144, 0.3), transparent);
  margin: 10px 0;
}

.streaming-indicator {
  margin-top: 10px;
}

.typing-initial {
  margin-top: 10px;
}

.typing-placeholder {
  margin-bottom: 8px;
  color: #7a9c7a;
  font-style: italic;
  font-size: 14px;
}

.typing-continue {
  margin-top: 10px;
}

/* 侧边栏动画 */
.sidebar-slide-enter-active, .sidebar-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.sidebar-slide-enter-from, .sidebar-slide-leave-to {
  transform: translateX(-100%); opacity: 0;
}

/* 移动端侧边栏 */
.sidebar-mobile {
  position: fixed; left: 0; top: 0; height: 100vh; z-index: 1000;
  box-shadow: 4px 0 20px rgba(0,0,0,0.15);
}
.sidebar-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 999;
}

/* 响应式断点 */
@media (max-width: 768px) {
  .user-info { display: none; }
  .chat-sidebar { width: 280px; }
  .message-content { max-width: 85%; }
  .input-area { padding: 12px; }
  .header-left { gap: 8px; }
  .sidebar-toggle-btn { margin-right: 8px; }
}

@media (max-width: 480px) {
  .chat-sidebar { width: 100%; }
  .message-avatar { width: 32px; height: 32px; }
  .message-content { max-width: 80%; }
  .input-container { flex-direction: column; align-items: stretch; }
  .input-actions { flex-direction: row; align-items: center; margin-top: 12px; }
  .upload-trigger-btn { align-self: flex-start; margin-bottom: 12px; }
}

/* 上下文设置部分样式 */
.context-settings-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid rgba(144, 238, 144, 0.3);
}

.context-settings-section h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 16px;
}

.context-slider-wrapper {
  padding: 12px 0;
}

.context-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.context-hint {
  font-size: 12px;
  color: #9caf9c;
  margin-top: 8px;
}

.sidebar-close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 1001;
}
</style>