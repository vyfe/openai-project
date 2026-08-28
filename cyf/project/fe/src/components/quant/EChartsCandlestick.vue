<template>
  <div ref="chartRef" class="quant-echart" :style="{ height: height }" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, BarChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  CandlestickChart,
  BarChart,
  LineChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
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

const props = withDefaults(
  defineProps<{
    bars: Bar[]
    symbol?: string
    isDark?: boolean
    height?: string
    frequency?: '1d' | '5m'
    /**
     * 仅画最后 N 根 K 线/成交量。MA 仍按 bars 全量计算（让前几根 K 线的 MA
     * 也能算出来），再按 N 切片到对应 X 轴区间。
     * 留空表示全部显示。
     */
    displayLimit?: number
  }>(),
  { symbol: '', isDark: false, height: '460px', frequency: '1d', displayLimit: Infinity }
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const sortedBars = computed(() => {
  // ECharts 要求按时间正序；后端按 trade_date 倒序返回，这里反转
  return [...(props.bars || [])].sort((a, b) => {
    const aKey = a.trade_datetime || a.trade_date || ''
    const bKey = b.trade_datetime || b.trade_date || ''
    return aKey < bKey ? -1 : 1
  })
})

// 只渲染最后 displayLimit 根 K 线/成交量；更早的 bars 只用来贡献 MA。
const displayBars = computed(() => {
  const list = sortedBars.value
  const limit = props.displayLimit
  if (!limit || limit >= list.length) return list
  return list.slice(-limit)
})

const dates = computed(() => displayBars.value.map(b => b.trade_datetime || b.trade_date || ''))

// ECharts candlestick: [open, close, low, high]
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

function maValues(period: number): (number | null)[] {
  const result: (number | null)[] = []
  // 用全部 sortedBars（含 padding）算 MA，让前几根 K 线的 MA 也能产出值；
  // 结果按 displayBars 的尾部区间切片，保证与 X 轴等长。
  const closes = sortedBars.value.map(b => b.close_price ?? null)
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      result.push(null)
      continue
    }
    let sum = 0
    let count = 0
    for (let j = i - period + 1; j <= i; j++) {
      if (closes[j] != null) {
        sum += closes[j] as number
        count += 1
      }
    }
    result.push(count === period ? +(sum / period).toFixed(3) : null)
  }
  return result
}

function trimToDisplay(allValues: (number | null)[]): (number | null)[] {
  const total = allValues.length
  const visible = displayBars.value.length
  if (visible >= total) return allValues
  return allValues.slice(total - visible)
}

const ma5 = computed(() => trimToDisplay(maValues(5)))
const ma10 = computed(() => trimToDisplay(maValues(10)))
const ma20 = computed(() => trimToDisplay(maValues(20)))

const baseOption = computed(() => {
  const axis = props.isDark ? '#cbd5e1' : '#1f2937'
  const split = props.isDark ? '#334155' : '#e5e7eb'
  const tooltipBg = props.isDark ? '#0f172a' : '#ffffff'
  const tooltipText = props.isDark ? '#e2e8f0' : '#0f172a'

  return {
    backgroundColor: 'transparent',
    legend: {
      top: 8,
      left: 'center',
      textStyle: { color: axis, fontSize: 12 },
      data: ['K线', 'MA5', 'MA10', 'MA20', '成交量']
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: tooltipBg,
      borderColor: split,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: (params: any[]) => {
        const candle = params.find(p => p.seriesType === 'candlestick')
        const lines: string[] = []
        lines.push(`<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`)
        if (candle) {
          const d = candle.data
          lines.push(`开 <b>${d[0]}</b>  收 <b>${d[1]}</b>`)
          lines.push(`低 <b>${d[2]}</b>  高 <b>${d[3]}</b>`)
        }
        const vol = params.find(p => p.seriesName === '成交量')
        if (vol) {
          const v = (vol.data.value ?? vol.data)
          lines.push(`成交量 <b>${(Number(v) / 100).toLocaleString('zh-CN')} 手</b>`)
        }
        for (const p of params) {
          if (p.seriesName && p.seriesName.startsWith('MA') && p.data != null) {
            lines.push(`${p.seriesName} <b>${p.data}</b>`)
          }
        }
        return lines.join('<br/>')
      }
    },
    grid: [
      { left: 50, right: 20, top: 50, height: '60%' },
      { left: 50, right: 20, top: '74%', height: '18%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates.value,
        boundaryGap: true,
        axisLine: { lineStyle: { color: split } },
        axisLabel: {
          color: axis,
          formatter: (value: string) => {
            // 5m 用 HH:mm；1d 用 yyyy-MM-dd（截掉 T 之后部分）
            if (props.frequency === '5m') {
              const tail = value.split('T')[1] || value
              return tail.slice(0, 5)
            }
            return value.split('T')[0]
          }
        },
        splitLine: { show: false },
        axisPointer: { z: 100 }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates.value,
        boundaryGap: true,
        axisLine: { lineStyle: { color: split } },
        axisLabel: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        position: 'left',
        axisLine: { lineStyle: { color: split } },
        axisLabel: { color: axis },
        splitLine: { lineStyle: { color: split, opacity: 0.4 } }
      },
      {
        scale: true,
        gridIndex: 1,
        position: 'left',
        axisLine: { lineStyle: { color: split } },
        axisLabel: { color: axis, fontSize: 10 },
        splitNumber: 2,
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: props.frequency === '5m' ? 70 : 0, end: 100 },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        start: props.frequency === '5m' ? 70 : 0,
        end: 100,
        bottom: 6,
        height: 22,
        borderColor: split,
        fillerColor: props.isDark ? 'rgba(99,102,241,0.25)' : 'rgba(99,102,241,0.18)',
        handleStyle: { color: '#6366f1' },
        textStyle: { color: axis, fontSize: 10 }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candleData.value,
        itemStyle: {
          color: '#ef232a',
          color0: '#14b143',
          borderColor: '#ef232a',
          borderColor0: '#14b143'
        }
      },
      { name: 'MA5', type: 'line', data: ma5.value, smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'MA10', type: 'line', data: ma10.value, smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#3b82f6' } },
      { name: 'MA20', type: 'line', data: ma20.value, smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#a855f7' } },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData.value
      }
    ]
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

watch(() => [props.bars, props.isDark], () => updateChart(), { deep: true })

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
  min-height: 320px;
}
</style>
