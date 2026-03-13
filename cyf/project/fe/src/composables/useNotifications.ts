import { ref } from 'vue'
import { chatAPI } from '@/services/api'

export interface Notification {
  id: number;
  title: string;
  content: string;
  publish_time: string;
  status?: string;
  priority?: number;
  created_at?: string;
  updated_at?: string;
}

const NOTIFICATION_LATEST_ID_KEY = 'latestNotificationId'

const getStoredLatestNotificationId = () => {
  const raw = localStorage.getItem(NOTIFICATION_LATEST_ID_KEY)
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

const getLatestNotificationId = (list: Notification[]) => {
  return list.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0)
}

const mapNotificationsFromResponse = (response: any): Notification[] => {
  if (response && response.data && Array.isArray(response.data.list)) {
    return response.data.list.map((item: any) => ({
      id: item.id,
      title: item.title,
      content: item.content,
      publish_time: item.publish_time,
      status: item.status,
      priority: item.priority,
      created_at: item.created_at,
      updated_at: item.updated_at
    }))
  }
  return []
}

export const useNotifications = () => {
  const notifications = ref<Notification[]>([])
  const notificationsLoading = ref(false)
  const hasNewNotifications = ref(false)
  const latestNotificationId = ref(0)

  const fetchNotifications = async () => {
    notificationsLoading.value = true
    try {
      const response = await chatAPI.getNotifications()
      const list = mapNotificationsFromResponse(response)
      notifications.value = list

      const latestId = getLatestNotificationId(list)
      latestNotificationId.value = latestId
      const storedId = getStoredLatestNotificationId()
      hasNewNotifications.value = latestId > storedId
    } catch (error) {
      console.error('Error fetching notifications:', error)
      notifications.value = []
      hasNewNotifications.value = false
    } finally {
      notificationsLoading.value = false
    }
  }

  const markNotificationsRead = () => {
    if (latestNotificationId.value > 0) {
      localStorage.setItem(NOTIFICATION_LATEST_ID_KEY, latestNotificationId.value.toString())
      hasNewNotifications.value = false
    }
  }

  return {
    notifications,
    notificationsLoading,
    hasNewNotifications,
    fetchNotifications,
    markNotificationsRead
  }
}
