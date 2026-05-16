import { computed, proxyRefs, reactive, ref } from 'vue'
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
  payload?: Record<string, any>
  result?: Record<string, any>
  next_retry_at?: string
  started_at?: string
  finished_at?: string
}

export type PromptTemplateRecord = {
  id: number
  strategy_id?: number | null
  template_name: string
  prompt_version: string
  status: string
  report_type: string
  prompt_template: string
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

function createQuantWorkbench() {
  const providers = ref<string[]>([])
  const symbolOptions = ref<Array<{ symbol: string; code: string; exchange: string; name?: string }>>([])
  const importBatches = ref<any[]>([])
  const clientTasks = ref<any[]>([])
  const dailyBars = ref<any[]>([])
  const strategies = ref<StrategyRecord[]>([])
  const strategyRuns = ref<StrategyRunRecord[]>([])
  const strategySignals = ref<any[]>([])
  const operationRecords = ref<OperationRecord[]>([])
  const backtestRuns = ref<BacktestRunRecord[]>([])
  const scheduleConfigs = ref<ScheduleConfigRecord[]>([])
  const scheduleRuns = ref<ScheduleRunRecord[]>([])
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
    limit: 120
  })

  const taskForm = reactive({
    symbols: [] as string[],
    startDate: '',
    endDate: '',
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
    dataLookbackTradeDays: 20,
    dataLeaseSeconds: 600,
    dataNote: '',
    analysisStrategyIds: [] as number[],
    analysisChannelIds: [] as number[],
    analysisSaveAllSignals: true,
    memorySymbols: [] as string[],
    memoryLookbackDays: 120,
    memoryLimit: 50
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

  const strategyStatusTag = (status: string) => (status === 'active' ? 'success' : 'info')

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

  function formatRate(value: any) {
    if (value === null || value === undefined || value === '') return '--'
    const num = Number(value)
    if (!Number.isFinite(num)) return '--'
    return `${(num * 100).toFixed(2)}%`
  }

  function formatNumber(value: any, digits = 2) {
    if (value === null || value === undefined || value === '') return '--'
    const num = Number(value)
    if (!Number.isFinite(num)) return '--'
    return num.toFixed(digits)
  }

  const resolveStrategyName = (strategyId?: number | null) => {
    if (!strategyId) return '未绑定策略'
    return strategies.value.find(item => item.id === strategyId)?.name || `策略 #${strategyId}`
  }

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
      dataLeaseSeconds: 600,
      dataNote: '',
      analysisStrategyIds: selectedStrategyId.value ? [selectedStrategyId.value] : [],
      analysisChannelIds: [],
      analysisSaveAllSignals: true,
      memorySymbols: [],
      memoryLookbackDays: 120,
      memoryLimit: 50
    })
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
    scheduleForm.dataLookbackTradeDays = payload.lookback_trade_days || 20
    scheduleForm.dataLeaseSeconds = payload.lease_seconds || 600
    scheduleForm.dataNote = payload.note || ''
    scheduleForm.analysisStrategyIds = payload.strategy_ids || []
    scheduleForm.analysisChannelIds = payload.channel_ids || []
    scheduleForm.analysisSaveAllSignals = payload.save_all_signals !== false
    scheduleForm.memorySymbols = payload.symbols || []
    scheduleForm.memoryLookbackDays = payload.lookback_days || 120
    scheduleForm.memoryLimit = payload.limit || 50
  }

  const buildSchedulePayload = () => {
    if (scheduleForm.taskType === 'data_sync') {
      return {
        symbols: scheduleForm.dataSymbols,
        provider: scheduleForm.dataProvider,
        adjust_flag: scheduleForm.dataAdjustFlag,
        lookback_trade_days: scheduleForm.dataLookbackTradeDays,
        lease_seconds: scheduleForm.dataLeaseSeconds,
        note: scheduleForm.dataNote
      }
    }
    if (scheduleForm.taskType === 'memory_digest') {
      return {
        symbols: scheduleForm.memorySymbols,
        lookback_days: scheduleForm.memoryLookbackDays,
        limit: scheduleForm.memoryLimit
      }
    }
    return {
      strategy_ids: scheduleForm.analysisStrategyIds,
      channel_ids: scheduleForm.analysisChannelIds,
      save_all_signals: scheduleForm.analysisSaveAllSignals
    }
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
    const response: any = await quantDataAPI.symbols({ limit: 1200 })
    symbolOptions.value = response.data || []
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

  const loadDailyBars = async () => {
    if (!dailyQuery.symbol.trim()) {
      ElMessage.warning('先输入或选择一个股票代码')
      return
    }
    loading.dailyBars = true
    try {
      const response: any = await quantDataAPI.dailyBars({
        symbol: dailyQuery.symbol.trim(),
        start_date: dailyQuery.startDate || undefined,
        end_date: dailyQuery.endDate || undefined,
        limit: dailyQuery.limit
      })
      dailyBars.value = response.data || []
      if (!dailyBars.value.length) ElMessage.info('当前条件下没有查询到日线数据')
    } catch (error: any) {
      ElMessage.error(error?.message || '查询日线失败')
    } finally {
      loading.dailyBars = false
    }
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
    loading.savingSchedule = true
    try {
      const payload = {
        id: scheduleForm.id || undefined,
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
        payload: buildSchedulePayload()
      }
      if (scheduleForm.id) {
        await quantScheduleAPI.updateConfig(payload)
        ElMessage.success('调度配置已更新')
      } else {
        await quantScheduleAPI.createConfig(payload)
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
    } catch (error: any) {
      ElMessage.error(error?.message || '执行调度记录失败')
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
    })
    return bootstrapPromise
  }

  return {
    providers,
    symbolOptions,
    importBatches,
    clientTasks,
    dailyBars,
    strategies,
    strategyRuns,
    strategySignals,
    operationRecords,
    backtestRuns,
    scheduleConfigs,
    scheduleRuns,
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
    taskForm,
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
    loadImportBatches,
    loadTasks,
    loadDailyBars,
    loadStrategies,
    loadRuns,
    loadSignals,
    loadOperations,
    loadBacktests,
    loadBacktestDetail,
    loadScheduleConfigs,
    loadScheduleRuns,
    createTask,
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

let quantWorkbenchInstance: ReturnType<typeof createQuantWorkbench> | null = null

export function useQuantWorkbench() {
  if (!quantWorkbenchInstance) {
    quantWorkbenchInstance = proxyRefs(createQuantWorkbench()) as ReturnType<typeof createQuantWorkbench>
  }
  return quantWorkbenchInstance
}
