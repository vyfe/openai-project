<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import ModelMetaTable from '@/components/admin/ModelMetaTable.vue'
import SystemPromptTable from '@/components/admin/SystemPromptTable.vue'
import UserTable from '@/components/admin/UserTable.vue'
import NotificationTable from '@/components/admin/NotificationTable.vue'
import TestLimitTable from '@/components/admin/TestLimitTable.vue'
import SqlExecutor from '@/components/admin/SqlExecutor.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const activeTab = ref('models')

const tabs = [
  { name: 'models', label: t('admin.modelManagement') },
  { name: 'prompts', label: t('admin.promptManagement') },
  { name: 'users', label: t('admin.userManagement') },
  { name: 'notifications', label: t('admin.notificationManagement') },
  { name: 'limits', label: t('admin.limitManagement') },
  { name: 'sql', label: t('admin.sqlExecute') }
]

const goBack = () => {
  router.push('/chat')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
    <!-- Header -->
    <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 shadow-sm">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <button
            @click="goBack"
            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <svg class="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <h1 class="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
            {{ t('admin.title') }}
          </h1>
        </div>
        <div class="text-sm text-gray-500 dark:text-gray-400">
          {{ authStore.user }}
        </div>
      </div>
    </header>

    <!-- Content -->
    <main class="flex-1 p-4 sm:p-6 lg:p-8">
      <div class="max-w-7xl mx-auto">
        <el-tabs v-model="activeTab" type="card" class="admin-tabs">
          <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name" :label="tab.label">
            <ModelMetaTable v-if="tab.name === 'models'" />
            <SystemPromptTable v-if="tab.name === 'prompts'" />
            <UserTable v-if="tab.name === 'users'" />
            <NotificationTable v-if="tab.name === 'notifications'" />
            <TestLimitTable v-if="tab.name === 'limits'" />
            <SqlExecutor v-if="tab.name === 'sql'" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </main>
  </div>
</template>

<style scoped>
@import '@/styles/admin.css';
</style>
