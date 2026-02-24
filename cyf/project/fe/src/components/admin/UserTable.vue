<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userAPI } from '@/services/adminApi'

const { t } = useI18n()

interface User {
  id: number
  username: string
  api_key: string
  role: string
  is_active: boolean
  created_at: string
  updated_at: string
}

const users = ref<User[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref({
  id: 0,
  username: '',
  password: '',
  api_key: '',
  role: 'user',
  is_active: true
})

const fetchUsers = async () => {
  loading.value = true
  try {
    const response = await userAPI.list()
    if (response.success) {
      users.value = response.data || []
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
    username: '',
    password: '',
    api_key: '',
    role: 'user',
    is_active: true
  }
  dialogVisible.value = true
}

const openEditDialog = (row: User) => {
  dialogMode.value = 'edit'
  formData.value = {
    id: row.id,
    username: row.username,
    password: '',
    api_key: row.api_key || '',
    role: row.role,
    is_active: row.is_active
  }
  dialogVisible.value = true
}

const saveUser = async () => {
  if (!formData.value.username) {
    ElMessage.error(t('admin.usernameRequired'))
    return
  }

  try {
    if (dialogMode.value === 'create') {
      if (!formData.value.password) {
        ElMessage.error(t('admin.passwordRequired'))
        return
      }
      const response = await userAPI.create(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchUsers()
      }
    } else {
      const updateData: any = {
        id: formData.value.id,
        username: formData.value.username,
        role: formData.value.role,
        is_active: formData.value.is_active
      }
      if (formData.value.api_key) {
        updateData.api_key = formData.value.api_key
      }
      if (formData.value.password) {
        updateData.new_password = formData.value.password
      }
      const response = await userAPI.update(updateData)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchUsers()
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.executeFailed'))
  }
}

const deleteUser = async (row: User) => {
  try {
    await ElMessageBox.confirm(
      `${t('admin.confirmDelete')} (${row.username})?`,
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.hardDelete'),
        cancelButtonText: t('admin.softDelete'),
        distinguishCancelAndClose: true,
        type: 'warning'
      }
    )
    const response = await userAPI.delete(row.id, true)
    if (response.success) {
      ElMessage.success(t('admin.deleteSuccess'))
      fetchUsers()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      // 软删除
      const response = await userAPI.delete(row.id, false)
      if (response.success) {
        ElMessage.success(t('admin.deleteSuccess'))
        fetchUsers()
      }
    }
  }
}

const maskApiKey = (key: string) => {
  if (!key) return '-'
  if (key.length <= 8) return key
  return key.substring(0, 4) + '****' + key.substring(key.length - 4)
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.userManagement') }}
      </h2>
      <el-button type="primary" @click="openCreateDialog" :icon="Plus">
        {{ t('admin.create') }}
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="users"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" :label="t('admin.username')" min-width="120" />
      <el-table-column prop="api_key" :label="t('admin.apiKey')" min-width="200">
        <template #default="{ row }">
          <code class="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
            {{ maskApiKey(row.api_key) }}
          </code>
        </template>
      </el-table-column>
      <el-table-column prop="role" :label="t('admin.role')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">
            {{ row.role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" :label="t('admin.isActive')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? t('admin.active') : t('admin.inactive') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" :label="t('admin.createdAt')" width="160" />
      <el-table-column prop="updated_at" :label="t('admin.updatedAt')" width="160" />
      <el-table-column :label="t('admin.actions')" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDialog(row)">
            {{ t('admin.edit') }}
          </el-button>
          <el-button type="danger" size="small" @click="deleteUser(row)">
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
        <el-form-item :label="t('admin.username')" required>
          <el-input v-model="formData.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'create'" :label="t('admin.password')" required>
          <el-input v-model="formData.password" type="password" />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'edit'" :label="t('admin.newPassword')">
          <el-input v-model="formData.password" type="password" :placeholder="t('admin.confirmPassword')" />
        </el-form-item>
        <el-form-item :label="t('admin.apiKey')">
          <el-input v-model="formData.api_key" :placeholder="t('admin.confirmPassword')" />
        </el-form-item>
        <el-form-item :label="t('admin.role')">
          <el-select v-model="formData.role">
            <el-option label="user" value="user" />
            <el-option label="admin" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dialogMode === 'edit'" :label="t('admin.isActive')">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
        <el-button type="primary" @click="saveUser">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-table {
  padding: 16px;
}
</style>
