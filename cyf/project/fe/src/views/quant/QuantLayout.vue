<template>
  <div class="quant-page min-h-screen" :class="{ dark: isDarkTheme, 'quant-dark': isDarkTheme, 'quant-page--overview': isOverview }">
    <AppHeader :title="t('chat.quantWorkbench')" :logo-icon="DataBoard" variant="quant" />

    <div class="quant-shell">
      <section v-if="isOverview" class="quant-summary-grid" aria-label="量化工作台摘要">
        <article v-for="card in summaryCards" :key="card.title" class="quant-summary-card">
          <div class="quant-summary-card__icon">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="quant-summary-card__body">
            <div class="quant-summary-card__title">{{ card.title }}</div>
            <div class="quant-summary-card__value">{{ card.value }}</div>
            <div class="quant-summary-card__hint">{{ card.hint }}</div>
          </div>
        </article>
      </section>

      <main class="quant-main-panel" v-loading="workbench.loading.bootstrap">
        <div class="quant-workspace">
          <aside class="quant-nav-panel">
            <h2 class="quant-nav-title">工作分区</h2>
            <nav class="quant-nav-list">
              <RouterLink
                v-for="item in navItems"
                :key="item.to"
                :to="item.to"
                class="quant-nav-link"
                :class="{ 'router-link-active': route.path === item.to }"
              >
                <span class="quant-nav-link__icon">
                  <el-icon><component :is="item.icon" /></el-icon>
                </span>
                <span>{{ item.label }}</span>
              </RouterLink>
            </nav>
          </aside>

          <section class="quant-content-panel">
            <RouterView />
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, unref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import {
  DataBoard,
  DocumentChecked,
  Histogram,
  MagicStick,
  Promotion,
  RefreshRight,
  Search,
  TrendCharts,
  VideoPlay
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useThemeManager } from '@/composables/useThemeManager'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'
import { useAuthStore } from '@/stores/auth'
import '@/styles/quant-workbench.css'

const { t } = useI18n()
const route = useRoute()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager } = useThemeManager()
const workbench = useQuantWorkbench()
const isOverview = computed(() => route.path === '/quant/overview')
const summaryCards = computed(() => (unref(workbench.dashboardCards) || []).filter((card): card is NonNullable<typeof card> => Boolean(card)))

const allNavItems = [
  { label: '总览', to: '/quant/overview', icon: DataBoard, adminOnly: false },
  { label: '数据中心', to: '/quant/data', icon: Search, adminOnly: false },
  { label: '行业看板', to: '/quant/industry', icon: Histogram, adminOnly: false },
  { label: '策略中心', to: '/quant/strategy', icon: MagicStick, adminOnly: false },
  { label: '执行记录', to: '/quant/runs', icon: VideoPlay, adminOnly: false },
  { label: '操作登记', to: '/quant/operations', icon: DocumentChecked, adminOnly: false },
  { label: '回测评估', to: '/quant/backtest', icon: TrendCharts, adminOnly: false },
  { label: '调度执行', to: '/quant/scheduler', icon: RefreshRight, adminOnly: true },
  { label: 'AI与记忆', to: '/quant/ai-memory', icon: Histogram, adminOnly: true },
  { label: 'IM 通道', to: '/quant/im-positions', icon: Promotion, adminOnly: true }
]

const navItems = computed(() =>
  allNavItems.filter(item => !item.adminOnly || authStore.isAdmin())
)

onMounted(async () => {
  initThemeManager()
  await workbench.initialize()
})
</script>
