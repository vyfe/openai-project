<template>
  <div class="quant-grid quant-grid--industry">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>行业看板</h2>
          <p>{{ activeBoard?.name || '等待板块数据' }} · {{ dashboard?.latest_trade_date || '--' }}</p>
        </div>
        <div class="quant-toolbar">
          <el-select v-model="selectedBoardId" placeholder="选择板块" style="width: 180px" @change="loadDashboard">
            <el-option v-for="board in boards" :key="board.id" :label="board.name" :value="board.id" />
          </el-select>
          <el-button :icon="RefreshRight" @click="loadDashboard" :loading="loading.dashboard">刷新</el-button>
        </div>
      </div>

      <div class="quant-toolbar quant-toolbar--wrap">
        <el-button type="primary" :icon="Download" :loading="loading.collectAll" @click="collect(['market', 'announcements', 'news', 'research_reports', 'indicators'], 'collectAll')">采集全部</el-button>
        <el-button plain :loading="loading.collectMarket" @click="collect(['market', 'indicators'], 'collectMarket')">行情资金</el-button>
        <el-button plain :loading="loading.collectNews" @click="collect(['announcements', 'news', 'indicators'], 'collectNews')">公告新闻</el-button>
        <el-button plain :loading="loading.collectReports" @click="collect(['research_reports', 'indicators'], 'collectReports')">研报</el-button>
        <el-button plain @click="loadPreview" :loading="loading.preview">日报预览</el-button>
      </div>

      <el-alert
        v-if="lastCollectResult"
        class="quant-industry-alert"
        :type="lastCollectResult.errors?.length ? 'warning' : 'success'"
        :closable="false"
        :title="collectSummary"
      />

      <div class="quant-industry-cards">
        <article v-for="item in dashboard?.latest_cards || []" :key="item.symbol" class="quant-metric-card">
          <span>{{ item.name }} · {{ item.symbol }}</span>
          <strong>{{ formatNumber(item.close_price) }}</strong>
          <div class="quant-card-row">
            <span :class="Number(item.pct_change) >= 0 ? 'quant-pos' : 'quant-neg'">{{ formatPct(item.pct_change) }}</span>
            <span>成交 {{ formatYi(item.amount) }}</span>
          </div>
          <div class="quant-card-row">
            <span>PE {{ formatNumber(item.pe_ttm) }}</span>
            <span>PB {{ formatNumber(item.pb) }}</span>
          </div>
          <div class="quant-card-row">
            <span>主力 {{ formatYi(item.main_flow) }}</span>
            <span>市值 {{ formatYi(item.market_cap) }}</span>
          </div>
        </article>
        <div v-if="!(dashboard?.latest_cards || []).length" class="quant-empty-card">暂无行情快照</div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>指标快照</h2>
          <p>行情、估值、资金和主题热度。</p>
        </div>
      </div>
      <el-table :data="dashboard?.indicators || []" stripe height="360" class="quant-table">
        <el-table-column prop="indicator_group" label="分组" width="120" />
        <el-table-column prop="indicator_name" label="指标" min-width="140" />
        <el-table-column label="对象" min-width="160">
          <template #default="{ row }">{{ row.subject_name || row.subject_code }}</template>
        </el-table-column>
        <el-table-column prop="observed_date" label="日期" width="120" />
        <el-table-column label="数值" width="130">
          <template #default="{ row }">{{ formatNumber(row.value) }}{{ row.unit || '' }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" min-width="160" />
      </el-table>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>公告与新闻</h2>
          <p>按采集时间和发布时间排序。</p>
        </div>
      </div>
      <el-table :data="dashboard?.news || []" stripe height="420" class="quant-table">
        <el-table-column prop="published_at" label="日期" width="120" />
        <el-table-column prop="source" label="来源" width="130" />
        <el-table-column prop="title" label="标题" min-width="320">
          <template #default="{ row }">
            <a :href="row.url" target="_blank" rel="noreferrer">{{ row.title }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="标签" width="150" />
      </el-table>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>研报</h2>
          <p>仅沉淀元数据、摘要和原文链接。</p>
        </div>
      </div>
      <el-table :data="dashboard?.research_reports || []" stripe height="420" class="quant-table">
        <el-table-column prop="published_at" label="日期" width="120" />
        <el-table-column prop="org_name" label="机构" width="140" />
        <el-table-column prop="rating" label="评级" width="100" />
        <el-table-column prop="title" label="标题" min-width="320">
          <template #default="{ row }">
            <a :href="row.url" target="_blank" rel="noreferrer">{{ row.title }}</a>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="previewVisible" title="行业日报预览" width="760px">
      <pre class="quant-industry-preview">{{ reportPreview }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, RefreshRight } from '@element-plus/icons-vue'
import { quantIndustryAPI } from '@/services/quantApi'

const boards = ref<any[]>([])
const selectedBoardId = ref<number | null>(null)
const dashboard = ref<any>(null)
const lastCollectResult = ref<any>(null)
const reportPreview = ref('')
const previewVisible = ref(false)
const loading = reactive({
  boards: false,
  dashboard: false,
  collectAll: false,
  collectMarket: false,
  collectNews: false,
  collectReports: false,
  preview: false
})

const activeBoard = computed(() => boards.value.find(item => item.id === selectedBoardId.value) || dashboard.value?.board)
const collectSummary = computed(() => {
  const result = lastCollectResult.value
  if (!result) return ''
  const fragments = [
    `行情 ${result.market_snapshots || 0}`,
    `日线 ${result.daily_bars || 0}`,
    `新闻 ${result.news_items || 0}`,
    `公告 ${result.announcements || 0}`,
    `研报 ${result.research_reports || 0}`,
    `指标 ${result.indicator_snapshots || 0}`
  ]
  if (result.errors?.length) fragments.push(`错误 ${result.errors.length}`)
  return fragments.join('，')
})

async function loadBoards() {
  loading.boards = true
  try {
    await quantIndustryAPI.initDefaults()
    const response: any = await quantIndustryAPI.boards({ status: 'active' })
    boards.value = response.data || []
    if (!selectedBoardId.value && boards.value.length) selectedBoardId.value = boards.value[0].id
  } finally {
    loading.boards = false
  }
}

async function loadDashboard() {
  loading.dashboard = true
  try {
    const response: any = await quantIndustryAPI.dashboard({ board_id: selectedBoardId.value || undefined, days: 90 })
    dashboard.value = response.data || null
    if (dashboard.value?.board?.id) selectedBoardId.value = dashboard.value.board.id
  } catch (error: any) {
    ElMessage.error(error?.message || '行业看板加载失败')
  } finally {
    loading.dashboard = false
  }
}

async function collect(targets: string[], loadingKey: keyof typeof loading) {
  if (!selectedBoardId.value) return ElMessage.warning('先选择行业板块')
  loading[loadingKey] = true
  try {
    const response: any = await quantIndustryAPI.collect({ board_id: selectedBoardId.value, targets })
    lastCollectResult.value = response.data || null
    if (lastCollectResult.value?.errors?.length) {
      ElMessage.warning(`采集完成，但有 ${lastCollectResult.value.errors.length} 个源失败`)
    } else {
      ElMessage.success('采集完成')
    }
    await loadDashboard()
  } catch (error: any) {
    ElMessage.error(error?.message || '采集失败')
  } finally {
    loading[loadingKey] = false
  }
}

async function loadPreview() {
  if (!selectedBoardId.value) return
  loading.preview = true
  try {
    const response: any = await quantIndustryAPI.reportPreview({ board_id: selectedBoardId.value })
    reportPreview.value = response.data?.markdown || ''
    previewVisible.value = true
  } finally {
    loading.preview = false
  }
}

function formatNumber(value: any, digits = 2) {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(digits) : '--'
}

function formatPct(value: any) {
  return `${formatNumber(value)}%`
}

function formatYi(value: any) {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  return Number.isFinite(num) ? `${(num / 1e8).toFixed(2)}亿` : '--'
}

onMounted(async () => {
  await loadBoards()
  await loadDashboard()
})
</script>
