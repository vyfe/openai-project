<template>
  <div class="rule-row" :class="{ 'is-passed': lastResult?.passed, 'is-failed': lastResult && !lastResult.passed }">
    <div class="rule-row__head">
      <el-input
        v-model="localLabel"
        size="small"
        placeholder="规则名（例：站上5日线）"
        class="rule-row__label"
        @update:model-value="emitLabel"
      />
      <el-input-number
        v-model="localWeight"
        :min="0"
        :step="0.5"
        size="small"
        class="rule-row__weight"
        @update:model-value="emitWeight"
      />
      <el-tag v-if="lastResult" :type="lastResult.passed ? 'success' : 'info'" effect="plain" size="small" class="rule-row__status">
        {{ lastResult.passed ? '通过' : '未通过' }}
        <span v-if="formatValue(lastResult.value)" class="rule-row__status-value">
          · {{ formatValue(lastResult.value) }}
        </span>
      </el-tag>
      <el-button :icon="Delete" circle size="small" plain type="danger" @click="$emit('remove')" />
    </div>

    <ExpressionInput
      :model-value="rule.expr"
      :meta="meta"
      :error="exprError"
      :rows="3"
      placeholder="例如：close > ma_5"
      @update:model-value="emitExpr"
    />

    <!-- AI 自然语言生成表达式 -->
    <div class="rule-row__ai">
      <el-input
        v-model="aiPrompt"
        type="textarea"
        :rows="2"
        placeholder="用一句话描述这条规则（例：收盘价站上 5 日线，且成交量大于近 5 根均量）"
        class="rule-row__ai-input"
      />
      <div class="rule-row__ai-actions">
        <el-select
          v-model="aiModel"
          size="small"
          class="rule-row__ai-model"
          title="选择生成表达式所用模型"
        >
          <el-option
            v-for="opt in aiModelOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button
          type="primary"
          plain
          :icon="MagicStick"
          :loading="aiLoading"
          @click="onAiGenerate"
        >
          {{ aiLoading ? '生成中…' : 'AI 生成表达式' }}
        </el-button>
        <el-button v-if="aiError" plain @click="clearAiError">清除错误</el-button>
        <span v-if="aiError" class="rule-row__ai-error">{{ aiError }}</span>
      </div>
    </div>

    <details class="rule-row__quick">
      <summary class="rule-row__quick-title">
        <el-icon><Plus /></el-icon>
        <span>快速插入（点 chip 直接填到表达式里）</span>
      </summary>

      <div class="rule-row__chips">
        <div class="rule-row__chip-group">
          <span class="rule-row__chip-label">字段</span>
          <el-tag
            v-for="f in barFieldsWithLabel"
            :key="f.name"
            size="small"
            effect="plain"
            class="rule-row__chip rule-row__chip--bare"
            :title="`点击插入 ${f.name}`"
            @click="insertAtCursor(f.name)"
          >{{ f.label }}</el-tag>
        </div>

        <div class="rule-row__chip-group">
          <span class="rule-row__chip-label">算子</span>
          <el-tag
            v-for="op in operators"
            :key="op"
            size="small"
            effect="plain"
            type="warning"
            class="rule-row__chip"
            @click="insertAtCursorWithSpace(op)"
          >{{ op }}</el-tag>
        </div>

        <div class="rule-row__chip-group">
          <span class="rule-row__chip-label">函数（中英对照）</span>
          <el-tag
            v-for="fn in functionsForChip"
            :key="fn.name"
            size="small"
            effect="plain"
            type="info"
            class="rule-row__chip"
            :title="fn.template"
            @click="insertAtCursorWithSpace(fn.template)"
          >
            <span class="rule-row__chip-name">{{ fn.label }}</span>
            <span class="rule-row__chip-aside">{{ fn.name }}</span>
          </el-tag>
        </div>

        <div v-if="indicatorOutputs.length" class="rule-row__chip-group">
          <span class="rule-row__chip-label">
            已启用指标输出
            <span class="rule-row__chip-hint">（上方"指标"面板勾选后自动出现）</span>
          </span>
          <el-tag
            v-for="o in indicatorOutputs"
            :key="o"
            size="small"
            effect="plain"
            type="success"
            class="rule-row__chip"
            @click="insertAtCursor(o)"
          >{{ o }}</el-tag>
        </div>

        <div v-if="!indicatorOutputs.length" class="rule-row__chip-empty">
          上方"指标"面板里勾选指标后，输出名会出现在这里——模板里的 ma_5 / vol_ratio_5 就是这样组合出来的。
        </div>

        <!-- 阈值输入 -->
        <div class="rule-row__threshold">
          <span class="rule-row__chip-label">阈值</span>
          <el-input-number
            v-model="thresholdValue"
            :step="0.1"
            size="small"
            class="rule-row__threshold-input"
            placeholder="数字"
          />
          <el-button size="small" type="primary" plain @click="insertThreshold">插入</el-button>
          <el-button size="small" plain @click="clearExpr" title="清空表达式">清空</el-button>
        </div>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Delete, MagicStick, Plus } from '@element-plus/icons-vue'
