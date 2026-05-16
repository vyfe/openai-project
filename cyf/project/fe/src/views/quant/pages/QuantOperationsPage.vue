<template>
  <div class="quant-grid quant-grid--operations">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>操作清单</h2>
          <p>这里登记人工是否采纳、怎么执行、后续结果如何，后面复盘和自学习都要用它。</p>
        </div>
        <div class="quant-toolbar">
          <el-button plain @click="workbench.resetOperationForm">新建登记</el-button>
          <el-button :icon="RefreshRight" @click="workbench.loadOperations" :loading="workbench.loading.operations">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="workbench.operationRecords"
        stripe
        height="700"
        class="quant-table"
        @row-click="workbench.handleOperationSelect"
        :row-class-name="({ row }) => row.id === workbench.selectedOperationId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="trade_date" label="交易日" width="110" />
        <el-table-column prop="symbol" label="标的" min-width="120" />
        <el-table-column prop="action" label="动作" width="92" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.operationStatusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.operationResultTag(row.result_status || '')">
              {{ row.result_status || '--' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联策略" min-width="150">
          <template #default="{ row }">{{ workbench.resolveStrategyName(row.strategy_id) }}</template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="180" />
      </el-table>
    </section>

    <section class="quant-panel quant-panel--editor">
      <div class="quant-panel__header">
        <div>
          <h2>{{ workbench.operationForm.id ? '编辑操作记录' : '新建操作记录' }}</h2>
          <p>{{ workbench.operationForm.signalId ? `已关联信号 #${workbench.operationForm.signalId}` : '可以手动录，也可以从执行记录里的信号直接带入。' }}</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadOperations" :loading="workbench.loading.operations">刷新</el-button>
        </div>
      </div>

      <div class="quant-form-stack">
        <div class="quant-form-grid quant-form-grid--two">
          <el-form label-position="top">
            <el-form-item label="关联策略">
              <el-select v-model="workbench.operationForm.strategyId" clearable placeholder="可选">
                <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="交易日">
              <el-date-picker v-model="workbench.operationForm.tradeDate" type="date" value-format="YYYY-MM-DD" placeholder="执行日期" />
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="标的">
              <el-select v-model="workbench.operationForm.symbol" filterable clearable placeholder="例如 600519.SH">
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
            <el-form-item label="动作">
              <el-select v-model="workbench.operationForm.action">
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
              <el-select v-model="workbench.operationForm.status">
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
              <el-input-number v-model="workbench.operationForm.price" :min="0" :precision="3" :step="0.1" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="数量">
              <el-input-number v-model="workbench.operationForm.quantity" :min="0" :step="100" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="金额">
              <el-input-number v-model="workbench.operationForm.amount" :min="0" :precision="2" :step="1000" class="quant-full-width" />
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="执行理由">
            <el-input v-model="workbench.operationForm.thesis" type="textarea" :rows="4" placeholder="写清楚为什么做这笔操作，最好和策略信号一一对应。" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="执行备注">
            <el-input v-model="workbench.operationForm.executionNote" type="textarea" :rows="3" placeholder="例如：分两笔成交、盘中追价、实际仓位控制。" />
          </el-form-item>
        </el-form>

        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="结果状态">
              <el-select v-model="workbench.operationForm.resultStatus" clearable placeholder="可选">
                <el-option label="pending" value="pending" />
                <el-option label="win" value="win" />
                <el-option label="loss" value="loss" />
                <el-option label="flat" value="flat" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="结果收益率">
              <el-input-number v-model="workbench.operationForm.resultPct" :precision="4" :step="0.01" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="结果金额">
              <el-input-number v-model="workbench.operationForm.resultAmount" :precision="2" :step="100" class="quant-full-width" />
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="复盘备注">
            <el-input v-model="workbench.operationForm.reviewNote" type="textarea" :rows="3" placeholder="写结果、偏差和下次如何改。" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="标签">
            <el-input v-model="workbench.operationForm.tagsText" placeholder="逗号分隔，例如：突破, 观察仓, 复盘重点" />
          </el-form-item>
        </el-form>
      </div>

      <div class="quant-actions">
        <el-button type="primary" :icon="EditPen" @click="workbench.saveOperation" :loading="workbench.loading.savingOperation">
          {{ workbench.operationForm.id ? '保存更新' : '录入操作' }}
        </el-button>
        <el-button plain @click="workbench.resetOperationForm">重置表单</el-button>
        <el-button v-if="workbench.operationForm.id" type="danger" plain @click="workbench.deleteSelectedOperation">删除记录</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { EditPen, RefreshRight } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()
</script>
