<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { userAPI } from '@/services/adminApi'
import { useAdminPagedList } from '@/composables/useAdminPagedList'
import { useAdminCrudDialog } from '@/composables/useAdminCrudDialog'
import { useAdminAction } from '@/composables/useAdminAction'
import { Plus } from '@element-plus/icons-vue'
import { BUSINESS_ROLE_ORDER, type BusinessRole } from '@/auth/permissions'
import { APP_META } from '@/auth/apps'

const { t } = useI18n()

interface User {
  id: number
  username: string
  api_key_masked: string
  api_key?: string
  role: string
  roles: string[]
  is_active: boolean
  deleted?: boolean
  created_at: string
  updated_at: string
}

const roleFilter = ref('')

const {
  items: users,
  loading,
  keyword,
  pagination,
  fetchList: fetchUsers,
  search: handleSearch,
  changePage: handlePageChange,
  changePageSize: handlePageSizeChange
} = useAdminPagedList<User, { page?: number; page_size?: number; keyword?: string; role?: string }>(
  userAPI.list,
  () => ({ role: roleFilter.value || undefined })
)

interface UserForm {
  id: number
  username: string
  password: string
  api_key: string
  roles: BusinessRole[]
  isAdmin: boolean
  is_active: boolean
}

const createEmptyForm = (): UserForm => ({
  id: 0,
  username: '',
  password: '',
  api_key: '',
  // 管理员创建普通账号默认勾选聊天
  roles: ['chat'],
  isAdmin: false,
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

/** 角色标签：管理员显示 admin，业务角色显示各自名称。 */
const roleTags = (roles: string[]) => (roles && roles.length ? roles : [])

const roleLabel = (role: string) => {
  if (role === 'admin') return t('admin.adminRole')
  return t(APP_META[role as BusinessRole]?.labelKey || role)
}

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
        const roles: string[] = Array.isArray(detail.roles) ? detail.roles : []
        const isAdmin = roles.includes('admin')
        formData.value = {
          id: detail.id,
          username: detail.username,
          password: '',
          api_key: detail.api_key || '',
          roles: isAdmin ? ['chat'] : (roles.filter((role) => BUSINESS_ROLE_ORDER.includes(role as BusinessRole)) as BusinessRole[]),
          isAdmin,
          is_active: detail.is_active
        }
        dialogVisible.value = true
      }
    }
  ).catch(() => undefined)
}

/** 关闭管理员开关后回到聊天默认值，允许重新组合。 */
const onAdminToggle = (value: boolean) => {
  if (!value && !formData.value.roles.length) {
    formData.value.roles = ['chat']
  }
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

  if (!formData.value.isAdmin && !formData.value.roles.length) {
    ElMessage.error(t('admin.roleRequired'))
    return
  }

  const roles = formData.value.isAdmin ? ['admin'] : [...formData.value.roles]

  await runAction(
    async () => {
      if (dialogMode.value === 'create') {
        return userAPI.create({
          username: formData.value.username,
          new_password: formData.value.password,
          api_key: formData.value.api_key || undefined,
          roles,
          is_active: formData.value.is_active
        })
      }
      const updateData: any = {
        id: formData.value.id,
        username: formData.value.username,
        roles,
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
      message: `${t('admin.deleteUserConfirm')} (${row.username})`,
      title: t('admin.confirm'),
      confirmButtonText: t('admin.delete'),
      cancelButtonText: t('admin.cancel'),
      distinguishCancelAndClose: true,
      type: 'warning'
    },
    () => userAPI.delete(row.id),
    {
      successText: t('admin.deleteSuccess'),
      errorFallbackText: 'admin.deleteFailed',
      onSuccess: async () => {
        await fetchUsers()
      }
    }
  ).catch(() => undefined)
}

const onRoleFilterChange = () => {
  handleSearch().catch((error: any) => {
    ElMessage.error(error.response?.data?.msg || error.message || t('admin.loading'))
  })
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
        <el-select
          v-model="roleFilter"
          clearable
          :placeholder="t('admin.roleFilter')"
          style="width: 160px"
          @change="onRoleFilterChange"
        >
          <el-option :label="t('admin.roleFilterAll')" value="" />
          <el-option label="chat" value="chat" />
          <el-option label="quant" value="quant" />
          <el-option label="sound" value="sound" />
          <el-option :label="t('admin.adminRole')" value="admin" />
        </el-select>
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
      empty-text="暂无用户"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" :label="t('admin.username')" min-width="120" />
      <el-table-column prop="api_key_masked" :label="t('admin.apiKey')" min-width="200">
        <template #default="{ row }">
          <code class="admin-code-chip">{{ row.api_key_masked || '-' }}</code>
        </template>
      </el-table-column>
      <el-table-column :label="t('admin.roles')" min-width="180">
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="role in roleTags(row.roles)"
              :key="role"
              :type="role === 'admin' ? 'danger' : 'primary'"
              size="small"
            >
              {{ roleLabel(role) }}
            </el-tag>
            <span v-if="!roleTags(row.roles).length" class="admin-code-chip">-</span>
          </div>
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

        <el-form-item :label="t('admin.adminRole')">
          <el-switch v-model="formData.isAdmin" @change="onAdminToggle" />
        </el-form-item>

        <el-form-item :label="t('admin.businessRoles')">
          <el-checkbox-group v-model="formData.roles" :disabled="formData.isAdmin">
            <el-checkbox v-for="role in BUSINESS_ROLE_ORDER" :key="role" :value="role">
              {{ t(APP_META[role].labelKey) }}
            </el-checkbox>
          </el-checkbox-group>
          <p v-if="formData.isAdmin" class="admin-role-hint">{{ t('admin.adminRoleEnabledHint') }}</p>
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

.admin-role-hint {
  margin: 6px 0 0;
  font-size: 12px;
  opacity: 0.75;
}
</style>
