<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left-flex">
        <div class="header-title-section">
          <el-button
            class="sidebar-toggle-btn tech-button"
            :icon="formData.sidebarCollapsed ? Expand : Fold"
            circle size="medium"
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
                class="usage-btn tech-button"
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
            class="latex-help-btn tech-button"
          >
            {{ formData.isMobile ? '' : t('chat.latexHelp') }}
          </el-button>

          <!-- 通知按钮 -->
          <div class="notification-button-wrapper">
            <el-button
              :icon="Bell"
              size="small"
              @click="openNotifications"
              class="notification-btn tech-button"
            >
              {{ formData.isMobile ? '' : t('chat.notifications') }}
            </el-button>
            <span v-if="hasNewNotifications" class="notification-dot" />
          </div>
          <!-- TODO(human): 优化移动端按钮的布局和样式，考虑添加更多针对移动设备的适配样式 -->
        </div>
      </div>
      <div class="header-right">
        <!-- 语言切换按钮 -->
        <el-button
          @click="toggleLanguage"
          class="logout-btn tech-button"
          :class="{'rounded-full': true}"
          size="medium"
          :icon="SwitchFilled"
        >
          {{ formData.isMobile ? '' : (currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese')) }}
        </el-button>

        <el-button @click="toggleTheme" class="theme-toggle-btn tech-button" :icon="formData.isDarkTheme ? Sunny : Moon">
          {{ formData.isMobile ? '' : (formData.isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme')) }}
        </el-button>

        <!-- 用户菜单 -->
        <el-dropdown class="user-menu">
          <el-button class="user-btn tech-button" type="default">
            <span class="user-name">{{ authStore.user }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="authStore.isAdmin()" @click="goToAdmin" :icon="Setting">
                {{ t('chat.adminPanel') }}
              </el-dropdown-item>
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

      <div class="chat-workspace">
        <div class="chat-tabs-wrap">
          <el-tabs v-model="activeTabKey" type="card" class="chat-tabs" @tab-remove="removeChatTab">
            <el-tab-pane
              v-for="tab in chatTabs"
              :key="tab.key"
              :name="tab.key"
              :closable="chatTabs.length > 1 && !tab.loading"
            >
              <template #label>
                <span class="chat-tab-label">
                  <el-icon v-if="tab.loading" class="is-loading chat-tab-loading"><Loading /></el-icon>
                  <span class="chat-tab-title">{{ tab.title || '新会话' }}</span>
                  <span v-if="tab.unread && !tab.loading" class="chat-tab-unread-dot"></span>
                </span>
              </template>
            </el-tab-pane>
          </el-tabs>
        </div>

        <!-- 聊天内容区域 -->
        <ChatContent
          :session-key="activeTabKey"
          @refresh-history="refreshHistory"
          @loading-change="handleTabLoadingChange"
          @session-dialog-created="handleSessionDialogCreated"
          v-model="formData"
        />
      </div>
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
      <p>{{ t('chat.useDollarSign') }} <code>$$...$$</code> {{ t('chat.surroundFormula') }} <code>$$y = X\beta + \epsilon$$</code></p>

      <h4>{{ t('chat.examples') }}</h4>
      <div class="example-formulas">
        <p><strong>{{ t('chat.quadraticFormula') }}：</strong> $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$</p>
        <p><strong>{{ t('chat.eulerIdentity') }} ：</strong> $$e^{i\pi} + 1 = 0$$</p>
        <p><strong>{{ t('chat.matrix') }}：</strong> $A = \begin{bmatrix} a & b \\ c & d \end{bmatrix}$</p>
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
            :isDarkTheme="formData.isDarkTheme"
            isModal
            :notifications="notifications"
            :loading="notificationsLoading"
            @close="closeNotifications"
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
import { useNotifications } from '@/composables/useNotifications'
import { useThemeManager } from '@/composables/useThemeManager'

// 国际化和认证
const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager, setThemeManually } = useThemeManager()

type ChatTab = {
  key: string
  title: string
  dialogId: number | null
  loading: boolean
  unread: boolean
  selectedModel: string
  selectedModelType: number
  providerValue: string
  modelValue: string
  currentModelDesc: string
}

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

const { notifications, notificationsLoading, hasNewNotifications, fetchNotifications, markNotificationsRead } = useNotifications()
const getModelStateByModelName = (modelName?: string) => {
  const modelKey = (modelName || '').trim()
  const fallback = {
    selectedModel: formData.selectedModel || '',
    selectedModelType: Number(formData.selectedModelType || 1),
    providerValue: formData.providerValue || '',
    modelValue: formData.modelValue || formData.selectedModel || '',
    currentModelDesc: formData.currentModelDesc || '',
  }
  if (!modelKey) {
    return fallback
  }
  const modelInfo = formData.models.find((item) => item.value === modelKey || item.label === modelKey)
  if (!modelInfo) {
    return {
      ...fallback,
      selectedModel: modelKey,
      modelValue: modelKey,
    }
  }
  return {
    selectedModel: modelInfo.value,
    selectedModelType: Number(modelInfo.model_type || 1),
    providerValue: modelInfo.group || '',
    modelValue: modelInfo.value,
    currentModelDesc: modelInfo.model_desc || '',
  }
}

const chatTabs = ref<ChatTab[]>([{
  key: `tab_${Date.now()}`,
  title: '',
  dialogId: null,
  loading: false,
  unread: false,
  ...getModelStateByModelName(formData.selectedModel || ''),
}])
const activeTabKey = ref(chatTabs.value[0].key)

const openNotifications = () => {
  showNotificationPanel.value = true
}

const closeNotifications = () => {
  showNotificationPanel.value = false
  markNotificationsRead()
}

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
watch(isDarkTheme, (val) => {
  formData.isDarkTheme = val
}, { immediate: true })

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

const getActiveTab = () => chatTabs.value.find(tab => tab.key === activeTabKey.value)
const isDraftTab = (tab?: ChatTab | null) => !!tab && tab.dialogId === null && !tab.loading

const syncFormDataFromActiveTab = () => {
  const tab = getActiveTab()
  if (!tab) return
  formData.currentDialogId = tab.dialogId
  formData.dialogTitle = tab.title || ''
  formData.selectedModel = tab.selectedModel
  formData.selectedModelType = tab.selectedModelType
  formData.providerValue = tab.providerValue
  formData.modelValue = tab.modelValue
  formData.currentModelDesc = tab.currentModelDesc
}

const createChatTab = (dialogId: number | null = null, title: string = '', modelName?: string) => {
  const modelState = getModelStateByModelName(modelName)
  const tab: ChatTab = {
    key: `tab_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    title,
    dialogId,
    loading: false,
    unread: false,
    ...modelState,
  }
  chatTabs.value.push(tab)
  activeTabKey.value = tab.key
  syncFormDataFromActiveTab()
}

// 加载对话
const loadDialog = (dialogId: number) => {
  const existing = chatTabs.value.find(tab => tab.dialogId === dialogId)
  if (existing) {
    activeTabKey.value = existing.key
    syncFormDataFromActiveTab()
    return
  }
  const historyItem = formData.dialogHistory.find((item: any) => item.id === dialogId)
  const title = historyItem?.dialog_name || `对话 ${dialogId}`
  createChatTab(dialogId, title, historyItem?.modelname || '')
}

// 处理模型变化
const handleModelChange = (model: string) => {
  formData.selectedModel = model
}

// 处理对话创建
const handleDialogCreated = (dialogId: number) => {
  formData.currentDialogId = dialogId
}

const handleTabLoadingChange = (payload: { sessionKey: string, loading: boolean }) => {
  const tab = chatTabs.value.find(item => item.key === payload.sessionKey)
  if (!tab) return
  const wasLoading = tab.loading
  tab.loading = payload.loading
  if (payload.loading) {
    tab.unread = false
    return
  }
  if (wasLoading && payload.sessionKey !== activeTabKey.value) {
    tab.unread = true
  }
}

const handleSessionDialogCreated = (payload: { sessionKey: string, dialogId: number }) => {
  const tab = chatTabs.value.find(item => item.key === payload.sessionKey)
  if (!tab) return
  tab.dialogId = payload.dialogId
  if (payload.sessionKey === activeTabKey.value) {
    formData.currentDialogId = payload.dialogId
  }
}

const removeChatTab = (targetKey: string | number) => {
  const key = String(targetKey)
  const target = chatTabs.value.find(tab => tab.key === key)
  if (!target) return
  if (target.loading) {
    ElMessage.warning('会话进行中，暂不支持关闭该标签')
    return
  }
  const index = chatTabs.value.findIndex(tab => tab.key === key)
  if (index < 0) return
  chatTabs.value.splice(index, 1)
  if (chatTabs.value.length === 0) {
    createChatTab(null, '')
    return
  }
  if (activeTabKey.value === key) {
    const next = chatTabs.value[index] || chatTabs.value[index - 1] || chatTabs.value[0]
    activeTabKey.value = next.key
  }
  syncFormDataFromActiveTab()
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
    ElMessage.error(t('chat.loadHistoryFailed'))
  } finally {
    formData.loadingHistory = false
  }
}

// 切换主题
const toggleTheme = () => {
  setThemeManually(!isDarkTheme.value)
}

// 登出
const logout = () => {
  authStore.logout()
  router.push('/login')
  ElMessage.success(t('chat.logoutSuccess'))
}

// 跳转到管理面板
const goToAdmin = () => {
  router.push('/admin')
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
  closeNotifications()
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
  const activeTab = getActiveTab()
  if (isDraftTab(activeTab)) {
    activeTab!.title = ''
    syncFormDataFromActiveTab()
    return
  }

  const rightmostTab = chatTabs.value[chatTabs.value.length - 1]
  if (isDraftTab(rightmostTab)) {
    activeTabKey.value = rightmostTab!.key
    rightmostTab!.title = ''
    syncFormDataFromActiveTab()
    return
  }

  createChatTab(null, '')
}

// 组件挂载
onMounted(() => {
  // 启动全局主题管理，统一自动/手动主题切换逻辑
  initThemeManager()

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

  fetchNotifications()
})

// 组件卸载
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

watch(activeTabKey, () => {
  const tab = getActiveTab()
  if (tab) {
    tab.unread = false
  }
  syncFormDataFromActiveTab()
})

watch(() => formData.currentDialogId, (newId) => {
  const activeTab = getActiveTab()
  if (!activeTab) return

  if (newId === null || newId === undefined) {
    activeTab.dialogId = null
    return
  }

  const targetDialogId = Number(newId)
  if (!Number.isFinite(targetDialogId) || targetDialogId <= 0) {
    return
  }

  if (activeTab.dialogId === targetDialogId) {
    return
  }

  const existingTab = chatTabs.value.find(tab => tab.dialogId === targetDialogId)
  if (existingTab) {
    if (existingTab.key !== activeTabKey.value) {
      activeTabKey.value = existingTab.key
      syncFormDataFromActiveTab()
    }
    return
  }

  const historyItem = formData.dialogHistory.find((item: any) => item.id === targetDialogId)
  const title = historyItem?.dialog_name || ''
  createChatTab(targetDialogId, title, historyItem?.modelname || '')
})

watch(
  () => [formData.selectedModel, formData.selectedModelType, formData.providerValue, formData.modelValue, formData.currentModelDesc],
  ([selectedModel, selectedModelType, providerValue, modelValue, currentModelDesc]) => {
    const tab = getActiveTab()
    if (!tab) return
    tab.selectedModel = selectedModel || ''
    tab.selectedModelType = Number(selectedModelType || 1)
    tab.providerValue = providerValue || ''
    tab.modelValue = modelValue || ''
    tab.currentModelDesc = currentModelDesc || ''
  }
)

watch(() => formData.dialogTitle, (newTitle) => {
  const tab = getActiveTab()
  if (!tab) return
  tab.title = (newTitle || '').trim()
})
</script>

<style>
/* 导入科技感字体 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@100..900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700&family=Exo+2:wght@300;400;500;600&display=swap');
@import '@/styles/chat.css';

/* 修复消息容器滚动问题 */
@import '@/styles/message-container-fix.css';

/* 为截图功能添加备用字体，避免Google Fonts加载问题 */
.messages-container *,
.message-text * {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

/* 仅在非截图模式下应用Google Fonts */
body:not(.screenshot-mode) .header-title-section h2 {
  font-family: "Noto Sans SC", sans-serif !important;
}

body:not(.screenshot-mode) .user-name {
  font-family: 'Exo 2', sans-serif !important;
}

/* 科技感动画关键帧 */
@keyframes techGlow {
  0% {
    box-shadow: 0 0 5px rgba(59, 130, 246, 0.5),
                inset 0 0 5px rgba(59, 130, 246, 0.1);
  }
  50% {
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.8),
                inset 0 0 10px rgba(59, 130, 246, 0.3);
  }
  100% {
    box-shadow: 0 0 5px rgba(59, 130, 246, 0.5),
                inset 0 0 5px rgba(59, 130, 246, 0.1);
  }
}

@keyframes techPulse {
  0% {
    transform: scale(1);
    filter: brightness(1);
  }
  50% {
    transform: scale(1.05);
    filter: brightness(1.2);
  }
  100% {
    transform: scale(1);
    filter: brightness(1);
  }
}

@keyframes techBorder {
  0% {
    border-color: rgba(59, 130, 246, 0.3);
  }
  50% {
    border-color: rgba(59, 130, 246, 0.8);
  }
  100% {
    border-color: rgba(59, 130, 246, 0.3);
  }
}

@keyframes techRipple {
  0% {
    transform: scale(0);
    opacity: 1;
  }
  100% {
    transform: scale(4);
    opacity: 0;
  }
}

@keyframes techScan {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

@keyframes techFlicker {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* 左上角标题样式优化 */
.header-title-section h2 {
  font-family: "Noto Sans SC", sans-serif;
  font-weight: 600;
  font-size: 24px;
  background: linear-gradient(135deg, #f63be7 0%, #1d4ed8 50% , #5c79f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: 0 0 5px rgba(59, 130, 246, 0.5);
  letter-spacing: 1px;
  position: relative;
}

.header-title-section h2::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(45deg, rgba(59, 130, 246, 0.3) 0%, rgba(139, 92, 246, 0.3) 100%);
  filter: blur(15px);
  z-index: -1;
  animation: techGlow 3s ease-in-out infinite;
}

.chat-workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-tabs-wrap {
  position: relative;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--el-border-color-light, #d9e0ef);
  box-shadow: inset 0 -1px 0 rgba(148, 163, 184, 0.2);
  background: transparent;
}

:deep(.dark-theme) .chat-tabs-wrap,
:deep(body.dark) .chat-tabs-wrap {
  background: transparent;
  border-bottom-color: rgba(148, 163, 184, 0.42);
  box-shadow: inset 0 -1px 0 rgba(148, 163, 184, 0.16);
}

.chat-tabs-wrap :deep(.el-tabs__header) {
  margin: 0;
}

.chat-tabs-wrap :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.chat-tabs-wrap :deep(.el-tabs__nav) {
  border: none !important;
  background: transparent !important;
}

.chat-tabs-wrap :deep(.el-tabs__item) {
  height: 36px;
  line-height: 36px;
  border: 1.5px solid rgba(99, 102, 241, 0.62) !important;
  border-radius: 12px 12px 0 0;
  margin-right: 8px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.34);
  box-shadow:
    0 6px 20px rgba(15, 23, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.46),
    inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  transition: all 0.2s ease;
}

.chat-tabs-wrap :deep(.el-tabs__item:hover) {
  color: #0f172a;
  border-color: rgba(37, 99, 235, 0.86) !important;
  transform: translateY(-1px);
  box-shadow:
    0 8px 24px rgba(37, 99, 235, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.56),
    inset 0 0 0 1px rgba(59, 130, 246, 0.22);
}

.chat-tabs-wrap :deep(.el-tabs__item.is-active) {
  color: #0f172a;
  border-color: rgba(37, 99, 235, 1) !important;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.9), rgba(219, 234, 254, 0.65));
  box-shadow:
    0 10px 26px rgba(37, 99, 235, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    inset 0 0 0 1px rgba(59, 130, 246, 0.3);
  animation: activeTabGlowLight 2.6s ease-in-out infinite;
}

:deep(.dark-theme) .chat-tabs-wrap :deep(.el-tabs__item),
:deep(body.dark) .chat-tabs-wrap :deep(.el-tabs__item) {
  color: #e2e8f0;
  background: linear-gradient(135deg, rgba(67, 56, 84, 0.58), rgba(47, 54, 72, 0.62));
  border: 1.5px solid rgba(192, 132, 252, 0.72) !important;
  box-shadow:
    0 6px 20px rgba(2, 6, 23, 0.34),
    inset 0 1px 0 rgba(196, 181, 253, 0.16),
    inset 0 0 0 1px rgba(167, 139, 250, 0.2);
}

:deep(.dark-theme) .chat-tabs-wrap :deep(.el-tabs__item:hover),
:deep(body.dark) .chat-tabs-wrap :deep(.el-tabs__item:hover) {
  color: #f8fafc;
  border-color: rgba(216, 180, 254, 0.92) !important;
  box-shadow: 0 8px 22px rgba(67, 56, 202, 0.24), inset 0 1px 0 rgba(221, 214, 254, 0.18);
}

:deep(.dark-theme) .chat-tabs-wrap :deep(.el-tabs__item.is-active),
:deep(body.dark) .chat-tabs-wrap :deep(.el-tabs__item.is-active) {
  color: #f8fafc;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.46), rgba(76, 82, 118, 0.7));
  border-color: rgba(233, 213, 255, 1) !important;
  box-shadow: 0 10px 28px rgba(88, 28, 135, 0.36), inset 0 1px 0 rgba(243, 232, 255, 0.2);
  animation: activeTabGlowDark 2.6s ease-in-out infinite;
}

@keyframes activeTabGlowLight {
  0%, 100% {
    box-shadow:
      0 10px 26px rgba(37, 99, 235, 0.22),
      inset 0 1px 0 rgba(255, 255, 255, 0.82),
      inset 0 0 0 1px rgba(59, 130, 246, 0.28);
  }
  50% {
    box-shadow:
      0 12px 30px rgba(37, 99, 235, 0.34),
      0 0 0 1px rgba(59, 130, 246, 0.34),
      inset 0 1px 0 rgba(255, 255, 255, 0.9),
      inset 0 0 0 1px rgba(59, 130, 246, 0.42);
  }
}

@keyframes activeTabGlowDark {
  0%, 100% {
    box-shadow:
      0 10px 28px rgba(88, 28, 135, 0.34),
      inset 0 1px 0 rgba(243, 232, 255, 0.2),
      inset 0 0 0 1px rgba(216, 180, 254, 0.22);
  }
  50% {
    box-shadow:
      0 12px 32px rgba(126, 34, 206, 0.44),
      0 0 0 1px rgba(233, 213, 255, 0.36),
      inset 0 1px 0 rgba(243, 232, 255, 0.26),
      inset 0 0 0 1px rgba(233, 213, 255, 0.36);
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat-tabs-wrap :deep(.el-tabs__item.is-active),
  :deep(.dark-theme) .chat-tabs-wrap :deep(.el-tabs__item.is-active),
  :deep(body.dark) .chat-tabs-wrap :deep(.el-tabs__item.is-active) {
    animation: none !important;
  }
}

.chat-tab-label {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 260px;
  min-width: 0;
}

.chat-tab-title {
  display: inline-block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-tab-loading {
  font-size: 12px;
  color: #2563eb;
}

.chat-tab-unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.78);
  flex-shrink: 0;
}

:deep(.dark-theme) .chat-tab-unread-dot,
:deep(body.dark) .chat-tab-unread-dot {
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.85);
}

@media (max-width: 768px) {
  .chat-tabs-wrap {
    padding: 8px 8px 6px;
  }

  .chat-tab-label {
    max-width: 170px;
  }

  .chat-tabs-wrap :deep(.el-tabs__item) {
    margin-right: 6px;
    padding: 0 10px;
    height: 32px;
    line-height: 32px;
    border-radius: 10px 10px 0 0;
  }
}

/* 科技感按钮基础样式 */
.tech-button {
  position: relative;
  overflow: hidden;
  font-family: "Noto Sans SC", sans-serif;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid transparent;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
  backdrop-filter: blur(10px);
  cursor: pointer;
}

/* 扫描光线效果 */
.tech-button::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 246, 0.6), transparent);
  transition: left 0.6s;
  pointer-events: none;
}

.tech-button:hover::after {
  left: 100%;
}

/* 波纹效果容器 */
.tech-button {
  overflow: hidden;
}

/* 科技感边框动画 */
.tech-button::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  background: linear-gradient(45deg, #3b82f6, #8b5cf6, #3b82f6);
  border-radius: inherit;
  opacity: 0;
  z-index: -1;
  transition: opacity 0.3s ease;
}

.tech-button:hover::before {
  opacity: 1;
  animation: techBorder 2s linear infinite;
}

.tech-button:hover {
  animation: techPulse 0.6s ease-in-out;
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.6);
  transform: translateY(-2px);
}

.tech-button:active {
  transform: translateY(0);
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.4);
}

/* 点击波纹效果 */
.tech-button.ripple-effect::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  transform: scale(0);
  animation: techRipple 0.6s ease-out;
  pointer-events: none;
}

/* 科技感按钮基础样式 - 保持原始背景色 */
.tech-button {
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid transparent;
  backdrop-filter: blur(10px);
  cursor: pointer;
}

/* 扫描光线效果 */
.tech-button::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 246, 0.4), transparent);
  transition: left 0.6s;
  pointer-events: none;
}

.tech-button:hover::after {
  left: 100%;
}

/* 科技感边框动画 */
.tech-button::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  background: linear-gradient(45deg, #3b82f6, #8b5cf6, #3b82f6);
  border-radius: inherit;
  opacity: 0;
  z-index: -1;
  transition: opacity 0.3s ease;
}

.tech-button:hover::before {
  opacity: 1;
  animation: techBorder 2s linear infinite;
}

.tech-button:hover {
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
  transform: translateY(-1px);
}

.tech-button:active {
  transform: translateY(0);
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
}

/* 侧边栏切换按钮 */
.sidebar-toggle-btn {
  animation: techBorder 4s ease-in-out infinite;
  border-radius: 50% !important;
}

/* 语言切换按钮 */
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

/* 主题切换按钮 */
.theme-toggle-btn {
  /* 保持原始背景色 */
}

/* 用户菜单按钮 */
.user-btn {
  padding: 8px 12px;
  border-radius: 20px;
  background-color: var(--el-button-bg-color, #f0f0f0);
  border: 1px solid var(--el-border-color, #dcdfe6);
}

.user-name {
  margin-right: 6px;
  font-weight: 500;
  font-family: 'Exo 2', sans-serif;
}

/* 按钮图标动画 */
.tech-button .el-icon {
  transition: all 0.3s ease;
}

.tech-button:hover .el-icon {
  transform: scale(1.2) rotate(5deg);
  filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.8));
}

/* 用户菜单下拉动画 */
.el-dropdown-menu {
  animation: techFadeIn 0.3s ease-out;
}

@keyframes techFadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.el-dropdown-item {
  transition: all 0.2s ease;
}

.el-dropdown-item:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
  transform: translateX(5px);
}

/* 暗色主题下的效果 - 简洁风格 */
.dark-theme .tech-button:hover {
  border-color: rgba(147, 197, 253, 0.6);
  box-shadow: 0 2px 8px rgba(147, 197, 253, 0.2);
}

.dark-theme .header-title-section h2 {
  background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 50%, #a78bfa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .header-title-section h2 {
    font-size: 20px;
  }
  
  .tech-button {
    padding: 6px 10px;
    font-size: 12px;
  }
  
  .language-toggle-btn {
    width: 32px;
    height: 32px;
    min-height: 32px;
  }
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
