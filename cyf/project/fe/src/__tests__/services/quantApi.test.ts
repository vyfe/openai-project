/**
 * quantApi.ts 测试 — 验证 API 请求路径与参数构造。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// 使用 vi.hoisted 确保 mockClient 在 vi.mock 工厂之前被初始化（vi.mock 会被 hoist）
const { mockClient } = vi.hoisted(() => ({
  mockClient: {
    get: vi.fn(() => Promise.resolve({ success: true, data: null, msg: '' })),
    post: vi.fn(() => Promise.resolve({ success: true, data: null, msg: '' })),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  }
}))

// Mock httpClient — 工厂中直接引用 hoisted 的 mockClient
vi.mock('@/services/httpClient', () => ({
  createApiClient: () => mockClient,
  getApiBaseUrl: () => 'http://localhost:39997',
  API_BASE_URL: 'http://localhost:39997',
  getValidAccessToken: () => Promise.resolve('test-token')
}))

import {
  quantDataAPI,
  quantTaskAPI,
  quantStrategyAPI,
  quantOperationAPI,
  quantBacktestAPI,
  quantScheduleAPI,
  quantPromptAPI,
  quantReportAPI,
  quantImAPI,
  quantMemoryAPI,
  quantPositionAPI
} from '@/services/quantApi'

beforeEach(() => {
  mockClient.get.mockClear()
  mockClient.post.mockClear()
})

describe('quantApi — 命名空间存在性', () => {
  const namespaces: Record<string, Record<string, Function>> = {
    quantDataAPI,
    quantTaskAPI,
    quantStrategyAPI,
    quantOperationAPI,
    quantBacktestAPI,
    quantScheduleAPI,
    quantPromptAPI,
    quantReportAPI,
    quantImAPI,
    quantMemoryAPI,
    quantPositionAPI
  }

  it('应导出 11 个 API 命名空间', () => {
    expect(Object.keys(namespaces)).toHaveLength(11)
  })

  it('每个命名空间的所有方法应为函数', () => {
    for (const [name, api] of Object.entries(namespaces)) {
      for (const [method, fn] of Object.entries(api)) {
        expect(typeof fn, `${name}.${method} 应为函数`).toBe('function')
      }
    }
  })
})

describe('quantDataAPI — 请求参数构造', () => {
  it('dailyBars 应传递 symbol 和可选参数', async () => {
    await quantDataAPI.dailyBars({ symbol: '000001.SZ', limit: 60 })
    expect(mockClient.get).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/data/daily_bars',
      { params: { symbol: '000001.SZ', limit: 60 } }
    )
  })

  it('backfill 应发送 POST 请求体', async () => {
    await quantDataAPI.backfill({ symbols: ['000001.SZ'], lookback_days: 30 })
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/data/backfill',
      { symbols: ['000001.SZ'], lookback_days: 30 }
    )
  })

  it('providers 应发送 GET 请求', async () => {
    await quantDataAPI.providers()
    expect(mockClient.get).toHaveBeenCalledWith('/never_guess_my_usage/quant/providers')
  })

  it('dashboardOverview 应发送 GET 请求', async () => {
    await quantDataAPI.dashboardOverview()
    expect(mockClient.get).toHaveBeenCalledWith('/never_guess_my_usage/quant/dashboard/overview')
  })
})

describe('quantStrategyAPI — 请求参数构造', () => {
  it('create 应发送策略数据', async () => {
    const payload = { name: '趋势放量', rule_config: { logic: 'all' }, symbols: [], status: 'active' }
    await quantStrategyAPI.create(payload)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/strategy/create',
      payload
    )
  })

  it('run 应传递 strategy_id 和可选参数', async () => {
    await quantStrategyAPI.run({ strategy_id: 1, save_all_signals: true })
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/strategy/run',
      { strategy_id: 1, save_all_signals: true }
    )
  })

  it('list 应传递可选 status 过滤', async () => {
    await quantStrategyAPI.list({ status: 'active' })
    expect(mockClient.get).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/strategy/list',
      { params: { status: 'active' } }
    )
  })

  it('delete 应传递 id', async () => {
    await quantStrategyAPI.delete(5)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/strategy/delete',
      { id: 5 }
    )
  })
})

describe('quantPositionAPI — 请求参数构造', () => {
  it('create 应发送持仓流水数据', async () => {
    const payload = { symbol: '000001.SZ', side: 'buy', quantity: 100, price: 12.5, occurred_at: '2025-01-15 10:00:00' }
    await quantPositionAPI.create(payload)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/positions/create',
      payload
    )
  })

  it('summary 应传递 strategy_id 过滤', async () => {
    await quantPositionAPI.summary({ strategy_id: 1 })
    expect(mockClient.get).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/positions/summary',
      { params: { strategy_id: 1 } }
    )
  })
})

describe('quantScheduleAPI — 请求参数构造', () => {
  it('createConfig 应发送调度配置数据', async () => {
    const payload = { name: '每日拉数', task_type: 'data_sync', cron_expr: '20 15 * * 1-5', payload: { symbols: ['000001.SZ'] } }
    await quantScheduleAPI.createConfig(payload)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/scheduler/config/create',
      payload
    )
  })

  it('manualRun 应传递 schedule_id', async () => {
    await quantScheduleAPI.manualRun(42)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/scheduler/manual_run',
      { schedule_id: 42 }
    )
  })

  it('resetRun 应传递 run_id 和 allow_success', async () => {
    await quantScheduleAPI.resetRun(7, true)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/scheduler/reset_run',
      { run_id: 7, allow_success: true }
    )
  })
})

describe('quantTaskAPI — 请求参数构造', () => {
  it('create 应发送任务数据', async () => {
    const payload = { symbols: ['000001.SZ'], start_date: '2025-01-01', end_date: '2025-01-31' }
    await quantTaskAPI.create(payload)
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/client/tasks/create',
      payload
    )
  })
})

describe('quantMemoryAPI — 请求参数构造', () => {
  it('curate 应发送 POST 请求', async () => {
    await quantMemoryAPI.curate({ symbols: ['000001.SZ'], lookback_days: 120 })
    expect(mockClient.post).toHaveBeenCalledWith(
      '/never_guess_my_usage/quant/memory/curate',
      { symbols: ['000001.SZ'], lookback_days: 120 }
    )
  })
})
