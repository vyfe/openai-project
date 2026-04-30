<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Calendar,
  Coin,
  DataBoard,
  DocumentChecked,
  EditPen,
  Histogram,
  MagicStick,
  Promotion,
  RefreshRight,
  Search,
  Setting,
  TrendCharts,
  VideoPlay,
  WarningFilled
} from '@element-plus/icons-vue'
import { useThemeManager } from '@/composables/useThemeManager'
import { useAuthStore } from '@/stores/auth'
import {
  quantBacktestAPI,
  quantDataAPI,
  quantOperationAPI,
  quantScheduleAPI,
  quantStrategyAPI,
  quantTaskAPI
} from '@/services/quantApi'

type StrategyRecord = {
  id: number
  name: string
  status: string
  description: string
  symbols: string[]
  rule_config: Record<string, any>
  updated_at?: string
}

type StrategyRunRecord = {
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

type OperationRecord = {
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

type BacktestRunRecord = {
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

type ScheduleConfigRecord = {
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

type ScheduleRunRecord = {
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

const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager } = useThemeManager()

const activeTab = ref('overview')
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
const selectedBacktestDetail = ref<BacktestRunRecord | null>(null)
const schedulerMeta = ref<any>(null)
const dashboardOverview = ref<any>(null)

const selectedStrategyId = ref<number | null>(null)
const selectedRunId = ref<number | null>(null)
const selectedOperationId = ref<number | null>(null)
const selectedBacktestId = ref<number | null>(null)
const selectedScheduleId = ref<number | null>(null)
const selectedScheduleRunId = ref<number | null>(null)

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
  manualScheduleRun: false
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
    {
      type: 'field_compare',
      field: 'pct_change',
      operator: '>=',
      value: 2,
      weight: 1,
      label: '涨跌幅至少 2%'
    },
    {
      type: 'close_above_ma',
      window: 5,
      weight: 1,
      label: '收盘站上 5 日线'
    },
    {
      type: 'volume_ratio',
      window: 5,
      operator: '>=',
      value: 1.2,
      weight: 1,
      label: '量比至少 1.2'
    }
  ]
}

const breakoutRuleConfig = {
  logic: 'all',
  signal_type: 'watch',
  min_score: 3,
  rules: [
    {
      type: 'breakout_high',
      window: 20,
      weight: 1,
      label: '突破前 20 日高点'
    },
    {
      type: 'field_compare',
      field: 'turnover_rate',
      operator: '>=',
      value: 1,
      weight: 1,
      label: '换手率至少 1%'
    },
    {
      type: 'volume_ratio',
      window: 5,
      operator: '>=',
      value: 1.5,
      weight: 1,
      label: '量比至少 1.5'
    }
  ]
}

const strategyPresets = [
  {
    key: 'trend',
    title: '趋势放量',
    summary: '适合找短期走强的日线标的',
    config: defaultRuleConfig
  },
  {
    key: 'breakout',
    title: '突破观察',
    summary: '适合找放量突破前高的观察名单',
    config: breakoutRuleConfig
  }
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
  analysisSaveAllSignals: true
})

const selectedStrategy = computed(() => strategies.value.find(item => item.id === selectedStrategyId.value) || null)
const selectedRun = computed(() => strategyRuns.value.find(item => item.id === selectedRunId.value) || null)
const selectedOperation = computed(() => operationRecords.value.find(item => item.id === selectedOperationId.value) || null)
const selectedBacktest = computed(() => selectedBacktestDetail.value || backtestRuns.value.find(item => item.id === selectedBacktestId.value) || null)
const selectedSchedule = computed(() => scheduleConfigs.value.find(item => item.id === selectedScheduleId.value) || null)
const selectedScheduleRun = computed(() => scheduleRuns.value.find(item => item.id === selectedScheduleRunId.value) || null)

const dashboardCards = computed(() => {
  const snapshot = dashboardOverview.value?.snapshot || {}
  return [
    {
      title: '最近交易日',
      value: snapshot.latest_trade_date || '--',
      hint: providers.value.join(' / ') || '等待数据源就绪',
      icon: Calendar
    },
    {
      title: '活跃策略',
      value: snapshot.active_strategies ?? strategies.value.filter(item => item.status === 'active').length,
      hint: '策略与规则入口已经具备',
      icon: MagicStick
    },
    {
      title: '待处理任务',
      value: snapshot.pending_tasks ?? clientTasks.value.filter(item => ['pending', 'leased'].includes(item.status)).length,
      hint: '客户端只负责抓数与回传',
      icon: Promotion
    },
    {
      title: '操作登记',
      value: snapshot.today_operations ?? operationRecords.value.length,
      hint: snapshot.successful_backtests ? `已完成回测 ${snapshot.successful_backtests} 次` : '等待人工回填执行结果',
      icon: DocumentChecked
    }
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

const goBack = () => router.push('/chat')
const goAdmin = () => router.push('/admin')

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

const formatRate = (value: any) => {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  if (!Number.isFinite(num)) return '--'
  return `${(num * 100).toFixed(2)}%`
}

const formatNumber = (value: any, digits = 2) => {
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
  if (!scheduleForm.analysisStrategyIds.length) {
    scheduleForm.analysisStrategyIds = [strategy.id]
  }
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
  operationForm.id = null
  operationForm.strategyId = selectedStrategyId.value
  operationForm.runId = null
  operationForm.signalId = null
  operationForm.symbol = ''
  operationForm.action = 'buy'
  operationForm.status = 'draft'
  operationForm.resultStatus = ''
  operationForm.tradeDate = ''
  operationForm.price = null
  operationForm.quantity = null
  operationForm.amount = null
  operationForm.thesis = ''
  operationForm.executionNote = ''
  operationForm.reviewNote = ''
  operationForm.resultPct = null
  operationForm.resultAmount = null
  operationForm.tagsText = ''
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
  activeTab.value = 'operations'
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
  await Promise.all([loadRuns(), loadBacktests()])
}

const handleOperationSelect = (record: OperationRecord) => {
  hydrateOperationForm(record)
}

const handleBacktestSelect = async (record: BacktestRunRecord) => {
  await loadBacktestDetail(record.id)
}

const resetScheduleForm = () => {
  selectedScheduleId.value = null
  scheduleForm.id = null
  scheduleForm.name = ''
  scheduleForm.taskType = 'data_sync'
  scheduleForm.status = 'active'
  scheduleForm.cronExpr = '20 15 * * 1-5'
  scheduleForm.marketCalendar = 'A_SHARE'
  scheduleForm.timezone = 'Asia/Shanghai'
  scheduleForm.retryMax = 1
  scheduleForm.retryDelaySeconds = 180
  scheduleForm.allowManualRun = true
  scheduleForm.description = ''
  scheduleForm.dataSymbols = []
  scheduleForm.dataProvider = 'auto'
  scheduleForm.dataAdjustFlag = 'qfq'
  scheduleForm.dataLookbackTradeDays = 20
  scheduleForm.dataLeaseSeconds = 600
  scheduleForm.dataNote = ''
  scheduleForm.analysisStrategyIds = selectedStrategyId.value ? [selectedStrategyId.value] : []
  scheduleForm.analysisSaveAllSignals = true
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
  scheduleForm.analysisSaveAllSignals = payload.save_all_signals !== false
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
  return {
    strategy_ids: scheduleForm.analysisStrategyIds,
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
    if (!dailyBars.value.length) {
      ElMessage.info('当前条件下没有查询到日线数据')
    }
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
      if (matched) {
        hydrateStrategyForm(matched)
      } else {
        resetStrategyForm()
      }
    }
  } finally {
    loading.strategies = false
  }
}

const loadRuns = async () => {
  loading.runs = true
  try {
    const response: any = await quantStrategyAPI.runs({
      strategy_id: selectedStrategyId.value || undefined,
      limit: 40
    })
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
    const response: any = await quantStrategyAPI.signals({
      run_id: finalRunId,
      limit: 300
    })
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
    const response: any = await quantBacktestAPI.list({
      strategy_id: selectedStrategyId.value || undefined,
      limit: 40
    })
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
      if (matched) {
        hydrateScheduleForm(matched)
      }
    }
  } finally {
    loading.schedules = false
  }
}

const loadScheduleRuns = async () => {
  loading.scheduleRuns = true
  try {
    const response: any = await quantScheduleAPI.runs({
      schedule_id: selectedScheduleId.value || undefined,
      limit: 80
    })
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
      await quantStrategyAPI.update({
        id: strategyForm.id,
        ...payload
      })
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
  await ElMessageBox.confirm('删除策略会连同它的运行记录一起删除，继续吗？', '删除策略', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
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
    return
  }
  loading.runningStrategy = true
  try {
    const response: any = await quantStrategyAPI.run({
      strategy_id: strategyForm.id,
      trade_date: runForm.tradeDate || undefined,
      save_all_signals: runForm.saveAllSignals
    })
    ElMessage.success('策略执行完成')
    activeTab.value = 'runs'
    await Promise.all([loadRuns(), loadOverview()])
    const runRecord = response.data
    if (runRecord?.id) {
      await loadSignals(runRecord.id)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '执行策略失败')
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
      tags: operationForm.tagsText
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
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
  await ElMessageBox.confirm('删除后无法恢复，继续吗？', '删除操作记录', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
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
    return
  }
  if (!backtestForm.startDate || !backtestForm.endDate) {
    ElMessage.warning('回测需要明确开始和结束日期')
    return
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
    activeTab.value = 'backtest'
    await Promise.all([loadBacktests(), loadOverview()])
    if (response.data?.id) {
      await loadBacktestDetail(response.data.id)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '执行回测失败')
  } finally {
    loading.runningBacktest = false
  }
}

const deleteSelectedBacktest = async () => {
  if (!selectedBacktestId.value) {
    ElMessage.info('先选中一条回测记录')
    return
  }
  await ElMessageBox.confirm('删除后将丢失这次回测的净值曲线和交易样本，继续吗？', '删除回测记录', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
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
  if (!scheduleForm.name.trim()) {
    ElMessage.warning('调度名称不能为空')
    return
  }
  if (!scheduleForm.cronExpr.trim()) {
    ElMessage.warning('cron 表达式不能为空')
    return
  }
  if (scheduleForm.taskType === 'data_sync' && !scheduleForm.dataSymbols.length) {
    ElMessage.warning('拉数任务至少选择一个标的')
    return
  }
  if (scheduleForm.taskType === 'analysis_report' && !scheduleForm.analysisStrategyIds.length) {
    ElMessage.warning('测试报告至少选择一个策略')
    return
  }

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
  await ElMessageBox.confirm('删除后会一并删除该配置的执行记录，继续吗？', '删除调度配置', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
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
      loadScheduleRuns()
    ])
  } finally {
    loading.bootstrap = false
  }
}

onMounted(async () => {
  initThemeManager()
  resetOperationForm()
  resetScheduleForm()
  await bootstrap()
})
</script>

<template>
  <div class="quant-page min-h-screen" :class="{ dark: isDarkTheme, 'quant-dark': isDarkTheme }">
    <div class="quant-shell">
      <header class="quant-header">
        <div class="quant-header__left">
          <button class="quant-back-btn" @click="goBack" aria-label="返回聊天">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <div>
            <div class="quant-eyebrow">A Share Quant Console</div>
            <h1 class="quant-title">量化工作台</h1>
            <p class="quant-subtitle">把数据同步、策略执行、人工操作和回测评估放到一个轻量闭环里。</p>
          </div>
        </div>
        <div class="quant-header__right">
          <el-button class="quant-header-btn" text @click="goAdmin">
            <el-icon><Setting /></el-icon>
            管理台
          </el-button>
          <div class="quant-user-pill">
            <el-icon><DataBoard /></el-icon>
            <span>{{ authStore.user }}</span>
          </div>
        </div>
      </header>

      <section class="quant-summary-grid">
        <article v-for="card in dashboardCards" :key="card.title" class="quant-summary-card">
          <div class="quant-summary-card__icon">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="quant-summary-card__body">
            <div class="quant-summary-card__title">{{ card.title }}</div>
            <div class="quant-summary-card__value">{{ card.value }}</div>
            <div class="quant-summary-card__hint">{{ card.hint }}</div>
          </div>
        </article>
      </section>

      <el-alert
        class="quant-banner"
        type="info"
        :closable="false"
        show-icon
        title="当前阶段：策略执行由主服务定时/手动触发，客户端任务只负责抓数与回传。"
      />

      <main class="quant-main-panel" v-loading="loading.bootstrap">
        <el-tabs v-model="activeTab" class="quant-tabs">
          <el-tab-pane name="overview" label="总览">
            <div class="quant-grid quant-grid--overview">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>风险提示</h2>
                    <p>先盯住最容易把闭环拖垮的地方：数据失败、未回填操作、回测回撤。</p>
                  </div>
                  <el-button text :icon="RefreshRight" @click="loadOverview" :loading="loading.overview">刷新</el-button>
                </div>
                <div class="quant-risk-list">
                  <div v-for="tip in dashboardOverview?.risk_tips || []" :key="tip" class="quant-risk-item">
                    <el-icon><WarningFilled /></el-icon>
                    <span>{{ tip }}</span>
                  </div>
                </div>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>今日任务</h2>
                    <p>客户端抓数和最近导入批次，先确认底层数据链路没有断。</p>
                  </div>
                </div>
                <div class="quant-mini-list">
                  <div v-for="task in dashboardOverview?.today_tasks || clientTasks" :key="task.task_id" class="quant-mini-item">
                    <div class="quant-mini-item__head">
                      <span class="quant-mini-item__title">{{ task.payload?.symbols?.slice(0, 2)?.join(', ') || task.task_id }}</span>
                      <el-tag size="small" :type="taskStatusTag(task.status)">{{ task.status }}</el-tag>
                    </div>
                    <div class="quant-mini-item__meta">{{ task.payload?.start_date }} 至 {{ task.payload?.end_date }}</div>
                    <div class="quant-mini-item__actions">
                      <span>{{ task.message || '等待执行' }}</span>
                    </div>
                  </div>
                </div>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>最新信号</h2>
                    <p>优先看最新通过信号，再决定是否补充到人工操作登记里。</p>
                  </div>
                </div>
                <div class="quant-mini-list">
                  <div v-for="signal in dashboardOverview?.latest_signals || []" :key="`${signal.run_id}-${signal.symbol}`" class="quant-mini-item">
                    <div class="quant-mini-item__head">
                      <span class="quant-mini-item__title">{{ signal.symbol }}</span>
                      <el-tag size="small" type="success">{{ signal.signal_type || 'watch' }}</el-tag>
                    </div>
                    <div class="quant-mini-item__meta">{{ signal.trade_date }} · 得分 {{ formatNumber(signal.score, 1) }}</div>
                    <div class="quant-mini-item__actions">
                      <span>{{ signal.reasons?.[0] || '规则通过' }}</span>
                      <el-button text @click="prefillOperationFromSignal(signal)">登记</el-button>
                    </div>
                  </div>
                </div>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>最近操作</h2>
                    <p>人工执行不是旁路数据，后续复盘、自学习都要依赖这里。</p>
                  </div>
                </div>
                <div class="quant-mini-list">
                  <div v-for="record in dashboardOverview?.recent_operations || operationRecords.slice(0, 6)" :key="record.id" class="quant-mini-item">
                    <div class="quant-mini-item__head">
                      <span class="quant-mini-item__title">{{ record.symbol }}</span>
                      <el-tag size="small" :type="operationStatusTag(record.status)">{{ record.status }}</el-tag>
                    </div>
                    <div class="quant-mini-item__meta">{{ resolveStrategyName(record.strategy_id) }} · {{ record.trade_date }}</div>
                    <div class="quant-mini-item__actions">
                      <span>{{ record.action }} / {{ record.result_status || '待复盘' }}</span>
                      <el-button text @click="handleOperationSelect(record); activeTab = 'operations'">查看</el-button>
                    </div>
                  </div>
                </div>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>最近回测</h2>
                    <p>用轻量事件回测先判断规则有没有基本解释力，再谈调参。</p>
                  </div>
                </div>
                <div class="quant-mini-list">
                  <div v-for="record in dashboardOverview?.recent_backtests || backtestRuns.slice(0, 6)" :key="record.id" class="quant-mini-item">
                    <div class="quant-mini-item__head">
                      <span class="quant-mini-item__title">{{ record.strategy_name }}</span>
                      <el-tag size="small" :type="backtestStatusTag(record.status)">{{ record.status }}</el-tag>
                    </div>
                    <div class="quant-mini-item__meta">{{ record.start_date }} ~ {{ record.end_date }}</div>
                    <div class="quant-mini-item__actions">
                      <span>收益 {{ formatRate(record.metrics?.total_return) }}</span>
                      <el-button text @click="handleBacktestSelect(record); activeTab = 'backtest'">查看</el-button>
                    </div>
                  </div>
                </div>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>最近运行</h2>
                    <p>策略执行结果仍然是主轴，人工操作和回测都应该围着它沉淀。</p>
                  </div>
                </div>
                <div class="quant-mini-list">
                  <div v-for="run in dashboardOverview?.recent_runs || strategyRuns.slice(0, 6)" :key="run.id" class="quant-mini-item">
                    <div class="quant-mini-item__head">
                      <span class="quant-mini-item__title">{{ run.summary?.strategy_name || `策略 #${run.strategy_id}` }}</span>
                      <el-tag size="small" :type="taskStatusTag(run.status)">{{ run.status }}</el-tag>
                    </div>
                    <div class="quant-mini-item__meta">{{ run.trade_date }} · 通过 {{ run.signals_total }}/{{ run.symbols_total }}</div>
                    <div class="quant-mini-item__actions">
                      <span>{{ run.created_at }}</span>
                      <el-button text @click="activeTab = 'runs'; loadSignals(run.id)">查看</el-button>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane name="data" label="数据中心">
            <div class="quant-grid quant-grid--data">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>查日线数据</h2>
                    <p>先看数据质量，再决定策略口径和观察标的。</p>
                  </div>
                  <el-button :icon="Search" type="primary" @click="loadDailyBars" :loading="loading.dailyBars">
                    查询
                  </el-button>
                </div>

                <div class="quant-form-grid">
                  <el-form label-position="top">
                    <el-form-item label="股票代码">
                      <el-select v-model="dailyQuery.symbol" filterable clearable placeholder="例如 600519.SH">
                        <el-option
                          v-for="item in symbolOptions"
                          :key="item.symbol"
                          :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                          :value="item.symbol"
                        />
                      </el-select>
                    </el-form-item>
                  </el-form>
                  <el-form label-position="top">
                    <el-form-item label="开始日期">
                      <el-date-picker v-model="dailyQuery.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
                    </el-form-item>
                  </el-form>
                  <el-form label-position="top">
                    <el-form-item label="结束日期">
                      <el-date-picker v-model="dailyQuery.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
                    </el-form-item>
                  </el-form>
                  <el-form label-position="top">
                    <el-form-item label="返回条数">
                      <el-input-number v-model="dailyQuery.limit" :min="20" :max="5000" :step="20" />
                    </el-form-item>
                  </el-form>
                </div>

                <el-table :data="dailyBars" stripe height="460" class="quant-table">
                  <el-table-column prop="trade_date" label="交易日" width="108" />
                  <el-table-column prop="close_price" label="收盘" min-width="88" />
                  <el-table-column prop="pct_change" label="涨跌幅%" min-width="96" />
                  <el-table-column prop="turnover_rate" label="换手率%" min-width="96" />
                  <el-table-column prop="volume" label="成交量(股)" min-width="126" />
                  <el-table-column prop="amount" label="成交额" min-width="128" />
                  <el-table-column prop="source" label="来源" width="100" />
                </el-table>
              </section>

              <div class="quant-side-stack">
                <section class="quant-panel">
                  <div class="quant-panel__header">
                    <div>
                      <h2>数据同步任务</h2>
                      <p>给独立客户端派发抓数任务，策略调度和它分开。</p>
                    </div>
                    <el-button type="primary" :icon="Promotion" @click="createTask" :loading="loading.createTask">
                      创建任务
                    </el-button>
                  </div>

                  <div class="quant-form-stack">
                    <el-form label-position="top">
                      <el-form-item label="股票池">
                        <el-select
                          v-model="taskForm.symbols"
                          multiple
                          filterable
                          collapse-tags
                          collapse-tags-tooltip
                          placeholder="选择一个或多个标的"
                        >
                          <el-option v-for="item in symbolOptions" :key="item.symbol" :label="item.symbol" :value="item.symbol" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <div class="quant-form-grid quant-form-grid--two">
                      <el-form label-position="top">
                        <el-form-item label="开始日期">
                          <el-date-picker v-model="taskForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="结束日期">
                          <el-date-picker v-model="taskForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
                        </el-form-item>
                      </el-form>
                    </div>
                    <div class="quant-form-grid quant-form-grid--two">
                      <el-form label-position="top">
                        <el-form-item label="数据源">
                          <el-select v-model="taskForm.provider">
                            <el-option v-for="provider in providers" :key="provider" :label="provider" :value="provider" />
                          </el-select>
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="复权">
                          <el-select v-model="taskForm.adjustFlag">
                            <el-option label="前复权" value="qfq" />
                            <el-option label="后复权" value="hfq" />
                            <el-option label="不复权" value="raw" />
                          </el-select>
                        </el-form-item>
                      </el-form>
                    </div>
                    <el-form label-position="top">
                      <el-form-item label="备注">
                        <el-input v-model="taskForm.note" placeholder="例如：补 2024-2025 年回测样本" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-mini-section">
                    <div class="quant-mini-section__title">
                      <span>最近任务</span>
                      <el-button text :icon="RefreshRight" @click="loadTasks" :loading="loading.tasks">刷新</el-button>
                    </div>
                    <div class="quant-mini-list">
                      <div v-for="task in clientTasks" :key="task.task_id" class="quant-mini-item">
                        <div class="quant-mini-item__head">
                          <span class="quant-mini-item__title">{{ task.payload?.symbols?.slice(0, 2)?.join(', ') || task.task_id }}</span>
                          <el-tag size="small" :type="taskStatusTag(task.status)">{{ task.status }}</el-tag>
                        </div>
                        <div class="quant-mini-item__meta">{{ task.payload?.start_date }} 至 {{ task.payload?.end_date }}</div>
                        <div class="quant-mini-item__actions">
                          <span>{{ task.message || '等待客户端处理' }}</span>
                          <el-button v-if="task.status === 'failed'" text @click="resetTask(task.task_id)">重置</el-button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="quant-mini-section">
                    <div class="quant-mini-section__title">
                      <span>最近导入批次</span>
                      <el-button text :icon="RefreshRight" @click="loadImportBatches" :loading="loading.importBatches">刷新</el-button>
                    </div>
                    <div class="quant-mini-list">
                      <div v-for="batch in importBatches" :key="batch.batch_id" class="quant-mini-item">
                        <div class="quant-mini-item__head">
                          <span class="quant-mini-item__title">{{ batch.source }}</span>
                          <el-tag size="small" :type="taskStatusTag(batch.status)">{{ batch.status }}</el-tag>
                        </div>
                        <div class="quant-mini-item__meta">{{ batch.records_imported }}/{{ batch.records_total }} 条</div>
                        <div class="quant-mini-item__actions">
                          <span>{{ batch.finished_at || batch.created_at }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane name="strategy" label="策略中心">
            <div class="quant-grid quant-grid--strategy">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>策略清单</h2>
                    <p>先把规则固化下来，执行和调度才能稳定复用。</p>
                  </div>
                  <el-button plain @click="resetStrategyForm">新建策略</el-button>
                </div>
                <el-table
                  :data="strategies"
                  stripe
                  height="680"
                  class="quant-table"
                  @row-click="handleStrategySelect"
                  :row-class-name="({ row }) => row.id === selectedStrategyId ? 'quant-row--active' : ''"
                >
                  <el-table-column prop="name" label="策略名" min-width="180" />
                  <el-table-column prop="status" label="状态" width="110">
                    <template #default="{ row }">
                      <el-tag size="small" :type="strategyStatusTag(row.status)">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="股票池" min-width="150">
                    <template #default="{ row }">
                      {{ row.symbols?.length || 0 }} 个
                    </template>
                  </el-table-column>
                  <el-table-column prop="updated_at" label="更新时间" min-width="180" />
                </el-table>
              </section>

              <section class="quant-panel quant-panel--editor">
                <div class="quant-panel__header">
                  <div>
                    <h2>{{ strategyForm.id ? '编辑策略' : '新建策略' }}</h2>
                    <p>{{ selectedStrategy ? `当前策略：${selectedStrategy.name}` : '这版先围绕日线规则，方便快速验证信号质量。' }}</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadStrategies" :loading="loading.strategies">刷新</el-button>
                    <el-button type="primary" :icon="VideoPlay" @click="executeSelectedStrategy" :loading="loading.runningStrategy">
                      执行策略
                    </el-button>
                  </div>
                </div>

                <div class="quant-form-stack">
                  <div class="quant-form-grid quant-form-grid--two">
                    <el-form label-position="top">
                      <el-form-item label="策略名称">
                        <el-input v-model="strategyForm.name" placeholder="例如：放量突破观察" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="状态">
                        <el-select v-model="strategyForm.status">
                          <el-option label="active" value="active" />
                          <el-option label="inactive" value="inactive" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="策略描述">
                      <el-input v-model="strategyForm.description" type="textarea" :rows="2" placeholder="写清楚这条策略要观察什么。" />
                    </el-form-item>
                  </el-form>

                  <el-form label-position="top">
                    <el-form-item label="股票池">
                      <el-select
                        v-model="strategyForm.symbols"
                        multiple
                        filterable
                        collapse-tags
                        collapse-tags-tooltip
                        placeholder="为空时默认扫描当前交易日已有数据的全部标的"
                      >
                        <el-option v-for="item in symbolOptions" :key="item.symbol" :label="item.symbol" :value="item.symbol" />
                      </el-select>
                    </el-form-item>
                  </el-form>

                  <div class="quant-preset-strip">
                    <button
                      v-for="preset in strategyPresets"
                      :key="preset.key"
                      class="quant-preset-chip"
                      @click="applyStrategyPreset(preset.config)"
                    >
                      <strong>{{ preset.title }}</strong>
                      <span>{{ preset.summary }}</span>
                    </button>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="规则 JSON">
                      <el-input
                        v-model="strategyForm.ruleConfigText"
                        type="textarea"
                        :rows="18"
                        placeholder="在这里编辑规则 JSON"
                        class="quant-code-input"
                      />
                    </el-form-item>
                  </el-form>

                  <div class="quant-run-inline">
                    <el-form label-position="top" class="quant-run-inline__date">
                      <el-form-item label="执行日期">
                        <el-date-picker v-model="runForm.tradeDate" type="date" value-format="YYYY-MM-DD" placeholder="为空则用最新交易日" />
                      </el-form-item>
                    </el-form>
                    <el-checkbox v-model="runForm.saveAllSignals">保存全部信号（包括未通过）</el-checkbox>
                  </div>
                </div>

                <div class="quant-actions">
                  <el-button type="primary" :icon="Setting" @click="saveStrategy" :loading="loading.savingStrategy">
                    {{ strategyForm.id ? '保存更新' : '创建策略' }}
                  </el-button>
                  <el-button plain @click="resetStrategyForm">重置表单</el-button>
                  <el-button v-if="strategyForm.id" type="danger" plain @click="deleteSelectedStrategy">删除策略</el-button>
                </div>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane name="operations" label="操作登记">
            <div class="quant-grid quant-grid--operations">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>操作清单</h2>
                    <p>这里登记人工是否采纳、怎么执行、后续结果如何，后面复盘和自学习都要用它。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button plain @click="resetOperationForm">新建登记</el-button>
                    <el-button :icon="RefreshRight" @click="loadOperations" :loading="loading.operations">刷新</el-button>
                  </div>
                </div>

                <el-table
                  :data="operationRecords"
                  stripe
                  height="700"
                  class="quant-table"
                  @row-click="handleOperationSelect"
                  :row-class-name="({ row }) => row.id === selectedOperationId ? 'quant-row--active' : ''"
                >
                  <el-table-column prop="trade_date" label="交易日" width="110" />
                  <el-table-column prop="symbol" label="标的" min-width="120" />
                  <el-table-column prop="action" label="动作" width="92" />
                  <el-table-column label="状态" width="96">
                    <template #default="{ row }">
                      <el-tag size="small" :type="operationStatusTag(row.status)">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="结果" width="96">
                    <template #default="{ row }">
                      <el-tag size="small" :type="operationResultTag(row.result_status || '')">{{ row.result_status || '--' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="关联策略" min-width="150">
                    <template #default="{ row }">
                      {{ resolveStrategyName(row.strategy_id) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="updated_at" label="更新时间" min-width="180" />
                </el-table>
              </section>

              <section class="quant-panel quant-panel--editor">
                <div class="quant-panel__header">
                  <div>
                    <h2>{{ operationForm.id ? '编辑操作记录' : '新建操作记录' }}</h2>
                    <p>{{ operationForm.signalId ? `已关联信号 #${operationForm.signalId}` : '可以手动录，也可以从执行记录里的信号直接带入。' }}</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadOperations" :loading="loading.operations">刷新</el-button>
                  </div>
                </div>

                <div class="quant-form-stack">
                  <div class="quant-form-grid quant-form-grid--two">
                    <el-form label-position="top">
                      <el-form-item label="关联策略">
                        <el-select v-model="operationForm.strategyId" clearable placeholder="可选">
                          <el-option v-for="item in strategies" :key="item.id" :label="item.name" :value="item.id" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="交易日">
                        <el-date-picker v-model="operationForm.tradeDate" type="date" value-format="YYYY-MM-DD" placeholder="执行日期" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-form-grid quant-form-grid--three">
                    <el-form label-position="top">
                      <el-form-item label="标的">
                        <el-select v-model="operationForm.symbol" filterable clearable placeholder="例如 600519.SH">
                          <el-option
                            v-for="item in symbolOptions"
                            :key="item.symbol"
                            :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                            :value="item.symbol"
                          />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="动作">
                        <el-select v-model="operationForm.action">
                          <el-option label="buy" value="buy" />
                          <el-option label="add" value="add" />
                          <el-option label="reduce" value="reduce" />
                          <el-option label="sell" value="sell" />
                          <el-option label="watch" value="watch" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="执行状态">
                        <el-select v-model="operationForm.status">
                          <el-option label="draft" value="draft" />
                          <el-option label="executed" value="executed" />
                          <el-option label="closed" value="closed" />
                          <el-option label="cancelled" value="cancelled" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-form-grid quant-form-grid--three">
                    <el-form label-position="top">
                      <el-form-item label="成交价">
                        <el-input-number v-model="operationForm.price" :min="0" :precision="3" :step="0.1" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="数量">
                        <el-input-number v-model="operationForm.quantity" :min="0" :step="100" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="金额">
                        <el-input-number v-model="operationForm.amount" :min="0" :precision="2" :step="1000" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="执行理由">
                      <el-input v-model="operationForm.thesis" type="textarea" :rows="4" placeholder="写清楚为什么做这笔操作，最好和策略信号一一对应。" />
                    </el-form-item>
                  </el-form>

                  <el-form label-position="top">
                    <el-form-item label="执行备注">
                      <el-input v-model="operationForm.executionNote" type="textarea" :rows="3" placeholder="例如：分两笔成交、盘中追价、实际仓位控制。" />
                    </el-form-item>
                  </el-form>

                  <div class="quant-form-grid quant-form-grid--three">
                    <el-form label-position="top">
                      <el-form-item label="结果状态">
                        <el-select v-model="operationForm.resultStatus" clearable placeholder="可选">
                          <el-option label="pending" value="pending" />
                          <el-option label="win" value="win" />
                          <el-option label="loss" value="loss" />
                          <el-option label="flat" value="flat" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="结果收益率">
                        <el-input-number v-model="operationForm.resultPct" :precision="4" :step="0.01" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="结果金额">
                        <el-input-number v-model="operationForm.resultAmount" :precision="2" :step="100" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="复盘备注">
                      <el-input v-model="operationForm.reviewNote" type="textarea" :rows="3" placeholder="写结果、偏差和下次如何改。" />
                    </el-form-item>
                  </el-form>

                  <el-form label-position="top">
                    <el-form-item label="标签">
                      <el-input v-model="operationForm.tagsText" placeholder="逗号分隔，例如：突破, 观察仓, 复盘重点" />
                    </el-form-item>
                  </el-form>
                </div>

                <div class="quant-actions">
                  <el-button type="primary" :icon="EditPen" @click="saveOperation" :loading="loading.savingOperation">
                    {{ operationForm.id ? '保存更新' : '录入操作' }}
                  </el-button>
                  <el-button plain @click="resetOperationForm">重置表单</el-button>
                  <el-button v-if="operationForm.id" type="danger" plain @click="deleteSelectedOperation">删除记录</el-button>
                </div>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane name="backtest" label="回测评估">
            <div class="quant-grid quant-grid--backtest">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>回测记录</h2>
                    <p>先把同一策略不同时间窗的结果并排留下来，后面才谈版本对比和参数建议。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadBacktests" :loading="loading.backtests">刷新</el-button>
                  </div>
                </div>
                <el-table
                  :data="backtestRuns"
                  stripe
                  height="700"
                  class="quant-table"
                  @row-click="handleBacktestSelect"
                  :row-class-name="({ row }) => row.id === selectedBacktestId ? 'quant-row--active' : ''"
                >
                  <el-table-column prop="strategy_name" label="策略" min-width="160" />
                  <el-table-column label="状态" width="96">
                    <template #default="{ row }">
                      <el-tag size="small" :type="backtestStatusTag(row.status)">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="区间" min-width="200">
                    <template #default="{ row }">
                      {{ row.start_date }} ~ {{ row.end_date }}
                    </template>
                  </el-table-column>
                  <el-table-column label="收益" width="100">
                    <template #default="{ row }">
                      {{ formatRate(row.metrics?.total_return) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="回撤" width="100">
                    <template #default="{ row }">
                      {{ formatRate(row.metrics?.max_drawdown) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="created_at" label="创建时间" min-width="180" />
                </el-table>
              </section>

              <section class="quant-panel quant-panel--editor">
                <div class="quant-panel__header">
                  <div>
                    <h2>轻量回测</h2>
                    <p>这版先做事件回测，目标是尽快验证规则有没有基础解释力，而不是做撮合级仿真。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button type="primary" :icon="TrendCharts" @click="runBacktest" :loading="loading.runningBacktest">
                      执行回测
                    </el-button>
                    <el-button v-if="selectedBacktestId" type="danger" plain @click="deleteSelectedBacktest">删除记录</el-button>
                  </div>
                </div>

                <div class="quant-form-stack">
                  <div class="quant-form-grid quant-form-grid--two">
                    <el-form label-position="top">
                      <el-form-item label="策略">
                        <el-select v-model="backtestForm.strategyId" placeholder="选择策略">
                          <el-option v-for="item in strategies" :key="item.id" :label="item.name" :value="item.id" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="基准标的">
                        <el-select v-model="backtestForm.benchmarkSymbol" filterable clearable placeholder="可选，例如 510300.SH">
                          <el-option
                            v-for="item in symbolOptions"
                            :key="item.symbol"
                            :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                            :value="item.symbol"
                          />
                        </el-select>
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-form-grid quant-form-grid--four">
                    <el-form label-position="top">
                      <el-form-item label="开始日期">
                        <el-date-picker v-model="backtestForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="结束日期">
                        <el-date-picker v-model="backtestForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="每日入选数">
                        <el-input-number v-model="backtestForm.topN" :min="1" :max="20" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="持有天数">
                        <el-input-number v-model="backtestForm.holdDays" :min="1" :max="60" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-form-grid quant-form-grid--three">
                    <el-form label-position="top">
                      <el-form-item label="初始资金">
                        <el-input-number v-model="backtestForm.initialCapital" :min="1000" :step="10000" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="手续费率">
                        <el-input-number v-model="backtestForm.commissionRate" :min="0" :precision="4" :step="0.0001" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="滑点率">
                        <el-input-number v-model="backtestForm.slippageRate" :min="0" :precision="4" :step="0.0001" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="回测股票池（为空则使用策略自带股票池）">
                      <el-select
                        v-model="backtestForm.symbols"
                        multiple
                        filterable
                        collapse-tags
                        collapse-tags-tooltip
                        placeholder="建议保持明确股票池，避免无边界扫描"
                      >
                        <el-option
                          v-for="item in symbolOptions"
                          :key="item.symbol"
                          :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                          :value="item.symbol"
                        />
                      </el-select>
                    </el-form-item>
                  </el-form>
                </div>

                <div v-if="selectedBacktest" class="quant-backtest-detail" v-loading="loading.backtestDetail">
                  <div class="quant-mini-section__title">
                    <span>结果概览</span>
                    <span class="quant-muted">{{ selectedBacktest.strategy_name }} · {{ selectedBacktest.start_date }} ~ {{ selectedBacktest.end_date }}</span>
                  </div>

                  <div class="quant-metric-grid">
                    <div v-for="card in backtestMetricCards" :key="card.title" class="quant-metric-card">
                      <span>{{ card.title }}</span>
                      <strong>{{ card.value }}</strong>
                    </div>
                  </div>

                  <div class="quant-sparkline-card">
                    <div class="quant-sparkline-card__header">
                      <div>
                        <h3>净值曲线</h3>
                        <p>当前为轻量聚合净值，适合做版本比较，不适合作为逐日持仓还原。</p>
                      </div>
                      <div class="quant-sparkline-stats">
                        <span>交易数 {{ selectedBacktest.trades_total }}</span>
                        <span>信号数 {{ selectedBacktest.signals_total }}</span>
                      </div>
                    </div>
                    <div class="quant-sparkline">
                      <svg viewBox="0 0 760 220" preserveAspectRatio="none">
                        <path v-if="backtestCurvePath" :d="backtestCurvePath" class="quant-sparkline__line" />
                      </svg>
                    </div>
                  </div>

                  <div class="quant-mini-section">
                    <div class="quant-mini-section__title">
                      <span>方法说明</span>
                    </div>
                    <div class="quant-pill-list">
                      <span v-for="tip in selectedBacktest.summary?.limitations || []" :key="tip" class="quant-pill">{{ tip }}</span>
                    </div>
                  </div>

                  <div class="quant-mini-section">
                    <div class="quant-mini-section__title">
                      <span>样本交易</span>
                    </div>
                    <el-table :data="backtestTradePreview" stripe height="280" class="quant-table">
                      <el-table-column prop="symbol" label="标的" min-width="110" />
                      <el-table-column prop="signal_date" label="信号日" width="108" />
                      <el-table-column prop="entry_date" label="入场日" width="108" />
                      <el-table-column prop="exit_date" label="离场日" width="108" />
                      <el-table-column label="净收益" width="100">
                        <template #default="{ row }">
                          {{ formatRate(row.net_return) }}
                        </template>
                      </el-table-column>
                      <el-table-column prop="score" label="得分" width="88" />
                    </el-table>
                  </div>
                </div>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane name="scheduler" label="调度执行">
            <div class="quant-grid quant-grid--scheduler">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>调度总览</h2>
                    <p>这版只管两个时间轴：定时拉日线数据、定时做分析报告。都按交易日过滤。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadSchedulerMeta" :loading="loading.schedulerMeta">刷新概览</el-button>
                    <el-button plain @click="rebuildDueScheduleRuns">补扫应执行</el-button>
                  </div>
                </div>

                <div class="quant-metric-grid">
                  <div v-for="card in schedulerCards" :key="card.title" class="quant-metric-card">
                    <span>{{ card.title }}</span>
                    <strong>{{ card.value }}</strong>
                  </div>
                </div>

                <div class="quant-mini-section">
                  <div class="quant-mini-section__title">
                    <span>配置清单</span>
                    <div class="quant-toolbar">
                      <el-button plain @click="resetScheduleForm">新建配置</el-button>
                      <el-button :icon="RefreshRight" @click="loadScheduleConfigs" :loading="loading.schedules">刷新</el-button>
                    </div>
                  </div>
                  <el-table
                    :data="scheduleConfigs"
                    stripe
                    height="420"
                    class="quant-table"
                    @row-click="handleScheduleSelect"
                    :row-class-name="({ row }) => row.id === selectedScheduleId ? 'quant-row--active' : ''"
                  >
                    <el-table-column prop="name" label="名称" min-width="150" />
                    <el-table-column prop="task_type" label="类型" width="130" />
                    <el-table-column prop="cron_expr" label="Cron" min-width="140" />
                    <el-table-column label="状态" width="90">
                      <template #default="{ row }">
                        <el-tag size="small" :type="strategyStatusTag(row.status)">{{ row.status }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="110">
                      <template #default="{ row }">
                        <el-button text @click.stop="manualRunSchedule(row.id)">手工触发</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </section>

              <section class="quant-panel quant-panel--editor">
                <div class="quant-panel__header">
                  <div>
                    <h2>{{ scheduleForm.id ? '编辑调度配置' : '新建调度配置' }}</h2>
                    <p>推荐 cron 例子：`20 15 * * 1-5`。工作日由交易日历再过滤一次，不靠 weekday 盲跑。</p>
                  </div>
                </div>

                <div class="quant-form-stack">
                  <div class="quant-form-grid quant-form-grid--two">
                    <el-form label-position="top">
                      <el-form-item label="名称">
                        <el-input v-model="scheduleForm.name" placeholder="例如：收盘后数据拉取" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="任务类型">
                        <el-select v-model="scheduleForm.taskType">
                          <el-option label="定时拉数" value="data_sync" />
                          <el-option label="测试报告" value="analysis_report" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                  </div>

                  <div class="quant-form-grid quant-form-grid--four">
                    <el-form label-position="top">
                      <el-form-item label="Cron">
                        <el-input v-model="scheduleForm.cronExpr" placeholder="20 15 * * 1-5" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="状态">
                        <el-select v-model="scheduleForm.status">
                          <el-option label="active" value="active" />
                          <el-option label="inactive" value="inactive" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="重试次数">
                        <el-input-number v-model="scheduleForm.retryMax" :min="0" :max="10" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="重试间隔(秒)">
                        <el-input-number v-model="scheduleForm.retryDelaySeconds" :min="30" :max="3600" :step="30" class="quant-full-width" />
                      </el-form-item>
                    </el-form>
                  </div>

                  <el-form label-position="top">
                    <el-form-item label="说明">
                      <el-input v-model="scheduleForm.description" type="textarea" :rows="2" placeholder="说明这个时点为什么跑，以及希望产出什么。" />
                    </el-form-item>
                  </el-form>

                  <el-form label-position="top">
                    <el-form-item label="允许手工重跑">
                      <el-checkbox v-model="scheduleForm.allowManualRun">允许手工创建一次执行记录</el-checkbox>
                    </el-form-item>
                  </el-form>

                  <template v-if="scheduleForm.taskType === 'data_sync'">
                    <div class="quant-form-grid quant-form-grid--two">
                      <el-form label-position="top">
                        <el-form-item label="标的池">
                          <el-select
                            v-model="scheduleForm.dataSymbols"
                            multiple
                            filterable
                            collapse-tags
                            collapse-tags-tooltip
                            placeholder="定时拉哪些股票"
                          >
                            <el-option
                              v-for="item in symbolOptions"
                              :key="item.symbol"
                              :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                              :value="item.symbol"
                            />
                          </el-select>
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="任务备注">
                          <el-input v-model="scheduleForm.dataNote" placeholder="例如：收盘后补齐最近 20 个交易日窗口" />
                        </el-form-item>
                      </el-form>
                    </div>

                    <div class="quant-form-grid quant-form-grid--four">
                      <el-form label-position="top">
                        <el-form-item label="数据源">
                          <el-select v-model="scheduleForm.dataProvider">
                            <el-option v-for="provider in providers" :key="provider" :label="provider" :value="provider" />
                          </el-select>
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="复权">
                          <el-select v-model="scheduleForm.dataAdjustFlag">
                            <el-option label="前复权" value="qfq" />
                            <el-option label="后复权" value="hfq" />
                            <el-option label="不复权" value="raw" />
                          </el-select>
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="回看交易日数">
                          <el-input-number v-model="scheduleForm.dataLookbackTradeDays" :min="1" :max="250" class="quant-full-width" />
                        </el-form-item>
                      </el-form>
                      <el-form label-position="top">
                        <el-form-item label="客户端租约(秒)">
                          <el-input-number v-model="scheduleForm.dataLeaseSeconds" :min="60" :max="7200" :step="60" class="quant-full-width" />
                        </el-form-item>
                      </el-form>
                    </div>
                  </template>

                  <template v-else>
                    <el-form label-position="top">
                      <el-form-item label="报告策略">
                        <el-select
                          v-model="scheduleForm.analysisStrategyIds"
                          multiple
                          filterable
                          collapse-tags
                          collapse-tags-tooltip
                          placeholder="报告时需要执行哪些策略"
                        >
                          <el-option v-for="item in strategies" :key="item.id" :label="item.name" :value="item.id" />
                        </el-select>
                      </el-form-item>
                    </el-form>
                    <el-form label-position="top">
                      <el-form-item label="附带未通过信号">
                        <el-checkbox v-model="scheduleForm.analysisSaveAllSignals">保存全部信号，方便复盘</el-checkbox>
                      </el-form-item>
                    </el-form>
                  </template>
                </div>

                <div class="quant-actions">
                  <el-button type="primary" :icon="Setting" @click="saveScheduleConfig" :loading="loading.savingSchedule">
                    {{ scheduleForm.id ? '保存更新' : '创建配置' }}
                  </el-button>
                  <el-button plain @click="resetScheduleForm">重置表单</el-button>
                  <el-button type="warning" plain @click="manualRunSchedule()" :loading="loading.manualScheduleRun">手工触发</el-button>
                  <el-button v-if="scheduleForm.id" type="danger" plain @click="deleteSelectedSchedule">删除配置</el-button>
                </div>
              </section>

              <section class="quant-panel quant-panel--full">
                <div class="quant-panel__header">
                  <div>
                    <h2>执行记录</h2>
                    <p>worker 会按 cron 生成执行记录并消费；这里主要用来观察、补偿和排错。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadScheduleRuns" :loading="loading.scheduleRuns">刷新记录</el-button>
                    <el-button plain @click="executeScheduleRunNow()">立即执行选中记录</el-button>
                  </div>
                </div>

                <el-table
                  :data="scheduleRuns"
                  stripe
                  height="360"
                  class="quant-table"
                  @row-click="selectedScheduleRunId = $event.id"
                  :row-class-name="({ row }) => row.id === selectedScheduleRunId ? 'quant-row--active' : ''"
                >
                  <el-table-column prop="scheduled_for" label="计划时间" min-width="176" />
                  <el-table-column prop="schedule_name" label="配置" min-width="150" />
                  <el-table-column prop="task_type" label="类型" width="130" />
                  <el-table-column prop="trigger_source" label="来源" width="100" />
                  <el-table-column label="状态" width="110">
                    <template #default="{ row }">
                      <el-tag size="small" :type="taskStatusTag(row.status)">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="attempts" label="次数" width="76" />
                  <el-table-column prop="message" label="说明" min-width="220" />
                  <el-table-column label="操作" width="96">
                    <template #default="{ row }">
                      <el-button
                        v-if="['pending', 'retry_wait', 'failed'].includes(row.status)"
                        text
                        @click.stop="executeScheduleRunNow(row.id)"
                      >
                        执行
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div v-if="selectedScheduleRun" class="quant-run-result">
                  <div class="quant-mini-section__title">
                    <span>结果详情</span>
                    <span class="quant-muted">{{ selectedScheduleRun.schedule_name }} · {{ selectedScheduleRun.status }}</span>
                  </div>
                  <el-input
                    :model-value="JSON.stringify(selectedScheduleRun.result || selectedScheduleRun.payload || {}, null, 2)"
                    type="textarea"
                    :rows="10"
                    readonly
                    class="quant-code-input"
                  />
                </div>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane name="runs" label="执行记录">
            <div class="quant-grid quant-grid--runs">
              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>运行记录</h2>
                    <p>先看这次扫了多少标的、出了多少信号，再往下看每只股票的判断原因。</p>
                  </div>
                  <div class="quant-toolbar">
                    <el-button :icon="RefreshRight" @click="loadRuns" :loading="loading.runs">刷新</el-button>
                  </div>
                </div>
                <el-table
                  :data="strategyRuns"
                  stripe
                  height="680"
                  class="quant-table"
                  @row-click="loadSignals($event.id)"
                  :row-class-name="({ row }) => row.id === selectedRunId ? 'quant-row--active' : ''"
                >
                  <el-table-column prop="trade_date" label="交易日" width="120" />
                  <el-table-column label="状态" width="100">
                    <template #default="{ row }">
                      <el-tag size="small" :type="taskStatusTag(row.status)">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="signals_total" label="通过数" width="90" />
                  <el-table-column prop="symbols_total" label="扫描数" width="90" />
                  <el-table-column prop="created_at" label="开始时间" min-width="180" />
                </el-table>
              </section>

              <section class="quant-panel">
                <div class="quant-panel__header">
                  <div>
                    <h2>信号明细</h2>
                    <p>{{ selectedRun ? `${selectedRun.trade_date} · ${selectedRun.summary?.strategy_name || '策略运行结果'}` : '先从左侧选择一次运行记录。' }}</p>
                  </div>
                </div>

                <div v-if="selectedRun" class="quant-run-summary">
                  <div class="quant-run-summary__metric">
                    <span>策略</span>
                    <strong>{{ selectedRun.summary?.strategy_name || selectedRun.strategy_id }}</strong>
                  </div>
                  <div class="quant-run-summary__metric">
                    <span>通过数</span>
                    <strong>{{ selectedRun.signals_total }}</strong>
                  </div>
                  <div class="quant-run-summary__metric">
                    <span>扫描数</span>
                    <strong>{{ selectedRun.symbols_total }}</strong>
                  </div>
                </div>

                <el-table :data="strategySignals" stripe height="620" class="quant-table">
                  <el-table-column prop="symbol" label="标的" min-width="120" />
                  <el-table-column label="结果" width="88">
                    <template #default="{ row }">
                      <el-tag size="small" :type="row.passed ? 'success' : 'info'">
                        {{ row.passed ? '通过' : '未过' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="score" label="得分" width="84" />
                  <el-table-column prop="signal_type" label="类型" width="96" />
                  <el-table-column label="规则说明" min-width="240">
                    <template #default="{ row }">
                      <div class="quant-reason-list">
                        <span v-for="reason in row.reasons" :key="reason" class="quant-reason-item">{{ reason }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="92">
                    <template #default="{ row }">
                      <el-button text @click="prefillOperationFromSignal(row)">登记</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </section>
            </div>
          </el-tab-pane>
        </el-tabs>
      </main>
    </div>
  </div>
</template>

<style scoped>
.quant-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--accent-1) 10%, transparent) 0, transparent 34%),
    radial-gradient(circle at top right, color-mix(in srgb, var(--accent-2) 12%, transparent) 0, transparent 28%),
    var(--bg-app-gradient);
  color: var(--text-1);
}

.quant-shell {
  max-width: 1520px;
  margin: 0 auto;
  padding: 28px 20px 48px;
}

.quant-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  padding: 20px 24px;
  border: 1px solid color-mix(in srgb, var(--line-1) 82%, transparent);
  border-radius: 24px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--bg-1) 86%, white) 0%, color-mix(in srgb, var(--bg-1) 92%, var(--accent-2-soft)) 100%);
  box-shadow: 0 18px 48px rgba(48, 45, 40, 0.08);
}

.quant-header__left,
.quant-header__right {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.quant-eyebrow {
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-2);
  margin-bottom: 6px;
}

.quant-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  color: var(--text-1);
}

.quant-subtitle {
  margin: 8px 0 0;
  color: var(--text-2);
}

.quant-back-btn {
  border: none;
  outline: none;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--bg-2) 88%, white);
  color: var(--text-1);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, background 0.2s ease;
}

.quant-back-btn:hover {
  transform: translateY(-1px);
  background: color-mix(in srgb, var(--accent-1-soft) 65%, var(--bg-2));
}

.quant-header-btn {
  color: var(--text-2);
}

.quant-user-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-2-soft) 70%, var(--bg-1));
  color: var(--text-1);
  font-size: 14px;
}

.quant-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.quant-summary-card {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 18px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--bg-1) 94%, white);
  border: 1px solid color-mix(in srgb, var(--line-1) 80%, transparent);
  box-shadow: 0 10px 28px rgba(48, 45, 40, 0.06);
}

