<template>
  <div class="quant-page min-h-screen" :class="{ dark: isDarkTheme, 'quant-dark': isDarkTheme }">
    <div class="quant-shell">
      <header class="quant-header">
        <div class="quant-header__left">
          <button class="quant-back-btn" @click="goBack" aria-label="返回聊天">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <div>
            <div class="quant-eyebrow">A Share Quant Console</div>
            <h1 class="quant-title">量化工作台</h1>
            <p class="quant-subtitle">按模块拆分数据、策略、调度、AI 和记忆，让后续能力可以持续演进。</p>
          </div>
        </div>
        <div class="quant-header__right">
          <el-button class="quant-header-btn" text @click="goAdmin">
            <el-icon><Setting /></el-icon>
            管理台
          </el-button>
          <div class="quant-user-pill">
            <el-icon><DataBoard /></el-icon>
            <span>{{ authStore.user }}</span>
          </div>
        </div>
      </header>

      <section class="quant-summary-grid">
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

      <el-alert
        class="quant-banner"
        type="info"
        :closable="false"
        show-icon
        title="当前阶段：页面已拆成子路由模式；策略执行仍由主服务触发，客户端任务只负责抓数与回传。"
      />

      <main class="quant-main-panel" v-loading="workbench.loading.bootstrap">
        <div class="quant-workspace">
          <aside class="quant-nav-panel">
            <h2 class="quant-nav-title">模块导航</h2>
            <p class="quant-nav-subtitle">按后端服务边界拆页，后续开发直接对应模块扩展。</p>
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
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  DataBoard,
  DocumentChecked,
  Histogram,
  MagicStick,
  Promotion,
  RefreshRight,
  Search,
  Setting,
  TrendCharts,
  VideoPlay
} from '@element-plus/icons-vue'
import { useThemeManager } from '@/composables/useThemeManager'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'
import { useAuthStore } from '@/stores/auth'
import '@/styles/quant-workbench.css'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager } = useThemeManager()
const workbench = useQuantWorkbench()
const summaryCards = computed(() => (unref(workbench.dashboardCards) || []).filter((card): card is NonNullable<typeof card> => Boolean(card)))

const allNavItems = [
  { label: '总览', to: '/quant/overview', icon: DataBoard, adminOnly: false },
  { label: '数据中心', to: '/quant/data', icon: Search, adminOnly: false },
  { label: '策略中心', to: '/quant/strategy', icon: MagicStick, adminOnly: true },
  { label: '执行记录', to: '/quant/runs', icon: VideoPlay, adminOnly: false },
  { label: '操作登记', to: '/quant/operations', icon: DocumentChecked, adminOnly: false },
  { label: '回测评估', to: '/quant/backtest', icon: TrendCharts, adminOnly: true },
  { label: '调度执行', to: '/quant/scheduler', icon: RefreshRight, adminOnly: true },
  { label: 'AI与记忆', to: '/quant/ai-memory', icon: Histogram, adminOnly: false },
  { label: 'IM与持仓', to: '/quant/im-positions', icon: Promotion, adminOnly: false }
]

const navItems = computed(() =>
  allNavItems.filter(item => !item.adminOnly || authStore.isAdmin())
)

const goBack = () => router.push('/chat')
const goAdmin = () => router.push('/admin')

onMounted(async () => {
  initThemeManager()
  await workbench.initialize()
})
</script>
