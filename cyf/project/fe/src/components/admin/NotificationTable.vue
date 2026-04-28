<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { notificationAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus } from '@element-plus/icons-vue'

const { t } = useI18n()

interface Notification {
  id: number
  title: string
  content: string
  publish_time: string
  status: string
  priority: number
  created_at: string
  updated_at: string
}

const {
  items: notifications,
  loading,
  keyword,
  pagination,
  fetchList: fetchNotifications,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<Notification, { page?: number; page_size?: number; keyword?: string }>(notificationAPI.list)

const createEmptyForm = () => ({
  id: 0,
  title: '',
  content: '',
  publish_time: '',
  priority: 0,
  status: 'active'
})

const { runAction, runConfirmedAction } = useAdminAction((key) => t(key))

const {
  dialogVisible,
  dialogMode,
  formData,
  openEditDialog,
  closeDialog
} = useAdminCrudDialog(
  createEmptyForm,
  (row: Notification) => ({ ...row })
)

const openCreateDialog = () => {
  const today = new Date().toISOString().slice(0, 10)
  formData.value = {
    ...createEmptyForm(),
    publish_time: today
  }
  dialogMode.value = 'create'
  dialogVisible.value = true
}

const saveNotification = async () => {
  if (!formData.value.title || !formData.value.content) {
    ElMessage.error(formData.value.title ? t('admin.contentRequired') : t('admin.titleRequired'))
    return
  }

  await runAction(
    async () => (dialogMode.value === 'create'
      ? notificationAPI.create(formData.value)
      : notificationAPI.update(formData.value)),
    {
      successText: t('admin.saveSuccess'),
      errorFallbackText: 'admin.executeFailed',
      onSuccess: async () => {
        closeDialog()
        await fetchNotifications()
      }
    }
  ).catch(() => undefined)
}

const deleteNotification = async (row: Notification) => {
  await runConfirmedAction(
    {
      message: `${t('admin.confirmDelete')} (${row.title})?`,
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => notificationAPI.delete(row.id),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchNotifications()
      }
    }
  ).catch(() => undefined)
}

onMounted(() => {
  fetchNotifications().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
})
</script>

<template>
  <div class="notification-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.notificationManagement') }}
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
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="notifications"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" :label="t('admin.title')" min-width="150" />
      <el-table-column prop="content" :label="t('admin.content')" min-width="200" show-overflow-tooltip />
      <el-table-column prop="publish_time" :label="t('admin.publishTime')" width="120" />
      <el-table-column prop="priority" :label="t('admin.priority')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.priority > 5 ? 'danger' : row.priority > 0 ? 'warning' : 'info'" size="small">
            {{ row.priority }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" :label="t('admin.statusValid')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? t('admin.active') : t('admin.inactive') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" :label="t('admin.createdAt')" width="160" />
      <el-table-column prop="updated_at" :label="t('admin.updatedAt')" width="160" />
      <el-table-column class-name="action-column" :label="t('admin.actions')" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDialog(row)">
            {{ t('admin.edit') }}
          </el-button>
          <el-button type="danger" size="small" @click="deleteNotification(row)">
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
      width="700px"
    >
      <el-form label-width="120px">
        <el-form-item :label="t('admin.title')" required>
          <el-input v-model="formData.title" />
        </el-form-item>
        <el-form-item :label="t('admin.content')" required>
          <el-input v-model="formData.content" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item :label="t('admin.publishTime')">
          <el-input v-model="formData.publish_time" type="date" />
        </el-form-item>
        <el-form-item :label="t('admin.priority')">
          <el-input-number v-model="formData.priority" :min="0" :max="10" />
        </el-form-item>
        <el-form-item :label="t('admin.statusValid')">
          <el-select v-model="formData.status">
            <el-option :label="t('admin.active')" value="active" />
            <el-option :label="t('admin.inactive')" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">{{ t('admin.cancel') }}</el-button>
        <el-button type="primary" @click="saveNotification">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.notification-table {
  padding: 16px;
}
</style>
