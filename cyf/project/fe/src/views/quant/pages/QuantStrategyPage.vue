<template>
  <div class="quant-grid quant-grid--strategy">
    <section class="quant-panel">
      <div class="quant-panel__header">
        <div>
          <h2>策略清单</h2>
          <p>先把规则固化下来，执行和调度才能稳定复用。</p>
        </div>
        <el-button plain @click="workbench.resetStrategyForm">新建策略</el-button>
      </div>
      <el-table
        :data="workbench.strategies"
        stripe
        height="680"
        class="quant-table"
        @row-click="workbench.handleStrategySelect"
        :row-class-name="({ row }) => row.id === workbench.selectedStrategyId ? 'quant-row--active' : ''"
      >
        <el-table-column prop="name" label="策略名" min-width="180" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="workbench.strategyStatusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="股票池" min-width="150">
          <template #default="{ row }">{{ row.symbols?.length || 0 }} 个</template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="180" />
      </el-table>
    </section>

    <section class="quant-panel quant-panel--editor">
      <div class="quant-panel__header">
        <div>
          <h2>{{ workbench.strategyForm.id ? '编辑策略' : '新建策略' }}</h2>
          <p>{{ workbench.selectedStrategy ? `当前策略：${workbench.selectedStrategy.name}` : '这版先围绕日线规则，方便快速验证信号质量。' }}</p>
        </div>
        <div class="quant-toolbar">
          <el-button :icon="RefreshRight" @click="workbench.loadStrategies" :loading="workbench.loading.strategies">刷新</el-button>
          <el-button type="primary" :icon="VideoPlay" @click="executeAndOpenRuns" :loading="workbench.loading.runningStrategy">执行策略</el-button>
        </div>
      </div>

      <div class="quant-form-stack">
        <div class="quant-form-grid quant-form-grid--two">
          <el-form label-position="top">
            <el-form-item label="策略名称">
              <el-input v-model="workbench.strategyForm.name" placeholder="例如：放量突破观察" />
            </el-form-item>
          </el-form>
          <el-form label-position="top">
            <el-form-item label="状态">
              <el-select v-model="workbench.strategyForm.status">
                <el-option label="active" value="active" />
                <el-option label="inactive" value="inactive" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <el-form label-position="top">
          <el-form-item label="策略描述">
            <el-input v-model="workbench.strategyForm.description" type="textarea" :rows="2" placeholder="写清楚这条策略要观察什么。" />
          </el-form-item>
        </el-form>

        <el-form label-position="top">
          <el-form-item label="股票池">
            <el-select v-model="workbench.strategyForm.symbols" multiple filterable collapse-tags collapse-tags-tooltip placeholder="为空时默认扫描当前交易日已有数据的全部标的">
              <el-option v-for="item in workbench.symbolOptions" :key="item.symbol" :label="item.symbol" :value="item.symbol" />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="quant-preset-strip">
          <button v-for="preset in workbench.strategyPresets" :key="preset.key" class="quant-preset-chip" @click="workbench.applyStrategyPreset(preset.config)">
            <strong>{{ preset.title }}</strong>
            <span>{{ preset.summary }}</span>
          </button>
        </div>

        <el-form label-position="top">
          <el-form-item label="规则 JSON">
            <el-input v-model="workbench.strategyForm.ruleConfigText" type="textarea" :rows="18" placeholder="在这里编辑规则 JSON" class="quant-code-input" />
          </el-form-item>
        </el-form>

        <div class="quant-run-inline">
          <el-form label-position="top" class="quant-run-inline__date">
            <el-form-item label="执行日期">
              <el-date-picker v-model="workbench.runForm.tradeDate" type="date" value-format="YYYY-MM-DD" placeholder="为空则用最新交易日" />
            </el-form-item>
          </el-form>
          <el-checkbox v-model="workbench.runForm.saveAllSignals">保存全部信号（包括未通过）</el-checkbox>
        </div>
      </div>

      <div class="quant-actions">
        <el-button type="primary" :icon="Setting" @click="workbench.saveStrategy" :loading="workbench.loading.savingStrategy">{{ workbench.strategyForm.id ? '保存更新' : '创建策略' }}</el-button>
        <el-button plain @click="workbench.resetStrategyForm">重置表单</el-button>
        <el-button v-if="workbench.strategyForm.id" type="danger" plain @click="workbench.deleteSelectedStrategy">删除策略</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { RefreshRight, Setting, VideoPlay } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const router = useRouter()
const workbench = useQuantWorkbench()

const executeAndOpenRuns = async () => {
  const runRecord = await workbench.executeSelectedStrategy()
  if (runRecord?.id) router.push('/quant/runs')
}
</script>
