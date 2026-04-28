<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { modelMetaAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus } from '@element-plus/icons-vue'

const { t } = useI18n()

interface ModelMeta {
  id: number
  model_name: string
  model_desc: string
  model_type: number
  model_grp: string
  recommend: boolean
  status_valid: boolean
}

const {
  items: models,
  loading,
  keyword,
  pagination,
  fetchList: fetchModels,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<ModelMeta, { page?: number; page_size?: number; keyword?: string }>(modelMetaAPI.list)

const createEmptyForm = () => ({
  id: 0,
  model_name: '',
  model_desc: '',
  model_type: 1,
  model_grp: '',
  recommend: false,
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

const saveModel = async () => {
  if (!formData.value.model_name) {
    ElMessage.error(t('admin.modelNameRequired'))
    return
  }

  await runAction(
    async () => (dialogMode.value === 'create'
      ? modelMetaAPI.create(formData.value)
      : modelMetaAPI.update(formData.value)),
    {
      successText: t('admin.saveSuccess'),
      errorFallbackText: 'admin.executeFailed',
      onSuccess: async () => {
        closeDialog()
        await fetchModels()
      }
    }
  ).catch(() => undefined)
}

const deleteModel = async (row: ModelMeta) => {
  await runConfirmedAction(
    {
      message: t('admin.confirmDelete'),
      title: t('admin.confirm'),
      confirmButtonText: t('admin.yes'),
      cancelButtonText: t('admin.no'),
      type: 'warning'
    },
    () => modelMetaAPI.delete(row.id),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      ignoreCancel: true,
      onSuccess: async () => {
        await fetchModels()
      }
    }
  ).catch(() => undefined)
}

onMounted(() => {
  fetchModels().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
})
</script>

<template>
  <div class="model-meta-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.modelManagement') }}
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
      :data="models"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="model_name" :label="t('admin.modelName')" min-width="150" />
      <el-table-column prop="model_desc" :label="t('admin.modelDesc')" min-width="200" />
      <el-table-column prop="model_type" :label="t('admin.modelType')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.model_type === 1 ? 'primary' : 'success'" size="small">
            {{ row.model_type === 1 ? t('admin.text') : t('admin.image') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="model_grp" :label="t('admin.modelGroup')" min-width="120" />
      <el-table-column prop="recommend" :label="t('admin.recommend')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.recommend ? 'warning' : 'info'" size="small">
            {{ row.recommend ? t('admin.yes') : t('admin.no') }}
          </el-tag>
        </template>
      </el-table-column>
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
          <el-button type="danger" size="small" @click="deleteModel(row)">
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
      width="600px"
    >
      <el-form label-width="120px">
        <el-form-item :label="t('admin.modelName')" required>
          <el-input v-model="formData.model_name" />
        </el-form-item>
        <el-form-item :label="t('admin.modelDesc')">
          <el-input v-model="formData.model_desc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('admin.modelType')">
          <el-select v-model="formData.model_type">
            <el-option :label="t('admin.text')" :value="1" />
            <el-option :label="t('admin.image')" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('admin.modelGroup')">
          <el-input v-model="formData.model_grp" :placeholder="t('admin.modelGroupPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('admin.recommend')">
          <el-switch v-model="formData.recommend" />
        </el-form-item>
        <el-form-item :label="t('admin.statusValid')">
          <el-switch v-model="formData.status_valid" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">{{ t('admin.cancel') }}</el-button>
        <el-button type="primary" @click="saveModel">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.model-meta-table {
  padding: 16px;
}
</style>
