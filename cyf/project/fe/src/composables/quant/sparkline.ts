/** 净值曲线 SVG path / axes 工具函数。

从 useQuantWorkbench.ts 抽出来的纯函数：
- buildSparklinePath(points, xFor, yFor) — 一组点 → SVG path d 字符串
- buildSparklineAxes(strategy, benchmark) — 两组点 → 网格 / 坐标 / baseline SVG fragment

所有函数无副作用，依赖 0，可单测。
*/

export interface SparklinePoint {
  date: string
  net_value: number | string
  capital?: number
}

export interface AxesOptions {
  /** SVG 画布尺寸 */
  width?: number
  height?: number
  /** 上下 padding 留给 axis label */
  padLeft?: number
  padRight?: number
  padTop?: number
  padBottom?: number
  /** 5 等分 Y 网格 */
  yGridCount?: number
  /** 5 等分 X 网格（按时间戳比例取最近实际点） */
  xGridCount?: number
}

const DEFAULT_AXES: Required<AxesOptions> = {
  width: 760,
  height: 220,
  padLeft: 44,
  padRight: 16,
  padTop: 12,
  padBottom: 28,
  yGridCount: 5,
  xGridCount: 5,
}

/** 根据时间戳比例 / 实际点 选 xTickIndices：等分比例找最近的点索引 */
function pickXTickIndices(tsList: number[], tsSpan: number, minTs: number, xGridCount: number): number[] {
  const indices: number[] = []
  for (let i = 0; i < xGridCount; i++) {
    const ratio = xGridCount === 1 ? 0 : i / (xGridCount - 1)
    const targetTs = minTs + tsSpan * ratio
    let bestIdx = 0
    let bestDist = Infinity
    tsList.forEach((t, idx) => {
      const d = Math.abs(t - targetTs)
      if (d < bestDist) { bestDist = d; bestIdx = idx }
    })
    indices.push(bestIdx)
  }
  return indices
}

/** 把一组点转为 SVG path d 字符串（M 起点 + L 后续）。xFor / yFor 由 caller 注入（已包好 padding）。 */
export function buildSparklinePath(
  points: SparklinePoint[],
  xFor: (ts: number) => number,
  yFor: (v: number) => number,
): string {
  return points
    .map((point, index) => {
      const ts = new Date(point.date).getTime()
      const x = xFor(ts)
      const y = yFor(Number(point.net_value) || 0)
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

/** 生成双线对比的轴 / 网格 / baseline SVG fragment（v-html 用）。
 *  - Y 网格 + 百分比标签
 *  - X 网格 + MM-DD 日期标签
 *  - y=1.0 基准线（如果落在画布内）
 */
export function buildSparklineAxes(
  strategy: SparklinePoint[],
  benchmark: SparklinePoint[],
  options: AxesOptions = {},
): string {
  const opts = { ...DEFAULT_AXES, ...options }
  const { width, height, padLeft, padRight, padTop, padBottom, yGridCount, xGridCount } = opts

  // x / y 坐标
  const allDates = [...strategy, ...benchmark].map((p) => p?.date).filter(Boolean) as string[]
  if (!allDates.length) return ''
  const tsList = allDates.map((d) => new Date(d).getTime())
  const minTs = Math.min(...tsList)
  const maxTs = Math.max(...tsList)
  const tsSpan = Math.max(maxTs - minTs, 1)

  const allValues = [...strategy, ...benchmark]
    .map((p) => Number(p.net_value) || 0)
    .concat([1.0])
  const minVal = Math.min(...allValues)
  const maxVal = Math.max(...allValues)
  const valPad = Math.max((maxVal - minVal) * 0.08, 0.005)
  const yMin = Math.max(0, minVal - valPad)
  const yMax = maxVal + valPad
  const valSpan = Math.max(yMax - yMin, 0.01)

  const xFor = (ts: number) => padLeft + ((ts - minTs) / tsSpan) * (width - padLeft - padRight)
  const yFor = (v: number) => padTop + ((yMax - v) / valSpan) * (height - padTop - padBottom)

  // Y 网格（按 valPad 后范围等分）
  const yTicks = Array.from({ length: yGridCount }, (_, i) => yMin + (yMax - yMin) * (i / (yGridCount - 1)))
  const yLines = yTicks
    .map((y) =>
      `<line x1="${padLeft}" x2="${width - padRight}" y1="${y.toFixed(2)}" y2="${y.toFixed(2)}" class="quant-sparkline__grid"/>` +
      `<text x="${padLeft - 6}" y="${(y + 3).toFixed(2)}" class="quant-sparkline__axis-label" text-anchor="end">${(y * 100).toFixed(0)}%</text>`
    )
    .join('')

  // X 网格（等分时间比例取最近点）
  const xTickIndices = pickXTickIndices(tsList, tsSpan, minTs, xGridCount)
  const xLines = xTickIndices
    .map((idx) => {
      const ts = tsList[idx]
      const x = xFor(ts)
      const dShort = (allDates[idx] || '').slice(5) // MM-DD
      return `<line x1="${x.toFixed(2)}" x2="${x.toFixed(2)}" y1="${padTop}" y2="${height - padBottom}" class="quant-sparkline__grid"/>` +
        `<text x="${x.toFixed(2)}" y="${(height - padBottom + 16).toFixed(2)}" class="quant-sparkline__axis-label" text-anchor="middle">${dShort}</text>`
    })
    .join('')

  // y=1.0 基准线（仅在画布内时画）
  const yBase = yFor(1.0)
  const baseLine = (yBase >= padTop && yBase <= height - padBottom)
    ? `<line x1="${padLeft}" x2="${width - padRight}" y1="${yBase.toFixed(2)}" y2="${yBase.toFixed(2)}" class="quant-sparkline__baseline"/>`
    : ''

  return yLines + xLines + baseLine
}

/** 把 strategy + benchmark 一次性转成 { strategy, benchmark, axes } 三段 SVG path / fragment。 */
export function buildSparklinePaths(
  strategy: SparklinePoint[],
  benchmark: SparklinePoint[],
  options: AxesOptions = {},
): { strategy: string; benchmark: string; axes: string } {
  const opts = { ...DEFAULT_AXES, ...options }
  const { width, height, padLeft, padRight, padTop, padBottom } = opts

  const allDates = [...strategy, ...benchmark].map((p) => p?.date).filter(Boolean) as string[]
  if (!allDates.length) return { strategy: '', benchmark: '', axes: '' }
  const tsList = allDates.map((d) => new Date(d).getTime())
  const minTs = Math.min(...tsList)
  const maxTs = Math.max(...tsList)
  const tsSpan = Math.max(maxTs - minTs, 1)

  const allValues = [...strategy, ...benchmark]
    .map((p) => Number(p.net_value) || 0)
    .concat([1.0])
  const minVal = Math.min(...allValues)
  const maxVal = Math.max(...allValues)
  const valPad = Math.max((maxVal - minVal) * 0.08, 0.005)
  const yMin = Math.max(0, minVal - valPad)
  const yMax = maxVal + valPad
  const valSpan = Math.max(yMax - yMin, 0.01)

  const xFor = (ts: number) => padLeft + ((ts - minTs) / tsSpan) * (width - padLeft - padRight)
  const yFor = (v: number) => padTop + ((yMax - v) / valSpan) * (height - padTop - padBottom)

  return {
    strategy: strategy.length >= 2 ? buildSparklinePath(strategy, xFor, yFor) : '',
    benchmark: benchmark.length >= 2 ? buildSparklinePath(benchmark, xFor, yFor) : '',
    axes: buildSparklineAxes(strategy, benchmark, options),
  }
}
