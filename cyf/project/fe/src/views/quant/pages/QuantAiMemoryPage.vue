<template>
  <div class="quant-grid quant-grid--ai-memory">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>Prompt 模板</h2>
          <p>这里管理测试报告的 Prompt 版本；真正报告生成仍然先经过 AnalysisBundle/ReportDraft 契约层。</p>
        </div>
        <div class="quant-toolbar">
          <el-button plain @click="workbench.resetPromptForm">新建模板</el-button>
          <el-button :icon="RefreshRight" @click="workbench.loadPromptTemplates" :loading="workbench.loading.prompts">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="workbench.promptTemplates"
        stripe
        height="280"
        class="quant-table"
        @row-click="workbench.hydratePromptForm"
        :row-class-name="({ row }) => row.id === workbench.selectedPromptId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="prompt_version" label="版本" width="130" />
        <el-table-column label="策略" min-width="150">
          <template #default="{ row }">{{ workbench.resolveStrategyName(row.strategy_id) }}</template>
        </el-table-column>
        <el-table-column prop="report_type" label="报告类型" width="120" />
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>

      <div class="quant-form-stack quant-section-gap">
        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="策略">
              <el-select v-model="workbench.promptForm.strategyId" clearable placeholder="为空表示全局模板">
                <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="版本">
              <el-input v-model="workbench.promptForm.promptVersion" placeholder="例如 template-v1" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="状态">
              <el-select v-model="workbench.promptForm.status">
                <el-option label="active" value="active" />
                <el-option label="inactive" value="inactive" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
        <el-form label-position="top">
          <el-form-item label="Prompt 模板">
            <el-input v-model="workbench.promptForm.promptTemplate" type="textarea" :rows="8" class="quant-code-input" />
          </el-form-item>
        </el-form>
        <el-form label-position="top">
          <el-form-item label="变更说明">
            <el-input v-model="workbench.promptForm.changeNote" placeholder="说明这次口径调整了什么。" />
          </el-form-item>
        </el-form>
        <div class="quant-actions">
          <el-button type="primary" :icon="Setting" @click="workbench.savePromptTemplate" :loading="workbench.loading.savingPrompt">保存模板</el-button>
          <el-button plain @click="workbench.resetPromptForm">重置</el-button>
          <el-button v-if="workbench.promptForm.id" type="danger" plain @click="workbench.deleteSelectedPrompt">删除</el-button>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>测试报告</h2>
          <p>报告由结构化 bundle 驱动，当前先做本地模板化输出，方便校验契约是否稳定。</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="VideoPlay" @click="workbench.generateReportFromRun()" :loading="workbench.loading.generatingReport">基于当前执行记录生成</el-button>
          <el-button :icon="RefreshRight" @click="workbench.loadReports" :loading="workbench.loading.reports">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="workbench.reports"
        stripe
        height="240"
        class="quant-table"
        @row-click="openReport"
        :row-class-name="({ row }) => row.id === workbench.selectedReportId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="trade_date" label="交易日" width="110" />
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="prompt_version" label="Prompt 版本" width="130" />
        <el-table-column prop="created_at" label="生成时间" min-width="170" />
      </el-table>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>报告正文</span>
          <span class="quant-muted">{{ workbench.selectedReport?.title || '先选一份报告' }}</span>
        </div>
        <el-input
          :model-value="workbench.selectedReport?.final_markdown || ''"
          type="textarea"
          :rows="14"
          readonly
          class="quant-code-input"
        />
      </div>

      <div class="quant-run-summary quant-section-gap">
        <div v-for="card in workbench.reportContractCards" :key="card.title" class="quant-run-summary__metric">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
        </div>
      </div>

      <div class="quant-grid quant-grid--report-contract quant-section-gap">
        <div>
          <div class="quant-mini-section__title">
            <span>AnalysisBundle</span>
          </div>
          <el-input
            :model-value="JSON.stringify(workbench.selectedReportBundle, null, 2)"
            type="textarea"
            :rows="10"
            readonly
            class="quant-code-input"
          />
        </div>
        <div>
          <div class="quant-mini-section__title">
            <span>ReportDraft</span>
          </div>
          <el-input
            :model-value="JSON.stringify(workbench.selectedReportDraft, null, 2)"
            type="textarea"
            :rows="10"
            readonly
            class="quant-code-input"
          />
        </div>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>生成元信息</span>
          <span class="quant-muted">{{ workbench.selectedReportMeta?.model_name || 'template-engine' }}</span>
        </div>
        <el-input
          :model-value="JSON.stringify(workbench.selectedReportMeta, null, 2)"
          type="textarea"
          :rows="5"
          readonly
          class="quant-code-input"
        />
      </div>
    </section>

    <section class="quant-panel quant-panel--full">
      <div class="quant-panel__header">
        <div>
          <h2>股票记忆库</h2>
          <p>参考 Markdown-first 的记忆管理思路，按股票维护一份可审阅的长期记忆文本，便于后续召回和人工检查。</p>
        </div>
        <div class="quant-toolbar">
          <el-button type="primary" @click="workbench.curateMemoryNow()" :loading="workbench.loading.curatingMemory">梳理当前记忆</el-button>
          <el-button :icon="RefreshRight" @click="workbench.loadMemoryFiles" :loading="workbench.loading.memoryFiles">刷新</el-button>
        </div>
      </div>

      <div class="quant-grid quant-grid--memory">
        <div>
          <el-table
            :data="workbench.memoryFiles"
            stripe
            height="320"
            class="quant-table"
            @row-click="openMemory"
            :row-class-name="({ row }) => row.symbol === workbench.selectedMemorySymbol ? 'quant-row--active' : ''"
          >
            <el-table-column prop="symbol" label="标的" min-width="120" />
            <el-table-column prop="updated_at" label="更新时间" min-width="180" />
            <el-table-column label="操作" width="92">
              <template #default="{ row }">
                <el-button text @click.stop="workbench.curateMemoryNow(row.symbol)">重整</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div>
          <div class="quant-mini-section__title">
            <span>记忆正文</span>
            <span class="quant-muted">{{ workbench.selectedMemoryDetail?.symbol || '先选一只股票' }}</span>
          </div>
          <div class="quant-run-summary">
            <div v-for="card in workbench.memorySummaryCards" :key="card.title" class="quant-run-summary__metric">
              <span>{{ card.title }}</span>
              <strong>{{ card.value }}</strong>
            </div>
          </div>
          <div v-if="workbench.memoryFocusLines.length" class="quant-mini-list quant-section-gap">
            <div v-for="line in workbench.memoryFocusLines" :key="line" class="quant-mini-item">
              {{ line }}
            </div>
          </div>
          <div class="quant-mini-section__title quant-section-gap">
            <span>文件路径</span>
            <span class="quant-muted">{{ workbench.selectedMemoryDetail?.path || '--' }}</span>
          </div>
          <el-input
            :model-value="workbench.selectedMemoryDetail?.content || ''"
            type="textarea"
            :rows="18"
            readonly
            class="quant-code-input"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { RefreshRight, Setting, VideoPlay } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()

const openReport = async (row: { id: number }) => {
  await workbench.loadReportDetail(row.id)
}

const openMemory = async (row: { symbol: string }) => {
  await workbench.loadMemoryDetail(row.symbol)
}
</script>
