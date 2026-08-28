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

  it('displaySymbol 应根据 symbolOptions 缓存返回"名称（代码）"展示串', async () => {
    const wb = await getWorkbench()
    // 默认 workbench.symbolOptions 为空 → 只能回退到 symbol 本身
    expect(wb.displaySymbol('600519.SH')).toBe('600519.SH')
    expect(wb.displaySymbol('')).toBe('')

    // 注入 name 后应展示"名称（代码）"
    wb.symbolOptions.push({ symbol: '600519.SH', code: '600519', exchange: 'SH', name: '贵州茅台' })
    wb.symbolOptions.push({ symbol: '000001.SZ', code: '000001', exchange: 'SZ', name: '平安银行' })
    expect(wb.displaySymbol('600519.SH')).toBe('贵州茅台（600519.SH）')
    expect(wb.displaySymbol('000001.SZ')).toBe('平安银行（000001.SZ）')

    // 没缓存的 symbol 回退到本身
    expect(wb.displaySymbol('999999.SH')).toBe('999999.SH')

    // name 是简称时正常拼接（"002837.SZ 英维克" 包含完整 symbol 时去重）
    wb.symbolOptions.push({ symbol: '002837.SZ', code: '002837', exchange: 'SZ', name: '002837.SZ 英维克' })
    expect(wb.displaySymbol('002837.SZ')).toBe('002837.SZ 英维克')
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

  it('data_sync 默认 frequencies=["1d"]，多选后透传列表', async () => {
    const wb = await getWorkbench()
    wb.scheduleForm.taskType = 'data_sync'
    expect(wb.scheduleForm.dataFrequencies).toEqual(['1d'])
    expect(wb.buildSchedulePayload().frequencies).toEqual(['1d'])

    wb.scheduleForm.dataFrequencies = ['1d', '5m']
    expect(wb.buildSchedulePayload().frequencies).toEqual(['1d', '5m'])

    // 用户全清空 → 默认回退 ["1d"]
    wb.scheduleForm.dataFrequencies = []
    expect(wb.buildSchedulePayload().frequencies).toEqual(['1d'])
  })

  it('hydrateScheduleForm 应正确回显 payload.frequencies', async () => {
    const wb = await getWorkbench()
    wb.hydrateScheduleForm({
      id: 100, name: 'test', task_type: 'data_sync', status: 'active',
      cron_expr: '*/5 * * * *', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { frequencies: ['1d', '5m'], symbols: ['600519.SH'], provider: 'baostock' },
    } as any)
    expect(wb.scheduleForm.dataFrequencies).toEqual(['1d', '5m'])

    // 旧 payload 单值 frequency 也要兼容
    wb.hydrateScheduleForm({
      id: 101, name: 'test', task_type: 'data_sync', status: 'active',
      cron_expr: '*/5 * * * *', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { frequency: '5m', symbols: [], provider: 'auto' },
    } as any)
    expect(wb.scheduleForm.dataFrequencies).toEqual(['5m'])

    // 没有 frequency 字段默认 ["1d"]
    wb.hydrateScheduleForm({
      id: 102, name: 'test', task_type: 'data_sync', status: 'active',
      cron_expr: '*/5 * * * *', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { symbols: [], provider: 'auto' },
    } as any)
    expect(wb.scheduleForm.dataFrequencies).toEqual(['1d'])
  })

  it('data_sync 勾选 5m 时下发 minute_lookback_minutes；仅 1d 时不下发', async () => {
    const wb = await getWorkbench()
    wb.scheduleForm.taskType = 'data_sync'

    // 仅日线：不带分时字段
    wb.scheduleForm.dataFrequencies = ['1d']
    wb.scheduleForm.dataMinuteLookbackMinutes = 90
    const payload1 = wb.buildSchedulePayload() as any
    expect(payload1.frequencies).toEqual(['1d'])
    expect(payload1.minute_lookback_minutes).toBeUndefined()

    // 加上分时：注入 minute_lookback_minutes
    wb.scheduleForm.dataFrequencies = ['1d', '5m']
    wb.scheduleForm.dataMinuteLookbackMinutes = 120
    const payload2 = wb.buildSchedulePayload() as any
    expect(payload2.frequencies).toEqual(['1d', '5m'])
    expect(payload2.minute_lookback_minutes).toBe(120)
  })

  it('hydrateScheduleForm 回显 minute_lookback_minutes（新字段优先于旧 lookback_minutes）', async () => {
    const wb = await getWorkbench()
    // 新字段
    wb.hydrateScheduleForm({
      id: 200, name: 't', task_type: 'data_sync', status: 'active',
      cron_expr: '', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { frequencies: ['5m'], symbols: [], minute_lookback_minutes: 240 },
    } as any)
    expect(wb.scheduleForm.dataMinuteLookbackMinutes).toBe(240)

    // 旧字段兼容
    wb.hydrateScheduleForm({
      id: 201, name: 't', task_type: 'data_sync', status: 'active',
      cron_expr: '', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { frequencies: ['5m'], symbols: [], lookback_minutes: 180 },
    } as any)
    expect(wb.scheduleForm.dataMinuteLookbackMinutes).toBe(180)

    // 都缺省 → 1200 分钟（5 个交易日）兜底
    wb.hydrateScheduleForm({
      id: 202, name: 't', task_type: 'data_sync', status: 'active',
      cron_expr: '', market_calendar: 'A_SHARE', timezone: 'Asia/Shanghai',
      retry_max: 1, retry_delay_seconds: 180, allow_manual_run: true, description: '',
      payload: { frequencies: ['1d'], symbols: [] },
    } as any)
    expect(wb.scheduleForm.dataMinuteLookbackMinutes).toBe(1200)
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
  it('切换到周线时应请求周线数据并更新当前图表数据', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    const weeklyRows = [{ trade_date: '2026-08-14', close: 100 }]
    vi.mocked(quantDataAPI.weeklyBars).mockResolvedValue({ success: true, data: weeklyRows, msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    wb.dailyQuery.limit = 100

    wb.switchChartCycle('weekly')
    await vi.waitFor(() => expect(quantDataAPI.weeklyBars).toHaveBeenCalledTimes(1))

    expect(quantDataAPI.weeklyBars).toHaveBeenCalledWith({
      symbol: '600519.SH',
      start_date: undefined,
      end_date: undefined,
      limit: 43
    })
    expect(unwrap(wb.chartCycle)).toBe('weekly')
    expect(unwrap(wb.currentBars)).toEqual(weeklyRows)
  })

  it('切换到分时应调用 minuteBars 并写入 minuteBars', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    const minuteRows = [
      { trade_datetime: '2024-01-02T09:35:00', open_price: 1, close_price: 1.5, high_price: 2, low_price: 0.5, volume: 100 },
      { trade_datetime: '2024-01-02T09:40:00', open_price: 1.5, close_price: 2, high_price: 2.1, low_price: 1.4, volume: 200 },
    ]
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: minuteRows, msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    wb.minuteQuery.interval = '5m'
    wb.minuteQuery.limit = 480
    wb.minuteQuery.adjustFlag = 'qfq'

    wb.switchChartCycle('minute')
    await vi.waitFor(() => expect(quantDataAPI.minuteBars).toHaveBeenCalledTimes(1))

    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith({
      symbol: '600519.SH',
      interval: '5m',
      start_datetime: undefined,
      end_datetime: undefined,
      limit: 499,
      adjust_flag: 'qfq',
    })
    expect(unwrap(wb.chartCycle)).toBe('minute')
    expect(unwrap(wb.currentBars)).toEqual(minuteRows)
    expect(unwrap(wb.minuteBars)).toEqual(minuteRows)
  })

  it('分时查询应复用 dailyQuery 起止日期（修复 tab 切换后日期条件失效）', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    // 用户在日期选择器选了 2024-01-02 ~ 2024-01-10
    wb.dailyQuery.startDate = '2024-01-02'
    wb.dailyQuery.endDate = '2024-01-10'
    wb.minuteQuery.interval = '5m'

    await wb.loadDailyBars('minute')

    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith(expect.objectContaining({
      symbol: '600519.SH',
      interval: '5m',
      start_datetime: '2024-01-02 00:00:00',
      end_datetime: '2024-01-10 23:59:59',
    }))
  })

  it('分时查询当 minuteQuery 显式设了 datetime 时优先使用（不强制覆盖）', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    wb.dailyQuery.startDate = '2024-01-02'
    wb.dailyQuery.endDate = '2024-01-10'
    wb.minuteQuery.interval = '5m'
    // 用户在 minuteQuery 显式指定了 datetime，应优先
    wb.minuteQuery.startDatetime = '2024-01-03 09:30:00'
    wb.minuteQuery.endDatetime = '2024-01-03 15:00:00'

    await wb.loadDailyBars('minute')

    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith(expect.objectContaining({
      start_datetime: '2024-01-03 09:30:00',
      end_datetime: '2024-01-03 15:00:00',
    }))
  })

  it('分时查询当 dailyQuery 日期为空时 start_datetime 应是 undefined', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    wb.minuteQuery.interval = '5m'

    await wb.loadDailyBars('minute')

    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith(expect.objectContaining({
      start_datetime: undefined,
      end_datetime: undefined,
    }))
  })

  it('响应式查询：symbol 变化应自动触发对应周期查询', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.dailyBars).mockResolvedValue({ success: true, data: [], msg: '' })
    // chartCycle 默认 'daily'，设 symbol 应触发 dailyBars
    wb.dailyQuery.symbol = '600519.SH'
    await vi.waitFor(() => expect(quantDataAPI.dailyBars).toHaveBeenCalledTimes(1))
    expect(quantDataAPI.dailyBars).toHaveBeenCalledWith(expect.objectContaining({ symbol: '600519.SH' }))
  })

  it('响应式查询：dateRange 变化应自动触发查询（deep watch）', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.dailyBars).mockResolvedValue({ success: true, data: [], msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    await vi.waitFor(() => expect(quantDataAPI.dailyBars).toHaveBeenCalledTimes(1))
    vi.mocked(quantDataAPI.dailyBars).mockClear()

    // 用户改起止日期（picker 是连续选择；这里直接改值）
    wb.dailyQuery.dateRange = ['2024-01-02', '2024-01-10']
    await vi.waitFor(() => expect(quantDataAPI.dailyBars).toHaveBeenCalledTimes(1))
    expect(quantDataAPI.dailyBars).toHaveBeenCalledWith(expect.objectContaining({
      symbol: '600519.SH',
      start_date: '2024-01-02',
      end_date: '2024-01-10',
    }))
  })

  it('响应式查询：minute interval 变化在 minute tab 下应触发分钟查询', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    wb.dailyQuery.symbol = '600519.SH'
    wb.switchChartCycle('minute')  // 先切到 minute tab
    wb.minuteQuery.interval = '15m'  // 再改 interval
    await vi.waitFor(() => expect(quantDataAPI.minuteBars).toHaveBeenCalledTimes(1))
    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith(expect.objectContaining({
      symbol: '600519.SH',
      interval: '15m',
    }))
  })

  it('响应式查询：同一帧内 symbol+interval+chartCycle 多次变化应合并为 1 次请求', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    // 同步连续触发：symbol、interval、chartCycle
    wb.dailyQuery.symbol = '600519.SH'
    wb.minuteQuery.interval = '15m'
    wb.switchChartCycle('minute')
    // 等待 microtask flush
    await vi.waitFor(() => expect(quantDataAPI.minuteBars).toHaveBeenCalledTimes(1))
    // 等待更多 microtask 后再次断言，确保没有遗漏
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(quantDataAPI.minuteBars).toHaveBeenCalledTimes(1)
    expect(quantDataAPI.minuteBars).toHaveBeenCalledWith(expect.objectContaining({
      symbol: '600519.SH',
      interval: '15m',
    }))
  })

  it('响应式查询：symbol 为空时不触发请求（避免空查询）', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.dailyBars).mockResolvedValue({ success: true, data: [], msg: '' })
    vi.mocked(quantDataAPI.minuteBars).mockResolvedValue({ success: true, data: [], msg: '' })
    // 不设 symbol，只切 tab —— 不应触发任何请求
    wb.switchChartCycle('minute')
    wb.switchChartCycle('weekly')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(quantDataAPI.dailyBars).not.toHaveBeenCalled()
    expect(quantDataAPI.minuteBars).not.toHaveBeenCalled()
    expect(quantDataAPI.weeklyBars).not.toHaveBeenCalled()
  })

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

  it('fetchNowFromTaskForm 应透传 frequency="5m" 与 interval', async () => {
    const wb = await getWorkbench()
    const { quantDataAPI, quantTaskAPI } = await import('@/services/quantApi')
    vi.mocked(quantDataAPI.fetchNow).mockResolvedValue({
      success: true, data: { records_imported: 48 }, msg: '',
    })
    wb.taskForm.symbols = ['600519.SH']
    wb.taskForm.startDate = '2024-01-02'
    wb.taskForm.endDate = '2024-01-02'
    wb.taskForm.provider = 'baostock'
    wb.taskForm.adjustFlag = 'qfq'
    wb.taskForm.frequency = '5m'
    wb.taskForm.interval = '5m'

    await wb.fetchNowFromTaskForm()

    expect(quantDataAPI.fetchNow).toHaveBeenCalledWith({
      symbols: ['600519.SH'],
      start_date: '2024-01-02',
      end_date: '2024-01-02',
      provider: 'baostock',
      adjust_flag: 'qfq',
      frequency: '5m',
      interval: '5m',
    })
  })

  it('createTask 默认 frequency=1d, interval=5m', async () => {
    const wb = await getWorkbench()
    const { quantTaskAPI } = await import('@/services/quantApi')
    wb.taskForm.symbols = ['600519.SH']
    wb.taskForm.startDate = '2024-01-02'
    wb.taskForm.endDate = '2024-01-02'

    await wb.createTask()

    expect(quantTaskAPI.create).toHaveBeenCalledWith(
      expect.objectContaining({
        frequency: '1d',
        interval: '5m',
      })
    )
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
