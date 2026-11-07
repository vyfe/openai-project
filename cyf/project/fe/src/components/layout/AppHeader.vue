<template>
  <header class="app-header">
    <div class="app-header__left">
      <slot name="left" />

      <!-- 有工作台入口时才做成可点击；普通用户只展示标识 -->
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
              :class="{ 'app-workspace-menu__item--current': item.key === variant }"
            >
              <span class="app-workspace-menu__label">{{ item.label }}</span>
              <el-icon v-if="item.key === variant" class="app-workspace-menu__check"><Select /></el-icon>
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
  </header>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowDown, DataBoard, Headset, Moon, Select, Setting, Sunny, SwitchButton, SwitchFilled } from '@element-plus/icons-vue'
import UserSettings from '@/components/chat/UserSettings.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeManager } from '@/composables/useThemeManager'

type WorkspaceKey = 'admin' | 'quant' | 'studio'

const props = withDefaults(defineProps<{
  title: string
  logoIcon: Component
  variant?: WorkspaceKey | 'chat'
}>(), {
  variant: 'chat',
})

const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager, setThemeManually } = useThemeManager()

const currentLang = ref(locale.value)
const showUserSettings = ref(false)
const workspaceMenuOpen = ref(false)

// 工作台入口的可见条件与原用户下拉菜单一致：仅 admin 可见。
const workspaceItems = computed(() => {
  if (!authStore.isAdmin()) return []
  return [
    { key: 'admin' as WorkspaceKey, label: t('chat.adminPanel'), icon: Setting, to: '/admin' },
    { key: 'quant' as WorkspaceKey, label: t('chat.quantWorkbench'), icon: DataBoard, to: '/quant' },
    { key: 'studio' as WorkspaceKey, label: t('chat.studioWorkbench'), icon: Headset, to: '/studio' },
  ]
})

const handleWorkspaceCommand = (command: string | number | object) => {
  const target = workspaceItems.value.find(item => item.key === command)
  if (!target) return
  if (target.key === props.variant) return
  router.push(target.to)
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

initThemeManager()
</script>

<style>
@import '@/styles/app-header.css';
</style>
