<template>
  <div class="quant-grid quant-grid--scheduler">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>调度总览</h2>
          <p>这版只管两个时间轴：定时拉日线数据、定时做分析报告。都按交易日过滤。</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadSchedulerMeta" :loading="workbench.loading.schedulerMeta">刷新概览</el-button>
          <el-button plain @click="workbench.rebuildDueScheduleRuns">补扫应执行</el-button>
        </div>
      </div>

      <div class="quant-metric-grid">
        <div v-for="card in workbench.schedulerCards" :key="card.title" class="quant-metric-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
        </div>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>配置清单</span>
          <div class="quant-toolbar">
            <el-button plain @click="workbench.resetScheduleForm">新建配置</el-button>
            <el-button :icon="RefreshRight" @click="workbench.loadScheduleConfigs" :loading="workbench.loading.schedules">刷新</el-button>
          </div>
        </div>
        <el-table
          :data="workbench.scheduleConfigs"
          stripe
          height="420"
          class="quant-table"
          @row-click="workbench.handleScheduleSelect"
          :row-class-name="({ row }) => row.id === workbench.selectedScheduleId ? 'quant-row--active' : ''"
        >
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column prop="task_type" label="类型" width="130" />
          <el-table-column prop="cron_expr" label="Cron" min-width="140" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="workbench.strategyStatusTag(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button text @click.stop="workbench.manualRunSchedule(row.id)">手工触发</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <section class="quant-panel quant-panel--editor">
      <div class="quant-panel__header">
        <div>
          <h2>{{ workbench.scheduleForm.id ? '编辑调度配置' : '新建调度配置' }}</h2>
          <p>推荐 cron 例子：`20 15 * * 1-5`。工作日由交易日历再过滤一次，不靠 weekday 盲跑。</p>
        </div>
      </div>

      <div class="quant-form-stack">
        <div class="quant-form-grid quant-form-grid--two">
          <el-form label-position="top">
            <el-form-item label="名称">
              <el-input v-model="workbench.scheduleForm.name" placeholder="例如：收盘后数据拉取" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="任务类型">
              <el-select v-model="workbench.scheduleForm.taskType">
                <el-option label="定时拉数" value="data_sync" />
                <el-option label="测试报告" value="analysis_report" />
                <el-option label="记忆梳理" value="memory_digest" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-form-grid quant-form-grid--four">
          <el-form label-position="top">
            <el-form-item label="Cron">
              <el-input v-model="workbench.scheduleForm.cronExpr" placeholder="20 15 * * 1-5" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="状态">
              <el-select v-model="workbench.scheduleForm.status">
                <el-option label="active" value="active" />
                <el-option label="inactive" value="inactive" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="重试次数">
              <el-input-number v-model="workbench.scheduleForm.retryMax" :min="0" :max="10" class="quant-full-width" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="重试间隔(秒)">
              <el-input-number v-model="workbench.scheduleForm.retryDelaySeconds" :min="30" :max="3600" :step="30" class="quant-full-width" />
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="说明">
            <el-input v-model="workbench.scheduleForm.description" type="textarea" :rows="2" placeholder="说明这个时点为什么跑，以及希望产出什么。" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="允许手工重跑">
            <el-checkbox v-model="workbench.scheduleForm.allowManualRun">允许手工创建一次执行记录</el-checkbox>
          </el-form-item>
        </el-form>

        <template v-if="workbench.scheduleForm.taskType === 'data_sync'">
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="标的池">
                <el-select
                  v-model="workbench.scheduleForm.dataSymbols"
                  multiple
                  filterable
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="定时拉哪些股票"
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
            <el-form label-position="top">
              <el-form-item label="任务备注">
                <el-input v-model="workbench.scheduleForm.dataNote" placeholder="例如：收盘后补齐最近 20 个交易日窗口" />
              </el-form-item>
            </el-form>
          </div>

          <div class="quant-form-grid quant-form-grid--four">
            <el-form label-position="top">
              <el-form-item label="数据源">
                <el-select v-model="workbench.scheduleForm.dataProvider">
                  <el-option v-for="provider in workbench.providers" :key="provider" :label="provider" :value="provider" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="复权">
                <el-select v-model="workbench.scheduleForm.dataAdjustFlag">
                  <el-option label="前复权" value="qfq" />
                  <el-option label="后复权" value="hfq" />
                  <el-option label="不复权" value="raw" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="回看交易日数">
                <el-input-number v-model="workbench.scheduleForm.dataLookbackTradeDays" :min="1" :max="250" class="quant-full-width" />
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="客户端租约(秒)">
                <el-input-number v-model="workbench.scheduleForm.dataLeaseSeconds" :min="60" :max="7200" :step="60" class="quant-full-width" />
              </el-form-item>
            </el-form>
          </div>
        </template>

        <template v-else-if="workbench.scheduleForm.taskType === 'analysis_report'">
          <el-form label-position="top">
            <el-form-item label="报告策略">
              <el-select
                v-model="workbench.scheduleForm.analysisStrategyIds"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                placeholder="报告时需要执行哪些策略"
              >
                <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="自动推送 IM 通道（可选）">
              <el-select
                v-model="workbench.scheduleForm.analysisChannelIds"
                multiple
                clearable
                collapse-tags
                collapse-tags-tooltip
                placeholder="执行完报告后自动推送到这些 IM 通道"
              >
                <el-option
                  v-for="item in workbench.schedulerMeta?.im_channel_options || []"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="附带未通过信号">
              <el-checkbox v-model="workbench.scheduleForm.analysisSaveAllSignals">保存全部信号，方便复盘</el-checkbox>
            </el-form-item>
          </el-form>
        </template>

        <template v-else>
          <el-form label-position="top">
            <el-form-item label="记忆股票池（为空则按有行情数据的标的自动挑选）">
              <el-select
                v-model="workbench.scheduleForm.memorySymbols"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                placeholder="可选：只梳理重点标的"
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
          <div class="quant-form-grid quant-form-grid--two">
            <el-form label-position="top">
              <el-form-item label="回看天数">
                <el-input-number v-model="workbench.scheduleForm.memoryLookbackDays" :min="7" :max="365" class="quant-full-width" />
              </el-form-item>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="最多梳理标的数">
                <el-input-number v-model="workbench.scheduleForm.memoryLimit" :min="1" :max="300" class="quant-full-width" />
              </el-form-item>
            </el-form>
          </div>
        </template>
      </div>

      <div class="quant-actions">
        <el-button type="primary" :icon="Setting" @click="workbench.saveScheduleConfig" :loading="workbench.loading.savingSchedule">
          {{ workbench.scheduleForm.id ? '保存更新' : '创建配置' }}
        </el-button>
        <el-button plain @click="workbench.resetScheduleForm">重置表单</el-button>
        <el-button type="warning" plain @click="workbench.manualRunSchedule()" :loading="workbench.loading.manualScheduleRun">手工触发</el-button>
        <el-button v-if="workbench.scheduleForm.id" type="danger" plain @click="workbench.deleteSelectedSchedule">删除配置</el-button>
      </div>
    </section>

    <section class="quant-panel quant-panel--full">
      <div class="quant-panel__header">
        <div>
          <h2>执行记录</h2>
          <p>worker 会按 cron 生成执行记录并消费；这里主要用来观察、补偿和排错。</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadScheduleRuns" :loading="workbench.loading.scheduleRuns">刷新记录</el-button>
          <el-button plain @click="workbench.executeScheduleRunNow()">立即执行选中记录</el-button>
          <el-button plain @click="workbench.resetScheduleRunNow()">重试选中记录</el-button>
        </div>
      </div>

        <el-table
          :data="workbench.scheduleRuns"
          stripe
          height="360"
          class="quant-table"
          @row-click="selectScheduleRun"
          :row-class-name="({ row }) => row.id === workbench.selectedScheduleRunId ? 'quant-row--active' : ''"
        >
        <el-table-column prop="scheduled_for" label="计划时间" min-width="176" />
        <el-table-column prop="schedule_name" label="配置" min-width="150" />
        <el-table-column prop="task_type" label="类型" width="130" />
        <el-table-column prop="trigger_source" label="来源" width="100" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.taskStatusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" label="次数" width="76" />
        <el-table-column prop="message" label="说明" min-width="220" />
          <el-table-column label="操作" width="96">
            <template #default="{ row }">
              <el-button
                v-if="['pending', 'retry_wait'].includes(row.status)"
                text
                @click.stop="workbench.executeScheduleRunNow(row.id)"
              >
                执行
              </el-button>
              <el-button
                v-else-if="['failed', 'success', 'skipped'].includes(row.status)"
                text
                @click.stop="workbench.resetScheduleRunNow(row.id, row.status === 'success')"
              >
                重试
              </el-button>
            </template>
          </el-table-column>
        </el-table>

      <div v-if="workbench.selectedScheduleRun" class="quant-run-result">
        <div class="quant-mini-section__title">
          <span>结果详情</span>
          <div class="quant-toolbar">
            <span class="quant-muted">{{ workbench.selectedScheduleRun.schedule_name }} · {{ workbench.selectedScheduleRun.status }}</span>
            <el-button text @click="workbench.loadScheduleRunLog(workbench.selectedScheduleRun.id)">刷新日志</el-button>
          </div>
        </div>
        <el-input
          :model-value="JSON.stringify(workbench.selectedScheduleRun.result || workbench.selectedScheduleRun.payload || {}, null, 2)"
          type="textarea"
          :rows="10"
          readonly
          class="quant-code-input"
        />
        <div class="quant-mini-section__title" style="margin-top: 16px;">
          <span>执行日志</span>
          <span class="quant-muted">{{ workbench.selectedScheduleRun.log_file || '--' }}</span>
        </div>
        <el-input
          :model-value="workbench.selectedScheduleRunLogText || '暂无日志'"
          type="textarea"
          :rows="12"
          readonly
          class="quant-code-input"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { RefreshRight, Setting } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()

const selectScheduleRun = (row: { id: number }) => {
  workbench.selectedScheduleRunId = row.id
  void workbench.loadScheduleRunLog(row.id)
}
</script>
