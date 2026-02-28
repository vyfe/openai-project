<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { notificationAPI } from '@/services/adminApi'

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

const notifications = ref<Notification[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref({
  id: 0,
  title: '',
  content: '',
  publish_time: '',
  priority: 0,
  status: 'active'
})

const fetchNotifications = async () => {
  loading.value = true
  try {
    const response = await notificationAPI.list()
    if (response.success) {
      notifications.value = response.data || []
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
    title: '',
    content: '',
    publish_time: new Date().toISOString().slice(0, 10),
    priority: 0,
    status: 'active'
  }
  dialogVisible.value = true
}

const openEditDialog = (row: Notification) => {
  dialogMode.value = 'edit'
  formData.value = { ...row }
  dialogVisible.value = true
}

const saveNotification = async () => {
  if (!formData.value.title || !formData.value.content) {
    ElMessage.error(formData.value.title ? t('admin.contentRequired') : t('admin.titleRequired'))
    return
  }

  try {
    if (dialogMode.value === 'create') {
      const response = await notificationAPI.create(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchNotifications()
      }
    } else {
      const response = await notificationAPI.update(formData.value)
      if (response.success) {
        ElMessage.success(t('admin.saveSuccess'))
        dialogVisible.value = false
        fetchNotifications()
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('admin.executeFailed'))
  }
}

const deleteNotification = async (row: Notification) => {
  try {
    await ElMessageBox.confirm(
      `${t('admin.confirmDelete')} (${row.title})?`,
      t('admin.confirm'),
      {
        confirmButtonText: t('admin.yes'),
        cancelButtonText: t('admin.no'),
        type: 'warning'
      }
    )
    const response = await notificationAPI.delete(row.id)
    if (response.success) {
      ElMessage.success(t('admin.deleteSuccess'))
      fetchNotifications()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('admin.deleteFailed'))
    }
  }
}

onMounted(() => {
  fetchNotifications()
})
</script>

<template>
  <div class="notification-table">
    <div class="mb-4 flex justify-between items-center">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
        {{ t('admin.notificationManagement') }}
      </h2>
      <el-button type="primary" @click="openCreateDialog" :icon="Plus">
        {{ t('admin.create') }}
      </el-button>
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
        <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
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
