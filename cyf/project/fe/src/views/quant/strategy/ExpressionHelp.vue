<template>
  <details class="expression-help">
    <summary class="expression-help__title">
      <el-icon><QuestionFilled /></el-icon>
      <span>表达式怎么写？（点击展开模板）</span>
    </summary>

    <div class="expression-help__body">
      <p class="expression-help__intro">
        每条规则的 <code class="expression-help__inline">expr</code> 是受限表达式——
        支持比较、布尔运算和一组白名单函数。
      </p>

      <div class="expression-help__legend">
        <span class="expression-help__legend-item">
          <code class="expression-help__ph">{{ '${变量名}' }}</code>
          <span class="expression-help__legend-hint">需要替换的变量（变量名/阈值）</span>
        </span>
        <span class="expression-help__legend-item">
          <code class="expression-help__bare">close</code>
          <span class="expression-help__legend-hint">直接可用的内置字段</span>
        </span>
        <span class="expression-help__legend-item">
          <code class="expression-help__str">"buy"</code>
          <span class="expression-help__legend-hint">字符串字面量（必须带引号）</span>
        </span>
      </div>

      <div
        v-for="grp in groups"
        :key="grp.title"
        class="expression-help__group"
      >
        <div class="expression-help__group-title">{{ grp.title }}</div>
        <ul class="expression-help__list">
          <li v-for="(item, i) in grp.items" :key="i">
            <button
              type="button"
              class="expression-help__code"
              :title="item.hint"
              @click="emit('insert', item.tpl)"
            >
              <span v-html="renderTemplate(item.tpl)" />
            </button>
            <div class="expression-help__hint">
              {{ item.hint }}
              <span v-if="item.note" class="expression-help__note">（{{ item.note }}）</span>
            </div>
          </li>
        </ul>
      </div>

      <div class="expression-help__caveats">
        <strong>几个容易踩的坑：</strong>
        <ul>
          <li>变量名区分大小写：<code>close</code> 和 <code>CLOSE</code> 不是同一个。</li>
          <li>取前 1 根用 <code>x[1]</code> 或 <code>prev(x)</code>；下标必须是非负整数。</li>
          <li>字符串字面量要带双引号：<code>td_signal == "buy_setup_complete"</code>。</li>
          <li>复合门控（gate.mode=expr）只能引用规则 id，例如 <code>r1 and (r2 or r3)</code>。</li>
        </ul>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'

const emit = defineEmits<{ insert: [text: string] }>()

/**
 * 模板中变量占位符规则：
 * - ${name}   → 用户需替换为具体变量名（点击插入时直接带过去）
 * - 其他字符    → 字面量，原样插入
 * 例如：
 *   "close > ${threshold}"           → 点击插入 "close > ${threshold}"
 *   "cross_up(${a}, ${b})"            → 点击插入 "cross_up(${a}, ${b})"
 *   "td_signal == \"${signal}\""      → 点击插入 "td_signal == \"${signal}\""
 */
const groups = [
  {
    title: 'bar 字段（直接可用，无需替换）',
    items: [
      { tpl: 'close > ${threshold}', hint: '收盘价阈值；可用 open/high/low', note: 'threshold 填数字' },
      { tpl: 'pct_change >= ${pct}', hint: '涨跌幅（百分比单位，如 2 表示 2%）', note: 'pct 填数字' },
      { tpl: 'turnover_rate >= ${pct}', hint: '换手率（百分比单位）' },
      { tpl: 'volume > ${vol}', hint: '成交量阈值' }
    ]
  },
  {
    title: 'MA / 均线（变量名要带窗口数字）',
    items: [
      { tpl: 'close > ma_${window}', hint: '站上 N 日线', note: 'window 填 5/10/20/60 等' },
      { tpl: 'close < ma_${window}', hint: '跌破 N 日线' },
      { tpl: 'close > ma_${fast} and close > ma_${slow}', hint: '均线多头排列' }
    ]
  },
  {
    title: '量能 / 区间',
    items: [
      { tpl: 'vol_ratio_${window} >= ${ratio}', hint: '量比阈值', note: 'ratio 如 1.2' },
      { tpl: 'period_return_${window} >= ${pct}', hint: 'N 日涨幅阈值', note: 'pct 百分比单位' },
      { tpl: 'volume > avg(volume, ${n})', hint: '成交量大于近 n 根均值' }
    ]
  },
  {
    title: '突破 / 区间',
    items: [
      { tpl: 'close > rolling_high_${window}', hint: '突破前 N 日最高（自动排除当日）' },
      { tpl: 'close < rolling_low_${window}', hint: '跌破前 N 日最低' }
    ]
  },
  {
    title: '指标信号',
    items: [
      { tpl: 'cross_up(${a}, ${b})', hint: 'a 上穿 b（金叉）', note: '常用于 MACD/KDJ' },
      { tpl: 'cross_down(${a}, ${b})', hint: 'a 下穿 b（死叉）' },
      { tpl: 'cross_up(${k}, ${d}) and ${k} < 30', hint: 'KDJ 超卖金叉（K<30）' },
      { tpl: 'td_signal == "${signal}"', hint: 'TD 序列特定信号', note: 'signal: buy_setup_complete / sell_setup_complete / bottom_divergence' },
      { tpl: 'td_signal == "bottom_divergence" or bottom_divergence', hint: '底背离（任一信号触发即可）' }
    ]
  },
  {
    title: '白名单函数',
    items: [
      { tpl: 'prev(${x})', hint: 'x 的前 1 根值' },
      { tpl: 'ref(${x}, ${n})', hint: 'x 的前 n 根值' },
      { tpl: 'avg(${x}, ${n})', hint: '当前及之前 n-1 根均值' },
      { tpl: 'abs(${x})', hint: '绝对值' },
      { tpl: 'min(${a}, ${b}) / max(${a}, ${b})', hint: '极值，跳过 None' }
    ]
  }
]

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** 把 ${var} 高亮成变量占位色，其他原样。 */
function renderTemplate(tpl: string): string {
  return escapeHtml(tpl).replace(
    /\$\{([^}]+)\}/g,
    '<span class="expression-help__ph">${$1}</span>'
  )
}
</script>

