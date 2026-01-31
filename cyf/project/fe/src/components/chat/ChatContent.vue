<template>
  <!-- 聊天内容区域 -->
  <div class="chat-content">
    <div class="chat-toolbar">
      <!-- 在桌面端显示完整toolbar，在移动端显示抽屉切换按钮 -->
      <div v-if="!formData.isMobile" class="toolbar-desktop">
        <!-- 新增：对话标题编辑区域 -->
        <div class="dialog-title-editor">
          <el-input v-model="formData.dialogTitle" :placeholder="t('chat.enterDialogTitle')" size="small"/>
          <!-- 更新标题按钮：当有当前对话ID时显示 -->
          <el-button v-if="formData.currentDialogId" type="primary" size="small" @click="updateDialogTitle"
            class="update-title-btn" :disabled="!formData.dialogTitle.trim()">
            {{ t('chat.updateDialogTitle') }}
          </el-button>
        </div>

        <!-- 新增：字体大小控制 -->
        <div class="font-size-controls">
          <span class="font-size-label">{{ t('chat.fontSizeLabel') }}:</span>
          <el-tooltip :content="t('chat.fontSizeLabel')" placement="bottom">
            <el-radio-group v-model="fontSize" size="small" @change="handleFontSizeChange">
              <el-radio-button label="small">{{ t('chat.small') }}</el-radio-button>
              <el-radio-button label="medium">{{ t('chat.medium') }}</el-radio-button>
              <el-radio-button label="large">{{ t('chat.large') }}</el-radio-button>
            </el-radio-group>
          </el-tooltip>
        </div>

        <div class="action-buttons">
          <el-button type="warning" size="small" @click="clearCurrentSession">
            <el-icon>
              <CirclePlus />
            </el-icon>
            {{ t('chat.openAnotherSession') }}
          </el-button>

          <!-- 新增：导出对话截屏按钮 -->
          <el-button type="primary" size="small" @click="exportConversationScreenshot">
            <el-icon>
              <Download />
            </el-icon>
            {{ t('chat.exportScreenshot') }}
          </el-button>
        </div>
      </div>

      <!-- 移动端：显示抽屉切换按钮 -->
      <div v-else class="toolbar-mobile">
        <!-- 回到顶部按钮 -->
        <div v-if="showBackToTop" class="back-to-top-btn" @click="scrollToTop">
          <el-icon>
            <Top />
          </el-icon>
        </div>
        <!-- 移动端：输入框显示/隐藏按钮，放在回到顶部按钮的右侧 -->
        <div class="back-to-top-btn input-btn" @click="toggleMobileInput">
          <el-icon>
            <component :is="showMobileInput ? 'Hide' : 'View'" />
          </el-icon>
        </div>
        <el-button icon="Menu" size="default" circle @click="showToolbarDrawer = true" class="mobile-toolbar-btn" />
      </div>

      <!-- 移动端抽屉菜单 -->
      <el-drawer v-if="formData.isMobile" v-model="showToolbarDrawer" title="工具栏" direction="rtl" size="80%"
        :destroy-on-close="true" :close-on-click-modal="true">
        <div class="mobile-toolbar-content">
          <!-- 对话标题编辑区域 -->
          <div class="dialog-title-editor">
            <span class="mobile-form-label">{{ t('chat.dialogTitle') }}</span>
            <el-input v-model="formData.dialogTitle" :placeholder="t('chat.enterDialogTitle')" size="default" />
            <!-- 更新标题按钮：当有当前对话ID时显示 -->
            <el-button v-if="formData.currentDialogId" type="primary" size="default" @click="updateDialogTitle"
              class="update-title-btn-mobile" :disabled="!formData.dialogTitle.trim()">
              {{ t('chat.updateDialogTitle') }}
            </el-button>
          </div>

          <!-- 字体大小控制 -->
          <div class="font-size-controls">
            <span class="mobile-form-label">{{ t('chat.fontSizeLabel') }}</span>
            <el-radio-group v-model="fontSize" size="default" @change="handleFontSizeChange">
              <el-radio-button label="small">{{ t('chat.small') }}</el-radio-button>
              <el-radio-button label="medium">{{ t('chat.medium') }}</el-radio-button>
              <el-radio-button label="large">{{ t('chat.large') }}</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button type="warning" size="default" @click="clearCurrentSession" class="drawer-button">
              <el-icon>
                <CirclePlus />
              </el-icon>
              {{ t('chat.openAnotherSession') }}
            </el-button>

            <!-- 导出对话截屏按钮 -->
            <el-button type="primary" size="default" @click="exportConversationScreenshot" class="drawer-button">
              <el-icon>
                <Download />
              </el-icon>
              {{ t('chat.exportScreenshot') }}
            </el-button>
          </div>
        </div>
      </el-drawer>
    </div>
    <div class="messages-container" :class="'font-' + fontSize" ref="messagesContainer">
      <!-- 对话区域内嵌水印（用于长截图） -->
      <div class="message-author">
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
        <div class="message-content">
          <div class="message-header">
            <span class="message-author">{{ message.type === 'user' ? authStore.user : t('chat.AI') }}</span>
            <span class="message-time">{{ message.time }}</span>
            <div class="message-actions">
              <el-button :icon="CopyDocument" circle size="small" text @click="copyMessageContent(message.content)" />
              <el-popconfirm title="确定要删除这条消息吗？" confirm-button-text="确定" cancel-button-text="取消"
                @confirm="deleteMessage(index)">
                <template #reference>
                  <el-button :icon="Delete" circle size="small" text />
                </template>
              </el-popconfirm>
            </div>
          </div>
          <div class="message-text" v-html="renderMarkdown(getTextContent(message.content))"></div>
          <!-- TODO(human): 添加响应式表格和代码块的移动端优化，确保在小屏幕上能够良好显示 -->
          <!-- 已完成: 代码块和表格的移动端响应式布局优化 -->
          <!-- 图片预览 -->
          <div v-if="extractFileUrls(message.content).length > 0" class="message-attachments">
            <template v-for="url in extractFileUrls(message.content)" :key="url">
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
                答案马上就到，不要担心！
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
              重试
            </el-button>
          </div>
          <!-- 当回复为空时，提示用户重新发送 -->
          <div v-if="message.type === 'ai' && message.content === '' && !message.isError && !isStreaming(index)"
            class="empty-response-actions">
            <el-alert :closable="false" title="AI助手暂时没有回复，请稍后再试或重新提问" type="info" show-icon />
            <el-button type="primary" size="small" @click="retryMessage(index)">
              <el-icon>
                <RefreshLeft />
              </el-icon>
              重新提问
            </el-button>
          </div>
          <!-- 截断消息继续生成按钮 -->
          <div v-if="message.type === 'ai' && message.isTruncated && !message.isError && !isStreaming(index)"
            class="truncated-actions">
            <div class="truncated-indicator">
              <span class="ellipsis">...</span>
              <span class="truncated-hint">内容被截断</span>
            </div>
            <el-button type="primary" size="small" @click="continueGeneration(index)" :disabled="formData.isLoading">
              <el-icon>
                <CaretRight />
              </el-icon>
              继续生成
            </el-button>
          </div>
          <div v-if="message.file" class="message-file">
            <el-icon>
              <Document />
            </el-icon>
            <span>{{ message.file.name }}</span>
          </div>
        </div>
      </div>

      <div class="copyright-watermark-inline">
        <span>© 2026 vyfe | aichat.609088523.xyz | vx:pata_data_studio</span>
      </div>

      <!-- 开源项目链接 -->
      <div class="github-link-inline">
        <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer">
          <el-icon>
            <Link />
          </el-icon> 开源项目 GitHub
        </a>
        <span class="wechat-info"> vx:pata_data_studio </span>
      </div>

      <!-- 回到顶部按钮 -->
      <div v-if="showBackToTop" class="back-to-top-btn-normal" @click="scrollToTop">
        <el-icon>
          <Top />
        </el-icon>
      </div>
      <!-- 移动端：输入框显示/隐藏按钮，放在回到顶部按钮的右侧 -->
      <!-- <div v-if="formData.isMobile" class="toggle-input-btn" @click="toggleMobileInput">
        <el-icon>
          <component :is="showMobileInput ? 'Hide' : 'View'" />
        </el-icon>
      </div> -->
    </div>

    <!-- 输入区域 -->
    <InputArea
      v-if="!formData.isMobile || showMobileInput"
      v-model="inputMessage"
      :send-preference="formData.sendPreference"
      :is-loading="isLoading"
      :selected-model="formData.selectedModel"
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
      @send-message="handleSendMessage"
      @file-change="handleFileChange"
      @clear-file="clearFile"
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
import { ref, reactive, nextTick, onMounted, watch, onUnmounted, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  UploadFilled,
  UserFilled,
  Cpu,
  Document,
  Position,
  Delete,
  Plus,
  CopyDocument,
  RefreshLeft,
  Top,
  Link,
  CaretRight,
  Hide,
  View,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { chatAPI, fileAPI } from '@/services/api'
import { FormData } from '@/utils/main'
import InputArea from './InputArea.vue' // 新增：导入InputArea组件
import 'highlight.js/styles/github-dark.css'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { marked } from 'marked'

// 定义 props 和 emits
const props = defineProps<{
  modelValue: FormData
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
  'refresh-history': []
}>()

// 添加加载对话内容的方法
const loadDialogContent = async (dialogId: number) => {
  if (!useAuthStore().user) {
    ElMessage.warning('请先登录')
    return
  }

  try {
    const response: any = await chatAPI.getDialogContent(dialogId)
    if (response && response.content) {
      // 将消息数组替换为历史对话内容
      messages.splice(0, messages.length) // 清空现有消息
      const context = response.content.context
      // 假设response.content包含了完整的对话历史，按照某种格式组织
      // 这里需要根据实际API返回的格式来处理
      if (Array.isArray(context)) {
        // 如果返回的是消息数组
        // 过滤掉role为"system"的消息，不显示在聊天界面上
        const filteredContext = filterSystemMessages(context);
        filteredContext.forEach((msg: any) => {
          messages.push({
            type: msg.role === 'user' ? 'user' : 'ai',
            content: msg.content,
            time: msg.time || getCurrentTime()
          })
        })
      } else if (typeof response.data.content === 'string') {
        // 如果返回的是序列化的字符串，需要解析
        try {
          const contentObj = JSON.parse(context)
          if (Array.isArray(contentObj)) {
            // 过滤掉role为"system"的消息
            const filteredContentObj = filterSystemMessages(contentObj);
            filteredContentObj.forEach((msg: any) => {
              messages.push({
                type: msg.role === 'user' ? 'user' : 'ai',
                content: msg.content,
                time: msg.time || getCurrentTime()
              })
            })
          }
        } catch (e) {
          // 如果不是JSON格式，可能是单条消息
          messages.push({
            type: 'ai',
            content: response.content,
            time: getCurrentTime()
          })
        }
      }

      ElMessage.success('对话内容已加载')
    }
  } catch (error: any) {
    console.error('加载对话内容错误:', error)
    ElMessage.error('加载对话内容失败')
  }
}

// 监听来自父组件的load-dialog事件
defineExpose({
  loadDialogContent
})

// 过滤掉role为"system"的消息的辅助函数
const filterSystemMessages = (messages: any[]) => {
  return messages.filter((msg: any) => msg.role !== 'system')
}

// 统一的异常消息过滤函数
const filterAbnormalMessages = (messages: any[], options: { excludeIndex?: number, includeCurrent?: boolean } = {}) => {
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？';
  return messages.filter((msg, msgIndex) => {
    // 保留欢迎消息
    if (msg.type === 'ai' && msg.content === welcomeMessage) {
      return true;
    }

    // 如果指定了excludeIndex，跳过该索引的消息（用于重试等场景）
    if (options.excludeIndex !== undefined && msgIndex === options.excludeIndex) {
      return options.includeCurrent || false;
    }

    // 过滤掉带有错误标记的消息
    if (msg.isError) {
      return false;
    }
    // 过滤掉内容为空的AI消息（这些通常是有重新提问按钮的消息）
    if (msg.type === 'ai' && msg.content === '') {
      return false;
    }
    // 过滤掉带有截断标记的消息
    if (msg.isTruncated) {
      return false;
    }
    return true;
  });
}

// 统一的欢迎消息常量
const WELCOME_MESSAGE = '您好！我是AI助手，有什么可以帮助您的吗？';

// 待发送的消息队列
const messages = reactive<Array<{
  type: 'user' | 'ai'
  content: string
  time: string
  file?: File
  isError?: boolean  // 添加错误状态
  finishReason?: 'stop' | 'length' | 'content_filter' | 'tool_calls'  // 新增
  isTruncated?: boolean  // 新增
}>>([
  {
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  }
])

// 国际化
const { t } = useI18n()

// 自定义 renderer 用于处理数学公式
const mathRenderer = {
  inlineMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: false
      });
    } catch (error) {
      console.warn('KaTeX rendering error:', error);
      // 如果渲染失败，返回原始公式文本
      return `$${math}$`;
    }
  },
  displayMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: true
      });
    } catch (error) {
      console.warn('KaTeX rendering error:', error);
      // 如果渲染失败，返回原始公式文本
      return `$$${math}$$`;
    }
  }
};

