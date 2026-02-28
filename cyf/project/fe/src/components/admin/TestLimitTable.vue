<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { testLimitAPI } from '@/services/adminApi'

const { t } = useI18n()

interface TestLimit {
  id: number
  user_ip: string
  user_count: number
  limit: number
}

const limits = ref<TestLimit[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref({
  id: 0,
  user_ip: '',
  user_count: 0,
  limit: 20
})

const fetchLimits = async () => {
  loading.value = true
  try {
    const response = await testLimitAPI.list()
    if (response.success) {
      limits.value = response.data || []
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
    user_ip: '',
    user_count: 0,
    limit: 20
  }
  dialogVisible.value = true
}

const openEditDialog = (row: TestLimit) => {
  dialogMode.value = 'edit'
  formData.value = { ...row }
  dialogVisible.value = true
}

const saveLimit = async () => {
  if (!formData.value.user_ip) {
    ElMessage.error(t('admin.userIpRequired'))
    return
  }

  try {
    if (dialogMode.value === 'create') {
      const response = await testLimitAPI.create(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchLimits()
      }
    } else {
      const response = await testLimitAPI.update(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchLimits()
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.executeFailed'))
  }
}

const deleteLimit = async (row: TestLimit) => {
  try {
    await ElMessageBox.confirm(
      `${t('admin.confirmDelete')} (${row.user_ip})?`,
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.yes'),
        cancelButtonText: t('admin.no'),
        type: 'warning'
      }
    )
    const response = await testLimitAPI.delete(row.id)
    if (response.success) {
      ElMessage.success(t('admin.deleteSuccess'))
      fetchLimits()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.deleteFailed'))
    }
  }
}

const resetLimit = async (row: TestLimit) => {
  try {
    await ElMessageBox.confirm(
      `${t('admin.reset')} (${row.user_ip})?`,
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.yes'),
        cancelButtonText: t('admin.no'),
        type: 'warning'
      }
    )
    const response = await testLimitAPI.reset({ id: row.id })
    if (response.success) {
      ElMessage.success(t('admin.resetPasswordSuccess'))
      fetchLimits()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.resetPasswordFailed'))
    }
  }
}

const resetAll = async () => {
  try {
    await ElMessageBox.confirm(
      t('admin.resetAll'),
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.yes'),
        cancelButtonText: t('admin.no'),
        type: 'warning'
      }
    )
    const response = await testLimitAPI.reset({ reset_all: true })
    if (response.success) {
      ElMessage.success(t('admin.resetPasswordSuccess'))
      fetchLimits()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.resetPasswordFailed'))
    }
  }
}

onMounted(() => {
  fetchLimits()
})
</script>

<template>
  <div class="test-limit-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.limitManagement') }}
      </h2>
      <div class="flex gap-2">
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
        <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
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
