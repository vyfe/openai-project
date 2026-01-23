import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

// 根据环境决定API端口，开发环境使用localhost:39997，生产环境使用线上地址
const API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:39997'
  : 'http://aichat.609088523.xyz:39996'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分钟超时 (原为 120000)
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
    if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
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
  sendChat: (model: string, message: string, dialogMode: string = 'single', dialog?: any, dialogTitle?: string) => {
    const data: any = {
      model,
      dialog: message
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) {
      data.dialog_title = dialogTitle
    }
    return api.post('/never_guess_my_usage/split', data)
  },

  // 流式聊天接口
  sendChatStream: async (
    model: string,
    message: string,
    onChunk: (content: string, done: boolean) => void,
    dialogMode: string = 'single',
    dialog?: any,
    dialogTitle?: string
  ): Promise<void> => {
    const data: any = {
      model,
      dialog: message
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) {
      data.dialog_title = dialogTitle
    }

    // 使用fetch API来处理SSE流式响应
    const params = new URLSearchParams({
      ...data,
      user: useAuthStore().user || '',
      password: useAuthStore().password || ''
    });

    const response = await fetch(`${API_BASE_URL}/never_guess_my_usage/split_stream?${params}`, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No reader available');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按行分割缓冲区
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留最后一行，可能是不完整的

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const dataStr = line.slice(6); // 移除 'data: ' 前缀
              if (dataStr.trim()) {
                const parsedData = JSON.parse(dataStr);

                // 检查是否存在错误
                if (parsedData.error) {
                  // 如果存在错误信息，抛出错误
                  throw new Error(parsedData.error.msg || 'API请求失败');
                }

                onChunk(parsedData.content, parsedData.done);

                if (parsedData.done) {
                  return; // 结束读取
                }
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
              // 如果解析错误或遇到异常，也需要把错误信息传出去
              if (e instanceof Error) {
                throw e; // 重新抛出错误，让调用方处理
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  // 图片生成接口
  sendImageGeneration: (model: string, prompt: string, dialogMode: string = 'single', dialog?: any, dialogTitle?: string) => {
    const data: any = {
      model,
      dialog: prompt
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) {
      data.dialog_title = dialogTitle
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
  },

  // 获取可用模型列表
  getModels: () => {
    return api.get('/never_guess_my_usage/models')
  },

  // 获取分组的模型列表
  getGroupedModels: () => {
    return api.get('/never_guess_my_usage/models/grouped')
  }
}

export default api