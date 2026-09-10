/**
 * useStrategyIde —— 策略 IDE 的状态管理。
 *
 * 单一职责：
 - 加载元数据（指标 catalog + 表达式函数 + 策略模板）
 - 管理 strategyForm（v2 rule_config）
 - debounced dry_run（默认 500ms）
 - validate（语法 + 变量）
 - 模板回填 / 重置 / 序列化为 JSON 字符串
 *
 * JSON 始终是 source of truth。外部组件可以通过 ruleConfigText 反向 setFormFromText 同步。
 */
import { computed, reactive, ref, watch } from 'vue'
import {
  quantMetaAPI,
  quantStrategyAPI
} from '@/services/quantApi'
import type {
  DryRunResponse,
  ExpressionMeta,
  IndicatorSpec,
  RuleConfigV2,
  StrategyTemplate,
  ValidationResult
} from './quant/strategyIdeTypes'

let _nextRuleSeq = 1
function newRuleId() {
  return `r${_nextRuleSeq++}`
}

export function useStrategyIde() {
  const indicators = ref<IndicatorSpec[]>([])
  const expressionMeta = ref<ExpressionMeta>({ bar_fields: [], functions: [] })
  const templates = ref<StrategyTemplate[]>([])

  const loading = reactive({
    meta: false,
    validate: false,
    dryRun: false
  })

  const form = reactive<{
    id: number | null
    name: string
    description: string
    status: 'active' | 'inactive'
    symbols: string[]
    rule_config: RuleConfigV2
  }>({
    id: null,
    name: '',
    description: '',
    status: 'active',
    symbols: [],
    rule_config: emptyV2()
  })

  const validation = ref<ValidationResult | null>(null)
  const dryRun = ref<DryRunResponse | null>(null)

  // 当前 dry_run 用的 symbol / 日期区间
  const dryRunParams = reactive({
    symbol: '000001.SZ',
    start_date: defaultStartDate(),
    end_date: defaultEndDate(),
    adjust_flag: 'qfq'
  })

  let dryRunTimer: number | null = null

  const ruleConfigText = computed({
    get: () => JSON.stringify(form.rule_config, null, 2),
    set: (text: string) => {
      try {
        const parsed = JSON.parse(text)
        if (parsed && typeof parsed === 'object') {
          form.rule_config = normalizeToV2(parsed)
        }
      } catch {
        // 解析失败保留旧值，不弹错（让抽屉捕获错误显示）
      }
    }
  })

  async function loadMeta() {
    if (loading.meta) return
    loading.meta = true
    try {
      const [indRes, fnRes, tmplRes] = await Promise.all([
        quantMetaAPI.indicators(),
        quantMetaAPI.expressionFunctions(),
        quantMetaAPI.strategyTemplates()
      ])
      if (indRes?.data) indicators.value = indRes.data as IndicatorSpec[]
      if (fnRes?.data) expressionMeta.value = fnRes.data as ExpressionMeta
      if (tmplRes?.data) templates.value = tmplRes.data as StrategyTemplate[]
    } finally {
      loading.meta = false
    }
  }

  function applyTemplate(tmpl: StrategyTemplate) {
    // 深拷贝避免模板被用户修改污染
    form.rule_config = JSON.parse(JSON.stringify(tmpl.rule_config)) as RuleConfigV2
    form.name = form.name || tmpl.title
  }

  function resetForm() {
    form.id = null
    form.name = ''
    form.description = ''
    form.status = 'active'
    form.symbols = []
    form.rule_config = emptyV2()
    validation.value = null
    dryRun.value = null
  }

  function loadFromRecord(record: { id: number; name: string; description: string; status: string; symbols: string[]; rule_config: any }) {
    form.id = record.id
    form.name = record.name || ''
    form.description = record.description || ''
    form.status = (record.status === 'inactive' ? 'inactive' : 'active') as 'active' | 'inactive'
    form.symbols = Array.isArray(record.symbols) ? [...record.symbols] : []
    form.rule_config = normalizeToV2(record.rule_config || {})
  }

  function addRule(preset?: Partial<{ label: string; expr: string; weight: number }>) {
    const r = {
      id: newRuleId(),
      label: preset?.label || '新规则',
      expr: preset?.expr || 'close > ma_5',
      weight: preset?.weight ?? 1
    }
    form.rule_config = { ...form.rule_config, rules: [...form.rule_config.rules, r] }
  }

  function updateRule(id: string, patch: Partial<{ label: string; expr: string; weight: number }>) {
    form.rule_config = {
      ...form.rule_config,
      rules: form.rule_config.rules.map(r => r.id === id ? { ...r, ...patch } : r)
    }
  }

  function removeRule(id: string) {
    form.rule_config = {
      ...form.rule_config,
      rules: form.rule_config.rules.filter(r => r.id !== id)
    }
  }

  function setIndicatorParam(key: string, paramName: string, value: any) {
    const list = [...form.rule_config.indicators]
    const idx = list.findIndex(i => i.key === key)
    if (idx === -1) {
      list.push({ key, params: { [paramName]: value } })
    } else {
      list[idx] = {
        ...list[idx],
        params: { ...(list[idx].params || {}), [paramName]: value }
      }
    }
    form.rule_config = { ...form.rule_config, indicators: list }
  }

  function removeIndicator(key: string) {
    form.rule_config = {
      ...form.rule_config,
      indicators: form.rule_config.indicators.filter(i => i.key !== key)
    }
  }

  function toggleIndicator(key: string) {
    const list = [...form.rule_config.indicators]
    const idx = list.findIndex(i => i.key === key)
    if (idx >= 0) {
      list.splice(idx, 1)
    } else {
      // 启用时把 spec.params 的 default 一并写入，避免后端 _v2_resolve
      // 时按 spec 重新算 window 列表与 UI 看到的不一致。
      const spec = indicators.value.find(i => i.key === key)
      const params: Record<string, any> = {}
      if (spec) {
        for (const p of spec.params) params[p.name] = p.default
      }
      list.push({ key, params })
    }
    form.rule_config = { ...form.rule_config, indicators: list }
  }

  function isIndicatorEnabled(key: string): boolean {
    return form.rule_config.indicators.some(i => i.key === key)
  }

  function setSignalType(v: 'buy' | 'sell' | 'watch') {
    form.rule_config = { ...form.rule_config, signal_type: v }
  }

  function setMinScore(v: number) {
    form.rule_config = { ...form.rule_config, min_score: Math.max(0, Number(v) || 0) }
  }

  function setGate(mode: 'all' | 'any' | 'expr', expr?: string | null) {
    form.rule_config = {
      ...form.rule_config,
      gate: { mode, expr: mode === 'expr' ? (expr || '') : null }
    }
  }

  async function runValidate() {
    if (loading.validate) return
    loading.validate = true
    try {
      const res = await quantStrategyAPI.validate({ rule_config: form.rule_config })
      if (res?.data) validation.value = res.data as ValidationResult
    } catch (err) {
      console.error('[strategy ide] validate failed', err)
    } finally {
      loading.validate = false
    }
  }

  function scheduleDryRun() {
    if (dryRunTimer) window.clearTimeout(dryRunTimer)
    dryRunTimer = window.setTimeout(() => executeDryRun(), 500)
  }

  async function executeDryRun() {
    if (loading.dryRun) return
    loading.dryRun = true
    try {
      const res = await quantStrategyAPI.dryRun({
        rule_config: form.rule_config,
        symbol: dryRunParams.symbol,
        start_date: dryRunParams.start_date,
        end_date: dryRunParams.end_date,
        adjust_flag: dryRunParams.adjust_flag
      })
      if (res?.data) dryRun.value = res.data as DryRunResponse
    } catch (err: any) {
      console.error('[strategy ide] dry_run failed', err)
      dryRun.value = null
    } finally {
      loading.dryRun = false
    }
  }

  // rule_config 变化时自动触发 validate + dry_run
  watch(
    () => JSON.stringify(form.rule_config),
    () => {
      runValidate()
      scheduleDryRun()
    }
  )

  // dryRunParams 变化时也触发 dry_run
  watch(
    () => [dryRunParams.symbol, dryRunParams.start_date, dryRunParams.end_date],
    () => scheduleDryRun()
  )

  // 暴露给模板的派生数据
  const passedDates = computed(() => dryRun.value?.passed_dates ?? [])
  const barsCount = computed(() => dryRun.value?.meta.bars_count ?? 0)
  const passedCount = computed(() => dryRun.value?.meta.passed_count ?? 0)

  // 把 form.rule_config.indicators 展开成具体输出名（ma_5、vol_ratio_10 等）
  const expandedIndicatorOutputs = computed<string[]>(() => {
    const out: string[] = []
    for (const ind of form.rule_config.indicators) {
      const spec = indicators.value.find(i => i.key === ind.key)
      if (!spec) continue
      // 把 spec.params 的 default 与用户 ind.params 合并
      const params: Record<string, any> = {}
      for (const p of spec.params) params[p.name] = p.default
      Object.assign(params, ind.params || {})
      for (const o of spec.outputs) {
        if (!o.name.includes('{')) {
          out.push(o.name)
          continue
        }
        // 模板展开：ma 走 windows 列表，其他走 window/lookback 单值
        if (spec.key === 'ma') {
          const ws = (params.windows as number[]) || [5, 10, 20, 60]
          for (const w of ws) out.push(o.name.replace('{window}', String(w)))
        } else {
          const singleParam = spec.params[0]
          if (singleParam) {
            const v = params[singleParam.name] ?? singleParam.default
            out.push(o.name.replace('{window}', String(v)))
          }
        }
      }
    }
    return Array.from(new Set(out))
  })

  return {
    // 元数据
    indicators,
    expressionMeta,
    templates,
    loadMeta,
    // 表单
    form,
    ruleConfigText,
    resetForm,
    loadFromRecord,
    applyTemplate,
    addRule,
    updateRule,
    removeRule,
    setIndicatorParam,
    removeIndicator,
    toggleIndicator,
    isIndicatorEnabled,
    setSignalType,
    setMinScore,
    setGate,
    // 校验 + 试算
    validation,
    runValidate,
    dryRun,
    dryRunParams,
    scheduleDryRun,
    executeDryRun,
    passedDates,
    barsCount,
    passedCount,
    expandedIndicatorOutputs,
    loading
  }
}

