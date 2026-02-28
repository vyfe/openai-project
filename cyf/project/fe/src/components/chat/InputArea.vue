<template>
  <div :class="['input-area', {'input-area-mobile': props.isMobile, 'always-fixed-bottom': props.isMobile}]">
    <div class="input-container">
      <!-- 文件预览区域 -->
      <div v-if="uploadedFiles.length > 0" class="file-preview-area">
        <div v-for="file in uploadedFiles" :key="file.url" class="file-preview-tag">
          <!-- 图片预览 -->
          <img v-if="file.isImage" :src="file.url" class="file-preview-thumb" alt="preview" />
          <!-- 非图片文件图标 -->
          <div v-else class="file-preview-icon">
            <el-icon><Document /></el-icon>
          </div>
          <!-- 文件名 -->
          <span class="file-preview-name">{{ file.name }}</span>
          <!-- 删除按钮 -->
          <el-button class="file-delete-btn" :icon="Close" size="small" circle @click="removeFile(file)" />
        </div>
      </div>

      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        :placeholder="`${t('chat.inputPlaceholder')} (${sendPreference === 'enter' ? t('chat.enterToSendHint') : t('chat.enterToNewlineHint')})`"
        class="message-input"
        @keydown="handleKeydown"
      />
      <div class="input-addons">
        <!-- 图片模型尺寸选择下拉框 -->
        <div v-if="isImageModel" class="image-size-control">
          <el-select
            v-model="selectedImageSize"
            placeholder="选择图片尺寸"
            class="image-size-select"
            size="default"
          >
            <el-option
              v-for="size in imageSizeOptions"
              :key="size.value"
              :label="size.label"
              :value="size.value"
            />
          </el-select>
        </div>

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
                  <span>{{ t('chat.uploadFile') }}</span>
                  <el-button v-if="uploadedFile" type="danger" size="small" text @click="clearFile">{{ t('chat.clear') }}</el-button>
                </div>
                <el-upload ref="uploadRef" drag :auto-upload="false" :on-change="handleFileChange"
                  accept=".txt,.pdf,.png,.jpg,.jpeg,.gif,.ppt,.pptx,.md,.markdown">
                  <el-icon><upload-filled /></el-icon>
                  <div class="el-upload__text">{{ t('chat.dragDropOrClickUpload') }}</div>
                </el-upload>
              </div>
            </el-popover>

            <el-button
              type="primary"
              :icon="Position"
              :disabled="(!inputMessage.trim() && uploadedFiles.length === 0) || isLoading"
              @click="sendMessage"
            >
              {{ t('chat.send') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  UploadFilled,
  Position,
  Plus,
  Document,
  Close,
} from '@element-plus/icons-vue'
import { fileAPI } from '@/services/api'
import { Props, FileUploadResponse } from '@/components/chat/types'

// 提取的文件接口
interface ExtractedFile {
  url: string
  name: string
  isImage: boolean
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
  selectedModelType: 1,  // 默认为1（非图片模型）
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
  'send-message': [message: string, file?: File, imageSize?: string]  // 添加图片尺寸参数
  'file-change': [file: any]
  'clear-file': []
}

const emit = defineEmits<Emits>()

// 国际化
const { t } = useI18n()

// 图片尺寸选项
const imageSizeOptions = [
  { value: '1024x1024', label: '1024x1024 (标准)' },
  { value: '1024x1792', label: '1024x1792 (纵向)' },
  { value: '1792x1024', label: '1792x1024 (横向)' },
  { value: '512x512', label: '512x512 (小)' },
  { value: '1280x1280', label: '1280x1280 (较大)' },
  { value: '1536x1536', label: '1536x1536 (大)' },
  { value: '2048x2048', label: '2048x2048 (2k超大)' },
  { value: '4096x4096', label: '4096x4096 (4k极大)' },
]

// 响应式数据
const inputMessage = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const uploadedFile = ref<File | null>(null)
const showUploadPopover = ref(false)
const uploadRef = ref()
const selectedImageSize = ref('1024x1024') // 默认尺寸

// 已上传的文件列表
const uploadedFiles = ref<ExtractedFile[]>([])

// 计算属性：判断是否为图片模型
const isImageModel = computed(() => {
  return props.selectedModelType === 2
})

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
  if (!inputMessage.value.trim() && uploadedFiles.value.length === 0) return

  if (!props.selectedModel) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  // 构建要发送的消息
  let messageToSend = inputMessage.value

  // 如果有已上传的文件，将文件URL转换为标记并追加到消息
  if (uploadedFiles.value.length > 0) {
    const fileMarkers = uploadedFiles.value.map(file => `\n[FILE_URL:${file.url}]`)
    messageToSend = messageToSend + fileMarkers.join('')
  }

  // 如果是图片模型，添加尺寸信息到消息中
  if (isImageModel.value) {
    // 在消息末尾添加图片尺寸信息
    messageToSend = `${messageToSend}\n[IMAGE_SIZE:${selectedImageSize.value}]`
  }

  emit('send-message', messageToSend, uploadedFile.value || undefined)

  // 清空输入框和文件
  inputMessage.value = ''
  uploadedFiles.value = []
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
    // 检查文件对象是否有效
    if (!file) {
      throw new Error('未选择文件')
    }
    
    // 检查是否为MD文件，如果是则重命名为TXT文件
    let fileToUpload = file.raw || file; // 兼容不同的文件对象格式
    
    // 确保文件对象有必要的属性
    if (!fileToUpload) {
      throw new Error('文件对象无效')
    }
    
    // 检查文件类型和扩展名
    const fileType = fileToUpload.type || '';
    const fileName = file.name || fileToUpload.name || '';
    
    if (fileType === 'text/markdown' || fileName.toLowerCase().endsWith('.md')) {
      // 确保文件有text方法
      if (typeof fileToUpload.text !== 'function') {
        throw new Error('无法读取文件内容')
      }
      
      // 读取MD文件内容并创建新的TXT文件
      const textContent = await fileToUpload.text();
      const txtFileName = fileName.replace(/\.md$/, '.txt');
      fileToUpload = new File([textContent], txtFileName, { type: 'text/plain' });
      ElMessage.info(`MD文件已转换为TXT格式: ${txtFileName}`)
    }

    // 上传文件到服务器
    const response: FileUploadResponse = await fileAPI.upload(fileToUpload)
    // 类型检查以处理可能未定义的content字段
    if (response && typeof response === 'object' && 'content' in response && response.content) {
      // 文件上传成功，将URL添加到已上传文件列表
      uploadedFile.value = fileToUpload
      // 如果后端返回的content是相对路径或缺少host，则补充完整URL
      let fullUrl = response.content
      if (response.content.startsWith(':')) {
        // 如果返回以冒号开头（如 :4567/download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.content
      } else if (response.content.startsWith('/')) {
        // 如果返回以斜杠开头（如 /download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.content
      }
      // 添加到已上传文件列表（不在输入框中插入标记）
      uploadedFiles.value.push({
        url: fullUrl,
        name: fileToUpload.name || fileName,
        isImage: isImageUrl(fullUrl)
      })
      ElMessage.success(`文件 "${fileToUpload.name || fileName}" 已上传`)

      emit('file-change', fileToUpload)
    } else {
      // 如果response没有content字段或content为空，抛出错误
      const errorMsg = response && typeof response === 'object' && 'msg' in response && response.msg
        ? response.msg
        : '文件上传失败或服务器响应格式错误';
      throw new Error(errorMsg)
    }
  } catch (error: any) {
    console.error('文件上传错误:', error)
    let errorMessage =  t('chat.fileUploadFailed')
    if (error.response?.data?.msg) {
      errorMessage = error.response.data.msg
    } else if (error?.response?.data?.content) {
      errorMessage = error.response.data.content
    } else if (typeof error === 'object' && error.msg) {
      errorMessage = error.msg
    } else if (typeof error === 'string') {
      errorMessage = error
    } else if (error.message) {
      errorMessage = error.message
    }
    ElMessage.error(errorMessage)
  }
}

const clearFile = () => {
  uploadedFile.value = null
  uploadedFiles.value = []
  emit('clear-file')
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

// 判断是否为图片
const isImageUrl = (url: string): boolean => {
  return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url)
}

// 删除文件
const removeFile = (fileToRemove: ExtractedFile) => {
  const index = uploadedFiles.value.findIndex(f => f.url === fileToRemove.url)
  if (index !== -1) {
    uploadedFiles.value.splice(index, 1)
  }
}
</script>

<style scoped>
@import '@/styles/input-area.css';
</style>