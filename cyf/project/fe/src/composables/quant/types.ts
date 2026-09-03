/**
 * 量化工作台数据类型定义（按业务域分组）。
 */

export type StrategyRecord = {
  id: number
  name: string
  status: string
  description: string
  symbols: string[]
  rule_config: Record<string, any>
  updated_at?: string
}

export type StrategyRunRecord = {
  id: number
  strategy_id: number
  trade_date: string
  status: string
  signals_total: number
  symbols_total: number
  summary: Record<string, any>
  created_at: string
  finished_at?: string
}

export type OperationRecord = {
  id: number
  strategy_id?: number | null
  run_id?: number | null
  signal_id?: number | null
  symbol: string
  action: string
  status: string
  result_status?: string
  trade_date: string
  price?: number | null
  quantity?: number | null
  amount?: number | null
  thesis?: string
  execution_note?: string
  review_note?: string
  result_pct?: number | null
  result_amount?: number | null
  tags?: string[]
  created_by?: string
  updated_at?: string
}

export type BacktestRunRecord = {
  id: number
  strategy_id: number
  strategy_name: string
  status: string
  start_date: string
  end_date: string
  hold_days: number
  top_n: number
  initial_capital: number
  commission_rate: number
  slippage_rate: number
  signals_total: number
  trades_total: number
  summary?: Record<string, any>
  metrics?: Record<string, any>
  equity_curve?: Array<{ date: string; capital: number; net_value: number; avg_return?: number; closed_trades?: number }>
  benchmark_curve?: Array<{ date: string; capital?: number; net_value: number }>
  trades?: Array<Record<string, any>>
  error_message?: string
  created_at?: string
}

export type ScheduleConfigRecord = {
  id: number
  name: string
  task_type: string
  status: string
  cron_expr: string
  market_calendar: string
  timezone: string
  payload: Record<string, any>
  retry_max: number
  retry_delay_seconds: number
  allow_manual_run: boolean
  description?: string
  updated_at?: string
}

export type ScheduleRunRecord = {
  id: number
  schedule_id: number
  schedule_name: string
  task_type: string
  trigger_source: string
  status: string
  scheduled_for: string
  trade_date?: string
  attempts: number
  max_retries: number
  message?: string
  log_file?: string
  payload?: Record<string, any>
  result?: Record<string, any>
  next_retry_at?: string
  started_at?: string
  finished_at?: string
  log_tail?: string
}

export type PromptTemplateRecord = {
  id: number
  strategy_id?: number | null
  template_name: string
  prompt_version: string
  status: string
  report_type: string
  prompt_template: string
  model_name?: string
  change_note?: string
  updated_at?: string
}

export type ReportRecord = {
  id: number
  report_key: string
  strategy_id: number
  run_id?: number | null
  schedule_run_id?: number | null
  trade_date: string
  report_type: string
  status: string
  bundle_version: string
  prompt_version: string
  title: string
  final_markdown: string
  memory_references?: string[]
  created_at?: string
}

export type MemoryFileRecord = {
  symbol: string
  path: string
  updated_at: string
  size: number
}

export type ImChannelRecord = {
  id: number
  name: string
  channel_type: string
  status: string
  config?: Record<string, any>
  description?: string
  updated_at?: string
}

export type DeliveryRecord = {
  id: number
  report_id?: number | null
  run_id?: number | null
  channel_id?: number | null
  channel_type: string
  channel_target: string
  message_type: string
  status: string
  error_message?: string
  sent_at?: string
  created_at?: string
}

export type ImInboundEventRecord = {
  id: number
  event_id: string
  channel_id?: number | null
  channel_type: string
  message_id?: string
  chat_id?: string
  sender_id?: string
  sender_type?: string
  message_type?: string
  command?: string
  status: string
  parsed_payload?: Record<string, any>
  error_message?: string
  received_at?: string
  processed_at?: string
}

export type PositionJournalRecord = {
  id: number
  strategy_id?: number | null
  run_id?: number | null
  operation_id?: number | null
  symbol: string
  side: string
  price?: number | null
  quantity: number
  occurred_at: string
  source: string
  reason?: string
  remark?: string
  created_by?: string
  updated_at?: string
}

export type PositionSummaryRecord = {
  symbol: string
  strategy_id?: number | null
  net_quantity: number
  avg_cost?: number | null
  latest_price?: number | null
  market_value?: number | null
  unrealized_pnl?: number | null
  unrealized_pnl_pct?: number | null
  last_occurred_at?: string
  last_side?: string
  sources?: string[]
}

export type SymbolOption = {
  symbol: string
  code: string
  exchange: string
  name?: string
  source?: string
  type?: string
}
