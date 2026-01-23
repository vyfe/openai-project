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
            <el-cascader
              v-model="cascaderValue"
              :options="cascaderOptions"
              :props="{ checkStrictly: false }"
              placeholder="请选择模型分类"
              size="small"
              filterable
              clearable
              @change="handleCascaderChange"
            />
          </div>

          <div class="dialog-history-section">
            <div class="history-section-header">
              <h3>对话历史</h3>
              <div class="history-actions">
                <el-button
                  v-if="!isEditMode"
                  type="primary"
                  size="small"
                  text
                  @click="enterEditMode"
                >
                  编辑
                </el-button>
                <div v-else class="edit-mode-actions">
                  <el-button
                    type="danger"
                    size="small"
                    :disabled="selectedDialogs.length === 0"
                    @click="confirmBatchDelete"
                  >
                    删除 ({{ selectedDialogs.length }})
                  </el-button>
                  <el-button
                    size="small"
                    @click="exitEditMode"
                  >
                    取消
                  </el-button>
                </div>
              </div>
            </div>
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
                :class="{ 'selected': isEditMode && selectedDialogs.includes(dialog.id) }"
                @click="isEditMode ? toggleSelectDialog(dialog.id) : loadDialogContent(dialog.id)"
              >
                <el-checkbox
                  v-if="isEditMode"
                  v-model="selectedDialogs"
                  :label="dialog.id"
                  @click.stop
                  class="dialog-checkbox"
                />
                <div class="dialog-content" @click.stop="!isEditMode && loadDialogContent(dialog.id)">
                  <div class="dialog-title">{{ dialog.dialog_name }}</div>
                  <div class="dialog-date">{{ dialog.start_date }}</div>
                </div>
                <el-popconfirm
                  v-if="!isEditMode"
                  title="确定要删除这个对话吗？"
                  confirm-button-text="确定"
                  cancel-button-text="取消"
                  @confirm="confirmSingleDelete(dialog.id)"
                  @cancel.stop
                >
                  <template #reference>
                    <el-button
                      v-if="!isEditMode"
                      class="delete-btn"
                      :icon="Delete"
                      circle
                      size="small"
                      text
                      @click.stop
                    />
                  </template>
                </el-popconfirm>
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
              <el-slider v-model="contextCount" :min="0" :max="50" :step="1"
                :marks="{ 0: '0', 25: '25', 50: '50' }"/>
              <div class="context-hint">设为0时仅发送当前消息</div>
            </div>

            <!-- 最大回复字数 -->
            <div class="context-slider-wrapper">
              <div class="context-label">
                <span>最大回复字数（仅供参考）</span>
                <el-tag size="small" type="info">{{ maxResponseChars }} 字</el-tag>
              </div>
              <el-slider v-model="maxResponseChars" :min="500" :max="32000" :step="500"
                :marks="{ 500: '500', 8000: '8千', 30000: '3万' }" />
              <div class="context-hint">限制AI回复的最大长度</div>
            </div>
          </div>

          <!-- 角色设定部分 -->
          <div class="system-prompt-section">
            <h3>角色设定</h3>
            <el-input
              v-model="systemPrompt"
              type="textarea"
              :rows="3"
              placeholder="输入系统提示词，例如：你是一个专业的程序员助手..."
              resize="vertical"
            />
            <div class="system-prompt-hint">设定 AI 的行为和角色</div>
          </div>

          <!-- 发送键偏好设置 -->
          <div class="send-preference-section">
            <h3>发送设置</h3>
            <div class="send-preference-wrapper">
              <el-switch
                v-model="sendPreference"
                :active-value="'enter'"
                :inactive-value="'ctrl_enter'"
                active-text="Enter发送"
                inactive-text="Ctrl+Enter发送"
              />
              <div class="send-preference-hint">
                当前: {{ sendPreference === 'enter' ? '直接按Enter发送' : '按Ctrl+Enter发送' }}
              </div>
            </div>
          </div>
        </div>
      </transition>
      <div v-if="isMobile && !sidebarCollapsed" class="sidebar-overlay" @click="sidebarCollapsed = true"/>

      <!-- 聊天内容区域 -->
      <div class="chat-content">
        <div class="chat-toolbar">
          <!-- 新增：对话标题编辑区域 -->
          <div class="dialog-title-editor">
            <el-input
              v-model="dialogTitle"
              placeholder="请输入对话标题..."
              size="small"
              @blur="handleTitleBlur"
            />
          </div>

          <!-- 新增：字体大小控制 -->
          <div class="font-size-controls">
            <span class="font-size-label">文字大小:</span>
            <el-tooltip content="文字大小" placement="bottom">
              <el-radio-group v-model="fontSize" size="small" @change="handleFontSizeChange">
                <el-radio-button label="small">小</el-radio-button>
                <el-radio-button label="medium">中</el-radio-button>
                <el-radio-button label="large">大</el-radio-button>
              </el-radio-group>
            </el-tooltip>
          </div>

          <div class="action-buttons">
            <el-button
              type="warning"
              size="small"
              @click="clearCurrentSession"
            >
              <el-icon><Delete /></el-icon>
              清空当前会话
            </el-button>

            <!-- 新增：导出对话截屏按钮 -->
            <el-button
              type="primary"
              size="small"
              @click="exportConversationScreenshot"
            >
              <el-icon><Download /></el-icon>
              导出对话截图
            </el-button>
          </div>
        </div>
        <div class="messages-container" :class="'font-' + fontSize" ref="messagesContainer">
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
                <div class="message-actions">
                  <el-button
                    :icon="CopyDocument"
                    circle
                    size="small"
                    text
                    @click="copyMessageContent(message.content)"
                  />
                  <el-popconfirm
                    title="确定要删除这条消息吗？"
                    confirm-button-text="确定"
                    cancel-button-text="取消"
                    @confirm="deleteMessage(index)"
                  >
                    <template #reference>
                      <el-button
                        :icon="Delete"
                        circle
                        size="small"
                        text
                      />
                    </template>
                  </el-popconfirm>
                </div>
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
              <!-- 错误消息重试按钮 -->
              <div v-if="message.type === 'ai' && message.isError" class="error-actions">
                <el-button
                  type="warning"
                  size="small"
                  @click="retryMessage(index)"
                >
                  <el-icon><RefreshLeft /></el-icon>
                  重试
                </el-button>
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
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              :placeholder="`请输入您的问题... (${sendPreference === 'enter' ? '回车发送，Shift+回车换行' : '回车换行，Ctrl+回车发送'})`"
              class="message-input"
              @keydown="handleKeydown"
            />
            <div class="input-actions">
              <!-- 文件上传按钮移到输入框上方，右侧 -->
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
import { ElMessage, ElMessageBox, ElCascader } from 'element-plus'
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
  Close,
  CopyDocument,
  RefreshLeft
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

