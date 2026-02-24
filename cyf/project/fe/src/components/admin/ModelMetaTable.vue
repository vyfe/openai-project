<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelMetaAPI } from '@/services/adminApi'

const { t } = useI18n()

interface ModelMeta {
  id: number
  model_name: string
  model_desc: string
  model_type: number
  recommend: boolean
  status_valid: boolean
}

const models = ref<ModelMeta[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref({
  id: 0,
  model_name: '',
  model_desc: '',
  model_type: 1,
  recommend: false,
  status_valid: true
})

const fetchModels = async () => {
  loading.value = true
  try {
    const response = await modelMetaAPI.list()
    if (response.success) {
      models.value = response.data || []
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.loading'))
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  dialogMode.value = 'create'
  formData.value = {
    id: 0,
    model_name: '',
    model_desc: '',
    model_type: 1,
    recommend: false,
    status_valid: true
  }
  dialogVisible.value = true
}

const openEditDialog = (row: ModelMeta) => {
  dialogMode.value = 'edit'
  formData.value = { ...row }
  dialogVisible.value = true
}

const saveModel = async () => {
  if (!formData.value.model_name) {
    ElMessage.error(t('admin.modelNameRequired'))
    return
  }

  try {
    if (dialogMode.value === 'create') {
      const response = await modelMetaAPI.create(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchModels()
      }
    } else {
      const response = await modelMetaAPI.update(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchModels()
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.executeFailed'))
  }
}

const deleteModel = async (row: ModelMeta) => {
  try {
    await ElMessageBox.confirm(
      t('admin.confirmDelete'),
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.yes'),
        cancelButtonText: t('admin.no'),
        type: 'warning'
      }
    )
    const response = await modelMetaAPI.delete(row.id)
    if (response.success) {
      ElMessage.success(t('admin.deleteSuccess'))
      fetchModels()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.deleteFailed'))
    }
  }
}

onMounted(() => {
  fetchModels()
})
</script>

<template>
  <div class="model-meta-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.modelManagement') }}
      </h2>
      <el-button type="primary" @click="openCreateDialog" :icon="Plus">
        {{ t('admin.create') }}
      </el-button>
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
      <el-table-column :label="t('admin.actions')" width="150" fixed="right">
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
        <el-form-item :label="t('admin.recommend')">
          <el-switch v-model="formData.recommend" />
        </el-form-item>
        <el-form-item :label="t('admin.statusValid')">
          <el-switch v-model="formData.status_valid" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
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