.quant-summary-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent-1-soft) 0%, var(--accent-2-soft) 100%);
  color: var(--accent-1);
  font-size: 22px;
}

.quant-summary-card__title {
  font-size: 13px;
  color: var(--text-2);
}

.quant-summary-card__value {
  font-size: 30px;
  line-height: 1;
  font-weight: 700;
  margin: 6px 0;
}

.quant-summary-card__hint {
  font-size: 13px;
  color: var(--text-2);
}

.quant-banner {
  margin-top: 18px;
}

.quant-main-panel {
  margin-top: 18px;
  padding: 18px;
  border-radius: 24px;
  background: color-mix(in srgb, var(--bg-1) 92%, white);
  border: 1px solid color-mix(in srgb, var(--line-1) 82%, transparent);
  box-shadow: 0 16px 46px rgba(48, 45, 40, 0.06);
}

.quant-grid {
  display: grid;
  gap: 18px;
}

.quant-grid--overview {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.quant-grid--data {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.8fr);
}

.quant-grid--strategy,
.quant-grid--runs,
.quant-grid--operations,
.quant-grid--backtest,
.quant-grid--scheduler {
  grid-template-columns: minmax(320px, 0.82fr) minmax(0, 1.18fr);
}

.quant-side-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.quant-panel {
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--line-1) 76%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--bg-1) 96%, white) 0%, color-mix(in srgb, var(--bg-1) 88%, var(--bg-2)) 100%);
  padding: 18px;
}