<style scoped>
.expression-help {
  margin-top: 8px;
  padding: 0;
  border: 1px solid var(--q-line);
  border-radius: 6px;
  background: var(--q-surface);
}
.expression-help__title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  color: var(--q-muted);
  font-size: 12px;
  list-style: none;
}
.expression-help__title::-webkit-details-marker { display: none; }
.expression-help__title:hover { color: var(--q-ink); }
.expression-help__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 12px 12px;
  border-top: 1px solid var(--q-line);
}
.expression-help__intro {
  margin: 8px 0 0;
  color: var(--q-muted);
  font-size: 12px;
  line-height: 1.5;
}
.expression-help__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 10px;
  background: var(--q-surface-2);
  border-radius: 4px;
  font-size: 11px;
}
.expression-help__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--q-muted);
}
.expression-help__legend-hint { color: var(--q-muted); }
.expression-help__inline {
  padding: 1px 4px;
  background: var(--q-surface);
  border: 1px solid var(--q-line);
  border-radius: 3px;
  font-family: var(--q-mono);
  font-size: 11px;
}
.expression-help__group-title {
  margin-top: 4px;
  color: var(--q-ink);
  font-size: 12px;
  font-weight: 600;
}
.expression-help__list {
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.expression-help__list li {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}
.expression-help__code {
  display: inline-block;
  text-align: left;
  padding: 6px 10px;
  border: 1px solid var(--q-line);
  border-radius: 4px;
  background: var(--q-surface-2);
  color: var(--q-ink);
  font-family: var(--q-mono);
  font-size: 12px;
  cursor: pointer;
  transition: background 120ms, border-color 120ms;
  white-space: pre-wrap;
  word-break: break-all;
  font-weight: normal;
}
.expression-help__code:hover {
  background: color-mix(in srgb, var(--q-copper) 14%, var(--q-surface-2));
  border-color: var(--q-copper);
}
.expression-help__code :deep(.expression-help__ph) {
  padding: 1px 4px;
  margin: 0 1px;
  background: color-mix(in srgb, var(--q-copper) 14%, transparent);
  border: 1px dashed var(--q-copper);
  border-radius: 3px;
  color: var(--q-copper);
  font-weight: 600;
}
.expression-help__code :deep(.expression-help__bare) {
  color: var(--q-ink);
}
.expression-help__code :deep(.expression-help__str) {
  color: var(--q-green);
}
.expression-help__hint {
  color: var(--q-muted);
  font-size: 12px;
  line-height: 1.45;
}
.expression-help__note {
  color: var(--q-line-strong);
  font-size: 11px;
}
.expression-help__caveats {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--q-line);
  color: var(--q-muted);
  font-size: 12px;
}
.expression-help__caveats ul {
  margin: 4px 0 0;
  padding-left: 18px;
  line-height: 1.6;
}
.expression-help__caveats code {
  background: var(--q-surface-2);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
  font-family: var(--q-mono);
}
.expression-help__ph {
  padding: 1px 4px;
  margin: 0 1px;
  background: color-mix(in srgb, var(--q-copper) 14%, transparent);
  border: 1px dashed var(--q-copper);
  border-radius: 3px;
  color: var(--q-copper);
  font-weight: 600;
  font-family: var(--q-mono);
}
.expression-help__bare {
  color: var(--q-ink);
  font-family: var(--q-mono);
}
.expression-help__str {
  color: var(--q-green);
  font-family: var(--q-mono);
}

@media (max-width: 768px) {
  .expression-help__list li { grid-template-columns: 1fr; }
}
</style>