<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemPromptAPI } from '@/services/adminApi'

const { t } = useI18n()

interface SystemPrompt {
  id: number
  role_name: string
  role_group: string
  role_desc: string
  role_content: string
  status_valid: boolean
}

const prompts = ref<SystemPrompt[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref({
  id: 0,
  role_name: '',
  role_group: '',
  role_desc: '',
  role_content: '',
  status_valid: true
})

const fetchPrompts = async () => {
  loading.value = true
  try {
    const response = await systemPromptAPI.list()
    if (response.success) {
      prompts.value = response.data || []
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
    role_name: '',
    role_group: '',
    role_desc: '',
    role_content: '',
    status_valid: true
  }
  dialogVisible.value = true
}

const openEditDialog = (row: SystemPrompt) => {
  dialogMode.value = 'edit'
  formData.value = { ...row }
  dialogVisible.value = true
}

const savePrompt = async () => {
  if (!formData.value.role_name || !formData.value.role_group) {
    ElMessage.error(formData.value.role_name ? t('admin.roleGroupRequired') : t('admin.roleNameRequired'))
    return
  }

  try {
    if (dialogMode.value === 'create') {
      const response = await systemPromptAPI.create(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchPrompts()
      }
    } else {
      const response = await systemPromptAPI.update(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchPrompts()
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.executeFailed'))
  }
}

const deletePrompt = async (row: SystemPrompt) => {
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
    const response = await systemPromptAPI.delete(row.id)
    if (response.success) {
      ElMessage.success(t('admin.deleteSuccess'))
      fetchPrompts()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.deleteFailed'))
    }
  }
}

onMounted(() => {
  fetchPrompts()
})
</script>

<template>
  <div class="system-prompt-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.promptManagement') }}
      </h2>
      <el-button type="primary" @click="openCreateDialog" :icon="Plus">
        {{ t('admin.create') }}
      </el-button>
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
      <el-table-column :label="t('admin.actions')" width="150" fixed="right">
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
        <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
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