// 添加对话标题状态
const dialogTitle = ref('')

// 添加字体大小控制
const fontSize = ref(localStorage.getItem('fontSize') || 'medium')

// 添加状态跟踪用户是否手动滚动离开了底部
const isScrolledToBottom = ref(true)

const selectedModel = ref(localStorage.getItem('selectedModel') || '')

// 添加上下文数量状态变量
const contextCount = ref(parseInt(localStorage.getItem('contextCount') || '10'))

// 最大回复字数（实际 token = 值 * 2）
const maxResponseChars = ref(parseInt(localStorage.getItem('maxResponseChars') || '8000'))

// 添加侧边栏折叠状态
const sidebarCollapsed = ref(JSON.parse(localStorage.getItem('sidebarCollapsed') || 'false'))
const isMobile = ref(false)

// TODO(human): 添加发送键偏好设置，默认为 'ctrl_enter'，表示使用Ctrl+Enter发送；若为 'enter' 则直接按Enter发送
const sendPreference = ref(localStorage.getItem('sendPreference') || 'ctrl_enter')

// 用于检测软键盘是否激活的状态
const isKeyboardVisible = ref(false)

// 角色设定（System Prompt）
const systemPrompt = ref(localStorage.getItem('systemPrompt') || '')

const models = ref<Array<{ label: string, value: string }>>([])

// 添加分组模型数据
const groupedModels = ref<Record<string, Array<{ label: string, value: string }>>>({});

// 对话历史数据
const dialogHistory = ref<any[]>([])

// TODO(human): 添加删除功能所需的状态变量
// 编辑模式状态
const isEditMode = ref(false)
// 已选择的对话ID列表
const selectedDialogs = ref<number[]>([])

// 监听contextCount变化并持久化
watch(contextCount, (newVal) => {
  localStorage.setItem('contextCount', newVal.toString())
})

// 监听maxResponseChars变化并持久化
watch(maxResponseChars, (newVal) => {
  localStorage.setItem('maxResponseChars', newVal.toString())
})

// 监听sidebarCollapsed变化并持久化
watch(sidebarCollapsed, (newVal) => {
  localStorage.setItem('sidebarCollapsed', JSON.stringify(newVal))
})

// 监听selectedModel变化并持久化
watch(selectedModel, (newVal) => {
  localStorage.setItem('selectedModel', newVal)
})

// 监听 systemPrompt 变化并持久化
watch(systemPrompt, (newVal) => {
  localStorage.setItem('systemPrompt', newVal)
})

// 监听 dialogTitle 变化并持久化
watch(dialogTitle, (newVal) => {
  localStorage.setItem('dialogTitle', newVal)
})

// 监听 fontSize 变化并持久化
watch(fontSize, (newVal) => {
  localStorage.setItem('fontSize', newVal)
})

// 监听 sendPreference 变化并持久化
watch(sendPreference, (newVal) => {
  localStorage.setItem('sendPreference', newVal)
})

// 添加级联选择器状态变量
const cascaderValue = ref<string[]>([])
const cascaderOptions = ref<any[]>([])

