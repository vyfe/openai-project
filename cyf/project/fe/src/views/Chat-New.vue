<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left">
        <el-button
          class="sidebar-toggle-btn"
          :icon="formData.sidebarCollapsed ? Expand : Fold"
          circle size="small"
          @click="formData.sidebarCollapsed = !formData.sidebarCollapsed"
        />
        <h2>{{ t('chat.title') }}</h2>
        <span class="user-info">用户：{{ authStore.user }}</span>

        <!-- 用量查询弹窗 -->
        <el-popover
          placement="bottom"
          :width="300"
          trigger="click"
          v-model:visible="showUsagePopover"
        >
          <template #reference>
            <el-button
              class="usage-btn"
              :icon="Coin"
              size="small"
              @click="fetchUsage"
            >
              查看用量
            </el-button>
          </template>
          <div class="usage-content">
            <div v-if="loadingUsage" class="loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              正在加载用量数据...
            </div>
            <div v-else-if="usageError" class="error">
              {{ usageError }}
            </div>
            <div v-else class="usage-data">
              <div class="usage-item">
                <span class="label">总用量：</span>
                <span class="value">{{ usageData?.total_usage }} 元</span>
              </div>
              <div class="usage-item">
                <span class="label">总额度：</span>
                <span class="value">{{ usageData?.quota > 10000 ? '-' : usageData?.quota }} 元</span>
              </div>
              <div class="usage-item" :class="{ 'low-balance': usageData?.remaining < 10 }">
                <span class="label">剩余额度：</span>
                <span class="value">{{ usageData?.remaining }} 元</span>
              </div>
            </div>
          </div>
        </el-popover>

        <!-- LaTeX 帮助按钮 -->
        <el-button
          :icon="Document"
          size="small"
          @click="showLatexHelp = true"
          class="latex-help-btn"
        >
          LaTeX 帮助
        </el-button>
      </div>
      <div class="header-right">
        <el-button @click="toggleTheme">
          {{ formData.isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme') }}
        </el-button>
        <el-button @click="logout">
          {{ t('chat.logout') }}
        </el-button>
      </div>
    </div>

    <div class="chat-main">
      <!-- 侧边栏 -->
      <ChatSidebar
        :collapsed="formData.sidebarCollapsed"
        :is-mobile="formData.isMobile"
        :current-dialog-id="formData.currentDialogId"
        @update:collapsed="updateSidebarCollapsed"
        @load-dialog="loadDialog"
        @model-change="handleModelChange"
        @settings-change="handleSettingsChange"
        @update:current-dialog-id="updateCurrentDialogId"
        v-model="formData"
      />

      <!-- 聊天内容区域 -->
      <ChatContent
        :selected-model="formData.selectedModel"
        :context-count="formData.contextCount"
        :max-response-chars="formData.maxResponseChars"
        :stream-enabled="formData.streamEnabled"
        :system-prompt="formData.systemPrompt"
        :send-preference="formData.sendPreference"
        :current-dialog-id="formData.currentDialogId"
        :is-mobile="formData.isMobile"
        @dialog-created="handleDialogCreated"
        @refresh-history="refreshHistory"
        @update:current-dialog-id="updateCurrentDialogId"
        v-model="formData"
      />
    </div>

    <!-- 侧边栏遮罩层（移动端） -->
    <div
      v-if="formData.isMobile && !formData.sidebarCollapsed"
      class="sidebar-overlay"
      @click="updateSidebarCollapsed(true)"
    />

    <!-- LaTeX帮助弹窗 -->
    <el-dialog
      v-model="showLatexHelp"
      :title="$t('chat.latexHelp')"
      width="60%"
    >
      <div class="latex-help-content">
        <p>LaTeX是一种专业的排版系统，常用于数学公式的书写。</p>
        <ul>
          <li>\frac{a}{b} - 分数形式，显示为 a/b</li>
          <li>x^2 - 上标，显示为 x²</li>
          <li>x_2 - 下标，显示为 x₂</li>
          <li>\sqrt{x} - 平方根，显示为 √x</li>
          <li>\sum_{i=1}^n - 求和符号</li>
          <li>\int_a^b - 积分符号</li>
          <li>\lim_{x \to \infty} - 极限符号</li>
          <li>\alpha, \beta, \gamma - 希腊字母</li>
        </ul>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Menu, Expand, Fold, Coin, Document, Loading } from '@element-plus/icons-vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ChatContent from '../components/chat/ChatContent.vue'
import { useChat } from '../composables/useChat'
import { useAuthStore } from '../stores/auth'
import { chatAPI } from '../services/api'

// 国际化和认证
const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

// 组件间共享状态
const formData = reactive({
  isDarkTheme: false,
  currentDialogId: ref<number | null>(null),
  selectedModel: localStorage.getItem('selectedModel') || '',
  // 上下文字数
  contextCount: parseInt(localStorage.getItem('contextCount') || '10'),
  // 侧边栏折叠状态
  sidebarCollapsed: JSON.parse(localStorage.getItem('sidebarCollapsed') || 'false'),
  // 最大回复字数（实际 token = 值 * 2）
  maxResponseChars: parseInt(localStorage.getItem('maxResponseChars') || '8000'),
  isMobile: false,
  streamEnabled: JSON.parse(localStorage.getItem('streamEnabled') || 'true'),
  systemPrompt: '',
  sendPreference: localStorage.getItem('sendPreference') || 'ctrl_enter',
})
const showToolbarDrawer = ref(false)


// 用于检测软键盘是否激活的状态
const isKeyboardVisible = ref(false)

// 记录之前的设备类型状态
const previousIsMobile = ref(false)

// 弹窗控制
const imagePreviewVisible = ref(false)
const currentImageUrl = ref('')
const showLatexHelp = ref(false)
const showUsagePopover = ref(false)

// 用量查询相关
const loadingUsage = ref(false)
const usageError = ref('')
const usageData = ref<any>(null)

// 检测设备类型
const checkDeviceType = () => {
  const wasMobile = formData.isMobile
  formData.isMobile = window.innerWidth < 768

  // 从移动端切换到非移动端时，自动展开侧边栏
  if (wasMobile && !formData.isMobile) {
    formData.sidebarCollapsed = false
  }
  // 从非移动端切换到移动端时，自动折叠侧边栏
  else if (!wasMobile && formData.isMobile) {
    formData.sidebarCollapsed = true
  }
}

// 更新侧边栏状态
const updateSidebarCollapsed = (collapsed: boolean) => {
  formData.sidebarCollapsed = collapsed
}

// 更新当前对话ID
const updateCurrentDialogId = (id: number | null) => {
  formData.currentDialogId = id
}

// 加载对话
const loadDialog = (dialogId: number) => {
  formData.currentDialogId = dialogId
  // 实际加载逻辑会在ChatContent中处理
}

// 处理模型变化
const handleModelChange = (model: string) => {
  formData.selectedModel = model
}

// 处理设置变化
const handleSettingsChange = (settings: any) => {
  formData.contextCount = settings.contextCount
  formData.maxResponseChars = settings.maxResponseChars
  formData.streamEnabled = settings.streamEnabled
  formData.systemPrompt = settings.systemPrompt
  formData.sendPreference = settings.sendPreference
}

// 处理对话创建
const handleDialogCreated = (dialogId: number) => {
  formData.currentDialogId = dialogId
}

// 刷新历史
const refreshHistory = () => {
  // 触发侧边栏刷新历史
}

// 切换主题
const toggleTheme = () => {
  formData.isDarkTheme = !formData.isDarkTheme
  // 实际的主题切换逻辑
  if (formData.isDarkTheme) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }
}

