<template>
  <div v-if="!isModal" :class="[
  'rounded-2xl shadow-xl border h-auto ml-6 p-4 flex flex-col max-w-full',
  isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
]">
    <div class="flex items-center mb-4">
      <h2 :class="[
        'text-lg font-bold flex items-center',
        isDarkTheme ? 'text-indigo-400' : 'text-indigo-600'
      ]">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
        </svg>
        通知中心
      </h2>
    </div>

    <div class="flex-1 overflow-y-auto max-h-[calc(100%-80px)]">
      <div v-if="loading" class="flex justify-center items-center h-32">
        <div :class="[
          'animate-spin rounded-full h-8 w-8 border-b-2',
          isDarkTheme ? 'border-indigo-400' : 'border-indigo-600'
        ]"></div>
      </div>

      <div v-else-if="notifications.length === 0" :class="[
        'text-center py-8',
        isDarkTheme ? 'text-gray-400' : 'text-gray-500'
      ]">
        暂无通知
      </div>

      <ul v-else class="space-y-3">
        <li
          v-for="(notification, index) in notifications"
          :key="notification.id || index"
          :class="[
            'p-3 rounded-lg border transition-colors cursor-pointer',
            isDarkTheme ? 'bg-gray-700 border-gray-600 hover:bg-gray-600/80' : 'bg-white border-gray-200 hover:bg-indigo-50'
          ]"
        >
          <div class="flex items-start">
            <div class="flex-shrink-0 mt-0.5">
              <div :class="[
                'w-2 h-2 rounded-full',
                isDarkTheme ? 'bg-indigo-400' : 'bg-indigo-500'
              ]"></div>
            </div>
            <div class="ml-3">
              <h3 :class="[
                'text-sm font-medium',
                isDarkTheme ? 'text-gray-100' : 'text-gray-900'
              ]">{{ notification.title }}</h3>
              <p :class="[
                'mt-1 text-xs',
                isDarkTheme ? 'text-gray-400' : 'text-gray-500'
              ]">{{ notification.content }}</p>
              <p :class="[
                'mt-1 text-xs',
                isDarkTheme ? 'text-gray-500' : 'text-gray-400'
              ]">{{ formatDate(notification.publish_time) }}</p>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <div :class="[
      'mt-4 pt-4 border-t text-xs text-center',
      isDarkTheme ? 'border-gray-700 text-gray-400' : 'border-gray-200 text-gray-500'
    ]">
      最近 {{ notifications.length }} 条通知
    </div>
  </div>

  <!-- 弹窗模式 -->
  <div v-else :class="[
    'rounded-lg shadow-xl border max-w-md w-full z-20',
    isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
  ]">
    <div :class="[
      'flex items-center justify-between p-4 border-b',
      isDarkTheme ? 'border-gray-700' : 'border-gray-200'
    ]">
      <h2 :class="[
        'text-lg font-bold flex items-center',
        isDarkTheme ? 'text-indigo-400' : 'text-indigo-600'
      ]">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
        </svg>
        通知中心
      </h2>
      <button @click="$emit('close')" :class="[
        'hover:text-gray-700',
        isDarkTheme ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500'
      ]">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <div class="p-4 max-h-96 overflow-y-auto">
      <div v-if="loading" class="flex justify-center items-center h-32">
        <div :class="[
          'animate-spin rounded-full h-8 w-8 border-b-2',
          isDarkTheme ? 'border-indigo-400' : 'border-indigo-600'
        ]"></div>
      </div>

      <div v-else-if="notifications.length === 0" :class="[
        'text-center py-8',
        isDarkTheme ? 'text-gray-400' : 'text-gray-500'
      ]">
        暂无通知
      </div>

      <ul v-else class="space-y-3">
        <li
          v-for="(notification, index) in notifications"
          :key="notification.id || index"
          :class="[
            'p-3 rounded-lg border transition-colors cursor-pointer',
            isDarkTheme ? 'bg-gray-700 border-gray-600 hover:bg-gray-600/80' : 'bg-white border-gray-200 hover:bg-indigo-50'
          ]"
        >
          <div class="flex items-start">
            <div class="flex-shrink-0 mt-0.5">
              <div :class="[
                'w-2 h-2 rounded-full',
                isDarkTheme ? 'bg-indigo-400' : 'bg-indigo-500'
              ]"></div>
            </div>
            <div class="ml-3">
              <h3 :class="[
                'text-sm font-medium',
                isDarkTheme ? 'text-gray-100' : 'text-gray-900'
              ]">{{ notification.title }}</h3>
              <p :class="[
                'mt-1 text-xs',
                isDarkTheme ? 'text-gray-400' : 'text-gray-500'
              ]">{{ notification.content }}</p>
              <p :class="[
                'mt-1 text-xs',
                isDarkTheme ? 'text-gray-500' : 'text-gray-400'
              ]">{{ formatDate(notification.publish_time) }}</p>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <div :class="[
      'p-3 border-t text-xs text-center',
      isDarkTheme ? 'border-gray-700 text-gray-400' : 'border-gray-200 text-gray-500'
    ]">
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

const props = defineProps<{
  isModal?: boolean;
  isDarkTheme?: boolean;
}>()

const emit = defineEmits(['close'])

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

<style>
/* NotificationPanel组件样式已通过Tailwind CSS和项目全局CSS管理 */
</style>