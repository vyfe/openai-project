/**
 * 策略 IDE 类型定义（v2 rule_config + 元数据 + 试算）。
 */

export type ParamType = 'int' | 'float' | 'int_list' | 'bool' | 'enum'

export interface ParamSpec {
  name: string
  label: string
  type: ParamType
  default: any
  min?: number | null
  max?: number | null
  options?: any[] | null
  help?: string
}

export interface OutputSpec {
  /** 'ma_{window}' 模板或 'macd_dif' 字面名 */
  name: string
  label: string
  kind: 'numeric' | 'bool' | 'enum'
}

export interface IndicatorSpec {
  key: string
  label: string
  category: string
  base_lookback: number
  params: ParamSpec[]
  outputs: OutputSpec[]
}

export interface FunctionSpec {
  name: string
  signature: string
  desc: string
}

export interface ExpressionMeta {
  bar_fields: string[]
  functions: FunctionSpec[]
}

export interface RuleV2 {
  id: string
  label: string
  /** 表达式文本，如 'close > ma_5' 或 'cross_up(macd_dif, macd_dea)' */
  expr: string
  weight: number
}

export type GateMode = 'all' | 'any' | 'expr'

export interface GateSpec {
  mode: GateMode
  /** 当 mode==='expr' 时使用，引用 rule id，如 'r1 and (r2 or r3)' */
  expr?: string | null
}

export interface IndicatorDecl {
  key: string
  params?: Record<string, any>
}

export interface RuleConfigV2 {
  version: 2
  signal_type: 'buy' | 'sell' | 'watch'
  logic?: 'all' | 'any'
  gate: GateSpec
  min_score: number
  indicators: IndicatorDecl[]
  rules: RuleV2[]
}

export interface StrategyTemplate {
  key: string
  title: string
  summary: string
  category: string
  rule_config: RuleConfigV2
}

export interface ValidationRuleResult {
  id: string
  label: string
  expr: string
  ok: boolean
  error: string
  used_vars: string[]
}

export interface ValidationResult {
  ok: boolean
  rules: ValidationRuleResult[]
}

export interface DryRunBar {
  trade_date: string | null
  open_price: number | null
  high_price: number | null
  low_price: number | null
  close_price: number | null
  volume: number | null
  amount: number | null
  pct_change: number | null
  turnover_rate: number | null
}

export interface DryRunRuleResult {
  id: string
  label: string
  passed: boolean
  value: any
}

export interface DryRunResultRow {
  date: string | null
  passed: boolean
  score: number
  signal_type: string
  reasons: string[]
  rule_results: DryRunRuleResult[]
}

export interface DryRunResponse {
  rule_config: RuleConfigV2
  symbol: string
  start_date: string
  end_date: string
  bars: DryRunBar[]
  results: DryRunResultRow[]
  passed_dates: (string | null)[]
  meta: {
    bars_count: number
    passed_count: number
    adjust_flag: string
  }
}

/** 把 JSON 字符串解析成 RuleConfigV2；解析失败时返回默认空白 v2 配置。 */
export function parseRuleConfig(text: string): RuleConfigV2 | null {
  try {
    const obj = JSON.parse(text)
    if (!obj || typeof obj !== 'object') return null
    return normalizeToV2(obj)
  } catch {
    return null
  }
}

function normalizeToV2(raw: any): RuleConfigV2 {
  if (raw.version === 2) {
    return {
      version: 2,
      signal_type: raw.signal_type || 'watch',
      logic: raw.logic,
      gate: raw.gate || { mode: 'all', expr: null },
      min_score: Number(raw.min_score) || 0,
      indicators: Array.isArray(raw.indicators) ? raw.indicators : [],
      rules: Array.isArray(raw.rules) ? raw.rules.map((r: any) => ({
        id: String(r.id || ''),
        label: String(r.label || ''),
        expr: String(r.expr || ''),
        weight: Number(r.weight) || 1,
      })) : [],
    }
  }
  // v1 → 后端 migrate 由 /validate/dry_run 自动处理；前端给个最小 v2 占位
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