// 登出
const logout = () => {
  authStore.logout()
  router.push('/login')
  ElMessage.success(t('chat.logoutSuccess'))
}

// 获取用量信息
const fetchUsage = async () => {
  loadingUsage.value = true
  usageError.value = ''

  try {
    const response = await chatAPI.getUsage()
    usageData.value = response.data
  } catch (error: any) {
    console.error('获取用量信息失败:', error)
    usageError.value = error.message || '获取用量信息失败'
    ElMessage.error('获取用量信息失败')
  } finally {
    loadingUsage.value = false
  }
}

// 监听窗口大小变化
const handleResize = () => {
  checkDeviceType()
}

// 组件挂载
onMounted(() => {
  checkDeviceType()
  window.addEventListener('resize', handleResize)

  // 检查认证状态
  if (!authStore.isAuthenticated()) {
    router.push('/login')
  }
})

// 组件卸载
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
@import '@/views/styles/chat.css';

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

.sidebar-toggle-btn {
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

/* 用量弹窗样式 */
.usage-content {
  min-height: 100px;
}

.loading {
  text-align: center;
  padding: 20px;
}

.error {
  color: var(--el-color-danger);
  text-align: center;
  padding: 20px;
}

.usage-data {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.usage-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dashed var(--el-border-color);
}

.usage-item:last-child {
  border-bottom: none;
}

.usage-item.low-balance {
  color: var(--el-color-warning);
}

.label {
  font-weight: 500;
}

.value {
  font-weight: 600;
  text-align: right;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .sidebar-toggle-btn {
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
