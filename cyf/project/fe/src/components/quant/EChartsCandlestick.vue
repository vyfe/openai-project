<template>
  <div ref="chartRef" class="quant-echart" :style="{ height: height }" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  CandlestickChart,
  BarChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer
])

interface Bar {
  trade_date?: string
  trade_datetime?: string
  open_price: number | null
  close_price: number | null
  high_price: number | null
  low_price: number | null
  volume: number | null
  amount?: number | null
}

export interface MaPoint {
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
}
export interface BollPoint {
  mid: number | null
  upper: number | null
  lower: number | null
}
export interface MacdPoint {
  dif: number | null
  dea: number | null
  bar: number | null
}
export interface KdjPoint {
  k: number | null
  d: number | null
  j: number | null
}
export interface TdMark {
  date: string
  num: number
  side: 'buy' | 'sell'
  kind?: 'setup' | 'countdown'
}
export interface BottomSignal {
  date: string
  type: 'divergence'
}
export interface TopSignal {
  date: string
  type: 'divergence'
}

const props = withDefaults(
  defineProps<{
    bars: Bar[]
    symbol?: string
    isDark?: boolean
    height?: string
    frequency?: '1d' | '5m'
    /** 主图只显示一组：均线或 BOLL */
    mainIndicator?: 'ma' | 'boll'
    /** 附图只显示一组：MACD 或 KDJ */
    subIndicator?: 'macd' | 'kdj'
    /**
     * 仅画最后 N 根 K 线/成交量；indicator 序列按当前 bars 全量计算后切片到对应 X 轴区间
     */
    displayLimit?: number
    /** MA 系列（与 bars 等长） */
    maSeries?: MaPoint[]
    /** BOLL 三轨（与 bars 等长） */
    bollSeries?: BollPoint[]
    /** MACD 三元（与 bars 等长） */
    macdSeries?: MacdPoint[]
    /** KDJ 三元（与 bars 等长） */
    kdjSeries?: KdjPoint[]
    /** 神奇九转数字标记（仅含 buy/sell setup > 0 的 bar） */
    tdMarks?: TdMark[]
    /** 底部结构信号（含底背离等） */
    bottomSignals?: BottomSignal[]
    /** 顶部结构信号（含顶背离等） */
    topSignals?: TopSignal[]
  }>(),
  { symbol: '', isDark: false, height: '540px', frequency: '1d', mainIndicator: 'ma', subIndicator: 'macd', displayLimit: Infinity,
    maSeries: () => [], bollSeries: () => [], macdSeries: () => [],
    kdjSeries: () => [], tdMarks: () => [], bottomSignals: () => [], topSignals: () => [] }
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const sortedBars = computed(() => {
  // ECharts 要求按时间正序；日线/分时接口与周线聚合接口的返回方向不同，统一排序。
  return [...(props.bars || [])].sort((a, b) => {
    const aKey = a.trade_datetime || a.trade_date || ''
    const bKey = b.trade_datetime || b.trade_date || ''
    return String(aKey).localeCompare(String(bKey))
  })
})

// 显示区间：最后 displayLimit 根
const displayBars = computed(() => {
  const list = sortedBars.value
  const limit = props.displayLimit
  if (!limit || limit >= list.length) return list
  return list.slice(-limit)
})

const dates = computed(() => displayBars.value.map(b => b.trade_datetime || b.trade_date || ''))

// 按 bar 时间键对齐指标序列，兼容日线/分时倒序和周线升序两种返回方向。
function _barKey(bar: any): string {
  const raw = bar?.trade_datetime || bar?.trade_date || ''
  return typeof raw === 'string' ? raw : String(raw)
}

function _alignSeries<T>(series: T[] | undefined): T[] {
  if (!series || series.length === 0) return []
  const source = props.bars || []
  const byKey = new Map<string, T>()
  source.forEach((bar, index) => byKey.set(_barKey(bar), series[index]))
  return displayBars.value.map(bar => byKey.get(_barKey(bar)) || ({} as T))
}

const maAligned = computed(() => _alignSeries(props.maSeries))
const bollAligned = computed(() => _alignSeries(props.bollSeries))
const macdAligned = computed(() => _alignSeries(props.macdSeries))
const kdjAligned = computed(() => _alignSeries(props.kdjSeries))

const candleData = computed(() =>
  displayBars.value.map(b => [b.open_price, b.close_price, b.low_price, b.high_price])
)

const volumeData = computed(() =>
  displayBars.value.map((b) => {
    const open = b.open_price ?? 0
    const close = b.close_price ?? 0
    const isUp = close >= open
    return {
      value: b.volume ?? 0,
      itemStyle: { color: isUp ? '#ef232a' : '#14b143' }
    }
  })
)

const ma5Series = computed(() => maAligned.value.map(p => p.ma5))
const ma10Series = computed(() => maAligned.value.map(p => p.ma10))
const ma20Series = computed(() => maAligned.value.map(p => p.ma20))
const ma60Series = computed(() => maAligned.value.map(p => p.ma60))

const bollMidSeries = computed(() => bollAligned.value.map(p => p.mid))
const bollUpperSeries = computed(() => bollAligned.value.map(p => p.upper))
const bollLowerSeries = computed(() => bollAligned.value.map(p => p.lower))

const macdDifSeries = computed(() => macdAligned.value.map(p => p.dif))
const macdDeaSeries = computed(() => macdAligned.value.map(p => p.dea))
const macdBarSeries = computed(() => macdAligned.value.map(p => ({
  value: p.bar,
  itemStyle: { color: (p.bar ?? 0) >= 0 ? '#ef232a' : '#14b143' }
})))

const kdjKSeries = computed(() => kdjAligned.value.map(p => p.k))
const kdjDSeries = computed(() => kdjAligned.value.map(p => p.d))
const kdjJSeries = computed(() => kdjAligned.value.map(p => p.j))

// TD 数字标记：把 tdMarks 转换为 markPoint data
const tdMarkPointData = computed(() => {
  if (!props.tdMarks || props.tdMarks.length === 0) return []
  // 找 sortedBars 中 date 对应的 idx（X 轴用 sortedBars 索引）
  const dateToIdx = new Map<string, number>()
  sortedBars.value.forEach((b, i) => dateToIdx.set(_barKey(b), i))
  const out: any[] = []
  // TD 标记的 X 轴需要从 sortedBars 索引转换成 displayBars 索引
  // displayBars 是 sortedBars 的尾部切片，所以 sortedIdx - offset = displayIdx
  const offset = sortedBars.value.length - displayBars.value.length
  for (const m of props.tdMarks) {
    const sortedIdx = dateToIdx.get(m.date)
    if (sortedIdx === undefined) continue
    const displayIdx = sortedIdx - offset
    if (displayIdx < 0 || displayIdx >= displayBars.value.length) continue
    const bar = displayBars.value[displayIdx]
    if (bar?.high_price == null && bar?.low_price == null) continue
    const isBuy = m.side === 'buy'
    const isCountdown = m.kind === 'countdown'
    const price = isBuy ? (bar.low_price ?? bar.high_price ?? 0) : (bar.high_price ?? bar.low_price ?? 0)
    const coord = [displayIdx, price * (isBuy ? (isCountdown ? 0.91 : 0.96) : (isCountdown ? 1.09 : 1.04))]
    out.push({
      name: String(m.num),
      coord,
      value: m.num,
      symbol: isCountdown ? 'diamond' : 'circle',
      symbolSize: isCountdown ? 22 : 18,
      itemStyle: {
        color: isBuy ? '#ef232a' : '#14b143',
        borderColor: isCountdown ? '#ffffff' : undefined,
        borderWidth: isCountdown ? 1 : 0,
      },
      label: {
        show: true,
        formatter: '{b}',
        color: '#fff',
        fontSize: 10,
        fontWeight: 'bold',
        position: 'inside',
      }
    })
  }
  return out
})

// 底部结构 scatter 数据
const bottomScatterData = computed(() => {
  if (!props.bottomSignals || props.bottomSignals.length === 0) return []
  const dateToIdx = new Map<string, number>()
  sortedBars.value.forEach((b, i) => dateToIdx.set(_barKey(b), i))
  const offset = sortedBars.value.length - displayBars.value.length
  const out: any[] = []
  for (const s of props.bottomSignals) {
    const sortedIdx = dateToIdx.get(s.date)
    if (sortedIdx === undefined) continue
    const displayIdx = sortedIdx - offset
    if (displayIdx < 0 || displayIdx >= displayBars.value.length) continue
    const bar = displayBars.value[displayIdx]
    if (!bar?.low_price) continue
    out.push({
      name: s.date,
      value: [displayIdx, bar.low_price * 0.97],
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#f59e0b' },
    })
  }
  return out
})

// 顶部结构 scatter 数据（绿色向下三角，叠加在主图高点上方）
const topScatterData = computed(() => {
  if (!props.topSignals || props.topSignals.length === 0) return []
  const dateToIdx = new Map<string, number>()
  sortedBars.value.forEach((b, i) => dateToIdx.set(_barKey(b), i))
  const offset = sortedBars.value.length - displayBars.value.length
  const out: any[] = []
  for (const s of props.topSignals) {
    const sortedIdx = dateToIdx.get(s.date)
    if (sortedIdx === undefined) continue
    const displayIdx = sortedIdx - offset
    if (displayIdx < 0 || displayIdx >= displayBars.value.length) continue
    const bar = displayBars.value[displayIdx]
    if (!bar?.high_price) continue
    out.push({
      name: s.date,
      value: [displayIdx, bar.high_price * 1.03],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: '#14b143' },
    })
  }
  return out
})

