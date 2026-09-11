<template>
  <div class="quant-grid quant-grid--runs">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>运行记录</h2>
          <p>先看这次扫了多少标的、出了多少信号，再往下看每只股票的判断原因。</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadRuns" :loading="workbench.loading.runs">刷新</el-button>
        </div>
      </div>

      <div class="quant-form-stack quant-section-gap">
        <el-select
          v-model="selectedRunIdProxy"
          placeholder="从下拉里选一条执行记录"
          filterable
          clearable
          class="quant-run-picker"
          @change="onSelectRun"
        >
          <el-option
            v-for="run in workbench.strategyRuns"
            :key="run.id"
            :label="runLabel(run)"
            :value="run.id"
          >
            <div class="quant-run-option">
              <span class="quant-run-option__id">#{{ run.id }}</span>
              <span class="quant-run-option__date">{{ run.trade_date }}</span>
              <span class="quant-run-option__strategy">{{ run.summary?.strategy_name || workbench.resolveStrategyName(run.strategy_id) }}</span>
              <el-tag size="small" :type="workbench.taskStatusTag(run.status)">{{ workbench.statusLabel(run.status) }}</el-tag>
              <span class="quant-run-option__ratio">{{ run.signals_total }}/{{ run.symbols_total }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <el-table
        :data="workbench.strategyRuns"
        stripe
        height="560"
        class="quant-table quant-table--interactive"
        empty-text="先选择一条运行记录查看信号"
        @row-click="(row) => workbench.handleRunSelect(row)"
        :row-class-name="({ row }) => row.id === workbench.selectedRunId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="trade_date" label="交易日" width="110" />
        <el-table-column label="策略" min-width="160">
          <template #default="{ row }">{{ row.summary?.strategy_name || workbench.resolveStrategyName(row.strategy_id) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.taskStatusTag(row.status)">{{ workbench.statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通过" width="96">
          <template #default="{ row }">{{ row.signals_total }}/{{ row.symbols_total }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="170" />
      </el-table>
    </section>

    <section class="quant-panel quant-panel--editor">
      <div class="quant-panel__header">
        <div>
          <h2>信号详情</h2>
          <p>{{ workbench.selectedRun ? `${workbench.selectedRun.trade_date} 的规则扫描结果` : '先在左侧选中一次运行记录。' }}</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="VideoPlay" @click="generateReportAndOpenAiMemory" :loading="workbench.loading.generatingReport">生成测试报告</el-button>
        </div>
      </div>

      <div v-if="workbench.selectedRun" class="quant-run-summary">
        <div class="quant-run-summary__metric">
          <span>交易日</span>
          <strong>{{ workbench.selectedRun.trade_date }}</strong>
        </div>
        <div class="quant-run-summary__metric">
          <span>通过信号</span>
          <strong>{{ workbench.selectedRun.signals_total }}</strong>
        </div>
        <div class="quant-run-summary__metric">
          <span>扫描标的</span>
          <strong>{{ workbench.selectedRun.symbols_total }}</strong>
        </div>
      </div>

      <el-table :data="workbench.strategySignals" stripe height="580" class="quant-table" empty-text="先选择一条运行记录查看信号" v-loading="workbench.loading.signals">
        <el-table-column label="标的" min-width="200">
          <template #default="{ row }">{{ workbench.displaySymbol(row.symbol) }}</template>
        </el-table-column>
        <el-table-column prop="signal_type" label="信号类型" width="110" />
        <el-table-column prop="score" label="得分" width="90" />
        <el-table-column label="是否通过" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="row.passed ? 'success' : 'info'">{{ row.passed ? '通过' : '未过' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="理由" min-width="320">
          <template #default="{ row }">
            <div class="quant-reason-list">
              <span v-for="reason in row.reasons || []" :key="reason" class="quant-reason-item">{{ reason }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="100">
          <template #default="{ row }">
            <el-button text @click="openOperationFromSignal(row)">登记</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { RefreshRight, VideoPlay } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const router = useRouter()
const workbench = useQuantWorkbench()

const openOperationFromSignal = (signal: any) => {
  workbench.prefillOperationFromSignal(signal)
  router.push('/quant/operations')
}

const generateReportAndOpenAiMemory = async () => {
  const report = await workbench.generateReportFromRun()
  if (report?.id) router.push('/quant/ai-memory')
}

// 下拉选择 run：用 computed proxy 绑 workbench.selectedRunId，
// 让 v-model 的 setter 直接调 handleRunSelect（先 setRunId 再 fetch）。
// 避免 v-model.number 直接改 ref 后还要手动调 loadSignals 二次触发。
const selectedRunIdProxy = computed<number | null>({
  get: () => workbench.selectedRunId,
  set: (value) => workbench.handleRunSelect(value ?? null),
})

const onSelectRun = (runId: number | null) => {
  // el-select @change 自带新值；这里走 workbench 入口以便统一 future 副作用
  workbench.handleRunSelect(runId ?? null)
}

const runLabel = (run: any) => {
  const strategy = run.summary?.strategy_name || workbench.resolveStrategyName(run.strategy_id) || '未知策略'
  const ratio = `${run.signals_total}/${run.symbols_total}`
  return `#${run.id} · ${run.trade_date} · ${strategy} · ${ratio} · ${workbench.statusLabel(run.status)}`
}
</script>