.quant-panel--editor {
  min-height: 720px;
}

.quant-panel--full {
  grid-column: 1 / -1;
}

.quant-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.quant-panel__header h2,
.quant-sparkline-card__header h3 {
  margin: 0;
  font-size: 22px;
}

.quant-panel__header p,
.quant-sparkline-card__header p {
  margin: 6px 0 0;
  color: var(--text-2);
  font-size: 14px;
}

.quant-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.quant-form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 12px;
}

.quant-form-grid--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.quant-form-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.quant-form-grid--four {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.quant-form-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quant-full-width {
  width: 100%;
}

.quant-mini-section {
  margin-top: 16px;
}

.quant-mini-section__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}

.quant-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quant-mini-item {
  padding: 12px 14px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-2) 62%, white);
  border: 1px solid color-mix(in srgb, var(--line-1) 72%, transparent);
}

.quant-mini-item__head,
.quant-mini-item__actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.quant-mini-item__title {
  font-weight: 600;
}

.quant-mini-item__meta,
.quant-mini-item__actions,
.quant-muted {
  margin-top: 6px;
  color: var(--text-2);
  font-size: 13px;
}

.quant-risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quant-risk-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, color-mix(in srgb, #f59e0b 12%, var(--bg-1)) 0%, color-mix(in srgb, #ef4444 10%, var(--bg-1)) 100%);
  border: 1px solid color-mix(in srgb, #f59e0b 24%, var(--line-1));
  color: var(--text-1);
}

.quant-preset-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 2px 0 8px;
}

