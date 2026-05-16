<template>
  <div class="quant-grid quant-grid--data">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>查日线数据</h2>
          <p>先看数据质量，再决定策略口径和观察标的。</p>
        </div>
        <el-button :icon="Search" type="primary" @click="workbench.loadDailyBars" :loading="workbench.loading.dailyBars">查询</el-button>
      </div>

      <div class="quant-form-grid">
        <el-form label-position="top">
          <el-form-item label="股票代码">
            <el-select v-model="workbench.dailyQuery.symbol" filterable clearable placeholder="例如 600519.SH">
              <el-option
                v-for="item in workbench.symbolOptions"
                :key="item.symbol"
                :label="`${item.symbol}${item.name ? ` · ${item.name}` : ''}`"
                :value="item.symbol"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <el-form label-position="top">
          <el-form-item label="开始日期">
            <el-date-picker v-model="workbench.dailyQuery.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
          </el-form-item>
        </el-form>
        <el-form label-position="top">
          <el-form-item label="结束日期">
            <el-date-picker v-model="workbench.dailyQuery.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
          </el-form-item>
        </el-form>
        <el-form label-position="top">
          <el-form-item label="返回条数">
            <el-input-number v-model="workbench.dailyQuery.limit" :min="20" :max="5000" :step="20" />
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="workbench.dailyBars" stripe height="460" class="quant-table">
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
          <el-button type="primary" :icon="Promotion" @click="workbench.createTask" :loading="workbench.loading.createTask">创建任务</el-button>
        </div>

        <div class="quant-form-stack">
          <el-form label-position="top">
            <el-form-item label="股票池">
              <el-select v-model="workbench.taskForm.symbols" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择一个或多个标的">
                <el-option v-for="item in workbench.symbolOptions" :key="item.symbol" :label="item.symbol" :value="item.symbol" />
              </el-select>
            </el-form-item>
          </el-form>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="开始日期">
                <el-date-picker v-model="workbench.taskForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="结束日期">
                <el-date-picker v-model="workbench.taskForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
              </el-form-item>
            </el-form>
          </div>
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="数据源">
                <el-select v-model="workbench.taskForm.provider">
                  <el-option v-for="provider in workbench.providers" :key="provider" :label="provider" :value="provider" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="复权">
                <el-select v-model="workbench.taskForm.adjustFlag">
                  <el-option label="前复权" value="qfq" />
                  <el-option label="后复权" value="hfq" />
                  <el-option label="不复权" value="raw" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>
          <el-form label-position="top">
            <el-form-item label="备注">
              <el-input v-model="workbench.taskForm.note" placeholder="例如：补 2024-2025 年回测样本" />
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>最近任务</span>
            <el-button text :icon="RefreshRight" @click="workbench.loadTasks" :loading="workbench.loading.tasks">刷新</el-button>
          </div>
          <div class="quant-mini-list">
            <div v-for="task in workbench.clientTasks" :key="task.task_id" class="quant-mini-item">
              <div class="quant-mini-item__head">
                <span class="quant-mini-item__title">{{ task.payload?.symbols?.slice(0, 2)?.join(', ') || task.task_id }}</span>
                <el-tag size="small" :type="workbench.taskStatusTag(task.status)">{{ task.status }}</el-tag>
              </div>
              <div class="quant-mini-item__meta">{{ task.payload?.start_date }} 至 {{ task.payload?.end_date }}</div>
              <div class="quant-mini-item__actions">
                <span>{{ task.message || '等待客户端处理' }}</span>
                <el-button v-if="task.status === 'failed'" text @click="workbench.resetTask(task.task_id)">重置</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="quant-mini-section">
          <div class="quant-mini-section__title">
            <span>最近导入批次</span>
            <el-button text :icon="RefreshRight" @click="workbench.loadImportBatches" :loading="workbench.loading.importBatches">刷新</el-button>
          </div>
          <div class="quant-mini-list">
            <div v-for="batch in workbench.importBatches" :key="batch.batch_id" class="quant-mini-item">
              <div class="quant-mini-item__head">
                <span class="quant-mini-item__title">{{ batch.source }}</span>
                <el-tag size="small" :type="workbench.taskStatusTag(batch.status)">{{ batch.status }}</el-tag>
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
</template>

<script setup lang="ts">
import { Promotion, RefreshRight, Search } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()
</script>
