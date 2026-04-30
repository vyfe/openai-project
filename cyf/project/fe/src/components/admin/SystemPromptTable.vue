<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { systemPromptAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus } from '@element-plus/icons-vue'

const { t } = useI18n()

interface SystemPrompt {
  id: number
  role_name: string
  role_group: string
  role_desc: string
  role_content: string
  status_valid: boolean
}

const {
  items: prompts,
  loading,
  keyword,
  pagination,
  fetchList: fetchPrompts,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<SystemPrompt, { page?: number; page_size?: number; keyword?: string }>(systemPromptAPI.list)

const createEmptyForm = () => ({
  id: 0,
  role_name: '',
  role_group: '',
  role_desc: '',
  role_content: '',
  status_valid: true
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

const savePrompt = async () => {
  if (!formData.value.role_name || !formData.value.role_group) {
    ElMessage.error(formData.value.role_name ? t('admin.roleGroupRequired') : t('admin.roleNameRequired'))
    return
  }

  await runAction(
    async () => (dialogMode.value === 'create'
      ? systemPromptAPI.create(formData.value)
      : systemPromptAPI.update(formData.value)),
    {
      successText: t('admin.saveSuccess'),
      errorFallbackText: 'admin.executeFailed',
      onSuccess: async () => {
        closeDialog()
        await fetchPrompts()
      }
    }
  ).catch(() => undefined)
}

const deletePrompt = async (row: SystemPrompt) => {
  await runConfirmedAction(
    {
      message: t('admin.confirmDelete'),
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => systemPromptAPI.delete(row.id),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchPrompts()
      }
    }
  ).catch(() => undefined)
}

onMounted(() => {
  fetchPrompts().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
})
</script>

<template>
  <div class="system-prompt-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold">
        {{ t('admin.promptManagement') }}
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
      :data="prompts"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="role_name" :label="t('admin.roleName')" min-width="120" />
      <el-table-column prop="role_group" :label="t('admin.roleGroup')" min-width="120" />
      <el-table-column prop="role_desc" :label="t('admin.roleDesc')" min-width="200" show-overflow-tooltip />
      <el-table-column prop="role_content" :label="t('admin.roleContent')" min-width="250" show-overflow-tooltip />
      <el-table-column prop="status_valid" :label="t('admin.statusValid')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status_valid ? 'success' : 'danger'" size="small">
            {{ row.status_valid ? t('admin.active') : t('admin.inactive') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column class-name="action-column" :label="t('admin.actions')" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDialog(row)">
            {{ t('admin.edit') }}
          </el-button>
          <el-button type="danger" size="small" @click="deletePrompt(row)">
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
        <el-form-item :label="t('admin.roleName')" required>
          <el-input v-model="formData.role_name" />
        </el-form-item>
        <el-form-item :label="t('admin.roleGroup')" required>
          <el-input v-model="formData.role_group" />
        </el-form-item>
        <el-form-item :label="t('admin.roleDesc')">
          <el-input v-model="formData.role_desc" />
        </el-form-item>
        <el-form-item :label="t('admin.roleContent')">
          <el-input v-model="formData.role_content" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item :label="t('admin.statusValid')">
          <el-switch v-model="formData.status_valid" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">{{ t('admin.cancel') }}</el-button>
        <el-button type="primary" @click="savePrompt">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.system-prompt-table {
  padding: 16px;
}
</style>
