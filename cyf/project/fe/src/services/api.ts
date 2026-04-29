import { API_BASE_URL, createApiClient, getValidAccessToken } from '@/services/httpClient'

const api = createApiClient({
  requireAuthByDefault: true,
  publicPathPrefixes: ['/never_guess_my_usage/login', '/never_guess_my_usage/register']
})

export const authAPI = {
  login: (username: string, password: string) => {
    return api.post('/never_guess_my_usage/login', {
      user: username,
      password
    })
  },
  register: (username: string, password: string, apiKey?: string) => {
    const data: any = {
      username,
      password
    }
    if (apiKey !== undefined) {
      data.api_key = apiKey
    }
    return api.post('/never_guess_my_usage/register', data)
  }
}

export const fileAPI = {
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/never_guess_my_usage/download', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

const getAuthHeaders = async () => {
  const token = await getValidAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const chatAPI = {
  sendChat: (model: string, message: string, dialogMode: string = 'single', dialog?: any, dialogTitle?: string, maxResponseTokens?: number, systemPromptId?: number) => {
    const data: any = {
      model,
      dialog: message
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) data.dialog_title = dialogTitle
    if (maxResponseTokens) data.max_response_tokens = maxResponseTokens
    if (systemPromptId) data.system_prompt_id = systemPromptId
    return api.post('/never_guess_my_usage/split', data)
  },

  sendChatStream: async (
    model: string,
    message: string,
    onChunk: (content: string, done: boolean, finishReason?: string, response?: any) => void,
    dialogMode: string = 'single',
    dialog?: any,
    dialogTitle?: string,
    maxResponseTokens?: number,
    systemPromptId?: number,
    requestId?: string,
    signal?: AbortSignal
  ): Promise<void> => {
    const data: any = {
      model,
      dialog: message
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) data.dialog_title = dialogTitle
    if (maxResponseTokens) data.max_response_tokens = maxResponseTokens
    if (systemPromptId) data.system_prompt_id = systemPromptId
    if (requestId) data.request_id = requestId

    const headers = await getAuthHeaders()
    const response = await fetch(`${API_BASE_URL}/never_guess_my_usage/split_stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        ...headers
      },
      body: JSON.stringify(data),
      signal
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No reader available')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6)
          if (!dataStr.trim()) continue
          const parsedData = JSON.parse(dataStr)
          if (parsedData.error) {
            throw new Error(parsedData.error.msg || 'API请求失败')
          }
          onChunk(parsedData.content, parsedData.done, parsedData.finish_reason, parsedData)
          if (parsedData.done) return
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  cancelChatStream: (requestId: string) => {
    return api.post('/never_guess_my_usage/split_stream_cancel', {
      request_id: requestId
    })
  },

  sendImageGeneration: (model: string, prompt: string, dialogMode: string = 'single', dialog?: any, dialogTitle?: string, imageSize?: string, dialogId?: number, systemPromptId?: number) => {
    const data: any = {
      model,
      dialog: prompt
    }
    if (dialogMode === 'multi' && dialog) {
      data.dialog_mode = 'multi'
      data.dialog = JSON.stringify(dialog)
    }
    if (dialogTitle) data.dialog_title = dialogTitle
    if (imageSize) data.size = imageSize
    if (dialogId) data.dialogId = dialogId
    if (systemPromptId) data.system_prompt_id = systemPromptId
    return api.post('/never_guess_my_usage/split_pic', data)
  },

  getDialogHistory: () => api.post('/never_guess_my_usage/split_his', {}),

  getDialogContent: (dialogId: number) => api.post('/never_guess_my_usage/split_his_content', { dialogId }),

  deleteDialogs: (dialogIds: number[]) => api.post('/never_guess_my_usage/split_his_delete', {
    dialog_ids: JSON.stringify(dialogIds)
  }),

  getModels: () => api.get('/never_guess_my_usage/models'),

  getGroupedModels: () => api.post('/never_guess_my_usage/models/grouped', {}),

  getUsage: () => api.post('/never_guess_my_usage/usage', {}),

  getSystemPromptsByGroup: () => api.get('/never_guess_my_usage/system_prompts_by_group'),

  updateDialogTitle: (dialogId: number, newTitle: string) => api.post('/never_guess_my_usage/update_dialog_title', {
    dialog_id: dialogId,
    new_title: newTitle
  }),

  resetPassword: (currentPassword: string, newPassword: string, newApiKey?: string) => {
    const data: any = {
      current_password: currentPassword,
      new_password: newPassword
    }
    if (newApiKey !== undefined) {
      data.new_api_key = newApiKey
    }
    return api.post('/never_guess_my_usage/del_password', data)
  },

  getNotifications: () => api.get('/never_guess_my_usage/notifications'),

  saveBrowserConf: (browserConf: string) => api.post('/never_guess_my_usage/browser_conf/save', {
    browser_conf: browserConf
  }),

  getBrowserConf: () => api.post('/never_guess_my_usage/browser_conf/get', {})
}

export type ChatApiMode = 'v1' | 'v2'
export type RuntimeChatMode = 'v1' | 'v2'

export const conversationV2API = {
  createMaster: (payload: {
    title: string
    session_type: 'single' | 'multi_compare'
    active_models: string[]
  }) => api.post('/never_guess_my_usage/conversation/master/create', payload),

  listMaster: (page: number = 1, pageSize: number = 50) => api.post('/never_guess_my_usage/conversation/master/list', {
    page,
    page_size: pageSize
  }),

  getMasterDetail: (masterId: number) => api.post('/never_guess_my_usage/conversation/master/detail', {
    master_id: masterId
  }),

  addModel: (masterId: number, modelId: string) => api.post('/never_guess_my_usage/conversation/master/add_model', {
    master_id: masterId,
    model_id: modelId
  }),

  removeModel: (masterId: number, modelId: string) => api.post('/never_guess_my_usage/conversation/master/remove_model', {
    master_id: masterId,
    model_id: modelId
  }),

  deleteMasters: (masterIds: number[]) => api.post('/never_guess_my_usage/conversation/master/delete', {
    master_ids: masterIds
  }),

  sendRound: (payload: {
    master_id: number
    user_prompt: string
    attachments?: any[]
    system_prompt_id?: number
    max_response_tokens?: number
  }) => api.post('/never_guess_my_usage/conversation/round/send', payload),

  createRound: (payload: {
    master_id: number
    user_prompt: string
    attachments?: any[]
    system_prompt_id?: number
    max_response_tokens?: number
  }) => api.post('/never_guess_my_usage/conversation/round/create', payload),

  streamCell: async (
    payload: {
      round_id: number
      child_id: number
      system_prompt_id?: number
      max_response_tokens?: number
      request_id?: string
    },
    onChunk: (evt: any) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const headers = await getAuthHeaders()
    const response = await fetch(`${API_BASE_URL}/never_guess_my_usage/conversation/cell/stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        ...headers
      },
      body: JSON.stringify(payload),
      signal
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader available')
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6)
          if (!dataStr.trim()) continue
          const parsedData = JSON.parse(dataStr)
          onChunk(parsedData)
          if (parsedData.done) return
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  cancelStreamCell: (requestId: string) => api.post('/never_guess_my_usage/conversation/cell/stream_cancel', {
    request_id: requestId
  }),

  retryCell: (payload: {
    round_id: number
    child_id: number
    system_prompt_id?: number
    max_response_tokens?: number
  }) => api.post('/never_guess_my_usage/conversation/cell/retry', payload),

  migrateLegacyDialogs: (payload: {
    dialog_ids: number[]
    target_models?: string[]
  }) => api.post('/never_guess_my_usage/conversation/legacy/migrate', payload)
}

export const chatModeAPI = {
  probeV2: async (): Promise<boolean> => {
    try {
      const response: any = await conversationV2API.listMaster(1, 1)
      return !!response?.success
    } catch {
      return false
    }
  }
}

export default api