const formData = (props.modelValue || {}) as FormData

const authStore = useAuthStore()
// 使用formData中的状态，不再定义局部状态
const inputMessage = ref('')
const uploadRef = ref()
const isLoading = ref(false)
const uploadedFile = ref<File | null>(null)
const showUploadPopover = ref(false)

// 添加字体大小控制 对话框
const fontSize = computed({
  get() {
    if (!formData) return 'medium'
    return formData.fontSize || 'medium'
  },
  set(value) {
    if (!formData) return
    formData.fontSize = value
    localStorage.setItem('fontSize', value)
  }
})

// 控制是否显示回到顶部按钮
const showBackToTop = ref(false)


// 添加侧边栏折叠状态
const isMobile = ref(false)
const showToolbarDrawer = ref(false)
// 控制移动端输入框显示/隐藏
const showMobileInput = ref(true)

// 记录之前的设备类型状态
const previousIsMobile = ref(false)
const messagesContainer = ref<HTMLElement>()
// 图片预览相关状态
const previewImageUrl = ref('')
const showImagePreview = ref(false)

// 添加键盘可见性检测
const isKeyboardVisible = ref(false)
const originalViewportHeight = ref(window.innerHeight)

// 检测视口高度变化以判断软键盘是否弹出
const checkKeyboardVisibility = () => {
  const currentHeight = window.innerHeight
  const heightDifference = originalViewportHeight.value - currentHeight

  // 如果视口高度减少超过150px，我们认为键盘弹出了
  isKeyboardVisible.value = heightDifference > 150
}

