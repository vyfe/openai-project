<template>
  <div class="quant-grid quant-grid--data">
    <section class="quant-panel">
      <div class="quant-panel__header quant-data-toolbar">
        <div class="quant-data-toolbar__row">
          <div>
            <h2>K线数据</h2>
            <p class="quant-panel__sub">按周期查看日线 / 周线聚合，配套 MA 与成交量</p>
          </div>
          <div class="quant-toolbar">
            <el-radio-group v-model="workbench.chartCycle" size="small" @change="onCycleChange">
              <el-radio-button label="daily">日线</el-radio-button>
              <el-radio-button label="weekly">周线</el-radio-button>
            </el-radio-group>
            <el-radio-group v-model="workbench.dailyQueryRange" size="small" @change="applyDailyRange">
              <el-radio-button label="1m">近1月</el-radio-button>
              <el-radio-button label="3m">近3月</el-radio-button>
              <el-radio-button label="6m">近6月</el-radio-button>
              <el-radio-button label="1y">近1年</el-radio-button>
              <el-radio-button label="all">全部</el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <div class="quant-data-toolbar__row quant-data-toolbar__row--filters">
          <el-form label-position="top" class="quant-data-toolbar__symbol">
            <el-form-item label="股票代码">
              <el-select v-model="workbench.dailyQuery.symbol" filterable clearable placeholder="例如 600519.SH" @change="onSymbolChange">
                <el-option
                  v-for="item in workbench.symbolOptions"
                  :key="item.symbol"
                  :label="symbolLabel(item)"
                  :value="item.symbol"
                />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top" class="quant-data-toolbar__dates">
            <el-form-item label="起止日期">
              <el-date-picker
                v-model="workbench.dailyQuery.dateRange"
                type="daterange"
                range-separator="→"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                unlink-panels
                style="width:100%"
                @change="onCustomDateChange"
              />
            </el-form-item>
          </el-form>
          <el-form label-position="top" class="quant-data-toolbar__limit">
            <el-form-item label="返回条数">
              <el-input-number v-model="workbench.dailyQuery.limit" :min="20" :max="5000" :step="20" style="width:100%" />
            </el-form-item>
          </el-form>
          <div class="quant-data-toolbar__action">
            <el-button :icon="Search" type="primary" @click="workbench.loadDailyBars" :loading="workbench.loading.dailyBars">查询</el-button>
          </div>
        </div>
      </div>

      <div class="quant-chart-wrap">
        <EChartsCandlestick
          v-if="(workbench.currentBars as any) && (workbench.currentBars as any).length"
          :bars="workbench.currentBars as any"
          :is-dark="isDarkTheme"
          :symbol="workbench.dailyQuery.symbol"
          height="480px"
        />
        <el-empty v-else :description="emptyDescription" />
      </div>
    </section>

    <div class="quant-side-stack">
      <section class="quant-panel">
        <div class="quant-panel__header">
          <div>
            <h2>数据同步任务</h2>
          </div>
          <div class="quant-toolbar">
            <el-button type="primary" :icon="Promotion" @click="workbench.createTask" :loading="workbench.loading.createTask">创建任务</el-button>
            <el-button plain :icon="Download" @click="workbench.fetchNowFromTaskForm" :loading="workbench.loading.fetchNow">手动拉数验证</el-button>
            <el-button plain :icon="Promotion" @click="workbench.createBackfillTask" :loading="workbench.loading.createTask">补历史数据</el-button>
          </div>
        </div>

        <div class="quant-mini-section quant-mini-section--first">
          <div class="quant-mini-section__title">
            <span>搜索并加入股票池</span>
          </div>
          <div class="quant-symbol-add-row">
            <el-select
              v-model="workbench.stockPoolForm.selectedSymbol"
              filterable
              remote
              clearable
              reserve-keyword
              allow-create
              default-first-option
              placeholder="输入 000657 / 中钨高新"
              :remote-method="workbench.searchSymbols"
              :loading="workbench.loading.symbolSearch"
              @change="workbench.handleStockPoolSelect"
            >
              <el-option
                v-for="item in workbench.visibleSymbolOptions"
                :key="item.symbol"
                :label="symbolLabel(item)"
                :value="item.symbol"
              />
            </el-select>
            <el-button type="primary" :loading="workbench.loading.savingSymbol" @click="workbench.addSelectedSymbolToPool">加入股票池</el-button>
          </div>
        </div>

        <div class="quant-form-stack">
          <el-form label-position="top">
            <el-form-item label="股票池">
              <el-select
                v-model="workbench.taskForm.symbols"
                multiple
                filterable
                remote
                reserve-keyword
                allow-create
                default-first-option
                collapse-tags
                collapse-tags-tooltip
                placeholder="搜索或选择一个或多个标的"
                :remote-method="workbench.searchSymbols"
                :loading="workbench.loading.symbolSearch"
              >
                <el-option
                  v-for="item in workbench.visibleSymbolOptions"
                  :key="item.symbol"
                  :label="symbolLabel(item)"
                  :value="item.symbol"
                />
              </el-select>
            </el-form-item>
          </el-form>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="日期范围">
                <el-radio-group v-model="workbench.taskFormRange" size="small" @change="applyTaskRange">
                  <el-radio-button label="1m">近1月</el-radio-button>
                  <el-radio-button label="3m">近3月</el-radio-button>
                  <el-radio-button label="6m">近6月</el-radio-button>
                  <el-radio-button label="1y">近1年</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-form>
          </div>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="起止日期">
                <el-date-picker
                  v-model="workbench.taskForm.dateRange"
                  type="daterange"
                  range-separator="→"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="YYYY-MM-DD"
                  unlink-panels
                  style="width:100%"
                  @change="onTaskCustomDateChange"
                />
              </el-form-item>
            </el-form>
          </div>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="数据源">
                <el-select v-model="workbench.taskForm.provider">
                  <el-option v-for="provider in workbench.providers" :key="provider" :label="provider" :value="provider" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="复权">
                <el-select v-model="workbench.taskForm.adjustFlag">
                  <el-option label="前复权" value="qfq" />
                  <el-option label="后复权" value="hfq" />
                  <el-option label="不复权" value="raw" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>
          <el-form label-position="top">
            <el-form-item label="备注">
              <el-input v-model="workbench.taskForm.note" placeholder="例如：补 2024-2025 年回测样本" />
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>补历史数据</span>
          </div>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="股票池">
                <el-select
                  v-model="workbench.backfillForm.symbols"
                  multiple
                  filterable
                  remote
                  reserve-keyword
                  allow-create
                  default-first-option
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="搜索或选择要补数的股票"
                  :remote-method="workbench.searchSymbols"
                  :loading="workbench.loading.symbolSearch"
                >
                  <el-option
                    v-for="item in workbench.visibleSymbolOptions"
                    :key="item.symbol"
                    :label="symbolLabel(item)"
                    :value="item.symbol"
                  />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="回看天数">
                <el-input-number v-model="workbench.backfillForm.lookbackDays" :min="30" :max="1000" :step="30" style="width:100%" />
              </el-form-item>
            </el-form>
          </div>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="数据源">
                <el-select v-model="workbench.backfillForm.provider">
                  <el-option v-for="provider in workbench.providers" :key="provider" :label="provider" :value="provider" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="复权">
                <el-select v-model="workbench.backfillForm.adjustFlag">
                  <el-option label="前复权" value="qfq" />
                  <el-option label="后复权" value="hfq" />
                  <el-option label="不复权" value="raw" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>
          <el-form label-position="top">
            <el-form-item label="备注">
              <el-input v-model="workbench.backfillForm.note" placeholder="例如：新买入后自动补 2 年历史" />
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>最近任务</span>
            <el-button text :icon="RefreshRight" @click="workbench.loadTasks" :loading="workbench.loading.tasks">刷新</el-button>
          </div>
          <div class="quant-mini-list">
            <div v-for="task in workbench.clientTasks" :key="task.task_id" class="quant-mini-item">
              <div class="quant-mini-item__head">
                <span class="quant-mini-item__title">{{ task.payload?.symbols?.slice(0, 2)?.join(', ') || task.task_id }}</span>
                <el-tag size="small" :type="workbench.taskStatusTag(task.status)">{{ task.status }}</el-tag>
              </div>
              <div class="quant-mini-item__meta">{{ task.payload?.start_date }} 至 {{ task.payload?.end_date }}</div>
              <div class="quant-mini-item__actions">
                <span>{{ task.message || '等待客户端处理' }}</span>
                <el-button v-if="task.status === 'failed'" text @click="workbench.resetTask(task.task_id)">重置</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>最近导入批次</span>
            <el-button text :icon="RefreshRight" @click="workbench.loadImportBatches" :loading="workbench.loading.importBatches">刷新</el-button>
          </div>
          <div class="quant-mini-list">
            <div v-for="batch in workbench.importBatches" :key="batch.batch_id" class="quant-mini-item">
              <div class="quant-mini-item__head">
                <span class="quant-mini-item__title">{{ batch.source }}</span>
                <el-tag size="small" :type="workbench.taskStatusTag(batch.status)">{{ batch.status }}</el-tag>
              </div>
              <div class="quant-mini-item__meta">{{ batch.records_imported }}/{{ batch.records_total }} 条</div>
              <div class="quant-mini-item__actions">
                <span>{{ batch.finished_at || batch.created_at }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download, Promotion, RefreshRight, Search } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'