import ExpressionInput from './ExpressionInput.vue'
import { quantMetaAPI, quantStrategyAPI } from '@/services/quantApi'
import type { ExpressionMeta, IndicatorSpec, RuleV2 } from '@/composables/quant/strategyIdeTypes'

type DryRunRuleResult = { id: string; label: string; passed: boolean; value: any }

// bar 字段中文对照（点击插入英文变量名）
const barFieldsWithLabel = [
  { label: '收盘价', name: 'close' },
  { label: '开盘价', name: 'open' },
  { label: '最高价', name: 'high' },
  { label: '最低价', name: 'low' },
  { label: '成交量', name: 'volume' },
  { label: '成交额', name: 'amount' },
  { label: '涨跌幅(%)', name: 'pct_change' },
  { label: '换手率(%)', name: 'turnover_rate' }
]

const operators = ['>', '>=', '<', '<=', '==', '!='] as const

const functionsForChip = [
  { name: 'prev', label: '前 1 根', template: 'prev(${x})' },
  { name: 'ref', label: '前 n 根', template: 'ref(${x}, ${n})' },
  { name: 'avg', label: '近 n 根均值', template: 'avg(${x}, ${n})' },
  { name: 'cross_up', label: '上穿', template: 'cross_up(${a}, ${b})' },
  { name: 'cross_down', label: '下穿', template: 'cross_down(${a}, ${b})' },
  { name: 'abs', label: '绝对值', template: 'abs(${x})' },
  { name: 'min', label: '最小值', template: 'min(${a}, ${b})' },
  { name: 'max', label: '最大值', template: 'max(${a}, ${b})' }
]

const props = defineProps<{
  rule: RuleV2
  meta: ExpressionMeta
  result?: DryRunRuleResult | null
  exprError?: string
  indicatorOutputs?: string[]
}>()

const emit = defineEmits<{
  'update': [patch: Partial<RuleV2>]
  'remove': []
}>()

const localLabel = ref(props.rule.label || '')
const localWeight = ref<number>(props.rule.weight ?? 1)
const thresholdValue = ref<number | undefined>(undefined)

// AI 生成
const aiPrompt = ref('')
const aiLoading = ref(false)
const aiError = ref('')
// 模型下拉项：luna 是历史默认；terra / sol 是新增可选模型。
// 后端 /strategy/llm_generate_expr 不做 allowlist，前端传啥就透传给 OpenAI client。
const aiModelOptions = [
  { value: 'gpt-5.6-luna', label: 'gpt-5.6-luna（默认）' },
  { value: 'gpt-5.6-terra', label: 'gpt-5.6-terra' },
  { value: 'gpt-5.6-sol', label: 'gpt-5.6-sol' }
] as const
const aiModel = ref<string>('gpt-5.6-luna')
// 缓存指标 catalog（来自 /quant/meta/indicators），用于动态把已启用的 output 名
// 反推成 registry key 喂给 LLM。避免硬编码前缀白名单遗漏新指标（如 top_divergence）。
const indicatorCatalog = ref<IndicatorSpec[]>([])

onMounted(async () => {
  try {
    const res: any = await quantMetaAPI.indicators()
    if (res?.data) indicatorCatalog.value = res.data as IndicatorSpec[]
  } catch {
    // catalog 拉取失败也不阻塞 AI 生成；onAiGenerate 会回退到宽松匹配
  }
})

async function onAiGenerate() {
  const desc = aiPrompt.value.trim()
  if (!desc) {
    aiError.value = '请先写一句策略描述'
    return
  }
  aiError.value = ''
  aiLoading.value = true
  try {
    // 动态从 catalog 反推：把 indicatorOutputs（已展开的具体名，如 rsi_14 / top_divergence）
    // 反向匹配到所属 registry key（rsi / top_structure），确保 LLM 拿到的指标列表
    // 永远跟后端 schema 同步。
    const indicatorKeys = new Set<string>()
    const outputs = props.indicatorOutputs || []
    if (indicatorCatalog.value.length > 0) {
      for (const outName of outputs) {
        let matched = false
        for (const spec of indicatorCatalog.value) {
          for (const o of spec.outputs) {
            if (!o.name.includes('{')) {
              // 字面量：直接 === 比对（top_divergence 等）
              if (o.name === outName) {
                indicatorKeys.add(spec.key)
                matched = true
                break
              }
            } else {
              // 模板（ma_{window}）：把 {xxx} 换成 .* 后正则匹配 ma_5 / rsi_14 等。
              const re = new RegExp('^' + o.name.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\\\{[a-zA-Z_]+\\\}/g, '.*') + '$')
              if (re.test(outName)) {
                indicatorKeys.add(spec.key)
                matched = true
                break
              }
            }
          }
          if (matched) break
        }
      }
    }
    // catalog 缺失或输出名未被任何 spec 覆盖时，把 indicatorOutputs 原样回传
    // —— 后端 _v2_resolve_indicator_keys 会按字面 / 前缀再次解析，最坏情况是空集合。
    if (indicatorKeys.size === 0) {
      for (const outName of outputs) indicatorKeys.add(outName)
    }
    const res: any = await quantStrategyAPI.llmGenerateExpr({
      description: desc,
      indicator_keys: indicatorKeys,
      model: aiModel.value
    })
    const data = res.data || {}
    if (data.error) {
      aiError.value = data.error
    } else if (data.expr) {
      emitExpr(data.expr)
    } else {
      aiError.value = '大模型未返回表达式'
    }
  } catch (err: any) {
    aiError.value = err?.message || '调用大模型失败'
  } finally {
    aiLoading.value = false
  }
}