// 监听视口变化以检测键盘状态
const handleViewportChange = () => {
  if (formData.isMobile) {
    checkKeyboardVisibility()
  }
}

// 当用户点击更新标题按钮时
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
    if (response && response.success) {
      ElMessage.success('对话标题更新成功')

      // 更新对话历史列表中的标题
      const dialogItem = formData.dialogHistory.find(d => d.id === formData.currentDialogId)
      if (dialogItem) {
        dialogItem.dialog_name = formData.dialogTitle.trim()
      }
    } else {
      ElMessage.error(response.msg || '更新对话标题失败')
    }
  } catch (error: any) {
    console.error('更新对话标题错误:', error)
    ElMessage.error('更新对话标题失败')
  }
}

// 处理字体大小变化
const handleFontSizeChange = (size: string) => {
  // 可以在这里执行一些额外的逻辑，如果需要
  fontSize.value = size
}

// 清空当前会话
const clearCurrentSession = () => {
  messages.splice(0, messages.length)
  messages.push({
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  })
  // 清空对话标题和当前对话ID
  formData.dialogTitle = ''
  formData.currentDialogId = null
  ElMessage.success('已开启新会话')
}

// 导出对话截屏（长截图）
const exportConversationScreenshot = async () => {
  try {
    // 动态导入html-to-image库
    const htmlToImageModule = await import('html-to-image');
    const { toPng } = htmlToImageModule;

    const messagesContainer = document.querySelector('.messages-container') as HTMLElement;
    if (!messagesContainer) {
      ElMessage.error('无法找到对话容器');
      return;
    }

    // 保存原始样式
    const originalStyles = {
      overflow: messagesContainer.style.overflow,
      maxHeight: messagesContainer.style.maxHeight,
      height: messagesContainer.style.height,
    };

    // 临时修改样式以显示全部内容
    messagesContainer.style.overflow = 'visible';
    messagesContainer.style.maxHeight = 'none';
    messagesContainer.style.height = 'auto';

    // 使用html-to-image直接生成图像，不需要克隆节点
    const dataUrl = await toPng(messagesContainer, {
      cacheBust: true, // 防止缓存问题
      pixelRatio: 2.5, // 提高清晰度
      style: {
        // 确保元素在截图中显示完整内容
        overflow: 'visible',
        maxHeight: 'none',
        height: 'auto',
        filter: 'contrast(110%)', // 微调对比度，解决截图可能发灰的问题
      },
      // 排除不需要截图的元素
      filter: (node: Node) => {
        if (node instanceof HTMLElement) {
          // 不排除任何元素，因为我们希望截图完整对话
          return true;
        }
        return true;
      }
    });

    // 恢复原始样式
    messagesContainer.style.overflow = originalStyles.overflow;
    messagesContainer.style.maxHeight = originalStyles.maxHeight;
    messagesContainer.style.height = originalStyles.height;

    // 创建下载链接
    const link = document.createElement('a');
    link.download = `conversation_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`;
    link.href = dataUrl;
    link.click();

    ElMessage.success('对话截图已导出');
  } catch (error) {
    console.error('导出截图失败:', error);
    ElMessage.error('导出截图失败，请稍后重试');
  }
}

