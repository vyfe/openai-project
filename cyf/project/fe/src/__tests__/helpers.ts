import { vi } from 'vitest'

/**
 * 测试共享 mock 工具函数。
 *
 * httpClient.ts 响应拦截器会解包 response.data，
 * 所以 API 调用方拿到的是 { success, data, msg } 结构。
 * mock quantApi 时应返回这个层级。
 */

/** 构造成功的 API 响应 */
export function mockApiSuccess<T>(data: T, msg = '') {
  return Promise.resolve({ success: true, data, msg })
}

/** 构造失败的 API 响应 */
export function mockApiError(msg: string, data: any = null) {
  return Promise.resolve({ success: false, data, msg })
}

/** 构造会抛异常的 API 响应（网络错误等） */
export function mockApiReject(message: string) {
  return Promise.reject(new Error(message))
}

/**
 * 为 quantApi 的 10 个命名空间创建统一 mock 对象。
 * 每个方法默认返回 mockApiSuccess(null)，
 * 测试中可通过 vi.fn() 覆盖单个方法。
 */
export function createMockQuantApi() {
  const noop = () => mockApiSuccess(null)

  return {
    quantDataAPI: {
      providers: vi.fn(noop),
      dashboardOverview: vi.fn(noop),
      dailyBars: vi.fn(noop),
      backfill: vi.fn(noop),
      importBatches: vi.fn(noop),
      symbols: vi.fn(noop)
    },
    quantTaskAPI: {
      create: vi.fn(noop),
      list: vi.fn(noop),
      reset: vi.fn(noop)
    },
    quantStrategyAPI: {
      list: vi.fn(noop),
      get: vi.fn(noop),
      create: vi.fn(noop),
      update: vi.fn(noop),
      delete: vi.fn(noop),
      run: vi.fn(noop),
      runs: vi.fn(noop),
      signals: vi.fn(noop)
    },
    quantOperationAPI: {
      list: vi.fn(noop),
      get: vi.fn(noop),
      create: vi.fn(noop),
      update: vi.fn(noop),
      delete: vi.fn(noop)
    },
    quantBacktestAPI: {
      list: vi.fn(noop),
      get: vi.fn(noop),
      run: vi.fn(noop),
      delete: vi.fn(noop)
    },
    quantScheduleAPI: {
      meta: vi.fn(noop),
      overview: vi.fn(noop),
      configs: vi.fn(noop),
      getConfig: vi.fn(noop),
      createConfig: vi.fn(noop),
      updateConfig: vi.fn(noop),
      deleteConfig: vi.fn(noop),
      runs: vi.fn(noop),
      getRun: vi.fn(noop),
      getRunLog: vi.fn(noop),
      manualRun: vi.fn(noop),
      rebuildDueRuns: vi.fn(noop),
      resetRun: vi.fn(noop),
      executeRun: vi.fn(noop)
    },
    quantPromptAPI: {
      list: vi.fn(noop),
      get: vi.fn(noop),
      create: vi.fn(noop),
      update: vi.fn(noop),
      delete: vi.fn(noop)
    },
    quantReportAPI: {
      list: vi.fn(noop),
      get: vi.fn(noop),
      generate: vi.fn(noop)
    },
    quantImAPI: {
      channels: vi.fn(noop),
      getChannel: vi.fn(noop),
      createChannel: vi.fn(noop),
      updateChannel: vi.fn(noop),
      deleteChannel: vi.fn(noop),
      deliveries: vi.fn(noop),
      inboundEvents: vi.fn(noop),
      sendReport: vi.fn(noop),
      sendPositions: vi.fn(noop),
      test: vi.fn(noop)
    },
    quantMemoryAPI: {
      files: vi.fn(noop),
      get: vi.fn(noop),
      curate: vi.fn(noop)
    },
    quantPositionAPI: {
      summary: vi.fn(noop),
      journal: vi.fn(noop),
      get: vi.fn(noop),
      create: vi.fn(noop),
      update: vi.fn(noop),
      delete: vi.fn(noop)
    }
  }
}
