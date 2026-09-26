<template>
  <div class="quant-grid quant-grid--im-positions">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>IM 通道</h2>
          <p>配置飞书自建应用通道；用于报告推送、对话查询和持仓录入。私聊通道由首次私聊消息自动注册。</p>
        </div>
        <div class="quant-toolbar">
          <el-button plain @click="workbench.resetImChannelForm">新建通道</el-button>
          <el-button :icon="RefreshRight" @click="refreshAll" :loading="anyLoading">刷新</el-button>
        </div>
      </div>

      <div class="quant-section-grid quant-section-grid--main">
        <el-table
          :data="workbench.imChannels"
          stripe
          height="100%"
          class="quant-table quant-table--interactive quant-table--flex"
          empty-text="暂无 IM 通道，点击「新建通道」开始"
          @row-click="workbench.hydrateImChannelForm"
          :row-class-name="({ row }) => row.id === workbench.selectedChannelId ? 'quant-row--active' : ''"
        >
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ workbench.statusLabel(row.status) }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" min-width="170" />
        </el-table>

        <el-form label-position="top" class="quant-form-stack">
          <div class="quant-form-grid quant-form-grid--two">
            <el-form-item label="名称">
              <el-input v-model="workbench.imChannelForm.name" placeholder="例如：量化日报群" />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="workbench.imChannelForm.status">
                <el-option label="启用" value="active" />
                <el-option label="停用" value="inactive" />
              </el-select>
            </el-form-item>
          </div>

          <div class="quant-form-grid quant-form-grid--three">
            <el-form-item label="飞书接收 ID 类型">
              <el-select v-model="workbench.imChannelForm.receiveIdType">
                <el-option label="chat_id（群）" value="chat_id" />
                <el-option label="open_id（单人）" value="open_id" />
                <el-option label="user_id" value="user_id" />
                <el-option label="union_id" value="union_id" />
                <el-option label="email" value="email" />
              </el-select>
            </el-form-item>
            <el-form-item label="receive_id">
              <el-input v-model="workbench.imChannelForm.receiveId" placeholder="群聊通常是 oc_xxx" />
            </el-form-item>
            <el-form-item label="回复方式">
              <el-switch v-model="workbench.imChannelForm.replyInThread" active-text="话题回复" inactive-text="普通回复" />
            </el-form-item>
          </div>

          <el-form-item label="入站群 chat_id（可选）">
            <el-input v-model="workbench.imChannelForm.inboundChatId" placeholder="默认等于 receive_id；用于多通道时匹配飞书回调来源" />
          </el-form-item>

          <el-form-item label="说明">
            <el-input v-model="workbench.imChannelForm.description" placeholder="例如：收盘后测试报告群" />
          </el-form-item>

          <div class="quant-actions">
            <el-button type="primary" :icon="Setting" @click="workbench.saveImChannel" :loading="workbench.loading.savingImChannel">保存通道</el-button>
            <el-button plain @click="workbench.sendImTestNow" :loading="workbench.loading.sendingIm">发送测试</el-button>
            <el-button plain @click="workbench.resetImChannelForm">重置</el-button>
            <el-button v-if="workbench.imChannelForm.id" type="danger" plain @click="workbench.deleteSelectedImChannel">删除</el-button>
          </div>
        </el-form>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>推送动作</h2>
          <p>选定通道后可发送报告或测试消息。私聊通道会自动按用户持仓过滤标的（参见调度执行任务）。</p>
        </div>
        <div class="quant-toolbar">
          <span class="quant-muted">{{ workbench.selectedImChannel?.name || '先选一个通道' }}</span>
        </div>
      </div>

      <div class="quant-form-stack">
        <div class="quant-form-grid quant-form-grid--three">
          <el-form-item label="发送通道">
            <el-select v-model="workbench.imSendForm.channelId" placeholder="选择已配置通道">
              <el-option v-for="item in workbench.imChannels" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="报告">
            <el-select v-model="workbench.imSendForm.reportId" clearable filterable placeholder="可选：发送一份测试报告">
              <el-option v-for="item in workbench.reports" :key="item.id" :label="`${item.trade_date} · ${item.title}`" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="持仓策略范围">
            <el-select v-model="workbench.imSendForm.strategyId" clearable placeholder="为空表示全部持仓">
              <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="测试消息内容">
          <el-input v-model="workbench.imSendForm.testContent" placeholder="发送 IM 联调消息" />
        </el-form-item>
        <div class="quant-actions">
          <el-button type="primary" @click="workbench.sendReportNow" :loading="workbench.loading.sendingIm">发送选中报告</el-button>
          <el-button plain @click="workbench.sendPositionSummaryNow" :loading="workbench.loading.sendingIm">发送持仓摘要</el-button>
        </div>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>发送记录</h2>
          <p>查看最近一次推送结果。</p>
        </div>
        <div class="quant-toolbar">
          <el-button text :icon="RefreshRight" @click="workbench.loadDeliveryRecords" :loading="workbench.loading.deliveryRecords">刷新</el-button>
        </div>
      </div>
      <el-table :data="workbench.deliveryRecords" stripe height="320" class="quant-table" empty-text="暂无发送记录">
        <el-table-column prop="channel_target" label="目标" min-width="200" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ workbench.statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="report_id" label="报告" width="90" />
        <el-table-column prop="sent_at" label="发送时间" min-width="170" />
        <el-table-column prop="error_message" label="错误" min-width="220" />
      </el-table>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>飞书入站事件</h2>
          <p>查看最近接收到的飞书事件；用于排查为什么某条消息没回复。</p>
        </div>
        <div class="quant-toolbar">
          <el-button text :icon="RefreshRight" @click="workbench.loadImInboundEvents" :loading="workbench.loading.imInboundEvents">刷新</el-button>
        </div>
      </div>
      <el-table :data="workbench.imInboundEvents" stripe height="320" class="quant-table" empty-text="暂无入站事件">
        <el-table-column prop="received_at" label="接收时间" min-width="170" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">{{ workbench.statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="command" label="命令" width="120" />
        <el-table-column prop="chat_id" label="chat_id" min-width="160" />
        <el-table-column label="内容" min-width="220">
          <template #default="{ row }">{{ row.parsed_payload?.text || '--' }}</template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误" min-width="180" />
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RefreshRight, Setting } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()

const anyLoading = computed(() =>
  workbench.loading.imChannels ||
  workbench.loading.deliveryRecords ||
  workbench.loading.imInboundEvents
)

const refreshAll = () => {
  void Promise.all([
    workbench.loadImChannels(),
    workbench.loadDeliveryRecords(),
    workbench.loadImInboundEvents(),
  ])
}
</script>