function emptyV2(): RuleConfigV2 {
  return {
    version: 2,
    signal_type: 'watch',
    logic: 'all',
    gate: { mode: 'all', expr: null },
    min_score: 0,
    indicators: [],
    rules: []
  }
}

function normalizeToV2(raw: any): RuleConfigV2 {
  if (!raw || typeof raw !== 'object') return emptyV2()
  if (raw.version === 2) {
    return {
      version: 2,
      signal_type: raw.signal_type || 'watch',
      logic: raw.logic,
      gate: raw.gate || { mode: 'all', expr: null },
      min_score: Number(raw.min_score) || 0,
      indicators: Array.isArray(raw.indicators) ? raw.indicators : [],
      rules: Array.isArray(raw.rules) ? raw.rules.map((r: any) => ({
        id: String(r.id || newRuleId()),
        label: String(r.label || ''),
        expr: String(r.expr || ''),
        weight: Number(r.weight) || 1,
      })) : [],
    }
  }
  // v1 形态：尽量塞到 rules 里但 expr 留空，等待后端 migrate 或人工修
  return {
    version: 2,
    signal_type: raw.signal_type || 'watch',
    logic: raw.logic,
    gate: { mode: raw.logic === 'any' ? 'any' : 'all', expr: null },
    min_score: Number(raw.min_score) || 0,
    indicators: [],
    rules: [],
  }
}

function defaultStartDate(): string {
  const d = new Date()
  d.setMonth(d.getMonth() - 3)
  return d.toISOString().slice(0, 10)
}

function defaultEndDate(): string {
  return new Date().toISOString().slice(0, 10)
}