// 解析包含数学公式的Markdown内容
const renderMarkdownWithMath = (content: string) => {
  // 保存代码块内容，防止其中的数学公式被错误处理
  const codeBlockPlaceholders: string[] = [];
  const inlineCodePlaceholders: string[] = [];

  // 提取并替换代码块（```code```）
  let processedContent = content.replace(/```[\s\S]*?```/g, (match) => {
    codeBlockPlaceholders.push(match);
    return `__CODE_BLOCK_PLACEHOLDER_${codeBlockPlaceholders.length - 1}__`;
  });

  // 提取并替换行内代码（`code`）
  processedContent = processedContent.replace(/`[^`]*`/g, (match) => {
    inlineCodePlaceholders.push(match);
    return `__INLINE_CODE_PLACEHOLDER_${inlineCodePlaceholders.length - 1}__`;
  });

  // 首先处理显示数学公式 $$...$$（只在非代码块内容中处理）
  let resultContent = processedContent.replace(/\$\$(.*?)\$\$/gs, (match, math) => {
    return mathRenderer.displayMath(math.trim());
  });

  // 然后处理内联数学公式 $...$（只在非代码块内容中处理）
  resultContent = resultContent.replace(/\$([^\$]+)\$/g, (match, math) => {
    // 确保 $ 不是紧跟在字母或数字后面的（避免将价格等误认为数学公式）
    // 检查匹配项之前是否有字母或数字，或者检查是否为常见价格格式
    const prevChar = content[content.indexOf(match) - 1];
    const pricePattern = /^\$\d+(\.\d{1,2})?\s*$/; // 匹配 $数字 格式，如 $50 或 $12.34

    if (match.startsWith('\\$') || (prevChar && /\w/.test(prevChar)) || pricePattern.test(match + ' ')) {
      return match; // 如果是类似 $50 的格式或前面紧接字母/数字，不处理
    }
    return mathRenderer.inlineMath(math.trim());
  });

  // 将代码块内容还原回去
  for (let i = 0; i < codeBlockPlaceholders.length; i++) {
    resultContent = resultContent.replace(
      `__CODE_BLOCK_PLACEHOLDER_${i}__`,
      codeBlockPlaceholders[i]
    );
  }

  // 将行内代码内容还原回去
  for (let i = 0; i < inlineCodePlaceholders.length; i++) {
    resultContent = resultContent.replace(
      `__INLINE_CODE_PLACEHOLDER_${i}__`,
      inlineCodePlaceholders[i]
    );
  }

  // 解析 Markdown
  let result: string;
  try {
    // marked.parse 应该是同步函数，但如果它返回Promise，我们处理这种情况
    const parsedContent = marked.parse(resultContent || '');
    if (parsedContent instanceof Promise) {
      // 如果是Promise，我们无法在此同步上下文中处理它，使用原始内容
      result = resultContent || '';
    } else {
      result = typeof parsedContent === 'string' ? parsedContent.trim() : String(parsedContent);
    }
  } catch (error) {
    console.error('Markdown parsing error:', error);
    result = resultContent || '';
  }

  // 为Markdown生成的图片添加CSS类
  result = result.replace(/<img\s+([^>]*?)>/gi, '<img $1 class="attachment-preview" />');

  return result;
}

const renderMarkdown = (content: string) => {
  return renderMarkdownWithMath(content);
}

function getCurrentTime() {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 复制消息内容到剪贴板
const copyMessageContent = async (content: string) => {
  try {
    // 转换为带有结构的纯文本
    const plainText = convertMarkdownToPlainText(content);
    await navigator.clipboard.writeText(plainText);
    ElMessage.success('内容已复制到剪贴板');
  } catch (err) {
    console.error('复制失败:', err);
    // 如果 navigator.clipboard 不可用，使用传统的 document.execCommand 方法
    try {
      const textArea = document.createElement('textarea');
      // 转换为带有结构的纯文本
      const plainText = convertMarkdownToPlainText(content);
      textArea.value = plainText;
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

// 将Markdown内容转换为纯文本格式，保留结构信息
const convertMarkdownToPlainText = (content: string) => {
  // 创建一个临时div来解析HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = renderMarkdownWithMath(content);

  // 递归处理DOM节点，保留适当的格式
  const processNode = (node: Node): string => {
    let result = '';

    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || '';
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const element = node as HTMLElement;
      const tagName = element.tagName.toLowerCase();

      // 根据标签类型添加适当的格式化
      switch (tagName) {
        case 'h1':
        case 'h2':
        case 'h3':
        case 'h4':
        case 'h5':
        case 'h6':
          // 标题添加对应的#号
          result += '#'.repeat(parseInt(tagName.charAt(1))) + ' ';
          break;
        case 'li':
          // 列表项前添加项目符号
          result += '• ';
          break;
        case 'p':
          // 段落之间添加换行
          result += '\n';
          break;
        case 'br':
          result += '\n';
          break;
        case 'strong':
        case 'b':
          // 粗体不添加标记，只保留内容
          break;
        case 'em':
        case 'i':
          // 斜体不添加标记，只保留内容
          break;
        case 'code':
          // 代码块保留反引号
          if (element.parentElement?.tagName.toLowerCase() !== 'pre') {
            result += '`';
          }
          break;
        case 'pre':
          // 代码块前后添加三个反引号
          result += '```\n';
          break;
      }

      // 递归处理子节点
      for (let i = 0; i < element.childNodes.length; i++) {
        result += processNode(element.childNodes[i]);
      }

      // 添加闭合格式
      switch (tagName) {
        case 'pre':
          result += '\n```';
          break;
        case 'code':
          if (element.parentElement?.tagName.toLowerCase() !== 'pre') {
            result += '`';
          }
          break;
        case 'p':
          result += '\n';
          break;
      }
    }

    return result;
  };

  // 处理整个div的内容
  let plainText = '';
  for (let i = 0; i < tempDiv.childNodes.length; i++) {
    plainText += processNode(tempDiv.childNodes[i]);
  }

  // 清理多余的空白行
  plainText = plainText.replace(/\n{3,}/g, '\n\n').trim();

  return plainText;
};

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

