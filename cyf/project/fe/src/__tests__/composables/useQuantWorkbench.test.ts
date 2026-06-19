/**
 * useQuantWorkbench composable 测试。
 *
 * 核心挑战：composable 使用模块级单例 quantWorkbenchInstance，
 * 测试间必须隔离。方案：vi.resetModules() + 动态 import()。
 *
 * 注意：Vue 的 proxyRefs 在测试环境会自动解包 ref，
 * 但某些情况下返回的仍是 Ref 对象。对于 proxyRefs 返回的
 * ref 类型属性，统一使用 .value 访问以确保一致性。
 *
 * 测试范围：
 * - 纯函数：formatRate / formatNumber / strategyStatusTag / buildSchedulePayload
 * - 表单操作：resetStrategyForm / hydrateStrategyForm / resetOperationForm
 * - 核心业务：saveStrategy / executeSelectedStrategy / saveOperation / createTask
 * - 初始化：initialize 调用 bootstrap
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createMockQuantApi, mockApiSuccess } from '../helpers'

// ─── mock 依赖 ───

// Mock quantApi 的全部命名空间
const mockApi = createMockQuantApi()
vi.mock('@/services/quantApi', () => mockApi)

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') }
}))

// Mock Pinia
vi.mock('pinia', () => ({
  defineStore: vi.fn(),
  createPinia: vi.fn()
}))

/**
 * 每个测试重新 import composable 以获取隔离实例。
 * 通过 vi.resetModules() 清除模块缓存中的单例。
 */
async function getWorkbench() {
  vi.resetModules()

  // 重新注册 mock（resetModules 会清除之前的 mock 注册）
  vi.doMock('@/services/quantApi', () => createMockQuantApi())
  vi.doMock('element-plus', () => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') }
  }))

  const { useQuantWorkbench } = await import('@/composables/useQuantWorkbench')
  return useQuantWorkbench()
}

/**
 * 安全获取 ref 值 — proxyRefs 在 vitest 环境下可能已解包也可能未解包。
 */
function unwrap<T>(v: T): any {
  return v && typeof v === 'object' && '__v_isRef' in (v as any) ? (v as any).value : v
}

describe('useQuantWorkbench — 纯函数', () => {
  it('formatRate 应将小数转为百分比字符串', async () => {
    const wb = await getWorkbench()
    expect(wb.formatRate(0.1234)).toBe('12.34%')
    expect(wb.formatRate(-0.05)).toBe('-5.00%')
    expect(wb.formatRate(null)).toBe('--')
    expect(wb.formatRate(undefined)).toBe('--')
    expect(wb.formatRate('')).toBe('--')
    expect(wb.formatRate(NaN)).toBe('--')
    expect(wb.formatRate(0)).toBe('0.00%')
  })

  it('formatNumber 应格式化数字到指定小数位', async () => {
    const wb = await getWorkbench()
    expect(wb.formatNumber(1234.567, 2)).toBe('1234.57')
    expect(wb.formatNumber(null)).toBe('--')
    expect(wb.formatNumber(undefined)).toBe('--')
    expect(wb.formatNumber(0, 3)).toBe('0.000')
  })

  it('strategyStatusTag 应返回正确的标签类型', async () => {
    const wb = await getWorkbench()
    expect(wb.strategyStatusTag('active')).toBe('success')
    expect(wb.strategyStatusTag('inactive')).toBe('info')
    expect(wb.strategyStatusTag('archived')).toBe('info')
  })

  it('buildSchedulePayload 应根据 taskType 返回对应 payload', async () => {
    const wb = await getWorkbench()
    // 默认 data_sync
    const payload1 = wb.buildSchedulePayload()
    expect(payload1).toHaveProperty('symbols')
    expect(payload1).toHaveProperty('provider')

    // analysis_report
    wb.scheduleForm.taskType = 'analysis_report'
    const payload2 = wb.buildSchedulePayload()
    expect(payload2).toHaveProperty('strategy_ids')
    expect(payload2).toHaveProperty('save_all_signals')

    // memory_digest
    wb.scheduleForm.taskType = 'memory_digest'
    const payload3 = wb.buildSchedulePayload()
    expect(payload3).toHaveProperty('symbols')
    expect(payload3).toHaveProperty('lookback_days')
    expect(payload3).toHaveProperty('limit')
  })
})

