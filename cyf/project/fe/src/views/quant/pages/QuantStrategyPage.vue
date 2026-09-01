<template>
  <div class="strategy-ide">
    <!-- 编辑器（左侧占主列） -->
    <section class="quant-panel strategy-ide__editor">
      <div class="quant-panel__header">
        <div>
          <h2>{{ ide.form.id ? '编辑策略' : '新建策略' }}</h2>
          <p>{{ workbench.selectedStrategy ? `当前策略：${workbench.selectedStrategy.name}` : '还没保存；模板可一键回填。' }}</p>
        </div>
        <div class="strategy-ide__toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadStrategies" :loading="workbench.loading.strategies">刷新</el-button>
          <el-button :icon="Document" plain @click="jsonDrawerRef?.show()">查看 JSON</el-button>
          <el-date-picker
            v-model="executeDate"
            type="date"
            value-format="YYYY-MM-DD"
            size="default"
            placeholder="执行日期（默认今天）"
            :clearable="true"
            class="strategy-ide__exec-date"
          />
          <el-button type="primary" :icon="VideoPlay" @click="executeAndOpenRuns" :loading="workbench.loading.runningStrategy">执行策略</el-button>
        </div>
      </div>

      <div class="strategy-ide__form">
        <div class="strategy-ide__form-row">
          <el-form label-position="top" class="strategy-ide__name">
            <el-form-item label="策略名称">
              <el-input v-model="ide.form.name" placeholder="例如：放量突破观察" />
            </el-form-item>
          </el-form>
          <el-form label-position="top" class="strategy-ide__status">
            <el-form-item label="状态">
              <el-select v-model="ide.form.status">
                <el-option label="active" value="active" />
                <el-option label="inactive" value="inactive" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top" class="strategy-ide__signal">
            <el-form-item label="信号类型">
              <el-select :model-value="ide.form.rule_config.signal_type" @update:model-value="ide.setSignalType">
                <el-option label="buy 买入" value="buy" />
                <el-option label="sell 卖出" value="sell" />
                <el-option label="watch 观察" value="watch" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="策略描述">
            <el-input v-model="ide.form.description" type="textarea" :rows="2" placeholder="写清楚这条策略要观察什么。" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="股票池">
            <el-select
              v-model="ide.form.symbols"
              multiple
              filterable
              remote
              :remote-method="onSymbolSearch"
              collapse-tags
              collapse-tags-tooltip
              :loading="workbench.loading.symbolSearch"
              placeholder="为空时默认扫描当前交易日已有数据的全部标的"
              class="strategy-ide__symbols"
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
      </div>

      <div class="strategy-ide__ide">
        <!-- 模板栏 -->
        <div class="strategy-ide__templates">
          <div class="strategy-ide__panel-title">策略模板</div>
          <div class="strategy-ide__chips">
            <button
              v-for="t in ide.templates.value"
              :key="t.key"
              type="button"
              class="strategy-ide__chip"
              @click="onApplyTemplate(t)"
            >
              <strong>{{ t.title }}</strong>
              <span class="strategy-ide__chip-summary">{{ t.summary }}</span>
              <span class="strategy-ide__chip-composition">
                <span v-if="templateUsedIndicators(t).length" class="strategy-ide__chip-comp-row">
                  <span class="strategy-ide__chip-comp-label">指标</span>
                  <span
                    v-for="k in templateUsedIndicators(t)"
                    :key="k"
                    class="strategy-ide__chip-comp-tag"
                  >{{ k }}</span>
                </span>
                <span v-if="templateUsedOutputs(t).length" class="strategy-ide__chip-comp-row">
                  <span class="strategy-ide__chip-comp-label">输出</span>
                  <code
                    v-for="o in templateUsedOutputs(t)"
                    :key="o"
                    class="strategy-ide__chip-comp-code"
                  >{{ o }}</code>
                </span>
              </span>
            </button>
            <div v-if="!ide.templates.value.length && !ide.loading.meta" class="strategy-ide__chip-empty">
              暂无模板
            </div>
          </div>
        </div>

        <!-- 主体：指标面板 + 规则 + gate -->
        <div class="strategy-ide__panels">
          <div class="strategy-ide__panel strategy-ide__panel--palette">
            <IndicatorPalette :ide="ide" @insert="onInsertExpr" />
          </div>

          <div class="strategy-ide__panel strategy-ide__panel--rules">
            <div class="strategy-ide__panel-title">
              规则 ({{ ide.form.rule_config.rules.length }})
              <el-button size="small" type="primary" plain :icon="Plus" @click="onAddRule" class="strategy-ide__add-rule">添加规则</el-button>
            </div>

            <div v-if="!ide.form.rule_config.rules.length" class="strategy-ide__rules-empty">
              还没有规则。点上方模板快速开始，或手动添加。
            </div>

            <div class="strategy-ide__rules">
              <RuleRow
                v-for="rule in ide.form.rule_config.rules"
                :key="rule.id"
                :rule="rule"
                :meta="ide.expressionMeta.value"
                :result="findRuleResult(rule.id)"
                :expr-error="findRuleError(rule.id)"
                :indicator-outputs="ide.expandedIndicatorOutputs.value"
                @update="(p) => ide.updateRule(rule.id, p)"
                @remove="ide.removeRule(rule.id)"
              />
            </div>

            <ExpressionHelp @insert="onInsertExpr" />

            <div class="strategy-ide__gate">
              <GateEditor
                :gate="ide.form.rule_config.gate"
                @update="onGateUpdate"
              />
            </div>

            <div class="strategy-ide__score">
              <span>最低分数</span>
              <el-input-number
                :model-value="ide.form.rule_config.min_score"
                :min="0"
                :step="0.5"
                size="small"
                @update:model-value="(v: number | undefined) => ide.setMinScore(Number(v) || 0)"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="strategy-ide__actions">
        <el-button type="primary" :icon="Setting" @click="onSave" :loading="saving">{{ ide.form.id ? '保存更新' : '创建策略' }}</el-button>
        <el-button plain @click="onReset">重置表单</el-button>
        <el-button v-if="ide.form.id" type="danger" plain @click="onDelete">删除策略</el-button>
      </div>

      <StrategyJsonDrawer ref="jsonDrawerRef" :model-value="ide.form.rule_config" @update:model-value="onJsonUpdate" />
    </section>

    <!-- 右侧栏：试算（顶）+ 策略清单（紧跟下方） -->
    <aside class="strategy-ide__right">
      <section class="quant-panel strategy-ide__dryrun">
        <DryRunPanel :ide="ide" :workbench="workbench" />
      </section>

      <section class="quant-panel strategy-ide__list">
        <div class="quant-panel__header">
          <div>
            <h2>策略清单</h2>
            <p>点行 → 左侧编辑器回填。</p>
          </div>
          <el-button plain @click="onReset">新建策略</el-button>
        </div>

        <el-table
          :data="workbench.strategies"
          stripe
          :height="listHeight"
          class="quant-table strategy-ide__list-table"
          @row-click="onSelect"
          :row-class-name="({ row }: { row: any }) => row.id === workbench.selectedStrategyId ? 'quant-row--active' : ''"
        >
          <el-table-column label="策略" min-width="200">
            <template #default="{ row }: { row: any }">
              <div class="strategy-ide__list-name" :title="row.description || row.name">
                <strong>{{ row.name }}</strong>
                <span class="strategy-ide__list-desc">{{ row.description || '—' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }: { row: any }">
              <el-tag size="small" :type="workbench.strategyStatusTag(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="池/规则" width="84">
            <template #default="{ row }: { row: any }">
              <div class="strategy-ide__list-stats">
                <span>池 {{ row.symbols?.length || 0 }}</span>
                <span>规则 {{ Array.isArray(row.rule_config?.rules) ? row.rule_config.rules.length : 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新" width="100">
            <template #default="{ row }: { row: any }">{{ formatUpdatedAt(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="68" align="center">
            <template #default="{ row }: { row: any }">
              <el-button
                size="small"
                type="danger"
                plain
                circle
                :icon="Delete"
                @click.stop="confirmDelete(row)"
              />
            </template>
          </el-table-column>
        </el-table>
      </section>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Plus, RefreshRight, Setting, VideoPlay, Delete } from '@element-plus/icons-vue'

import { useQuantWorkbench } from '@/composables/useQuantWorkbench'
import { useStrategyIde } from '@/composables/useStrategyIde'
import { symbolLabel } from '@/composables/quant/format'
import { quantStrategyAPI } from '@/services/quantApi'

import IndicatorPalette from '../strategy/IndicatorPalette.vue'
import RuleRow from '../strategy/RuleRow.vue'
import ExpressionHelp from '../strategy/ExpressionHelp.vue'
import GateEditor from '../strategy/GateEditor.vue'
import DryRunPanel from '../strategy/DryRunPanel.vue'
import StrategyJsonDrawer from '../strategy/StrategyJsonDrawer.vue'

const router = useRouter()
const workbench = useQuantWorkbench()
const ide = useStrategyIde()
const jsonDrawerRef = ref<InstanceType<typeof StrategyJsonDrawer> | null>(null)
const saving = ref(false)
const executeDate = ref<string>(new Date().toISOString().slice(0, 10))

onMounted(async () => {
  await Promise.all([
    workbench.loadStrategies(),
    workbench.loadSymbols(),
    ide.loadMeta()
  ])
})

function onReset() {
  ide.resetForm()
}

function onSelect(strategy: any) {
  workbench.handleStrategySelect(strategy)
  ide.loadFromRecord({
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    status: strategy.status,
    symbols: strategy.symbols || [],
    rule_config: strategy.rule_config || {}
  })
}

function onApplyTemplate(tmpl: any) {
  ide.applyTemplate(tmpl)
}

function templateUsedIndicators(t: any): string[] {
  const declared = (t.rule_config?.indicators || []) as Array<{ key: string; params?: Record<string, any> }>
  return declared.map(i => i.key).filter((k, i, arr) => arr.indexOf(k) === i)
}

// 列表表格高度：右侧栏总高 - 试算面板预估高 - 头部 - gap；
// 用计算属性根据窗口高度动态算。
const listHeight = computed(() => {
  // 视口高 - 上层 nav (~52px) - 上下 padding*2 - 试算面板 ~440px
  const vh = typeof window !== 'undefined' ? window.innerHeight : 800
  const remaining = vh - 52 - 24 - 440
  return Math.max(220, remaining)
})

function formatUpdatedAt(s: string | undefined): string {
  if (!s) return '—'
  // 显示 MM-DD HH:MM 紧凑格式
  try {
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return s.slice(0, 16)
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${m}-${day} ${hh}:${mm}`
  } catch {
    return s.slice(0, 16)
  }
}

async function confirmDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除策略 "${row.name}"？会连同其运行记录一起删除。`,
      '删除策略',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await quantStrategyAPI.delete(row.id)
    ElMessage.success(`已删除：${row.name}`)
    if (ide.form.id === row.id) {
      ide.resetForm()
      workbench.selectedStrategyId = null
    }
    await Promise.all([workbench.loadStrategies(), workbench.loadOverview()])
  } catch (err: any) {
    ElMessage.error(err?.message || '删除策略失败')
  }
}

function templateUsedOutputs(t: any): string[] {
  const out = new Set<string>()
  for (const r of (t.rule_config?.rules || []) as Array<{ expr?: string }>) {
    const expr = String(r.expr || '')
    // 抓出所有标识符（简单正则：字母数字下划线），过滤掉 bar 字段 / 函数名 / 关键字
    const candidates = expr.match(/[A-Za-z_][A-Za-z0-9_]*/g) || []
    for (const tok of candidates) {
      if (['close', 'open', 'high', 'low', 'vol', 'amt', 'pct', 'turnover',
           'True', 'False', 'and', 'or', 'not', 'prev', 'ref', 'avg',
           'abs', 'min', 'max', 'cross_up', 'cross_down', 'any_', 'all_',
           'close_price', 'open_price', 'high_price', 'low_price',
           'volume', 'amount', 'pct_change', 'turnover_rate'].includes(tok)) continue
      out.add(tok)
    }
  }
  return Array.from(out)
}

function onAddRule() {
  ide.addRule()
}

function onInsertExpr(text: string) {
  // 帮用户把模板/示例片段拼到第一条规则；前后补空格（单次更新避免连续 emit 读到旧值）
  if (!ide.form.rule_config.rules.length) {
    ide.addRule({ expr: text, label: '新规则' })
    return
  }
  const first = ide.form.rule_config.rules[0]
  const cur = first.expr || ''
  const sep = cur && !/[\s(]$/.test(cur) ? ' ' : ''
  let next = `${cur}${sep}${text}`
  if (!next.endsWith(' ')) next += ' '
  ide.updateRule(first.id, { expr: next })
}

function onGateUpdate(patch: any) {
  ide.setGate(patch.mode, patch.expr)
}

function onJsonUpdate(v: any) {
  // 抽屉里改 JSON 后，应用为 form.rule_config；保持 gate / indicators 结构
  ide.form.rule_config = {
    ...ide.form.rule_config,
    version: 2,
    signal_type: v.signal_type || ide.form.rule_config.signal_type,
    gate: v.gate || ide.form.rule_config.gate,
    min_score: Number(v.min_score) || 0,
    indicators: Array.isArray(v.indicators) ? v.indicators : [],
    rules: Array.isArray(v.rules) ? v.rules : []
  }
}

function onSymbolSearch(keyword: string) {
  workbench.searchSymbols(keyword)
}

function findRuleResult(ruleId: string) {
  const dry = ide.dryRun.value
  if (!dry) return null
  for (let i = dry.results.length - 1; i >= 0; i--) {
    const rr = dry.results[i].rule_results.find(r => r.id === ruleId)
    if (rr) return rr
  }
  return null
}

function findRuleError(ruleId: string) {
  return ide.validation.value?.rules.find(r => r.id === ruleId)?.error || ''
}

async function onSave() {
  if (!ide.form.name.trim()) {
    ElMessage.warning('策略名称不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: ide.form.name.trim(),
      description: ide.form.description.trim(),
      status: ide.form.status,
      symbols: ide.form.symbols,
      rule_config: ide.form.rule_config
    }
    if (ide.form.id) {
      await quantStrategyAPI.update({ id: ide.form.id, ...payload })
      ElMessage.success('策略已更新')
    } else {
      await quantStrategyAPI.create(payload)
      ElMessage.success('策略已创建')
    }
    await Promise.all([workbench.loadStrategies(), workbench.loadOverview()])
  } catch (err: any) {
    ElMessage.error(err?.message || '保存策略失败')
  } finally {
    saving.value = false
  }
}

async function onDelete() {
  if (!ide.form.id) {
    ElMessage.info('先选中一个策略再删除')
    return
  }
  try {
    await ElMessageBox.confirm('删除策略会连同它的运行记录一起删除，继续吗？', '删除策略', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await quantStrategyAPI.delete(ide.form.id)
    ElMessage.success('策略已删除')
    ide.resetForm()
    workbench.selectedStrategyId = null
    await Promise.all([workbench.loadStrategies(), workbench.loadOverview()])
  } catch (err: any) {
    ElMessage.error(err?.message || '删除策略失败')
  }
}

async function executeAndOpenRuns() {
  if (!ide.form.id) {
    ElMessage.info('请先保存策略再执行')
    return
  }
  workbench.loading.runningStrategy = true
  try {
    await quantStrategyAPI.run({
      strategy_id: ide.form.id,
      trade_date: executeDate.value || undefined,
      save_all_signals: true
    })
    ElMessage.success(`策略执行完成（交易日：${executeDate.value || '最新有数据日'}）`)
    router.push('/quant/runs')
  } catch (err: any) {
    ElMessage.error(err?.message || '执行策略失败')
  } finally {
    workbench.loading.runningStrategy = false
  }
}
</script>

<style scoped>
.strategy-ide {
  display: grid;
  /* 左：编辑器（铺满大）｜右：flex column wrapper（试算 + 列表紧跟） */
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 14px;
  align-items: start;
}
.strategy-ide__editor { min-width: 0; }
.strategy-ide__right {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  position: sticky;
  top: 14px;
}
.strategy-ide__dryrun,
.strategy-ide__list { min-width: 0; }
.strategy-ide__list-table :deep(.el-table__cell) {
  padding: 6px 0;
}
.strategy-ide__list-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.strategy-ide__list-name strong {
  color: var(--q-ink);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.strategy-ide__list-desc {
  color: var(--q-muted);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}
.strategy-ide__list-stats {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--q-muted);
  font-family: var(--q-mono);
  font-size: 11px;
  line-height: 1.4;
}
.strategy-ide__toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.strategy-ide__exec-date { width: 170px; }
.strategy-ide__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.strategy-ide__form-row {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 140px 160px;
  gap: 10px;
}
.strategy-ide__name,
.strategy-ide__status,
.strategy-ide__signal {
  min-width: 0;
}
.strategy-ide__symbols {
  width: 100%;
}
.strategy-ide__ide {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.strategy-ide__templates {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.strategy-ide__panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--q-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.strategy-ide__add-rule {
  font-size: 11px;
}
.strategy-ide__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.strategy-ide__chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  border: 1px solid var(--q-line);
  border-radius: 6px;
  background: var(--q-surface);
  cursor: pointer;
  transition: background 120ms;
  text-align: left;
}
.strategy-ide__chip:hover {
  background: var(--q-surface-2);
}
.strategy-ide__chip strong {
  color: var(--q-ink);
  font-size: 13px;
}
.strategy-ide__chip-summary {
  color: var(--q-muted);
  font-size: 11px;
  line-height: 1.4;
}
.strategy-ide__chip-composition {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}
.strategy-ide__chip-comp-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.strategy-ide__chip-comp-label {
  color: var(--q-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin-right: 2px;
}
.strategy-ide__chip-comp-tag {
  padding: 1px 6px;
  border: 1px solid var(--q-line);
  border-radius: 3px;
  background: var(--q-surface);
  color: var(--q-ink);
  font-size: 10px;
}
.strategy-ide__chip-comp-code {
  padding: 1px 4px;
  border: 1px solid var(--q-line);
  border-radius: 3px;
  background: var(--q-surface-2);
  color: var(--q-copper);
  font-family: var(--q-mono);
  font-size: 10px;
}
.strategy-ide__chip-empty {
  color: var(--q-muted);
  font-size: 12px;
  font-style: italic;
}
.strategy-ide__panels {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
}
.strategy-ide__panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.strategy-ide__panel--rules {
  min-width: 0;
}
.strategy-ide__rules-empty {
  padding: 18px;
  color: var(--q-muted);
  font-size: 12px;
  text-align: center;
  border: 1px dashed var(--q-line);
  border-radius: 6px;
}
.strategy-ide__rules {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.strategy-ide__gate {
  padding-top: 4px;
  border-top: 1px solid var(--q-line);
}
.strategy-ide__score {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--q-muted);
  font-size: 12px;
}
.strategy-ide__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 1080px) {
  .strategy-ide {
    grid-template-columns: 1fr;
  }
  .strategy-ide__right { position: static; }
}
@media (max-width: 768px) {
  .strategy-ide__form-row { grid-template-columns: 1fr; }
  .strategy-ide__panels { grid-template-columns: 1fr; }
}
</style>