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
      <el-table
        :data="workbench.strategyRuns"
        stripe
        height="680"
        class="quant-table"
        @row-click="workbench.loadSignals($event.id)"
        :row-class-name="({ row }) => row.id === workbench.selectedRunId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="trade_date" label="交易日" width="110" />
        <el-table-column label="策略" min-width="160">
          <template #default="{ row }">{{ row.summary?.strategy_name || workbench.resolveStrategyName(row.strategy_id) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.taskStatusTag(row.status)">{{ row.status }}</el-tag>
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

      <el-table :data="workbench.strategySignals" stripe height="580" class="quant-table" v-loading="workbench.loading.signals">
        <el-table-column prop="symbol" label="标的" min-width="120" />
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
</script>
