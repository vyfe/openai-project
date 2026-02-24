<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { sqlAPI } from '@/services/adminApi'

const { t } = useI18n()

const sqlInput = ref('')
const executing = ref(false)
const results = ref<any[]>([])
const columns = ref<string[]>([])
const hasError = ref(false)
const errorMessage = ref('')

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

      // 处理结果
      if (Array.isArray(response.data)) {
        if (response.data.length > 0) {
          // 如果是数组，提取列名
          columns.value = Object.keys(response.data[0])
          results.value = response.data
        }
      } else if (typeof response.data === 'object' && response.data !== null) {
        // 如果是对象，转换为数组
        columns.value = Object.keys(response.data)
        results.value = [response.data]
      }

      if (results.value.length === 0) {
        // 如果没有结果，可能是INSERT/UPDATE/DELETE等操作
        ElMessage.success(t('admin.executeSuccess'))
      }
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

const clearResults = () => {
  results.value = []
  columns.value = []
  hasError.value = false
  errorMessage.value = ''
}

// TODO(human): 实现SQL语法高亮功能
// 前端使用CodeMirror编辑器实现SQL语法高亮
// 考虑添加常用SQL模板按钮（如SELECT、INSERT、UPDATE等）
// 可以添加表名自动补全功能

// TODO(human): 实现查询历史记录功能
// 保存最近执行的SQL语句
// 提供快速访问历史查询的功能
// 可以添加收藏常用查询的功能
</script>

<template>
  <div class="sql-executor">
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">
        {{ t('admin.sqlExecute') }}
      </h2>
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{ t('admin.sqlPlaceholder') }}
      </p>
    </div>

    <!-- SQL输入区域 -->
    <div class="mb-4">
      <el-input
        v-model="sqlInput"
        type="textarea"
        :rows="8"
        :placeholder="t('admin.sqlPlaceholder')"
        class="sql-input"
      />
    </div>

    <!-- 操作按钮 -->
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

    <!-- 执行结果 -->
    <div class="results-container" v-if="hasError || columns.length > 0">
      <!-- 错误信息 -->
      <div v-if="hasError" class="error-message mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <div class="flex items-center gap-2 text-red-600 dark:text-red-400">
          <el-icon><CircleCloseFilled /></el-icon>
          <span class="font-semibold">{{ t('admin.executeFailed') }}</span>
        </div>
        <p class="mt-2 text-sm">{{ errorMessage }}</p>
      </div>

      <!-- 结果表格 -->
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

    <!-- 空状态 -->
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
