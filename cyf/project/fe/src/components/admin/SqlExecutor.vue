<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { sqlAPI } from '@/services/adminApi'

const { t } = useI18n()

type SqlMetaTable = {
  table_name: string
  row_count: number
  columns: Array<{
    name: string
    data_type: string
    nullable: boolean
    primary_key: boolean
  }>
}

const sqlInput = ref('')
const executing = ref(false)
const loadingMeta = ref(false)
const results = ref<any[]>([])
const columns = ref<string[]>([])
const hasError = ref(false)
const errorMessage = ref('')
const dbPath = ref('')
const metaTables = ref<SqlMetaTable[]>([])
const activeMetaTable = ref('')

const executeSQL = async () => {
  const sql = sqlInput.value.trim()
  if (!sql) {
    ElMessage.error(t('admin.sqlRequired'))
    return
  }

  executing.value = true
  hasError.value = false
  errorMessage.value = ''

  try {
    const response = await sqlAPI.execute(sql)
    if (response.success) {
      results.value = []
      columns.value = []
      if (Array.isArray(response.data) && response.data.length > 0) {
        columns.value = Object.keys(response.data[0])
        results.value = response.data
      } else if (typeof response.data === 'object' && response.data !== null) {
        columns.value = Object.keys(response.data)
        results.value = [response.data]
      }
      if (results.value.length === 0) {
        ElMessage.success(t('admin.executeSuccess'))
      }
      await fetchSqlMeta()
    } else {
      hasError.value = true
      errorMessage.value = response.msg || t('admin.executeFailed')
    }
  } catch (error: any) {
    hasError.value = true
    errorMessage.value = error.response?.data?.msg || error.message || t('admin.executeFailed')
  } finally {
    executing.value = false
  }
}

const fetchSqlMeta = async () => {
  loadingMeta.value = true
  try {
    const response = await sqlAPI.meta()
    if (response.success) {
      dbPath.value = response.data?.database?.path || ''
      metaTables.value = response.data?.tables || []
      if (metaTables.value.length > 0 && !activeMetaTable.value) {
        activeMetaTable.value = metaTables.value[0].table_name
      }
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.executeFailed'))
  } finally {
    loadingMeta.value = false
  }
}

const clearResults = () => {
  results.value = []
  columns.value = []
  hasError.value = false
  errorMessage.value = ''
}

onMounted(() => {
  fetchSqlMeta()
})
</script>

<template>
  <div class="sql-executor">
    <div class="mb-4">
      <h2 class="text-lg font-semibold mb-2">
        {{ t('admin.sqlExecute') }}
      </h2>
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{ t('admin.sqlPlaceholder') }}
      </p>
    </div>

    <div class="mb-6 rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white/80 dark:bg-gray-800/60">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-md font-semibold text-gray-800 dark:text-gray-200">
          {{ t('admin.sqlMeta') }}
        </h3>
        <el-button size="small" :loading="loadingMeta" @click="fetchSqlMeta">{{ t('admin.refresh') }}</el-button>
      </div>
      <p class="text-xs text-gray-500 mb-3 break-all">{{ dbPath }}</p>

      <el-table
        v-loading="loadingMeta"
        :data="metaTables"
        size="small"
        border
        max-height="220"
      >
        <el-table-column prop="table_name" :label="t('admin.tableName')" min-width="160" />
        <el-table-column prop="row_count" :label="t('admin.rowCount')" width="120" />
      </el-table>

      <div class="mt-4" v-if="metaTables.length">
        <el-select v-model="activeMetaTable" style="width: 260px" :placeholder="t('admin.tableName')">
          <el-option
            v-for="item in metaTables"
            :key="item.table_name"
            :label="item.table_name"
            :value="item.table_name"
          />
        </el-select>
        <el-table
          class="mt-3"
          :data="metaTables.find(ti => ti.table_name === activeMetaTable)?.columns || []"
          size="small"
          border
          max-height="220"
        >
          <el-table-column prop="name" :label="t('admin.columnName')" min-width="180" />
          <el-table-column prop="data_type" :label="t('admin.columnType')" min-width="120" />
          <el-table-column prop="nullable" :label="t('admin.nullable')" width="100">
            <template #default="{ row }">{{ row.nullable ? t('admin.yes') : t('admin.no') }}</template>
          </el-table-column>
          <el-table-column prop="primary_key" :label="t('admin.primaryKey')" width="100">
            <template #default="{ row }">{{ row.primary_key ? t('admin.yes') : t('admin.no') }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="mb-4">
      <el-input
        v-model="sqlInput"
        type="textarea"
        :rows="8"
        :placeholder="t('admin.sqlPlaceholder')"
        class="sql-input"
      />
    </div>

    <div class="mb-4 flex gap-2">
      <el-button
        type="primary"
        @click="executeSQL"
        :loading="executing"
        :disabled="!sqlInput.trim()"
      >
        <el-icon v-if="!executing"><CaretRight /></el-icon>
        {{ executing ? t('admin.loading') : t('admin.execute') }}
      </el-button>
      <el-button @click="clearResults">
        {{ t('admin.clear') }}
      </el-button>
    </div>

    <div class="results-container" v-if="hasError || columns.length > 0">
      <div v-if="hasError" class="error-message mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <div class="flex items-center gap-2 text-red-600 dark:text-red-400">
          <el-icon><CircleCloseFilled /></el-icon>
          <span class="font-semibold">{{ t('admin.executeFailed') }}</span>
        </div>
        <p class="mt-2 text-sm">{{ errorMessage }}</p>
      </div>

      <div v-else-if="columns.length > 0">
        <h3 class="text-md font-semibold text-gray-800 dark:text-gray-200 mb-2">
          {{ t('admin.result') }} ({{ results.length }} {{ t('admin.units') }})
        </h3>
        <el-table
          :data="results"
          stripe
          border
          max-height="500"
          style="width: 100%"
        >
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
      </div>
    </div>

    <div v-else class="empty-state p-8 text-center">
      <el-icon class="text-6xl text-gray-300 dark:text-gray-600"><Document /></el-icon>
      <p class="mt-4 text-gray-500 dark:text-gray-400">
        {{ t('admin.noData') }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.sql-executor {
  padding: 16px;
}

.sql-input {
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
}

.error-message {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.empty-state {
  animation: fadeIn 0.5s ease-in;
}
</style>