// 通用API调用函数
const callApi = async (
  userMessage: any,
  contextSnapshot: any[],
  options: {
    isRetry?: boolean,
    originalIndex?: number,
    isContinue?: boolean
  } = {}
) => {
  const { isRetry = false, originalIndex, isContinue = false } = options;

  isLoading.value = true;

  try {
    // 检查是否是图像生成模型
    const isImageModel = formData.selectedModel && (formData.selectedModel.toLowerCase().includes('dall') || formData.selectedModel.toLowerCase().includes('image'));

    if (isImageModel) {
      // 图像生成模型仍使用普通API
      const aiResponse: any = await chatAPI.sendImageGeneration(
        formData.selectedModel,
        userMessage.content,
        formData.contextCount > 0 ? 'multi' : 'single',
        buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content),
        formData.dialogTitle
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

      // 根据是新消息还是重试消息决定如何添加到消息列表
      if (isRetry && originalIndex !== undefined) {
        // 替换重试的消息
        messages.splice(originalIndex, 1, {
          type: 'ai',
          content: responseContent,
          time: getCurrentTime()
        });
      } else {
        // 添加新AI消息
        messages.push({
          type: 'ai',
          content: responseContent,
          time: getCurrentTime()
        });
      }
    } else {
      // 根据开关决定使用流式还是非流式API
      if (formData.streamEnabled) {
        // 使用流式API
        let aiMessageIndex: number;

        if (isRetry && originalIndex !== undefined) {
          // 重试时替换原消息
          messages[originalIndex] = {
            type: 'ai',
            content: '',  // 初始内容为空
            time: getCurrentTime()
          };
          aiMessageIndex = originalIndex;
        } else {
          // 新消息时添加
          aiMessageIndex = messages.length;
          messages.push({
            type: 'ai',
            content: '',  // 初始内容为空
            time: getCurrentTime()
          });
        }

        // 使用之前保存的上下文快照构建对话数组，避免因异步操作造成的混乱
        const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content);

        await chatAPI.sendChatStream(
          formData.selectedModel,
          userMessage.content,
          (content, done, finishReason) => {
            messages[aiMessageIndex].content += content;
            if (done) {
              isLoading.value = false;
              if (finishReason === 'length') {
                messages[aiMessageIndex].finishReason = 'length';
                messages[aiMessageIndex].isTruncated = true;
              }
              // 如果内容仍然为空，说明出现了问题
              else if (messages[aiMessageIndex].content === '') {
                messages[aiMessageIndex].isError = true;
              }
            }
            // 只在用户位于底部时才滚动
            nextTick(() => {
              if (formData.isScrolledToBottom) {
                scrollToBottom();
              }
            });
          },
          formData.contextCount > 0 ? 'multi' : 'single',
          dialogArray,
          formData.dialogTitle,  // 添加dialogTitle参数
          Math.round(formData.maxResponseChars * 1.2 + 30) // 添加最大回复tokens参数（字数×2）
        );
      } else {
        // 使用非流式API
        let aiMessageIndex: number;

        if (isRetry && originalIndex !== undefined) {
          // 重试时替换原消息
          messages[originalIndex] = {
            type: 'ai',
            content: '',  // 初始内容为空
            time: getCurrentTime()
          };
          aiMessageIndex = originalIndex;
        } else {
          // 新消息时添加
          aiMessageIndex = messages.length;
          messages.push({
            type: 'ai',
            content: '',  // 初始内容为空
            time: getCurrentTime()
          });
        }

        // 使用之前保存的上下文快照构建对话数组
        const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content);

        const response: any = await chatAPI.sendChat(
          formData.selectedModel,
          userMessage.content,
          formData.contextCount > 0 ? 'multi' : 'single',
          dialogArray,
          formData.dialogTitle,
          Math.round(formData.maxResponseChars * 1.2 + 30) // 添加最大回复tokens参数（字数×2）
        );

        // 更新AI消息内容
        messages[aiMessageIndex].content = response.content;
        if (response.finish_reason === 'length') {
          messages[aiMessageIndex].finishReason = response.finish_reason as 'length';
          messages[aiMessageIndex].isTruncated = true;
        }

        isLoading.value = false;
        // 滚动到底部
        nextTick(() => {
          if (formData.isScrolledToBottom) {
            scrollToBottom();
          }
        });
      }
    }
  } catch (error: any) {
    console.error(isRetry ? '重试API Error:' : 'API Error:', error);

    let errorMessage = isRetry ? '重试失败，请稍后再次重试' : '获取AI回复失败，请重试';
    if (error.response) {
      errorMessage = isRetry
        ? `重试失败: ${error.response.data?.msg || error.response.statusText}`
        : `错误: ${error.response.data?.msg || error.response.statusText}`;
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行';
    } else if (error.message) {
      if (error.message.includes('API错误') || error.message.includes('API请求失败') ||
          error.message.includes('网段') || error.message.includes('白名单') ||
          error.message.includes('IP') || error.message.includes('ip')) {
        // 特别处理API错误信息，这通常来自SSE流中的错误消息
        errorMessage = isRetry ? `重试失败: ${error.message}` : error.message;
      } else {
        // 其他类型的错误消息也直接使用
        errorMessage = isRetry ? `重试失败: ${error.message}` : error.message;
      }
    }

    // 根据是新消息还是重试消息决定如何添加到消息列表
    if (isRetry && originalIndex !== undefined) {
      // 重试失败时替换消息
      messages.splice(originalIndex, 0, {
        type: 'ai',
        content: errorMessage,
        time: getCurrentTime(),
        isError: true  // 保持错误状态，用户仍可以再次重试
      });
    } else {
      // 添加错误AI消息，带有重试功能
      messages.push({
        type: 'ai',
        content: errorMessage,
        time: getCurrentTime(),
        isError: true  // 添加错误状态
      });
    }
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();

    if (!isRetry && !isContinue) {
      // 刷新对话历史记录（仅新消息发送时）
      emit('refresh-history');
    }
  }
}