import { useThemeManager } from '@/composables/useThemeManager'
import { symbolLabel } from '@/composables/quant/format'
import EChartsCandlestick from '@/components/quant/EChartsCandlestick.vue'

const workbench = useQuantWorkbench()
const { isDarkTheme } = useThemeManager()

const RANGE_MONTHS: Record<string, number | null> = { '1m': 1, '3m': 3, '6m': 6, '1y': 12, all: null }

function applyDailyRange(range: string) {
  const months = RANGE_MONTHS[range]
  const end = new Date()
  let start: Date
  if (months == null) {
    // 全部：置空让后端返回所有数据
    workbench.dailyQuery.startDate = ''
    workbench.dailyQuery.endDate = ''
    workbench.loadDailyBars()
    return
  }
  start = new Date(end)
  start.setMonth(start.getMonth() - months)
  workbench.dailyQuery.startDate = start.toISOString().slice(0, 10)
  workbench.dailyQuery.endDate = end.toISOString().slice(0, 10)
  workbench.loadDailyBars()
}

function applyTaskRange(range: string) {
  const months = RANGE_MONTHS[range]
  if (months == null) return
  const end = new Date()
  const start = new Date(end)
  start.setMonth(start.getMonth() - months)
  workbench.taskForm.startDate = start.toISOString().slice(0, 10)
  workbench.taskForm.endDate = end.toISOString().slice(0, 10)
}

function onCustomDateChange() {
  ;(workbench.dailyQueryRange as any) = ''
}

function onTaskCustomDateChange() {
  ;(workbench.taskFormRange as any) = ''
}

function onCycleChange(cycle: 'daily' | 'weekly') {
  workbench.switchChartCycle(cycle)
}

function onSymbolChange(symbol: string) {
  // 切 symbol 时同时清空两个周期的缓存，触发新一轮加载
  if (!symbol) return
  workbench.loadDailyBars()
}

const emptyDescription = computed(() => {
  const cycle = workbench.chartCycle as unknown as 'daily' | 'weekly'
  const base = '请选择股票并点击查询，或先在数据同步任务里拉数入库'
  return cycle === 'weekly' ? `${base}（日线 ≥ 5 条才会聚合成周线）` : base
})
</script>