.quant-preset-chip {
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--line-1) 76%, transparent);
  border-radius: 18px;
  padding: 14px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--accent-1-soft) 48%, var(--bg-1)) 0%, color-mix(in srgb, var(--accent-2-soft) 60%, var(--bg-1)) 100%);
  color: var(--text-1);
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.quant-preset-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(48, 45, 40, 0.08);
}

.quant-preset-chip strong {
  display: block;
  margin-bottom: 6px;
}

.quant-preset-chip span {
  display: block;
  color: var(--text-2);
  font-size: 13px;
}

.quant-code-input :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.quant-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.quant-run-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.quant-run-inline__date {
  flex: 1;
}

.quant-run-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.quant-run-summary__metric,
.quant-metric-card {
  padding: 12px 14px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--accent-2-soft) 55%, var(--bg-1));
}

.quant-run-summary__metric span,
.quant-metric-card span {
  display: block;
  font-size: 12px;
  color: var(--text-2);
}

.quant-run-summary__metric strong,
.quant-metric-card strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
}

.quant-reason-list,
.quant-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quant-reason-item,
.quant-pill {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-2) 80%, white);
  color: var(--text-2);
  width: fit-content;
}

.quant-backtest-detail {
  margin-top: 18px;
}

.quant-run-result {
  margin-top: 16px;
}

