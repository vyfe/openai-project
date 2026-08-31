import { computed, nextTick, proxyRefs, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Calendar,
  DocumentChecked,
  MagicStick,
  Promotion
} from '@element-plus/icons-vue'
import {
  quantBacktestAPI,
  quantDataAPI,
  quantIndustryAPI,
  quantImAPI,
  quantMemoryAPI,
  quantOperationAPI,
  quantPositionAPI,
  quantPromptAPI,
  quantReportAPI,
  quantScheduleAPI,
  quantStrategyAPI,
  quantTaskAPI
} from '@/services/quantApi'
import { formatRate, formatNumber, strategyStatusTag, buildSchedulePayload as buildSchedulePayloadImpl, displaySymbolWithName } from './quant/format'

// 类型定义已抽到 composables/quant/types.ts
import type {
  StrategyRecord,
  StrategyRunRecord,
  OperationRecord,
  BacktestRunRecord,
  ScheduleConfigRecord,
  ScheduleRunRecord,
  PromptTemplateRecord,
  ReportRecord,
  MemoryFileRecord,
  ImChannelRecord,
  DeliveryRecord,
  ImInboundEventRecord,
  PositionJournalRecord,
  PositionSummaryRecord,
  SymbolOption
} from './quant/types'


function createQuantWorkbench() {
  // 指标 warmup 由后端 compute 路由根据 indicator_names 自动决定；
  // 前端只传 symbol + 日期区间 + interval，不再加 MA_PADDING。

  const providers = ref<string[]>([])
  const symbolOptions = ref<SymbolOption[]>([])
  const symbolSearchOptions = ref<SymbolOption[]>([])
  const symbolSearchKeyword = ref('')
  const visibleSymbolOptions = computed(() => (symbolSearchKeyword.value ? symbolSearchOptions.value : symbolOptions.value))
  const importBatches = ref<any[]>([])
  const stockPoolItems = ref<SymbolOption[]>([])
  const stockPoolTotal = ref(0)
  const stockPoolPage = reactive({ limit: 20, offset: 0, keyword: '' })
  const stockPoolSelected = ref<string[]>([])
  const stockPoolLoading = ref(false)
  const clientTasks = ref<any[]>([])
  const dailyBars = ref<any[]>([])
  const weeklyBars = ref<any[]>([])
  const strategies = ref<StrategyRecord[]>([])
  const strategyRuns = ref<StrategyRunRecord[]>([])
  const strategySignals = ref<any[]>([])
  const operationRecords = ref<OperationRecord[]>([])
  const backtestRuns = ref<BacktestRunRecord[]>([])
  const scheduleConfigs = ref<ScheduleConfigRecord[]>([])
  const scheduleRuns = ref<ScheduleRunRecord[]>([])
  const industryBoards = ref<any[]>([])
  const promptTemplates = ref<PromptTemplateRecord[]>([])
  const reports = ref<ReportRecord[]>([])
  const memoryFiles = ref<MemoryFileRecord[]>([])
  const imChannels = ref<ImChannelRecord[]>([])
  const deliveryRecords = ref<DeliveryRecord[]>([])
  const imInboundEvents = ref<ImInboundEventRecord[]>([])
  const positionSummary = ref<PositionSummaryRecord[]>([])
  const positionJournal = ref<PositionJournalRecord[]>([])
  const selectedBacktestDetail = ref<BacktestRunRecord | null>(null)
  const schedulerMeta = ref<any>(null)
  const selectedReportDetail = ref<any>(null)
  const selectedMemoryDetail = ref<any>(null)
  const dashboardOverview = ref<any>(null)

  const selectedStrategyId = ref<number | null>(null)
  const selectedRunId = ref<number | null>(null)
  const selectedOperationId = ref<number | null>(null)
  const selectedBacktestId = ref<number | null>(null)
  const selectedScheduleId = ref<number | null>(null)
  const selectedScheduleRunId = ref<number | null>(null)
  const selectedPromptId = ref<number | null>(null)
  const selectedReportId = ref<number | null>(null)
  const selectedMemorySymbol = ref<string>('')
  const selectedChannelId = ref<number | null>(null)
  const selectedPositionEntryId = ref<number | null>(null)

  const loading = reactive({
    bootstrap: false,
    overview: false,
    dailyBars: false,
    importBatches: false,
    tasks: false,
    strategies: false,
    savingStrategy: false,
    runningStrategy: false,
    runs: false,
    signals: false,
    createTask: false,
    symbolSearch: false,
    savingSymbol: false,
    stockPool: false,
    fetchNow: false,
    operations: false,
    savingOperation: false,
    backtests: false,
    runningBacktest: false,
    backtestDetail: false,
    schedulerMeta: false,
    schedules: false,
    scheduleRuns: false,
    savingSchedule: false,
    manualScheduleRun: false,
    prompts: false,
    savingPrompt: false,
    reports: false,
    reportDetail: false,
    generatingReport: false,
    memoryFiles: false,
    memoryDetail: false,
    curatingMemory: false,
    imChannels: false,
    savingImChannel: false,
    deliveryRecords: false,
    imInboundEvents: false,
    sendingIm: false,
    positionSummary: false,
    positionJournal: false,
    savingPosition: false
  })

  const dailyQuery = reactive({
    symbol: '',
    startDate: '',
    endDate: '',
    dateRange: ['', ''] as [string, string],
    limit: 120
  })

  const minuteQuery = reactive({
    symbol: '',
    interval: '5m',
    startDatetime: '',
    endDatetime: '',
    limit: 480,
    adjustFlag: 'qfq'
  })

  const dailyQueryRange = ref('3m')
  const chartCycle = ref<'daily' | 'weekly' | 'minute'>('daily')
  const mainIndicator = ref<'ma' | 'boll'>('ma')
  const subIndicator = ref<'macd' | 'kdj'>('macd')
  const minuteBars = ref<any[]>([])
  const currentBars = computed(() => {
    if (chartCycle.value === 'weekly') return weeklyBars.value
    if (chartCycle.value === 'minute') return minuteBars.value
    return dailyBars.value
  })

  const indicatorState = reactive({
    loading: false,
    error: null as string | null,
    result: {} as Record<string, Record<string, any>>,
  })

  let _computeTimer: ReturnType<typeof setTimeout> | null = null
  let _computeRequestId = 0
  const COMPUTE_DEBOUNCE_MS = 300

  function _barDateKey(bar: any): string {
    const raw = bar?.trade_datetime || bar?.trade_date || ''
    if (typeof raw === 'string') return raw
    return String(raw)
  }

  async function computeIndicatorsForCurrentBars() {
    if (_computeTimer) {
      clearTimeout(_computeTimer)
      _computeTimer = null
    }
    _computeTimer = setTimeout(async () => {
      const requestId = ++_computeRequestId
      const cycle = chartCycle.value
      const interval = cycle === 'weekly' ? 'weekly'
        : cycle === 'minute' ? 'minute'
          : 'daily'
      const symbol = (cycle === 'minute'
        ? (minuteQuery.symbol || dailyQuery.symbol)
        : dailyQuery.symbol
      ).trim()
      // 用户没填 start/end 时，从已加载的 K 线推导，保持旧行为"没指定范围也算指标"
      let start_date = dailyQuery.startDate
      let end_date = dailyQuery.endDate
      if (!start_date || !end_date) {
        const sourceBars = cycle === 'minute' ? minuteBars.value
          : cycle === 'weekly' ? weeklyBars.value
            : dailyBars.value
        if (sourceBars && sourceBars.length > 0) {
          const sorted = [...sourceBars].sort((a, b) =>
            String(_barDateKey(a)).localeCompare(String(_barDateKey(b)))
          )
          start_date = String(_barDateKey(sorted[0])).slice(0, 10)
          end_date = String(_barDateKey(sorted[sorted.length - 1])).slice(0, 10)
        }
      }
      if (!symbol || !start_date || !end_date) {
        indicatorState.result = {}
        indicatorState.error = null
        indicatorState.loading = false
        return
      }
      indicatorState.loading = true
      indicatorState.error = null
      try {
        const payload: Record<string, any> = {
          symbol,
          start_date,
          end_date,
          interval,
          indicator_names: ['ma', 'boll', 'macd', 'kdj', 'td_sequential', 'bottom_structure'],
        }
        if (interval === 'minute') {
          payload.start_datetime = minuteQuery.startDatetime || `${start_date} 00:00:00`
          payload.end_datetime = minuteQuery.endDatetime || `${end_date} 23:59:59`
          payload.adjust_flag = minuteQuery.adjustFlag || dailyQuery.adjustFlag || 'qfq'
        } else {
          payload.adjust_flag = dailyQuery.adjustFlag || 'qfq'
        }
        const resp = await quantDataAPI.computeIndicators(payload)
        if (requestId !== _computeRequestId) return
        if (resp?.success && resp?.data?.results) {
          indicatorState.result = resp.data.results
        } else {
          indicatorState.error = resp?.msg || '计算指标失败'
        }
      } catch (err: any) {
        if (requestId !== _computeRequestId) return
        indicatorState.error = err?.message || '计算指标失败'
      } finally {
        if (requestId === _computeRequestId) indicatorState.loading = false
      }
    }, COMPUTE_DEBOUNCE_MS)
  }

  const maSeries = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    return bars.map((b: any) => {
      const row = map[_barDateKey(b)] || {}
      return {
        ma5: row.ma_5 ?? null,
        ma10: row.ma_10 ?? null,
        ma20: row.ma_20 ?? null,
        ma60: row.ma_60 ?? null,
      }
    })
  })

  const bollSeries = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    return bars.map((b: any) => {
      const row = map[_barDateKey(b)] || {}
      return {
        mid: row.boll_mid ?? null,
        upper: row.boll_upper ?? null,
        lower: row.boll_lower ?? null,
      }
    })
  })

  const macdSeries = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    return bars.map((b: any) => {
      const row = map[_barDateKey(b)] || {}
      return {
        dif: row.macd_dif ?? null,
        dea: row.macd_dea ?? null,
        bar: row.macd_bar ?? null,
      }
    })
  })

  const kdjSeries = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    return bars.map((b: any) => {
      const row = map[_barDateKey(b)] || {}
      return {
        k: row.kdj_k ?? null,
        d: row.kdj_d ?? null,
        j: row.kdj_j ?? null,
      }
    })
  })

  const tdMarks = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    const out: Array<{ date: string; num: number; side: 'buy' | 'sell'; kind: 'setup' | 'countdown' }> = []
    for (const b of bars) {
      const date = _barDateKey(b)
      const row = map[date]
      if (!row) continue
      const buy = row.td_buy_setup
      const sell = row.td_sell_setup
      const buyCountdown = row.td_buy_countdown
      const sellCountdown = row.td_sell_countdown
      if (typeof buy === 'number' && buy > 0) {
        out.push({ date, num: buy, side: 'buy', kind: 'setup' })
      }
      if (typeof sell === 'number' && sell > 0) {
        out.push({ date, num: sell, side: 'sell', kind: 'setup' })
      }
      // Countdown 允许不连续计数，图上只标完成的 13，避免把附加图层堆满。
      if (buyCountdown === 13) {
        out.push({ date, num: buyCountdown, side: 'buy', kind: 'countdown' })
      }
      if (sellCountdown === 13) {
        out.push({ date, num: sellCountdown, side: 'sell', kind: 'countdown' })
      }
    }
    return out
  })

  const bottomSignals = computed(() => {
    const bars = currentBars.value || []
    const map = indicatorState.result
    const out: Array<{ date: string; type: 'divergence' }> = []
    for (const b of bars) {
      const date = _barDateKey(b)
      const row = map[date]
      if (row?.bottom_divergence) {
        out.push({ date, type: 'divergence' })
      }
    }
    return out
  })

  watch(currentBars, () => {
    computeIndicatorsForCurrentBars()
  })

  const taskForm = reactive({
    symbols: [] as string[],
    startDate: '',
    endDate: '',
    dateRange: ['', ''] as [string, string],
    provider: 'auto',
    adjustFlag: 'qfq',
    frequency: '1d' as '1d' | '5m',
    interval: '5m',
    note: '',
    leaseSeconds: 600
  })

  const taskFormRange = ref('')

  const stockPoolForm = reactive({
    keyword: '',
    selectedSymbol: '',
    selectedOption: null as SymbolOption | null
  })

  const backfillForm = reactive({
    symbols: [] as string[],
    startDate: '',
    endDate: '',
    dateRange: ['', ''] as [string, string],
    lookbackDays: 730,
    provider: 'auto',
    adjustFlag: 'qfq',
    note: '',
    leaseSeconds: 600
  })

  const defaultRuleConfig = {
    logic: 'all',
    signal_type: 'watch',
    min_score: 2,
    rules: [
      { type: 'field_compare', field: 'pct_change', operator: '>=', value: 2, weight: 1, label: '涨跌幅至少 2%' },
      { type: 'close_above_ma', window: 5, weight: 1, label: '收盘站上 5 日线' },
      { type: 'volume_ratio', window: 5, operator: '>=', value: 1.2, weight: 1, label: '量比至少 1.2' }
    ]
  }

  const breakoutRuleConfig = {
    logic: 'all',
    signal_type: 'watch',
    min_score: 3,
    rules: [
      { type: 'breakout_high', window: 20, weight: 1, label: '突破前 20 日高点' },
      { type: 'field_compare', field: 'turnover_rate', operator: '>=', value: 1, weight: 1, label: '换手率至少 1%' },
      { type: 'volume_ratio', window: 5, operator: '>=', value: 1.5, weight: 1, label: '量比至少 1.5' }
    ]
  }

  const strategyPresets = [
    { key: 'trend', title: '趋势放量', summary: '适合找短期走强的日线标的', config: defaultRuleConfig },
    { key: 'breakout', title: '突破观察', summary: '适合找放量突破前高的观察名单', config: breakoutRuleConfig }
  ]

  const strategyForm = reactive({
    id: null as number | null,
    name: '',
    description: '',
    status: 'active',
    symbols: [] as string[],
    ruleConfigText: JSON.stringify(defaultRuleConfig, null, 2)
  })

  const runForm = reactive({
    tradeDate: '',
    saveAllSignals: true
  })

  const operationForm = reactive({
    id: null as number | null,
    strategyId: null as number | null,
    runId: null as number | null,
    signalId: null as number | null,
    symbol: '',
    action: 'buy',
    status: 'draft',
    resultStatus: '',
    tradeDate: '',
    price: null as number | null,
    quantity: null as number | null,
    amount: null as number | null,
    thesis: '',
    executionNote: '',
    reviewNote: '',
    resultPct: null as number | null,
    resultAmount: null as number | null,
    tagsText: ''
  })

  const backtestForm = reactive({
    strategyId: null as number | null,
    startDate: '',
    endDate: '',
    topN: 3,
    holdDays: 5,
    initialCapital: 100000,
    commissionRate: 0.001,
    slippageRate: 0.0005,
    benchmarkSymbol: '',
    symbols: [] as string[]
  })

  const scheduleForm = reactive({
    id: null as number | null,
    name: '',
    taskType: 'data_sync',
    status: 'active',
    cronExpr: '20 15 * * 1-5',
    marketCalendar: 'A_SHARE',
    timezone: 'Asia/Shanghai',
    retryMax: 1,
    retryDelaySeconds: 180,
    allowManualRun: true,
    description: '',
    dataSymbols: [] as string[],
    dataProvider: 'auto',
    dataAdjustFlag: 'qfq',
    dataFrequencies: ['1d'] as ('1d' | '5m')[],
    dataLookbackTradeDays: 20,
    dataMinuteLookbackMinutes: 1200,
    dataLeaseSeconds: 600,
    dataNote: '',
    analysisStrategyIds: [] as number[],
    analysisChannelIds: [] as number[],
    analysisSaveAllSignals: true,
    memorySymbols: [] as string[],
    memoryLookbackDays: 120,
    memoryLimit: 50,
    industryBoardIds: [] as number[],
    industryTargets: ['market', 'announcements', 'news', 'research_reports', 'indicators'] as string[],
    industryChannelIds: [] as number[]
  })

  const promptForm = reactive({
    id: null as number | null,
    strategyId: null as number | null,
    templateName: 'default',
    promptVersion: 'template-v1',
    status: 'active',
    reportType: 'test_report',
    promptTemplate: `你是量化研究助理。基于结构化 AnalysisBundle 输出受约束的 ReportDraft。\n规则：\n1. 不得虚构 bundle 中不存在的数值。\n2. 数值必须引用 bundle 中已有字段。\n3. 记忆仅用于解释增强，不得替代当天信号。\n4. 输出应包含摘要、信号概览、风险、动作建议、记忆引用。`,
    changeNote: ''
  })

  const imChannelForm = reactive({
    id: null as number | null,
    name: '',
    status: 'active',
    receiveIdType: 'chat_id',
    receiveId: '',
    inboundChatId: '',
    replyInThread: false,
    description: ''
  })

  const imSendForm = reactive({
    channelId: null as number | null,
    reportId: null as number | null,
    strategyId: null as number | null,
    testContent: '量化模块 IM 联调测试'
  })

  const positionForm = reactive({
    id: null as number | null,
    strategyId: null as number | null,
    runId: null as number | null,
    operationId: null as number | null,
    symbol: '',
    side: 'buy',
    price: null as number | null,
    quantity: 100,
    occurredAt: '',
    source: 'manual',
    reason: '',
    remark: ''
  })

  const selectedStrategy = computed(() => strategies.value.find(item => item.id === selectedStrategyId.value) || null)
  const selectedRun = computed(() => strategyRuns.value.find(item => item.id === selectedRunId.value) || null)
  const selectedOperation = computed(() => operationRecords.value.find(item => item.id === selectedOperationId.value) || null)
  const selectedBacktest = computed(() => selectedBacktestDetail.value || backtestRuns.value.find(item => item.id === selectedBacktestId.value) || null)
  const selectedSchedule = computed(() => scheduleConfigs.value.find(item => item.id === selectedScheduleId.value) || null)
  const selectedScheduleRun = computed(() => scheduleRuns.value.find(item => item.id === selectedScheduleRunId.value) || null)
  const selectedScheduleRunLogText = computed(() => selectedScheduleRun.value?.log_tail || '')
  const selectedPrompt = computed(() => promptTemplates.value.find(item => item.id === selectedPromptId.value) || null)
  const selectedReport = computed(() => selectedReportDetail.value || reports.value.find(item => item.id === selectedReportId.value) || null)
  const selectedImChannel = computed(() => imChannels.value.find(item => item.id === selectedChannelId.value) || null)
  const selectedPositionEntry = computed(() => positionJournal.value.find(item => item.id === selectedPositionEntryId.value) || null)
  const selectedReportBundle = computed(() => selectedReportDetail.value?.analysis_bundle || selectedReportDetail.value?.analysis_bundle_json || {})
  const selectedReportDraft = computed(() => selectedReportDetail.value?.report_draft || selectedReportDetail.value?.report_draft_json || {})
  const selectedReportMeta = computed(() => selectedReportDetail.value?.meta || {})
  const selectedMemorySummary = computed(() => selectedMemoryDetail.value?.summary || {})
  const selectedMemorySections = computed(() => selectedMemoryDetail.value?.sections || {})

  const reportContractCards = computed(() => [
    { title: 'Bundle 版本', value: selectedReportBundle.value?.bundle_version || '--' },
    { title: 'Prompt 版本', value: selectedReportDraft.value?.prompt_version || selectedReport.value?.prompt_version || '--' },
    { title: '风险标记', value: String((selectedReportBundle.value?.risk_flags || []).length || 0) },
    { title: '记忆引用', value: String((selectedReportDraft.value?.memory_references || []).length || 0) }
  ])

  const memorySummaryCards = computed(() => [
    { title: '当前画像', value: String(selectedMemorySummary.value?.current_profile_count || 0) },
    { title: '近期事实', value: String(selectedMemorySummary.value?.recent_facts_count || 0) },
    { title: '人工备注', value: String(selectedMemorySummary.value?.operator_notes_count || 0) },
    { title: '待验证假设', value: String(selectedMemorySummary.value?.hypotheses_count || 0) }
  ])

  const memoryFocusLines = computed(() => [
    ...(selectedMemorySections.value?.current_profile || []).slice(0, 2),
    ...(selectedMemorySections.value?.evaluation_contract || []).slice(0, 2)
  ])

  const dashboardCards = computed(() => {
    const snapshot = dashboardOverview.value?.snapshot || {}
    return [
      { title: '最近交易日', value: snapshot.latest_trade_date || '--', hint: providers.value.join(' / ') || '等待数据源就绪', icon: Calendar },
      { title: '活跃策略', value: snapshot.active_strategies ?? strategies.value.filter(item => item.status === 'active').length, hint: '策略与规则入口已经具备', icon: MagicStick },
      { title: '待处理任务', value: snapshot.pending_tasks ?? clientTasks.value.filter(item => ['pending', 'leased'].includes(item.status)).length, hint: '客户端只负责抓数与回传', icon: Promotion },
      { title: '操作登记', value: snapshot.today_operations ?? operationRecords.value.length, hint: snapshot.successful_backtests ? `已完成回测 ${snapshot.successful_backtests} 次` : '等待人工回填执行结果', icon: DocumentChecked }
    ]
  })

  const backtestMetricCards = computed(() => {
    const metrics = selectedBacktest.value?.metrics || {}
    return [
      { title: '总收益', value: formatRate(metrics.total_return) },
      { title: '最大回撤', value: formatRate(metrics.max_drawdown) },
      { title: '胜率', value: formatRate(metrics.win_rate) },
      { title: '夏普', value: formatNumber(metrics.sharpe, 2) }
    ]
  })

  const backtestTradePreview = computed(() => (selectedBacktest.value?.trades || []).slice(0, 40))

  const schedulerCards = computed(() => {
    const overview = schedulerMeta.value?.overview || {}
    return [
      { title: '启用配置', value: overview.active_configs ?? scheduleConfigs.value.filter(item => item.status === 'active').length },
      { title: '待执行', value: overview.pending_runs ?? scheduleRuns.value.filter(item => ['pending', 'retry_wait'].includes(item.status)).length },
      { title: '失败记录', value: overview.failed_runs ?? scheduleRuns.value.filter(item => item.status === 'failed').length },
      { title: '最新数据日', value: schedulerMeta.value?.latest_market_data_date || '--' }
    ]
  })

  const positionSummaryCards = computed(() => {
    const totalMarketValue = positionSummary.value.reduce((sum, item) => sum + Number(item.market_value || 0), 0)
    const totalPnl = positionSummary.value.reduce((sum, item) => sum + Number(item.unrealized_pnl || 0), 0)
    return [
      { title: '持仓标的', value: String(positionSummary.value.length) },
      { title: '市值合计', value: formatNumber(totalMarketValue, 2) },
      { title: '浮盈合计', value: formatNumber(totalPnl, 2) },
      { title: '流水条数', value: String(positionJournal.value.length) }
    ]
  })

  const backtestCurvePath = computed(() => {
    const points = selectedBacktest.value?.equity_curve || []
    if (points.length < 2) return ''
    const width = 760
    const height = 220
    const padding = 18
    const values = points.map(point => Number(point.net_value) || 0)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = max - min || 1
    return points
      .map((point, index) => {
        const x = padding + ((width - padding * 2) * index) / Math.max(points.length - 1, 1)
        const y = padding + ((max - (Number(point.net_value) || 0)) / span) * (height - padding * 2)
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
      })
      .join(' ')
  })


  const taskStatusTag = (status: string) => {
    if (status === 'success') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'leased') return 'warning'
    return 'info'
  }

  const operationStatusTag = (status: string) => {
    if (status === 'closed') return 'success'
    if (status === 'executed') return 'warning'
    if (status === 'cancelled') return 'info'
    return ''
  }

  const operationResultTag = (status: string) => {
    if (status === 'win') return 'success'
    if (status === 'loss') return 'danger'
    if (status === 'flat') return 'info'
    return ''
  }

  const backtestStatusTag = (status: string) => {
    if (status === 'success') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'running') return 'warning'
    return 'info'
  }



  const resolveStrategyName = (strategyId?: number | null) => {
    if (!strategyId) return '未绑定策略'
    return strategies.value.find(item => item.id === strategyId)?.name || `策略 #${strategyId}`
  }

  // 把 symbol 代码渲染成"名称（代码）"展示串。优先用 symbolOptions 缓存的 name，
  // 没有 name 时回退到 symbol 本身（保证列永远可读）。适用于后端只返回 symbol
  // 不返回 name 的列表（signals/operations/memory/position/backtest trades）。
  const displaySymbol = (symbol: string): string => displaySymbolWithName(
    symbol,
    (s) => symbolOptions.value.find(item => item.symbol === s)?.name,
  )

  const applyStrategyPreset = (config: Record<string, any>) => {
    strategyForm.ruleConfigText = JSON.stringify(config, null, 2)
  }

  const syncStrategyContext = (strategy: StrategyRecord | null) => {
    if (!strategy) return
    operationForm.strategyId = strategy.id
    backtestForm.strategyId = strategy.id
    backtestForm.symbols = [...(strategy.symbols || [])]
    positionForm.strategyId = strategy.id
    imSendForm.strategyId = strategy.id
    if (!scheduleForm.analysisStrategyIds.length) scheduleForm.analysisStrategyIds = [strategy.id]
  }

  const resetStrategyForm = () => {
    selectedStrategyId.value = null
    strategyForm.id = null
    strategyForm.name = ''
    strategyForm.description = ''
    strategyForm.status = 'active'
    strategyForm.symbols = []
    strategyForm.ruleConfigText = JSON.stringify(defaultRuleConfig, null, 2)
  }

  const hydrateStrategyForm = (strategy: StrategyRecord) => {
    selectedStrategyId.value = strategy.id
    strategyForm.id = strategy.id
    strategyForm.name = strategy.name
    strategyForm.description = strategy.description || ''
    strategyForm.status = strategy.status
    strategyForm.symbols = [...(strategy.symbols || [])]
    strategyForm.ruleConfigText = JSON.stringify(strategy.rule_config || defaultRuleConfig, null, 2)
    syncStrategyContext(strategy)
  }

  const resetOperationForm = () => {
    selectedOperationId.value = null
    Object.assign(operationForm, {
      id: null,
      strategyId: selectedStrategyId.value,
      runId: null,
      signalId: null,
      symbol: '',
      action: 'buy',
      status: 'draft',
      resultStatus: '',
      tradeDate: '',
      price: null,
      quantity: null,
      amount: null,
      thesis: '',
      executionNote: '',
      reviewNote: '',
      resultPct: null,
      resultAmount: null,
      tagsText: ''
    })
  }

  const hydrateOperationForm = (record: OperationRecord) => {
    selectedOperationId.value = record.id
    operationForm.id = record.id
    operationForm.strategyId = record.strategy_id || null
    operationForm.runId = record.run_id || null
    operationForm.signalId = record.signal_id || null
    operationForm.symbol = record.symbol
    operationForm.action = record.action || 'buy'
    operationForm.status = record.status || 'draft'
    operationForm.resultStatus = record.result_status || ''
    operationForm.tradeDate = record.trade_date || ''
    operationForm.price = record.price ?? null
    operationForm.quantity = record.quantity ?? null
    operationForm.amount = record.amount ?? null
    operationForm.thesis = record.thesis || ''
    operationForm.executionNote = record.execution_note || ''
    operationForm.reviewNote = record.review_note || ''
    operationForm.resultPct = record.result_pct ?? null
    operationForm.resultAmount = record.result_amount ?? null
    operationForm.tagsText = (record.tags || []).join(', ')
  }

  const prefillOperationFromSignal = (signal: any) => {
    selectedOperationId.value = null
    operationForm.id = null
    operationForm.strategyId = signal.strategy_id || selectedStrategyId.value
    operationForm.runId = signal.run_id || selectedRunId.value
    operationForm.signalId = signal.id || null
    operationForm.symbol = signal.symbol || ''
    operationForm.action = 'buy'
    operationForm.status = 'draft'
    operationForm.resultStatus = ''
    operationForm.tradeDate = signal.trade_date || ''
    operationForm.price = signal.metrics?.close_price ?? null
    operationForm.quantity = null
    operationForm.amount = null
    operationForm.thesis = Array.isArray(signal.reasons) ? signal.reasons.join('\n') : ''
    operationForm.executionNote = ''
    operationForm.reviewNote = ''
    operationForm.resultPct = null
    operationForm.resultAmount = null
    operationForm.tagsText = signal.signal_type || ''
  }

  const handleStrategySelect = async (strategy: StrategyRecord) => {
    hydrateStrategyForm(strategy)
    selectedRunId.value = null
    strategySignals.value = []
    await Promise.all([loadRuns(), loadBacktests(), loadPositionSummary(), loadPositionJournal()])
  }

  const handleOperationSelect = (record: OperationRecord) => hydrateOperationForm(record)
  const handleBacktestSelect = async (record: BacktestRunRecord) => { await loadBacktestDetail(record.id) }

  const resetImChannelForm = () => {
    selectedChannelId.value = null
    Object.assign(imChannelForm, {
      id: null,
      name: '',
      status: 'active',
      receiveIdType: 'chat_id',
      receiveId: '',
      inboundChatId: '',
      replyInThread: false,
      description: ''
    })
  }

  const hydrateImChannelForm = (record: ImChannelRecord) => {
    selectedChannelId.value = record.id
    imChannelForm.id = record.id
    imChannelForm.name = record.name
    imChannelForm.status = record.status
    imChannelForm.receiveIdType = record.config?.receive_id_type || 'chat_id'
    imChannelForm.receiveId = record.config?.receive_id || ''
    imChannelForm.inboundChatId = record.config?.inbound_chat_id || ''
    imChannelForm.replyInThread = record.config?.reply_in_thread === true
    imChannelForm.description = record.description || ''
    imSendForm.channelId = record.id
  }

  const resetPositionForm = () => {
    selectedPositionEntryId.value = null
    Object.assign(positionForm, {
      id: null,
      strategyId: selectedStrategyId.value,
      runId: null,
      operationId: null,
      symbol: '',
      side: 'buy',
      price: null,
      quantity: 100,
      occurredAt: '',
      source: 'manual',
      reason: '',
      remark: ''
    })
  }

  const hydratePositionForm = (record: PositionJournalRecord) => {
    selectedPositionEntryId.value = record.id
    positionForm.id = record.id
    positionForm.strategyId = record.strategy_id || null
    positionForm.runId = record.run_id || null
    positionForm.operationId = record.operation_id || null
    positionForm.symbol = record.symbol
    positionForm.side = record.side
    positionForm.price = record.price ?? null
    positionForm.quantity = record.quantity || 100
    positionForm.occurredAt = (record.occurred_at || '').slice(0, 19)
    positionForm.source = record.source || 'manual'
    positionForm.reason = record.reason || ''
    positionForm.remark = record.remark || ''
  }

  const resetPromptForm = () => {
    selectedPromptId.value = null
    Object.assign(promptForm, {
      id: null,
      strategyId: selectedStrategyId.value,
      templateName: 'default',
      promptVersion: 'template-v1',
      status: 'active',
      reportType: 'test_report',
      promptTemplate: `你是量化研究助理。基于结构化 AnalysisBundle 输出受约束的 ReportDraft。\n规则：\n1. 不得虚构 bundle 中不存在的数值。\n2. 数值必须引用 bundle 中已有字段。\n3. 记忆仅用于解释增强，不得替代当天信号。\n4. 输出应包含摘要、信号概览、风险、动作建议、记忆引用。`,
      changeNote: ''
    })
  }

  const hydratePromptForm = (record: PromptTemplateRecord) => {
    selectedPromptId.value = record.id
    promptForm.id = record.id
    promptForm.strategyId = record.strategy_id || null
    promptForm.templateName = record.template_name
    promptForm.promptVersion = record.prompt_version
    promptForm.status = record.status
    promptForm.reportType = record.report_type
    promptForm.promptTemplate = record.prompt_template
    promptForm.changeNote = record.change_note || ''
  }

  const resetScheduleForm = () => {
    selectedScheduleId.value = null
    Object.assign(scheduleForm, {
      id: null,
      name: '',
      taskType: 'data_sync',
      status: 'active',
      cronExpr: '20 15 * * 1-5',
      marketCalendar: 'A_SHARE',
      timezone: 'Asia/Shanghai',
      retryMax: 1,
      retryDelaySeconds: 180,
      allowManualRun: true,
      description: '',
      dataSymbols: [],
      dataProvider: 'auto',
      dataAdjustFlag: 'qfq',
      dataLookbackTradeDays: 20,
      dataMinuteLookbackMinutes: 1200,
      dataLeaseSeconds: 600,
      dataNote: '',
      analysisStrategyIds: selectedStrategyId.value ? [selectedStrategyId.value] : [],
      analysisChannelIds: [],
      analysisSaveAllSignals: true,
      memorySymbols: [],
      memoryLookbackDays: 120,
      memoryLimit: 50,
      industryBoardIds: [],
      industryTargets: ['market', 'announcements', 'news', 'research_reports', 'indicators'],
      industryChannelIds: []
    })
    // 就地变更 dataFrequencies：保留同一个 reactive 引用，让 el-checkbox-group 的内部
    // 状态不会因为 reset 而错位（避免"重置后再勾选不响应"这类隐性 bug）。
    scheduleForm.dataFrequencies.splice(0, scheduleForm.dataFrequencies.length, '1d')
  }

  const hydrateScheduleForm = (record: ScheduleConfigRecord) => {
    selectedScheduleId.value = record.id
    scheduleForm.id = record.id
    scheduleForm.name = record.name
    scheduleForm.taskType = record.task_type
    scheduleForm.status = record.status
    scheduleForm.cronExpr = record.cron_expr
    scheduleForm.marketCalendar = record.market_calendar
    scheduleForm.timezone = record.timezone
    scheduleForm.retryMax = record.retry_max
    scheduleForm.retryDelaySeconds = record.retry_delay_seconds
    scheduleForm.allowManualRun = record.allow_manual_run
    scheduleForm.description = record.description || ''
    const payload = record.payload || {}
    scheduleForm.dataSymbols = payload.symbols || []
    scheduleForm.dataProvider = payload.provider || 'auto'
    scheduleForm.dataAdjustFlag = payload.adjust_flag || 'qfq'
    // 兼容旧 payload.frequency 单值 + 新 payload.frequencies 列表
    const frequenciesRaw = (Array.isArray(payload.frequencies) && payload.frequencies.length > 0)
      ? payload.frequencies
      : [payload.frequency || '1d']
    const filteredFrequencies = frequenciesRaw.filter((f: string) => f === '1d' || f === '5m')
    // 就地变更：保留同一个 reactive Proxy 数组的引用，避免 el-checkbox-group
    // 内部对旧数组的引用错位（整体赋值会让 click 写入的是新数组副本，
    // 而 v-model 期望回填的对象不是同一个 Proxy）。
    scheduleForm.dataFrequencies.splice(0, scheduleForm.dataFrequencies.length, ...filteredFrequencies)
    console.debug('[schedule.hydrate] payload.frequencies=', payload.frequencies, 'payload.frequency=', payload.frequency, '→ dataFrequencies=', [...scheduleForm.dataFrequencies])
    scheduleForm.dataLookbackTradeDays = payload.lookback_trade_days || 20
    // 兼容旧 payload：minute_lookback_minutes 优先；旧别名 lookback_minutes 回退
    scheduleForm.dataMinuteLookbackMinutes = payload.minute_lookback_minutes || payload.lookback_minutes || 1200
    scheduleForm.dataLeaseSeconds = payload.lease_seconds || 600
    scheduleForm.dataNote = payload.note || ''
    scheduleForm.analysisStrategyIds = payload.strategy_ids || []
    scheduleForm.analysisChannelIds = payload.channel_ids || []
    scheduleForm.analysisSaveAllSignals = payload.save_all_signals !== false
    scheduleForm.memorySymbols = payload.symbols || []
    scheduleForm.memoryLookbackDays = payload.lookback_days || 120
    scheduleForm.memoryLimit = payload.limit || 50
    scheduleForm.industryBoardIds = payload.board_ids || (payload.board_id ? [payload.board_id] : [])
    scheduleForm.industryTargets = payload.targets || ['market', 'announcements', 'news', 'research_reports', 'indicators']
    scheduleForm.industryChannelIds = payload.channel_ids || []
  }


  const loadOverview = async () => {
    loading.overview = true
    try {
      const response: any = await quantDataAPI.dashboardOverview()
      dashboardOverview.value = response.data || null
    } finally {
      loading.overview = false
    }
  }

  const loadSchedulerMeta = async () => {
    loading.schedulerMeta = true
    try {
      const response: any = await quantScheduleAPI.meta()
      schedulerMeta.value = response.data || null
    } finally {
      loading.schedulerMeta = false
    }
  }

  const loadPromptTemplates = async () => {
    loading.prompts = true
    try {
      const response: any = await quantPromptAPI.list({ report_type: 'test_report' })
      promptTemplates.value = response.data || []
    } finally {
      loading.prompts = false
    }
  }

  const loadReports = async () => {
    loading.reports = true
    try {
      const response: any = await quantReportAPI.list({ limit: 80 })
      reports.value = response.data || []
    } finally {
      loading.reports = false
    }
  }

  const loadReportDetail = async (reportId?: number | null) => {
    const finalId = reportId ?? selectedReportId.value
    if (!finalId) {
      selectedReportDetail.value = null
      return
    }
    loading.reportDetail = true
    try {
      const response: any = await quantReportAPI.get(finalId)
      selectedReportDetail.value = response.data || null
      selectedReportId.value = finalId
      imSendForm.reportId = finalId
    } finally {
      loading.reportDetail = false
    }
  }

  const loadMemoryFiles = async () => {
    loading.memoryFiles = true
    try {
      const response: any = await quantMemoryAPI.files({ limit: 100 })
      memoryFiles.value = response.data || []
    } finally {
      loading.memoryFiles = false
    }
  }

  const loadMemoryDetail = async (symbol?: string) => {
    const finalSymbol = symbol || selectedMemorySymbol.value
    if (!finalSymbol) {
      selectedMemoryDetail.value = null
      return
    }
    loading.memoryDetail = true
    try {
      const response: any = await quantMemoryAPI.get(finalSymbol)
      selectedMemoryDetail.value = response.data || null
      selectedMemorySymbol.value = finalSymbol
    } finally {
      loading.memoryDetail = false
    }
  }

  const loadImChannels = async () => {
    loading.imChannels = true
    try {
      const response: any = await quantImAPI.channels()
      imChannels.value = response.data || []
      if (selectedChannelId.value) {
        const matched = imChannels.value.find(item => item.id === selectedChannelId.value)
        if (matched) hydrateImChannelForm(matched)
      }
    } finally {
      loading.imChannels = false
    }
  }

  const loadDeliveryRecords = async () => {
    loading.deliveryRecords = true
    try {
      const response: any = await quantImAPI.deliveries({ limit: 80 })
      deliveryRecords.value = response.data || []
    } finally {
      loading.deliveryRecords = false
    }
  }

  const loadImInboundEvents = async () => {
    loading.imInboundEvents = true
    try {
      const response: any = await quantImAPI.inboundEvents({ limit: 80 })
      imInboundEvents.value = response.data || []
    } finally {
      loading.imInboundEvents = false
    }
  }

  const loadPositionSummary = async () => {
    loading.positionSummary = true
    try {
      const response: any = await quantPositionAPI.summary({ strategy_id: selectedStrategyId.value || undefined })
      positionSummary.value = response.data || []
    } finally {
      loading.positionSummary = false
    }
  }

  const loadPositionJournal = async () => {
    loading.positionJournal = true
    try {
      const response: any = await quantPositionAPI.journal({ strategy_id: selectedStrategyId.value || undefined, limit: 80 })
      positionJournal.value = response.data || []
    } finally {
      loading.positionJournal = false
    }
  }

  const loadProviders = async () => {
    const response: any = await quantDataAPI.providers()
    providers.value = response.data?.providers || []
  }

  const loadSymbols = async () => {
    const response: any = await quantDataAPI.symbols({ limit: 500 })
    const payload = response.data
    symbolOptions.value = Array.isArray(payload) ? payload : (payload?.items || [])
  }

  const loadStockPool = async () => {
    loading.stockPool = true
    try {
      const response: any = await quantDataAPI.symbols({
        limit: stockPoolPage.limit,
        offset: stockPoolPage.offset,
        keyword: stockPoolPage.keyword || undefined
      })
      const payload = response.data || {}
      stockPoolItems.value = payload.items || []
      stockPoolTotal.value = Number(payload.total) || 0
      // 清理失效的选中（被删的 symbol 不应该留在 selected 里）
      stockPoolSelected.value = stockPoolSelected.value.filter(sym =>
        stockPoolItems.value.some(item => item.symbol === sym)
      )
    } catch (error: any) {
      ElMessage.error(error?.message || '加载股票池失败')
    } finally {
      loading.stockPool = false
    }
  }

  const deletePoolSymbol = async (symbol: string) => {
    try {
      await ElMessageBox.confirm(`确认从股票池移除 ${symbol}？该操作将停止该标的的同步任务调度。`, '删除股票', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
    loading.savingSymbol = true
    try {
      const response: any = await quantDataAPI.deleteSymbol(symbol)
      ElMessage.success(response?.msg || `已删除 ${symbol}`)
      stockPoolSelected.value = stockPoolSelected.value.filter(s => s !== symbol)
      await Promise.all([loadStockPool(), loadSymbols()])
    } catch (error: any) {
      ElMessage.error(error?.message || `删除 ${symbol} 失败`)
    } finally {
      loading.savingSymbol = false
    }
  }

  const batchDeletePoolSymbols = async (symbols?: string[]) => {
    const targets = symbols && symbols.length ? symbols : stockPoolSelected.value
    if (!targets.length) {
      ElMessage.warning('请先选择要删除的股票')
      return
    }
    try {
      await ElMessageBox.confirm(`确认从股票池批量移除 ${targets.length} 个标的？`, '批量删除', {
        type: 'warning',
        confirmButtonText: '批量删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
    loading.savingSymbol = true
    try {
      const response: any = await quantDataAPI.batchDeleteSymbols(targets)
      const data = response?.data || {}
      const deletedCount = (data.deleted || []).length
      const missingCount = (data.missing || []).length
      const msg = missingCount > 0
        ? `删除 ${deletedCount} 条，${missingCount} 条已不在池中`
        : `已删除 ${deletedCount} 个标的`
      ElMessage.success(msg)
      stockPoolSelected.value = []
      await Promise.all([loadStockPool(), loadSymbols()])
    } catch (error: any) {
      ElMessage.error(error?.message || '批量删除失败')
    } finally {
      loading.savingSymbol = false
    }
  }

  const mergeSymbolOptions = (items: SymbolOption[] = []) => {
    const merged = new Map<string, SymbolOption>()
    for (const item of symbolOptions.value) {
      if (item?.symbol) merged.set(item.symbol, item)
    }
    for (const item of items) {
      if (!item?.symbol) continue
      merged.set(item.symbol, { ...merged.get(item.symbol), ...item })
    }
    symbolOptions.value = Array.from(merged.values()).sort((a, b) => a.symbol.localeCompare(b.symbol))
  }

  const normalizeSymbolInputOption = (value: string): SymbolOption | null => {
    const raw = String(value || '').trim()
    if (!raw) return null
    const upper = raw.toUpperCase()
    if (!/^\d{6}(\.(SH|SZ|BJ))?$/.test(upper)) return null
    const code = upper.includes('.') ? upper.split('.')[0] : upper
    let exchange = upper.includes('.') ? upper.split('.')[1] : ''
    if (!exchange) {
      if (/^[659]/.test(code)) exchange = 'SH'
      else if (/^[023]/.test(code)) exchange = 'SZ'
      else if (/^[48]/.test(code)) exchange = 'BJ'
    }
    const symbol = exchange ? `${code}.${exchange}` : upper
    return { symbol, code, exchange, name: '' }
  }

  const searchSymbols = async (keyword: string) => {
    const finalKeyword = String(keyword || '').trim()
    symbolSearchKeyword.value = finalKeyword
    if (!finalKeyword) {
      symbolSearchOptions.value = []
      return []
    }
    symbolSearchOptions.value = []
    loading.symbolSearch = true
    try {
      const response: any = await quantDataAPI.symbolSearch({ keyword: finalKeyword, limit: 20 })
      const results: SymbolOption[] = response.data || []
      const direct = normalizeSymbolInputOption(finalKeyword)
      const withDirect = direct && !results.some(item => item.symbol === direct.symbol)
        ? [direct, ...results]
        : results
      symbolSearchOptions.value = withDirect
      return withDirect
    } finally {
      loading.symbolSearch = false
    }
  }

  const handleStockPoolSelect = (symbol: string) => {
    const normalized = normalizeSymbolInputOption(symbol)
    const searchKey = normalized?.symbol || symbol
    const matched = [...symbolSearchOptions.value, ...symbolOptions.value].find(
      item => item.symbol === searchKey || item.symbol === symbol || item.code === symbol
    )
    stockPoolForm.selectedSymbol = matched?.symbol || searchKey
    stockPoolForm.selectedOption = matched || normalized || { symbol, name: '' }
  }

  const addSelectedSymbolToPool = async () => {
    let option = stockPoolForm.selectedOption
    if (!option?.name) {
      // name 为空：先尝试从搜索结果或已有股票池回填，避免存进 DB 后是空字符串
      const keyword = (stockPoolForm.keyword || stockPoolForm.selectedSymbol || '').trim()
      if (keyword) {
        try {
          await searchSymbols(keyword)
        } catch {
          // 搜索失败也继续 upsert，name 留空
        }
        const normalized = normalizeSymbolInputOption(keyword) || normalizeSymbolInputOption(option?.symbol || '')
        const hit = symbolSearchOptions.value.find(item =>
          item.symbol === normalized?.symbol || item.code === normalized?.code
        )
        if (hit) option = hit
        else if (normalized) option = { ...normalized, name: '' }
      }
    }
    if (!option?.symbol) {
      ElMessage.warning('先搜索并选择一个股票')
      return
    }
    loading.savingSymbol = true
    try {
      const response: any = await quantDataAPI.upsertSymbol({
        symbol: option.symbol,
        code: option.code,
        exchange: option.exchange,
        name: option.name || '',
        source: option.source || 'manual_search'
      })
      const saved = response.data || option
      mergeSymbolOptions([saved])
      stockPoolForm.selectedSymbol = saved.symbol
      stockPoolForm.selectedOption = saved
      ElMessage.success(`已加入股票池：${saved.symbol}${saved.name ? ` · ${saved.name}` : ''}`)
      await loadSymbols()
    } catch (error: any) {
      ElMessage.error(error?.message || '加入股票池失败')
    } finally {
      loading.savingSymbol = false
    }
  }

  const loadIndustryBoards = async () => {
    await quantIndustryAPI.initDefaults()
    const response: any = await quantIndustryAPI.boards({ status: 'active' })
    industryBoards.value = response.data || []
  }

  const loadImportBatches = async () => {
    loading.importBatches = true
    try {
      const response: any = await quantDataAPI.importBatches({ limit: 8 })
      importBatches.value = response.data || []
    } finally {
      loading.importBatches = false
    }
  }

  const loadTasks = async () => {
    loading.tasks = true
    try {
      const response: any = await quantTaskAPI.list({ limit: 12 })
      clientTasks.value = response.data || []
    } finally {
      loading.tasks = false
    }
  }

  const loadDailyBars = async (cycle?: 'daily' | 'weekly' | 'minute') => {
    const target = cycle || chartCycle.value
    if (!dailyQuery.symbol.trim()) {
      ElMessage.warning('先输入或选择一个股票代码')
      return
    }
    loading.dailyBars = true
    try {
      let response: any
      let rows: any[] = []
      if (target === 'minute') {
        // 分时：调用 minuteBars；symbol 优先用 minuteQuery.symbol 兼容
        const symbol = (minuteQuery.symbol || dailyQuery.symbol).trim()
        // 起止时间条件复用 dailyQuery 的日期选择器：把日期补成 YYYY-MM-DD 00:00:00 / 23:59:59
        // 后端 fetch_minute_bars 用 parse_trade_datetime 解析，纯日期也能匹配。
        const startDatetime = minuteQuery.startDatetime
          || (dailyQuery.startDate ? `${dailyQuery.startDate} 00:00:00` : undefined)
        const endDatetime = minuteQuery.endDatetime
          || (dailyQuery.endDate ? `${dailyQuery.endDate} 23:59:59` : undefined)
        response = await quantDataAPI.minuteBars({
          symbol,
          interval: minuteQuery.interval,
          start_datetime: startDatetime,
          end_datetime: endDatetime,
          limit: minuteQuery.limit,
          adjust_flag: minuteQuery.adjustFlag
        })
        rows = response.data || []
        minuteBars.value = rows
      } else {
        const apiCall = target === 'weekly' ? quantDataAPI.weeklyBars : quantDataAPI.dailyBars
        const baseLimit = target === 'weekly'
          ? Math.max(Math.floor(dailyQuery.limit / 5), 24)
          : dailyQuery.limit
        response = await apiCall({
          symbol: dailyQuery.symbol.trim(),
          start_date: dailyQuery.startDate || undefined,
          end_date: dailyQuery.endDate || undefined,
          limit: baseLimit
        })
        rows = response.data || []
        if (target === 'weekly') weeklyBars.value = rows
        else dailyBars.value = rows
      }
      if (!rows.length) {
        const label = target === 'weekly' ? '周线' : target === 'minute' ? '分时' : '日线'
        ElMessage.info(`当前条件下没有查询到${label}数据`)
      }
    } catch (error: any) {
      const label = target === 'weekly' ? '周线' : target === 'minute' ? '分时' : '日线'
      ElMessage.error(error?.message || `查询${label}失败`)
    } finally {
      loading.dailyBars = false
    }
  }

  const switchChartCycle = (cycle: 'daily' | 'weekly' | 'minute') => {
    if (chartCycle.value === cycle) return
    chartCycle.value = cycle
    // 加载由 watch(chartCycle) 自动触发，无需在这里手动调用 loadDailyBars
  }

  const loadStrategies = async () => {
    loading.strategies = true
    try {
      const response: any = await quantStrategyAPI.list()
      strategies.value = response.data || []
      if (selectedStrategyId.value) {
        const matched = strategies.value.find(item => item.id === selectedStrategyId.value)
        if (matched) hydrateStrategyForm(matched)
        else resetStrategyForm()
      }
    } finally {
      loading.strategies = false
    }
  }

  const loadRuns = async () => {
    loading.runs = true
    try {
      const response: any = await quantStrategyAPI.runs({ strategy_id: selectedStrategyId.value || undefined, limit: 40 })
      strategyRuns.value = response.data || []
    } finally {
      loading.runs = false
    }
  }

  const loadSignals = async (runId?: number | null) => {
    const finalRunId = runId ?? selectedRunId.value
    if (!finalRunId) {
      strategySignals.value = []
      return
    }
    loading.signals = true
    try {
      const response: any = await quantStrategyAPI.signals({ run_id: finalRunId, limit: 300 })
      strategySignals.value = response.data || []
      selectedRunId.value = finalRunId
    } finally {
      loading.signals = false
    }
  }

  const loadOperations = async () => {
    loading.operations = true
    try {
      const response: any = await quantOperationAPI.list({ limit: 80 })
      operationRecords.value = response.data || []
    } finally {
      loading.operations = false
    }
  }

  const loadBacktests = async () => {
    loading.backtests = true
    try {
      const response: any = await quantBacktestAPI.list({ strategy_id: selectedStrategyId.value || undefined, limit: 40 })
      backtestRuns.value = response.data || []
    } finally {
      loading.backtests = false
    }
  }

  const loadBacktestDetail = async (backtestId?: number | null) => {
    const finalId = backtestId ?? selectedBacktestId.value
    if (!finalId) {
      selectedBacktestDetail.value = null
      return
    }
    loading.backtestDetail = true
    try {
      const response: any = await quantBacktestAPI.get(finalId)
      selectedBacktestDetail.value = response.data || null
      selectedBacktestId.value = finalId
    } finally {
      loading.backtestDetail = false
    }
  }

  const loadScheduleConfigs = async () => {
    loading.schedules = true
    try {
      const response: any = await quantScheduleAPI.configs()
      scheduleConfigs.value = response.data || []
      if (selectedScheduleId.value) {
        const matched = scheduleConfigs.value.find(item => item.id === selectedScheduleId.value)
        if (matched) hydrateScheduleForm(matched)
      }
    } finally {
      loading.schedules = false
    }
  }

  const loadScheduleRuns = async () => {
    loading.scheduleRuns = true
    try {
      const response: any = await quantScheduleAPI.runs({ schedule_id: selectedScheduleId.value || undefined, limit: 80 })
      scheduleRuns.value = response.data || []
    } finally {
      loading.scheduleRuns = false
    }
  }

  const loadScheduleRunLog = async (runId?: number | null) => {
    const finalId = runId || selectedScheduleRunId.value
    if (!finalId) return
    try {
      const response: any = await quantScheduleAPI.getRunLog(finalId, { limit: 200 })
      const target = scheduleRuns.value.find(item => item.id === finalId)
      if (target) {
        target.log_tail = response.data?.log_tail || ''
        target.log_file = response.data?.log_file || target.log_file
      }
    } catch (error: any) {
      ElMessage.error(error?.message || '加载执行日志失败')
    }
  }

  const createTask = async () => {
    if (!taskForm.symbols.length || !taskForm.startDate || !taskForm.endDate) {
      ElMessage.warning('请先补全任务的股票池和时间范围')
      return
    }
    loading.createTask = true
    try {
      await quantTaskAPI.create({
        symbols: taskForm.symbols,
        start_date: taskForm.startDate,
        end_date: taskForm.endDate,
        provider: taskForm.provider,
        adjust_flag: taskForm.adjustFlag,
        frequency: taskForm.frequency,
        interval: taskForm.interval,
        note: taskForm.note,
        lease_seconds: taskForm.leaseSeconds
      })
      ElMessage.success('数据同步任务已创建')
      await Promise.all([loadTasks(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '创建任务失败')
    } finally {
      loading.createTask = false
    }
  }

  const fetchNowFromTaskForm = async () => {
    if (!taskForm.symbols.length || !taskForm.startDate || !taskForm.endDate) {
      ElMessage.warning('请先补全股票池和时间范围')
      return
    }
    loading.fetchNow = true
    try {
      const response: any = await quantDataAPI.fetchNow({
        symbols: taskForm.symbols,
        start_date: taskForm.startDate,
        end_date: taskForm.endDate,
        provider: taskForm.provider,
        adjust_flag: taskForm.adjustFlag,
        frequency: taskForm.frequency,
        interval: taskForm.interval
      })
      const result = response.data || {}
      const cycleLabel = taskForm.frequency === '5m' ? '分时' : '日线'
      ElMessage.success(`手动拉${cycleLabel}完成：导入 ${result.records_imported ?? result.records_total ?? 0} 条`)
      if (taskForm.symbols[0]) {
        dailyQuery.symbol = taskForm.symbols[0]
        dailyQuery.startDate = taskForm.startDate
        dailyQuery.endDate = taskForm.endDate
      }
      await Promise.all([loadImportBatches(), loadSymbols(), loadDailyBars(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '手动拉数失败')
    } finally {
      loading.fetchNow = false
    }
  }

  const createBackfillTask = async () => {
    if (!backfillForm.symbols.length) {
      ElMessage.warning('先选择需要补历史数据的股票')
      return
    }
    loading.createTask = true
    try {
      await quantDataAPI.backfill({
        symbols: backfillForm.symbols,
        lookback_days: backfillForm.lookbackDays,
        provider: backfillForm.provider,
        adjust_flag: backfillForm.adjustFlag,
        note: backfillForm.note,
        lease_seconds: backfillForm.leaseSeconds
      })
      ElMessage.success('历史补数任务已创建')
      await Promise.all([loadTasks(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '创建历史补数任务失败')
    } finally {
      loading.createTask = false
    }
  }

  const resetTask = async (taskId: string) => {
    try {
      await quantTaskAPI.reset(taskId)
      ElMessage.success('任务已重置回待领取状态')
      await Promise.all([loadTasks(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '重置任务失败')
    }
  }

  const saveStrategy = async () => {
    if (!strategyForm.name.trim()) {
      ElMessage.warning('策略名称不能为空')
      return
    }
    let parsedRuleConfig: Record<string, any>
    try {
      parsedRuleConfig = JSON.parse(strategyForm.ruleConfigText)
    } catch {
      ElMessage.error('规则 JSON 解析失败，请先修正格式')
      return
    }
    loading.savingStrategy = true
    try {
      const payload = {
        name: strategyForm.name.trim(),
        description: strategyForm.description.trim(),
        status: strategyForm.status,
        symbols: strategyForm.symbols,
        rule_config: parsedRuleConfig
      }
      if (strategyForm.id) {
        await quantStrategyAPI.update({ id: strategyForm.id, ...payload })
        ElMessage.success('策略已更新')
      } else {
        await quantStrategyAPI.create(payload)
        ElMessage.success('策略已创建')
      }
      await Promise.all([loadStrategies(), loadRuns(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '保存策略失败')
    } finally {
      loading.savingStrategy = false
    }
  }

  const deleteSelectedStrategy = async () => {
    if (!strategyForm.id) {
      ElMessage.info('先选中一个策略再删除')
      return
    }
    await ElMessageBox.confirm('删除策略会连同它的运行记录一起删除，继续吗？', '删除策略', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantStrategyAPI.delete(strategyForm.id)
      ElMessage.success('策略已删除')
      resetStrategyForm()
      await Promise.all([loadStrategies(), loadRuns(), loadBacktests(), loadOverview()])
      strategySignals.value = []
    } catch (error: any) {
      ElMessage.error(error?.message || '删除策略失败')
    }
  }

  const executeSelectedStrategy = async () => {
    if (!strategyForm.id) {
      ElMessage.info('先保存或选择一个策略')
      return null
    }
    loading.runningStrategy = true
    try {
      const response: any = await quantStrategyAPI.run({
        strategy_id: strategyForm.id,
        trade_date: runForm.tradeDate || undefined,
        save_all_signals: runForm.saveAllSignals
      })
      ElMessage.success('策略执行完成')
      await Promise.all([loadRuns(), loadOverview()])
      const runRecord = response.data
      if (runRecord?.id) await loadSignals(runRecord.id)
      return runRecord
    } catch (error: any) {
      ElMessage.error(error?.message || '执行策略失败')
      return null
    } finally {
      loading.runningStrategy = false
    }
  }

  const saveOperation = async () => {
    if (!operationForm.symbol.trim() || !operationForm.tradeDate) {
      ElMessage.warning('操作登记至少需要标的和交易日')
      return
    }
    loading.savingOperation = true
    try {
      const payload = {
        id: operationForm.id || undefined,
        strategy_id: operationForm.strategyId || undefined,
        run_id: operationForm.runId || undefined,
        signal_id: operationForm.signalId || undefined,
        symbol: operationForm.symbol.trim(),
        action: operationForm.action,
        status: operationForm.status,
        result_status: operationForm.resultStatus,
        trade_date: operationForm.tradeDate,
        price: operationForm.price,
        quantity: operationForm.quantity,
        amount: operationForm.amount,
        thesis: operationForm.thesis,
        execution_note: operationForm.executionNote,
        review_note: operationForm.reviewNote,
        result_pct: operationForm.resultPct,
        result_amount: operationForm.resultAmount,
        tags: operationForm.tagsText.split(',').map(item => item.trim()).filter(Boolean)
      }
      if (operationForm.id) {
        await quantOperationAPI.update(payload)
        ElMessage.success('操作记录已更新')
      } else {
        await quantOperationAPI.create(payload)
        ElMessage.success('操作记录已创建')
      }
      await Promise.all([loadOperations(), loadOverview()])
      resetOperationForm()
    } catch (error: any) {
      ElMessage.error(error?.message || '保存操作记录失败')
    } finally {
      loading.savingOperation = false
    }
  }

  const deleteSelectedOperation = async () => {
    if (!operationForm.id) {
      ElMessage.info('先选中一条操作记录')
      return
    }
    await ElMessageBox.confirm('删除后无法恢复，继续吗？', '删除操作记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantOperationAPI.delete(operationForm.id)
      ElMessage.success('操作记录已删除')
      await Promise.all([loadOperations(), loadOverview()])
      resetOperationForm()
    } catch (error: any) {
      ElMessage.error(error?.message || '删除操作记录失败')
    }
  }

  const runBacktest = async () => {
    if (!backtestForm.strategyId) {
      ElMessage.warning('先选中一个策略')
      return null
    }
    if (!backtestForm.startDate || !backtestForm.endDate) {
      ElMessage.warning('回测需要明确开始和结束日期')
      return null
    }
    loading.runningBacktest = true
    try {
      const response: any = await quantBacktestAPI.run({
        strategy_id: backtestForm.strategyId,
        start_date: backtestForm.startDate,
        end_date: backtestForm.endDate,
        top_n: backtestForm.topN,
        hold_days: backtestForm.holdDays,
        initial_capital: backtestForm.initialCapital,
        commission_rate: backtestForm.commissionRate,
        slippage_rate: backtestForm.slippageRate,
        benchmark_symbol: backtestForm.benchmarkSymbol || undefined,
        symbols: backtestForm.symbols
      })
      ElMessage.success('回测执行完成')
      await Promise.all([loadBacktests(), loadOverview()])
      if (response.data?.id) await loadBacktestDetail(response.data.id)
      return response.data
    } catch (error: any) {
      ElMessage.error(error?.message || '执行回测失败')
      return null
    } finally {
      loading.runningBacktest = false
    }
  }

  const deleteSelectedBacktest = async () => {
    if (!selectedBacktestId.value) {
      ElMessage.info('先选中一条回测记录')
      return
    }
    await ElMessageBox.confirm('删除后将丢失这次回测的净值曲线和交易样本，继续吗？', '删除回测记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantBacktestAPI.delete(selectedBacktestId.value)
      ElMessage.success('回测记录已删除')
      selectedBacktestId.value = null
      selectedBacktestDetail.value = null
      await Promise.all([loadBacktests(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '删除回测记录失败')
    }
  }

  const saveScheduleConfig = async () => {
    if (!scheduleForm.name.trim()) return ElMessage.warning('调度名称不能为空')
    if (!scheduleForm.cronExpr.trim()) return ElMessage.warning('cron 表达式不能为空')
    if (scheduleForm.taskType === 'data_sync' && !scheduleForm.dataSymbols.length) return ElMessage.warning('拉数任务至少选择一个标的')
    if (scheduleForm.taskType === 'analysis_report' && !scheduleForm.analysisStrategyIds.length) return ElMessage.warning('测试报告至少选择一个策略')
    if (scheduleForm.taskType === 'memory_digest' && scheduleForm.memoryLimit < 1) return ElMessage.warning('记忆梳理的标的数量至少为 1')
    if (['industry_collect', 'industry_report'].includes(scheduleForm.taskType) && !scheduleForm.industryBoardIds.length) return ElMessage.warning('行业任务至少选择一个板块')
    loading.savingSchedule = true
    try {
      const payload = buildSchedulePayload()
      // [debug] 临时日志：确认 frequencies 是否随 checkbox 勾选更新
      console.debug('[schedule.save] dataFrequencies=', [...scheduleForm.dataFrequencies], 'payload.frequencies=', [...((payload as any).frequencies || [])])
      if (scheduleForm.id) {
        await quantScheduleAPI.updateConfig({
          id: scheduleForm.id,
          name: scheduleForm.name.trim(),
          task_type: scheduleForm.taskType,
          status: scheduleForm.status,
          cron_expr: scheduleForm.cronExpr.trim(),
          market_calendar: scheduleForm.marketCalendar,
          timezone: scheduleForm.timezone,
          retry_max: scheduleForm.retryMax,
          retry_delay_seconds: scheduleForm.retryDelaySeconds,
          allow_manual_run: scheduleForm.allowManualRun,
          description: scheduleForm.description.trim(),
          payload
        })
        ElMessage.success('调度配置已更新')
      } else {
        await quantScheduleAPI.createConfig({
          name: scheduleForm.name.trim(),
          task_type: scheduleForm.taskType,
          status: scheduleForm.status,
          cron_expr: scheduleForm.cronExpr.trim(),
          market_calendar: scheduleForm.marketCalendar,
          timezone: scheduleForm.timezone,
          retry_max: scheduleForm.retryMax,
          retry_delay_seconds: scheduleForm.retryDelaySeconds,
          allow_manual_run: scheduleForm.allowManualRun,
          description: scheduleForm.description.trim(),
          payload
        })
        ElMessage.success('调度配置已创建')
      }
      await Promise.all([loadScheduleConfigs(), loadScheduleRuns(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '保存调度配置失败')
    } finally {
      loading.savingSchedule = false
    }
  }

  const deleteSelectedSchedule = async () => {
    if (!scheduleForm.id) {
      ElMessage.info('先选中一个调度配置')
      return
    }
    await ElMessageBox.confirm('删除后会一并删除该配置的执行记录，继续吗？', '删除调度配置', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantScheduleAPI.deleteConfig(scheduleForm.id)
      ElMessage.success('调度配置已删除')
      resetScheduleForm()
      await Promise.all([loadScheduleConfigs(), loadScheduleRuns(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '删除调度配置失败')
    }
  }

  const handleScheduleSelect = async (record: ScheduleConfigRecord) => {
    hydrateScheduleForm(record)
    await loadScheduleRuns()
  }

  const manualRunSchedule = async (scheduleId?: number | null) => {
    const finalId = scheduleId || scheduleForm.id
    if (!finalId) {
      ElMessage.info('先选中一个调度配置')
      return
    }
    loading.manualScheduleRun = true
    try {
      await quantScheduleAPI.manualRun(finalId)
      ElMessage.success('已创建手工执行任务，等待 worker 拉起执行')
      await Promise.all([loadScheduleRuns(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '手工触发失败')
    } finally {
      loading.manualScheduleRun = false
    }
  }

  const rebuildDueScheduleRuns = async () => {
    try {
      await quantScheduleAPI.rebuildDueRuns(180)
      ElMessage.success('已补扫最近 180 分钟的应执行记录')
      await Promise.all([loadScheduleRuns(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '补偿执行生成失败')
    }
  }

  const executeScheduleRunNow = async (runId?: number | null) => {
    const finalId = runId || selectedScheduleRunId.value
    if (!finalId) {
      ElMessage.info('先选中一条执行记录')
      return
    }
    try {
      await quantScheduleAPI.executeRun(finalId)
      ElMessage.success('执行记录已在当前服务内触发')
      await Promise.all([loadScheduleRuns(), loadSchedulerMeta(), loadOverview(), loadTasks(), loadRuns()])
      if (finalId) await loadScheduleRunLog(finalId)
    } catch (error: any) {
      ElMessage.error(error?.message || '执行调度记录失败')
    }
  }

  const resetScheduleRunNow = async (runId?: number | null, allowSuccess = false) => {
    const finalId = runId || selectedScheduleRunId.value
    if (!finalId) {
      ElMessage.info('先选中一条执行记录')
      return
    }
    try {
      await quantScheduleAPI.resetRun(finalId, allowSuccess)
      ElMessage.success('执行记录已重置回待执行')
      await Promise.all([loadScheduleRuns(), loadSchedulerMeta(), loadOverview()])
    } catch (error: any) {
      ElMessage.error(error?.message || '重置执行记录失败')
    }
  }

  const saveImChannel = async () => {
    if (!imChannelForm.name.trim()) return ElMessage.warning('IM 通道名称不能为空')
    if (!imChannelForm.receiveId.trim()) return ElMessage.warning('飞书通道 receive_id 不能为空')
    loading.savingImChannel = true
    try {
      const payload = {
        id: imChannelForm.id || undefined,
        name: imChannelForm.name.trim(),
        status: imChannelForm.status,
        config: {
          receive_id_type: imChannelForm.receiveIdType,
          receive_id: imChannelForm.receiveId.trim(),
          inbound_chat_id: imChannelForm.inboundChatId.trim(),
          reply_in_thread: imChannelForm.replyInThread
        },
        description: imChannelForm.description.trim()
      }
      if (imChannelForm.id) {
        await quantImAPI.updateChannel(payload)
        ElMessage.success('IM 通道已更新')
      } else {
        await quantImAPI.createChannel(payload)
        ElMessage.success('IM 通道已创建')
      }
      await Promise.all([loadImChannels(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '保存 IM 通道失败')
    } finally {
      loading.savingImChannel = false
    }
  }

  const deleteSelectedImChannel = async () => {
    if (!imChannelForm.id) {
      ElMessage.info('先选中一个 IM 通道')
      return
    }
    await ElMessageBox.confirm('删除后调度里的关联通道需要手工检查，继续吗？', '删除 IM 通道', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantImAPI.deleteChannel(imChannelForm.id)
      ElMessage.success('IM 通道已删除')
      resetImChannelForm()
      await Promise.all([loadImChannels(), loadSchedulerMeta()])
    } catch (error: any) {
      ElMessage.error(error?.message || '删除 IM 通道失败')
    }
  }

  const sendReportNow = async () => {
    if (!imSendForm.reportId) return ElMessage.warning('先选择一份报告')
    if (!imSendForm.channelId) return ElMessage.warning('先选择一个 IM 通道')
    loading.sendingIm = true
    try {
      await quantImAPI.sendReport({ report_id: imSendForm.reportId, channel_id: imSendForm.channelId })
      ElMessage.success('报告推送已执行')
      await loadDeliveryRecords()
    } catch (error: any) {
      ElMessage.error(error?.message || '推送报告失败')
    } finally {
      loading.sendingIm = false
    }
  }

  const sendPositionSummaryNow = async () => {
    if (!imSendForm.channelId) return ElMessage.warning('先选择一个 IM 通道')
    loading.sendingIm = true
    try {
      await quantImAPI.sendPositions({ channel_id: imSendForm.channelId, strategy_id: imSendForm.strategyId || undefined })
      ElMessage.success('持仓摘要推送已执行')
      await loadDeliveryRecords()
    } catch (error: any) {
      ElMessage.error(error?.message || '推送持仓摘要失败')
    } finally {
      loading.sendingIm = false
    }
  }

  const sendImTestNow = async () => {
    if (!imSendForm.channelId) return ElMessage.warning('先选择一个 IM 通道')
    loading.sendingIm = true
    try {
      await quantImAPI.test({ channel_id: imSendForm.channelId, content: imSendForm.testContent })
      ElMessage.success('测试消息已发送')
    } catch (error: any) {
      ElMessage.error(error?.message || '发送测试消息失败')
    } finally {
      loading.sendingIm = false
    }
  }

  const savePositionEntry = async () => {
    if (!positionForm.symbol.trim() || !positionForm.occurredAt) return ElMessage.warning('持仓流水至少需要标的和发生时间')
    loading.savingPosition = true
    try {
      const payload = {
        id: positionForm.id || undefined,
        strategy_id: positionForm.strategyId || undefined,
        run_id: positionForm.runId || undefined,
        operation_id: positionForm.operationId || undefined,
        symbol: positionForm.symbol.trim(),
        side: positionForm.side,
        price: positionForm.price,
        quantity: positionForm.quantity,
        occurred_at: positionForm.occurredAt,
        source: positionForm.source,
        reason: positionForm.reason,
        remark: positionForm.remark
      }
      if (positionForm.id) {
        await quantPositionAPI.update(payload)
        ElMessage.success('持仓流水已更新')
      } else {
        await quantPositionAPI.create(payload)
        ElMessage.success('持仓流水已创建')
      }
      await Promise.all([loadPositionSummary(), loadPositionJournal(), loadOverview()])
      resetPositionForm()
    } catch (error: any) {
      ElMessage.error(error?.message || '保存持仓流水失败')
    } finally {
      loading.savingPosition = false
    }
  }

  const deleteSelectedPositionEntry = async () => {
    if (!positionForm.id) {
      ElMessage.info('先选中一条持仓流水')
      return
    }
    await ElMessageBox.confirm('删除后会影响当前持仓汇总，继续吗？', '删除持仓流水', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantPositionAPI.delete(positionForm.id)
      ElMessage.success('持仓流水已删除')
      await Promise.all([loadPositionSummary(), loadPositionJournal(), loadOverview()])
      resetPositionForm()
    } catch (error: any) {
      ElMessage.error(error?.message || '删除持仓流水失败')
    }
  }

  const savePromptTemplate = async () => {
    if (!promptForm.promptVersion.trim()) return ElMessage.warning('Prompt 版本不能为空')
    if (!promptForm.promptTemplate.trim()) return ElMessage.warning('Prompt 模板不能为空')
    loading.savingPrompt = true
    try {
      const payload = {
        id: promptForm.id || undefined,
        strategy_id: promptForm.strategyId || undefined,
        template_name: promptForm.templateName,
        prompt_version: promptForm.promptVersion.trim(),
        status: promptForm.status,
        report_type: promptForm.reportType,
        prompt_template: promptForm.promptTemplate,
        change_note: promptForm.changeNote
      }
      if (promptForm.id) {
        await quantPromptAPI.update(payload)
        ElMessage.success('Prompt 模板已更新')
      } else {
        await quantPromptAPI.create(payload)
        ElMessage.success('Prompt 模板已创建')
      }
      await loadPromptTemplates()
    } catch (error: any) {
      ElMessage.error(error?.message || '保存 Prompt 模板失败')
    } finally {
      loading.savingPrompt = false
    }
  }

  const deleteSelectedPrompt = async () => {
    if (!promptForm.id) {
      ElMessage.info('先选中一个 Prompt 模板')
      return
    }
    await ElMessageBox.confirm('删除后无法恢复，继续吗？', '删除 Prompt 模板', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    try {
      await quantPromptAPI.delete(promptForm.id)
      ElMessage.success('Prompt 模板已删除')
      resetPromptForm()
      await loadPromptTemplates()
    } catch (error: any) {
      ElMessage.error(error?.message || '删除 Prompt 模板失败')
    }
  }

  const generateReportFromRun = async (runId?: number | null) => {
    const finalRunId = runId || selectedRunId.value
    if (!finalRunId) {
      ElMessage.info('先选中一条策略执行记录')
      return null
    }
    loading.generatingReport = true
    try {
      const response: any = await quantReportAPI.generate({ run_id: finalRunId, report_type: 'test_report' })
      ElMessage.success('测试报告已生成')
      await loadReports()
      if (response.data?.id) await loadReportDetail(response.data.id)
      return response.data
    } catch (error: any) {
      ElMessage.error(error?.message || '生成测试报告失败')
      return null
    } finally {
      loading.generatingReport = false
    }
  }

  const curateMemoryNow = async (symbol?: string) => {
    loading.curatingMemory = true
    try {
      const symbols = symbol ? [symbol] : (selectedMemorySymbol.value ? [selectedMemorySymbol.value] : undefined)
      await quantMemoryAPI.curate({
        symbols,
        lookback_days: scheduleForm.memoryLookbackDays,
        limit: symbols ? symbols.length : 30
      })
      ElMessage.success('记忆梳理完成')
      await Promise.all([loadMemoryFiles(), loadSchedulerMeta()])
      if (symbols?.[0]) await loadMemoryDetail(symbols[0])
    } catch (error: any) {
      ElMessage.error(error?.message || '记忆梳理失败')
    } finally {
      loading.curatingMemory = false
    }
  }

  const bootstrap = async () => {
    loading.bootstrap = true
    try {
      await Promise.all([
        loadOverview(),
        loadProviders(),
        loadSymbols(),
        loadStockPool(),
        loadIndustryBoards(),
        loadImportBatches(),
        loadTasks(),
        loadStrategies(),
        loadRuns(),
        loadOperations(),
        loadBacktests(),
        loadSchedulerMeta(),
        loadScheduleConfigs(),
        loadScheduleRuns(),
        loadPromptTemplates(),
        loadReports(),
        loadMemoryFiles(),
        loadImChannels(),
        loadDeliveryRecords(),
        loadImInboundEvents(),
        loadPositionSummary(),
        loadPositionJournal()
      ])
    } finally {
      loading.bootstrap = false
    }
  }

  let bootstrapPromise: Promise<void> | null = null
  const initialize = async () => {
    if (bootstrapPromise) return bootstrapPromise
    resetOperationForm()
    resetScheduleForm()
    resetPromptForm()
    resetImChannelForm()
    resetPositionForm()
    bootstrapPromise = bootstrap().finally(() => {
      bootstrapPromise = null
      // bootstrap 完成后才允许响应式查询触发，避免初始化时多余请求
      autoQueryReady = true
    })
    return bootstrapPromise
  }


  // 包装 buildSchedulePayloadImpl（来自 ./quant/format）为闭包，捕获 scheduleForm
  const buildSchedulePayload = () => buildSchedulePayloadImpl(scheduleForm)

  // 同步 daterange 与 startDate/endDate（双向）
  const syncDateRange = (form: { startDate: string; endDate: string; dateRange: [string, string] }) => {
    watch(() => form.dateRange, (v) => {
      if (!v) return
      const s = v[0] || ''
      const e = v[1] || ''
      if (form.startDate !== s) form.startDate = s
      if (form.endDate !== e) form.endDate = e
    }, { deep: true })
    watch([() => form.startDate, () => form.endDate], ([s, e]) => {
      const cur = form.dateRange || ['', '']
      const ns = s || ''
      const ne = e || ''
      if ((cur[0] || '') === ns && (cur[1] || '') === ne) return
      form.dateRange = [ns, ne]
    })
  }
  syncDateRange(dailyQuery)
  syncDateRange(taskForm)
  syncDateRange(backfillForm)

  // 响应式查询：监测 chartCycle / symbol / dateRange / interval 变化，自动触发对应周期查询。
  // 用 nextTick 去重：同一 microtask 内多次触发只执行一次（避免 symbol 同步设置时
  // 与 chartCycle 切换重叠产生重复请求）。autoQueryReady 默认 true 让测试可直接触发；
  // 生产中 bootstrap 不调 loadDailyBars，所以即便用户在 bootstrap 完成前选 symbol 也不会并发冲突。
  let autoQueryReady = true
  let autoQueryScheduled = false
  const triggerAutoQuery = () => {
    if (!autoQueryReady) return
    if (autoQueryScheduled) return
    autoQueryScheduled = true
    nextTick(() => {
      autoQueryScheduled = false
      const symbol = (dailyQuery.symbol || minuteQuery.symbol || '').trim()
      if (!symbol) return
      loadDailyBars()
    })
  }

  watch(() => chartCycle.value, triggerAutoQuery)
  watch(() => dailyQuery.symbol, triggerAutoQuery)
  watch(() => dailyQuery.dateRange, triggerAutoQuery, { deep: true })
  watch(() => minuteQuery.interval, triggerAutoQuery)

  // 调度周期 checkbox 探针：watch 数组变更，验证 el-checkbox-group 的 v-model
  // 是否真正回写到 scheduleForm.dataFrequencies（比 @change 更可靠，watch
  // 能拿到 [newVal, oldVal] 两个数组）。
  // deep: true 是必须的——splice 是 in-place mutation，数组引用不变，
  // 不加 deep watch 不会触发。
  watch(
    () => scheduleForm.dataFrequencies,
    (newVal, oldVal) => {
      console.debug('[scheduler.cycle.watch]', 'old=', [...oldVal], 'new=', [...newVal])
    },
    { deep: true }
  )
  return {
    providers,
    symbolOptions,
    symbolSearchOptions,
    visibleSymbolOptions,
    stockPoolItems,
    stockPoolTotal,
    stockPoolPage,
    stockPoolSelected,
    importBatches,
    clientTasks,
    dailyBars,
    weeklyBars,
    minuteBars,
    minuteQuery,
    chartCycle,
    mainIndicator,
    subIndicator,
    currentBars,
    indicatorState,
    maSeries,
    bollSeries,
    macdSeries,
    kdjSeries,
    tdMarks,
    bottomSignals,
    computeIndicatorsForCurrentBars,
    strategies,
    strategyRuns,
    strategySignals,
    operationRecords,
    backtestRuns,
    scheduleConfigs,
    scheduleRuns,
    industryBoards,
    promptTemplates,
    reports,
    memoryFiles,
    imChannels,
    deliveryRecords,
    imInboundEvents,
    positionSummary,
    positionJournal,
    selectedBacktestDetail,
    schedulerMeta,
    selectedReportDetail,
    selectedMemoryDetail,
    dashboardOverview,
    selectedStrategyId,
    selectedRunId,
    selectedOperationId,
    selectedBacktestId,
    selectedScheduleId,
    selectedScheduleRunId,
    selectedPromptId,
    selectedReportId,
    selectedMemorySymbol,
    selectedChannelId,
    selectedPositionEntryId,
    loading,
    dailyQuery,
    dailyQueryRange,
    taskForm,
    taskFormRange,
    stockPoolForm,
    backfillForm,
    defaultRuleConfig,
    breakoutRuleConfig,
    strategyPresets,
    strategyForm,
    runForm,
    operationForm,
    backtestForm,
    scheduleForm,
    promptForm,
    imChannelForm,
    imSendForm,
    positionForm,
    selectedStrategy,
    selectedRun,
    selectedOperation,
    selectedBacktest,
    selectedSchedule,
    selectedScheduleRun,
    selectedScheduleRunLogText,
    selectedPrompt,
    selectedReport,
    selectedImChannel,
    selectedPositionEntry,
    selectedReportBundle,
    selectedReportDraft,
    selectedReportMeta,
    selectedMemorySummary,
    selectedMemorySections,
    reportContractCards,
    memorySummaryCards,
    memoryFocusLines,
    dashboardCards,
    backtestMetricCards,
    backtestTradePreview,
    schedulerCards,
    positionSummaryCards,
    backtestCurvePath,
    strategyStatusTag,
    taskStatusTag,
    operationStatusTag,
    operationResultTag,
    backtestStatusTag,
    formatRate,
    formatNumber,
    displaySymbol,
    resolveStrategyName,
    applyStrategyPreset,
    syncStrategyContext,
    resetStrategyForm,
    hydrateStrategyForm,
    resetOperationForm,
    hydrateOperationForm,
    prefillOperationFromSignal,
    handleStrategySelect,
    handleOperationSelect,
    handleBacktestSelect,
    resetImChannelForm,
    hydrateImChannelForm,
    resetPositionForm,
    hydratePositionForm,
    resetPromptForm,
    hydratePromptForm,
    resetScheduleForm,
    hydrateScheduleForm,
    buildSchedulePayload,
    loadOverview,
    loadSchedulerMeta,
    loadPromptTemplates,
    loadReports,
    loadReportDetail,
    loadMemoryFiles,
    loadMemoryDetail,
    loadImChannels,
    loadDeliveryRecords,
    loadImInboundEvents,
    loadPositionSummary,
    loadPositionJournal,
    loadProviders,
    loadSymbols,
    loadStockPool,
    deletePoolSymbol,
    batchDeletePoolSymbols,
    searchSymbols,
    handleStockPoolSelect,
    addSelectedSymbolToPool,
    loadIndustryBoards,
    loadImportBatches,
    loadTasks,
    loadDailyBars,
    switchChartCycle,
    loadStrategies,
    loadRuns,
    loadSignals,
    loadOperations,
    loadBacktests,
    loadBacktestDetail,
    loadScheduleConfigs,
    loadScheduleRuns,
    loadScheduleRunLog,
    createTask,
    fetchNowFromTaskForm,
    createBackfillTask,
    resetTask,
    saveStrategy,
    deleteSelectedStrategy,
    executeSelectedStrategy,
    saveOperation,
    deleteSelectedOperation,
    runBacktest,
    deleteSelectedBacktest,
    saveScheduleConfig,
    deleteSelectedSchedule,
    handleScheduleSelect,
    manualRunSchedule,
    rebuildDueScheduleRuns,
    executeScheduleRunNow,
    resetScheduleRunNow,
    saveImChannel,
    deleteSelectedImChannel,
    sendReportNow,
    sendPositionSummaryNow,
    sendImTestNow,
    savePositionEntry,
    deleteSelectedPositionEntry,
    savePromptTemplate,
    deleteSelectedPrompt,
    generateReportFromRun,
    curateMemoryNow,
    bootstrap,
    initialize
  }
}

let quantWorkbenchInstance: ReturnType<typeof proxyRefs<ReturnType<typeof createQuantWorkbench>>> | null = null

export function useQuantWorkbench() {
  if (!quantWorkbenchInstance) {
    quantWorkbenchInstance = proxyRefs(createQuantWorkbench()) as ReturnType<typeof proxyRefs<ReturnType<typeof createQuantWorkbench>>>
  }
  return quantWorkbenchInstance
}
