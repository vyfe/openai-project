import { createApiClient } from '@/services/httpClient'

const quantApi = createApiClient({
  requireAuthByDefault: true
})

export const quantDataAPI = {
  providers: () => quantApi.get('/never_guess_my_usage/quant/providers'),
  dashboardOverview: () => quantApi.get('/never_guess_my_usage/quant/dashboard/overview'),
  dailyBars: (params: { symbol: string; start_date?: string; end_date?: string; limit?: number }) =>
    quantApi.get('/never_guess_my_usage/quant/data/daily_bars', { params }),
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
  manualRun: (schedule_id: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/manual_run', { schedule_id }),
  rebuildDueRuns: (lookback_minutes: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/rebuild_due_runs', { lookback_minutes }),
  executeRun: (run_id: number) =>
    quantApi.post('/never_guess_my_usage/quant/scheduler/execute_run', { run_id })
}
