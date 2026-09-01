<template>
  <div class="dry-run-panel">
    <div class="dry-run-panel__header">
      <h4>试算</h4>
      <span v-if="ide.loading.dryRun" class="dry-run-panel__status">运行中…</span>
      <span v-else-if="ide.dryRun.value" class="dry-run-panel__status">
        {{ ide.dryRun.value.meta.passed_count }} / {{ ide.dryRun.value.meta.bars_count }} 命中
      </span>
    </div>

    <div class="dry-run-panel__params">
      <div class="dry-run-panel__row">
        <span class="dry-run-panel__label">标的</span>
        <el-select
          v-model="ide.dryRunParams.symbol"
          filterable
          allow-create
          default-first-option
          :filter-method="onSymbolSearch"
          :loading="poolLoading"
          placeholder="选择或输入 symbol"
          size="small"
          class="dry-run-panel__symbol"
          popper-class="dry-run-panel__symbol-popper"
        >
          <el-option
            v-for="item in displayedSymbols"
            :key="item.symbol"
            :label="`${item.code} ${item.name || ''} (${item.symbol})`"
            :value="item.symbol"
          />
        </el-select>
        <el-select
          v-model="ide.dryRunParams.adjust_flag"
          size="small"
          class="dry-run-panel__adjust"
        >
          <el-option label="前复权 qfq" value="qfq" />
          <el-option label="不复权 none" value="none" />
        </el-select>
      </div>

      <div class="dry-run-panel__row">
        <span class="dry-run-panel__label">区间</span>
        <el-date-picker
          v-model="ide.dryRunParams.start_date"
          type="date"
          value-format="YYYY-MM-DD"
          size="small"
          placeholder="开始"
          class="dry-run-panel__date"
        />
        <span class="dry-run-panel__dash">→</span>
        <el-date-picker
          v-model="ide.dryRunParams.end_date"
          type="date"
          value-format="YYYY-MM-DD"
          size="small"
          placeholder="结束"
          class="dry-run-panel__date"
        />
        <div class="dry-run-panel__presets">
          <el-tag
            v-for="p in rangePresets"
            :key="p.key"
            size="small"
            :effect="isPresetActive(p) ? 'dark' : 'plain'"
            :type="isPresetActive(p) ? 'primary' : 'info'"
            class="dry-run-panel__preset"
            @click="applyPreset(p)"
          >
            {{ p.label }}
          </el-tag>
        </div>
      </div>

      <div v-if="strategyPoolSymbols.length" class="dry-run-panel__row dry-run-panel__pool-row">
        <span class="dry-run-panel__label">策略股票池</span>
        <div class="dry-run-panel__pool">
          <el-tag
            v-for="s in strategyPoolSymbols.slice(0, 8)"
            :key="s"
            size="small"
            effect="plain"
            class="dry-run-panel__pool-tag"
            @click="ide.dryRunParams.symbol = s"
          >
            {{ s }}
          </el-tag>
          <el-tag
            v-if="strategyPoolSymbols.length > 8"
            size="small"
            type="info"
            effect="plain"
            class="dry-run-panel__pool-tag"
          >
            +{{ strategyPoolSymbols.length - 8 }} 更多
          </el-tag>
          <el-tag
            v-if="!strategyPoolSymbols.includes(ide.dryRunParams.symbol)"
            size="small"
            effect="plain"
            class="dry-run-panel__pool-tag dry-run-panel__pool-tag--loop"
            @click="loopPool"
            title="依次用股票池每个 symbol 试算"
          >
            循环试算
          </el-tag>
        </div>
      </div>
    </div>

    <div v-if="!ide.dryRun.value && !ide.loading.dryRun" class="dry-run-panel__empty">
      调整指标 / 表达式后会自动试算。
    </div>

    <div v-else-if="ide.dryRun.value" class="dry-run-panel__results">
      <div class="dry-run-panel__summary">
        <span>共 {{ ide.dryRun.value.bars.length }} 根 bar</span>
        <span class="dry-run-panel__divider">·</span>
        <span>命中 {{ ide.passedDates.value.length }} 个</span>
        <span class="dry-run-panel__divider">·</span>
        <span>命中率 {{ hitRate }}%</span>
      </div>

      <el-table
        :data="passedRows"
        stripe
        size="small"
        height="220"
        empty-text="区间内无命中"
        class="dry-run-panel__table"
      >
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="score" label="分数" width="70" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }: { row: any }">
            <el-tag size="small" :type="row.signal_type === 'buy' ? 'success' : 'info'" effect="plain">
              {{ row.signal_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="命中规则">
          <template #default="{ row }: { row: any }">
            <span class="dry-run-panel__rules">
              <el-tag
                v-for="rr in row.rule_results"
                :key="rr.id"
                size="small"
                effect="plain"
                :type="rr.passed ? 'success' : 'info'"
              >
                {{ rr.label || rr.id }}
              </el-tag>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { quantDataAPI } from '@/services/quantApi'
import type { useStrategyIde } from '@/composables/useStrategyIde'
import type { useQuantWorkbench } from '@/composables/useQuantWorkbench'

type Ide = ReturnType<typeof useStrategyIde>
type Wb = ReturnType<typeof useQuantWorkbench>

const props = defineProps<{ ide: Ide; workbench: Wb }>()

const rangePresets = [
  { key: '1m', label: '近 1 月', months: 1 },
  { key: '3m', label: '近 3 月', months: 3 },
  { key: '6m', label: '近半年', months: 6 },
  { key: '1y', label: '近 1 年', months: 12 }
]

function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function applyPreset(p: { key: string; months: number }) {
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - p.months)
  props.ide.dryRunParams.start_date = isoDate(start)
  props.ide.dryRunParams.end_date = isoDate(end)
}

function isPresetActive(p: { key: string; months: number }): boolean {
  if (!props.ide.dryRunParams.start_date || !props.ide.dryRunParams.end_date) return false
  const end = new Date(props.ide.dryRunParams.end_date)
  const start = new Date(props.ide.dryRunParams.start_date)
  const diffMs = end.getTime() - start.getTime()
  const diffMonths = diffMs / (1000 * 60 * 60 * 24 * 30)
  return Math.abs(diffMonths - p.months) < 0.5
}

const strategyPoolSymbols = computed(() => props.ide.form.symbols || [])

interface SymbolOption {
  symbol: string
  code: string
  name?: string
  exchange?: string
}

const symbolCandidates = ref<SymbolOption[]>([])
const poolLoaded = ref(false)
const poolLoading = ref(false)
const poolVisibleLimit = 200

async function loadPool() {
  if (poolLoading.value) return
  poolLoading.value = true
  try {
    const res: any = await quantDataAPI.symbols({ limit: 500, offset: 0 })
    symbolCandidates.value = (res.data?.items || res.data || []) as SymbolOption[]
    poolLoaded.value = true
  } catch {
    symbolCandidates.value = []
  } finally {
    poolLoading.value = false
  }
}

function onSymbolSearch(keyword: string) {
  // 本地过滤（pool 已加载 500 条足够覆盖常见场景）
  if (!keyword) return true  // 返回 true = 不阻止默认行为
  return false  // false = 自定义过滤（保留全量，filter 由 el-select 处理）
}

// 默认显示前 200，搜索过滤全量（最多 500）
const displayedSymbols = computed(() => {
  return symbolCandidates.value.slice(0, poolVisibleLimit)
})

onMounted(() => {
  if (!poolLoaded.value) loadPool()
})

// 把当前 symbol 显示在下拉里
watch(
  () => props.ide.dryRunParams.symbol,
  (v) => {
    if (v && !symbolCandidates.value.find(c => c.symbol === v)) {
      symbolCandidates.value = [
        { symbol: v, code: v.split('.')[0] || v },
        ...symbolCandidates.value
      ]
    }
  },
  { immediate: true }
)

function loopPool() {
  // eslint-disable-next-line no-console
  console.info('[strategy ide] 循环试算股票池待 P2 实现')
}

const passedRows = computed(() => {
  const dr = props.ide.dryRun.value
  if (!dr) return []
  return dr.results.filter(r => r.passed).slice(-50).reverse()
})

const hitRate = computed(() => {
  const dr = props.ide.dryRun.value
  if (!dr || !dr.meta.bars_count) return '0.0'
  return ((dr.meta.passed_count / dr.meta.bars_count) * 100).toFixed(1)
})
</script>

<style scoped>
.dry-run-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--q-line);
  border-radius: 8px;
  background: var(--q-surface);
}
.dry-run-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dry-run-panel__header h4 {
  margin: 0;
  color: var(--q-ink);
  font-size: 13px;
  font-weight: 760;
}
.dry-run-panel__status {
  color: var(--q-muted);
  font-size: 12px;
  font-family: var(--q-mono);
}
.dry-run-panel__params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dry-run-panel__row {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.dry-run-panel__label {
  color: var(--q-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.dry-run-panel__symbol {
  width: 100%;
}
.dry-run-panel__adjust { width: 130px; }
.dry-run-panel__date { width: 130px; }
.dry-run-panel__dash {
  color: var(--q-muted);
  font-size: 12px;
}
.dry-run-panel__presets {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  grid-column: 1 / -1;
  margin-left: 68px;
}
.dry-run-panel__preset {
  cursor: pointer;
}
.dry-run-panel__pool-row {
  align-items: flex-start;
}
.dry-run-panel__pool {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  grid-column: 2 / -1;
}
.dry-run-panel__pool-tag {
  font-family: var(--q-mono);
  cursor: pointer;
}
.dry-run-panel__pool-tag--loop {
  border-color: var(--q-copper);
  color: var(--q-copper);
}
.dry-run-panel__empty {
  padding: 24px;
  color: var(--q-muted);
  font-size: 12px;
  text-align: center;
  border: 1px dashed var(--q-line);
  border-radius: 6px;
}
.dry-run-panel__summary {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--q-muted);
  font-size: 12px;
}
.dry-run-panel__divider { color: var(--q-line-strong); }
.dry-run-panel__table { font-size: 12px; }
.dry-run-panel__rules {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
@media (max-width: 768px) {
  .dry-run-panel__row {
    grid-template-columns: 1fr;
  }
  .dry-run-panel__presets { margin-left: 0; }
  .dry-run-panel__pool { grid-column: 1 / -1; }
}
</style>