<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left">
        <el-button
          :icon="Menu"
          @click="toggleSidebar"
          class="menu-button"
        />
        <h2>{{ t('chat.title') }}</h2>
      </div>
      <div class="header-right">
        <el-button @click="showUsageQuery = true">
          {{ t('chat.usage') }}
        </el-button>
        <el-button @click="toggleTheme">
          {{ isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme') }}
        </el-button>
        <el-button @click="logout">
          {{ t('chat.logout') }}
        </el-button>
      </div>
    </div>

    <div class="chat-main">
      <!-- 侧边栏 -->
      <ChatSidebar
        :collapsed="sidebarCollapsed"
        :is-mobile="isMobile"
        :current-dialog-id="currentDialogId"
        @update:collapsed="updateSidebarCollapsed"
        @load-dialog="loadDialog"
        @model-change="handleModelChange"
        @settings-change="handleSettingsChange"
        @update:current-dialog-id="updateCurrentDialogId"
      />

      <!-- 聊天内容区域 -->
      <ChatContent
        :selected-model="selectedModel"
        :context-count="contextCount"
        :max-response-chars="maxResponseChars"
        :stream-enabled="streamEnabled"
        :system-prompt="systemPrompt"
        :send-preference="sendPreference"
        :current-dialog-id="currentDialogId"
        :is-mobile="isMobile"
        @dialog-created="handleDialogCreated"
        @refresh-history="refreshHistory"
        @update:current-dialog-id="updateCurrentDialogId"
      />
    </div>

    <!-- 侧边栏遮罩层（移动端） -->
    <div
      v-if="isMobile && !sidebarCollapsed"
      class="sidebar-overlay"
      @click="updateSidebarCollapsed(true)"
    />

    <!-- 图片预览弹窗 -->
    <el-dialog
      v-model="imagePreviewVisible"
      :title="$t('chat.imagePreview')"
      width="80%"
      top="5vh"
    >
      <img
        :src="currentImageUrl"
        alt="预览图片"
        style="width: 100%; height: auto; max-height: 70vh; object-fit: contain;"
      />
    </el-dialog>

    <!-- LaTeX帮助弹窗 -->
    <el-dialog
      v-model="latexHelpVisible"
      :title="$t('chat.latexHelp')"
      width="60%"
    >
      <div class="latex-help-content">
        <p>{{ $t('chat.latexHelpText') }}</p>
        <ul>
          <li>\frac{a}{b} - {{ $t('chat.fraction') }}</li>
          <li>x^2 - {{ $t('chat.superscript') }}</li>
          <li>x_2 - {{ $t('chat.subscript') }}</li>
          <li>\sqrt{x} - {{ $t('chat.squareRoot') }}</li>
          <li>\sum_{i=1}^n - {{ $t('chat.summation') }}</li>
          <li>\int_a^b - {{ $t('chat.integral') }}</li>
        </ul>
      </div>
    </el-dialog>

    <!-- 使用量查询弹窗 -->
    <el-dialog
      v-model="showUsageQuery"
      :title="$t('chat.usageQuery')"
      width="50%"
    >
      <el-form :model="usageQueryForm" label-width="auto">
        <el-form-item :label="t('chat.startDate')">
          <el-date-picker
            v-model="usageQueryForm.startDate"
            type="date"
            :placeholder="t('chat.selectDate')"
          />
        </el-form-item>
        <el-form-item :label="t('chat.endDate')">
          <el-date-picker
            v-model="usageQueryForm.endDate"
            type="date"
            :placeholder="t('chat.selectDate')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUsageQuery = false">
          {{ t('chat.close') }}
        </el-button>
        <el-button type="primary" @click="queryUsage">
          {{ t('chat.query') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Menu } from '@element-plus/icons-vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ChatContent from '../components/chat/ChatContent.vue'
import { useChat } from '../composables/useChat'

// 国际化
const { t } = useI18n()
const router = useRouter()

// 共享状态
const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const isDarkTheme = ref(false)
const currentDialogId = ref<number | null>(null)

// 全局设置
const selectedModel = ref('gpt-4o')
const contextCount = ref(5)
const maxResponseChars = ref(2000)
const streamEnabled = ref(true)
const systemPrompt = ref('')
const sendPreference = ref<'enter' | 'ctrl_enter'>('enter')

// 弹窗控制
const imagePreviewVisible = ref(false)
const currentImageUrl = ref('')
const latexHelpVisible = ref(false)
const showUsageQuery = ref(false)

// 使用量查询表单
const usageQueryForm = ref({
  startDate: '',
  endDate: ''
})

// 检测设备类型
const checkDeviceType = () => {
  isMobile.value = window.innerWidth < 768
}

// 切换侧边栏
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 更新侧边栏状态
const updateSidebarCollapsed = (collapsed: boolean) => {
  sidebarCollapsed.value = collapsed
}

// 更新当前对话ID
const updateCurrentDialogId = (id: number | null) => {
  currentDialogId.value = id
}

// 加载对话
const loadDialog = (dialogId: number) => {
  currentDialogId.value = dialogId
  // 实际加载逻辑会在ChatContent中处理
}

// 处理模型变化
const handleModelChange = (model: string) => {
  selectedModel.value = model
}

// 处理设置变化
const handleSettingsChange = (settings: any) => {
  contextCount.value = settings.contextCount
  maxResponseChars.value = settings.maxResponseChars
  streamEnabled.value = settings.streamEnabled
  systemPrompt.value = settings.systemPrompt
  sendPreference.value = settings.sendPreference
}

// 处理对话创建
const handleDialogCreated = (dialogId: number) => {
  currentDialogId.value = dialogId
}

// 刷新历史
const refreshHistory = () => {
  // 触发侧边栏刷新历史
}

// 切换主题
const toggleTheme = () => {
  isDarkTheme.value = !isDarkTheme.value
  // 实际的主题切换逻辑
  if (isDarkTheme.value) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }
}

// 登出
const logout = () => {
  localStorage.removeItem('token')
  router.push('/login')
  ElMessage.success(t('chat.logoutSuccess'))
}

// 查询使用量
const queryUsage = () => {
  // 实际的使用量查询逻辑
  console.log('查询使用量', usageQueryForm.value)
  showUsageQuery.value = false
}

// 监听窗口大小变化
const handleResize = () => {
  checkDeviceType()
}

// 组件挂载
onMounted(() => {
  checkDeviceType()
  window.addEventListener('resize', handleResize)
})

// 组件卸载
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-button {
  display: none;
}

.header-right {
  display: flex;
  gap: 12px;
}

.chat-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar-overlay {
  position: fixed;
  top: 60px;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: none;
}

.latex-help-content ul {
  padding-left: 20px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .menu-button {
    display: block;
  }

  .chat-main {
    position: relative;
  }

  .sidebar-overlay {
    display: block;
  }
}
</style>
