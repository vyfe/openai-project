import { createApiClient } from '@/services/httpClient'

const quantApi = createApiClient({
  requireAuthByDefault: true
})

export const quantDataAPI = {
  providers: () => quantApi.get('/never_guess_my_usage/quant/providers'),
  dashboardOverview: () => quantApi.get('/never_guess_my_usage/quant/dashboard/overview'),
  dailyBars: (params: { symbol: string; start_date?: string; end_date?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/data/daily_bars', { params }),
  backfill: (data: {
    symbols?: string[]
    symbols_text?: string
    lookback_days?: number
    provider?: string
    adjust_flag?: string
    note?: string
    lease_seconds?: number
  }) => quantApi.post('/never_guess_my_usage/quant/data/backfill', data),
  importBatches: (params?: { limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/data/import_batches', { params }),
  symbols: (params?: { limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/symbols', { params })
}

export const quantTaskAPI = {
  create: (data: {
    symbols?: string[]
    symbols_text?: string
    start_date: string
    end_date: string
    provider?: string
    adjust_flag?: string
    note?: string
    lease_seconds?: number
  }) => quantApi.post('/never_guess_my_usage/quant/client/tasks/create', data),
  list: (params?: { limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/client/tasks/list', { params }),
  reset: (task_id: string) =>
    quantApi.post('/never_guess_my_usage/quant/client/tasks/reset', { task_id })
}

export const quantStrategyAPI = {
  list: (params?: { status?: string }) =>
    quantApi.get('/never_guess_my_usage/quant/strategy/list', { params }),
  get: (strategyId: number) =>
    quantApi.get(`/never_guess_my_usage/quant/strategy/get/${strategyId}`),
  create: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/strategy/create', data),
  update: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/strategy/update', data),
  delete: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/strategy/delete', { id }),
  run: (data: { strategy_id: number; trade_date?: string; save_all_signals?: boolean }) =>
    quantApi.post('/never_guess_my_usage/quant/strategy/run', data),
  runs: (params?: { strategy_id?: number; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/strategy/runs', { params }),
  signals: (params?: { strategy_id?: number; run_id?: number; passed_only?: boolean; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/strategy/signals', { params })
}

export const quantOperationAPI = {
  list: (params?: { strategy_id?: number; symbol?: string; status?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/operations/list', { params }),
  get: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/operations/get/${id}`),
  create: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/operations/create', data),
  update: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/operations/update', data),
  delete: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/operations/delete', { id })
}

export const quantBacktestAPI = {
  list: (params?: { strategy_id?: number; status?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/backtest/list', { params }),
  get: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/backtest/get/${id}`),
  run: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/backtest/run', data),
  delete: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/backtest/delete', { id })
}

export const quantScheduleAPI = {
  meta: () => quantApi.get('/never_guess_my_usage/quant/scheduler/meta'),
  overview: () => quantApi.get('/never_guess_my_usage/quant/scheduler/overview'),
  configs: (params?: { status?: string; task_type?: string }) =>
    quantApi.get('/never_guess_my_usage/quant/scheduler/configs', { params }),
  getConfig: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/scheduler/config/${id}`),
  createConfig: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/config/create', data),
  updateConfig: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/config/update', data),
  deleteConfig: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/config/delete', { id }),
  runs: (params?: { schedule_id?: number; status?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/scheduler/runs', { params }),
  getRun: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/scheduler/run/${id}`),
  getRunLog: (id: number, params?: { limit?: number }) =>
    quantApi.get(`/never_guess_my_usage/quant/scheduler/run/${id}/log`, { params }),
  manualRun: (schedule_id: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/manual_run', { schedule_id }),
  rebuildDueRuns: (lookback_minutes: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/rebuild_due_runs', { lookback_minutes }),
  resetRun: (run_id: number, allow_success = false) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/reset_run', { run_id, allow_success }),
  executeRun: (run_id: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/execute_run', { run_id })
}

export const quantPromptAPI = {
  list: (params?: { strategy_id?: number; report_type?: string }) =>
    quantApi.get('/never_guess_my_usage/quant/prompt_templates', { params }),
  get: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/prompt_template/${id}`),
  create: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/prompt_template/create', data),
  update: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/prompt_template/update', data),
  delete: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/prompt_template/delete', { id })
}

export const quantReportAPI = {
  list: (params?: { strategy_id?: number; run_id?: number; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/reports', { params }),
  get: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/report/${id}`),
  generate: (data: { run_id: number; report_type?: string }) =>
    quantApi.post('/never_guess_my_usage/quant/report/generate', data)
}

export const quantImAPI = {
  channels: (params?: { status?: string; channel_type?: string }) =>
    quantApi.get('/never_guess_my_usage/quant/im/channels', { params }),
  getChannel: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/im/channel/${id}`),
  createChannel: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/im/channel/create', data),
  updateChannel: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/im/channel/update', data),
  deleteChannel: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/im/channel/delete', { id }),
  deliveries: (params?: { report_id?: number; channel_id?: number; status?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/im/deliveries', { params }),
  inboundEvents: (params?: { channel_id?: number; status?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/im/inbound_events', { params }),
  sendReport: (data: { report_id: number; channel_id: number }) =>
    quantApi.post('/never_guess_my_usage/quant/im/send_report', data),
  sendPositions: (data: { channel_id: number; strategy_id?: number }) =>
    quantApi.post('/never_guess_my_usage/quant/im/send_positions', data),
  test: (data: { content: string; channel_id: number }) =>
    quantApi.post('/never_guess_my_usage/quant/im/test', data)
}

export const quantMemoryAPI = {
  files: (params?: { limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/memory/files', { params }),
  get: (symbol: string) =>
    quantApi.get(`/never_guess_my_usage/quant/memory/${encodeURIComponent(symbol)}`),
  curate: (data?: { symbols?: string[]; lookback_days?: number; limit?: number }) =>
    quantApi.post('/never_guess_my_usage/quant/memory/curate', data || {})
}

export const quantPositionAPI = {
  summary: (params?: { strategy_id?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/positions/summary', { params }),
  journal: (params?: { strategy_id?: number; symbol?: string; source?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/positions/journal', { params }),
  get: (id: number) =>
    quantApi.get(`/never_guess_my_usage/quant/positions/journal/${id}`),
  create: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/positions/create', data),
  update: (data: any) =>
    quantApi.post('/never_guess_my_usage/quant/positions/update', data),
  delete: (id: number) =>
    quantApi.post('/never_guess_my_usage/quant/positions/delete', { id })
}