const baseOption = computed(() => {
  const axis = props.isDark ? '#cbd5e1' : '#1f2937'
  const split = props.isDark ? '#334155' : '#e5e7eb'
  const tooltipBg = props.isDark ? '#0f172a' : '#ffffff'
  const tooltipText = props.isDark ? '#e2e8f0' : '#0f172a'

  const grids = [
    { left: 50, right: 20, top: 44, height: '50%' },        // K线
    { left: 50, right: 20, top: '65%', height: '12%' },     // 成交量
    { left: 50, right: 20, top: '80%', height: '14%' },     // 当前附图
  ]
  const xAxes = [
    { type: 'category', gridIndex: 0, data: dates.value, boundaryGap: true,
      axisLine: { lineStyle: { color: split } },
      axisLabel: { color: axis, formatter: (v: string) => props.frequency === '5m' ? (v.split('T')[1] || v).slice(0, 5) : (v.split('T')[0]) },
      splitLine: { show: false }, axisPointer: { z: 100 } },
    { type: 'category', gridIndex: 1, data: dates.value, boundaryGap: true,
      axisLine: { lineStyle: { color: split } }, axisLabel: { show: false },
      axisTick: { show: false }, splitLine: { show: false } },
    { type: 'category', gridIndex: 2, data: dates.value, boundaryGap: true,
      axisLine: { lineStyle: { color: split } }, axisLabel: { show: false },
      axisTick: { show: false }, splitLine: { show: false } },
  ]
  const yAxes = [
    { scale: true, gridIndex: 0, position: 'left',
      axisLine: { lineStyle: { color: split } }, axisLabel: { color: axis },
      splitLine: { lineStyle: { color: split, opacity: 0.4 } } },
    { scale: true, gridIndex: 1, position: 'left',
      axisLine: { lineStyle: { color: split } }, axisLabel: { color: axis, fontSize: 10 },
      splitNumber: 2, splitLine: { show: false } },
    { scale: true, gridIndex: 2, position: 'left',
      axisLine: { lineStyle: { color: split } }, axisLabel: { color: axis, fontSize: 10 },
      splitNumber: 2, splitLine: { show: false } },
  ]
  const dataZoom = [
    { type: 'inside', xAxisIndex: [0, 1, 2], start: props.frequency === '5m' ? 70 : 0, end: 100 },
    { type: 'slider', xAxisIndex: [0, 1, 2], start: props.frequency === '5m' ? 70 : 0, end: 100,
      bottom: 6, height: 22, borderColor: split,
      fillerColor: props.isDark ? 'rgba(99,102,241,0.25)' : 'rgba(99,102,241,0.18)',
      handleStyle: { color: '#6366f1' }, textStyle: { color: axis, fontSize: 10 } },
  ]

  const series: any[] = [
    {
      name: 'K线', type: 'candlestick', data: candleData.value,
      xAxisIndex: 0, yAxisIndex: 0,
      itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' },
      markPoint: tdMarkPointData.value.length > 0 ? {
        symbol: 'pin', symbolSize: 22, data: tdMarkPointData.value,
        animation: false,
      } : undefined,
    },
  ]
  // 主图：均线与 BOLL 互斥，避免同一价格面板叠加过多轨道。
  if (props.mainIndicator === 'boll' && bollMidSeries.value.length > 0) {
    series.push({ name: 'BOLL中', type: 'line', data: bollMidSeries.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b', type: 'dashed' } })
    series.push({ name: 'BOLL上', type: 'line', data: bollUpperSeries.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#94a3b8' } })
    series.push({ name: 'BOLL下', type: 'line', data: bollLowerSeries.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#94a3b8' } })
  }
  if (props.mainIndicator === 'ma' && ma5Series.value.length > 0) {
    series.push({ name: 'MA5', type: 'line', data: ma5Series.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' } })
    series.push({ name: 'MA10', type: 'line', data: ma10Series.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#3b82f6' } })
    series.push({ name: 'MA20', type: 'line', data: ma20Series.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#a855f7' } })
    series.push({ name: 'MA60', type: 'line', data: ma60Series.value, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#6b7280' } })
  }
  // 成交量
  series.push({ name: '成交量', type: 'bar', data: volumeData.value, xAxisIndex: 1, yAxisIndex: 1 })
  // 附图：MACD 与 KDJ 互斥，共用一个附图区域。
  if (props.subIndicator === 'macd' && macdDifSeries.value.length > 0) {
    series.push({ name: 'MACD柱', type: 'bar', data: macdBarSeries.value, xAxisIndex: 2, yAxisIndex: 2 })
    series.push({ name: 'DIF', type: 'line', data: macdDifSeries.value, xAxisIndex: 2, yAxisIndex: 2,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' } })
    series.push({ name: 'DEA', type: 'line', data: macdDeaSeries.value, xAxisIndex: 2, yAxisIndex: 2,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#3b82f6' } })
  }
  if (props.subIndicator === 'kdj' && kdjKSeries.value.length > 0) {
    series.push({ name: 'K', type: 'line', data: kdjKSeries.value, xAxisIndex: 2, yAxisIndex: 2,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' } })
    series.push({ name: 'D', type: 'line', data: kdjDSeries.value, xAxisIndex: 2, yAxisIndex: 2,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#e2e8f0' } })
    series.push({ name: 'J', type: 'line', data: kdjJSeries.value, xAxisIndex: 2, yAxisIndex: 2,
      smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#a855f7' } })
  }
  // 底部结构 scatter（叠加在主图）
  if (bottomScatterData.value.length > 0) {
    series.push({
      name: '底部背离', type: 'scatter', data: bottomScatterData.value,
      xAxisIndex: 0, yAxisIndex: 0,
      symbol: 'triangle', symbolSize: 12,
      itemStyle: { color: '#f59e0b' },
    })
  }
  // 顶部结构 scatter（叠加在主图）
  if (topScatterData.value.length > 0) {
    series.push({
      name: '顶部背离', type: 'scatter', data: topScatterData.value,
      xAxisIndex: 0, yAxisIndex: 0,
      symbol: 'triangle', symbolRotate: 180, symbolSize: 12,
      itemStyle: { color: '#14b143' },
    })
  }

  return {
    backgroundColor: 'transparent',
    legend: {
      top: 8, left: 'center', textStyle: { color: axis, fontSize: 12 },
      data: series.map((s: any) => s.name).filter(Boolean),
    },
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross' },
      backgroundColor: tooltipBg, borderColor: split,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: (params: any[]) => {
        const candle = params.find(p => p.seriesType === 'candlestick')
        const lines: string[] = []
        lines.push(`<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`)
        if (candle) {
          // ECharts candlestick 默认维度顺序 OCLH（Open, Close, Lowest, Highest）；
          // candleData 传入 [open_price, close_price, low_price, high_price] 与之对齐。
          // axisPointer(trigger:'axis'+cross) 触发时 candle.data 可能是 4 元 OCLH，
          // 也可能被 ECharts 前置 axisValue 变成 5 元 [axisValue, ...OCLH]，
          // 还可能被包装成 {value: [...]}。三种形态都要兼容。
          const raw = candle.data
          const arr = Array.isArray(raw)
            ? raw
            : (raw && Array.isArray(raw.value) ? raw.value : null)
          if (arr && arr.length >= 4) {
            // 5 元场景：第 0 位是 axisValue（x 轴类别/序号），丢弃；OCLH 永远在后 4 位
            const ohlc = arr.length >= 5 ? arr.slice(-4) : arr
            const fmt = (v: any) => typeof v === 'number' ? v.toFixed(2) : v
            const [openPrice, closePrice, lowestPrice, highestPrice] = ohlc
            lines.push(
              `开 <b>${fmt(openPrice)}</b>  收 <b>${fmt(closePrice)}</b>`
              + `  高 <b>${fmt(highestPrice)}</b>  低 <b>${fmt(lowestPrice)}</b>`
            )
          }
        }
        const vol = params.find(p => p.seriesName === '成交量')
        if (vol) {
          const v = (vol.data.value ?? vol.data)
          lines.push(`成交量 <b>${(Number(v) / 100).toLocaleString('zh-CN')} 手</b>`)
        }
        for (const p of params) {
          const name = p.seriesName || ''
          if (p.data != null && (name.startsWith('MA') || name.startsWith('BOLL'))) {
            lines.push(`${name} <b>${typeof p.data === 'number' ? p.data.toFixed(2) : p.data}</b>`)
          } else if (p.data != null && (name === 'DIF' || name === 'DEA')) {
            lines.push(`MACD ${name} <b>${typeof p.data === 'number' ? p.data.toFixed(3) : p.data}</b>`)
          } else if (p.data != null && (name === 'K' || name === 'D' || name === 'J')) {
            lines.push(`KDJ ${name} <b>${typeof p.data === 'number' ? p.data.toFixed(2) : p.data}</b>`)
          } else if (name === '底部背离') {
            lines.push(`<span style="color:#f59e0b">▲ 底部背离</span>`)
          } else if (name === '顶部背离') {
            lines.push(`<span style="color:#14b143">▼ 顶部背离</span>`)
          } else if (p.seriesType === 'candlestick' && p.data && typeof p.data.name === 'string' && /^\d+$/.test(p.data.name)) {
            // TD markPoint 的 name 是数字串（1-9 setup / 13 countdown），输出可读 tooltip。
            const n = Number(p.data.name)
            const tag = n === 13 ? '九转 · 计数完成' : '九转 · 计数中'
            lines.push(`<span style="color:#0f172a">【${tag}】${n}</span>`)
          }
        }
        return lines.join('<br/>')
      },
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom,
    series,
  }
})

function buildChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  chart.setOption(baseOption.value, { notMerge: true })
}

function updateChart() {
  if (!chart) return
  chart.setOption(baseOption.value, { notMerge: true })
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  buildChart()
  if (chartRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartRef.value)
  } else {
    window.addEventListener('resize', handleResize)
  }
})

watch(() => [
  props.bars,
  props.maSeries,
  props.bollSeries,
  props.macdSeries,
  props.kdjSeries,
  props.tdMarks,
  props.bottomSignals,
  props.topSignals,
  props.mainIndicator,
  props.subIndicator,
  props.isDark,
], () => updateChart(), { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.quant-echart {
  width: 100%;
  min-height: 360px;
}
</style>
