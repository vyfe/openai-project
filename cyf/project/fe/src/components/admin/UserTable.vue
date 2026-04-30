<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { userAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus } from '@element-plus/icons-vue'

const { t } = useI18n()

interface User {
  id: number
  username: string
  api_key_masked: string
  api_key?: string
  role: string
  is_active: boolean
  created_at: string
  updated_at: string
}

const {
  items: users,
  loading,
  keyword,
  pagination,
  fetchList: fetchUsers,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<User, { page?: number; page_size?: number; keyword?: string }>(userAPI.list)

const createEmptyForm = () => ({
  id: 0,
  username: '',
  password: '',
  api_key: '',
  role: 'user',
  is_active: true
})

const { runAction, runConfirmedAction } = useAdminAction((key) => t(key))

const {
  dialogVisible,
  dialogMode,
  formData,
  openCreateDialog,
  closeDialog
} = useAdminCrudDialog(createEmptyForm)

const openEditDialog = async (row: User) => {
  dialogMode.value = 'edit'
  await runAction(
    () => userAPI.get(row.id),
    {
      errorFallbackText: 'admin.executeFailed',
      onSuccess: (response: any) => {
        if (!response.success) {
          throw new Error(response.msg || t('admin.executeFailed'))
        }
        const detail = response.data
        formData.value = {
          id: detail.id,
          username: detail.username,
          password: '',
          api_key: detail.api_key || '',
          role: detail.role,
          is_active: detail.is_active
        }
        dialogVisible.value = true
      }
    }
  ).catch(() => undefined)
}

const saveUser = async () => {
  if (!formData.value.username) {
    ElMessage.error(t('admin.usernameRequired'))
    return
  }

  if (dialogMode.value === 'create' && !formData.value.password) {
    ElMessage.error(t('admin.passwordRequired'))
    return
  }

  await runAction(
    async () => {
      if (dialogMode.value === 'create') {
        return userAPI.create({
          username: formData.value.username,
          new_password: formData.value.password,
          api_key: formData.value.api_key || undefined,
          role: formData.value.role,
          is_active: formData.value.is_active
        })
      }
      const updateData: any = {
        id: formData.value.id,
        username: formData.value.username,
        role: formData.value.role,
        is_active: formData.value.is_active,
        api_key: formData.value.api_key || ''
      }
      if (formData.value.password) {
        updateData.new_password = formData.value.password
      }
      return userAPI.update(updateData)
    },
    {
      successText: t('admin.saveSuccess'),
      errorFallbackText: 'admin.executeFailed',
      onSuccess: async () => {
        closeDialog()
        await fetchUsers()
      }
    }
  ).catch(() => undefined)
}

const deleteUser = async (row: User) => {
  await runConfirmedAction(
    {
      message: `${t('admin.confirmDelete')} (${row.username})?`,
      title: t('admin.confirm'),
      confirmButtonText: t('admin.hardDelete'),
      cancelButtonText: t('admin.softDelete'),
      distinguishCancelAndClose: true,
      type: 'warning'
    },
    () => userAPI.delete(row.id, true),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      onSuccess: async () => {
        await fetchUsers()
      },
      onCancel: async (cancelError) => {
        if (cancelError !== 'cancel') return
        await runAction(
          () => userAPI.delete(row.id, false),
          {
            successText: t('admin.deleteSuccess'),
            errorFallbackText: 'admin.deleteFailed',
            onSuccess: async () => {
              await fetchUsers()
            }
          }
        ).catch(() => undefined)
      }
    }
  ).catch(() => undefined)
}

onMounted(() => {
  fetchUsers().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
})
</script>

<template>
  <div class="user-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold">
        {{ t('admin.userManagement') }}
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
      :data="users"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" :label="t('admin.username')" min-width="120" />
      <el-table-column prop="api_key_masked" :label="t('admin.apiKey')" min-width="200">
        <template #default="{ row }">
          <code class="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
            {{ row.api_key_masked || '-' }}
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
      <el-table-column class-name="action-column" :label="t('admin.actions')" width="200" fixed="right">
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
        <el-button @click="closeDialog">{{ t('admin.cancel') }}</el-button>
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