// 发送消息
const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  if (!formData.selectedModel) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  // 清除异常类的消息（包含重试或继续输出按钮的消息）
  const normalMessages = filterAbnormalMessages(messages);

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

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
  if (!formData.dialogTitle.trim()) {
    // 截取前50个字符作为标题
    formData.dialogTitle = inputMessage.value.length > 50
      ? inputMessage.value.substring(0, 50) + '...'
      : inputMessage.value
  }

  inputMessage.value = ''
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 调用通用API函数
  await callApi(userMessage, contextSnapshot)
}

// 处理InputArea组件的发送消息事件
const handleSendMessage = async (message: string, file?: File) => {
  if (!message.trim()) return
  if (!formData.selectedModel) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  // 清除异常类的消息（包含重试或继续输出按钮的消息）
  const normalMessages = filterAbnormalMessages(messages);

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  const userMessage = {
    type: 'user' as const,
    content: message,
    time: getCurrentTime(),
    file: file || undefined
  }

  // 在构建对话数组之前先保存当前的上下文消息
  const contextSnapshot = [...messages]; // 创建当前消息快照用于构建上下文

  // 添加用户消息到数组
  messages.push(userMessage)

  // 如果当前没有设置标题，则将用户输入作为对话标题（只在第一次发送时）
  if (!formData.dialogTitle.trim()) {
    // 截取前50个字符作为标题
    formData.dialogTitle = message.length > 50
      ? message.substring(0, 50) + '...'
      : message
  }

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 调用通用API函数
  await callApi(userMessage, contextSnapshot)
}