.quant-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.quant-sparkline-card {
  padding: 14px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--bg-2) 55%, white);
  border: 1px solid color-mix(in srgb, var(--line-1) 72%, transparent);
}

.quant-sparkline-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.quant-sparkline-stats {
  display: inline-flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-2);
}

.quant-sparkline {
  width: 100%;
  height: 220px;
  border-radius: 18px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--accent-2-soft) 20%, transparent) 0%, transparent 100%),
    color-mix(in srgb, var(--bg-1) 96%, white);
  overflow: hidden;
}

.quant-sparkline svg {
  width: 100%;
  height: 100%;
}

.quant-sparkline__line {
  fill: none;
  stroke: var(--accent-1);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.quant-table :deep(.el-table__row.quant-row--active > td) {
  background: color-mix(in srgb, var(--accent-1-soft) 56%, transparent) !important;
}

.quant-tabs :deep(.el-tabs__item) {
  font-weight: 600;
}

@media (max-width: 1280px) {
  .quant-grid--overview,
  .quant-grid--data,
  .quant-grid--strategy,
  .quant-grid--runs,
  .quant-grid--operations,
  .quant-grid--backtest,
  .quant-grid--scheduler,
  .quant-summary-grid,
  .quant-form-grid,
  .quant-preset-strip,
  .quant-run-summary,
  .quant-metric-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .quant-run-inline,
  .quant-header,
  .quant-sparkline-card__header {
    flex-direction: column;
  }

  .quant-header__right {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 768px) {
  .quant-shell {
    padding: 16px 12px 28px;
  }

  .quant-title {
    font-size: 28px;
  }

  .quant-main-panel,
  .quant-panel,
  .quant-header {
    padding: 14px;
    border-radius: 18px;
  }

  .quant-panel__header {
    flex-direction: column;
  }
}
</style>
