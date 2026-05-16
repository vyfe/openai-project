<template>
  <div class="quant-grid quant-grid--backtest">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>回测记录</h2>
          <p>先把同一策略不同时间窗的结果并排留下来，后面才谈版本对比和参数建议。</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadBacktests" :loading="workbench.loading.backtests">刷新</el-button>
        </div>
      </div>
      <el-table
        :data="workbench.backtestRuns"
        stripe
        height="700"
        class="quant-table"
        @row-click="workbench.handleBacktestSelect"
        :row-class-name="({ row }) => row.id === workbench.selectedBacktestId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="strategy_name" label="策略" min-width="160" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.backtestStatusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="区间" min-width="200">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="收益" width="100">
          <template #default="{ row }">{{ workbench.formatRate(row.metrics?.total_return) }}</template>
        </el-table-column>
        <el-table-column label="回撤" width="100">
          <template #default="{ row }">{{ workbench.formatRate(row.metrics?.max_drawdown) }}</template>
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
          <el-button type="primary" :icon="TrendCharts" @click="workbench.runBacktest" :loading="workbench.loading.runningBacktest">
            执行回测
          </el-button>
          <el-button v-if="workbench.selectedBacktestId" type="danger" plain @click="workbench.deleteSelectedBacktest">删除记录</el-button>
        </div>
      </div>

      <div class="quant-form-stack">
        <div class="quant-form-grid quant-form-grid--two">
          <el-form label-position="top">
            <el-form-item label="策略">
              <el-select v-model="workbench.backtestForm.strategyId" placeholder="选择策略">
                <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="基准标的">
              <el-select v-model="workbench.backtestForm.benchmarkSymbol" filterable clearable placeholder="可选，例如 510300.SH">
                <el-option
                  v-for="item in workbench.symbolOptions"
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
              <el-date-picker v-model="workbench.backtestForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="结束日期">
              <el-date-picker v-model="workbench.backtestForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="每日入选数">
              <el-input-number v-model="workbench.backtestForm.topN" :min="1" :max="20" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="持有天数">
              <el-input-number v-model="workbench.backtestForm.holdDays" :min="1" :max="60" class="quant-full-width" />
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="初始资金">
              <el-input-number v-model="workbench.backtestForm.initialCapital" :min="1000" :step="10000" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="手续费率">
              <el-input-number v-model="workbench.backtestForm.commissionRate" :min="0" :precision="4" :step="0.0001" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="滑点率">
              <el-input-number v-model="workbench.backtestForm.slippageRate" :min="0" :precision="4" :step="0.0001" class="quant-full-width" />
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="回测股票池（为空则使用策略自带股票池）">
            <el-select
              v-model="workbench.backtestForm.symbols"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="建议保持明确股票池，避免无边界扫描"
            >
              <el-option
                v-for="item in workbench.symbolOptions"
                :key="item.symbol"
                :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                :value="item.symbol"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <div v-if="workbench.selectedBacktest" class="quant-backtest-detail" v-loading="workbench.loading.backtestDetail">
        <div class="quant-mini-section__title">
          <span>结果概览</span>
          <span class="quant-muted">
            {{ workbench.selectedBacktest.strategy_name }} · {{ workbench.selectedBacktest.start_date }} ~ {{ workbench.selectedBacktest.end_date }}
          </span>
        </div>

        <div class="quant-metric-grid">
          <div v-for="card in workbench.backtestMetricCards" :key="card.title" class="quant-metric-card">
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
              <span>交易数 {{ workbench.selectedBacktest.trades_total }}</span>
              <span>信号数 {{ workbench.selectedBacktest.signals_total }}</span>
            </div>
          </div>
          <div class="quant-sparkline">
            <svg viewBox="0 0 760 220" preserveAspectRatio="none">
              <path v-if="workbench.backtestCurvePath" :d="workbench.backtestCurvePath" class="quant-sparkline__line" />
            </svg>
          </div>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>方法说明</span>
          </div>
          <div class="quant-pill-list">
            <span v-for="tip in workbench.selectedBacktest.summary?.limitations || []" :key="tip" class="quant-pill">{{ tip }}</span>
          </div>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>样本交易</span>
          </div>
          <el-table :data="workbench.backtestTradePreview" stripe height="280" class="quant-table">
            <el-table-column prop="symbol" label="标的" min-width="110" />
            <el-table-column prop="signal_date" label="信号日" width="108" />
            <el-table-column prop="entry_date" label="入场日" width="108" />
            <el-table-column prop="exit_date" label="离场日" width="108" />
            <el-table-column label="净收益" width="100">
              <template #default="{ row }">{{ workbench.formatRate(row.net_return) }}</template>
            </el-table-column>
            <el-table-column prop="score" label="得分" width="88" />
          </el-table>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { RefreshRight, TrendCharts } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()
</script>
