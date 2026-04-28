<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runtimeAPI } from '@/services/adminApi'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const loading = ref(false)
const runtime = ref<any>(null)
const dbPath = ref('')

const formatSeconds = (seconds: number) => {
  if (!Number.isFinite(seconds)) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${h}h ${m}m ${s}s`
}

const fetchOverview = async () => {
  loading.value = true
  try {
    const response = await runtimeAPI.overview()
    if (response.success) {
      runtime.value = response.data?.runtime || null
      dbPath.value = response.data?.database?.path || ''
    } else {
      throw new Error(response.msg || '加载失败')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchOverview()
})
</script>

<template>
  <div class="runtime-overview p-4">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.observability') }}
      </h2>
      <el-button type="primary" size="small" :loading="loading" @click="fetchOverview">
        {{ t('admin.refresh') }}
      </el-button>
    </div>

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <el-card>
          <template #header>{{ t('admin.uptime') }}</template>
          <div class="text-xl font-semibold">{{ formatSeconds(runtime?.uptime_seconds || 0) }}</div>
        </el-card>
        <el-card>
          <template #header>{{ t('admin.activeTokens') }}</template>
          <div class="text-xl font-semibold">{{ runtime?.token_stats?.active_token_count ?? 0 }}</div>
        </el-card>
        <el-card>
          <template #header>{{ t('admin.modelCache') }}</template>
          <div class="text-sm">
            <div>{{ t('admin.status') }}: {{ runtime?.model_cache?.cached ? t('admin.active') : t('admin.inactive') }}</div>
            <div>{{ t('admin.modelCount') }}: {{ runtime?.model_cache?.model_count ?? 0 }}</div>
            <div>{{ t('admin.expireIn') }}: {{ runtime?.model_cache?.expires_in_seconds ?? 0 }}s</div>
          </div>
        </el-card>
      </div>

      <el-card class="mb-4">
        <template #header>{{ t('admin.databasePath') }}</template>
        <div class="text-xs break-all text-gray-600 dark:text-gray-300">{{ dbPath || '-' }}</div>
      </el-card>

      <el-card>
        <template #header>{{ t('admin.apiHostStatus') }}</template>
        <el-table :data="runtime?.api_hosts || []" border stripe>
          <el-table-column prop="index" label="#" width="60" />
          <el-table-column prop="host" :label="t('admin.host')" min-width="220" />
          <el-table-column :label="t('admin.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.blacklisted ? 'danger' : 'success'">
                {{ row.blacklisted ? t('admin.blacklisted') : t('admin.active') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="blacklist_remaining_seconds" :label="t('admin.remainingSeconds')" width="150" />
        </el-table>
      </el-card>
    </template>
  </div>
</template>
