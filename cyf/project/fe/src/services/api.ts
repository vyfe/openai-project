import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

// 后端实际API端口为39997，不需要额外的/api前缀
const API_BASE_URL = 'http://localhost:39997'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 增加超时时间以应对可能较慢的AI响应
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  }
})

// 请求拦截器 - 自动注入用户凭据并将数据转换为form格式
api.interceptors.request.use(
  (config) => {
    // 获取认证信息并注入到请求参数中
    const authStore = useAuthStore()
    const credentials = authStore.getCredentials()

    // 将凭据注入到参数中
    if (credentials.user) {
      if (config.params) {
        config.params.user = credentials.user
      } else {
        config.params = { user: credentials.user }
      }
    }

    if (credentials.password) {
      if (config.params) {
        config.params.password = credentials.password
      } else {
        config.params = { ...config.params, password: credentials.password }
      }
    }

    // 如果数据是对象，将其转换为form格式
    if (config.data && typeof config.data === 'object' && !config.data instanceof FormData) {
      const formData = new URLSearchParams();
      for (const key in config.data) {
        if (config.data[key] !== undefined && config.data[key] !== null) {
          formData.append(key, config.data[key]);
        }
      }
      config.data = formData.toString();
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 用户相关API - 适配后端实际API
export const authAPI = {
  login: (username: string, password: string) => {
    return api.post('/never_guess_my_usage/login', {
      user: username,
      password: password
    })
  }
}

// 文件上传API - 适配后端实际API
export const fileAPI = {
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    // 后端实际文件上传接口，Content-Type由浏览器自动设置
    return axios.post(`${API_BASE_URL}/never_guess_my_usage/download`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

// 聊天API - 适配后端实际API
export const chatAPI = {
  // 普通聊天接口
  sendChat: (model: string, message: string, dialogMode: string = 'single', dialog?: any) => {
    const data: any = {
      model,
      dialog: message
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    return api.post('/never_guess_my_usage/split', data)
  },

  // 图片生成接口
  sendImageGeneration: (model: string, prompt: string, dialogMode: string = 'single', dialog?: any) => {
    const data: any = {
      model,
      dialog: prompt
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    return api.post('/never_guess_my_usage/split_pic', data)
  },

  // 获取对话历史列表
  getDialogHistory: (model: string) => {
    return api.post('/never_guess_my_usage/split_his', {
      model
    })
  },

  // 获取特定对话内容
  getDialogContent: (dialogId: number) => {
    return api.post('/never_guess_my_usage/split_his_content', {
      dialogId
    })
  }
}

export default api