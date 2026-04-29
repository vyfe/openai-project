<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header chat-header-v2">
      <div class="header-left-v2">
        <el-button
          class="sidebar-toggle-btn header-icon-btn"
          :icon="formData.sidebarCollapsed ? Expand : Fold"
          circle
          size="default"
          @click="formData.sidebarCollapsed = !formData.sidebarCollapsed"
        />
        <h2>{{ t('chat.title') }}</h2>
      </div>

      <div class="header-center-v2">
        <!-- 用量查询弹窗 -->
        <el-popover
          placement="bottom"
          :width="300"
          trigger="click"
          v-model:visible="showUsagePopover"
        >
          <template #reference>
            <el-button class="header-icon-btn" :icon="Coin" circle @click="fetchUsage" />
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

        <el-button :icon="Document" circle @click="showLatexHelp = true" class="header-icon-btn" />

        <div class="notification-button-wrapper">
          <el-button :icon="Bell" circle @click="openNotifications" class="header-icon-btn" />
          <span v-if="hasNewNotifications" class="notification-dot" />
        </div>
      </div>

      <div class="header-right header-right-v2">
        <!-- 语言切换按钮 -->
        <el-button
          @click="toggleLanguage"
          class="header-action-btn"
          :icon="SwitchFilled"
        >
          {{ formData.isMobile ? '' : (currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese')) }}
        </el-button>

        <el-button @click="toggleTheme" class="header-action-btn" :icon="formData.isDarkTheme ? Sunny : Moon">
          {{ formData.isMobile ? '' : (formData.isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme')) }}
        </el-button>

        <!-- 用户菜单 -->
        <el-dropdown class="user-menu">
          <el-button class="user-btn user-btn-v2" type="default">
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
@import '@/styles/chat.css';
@import '@/styles/message-container-fix.css';

/* =========================
   Round 2: calm header/layout
   ========================= */
.chat-container {
  background: var(--bg-app-gradient);
}

.chat-header.chat-header-v2 {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto minmax(280px, auto);
  align-items: center;
  gap: var(--sp-3);
  padding: 10px 16px;
  background: var(--overlay-1);
  border-bottom: 1px solid var(--line-1);
  box-shadow: none;
}

.header-left-v2 {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-width: 0;
}

.header-left-v2 h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-1);
  letter-spacing: 0;
  background: none;
  -webkit-text-fill-color: initial;
  text-shadow: none;
}

.header-left-v2 h2::after {
  display: none;
}

.header-center-v2 {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.header-right-v2 {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--sp-2);
}

.header-icon-btn,
.header-action-btn,
.user-btn-v2 {
  border-radius: 999px !important;
  border: 1px solid var(--line-1) !important;
  background: var(--bg-1) !important;
  color: var(--text-1) !important;
  box-shadow: none !important;
  transition: background-color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
}

.header-icon-btn {
  width: 34px;
  height: 34px;
  padding: 0 !important;
}

.header-action-btn {
  padding: 8px 12px;
}

.header-icon-btn:hover,
.header-action-btn:hover,
.user-btn-v2:hover {
  background: var(--bg-2) !important;
  border-color: var(--line-1) !important;
  transform: none !important;
}

.notification-button-wrapper {
  position: relative;
}

.notification-dot {
  box-shadow: 0 0 0 2px var(--bg-1);
}

.chat-main {
  background: transparent;
}

.chat-workspace {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
}

.chat-tabs-wrap {
  padding: 8px 12px 6px;
  border-bottom: 1px solid var(--line-1);
  box-shadow: none;
}

.chat-tabs-wrap :deep(.el-tabs__item) {
  height: 32px;
  line-height: 32px;
  border: 1px solid var(--line-1) !important;
  border-radius: 10px 10px 0 0;
  margin-right: 6px;
  padding: 0 12px;
  color: var(--text-2);
  background: var(--bg-1);
  box-shadow: none;
}

.chat-tabs-wrap :deep(.el-tabs__item:hover) {
  color: var(--text-1);
  border-color: var(--line-1) !important;
  background: var(--bg-2);
  transform: none;
  box-shadow: none;
}

.chat-tabs-wrap :deep(.el-tabs__item.is-active) {
  color: var(--text-1);
  border-color: var(--line-1) !important;
  background: var(--bg-1);
  box-shadow: none;
  animation: none;
}

.chat-tab-loading {
  color: var(--text-2);
}

body.dark-theme .chat-header.chat-header-v2 {
  border-bottom-color: var(--line-1);
}

body.dark-theme .header-icon-btn,
body.dark-theme .header-action-btn,
body.dark-theme .user-btn-v2,
body.dark-theme .chat-tabs-wrap :deep(.el-tabs__item),
body.dark-theme .chat-tabs-wrap :deep(.el-tabs__item.is-active) {
  background: var(--bg-1) !important;
  color: var(--text-1) !important;
  border-color: var(--line-1) !important;
}

body.dark-theme .header-icon-btn:hover,
body.dark-theme .header-action-btn:hover,
body.dark-theme .user-btn-v2:hover,
body.dark-theme .chat-tabs-wrap :deep(.el-tabs__item:hover) {
  background: var(--bg-2) !important;
}

@media (max-width: 1024px) {
  .chat-header.chat-header-v2 {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      "left right"
      "center center";
  }

  .header-left-v2 {
    grid-area: left;
  }

  .header-right-v2 {
    grid-area: right;
  }

  .header-center-v2 {
    grid-area: center;
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .chat-header.chat-header-v2 {
    grid-template-columns: 1fr auto;
    gap: var(--sp-2);
    padding: 8px 10px;
  }

  .header-left-v2 h2 {
    font-size: 16px;
  }

  .header-action-btn {
    padding: 6px 10px;
    font-size: 12px;
  }

  .chat-tabs-wrap {
    padding: 6px 8px 4px;
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
</style>
