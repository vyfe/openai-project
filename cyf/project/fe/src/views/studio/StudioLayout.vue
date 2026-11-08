<template>
  <div class="studio-page min-h-screen" :class="{ dark: isDarkTheme, 'studio-dark': isDarkTheme }">
    <AppHeader :title="t('chat.studioWorkbench')" :logo-icon="Headset" variant="studio" />

    <div class="studio-shell">
      <div class="studio-workspace">
        <aside class="studio-nav-panel">
          <h2 class="studio-nav-title">功能分区</h2>
          <p class="studio-nav-subtitle">音色复刻、语音合成与音乐创作共用一套 MiniMax 凭据。</p>
          <nav class="studio-nav-list">
            <RouterLink
              v-for="item in navItems"
              :key="item.to"
              :to="item.to"
              class="studio-nav-link"
              :class="{ 'router-link-active': route.path === item.to }"
            >
              <span class="studio-nav-link__icon">
                <el-icon><component :is="item.icon" /></el-icon>
              </span>
              <span>{{ item.label }}</span>
            </RouterLink>
          </nav>
        </aside>

        <section class="studio-content-panel">
          <RouterView />
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { Headset, Microphone } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useThemeManager } from '@/composables/useThemeManager'
import AppHeader from '@/components/layout/AppHeader.vue'
import '@/styles/studio.css'

const { t } = useI18n()
const route = useRoute()
const { isDarkTheme, initThemeManager } = useThemeManager()

const navItems = [
  { label: '音色与语音', to: '/studio/voice', icon: Microphone },
  { label: '音乐创作', to: '/studio/music', icon: Headset }
]

onMounted(() => initThemeManager())
</script>
