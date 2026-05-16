<template>
  <div class="quant-grid quant-grid--im-positions">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>IM 通道</h2>
          <p>只保留飞书自建应用主通道；支持报告推送、对话查询和持仓录入。</p>
        </div>
        <div class="quant-toolbar">
          <el-button plain @click="workbench.resetImChannelForm">新建通道</el-button>
          <el-button :icon="RefreshRight" @click="workbench.loadImChannels" :loading="workbench.loading.imChannels">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="workbench.imChannels"
        stripe
        height="240"
        class="quant-table"
        @row-click="workbench.hydrateImChannelForm"
        :row-class-name="({ row }) => row.id === workbench.selectedChannelId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
      </el-table>

      <div class="quant-form-stack quant-section-gap">
        <div class="quant-form-grid quant-form-grid--two">
          <el-form label-position="top">
            <el-form-item label="名称">
              <el-input v-model="workbench.imChannelForm.name" placeholder="例如：量化日报群" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="状态">
              <el-select v-model="workbench.imChannelForm.status">
                <el-option label="active" value="active" />
                <el-option label="inactive" value="inactive" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="飞书接收 ID 类型">
              <el-select v-model="workbench.imChannelForm.receiveIdType">
                <el-option label="chat_id（群）" value="chat_id" />
                <el-option label="open_id（单人）" value="open_id" />
                <el-option label="user_id" value="user_id" />
                <el-option label="union_id" value="union_id" />
                <el-option label="email" value="email" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="receive_id">
              <el-input v-model="workbench.imChannelForm.receiveId" placeholder="群聊通常是 oc_xxx" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="回复方式">
              <el-switch v-model="workbench.imChannelForm.replyInThread" active-text="话题回复" inactive-text="普通回复" />
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="入站群 chat_id（可选）">
            <el-input v-model="workbench.imChannelForm.inboundChatId" placeholder="默认等于 receive_id；用于多通道时匹配飞书回调来源" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="说明">
            <el-input v-model="workbench.imChannelForm.description" placeholder="例如：收盘后测试报告群" />
          </el-form-item>
        </el-form>

        <div class="quant-actions">
          <el-button type="primary" :icon="Setting" @click="workbench.saveImChannel" :loading="workbench.loading.savingImChannel">保存通道</el-button>
          <el-button plain @click="workbench.sendImTestNow" :loading="workbench.loading.sendingIm">发送测试</el-button>
          <el-button plain @click="workbench.resetImChannelForm">重置</el-button>
          <el-button v-if="workbench.imChannelForm.id" type="danger" plain @click="workbench.deleteSelectedImChannel">删除</el-button>
        </div>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>推送动作</span>
          <span class="quant-muted">{{ workbench.selectedImChannel?.name || '先选一个通道' }}</span>
        </div>
        <div class="quant-form-grid quant-form-grid--three">
          <el-form label-position="top">
            <el-form-item label="发送通道">
              <el-select v-model="workbench.imSendForm.channelId" placeholder="选择已配置通道">
                <el-option v-for="item in workbench.imChannels" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="报告">
              <el-select v-model="workbench.imSendForm.reportId" clearable filterable placeholder="可选：发送一份测试报告">
                <el-option v-for="item in workbench.reports" :key="item.id" :label="`${item.trade_date} · ${item.title}`" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="持仓策略范围">
              <el-select v-model="workbench.imSendForm.strategyId" clearable placeholder="为空表示全部持仓">
                <el-option v-for="item in workbench.strategies" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
        <el-form label-position="top">
          <el-form-item label="测试消息内容">
            <el-input v-model="workbench.imSendForm.testContent" placeholder="发送 IM 联调消息" />
          </el-form-item>
        </el-form>
        <div class="quant-actions">
          <el-button type="primary" @click="workbench.sendReportNow" :loading="workbench.loading.sendingIm">发送选中报告</el-button>
          <el-button plain @click="workbench.sendPositionSummaryNow" :loading="workbench.loading.sendingIm">发送持仓摘要</el-button>
        </div>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>发送记录</span>
          <el-button text :icon="RefreshRight" @click="workbench.loadDeliveryRecords" :loading="workbench.loading.deliveryRecords">刷新</el-button>
        </div>
        <el-table :data="workbench.deliveryRecords" stripe height="240" class="quant-table">
          <el-table-column prop="channel_target" label="目标" min-width="200" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="report_id" label="报告" width="90" />
          <el-table-column prop="sent_at" label="发送时间" min-width="170" />
          <el-table-column prop="error_message" label="错误" min-width="220" />
        </el-table>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>飞书入站事件</span>
          <el-button text :icon="RefreshRight" @click="workbench.loadImInboundEvents" :loading="workbench.loading.imInboundEvents">刷新</el-button>
        </div>
        <el-table :data="workbench.imInboundEvents" stripe height="220" class="quant-table">
          <el-table-column prop="received_at" label="接收时间" min-width="170" />
          <el-table-column prop="status" label="状态" width="96" />
          <el-table-column prop="command" label="命令" width="120" />
          <el-table-column prop="chat_id" label="chat_id" min-width="160" />
          <el-table-column label="内容" min-width="220">
            <template #default="{ row }">{{ row.parsed_payload?.text || '--' }}</template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误" min-width="180" />
        </el-table>
      </div>
    </section>

    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>持仓台账</h2>
          <p>这里记录净持仓相关流水；机器人只负责摘要推送，录入仍由主服务承载。</p>
        </div>
        <div class="quant-toolbar">
          <el-button plain @click="workbench.resetPositionForm">新建流水</el-button>
          <el-button :icon="RefreshRight" @click="refreshPositions" :loading="workbench.loading.positionSummary || workbench.loading.positionJournal">刷新</el-button>
        </div>
      </div>

      <div class="quant-metric-grid">
        <div v-for="card in workbench.positionSummaryCards" :key="card.title" class="quant-metric-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
        </div>
      </div>

      <div class="quant-mini-section">
        <div class="quant-mini-section__title">
          <span>当前持仓</span>
        </div>
        <el-table :data="workbench.positionSummary" stripe height="220" class="quant-table">
          <el-table-column prop="symbol" label="标的" min-width="110" />
          <el-table-column prop="net_quantity" label="净持仓" width="96" />
          <el-table-column label="成本" width="100">
            <template #default="{ row }">{{ workbench.formatNumber(row.avg_cost, 4) }}</template>
          </el-table-column>
          <el-table-column label="现价" width="100">
            <template #default="{ row }">{{ workbench.formatNumber(row.latest_price, 4) }}</template>
          </el-table-column>
          <el-table-column label="浮盈" width="100">
            <template #default="{ row }">{{ workbench.formatRate(row.unrealized_pnl_pct) }}</template>
          </el-table-column>
          <el-table-column prop="last_occurred_at" label="最近变动" min-width="160" />
        </el-table>
      </div>
    </section>
  </div>
</template>
