<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left-flex">
        <div class="header-title-section">
          <el-button
            class="sidebar-toggle-btn"
            :icon="formData.sidebarCollapsed ? Expand : Fold"
            circle size="small"
            @click="formData.sidebarCollapsed = !formData.sidebarCollapsed"
          />
          <h2>{{ t('chat.title') }}</h2>
        </div>
        <!-- 在移动端显示在标题下方的按钮组 -->
        <div class="header-mobile-buttons md:hidden">
          <el-button size="small" >{{ authStore.user }}</el-button>

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
                {{ formData.isMobile ? '' : t('chat.viewUsage') }}
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
                  <span class="value">{{ usageData?.remaining > 10000 ? '-' : usageData?.remaining }} 元</span>
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
            {{ formData.isMobile ? '' : t('chat.latexHelp') }}
          </el-button>

          <!-- 通知按钮 -->
          <el-button
            :icon="Bell"
            size="small"
            @click="showNotificationPanel = true"
            class="notification-btn"
          >
            {{ formData.isMobile ? '' : '通知' }}
          </el-button>
          <!-- TODO(human): 优化移动端按钮的布局和样式，考虑添加更多针对移动设备的适配样式 -->
        </div>
      </div>
      <div class="header-right">
        <!-- 语言切换按钮 -->
        <el-button
          @click="toggleLanguage"
          class="logout-btn"
          :class="{'rounded-full': true}"
          size="medium"
          :icon="SwitchFilled"
        >
          {{ formData.isMobile ? '' : (currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese')) }}
        </el-button>

        <el-button @click="toggleTheme" class="theme-toggle-btn" :icon="formData.isDarkTheme ? Sunny : Moon">
          {{ formData.isMobile ? '' : (formData.isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme')) }}
        </el-button>
        <el-button @click="logout" class="logout-btn" :icon="SwitchButton">
          {{ formData.isMobile ? '' : t('chat.logout') }}
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
        @clear-session="clearSession"
        @model-change="handleModelChange"
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
      class="mobile-sidebar-mask"
      @click="updateSidebarCollapsed(true)"
    />

    <!-- LaTeX帮助弹窗 -->
    <el-dialog
      v-model="showLatexHelp"
      :title="$t('chat.latexHelp')"
      width="60%"
    >
    <div class="latex-help-content">
      <h2>专业输出帮助</h2>
      <h3>如何在对话中使用 LaTeX 数学公式</h3>
      <p>您可以使用以下语法在对话中插入数学公式：</p>

      <h4>内联公式（行内）</h4>
      <p>使用 <code>$...$</code> 包围公式，例如：<code>$E=mc^2$</code></p>

      <h4>独立公式（居中显示）</h4>
      <p>使用 <code>$$...$$</code> 包围公式，例如：<code>$$y = X\\beta + \\epsilon$$</code></p>

      <h4>示例</h4>
      <div class="example-formulas">
        <p><strong>二次公式：</strong> $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$</p>
        <p><strong>欧拉恒等式：</strong> $$e^{i\\pi} + 1 = 0$$</p>
        <p><strong>矩阵：</strong> $A = \\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$</p>
      </div>

      <p>公式将在消息中自动渲染为美观的数学符号。</p>
    </div>
    </el-dialog>

    <!-- 通知模态框 -->
    <Teleport to="body">
      <div v-if="showNotificationPanel" class="fixed inset-0 bg-transparent flex items-center justify-center z-50 p-4">
        <div class="relative">
          <NotificationPanel
            isModal
            @close="showNotificationPanel = false"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Expand, Fold, Coin, Document, Loading, SwitchButton, Sunny, Moon, SwitchFilled, Bell } from '@element-plus/icons-vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ChatContent from '../components/chat/ChatContent.vue'
import { useAuthStore } from '../stores/auth'
import { chatAPI } from '../services/api'
import NotificationPanel from '../components/NotificationPanel.vue'

// 国际化和认证
const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

// 组件间共享状态
const formData = reactive({
  isDarkTheme: JSON.parse(localStorage.getItem('isDarkTheme') || 'false'),
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
  systemPrompt: localStorage.getItem('systemPrompt') || '',
  sendPreference: localStorage.getItem('sendPreference') || 'ctrl_enter',

  // ===== 新增属性 =====
  // 对话相关
  dialogTitle: '',
  dialogHistory: [] as any[],
  loadingHistory: false,
  isLoading: false,
  fontSize: localStorage.getItem('fontSize') || 'medium', // 字体大小控制
  // 添加状态跟踪用户是否手动滚动离开了底部
  isScrolledToBottom: true,

  // 模型相关
  models: [] as Array<{ label: string, value: string, recommend?: boolean, model_desc?: string }>,
  groupedModels: {} as Record<string, any[]>,
  providers: [] as string[],
  providerValue: '',
  modelValue: '',
  currentModelDesc: '',

  // 角色相关
  enhancedRoleEnabled: JSON.parse(localStorage.getItem('enhancedRoleEnabled') || 'false'),
  enhancedRoleGroups: {} as Record<string, any[]>,
  activeEnhancedGroup: localStorage.getItem('activeEnhancedGroup') || '',
  selectedEnhancedRole: localStorage.getItem('selectedEnhancedRole') || '',
  rolePresets: [
    { id: 'default', name: '默认', prompt: '' },
    { id: 'translator', name: '翻译', prompt: '你是一个专业的翻译助手，擅长中英文互译，注重语义准确和表达流畅。' },
    { id: 'writer', name: '写作', prompt: '你是一个专业的写作助手，擅长文章润色、创意写作和文案编辑。' }
  ] as Array<{ id: string, name: string, prompt: string }>,
  activeRoleId: localStorage.getItem('activeRoleId') || 'default',
})

// 添加语言切换相关的响应式变量
const currentLang = ref(locale.value)
const showLatexHelp = ref(false)
const showUsagePopover = ref(false)
const showNotificationPanel = ref(false)

// 用量查询相关
const loadingUsage = ref(false)
const usageError = ref('')
const usageData = ref<any>(null)

// 持久化监听器（统一在父组件管理）
watch(() => formData.contextCount, (val) => localStorage.setItem('contextCount', val.toString()))
watch(() => formData.maxResponseChars, (val) => localStorage.setItem('maxResponseChars', val.toString()))
watch(() => formData.sidebarCollapsed, (val) => localStorage.setItem('sidebarCollapsed', JSON.stringify(val)))
watch(() => formData.selectedModel, (val) => localStorage.setItem('selectedModel', val))
watch(() => formData.streamEnabled, (val) => localStorage.setItem('streamEnabled', JSON.stringify(val)))
watch(() => formData.systemPrompt, (val) => localStorage.setItem('systemPrompt', val))
watch(() => formData.sendPreference, (val) => localStorage.setItem('sendPreference', val))
watch(() => formData.enhancedRoleEnabled, (val) => localStorage.setItem('enhancedRoleEnabled', JSON.stringify(val)))
watch(() => formData.activeEnhancedGroup, (val) => localStorage.setItem('activeEnhancedGroup', val))
watch(() => formData.selectedEnhancedRole, (val) => localStorage.setItem('selectedEnhancedRole', val))
watch(() => formData.activeRoleId, (val) => localStorage.setItem('activeRoleId', val))
watch(() => formData.fontSize, (val) => localStorage.setItem('fontSize', val))

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

// 处理对话创建
const handleDialogCreated = (dialogId: number) => {
  formData.currentDialogId = dialogId
}

// 刷新历史
const refreshHistory = async () => {
  await loadDialogHistory()
}

// 加载对话历史
const loadDialogHistory = async () => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  formData.loadingHistory = true
  try {
    const response: any = await chatAPI.getDialogHistory()
    if (response && response.content) {
      formData.dialogHistory = response.content
      // ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
    } else {
      formData.dialogHistory = []
      ElMessage.info('暂无历史对话')
    }
  } catch (error: any) {
    console.error('加载对话历史错误:', error)
    ElMessage.error('加载对话历史失败')
  } finally {
    formData.loadingHistory = false
  }
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

// 切换语言
const toggleLanguage = () => {
  const newLocale = currentLang.value === 'zh' ? 'en' : 'zh'
  locale.value = newLocale
  currentLang.value = newLocale
  localStorage.setItem('locale', newLocale)
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

const clearSession = () => {
  formData.currentDialogId = null
}

// 组件挂载
onMounted(() => {
  checkDeviceType()
  window.addEventListener('resize', handleResize)

  // 检查认证状态
  if (!authStore.isAuthenticated()) {
    router.push('/login')
  }

  // 初始化当前语言
  currentLang.value = locale.value
})

// 组件卸载
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style>
@import '@/views/styles/chat.css';

/* 语言切换按钮样式 */
.language-toggle-btn {
  width: 36px;
  height: 36px;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 10px;
  border-radius: 50% !important;
  padding: 0;
}
</style>
