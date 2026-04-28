<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { testLimitAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus, Refresh } from '@element-plus/icons-vue'

const { t } = useI18n()

interface TestLimit {
  id: number
  user_ip: string
  user_count: number
  limit: number
}

const {
  items: limits,
  loading,
  keyword,
  pagination,
  fetchList: fetchLimits,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<TestLimit, { page?: number; page_size?: number; keyword?: string }>(testLimitAPI.list)

const createEmptyForm = () => ({
  id: 0,
  user_ip: '',
  user_count: 0,
  limit: 20
})

const { runAction, runConfirmedAction } = useAdminAction((key) => t(key))

const {
  dialogVisible,
  dialogMode,
  formData,
  openCreateDialog,
  openEditDialog,
  closeDialog
} = useAdminCrudDialog(createEmptyForm)

const saveLimit = async () => {
  if (!formData.value.user_ip) {
    ElMessage.error(t('admin.userIpRequired'))
    return
  }

  await runAction(
    async () => (dialogMode.value === 'create'
      ? testLimitAPI.create(formData.value)
      : testLimitAPI.update(formData.value)),
    {
      successText: t('admin.saveSuccess'),
      errorFallbackText: 'admin.executeFailed',
      onSuccess: async () => {
        closeDialog()
        await fetchLimits()
      }
    }
  ).catch(() => undefined)
}

const deleteLimit = async (row: TestLimit) => {
  await runConfirmedAction(
    {
      message: `${t('admin.confirmDelete')} (${row.user_ip})?`,
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => testLimitAPI.delete(row.id),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchLimits()
      }
    }
  ).catch(() => undefined)
}

const resetLimit = async (row: TestLimit) => {
  await runConfirmedAction(
    {
      message: `${t('admin.reset')} (${row.user_ip})?`,
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => testLimitAPI.reset({ id: row.id }),
    {
      successText: t('admin.resetPasswordSuccess'),
      errorFallbackText: 'admin.resetPasswordFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchLimits()
      }
    }
  ).catch(() => undefined)
}

const resetAll = async () => {
  await runConfirmedAction(
    {
      message: t('admin.resetAll'),
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => testLimitAPI.reset({ reset_all: true }),
    {
      successText: t('admin.resetPasswordSuccess'),
      errorFallbackText: 'admin.resetPasswordFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchLimits()
      }
    }
  ).catch(() => undefined)
}

onMounted(() => {
  fetchLimits().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
})
</script>

<template>
  <div class="test-limit-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.limitManagement') }}
      </h2>
      <div class="flex items-center gap-2">
        <el-input
          v-model="keyword"
          clearable
          :placeholder="t('admin.searchPlaceholder')"
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="() => handleSearch().catch(() => undefined)"
        />
        <el-button type="primary" @click="() => handleSearch().catch(() => undefined)">{{ t('admin.query') }}</el-button>
        <el-button type="primary" @click="openCreateDialog" :icon="Plus">
          {{ t('admin.create') }}
        </el-button>
        <el-button type="warning" @click="resetAll" :icon="Refresh">
          {{ t('admin.resetAll') }}
        </el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="limits"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="user_ip" :label="t('admin.userIp')" min-width="150" />
      <el-table-column prop="user_count" :label="t('admin.userCount')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.user_count >= row.limit ? 'danger' : 'success'" size="small">
            {{ row.user_count }} / {{ row.limit }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="limit" :label="t('admin.limit')" width="100" />
      <el-table-column class-name="action-column wide" :label="t('admin.actions')" width="250" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDialog(row)">
            {{ t('admin.edit') }}
          </el-button>
          <el-button type="warning" size="small" @click="resetLimit(row)" :icon="Refresh">
            {{ t('admin.reset') }}
          </el-button>
          <el-button type="danger" size="small" @click="deleteLimit(row)">
            {{ t('admin.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-4 flex justify-end">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :total="pagination.total"
        :page-size="pagination.page_size"
        :current-page="pagination.page"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="(page) => handlePageChange(page).catch(() => undefined)"
        @size-change="(size) => handlePageSizeChange(size).catch(() => undefined)"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? t('admin.create') : t('admin.edit')"
      width="500px"
    >
      <el-form label-width="120px">
        <el-form-item :label="t('admin.userIp')" required>
          <el-input v-model="formData.user_ip" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('admin.userCount')">
          <el-input-number v-model="formData.user_count" :min="0" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('admin.limit')">
          <el-input-number v-model="formData.limit" :min="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">{{ t('admin.cancel') }}</el-button>
        <el-button type="primary" @click="saveLimit">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.test-limit-table {
  padding: 16px;
}
</style>
