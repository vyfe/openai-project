<template>
  <header class="app-header">
    <div class="app-header__left">
      <slot name="left" />

      <!-- 功能切换：只列出当前账号有权访问的入口 -->
      <el-dropdown
        v-if="workspaceItems.length"
        trigger="click"
        @command="handleWorkspaceCommand"
        @visible-change="workspaceMenuOpen = $event"
      >
        <button
          type="button"
          class="app-logo"
          :class="[`app-logo--${variant}`, { 'app-logo--open': workspaceMenuOpen }]"
          aria-haspopup="menu"
          :aria-expanded="workspaceMenuOpen"
        >
          <span class="app-logo__mark">
            <el-icon><component :is="logoIcon" /></el-icon>
          </span>
          <span class="app-logo__title">{{ title }}</span>
          <el-icon class="app-logo__caret"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu class="app-workspace-menu">
            <el-dropdown-item
              v-for="item in workspaceItems"
              :key="item.key"
              :command="item.key"
              :icon="item.icon"
              :class="{ 'app-workspace-menu__item--current': item.key === currentApp }"
            >
              <span class="app-workspace-menu__label">{{ item.label }}</span>
              <el-icon v-if="item.key === currentApp" class="app-workspace-menu__check"><Select /></el-icon>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <span v-else class="app-logo app-logo--static" :class="`app-logo--${variant}`">
        <span class="app-logo__mark">
          <el-icon><component :is="logoIcon" /></el-icon>
        </span>
        <span class="app-logo__title">{{ title }}</span>
      </span>
    </div>

    <div class="app-header__center">
      <slot name="center" />
    </div>

    <div class="app-header__right">
      <slot name="right" />

      <div class="notification-button-wrapper">
        <el-button
          :icon="Bell"
          circle
          :aria-label="t('chat.notifications')"
          :title="t('chat.notifications')"
          class="app-header__action"
          @click="openNotifications"
        />
        <span v-if="hasNewNotifications" class="notification-dot" />
      </div>

      <el-button @click="toggleLanguage" class="app-header__action" :icon="SwitchFilled">
        <span class="app-header__action-text">{{ currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese') }}</span>
      </el-button>

      <el-button @click="toggleTheme" class="app-header__action" :icon="isDarkTheme ? Sunny : Moon">
        <span class="app-header__action-text">{{ isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme') }}</span>
      </el-button>

      <el-dropdown class="app-user-menu" trigger="click">
        <el-button class="app-user-btn" type="default">
          <span class="app-user-btn__name">{{ authStore.user }}</span>
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

    <UserSettings v-model="showUserSettings" @password-updated="handlePasswordUpdated" />

    <Teleport to="body">
      <div v-if="showNotificationModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="relative">
          <NotificationPanel
            isModal
            :notifications="notifications"
            :loading="notificationsLoading"
            @close="closeNotifications"
          />
        </div>
      </div>
    </Teleport>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowDown, Bell, Moon, Select, Setting, Sunny, SwitchButton, SwitchFilled } from '@element-plus/icons-vue'
import UserSettings from '@/components/chat/UserSettings.vue'
import NotificationPanel from '@/components/NotificationPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeManager } from '@/composables/useThemeManager'
import { useNotifications } from '@/composables/useNotifications'
import { APP_META, APP_ORDER, type AppKey } from '@/auth/apps'
import { defaultRouteFor } from '@/auth/destination'
import { syncCurrentRoles } from '@/auth/sync'

/** 旧 variant 命名 → 功能入口 */
const VARIANT_TO_APP: Record<string, AppKey> = {
  chat: 'chat',
  quant: 'quant',
  studio: 'sound',
  admin: 'admin'
}

const props = withDefaults(defineProps<{
  title: string
  logoIcon: Component
  variant?: string
}>(), {
  variant: 'chat',
})

const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager, setThemeManually } = useThemeManager()
const { notifications, notificationsLoading, hasNewNotifications, fetchNotifications, markNotificationsRead } = useNotifications()

const currentLang = ref(locale.value)
const showUserSettings = ref(false)
const workspaceMenuOpen = ref(false)
const showNotificationModal = ref(false)

const currentApp = computed<AppKey>(() => VARIANT_TO_APP[props.variant] ?? 'chat')

/** 只展示当前账号有权访问的功能入口。 */
const workspaceItems = computed(() =>
  APP_ORDER
    .filter((key) => authStore.canAccessApp(key))
    .map((key) => ({
      key,
      label: t(APP_META[key].labelKey),
      icon: APP_META[key].icon
    }))
)

const handleWorkspaceCommand = async (command: string | number | object) => {
  const key = String(command) as AppKey
  const item = workspaceItems.value.find((entry) => entry.key === key)
  if (!item) return
  if (item.key === currentApp.value) return
  authStore.setLastApp(item.key)
  await router.push(defaultRouteFor(item.key))
}

const openNotifications = () => {
  showNotificationModal.value = true
}

const closeNotifications = () => {
  showNotificationModal.value = false
  markNotificationsRead()
}

const toggleLanguage = () => {
  const nextLocale = currentLang.value === 'zh' ? 'en' : 'zh'
  locale.value = nextLocale
  currentLang.value = nextLocale
  localStorage.setItem('locale', nextLocale)
}

const toggleTheme = () => {
  setThemeManually(!isDarkTheme.value)
}

const logout = () => {
  authStore.logout()
  router.push('/login')
  ElMessage.success(t('chat.logoutSuccess'))
}

const handlePasswordUpdated = () => {
  setTimeout(logout, 1000)
}

watch(locale, (value) => {
  currentLang.value = value
})

onMounted(async () => {
  initThemeManager()
  // 进入工作台先确认服务端授权，再拉取需要登录的通知。
  await syncCurrentRoles()
  fetchNotifications()
})

initThemeManager()
</script>

<style>
@import '@/styles/app-header.css';
</style>
