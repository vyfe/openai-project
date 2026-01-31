<template>
  <div class="w-96 bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-blue-200/30 h-[350px] ml-6 p-6 flex flex-col">
    <div class="flex items-center mb-4">
      <h2 class="text-lg font-bold text-indigo-600 flex items-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
        </svg>
        通知中心
      </h2>
    </div>

    <div class="flex-1 overflow-y-auto max-h-[calc(100%-80px)]">
      <div v-if="loading" class="flex justify-center items-center h-32">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>

      <div v-else-if="notifications.length === 0" class="text-center text-gray-500 py-8">
        暂无通知
      </div>

      <ul v-else class="space-y-3">
        <li
          v-for="(notification, index) in notifications"
          :key="notification.id || index"
          class="p-3 bg-white/80 rounded-lg border border-gray-200/50 hover:bg-indigo-50/80 transition-colors cursor-pointer"
        >
          <div class="flex items-start">
            <div class="flex-shrink-0 mt-0.5">
              <div class="w-2 h-2 bg-indigo-500 rounded-full"></div>
            </div>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-gray-900">{{ notification.title }}</h3>
              <p class="mt-1 text-xs text-gray-500">{{ notification.content }}</p>
              <p class="mt-1 text-xs text-gray-400">{{ formatDate(notification.publish_time) }}</p>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <div class="mt-4 pt-4 border-t border-gray-200/30 text-xs text-gray-500 text-center">
      最近 {{ notifications.length }} 条通知
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { chatAPI } from '@/services/api'

interface Notification {
  id: number;
  title: string;
  content: string;
  publish_time: string; // 后端返回的时间字段名为publish_time
  status?: string;
  priority?: number;
  created_at?: string;
  updated_at?: string;
}

const notifications = ref<Notification[]>([])
const loading = ref(true)

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateString
  }
}

const fetchNotifications = async () => {
  try {
    loading.value = true

    const response = await chatAPI.getNotifications()

    // 由于API响应类型未定义success属性，我们假设返回的数据是正确的格式
    // 检查是否有数据返回
    if (response && response.data && Array.isArray(response.data.list)) {
      // 将后端返回的字段映射到组件使用的字段
      notifications.value = response.data.list.map((item: any) => ({
        id: item.id,
        title: item.title,
        content: item.content,
        publish_time: item.publish_time, // 使用后端实际的时间字段
        status: item.status,
        priority: item.priority,
        created_at: item.created_at,
        updated_at: item.updated_at
      }))
    } else {
      notifications.value = []
    }
  } catch (error) {
    console.error('Error fetching notifications:', error)
    notifications.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchNotifications()
})
</script>

<style scoped>
/* 为深色模式添加样式 */
@media (prefers-color-scheme: dark) {
  .bg-white\/90 {
    background-color: rgba(34, 34, 34, 0.9) !important;
  }

  .bg-white\/80 {
    background-color: rgba(45, 45, 45, 0.8) !important;
  }

  .hover\:bg-indigo-50\/80:hover {
    background-color: rgba(99, 102, 241, 0.2) !important;
  }

  .text-gray-900 {
    color: #f0f0f0 !important;
  }

  .text-gray-500 {
    color: #a0a0a0 !important;
  }

  .text-gray-400 {
    color: #808080 !important;
  }

  .border-gray-200\/50 {
    border-color: rgba(100, 100, 100, 0.5) !important;
  }

  .border-t.border-gray-200\/30 {
    border-top: 1px solid rgba(100, 100, 100, 0.3) !important;
  }
}
</style>