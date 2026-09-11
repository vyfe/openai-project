<script setup lang="ts">
/**
 * 报告生成 IDE（不落库预览）子组件。
 * 从 QuantAiMemoryPage 抽出来（2026-09-03 重构），让 IDE 区可被策略页 / 调度页复用。
 *
 * 用法：
 *   <ReportPreviewIde />  // 默认从 useQuantWorkbench 拿数据
 *
 * 交互通过 workbench.previewReportDraft 调后端 /report/preview。
 */
import { computed, ref } from 'vue'
import { VideoPlay } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()

// IDE 表单状态
const reportIdeRunId = ref<number | null>(null)
const reportIdePromptTemplateId = ref<number | null>(null)
const reportIdeModelName = ref('')
const reportIdeLlmEnabled = ref(true)

const previewStatusLabel = computed(() => {
  const status = workbench.reportPreview?.meta?.llm_status
  if (!status) return '未生成'
  const mapping: Record<string, string> = {
    success: 'LLM 改写成功',
    fallback_contract: '合同违约 → 兜底模板',
    fallback_call: 'LLM 调用失败 → 兜底模板',
    disabled: '未启用 LLM',
  }
  return mapping[status] || status
})

const previewStatusTagType = computed<'success' | 'warning' | 'info' | 'danger'>(() => {
  const status = workbench.reportPreview?.meta?.llm_status
  if (status === 'success') return 'success'
  if (status?.startsWith('fallback')) return 'warning'
  if (status === 'disabled') return 'info'
  return 'info'
})

const ideRunLabel = (run: any) => {
  const strategy = run.summary?.strategy_name || workbench.resolveStrategyName(run.strategy_id) || '未知策略'
  const ratio = `${run.signals_total}/${run.symbols_total}`
  return `#${run.id} · ${run.trade_date} · ${strategy} · ${ratio} · ${workbench.statusLabel(run.status)}`
}

const runReportPreview = async () => {
  const explicitRunId = reportIdeRunId.value && reportIdeRunId.value > 0 ? reportIdeRunId.value : undefined
  await workbench.previewReportDraft(explicitRunId, {
    llm_enabled: reportIdeLlmEnabled.value,
    prompt_template_id: reportIdePromptTemplateId.value,
    model_name: reportIdeModelName.value.trim() || undefined,
  })
}

const clearReportPreview = () => {
  workbench.clearReportPreview()
}
</script>

<template>
  <div class="quant-mini-section">
    <div class="quant-mini-section__title">
      <span>报告生成 IDE（不落库预览）</span>
      <span class="quant-muted">
        run:
        <el-select
          v-model="reportIdeRunId"
          placeholder="从下拉选一条执行记录，留空用 workbench 当前选中的"
          filterable
          clearable
          size="small"
          class="quant-run-picker"
        >
          <el-option
            v-for="run in workbench.strategyRuns"
            :key="run.id"
            :label="ideRunLabel(run)"
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
      </span>
    </div>
    <div class="quant-form-grid quant-form-grid--three">
      <el-form label-position="top">
        <el-form-item label="Prompt 模板（可选）">
          <el-select
            v-model="reportIdePromptTemplateId"
            clearable
            filterable
            placeholder="留空走 latest_prompt 自动选"
          >
            <el-option
              v-for="item in workbench.promptTemplates"
              :key="item.id"
              :label="`${item.prompt_version} · ${item.template_name}${item.model_name ? ' · ' + item.model_name : ''}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <el-form label-position="top">
        <el-form-item label="覆盖模型（可选）">
          <el-input v-model="reportIdeModelName" placeholder="留空走模板默认" />
        </el-form-item>
      </el-form>
      <el-form label-position="top">
        <el-form-item label="AI 改写">
          <el-switch v-model="reportIdeLlmEnabled" active-text="启用 LLM" inactive-text="走模板" />
        </el-form-item>
      </el-form>
    </div>
    <div class="quant-actions">
      <el-button type="primary" :icon="VideoPlay" :loading="workbench.loading.generatingReport" @click="runReportPreview">生成预览</el-button>
      <el-button plain @click="clearReportPreview">清空预览</el-button>
    </div>
    <div v-if="workbench.reportPreview" class="quant-mini-section__title quant-section-gap">
      <span>预览 Markdown</span>
      <span class="quant-muted">
        状态：<el-tag size="small" :type="previewStatusTagType">{{ previewStatusLabel }}</el-tag>
        模型：<code>{{ workbench.reportPreview.meta?.model_name || '--' }}</code>
      </span>
    </div>
    <el-input
      v-if="workbench.reportPreview"
      :model-value="workbench.reportPreview.markdown"
      type="textarea"
      :rows="14"
      readonly
      class="quant-code-input"
    />
    <div v-if="workbench.reportPreview" class="quant-grid quant-grid--report-contract quant-section-gap">
      <div>
        <div class="quant-mini-section__title">
          <span>AnalysisBundle</span>
        </div>
        <el-input
          :model-value="JSON.stringify(workbench.reportPreview.bundle, null, 2)"
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
          :model-value="JSON.stringify(workbench.reportPreview.draft, null, 2)"
          type="textarea"
          :rows="10"
          readonly
          class="quant-code-input"
        />
      </div>
    </div>
  </div>
</template>