// 将原始模型列表转换为级联选项
const convertModelsToCascaderOptions = (modelList: Array<{ label: string, value: string }>) => {
  // 使用真实获取的分组数据
  if (Object.keys(groupedModels.value).length > 0) {
    // 如果已有分组数据，直接使用
    return Object.entries(groupedModels.value)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => ({
        value: groupName,
        label: groupName.charAt(0).toUpperCase() + groupName.slice(1), // 首字母大写
        children: (models as any[]).map(model => ({
          value: model.id,
          label: model.label || model.id
        }))
      }));
  } else {
    // 回退到按关键词匹配的方式
    const prefixes = ['gpt', 'gemini', 'qwen', 'nano-banana', 'deepseek'];

    // 按前缀分组模型
    const grouped: Record<string, { label: string, value: string }[]> = {};

    // 初始化分组
    prefixes.forEach(prefix => {
      grouped[prefix] = [];
    });

    // 分类模型
    modelList.forEach(model => {
      const lowerValue = model.value.toLowerCase();
      let matched = false;

      // 按优先级匹配前缀
      for (const prefix of prefixes) {
        if (lowerValue.includes(prefix)) {
          grouped[prefix].push(model);
          matched = true;
          break;
        }
      }

      // 如果没有匹配到任何前缀，放入"其他"分组
      if (!matched) {
        if (!grouped['other']) {
          grouped['other'] = [];
        }
        grouped['other'].push(model);
      }
    });

    // 生成级联选项
    return Object.entries(grouped)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => {
        // 显示友好名称
        let displayName = groupName;
        if (groupName === 'other') displayName = '其他';

        return {
          value: groupName,
          label: displayName.charAt(0).toUpperCase() + displayName.slice(1), // 首字母大写
          children: models.map(model => ({
            value: model.value,
            label: model.label || model.value
          }))
        }
      });
  }
}

// 监听模型列表变化，自动生成级联选项
watch(models, (newModels) => {
  if (newModels && newModels.length > 0) {
    cascaderOptions.value = convertModelsToCascaderOptions(newModels)
    // 新增：同步 cascaderValue
    if (selectedModel.value) {
      for (const group of cascaderOptions.value) {
        const modelOption = group.children.find((child: any) => child.value === selectedModel.value)
        if (modelOption) {
          cascaderValue.value = [group.value, modelOption.value]
          break
        }
      }
    }
  }
}, { deep: true })

// 处理级联选择器变化
const handleCascaderChange = (value: string[]) => {
  if (value && value.length === 2) {
    // value[0] 是分组名, value[1] 是模型值
    selectedModel.value = value[1]
  } else {
    selectedModel.value = ''
  }
}

// 监听selectedModel变化，同步更新级联选择器
watch(selectedModel, (newValue) => {
  if (newValue) {
    // 找到对应的分组和模型
    for (const group of cascaderOptions.value) {
      const modelOption = group.children.find((child: any) => child.value === newValue)
      if (modelOption) {
        cascaderValue.value = [group.value, modelOption.value]
        return
      }
    }
  } else {
    cascaderValue.value = []
  }
})

const messages = reactive<Array<{
  type: 'user' | 'ai'
  content: string
  time: string
  file?: File
  isError?: boolean  // 添加错误状态
}>>([
  {
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  }
])

