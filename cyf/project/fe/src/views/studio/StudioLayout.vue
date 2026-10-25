<template>
  <div class="studio-page min-h-screen" :class="{ dark: isDarkTheme, 'studio-dark': isDarkTheme }">
    <div class="studio-shell">
      <header class="studio-header">
        <div class="studio-header__left">
          <button class="studio-back-btn" @click="goBack" aria-label="返回聊天">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <div>
            <div class="studio-eyebrow">MINIMAX AUDIO STUDIO</div>
            <h1 class="studio-title">声音工作台</h1>
          </div>
        </div>
        <div class="studio-header__right">
          <el-button class="studio-header-btn" text @click="goAdmin">
            <el-icon><Setting /></el-icon>
            管理台
          </el-button>
          <div class="studio-user-pill">
            <el-icon><Headset /></el-icon>
            <span>{{ authStore.user }}</span>
          </div>
        </div>
      </header>

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
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { Headset, Microphone, Setting } from '@element-plus/icons-vue'
import { useThemeManager } from '@/composables/useThemeManager'
import { useAuthStore } from '@/stores/auth'
import '@/styles/studio.css'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager } = useThemeManager()

const navItems = [
  { label: '音色与语音', to: '/studio/voice', icon: Microphone },
  { label: '音乐创作', to: '/studio/music', icon: Headset }
]

const goBack = () => router.push('/chat')
const goAdmin = () => router.push('/admin')

onMounted(() => initThemeManager())
</script>
