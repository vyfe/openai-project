<template>
  <div class="quant-grid quant-grid--overview">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>风险提示</h2>
          <p>先盯住最容易把闭环拖垮的地方：数据失败、未回填操作、回测回撤。</p>
        </div>
        <el-button text :icon="RefreshRight" @click="workbench.loadOverview" :loading="workbench.loading.overview">刷新</el-button>
      </div>
      <div class="quant-risk-list">
        <div v-for="tip in workbench.dashboardOverview?.risk_tips || []" :key="tip" class="quant-risk-item">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ tip }}</span>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>今日任务</h2>
          <p>客户端抓数和最近导入批次，先确认底层数据链路没有断。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="task in workbench.dashboardOverview?.today_tasks || workbench.clientTasks" :key="task.task_id" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ task.payload?.symbols?.slice(0, 2)?.join(', ') || task.task_id }}</span>
            <el-tag size="small" :type="workbench.taskStatusTag(task.status)">{{ task.status }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ task.payload?.start_date }} 至 {{ task.payload?.end_date }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ task.message || '等待执行' }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最新信号</h2>
          <p>优先看最新通过信号，再决定是否补充到人工操作登记里。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="signal in workbench.dashboardOverview?.latest_signals || []" :key="`${signal.run_id}-${signal.symbol}`" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ signal.symbol }}</span>
            <el-tag size="small" type="success">{{ signal.signal_type || 'watch' }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ signal.trade_date }} · 得分 {{ workbench.formatNumber(signal.score, 1) }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ signal.reasons?.[0] || '规则通过' }}</span>
            <el-button text @click="openOperationFromSignal(signal)">登记</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最近操作</h2>
          <p>人工执行不是旁路数据，后续复盘、自学习都要依赖这里。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="record in workbench.dashboardOverview?.recent_operations || workbench.operationRecords.slice(0, 6)" :key="record.id" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ record.symbol }}</span>
            <el-tag size="small" :type="workbench.operationStatusTag(record.status)">{{ record.status }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ workbench.resolveStrategyName(record.strategy_id) }} · {{ record.trade_date }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ record.action }} / {{ record.result_status || '待复盘' }}</span>
            <el-button text @click="openOperation(record)">查看</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最近回测</h2>
          <p>用轻量事件回测先判断规则有没有基本解释力，再谈调参。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="record in workbench.dashboardOverview?.recent_backtests || workbench.backtestRuns.slice(0, 6)" :key="record.id" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ record.strategy_name }}</span>
            <el-tag size="small" :type="workbench.backtestStatusTag(record.status)">{{ record.status }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ record.start_date }} ~ {{ record.end_date }}</div>
          <div class="quant-mini-item__actions">
            <span>收益 {{ workbench.formatRate(record.metrics?.total_return) }}</span>
            <el-button text @click="openBacktest(record)">查看</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最近运行</h2>
          <p>策略执行结果仍然是主轴，人工操作和回测都应该围着它沉淀。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="run in workbench.dashboardOverview?.recent_runs || workbench.strategyRuns.slice(0, 6)" :key="run.id" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ run.summary?.strategy_name || `策略 #${run.strategy_id}` }}</span>
            <el-tag size="small" :type="workbench.taskStatusTag(run.status)">{{ run.status }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ run.trade_date }} · 通过 {{ run.signals_total }}/{{ run.symbols_total }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ run.created_at }}</span>
            <el-button text @click="openRun(run.id)">查看</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最近报告</h2>
          <p>先看报告有没有稳定沉淀，再决定是否继续接 IM 或做更重的 AI 生成。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="record in workbench.dashboardOverview?.recent_reports || workbench.reports.slice(0, 6)" :key="record.id" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ record.title }}</span>
            <el-tag size="small" type="success">{{ record.report_type || 'test_report' }}</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ record.trade_date }} · {{ record.prompt_version }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ record.created_at || '刚生成' }}</span>
            <el-button text @click="openReport(record.id)">查看</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>最近记忆梳理</h2>
          <p>这里看长期记忆是否有持续更新，避免后续召回只建立在陈旧样本上。</p>
        </div>
      </div>
      <div class="quant-mini-list">
        <div v-for="record in workbench.dashboardOverview?.recent_memory_files || workbench.memoryFiles.slice(0, 6)" :key="record.symbol" class="quant-mini-item">
          <div class="quant-mini-item__head">
            <span class="quant-mini-item__title">{{ record.symbol }}</span>
            <el-tag size="small" type="info">memory</el-tag>
          </div>
          <div class="quant-mini-item__meta">{{ record.updated_at }}</div>
          <div class="quant-mini-item__actions">
            <span>{{ record.path?.split('/').slice(-1)[0] || '记忆档案' }}</span>
            <el-button text @click="openMemory(record.symbol)">查看</el-button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const router = useRouter()
const workbench = useQuantWorkbench()

const openOperationFromSignal = (signal: any) => {
  workbench.prefillOperationFromSignal(signal)
  router.push('/quant/operations')
}

const openOperation = (record: any) => {
  workbench.handleOperationSelect(record)
  router.push('/quant/operations')
}

const openBacktest = async (record: any) => {
  await workbench.handleBacktestSelect(record)
  router.push('/quant/backtest')
}

const openRun = async (runId: number) => {
  await workbench.loadSignals(runId)
  router.push('/quant/runs')
}

const openReport = async (reportId: number) => {
  await workbench.loadReportDetail(reportId)
  router.push('/quant/ai-memory')
}

const openMemory = async (symbol: string) => {
  await workbench.loadMemoryDetail(symbol)
  router.push('/quant/ai-memory')
}
</script>
