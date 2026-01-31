<template>
  <div :class="['input-area', {'input-area-mobile': props.isMobile, 'always-fixed-bottom': props.isMobile}]">
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
        <!-- 将按钮放入编组容器中 -->
        <div class="button-group">
          <!-- 文件上传按钮移到输入框上方，右侧 -->
          <el-popover placement="top-start" :width="280" trigger="click" v-model:visible="showUploadPopover">
            <template #reference>
              <el-button class="upload-trigger-btn" :icon="Plus" size="large" />
            </template>
            <div class="upload-popover-content">
              <div class="upload-popover-header">
                <span>上传文件</span>
                <el-button v-if="uploadedFile" type="danger" size="small" text @click="clearFile">清除</el-button>
              </div>
              <el-upload ref="uploadRef" drag :auto-upload="false" :on-change="handleFileChange"
                accept=".txt,.pdf,.png,.jpg,.jpeg,.gif,.ppt,.pptx,.md,.markdown">
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  UploadFilled,
  Position,
  Plus,
} from '@element-plus/icons-vue'
import { fileAPI } from '@/services/api'

// 定义 props
interface Props {
  modelValue: string
  sendPreference?: 'enter' | 'ctrl_enter'
  isLoading?: boolean
  contextCount?: number
  enhancedRoleEnabled?: boolean
  systemPrompt?: string
  activeEnhancedGroup?: string
  selectedEnhancedRole?: string
  enhancedRoleGroups?: Record<string, any[]>
  selectedModel?: string
  streamEnabled?: boolean
  maxResponseChars?: number
  dialogTitle?: string
  currentDialogId?: number | null
  isScrolledToBottom?: boolean
  isMobile?: boolean
  fontSize?: string
}

const props = withDefaults(defineProps<Props>(), {
  sendPreference: 'enter',
  isLoading: false,
  contextCount: 0,
  enhancedRoleEnabled: false,
  systemPrompt: '',
  activeEnhancedGroup: '',
  selectedEnhancedRole: '',
  selectedModel: '',
  streamEnabled: true,
  maxResponseChars: 1000,
  dialogTitle: '',
  currentDialogId: null,
  isScrolledToBottom: true,
  isMobile: false,
  fontSize: 'medium',
})

// 定义 emits
interface Emits {
  'update:modelValue': [value: string]
  'send-message': [message: string, file?: File]
  'file-change': [file: any]
  'clear-file': []
}

const emit = defineEmits<Emits>()

// 响应式数据
const inputMessage = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const uploadedFile = ref<File | null>(null)
const showUploadPopover = ref(false)
const uploadRef = ref()

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
  if (props.isMobile) {
    checkKeyboardVisibility()
  }
}

// 组件挂载时添加事件监听
onMounted(() => {
  if (props.isMobile) {
    // 初始化时检测当前键盘状态
    originalViewportHeight.value = window.innerHeight;
    checkKeyboardVisibility();
    window.addEventListener('resize', handleViewportChange)
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  if (props.isMobile) {
    window.removeEventListener('resize', handleViewportChange)
  }
})

// 方法
const sendMessage = () => {
  if (!inputMessage.value.trim()) return

  if (!props.selectedModel) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  emit('send-message', inputMessage.value, uploadedFile.value || undefined)

  // 清空输入框和文件
  inputMessage.value = ''
  if (uploadedFile.value) {
    uploadedFile.value = null
    emit('clear-file')
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (props.sendPreference === 'ctrl_enter') {
    // 如果用户选择Ctrl+Enter发送
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      sendMessage()
    }
    // 普通回车不阻止默认行为，允许换行
  } else if (props.sendPreference === 'enter') {
    // 如果用户选择Enter发送
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      sendMessage()
    }
    // Shift+Enter 或其他组合键仍然允许换行
  }
}

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

      emit('file-change', fileToUpload)
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
  emit('clear-file')
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}
</script>

<style scoped>
@import './input-area.css';
</style>