function clearAiError() {
  aiError.value = ''
}

watch(() => props.rule.label, (v) => { localLabel.value = v || '' })
watch(() => props.rule.weight, (v) => { localWeight.value = v ?? 1 })

const lastResult = computed(() => props.result)
const indicatorOutputs = computed(() => props.indicatorOutputs || [])

function emitLabel(v: string) { emit('update', { label: v }) }
function emitWeight(v: number | undefined) { emit('update', { weight: Number(v) || 1 }) }
function emitExpr(v: string) { emit('update', { expr: v }) }

function formatValue(v: any): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') {
    if (Math.abs(v) >= 100) return v.toFixed(2)
    return v.toFixed(4)
  }
  return String(v)
}

function appendToken(token: string, opts: { trailingSpace?: boolean } = {}) {
  const cur = props.rule.expr || ''
  let prefix = cur
  if (prefix && !/[\s(+\-*/%<>=!]$/.test(prefix)) {
    prefix += ' '
  }
  let result = `${prefix}${token}`
  // 算子 / 函数 / 阈值后面补一个空格，方便下次插入；用户敲字时光标正好停在这。
  if (opts.trailingSpace && !result.endsWith(' ')) {
    result += ' '
  }
  emitExpr(result)
}

function insertAtCursor(token: string) {
  appendToken(token)
}

function insertAtCursorWithSpace(token: string) {
  // 关键：合并成一次 emit；连续 emit 会读到过时的 props.rule.expr。
  appendToken(token, { trailingSpace: true })
}

function insertThreshold() {
  if (thresholdValue.value === undefined || thresholdValue.value === null) return
  appendToken(String(thresholdValue.value), { trailingSpace: true })
}

function clearExpr() {
  emitExpr('')
}
</script>

<style scoped>
.rule-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--q-line);
  border-radius: 6px;
  background: var(--q-surface);
  transition: border-color 120ms;
}
.rule-row.is-passed { border-color: color-mix(in srgb, var(--q-green) 60%, transparent); }
.rule-row.is-failed { border-color: var(--q-line); }
.rule-row__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rule-row__label { flex: 1; max-width: 220px; }
.rule-row__weight { width: 90px; }
.rule-row__status { font-family: var(--q-mono); }
.rule-row__status-value { margin-left: 2px; color: var(--q-muted); }

.rule-row__ai {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  border: 1px dashed var(--q-copper);
  border-radius: 6px;
  background: color-mix(in srgb, var(--q-copper) 6%, var(--q-surface));
}
.rule-row__ai-input :deep(.el-textarea__inner) {
  font-size: 12px;
  line-height: 1.5;
  background: var(--q-surface);
}
.rule-row__ai-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.rule-row__ai-model {
  width: 180px;
}
.rule-row__ai-error {
  color: var(--q-red);
  font-size: 12px;
  font-family: var(--q-mono);
}

.rule-row__quick {
  border: 1px solid var(--q-line);
  border-radius: 6px;
  background: var(--q-surface-2);
}
.rule-row__quick-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  color: var(--q-muted);
  font-size: 12px;
  list-style: none;
}
.rule-row__quick-title::-webkit-details-marker { display: none; }
.rule-row__quick-title:hover { color: var(--q-ink); }
.rule-row__chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 10px 10px;
  border-top: 1px solid var(--q-line);
}
.rule-row__chip-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
}
.rule-row__chip-label {
  width: 96px;
  color: var(--q-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.rule-row__chip-hint {
  color: var(--q-line-strong);
  font-size: 10px;
  font-weight: normal;
  letter-spacing: 0;
  margin-left: 2px;
}
.rule-row__chip {
  font-family: var(--q-mono);
  font-size: 11px;
  cursor: pointer;
}
.rule-row__chip--bare {
  background: var(--q-surface);
  border-color: var(--q-line-strong);
}
.rule-row__chip-name {
  color: var(--q-ink);
}
.rule-row__chip-aside {
  margin-left: 4px;
  color: var(--q-muted);
  font-family: var(--q-mono);
  font-size: 10px;
}
.rule-row__chip-empty {
  padding: 8px 10px;
  color: var(--q-muted);
  font-size: 11px;
  background: var(--q-surface);
  border: 1px dashed var(--q-line);
  border-radius: 4px;
  line-height: 1.5;
}
.rule-row__threshold {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 4px;
  border-top: 1px dashed var(--q-line);
}
.rule-row__threshold-input { width: 130px; }
@media (max-width: 768px) {
  .rule-row__chip-label { width: 100%; }
}
</style>