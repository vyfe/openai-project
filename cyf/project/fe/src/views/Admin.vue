<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/layout/AppHeader.vue'
import { Setting } from '@element-plus/icons-vue'
import ModelMetaTable from '@/components/admin/ModelMetaTable.vue'
import SystemPromptTable from '@/components/admin/SystemPromptTable.vue'
import UserTable from '@/components/admin/UserTable.vue'
import NotificationTable from '@/components/admin/NotificationTable.vue'
import TestLimitTable from '@/components/admin/TestLimitTable.vue'
import SqlExecutor from '@/components/admin/SqlExecutor.vue'
import RuntimeOverview from '@/components/admin/RuntimeOverview.vue'
import { useThemeManager } from '@/composables/useThemeManager'

const { t } = useI18n()
const activeTab = ref('models')
const loadedTabs = ref(new Set<string>(['models']))
const { isDarkTheme, initThemeManager } = useThemeManager()

const tabs = [
  { name: 'models', label: t('admin.modelManagement') },
  { name: 'prompts', label: t('admin.promptManagement') },
  { name: 'users', label: t('admin.userManagement') },
  { name: 'notifications', label: t('admin.notificationManagement') },
  { name: 'limits', label: t('admin.limitManagement') },
  { name: 'sql', label: t('admin.sqlExecute') },
  { name: 'observability', label: t('admin.observability') }
]

onMounted(() => {
  initThemeManager()
})

watch(activeTab, (tab) => {
  loadedTabs.value.add(tab)
})
</script>

<template>
  <div class="admin-page min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col" :class="{ dark: isDarkTheme, 'admin-dark': isDarkTheme }">
    <!-- Header -->
    <AppHeader :title="t('admin.title')" :logo-icon="Setting" variant="admin">
    </AppHeader>

    <!-- Content -->
    <main class="admin-main flex-1 p-4 sm:p-6 lg:p-8">
      <div class="admin-shell max-w-7xl mx-auto">
        <el-tabs v-model="activeTab" class="admin-tabs">
          <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name" :label="tab.label">
            <ModelMetaTable v-if="tab.name === 'models' && loadedTabs.has('models')" />
            <SystemPromptTable v-if="tab.name === 'prompts' && loadedTabs.has('prompts')" />
            <UserTable v-if="tab.name === 'users' && loadedTabs.has('users')" />
            <NotificationTable v-if="tab.name === 'notifications' && loadedTabs.has('notifications')" />
            <TestLimitTable v-if="tab.name === 'limits' && loadedTabs.has('limits')" />
            <SqlExecutor v-if="tab.name === 'sql' && loadedTabs.has('sql')" />
            <RuntimeOverview v-if="tab.name === 'observability' && loadedTabs.has('observability')" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </main>
  </div>
</template>

<style>
@import '@/styles/admin.css';
</style>