describe('useQuantWorkbench — 表单操作', () => {
  it('resetStrategyForm 应清空策略表单', async () => {
    const wb = await getWorkbench()
    wb.strategyForm.name = '测试策略'
    wb.strategyForm.id = 1

    wb.resetStrategyForm()

    expect(wb.strategyForm.name).toBe('')
    expect(wb.strategyForm.id).toBeNull()
    expect(unwrap(wb.selectedStrategyId)).toBeNull()
    expect(wb.strategyForm.status).toBe('active')
  })

  it('hydrateStrategyForm 应填充策略表单并同步上下文', async () => {
    const wb = await getWorkbench()
    const strategy = {
      id: 5,
      name: '趋势放量',
      status: 'active',
      description: '测试描述',
      symbols: ['000001.SZ'],
      rule_config: { logic: 'all', rules: [] },
      updated_at: '2025-01-01'
    }

    wb.hydrateStrategyForm(strategy)

    expect(wb.strategyForm.id).toBe(5)
    expect(wb.strategyForm.name).toBe('趋势放量')
    expect(unwrap(wb.selectedStrategyId)).toBe(5)
    // syncStrategyContext
    expect(unwrap(wb.operationForm.strategyId)).toBe(5)
    expect(unwrap(wb.backtestForm.strategyId)).toBe(5)
  })

  it('resetOperationForm 应保留当前 strategyId', async () => {
    const wb = await getWorkbench()
    // proxyRefs 已解包 ref，直接赋值即可设置 ref.value
    wb.selectedStrategyId = 3

    wb.operationForm.symbol = '000001.SZ'
    wb.operationForm.action = 'sell'

    wb.resetOperationForm()

    // resetOperationForm 内部用 selectedStrategyId.value 取值作为 strategyId
    expect(unwrap(wb.operationForm.strategyId)).toBe(3)
    expect(wb.operationForm.symbol).toBe('')
    expect(wb.operationForm.action).toBe('buy')
  })

  it('resetScheduleForm 应恢复默认值', async () => {
    const wb = await getWorkbench()
    wb.scheduleForm.name = '每日拉数'
    wb.scheduleForm.taskType = 'memory_digest'

    wb.resetScheduleForm()

    expect(wb.scheduleForm.name).toBe('')
    expect(wb.scheduleForm.taskType).toBe('data_sync')
    expect(wb.scheduleForm.cronExpr).toBe('20 15 * * 1-5')
  })

  it('hydrateScheduleForm 应正确解析 payload 到表单', async () => {
    const wb = await getWorkbench()
    const config = {
      id: 10,
      name: '测试调度',
      task_type: 'data_sync',
      status: 'active',
      cron_expr: '0 9 * * 1-5',
      market_calendar: 'A_SHARE',
      timezone: 'Asia/Shanghai',
      retry_max: 2,
      retry_delay_seconds: 300,
      allow_manual_run: false,
      description: '测试',
      payload: {
        symbols: ['000001.SZ', '600000.SH'],
        provider: 'baostock',
        adjust_flag: 'hfq',
        lookback_trade_days: 30,
        lease_seconds: 900,
        note: '每日同步'
      },
      updated_at: '2025-01-01'
    }

    wb.hydrateScheduleForm(config)

    expect(wb.scheduleForm.id).toBe(10)
    expect(wb.scheduleForm.name).toBe('测试调度')
    expect(wb.scheduleForm.dataSymbols).toEqual(['000001.SZ', '600000.SH'])
    expect(wb.scheduleForm.dataProvider).toBe('baostock')
    expect(wb.scheduleForm.dataAdjustFlag).toBe('hfq')
    expect(wb.scheduleForm.allowManualRun).toBe(false)
  })
})

describe('useQuantWorkbench — 核心业务', () => {
  it('saveStrategy 空名称应触发 warning', async () => {
    const wb = await getWorkbench()
    const { ElMessage } = await import('element-plus')
    wb.strategyForm.name = ''

    await wb.saveStrategy()

    expect(ElMessage.warning).toHaveBeenCalledWith('策略名称不能为空')
  })

  it('executeSelectedStrategy 未选择策略应返回 null', async () => {
    const wb = await getWorkbench()
    wb.strategyForm.id = null

    const result = await wb.executeSelectedStrategy()

    expect(result).toBeNull()
  })

  it('createTask 缺少必填字段应触发 warning', async () => {
    const wb = await getWorkbench()
    const { ElMessage } = await import('element-plus')
    wb.taskForm.symbols = []
    wb.taskForm.startDate = ''

    await wb.createTask()

    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('saveOperation 缺少标的和交易日应触发 warning', async () => {
    const wb = await getWorkbench()
    const { ElMessage } = await import('element-plus')
    wb.operationForm.symbol = ''
    wb.operationForm.tradeDate = ''

    await wb.saveOperation()

    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('savePositionEntry 缺少标的和时间应触发 warning', async () => {
    const wb = await getWorkbench()
    const { ElMessage } = await import('element-plus')
    wb.positionForm.symbol = ''
    wb.positionForm.occurredAt = ''

    await wb.savePositionEntry()

    expect(ElMessage.warning).toHaveBeenCalled()
  })
})

describe('useQuantWorkbench — 初始化', () => {
  it('initialize 应调用多个 load 方法', async () => {
    const wb = await getWorkbench()

    // 获取当前 mock 的 API 命名空间（由 doMock 创建的新实例）
    const { quantDataAPI, quantScheduleAPI } = await import('@/services/quantApi') as any

    // 让关键 API 返回成功响应
    if (quantDataAPI.dashboardOverview?.mockResolvedValue) {
      quantDataAPI.dashboardOverview.mockResolvedValue({ success: true, data: { snapshot: {} }, msg: '' })
    }
    if (quantDataAPI.providers?.mockResolvedValue) {
      quantDataAPI.providers.mockResolvedValue({ success: true, data: { providers: [] }, msg: '' })
    }
    if (quantDataAPI.symbols?.mockResolvedValue) {
      quantDataAPI.symbols.mockResolvedValue({ success: true, data: [], msg: '' })
    }
    if (quantDataAPI.importBatches?.mockResolvedValue) {
      quantDataAPI.importBatches.mockResolvedValue({ success: true, data: [], msg: '' })
    }
    if (quantScheduleAPI.meta?.mockResolvedValue) {
      quantScheduleAPI.meta.mockResolvedValue({ success: true, data: null, msg: '' })
    }
    if (quantScheduleAPI.configs?.mockResolvedValue) {
      quantScheduleAPI.configs.mockResolvedValue({ success: true, data: [], msg: '' })
    }
    if (quantScheduleAPI.runs?.mockResolvedValue) {
      quantScheduleAPI.runs.mockResolvedValue({ success: true, data: [], msg: '' })
    }

    await wb.initialize()

    // 验证关键 load 方法被调用
    expect(quantDataAPI.dashboardOverview).toHaveBeenCalled()
    expect(quantDataAPI.providers).toHaveBeenCalled()
    expect(quantScheduleAPI.meta).toHaveBeenCalled()
  })
})