const renderMarkdown = (content: string) => {
  const parsedContent = marked.parse(content || '');
  // 确保返回的是字符串
  return typeof parsedContent === 'string' ? parsedContent.trim() : parsedContent;
}

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
  const isImageModel = selectedModel.value && (selectedModel.value.toLowerCase().includes('dall') || selectedModel.value.toLowerCase().includes('image'));

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

  // 如果当前没有设置标题，则将用户输入作为对话标题（只在第一次发送时）
  if (!dialogTitle.value.trim()) {
    // 截取前50个字符作为标题
    dialogTitle.value = inputMessage.value.length > 50
      ? inputMessage.value.substring(0, 50) + '...'
      : inputMessage.value
  }

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
      const aiResponse: any = await chatAPI.sendImageGeneration(selectedModel.value, userMessage.content, contextCount.value > 0 ? 'multi' : 'single', buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content), dialogTitle.value)

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
          // 只在用户位于底部时才滚动
          nextTick(() => {
            if (isScrolledToBottom.value) {
              scrollToBottom()
            }
          })
        },
        contextCount.value > 0 ? 'multi' : 'single',
        dialogArray,
        dialogTitle.value,  // 添加dialogTitle参数
        maxResponseChars.value * 2 // 添加最大回复tokens参数（字数×2）
      )
    }
  } catch (error: any) {
    console.error('API Error:', error)
    let errorMessage = '获取AI回复失败，请重试'
    if (error.response) {
      errorMessage = `错误: ${error.response.data?.msg || error.response.statusText}`
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行'
    } else if (error.message) {
      // 更新判断条件，匹配后端返回的实际错误消息内容
      if (error.message.includes('API错误') || error.message.includes('API请求失败') ||
          error.message.includes('网段') || error.message.includes('白名单') ||
          error.message.includes('IP') || error.message.includes('ip')) {
        // 特别处理API错误信息，这通常来自SSE流中的错误消息
        errorMessage = error.message
      } else {
        // 其他类型的错误消息也直接使用
        errorMessage = error.message
      }
    }

    // 将最后的AI消息标记为错误状态
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].type === 'ai' && messages[i].content === '') {
        messages[i].content = errorMessage;
        messages[i].isError = true;  // 添加错误状态
        break;
      }
    }

    // 添加错误AI消息，带有重试功能
    messages.push({
      type: 'ai',
      content: errorMessage,
      time: getCurrentTime(),
      isError: true  // 添加错误状态
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
    const response: any = await chatAPI.getDialogHistory(selectedModel.value)
    if (response && response.content) {
      dialogHistory.value = response.content
      // ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
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
  // 清空对话标题
  dialogTitle.value = ''
  ElMessage.success('当前会话已清空')
}

// 加载特定对话内容
const loadDialogContent = async (dialogId: number) => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  try {
    const response: any = await chatAPI.getDialogContent(dialogId)
    if (response && response.content) {
      // 清空当前消息并加载对话内容
      messages.splice(0, messages.length)

      // 根据对话类型确定如何解析内容
      const context = response.content.context
      if (Array.isArray(context)) {
        context.forEach((item: any) => {
          if (item.role === 'system') {
            // 跳过 system 消息，恢复到角色设定
            systemPrompt.value = item.content || ''
            return
          }
          if (item.role === 'user') {
            messages.push({
              type: 'user',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          } else if (item.role === 'assistant') {
            messages.push({
              type: 'ai',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          }
        })
      }

      // 从对话历史中获取该对话的标题
      const dialogItem = dialogHistory.value.find(d => d.id === dialogId)
      if (dialogItem) {
        dialogTitle.value = dialogItem.dialog_name
      }

      ElMessage.success('对话加载成功')
    }
  } catch (error: any) {
    console.error('加载对话内容错误:', error)
    ElMessage.error('加载对话内容失败')
  }
}

// 当标题输入框失去焦点时的处理
const handleTitleBlur = () => {
  // 在这里可以进行额外的验证或处理
  if (dialogTitle.value.trim()) {
    localStorage.setItem('dialogTitle', dialogTitle.value.trim())
  }
}

// 处理字体大小变化
const handleFontSizeChange = (size: string) => {
  // 可以在这里执行一些额外的逻辑，如果需要
  fontSize.value = size
}

// 导出对话截屏（长截图）
const exportConversationScreenshot = async () => {
  try {
    let html2canvas: any;
    try {
      // 尝试动态导入 html2canvas
      const html2canvasModule = await import('html2canvas');
      html2canvas = html2canvasModule.default || html2canvasModule;
    } catch (e) {
      // 如果没有安装，提示用户安装
      ElMessage.warning('截图功能需要安装 html2canvas 库：npm install html2canvas');
      return;
    }

    const messagesContainer = document.querySelector('.messages-container') as HTMLElement;
    if (!messagesContainer) {
      ElMessage.error('无法找到对话容器');
      return;
    }

    // 创建一个临时的容器来存放完整的消息列表
    const tempContainer = document.createElement('div');
    tempContainer.className = 'messages-container-temp';
    tempContainer.style.position = 'absolute';
    tempContainer.style.left = '-9999px'; // 隐藏元素
    tempContainer.style.width = messagesContainer.clientWidth + 'px';
    tempContainer.style.backgroundColor = '#f9f7f0';
    tempContainer.style.padding = '20px';
    tempContainer.style.boxSizing = 'border-box';

    // 复制消息内容到临时容器
    tempContainer.innerHTML = messagesContainer.innerHTML;

    // 将临时容器添加到文档中
    document.body.appendChild(tempContainer);

    // 生成截图
    const canvas = await html2canvas(tempContainer, {
      scale: 2, // 提高清晰度
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#f9f7f0',
      width: tempContainer.scrollWidth,
      height: tempContainer.scrollHeight,
      scrollX: 0,
      scrollY: 0
    });

    // 移除临时容器
    document.body.removeChild(tempContainer);

    // 创建下载链接
    const link = document.createElement('a');
    link.download = `conversation_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();

    ElMessage.success('对话截图已导出');
  } catch (error) {
    console.error('导出截图失败:', error);
    ElMessage.error('导出截图失败，请稍后重试');
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
  const dialogArray: Array<{role: string, content: string}> = []

  // 如果有角色设定，添加到最前面
  if (systemPrompt.value.trim()) {
    dialogArray.push({ role: 'system', content: systemPrompt.value.trim() })
  }

  // 如果上下文数量为 0，只发送当前消息（但仍需包含 system 消息）
  if (contextCount.value === 0) {
    dialogArray.push({ role: 'user', content: currentMessage })
    return dialogArray
  }

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
  const wasMobile = isMobile.value;
  isMobile.value = window.innerWidth < 768

  // 只在首次检测到移动设备或从桌面切换到移动设备时折叠侧边栏
  // 避免在移动端键盘弹出/隐藏时重复折叠侧边栏
  if (isMobile.value && !wasMobile) {
    sidebarCollapsed.value = true
  }
}

// 处理软键盘显示/隐藏
const handleResize = () => {
  // 检测是否为移动设备上的键盘变化
  const currentIsMobile = window.innerWidth < 768
  if (currentIsMobile) {
    // 使用屏幕高度变化来判断键盘是否弹出
    const screenHeight = window.screen.height
    const windowHeight = window.innerHeight

    // 如果窗口高度明显小于屏幕高度，很可能是因为键盘弹出了
    const likelyKeyboardVisible = screenHeight - windowHeight > 150

    if (likelyKeyboardVisible !== isKeyboardVisible.value) {
      isKeyboardVisible.value = likelyKeyboardVisible

      // 如果键盘弹出，延时滚动到底部确保输入框和按钮可见
      if (likelyKeyboardVisible) {
        setTimeout(() => {
          scrollToBottom()
        }, 300) // 给一点时间让键盘完全弹出
      }
    }
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value && isScrolledToBottom.value) {
    // 只有在用户已经滚动到底部时才继续滚动
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听滚动事件，判断用户是否滚动到了底部
const handleScroll = () => {
  if (messagesContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
    // 如果距离底部小于50像素，则认为是在底部
    isScrolledToBottom.value = scrollHeight - scrollTop - clientHeight < 50

    // 如果软键盘弹出，自动保持滚动到底部
    if (isKeyboardVisible.value) {
      scrollToBottom()
    }
  }
}

// 处理键盘事件：根据用户偏好发送消息
const handleKeydown = (event: KeyboardEvent) => {
  if (sendPreference.value === 'ctrl_enter') {
    // 如果用户选择Ctrl+Enter发送
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      sendMessage()
    }
    // 普通回车不阻止默认行为，允许换行
  } else if (sendPreference.value === 'enter') {
    // 如果用户选择Enter发送
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      sendMessage()
    }
    // Shift+Enter 或其他组合键仍然允许换行
  }
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

// 复制消息内容到剪贴板
const copyMessageContent = async (content: string) => {
  try {
    await navigator.clipboard.writeText(content);
    ElMessage.success('内容已复制到剪贴板');
  } catch (err) {
    console.error('复制失败:', err);
    // 如果 navigator.clipboard 不可用，使用传统的 document.execCommand 方法
    try {
      const textArea = document.createElement('textarea');
      textArea.value = content;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      ElMessage.success('内容已复制到剪贴板');
    } catch (fallbackErr) {
      console.error('复制失败:', fallbackErr);
      ElMessage.error('复制失败，请手动选择内容');
    }
  }
}

// 删除指定的消息
const deleteMessage = (index: number) => {
  if (index >= 0 && index < messages.length) {
    // 检查是否是AI欢迎消息，如果是则不允许删除
    const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？';
    if (messages[index].content === welcomeMessage && messages[index].type === 'ai') {
      ElMessage.warning('无法删除欢迎消息');
      return;
    }

    messages.splice(index, 1);
    ElMessage.success('消息已删除');
  }
}

// 重试发送特定AI消息（重新发送该消息所属的上下文）
const retryMessage = async (index: number) => {
  if (index < 0 || index >= messages.length || messages[index].type !== 'ai' || !messages[index].isError) {
    return;
  }

  // 查找这个AI消息之前的用户消息
  let userMessageIndex = -1;
  for (let i = index - 1; i >= 0; i--) {
    if (messages[i].type === 'user') {
      userMessageIndex = i;
      break;
    }
  }

  if (userMessageIndex === -1) {
    ElMessage.error('找不到对应的问题消息，无法重试');
    return;
  }

  // 从AI错误消息中获取内容，准备重新发送
  const userMessage = messages[userMessageIndex];
  const aiMessage = messages[index];

  // 临时移除错误的AI消息，标记为正在重试
  messages.splice(index, 1);

  // 准备上下文信息
  const contextSnapshot = messages.slice(0, userMessageIndex); // 获取AI消息前的上下文

  // 设置为加载状态
  isLoading.value = true;

  try {
    // 根据模型类型调用相应的API
    const isImageModel = selectedModel.value && (selectedModel.value.toLowerCase().includes('dall') || selectedModel.value.toLowerCase().includes('image'));

    if (isImageModel) {
      // 图像生成模型仍使用普通API
      const aiResponse: any = await chatAPI.sendImageGeneration(
        selectedModel.value,
        userMessage.content,
        contextCount.value > 0 ? 'multi' : 'single',
        buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content),
        dialogTitle.value
      );

      // 处理响应
      let responseContent = '';
      if (typeof aiResponse === 'object' && aiResponse.desc) {
        responseContent = aiResponse.desc;
        // 如果是图片生成，添加图片URL
        if (aiResponse.url) {
          responseContent += `\n图片链接: ${window.location.origin}${aiResponse.url}`;
        }
      } else {
        responseContent = JSON.stringify(aiResponse);
      }

      // 添加新的AI消息（替代之前的错误消息）
      messages.splice(index, 0, {
        type: 'ai',
        content: responseContent,
        time: getCurrentTime()
      });
    } else {
      // 文本聊天使用流式API
      // 添加占位AI消息
      messages.splice(index, 0, {
        type: 'ai',
        content: '',  // 初始内容为空
        time: getCurrentTime()
      });

      // 使用之前保存的上下文快照构建对话数组
      const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content);

      await chatAPI.sendChatStream(
        selectedModel.value,
        userMessage.content,
        (content, done) => {
          messages[index].content += content;
          if (done) {
            isLoading.value = false;
          }
          // 只在用户位于底部时才滚动
          nextTick(() => {
            if (isScrolledToBottom.value) {
              scrollToBottom();
            }
          });
        },
        contextCount.value > 0 ? 'multi' : 'single',
        dialogArray,
        dialogTitle.value,  // 添加dialogTitle参数
        maxResponseChars.value * 2 // 添加最大回复tokens参数（字数×2）
      );
    }

    ElMessage.success('消息重试成功');
  } catch (error: any) {
    console.error('重试API Error:', error);

    // 保留错误消息在AI消息中，而不是显示全局通知
    let errorMessage = '重试失败，请稍后再次重试';
    if (error.response) {
      errorMessage = `重试失败: ${error.response.data?.msg || error.response.statusText}`;
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行';
    } else if (error.message) {
      if (error.message.includes('API错误') || error.message.includes('API请求失败') ||
          error.message.includes('网段') || error.message.includes('白名单') ||
          error.message.includes('IP') || error.message.includes('ip')) {
        errorMessage = `重试失败: ${error.message}`;
      } else {
        errorMessage = `重试失败: ${error.message}`;
      }
    }

    // 将错误信息更新到AI消息中
    messages.splice(index, 0, {
      type: 'ai',
      content: errorMessage,
      time: getCurrentTime(),
      isError: true  // 保持错误状态，用户仍可以再次重试
    });

    ElMessage.warning('重试失败，错误消息已更新到对话中');
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

// 进入编辑模式
const enterEditMode = () => {
  isEditMode.value = true
  selectedDialogs.value = []
}

// 退出编辑模式
const exitEditMode = () => {
  isEditMode.value = false
  selectedDialogs.value = []
}

// 切换选择对话
const toggleSelectDialog = (dialogId: number) => {
  const index = selectedDialogs.value.indexOf(dialogId)
  if (index > -1) {
    selectedDialogs.value.splice(index, 1)
  } else {
    selectedDialogs.value.push(dialogId)
  }
}

// 确认单个删除
const confirmSingleDelete = async (dialogId: number) => {
  try {
    const response: any = await chatAPI.deleteDialogs([dialogId])
    if (response && response.success) {
      ElMessage.success(`对话删除成功，共删除 ${response.deleted_count} 条`)
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前会话被删除，清空聊天内容
      const dialogItem = dialogHistory.value.find(d => d.id === dialogId)
      if (dialogItem && dialogItem.dialog_name === dialogTitle.value) {
        clearCurrentSession()
      }
    } else {
      ElMessage.error('删除对话失败')
    }
  } catch (error: any) {
    console.error('删除对话错误:', error)
    ElMessage.error('删除对话失败')
  }
}

// 确认批量删除
const confirmBatchDelete = async () => {
  if (selectedDialogs.value.length === 0) {
    ElMessage.warning('请至少选择一个对话')
    return
  }

  try {
    const response: any = await chatAPI.deleteDialogs(selectedDialogs.value)
    if (response && response.success) {
      ElMessage.success(`批量删除成功，共删除 ${response.deleted_count} 条`)
      // 退出编辑模式
      exitEditMode()
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前会话被删除，清空聊天内容
      const currentDialog = dialogHistory.value.find(d => d.dialog_name === dialogTitle.value)
      if (currentDialog && selectedDialogs.value.includes(currentDialog.id)) {
        clearCurrentSession()
      }
    } else {
      ElMessage.error('批量删除失败')
    }
  } catch (error: any) {
    console.error('批量删除错误:', error)
    ElMessage.error('批量删除失败')
  }
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
    // 优先尝试获取分组模型列表
    const response: any = await chatAPI.getGroupedModels()
    if (response && response.success && response.grouped_models) {
      // 保存分组模型数据
      groupedModels.value = response.grouped_models;

      // 将分组模型展平为普通列表
      models.value = [];
      for (const [prefix, modelList] of Object.entries(response.grouped_models)) {
        (modelList as Array<any>).forEach((model: any) => {
          models.value.push({
            label: `${prefix}: ${model.label || model.id}`,
            value: model.id
          });
        });
      }
    } else {
      // 如果获取分组模型失败，回退到普通模型列表
      const normalResponse: any = await chatAPI.getModels();
      if (normalResponse && normalResponse.success && normalResponse.models) {
        models.value = normalResponse.models.map((model: any) => ({
          label: model.label,
          value: model.id
        }));
      } else {
        console.error('获取模型列表失败:', response?.msg || normalResponse?.msg)
        // 设置默认模型列表作为备选
        models.value = [
          { label: 'GPT-4o mini', value: 'gpt-4o-mini' },
          { label: 'GPT-4o', value: 'gpt-4o' },
          { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo' }
        ]
      }
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

  // 从localStorage恢复对话标题
  const savedDialogTitle = localStorage.getItem('dialogTitle')
  if (savedDialogTitle) {
    dialogTitle.value = savedDialogTitle
  }

  // 从localStorage恢复发送键偏好
  const savedSendPreference = localStorage.getItem('sendPreference')
  if (savedSendPreference) {
    sendPreference.value = savedSendPreference
  }

  // 自动加载历史会话
  await loadDialogHistory()

  // 添加移动端检测和事件监听
  checkMobile()
  window.addEventListener('resize', checkMobile)

  // 添加resize事件监听器以处理软键盘弹出/收起
  window.addEventListener('resize', handleResize)

  // 添加滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll)
    // 初始化滚动位置状态
    handleScroll()
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('resize', handleResize) // 移除软键盘检测监听器
  // 移除滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', handleScroll)
  }
})
</script>

<style scoped>
.chat-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #f9f7f0 0%, #e8f5e8 100%);
  /* 修复移动端视口高度问题 */
  height: -webkit-fill-available;
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
  flex-shrink: 0; /* 防止头部被压缩 */
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
  /* 新增以下属性 */
  -webkit-overflow-scrolling: touch;  /* 启用惯性滚动 */
  touch-action: pan-y;                 /* 只允许垂直滚动 */
  overscroll-behavior: contain;        /* 防止滚动链 */
}

.model-selector {
  margin-bottom: 30px;
}

.model-selector h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

/* 级联选择器样式 */
:deep(.el-cascader) {
  width: 100%;
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
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  overscroll-behavior: contain;
  /* 其他现有样式保持不变 */
}

.dialog-item {
  padding: 8px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  background: rgba(232, 245, 232, 0.5);
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative; /* 添加定位上下文 */
}

.dialog-item.selected {
  background: rgba(144, 238, 144, 0.5);
  outline: 2px solid rgba(144, 238, 144, 0.8);
}

.dialog-item:hover {
  background: rgba(144, 238, 144, 0.3);
}

.dialog-content {
  flex: 1;
  cursor: pointer;
}

.dialog-checkbox {
  margin-right: 8px;
}

.delete-btn {
  visibility: hidden;
  opacity: 0;
  transition: visibility 0.2s, opacity 0.2s;
}

.dialog-item:hover .delete-btn {
  visibility: visible;
  opacity: 1;
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

.dialog-content {
  flex: 1;
  cursor: pointer;
  min-width: 0; /* 允许flex项目收缩 */
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-date {
  font-size: 12px;
  color: #9caf9c;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.history-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.edit-mode-actions {
  display: flex;
  gap: 8px;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-title-editor {
  flex: 1;
  max-width: 460px;
  margin-right: 10px;
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

.message-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.message-actions .el-button {
  color: #9caf9c;
  opacity: 0;
  transition: opacity 0.3s;
}

.message:hover .message-actions .el-button {
  opacity: 1;
}

.message-text {
  background: rgba(255, 255, 255, 0.9);
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(144, 238, 144, 0.3);
  color: #333;
  line-height: 1.5;
  white-space: pre-line; /* 更改：保留换行符，但合并空格和制表符 */
  overflow-wrap: break-word; /* 确保长单词能换行 */
  margin-bottom: 0; /* 确保底部没有额外边距 */
}

/* 处理末尾的换行符问题 */
.message-text br:last-child {
  display: none;
}

/* 确保Markdown渲染后的元素也没有多余的底部边距 */
.message-text > :last-child {
  margin-bottom: 0;
}

/* 对特定元素的处理 */
.message-text p:last-child {
  margin-bottom: 0;
}

.message-text div:last-child {
  margin-bottom: 0;
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

.error-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-start;
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
  flex-shrink: 0; /* 防止输入区域被压缩 */
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
  flex-direction: row;
}

/* 确保移动端输入区域的按钮都可见 */
.input-actions {
  display: flex;
  gap: 8px;
  flex-direction: row;
  align-self: flex-end; /* 确保按钮与输入框底部对齐 */
}

/* 针对软键盘弹出时的调整 */
.chat-container.keyboard-visible .input-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  border-top: 1px solid rgba(144, 238, 144, 0.3);
}

/* 修复Element Plus按钮默认边距在移动端的影响 */
.input-actions .el-button + .el-button {
  margin-left: 0;
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
  position: fixed; left: 0; top: 0; height: 100%;              /* 替换 100vh */
  max-height: 100dvh;        /* 使用动态视口高度作为上限 */
  z-index: 1000;
  box-shadow: 4px 0 20px rgba(0,0,0,0.15);
  overflow-y: auto;          /* 确保移动端也能滚动 */
  -webkit-overflow-scrolling: touch;
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

/* 角色设定部分样式 */
.system-prompt-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(144, 238, 144, 0.3);
}

.system-prompt-section h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

.system-prompt-section :deep(.el-textarea__inner) {
  background: rgba(232, 245, 232, 0.3);
  border: 1px solid #c0e0c0;
  border-radius: 8px;
}

.system-prompt-section :deep(.el-textarea__inner:focus) {
  border-color: #90ee90;
  box-shadow: 0 0 0 2px rgba(144, 238, 144, 0.2);
}

/* 发送键偏好设置部分样式 */
.send-preference-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(144, 238, 144, 0.3);
}

.send-preference-section h3 {
  color: #5a8a5a;
  font-size: 16px;
  margin-bottom: 12px;
}

.send-preference-wrapper {
  padding: 12px 0;
}

.send-preference-hint {
  font-size: 12px;
  color: #9caf9c;
  margin-top: 8px;
}

/* 字体大小控制样式 */
.font-size-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 15px;
}

.font-size-label {
  white-space: nowrap;
}

.messages-container {
  /* 小字体 */
  &:not(.font-medium):not(.font-large) {
    font-size: 12px;
  }

  /* 中等字体 */
  &.font-medium {
    font-size: 14px;
  }

  /* 大字体 */
  &.font-large {
    font-size: 16px;
  }
}

.message-text {
  /* 小字体 */
  .messages-container:not(.font-medium):not(.font-large) & {
    font-size: 12px;
  }

  /* 中等字体 */
  .messages-container.font-medium & {
    font-size: 14px;
  }

  /* 大字体 */
  .messages-container.font-large & {
    font-size: 16px;
  }
}

.messages-container-temp {
  position: absolute;
  left: -9999px;
  background-color: #f9f7f0 !important;
  padding: 20px !important;
  box-sizing: border-box !important;
  width: 100% !important;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 响应式断点 */
@media (max-width: 768px) {
  .user-info { display: none; }
  .chat-sidebar { width: 280px; }
  .message-content { max-width: 85%; }
  .input-area { padding: 12px; }
  .header-left { gap: 8px; }
  .sidebar-toggle-btn { margin-right: 8px; }

  .chat-toolbar {
    flex-direction: column;
    align-items: stretch; /* 改为拉伸以填满宽度 */
    gap: 12px;
  }

  .dialog-title-editor,
  .font-size-controls,
  .action-buttons {
    width: 100%; /* 让各个组件填满宽度 */
  }

  .dialog-title-editor {
    margin-right: 0; /* 移除移动端的右边距 */
  }

  .font-size-controls {
    justify-content: center; /* 在移动端居中对齐字体大小控制 */
  }

  .action-buttons {
    flex-direction: column;
  }

  /* 修复Element Plus按钮默认边距在移动端的影响 */
  .action-buttons .el-button + .el-button {
    margin-left: 0;
  }
}

@media (max-width: 480px) {
  .chat-sidebar { width: 100%; }
  .message-avatar { width: 32px; height: 32px; }
  .message-content { max-width: 80%; }
  .input-container { flex-direction: column; align-items: stretch; }
  .input-actions {
    flex-direction: row;
    align-items: center;
    margin-top: 12px;
    justify-content: flex-end; /* 确保按钮靠右对齐 */
    width: 100%; /* 确保动作区占满整行 */
    flex-wrap: wrap; /* 允许换行以适应小屏幕 */
  }
  .upload-trigger-btn { align-self: flex-end; margin-bottom: 0; }

  .action-buttons {
    width: 100%;
  }
  .dialog-title-editor {
    width: 100%;
    margin-right: 0;
  }

  /* 修复Element Plus按钮默认边距在移动端的影响 */
  .action-buttons .el-button + .el-button {
    margin-left: 0;
  }

  /* 确保输入框和按钮都能适应小屏幕 */
  .input-area {
    padding: 12px;
  }

  /* 确保按钮不会因为太宽而挤压输入框 */
  .input-actions .el-button {
    flex-shrink: 0;
  }

  /* 确保发送按钮在移动端可见 */
  .input-actions .el-button--primary {
    min-width: 60px; /* 确保发送按钮有最小宽度 */
  }
}

/* Android设备特定优化 */
@media screen and (-webkit-device-pixel-ratio: 1.5), screen and (-webkit-device-pixel-ratio: 2), screen and (-webkit-device-pixel-ratio: 3) {
  .chat-sidebar,
  .sidebar-mobile,
  .dialog-list {
    /* 在Android设备上增强滚动性能 */
    will-change: scroll-position;
    transform: translateZ(0);
    -webkit-transform: translateZ(0);
  }
}

/* 移动端视口高度调整 */
@supports (-webkit-touch-callout: none) {
  /* iOS Safari */
  .chat-container {
    height: -webkit-fill-available;
  }
}

@supports (height: -webkit-fill-available) {
  /* Chrome, Firefox on mobile */
  .chat-container {
    height: -webkit-fill-available;
  }
}

@supports (height: 100dvh) {
  /* Modern browsers supporting dynamic viewport height */
  .chat-container {
    height: 100dvh;
  }
}

/* 修复软键盘弹出时的布局问题 */
@media screen and (max-height: 600px) and (orientation: portrait) {
  .chat-content {
    height: 100%;
  }

  .messages-container {
    height: calc(100% - 100px); /* 为输入区域留出空间 */
  }

  .input-area {
    position: sticky;
    bottom: 0;
    z-index: 10;
  }
}

.system-prompt-hint {
  font-size: 12px;
  color: #9caf9c;
  margin-top: 8px;
}
</style>