// 重试发送特定AI消息（重新发送该消息所属的上下文）
const retryMessage = async (index: number) => {
  if (index < 0 || index >= messages.length || messages[index].type !== 'ai') {
    return;
  }

  // 清除异常类的消息（包含重试或继续输出按钮的消息），但保留当前要重试的消息
  const currentMessageToRetry = messages[index]; // 保存当前要重试的消息
  const normalMessages = filterAbnormalMessages(messages, { excludeIndex: index, includeCurrent: true });

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  // 重新查找要重试的消息的新索引
  const newIndexOfRetryMessage = messages.indexOf(currentMessageToRetry);

  // 如果消息不存在（不应该发生），则返回
  if (newIndexOfRetryMessage === -1) {
    ElMessage.error('重试的消息不存在');
    return;
  }

  // 查找这个AI消息之前的用户消息
  let userMessageIndex = -1;
  for (let i = newIndexOfRetryMessage - 1; i >= 0; i--) {
    if (messages[i].type === 'user') {
      userMessageIndex = i;
      break;
    }
  }

  if (userMessageIndex === -1) {
    ElMessage.error('找不到对应的问题消息，无法重试');
    return;
  }

  const userMessage = messages[userMessageIndex];

  // 移除错误或空的AI消息
  messages.splice(newIndexOfRetryMessage, 1);

  // 准备上下文信息（不包括当前错误的AI消息）
  const contextSnapshot = messages.slice(0, newIndexOfRetryMessage); // 获取到当前位置前的所有消息

  // 调用通用API函数
  await callApi(userMessage, contextSnapshot, {
    isRetry: true,
    originalIndex: newIndexOfRetryMessage
  });

  ElMessage.success('消息重试成功');
}

// 继续生成函数
// TODO 发送的逻辑可以重构到一个函数中，避免重复代码
const continueGeneration = async (index: number) => {
  if (formData.contextCount < 3) {
    ElMessageBox.alert('请将携带历史消息数量设置为3或更高，以支持连续续写功能', '提示', {
      confirmButtonText: '确定',
    })
    return
  }

  if (isLoading.value) return

  const truncatedMessage = messages[index]
  if (!truncatedMessage || !truncatedMessage.isTruncated) return

  // 清除异常类的消息（包含重试或继续输出按钮的消息），但保留当前要继续生成的消息
  const currentMessageToContinue = messages[index]; // 保存当前要继续生成的消息
  const normalMessages = filterAbnormalMessages(messages, { excludeIndex: index, includeCurrent: true });

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  // 重新查找要继续生成的消息的新索引
  const newIndexOfContinueMessage = messages.indexOf(currentMessageToContinue);

  // 如果消息不存在（不应该发生），则返回
  if (newIndexOfContinueMessage === -1) {
    ElMessage.error('继续生成的消息不存在');
    return;
  }

  // 创建用户消息对象用于继续生成
  const userMessage = {
    type: 'user' as const,
    content: "请继续生成未完成的内容，直接从上次中断的地方继续，不要重复已生成的内容。",
    time: getCurrentTime()
  };

  // 准备上下文信息
  const contextSnapshot = messages.slice(0, newIndexOfContinueMessage + 1);

  // 调用通用API函数
  await callApi(userMessage, contextSnapshot, {
    isContinue: true
  });
}

const currentEnhancedRoleContent = computed(() => {
  if (formData.activeEnhancedGroup && formData.selectedEnhancedRole) {
    const group = formData.enhancedRoleGroups[formData.activeEnhancedGroup]
    if (group) {
      const role = group.find(r => r.role_name === formData.selectedEnhancedRole)
      return role ? role.role_content : ''
    }
  }
  return ''
})

// 从消息快照构建对话数组函数
const buildDialogArrayFromSnapshot = (snapshot: any[], currentMessage: string): Array<{role: string, content: string}> => {
  const dialogArray: Array<{role: string, content: string}> = []

  // 如果有角色设定，添加到最前面
  // 根据enhancedRoleEnabled状态决定使用systemPrompt还是currentEnhancedRoleContent作为system角色的内容
  const systemContent = formData.enhancedRoleEnabled ? currentEnhancedRoleContent.value : formData.systemPrompt
  if (systemContent && systemContent.trim()) {
    dialogArray.push({ role: 'system', content: systemContent.trim() })
  }

  // 如果上下文数量为 0，只发送当前消息（但仍需包含 system 消息）
  if (formData.contextCount === 0) {
    dialogArray.push({ role: 'user', content: currentMessage })
    return dialogArray
  }

  // 获取快照中的有效消息（user 和 ai 类型），但排除初始欢迎消息
  const validMessages = snapshot.filter((msg: any) => (msg.type === 'user' || msg.type === 'ai') && msg.content !== WELCOME_MESSAGE)

  // 获取要包含的上下文消息
  const messagesToInclude = validMessages.slice(-formData.contextCount) // 只取最新的几条

  for (const msg of messagesToInclude) {
    dialogArray.push({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    })
  }

  dialogArray.push({ role: 'user', content: currentMessage })
  return dialogArray
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
// 滚动相关
// 回到顶部函数
const scrollToTop = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: 0,
      behavior: 'smooth'
    })
  }
}

