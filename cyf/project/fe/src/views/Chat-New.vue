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
                {{ t('chat.loadingUsageData') }}
              </div>
              <div v-else-if="usageError" class="error">
                {{ usageError }}
              </div>
              <div v-else class="usage-data">
                <div class="usage-item">
                  <span class="label">{{ t('chat.totalUsage') }}：</span>
                  <span class="value">{{ usageData?.total_usage }} {{ t('chat.yuan') }}</span>
                </div>
                <div class="usage-item">
                  <span class="label">{{ t('chat.quota') }}：</span>
                  <span class="value">{{ usageData?.quota > 10000 ? '-' : usageData?.quota }} {{ t('chat.yuan') }}</span>
                </div>
                <div class="usage-item" :class="{ 'low-balance': usageData?.remaining < 10 }">
                  <span class="label">{{ t('chat.remainingQuota') }}：</span>
                  <span class="value">{{ usageData?.remaining > 10000 ? '-' : usageData?.remaining }} {{ t('chat.yuan') }}</span>
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
            {{ formData.isMobile ? '' : t('chat.notifications') }}
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
          size="small"
          :icon="SwitchFilled"
        >
          {{ formData.isMobile ? '' : (currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese')) }}
        </el-button>

        <el-button @click="toggleTheme" class="theme-toggle-btn" :icon="formData.isDarkTheme ? Sunny : Moon">
          {{ formData.isMobile ? '' : (formData.isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme')) }}
        </el-button>

        <!-- 用户菜单 -->
        <el-dropdown class="user-menu">
          <el-button class="user-btn" type="default">
            <span class="user-name">{{ authStore.user }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="showUserSettings = true" :icon="Setting">
                {{ t('chat.userSettings') }}
              </el-dropdown-item>
              <el-dropdown-item @click="logout" :icon="SwitchButton">
                {{ t('chat.logout') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
        :selected-model-type="formData.selectedModelType"
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
      <h2>{{ t('chat.professionalOutputHelp') }}</h2>
      <h3>{{ t('chat.howToUseLatex') }}</h3>
      <p>{{ t('chat.useSyntaxBelow') }}</p>

      <h4>{{ t('chat.inlineFormula') }}</h4>
      <p>{{ t('chat.useDollarSign') }} <code>$...$</code> {{ t('chat.surroundFormula') }} <code>$E=mc^2$</code></p>

      <h4>{{ t('chat.standaloneFormula') }}</h4>
      <p>{{ t('chat.useDollarSign') }} <code>$$...$$</code> {{ t('chat.surroundFormula') }} <code>$$y = X\\beta + \\epsilon$$</code></p>

      <h4>{{ t('chat.examples') }}</h4>
      <div class="example-formulas">
        <p><strong>{{ t('chat.quadraticFormula') }}：</strong> $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$</p>
        <p><strong>{{ t('chat.eulerIdentity') }} ：</strong> $$e^{i\\pi} + 1 = 0$$</p>
        <p><strong>{{ t('chat.matrix') }}：</strong> $A = \\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$</p>
      </div>

      <p>{{ t('chat.formulaWillRender') }}</p>
    </div>
    </el-dialog>

    <!-- 通知模态框 -->
    <Teleport to="body">
      <div
        v-if="showNotificationPanel"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        @click="handleNotificationBackdropClick"
      >
        <div
          class="relative"
          @click.stop
        >
          <NotificationPanel
            isModal
            @close="showNotificationPanel = false"
          />
        </div>
      </div>
    </Teleport>

    <!-- 用户设置弹窗 -->
    <UserSettings
      v-model="showUserSettings"
      @password-updated="handlePasswordUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Expand, Fold, Coin, Document, Loading, SwitchButton, Sunny, Moon, SwitchFilled, Bell, ArrowDown, Setting } from '@element-plus/icons-vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ChatContent from '../components/chat/ChatContent.vue'
import UserSettings from '../components/chat/UserSettings.vue'
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
  selectedModelType: parseInt(localStorage.getItem('selectedModelType') || '1'),
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
  models: [] as Array<{ group: string, label: string, value: string, recommend?: boolean, model_desc?: string }>,
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
  rolePresets: [] as Array<{ id: string, name: string, prompt: string }>,
  activeRoleId: localStorage.getItem('activeRoleId') || 'default',
})

// 添加语言切换相关的响应式变量
const currentLang = ref(locale.value)
const showLatexHelp = ref(false)
const showUsagePopover = ref(false)
const showNotificationPanel = ref(false)
const showUserSettings = ref(false)

// 用量查询相关
const loadingUsage = ref(false)
const usageError = ref('')
const usageData = ref<any>(null)

// 持久化监听器（统一在父组件管理）
watch(() => formData.contextCount, (val) => localStorage.setItem('contextCount', val.toString()))
watch(() => formData.maxResponseChars, (val) => localStorage.setItem('maxResponseChars', val.toString()))
watch(() => formData.sidebarCollapsed, (val) => localStorage.setItem('sidebarCollapsed', JSON.stringify(val)))
watch(() => formData.selectedModel, (val) => localStorage.setItem('selectedModel', val))
watch(() => formData.selectedModelType, (val) => localStorage.setItem('selectedModelType', val.toString()))
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
    ElMessage.warning(t('chat.pleaseLoginFirst'))
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
    console.error(t('chat.loadHistoryError'), error)
    ElMessage.error(t('chat.loadHistoryFailed'))
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

// 处理密码更新后的行为
const handlePasswordUpdated = () => {
  // 密码更新成功后，让用户退出登录
  setTimeout(() => {
    logout()
  }, 1000) // 给用户一点时间看到成功的消息
}

// 处理点击通知面板外部区域关闭面板
const handleNotificationBackdropClick = () => {
  showNotificationPanel.value = false
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
    ElMessage.error(t('chat.fetchUsageFailed'))
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

  // 设置角色预设
  formData.rolePresets = [
    { id: 'default', name: t('chat.defaultRole'), prompt: '' },
    { id: 'translator', name: t('chat.translatorRole'), prompt: t('chat.translatorPrompt') },
    { id: 'writer', name: t('chat.writerRole'), prompt: t('chat.writerPrompt') },
  ]

  // 加载本地存储的自定义角色并合并
  const savedCustomRoles = localStorage.getItem('customRoles')
  if (savedCustomRoles) {
    try {
      const customRoles = JSON.parse(savedCustomRoles)
      if (Array.isArray(customRoles)) {
        // 确保自定义角色不与预设角色冲突
        const existingIds = new Set(formData.rolePresets.map(role => role.id))
        const uniqueCustomRoles = customRoles.filter(role => !existingIds.has(role.id))
        formData.rolePresets.push(...uniqueCustomRoles)
      }
    } catch (e) {
      console.error('加载本地自定义角色失败:', e)
    }
  }

  // 设置活动角色
  const savedActiveRoleId = localStorage.getItem('activeRoleId') || 'default'
  if (savedActiveRoleId) {
    formData.activeRoleId = savedActiveRoleId

    // 如果活动角色是预设的，恢复相应的提示词
    const activeRole = formData.rolePresets.find(role => role.id === savedActiveRoleId)
    if (activeRole) {
      formData.systemPrompt = activeRole.prompt
    }
  }
})

// 组件卸载
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style>
@import '@/styles/chat.css';

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

/* 用户菜单样式 */
.user-menu {
  margin-left: 10px;
}

.user-btn {
  padding: 8px 12px;
  border-radius: 20px;
  background-color: var(--el-button-bg-color, #f0f0f0);
  border: 1px solid var(--el-border-color, #dcdfe6);
}

.user-name {
  margin-right: 6px;
  font-weight: 500;
}

/* 为移动端调整样式 */
@media (max-width: 768px) {
  .user-menu {
    margin-left: 5px;
  }

  .user-btn {
    padding: 6px 10px;
    font-size: 12px;
  }
}
</style>