// 切换移动端输入框显示/隐藏
const toggleMobileInput = () => {
  showMobileInput.value = !showMobileInput.value
}
const scrollToBottom = () => {
  if (messagesContainer.value && formData.isScrolledToBottom) {
    // 只有在用户已经滚动到底部时才继续滚动
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听滚动事件，判断用户是否滚动到了底部
const handleScroll = () => {
  if (messagesContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
    // 如果距离底部小于50像素，则认为是在底部
    formData.isScrolledToBottom = scrollHeight - scrollTop - clientHeight < 50

    // 控制回到顶部按钮的显示：当滚动位置超过一屏时显示
    showBackToTop.value = scrollTop > clientHeight

    // 如果软键盘弹出，自动保持滚动到底部
    if (isKeyboardVisible.value) {
      scrollToBottom()
    }
  }
}

// 文件相关处理
const handleFileChange = async (file: any) => {
  try {
    // 检查是否为MD文件，如果是则重命名为TXT文件
    let fileToUpload = file.raw;
    if (file.raw.type === 'text/markdown' || file.name.toLowerCase().endsWith('.md')) {
      // 读取MD文件内容并创建新的TXT文件
      const textContent = await file.raw.text();
      const txtFileName = file.name.replace(/\.md$/, '.txt');
      fileToUpload = new File([textContent], txtFileName, { type: 'text/plain' });
      ElMessage.info(`MD文件已转换为TXT格式: ${txtFileName}`)
    }

    // 上传文件到服务器
    const response = await fileAPI.upload(fileToUpload)
    if (response && response.data.content) {
      // 文件上传成功，将URL添加到当前消息中
      uploadedFile.value = fileToUpload
      // 如果后端返回的content是相对路径或缺少host，则补充完整URL
      let fullUrl = response.data.content
      if (response.data.content.startsWith(':')) {
        // 如果返回以冒号开头（如 :4567/download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.data.content
      } else if (response.data.content.startsWith('/')) {
        // 如果返回以斜杠开头（如 /download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.data.content
      }
      // 在输入框中插入文件URL，使用特殊格式以支持Gemini模型
      inputMessage.value += `\n[FILE_URL:${fullUrl}]`
      ElMessage.success(`文件 "${fileToUpload.name}" 已上传`)
    } else {
      throw new Error(response.data.msg || '文件上传失败')
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

// 实现移动端设备检测逻辑，当屏幕宽度小于768px时将isMobile设为true，并监听窗口大小变化
const checkIsMobile = () => {
  // 当窗口宽度小于768px时，认为是移动端
  const currentIsMobile = window.innerWidth < 768

  // 如果设备类型发生变化，则相应地调整抽屉状态
  if (currentIsMobile !== previousIsMobile.value) {
    // 在从桌面端切换到移动端时，不自动打开抽屉
    // 在从移动端切换到桌面端时，如果抽屉是打开的则关闭它
    if (!currentIsMobile && showToolbarDrawer.value) {
      showToolbarDrawer.value = false
    }
  }

  isMobile.value = currentIsMobile
  previousIsMobile.value = currentIsMobile
}

// 打开图片预览
const openImagePreview = (url: string) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

// 初始化时检测是否为移动端
onMounted(() => {
  checkIsMobile()

  // 监听窗口大小变化
  window.addEventListener('resize', checkIsMobile)
})

// 组件卸载时移除事件监听器
onUnmounted(() => {
  window.removeEventListener('resize', checkIsMobile)
})

// 在组件挂载时应用主题
onMounted(() => {
  checkIsMobile()

  if (formData.isDarkTheme) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }

  // 添加滚动事件监听器
  const container = messagesContainer.value
  if (container) {
    container.addEventListener('scroll', handleScroll)
  }
})

// 组件卸载时移除事件监听器
onUnmounted(() => {
  window.removeEventListener('resize', checkIsMobile)

  // 移除滚动事件监听器
  const container = messagesContainer.value
  if (container) {
    container.removeEventListener('scroll', handleScroll)
  }
})

// 从消息内容中提取文件URL列表（兼容新旧格式）
const extractFileUrls = (content: string): string[] => {
  const urls: string[] = [];

  // 定义URL提取正则表达式
  const patterns = [
    { regex: /\[FILE_URL:(https?:\/\/[^\]]+)\]/g, name: 'new' },         // 新格式: [FILE_URL:xxx]
    { regex: /文件已上传:\s*(https?:\/\/[^\s]+)/g, name: 'old' }         // 旧格式: 文件已上传: xxx
  ];

  // 遍历所有模式并提取URL
  patterns.forEach(({ regex }) => {
    let match;
    while ((match = regex.exec(content)) !== null) {
      urls.push(match[1]);
    }
  });

  return urls;
};

// 测试函数（仅供验证，后续可以移除）
// const testExtractFileUrls = () => {
//   console.log("Test 1:", extractFileUrls("[FILE_URL:https://example.com/test.pdf]"));
//   console.log("Test 2:", extractFileUrls("文件已上传: https://example.com/test2.jpg"));
//   console.log("Test 3:", extractFileUrls("[FILE_URL:https://example.com/test.pdf] and 文件已上传: https://example.com/test2.jpg"));
// };

// 在组件挂载时运行测试（可选）
// onMounted(() => {
//   testExtractFileUrls();
//   if (formData.isDarkTheme) {
//     document.body.classList.add('dark-theme')
//   } else {
//     document.body.classList.remove('dark-theme')
//   }
// })

// 获取纯文本内容（移除文件标记）
const getTextContent = (content: string): string => {
  return content.replace(/\[(FILE_URL|文件已上传):[^\]]+\]/g, '').trim()
}

// 判断URL是否为图片
const isImageUrl = (url: string): boolean => {
  return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url)
}

// 监听对话ID变化，当ID变化时自动加载对话内容
watch(() => formData.currentDialogId, async (newDialogId) => {
  if (newDialogId !== null && newDialogId !== undefined) {
    await loadDialogContent(newDialogId)
  }
})

// 监听暗色主题变化
watch(() => formData.isDarkTheme, (newVal) => {
  if (newVal) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }
}, { immediate: true })

// 监听模型列表变化，自动生成级联选项
</script>

<style scoped>
@import './chat-content.css';
</style>
